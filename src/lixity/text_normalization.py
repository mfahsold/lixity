"""NFC counting text with conservative ranges into the unchanged source.

Offsets are Python code-point offsets, not byte or grapheme offsets. Changed
canonical clusters map only at their outer boundaries; ambiguous cuts return
``None``. Already normalized text needs no offset table.
"""

from __future__ import annotations

import unicodedata
from bisect import bisect_right
from dataclasses import dataclass


@dataclass(frozen=True)
class CountingText:
    text: str
    _source_length: int
    # Normalized start/end, original start/end, unchanged cluster/run.
    _segments: tuple[tuple[int, int, int, int, bool], ...] = ()

    def source_span(self, start: int, end: int) -> tuple[int, int] | None:
        """Return an exact original range, or None for invalid/ambiguous cuts."""
        if type(start) is not int or type(end) is not int or not 0 <= start <= end <= len(self.text):
            return None
        if not self._segments:
            return start, end

        def boundary(offset: int) -> int | None:
            if offset == len(self.text):
                return self._source_length
            index = bisect_right(self._segments, offset, key=lambda segment: segment[0]) - 1
            normalized_start, _normalized_end, original_start, _original_end, unchanged = self._segments[index]
            if offset == normalized_start:
                return original_start
            return original_start + offset - normalized_start if unchanged else None

        original_start, original_end = boundary(start), boundary(end)
        if original_start is None or original_end is None:
            return None
        return original_start, original_end


def counting_view(original: str) -> CountingText:
    """Normalize for counting while preserving conservative source offsets.

    Canonical combining sequences stay together. Starter-to-starter NFC
    composition (including Hangul Jamo) also joins clusters. A final whole-text
    verification fails closed to whole-text boundaries if this partition ever
    misses an interaction; this is not a Unicode grapheme segmenter.
    """
    normalized = unicodedata.normalize("NFC", original)
    if normalized == original:
        return CountingText(original, len(original))

    segments: list[tuple[int, int, int, int, bool]] = []
    pieces: list[str] = []
    normalized_offset = 0

    def append_cluster(start: int, end: int) -> None:
        nonlocal normalized_offset
        raw = original[start:end]
        piece = unicodedata.normalize("NFC", raw)
        unchanged = piece == raw
        pieces.append(piece)
        segment = (normalized_offset, normalized_offset + len(piece), start, end, unchanged)
        if unchanged and segments and segments[-1][4]:
            previous = segments[-1]
            segments[-1] = (previous[0], segment[1], previous[2], end, True)
        else:
            segments.append(segment)
        normalized_offset += len(piece)

    cluster_start = 0
    for index, character in enumerate(original):
        if index == 0 or unicodedata.combining(character):
            continue
        previous = unicodedata.normalize("NFC", original[cluster_start:index])
        following = unicodedata.normalize("NFC", character)
        if unicodedata.normalize("NFC", previous + following) != previous + following:
            continue
        append_cluster(cluster_start, index)
        cluster_start = index
    append_cluster(cluster_start, len(original))
    if "".join(pieces) != normalized:
        segments = [(0, len(normalized), 0, len(original), False)]
    return CountingText(normalized, len(original), tuple(segments))
