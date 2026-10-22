"""Exact chapter-versus-rest ordinal effects without quadratic comparisons."""

import itertools
import math

from lixity import style_fingerprint


def test_chapter_cliff_deltas_match_pairwise_oracle_with_ties_and_extremes():
    from lixity.style_fingerprint import _chapter_cliff_deltas

    choices = (-1e308, -1.0, -0.0, 0.0, 1.0, 1e308)
    for n in range(1, 5):
        for sample in itertools.product(choices, repeat=n):
            column = {i * 3 + 2: value for i, value in enumerate(sample)}
            column[-1] = None
            expected = {}
            for chapter, value in column.items():
                if value is None:
                    continue
                others = [other for ch, other in column.items() if ch != chapter and other is not None]
                expected[chapter] = style_fingerprint.cliff_delta([value], others)
            actual = _chapter_cliff_deltas(column)
            assert actual == expected
            assert {ch: value.hex() for ch, value in actual.items()} == {
                ch: value.hex() for ch, value in expected.items()
            }
    assert _chapter_cliff_deltas({}) == {}
    assert _chapter_cliff_deltas({1: None}) == {}


def test_chapter_cliff_deltas_use_subquadratic_value_comparisons():
    from lixity.style_fingerprint import _chapter_cliff_deltas

    class ComparedFloat(float):
        comparisons = 0
        __hash__ = float.__hash__

        def __lt__(self, other):
            type(self).comparisons += 1
            return super().__lt__(other)

        def __gt__(self, other):
            type(self).comparisons += 1
            return super().__gt__(other)

        def __eq__(self, other):
            type(self).comparisons += 1
            return super().__eq__(other)

    n = 512
    column = {i: ComparedFloat((i * 47) % 113) for i in range(n)}
    actual = _chapter_cliff_deltas(column)
    assert len(actual) == n
    assert ComparedFloat.comparisons < 8 * n * math.ceil(math.log2(n))
