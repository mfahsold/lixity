"""Quotation boundaries and counted-word membership in canonical prose.

Callers supply normalized prose with physical line breaks and bound each
scan to one chapter or other independently measured unit. All ranges are
half-open code-point offsets in that supplied text.
"""

from __future__ import annotations

import re
from bisect import bisect_right
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from functools import cache, cached_property
from typing import Literal, TypeAlias
from unicodedata import category

from .language import quotation_capture_group

Range: TypeAlias = tuple[int, int]
QuotationKind: TypeAlias = Literal["quotation", "marked_speech", "custom"]
QuotationContext: TypeAlias = Literal["in_quotation", "outside_quotation", "overlaps_quotation"]


@dataclass(frozen=True, order=True)
class QuotationSpan:
    """Recognized content between delimiters, including multi-line passages."""

    start: int
    end: int
    kind: QuotationKind
    marker: str = ""


@dataclass(frozen=True)
class QuotationAnalysis:
    spans: tuple[QuotationSpan, ...] = ()
    unclear: tuple[Range, ...] = ()
    # Preserve the identity of configured matches with an empty first capture.
    empty_matches: tuple[int, ...] = ()

    @cached_property
    def quote_ranges(self) -> tuple[Range, ...]:
        return merge_quotation_spans(self.spans)


def quotation_context(
    start: int, end: int, ranges: Sequence[Range], unclear: Sequence[Range],
) -> QuotationContext | None:
    """Classify an exact span against known ranges and unresolved boundaries."""
    if any(left <= start and end <= right for left, right in ranges):
        return "in_quotation"
    if any(start < right and end > left for left, right in unclear):
        return None
    if any(start < right and end > left for left, right in ranges):
        return "overlaps_quotation"
    return "outside_quotation"


_DOUBLE_QUOTES = {'"': '"', "\u201c": "\u201d"}
_SINGLE_QUOTES = {"'": "'", "\u2018": "\u2019"}
_GENERIC_PAIRS = {**_DOUBLE_QUOTES, "«": "»", "\u201e": "\u201c", "»": "«"}
_ROMANCE_PAIRS = {**_DOUBLE_QUOTES, "«": "»", "\u2018": "\u2019", "\u2039": "\u203a"}
_PAIRS = {
    "de": {**_GENERIC_PAIRS, "\u201a": "\u2018", "\u203a": "\u2039", "\u2039": "\u203a",
           "\u2018": "\u2019"},
    "en": {**_DOUBLE_QUOTES, **_SINGLE_QUOTES},
    "fr": _ROMANCE_PAIRS,
    "es": {**_ROMANCE_PAIRS, "'": "'"},
    "it": _ROMANCE_PAIRS,
    "pt": _ROMANCE_PAIRS,
    "nl": {**_DOUBLE_QUOTES, **_SINGLE_QUOTES, "\u201e": "\u201d"},
}
_REPEATED_OPENERS = frozenset({"en", "fr", "nl"})
_DASH_LANGUAGES = frozenset({"es", "fr", "it", "pt"})
_DASHES = frozenset({"—", "–", "\u2015"})
_DASH_BOUNDARY = re.compile(r"[—–\u2015]")
_APOSTROPHES = frozenset({"'", "\u2019"})
_DUTCH_ELISIONS = frozenset({"s", "t", "k", "n", "m", "ns"})
_ENGLISH_ELISIONS = frozenset({"tis", "twas", "twere", "em", "cause", "bout", "round"})
_LINE_BREAKS = frozenset("\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029")


@cache
def _markers(language: str) -> re.Pattern[str]:
    pairs = _PAIRS.get(language, _GENERIC_PAIRS)
    return re.compile("[" + re.escape("".join(dict.fromkeys((*pairs, *pairs.values())))) + "]")


def merge_quotation_spans(spans: Iterable[QuotationSpan | Range]) -> tuple[Range, ...]:
    """Return the sorted union used for contextual membership and shares."""
    ranges = sorted((span.start, span.end) if isinstance(span, QuotationSpan) else span
                    for span in spans)
    result: list[Range] = []
    for start, end in ranges:
        if end <= start:
            continue
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(end, result[-1][1]))
        else:
            result.append((start, end))
    return tuple(result)


def _memberships(
    text: str, word_pattern: re.Pattern[str], ranges: tuple[Range, ...], group: int,
) -> Iterator[tuple[int | None, re.Match[str]]]:
    starts = tuple(start for start, _ in ranges)
    for match in word_pattern.finditer(text):
        start, end = match.span(group)
        if end <= start:
            yield None, match
            continue
        index = bisect_right(starts, start) - 1
        quote = index if index >= 0 and end <= ranges[index][1] else None
        yield quote, match


def count_quoted_words(
    text: str, word_pattern: re.Pattern[str], spans: Iterable[QuotationSpan | Range],
) -> int:
    """Count word matches from the full scope that lie wholly in a quote."""
    ranges = merge_quotation_spans(spans)
    group = 1 if word_pattern.groups else 0
    return sum(index is not None for index, _ in _memberships(text, word_pattern, ranges, group)) if ranges else 0


def quoted_word_counts(
    text: str, word_pattern: re.Pattern[str], spans: Iterable[QuotationSpan | Range],
) -> tuple[int, ...]:
    """Count membership per sorted, unioned range in a single word scan."""
    ranges = merge_quotation_spans(spans)
    counts = [0] * len(ranges)
    if ranges:
        group = 1 if word_pattern.groups else 0
        for index, _ in _memberships(text, word_pattern, ranges, group):
            if index is not None:
                counts[index] += 1
    return tuple(counts)


def partition_quoted_words(
    text: str, word_pattern: re.Pattern[str], spans: Iterable[QuotationSpan | Range],
) -> tuple[list[list[str]], list[str]]:
    """Return full-scope word matches per unioned range plus the other words."""
    ranges = merge_quotation_spans(spans)
    quoted: list[list[str]] = [[] for _ in ranges]
    outside: list[str] = []
    group = 1 if word_pattern.groups else 0
    for index, match in _memberships(text, word_pattern, ranges, group):
        (outside if index is None else quoted[index]).append(match[group] or "")
    return quoted, outside


def _word_part(character: str) -> bool:
    return bool(character and (character.isalnum() or character == "_" or category(character)[0] == "M"))


def _is_apostrophe(text: str, index: int, language: str) -> bool:
    if text[index] not in _APOSTROPHES:
        return False
    before = text[index - 1] if index else ""
    after = text[index + 1] if index + 1 < len(text) else ""
    if _word_part(before) and _word_part(after):
        return True
    # Leading elisions and abbreviated years can occupy the opener position.
    if _word_part(before) or not _word_part(after):
        return False
    match = re.match(r"\w+", text[index + 1:index + 10])
    if match is None:
        return False
    word = match[0].lower()
    end = index + 1 + len(word)
    if end < len(text) and (text[end] in _APOSTROPHES or _word_part(text[end])):
        return False
    if language == "nl":
        return word in _DUTCH_ELISIONS
    return language == "en" and (word in _ENGLISH_ELISIONS or re.fullmatch(r"[0-9]{2}s?", word) is not None)


@dataclass(frozen=True)
class _Line:
    start: int
    end: int
    paragraph_start: bool


def _physical_lines(text: str) -> Iterator[_Line]:
    offset = 0
    paragraph_start = True
    for line in text.splitlines(keepends=True):
        trimmed = line.strip()
        if trimmed:
            start = offset + len(line) - len(line.lstrip())
            yield _Line(start, start + len(trimmed), paragraph_start)
        paragraph_start = not trimmed
        offset += len(line)


@dataclass(frozen=True)
class _Opening:
    position: int
    character: str
    closer: str


def _has_opening_content(text: str, start: int) -> bool:
    for index in range(start, len(text)):
        character = text[index]
        if character in _LINE_BREAKS:
            return False
        if not character.isspace():
            return True
    return False


def _escaped(text: str, index: int) -> bool:
    start = index
    while start and text[start - 1] == "\\":
        start -= 1
    return bool((index - start) % 2)


def _paired_quotes(
    text: str, language: str, lines: dict[int, _Line],
) -> tuple[list[QuotationSpan], list[Range]]:
    pairs = _PAIRS.get(language, _GENERIC_PAIRS)
    spans: list[QuotationSpan] = []
    unclear: list[Range] = []
    stack: list[_Opening] = []
    for mark in _markers(language).finditer(text):
        index = mark.start()
        character = mark[0]
        if _escaped(text, index) or _is_apostrophe(text, index, language):
            continue
        previous = text[index - 1] if index else ""
        following = text[index + 1] if index + 1 < len(text) else ""
        closer = pairs.get(character)
        can_open = closer is not None and not _word_part(previous) and _has_opening_content(text, index + 1)
        line = lines.get(index)
        if stack:
            opening = stack[-1]
            continued = (
                line is not None and line.paragraph_start and index + 1 < line.end
                and (
                    (language in _REPEATED_OPENERS and character == opening.character)
                    or (language in {"es", "fr"} and character == "»" and opening.character == "«")
                )
            )
            if continued:
                continue
            if character == opening.closer:
                if closer == character and can_open and previous.isspace() and _word_part(following):
                    # Symmetric marks at another apparent opener leave the
                    # first attempt unresolved. The new pair can still close.
                    unclear.append((stack[0].position, index))
                    stack.clear()
                else:
                    stack.pop()
                    if index > opening.position + 1:
                        spans.append(QuotationSpan(
                            opening.position + 1, index, "quotation", f"{opening.character}…{character}",
                        ))
                    continue
            elif closer is None or not can_open:
                unclear.append((stack[0].position, index + 1))
                stack.clear()
                continue
        if can_open and closer is not None:
            stack.append(_Opening(index, character, closer))
        elif character not in _APOSTROPHES and character != '"' and closer != character:
            # A closing quotation mark without an established opening range.
            unclear.append((index, index + 1))
    if stack:
        unclear.append((stack[0].position, len(text)))
    return spans, unclear


def _inside(index: int, ranges: tuple[Range, ...], starts: tuple[int, ...]) -> bool:
    position = bisect_right(starts, index) - 1
    return position >= 0 and index < ranges[position][1]


def _inline_dashes(text: str, start: int, end: int, ranges: tuple[Range, ...],
                   starts: tuple[int, ...]) -> list[re.Match[str]]:
    separators: list[re.Match[str]] = []
    for marker in _DASH_BOUNDARY.finditer(text, start, end):
        index = marker.start()
        before = text[index - 1]
        after = text[index + 1] if index + 1 < end else ""
        if _inside(index, ranges, starts) or before in _DASHES or after in _DASHES:
            continue
        if before.isspace() or not after or after.isspace() or category(after)[0] == "P":
            left, right = index - 1, index + 1
            while left >= start and text[left].isspace():
                left -= 1
            while right < end and text[right].isspace():
                right += 1
            if left >= start and right < end and text[left].isdigit() and text[right].isdigit():
                continue
            separators.append(marker)
    return separators


def _reply_pieces(
    text: str, start: int, line: _Line, marker: str, language: str,
    ranges: tuple[Range, ...], starts: tuple[int, ...], unclear: list[Range],
) -> Iterator[QuotationSpan]:
    separators = _inline_dashes(text, start, line.end, ranges, starts)
    for index in range(0, len(separators) + 1, 2):
        opening = separators[index] if index < len(separators) else None
        end = opening.start() if opening is not None else line.end
        spoken = text[start:end].rstrip()
        if spoken:
            yield QuotationSpan(start, start + len(spoken), "marked_speech", marker)
        if opening is None or opening.end() == line.end:
            return
        attached = language == "es" and opening[0] in {"—", "\u2015"} and not text[opening.end()].isspace()
        if index + 1 == len(separators):
            if not attached:
                unclear.append((opening.start(), line.end))
            return

        closing = separators[index + 1]
        interruption = text[opening.end():closing.start()].strip()
        # Spaced marks can signal a new reply or a pause. Prefer the shared
        # editorial shape of a suspended reply plus a completed incise.
        spaced_incise = (
            bool(spoken and interruption) and (spoken[-1] not in ".!?…" or interruption[0].islower())
            and interruption[-1] in ".!?…" and text[opening.end()].isspace()
        )
        if opening[0] != closing[0] or not (attached or spaced_incise):
            unclear.append((opening.start(), line.end))
            return
        start = closing.end()
        if attached and start < line.end and text[start] in ".,:;":
            start += 1
        while start < line.end and text[start].isspace():
            start += 1
        marker = closing[0]


def _marked_speech(
    text: str, language: str, lines: Iterable[_Line], ranges: tuple[Range, ...],
    unclear: list[Range],
) -> list[QuotationSpan]:
    spans: list[QuotationSpan] = []
    starts = tuple(start for start, _ in ranges)
    previous_reply = False
    continued_markers: set[Range] = set()
    for line in lines:
        marker = text[line.start]
        opening = marker in _DASHES
        continuation = language == "es" and marker == "»" and previous_reply
        previous_reply = False
        start = line.start + 1
        if start >= line.end or _inside(line.start, ranges, starts):
            continue
        if not opening and not continuation:
            continue
        after = text[start]
        attached = language == "es" and marker in {"—", "\u2015"}
        if opening and not (after.isspace() or attached):
            continue
        while start < line.end and text[start].isspace():
            start += 1
        if start == line.end or text[start] in _DASHES:
            continue
        previous_reply = True
        if continuation:
            continued_markers.add((line.start, line.start + 1))
        spans.extend(_reply_pieces(text, start, line, marker, language, ranges, starts, unclear))
    if continued_markers:
        unclear[:] = [region for region in unclear if region not in continued_markers]
    return spans


def scan_quotations(
    text: str, language: str, *, pattern: re.Pattern[str] | None = None,
) -> QuotationAnalysis:
    """Recognize quotations from the selected profile or explicit project rule."""
    if pattern is not None:
        spans: list[QuotationSpan] = []
        empty: list[int] = []
        group = quotation_capture_group(pattern)
        for match in pattern.finditer(text):
            start, end = match.span(group)
            if end > start:
                spans.append(QuotationSpan(start, end, "custom"))
            else:
                empty.append(match.start())
        return QuotationAnalysis(tuple(sorted(spans)), empty_matches=tuple(empty))

    language = language if language in _PAIRS else "generic"
    if not _markers(language).search(text) and not (
        language in _DASH_LANGUAGES and _DASH_BOUNDARY.search(text)
    ):
        return QuotationAnalysis()
    lines = {line.start: line for line in _physical_lines(text)}
    spans, unclear = _paired_quotes(text, language, lines)
    if language in _DASH_LANGUAGES:
        spans.extend(_marked_speech(text, language, lines.values(), merge_quotation_spans(spans), unclear))
    return QuotationAnalysis(tuple(sorted(spans)), merge_quotation_spans(unclear))
