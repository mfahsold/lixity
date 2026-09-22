"""
tests/test_engine.py
====================
Comprehensive unit tests for the generic corpus analysis engine.
Covers syllable counting, sentence classification, lexicometry, readability
indices, idempotent atomic file I/O and formatters.
"""

import os
import sys
import tempfile
import unittest

# Ensure the project directory is on the module path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity import (  # noqa: E402
    CorpusAnalyzer,
    CorpusConfig,
    FileUtils,
    ReportFormatter,
)
from lixity.diversity import mtld  # noqa: E402
from lixity.syllables import count_de  # noqa: E402


class TestSyllableCounter(unittest.TestCase):
    """Checks the syllable counting heuristic."""

    def setUp(self):
        self.analyzer = CorpusAnalyzer()

    def test_single_syllables(self):
        words = ["ich", "du", "wir", "gut", "rot", "wut", "haus", "wein", "zeit"]
        for w in words:
            self.assertEqual(count_de(w), 1, f"word '{w}' should have 1 syllable")

    def test_diphthongs(self):
        # Diphthongs such as ei, au, eu, äu, ie should count as 1 vowel
        diphthong_words = [
            ("meine", 2),
            ("heute", 2),
            ("bäume", 2),
            ("wieder", 2),
            ("kaiser", 2),
        ]
        for w, expected in diphthong_words:
            self.assertEqual(
                count_de(w),
                expected,
                f"word '{w}' should have {expected} syllables",
            )

    def test_polysyllabic_words(self):
        cases = [
            ("kater", 2),
            ("eigentlich", 3),
            ("küchenmesser", 4),
            ("hyperästhesie", 5),
        ]
        for w, expected in cases:
            self.assertEqual(
                count_de(w),
                expected,
                f"word '{w}' should have {expected} syllables",
            )


class TestCorpusAnalyzer(unittest.TestCase):
    """Checks the linguistic calculations on test texts."""

    def setUp(self):
        self.config = CorpusConfig(
            chapter_regex=r"(?m)^##\s+",
            appendix_marker="## Anhang",
        )
        self.analyzer = CorpusAnalyzer(self.config)

    def test_sentence_distribution_and_asl(self):
        # 4 sentences of different lengths:
        # 1. "Ich gehe." (2 words -> short)
        # 2. "Heute scheint die Sonne über Hamburg sehr schön." (8 words -> medium)
        # 3. "Wenn wir heute Abend gemeinsam kochen, ..." (18 words -> long)
        # 4. Very long sentence (> 25 words -> complex)
        sample = (
            "## Erstes Kapitel\n\n"
            "Ich gehe.\n\n"
            "Heute scheint die Sonne über Hamburg sehr schön.\n\n"
            "Wenn wir heute Abend gemeinsam kochen, müssen wir unbedingt frischen Koriander und gute Limetten auf dem Isemarkt einkaufen gehen.\n\n"
            "Als ich damals in Altona ankam und die Kisten noch alle unberührt im Flur gestapelt standen, ahnte ich noch nicht im Entferntesten, welche chaotischen Wochen und Nächte mir bevorstehen würden.\n"
        )
        metrics = self.analyzer.analyze_text(sample)

        self.assertEqual(metrics.total_sentences, 4)
        dist = metrics.sentence_dist
        self.assertEqual(dist.short_count, 1)
        self.assertEqual(dist.medium_count, 1)
        self.assertEqual(dist.long_count, 1)
        self.assertEqual(dist.complex_count, 1)

        # The sum of all shares must be 100%
        total_pct = dist.short_pct + dist.medium_pct + dist.long_pct + dist.complex_pct
        self.assertAlmostEqual(total_pct, 100.0, places=1)

    def test_dialogue_extraction(self):
        sample = (
            "## Dialog-Test\n\n"
            "Er sah mich an. »Was gibt es heute zu essen?«, fragte er leise.\n\n"
            "Ich lächelte nur müde. „Pasta mit Salbeibutter und Zitrone.“\n"
        )
        metrics = self.analyzer.analyze_text(sample)
        self.assertGreater(metrics.dialog_words, 0)
        self.assertGreater(metrics.dialog_ratio, 0.0)

    def test_appendix_separation(self):
        sample = (
            "## Kapitel 1\n\n"
            "Das ist die eigentliche Prosa des Romans.\n\n"
            "## Anhang\n\n"
            "Dies ist nur wissenschaftliches Begleitmaterial und gehört nicht zur Romanprosa.\n"
        )
        metrics = self.analyzer.analyze_text(sample)
        # clean_words should only cover the main text before the appendix
        self.assertLess(metrics.clean_words, metrics.raw_words)
        self.assertEqual(len(metrics.chapters), 1)
        self.assertEqual(metrics.chapters[0].title, "Kapitel 1")

    def test_lexical_metrics(self):
        sample = (
            "## Kapitel\n\n"
            "Das Brot schmeckt gut. Der Kaffee schmeckt warm. Das Wasser ist frisch.\n"
        )
        metrics = self.analyzer.analyze_text(sample)
        self.assertGreater(metrics.ttr, 0.0)
        self.assertLessEqual(metrics.ttr, 1.0)
        self.assertGreater(metrics.guiraud_r, 0.0)
        self.assertGreater(metrics.flesch_de, 0.0)
        self.assertGreater(metrics.lix, 0.0)

    def test_yules_k_stability(self):
        # Repetitive text has a high Yule's K (low diversity)
        repetitive = "## Repetitiv\n\n" + ("Das Haus ist groß. " * 30)
        m_rep = self.analyzer.analyze_text(repetitive)
        self.assertGreater(m_rep.yules_k, 100.0)

        # Diverse text has a moderate Yule's K
        diverse = (
            "## Divers\n\n"
            "Der alte Kapitän stand am nebligen Kai und beobachtete die einfahrenden Frachtschiffe aus Übersee.\n"
        )
        m_div = self.analyzer.analyze_text(diverse)
        self.assertLess(m_div.yules_k, m_rep.yules_k)

    def test_readability_flesch_and_lix(self):
        # Simple language -> high Flesch value, low LIX
        simple_sample = "## Einfach\n\nIch gehe nach Hause. Du kommst mit. Wir essen Brot.\n"
        m = self.analyzer.analyze_text(simple_sample)
        self.assertGreater(m.flesch_de, 80.0)
        self.assertLess(m.lix, 25.0)

    def test_lexical_diversity_indices(self):
        # >= 50 tokens so that MTLD, MATTR and Maas a² are computable
        diverse = " ".join(f"Wort{i} klingt anders und trägt eigene Farbe" for i in range(15))
        metrics = self.analyzer.analyze_text(f"## Diversität\n\n{diverse}.\n")
        self.assertTrue(metrics.mtld is not None and metrics.mtld > 0.0)
        self.assertTrue(metrics.mattr is not None and 0.0 < metrics.mattr <= 1.0)
        self.assertTrue(metrics.maas_a2 is not None and metrics.maas_a2 > 0.0)

    def test_lexical_diversity_none_for_short_texts(self):
        metrics = self.analyzer.analyze_text("## Kurz\n\nNur ein kurzer Satz.\n")
        self.assertIsNone(metrics.mtld)
        self.assertIsNone(metrics.mattr)

    def test_mtld_deterministic_and_partial_factor(self):
        # Every factor spans exactly 5 tokens (TTR hits 0.6 on the 5th),
        # so MTLD = 120 / 24 = 5.0 – catches segment-reset regressions.
        self.assertEqual(mtld(["a", "b", "c"] * 40), 5.0)
        # Trailing partial factor: (1 − 0.75) / (1 − 0.72) = 0.8929 factors.
        partial = ["a", "b", "c"] * 40 + ["a", "b", "c", "a"]
        value = mtld(partial)
        self.assertIsNotNone(value)
        if value is None:
            self.fail("MTLD should be computable for the partial-factor sample")
        self.assertAlmostEqual(value, 124 / (24 + (1 - 0.75) / 0.28), places=6)

    def test_readability_is_language_calibrated(self):
        sample = "## Test\n\nDer alte Mann ging langsam über die Straße und sah den Himmel.\n"
        m_de = self.analyzer.analyze_text(sample)
        self.assertEqual(m_de.flesch_variant, "Flesch Reading Ease (Amstad)")
        en_analyzer = CorpusAnalyzer(CorpusConfig(language="en", chapter_regex=r"(?m)^##\s+"))
        m_en = en_analyzer.analyze_text(sample)
        self.assertEqual(m_en.flesch_variant, "Flesch Reading Ease")
        self.assertNotAlmostEqual(m_de.flesch_de, m_en.flesch_de, places=1)


class TestFileUtils(unittest.TestCase):
    """Checks idempotent, atomic write operations."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.temp_dir, "test_output.txt")

    def tearDown(self):
        if os.path.exists(self.test_file):
            os.remove(self.test_file)
        if os.path.exists(self.temp_dir):
            os.rmdir(self.temp_dir)

    def test_atomic_write_if_changed(self):
        content_v1 = "Erste Version des Textes.\n"
        content_v2 = "Zweite Version des Textes.\n"

        # 1. First write -> True
        written = FileUtils.atomic_write_if_changed(self.test_file, content_v1)
        self.assertTrue(written)
        self.assertTrue(os.path.exists(self.test_file))
        self.assertEqual(FileUtils.read_file(self.test_file), content_v1)

        # 2. Second write with identical content -> False (idempotent, no disk jitter)
        written_again = FileUtils.atomic_write_if_changed(self.test_file, content_v1)
        self.assertFalse(written_again)

        # 3. Write with new content -> True
        updated = FileUtils.atomic_write_if_changed(self.test_file, content_v2)
        self.assertTrue(updated)
        self.assertEqual(FileUtils.read_file(self.test_file), content_v2)


class TestReportFormatter(unittest.TestCase):
    """Checks Markdown and JSON serialization."""

    def setUp(self):
        analyzer = CorpusAnalyzer()
        self.metrics = analyzer.analyze_text(
            "## Kapitel 1\n\n"
            "Ich koche heute Abend. Der Kater ist endlich weg. »Kommst du vorbei?«, fragte Ralf.\n"
        )

    def test_markdown_formatter_defaults_to_english(self):
        md = ReportFormatter.format_markdown_report(self.metrics)
        self.assertIn("### 1.1 Corpus metrics", md)
        self.assertIn("### 1.2 Sentence-length architecture", md)
        self.assertIn("Average sentence length (ASL)", md)

    def test_markdown_formatter_german_pack(self):
        md = ReportFormatter.format_markdown_report(self.metrics, language_key="de")
        self.assertIn("### 1.1 Gesamtkorpus-Kennzahlen", md)
        self.assertIn("Mittlere Satzlänge (ASL)", md)

    def test_punctuation_rows_use_their_own_texts(self):
        """Regression: 'colons' must not match inside 'semicolons'."""
        md = ReportFormatter.format_markdown_report(
            self.metrics,
            texts={"punct_Doppelpunkte": "COLON_TEXT", "punct_Semikolons": "SEMI_TEXT"},
            language_key="de",
        )
        semi_row = next(line for line in md.splitlines() if "Semikolons" in line)
        colon_row = next(line for line in md.splitlines() if "Doppelpunkte" in line)
        self.assertIn("SEMI_TEXT", semi_row)
        self.assertNotIn("COLON_TEXT", semi_row)
        self.assertIn("COLON_TEXT", colon_row)

    def test_front_matter_with_leading_comment_is_not_a_chapter(self):
        md = (
            "<!-- Sample: provenance notice -->\n\n"
            "# Book Title\n\n*Author*\n\n"
            "## Kapitel 1\n\nIch trinke Kaffee. Ich gehe zum Fenster.\n"
        )
        metrics = CorpusAnalyzer().analyze_text(md)
        self.assertEqual(len(metrics.chapters), 1)
        self.assertEqual(metrics.chapters[0].title, "Kapitel 1")

    def test_rich_report_reference_columns_are_opt_in(self):
        from io import StringIO

        from rich.console import Console

        default_console = Console(file=StringIO(), width=200)
        ReportFormatter.print_rich_report(self.metrics, console=default_console)
        self.assertNotIn("Reference corridor", default_console.file.getvalue())

        project_console = Console(file=StringIO(), width=200)
        ReportFormatter.print_rich_report(
            self.metrics,
            console=project_console,
            texts={"t1_asl_ref": "8.0 – 11.5", "t1_asl_note": "concise"},
        )
        self.assertIn("Reference corridor", project_console.file.getvalue())

    def test_json_formatter(self):
        json_str = ReportFormatter.to_json(self.metrics)
        self.assertIn('"raw_words":', json_str)
        self.assertIn('"clean_words":', json_str)
        self.assertIn('"asl":', json_str)
        self.assertIn('"ttr":', json_str)


if __name__ == "__main__":
    unittest.main()
