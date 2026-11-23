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
    MAX_CHARACTER_NAME_CHARS,
    Names,
    _name_pattern,
    presence_report,
    resolve_character_settings,
)
from ..format import num, pct
from ..language import get_language_profile
from ..markdown_parser import CountedChapterPassage, counted_chapter_passages, split_chapters
from ..pipeline import resolve_document_config
from ..publication import validate_metadata_text
from ..scenes import SceneSettingsError, scene_report
from ..workspace_labels import workspace_labels_for
from .character_evidence import (
    _auto_character_names,
    _chapter_passages,
    character_dialogue_evidence,
    character_dialogue_markdown,
)
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
_INFERRED_LOCATION_LIMIT = 12
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
    quote: str


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
    value = settings.get("locations", settings.get("places"))
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise ValueError("locations must be a list of names")
    names: dict[str, str] = {}
    for item in value:
        if not isinstance(item, str):
            raise ValueError("Each configured location must be a nonempty name")
        name = validate_metadata_text(item, "Location name", MAX_CHARACTER_NAME_CHARS)
        if not name:
            raise ValueError("Each configured location must be a nonempty name")
        names.setdefault(_name_key(name), name)
    return list(names.values())


def _suggested_locations(
    paragraphs: Sequence[CountedChapterPassage], language: str, excluded_names: set[str],
) -> list[str]:
    directional, local = _LOCATION_CUES.get(language, _LOCATION_CUES["en"])
    cue = "|".join(re.escape(value) for value in (*directional, *local))
    pattern = re.compile(
        rf"(?<!\w)(?P<cue>(?i:{cue}))\s+(?P<name>{_LOCATION_WORD})"
        rf"(?=(?:[ \t]+(?P<following>{_LOCATION_WORD}))?)"
    )
    stopwords = get_language_profile(language).stopwords | excluded_names
    found: dict[str, str] = {}
    counts: Counter[str] = Counter()
    directional_hits: set[str] = set()
    for paragraph in paragraphs:
        for match in pattern.finditer(paragraph.text):
            first, second = match["name"], match["following"]
            if len(first) < 3 or not first[0].isupper() or _name_key(first) in stopwords:
                continue
            candidate = (
                f"{first} {second}"
                if second and second[0].isupper() and _name_key(second) not in stopwords else first
            )
            key = _name_key(candidate)
            if key in stopwords:
                continue
            found.setdefault(key, candidate)
            counts[key] += 1
            if match["cue"].casefold() in directional:
                directional_hits.add(key)
    eligible = (key for key, count in counts.items() if count > 1 and key in directional_hits)
    return [found[key] for key in sorted(eligible, key=lambda key: (-counts[key], key))[:_INFERRED_LOCATION_LIMIT]]


def _short_excerpt(text: str, match_start: int = 0) -> str:
    if len(text) <= _QUOTE_WIDTH:
        return text
    leading_context = _QUOTE_WIDTH // 4
    if match_start > leading_context:
        boundary = re.search(r"\s+", text[match_start - leading_context:match_start])
        left = match_start - leading_context + boundary.end() if boundary else match_start
        text = "…" + text[left:]
    return shorten(text, width=_QUOTE_WIDTH, placeholder="…")


def _first_hit_blocks(hit: _FirstHit, labels: Mapping[str, str], language: str) -> tuple[str, str, str, str]:
    return (
        f"## {labels['research_dossier_draft_first_match']}",
        chapter_heading(hit["chapter"], hit["chapter_title"], labels, language),
        chapter_line_range(hit["line"], hit["line"], labels, language),
        dossier_quote(hit["quote"]),
    )


def _extract_location_drafts(
    chapters: Sequence[tuple[int, str, str]], *,
    excluded_names: set[str], configured_locations: Sequence[str] | None,
    language: str, labels: Mapping[str, str],
) -> list[dict[str, Any]]:
    if configured_locations is not None and not configured_locations:
        return []
    prepared = [(number, title, list(counted_chapter_passages(body))) for number, title, body in chapters]
    basis = "configured" if configured_locations is not None else "inferred"
    names = configured_locations if configured_locations is not None else _suggested_locations(
        [part for _, _, parts in prepared for part in parts], language, excluded_names,
    )
    drafts: list[dict[str, Any]] = []
    for name in names:
        pattern = _name_pattern(re.escape(normalize("NFC", name)))
        by_chapter: Counter[int] = Counter()
        first_hit: _FirstHit | None = None
        for number, title, parts in prepared:
            for part in parts:
                matches = list(pattern.finditer(part.text))
                if not matches:
                    continue
                by_chapter[number] += len(matches)
                if first_hit is None:
                    first_hit = {"chapter": number, "chapter_title": title, "line": part.start_line,
                                 "quote": _short_excerpt(part.text, matches[0].start())}
        if first_hit is None:
            continue
        total = sum(by_chapter.values())
        place_label = labels["research_dossier_draft_location_title"]
        summary = name_mentions_summary(name, total, len(by_chapter), len(chapters), labels, language)
        distribution = chapter_mention_table(((number, by_chapter[number]) for number, _, _ in chapters),
                                              labels, language)
        body = "\n\n".join((
            f"## {place_label}", labels[f"research_dossier_draft_location_{basis}"], summary,
            f"## {labels['research_dossier_character_distribution']}", distribution,
            *_first_hit_blocks(first_hit, labels, language),
        ))
        drafts.append({
            **_named_draft_id("location", name),
            "kind": "location", "title": f"{place_label}: {name}", "summary": summary,
            "tags": ["manuscript-draft", "location"], "body": body,
            "evidence_hints": {"location": name, "basis": basis, "mentions": total,
                               "chapters": sorted(by_chapter), "first_hit": first_hit},
        })
    drafts.sort(key=lambda draft: (-draft["evidence_hints"]["mentions"], _name_key(draft["title"])))
    return drafts


def _first_character_quote(
    chapter: tuple[int, str, str], name: str, names: Names,
) -> _FirstHit | None:
    """Keep a brief saved excerpt around the first match in counted prose."""
    number, title, body = chapter
    patterns = (pattern for pattern, label in names.items() if label == name) if isinstance(names, Mapping) else (name,)
    _, passages = _chapter_passages(body, [_name_pattern(pattern) for pattern in patterns])
    if not passages:
        return None
    passage = passages[0]
    return {"chapter": number, "chapter_title": title, "line": passage["start_line"],
            "quote": _short_excerpt(passage["text"], passage["matches"][0]["start"])}


def _character_draft(
    figure: Mapping[str, Any], voice: Mapping[str, Any] | None, first_hit: _FirstHit | None,
    aliases: Sequence[str], total_chapters: int, labels: Mapping[str, str], language: str,
) -> dict[str, Any]:
    name = figure["name"].strip()
    total, chapters = figure["mentions"], figure["chapters_present"]
    summary = name_mentions_summary(name, total, len(chapters), total_chapters, labels, language)
    blocks = [f"## {labels['research_dossier_character_heading']}", summary,
              labels["research_dossier_character_scope"]]
    facts = []
    if aliases:
        facts.append(f"- **{labels['research_dossier_character_aliases']}:** {', '.join(aliases)}")
    if pov_chapters := figure.get("declared_pov_chapters"):
        chapters_text = ", ".join(num(chapter, language, 0) for chapter in pov_chapters)
        facts.append(f"- **{labels['research_dossier_character_pov']}:** {chapters_text}")
    if facts:
        blocks.append("\n".join(facts))
    if voice and voice["turns"]:
        blocks.extend((f"### {labels['research_dossier_character_dialogue']}",
                       character_dialogue_markdown(voice, labels, language)))
    if first_hit:
        blocks.extend(_first_hit_blocks(first_hit, labels, language))

    # Generated character bindings read the original title prefix on older archives.
    prefix = "Figur" if language == "de" else "Character"
    return {
        **_named_draft_id("character", name),
        "kind": "character", "title": f"{prefix}: {name}", "summary": summary,
        "tags": ["manuscript-draft", "character"], "body": "\n\n".join(blocks),
        "evidence_hints": {"character": name, "mentions": total, "chapters": chapters,
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
        title = " ".join(scene["scene_title"].split())
        blocks = [f"## {title}", position, stats]
        if scope == "chapter":
            blocks.append(labels["research_dossier_draft_scene_chapter_fallback"])
        dialogue = scene["features"]["dialog_pct"]
        if dialogue is not None:
            blocks.append(f"{labels['feat_dialog']} · {pct(dialogue, language, 0)}")
        citations = []
        for edge, passage_key, passage in (
            ("entry", "first_passage", scene["opening"]), ("exit", "last_passage", scene["closing"]),
        ):
            hook = labels.get(f"hook_type_{scene[f'{edge}_hook_type']}", labels["hook_type_unknown"])
            if edge == "exit" and scene["sentences"] == 1 and scene["closing"] == scene["opening"]:
                blocks.append(f"{labels['scene_exit_hook']} · {hook}")
                continue
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
            "title": f"{heading}: {scene['scene_title']}", "summary": f"{position} · {stats}",
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
    lines = [f"## {title}", "", summary, ""]
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
        names_input = (resolved.names or _auto_character_names(chapters)) if want_characters else ()
        if names_input:
            pres = presence_report(
                text,
                names_input,
                config,
                declared_pov=resolved.declared_pov or None,
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
            language=lang_key, labels=labels,
        ))

    return {
        "schema_version": DRAFT_SCHEMA,
        "language": lang_key,
        "chapters": total_chapters,
        "drafts": drafts,
        **({"unavailable": unavailable} if unavailable else {}),
    }
