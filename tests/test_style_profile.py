"""
tests/test_style_profile.py
===========================
Tests für die sprachneutrale Analyse-Schicht:
Zeilenanker im Markdown-Parser, Sprachprofile (de/en/generic), absatzgenaue
Tempusprofile mit Wechsel-/Misch-Erkennung sowie die idempotente HTML-UI.
"""

import os
import sys
import tempfile
import unittest

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.analyzer import CorpusAnalyzer  # noqa: E402
from lixity.io import FileUtils  # noqa: E402
from lixity.language import (  # noqa: E402
    LANGUAGE_PROFILES,
    detect_language,
    get_language_profile,
    resolve_language,
)
from lixity.markdown_parser import parse_markdown_blocks  # noqa: E402
from lixity.models import CorpusConfig  # noqa: E402
from lixity.style_profile import (  # noqa: E402
    TENSE_MIXED,
    TENSE_PAST,
    TENSE_PRESENT,
    ParagraphProfiler,
)
from lixity.visualizer import render_style_report  # noqa: E402


class TestParserLineAnchors(unittest.TestCase):
    """Zeilenanker: jeder Block trägt start_line/end_line (1-basiert)."""

    def test_every_block_has_line_anchors(self):
        md = "# Titel\n\nEin Absatz.\n\n> Zitat.\n\n## Kapitel\n\nNoch ein Absatz.\n"
        blocks = parse_markdown_blocks(md)
        for block in blocks:
            self.assertIn("start_line", block)
            self.assertIn("end_line", block)
            self.assertGreaterEqual(block["start_line"], 1)
            self.assertGreaterEqual(block["end_line"], block["start_line"])

    def test_anchor_positions(self):
        md = "# Titel\n\nEin Absatz.\n\n## Kapitel\n\nNoch ein Absatz.\n"
        blocks = parse_markdown_blocks(md)
        by_type = {}
        for block in blocks:
            by_type.setdefault(block["type"], block)
        self.assertEqual(by_type["h1"]["start_line"], 1)
        self.assertEqual(by_type["p"]["start_line"], 3)
        self.assertEqual(by_type["h2"]["start_line"], 5)
        self.assertEqual(blocks[-1]["start_line"], 7)

    def test_multiline_paragraph_anchor(self):
        md = "Erste Zeile\nzweite Zeile\n\nNächster Absatz.\n"
        blocks = parse_markdown_blocks(md)
        self.assertEqual(blocks[0]["start_line"], 1)
        self.assertEqual(blocks[0]["end_line"], 2)
        self.assertEqual(blocks[1]["start_line"], 4)


class TestLanguageProfiles(unittest.TestCase):
    """Sprachprofile: de/en/generic, Overrides, Fallback."""

    def test_german_profile_detects_markers(self):
        lang = resolve_language(CorpusConfig(language="de"))
        self.assertEqual(lang.key, "de")
        self.assertIn("Präsens", lang.labels["present"])
        import re

        self.assertTrue(re.search(lang.praesens_regex, "Ich trinke", re.IGNORECASE))
        self.assertTrue(re.search(lang.praeteritum_regex, "Ich trank", re.IGNORECASE))

    def test_english_profile_detects_markers(self):
        lang = resolve_language(CorpusConfig(language="en"))
        self.assertEqual(lang.key, "en")
        self.assertEqual(lang.labels["present"], "Present")
        import re

        self.assertTrue(re.search(lang.praesens_regex, "I drink", re.IGNORECASE))
        self.assertTrue(re.search(lang.praeteritum_regex, "I drank", re.IGNORECASE))

    def test_unknown_language_falls_back_to_generic(self):
        lang = resolve_language(CorpusConfig(language="xx"))
        self.assertEqual(lang.key, "generic")
        self.assertEqual(lang.praesens_regex, "")
        self.assertEqual(lang.praeteritum_regex, "")

    def test_config_overrides_win(self):
        config = CorpusConfig(
            language="de", praesens_regex=r"\bFOO\b", signal_keywords={"Custom": r"\bBAR\b"}
        )
        lang = resolve_language(config)
        self.assertEqual(lang.praesens_regex, r"\bFOO\b")
        self.assertEqual(dict(lang.signal_keywords), {"Custom": r"\bBAR\b"})

    def test_profiles_registry_is_extensible(self):
        self.assertIn("de", LANGUAGE_PROFILES)
        self.assertIn("en", LANGUAGE_PROFILES)
        self.assertIs(get_language_profile("DE"), LANGUAGE_PROFILES["de"])


class TestParagraphProfiler(unittest.TestCase):
    """Absatzgenaue Tempusprofile inkl. Wechsel- und Misch-Erkennung."""

    def _profile(self, md):
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+", appendix_marker="## Anhang")
        return ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))

    def test_present_and_past_paragraphs(self):
        md = (
            "## Kapitel 1\n\n"
            "Ich trinke Kaffee. Ich gehe zum Fenster. Ich sehe den Regen.\n\n"
            "Ich trank Kaffee. Ich ging zum Fenster. Ich sah den Regen.\n"
        )
        paragraphs, chapters = self._profile(md)
        self.assertEqual(len(paragraphs), 2)
        self.assertEqual(paragraphs[0].dominant, TENSE_PRESENT)
        self.assertEqual(paragraphs[1].dominant, TENSE_PAST)
        self.assertTrue(paragraphs[1].switch)
        self.assertEqual(chapters[0].dominant, TENSE_MIXED)

    def test_mixed_paragraph_detection(self):
        md = (
            "## Kapitel 1\n\n"
            "Ich trinke Kaffee und ich ging zum Fenster. Ich sehe den Regen und ich sah die Straße. "
            "Ich trinke noch einen Schluck.\n"
        )
        paragraphs, _ = self._profile(md)
        self.assertTrue(paragraphs[0].mixed)
        self.assertGreaterEqual(paragraphs[0].severity, 1)

    def test_line_anchors_and_appendix_cutoff(self):
        md = "## Kapitel 1\n\nIch trinke Kaffee.\n\n## Anhang\n\nIch trinke auch hier.\n"
        paragraphs, chapters = self._profile(md)
        self.assertEqual(len(paragraphs), 1)
        self.assertEqual(paragraphs[0].start_line, 3)
        self.assertEqual(paragraphs[0].chapter_num, 1)
        self.assertEqual(len(chapters), 1)

    def test_neutral_without_markers(self):
        md = "## Kapitel 1\n\nDer Kater, die Kartons, der Regen.\n"
        paragraphs, _ = self._profile(md)
        self.assertEqual(paragraphs[0].dominant, "Neutral")
        self.assertFalse(paragraphs[0].mixed)
        self.assertEqual(paragraphs[0].severity, 0)

    def test_generic_language_degrades_gracefully(self):
        md = "## Kapitel 1\n\nIch trinke Kaffee. Ich ging zum Fenster.\n"
        config = CorpusConfig(language="generic", chapter_regex=r"(?m)^##\s+")
        paragraphs, _ = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))
        self.assertEqual(paragraphs[0].dominant, "Neutral")
        self.assertEqual(paragraphs[0].present_hits, 0)
        self.assertEqual(paragraphs[0].past_hits, 0)
        self.assertGreater(paragraphs[0].words, 0)


class TestVisualizer(unittest.TestCase):
    """HTML-UI: deterministisch, eigenständig, mit Zeilenankern."""

    def _render(self):
        md = (
            "## Einleitung\n\n"
            "Ich trinke Kaffee. Ich gehe zum Fenster.\n\n"
            "Ich trank Kaffee und ich ging zum Fenster. Ich sah den Regen.\n"
        )
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        profiler = ParagraphProfiler(config)
        paragraphs, chapters = profiler.profile_blocks(parse_markdown_blocks(md))
        return render_style_report(chapters, paragraphs, title="Testroman")

    def test_html_contains_structure_and_anchors(self):
        html = self._render()
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Testroman", html)
        self.assertIn("Einleitung", html)
        self.assertIn("Z. 3", html)
        self.assertIn("data-target=", html)
        self.assertIn("<style>", html)
        self.assertNotIn("http://", html)
        self.assertNotIn("https://", html)

    def test_html_is_deterministic(self):
        self.assertEqual(self._render(), self._render())

    def test_html_escapes_manuscript_text(self):
        md = "## Kapitel\n\nEin <b>Test</b> & mehr.\n"
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))
        html = render_style_report(chapters, paragraphs, title="X")
        self.assertIn("&lt;b&gt;Test&lt;/b&gt; &amp; mehr", html)
        self.assertNotIn("<b>Test</b>", html)

    def test_labels_are_overridable(self):
        md = "## Chapter One\n\nI drink coffee. I drink tea.\n"
        config = CorpusConfig(language="en", chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))
        html = render_style_report(
            chapters, paragraphs, title="My Novel", labels={"app_suffix": "Custom Suffix"}
        )
        self.assertIn("Custom Suffix", html)
        self.assertIn("Chapter One", html)


class TestVisualizeAdapterIdempotency(unittest.TestCase):
    """Adapter-Schreibvorgang ist atomar und idempotent (kein Diff-Jitter)."""

    def test_atomic_write_if_changed_is_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "analyse.html")
            content = "<!DOCTYPE html><html><body>Test</body></html>\n"
            self.assertTrue(FileUtils.atomic_write_if_changed(path, content))
            self.assertFalse(FileUtils.atomic_write_if_changed(path, content))
            with open(path, "r", encoding="utf-8") as f:
                self.assertEqual(f.read(), content)


class TestLexiconAndDetection(unittest.TestCase):
    """Linguistische Standardlisten (LEXICON) und Spracherkennung."""

    def test_lexicon_categories_per_language(self):
        for key in ("de", "en", "fr", "es", "it", "pt", "nl"):
            profile = get_language_profile(key)
            for category in ("auxiliaries", "modals", "articles", "pronouns", "prepositions", "conjunctions"):
                with self.subTest(lang=key, category=category):
                    self.assertTrue(profile.lexicon.get(category), f"{key}:{category} fehlt")
            self.assertTrue(profile.function_words, f"{key}: Funktionswörter fehlen")
            self.assertTrue(profile.stopwords, f"{key}: Stopwörter fehlen")

    def test_detection_for_all_profiles(self):
        samples = {
            "de": "Ich trinke Kaffee und ich ging zum Fenster. Der Kater war endlich weg.",
            "en": "I drink coffee and I went to the window. The hangover was finally gone.",
            "fr": "Je bois du café et je suis allé à la fenêtre. La gueule de bois était partie.",
            "es": "Bebo café y fui a la ventana. La resaca por fin se había ido.",
            "it": "Bevo un caffè e sono andato alla finestra. La sbornia era finalmente passata.",
            "pt": "Bebo café e fui à janela. A ressaca finalmente tinha passado.",
            "nl": "Ik drink koffie en ik ging naar het raam. De kater was eindelijk weg.",
        }
        for expected, text in samples.items():
            with self.subTest(lang=expected):
                self.assertEqual(detect_language(text), expected)

    def test_detection_short_text_is_ambiguous(self):
        self.assertEqual(detect_language("Hallo"), "generic")
        self.assertEqual(detect_language(""), "generic")

    def test_auto_resolution_uses_sample_text(self):
        config = CorpusConfig(language="auto")
        self.assertEqual(resolve_language(config).key, "generic")
        self.assertEqual(
            resolve_language(config, sample_text="Der Kater war endlich weg und ich trinke Kaffee.").key,
            "de",
        )

    def test_function_word_share_is_measurable(self):
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        md = (
            "## Kapitel\n\n"
            "Der Kater war endlich weg und ich trinke Kaffee mit dem Nachbarn an der Theke.\n\n"
            "Kater, Theke, Kaffee, Nachbar, Regen, Fenster, Asphalt, Neonlicht.\n"
        )
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))
        self.assertGreater(paragraphs[0].function_word_pct, paragraphs[1].function_word_pct)
        self.assertGreater(chapters[0].function_word_pct, 0.0)

    def test_all_language_labels_are_localized(self):
        for key, expected_present in (
            ("de", "Präsens"),
            ("en", "Present"),
            ("fr", "Présent"),
            ("es", "Presente"),
            ("it", "Presente"),
            ("pt", "Presente"),
            ("nl", "Tegenwoordige tijd"),
        ):
            with self.subTest(lang=key):
                self.assertEqual(get_language_profile(key).labels["present"], expected_present)
                self.assertIn("artifacts", get_language_profile(key).labels)


class TestDashboard(unittest.TestCase):
    """Dashboard: Kennzahlen, Artefakte, Lokalisierung, Determinismus."""

    def _build(self, labels=None, artifacts=None):
        md = (
            "## Einleitung\n\n"
            "Ich trinke Kaffee. Ich gehe zum Fenster. Der Regen fällt.\n\n"
            "Ich trank Kaffee und ich ging zum Fenster. Ich sah den Regen.\n"
        )
        config = CorpusConfig(chapter_regex=r"(?m)^##\s+")
        paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(md))
        metrics = CorpusAnalyzer(config).analyze_text(md)
        return render_style_report(
            chapters,
            paragraphs,
            metrics=metrics,
            artifacts=artifacts,
            title="Testroman",
            labels=labels,
        )

    def test_dashboard_contains_metrics_and_map(self):
        html = self._build()
        for needle in ("ASL", "TTR", "Yule", "Flesch", "LIX", 'class="kpi"', 'class="chip'):
            self.assertIn(needle, html)

    def test_dashboard_artifacts_and_links(self):
        artifacts = [
            {"name": "Buch.pdf", "size_kb": 1234.0, "pages": 184, "href": "Buch.pdf"},
            {"name": "NDA_lvp.pdf", "size_kb": 75.0, "pages": 1, "href": "NDA_lvp.pdf"},
        ]
        html = self._build(artifacts=artifacts)
        self.assertIn("Buch.pdf", html)
        self.assertIn("184 pages", html)
        self.assertIn('href="NDA_lvp.pdf"', html)
        self.assertIn("Open</a>", html)

    def test_dashboard_localization_french(self):
        labels = get_language_profile("fr").labels
        artifacts = [{"name": "Livre.pdf", "size_kb": 100.0, "pages": 12, "href": "Livre.pdf"}]
        html = self._build(labels=labels, artifacts=artifacts)
        self.assertIn("Présent", html)
        self.assertIn("Passé", html)
        self.assertIn("Publications", html)
        self.assertIn("Ouvrir", html)
        self.assertIn("12 pages", html)

    def test_dashboard_is_deterministic(self):
        self.assertEqual(self._build(), self._build())

    def test_dashboard_has_no_unresolved_help_keys(self):
        html = self._build(labels=get_language_profile("de").labels)
        self.assertNotIn('data-help="help_', html, "unaufgelöster Tooltip-Schlüssel")
        self.assertIn('data-help="', html)


class TestEngineLicense(unittest.TestCase):
    """Extraktionsvorbereitung: restriktive Engine-Lizenz (Lixity, LNCL-1.0)."""

    def test_license_file_exists_and_is_restrictive(self):
        path = os.path.join(BASE_DIR, "LICENSE")
        self.assertTrue(os.path.isfile(path), "LICENSE-ENGINE fehlt")
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn("Lixity Non-Commercial License", text)
        self.assertIn("kommerzielle Nutzung", text)
        self.assertIn("mfahsold@googlemail.com", text)
        self.assertIn("Forschung", text)

    def test_pyproject_declares_lixity_and_noncommercial_license(self):
        path = os.path.join(BASE_DIR, "pyproject.toml")
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        self.assertIn('name = "lixity"', text)
        self.assertIn("Non-Commercial", text)


if __name__ == "__main__":
    unittest.main()
