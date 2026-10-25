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
from lixity.sentences import split_sentence_spans, split_sentences  # noqa: E402


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

    def test_german_single_quote_direction_and_original_sentence_spans(self):
        cases = (
            ("Er fragte: \u201aKommst du?\u2018 Sie schwieg. Dann ging sie.",
             ["Er fragte: \u201aKommst du?\u2018", "Sie schwieg.", "Dann ging sie."]),
            ("Sie sagte: \u201aKomm.\u2018 Er ging.", ["Sie sagte: \u201aKomm.\u2018", "Er ging."]),
            ("Sie rief: \u201aKomm!\u2018 Er ging.", ["Sie rief: \u201aKomm!\u2018", "Er ging."]),
            ("Sie fragte: \u201aKommst du? \u2018 Er ging.", ["Sie fragte: \u201aKommst du? \u2018", "Er ging."]),
            ("Er sagte. \u2018Komm.’ Sie ging.", ["Er sagte.", "\u2018Komm.’", "Sie ging."]),
            ("„Sie sagte: \u201aKomm.\u2018“ Er ging.", ["„Sie sagte: \u201aKomm.\u2018“", "Er ging."]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(split_sentences(text, "de"), expected)
                self.assertEqual([text[a:b] for a, b in split_sentence_spans(text, "de")], expected)

    def test_german_single_quotes_reach_corpus_paragraph_and_literal_evidence(self):
        from lixity.pipeline import analyze_document
        from lixity.style_fingerprint import FingerprintThresholds

        text = "Er fragte: \u201aKommst du?\u2018 Sie schwieg. Dann ging sie."
        result = analyze_document("## Example\n\n" + text, CorpusConfig(language="de"),
                                  FingerprintThresholds(), include_evidence=True)
        self.assertEqual((result.metrics.tokens, result.metrics.total_sentences, result.metrics.asl), (9, 3, 3.0))
        self.assertEqual((result.paragraphs[0].sentences, result.paragraphs[0].asl), (3, 3.0))
        spans = result.evidence[0]["layers"]["asl"]["spans"]
        self.assertEqual([text[s["start"]:s["end"]] for s in spans],
                         ["Er fragte: \u201aKommst du?\u2018", "Sie schwieg.", "Dann ging sie."])

    def test_spaced_matching_closers_stay_with_their_sentence_and_exact_spans(self):
        cases = (
            ("« Bonjour. » Il partit.", ["« Bonjour. »", "Il partit."]),
            ("« Bonjour.\u00a0» Il partit.", ["« Bonjour.\u00a0»", "Il partit."]),
            ("„ Hallo. ” Hij vertrok.", ["„ Hallo. ”", "Hij vertrok."]),
            ("“ Hello. ” She left.", ["“ Hello. ”", "She left."]),
            ("« \u2018Hello.’ » She left.", ["« \u2018Hello.’ »", "She left."]),
            ("\u2018It’s ready. ’ She left.", ["\u2018It’s ready. ’", "She left."]),
            ("\u2018cafe\u0301’s ready. ’ She left.", ["\u2018cafe\u0301’s ready. ’", "She left."]),
            ("« (Ready! ) » She left.", ["« (Ready! ) »", "She left."]),
            ("« (Ready!) » She left.", ["« (Ready!) »", "She left."]),
            ("(Ready. ) She left.", ["(Ready. )", "She left."]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(split_sentences(text), expected)
                self.assertEqual([text[start:end] for start, end in split_sentence_spans(text)], expected)

    def test_spaced_openers_and_closers_across_blank_blocks_are_not_consumed(self):
        cases = (
            ("Elle partit. « Bonjour. »", ["Elle partit.", "« Bonjour. »"]),
            ("She left. “Next.”", ["She left.", "“Next.”"]),
            ("She left. »Next.«", ["She left.", "»Next.«"]),
            ("Bonjour. » Il partit.", ["Bonjour.", "» Il partit."]),
            ("« Bonjour.\n\n» Il partit.", ["« Bonjour.", "» Il partit."]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(split_sentences(text), expected)
                self.assertEqual([text[start:end] for start, end in split_sentence_spans(text)], expected)

    def test_word_final_apostrophe_closes_a_quote_but_does_not_open_one(self):
        cases = (
            ("The authors' paper ended. 'Next.' She left.",
             ["The authors' paper ended.", "'Next.'", "She left."]),
            ("The cafe\u0301s' paper ended. 'Next.' She left.",
             ["The cafe\u0301s' paper ended.", "'Next.'", "She left."]),
            ("'Authors' wrote it. 'Next.' She left.",
             ["'Authors' wrote it.", "'Next.'", "She left."]),
            ("'Ready. ' She left.", ["'Ready. '", "She left."]),
        )
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(split_sentences(text, "en"), expected)
                self.assertEqual([text[start:end] for start, end in split_sentence_spans(text, "en")], expected)

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


def test_utterance_abbreviations_no_longer_merge_sentences():
    assert split_sentences("He said no. She left.", "en") == ["He said no.", "She left."]
    assert split_sentences("He answered. She said co.", "en") == ["He answered.", "She said co."]


def test_spanish_honorific_d_abbreviation_protects_initials():
    assert split_sentences("Vino don d. Gómez. Luego salió.", "es") == [
        "Vino don d. Gómez.",
        "Luego salió.",
    ]

def test_prose_splitting_keeps_blocks_apart():
    from lixity.sentences import split_prose_sentences

    assert split_prose_sentences(
        "[Kinderzeichnung eines Weihnachtsmanns]\n\nLieber Weihnachtsmann,\n"
        "ich wünsche mir ein buntes Haus.",
        "de",
    ) == [
        "[Kinderzeichnung eines Weihnachtsmanns]",
        "Lieber Weihnachtsmann,\nich wünsche mir ein buntes Haus.",
    ]
    assert split_prose_sentences("Er ging.\n\nENDE", "de") == ["Er ging.", "ENDE"]
    assert split_prose_sentences("Hallo Welt,\nwie geht es dir.", "de") == [
        "Hallo Welt,\nwie geht es dir."
    ]


def test_analyzer_and_profile_count_letter_blocks_the_same():
    from lixity.markdown_parser import parse_markdown_blocks
    from lixity.style_profile import ParagraphProfiler

    md = (
        "## Brief I\n\n*[Kinderzeichnung eines Weihnachtsmanns]*\n\n"
        "Lieber Weihnachtsmann,\nich wünsche mir ein buntes Haus.\n"
    )
    metrics = CorpusAnalyzer(CorpusConfig(language="de")).analyze_text(md)
    paragraphs, chapters = ParagraphProfiler(CorpusConfig(language="de")).profile_blocks(
        parse_markdown_blocks(md)
    )
    assert metrics.chapters[0].sentences == 2
    assert metrics.chapters[0].asl == chapters[0].asl == 5.5
    assert paragraphs[-1].asl == 8.0


if __name__ == "__main__":
    unittest.main()
