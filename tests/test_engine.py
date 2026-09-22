"""
tests/test_engine.py
====================
Umfassende Unit-Tests für die generische Korpusanalyse-Engine (scripts.engine).
Testet Silbenzählung, Satzklassifikation, Lexikometrie, Lesbarkeitsindizes,
idempotente atomare Datei-I/O und Formatierer.
"""

import os
import sys
import tempfile
import unittest

# Sicherstellen, dass das Projektverzeichnis im Modulpfad liegt
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity import (  # noqa: E402
    CorpusConfig,
    CorpusAnalyzer,
    FileUtils,
    ReportFormatter,
)


class TestSyllableCounter(unittest.TestCase):
    """Prüft die Heuristik zur Silbenzählung."""

    def setUp(self):
        self.analyzer = CorpusAnalyzer()

    def test_single_syllables(self):
        words = ["ich", "du", "wir", "gut", "rot", "wut", "haus", "wein", "zeit"]
        for w in words:
            self.assertEqual(
                self.analyzer.count_syllables_de(w), 1,
                f"Wort '{w}' sollte 1 Silbe haben"
            )

    def test_diphthongs(self):
        # Diphthonge wie ei, au, eu, äu, ie sollen als 1 Vokal gezählt werden
        diphthong_words = [
            ("meine", 2),
            ("heute", 2),
            ("bäume", 2),
            ("wieder", 2),
            ("kaiser", 2),
        ]
        for w, expected in diphthong_words:
            self.assertEqual(
                self.analyzer.count_syllables_de(w), expected,
                f"Wort '{w}' sollte {expected} Silben haben"
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
                self.analyzer.count_syllables_de(w), expected,
                f"Wort '{w}' sollte {expected} Silben haben"
            )


class TestCorpusAnalyzer(unittest.TestCase):
    """Prüft die linguistischen Berechnungen auf Testtexten."""

    def setUp(self):
        self.config = CorpusConfig(
            chapter_regex=r"(?m)^##\s+",
            appendix_marker="## Anhang",
        )
        self.analyzer = CorpusAnalyzer(self.config)

    def test_sentence_distribution_and_asl(self):
        # 4 Sätze unterschiedlicher Längen:
        # 1. "Ich gehe." (2 Wörter -> kurz)
        # 2. "Heute scheint die Sonne über Hamburg sehr schön." (8 Wörter -> mittel)
        # 3. "Wenn wir heute Abend gemeinsam kochen, müssen wir unbedingt frischen Koriander und gute Limetten auf dem Isemarkt einkaufen gehen." (18 Wörter -> lang)
        # 4. Sehr langer Satz (> 25 Wörter -> komplex)
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

        # Gesamtsumme der Anteile muss 100% sein
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
        # clean_words sollte nur den Haupttext vor dem Anhang erfassen
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
        # Repetitiver Text hat hohes Yule's K (geringe Diversität)
        repetitive = "## Repetitiv\n\n" + ("Das Haus ist groß. " * 30)
        m_rep = self.analyzer.analyze_text(repetitive)
        self.assertGreater(m_rep.yules_k, 100.0)

        # Diverser Text hat moderates Yule's K
        diverse = (
            "## Divers\n\n"
            "Der alte Kapitän stand am nebligen Kai und beobachtete die einfahrenden Frachtschiffe aus Übersee.\n"
        )
        m_div = self.analyzer.analyze_text(diverse)
        self.assertLess(m_div.yules_k, m_rep.yules_k)

    def test_readability_flesch_and_lix(self):
        # Einfache Sprache -> hoher Flesch-Wert, niedriger LIX
        simple_sample = "## Einfach\n\nIch gehe nach Hause. Du kommst mit. Wir essen Brot.\n"
        m = self.analyzer.analyze_text(simple_sample)
        self.assertGreater(m.flesch_de, 80.0)
        self.assertLess(m.lix, 25.0)


class TestFileUtils(unittest.TestCase):
    """Prüft idempotente, atomare Schreibvorgänge."""

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

        # 1. Erstes Schreiben -> True
        written = FileUtils.atomic_write_if_changed(self.test_file, content_v1)
        self.assertTrue(written)
        self.assertTrue(os.path.exists(self.test_file))
        self.assertEqual(FileUtils.read_file(self.test_file), content_v1)

        # 2. Zweites Schreiben mit identischem Inhalt -> False (idempotent, kein Disk-Jitter)
        written_again = FileUtils.atomic_write_if_changed(self.test_file, content_v1)
        self.assertFalse(written_again)

        # 3. Schreiben mit neuem Inhalt -> True
        updated = FileUtils.atomic_write_if_changed(self.test_file, content_v2)
        self.assertTrue(updated)
        self.assertEqual(FileUtils.read_file(self.test_file), content_v2)


class TestReportFormatter(unittest.TestCase):
    """Prüft Markdown- und JSON-Serialisierung."""

    def setUp(self):
        analyzer = CorpusAnalyzer()
        self.metrics = analyzer.analyze_text(
            "## Kapitel 1\n\n"
            "Ich koche heute Abend. Der Kater ist endlich weg. »Kommst du vorbei?«, fragte Ralf.\n"
        )

    def test_markdown_formatter(self):
        md = ReportFormatter.format_markdown_report(self.metrics)
        self.assertIn("### 1.1 Gesamtkorpus-Kennzahlen", md)
        self.assertIn("### 1.2 Satzlängen-Architektur", md)
        self.assertIn("### 1.3 Interpunktion", md)
        self.assertIn("Mittlere Satzlänge (ASL)", md)

    def test_json_formatter(self):
        json_str = ReportFormatter.to_json(self.metrics)
        self.assertIn('"raw_words":', json_str)
        self.assertIn('"clean_words":', json_str)
        self.assertIn('"asl":', json_str)
        self.assertIn('"ttr":', json_str)


if __name__ == "__main__":
    unittest.main()
