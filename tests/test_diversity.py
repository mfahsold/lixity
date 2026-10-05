"""Numerical fixtures for lexical-diversity estimators."""

from __future__ import annotations

import math
import unittest
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import combinations

from lixity.diversity import hd_d, hd_d_stats, maas_a2, mattr, mtld, yules_k


def _directional_mtld_reference(tokens: list[str], threshold: Fraction) -> Fraction | None:
    """Find complete prefixes directly, without the incremental type inventory."""
    n = len(tokens)
    start = 0
    factors = Fraction(0)
    while start < n:
        end = next(
            (stop for stop in range(start + 1, n + 1)
             if Fraction(len(set(tokens[start:stop])), stop - start) <= threshold),
            None,
        )
        if end is None:
            remainder_ttr = Fraction(len(set(tokens[start:])), n - start)
            factors += (1 - remainder_ttr) / (1 - threshold)
            break
        factors += 1
        start = end
    return Fraction(n) / factors if factors else None


class HypergeometricHDDTests(unittest.TestCase):
    def test_exact_frequency_fixtures(self) -> None:
        self.assertAlmostEqual(hd_d(["same"] * 100), 1 / 42, places=14)
        self.assertAlmostEqual(hd_d([f"w{i}" for i in range(100)]), 1.0, places=14)

        tokens = ["a"] * 100 + ["b"] * 100
        absence = math.comb(100, 42) / math.comb(200, 42)
        expected = 2 * (1 - absence) / 42
        value, se = hd_d_stats(tokens)
        self.assertIsNotNone(value)
        self.assertAlmostEqual(value, expected, places=14)
        self.assertEqual(se, 0.0)

    def test_mixed_frequencies_match_exact_combinatorial_expectation(self) -> None:
        fixtures = (
            (100,), (1,) * 100, (60, 25, 10, 4, 1), (59, 25, 10, 4, 2),
            (95, 2, 2, 1), (70, 70, 42, 7, 7, 2),
        )
        for frequencies in fixtures:
            n = sum(frequencies)
            denominator = math.comb(n, 42)
            expected = float(sum(
                (Fraction(denominator - math.comb(n - count, 42), denominator)
                 for count in frequencies),
                start=Fraction(0),
            ) / 42)
            tokens = [f"type{i}" for i, count in enumerate(frequencies) for _ in range(count)]
            for sequence in (tokens, tokens[::-1]):
                with self.subTest(frequencies=frequencies, reversed=sequence is not tokens):
                    value, se = hd_d_stats(sequence)
                    self.assertAlmostEqual(value, expected, places=14)
                    self.assertEqual(se, 0.0)

    def test_token_order_and_legacy_sampling_arguments_do_not_change_result(self) -> None:
        grouped = ["a"] * 100 + ["b"] * 100
        alternating = [token for _ in range(100) for token in ("a", "b")]
        self.assertEqual(hd_d(grouped), hd_d(alternating))
        # The legacy sampling arguments are still accepted and still ignored,
        # but they now announce that they do nothing.
        with self.assertWarns(DeprecationWarning) as caught:
            self.assertEqual(hd_d(grouped), hd_d(grouped, seed=123, min_samples=99))
        self.assertIn("seed/min_samples", str(caught.warning))
        self.assertIn("performs no sampling", str(caught.warning))
        self.assertIn("without sampling arguments", str(caught.warning))

    def test_each_legacy_sampling_argument_warns_for_both_entrypoints(self) -> None:
        tokens = ["a"] * 100
        arguments = (
            {"seed": 0}, {"seed": None}, {"min_samples": 0}, {"min_samples": None},
            {"seed": 123, "min_samples": 99},
        )
        for function, expected in ((hd_d, 1 / 42), (hd_d_stats, (1 / 42, 0.0))):
            for kwargs in arguments:
                with (
                    self.subTest(function=function.__name__, arguments=kwargs),
                    self.assertWarnsRegex(DeprecationWarning, "accepted but ignored"),
                ):
                    self.assertEqual(function(tokens, **kwargs), expected)

    def test_hd_d_is_silent_without_legacy_arguments(self) -> None:
        """The whole suite runs under -W error, so the normal call must not warn."""
        tokens = [f"w{i}" for i in range(200)]
        self.assertIsNotNone(hd_d(tokens))
        self.assertIsNotNone(hd_d_stats(tokens)[0])

    def test_short_text_guard_is_shared_lexical_diversity_floor(self) -> None:
        self.assertEqual(hd_d_stats(["a"] * 99), (None, 0.0))
        self.assertAlmostEqual(hd_d(["a"] * 100), 1 / 42, places=14)

    def test_rare_type_probability_is_stable_in_long_input(self) -> None:
        tokens = ["common"] * 100_000 + ["rare"]
        expected = (1 + 42 / len(tokens)) / 42
        self.assertAlmostEqual(hd_d(tokens), expected, places=14)


class MaasTests(unittest.TestCase):
    def test_single_type_has_a_defined_value_above_the_existing_token_floor(self) -> None:
        self.assertEqual(maas_a2(100, 1), 0.5)
        self.assertEqual(maas_a2(100, 100), 0.0)
        self.assertIsNone(maas_a2(99, 1))
        self.assertIsNone(maas_a2(0, 0))
        self.assertIsNone(maas_a2(100, 0))

    def test_base_ten_scale_matches_high_precision_natural_log_conversion(self) -> None:
        for n, v in ((100, 1), (100, 2), (101, 80), (127, 100), (1000, 32)):
            with self.subTest(tokens=n, types=v), localcontext() as context:
                context.prec = 50
                ln_n = Decimal(n).ln()
                expected = float((ln_n - Decimal(v).ln()) * Decimal(10).ln() / ln_n**2)
                self.assertAlmostEqual(maas_a2(n, v), expected, places=14)


class MATTRTests(unittest.TestCase):
    def test_incremental_windows_match_direct_overlapping_type_sets(self) -> None:
        fixtures = (
            [], ["a"] * 49, ["a"] * 50, ["a"] * 51,
            [f"unique{i}" for i in range(100)],
            ["a"] * 50 + ["b"] * 50, ["a", "b"] * 50, ["a", "b", "c", "a"] * 26,
        )
        for i, tokens in enumerate(fixtures):
            for window in (1, 2, 42, 50, 100):
                with self.subTest(fixture=i, window=window):
                    windows = len(tokens) - window + 1
                    if windows <= 0:
                        self.assertIsNone(mattr(tokens, window=window))
                    else:
                        distinct_sum = sum(
                            len(set(tokens[start:start + window])) for start in range(windows)
                        )
                        expected = float(Fraction(distinct_sum, window * windows))
                        self.assertAlmostEqual(mattr(tokens, window=window), expected, places=14)


class YuleTests(unittest.TestCase):
    def test_frequency_formula_matches_count_of_equal_unordered_pairs(self) -> None:
        fixtures = (
            [], ["a"], ["a"] * 100, [f"unique{i}" for i in range(100)],
            ["a"] * 60 + ["b"] * 25 + ["c"] * 15, ["a", "b", "c", "a"] * 25,
        )
        for i, tokens in enumerate(fixtures):
            with self.subTest(fixture=i):
                equal_pairs = sum(left == right for left, right in combinations(tokens, 2))
                expected = 20000 * equal_pairs / len(tokens)**2 if tokens else 0.0
                self.assertAlmostEqual(yules_k(tokens), expected, places=12)


class MTLDTests(unittest.TestCase):
    def test_asymmetric_directions_are_averaged_as_lengths(self) -> None:
        tokens = ["a"] * 50 + [f"unique{i}" for i in range(50)]
        # Forward: 25 two-token factors, then a zero-weight unique remainder.
        # Reverse: one 71-token factor, then 14 two-token factors and one token.
        expected = (100 / 25 + 100 / 15) / 2
        self.assertAlmostEqual(mtld(tokens), expected, places=12)
        self.assertAlmostEqual(mtld(tokens[::-1]), expected, places=12)

    def test_directional_scores_match_exact_prefix_and_partial_factor_reference(self) -> None:
        exact_boundary = [f"type{i}" for i in range(18)] + ["type0"] * 7
        fixtures = (
            ["a"] * 100, ["a", "b", "c"] * 34,
            ["a", "b", "c"] * 40 + ["a", "b", "c", "a"],
            ["a"] * 51 + [f"unique{i}" for i in range(50)],
            [f"unique{i}" for i in range(99)] + ["unique0"],
            [f"type{i % 17}" for i in range(127)], exact_boundary * 4,
        )
        for i, tokens in enumerate(fixtures):
            for threshold in (Fraction(18, 25), Fraction(1, 2)):
                forward = _directional_mtld_reference(tokens, threshold)
                reverse = _directional_mtld_reference(tokens[::-1], threshold)
                if forward is None or reverse is None:
                    self.fail("These repeated-token fixtures must have positive factors")
                expected = float((forward + reverse) / 2)
                for sequence in (tokens, tokens[::-1]):
                    with self.subTest(fixture=i, threshold=threshold, reversed=sequence is not tokens):
                        self.assertAlmostEqual(mtld(sequence, float(threshold)), expected, places=10)

    def test_short_text_and_zero_factor_availability_policies_are_preserved(self) -> None:
        for n in (0, 1, 42, 99):
            with self.subTest(tokens=n):
                self.assertIsNone(mtld(["a"] * n))
        self.assertEqual(mtld(["a"] * 100), 2.0)
        for n in (100, 200):
            with self.subTest(unique_tokens=n):
                self.assertIsNone(mtld([f"unique{i}" for i in range(n)]))


if __name__ == "__main__":
    unittest.main()
