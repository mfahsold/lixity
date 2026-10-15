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
# neutral chapters give the median/MAD reference enough spread. Every chapter
# clears the comparability floor of 100 words.
NEUTRAL = (
    "Der Regen fiel auf die Straße. Die Stadt war still. Der Abend kam. "
    "Die Lichter gingen an. Ein Wagen fuhr vorbei. Die Fenster wurden dunkel. "
    "Auf dem Asphalt spiegelten sich die Laternen. Ein Hund lief über den Platz. "
    "Die Uhren am Turm schlugen. Niemand blieb stehen. Die Nacht wurde kalt. "
    "Der Wind drehte über den Dächern. Ein Zug verließ den Bahnhof. "
    "Die Geschäfte schlossen leise. Ein Fahrrad klingelte im Hof. "
    "Die Bäume standen schwarz vor dem Himmel. Eine Tür fiel ins Schloss. "
    "Die Gasse lag leer. Der Brunnen plätscherte leise. Ein Vogel strich über "
    "das Dach. Vor dem Tor wartete ein Wagen mit laufendem Motor."
)
DIALOGUE = (
    "»Komm!«, sagte sie. »Nein!«, sagte er. »Doch!«, rief sie. »Nie!«, rief er. "
    "»Warum?«, fragte sie. »Darum!«, sagte er. »Warte!«, bat sie. »Gleich!«, "
    "antwortete er. »Jetzt!«, drängte sie. »Später!«, winkte er ab. »Bitte!«, "
    "flüsterte sie. »Nein!«, wiederholte er. »Immer!«, lachte sie. »Niemals!«, "
    "murmelte er. »Hier!«, rief sie. »Dort!«, sagte er. »Sofort!«, verlangte "
    "sie. »Geduld!«, erwiderte er. »Warum nicht?«, fragte sie. »Weil nicht!«, "
    "sagte er. »Und morgen?«, hoffte sie. »Vielleicht«, brummte er. "
    "»Versprochen?«, hakte sie nach. »Versprochen!«, log er. »Schwöre es!«, "
    "forderte sie. »Ich schwöre!«, sagte er. »Ende!«, sagte sie. »Noch nicht!«, "
    "antwortete er. »Doch!«, beharrte sie. »Gut!«, gab er schließlich nach."
)
TELLING = (
    "Er spürte die Kälte. Er merkte den Wind. Er fühlte den Regen. Er glaubte, "
    "dass es kalt werden könnte. Er spürte das Zittern. Er merkte die Angst. "
    "Er fühlte die Leere. Er glaubte an nichts. Er spürte den Schmerz. "
    "Er merkte den Druck. Er fühlte die Müdigkeit. Er glaubte, dass niemand "
    "ihm helfen würde. Er spürte den Hunger. Er merkte die Stille. "
    "Er fühlte den Zweifel. Er glaubte an den Zufall. Er spürte die Kälte "
    "wieder. Er merkte, dass er zitterte. Er fühlte den Boden unter den Füßen. "
    "Er glaubte an einen neuen Morgen. Er merkte die Schwere in den Beinen. "
    "Er fühlte, dass der Regen nachließ."
)
TEXT = (
    "## Eins\n\n" + DIALOGUE + "\n\n"
    "## Zwei\n\n" + TELLING + "\n\n"
    "## Drei\n\n" + NEUTRAL + "\n\n"
    "## Vier\n\n" + NEUTRAL + "\n\n"
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

    def test_rankings_require_a_distinguishable_chapter_balance(self):
        report = showing_report("\n".join(f"## {number}\n\n{NEUTRAL}" for number in range(1, 5)), DE)
        self.assertTrue(report.chapter_list)
        self.assertEqual({chapter.balance for chapter in report.chapter_list}, {0.0})
        self.assertEqual(report.most_telling, [])
        self.assertEqual(report.most_showing, [])
        payload = report.to_dict()
        self.assertEqual(payload["most_telling"], [])
        self.assertEqual(payload["most_showing"], [])
        self.assertIsInstance(payload["balance_mean"], float)

    def test_short_chapters_stay_out_of_comparisons(self):
        text = "## Kurz\n\nEr ging. Sie blieb am Fenster. Der Regen fiel.\n\n" + "\n\n".join(
            f"## {number}\n\n{NEUTRAL}" for number in range(2, 5)
        )
        report = showing_report(text, DE)
        short = report.chapter_list[0]
        self.assertFalse(short.comparable)
        self.assertIsNone(short.balance)
        self.assertIsNone(short.tell_z)
        self.assertEqual(report.comparable_chapters, 3)
        self.assertNotIn(1, report.most_telling + report.most_showing)
        payload = report.to_dict()
        self.assertIsNone(payload["chapter_list"][0]["balance"])
        self.assertIs(payload["chapter_list"][0]["comparable"], False)

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
