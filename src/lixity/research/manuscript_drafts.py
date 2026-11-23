"""Deterministic, read-only dossier draft synthesis from manuscript analysis signals."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from textwrap import shorten
from typing import Any, Literal, TypedDict, get_args
from unicodedata import normalize
from urllib.parse import quote

from ..characters import (
    Names,
    _name_pattern,
    presence_report,
    resolve_character_settings,
)
from ..dossier_draft_settings import parse_location_names, resolve_dossier_draft_settings
from ..format import num, pct
from ..language import get_language_profile
from ..markdown_parser import CountedChapterPassage, counted_chapter_passages, split_chapters
from ..pipeline import resolve_document_config
from ..scenes import SceneSettingsError, scene_report
from ..workspace_labels import workspace_labels_for
from .character_evidence import (
    _auto_character_names,
    _chapter_passages,
    character_dialogue_evidence,
    character_dialogue_markdown,
    character_overview_markdown,
)
from .dossier_analysis import mark_character_analysis
from .dossier_markdown import (
    chapter_heading,
    chapter_line_range,
    chapter_mention_table,
    dossier_quote,
    name_mentions_summary,
)
from .limits import MAX_DOSSIER_BODY_CHARS

DRAFT_SCHEMA = "manuscript-dossier-drafts/1"
DraftKind = Literal["all", "character", "scene", "location"]
DRAFT_KINDS = get_args(DraftKind)
DRAFT_KIND_CHOICES = ", ".join((*DRAFT_KINDS[:-1], f"or {DRAFT_KINDS[-1]}"))
_QUOTE_WIDTH = 180

# Repeated wording with a directional cue can suggest a place. Ordinary
# locative prepositions alone are too broad, especially for German nouns.
_LOCATION_CUES: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    "de": (("nach", "richtung"), ("in", "im", "am", "an", "bei", "vor", "aus")),
    "en": (("to", "toward", "towards"), ("in", "at", "from", "near")),
    "es": (("hacia",), ("a", "en", "desde", "cerca de")),
    "fr": (("vers",), ("à", "dans", "depuis", "près de")),
    "it": (("verso",), ("a", "in", "da", "vicino a")),
    "nl": (("naar",), ("in", "bij", "van", "nabij")),
    "pt": (("para", "rumo a"), ("em", "de", "perto de")),
}
_LOCATION_WORD = r"[^\W\d_]+(?:-[^\W\d_]+)*"


class _FirstHit(TypedDict):
    chapter: int
    chapter_title: str
    line: int
    end_line: int
    quote: str


class _LocationSignal(TypedDict):
    qualifying_mentions: int
    reason_hit: _FirstHit


def _draft_title(kind: str, name: str, labels: Mapping[str, str]) -> str:
    # Keep the name after the first colon for the saved character binding.
    return labels["research_dossier_draft_title"].format(kind=kind, name=name)


def _name_key(name: str) -> str:
    return normalize("NFC", name.casefold())


def _named_draft_id(kind: str, name: str) -> dict[str, str]:
    key = _name_key(name)
    identifier = f"{kind}:{quote(key, safe='')}"
    old_slug = re.sub(r"[^a-z0-9]+", "-", name.casefold()).strip("-") or "entry"
    legacy = f"{kind}:{old_slug}"
    return {"id": identifier, **({"legacy_id": legacy} if legacy != identifier else {})}


def _configured_location_names(settings: Mapping[str, Any]) -> list[str] | None:
    # The direct-text API previously accepted places as a synonym. The project
    # configuration exposes locations as its canonical key.
    if "locations" not in settings and "places" not in settings:
        return None
    return parse_location_names(settings.get("locations", settings.get("places")))


def _suggested_locations(
    chapters: Sequence[tuple[int, str, list[CountedChapterPassage]]], language: str,
    excluded_names: set[str], *, limit: int,
) -> dict[str, _LocationSignal]:
    directional, local = _LOCATION_CUES.get(language, _LOCATION_CUES["en"])
    cue = "|".join(re.escape(value) for value in (*directional, *local))
    pattern = re.compile(
        rf"(?<!\w)(?P<cue>(?i:{cue}))\s+(?P<name>{_LOCATION_WORD})"
        rf"(?=(?:[ \t]+(?P<following>{_LOCATION_WORD}))?)"
    )
    stopwords = get_language_profile(language).stopwords | excluded_names
    found: dict[str, str] = {}
    counts: Counter[str] = Counter()
    directional_hits: dict[str, _FirstHit] = {}
    for number, title, paragraphs in chapters:
        for paragraph in paragraphs:
            for match in pattern.finditer(paragraph.text):
                first, second = match["name"], match["following"]
                if len(first) < 3 or not first[0].isupper() or _name_key(first) in stopwords:
                    continue
                two_words = second and second[0].isupper() and _name_key(second) not in stopwords
                candidate = f"{first} {second}" if two_words else first
                key = _name_key(candidate)
                if key in stopwords:
                    continue
                found.setdefault(key, candidate)
                counts[key] += 1
                if key not in directional_hits and match["cue"].casefold() in directional:
                    edge = match.end("following" if two_words else "name")
                    directional_hits[key] = {
                        "chapter": number, "chapter_title": title,
                        "line": paragraph.start_line, "end_line": paragraph.end_line,
                        "quote": _short_excerpt(paragraph.text, (match.start("cue"), edge)),
                    }
    eligible = (key for key, count in counts.items() if count > 1 and key in directional_hits)
    return {
        found[key]: {"qualifying_mentions": counts[key], "reason_hit": directional_hits[key]}
        for key in sorted(eligible, key=lambda key: (-counts[key], key))[:limit]
    }


def _short_excerpt(text: str, match: tuple[int, int] | None = None) -> str:
    if len(text) <= _QUOTE_WIDTH:
        return text
    if match is None:
        return shorten(text, width=_QUOTE_WIDTH, placeholder="…")

    start, end = match
    width = max(_QUOTE_WIDTH, end - start + 2)
    leading_context = min(_QUOTE_WIDTH // 4, width - (end - start) - 2)
    left = max(0, start - leading_context)
    if left:
        boundary = re.search(r"\s+", text[left:start])
        left = left + boundary.end() if boundary else start
    prefix = "…" if left else ""
    right = left + width - len(prefix)
    if len(text) <= right:
        return prefix + text[left:]
    tail = text[end:right - 1]
    boundary = re.search(r"\s+\S*$", tail)
    context = tail[:boundary.start()].rstrip() if boundary else ""
    return prefix + text[left:end] + context + "…"


def _first_hit_blocks(
    hit: _FirstHit, labels: Mapping[str, str], language: str, *,
    heading: str = "research_dossier_draft_first_match", pattern: re.Pattern[str] | None = None,
) -> tuple[str, str, str, str]:
    matches = (match.span() for match in pattern.finditer(hit["quote"])) if pattern is not None else ()
    return (
        f"## {labels[heading]}",
        chapter_heading(hit["chapter"], hit["chapter_title"], labels, language),
        chapter_line_range(hit["line"], hit["end_line"], labels, language),
        dossier_quote(hit["quote"], matches=matches),
    )


def _extract_location_drafts(
    chapters: Sequence[tuple[int, str, str]], *,
    excluded_names: set[str], configured_locations: Sequence[str] | None, inferred_limit: int,
    language: str, labels: Mapping[str, str],
) -> list[dict[str, Any]]:
    if not (inferred_limit if configured_locations is None else configured_locations):
        return []
    prepared = [(number, title, list(counted_chapter_passages(body))) for number, title, body in chapters]
    basis = "configured" if configured_locations is not None else "inferred"
    signals = _suggested_locations(prepared, language, excluded_names, limit=inferred_limit) if basis == "inferred" else {}
    names = configured_locations if configured_locations is not None else tuple(signals)
    drafts: list[dict[str, Any]] = []
    for name in names:
        pattern = _name_pattern(re.escape(normalize("NFC", name)))
        by_chapter: Counter[int] = Counter()
        first_hit: _FirstHit | None = None
        last_match: tuple[int, str, CountedChapterPassage, tuple[int, int]] | None = None
        for number, title, parts in prepared:
            for part in parts:
                matches = list(pattern.finditer(part.text))
                if not matches:
                    continue
                by_chapter[number] += len(matches)
                last_match = (number, title, part, matches[-1].span())
                if first_hit is None:
                    first_hit = {"chapter": number, "chapter_title": title, "line": part.start_line,
                                 "end_line": part.end_line,
                                 "quote": _short_excerpt(part.text, matches[0].span())}
        if first_hit is None or last_match is None:
            continue
        total = sum(by_chapter.values())
        place_label = labels["research_dossier_draft_location_title"]
        summary = name_mentions_summary(name, total, len(by_chapter), len(chapters), labels, language)
        distribution = chapter_mention_table(sorted(by_chapter.items()), labels, language)
        blocks = [summary, labels[f"research_dossier_draft_location_{basis}"],
                  labels["research_dossier_draft_location_review"],
                  f"## {labels['research_dossier_draft_location_chapters']}", distribution,
                  *_first_hit_blocks(first_hit, labels, language, pattern=pattern)]
        number, title, part, match_span = last_match
        last_hit: _FirstHit | None = None
        if (number, part.start_line) != (first_hit["chapter"], first_hit["line"]):
            last_hit = {"chapter": number, "chapter_title": title, "line": part.start_line,
                        "end_line": part.end_line, "quote": _short_excerpt(part.text, match_span)}
            blocks.extend(_first_hit_blocks(
                last_hit, labels, language, heading="research_dossier_draft_location_last_match",
                pattern=pattern,
            ))
        drafts.append({
            **_named_draft_id("location", name),
            "kind": "location", "title": _draft_title(place_label, name, labels), "summary": summary,
            "tags": ["manuscript-draft", "location"], "body": "\n\n".join(blocks),
            "evidence_hints": {"location": name, "basis": basis, "mentions": total,
                               "chapters": sorted(by_chapter), "first_hit": first_hit,
                               **({"last_hit": last_hit} if last_hit else {}),
                               **signals.get(name, {})},
        })
    drafts.sort(key=lambda draft: (-draft["evidence_hints"]["mentions"], _name_key(draft["title"])))
    return drafts


def _first_character_quote(
    chapter: tuple[int, str, str], name: str, names: Names,
) -> _FirstHit | None:
    """Keep a brief saved excerpt around the first match in counted prose."""
    number, title, body = chapter
    patterns = (pattern for pattern, label in names.items() if label == name) if isinstance(names, Mapping) else (name,)
    _, passages = _chapter_passages(body, [_name_pattern(pattern) for pattern in patterns], limit=1)
    if not passages:
        return None
    passage = passages[0]
    first_match = passage["matches"][0]
    return {"chapter": number, "chapter_title": title, "line": passage["start_line"], "end_line": passage["end_line"],
            "quote": _short_excerpt(passage["text"], (first_match["start"], first_match["end"]))}


def _character_draft(
    figure: Mapping[str, Any], voice: Mapping[str, Any] | None, first_hit: _FirstHit | None,
    aliases: Sequence[str], total_chapters: int, labels: Mapping[str, str], language: str, *,
    basis: Literal["configured", "inferred"],
    include_passage: bool,
) -> dict[str, Any]:
    name = figure["name"].strip()
    total, chapters = figure["mentions"], figure["chapters_present"]
    summary = name_mentions_summary(name, total, len(chapters), total_chapters, labels, language)
    blocks = character_overview_markdown(total, chapters, total_chapters, aliases=aliases,
                                         pov_chapters=figure.get("declared_pov_chapters") or (), language=language)
    if voice and voice["turns"]:
        blocks.extend((f"### {labels['research_dossier_character_dialogue']}",
                       character_dialogue_markdown(voice, labels, language)))
    if first_hit and include_passage:
        blocks.extend(_first_hit_blocks(first_hit, labels, language))

    return {
        **_named_draft_id("character", name),
        "kind": "character", "title": _draft_title(labels["research_tpl_character"], name, labels), "summary": summary,
        "tags": ["manuscript-draft", "character"], "body": mark_character_analysis("\n\n".join(blocks)),
        "evidence_hints": {"character": name, "basis": basis, "mentions": total, "chapters": chapters,
                           "includes_passages": bool(first_hit and include_passage),
                           **({"aliases": list(aliases)} if aliases else {}),
                           **({"first_hit": dict(first_hit)} if first_hit else {})},
    }


def _scene_position(scene: Mapping[str, Any], labels: Mapping[str, str], language: str) -> str:
    chapter = chapter_heading(scene["chapter"], "", labels, language)
    return chapter if scene["chapter_as_unit"] else f"{chapter} · {labels['scene_unit']} {num(scene['scene'], language, 0)}"


def _scene_counts(scene: Mapping[str, Any], labels: Mapping[str, str], language: str) -> str:
    return f"{labels['words']} {num(scene['words'], language, 0)} · {labels['sentences']} {num(scene['sentences'], language, 0)}"


def _individual_scene_drafts(
    scenes: Sequence[Mapping[str, Any]], labels: Mapping[str, str], language: str,
) -> list[dict[str, Any]]:
    drafts = []
    for scene in scenes:
        scope = "chapter" if scene["chapter_as_unit"] else "scene"
        heading = labels["chapter"] if scope == "chapter" else labels["scene_unit"]
        position = _scene_position(scene, labels, language)
        stats = _scene_counts(scene, labels, language)
        blocks = [f"{position} · {stats}"]
        if scope == "chapter":
            blocks.append(labels["research_dossier_draft_scene_chapter_fallback"])
        dialogue = scene["features"]["dialog_pct"]
        if dialogue is not None:
            blocks.append(f"{labels['feat_dialog']} · {pct(dialogue, language, 0)}")
        single_passage = scene["sentences"] == 1 and scene["closing"] == scene["opening"]
        review_key = "research_dossier_draft_scene_single_passage" if single_passage else "research_dossier_draft_scene_review"
        blocks.append(labels[review_key])
        citations = []
        for edge, passage_key, passage in (
            ("entry", "first_passage", scene["opening"]), ("exit", "last_passage", scene["closing"]),
        ):
            if edge == "exit" and single_passage:
                break
            hook = labels.get(f"hook_type_{scene[f'{edge}_hook_type']}", labels["hook_type_unknown"])
            blocks.extend((f"## {labels['research_dossier_draft_' + passage_key]}", hook))
            if passage:
                citations.append((len(blocks), passage))
                blocks.append(dossier_quote(passage))
        body = "\n\n".join(blocks)
        excerpt_limited = len(body) > MAX_DOSSIER_BODY_CHARS and bool(citations)
        if excerpt_limited:
            for index, passage in citations:
                blocks[index] = dossier_quote(_short_excerpt(passage))
            blocks.append(labels["research_dossier_draft_scene_excerpts_limited"])
            body = "\n\n".join(blocks)
        drafts.append({
            "id": f"scene:{scene['id']}", "kind": "scene",
            "title": _draft_title(heading, scene["scene_title"], labels), "summary": f"{position} · {stats}",
            "tags": ["manuscript-draft", "scene"], "body": body,
            "evidence_hints": {
                "scene": scene["scene_title"], "scene_scope": scope, "chapter": scene["chapter"],
                "chapter_title": scene["chapter_title"], "scene_index": scene["scene"],
                "scene_source_sha256": scene["source_sha256"], "words": scene["words"],
                "sentences": scene["sentences"],
                **({"excerpt_limited": True} if excerpt_limited else {}),
            },
        })
    return drafts


def _scenes_draft(
    scenes: Sequence[Mapping[str, Any]], total_chapters: int, labels: Mapping[str, str], language: str,
) -> dict[str, Any]:
    title = labels["research_dossier_draft_scene_register"]
    unit_label = "research_dossier_draft_scene_units_one" if len(scenes) == 1 else "research_dossier_draft_scene_units"
    summary = labels[unit_label].format(count=num(len(scenes), language, 0))
    uses_chapters = any(scene["chapter_as_unit"] for scene in scenes)
    lines = [summary, ""]
    if uses_chapters:
        lines.extend((labels["research_dossier_draft_scene_chapter_fallback"], ""))
    for scene in scenes:
        position = _scene_position(scene, labels, language)
        stats = _scene_counts(scene, labels, language)
        title_text = " ".join(scene["scene_title"].split())
        lines.append(f"- **{position}** · {title_text} · {stats}")
    return {
        "id": "scenes:manuscript", "kind": "scene", "title": title, "summary": summary,
        "tags": ["manuscript-draft", "scenes"], "body": "\n".join(lines),
        "evidence_hints": {"scene_scope": "register", "chapters": total_chapters, "scenes": len(scenes),
                           "chapter_fallback": uses_chapters},
    }


def extract_manuscript_dossier_drafts(
    text: str,
    *,
    language: str = "en",
    settings: Mapping[str, Any] | None = None,
    kind: str = "all",
) -> dict[str, Any]:
    """Build deterministic, read-only dossier drafts from manuscript characters, dialogue, and scenes."""
    settings = settings or {}
    draft_settings = resolve_dossier_draft_settings(settings)
    config, resolved_language = resolve_document_config(text, language, project_config=settings)
    lang_key = resolved_language.key
    chapters = split_chapters(text, config)
    total_chapters = len(chapters)

    drafts: list[dict[str, Any]] = []
    want_characters = kind in ("all", "character", "characters")
    want_scenes = kind in ("all", "scene", "scenes")
    want_locations = kind in ("all", "location", "locations")
    labels = {**get_language_profile(lang_key).labels, **workspace_labels_for(lang_key)}
    unavailable: dict[str, str] = {}
    configured_locations = None
    if want_locations:
        try:
            configured_locations = _configured_location_names(settings)
        except ValueError as exc:
            if kind != "all":
                raise
            unavailable["location"] = str(exc)
            want_locations = False
    excluded_character_names: set[str] = set()

    if want_characters or (want_locations and configured_locations is None):
        resolved = resolve_character_settings(None, settings)
        # Recurring capitals alone do not prove that a name belongs to a
        # character. Only an explicit character declaration excludes a place.
        declared_names = resolved.names.values() if isinstance(resolved.names, Mapping) else resolved.names
        excluded_character_names.update(_name_key(name) for name in declared_names)
        names_input = (
            resolved.names or _auto_character_names(chapters, limit=draft_settings.inferred_character_limit)
        ) if want_characters else ()
        if names_input:
            pres = presence_report(
                text,
                names_input,
                config,
                declared_pov=resolved.declared_pov or None,
                _include_narrator_and_interactions=False,
            )
            configured = settings.get("characters", {})
            voice_by_name = {entry["name"]: entry for entry in pres["character_voices"]["characters"]}
            chapter_by_number = {chapter[0]: chapter for chapter in chapters}
            char_drafts: list[dict[str, Any]] = []
            for fig in pres["figures"]:
                fig_name = fig["name"]
                if not fig_name.strip() or not fig["mentions"]:
                    continue
                first_hit = _first_character_quote(chapter_by_number[fig["first_chapter"]], fig_name, names_input)
                char_drafts.append(
                    _character_draft(
                        figure=fig,
                        voice=character_dialogue_evidence(voice_by_name.get(fig_name)),
                        first_hit=first_hit,
                        aliases=(configured.get(fig_name) or {}).get("aliases", ()),
                        total_chapters=total_chapters,
                        labels=labels,
                        language=lang_key,
                        basis="configured" if resolved.names else "inferred",
                        include_passage=draft_settings.character_report_passages,
                    )
                )
            char_drafts.sort(
                key=lambda item: (-item["evidence_hints"]["mentions"], item["title"]),
            )
            drafts.extend(char_drafts)

    if want_scenes:
        try:
            scene_settings = settings.get("scene_analysis", {
                key: settings[key] for key in ("assignments", "groups", "planned", "titles") if key in settings
            })
            if not isinstance(scene_settings, Mapping):
                raise SceneSettingsError("scene_analysis must be a table")
            scenes = scene_report(text, config, scene_settings, _include_draft_evidence=True)["items"]
        except SceneSettingsError as exc:
            if kind != "all":
                raise
            unavailable["scene"] = str(exc)
        else:
            if scenes:
                drafts.append(_scenes_draft(scenes, total_chapters, labels, lang_key))
                drafts.extend(_individual_scene_drafts(scenes, labels, lang_key))

    if want_locations:
        drafts.extend(_extract_location_drafts(
            chapters, excluded_names=excluded_character_names, configured_locations=configured_locations,
            inferred_limit=draft_settings.inferred_location_limit, language=lang_key, labels=labels,
        ))

    return {
        "schema_version": DRAFT_SCHEMA,
        "language": lang_key,
        "chapters": total_chapters,
        "drafts": drafts,
        **({"unavailable": unavailable} if unavailable else {}),
    }
