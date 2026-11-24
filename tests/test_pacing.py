"""
tests/test_pacing.py
====================
Scene structure, pacing signals and chapter hooks: scene-break detection,
aggregation, hook heuristics and the CLI/API surface.
"""

import os
import sys
import unittest
from decimal import Decimal, localcontext

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.models import CorpusConfig  # noqa: E402
from lixity.pacing import burstiness, compute_rhythm_profile, pacing_report  # noqa: E402

DE = CorpusConfig(language="de")

SCENES = """## Erstes Kapitel

Er ging zum Fenster. Sie blieb am Tisch.

---

Später kam der Regen. Alles war still und ruhig und leer.

## Zweites Kapitel

»Komm her!«
"""

HOOKS = """## Kurz

Er ging. Sie blieb. Dann war es still.

## Frage

Es war dunkel.

## Ausruf

Der Regen fiel. Dann kam der Sturm!
"""


class TestScenes(unittest.TestCase):
    def test_scene_breaks_split_scenes(self):
        report = pacing_report(SCENES, DE)
        first = report.chapter_list[0]
        self.assertEqual(first.scenes, 2)
        self.assertEqual([scene.index for scene in first.scene_list], [1, 2])

    def test_scene_words_and_signals(self):
        report = pacing_report(SCENES, DE)
        first = report.chapter_list[0]
        self.assertEqual(sum(scene.words for scene in first.scene_list), first.words)
        self.assertGreater(first.asl, 0.0)
        self.assertLessEqual(first.dialogue_pct, 100.0)

    def test_corpus_aggregates(self):
        report = pacing_report(SCENES, DE)
        self.assertEqual(report.chapters, 2)
        self.assertEqual(report.scenes, 3)
        self.assertGreater(report.avg_scene_words, 0.0)
        self.assertAlmostEqual(report.avg_chapter_scenes, 1.5, places=6)

    def test_alternative_divider_forms(self):
        text = "## Eins\n\nA. B.\n\n* * *\n\nC. D.\n\n***\n\nE. F.\n"
        report = pacing_report(text, DE)
        self.assertEqual(report.chapter_list[0].scenes, 3)


class TestHooks(unittest.TestCase):
    def test_short_closing_sentence_scores(self):
        report = pacing_report(HOOKS, DE)
        by_num = {chapter.chapter_num: chapter for chapter in report.chapter_list}
        # "Dann war es still." (4 words, period, no dialogue) -> 1
        self.assertEqual(by_num[1].hook_score, 1)
        # "Es war dunkel." (3 words, period) -> 1
        self.assertEqual(by_num[2].hook_score, 1)
        # "Dann kam der Sturm!" (4 words, "!", no dialogue) -> 2
        self.assertEqual(by_num[3].hook_score, 2)
        self.assertEqual(by_num[3].closing_terminal, "!")

    def test_closing_dialogue_counts(self):
        text = "## Eins\n\nEr ging. »Komm her!«\n"
        report = pacing_report(text, DE)
        chapter = report.chapter_list[0]
        self.assertTrue(chapter.closing_is_dialogue)
        self.assertEqual(chapter.hook_score, 3)  # short + "!" + dialogue

    def test_long_closing_sentence_scores_zero(self):
        text = (
            "## Eins\n\n"
            "Der Abend senkte sich langsam über die Dächer der stillen Stadt und "
            "niemand sagte ein Wort darüber.\n"
        )
        report = pacing_report(text, DE)
        self.assertEqual(report.chapter_list[0].hook_score, 0)

    def test_hook_mean(self):
        report = pacing_report(HOOKS, DE)
        self.assertAlmostEqual(report.hook_score_mean, 4 / 3, places=6)


class TestReportSurface(unittest.TestCase):
    def test_fastest_and_slowest_chapter(self):
        text = (
            "## Eins\n\nKurz. Sehr kurz. Noch kurz.\n\n"
            "## Zwei\n\n"
            "Ein außerordentlich langer Satz mit vielen Wörtern zieht sich über "
            "die Zeile und noch weiter.\n"
        )
        report = pacing_report(text, DE)
        self.assertEqual(report.fastest_chapter, 1)
        self.assertEqual(report.slowest_chapter, 2)

    def test_deterministic(self):
        first = pacing_report(SCENES, DE).to_dict()
        second = pacing_report(SCENES, DE).to_dict()
        self.assertEqual(first, second)

    def test_empty_text(self):
        report = pacing_report("", DE)
        self.assertEqual(report.chapters, 0)
        self.assertEqual(report.scenes, 0)
        self.assertEqual(report.explicit_scene_breaks, 0)
        self.assertFalse(report.scenes_are_chapters)
        self.assertIsNone(report.fastest_chapter)

    def test_spaced_dividers_and_asterism_split_scenes(self):
        text = ("## Eins\n\nErster Absatz.\n\n- - -\n\nZweiter Absatz.\n\n_ _ _\n\nDritter Absatz.\n\n"
                "• • •\n\nVierter Absatz.\n\n———\n\nFünfter Absatz.\n\n⁂\n\nSechster Absatz.\n")
        report = pacing_report(text, DE)
        self.assertEqual(report.explicit_scene_breaks, 5)
        self.assertEqual(report.scenes, 6)
        self.assertFalse(report.scenes_are_chapters)

    def test_no_dividers_flags_scenes_are_chapters(self):
        text = "## Eins\n\nEr ging. Sie blieb.\n\n## Zwei\n\nEs war still.\n"
        report = pacing_report(text, DE)
        self.assertEqual(report.explicit_scene_breaks, 0)
        self.assertTrue(report.scenes_are_chapters)
        self.assertEqual(report.scenes, report.chapters)
        payload = report.to_dict()
        self.assertIs(payload["scenes_are_chapters"], True)
        self.assertEqual(payload["explicit_scene_breaks"], 0)

    def test_explicit_breaks_clears_flag(self):
        report = pacing_report(SCENES, DE)
        self.assertEqual(report.explicit_scene_breaks, 1)
        self.assertFalse(report.scenes_are_chapters)
        self.assertIs(report.to_dict()["scenes_are_chapters"], False)

    def test_repeated_start_runs_and_sentence_overlap(self):
        text = (
            "## Eins\n\n"
            "Er öffnete die schwere Eisentür. "
            "Er blickte hinter die Eisentür in den Gang. "
            "Er betrat den dunklen Gang.\n\n"
            "Mara wartete draußen. Tomas schwieg.\n"
        )
        report = pacing_report(text, DE)
        chapter = report.chapter_list[0]
        self.assertEqual(chapter.repeated_start_runs, 1)
        self.assertEqual(chapter.adjacent_sentence_pairs, 3)
        self.assertAlmostEqual(chapter.sentence_overlap_pct, 2 / 3 * 100.0, places=4)
        self.assertEqual(report.repeated_start_runs, 1)
        self.assertEqual(report.adjacent_sentence_pairs, 3)
        self.assertAlmostEqual(report.sentence_overlap_pct, 2 / 3 * 100.0, places=4)

    def test_configurable_hook_and_monotony_thresholds(self):
        text = (
            "## Eins\n\n"
            "Er ging schnell. Er ging weiter. Er ging heim.\n"
        )
        custom_strict = CorpusConfig(language="de", hook_short_sentence=2, monotony_min_run=4)
        report_strict = pacing_report(text, custom_strict)
        # Closing sentence has 3 words > hook_short_sentence(2) -> hook_score 0
        self.assertEqual(report_strict.chapter_list[0].hook_score, 0)
        # 3 identical sentence starts < monotony_min_run(4) -> 0 runs
        self.assertEqual(report_strict.chapter_list[0].repeated_start_runs, 0)

        custom_relaxed = CorpusConfig(language="de", hook_short_sentence=5, monotony_min_run=2)
        report_relaxed = pacing_report(text, custom_relaxed)
        self.assertEqual(report_relaxed.chapter_list[0].hook_score, 1)
        self.assertEqual(report_relaxed.chapter_list[0].repeated_start_runs, 1)

    def test_pacing_micro_timeline_and_sparkline(self):
        from lixity.pacing import compute_rolling_asl, compute_sparkline, condense_timeline

        lengths = [4, 6, 8, 10, 12, 14, 16, 18, 20]
        rolling = compute_rolling_asl(lengths, window=3)
        self.assertEqual(len(rolling), 7)
        self.assertEqual(rolling[0], round((4 + 6 + 8) / 3, 1))

        condensed = condense_timeline(rolling, target_points=4)
        self.assertEqual(len(condensed), 4)

        spark = compute_sparkline([1.0, 5.0, 10.0])
        self.assertEqual(len(spark), 3)
        self.assertEqual(spark[0], " ")
        self.assertEqual(spark[-1], "█")

        text = "## Test\n\nKurz. Ein zweiter Satz. Und noch ein viel längerer Satz hier.\n"
        report = pacing_report(text, DE)
        ch = report.chapter_list[0]
        self.assertTrue(ch.pacing_sparkline)
        self.assertGreater(ch.sentence_cv, 0.0)
        self.assertTrue(ch.pacing_curve)
        payload = ch.to_dict()
        self.assertIn("pacing_sparkline", payload)
        self.assertIn("sentence_cv", payload)
        self.assertIn("pacing_curve", payload)


class TestBurstiness(unittest.TestCase):
    def test_extreme_scales_match_independent_decimal_moments(self) -> None:
        cases = (
            [4, 12, 25, 8, 30],
            [1e308, 5e307, 2e307],
            [1e-310, 2e-310, 4e-310],
            [10**400, 2 * 10**400, 0.5, 10**399],
        )
        for values in cases:
            with self.subTest(values=values), localcontext() as context:
                context.prec = 80
                n = Decimal(len(values))
                decimal_values = [Decimal(value) for value in values]
                total = sum(decimal_values)
                squares = sum(value**2 for value in decimal_values)
                r = ((n * squares / total**2 - 1) * n / (n - 1)).sqrt()
                expected = (r - 1) / (1 + (1 - 2 / n.sqrt()) * r)
                actual = burstiness(values)
                assert actual is not None
                self.assertAlmostEqual(actual, float(expected), places=14)

    def test_invalid_observations_raise_instead_of_returning_a_signal(self) -> None:
        for value in (-1, float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, "finite nonnegative"):
                burstiness([3, value])

    def test_finite_sample_burstiness_bounds_and_rhythm_profile(self):
        self.assertIsNone(burstiness([]))
        self.assertIsNone(burstiness([5]))
        self.assertIsNone(burstiness([0, 0, 0]))

        self.assertAlmostEqual(burstiness([5, 5, 5, 5]), -1.0, places=12)
        self.assertAlmostEqual(burstiness([0, 0, 0, 10]), 1.0, places=12)
        varied = burstiness([4, 12, 25, 8, 30])
        self.assertIsNotNone(varied)
        assert varied is not None
        self.assertGreater(varied, -1.0)
        self.assertLess(varied, 1.0)

        empty_prof = compute_rhythm_profile([5])
        self.assertIsNone(empty_prof["burstiness"])
        flat_prof = compute_rhythm_profile([10, 10, 10, 10])
        self.assertEqual(flat_prof["burstiness"], -1.0)


if __name__ == "__main__":
    unittest.main()
