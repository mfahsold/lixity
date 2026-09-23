"""
tests/test_pacing.py
====================
Scene structure, pacing signals and chapter hooks: scene-break detection,
aggregation, hook heuristics and the CLI/API surface.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.models import CorpusConfig  # noqa: E402
from lixity.pacing import pacing_report  # noqa: E402

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


if __name__ == "__main__":
    unittest.main()
