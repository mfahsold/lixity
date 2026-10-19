"""
tests/test_math_core.py
=======================
Known-value and property tests for the mathematical core: readability
formulas, LIX threshold, syllable rules, robust statistics (median/MAD/z*),
normal tail probabilities, Benjamini-Hochberg FDR, Spearman correlation,
and Jacobi eigendecomposition. Exact lexical-diversity references live in
test_diversity.py; fingerprint/pipeline integration lives in test_style_fingerprint.py.
"""

from __future__ import annotations

import math
import os
import sys
import unittest
from collections import Counter
from typing import ClassVar

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.analyzer import CorpusAnalyzer  # noqa: E402
from lixity.config import resolve_thresholds  # noqa: E402
from lixity.math_core import (  # noqa: E402
    MAD_TO_SIGMA,
    binomial_se_percent,
    per_mille,
    percent,
    poisson_se_per_mille,
    ratio_or_zero,
    robust_scale,
)
from lixity.models import CorpusConfig  # noqa: E402
from lixity.style_fingerprint import (  # noqa: E402
    FingerprintThresholds,
    benjamini_hochberg,
    benjamini_yekutieli,
    cliff_delta,
    dunning_g2,
    effect_label,
    fdr_rejects,
    jacobi_eigh,
    lag1_autocorrelation,
    mad,
    median,
    normal_tail_probability,
    robust_z,
    runs_above_median_z,
    significance_z,
    spearman_rho,
)
from lixity.syllables import count_de, count_en  # noqa: E402


class TestDunningContingency(unittest.TestCase):
    def test_complete_separation_counts_term_and_nonterm_cells(self):
        # Two equiprobable cells each have 50 observations instead of 25.
        self.assertAlmostEqual(dunning_g2(50, 0, 50, 50), 200 * math.log(2), places=12)

    def test_swapping_corpora_or_term_complement_reverses_direction(self):
        score = dunning_g2(12, 3, 20, 30)
        self.assertGreater(score, 0)
        self.assertAlmostEqual(dunning_g2(3, 12, 30, 20), -score, places=12)
        self.assertAlmostEqual(dunning_g2(8, 27, 20, 30), -score, places=12)

    def test_equal_rates_and_degenerate_tables_have_no_keyness(self):
        for counts in ((5, 10, 10, 20), (0, 0, 10, 20), (10, 20, 10, 20), (0, 3, 0, 10)):
            with self.subTest(counts=counts):
                self.assertEqual(dunning_g2(*counts), 0.0)

    def test_impossible_observed_counts_are_rejected(self):
        for counts in ((-1, 1, 10, 10), (11, 1, 10, 10), (1, 11, 10, 10)):
            with self.subTest(counts=counts), self.assertRaises(ValueError):
                dunning_g2(*counts)


class TestResolveThresholds(unittest.TestCase):
    """Shared threshold builder: kwargs > project config > code default."""

    def test_defaults_when_no_overrides(self):
        t = resolve_thresholds(use_project_config=False)
        self.assertEqual(t, FingerprintThresholds())

    def test_explicit_kwargs_win_over_defaults(self):
        t = resolve_thresholds(z_mild=1.5, fdr_q=0.1, use_project_config=False)
        self.assertEqual(t.z_mild, 1.5)
        self.assertEqual(t.fdr_q, 0.1)
        self.assertEqual(t.z_strong, FingerprintThresholds().z_strong)

    def test_none_kwargs_do_not_clobber_defaults(self):
        t = resolve_thresholds(z_mild=None, fdr_q=None, use_project_config=False)
        self.assertEqual(t.z_mild, FingerprintThresholds().z_mild)
        self.assertEqual(t.fdr_q, FingerprintThresholds().fdr_q)

    def test_flag_min_severity_injectable(self):
        t = resolve_thresholds(flag_min_severity=3, use_project_config=False)
        self.assertEqual(t.flag_min_severity, 3)

    def test_fdr_method_injectable(self):
        t = resolve_thresholds(fdr_method="by", use_project_config=False)
        self.assertEqual(t.fdr_method, "by")


class TestReadabilityFormulas(unittest.TestCase):
    """Documented language formulas at ASL=20, ASW=1.5 (hand-computed)."""

    CASES: ClassVar[dict[str, float]] = {
        "de": 180.0 - 20.0 - 58.5 * 1.5,
        "en": 206.835 - 1.015 * 20.0 - 84.6 * 1.5,
        "fr": 207.0 - 1.015 * 20.0 - 73.6 * 1.5,
        "es": 206.835 - 20.0 - 62.35 * 1.5,
        "it": 217.0 - 1.3 * 20.0 - 60.0 * 1.5,
        "pt": 248.835 - 1.015 * 20.0 - 84.6 * 1.5,
        "nl": 207.0 - 0.93 * 20.0 - 77.0 * 1.5,
    }

    def test_language_formulas(self):
        for key, expected in self.CASES.items():
            with self.subTest(language=key):
                analyzer = CorpusAnalyzer(CorpusConfig(language=key))
                score, _name = analyzer.readability(20.0, 1.5)
                self.assertAlmostEqual(score, expected, places=6)

    def test_generic_falls_back_to_flesch(self):
        analyzer = CorpusAnalyzer(CorpusConfig(language="generic"))
        score, name = analyzer.readability(20.0, 1.5)
        self.assertAlmostEqual(score, 206.835 - 1.015 * 20.0 - 84.6 * 1.5, places=6)
        self.assertIn("Flesch", name)


class TestLixThreshold(unittest.TestCase):
    def test_long_words_follow_the_bjornsson_threshold(self):
        """LIX counts words with more than six characters (all languages)."""
        for key in ("de", "en", "fr", "es", "it", "pt", "nl"):
            with self.subTest(language=key):
                analyzer = CorpusAnalyzer(CorpusConfig(language=key))
                self.assertEqual(analyzer.long_word_min(), 6)

    def test_lix_formula(self):
        analyzer = CorpusAnalyzer(CorpusConfig(language="de"))
        # No long word (>6 characters): LIX equals the average sentence length.
        short = analyzer.analyze_text("## K\n\nHaus. Hund. Baum. Katze.\n")
        self.assertAlmostEqual(short.lix, short.asl, places=6)
        # One long word ("Fahrrad"): LIX = ASL + share of long words in percent.
        longer = analyzer.analyze_text("## K\n\nHaus. Hund. Baum. Katze. Fahrrad.\n")
        expected = longer.asl + 1.0 / longer.tokens * 100.0
        self.assertAlmostEqual(longer.lix, expected, places=6)


class TestChapterJensenShannon(unittest.TestCase):
    def test_identical_distributions_have_zero_divergence_with_unequal_lengths(self):
        analyzer = CorpusAnalyzer(CorpusConfig(language="en"))
        value, _ = analyzer._jsd_chapter(
            Counter({"alpha": 90}), Counter({"alpha": 100}), 90, 100
        )
        self.assertAlmostEqual(value, 0.0, places=12)

    def test_disjoint_distributions_reach_log_two_with_unequal_lengths(self):
        analyzer = CorpusAnalyzer(CorpusConfig(language="de"))
        value, _ = analyzer._jsd_chapter(
            Counter({"alpha": 90}), Counter({"alpha": 90, "beta": 10}), 90, 100
        )
        self.assertAlmostEqual(value, math.log(2.0), places=12)
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, math.log(2.0))


class TestSyllableRules(unittest.TestCase):
    GERMAN: ClassVar[dict[str, int]] = {
        "Kaffee": 2,
        "Idee": 2,
        "See": 1,
        "Boot": 1,
        "Straße": 2,
        "Theke": 2,
        "Eigentlich": 3,
    }
    ENGLISH: ClassVar[dict[str, int]] = {
        "table": 2,
        "little": 2,
        "people": 2,
        "mile": 1,
        "whole": 1,
        "style": 1,
        "gentle": 2,
        "business": 2,
        "rhythm": 1,
    }

    def test_german_syllables(self):
        for word, expected in self.GERMAN.items():
            with self.subTest(word=word):
                self.assertEqual(count_de(word), expected)

    def test_english_syllables(self):
        for word, expected in self.ENGLISH.items():
            with self.subTest(word=word):
                self.assertEqual(count_en(word), expected)

    def test_minimum_one_syllable(self):
        for word in ("x", "bzgl", ""):
            self.assertGreaterEqual(count_de(word), 1)
            self.assertGreaterEqual(count_en(word), 0)


class TestRobustStatistics(unittest.TestCase):
    def test_median_and_mad(self):
        cases = (([1.0, 2.0, 3.0], 2.0, 1.0),
                 ([1.0, 2.0, 3.0, 4.0], 2.5, 1.0),
                 ([1.0, 2.0, 3.0, 4.0, 5.0], 3.0, 1.0),
                 ([5.0], 5.0, 0.0))
        for values, centre, spread in cases:
            with self.subTest(values=values):
                self.assertEqual(median(values), centre)
                self.assertEqual(mad(values, centre), spread)
        self.assertEqual(mad([], 0.0), 0.0)

    def test_robust_z_and_significance_z(self):
        # Modified z-score (Iglewicz & Hoaglin): the exact inverse of the
        # MAD->sigma factor 1.4826, i.e. 0.674490759... (not a pinned 0.6745).
        self.assertAlmostEqual(robust_z(4.0, 2.0, 1.0), (1.0 / 1.4826) * 2.0, places=9)
        self.assertAlmostEqual(robust_z(1.0, 2.0, 1.0), -1.0 / 1.4826, places=9)
        self.assertEqual(robust_z(4.0, 2.0, 0.0), 0.0)  # no spread -> no statement
        # z* shrinks noisy observations: sigma=1, se=1 -> denominator sqrt(2)
        self.assertAlmostEqual(significance_z(3.0, 1.0, 1.0, 1.0), 2.0 / math.sqrt(2.0), places=9)
        self.assertEqual(significance_z(3.0, 1.0, 0.0, 0.0), 0.0)
        self.assertAlmostEqual(significance_z(5.0, 0.0, 2.0, 0.0), 2.5)
        self.assertLess(abs(significance_z(5.0, 0.0, 2.0, 1.5)), 2.5)

    def test_normal_tail_probability(self):
        self.assertAlmostEqual(normal_tail_probability(0.0), 1.0, places=9)
        self.assertAlmostEqual(normal_tail_probability(1.959964), 0.05, places=5)
        self.assertAlmostEqual(normal_tail_probability(2.575829), 0.01, places=5)
        self.assertLess(normal_tail_probability(3.5), normal_tail_probability(2.5))


class TestSharedPrimitives(unittest.TestCase):
    """lixity.math_core is the single source for the plug-in conventions."""

    def test_robust_scale_reuses_the_mad_factor(self):
        values = [1.0, 2.0, 3.0, 4.0, 40.0]
        centre = median(values)
        self.assertEqual(robust_scale(values, centre), MAD_TO_SIGMA * mad(values, centre))
        self.assertEqual(robust_scale(values), MAD_TO_SIGMA * mad(values, centre))

    def test_ratio_density_and_share_totalize_on_zero_denominator(self):
        self.assertEqual(per_mille(4, 1000), 4.0)
        self.assertEqual(per_mille(4, 0), 0.0)
        self.assertEqual(percent(1, 4), 25.0)
        self.assertEqual(percent(1, 0), 0.0)
        self.assertEqual(ratio_or_zero(3.0, 0.0), 0.0)
        self.assertEqual(ratio_or_zero(3.0, 2.0, scale=10.0), 15.0)

    def test_plugin_standard_errors_match_the_documented_estimators(self):
        # Binomial SE of a 50 % share over 100 observations: sqrt(.25/100)*100.
        self.assertAlmostEqual(binomial_se_percent(50.0, 100), 5.0)
        self.assertEqual(binomial_se_percent(50.0, 0), 0.0)
        # Poisson SE of 4 hits per 1,000 words: sqrt(4)*1000/1000.
        self.assertAlmostEqual(poisson_se_per_mille(4, 1000), 2.0)
        self.assertEqual(poisson_se_per_mille(4, 0), 0.0)


class TestPublishedEffectAndFdrReferences(unittest.TestCase):
    """Known-value anchors from the published literature."""

    def test_cliffs_delta_and_romano_bands(self):
        self.assertEqual(cliff_delta([2.0, 3.0], [1.0]), 1.0)
        self.assertEqual(cliff_delta([1.0], [2.0, 3.0]), -1.0)
        self.assertEqual(cliff_delta([1.0, 2.0], [2.0, 1.0]), 0.0)
        labels = [effect_label(value) for value in (0.1469, 0.147, 0.3299, 0.33, 0.4739, 0.474)]
        self.assertEqual(labels, ["negligible", "small", "small", "medium", "medium", "large"])

    def test_benjamini_yekutieli_and_dispatch(self):
        cells = [(1, "a", 0.001), (1, "b", 0.02), (1, "c", 0.04)]
        self.assertEqual(benjamini_hochberg(cells), [(1, "a"), (1, "b"), (1, "c")])
        # Harmonic factor c(3) = 11/6 lowers the BY threshold to q*3/11.
        self.assertEqual(benjamini_yekutieli(cells), [(1, "a")])
        self.assertEqual(fdr_rejects(cells, method="by"), [(1, "a")])
        self.assertEqual(fdr_rejects(cells, method="bh"), benjamini_hochberg(cells))
        self.assertEqual(fdr_rejects([], method="by"), [])

    def test_runs_and_lag1_known_values(self):
        alternating = [1.0, 9.0, 1.0, 9.0, 1.0, 9.0, 1.0, 9.0]
        pooled = [1.0, 1.0, 1.0, 1.0, 9.0, 9.0, 9.0, 9.0]
        # mu = 5 and var = 768/448 for n = 8 with 4/4 signs; runs are 8 and 2.
        expected = 3.0 / math.sqrt(768.0 / 448.0)
        self.assertAlmostEqual(runs_above_median_z(alternating), expected)
        self.assertAlmostEqual(runs_above_median_z(pooled), -expected)
        self.assertIsNone(runs_above_median_z([1.0, 2.0, 3.0]))
        self.assertEqual(lag1_autocorrelation([1.0, 2.0, 3.0, 4.0]), 0.25)
        self.assertIsNone(lag1_autocorrelation([1.0, 2.0]))
        self.assertIsNone(lag1_autocorrelation([3.0, 3.0, 3.0]))


class TestBenjaminiHochberg(unittest.TestCase):
    """Published example: Benjamini & Hochberg (1995), Table 1 (q = 0.05)."""

    P_VALUES: ClassVar[list[float]] = [
        0.0001,
        0.0004,
        0.0019,
        0.0095,
        0.0201,
        0.0278,
        0.0298,
        0.0344,
        0.0459,
        0.3240,
        0.4262,
        0.5719,
        0.6528,
        0.7590,
        1.0000,
    ]

    def test_four_rejections(self):
        cells = [(i, f"f{i}", p) for i, p in enumerate(self.P_VALUES)]
        rejected = benjamini_hochberg(cells, q=0.05)
        self.assertEqual(len(rejected), 4)
        self.assertEqual([ch for ch, _ in rejected], [0, 1, 2, 3])
        sparse = [(1, "asl", 0.001), (2, "asl", 0.03), (3, "asl", 0.04), (4, "asl", 0.5)]
        self.assertEqual(benjamini_hochberg(sparse, q=0.05), [(1, "asl")])

    def test_q_zero_rejects_nothing(self):
        cells = [(i, f"f{i}", p) for i, p in enumerate(self.P_VALUES)]
        self.assertEqual(benjamini_hochberg(cells, q=0.0), [])

    def test_empty_input(self):
        self.assertEqual(benjamini_hochberg([], q=0.05), [])

    def test_deterministic_ordering_on_ties(self):
        cells = [(2, "b", 0.01), (1, "a", 0.01), (3, "c", 0.001)]
        first = benjamini_hochberg(cells, q=0.05)
        second = benjamini_hochberg(list(reversed(cells)), q=0.05)
        self.assertEqual(first, second)
        self.assertEqual(first, [(3, "c"), (1, "a"), (2, "b")])


class TestSpearman(unittest.TestCase):
    def test_monotone_and_reversed(self):
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        self.assertAlmostEqual(spearman_rho(x, [2.0, 4.0, 6.0, 8.0, 10.0]), 1.0, places=9)
        self.assertAlmostEqual(spearman_rho(x, [10.0, 8.0, 6.0, 4.0, 2.0]), -1.0, places=9)

    def test_ties_use_average_ranks(self):
        cases = (([1.0, 1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0], 3 / math.sqrt(10)),
                 ([1.0, 1.0, 2.0], [1.0, 2.0, 2.0], 0.5))
        for left, right, expected in cases:
            with self.subTest(left=left, right=right):
                self.assertAlmostEqual(spearman_rho(left, right), expected, places=12)

    def test_short_series_returns_zero(self):
        self.assertEqual(spearman_rho([1.0, 2.0], [2.0, 1.0]), 0.0)

    def test_zero_variance_returns_zero(self):
        self.assertEqual(spearman_rho([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]), 0.0)


class TestJacobiEigendecomposition(unittest.TestCase):
    def test_two_by_two_known_solution(self):
        eigenvalues, eigenvectors = jacobi_eigh([[2.0, 1.0], [1.0, 2.0]])
        self.assertAlmostEqual(eigenvalues[0], 3.0, places=9)
        self.assertAlmostEqual(eigenvalues[1], 1.0, places=9)
        diagonal, _ = jacobi_eigh([[2.0, 0.0], [0.0, 3.0]])
        self.assertEqual(diagonal, [3.0, 2.0])
        # eigenvectors[i] belongs to eigenvalues[i] (sorted descending)
        self.assertAlmostEqual(abs(eigenvectors[0][0]), 1.0 / math.sqrt(2.0), places=9)

    def test_eigenpairs_orthogonality_and_determinism_on_symmetric_matrices(self):
        matrices = (
            [[4.0, 1.0, 2.0], [1.0, 3.0, 0.5], [2.0, 0.5, 2.0]],
            [[1.0, 0.4, 0.1, -0.2], [0.4, 1.0, 0.3, 0.1],
             [0.1, 0.3, 1.0, -0.4], [-0.2, 0.1, -0.4, 1.0]],
        )
        for matrix in matrices:
            with self.subTest(size=len(matrix)):
                eigenvalues, eigenvectors = jacobi_eigh(matrix)
                self.assertEqual(jacobi_eigh(matrix), (eigenvalues, eigenvectors))
                n = len(matrix)
                self.assertAlmostEqual(sum(eigenvalues), sum(matrix[i][i] for i in range(n)), places=8)
                if n == 3:
                    det = (
                        matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
                        - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
                        + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
                    )
                    self.assertAlmostEqual(math.prod(eigenvalues), det, places=8)
                for index, lam in enumerate(eigenvalues):
                    vector = eigenvectors[index]
                    for row in range(n):
                        ax = sum(matrix[row][col] * vector[col] for col in range(n))
                        self.assertAlmostEqual(ax, lam * vector[row], places=8)
                for i, left in enumerate(eigenvectors):
                    for j, right in enumerate(eigenvectors):
                        self.assertAlmostEqual(sum(a * b for a, b in zip(left, right, strict=True)),
                                               1.0 if i == j else 0.0, places=9)


if __name__ == "__main__":
    unittest.main()
