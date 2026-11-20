"""lixity.motifs – motif tracking and repetition analysis.

Two complementary views for macro editing:

- **Motifs** (project-specific): where a curated motif appears across the
  chapters — mentions, density, first/last chapter, longest gap. Patterns are
  regular expressions, so a motif can cover a word field ("Wut|wütend").
- **Repetition** (generic, no configuration): the most frequent content words
  (function words and stop words excluded) and repeated n-grams (default
  3-grams) with their chapter spread. Deterministic, offline, no embeddings.

Repetition is a *signal*, not a verdict: deliberate repetition is a stylistic
device. The report provides counts and locations so the editor can decide.
"""

from __future__ import annotations

import re
import unicodedata
from bisect import bisect_left, bisect_right
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from itertools import accumulate, pairwise
from typing import TYPE_CHECKING, Any

from .language import compile_pattern, compile_word_pattern, resolve_language
from .markdown_parser import (
    _chapter_spans,
    before_appendix,
    chapter_heading_spans,
    counting_inline_text,
    parse_markdown_blocks,
    prose_text,
    split_chapters,
    strip_inline_markup,
)
from .models import CorpusConfig
from .quotation import QuotationAnalysis, quotation_context
from .quotation_projection import QuotedProse, project_quotations, quoted_prose
from .text_normalization import CountingText, counting_view

if TYPE_CHECKING:
    from .style_profile import ParagraphProfile, ParagraphText

MIN_PHRASE_COUNT = 3  # a repeated n-gram must occur at least this often
DEFAULT_PHRASE_SIZE = 3
DEFAULT_TOP_WORDS = 15
DEFAULT_TOP_PHRASES = 10
DEFAULT_ECHO_WINDOW = 300
DEFAULT_ECHO_MIN_COUNT = 2
DEFAULT_TOP_ECHOES = 20
MAX_DISPLAY_OCCURRENCES = 250


def resolve_motif_settings(
    explicit: Mapping[str, str] | None, settings: Mapping[str, Any],
) -> dict[str, str]:
    """Resolve explicit patterns or compatible canonical/legacy project tables.

    An explicit mapping replaces project patterns, including an empty mapping.
    Project tables combine distinct names; conflicting duplicate names fail
    instead of silently changing which pattern a named motif measures.
    """
    tables = (("motifs", explicit),) if explicit is not None else (
        (key, settings[key]) for key in ("motif_regexes", "motifs") if key in settings
    )
    patterns: dict[str, str] = {}
    for key, table in tables:
        if not isinstance(table, Mapping):
            raise ValueError(f"{key} must be a table of motif names and regular expressions")
        for name, pattern in table.items():
            if not isinstance(name, str) or not name.strip() or not isinstance(pattern, str):
                raise ValueError(f"{key} must map nonblank motif names to regular-expression strings")
            try:
                compile_pattern(pattern)
            except ValueError as exc:
                raise ValueError(f"Invalid {key} pattern for {name}: {exc}") from exc
            if name in patterns and patterns[name] != pattern:
                raise ValueError(f"Conflicting motif {name} in motif_regexes and motifs")
            patterns[name] = pattern
    return patterns


@dataclass(frozen=True)
class MotifPresence:
    """Where one curated motif appears across the chapters."""

    name: str
    mentions: int
    density_per_1000: float
    chapters_present: list[int]
    first_chapter: int | None
    last_chapter: int | None
    longest_gap: int
    per_chapter: dict[int, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "mentions": self.mentions,
            "density_per_1000": round(self.density_per_1000, 3),
            "chapters_present": self.chapters_present,
            "first_chapter": self.first_chapter,
            "last_chapter": self.last_chapter,
            "longest_gap": self.longest_gap,
            "per_chapter": {str(k): v for k, v in sorted(self.per_chapter.items())},
        }


@dataclass(frozen=True)
class RepeatedPhrase:
    """One repeated n-gram with its chapter spread."""

    phrase: str
    count: int
    chapters: list[int]

    def to_dict(self) -> dict[str, Any]:
        return {"phrase": self.phrase, "count": self.count, "chapters": self.chapters}


@dataclass(frozen=True)
class Echo:
    """An n-gram's densest local cluster, with 1-based inclusive word bounds."""

    term: str
    chapter: int
    count: int
    first_word: int
    last_word: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "term": self.term,
            "chapter": self.chapter,
            "count": self.count,
            "first_word": self.first_word,
            "last_word": self.last_word,
        }


@dataclass(frozen=True)
class MotifReport:
    """Motif tracking plus generic repetition signals."""

    language: str
    chapters: int
    motifs: list[MotifPresence] = field(default_factory=list)
    top_words: list[tuple[str, int]] = field(default_factory=list)
    repeated_phrases: list[RepeatedPhrase] = field(default_factory=list)
    echoes: list[Echo] = field(default_factory=list)
    _locations: dict[str, list[_OccurrenceLocations]] = field(default_factory=dict, repr=False, compare=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "language": self.language,
            "chapters": self.chapters,
            "motifs": [motif.to_dict() for motif in self.motifs],
            "top_words": [{"word": word, "count": count} for word, count in self.top_words],
            "repeated_phrases": [phrase.to_dict() for phrase in self.repeated_phrases],
            "echoes": [echo.to_dict() for echo in self.echoes],
        }

    def to_display_dict(self) -> dict[str, Any]:
        """Supply verified reader locations while leaving the public report stable."""
        report = self.to_dict()
        for key, locations in self._locations.items():
            for row, location in zip(report[key], locations, strict=True):
                row["occurrences"] = location.items
                row["mapped_occurrence_count"] = location.count
        return report


@dataclass(frozen=True)
class _ReaderBlock:
    start: int
    index: int
    paragraph: ParagraphProfile | ParagraphText
    view: CountingText
    quotation: QuotationAnalysis


@dataclass
class _OccurrenceLocations:
    items: list[dict[str, Any]] = field(default_factory=list)
    count: int = 0

    def add(self, blocks: Sequence[_ReaderBlock], start: int, end: int) -> None:
        index = bisect_right(blocks, start, key=lambda block: block.start) - 1
        if index < 0 or start >= end:
            return
        block = blocks[index]
        left, right = start - block.start, end - block.start
        mapped = block.view.source_span(left, right)
        if mapped is None or mapped[0] >= mapped[1]:
            return
        self.count += 1
        if len(self.items) < MAX_DISPLAY_OCCURRENCES:
            occurrence = _make_occurrence(
                block.index, block.paragraph, block.view, left, right, quotation=block.quotation
            )
            if occurrence is not None:
                self.items.append(occurrence)


def _reader_block_ranges(
    text: str,
    config: CorpusConfig,
    chapter_prose: Mapping[int, str],
    paragraphs: Sequence[ParagraphProfile | ParagraphText],
    projection: QuotedProse,
) -> dict[int, list[_ReaderBlock]]:
    """Align the counted chapter projection to exact profiled line anchors."""
    by_line = {(p.chapter_num, p.start_line, p.end_line): (index, p)
               for index, p in enumerate(paragraphs)}
    source = before_appendix(text, config)
    line_offsets = [0, *accumulate(len(line) for line in source.splitlines(keepends=True))]
    headings = chapter_heading_spans(source, config)
    heading_lines = [line for _start, _end, line, _title in headings]
    output: dict[int, list[_ReaderBlock]] = {}
    for number, _title, body, heading_line in _chapter_spans(text, config):
        next_heading = bisect_right(heading_lines, heading_line)
        stop = headings[next_heading][0] if next_heading < len(headings) else len(source)
        offset = source.rfind(body, line_offsets[heading_line - 1], stop)
        if offset < 0 or source[offset + len(body):stop].strip():
            continue
        line_offset = bisect_left(line_offsets, offset)
        if line_offsets[line_offset] != offset:
            continue
        chunks: list[str] = []
        projected: list[_ReaderBlock] = []
        cursor = 0
        for raw in parse_markdown_blocks(body, _front_matter=False):
            kind = raw["type"]
            values = raw["paras"] if kind == "quote_block" else [raw["text"]] if kind in ("p", "list_item") else []
            for value in values:
                clean = counting_inline_text(value)
                if not clean:
                    continue
                anchor = (number, line_offset + raw["start_line"], line_offset + raw["end_line"])
                if kind != "quote_block" and anchor in by_line:
                    index, paragraph = by_line[anchor]
                    view = counting_view(paragraph.text)
                    if paragraph.text == strip_inline_markup(value) and view.text == clean:
                        quotation = projection.paragraph_analysis(paragraph.start_line)
                        projected.append(_ReaderBlock(cursor, index, paragraph, view, quotation))
                chunks.append(clean)
                cursor += len(clean) + 2
        if "\n\n".join(chunks) == chapter_prose[number]:
            output[number] = projected
    return output


def _gaps(present: list[int]) -> int:
    longest = 0
    for left, right in pairwise(present):
        longest = max(longest, right - left - 1)
    return longest


def motif_report(
    text: str,
    motifs: Mapping[str, str] | None = None,
    config: CorpusConfig | None = None,
    phrase_size: int = DEFAULT_PHRASE_SIZE,
    top_words: int = DEFAULT_TOP_WORDS,
    top_phrases: int = DEFAULT_TOP_PHRASES,
    echo_window: int = DEFAULT_ECHO_WINDOW,
    echo_min_count: int = DEFAULT_ECHO_MIN_COUNT,
    top_echoes: int = DEFAULT_TOP_ECHOES,
    *,
    _paragraphs: Sequence[ParagraphProfile | ParagraphText] | None = None,
    _projection: QuotedProse | None = None,
) -> MotifReport:
    """Motif presence and repetition signals (deterministic, offline).

    Omitted patterns inherit ``config.motif_regexes``; an explicit mapping,
    including ``{}``, replaces those configured patterns.
    """
    config = config or CorpusConfig()
    patterns = resolve_motif_settings(motifs, {"motif_regexes": config.motif_regexes})
    resolved = resolve_language(config, sample_text=text)
    word_re = compile_word_pattern(resolved.word_regex)
    content_blacklist = resolved.function_words | resolved.stopwords

    chapters = split_chapters(text, config)
    chapter_bodies = {
        number: prose_text(body, _front_matter=False)
        for number, _title, body in chapters
    }
    reader_blocks: dict[int, list[_ReaderBlock]] = {}
    token_spans: dict[int, list[tuple[int, int]]] = {}
    chapter_tokens: dict[int, list[str]] = {}
    if _paragraphs is None:
        chapter_tokens = {number: [token.lower() for token in word_re.findall(body)]
                          for number, body in chapter_bodies.items()}
    else:
        reader_blocks = _reader_block_ranges(
            text, config, chapter_bodies, _paragraphs, _projection or quoted_prose(text, config, language=resolved)
        )
        token_group = 1 if word_re.groups == 1 else 0
        for number, body in chapter_bodies.items():
            words, spans = [], []
            for match in word_re.finditer(body):
                words.append((match.group(token_group) or "").lower())
                spans.append(match.span(token_group))
            chapter_tokens[number] = words
            token_spans[number] = spans
    total_words = sum(len(tokens) for tokens in chapter_tokens.values())

    motif_items: list[MotifPresence] = []
    motif_locations: dict[str, _OccurrenceLocations] = {}
    for name, pattern in patterns.items():
        compiled = compile_pattern(pattern)
        per_chapter: dict[int, int] = {}
        locations = _OccurrenceLocations()
        for number, body in chapter_bodies.items():
            if _paragraphs is None:
                hits = len(compiled.findall(body))
            else:
                hits = 0
                for match in compiled.finditer(body):
                    hits += 1
                    locations.add(reader_blocks.get(number, ()), *match.span())
            if hits:
                per_chapter[number] = hits
        motif_locations[name] = locations
        present = sorted(per_chapter)
        mentions = sum(per_chapter.values())
        motif_items.append(
            MotifPresence(
                name=name,
                mentions=mentions,
                density_per_1000=(mentions / total_words * 1000.0) if total_words else 0.0,
                chapters_present=present,
                first_chapter=present[0] if present else None,
                last_chapter=present[-1] if present else None,
                longest_gap=_gaps(present),
                per_chapter=per_chapter,
            )
        )
    motif_items.sort(key=lambda item: (-item.mentions, item.name))

    # Generic repetition: content words and n-grams across the whole manuscript,
    # plus bounded local echo clusters per chapter (computed in one token pass).
    word_counts: Counter[str] = Counter()
    phrase_chapters: dict[str, set[int]] = {}
    phrase_counts: Counter[str] = Counter()
    echo_items: list[Echo] = []
    local_positions: dict[tuple[str, int], list[int]] = {}
    phrase_positions: dict[int, dict[str, list[int]]] = {}
    min_echo_cluster = max(2, echo_min_count)

    for number, tokens in chapter_tokens.items():
        word_counts.update(token for token in tokens if token not in content_blacklist)
        n_tokens = len(tokens)
        if n_tokens < phrase_size:
            continue
        is_blacklisted = [token in content_blacklist for token in tokens]
        occurrences: dict[str, list[int]] = {}
        for index in range(n_tokens - phrase_size + 1):
            if all(is_blacklisted[index : index + phrase_size]):
                continue  # pure function-word phrase: not a repetition signal
            phrase = " ".join(tokens[index : index + phrase_size])
            phrase_counts[phrase] += 1
            phrase_chapters.setdefault(phrase, set()).add(number)
            occurrences.setdefault(phrase, []).append(index)

        if _paragraphs is not None:
            phrase_positions[number] = occurrences
        for phrase, positions in occurrences.items():
            if len(positions) < echo_min_count:
                continue
            left = 0
            best_start = 0
            best_end = 0
            for right, position in enumerate(positions):
                while left <= right and position - positions[left] + phrase_size > echo_window:
                    left += 1
                if right - left + 1 > best_end - best_start:
                    best_start, best_end = left, right + 1
            cluster = positions[best_start:best_end]
            if len(cluster) < min_echo_cluster:
                continue
            local_positions[(phrase, number)] = cluster
            echo_items.append(
                Echo(
                    term=phrase,
                    chapter=number,
                    count=len(cluster),
                    first_word=cluster[0] + 1,
                    last_word=cluster[-1] + phrase_size,
                )
            )

    repeated = [
        RepeatedPhrase(phrase=phrase, count=count, chapters=sorted(phrase_chapters[phrase]))
        for phrase, count in phrase_counts.most_common(top_phrases)
        if count >= MIN_PHRASE_COUNT
    ]

    # Deduplicate shifted n-grams only when their actual occurrences overlap
    # in the same repeated passage. Shared vocabulary alone is insufficient:
    # "red wooden door" and "red metal door" are independent echo candidates.
    echo_items.sort(key=lambda e: (-e.count, e.chapter, e.first_word, e.term))
    deduped: list[Echo] = []
    kept_positions: dict[tuple[int, int], Echo] = {}
    for echo in echo_items:
        words = echo.term.split()
        positions = local_positions[(echo.term, echo.chapter)]
        duplicate = False
        for shift in range(1, phrase_size - 1):
            for offset in (shift, -shift):
                existing = kept_positions.get((echo.chapter, positions[0] + offset))
                if existing is None:
                    continue
                existing_words = existing.term.split()
                overlap = (words[offset:] == existing_words[:-offset] if offset > 0 else
                           words[:offset] == existing_words[-offset:])
                if overlap and all(
                    kept_positions.get((echo.chapter, position + offset)) == existing
                    for position in positions
                ):
                    duplicate = True
                    break
            if duplicate:
                break
        if not duplicate:
            deduped.append(echo)
            for position in positions:
                kept_positions[(echo.chapter, position)] = echo
    echo_items = deduped

    # Keep the most frequent echoes, capped.
    echo_items.sort(key=lambda e: (-e.count, e.chapter, e.term))
    echo_items = echo_items[:top_echoes]

    def add_ngram_locations(locations: _OccurrenceLocations, chapter: int, positions: Sequence[int]) -> None:
        if not positions or not reader_blocks.get(chapter) or phrase_size < 1:
            return
        spans = token_spans[chapter]
        for position in positions:
            phrase_spans = spans[position : position + phrase_size]
            if any(start < 0 or start >= end for start, end in phrase_spans) or any(
                first[1] > second[0] for first, second in pairwise(phrase_spans)
            ):
                continue
            locations.add(reader_blocks[chapter], phrase_spans[0][0], phrase_spans[-1][1])

    display_locations: dict[str, list[_OccurrenceLocations]] = {}
    if _paragraphs is not None:
        repeated_locations, echo_locations = [], []
        for item in repeated:
            locations = _OccurrenceLocations()
            for number in item.chapters:
                add_ngram_locations(locations, number, phrase_positions[number][item.phrase])
            repeated_locations.append(locations)
        for echo in echo_items:
            locations = _OccurrenceLocations()
            add_ngram_locations(locations, echo.chapter, local_positions[(echo.term, echo.chapter)])
            echo_locations.append(locations)
        display_locations = {
            "motifs": [motif_locations[item.name] for item in motif_items],
            "repeated_phrases": repeated_locations,
            "echoes": echo_locations,
        }
    return MotifReport(
        language=resolved.key,
        chapters=len(chapters),
        motifs=motif_items,
        top_words=word_counts.most_common(top_words),
        repeated_phrases=repeated,
        echoes=echo_items,
        _locations=display_locations,
    )


def _occurrence_excerpt(text: str, start: int, end: int, radius: int = 36) -> str:
    left = max(0, start - radius)
    right = min(len(text), end + radius)
    prefix = ("…" if left > 0 else "") + text[left:start].replace("\n", " ")
    quote = text[start:end].replace("\n", " ")
    suffix = text[end:right].replace("\n", " ") + ("…" if right < len(text) else "")
    return f"{prefix}{quote}{suffix}".strip()


def _is_word_char(char: str) -> bool:
    return char == "_" or unicodedata.category(char)[0] in ("L", "N")


class InvalidSearchPattern(ValueError):
    """A regular expression supplied for manuscript search could not be compiled."""


def compile_search_pattern(
    query: str,
    *,
    is_regex: bool = False,
    case_sensitive: bool = False,
) -> re.Pattern[str]:
    """Compile a literal multi-word phrase or optional regex for manuscript search."""
    if not isinstance(query, str):
        raise ValueError("Search query must be a string")
    trimmed = query.strip()
    if not trimmed:
        raise ValueError("Search query must not be empty")
    flags = 0 if case_sensitive else re.IGNORECASE
    if is_regex:
        try:
            return re.compile(trimmed, flags)
        except re.error as exc:
            raise InvalidSearchPattern(f"Invalid regular expression: {exc}") from exc
    normalized = unicodedata.normalize("NFC", trimmed)
    parts = normalized.split()
    body = r"\s+".join(re.escape(part) for part in parts)
    prefix = r"(?<!\w)" if _is_word_char(normalized[0]) else ""
    suffix = r"(?!\w)" if _is_word_char(normalized[-1]) else ""
    return re.compile(prefix + body + suffix, flags)


def _make_occurrence(
    paragraph_idx: int,
    paragraph: Any,
    view: CountingText,
    start: int,
    end: int,
    *,
    quotation: QuotationAnalysis | None = None,
) -> dict[str, Any] | None:
    mapped = view.source_span(start, end)
    if mapped is None:
        return None
    src_start, src_end = mapped
    if src_end <= src_start:
        return None
    display = str(paragraph.text)
    occurrence: dict[str, Any] = {
        "paragraph_id": f"p-{paragraph_idx}",
        "chapter": int(paragraph.chapter_num),
        "start_line": int(paragraph.start_line),
        "end_line": int(paragraph.end_line),
        "start": int(src_start),
        "end": int(src_end),
        "offset_unit": "unicode_codepoint",
        "quote": display[src_start:src_end],
        "excerpt": _occurrence_excerpt(display, src_start, src_end),
    }
    if quotation is not None:
        q_ctx = quotation_context(start, end, quotation.quote_ranges, quotation.unclear)
        if q_ctx is not None:
            occurrence["quotation_context"] = q_ctx
    return occurrence


def search_manuscript(
    text: str,
    query: str,
    config: CorpusConfig | None = None,
    *,
    paragraphs: Sequence[Any] | None = None,
    is_regex: bool = False,
    case_sensitive: bool = False,
    limit: int | None = 500,
) -> dict[str, Any]:
    """Search manuscript paragraphs for a phrase or regex with exact offsets and quotation context."""
    if limit is not None and limit < 1:
        raise ValueError("Search limit must be at least 1")
    compiled = compile_search_pattern(
        query, is_regex=is_regex, case_sensitive=case_sensitive
    )
    cfg = config or CorpusConfig()
    resolved = resolve_language(cfg, sample_text=text)
    blocks = parse_markdown_blocks(text, cfg, _quote_lines=True)
    projection = project_quotations(blocks, cfg, resolved)

    if paragraphs is None:
        from .style_profile import ParagraphProfiler

        paragraphs = ParagraphProfiler(cfg, sample_text=text).text_blocks(
            blocks
        )

    occurrences: list[dict[str, Any]] = []
    total_matches = 0
    for idx, paragraph in enumerate(paragraphs):
        display = str(paragraph.text)
        view = counting_view(display)
        clean = view.text
        matches = [match.span() for match in compiled.finditer(clean) if match.end() > match.start()]
        if not matches:
            continue
        bounds = projection.blocks.get(paragraph.start_line)
        quotation = (projection.slice_analysis(*bounds)
                     if bounds is not None and projection.text[slice(*bounds)] == clean else None)
        for s, e in matches:
            if limit is not None and len(occurrences) >= limit:
                mapped = view.source_span(s, e)
                if mapped is not None and mapped[1] > mapped[0]:
                    total_matches += 1
                continue
            occ = _make_occurrence(idx, paragraph, view, s, e, quotation=quotation)
            if occ is not None:
                total_matches += 1
                occurrences.append(occ)

    return {
        "schema_version": "lixity-motif-search/1",
        "query": query.strip(),
        "regex": bool(is_regex),
        "case_sensitive": bool(case_sensitive),
        "language": resolved.key,
        "offset_unit": "unicode_codepoint",
        "total_matches": total_matches,
        "truncated": limit is not None and total_matches > len(occurrences),
        "occurrences": occurrences,
    }
