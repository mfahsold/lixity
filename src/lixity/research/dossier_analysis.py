"""Preserve authored dossier text while presenting and refreshing generated analysis."""

from __future__ import annotations

import re
from dataclasses import dataclass
from itertools import pairwise

from ..workspace_labels import workspace_labels_for
from .dossier_markdown import chapter_heading, name_mentions_summary
from .images import markdown_code_mask
from .models import Dossier
from .repository import Snapshot, digest
from .sections import _section_spans

# Stored Markdown can outlive translations. These are the exact headings and
# interchangeable gap labels written by the two unmarked character exporters.
_LEGACY_REPORTS = {
    "Auswertung aus dem Manuskript": (
        "Figur im Manuskript", "Namensnennungen pro Kapitel", "Fundstellen lesen",
        "Längste Lücke zwischen Treffern (Kapitel)",
        "Längste Lücke zwischen Namensnennungen (Kapitel ohne Treffer)",
    ),
    "Analysis from the manuscript": (
        "Character in the manuscript", "Name mentions by chapter", "Read the matching passages",
        "Longest gap between matching chapters (chapters)",
        "Longest gap between mentions (chapters without a match)",
    ),
    "Análisis del manuscrito": (
        "Personaje en el manuscrito", "Menciones del nombre por capítulo", "Leer los pasajes encontrados",
        "Mayor intervalo entre capítulos con menciones (en capítulos)",
        "Mayor intervalo entre menciones (capítulos sin coincidencias)",
    ),
    "Analyse tirée du manuscrit": (
        "Personnage dans le manuscrit", "Mentions du nom par chapitre", "Lire les passages repérés",
        "Plus long intervalle entre deux chapitres avec des mentions (en chapitres)",
        "Plus long intervalle entre deux mentions (chapitres sans mention)",
    ),
    "Analisi dal manoscritto": (
        "Personaggio nel manoscritto", "Menzioni del nome per capitolo", "Leggi i passaggi trovati",
        "Intervallo più lungo tra capitoli con menzioni (in capitoli)",
        "Intervallo più lungo tra le menzioni (capitoli senza riscontri)",
    ),
    "Analyse uit het manuscript": (
        "Personage in het manuscript", "Naamsvermeldingen per hoofdstuk", "Gevonden passages lezen",
        "Langste afstand tussen hoofdstukken met treffers (in hoofdstukken)",
        "Langste gat tussen vermeldingen (hoofdstukken zonder treffer)",
    ),
    "Análise do manuscrito": (
        "Personagem no manuscrito", "Menções do nome por capítulo", "Ler os trechos encontrados",
        "Maior intervalo entre capítulos com menções (em capítulos)",
        "Maior intervalo entre menções (capítulos sem ocorrências)",
    ),
}

_OPEN = re.compile(r"^<!-- lixity:character-analysis ([0-9a-f]{64}) -->\r?\n", re.MULTILINE)
_CLOSE = re.compile(r"^<!-- /lixity:character-analysis -->(?:\r?\n|\Z)", re.MULTILINE)
_LEGACY_REPORT_SECTIONS: dict[tuple[str, ...], tuple[str, str]] = {
    values[:3]: (values[3], values[4]) for values in _LEGACY_REPORTS.values()
}
_LEGACY_PREVIEWS = {
    "de": re.compile(
        r"## Überblick\n- \*\*Figur:\*\* (?P<name>[^\n]+)\n"
        r"- \*\*Erwähnungen:\*\* (?P<mentions>\d{1,9}) in (?P<covered>\d{1,9}) von (?P<total>\d{1,9}) Kapiteln"
        r"(?: \(Kapitel (?P<chapters>\d+(?:, \d+)*)\))?\n\n"
        r"## Erste Textstelle\n- Kapitel (?P<chapter>\d{1,9}) \((?P<title>[^\n]+)\), "
        r"Zeile (?P<line>\d+): „(?P<quote>[^\n]+)“",
    ),
    "en": re.compile(
        r"## Overview\n- \*\*Character:\*\* (?P<name>[^\n]+)\n"
        r"- \*\*Mentions:\*\* (?P<mentions>\d{1,9}) across (?P<covered>\d{1,9}) of (?P<total>\d{1,9}) chapters"
        r"(?: \(chapters (?P<chapters>\d+(?:, \d+)*)\))?\n\n"
        r"## First manuscript passage\n- Chapter (?P<chapter>\d{1,9}) \((?P<title>[^\n]+)\), "
        r"line (?P<line>\d+): “(?P<quote>[^\n]+)”",
    ),
}


@dataclass(frozen=True)
class _Analysis:
    start: int
    end: int
    text_end: int
    key: str
    managed: bool = False
    marked: bool = False


def _marked_analyses(body: str) -> list[_Analysis]:
    boundaries = markdown_code_mask(body, inline=False)
    markers = sorted((*_OPEN.finditer(boundaries), *_CLOSE.finditer(boundaries)), key=lambda marker: marker.start())
    result = []
    for start, end in pairwise(markers):
        if start.re is _OPEN and end.re is _CLOSE:
            heading_start = body.rfind("\n", 0, start.start() - 1) + 1
            heading = body[heading_start:start.start()]
            if not heading.startswith("## "):
                continue
            contents = heading + body[start.end():end.start()]
            checksum = digest(contents.encode("utf-8"))
            result.append(_Analysis(heading_start, end.end(), end.start(), checksum,
                                    managed=checksum == start.group(1), marked=True))
    return result


def _legacy_analyses(body: str, start: int, end: int) -> list[_Analysis]:
    region = body[start:end]
    if not any(f"## {heading}" in region for heading in _LEGACY_REPORTS):
        return []
    headings = _section_spans(region)
    outer = [(index, heading) for index, heading in enumerate(headings) if heading.level <= 2]
    result = []
    for (index, heading), (next_index, next_heading) in pairwise([*outer, (len(headings), None)]):
        if heading is None:
            continue
        if heading.level != 2 or heading.title not in _LEGACY_REPORTS:
            continue
        sections = headings[index + 1:next_index]
        legacy = _LEGACY_REPORT_SECTIONS.get(tuple(part.title for part in sections if part.level == 3))
        if legacy is None:
            continue
        # The one known label-only change is safe to ignore only in the facts
        # of the opening section. Quoted prose and authored edits stay exact.
        summary = sections[0]
        old_gap, new_gap = legacy
        summary_body = region[summary.content_start:summary.end]
        gap_line = re.compile(rf"^(- \*\*){re.escape(old_gap)}(?=:\*\* [0-9]+\r?$)", re.MULTILINE)
        normalized = gap_line.sub(r"\g<1>" + new_gap, summary_body, count=1)
        section_end = next_heading.start if next_heading else len(region)
        canonical = (region[heading.start:summary.content_start] + normalized
                     + region[summary.end:section_end]).rstrip("\r\n")
        result.append(_Analysis(start + heading.start, start + section_end, start + section_end,
                                digest(canonical.encode("utf-8"))))
    return result


def _analyses(body: str) -> list[_Analysis]:
    marked = _marked_analyses(body) if "<!-- lixity:character-analysis " in body else []
    result = []
    cursor = 0
    for block in marked:
        result.extend(_legacy_analyses(body, cursor, block.start))
        result.append(block)
        cursor = block.end
    result.extend(_legacy_analyses(body, cursor, len(body)))
    return result


def _redundant_legacy_preview(body: str, original: Dossier, blocks: list[_Analysis]) -> int:
    """Hide the exact first-version stub only when all its evidence is retained."""
    preview = _LEGACY_PREVIEWS.get(original.language)
    initial = original.body.rstrip("\r\n")
    if preview is None or not body.startswith(initial + "\n\n") or not blocks:
        return 0
    match = preview.fullmatch(initial)
    if match is None:
        return 0
    language = original.language
    labels = workspace_labels_for(language)
    summary = name_mentions_summary(match["name"], int(match["mentions"]), int(match["covered"]),
                                    int(match["total"]), labels, language)
    chapter = chapter_heading(int(match["chapter"]), match["title"], labels, language)
    prefix, one, many = ("Kapiteltext", "Zeile", "Zeilen") if language == "de" else ("Chapter text", "line", "lines")
    line = match["line"]
    line_pattern = re.compile(rf"^\*\*{prefix} · (?:{one} {line}|{many} {line}–\d+)\*\*$", re.MULTILINE)
    for block in blocks:
        if block.marked:
            continue
        analysis = body[block.start:block.text_end]
        if f"\n\n{summary}\n\n" not in analysis or any(
            re.search(rf"^\| {number} \| [1-9]", analysis, re.MULTILINE) is None
            for number in (match["chapters"] or "").split(", ") if number
        ):
            continue
        for heading in _section_spans(analysis):
            if heading.level != 4 or heading.title != chapter:
                continue
            excerpts = line_pattern.split(analysis[heading.content_start:heading.end])[1:]
            passage_label = f"> **{labels['research_read_passage']}**\n>\n> "
            if any(match["quote"] in excerpt.partition(passage_label)[2].split("\n\n", 1)[0] for excerpt in excerpts):
                return len(initial) + 2
    return 0


def _character_analysis_display(body: str, original: Dossier) -> str:
    blocks = _analyses(body)
    latest = {block.key: block for block in blocks}
    visible = 0
    cursor = _redundant_legacy_preview(body, original, list(latest.values()))
    parts = []
    for block in blocks:
        parts.append(body[cursor:block.start])
        if latest[block.key] == block:
            visible += 1
            contents = body[block.start:block.text_end]
            if block.marked:
                contents = _OPEN.sub("", contents, count=1)
            if len(latest) > 1:
                contents = re.sub(r"^(## [^\r\n]+)", rf"\g<1> ({visible})", contents, count=1)
            parts.append(contents)
        cursor = block.end
    return "".join((*parts, body[cursor:]))


def dossier_display_body(snapshot: Snapshot, dossier: Dossier) -> str:
    """Read a saved dossier without repeating identical generated reports."""
    original = snapshot.revisions.get((dossier.id, 1))
    if isinstance(original, Dossier) and {"character", "manuscript-draft"}.issubset(original.tags):
        return _character_analysis_display(dossier.body, original)
    return dossier.body


def mark_character_analysis(markdown: str) -> str:
    """Mark the exact generated text so future refreshes can detect manual edits."""
    contents = markdown.strip() + "\n\n"
    checksum = digest(contents.encode("utf-8"))
    heading, _, body = contents.partition("\n")
    return f"{heading}\n<!-- lixity:character-analysis {checksum} -->\n{body}<!-- /lixity:character-analysis -->\n"


def prepare_character_analysis(body: str, analysis: str, language: str) -> str:
    """Stage a full-body proposal, replacing only a verified generated block."""
    if body.strip() == analysis.strip():
        return body
    heading = workspace_labels_for(language)["research_dossier_draft_refresh_heading"]
    nested = re.sub(r"^(#{2,5}) ", r"#\1 ", analysis.strip(), flags=re.MULTILINE)
    report = mark_character_analysis(f"## {heading}\n\n{nested}")
    marked = _marked_analyses(body) if "<!-- lixity:character-analysis " in body else []
    managed = next((block for block in reversed(marked) if block.managed), None)
    if managed is not None:
        return body[:managed.start] + report + body[managed.end:]
    separator = "" if not body or body.endswith(("\n\n", "\r\n\r\n")) else "\n" if body.endswith("\n") else "\n\n"
    return body + separator + report
