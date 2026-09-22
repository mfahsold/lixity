"""
tests/test_sentences.py
=======================
Sentence segmentation: abbreviation, number and initial guards, closing
marks, and the integration into corpus metrics and paragraph profiling.
"""

import os
import sys
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.analyzer import CorpusAnalyzer  # noqa: E402
from lixity.models import CorpusConfig  # noqa: E402
from lixity.sentences import split_sentences  # noqa: E402


class TestSentenceSplitter(unittest.TestCase):
    def test_plain_sentences(self):
        self.assertEqual(split_sentences("Er ging. Sie blieb.", "de"), ["Er ging.", "Sie blieb."])

    def test_german_abbreviations(self):
        parts = split_sentences("z.B. das Haus war alt. Er ging.", "de")
        self.assertEqual(len(parts), 2)
        parts = split_sentences("Dr. Müller kam. Es war still.", "de")
        self.assertEqual(len(parts), 2)

    def test_english_abbreviations(self):
        parts = split_sentences("Mr. Bennet ging zum Fenster. Er sah Mrs. Bennet.", "en")
        self.assertEqual(len(parts), 2)

    def test_numbers_are_not_split(self):
        parts = split_sentences("Er zahlte 1.000,50 Euro. Dann ging er.", "de")
        self.assertEqual(len(parts), 2)
        parts = split_sentences("It cost 3.14 dollars. He left.", "en")
        self.assertEqual(len(parts), 2)

    def test_initials_are_not_split(self):
        parts = split_sentences("J. R. R. Tolkien schrieb. Der Ring war mächtig.", "de")
        self.assertEqual(len(parts), 2)

    def test_closing_marks_stay_with_their_sentence(self):
        self.assertEqual(split_sentences("»Komm!« Er ging.", "de"), ["»Komm!«", "Er ging."])

    def test_ellipsis_without_space_does_not_split(self):
        self.assertEqual(len(split_sentences("Das war alles … dann kam sie.", "de")), 1)

    def test_language_fallback_uses_universal_abbreviations(self):
        parts = split_sentences("Mr. Smith arrived. He left.", "generic")
        self.assertEqual(len(parts), 2)

    def test_empty_and_whitespace(self):
        self.assertEqual(split_sentences("", "de"), [])
        self.assertEqual(split_sentences("   \n\n  ", "de"), [])

    def test_deterministic(self):
        text = "Dr. Meyer ging. Er kam um 8.30 Uhr. Mrs. Meyer blieb."
        self.assertEqual(split_sentences(text, "de"), split_sentences(text, "de"))


class TestSentenceMetricsIntegration(unittest.TestCase):
    def test_analyzer_counts_abbreviations_as_one_sentence(self):
        md = "## Kapitel\n\nMr. Bennet ging zum Fenster. Er sah Mrs. Bennet.\n"
        metrics = CorpusAnalyzer(CorpusConfig(language="en")).analyze_text(md)
        self.assertEqual(metrics.total_sentences, 2)

    def test_profile_uses_the_shared_splitter(self):
        from lixity.markdown_parser import parse_markdown_blocks
        from lixity.style_profile import ParagraphProfiler

        md = "## Kapitel\n\nMr. Bennet ging zum Fenster. Er sah Mrs. Bennet.\n"
        paragraphs, _ = ParagraphProfiler(CorpusConfig(language="en")).profile_blocks(
            parse_markdown_blocks(md)
        )
        self.assertEqual(paragraphs[0].sentences, 2)


if __name__ == "__main__":
    unittest.main()
