"""Cross-language contracts for defaults, resources and numerical presentation."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from lixity import api, language_data
from lixity.analyzer import CorpusAnalyzer
from lixity.cli import main
from lixity.format import num, pct
from lixity.language import LANGUAGE_PROFILES
from lixity.models import CorpusConfig


class TestLocalization(unittest.TestCase):
    def test_english_defaults_and_explicit_detection(self):
        text = "## Chapter\n\nIch gehe und ich sehe das Haus. Die Tür ist offen.\n"
        self.assertEqual(CorpusConfig().language, "en")
        self.assertEqual(CorpusAnalyzer().lang.key, "en")
        self.assertEqual(api.analyze(text)["meta"]["language"], "en")
        self.assertEqual(api.analyze(text, language="auto")["meta"]["language"], "de")

    def test_all_supported_profiles_have_complete_resource_keys(self):
        for name in ("LABELS", "METRIC_LABELS", "HELP_TEXTS", "GROUP_LABELS", "LAYER_LABELS", "UI_LABELS", "IDENTITY_LABELS"):
            table = getattr(language_data, name)
            for language in ("en", "de", "fr", "es", "it", "pt", "nl"):
                with self.subTest(resource=name, language=language):
                    self.assertFalse(set(table["en"]) - set(table[language]))
                    self.assertTrue(all(table[language][key].strip() for key in table["en"]))

    def test_readability_dispatch_uses_language_specific_coefficients(self):
        expected = {"en": 27.485, "de": 53.0, "fr": 49.65, "es": 72.135,
                    "it": 84.0, "pt": 69.485, "nl": 43.7}
        for language, score in expected.items():
            with self.subTest(language=language):
                analyzer = CorpusAnalyzer(CorpusConfig(language=language))
                actual, variant = analyzer.readability(10.0, 2.0)
                self.assertAlmostEqual(actual, score)
                self.assertEqual(variant, language_data.READABILITY[language]["name"])
                self.assertTrue(LANGUAGE_PROFILES[language].function_words)
                self.assertTrue(LANGUAGE_PROFILES[language].praesens_regex)
                self.assertTrue(LANGUAGE_PROFILES[language].praeteritum_regex)

    def test_percentage_units_and_number_separators(self):
        self.assertEqual(pct(12.5, "en"), "12.5%")
        self.assertEqual(pct(12.5, "generic"), "12.5%")
        for language in ("de", "fr", "es", "it", "pt", "nl"):
            with self.subTest(language=language):
                self.assertEqual(pct(12.5, language), "12,5 %")
        self.assertEqual(num(1234.5, "en"), "1,234.5")
        self.assertEqual(num(1234.5, "fr"), "1\u202f234,5")

    def test_project_identity_is_escaped_versioned_and_localized(self):
        from lixity import __version__
        from lixity.ui.components import project_header

        for language in ("en", "de", "fr", "es", "it", "pt", "nl"):
            with self.subTest(language=language):
                labels = LANGUAGE_PROFILES[language].labels
                rendered = project_header('<img src=x onerror="alert(1)">', labels)
                self.assertIn(__version__, rendered)
                self.assertIn(labels["license_notice"], rendered)
                self.assertIn("&lt;img", rendered)
                self.assertNotIn("<img", rendered)

    def test_cli_language_precedence(self):
        with tempfile.TemporaryDirectory() as directory:
            manuscript = Path(directory) / "sample.md"
            manuscript.write_text("## Chapter\n\nThe door is open.\n", encoding="utf-8")
            for settings, flags, expected in (({}, [], "en"), ({"language": "fr"}, [], "fr"),
                                               ({"language": "fr"}, ["--language", "en"], "en")):
                with self.subTest(settings=settings, flags=flags):
                    output = io.StringIO()
                    with patch("lixity.cli.load_project_config", return_value=settings), redirect_stdout(output):
                        self.assertEqual(main(["analyze", str(manuscript), "--json", *flags]), 0)
                    self.assertEqual(json.loads(output.getvalue())["meta"]["language"], expected)
