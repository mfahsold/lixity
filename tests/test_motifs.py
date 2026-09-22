"""
tests/test_motifs.py
====================
Motif tracking (presence, density, gaps) and generic repetition analysis
(content words, repeated n-grams) — deterministic and configuration-driven.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.models import CorpusConfig  # noqa: E402
from lixity.motifs import motif_report  # noqa: E402

DE = CorpusConfig(language="de")

TEXT = """## Eins

Der Regen fiel auf die Straße. Der Regen war laut.

## Zwei

Niemand sprach ein Wort.

## Drei

Wieder Regen. Der Regen kam zurück.
"""


class TestMotifs(unittest.TestCase):
    def test_motif_counts_and_gaps(self):
        report = motif_report(TEXT, {"Regen": r"\bRegen\b"}, DE)
        motif = report.motifs[0]
        self.assertEqual(motif.name, "Regen")
        self.assertEqual(motif.mentions, 4)
        self.assertEqual(motif.chapters_present, [1, 3])
        self.assertEqual(motif.first_chapter, 1)
        self.assertEqual(motif.last_chapter, 3)
        self.assertEqual(motif.longest_gap, 1)

    def test_density_per_1000(self):
        report = motif_report(TEXT, {"Regen": r"\bRegen\b"}, DE)
        motif = report.motifs[0]
        self.assertGreater(motif.density_per_1000, 0.0)
        self.assertLessEqual(motif.density_per_1000, 1000.0)

    def test_motifs_sorted_by_mentions(self):
        report = motif_report(TEXT, {"Regen": r"\bRegen\b", "Wort": r"\bWort\b"}, DE)
        self.assertEqual([m.name for m in report.motifs], ["Regen", "Wort"])

    def test_absent_motif(self):
        report = motif_report(TEXT, {"Schnee": r"\bSchnee\b"}, DE)
        motif = report.motifs[0]
        self.assertEqual(motif.mentions, 0)
        self.assertIsNone(motif.first_chapter)
        self.assertEqual(motif.chapters_present, [])


class TestRepetition(unittest.TestCase):
    def test_repeated_phrases(self):
        text = (
            "## Eins\n\nDer alte Mann ging. Der alte Mann blieb.\n\n"
            "## Zwei\n\nDer alte Mann kam zurück.\n"
        )
        report = motif_report(text, None, DE, phrase_size=3)
        phrases = {phrase.phrase: phrase for phrase in report.repeated_phrases}
        self.assertIn("der alte mann", phrases)
        self.assertEqual(phrases["der alte mann"].count, 3)
        self.assertEqual(phrases["der alte mann"].chapters, [1, 2])

    def test_function_words_are_excluded(self):
        text = "## Eins\n\nund der die das und der die das und der die das\n"
        report = motif_report(text, None, DE, phrase_size=3)
        self.assertEqual(report.repeated_phrases, [])

    def test_top_words_are_content_words(self):
        text = "## Eins\n\nDer Regen fiel. Der Regen blieb. Der Regen ging. Der Regen war da.\n"
        report = motif_report(text, None, DE)
        words = dict(report.top_words)
        self.assertIn("regen", words)
        self.assertNotIn("der", words)

    def test_phrase_minimum_count(self):
        text = "## Eins\n\nEin seltener Satz steht hier.\n"
        report = motif_report(text, None, DE)
        self.assertEqual(report.repeated_phrases, [])

    def test_deterministic(self):
        first = motif_report(TEXT, {"Regen": r"\bRegen\b"}, DE).to_dict()
        second = motif_report(TEXT, {"Regen": r"\bRegen\b"}, DE).to_dict()
        self.assertEqual(first, second)

    def test_empty_text(self):
        report = motif_report("", {"Regen": r"\bRegen\b"}, DE)
        self.assertEqual(report.chapters, 0)
        self.assertEqual(report.motifs[0].mentions, 0)
        self.assertEqual(report.top_words, [])


if __name__ == "__main__":
    unittest.main()
