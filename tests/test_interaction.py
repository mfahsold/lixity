"""
tests/test_interaction.py
=========================
Dialogue turn structure and character presence: chapter conventions (front
matter, appendix cut), turn statistics, aliases, gaps and determinism.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.characters import character_presence, presence_report  # noqa: E402
from lixity.dialogue import dialogue_report, split_chapters  # noqa: E402
from lixity.models import CorpusConfig  # noqa: E402

DE = CorpusConfig(language="de")

MANUSCRIPT = """# Titel

*Autor*

## Erstes Kapitel

Er ging zum Fenster. »Komm her!«, sagte sie. Er blieb stehen.

»Warum?«

»Weil es regnet.« Draußen fiel Regen auf die Straße.

## Zweites Kapitel

Anna kam später. »Wo warst du?«, fragte sie. Er zuckte mit den Schultern.

## Anmerkungen und Literaturverzeichnis

Anna und Matthias erscheinen hier nur im Anhang.
"""


class TestChapterConventions(unittest.TestCase):
    def test_front_matter_and_appendix_are_not_chapters(self):
        chapters = split_chapters(MANUSCRIPT, DE)
        self.assertEqual(
            [title for _n, title, _b in chapters], ["Erstes Kapitel", "Zweites Kapitel"]
        )

    def test_heading_without_content_is_not_a_chapter(self):
        text = "## Eins\n\nText.\n\n## Leer\n\n## Zwei\n\nMehr Text.\n"
        chapters = split_chapters(text, DE)
        self.assertEqual([title for _n, title, _b in chapters], ["Eins", "Zwei"])

    def test_chapter_numbers_are_sequential(self):
        chapters = split_chapters(MANUSCRIPT, DE)
        self.assertEqual([num for num, _t, _b in chapters], [1, 2])


class TestDialogueReport(unittest.TestCase):
    def test_turn_statistics(self):
        report = dialogue_report(MANUSCRIPT, DE)
        self.assertEqual(report.language, "de")
        self.assertEqual(report.turns, 4)
        # Turn words: "Komm her!" (2) + "Warum?" (1) + "Weil es regnet." (3) + "Wo warst du?" (3)
        self.assertEqual(report.dialogue_words, 9)
        self.assertAlmostEqual(report.avg_turn_words, 9 / 4, places=6)
        self.assertEqual(report.longest_turn_words, 3)

    def test_dialogue_paragraph_share(self):
        report = dialogue_report(MANUSCRIPT, DE)
        # Two pure dialogue paragraphs of five prose paragraphs
        self.assertGreater(report.dialogue_paragraph_pct, 0.0)
        self.assertLessEqual(report.dialogue_paragraph_pct, 100.0)

    def test_appendix_is_excluded(self):
        report = dialogue_report(MANUSCRIPT, DE)
        self.assertEqual(len(report.chapters), 2)
        self.assertEqual(report.chapters[-1].chapter_num, 2)

    def test_deterministic(self):
        first = dialogue_report(MANUSCRIPT, DE).to_dict()
        second = dialogue_report(MANUSCRIPT, DE).to_dict()
        self.assertEqual(first, second)

    def test_empty_text(self):
        report = dialogue_report("", DE)
        self.assertEqual(report.turns, 0)
        self.assertEqual(report.dialogue_pct, 0.0)
        self.assertEqual(report.chapters, [])

    def test_english_dialogue_pattern(self):
        text = '## Chapter 1\n\nHe said, "Come here!" and she left.\n'
        report = dialogue_report(text, CorpusConfig(language="en"))
        self.assertEqual(report.turns, 1)
        self.assertEqual(report.dialogue_words, 2)


class TestCharacterPresence(unittest.TestCase):
    def test_mentions_and_chapters(self):
        figures = character_presence(MANUSCRIPT, ["Anna", "Matthias"], DE)
        by_name = {figure.name: figure for figure in figures}
        self.assertEqual(by_name["Anna"].mentions, 1)
        self.assertEqual(by_name["Anna"].chapters_present, [2])
        self.assertEqual(by_name["Matthias"].mentions, 0)
        self.assertIsNone(by_name["Matthias"].first_chapter)

    def test_appendix_mentions_do_not_count(self):
        report = presence_report(MANUSCRIPT, ["Anna", "Matthias"], DE)
        anna = next(f for f in report["figures"] if f["name"] == "Anna")
        self.assertEqual(anna["mentions"], 1)
        self.assertEqual(report["chapters"], 2)

    def test_aliases_map_to_one_figure(self):
        figures = character_presence(MANUSCRIPT, {"Anna|Anni": "Anna"}, DE)
        self.assertEqual(figures[0].name, "Anna")

    def test_longest_gap(self):
        text = (
            "## Eins\n\nAnna ging.\n\n## Zwei\n\nNiemand da.\n\n## Drei\n\nNiemand da.\n\n"
            "## Vier\n\nAnna kam wieder.\n"
        )
        figure = character_presence(text, ["Anna"], DE)[0]
        self.assertEqual(figure.chapters_present, [1, 4])
        self.assertEqual(figure.longest_gap, 2)

    def test_sorted_by_mentions(self):
        figures = character_presence(MANUSCRIPT, ["Matthias", "Anna"], DE)
        self.assertEqual([f.name for f in figures], ["Anna", "Matthias"])

    def test_presence_ratio(self):
        report = presence_report(MANUSCRIPT, ["Anna"], DE)
        self.assertAlmostEqual(report["figures"][0]["presence_ratio"], 0.5, places=6)

    def test_word_boundaries(self):
        figures = character_presence("## Eins\n\nAnna und Annabelle gingen.\n", ["Anna"], DE)
        self.assertEqual(figures[0].mentions, 1)


if __name__ == "__main__":
    unittest.main()
