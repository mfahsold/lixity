"""Deterministic, read-only dossier draft synthesis from manuscript analysis signals."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from textwrap import shorten
from typing import Any

from ..characters import Names, _name_pattern, presence_report, resolve_character_settings
from ..markdown_parser import split_chapters
from ..pipeline import resolve_document_config
from ..scenes import scene_report
from .character_evidence import _auto_character_names, _chapter_passages

DRAFT_SCHEMA = "manuscript-dossier-drafts/1"
_MAX_INDIVIDUAL_SCENES = 12
_MAX_LOCATIONS = 12
_CHARACTER_QUOTE_WIDTH = 180

_LOCATION_PREPOSITIONS = (
    "in", "im", "am", "an", "nach", "aus", "bei", "vor", "hinter",
    "zwischen", "unter", "neben", "auf", "durch", "at", "to", "from", "near",
)
_LOCATION_STOPWORDS = frozenset({
    "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem", "einer",
    "montag", "dienstag", "mittwoch", "donnerstag", "freitag", "samstag", "sonntag",
    "januar", "februar", "märz", "april", "mai", "juni", "juli", "august", "september",
    "oktober", "november", "dezember", "kapitel", "chapter", "szene", "scene", "teil", "part",
    "the", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday",
    "january", "february", "march", "may", "june", "july", "october", "december",
})
_LOCATION_CUE_RE = re.compile(
    r"\b(?:" + "|".join(_LOCATION_PREPOSITIONS) + r")\s+([A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-]{2,}(?:\s+[A-ZÄÖÜ][a-zäöüßA-ZÄÖÜ\-]{2,})?)"
)


def _extract_location_drafts(
    chapters: Sequence[tuple[int, str, str]],
    *,
    excluded_names: set[str],
    configured_locations: Sequence[str],
    is_de: bool,
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    chapters_by_loc: dict[str, set[int]] = {}
    if configured_locations:
        targets = [loc.strip() for loc in configured_locations if str(loc).strip()]
        for ch_num, _ch_title, ch_body in chapters:
            for loc in targets:
                hits = len(re.findall(rf"\b{re.escape(loc)}\b", ch_body))
                if hits:
                    counts[loc] += hits
                    chapters_by_loc.setdefault(loc, set()).add(int(ch_num))
    else:
        for ch_num, ch_title, ch_body in chapters:
            for match in _LOCATION_CUE_RE.finditer(f"{ch_title}\n{ch_body}"):
                candidate = match.group(1).strip()
                parts = candidate.split()
                if any(p.casefold() in _LOCATION_STOPWORDS for p in parts):
                    continue
                if candidate.casefold() in excluded_names or any(p.casefold() in excluded_names for p in parts):
                    continue
                counts[candidate] += 1
                chapters_by_loc.setdefault(candidate, set()).add(int(ch_num))
        counts = Counter({k: v for k, v in counts.items() if v >= 2})

    drafts: list[dict[str, Any]] = []
    for loc, total in counts.most_common(_MAX_LOCATIONS):
        chs = sorted(chapters_by_loc.get(loc, ()))
        first_hit = _first_quote_for_name(chapters, loc)
        if is_de:
            body_lines = [
                f"## Überblick\n- **Ort / Schauplatz:** {loc}",
                f"- **Erwähnungen:** {total} in {len(chs)} von {len(chapters)} Kapiteln"
                + (f" (Kapitel {', '.join(str(c) for c in chs[:12])})" if chs else ""),
                "\n## Atmosphäre & Fakten\n- (Offene Details aus dem Manuskript ergänzen)",
            ]
            if first_hit:
                body_lines.append(
                    f"\n## Erste Textstelle\n- Kapitel {first_hit['chapter']} ({first_hit['chapter_title']}), "
                    f"Zeile {first_hit['line']}: „{first_hit['quote']}“"
                )
            title = f"Ort: {loc}"
            summary = f"{total} Erwähnungen · {len(chs)}/{len(chapters)} Kapitel"
        else:
            body_lines = [
                f"## Overview\n- **Location:** {loc}",
                f"- **Mentions:** {total} in {len(chs)} of {len(chapters)} chapters"
                + (f" (chapters {', '.join(str(c) for c in chs[:12])})" if chs else ""),
                "\n## Setting & facts\n- (Add verified details from manuscript or research)",
            ]
            if first_hit:
                body_lines.append(
                    f"\n## First occurrence\n- Chapter {first_hit['chapter']} ({first_hit['chapter_title']}), "
                    f"line {first_hit['line']}: “{first_hit['quote']}”"
                )
            title = f"Location: {loc}"
            summary = f"{total} mentions · {len(chs)}/{len(chapters)} chapters"
        drafts.append(
            {
                "id": f"location:{_slug(loc)}",
                "kind": "location",
                "title": title,
                "summary": summary,
                "tags": ["manuscript-draft", "location"],
                "body": "\n".join(body_lines),
                "evidence_hints": {
                    "location": loc,
                    "mentions": int(total),
                    "chapters": chs,
                    **({"first_hit": dict(first_hit)} if first_hit else {}),
                },
            }
        )
    return drafts


def _individual_scene_drafts(*, report: Mapping[str, Any], is_de: bool) -> list[dict[str, Any]]:
    scenes = list(report.get("items") or report.get("scenes") or [])
    ranked = sorted(scenes, key=lambda sc: -int(sc.get("words") or 0))[:_MAX_INDIVIDUAL_SCENES]
    out: list[dict[str, Any]] = []
    for idx, sc in enumerate(ranked, start=1):
        ch = int(sc.get("chapter") or 0)
        sc_num = int(sc.get("scene") or idx)
        words = int(sc.get("words") or 0)
        feats = sc.get("features") or {}
        dlg = feats.get("dialog_pct")
        label = str(sc.get("scene_title") or (f"Kap. {ch} · Szene {sc_num}" if is_de else f"Ch. {ch} · Scene {sc_num}"))
        if is_de:
            title = f"Szene: {label}"
            summary = f"{words} Wörter" + (f" · {float(dlg):.0f}% Dialog" if isinstance(dlg, (int, float)) else "")
            body = (
                f"## Szenenprofil\n- **Szene:** {label}\n- **Umfang:** {words} Wörter\n"
                + (f"- **Dialoganteil:** {float(dlg):.0f}%\n" if isinstance(dlg, (int, float)) else "")
                + f"- **Einstieg / Ausstieg:** {sc.get('entry_hook_type') or '–'} / {sc.get('exit_hook_type') or '–'}\n"
            )
        else:
            title = f"Scene: {label}"
            summary = f"{words} words" + (f" · {float(dlg):.0f}% dialogue" if isinstance(dlg, (int, float)) else "")
            body = (
                f"## Scene profile\n- **Scene:** {label}\n- **Length:** {words} words\n"
                + (f"- **Dialogue share:** {float(dlg):.0f}%\n" if isinstance(dlg, (int, float)) else "")
                + f"- **Entry / Exit:** {sc.get('entry_hook_type') or '–'} / {sc.get('exit_hook_type') or '–'}\n"
            )
        out.append(
            {
                "id": f"scene:{ch}:{sc_num}",
                "kind": "scene",
                "title": title,
                "summary": summary,
                "tags": ["manuscript-draft", "scene"],
                "body": body,
                "evidence_hints": {
                    "scene": label,
                    "chapter": ch,
                    "scene_index": sc_num,
                    "words": words,
                },
            }
        )
    return out


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned or "entry"


def _first_quote_for_name(
    chapters: Sequence[tuple[int, str, str]], pattern_text: str
) -> dict[str, Any] | None:
    pattern = re.compile(rf"\b{re.escape(pattern_text)}\b")
    for chapter_num, chapter_title, chapter_body in chapters:
        lines = chapter_body.splitlines()
        for offset, raw_line in enumerate(lines):
            stripped = raw_line.strip()
            if not stripped or stripped.startswith("#"):
                continue
            if pattern.search(stripped):
                return {
                    "chapter": int(chapter_num),
                    "chapter_title": str(chapter_title),
                    "line": int(offset + 1),
                    "quote": stripped[:180],
                }
    return None


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
    text: str = passage["text"]
    start: int = passage["matches"][0]["start"]
    if len(text) > _CHARACTER_QUOTE_WIDTH:
        leading_context = _CHARACTER_QUOTE_WIDTH // 4
        if start > leading_context:
            boundary = re.search(r"\s+", text[start - leading_context:start])
            left = start - leading_context + boundary.end() if boundary else start
            text = "…" + text[left:]
        text = shorten(text, width=_CHARACTER_QUOTE_WIDTH, placeholder="…")
    return {"chapter": number, "chapter_title": title, "line": passage["start_line"], "quote": text}


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
        "id": f"character:{_slug(name)}",
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


def _scenes_draft(*, report: Mapping[str, Any], total_chapters: int, is_de: bool) -> dict[str, Any] | None:
    scenes = list(report.get("items") or report.get("scenes") or [])
    if not scenes:
        return None
    lines: list[str] = []
    if is_de:
        lines.append("## Szenenübersicht")
        lines.append(f"- **Erkannte Szenen:** {len(scenes)} über {total_chapters} Kapitel")
        plateaus = list(report.get("pacing_plateaus") or [])
        if plateaus:
            lines.append(f"- **Gleichförmige Pacing-Strecken:** {len(plateaus)}")
        lines.append("\n## Szenenliste")
        for idx, sc in enumerate(scenes[:40], start=1):
            label = sc.get("scene_title") or f"Kap. {sc.get('chapter')} · Szene {sc.get('scene', idx)}"
            words = sc.get("words")
            feats = sc.get("features") or {}
            dlg = feats.get("dialog_pct")
            dlg_str = f" · Dialog: {dlg:.0f}%" if isinstance(dlg, (int, float)) else ""
            hooks = f" · Einstieg/Ausstieg: {sc.get('entry_hook_type') or '–'}/{sc.get('exit_hook_type') or '–'}"
            lines.append(f"- **{label}** ({words} Wörter{dlg_str}{hooks})")
        if len(scenes) > 40:
            lines.append(f"- … und {len(scenes) - 40} weitere Szenen")
        title = f"Szenenregister ({total_chapters} Kapitel, {len(scenes)} Szenen)"
        summary = f"{len(scenes)} Szenen in {total_chapters} Kapiteln"
    else:
        lines.append("## Scene overview")
        lines.append(f"- **Detected scenes:** {len(scenes)} across {total_chapters} chapters")
        plateaus = list(report.get("pacing_plateaus") or [])
        if plateaus:
            lines.append(f"- **Pacing plateaus:** {len(plateaus)}")
        lines.append("\n## Scene list")
        for idx, sc in enumerate(scenes[:40], start=1):
            label = sc.get("scene_title") or f"Ch. {sc.get('chapter')} · Scene {sc.get('scene', idx)}"
            words = sc.get("words")
            feats = sc.get("features") or {}
            dlg = feats.get("dialog_pct")
            dlg_str = f" · Dialogue: {dlg:.0f}%" if isinstance(dlg, (int, float)) else ""
            hooks = f" · Entry/Exit: {sc.get('entry_hook_type') or '–'}/{sc.get('exit_hook_type') or '–'}"
            lines.append(f"- **{label}** ({words} words{dlg_str}{hooks})")
        if len(scenes) > 40:
            lines.append(f"- … and {len(scenes) - 40} more scenes")
        title = f"Scene register ({total_chapters} chapters, {len(scenes)} scenes)"
        summary = f"{len(scenes)} scenes across {total_chapters} chapters"
    return {
        "id": "scenes:manuscript",
        "kind": "scene",
        "title": title,
        "summary": summary,
        "tags": ["manuscript-draft", "scenes"],
        "body": "\n".join(lines),
        "evidence_hints": {"chapters": total_chapters, "scenes": len(scenes)},
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
    excluded_character_names: set[str] = set()

    if want_characters or want_locations:
        resolved = resolve_character_settings(None, settings)
        names_input: Mapping[str, str] | Sequence[str] = (
            resolved.names or _auto_character_names(chapters)
        )
        if isinstance(names_input, Mapping):
            excluded_character_names.update(str(v).casefold() for v in names_input.values())
            excluded_character_names.update(str(k).casefold() for k in names_input)
        else:
            excluded_character_names.update(str(n).casefold() for n in names_input)
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
        sc_report = scene_report(text, config, scene_settings)
        sc_draft = _scenes_draft(report=sc_report, total_chapters=total_chapters, is_de=is_de)
        if sc_draft is not None:
            drafts.append(sc_draft)
        drafts.extend(_individual_scene_drafts(report=sc_report, is_de=is_de))

    if want_locations:
        raw_locs = (settings or {}).get("locations") or (settings or {}).get("places") or []
        configured_locs = [str(item) for item in raw_locs] if isinstance(raw_locs, Sequence) and not isinstance(raw_locs, str) else []
        drafts.extend(
            _extract_location_drafts(
                chapters,
                excluded_names=excluded_character_names,
                configured_locations=configured_locs,
                is_de=is_de,
            )
        )

    return {
        "schema_version": DRAFT_SCHEMA,
        "language": lang_key,
        "chapters": total_chapters,
        "drafts": drafts,
    }
