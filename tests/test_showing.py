"""
tests/test_showing.py
=====================
Showing/telling balance: self-calibrating robust z-scores, chapter ranking
and determinism.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.models import CorpusConfig  # noqa: E402
from lixity.showing import showing_report  # noqa: E402

DE = CorpusConfig(language="de")

# Dialogue-heavy (showing) vs. filter/modal-heavy (telling) chapters; the
# neutral chapters give the median/MAD reference enough spread.
NEUTRAL = (
    "Der Regen fiel auf die Straße. Die Stadt war still. Der Abend kam. "
    "Die Lichter gingen an. Ein Wagen fuhr vorbei.\n"
)
TEXT = (
    "## Eins\n\n"
    "»Komm!«, sagte sie. »Nein!«, sagte er. »Doch!«, rief sie. »Nie!«, rief er.\n"
    "»Warum?«, fragte sie. »Darum!«, sagte er.\n\n"
    "## Zwei\n\n"
    "Er spürte die Kälte. Er merkte den Wind. Er fühlte den Regen. Er glaubte, "
    "dass es kalt werden könnte. Er spürte das Zittern. Er merkte die Angst. "
    "Er fühlte die Leere. Er glaubte an nichts. Er spürte den Schmerz.\n\n"
    "## Drei\n\n" + NEUTRAL + "\n"
    "## Vier\n\n" + NEUTRAL + "\n"
    "## Fünf\n\n" + NEUTRAL + "\n"
)


class TestShowingReport(unittest.TestCase):
    def test_dialogue_chapter_shows_more(self):
        report = showing_report(TEXT, DE)
        by_num = {c.chapter_num: c for c in report.chapter_list}
        self.assertGreater(by_num[1].balance, by_num[2].balance)

    def test_most_telling_and_showing(self):
        report = showing_report(TEXT, DE)
        self.assertIn(2, report.most_telling)
        self.assertIn(1, report.most_showing)

    def test_balance_definition(self):
        report = showing_report(TEXT, DE)
        for chapter in report.chapter_list:
            self.assertAlmostEqual(chapter.balance, chapter.show_z - chapter.tell_z, places=9)

    def test_signals_present(self):
        report = showing_report(TEXT, DE)
        chapter = report.chapter_list[0]
        self.assertGreater(chapter.dialog_pct, 0.0)
        self.assertGreaterEqual(chapter.filter_density, 0.0)

    def test_deterministic(self):
        first = showing_report(TEXT, DE).to_dict()
        second = showing_report(TEXT, DE).to_dict()
        self.assertEqual(first, second)

    def test_empty_text(self):
        report = showing_report("", DE)
        self.assertEqual(report.chapters, 0)
        self.assertEqual(report.chapter_list, [])


if __name__ == "__main__":
    unittest.main()
