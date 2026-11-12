"""Numerical fixtures for lexical-diversity estimators."""

from __future__ import annotations

import math
import unittest
from decimal import Decimal, localcontext
from fractions import Fraction
from itertools import combinations
from pathlib import Path

from lixity.analyzer import CorpusAnalyzer
from lixity.diversity import hd_d, hd_d_stats, maas_a2, mattr, mtld, stratified_mattr, yules_k
from lixity.models import CorpusConfig

ROOT = Path(__file__).resolve().parents[1]


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
    def test_mixed_frequencies_match_exact_combinatorial_expectation(self) -> None:
        fixtures = (
            (100,), (1,) * 100, (100, 100), (60, 25, 10, 4, 1), (59, 25, 10, 4, 2),
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
            for sequence in (tokens, tokens[::-1], tokens[::2] + tokens[1::2]):
                with self.subTest(frequencies=frequencies, reversed=sequence is not tokens):
                    value, se = hd_d_stats(sequence)
                    self.assertAlmostEqual(value, expected, places=14)
                    self.assertEqual(se, 0.0)

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

    def test_short_text_guard_is_shared_lexical_diversity_floor(self) -> None:
        self.assertEqual(hd_d_stats(["a"] * 99), (None, 0.0))
        self.assertAlmostEqual(hd_d(["a"] * 100), 1 / 42, places=14)

    def test_rare_type_probability_is_stable_in_long_input(self) -> None:
        tokens = ["common"] * 100_000 + ["rare"]
        expected = (1 + 42 / len(tokens)) / 42
        self.assertAlmostEqual(hd_d(tokens), expected, places=14)


class MaasTests(unittest.TestCase):
    def test_invalid_or_inconsistent_counts_raise_value_error(self) -> None:
        for n, v in ((-1, 0), (100, -1), (100, 101), (0, 1), (99, 100),
                     (100.0, 20), (100, 20.5), (True, 1), (100, False)):
            with self.subTest(tokens=n, types=v), self.assertRaises(ValueError):
                maas_a2(n, v)

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
    def test_invalid_windows_raise_value_error_even_for_empty_input(self) -> None:
        for tokens in ([], ["a"] * 100):
            for window in (0, -1, 0.5, True, False, float("nan"), float("inf"), "50", None):
                with self.subTest(tokens=len(tokens), window=window), self.assertRaises(ValueError):
                    mattr(tokens, window=window)

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
    def test_invalid_thresholds_raise_value_error_even_below_token_floor(self) -> None:
        for tokens in ([], ["a"] * 100):
            for threshold in (0, 1, -0.2, 1.1, float("nan"), float("inf"), -float("inf"), True, False, "0.72", None):
                with self.subTest(tokens=len(tokens), threshold=threshold), self.assertRaises(ValueError):
                    mtld(tokens, threshold=threshold)

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


class StratifiedMATTRTests(unittest.TestCase):
    def test_stratified_mattr_filters_and_computes_mattr(self) -> None:
        # 30 verbs, 30 nouns
        verbs = [f"verb{i}" for i in range(30)]
        nouns = [f"noun{i}" for i in range(30)]
        interleaved = [tok for pair in zip(verbs, nouns, strict=True) for tok in pair]

        # Filter verbs only with window=10
        val = stratified_mattr(interleaved, lambda t: t.startswith("verb"), window=10)
        self.assertIsNotNone(val)
        # All verbs are unique -> MATTR over unique tokens is 1.0
        self.assertEqual(val, 1.0)

        # Repetitive verbs
        rep_verbs = ["walk", "run"] * 15
        interleaved_rep = [tok for pair in zip(rep_verbs, nouns, strict=True) for tok in pair]
        val_rep = stratified_mattr(interleaved_rep, lambda t: t in ("walk", "run"), window=10)
        self.assertIsNotNone(val_rep)
        self.assertEqual(val_rep, 2 / 10)

    def test_stratified_mattr_below_window_returns_none(self) -> None:
        tokens = ["verb1", "noun1", "verb2"]
        val = stratified_mattr(tokens, lambda t: t.startswith("verb"), window=10)
        self.assertIsNone(val)

    def test_invalid_window_raises(self) -> None:
        with self.assertRaises(ValueError):
            stratified_mattr(["a"] * 10, lambda t: True, window=0)


class BookScalePlausibilityTests(unittest.TestCase):
    """Book-scale cross-validation and scientific plausibility bands on public-domain novels."""

    def test_public_domain_novels_satisfy_formula_identities_and_plausibility_bands(self) -> None:
        novels = (
            (
                "effi-briest",
                ROOT / "samples" / "effi-briest.md",
                "de",
                "Flesch Reading Ease (Amstad)",
                lambda asl, asw: 180.0 - 1.0 * asl - 58.5 * asw,
            ),
            (
                "pride-and-prejudice",
                ROOT / "samples" / "pride-and-prejudice.md",
                "en",
                "Flesch Reading Ease",
                lambda asl, asw: 206.835 - 1.015 * asl - 84.6 * asw,
            ),
        )
        for slug, path, lang, expected_variant, flesch_fn in novels:
            with self.subTest(novel=slug):
                text = path.read_text(encoding="utf-8")
                cfg = CorpusConfig(language=lang)
                analyzer = CorpusAnalyzer(cfg, sample_text=text)
                metrics = analyzer.analyze_text(text)

                self.assertGreater(metrics.tokens, 80_000)
                self.assertEqual(metrics.flesch_variant, expected_variant)
                self.assertAlmostEqual(
                    metrics.flesch_de,
                    flesch_fn(metrics.asl, metrics.asw),
                    places=10,
                )
                # 19th-century literary prose plausibility bands (Björnsson 1968; McCarthy & Jarvis 2010)
                self.assertTrue(50.0 <= metrics.flesch_de <= 80.0, f"Unexpected Flesch: {metrics.flesch_de}")
                self.assertTrue(30.0 <= metrics.lix <= 50.0, f"Unexpected LIX: {metrics.lix}")
                self.assertIsNotNone(metrics.hd_d)
                self.assertIsNotNone(metrics.mattr)
                self.assertIsNotNone(metrics.mtld)
                self.assertIsNotNone(metrics.maas_a2)
                assert metrics.hd_d is not None
                assert metrics.mattr is not None
                assert metrics.mtld is not None
                assert metrics.maas_a2 is not None
                self.assertTrue(0.80 <= metrics.hd_d <= 0.95)
                self.assertTrue(0.75 <= metrics.mattr <= 0.92)
                self.assertTrue(70.0 <= metrics.mtld <= 160.0)
                self.assertTrue(40.0 <= metrics.yules_k <= 120.0)
                self.assertTrue(0.02 <= metrics.maas_a2 <= 0.08)

                # Cross-validate exact hypergeometric HD-D and Yule's K on a 2,000-token book slice
                chapter_tokens = [w.lower() for w in analyzer._word_re.findall(text[:25_000])][:2_000]
                n = len(chapter_tokens)
                denom = math.comb(n, 42)
                from collections import Counter

                freqs = Counter(chapter_tokens)
                ref_hdd = float(
                    sum(
                        (Fraction(denom - math.comb(n - c, 42), denom) for c in freqs.values()),
                        start=Fraction(0),
                    )
                    / 42
                )
                self.assertAlmostEqual(hd_d(chapter_tokens), ref_hdd, places=13)
                spec = Counter(freqs.values())
                ref_yule = 10_000.0 * (sum(m * m * vm for m, vm in spec.items()) - n) / (n * n)
                self.assertAlmostEqual(yules_k(chapter_tokens), ref_yule, places=12)


if __name__ == "__main__":
    unittest.main()
