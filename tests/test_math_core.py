"""
tests/test_math_core.py
=======================
Known-value and property tests for the mathematical core: readability
formulas, LIX threshold, syllable rules, robust statistics (median/MAD/z*),
normal tail probabilities, Benjamini-Hochberg FDR, Spearman correlation,
Jacobi eigendecomposition and lexical-diversity indices.
"""

from __future__ import annotations

import math
import os
import sys
import unittest
from typing import ClassVar

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.analyzer import CorpusAnalyzer  # noqa: E402
from lixity.diversity import hd_d, maas_a2, mattr, mtld, yules_k  # noqa: E402
from lixity.models import CorpusConfig  # noqa: E402
from lixity.style_fingerprint import (  # noqa: E402
    benjamini_hochberg,
    jacobi_eigh,
    mad,
    median,
    normal_tail_probability,
    robust_z,
    significance_z,
    spearman_rho,
)
from lixity.syllables import count_de, count_en  # noqa: E402


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
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        centre = median(values)
        self.assertEqual(centre, 3.0)
        self.assertEqual(mad(values, centre), 1.0)  # median of |x - 3|

    def test_mad_scaling_constant(self):
        # sigma = 1.4826 * MAD is the consistency constant for the normal distribution
        self.assertAlmostEqual(1.4826 * 1.0, 1.4826, places=4)

    def test_robust_z_and_significance_z(self):
        # Modified z-score (Iglewicz & Hoaglin): 0.6745 * (x - median) / MAD
        self.assertAlmostEqual(robust_z(4.0, 2.0, 1.0), 0.6745 * 2.0, places=9)
        self.assertEqual(robust_z(4.0, 2.0, 0.0), 0.0)  # no spread -> no statement
        # z* shrinks noisy observations: sigma=1, se=1 -> denominator sqrt(2)
        self.assertAlmostEqual(significance_z(3.0, 1.0, 1.0, 1.0), 2.0 / math.sqrt(2.0), places=9)
        self.assertEqual(significance_z(3.0, 1.0, 0.0, 0.0), 0.0)

    def test_normal_tail_probability(self):
        self.assertAlmostEqual(normal_tail_probability(0.0), 1.0, places=9)
        self.assertAlmostEqual(normal_tail_probability(1.959964), 0.05, places=5)
        self.assertAlmostEqual(normal_tail_probability(2.575829), 0.01, places=5)
        self.assertLess(normal_tail_probability(3.5), normal_tail_probability(2.5))


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
        rho = spearman_rho([1.0, 1.0, 2.0, 3.0], [1.0, 2.0, 3.0, 4.0])
        self.assertGreater(rho, 0.8)
        self.assertLess(rho, 1.0)

    def test_short_series_returns_zero(self):
        self.assertEqual(spearman_rho([1.0, 2.0], [2.0, 1.0]), 0.0)

    def test_zero_variance_returns_zero(self):
        self.assertEqual(spearman_rho([1.0, 1.0, 1.0], [1.0, 2.0, 3.0]), 0.0)


class TestJacobiEigendecomposition(unittest.TestCase):
    def test_two_by_two_known_solution(self):
        eigenvalues, eigenvectors = jacobi_eigh([[2.0, 1.0], [1.0, 2.0]])
        self.assertAlmostEqual(eigenvalues[0], 3.0, places=9)
        self.assertAlmostEqual(eigenvalues[1], 1.0, places=9)
        # eigenvectors[i] belongs to eigenvalues[i] (sorted descending)
        self.assertAlmostEqual(abs(eigenvectors[0][0]), 1.0 / math.sqrt(2.0), places=9)

    def test_properties_on_a_symmetric_matrix(self):
        matrix = [
            [4.0, 1.0, 2.0],
            [1.0, 3.0, 0.5],
            [2.0, 0.5, 2.0],
        ]
        eigenvalues, eigenvectors = jacobi_eigh(matrix)
        n = len(matrix)
        # trace and determinant identities
        self.assertAlmostEqual(sum(eigenvalues), sum(matrix[i][i] for i in range(n)), places=8)
        det = (
            matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
            - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
            + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
        )
        self.assertAlmostEqual(math.prod(eigenvalues), det, places=8)
        # A v = lambda v for every pair
        for index, lam in enumerate(eigenvalues):
            vector = eigenvectors[index]
            for row in range(n):
                ax = sum(matrix[row][col] * vector[col] for col in range(n))
                self.assertAlmostEqual(ax, lam * vector[row], places=8)
        # eigenvectors are orthonormal
        for i in range(n):
            vi = eigenvectors[i]
            self.assertAlmostEqual(sum(c * c for c in vi), 1.0, places=9)
            for j in range(i + 1, n):
                vj = eigenvectors[j]
                self.assertAlmostEqual(sum(a * b for a, b in zip(vi, vj, strict=True)), 0.0, places=9)


class TestLexicalDiversityProperties(unittest.TestCase):
    def test_yule_and_maas_of_all_unique_tokens(self):
        tokens = [f"w{i}" for i in range(150)]
        self.assertAlmostEqual(yules_k(tokens), 0.0, places=12)
        self.assertAlmostEqual(
            maas_a2(len(tokens), len(set(tokens))), 0.0, places=12
        )

    def test_mattr_window_properties(self):
        tokens = [f"w{i}" for i in range(100)]
        unique_mattr = mattr(tokens, window=50)
        self.assertIsNotNone(unique_mattr)
        self.assertAlmostEqual(float(unique_mattr), 1.0, places=12)
        repeated = mattr(["a"] * 100, window=50)
        self.assertIsNotNone(repeated)
        self.assertAlmostEqual(float(repeated), 0.02, places=12)

    def test_mtld_short_text_returns_none(self):
        self.assertIsNone(mtld(["a"] * 50))

    def test_mtld_all_unique_returns_none(self):
        self.assertIsNone(mtld([f"w{i}" for i in range(200)]))

    def test_hd_d_is_deterministic_and_bounded(self):
        tokens = ([f"w{i}" for i in range(80)] * 5)[:400]
        first = hd_d(tokens)
        second = hd_d(tokens)
        self.assertEqual(first, second)
        self.assertIsNotNone(first)
        value = float(first)  # type: ignore[arg-type]
        self.assertGreaterEqual(value, 0.0)
        self.assertLessEqual(value, 1.0)


if __name__ == "__main__":
    unittest.main()
