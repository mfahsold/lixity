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
        self.assertEqual(motif.density_per_1000, 200.0)

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

    def test_echo_detector_finds_nearby_repetition(self):
        text = (
            "## Eins\n\nDer Hund lief. Der Hund lief schnell. "
            "Der Hund lief sehr schnell.\n"
        )
        report = motif_report(text, None, DE, echo_window=300)
        terms = [e.term for e in report.echoes]
        self.assertIn("der hund lief", terms)

    def test_echo_detector_empty_for_no_repetition(self):
        text = "## Eins\n\nDer Hund lief. Die Katze sprang. Der Vogel flog.\n"
        report = motif_report(text, None, DE, echo_window=300)
        self.assertEqual(report.echoes, [])

    def test_echoes_keep_independent_phrases_with_shared_words(self):
        text = (
            "## One\n\nred wooden door. appears. red wooden door. closes. "
            "red metal door. opens. red metal door."
        )
        report = motif_report(text, config=CorpusConfig(language="en"))
        self.assertEqual(
            {echo.term for echo in report.echoes},
            {"red wooden door", "red metal door"},
        )

    def test_echo_count_and_locations_describe_only_the_local_window(self):
        text = (
            "## One\n\nsilver lantern shines. blue river flows. silver lantern shines. "
            + "other " * 20 + "silver lantern shines."
        )
        report = motif_report(text, config=CorpusConfig(language="en"), echo_window=12)
        echo = next(echo for echo in report.echoes if echo.term == "silver lantern shines")
        self.assertEqual((echo.count, echo.first_word, echo.last_word), (2, 1, 9))
        strict = motif_report(
            text, config=CorpusConfig(language="en"), echo_window=12, echo_min_count=3,
        )
        self.assertNotIn("silver lantern shines", {echo.term for echo in strict.echoes})

    def test_echo_window_uses_the_densest_cluster(self):
        text = "## One\n\nbright copper bell. " + "other " * 20 + "bright copper bell. " * 3
        report = motif_report(text, config=CorpusConfig(language="en"), echo_window=10)
        echo = next(echo for echo in report.echoes if echo.term == "bright copper bell")
        self.assertEqual((echo.count, echo.first_word, echo.last_word), (3, 24, 32))

    def test_echo_window_contains_the_complete_repeated_phrases(self):
        text = "## One\n\nbright copper bell. blue river flows. bright copper bell."
        report = motif_report(text, config=CorpusConfig(language="en"), echo_window=8)
        self.assertEqual(report.echoes, [])

    def test_echo_dedup_collapses_shifted_ngrams_of_the_same_passage(self):
        text = "## One\n\nthe bright silver lantern. the bright silver lantern."
        report = motif_report(text, config=CorpusConfig(language="en"))
        self.assertEqual(len(report.echoes), 1)
        self.assertEqual(report.echoes[0].term, "the bright silver")

    def test_search_manuscript_handles_punctuated_phrases_unicode_boundaries_and_quotations(self):
        from lixity.motifs import search_manuscript

        text = (
            "## Eins\n\n"
            '🧭 Am Fenster: Es ist so, dass die Straße leer bleibt. '
            '„Es ist so,\ndass die Straßenlaterne brennt“, sagte Mara.\n\n'
            "## Zwei\n\n"
            "Dies ist so, dasselbe gilt für andere.\n"
        )
        cfg = CorpusConfig(language="de")
        res = search_manuscript(text, "es ist so, dass", cfg)
        self.assertEqual(res["schema_version"], "lixity-motif-search/1")
        self.assertEqual(res["offset_unit"], "unicode_codepoint")
        self.assertEqual(res["total_matches"], 2)
        self.assertFalse(res["truncated"])
        occs = res["occurrences"]
        self.assertEqual([o["paragraph_id"] for o in occs], ["p-0", "p-0"])
        self.assertEqual([o["chapter"] for o in occs], [1, 1])
        self.assertEqual([o["start_line"] for o in occs], [3, 3])
        self.assertEqual(occs[0]["quotation_context"], "outside_quotation")
        self.assertEqual(occs[1]["quotation_context"], "in_quotation")
        self.assertEqual(occs[0]["quote"], "Es ist so, dass")
        # Codepoint offset check after astral emoji 🧭 (index 0).
        self.assertEqual(occs[0]["start"], 14)

        street = search_manuscript(text, "Straße", cfg)
        self.assertEqual(street["total_matches"], 1)
        self.assertEqual(street["occurrences"][0]["quote"], "Straße")

    def test_search_manuscript_supports_regex_truncation_and_validation(self):
        from lixity.motifs import search_manuscript

        text = "## One\n\nI feel calm. \"I feel bold.\" I feel ready.\n"
        cfg = CorpusConfig(language="en")
        res = search_manuscript(text, r"\bfeel\s+\w+", cfg, is_regex=True, limit=2)
        self.assertEqual(res["total_matches"], 3)
        self.assertTrue(res["truncated"])
        self.assertEqual(len(res["occurrences"]), 2)
        self.assertEqual(res["occurrences"][0]["quotation_context"], "outside_quotation")
        self.assertEqual(res["occurrences"][1]["quotation_context"], "in_quotation")

        with self.assertRaises(ValueError):
            search_manuscript(text, "   ", cfg)
        with self.assertRaises(ValueError):
            search_manuscript(text, "[unclosed", cfg, is_regex=True)
        with self.assertRaises(ValueError):
            search_manuscript(text, "feel", cfg, limit=0)


if __name__ == "__main__":
    unittest.main()
