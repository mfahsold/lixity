"""Read-only manuscript evidence for a saved character dossier."""

from __future__ import annotations

import json
import re
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from itertools import groupby, islice, pairwise
from typing import Any

from ..characters import _mention_spans, _name_pattern, resolve_character_settings
from ..dialogue import character_voice_profiles
from ..dossier_draft_settings import (
    DEFAULT_CHARACTER_CONTEXT_SENTENCES,
    DEFAULT_INFERRED_DOSSIER_LIMIT,
    resolve_dossier_draft_settings,
)
from ..format import num, pct
from ..markdown_parser import (
    CountedChapterPassage,
    chapter_body_line_offsets,
    counted_chapter_passages,
    counting_inline_text,
    prose_paragraphs,
    split_chapters,
)
from ..models import CorpusConfig
from ..pipeline import document_paragraph_texts, paragraph_identity, resolve_document_config
from ..scenes import _chapter_recurring_names
from ..sentences import split_prose_sentence_spans, split_sentence_spans
from ..workspace_labels import workspace_labels_for
from .dossier_markdown import (
    chapter_heading,
    chapter_line_range,
    chapter_mention_table,
    dossier_quote,
)

CHARACTER_EVIDENCE_SCHEMA = "dossier-character-local/1"
_PASSAGES_PER_PAGE = 20
_PASSAGE_TEXT_BYTES_PER_PAGE = 64 * 1024


class CharacterEvidenceChanged(ValueError):
    """The source or rules changed between reads."""


def character_dialogue_evidence(profile: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if profile is None:
        return None
    return {
        "status": profile["status"], "turns": profile["turns"],
        "min_turns": profile["min_turns"], "words": profile["words"],
        "mean_sentence_words": profile["dialogue_asl"], "question_excl_pct": profile["question_excl_rate"],
    }


def character_dialogue_markdown(voice: Mapping[str, Any], labels: Mapping[str, str], language: str) -> str:
    def label(suffix: str) -> str:
        return labels["research_dossier_character_" + suffix]

    facts = [f"- **{label('turns')}:** {num(voice['turns'], language, 0)}"]
    if voice["mean_sentence_words"] is not None:
        facts.append(f"- **{label('sentence_words')}:** {num(voice['mean_sentence_words'], language)}")
    if voice["question_excl_pct"] is not None:
        facts.append(f"- **{label('questions')}:** {pct(voice['question_excl_pct'], language)}")
    body = "\n".join(facts)
    if voice["status"] == "insufficient_turns":
        body += "\n\n" + label("dialogue_sample").format(minimum=num(voice["min_turns"], language, 0))
    return body


def _longest_mention_gap(chapters: Sequence[int]) -> tuple[int, int] | None:
    return max(((a + 1, b - 1) for a, b in pairwise(chapters) if b > a + 1),
               key=lambda bounds: bounds[1] - bounds[0], default=None)


def character_overview_markdown(
    mentions: int, chapters: Sequence[int], total_chapters: int, *,
    aliases: Sequence[str], pov_chapters: Sequence[int], language: str,
) -> list[str]:
    """Describe counted coverage and meaningful chapter boundaries once."""
    labels = workspace_labels_for(language)

    def label(suffix: str) -> str:
        return labels["research_dossier_character_" + suffix]

    def number(value: int) -> str:
        return num(value, language, 0)

    coverage = label("coverage_one" if mentions == 1 else "coverage").format(
        mentions=number(mentions), covered=number(len(chapters)), chapters=number(total_chapters),
    )
    blocks = [f"## {label('heading')}", coverage, label("scope")]
    facts = []
    if len(chapters) > 1:
        span = label("span").format(first=number(chapters[0]), last=number(chapters[-1]))
        facts.append(f"- {span}")
    if gap := _longest_mention_gap(chapters):
        first, last = gap
        span = label("gap_chapter" if first == last else "gap_chapters")
        facts.append("- " + span.format(first=number(first), last=number(last)))
    if aliases:
        facts.append(f"- **{label('aliases')}:** {', '.join(aliases)}")
    if pov_chapters:
        declared = ", ".join(number(chapter) for chapter in pov_chapters)
        facts.append(f"- **{label('pov')}:** {declared}")
    if facts:
        blocks.append("\n".join(facts))
    return blocks


def _auto_character_names(
    chapters: Sequence[tuple[int, str, str]], *, limit: int = DEFAULT_INFERRED_DOSSIER_LIMIT,
) -> list[str]:
    if not limit:
        return []
    counts: Counter[str] = Counter()
    for _number, _title, body in chapters:
        paragraphs = prose_paragraphs(body, _front_matter=False)
        for name in _chapter_recurring_names(paragraphs):
            counts[name] += sum(1 for paragraph in paragraphs if name in paragraph)
    return sorted(counts, key=lambda name: (-counts[name], name.casefold(), name))[:limit]


def _neighboring_prose(
    parts: Sequence[CountedChapterPassage], boundary: int, indices: range, needed: int,
    language: str,
) -> str:
    """Take nearest measured sentences while staying in the same region."""
    snippets: list[str] = []
    preceding = indices.step == -1
    for index in indices:
        part = parts[index]
        if needed <= 0 or part.region != parts[boundary].region:
            break
        spans = split_sentence_spans(part.text, language)
        chosen = spans[-needed:] if preceding else spans[:needed]
        if chosen:
            snippets.append(part.text[chosen[0][0]:chosen[-1][1]])
            needed -= len(chosen)
    return "\n\n".join(reversed(snippets) if preceding else snippets)


@dataclass(frozen=True)
class _ChapterMatches:
    parts: list[CountedChapterPassage]
    offsets: list[int]
    prose: str
    groups: list[tuple[int, int, list[tuple[int, int]]]]
    mentions: int

    def passages(
        self, *, offset: int = 0, context_language: str | None = None,
        context_sentences: int = DEFAULT_CHARACTER_CONTEXT_SENTENCES,
    ) -> Iterator[dict[str, Any]]:
        for index in range(offset, len(self.groups)):
            left, right, spans = self.groups[index]
            # Keep literal separators, even for a configured pattern that ends in
            # the whitespace between paragraphs.
            start = self.offsets[left]
            end = max(self.offsets[right] + len(self.parts[right].text), spans[-1][1])
            excerpt = self.prose[start:end]
            passage = {
                "start_line": self.parts[left].start_line, "end_line": self.parts[right].end_line,
                "text": excerpt,
                "matches": [{"start": a - start, "end": b - start} for a, b in spans],
            }
            if context_language is not None:
                passage.update(context_before="", context_after="")
            if context_language is not None and context_sentences:
                excerpt_sentences = split_prose_sentence_spans(excerpt, context_language)
                first_hit, last_hit = spans[0][0] - start, spans[-1][1] - start
                before = context_sentences - sum(b <= first_hit for _, b in excerpt_sentences)
                after = context_sentences - sum(a >= last_hit for a, _ in excerpt_sentences)
                previous_hit = self.groups[index - 1][1] if index else -1
                next_hit = self.groups[index + 1][0] if index + 1 < len(self.groups) else len(self.parts)
                passage["context_before"] = _neighboring_prose(
                    self.parts, left, range(left - 1, previous_hit, -1), before, context_language,
                )
                passage["context_after"] = _neighboring_prose(
                    self.parts, right, range(right + 1, next_hit), after, context_language,
                )
            yield passage


def _chapter_match_groups(body: str, patterns: list[re.Pattern[str]]) -> _ChapterMatches:
    """Count the full chapter and retain the ranges needed to read selected hits."""
    parts = list(counted_chapter_passages(body))
    if not parts:
        return _ChapterMatches([], [], "", [], 0)
    offsets: list[int] = []
    cursor = 0
    for part in parts:
        offsets.append(cursor)
        cursor += len(part.text) + 2
    prose = "\n\n".join(part.text for part in parts)
    matches = _mention_spans(prose, patterns)
    groups: list[tuple[int, int, list[tuple[int, int]]]] = []
    for start, end in matches:
        left = bisect_right(offsets, start) - 1
        right = bisect_left(offsets, max(start + 1, end)) - 1
        # A configured pattern can span paragraphs. Keep the entire range in
        # the same excerpt, and let repeated matches share it.
        if groups and left <= groups[-1][1]:
            previous_left, previous_right, spans = groups.pop()
            spans.append((start, end))
            groups.append((previous_left, max(previous_right, right), spans))
        else:
            groups.append((left, right, [(start, end)]))
    return _ChapterMatches(parts, offsets, prose, groups, len(matches))


def _chapter_passages(
    body: str, patterns: list[re.Pattern[str]], *, context_language: str | None = None,
    context_sentences: int = DEFAULT_CHARACTER_CONTEXT_SENTENCES, limit: int | None = None,
) -> tuple[int, list[dict[str, Any]]]:
    """Group the same name matches as character presence into readable passages."""
    matches = _chapter_match_groups(body, patterns)
    passages = matches.passages(context_language=context_language, context_sentences=context_sentences)
    return matches.mentions, list(islice(passages, limit))


def _character_evidence(
    text: str,
    source_sha256: str,
    *,
    character: str,
    language: str,
    settings: Mapping[str, Any],
    context_sentences: int,
    chapter: int | None = None,
    offset: int | None = None,
    include_passages: bool = True,
    expected_analysis_sha256: str | None = None,
) -> tuple[CorpusConfig, dict[str, Any]]:
    """Measure chapter totals and project only requested passages."""
    config, resolved_language = resolve_document_config(text, language, project_config=settings)
    resolved = resolve_character_settings(None, settings)
    chapters = split_chapters(text, config)
    names = resolved.names or _auto_character_names(chapters)
    patterns = dict(names.items()) if isinstance(names, Mapping) else {name: name for name in names}
    selected_patterns = [pattern for pattern, label in patterns.items() if label == character]
    if not selected_patterns:
        literal = re.escape(character)
        if literal not in patterns:
            patterns[literal] = character
        selected_patterns = [literal]
    known_chapters = {number for number, _, _ in chapters}
    declared = [number for number in resolved.declared_pov.get(character, ()) if number in known_chapters]
    profiles = settings.get("characters", {})
    aliases = list((profiles.get(character) or {}).get("aliases", ()))

    analysis_sha256 = sha256(json.dumps({
        "schema": CHARACTER_EVIDENCE_SCHEMA, "source": source_sha256,
        "config": config.model_dump(mode="json"), "patterns": patterns,
        "character": character, "declared": declared, "aliases": aliases,
        "context_sentences": context_sentences,
    }, sort_keys=True).encode("utf-8")).hexdigest()
    if expected_analysis_sha256 is not None and expected_analysis_sha256 != analysis_sha256:
        raise CharacterEvidenceChanged("Manuscript or character settings changed; reopen the evidence")
    if chapter is not None and chapter not in known_chapters:
        raise ValueError("Choose a chapter in the selected manuscript")

    compiled = [_name_pattern(pattern) for pattern in selected_patterns]
    chapter_rows: list[dict[str, Any]] = []
    ordered_chapters: list[int] = []
    selected_passages: list[dict[str, Any]] = []
    passage_count = 0
    page_bytes = 0
    page_complete = False
    for number, title, body in chapters:
        matches = _chapter_match_groups(body, compiled)
        count = len(matches.groups)
        chapter_rows.append({"chapter": number, "chapter_title": title, "mentions": matches.mentions,
                             "passage_count": count})
        if matches.mentions:
            ordered_chapters.append(number)
        if chapter is not None and chapter != number:
            continue
        first = max(0, (offset or 0) - passage_count)
        passage_count += count
        if not include_passages or page_complete or first >= count:
            continue
        passages = matches.passages(
            offset=first, context_language=resolved_language.key, context_sentences=context_sentences,
        )
        if offset is None:
            selected_passages.extend({"chapter": number, "chapter_title": title, **row} for row in passages)
            continue
        for row in islice(passages, _PASSAGES_PER_PAGE - len(selected_passages)):
            size = sum(len(row[key].encode("utf-8")) for key in ("text", "context_before", "context_after"))
            # A paragraph larger than the ordinary page budget gets a page of its own.
            if selected_passages and page_bytes + size > _PASSAGE_TEXT_BYTES_PER_PAGE:
                page_complete = True
                break
            selected_passages.append({"chapter": number, "chapter_title": title, **row})
            page_bytes += size
        page_complete = page_complete or len(selected_passages) >= _PASSAGES_PER_PAGE

    voices = character_voice_profiles(text, patterns, config, _include_narrator_and_interactions=False)
    profile = next((entry for entry in voices["characters"] if entry["name"] == character), None)
    gap = _longest_mention_gap(ordered_chapters)
    return config, {
        "schema_version": CHARACTER_EVIDENCE_SCHEMA, "character": character, "aliases": aliases,
        "mentions": sum(row["mentions"] for row in chapter_rows),
        "chapters_with_mentions": len(ordered_chapters),
        "longest_gap": gap[1] - gap[0] + 1 if gap else 0,
        "longest_gap_chapters": gap,
        "declared_pov_chapters": declared, "dialogue": character_dialogue_evidence(profile),
        "chapters": chapter_rows, "passages": selected_passages, "passage_count": passage_count,
        "analysis_sha256": analysis_sha256, "source_sha256": source_sha256, "line_scope": "chapter_body",
        "context_sentences": context_sentences,
    }


def _attach_reader_anchors(page: Sequence[dict[str, Any]], text: str, config: CorpusConfig) -> None:
    """Link the start of a matching passage to an exact displayed paragraph."""
    if not page:
        return
    offsets = chapter_body_line_offsets(text, config)
    by_line = {(p.chapter_num, p.start_line): p for p in document_paragraph_texts(text, config)}
    for row in page:
        offset = offsets.get(row["chapter"])
        if offset is None:
            continue
        paragraph = by_line.get((row["chapter"], offset + row["start_line"]))
        if paragraph is None or paragraph.end_line > offset + row["end_line"]:
            continue
        displayed = counting_inline_text(paragraph.text)
        if displayed and (row["text"] == displayed or row["text"].startswith(displayed + "\n\n")):
            row["reader_anchor"] = paragraph_identity(paragraph)


def character_evidence(
    text: str,
    source_sha256: str,
    *,
    character: str,
    language: str,
    settings: Mapping[str, Any],
    chapter: int | None = None,
    offset: int = 0,
    expected_analysis_sha256: str | None = None,
) -> dict[str, Any]:
    """Return chapter counts and a page of full matching prose for one character."""
    if offset < 0:
        raise ValueError("Choose a valid page offset")
    config, report = _character_evidence(
        text, source_sha256, character=character, language=language, settings=settings,
        context_sentences=resolve_dossier_draft_settings(settings).character_context_sentences,
        chapter=chapter, offset=offset, expected_analysis_sha256=expected_analysis_sha256,
    )
    page = report["passages"]
    _attach_reader_anchors(page, text, config)
    end = offset + len(page)
    report.update(passages=page, offset=offset, next_offset=end if end < report["passage_count"] else None)
    return report


def character_dossier_text(
    text: str,
    source_sha256: str,
    *,
    character: str,
    language: str,
    settings: Mapping[str, Any],
) -> dict[str, Any]:
    """Prepare a complete, readable character analysis for a dossier revision."""
    draft_settings = resolve_dossier_draft_settings(settings)
    config, report = _character_evidence(
        text, source_sha256, character=character, language=language, settings=settings,
        context_sentences=draft_settings.character_context_sentences,
        include_passages=draft_settings.character_report_passages,
    )
    language_key = config.language
    labels = workspace_labels_for(language_key)

    def label(suffix: str) -> str:
        return labels["research_dossier_character_" + suffix]

    chapters = report["chapters"]
    hits = [row for row in chapters if row["mentions"]]
    blocks = character_overview_markdown(
        report["mentions"], [row["chapter"] for row in hits], len(chapters), aliases=report["aliases"],
        pov_chapters=report["declared_pov_chapters"], language=language_key,
    )

    if hits:
        distribution = chapter_mention_table(((row["chapter"], row["mentions"]) for row in hits), labels, language_key)
        blocks.extend((f"## {label('distribution')}", distribution))
    voice = report["dialogue"]
    if voice and voice["turns"]:
        blocks.extend((f"## {label('dialogue')}", character_dialogue_markdown(voice, labels, language_key)))

    if draft_settings.character_report_passages:
        blocks.extend((f"## {label('passages')}", label("context_hint" if report["passages"] else "empty")))
        passage_groups = groupby(report["passages"], key=lambda row: (row["chapter"], row["chapter_title"]))
        for (chapter, source_title), passages in passage_groups:
            blocks.append(f"### {chapter_heading(chapter, source_title, labels, language_key)}")
            for row in passages:
                lines = chapter_line_range(row["start_line"], row["end_line"], labels, language_key)
                blocks.append(f"**{lines}**")
                if row["context_before"]:
                    blocks.append(dossier_quote(row["context_before"], label=label("context_before")))
                blocks.append(dossier_quote(row["text"], matches=((span["start"], span["end"]) for span in row["matches"])))
                if row["context_after"]:
                    blocks.append(dossier_quote(row["context_after"], label=label("context_after")))

    return {
        "body": "\n\n".join(blocks), "analysis_sha256": report["analysis_sha256"],
        "mentions": report["mentions"], "passage_count": report["passage_count"],
        "chapters_with_mentions": report["chapters_with_mentions"], "chapter_count": len(chapters),
        "context_sentences": report["context_sentences"],
        "includes_passages": draft_settings.character_report_passages,
    }
