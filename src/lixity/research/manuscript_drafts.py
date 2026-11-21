"""Deterministic, read-only dossier draft synthesis from manuscript analysis signals."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from textwrap import shorten
from typing import Any
from unicodedata import normalize
from urllib.parse import quote

from ..characters import (
    MAX_CHARACTER_NAME_CHARS,
    Names,
    _name_pattern,
    presence_report,
    resolve_character_settings,
)
from ..language import get_language_profile
from ..markdown_parser import CountedChapterPassage, counted_chapter_passages, split_chapters
from ..pipeline import resolve_document_config
from ..publication import validate_metadata_text
from ..scenes import scene_report
from ..workspace_labels import workspace_labels_for
from .character_evidence import _auto_character_names, _chapter_passages

DRAFT_SCHEMA = "manuscript-dossier-drafts/1"
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


def _extract_location_drafts(
    chapters: Sequence[tuple[int, str, str]], *,
    excluded_names: set[str], configured_locations: Sequence[str] | None,
    language: str, labels: Mapping[str, str],
) -> list[dict[str, Any]]:
    prepared = [(number, title, list(counted_chapter_passages(body))) for number, title, body in chapters]
    basis = "configured" if configured_locations is not None else "inferred"
    names = configured_locations if configured_locations is not None else _suggested_locations(
        [part for _, _, parts in prepared for part in parts], language, excluded_names,
    )
    drafts: list[dict[str, Any]] = []
    for name in names:
        pattern = _name_pattern(re.escape(name))
        by_chapter: Counter[int] = Counter()
        first_hit = None
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
        mentions_label = labels["research_dossier_character_mentions"]
        chapter_label = labels["chapter"]
        summary = f"{mentions_label} · {total} · {chapter_label} {len(by_chapter)}/{len(chapters)}"
        body = "\n".join((
            f"## {place_label}", "", labels[f"research_dossier_draft_location_{basis}"], "", summary, "",
            f"## {labels['research_dossier_draft_first_match']}", "",
            f"{chapter_label} {first_hit['chapter']} · {first_hit['chapter_title']}"
            f" · {labels['line']} {first_hit['line']}", "", f"> {first_hit['quote']}",
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
) -> dict[str, Any] | None:
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
    *,
    figure: Mapping[str, Any],
    voice: Mapping[str, Any] | None,
    first_hit: Mapping[str, Any] | None,
    aliases: Sequence[str],
    total_chapters: int,
    is_de: bool,
) -> dict[str, Any]:
    name = str(figure.get("name") or "").strip()
    total = int(figure.get("mentions") or figure.get("total") or 0)
    chapters_present = [
        int(ch) for ch in (figure.get("chapters_present") or figure.get("chapters") or [])
    ]
    pov_chapters = [int(ch) for ch in (figure.get("declared_pov_chapters") or [])]

    sections: list[str] = []
    if is_de:
        sections.append(f"## Überblick\n\n- **Figur:** {name}")
        if aliases:
            sections.append(f"- **Alternative Namen:** {', '.join(aliases)}")
        sections.append(f"- **Namensnennungen:** {total} in {len(chapters_present)} von {total_chapters} Kapiteln")
        if pov_chapters:
            sections.append(f"- **Festgelegte Perspektivkapitel:** {', '.join(str(c) for c in pov_chapters)}")
        if voice and voice.get("turns"):
            turns = int(voice["turns"])
            mean_len = voice.get("dialogue_asl")
            q_share = voice.get("question_excl_rate")
            sections.append(
                "\n## Figurenrede\n\n"
                f"- **Der Figur zugeordnete Redezüge (geschätzt):** {turns}"
                + (f"\n- **Mittlere Satzlänge im Dialog:** {float(mean_len):.1f} Wörter" if mean_len is not None else "")
                + (f"\n- **Anteil der Frage- und Ausrufesätze:** {float(q_share):.0f} %" if q_share is not None else "")
            )
        if first_hit:
            sections.append(
                "\n## Erste erfasste Textstelle\n\n"
                f"- Kapitel {first_hit['chapter']} ({first_hit['chapter_title']}), Zeile {first_hit['line']}: „{first_hit['quote']}“"
            )
        summary = f"{total} Erwähnungen · {len(chapters_present)}/{total_chapters} Kapitel" + (
            f" · {int(voice['turns'])} Dialogzüge" if voice and voice.get("turns") else ""
        )
        title = f"Figur: {name}"
    else:
        sections.append(f"## Overview\n\n- **Character:** {name}")
        if aliases:
            sections.append(f"- **Aliases:** {', '.join(aliases)}")
        sections.append(f"- **Name mentions:** {total} across {len(chapters_present)} of {total_chapters} chapters")
        if pov_chapters:
            sections.append(f"- **Declared viewpoint chapters:** {', '.join(str(c) for c in pov_chapters)}")
        if voice and voice.get("turns"):
            turns = int(voice["turns"])
            mean_len = voice.get("dialogue_asl")
            q_share = voice.get("question_excl_rate")
            sections.append(
                "\n## Dialogue voice\n\n"
                f"- **Turns attributed to this character (estimate):** {turns}"
                + (f"\n- **Mean dialogue sentence length:** {float(mean_len):.1f} words" if mean_len is not None else "")
                + (f"\n- **Share of questions and exclamations:** {float(q_share):.0f} %" if q_share is not None else "")
            )
        if first_hit:
            sections.append(
                "\n## First matching passage\n\n"
                f"- Chapter {first_hit['chapter']} ({first_hit['chapter_title']}), line {first_hit['line']}: “{first_hit['quote']}”"
            )
        summary = f"{total} mentions · {len(chapters_present)}/{total_chapters} chapters" + (
            f" · {int(voice['turns'])} dialogue turns" if voice and voice.get("turns") else ""
        )
        title = f"Character: {name}"

    return {
        **_named_draft_id("character", name),
        "kind": "character",
        "title": title,
        "summary": summary,
        "tags": ["manuscript-draft", "character"],
        "body": "\n".join(sections),
        "evidence_hints": {
            "character": name,
            "mentions": total,
            "chapters": chapters_present,
            **({"first_hit": dict(first_hit)} if first_hit else {}),
        },
    }


def _scene_position(scene: Mapping[str, Any], labels: Mapping[str, str]) -> str:
    chapter = f"{labels['chapter']} {scene['chapter']}"
    return chapter if scene["chapter_as_unit"] else f"{chapter} · {labels['scene_unit']} {scene['scene']}"


def _scene_counts(scene: Mapping[str, Any], labels: Mapping[str, str]) -> str:
    return f"{scene['words']} {labels['words']} · {scene['sentences']} {labels['sentences']}"


def _individual_scene_drafts(
    scenes: Sequence[Mapping[str, Any]], labels: Mapping[str, str],
) -> list[dict[str, Any]]:
    drafts = []
    for scene in scenes:
        scope = "chapter" if scene["chapter_as_unit"] else "scene"
        heading = labels["chapter"] if scope == "chapter" else labels["scene_unit"]
        position = _scene_position(scene, labels)
        stats = _scene_counts(scene, labels)
        lines = [f"## {scene['scene_title']}", "", position, "", stats]
        if scope == "chapter":
            lines.extend(("", labels["research_dossier_draft_scene_chapter_fallback"]))
        features = scene["features"]
        if features["dialog_pct"] is not None:
            lines.extend(("", f"{labels['feat_dialog']} · {features['dialog_pct']:.0f} %"))
        for edge, passage in (("entry", "opening"), ("exit", "closing")):
            hook = labels.get(f"hook_type_{scene[f'{edge}_hook_type']}", labels["hook_type_unknown"])
            if edge == "exit" and scene["closing"] == scene["opening"]:
                lines.extend(("", f"{labels['scene_exit_hook']} · {hook}"))
                continue
            passage_key = "first_passage" if edge == "entry" else "last_passage"
            lines.extend(("", f"## {labels['research_dossier_draft_' + passage_key]}", "", hook))
            if scene[passage]:
                lines.extend(("", f"> {_short_excerpt(scene[passage])}"))
        drafts.append({
            "id": f"scene:{scene['id']}", "kind": "scene",
            "title": f"{heading}: {scene['scene_title']}", "summary": f"{position} · {stats}",
            "tags": ["manuscript-draft", "scene"], "body": "\n".join(lines),
            "evidence_hints": {
                "scene": scene["scene_title"], "scene_scope": scope, "chapter": scene["chapter"],
                "chapter_title": scene["chapter_title"], "scene_index": scene["scene"],
                "scene_source_sha256": scene["source_sha256"], "words": scene["words"],
                "sentences": scene["sentences"],
            },
        })
    return drafts


def _scenes_draft(
    scenes: Sequence[Mapping[str, Any]], total_chapters: int, labels: Mapping[str, str],
) -> dict[str, Any]:
    title = labels["research_dossier_draft_scene_register"]
    unit_label = "research_dossier_draft_scene_units_one" if len(scenes) == 1 else "research_dossier_draft_scene_units"
    summary = labels[unit_label].format(count=len(scenes))
    uses_chapters = any(scene["chapter_as_unit"] for scene in scenes)
    lines = [f"## {title}", "", summary, ""]
    if uses_chapters:
        lines.extend((labels["research_dossier_draft_scene_chapter_fallback"], ""))
    for scene in scenes:
        position = _scene_position(scene, labels)
        stats = _scene_counts(scene, labels)
        lines.append(f"- **{position}** · {scene['scene_title']} · {stats}")
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
    is_de = lang_key == "de"
    chapters = split_chapters(text, config)
    total_chapters = len(chapters)

    drafts: list[dict[str, Any]] = []
    want_characters = kind in ("all", "character", "characters")
    want_scenes = kind in ("all", "scene", "scenes")
    want_locations = kind in ("all", "location", "locations")
    labels = {**get_language_profile(lang_key).labels, **workspace_labels_for(lang_key)}
    configured_locations = _configured_location_names(settings) if want_locations else None
    excluded_character_names: set[str] = set()

    if want_characters or (want_locations and configured_locations is None):
        resolved = resolve_character_settings(None, settings)
        names_input: Mapping[str, str] | Sequence[str] = (
            resolved.names or _auto_character_names(chapters)
        )
        # Recurring capitals alone do not prove that a name belongs to a
        # character. Only an explicit character declaration excludes a place.
        declared_names = resolved.names.values() if isinstance(resolved.names, Mapping) else resolved.names
        excluded_character_names.update(_name_key(name) for name in declared_names)
        if want_characters and names_input:
            pres = presence_report(
                text,
                names_input,
                config,
                declared_pov=resolved.declared_pov or None,
            )
            voices_raw = pres["character_voices"]
            configured = settings.get("characters", {})
            voice_by_name = {
                str(entry.get("name")): entry
                for entry in (voices_raw.get("characters") or voices_raw.get("profiles") or [])
                if entry.get("name")
            }
            chapter_by_number = {chapter[0]: chapter for chapter in chapters}
            char_drafts: list[dict[str, Any]] = []
            for fig in pres.get("figures") or []:
                fig_name = str(fig.get("name") or "").strip()
                if not fig_name or int(fig.get("mentions") or fig.get("total") or 0) <= 0:
                    continue
                first_hit = _first_character_quote(chapter_by_number[fig["first_chapter"]], fig_name, names_input)
                char_drafts.append(
                    _character_draft(
                        figure=fig,
                        voice=voice_by_name.get(fig_name),
                        first_hit=first_hit,
                        aliases=(configured.get(fig_name) or {}).get("aliases", ()),
                        total_chapters=total_chapters,
                        is_de=is_de,
                    )
                )
            char_drafts.sort(
                key=lambda item: (-int((item.get("evidence_hints") or {}).get("mentions") or 0), str(item.get("title") or ""))
            )
            drafts.extend(char_drafts)

    if want_scenes:
        scene_settings: Mapping[str, Any] | None = None
        if isinstance(settings, Mapping):
            raw_scene = settings.get("scene_analysis")
            if isinstance(raw_scene, Mapping):
                scene_settings = raw_scene
            else:
                filtered = {
                    k: v for k, v in settings.items() if k in {"assignments", "groups", "planned", "titles"}
                }
                scene_settings = filtered or None
        sc_report = scene_report(text, config, scene_settings, _include_draft_evidence=True)
        scenes = sc_report["items"]
        if scenes:
            drafts.append(_scenes_draft(scenes, total_chapters, labels))
            drafts.extend(_individual_scene_drafts(scenes, labels))

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
    }
