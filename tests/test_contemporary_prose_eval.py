"""Tests for scripts/evaluate_contemporary_prose.py."""

from __future__ import annotations

import io
import json
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import evaluate_contemporary_prose as bench  # noqa: E402


class TestContemporaryProseBenchmark(unittest.TestCase):
    def test_wilson_interval_edge_cases_and_bounds(self) -> None:
        self.assertEqual(bench.wilson_interval(0, 0), (None, None))
        with self.assertRaises(ValueError):
            bench.wilson_interval(5, 4)
        with self.assertRaises(ValueError):
            bench.wilson_interval(-1, 4)

        for k, n in ((0, 1), (1, 1), (0, 10), (5, 10), (10, 10), (22, 24), (49, 54)):
            lo, hi = bench.wilson_interval(k, n)
            assert lo is not None and hi is not None
            p = k / n
            self.assertGreaterEqual(lo, 0.0)
            self.assertLessEqual(hi, 1.0)
            self.assertLessEqual(lo, p + 1e-12)
            self.assertGreaterEqual(hi, p - 1e-12)
            self.assertLess(lo, hi)

    def test_benchmark_is_deterministic_and_offline(self) -> None:
        first = bench.run_benchmark()
        second = bench.run_benchmark()
        self.assertEqual(
            json.dumps(first, sort_keys=True),
            json.dumps(second, sort_keys=True),
        )

    def test_all_reported_wilson_cis_are_valid(self) -> None:
        report = bench.run_benchmark()

        def check_metric_block(block: dict[str, Any], label: str) -> None:
            for rate_key, ci_key in (("precision", "precision_ci95"), ("recall", "recall_ci95")):
                rate = block[rate_key]
                ci = block[ci_key]
                if rate is None:
                    self.assertIsNone(ci, label)
                else:
                    self.assertIsNotNone(ci, label)
                    lo, hi = ci
                    self.assertGreaterEqual(lo, 0.0, label)
                    self.assertLessEqual(hi, 1.0, label)
                    self.assertLessEqual(lo, rate + 1e-12, label)
                    self.assertGreaterEqual(hi, rate - 1e-12, label)

        for lang in ("en", "de"):
            lang_data = report["languages"][lang]
            check_metric_block(lang_data["sentence_boundaries"], f"{lang}.sentences")
            check_metric_block(lang_data["dialogue_cues"], f"{lang}.dialogue")
            for cat, cat_metrics in lang_data["dialogue_cues"]["by_category"].items():
                check_metric_block(cat_metrics, f"{lang}.dialogue.{cat}")
            for sub in ("combined", "present", "past"):
                check_metric_block(lang_data["tense_cues"][sub], f"{lang}.tense.{sub}")

    def test_honest_reporting_of_hits_and_misses(self) -> None:
        report = bench.run_benchmark()
        for lang in ("en", "de"):
            lang_data = report["languages"][lang]

            sent = lang_data["sentence_boundaries"]
            self.assertGreaterEqual(sent["n_gold_sentences"], 35)
            self.assertGreater(sent["tp"], 0)
            self.assertGreater(sent["fp"] + sent["fn"], 0)

            dlg = lang_data["dialogue_cues"]
            self.assertGreater(dlg["tp"], 0)
            self.assertGreater(dlg["fp"], 0)
            self.assertGreater(dlg["fn"], 0)
            self.assertLess(dlg["recall"], 0.70)
            self.assertLess(dlg["precision"], 1.0)
            by_cat = dlg["by_category"]
            self.assertGreater(by_cat["standard_quoted"]["tp"], 0)
            for missed_cat in ("dash_speech", "interior_thought", "free_indirect"):
                self.assertEqual(by_cat[missed_cat]["tp"], 0, f"{lang}.{missed_cat}")
                self.assertGreater(by_cat[missed_cat]["fn"], 0, f"{lang}.{missed_cat}")
            self.assertGreater(by_cat["non_speech_quote"]["fp"], 0)

            tense = lang_data["tense_cues"]
            self.assertGreaterEqual(tense["n_passages"], 30)
            combined = tense["combined"]
            self.assertGreater(combined["tp"], 0)
            self.assertGreater(combined["fp"], 0)
            self.assertGreater(combined["fn"], 0)

    def test_cli_json_and_markdown_outputs(self) -> None:
        buf_json = io.StringIO()
        with redirect_stdout(buf_json):
            rc = bench.main(["--json"])
        self.assertEqual(rc, 0)
        parsed = json.loads(buf_json.getvalue())
        self.assertEqual(parsed["benchmark"], "contemporary-style-prose-heldout/1")
        self.assertEqual(parsed["ci_method"], "wilson-95")

        buf_md = io.StringIO()
        with redirect_stdout(buf_md):
            rc = bench.main([])
        self.assertEqual(rc, 0)
        markdown = buf_md.getvalue()
        self.assertIn("95% Wilson CI", markdown)
        self.assertIn("| EN | Sentence boundaries |", markdown)
        self.assertIn("| DE | Dialogue cues (all) |", markdown)
        self.assertIn("## Dialogue recall breakdown by category", markdown)


if __name__ == "__main__":
    unittest.main()
