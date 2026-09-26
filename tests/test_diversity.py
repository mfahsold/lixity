"""Numerical fixtures for lexical-diversity estimators."""

from __future__ import annotations

import math
import unittest

from lixity.diversity import hd_d, hd_d_stats


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

    def test_token_order_and_legacy_sampling_arguments_do_not_change_result(self) -> None:
        grouped = ["a"] * 100 + ["b"] * 100
        alternating = [token for _ in range(100) for token in ("a", "b")]
        self.assertEqual(hd_d(grouped), hd_d(alternating))
        self.assertEqual(hd_d(grouped), hd_d(grouped, seed=123, min_samples=99))

    def test_short_text_guard_is_shared_lexical_diversity_floor(self) -> None:
        self.assertEqual(hd_d_stats(["a"] * 99), (None, 0.0))
        self.assertAlmostEqual(hd_d(["a"] * 100), 1 / 42, places=14)

    def test_rare_type_probability_is_stable_in_long_input(self) -> None:
        tokens = ["common"] * 100_000 + ["rare"]
        expected = (1 + 42 / len(tokens)) / 42
        self.assertAlmostEqual(hd_d(tokens), expected, places=14)


if __name__ == "__main__":
    unittest.main()
