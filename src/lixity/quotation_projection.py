"""Project one quotation analysis onto the shared, folded Markdown prose."""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from itertools import accumulate
from types import MappingProxyType
from typing import Any

from .language import ResolvedLanguage, compile_pattern, resolve_language
from .markdown_parser import counting_inline_text, parse_markdown_blocks
from .models import CorpusConfig
from .quotation import QuotationAnalysis, QuotationSpan, scan_quotations

# Each of these is one NFC-stable space. It passes through the same inline
# Markdown rules as the ASCII space inserted by paragraph folding.
_SOFT_SPACES = "\u00a0\u202f\u2002\u2003\u2009\u200a\u205f\u3000\u1680"
_MAX_CACHED_SCOPE_CHARS = 64_000
_cached_scan = lru_cache(maxsize=96)(scan_quotations)


def _physical_projection(raw: str, clean: str, soft_breaks: Sequence[int]) -> str:
    """Restore line starts that survive the counting projection at equal offsets."""
    if not soft_breaks:
        return clean
    sentinel = next((space for space in _SOFT_SPACES if space not in raw), None)
    if sentinel is None:
        return clean
    marked = list(raw)
    for offset in soft_breaks:
        marked[offset] = sentinel
    projected = counting_inline_text("".join(marked))
    if projected.replace(sentinel, " ") != clean:
        return clean
    return projected.replace(sentinel, "\n")


@dataclass(frozen=True)
class QuotedProse:
    text: str
    parts: tuple[str, ...]
    analysis: QuotationAnalysis
    regions: tuple[tuple[int, int], ...]
    blocks: Mapping[int, tuple[int, int]]
    _span_ends: tuple[int, ...] = field(init=False, repr=False)
    _unclear_ends: tuple[int, ...] = field(init=False, repr=False)

    def __post_init__(self) -> None:
        # Prefix maxima also find outer spans when a nested span ends first.
        object.__setattr__(self, "_span_ends", tuple(accumulate((s.end for s in self.analysis.spans), max)))
        object.__setattr__(self, "_unclear_ends", tuple(accumulate((end for _, end in self.analysis.unclear), max)))

    def slice_analysis(self, start: int, end: int) -> QuotationAnalysis:
        """Clip resolved and uncertain spans to one range without rescanning it."""
        spans = self.analysis.spans
        left = bisect_right(self._span_ends, start)
        right = bisect_left(spans, end, key=lambda span: span.start)
        unclear = self.analysis.unclear
        unclear_left = bisect_right(self._unclear_ends, start)
        unclear_right = bisect_left(unclear, end, key=lambda span: span[0])
        empty = self.analysis.empty_matches
        return QuotationAnalysis(
            spans=tuple(replace(span, start=max(start, span.start) - start, end=min(end, span.end) - start)
                        for span in spans[left:right] if span.end > start),
            unclear=tuple((max(start, a) - start, min(end, b) - start)
                          for a, b in unclear[unclear_left:unclear_right] if b > start),
            empty_matches=tuple(pos - start for pos in empty[bisect_left(empty, start):bisect_left(empty, end)]),
        )

    def paragraph_analysis(self, line: int) -> QuotationAnalysis:
        """Return quotation context relative to a profiled body or list block."""
        bounds = self.blocks.get(line)
        return self.slice_analysis(*bounds) if bounds is not None else QuotationAnalysis()


def project_quotations(
    blocks: Sequence[Mapping[str, Any]], config: CorpusConfig, language: ResolvedLanguage,
) -> QuotedProse:
    """Recognize quotes in chapter/scene-bounded prose, keeping paragraph offsets."""
    pattern = compile_pattern(config.dialogue_regex) if config.dialogue_regex is not None else None
    parts: list[str] = []
    scan_parts: list[str] = []
    spans: list[QuotationSpan] = []
    unclear: list[tuple[int, int]] = []
    empty: list[int] = []
    regions: list[tuple[int, int]] = []
    by_line: dict[int, tuple[int, int]] = {}
    end = start = 0

    def flush() -> None:
        if scan_parts:
            scope = "\n\n".join(scan_parts)
            scan = _cached_scan if len(scope) <= _MAX_CACHED_SCOPE_CHARS else scan_quotations
            result = scan(scope, language.key, pattern=pattern)
            spans.extend(replace(span, start=span.start + start, end=span.end + start) for span in result.spans)
            unclear.extend((a + start, b + start) for a, b in result.unclear)
            empty.extend(pos + start for pos in result.empty_matches)
            regions.append((start, end))
            scan_parts.clear()

    for block in blocks:
        kind = block["type"]
        body = kind in ("p", "list_item")
        if not body:
            flush()
        values = [block["text"]] if body else block["paras"] if kind == "quote_block" else ()
        breaks = block.get("quote_breaks", [()] * len(values))
        for raw, soft_breaks in zip(values, breaks, strict=True):
            clean = counting_inline_text(raw)
            if not clean:
                continue
            left = end + (2 if parts else 0)
            if not scan_parts:
                start = left
            end = left + len(clean)
            parts.append(clean)
            scan_parts.append(_physical_projection(raw, clean, soft_breaks) if pattern is None else clean)
            if body:
                by_line[block["start_line"]] = (left, end)
        if not body:
            flush()
    flush()
    return QuotedProse(
        "\n\n".join(parts), tuple(parts), QuotationAnalysis(tuple(spans), tuple(unclear), tuple(empty)),
        tuple(regions), MappingProxyType(by_line),
    )


def quoted_prose(
    text: str, config: CorpusConfig, *, language: ResolvedLanguage | None = None,
    chapter_body: bool = False,
) -> QuotedProse:
    """Recognize quotes for a full manuscript or a previously selected body."""
    blocks = parse_markdown_blocks(text, None if chapter_body else config,
                                   _front_matter=not chapter_body, _quote_lines=True)
    return project_quotations(blocks, config, language or resolve_language(config, sample_text=text))
