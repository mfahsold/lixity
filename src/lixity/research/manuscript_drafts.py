"""Deterministic, read-only dossier draft synthesis from manuscript analysis signals."""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any

from ..characters import presence_report, resolve_character_settings
from ..dialogue import character_voice_profiles
from ..language import resolve_language
from ..markdown_parser import prose_paragraphs, split_chapters
from ..models import CorpusConfig
from ..scenes import _chapter_recurring_names, scene_report

DRAFT_SCHEMA = "manuscript-dossier-drafts/1"
_MAX_AUTO_CHARACTERS = 12


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return cleaned or "entry"


def _auto_character_names(chapters: Sequence[tuple[int, str, str]]) -> list[str]:
    counts: Counter[str] = Counter()
    for _chapter_num, _chapter_title, chapter_body in chapters:
        paragraphs = prose_paragraphs(chapter_body)
        recurring = _chapter_recurring_names(paragraphs)
        for name in recurring:
            counts[name] += sum(1 for para in paragraphs if name in para)
    return [name for name, _count in counts.most_common(_MAX_AUTO_CHARACTERS)]


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


def _character_draft(
    *,
    figure: Mapping[str, Any],
    voice: Mapping[str, Any] | None,
    first_hit: Mapping[str, Any] | None,
    total_chapters: int,
    is_de: bool,
) -> dict[str, Any]:
    name = str(figure.get("name") or "").strip()
    total = int(figure.get("mentions") or figure.get("total") or 0)
    chapters_present = [
        int(ch) for ch in (figure.get("chapters_present") or figure.get("chapters") or [])
    ]
    pov_chapters = [int(ch) for ch in (figure.get("pov_chapters") or [])]
    pov_gaps = figure.get("longest_gap") if figure.get("longest_gap") is not None else figure.get("pov_max_gap")
    aliases = [str(a) for a in (figure.get("aliases") or []) if str(a).strip()]

    sections: list[str] = []
    if is_de:
        sections.append(f"## Überblick\n- **Figur:** {name}")
        if aliases:
            sections.append(f"- **Aliase / Schreibweisen:** {', '.join(aliases)}")
        sections.append(
            f"- **Erwähnungen:** {total} in {len(chapters_present)} von {total_chapters} Kapiteln"
            + (f" (Kapitel {', '.join(str(c) for c in chapters_present[:12])})" if chapters_present else "")
        )
        if pov_chapters:
            sections.append(f"- **POV-Kapitel:** {', '.join(str(c) for c in pov_chapters)}")
            if isinstance(pov_gaps, int) and pov_gaps > 0:
                sections.append(f"- **Größte POV-Lücke:** {pov_gaps} Kapitel")
        if voice and voice.get("turns"):
            turns = int(voice["turns"])
            mean_len = voice.get("mean_sentence_words")
            q_share = voice.get("question_ratio")
            sections.append(
                "\n## Dialogprofil\n"
                f"- **Erkannte Redezüge:** {turns}"
                + (f"\n- **Mittlere Satzlänge im Dialog:** {float(mean_len):.1f} Wörter" if mean_len is not None else "")
                + (f"\n- **Frageanteil:** {float(q_share) * 100:.0f} %" if q_share is not None else "")
            )
        if first_hit:
            sections.append(
                "\n## Erste Textstelle\n"
                f"- Kapitel {first_hit['chapter']} ({first_hit['chapter_title']}), Zeile {first_hit['line']}: „{first_hit['quote']}“"
            )
        summary = f"{total} Erwähnungen · {len(chapters_present)}/{total_chapters} Kapitel" + (
            f" · {int(voice['turns'])} Dialogzüge" if voice and voice.get("turns") else ""
        )
        title = f"Figur: {name}"
    else:
        sections.append(f"## Overview\n- **Character:** {name}")
        if aliases:
            sections.append(f"- **Aliases:** {', '.join(aliases)}")
        sections.append(
            f"- **Mentions:** {total} across {len(chapters_present)} of {total_chapters} chapters"
            + (f" (chapters {', '.join(str(c) for c in chapters_present[:12])})" if chapters_present else "")
        )
        if pov_chapters:
            sections.append(f"- **POV chapters:** {', '.join(str(c) for c in pov_chapters)}")
            if isinstance(pov_gaps, int) and pov_gaps > 0:
                sections.append(f"- **Largest POV gap:** {pov_gaps} chapters")
        if voice and voice.get("turns"):
            turns = int(voice["turns"])
            mean_len = voice.get("mean_sentence_words")
            q_share = voice.get("question_ratio")
            sections.append(
                "\n## Dialogue voice\n"
                f"- **Attributed turns:** {turns}"
                + (f"\n- **Mean dialogue sentence length:** {float(mean_len):.1f} words" if mean_len is not None else "")
                + (f"\n- **Question ratio:** {float(q_share) * 100:.0f} %" if q_share is not None else "")
            )
        if first_hit:
            sections.append(
                "\n## First manuscript passage\n"
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
    config = CorpusConfig(language=language)
    lang_key = resolve_language(config).key
    is_de = lang_key == "de"
    chapters = split_chapters(text, config)
    total_chapters = len(chapters)

    drafts: list[dict[str, Any]] = []
    want_characters = kind in ("all", "character", "characters")
    want_scenes = kind in ("all", "scene", "scenes")

    if want_characters:
        resolved = resolve_character_settings(None, settings or {})
        names_input: Mapping[str, str] | Sequence[str] = (
            resolved.names or _auto_character_names(chapters)
        )
        if names_input:
            pres = presence_report(
                text,
                names_input,
                config,
                declared_pov=resolved.declared_pov or None,
            )
            voices_raw = pres.get("character_voices") or character_voice_profiles(text, names_input, config)
            voice_by_name = {
                str(entry.get("name")): entry
                for entry in (voices_raw.get("characters") or voices_raw.get("profiles") or [])
                if entry.get("name")
            }
            for fig in pres.get("figures") or []:
                fig_name = str(fig.get("name") or "").strip()
                if not fig_name or int(fig.get("mentions") or fig.get("total") or 0) <= 0:
                    continue
                first_hit = _first_quote_for_name(chapters, fig_name)
                drafts.append(
                    _character_draft(
                        figure=fig,
                        voice=voice_by_name.get(fig_name),
                        first_hit=first_hit,
                        total_chapters=total_chapters,
                        is_de=is_de,
                    )
                )

    if want_scenes:
        sc_report = scene_report(text, config, settings)
        sc_draft = _scenes_draft(report=sc_report, total_chapters=total_chapters, is_de=is_de)
        if sc_draft is not None:
            drafts.append(sc_draft)

    return {
        "schema_version": DRAFT_SCHEMA,
        "language": lang_key,
        "chapters": total_chapters,
        "drafts": drafts,
    }
