"""Shared function-word heuristic for measured sentence tokens."""

from __future__ import annotations

from collections.abc import Sequence
from typing import NamedTuple


class FunctionWordMeasurement(NamedTuple):
    words: int
    function_words: int
    pct: float
    sticky: bool


def measure_function_words(
    tokens: Sequence[str],
    vocabulary: frozenset[str],
    *,
    min_words: int,
    min_pct: float,
) -> FunctionWordMeasurement:
    """Measure case-normalized tokens in the caller's existing sentence scope."""
    words = len(tokens)
    function_words = sum(token in vocabulary for token in tokens)
    pct = 100 * function_words / words if words else 0.0
    return FunctionWordMeasurement(words, function_words, pct, words >= min_words and pct >= min_pct)
