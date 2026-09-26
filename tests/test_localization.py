"""Cross-language contracts for defaults, resources and numerical presentation."""

import io
import json
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from html import escape
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch

from lixity import api, language_data
from lixity.analyzer import CorpusAnalyzer
from lixity.cli import main
from lixity.format import num, pct
from lixity.language import LANGUAGE_PROFILES
from lixity.models import CorpusConfig
from lixity.ui.dashboard import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS


class _DashboardBodyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = {}

    def handle_starttag(self, tag, attrs):
        if tag == "body":
            self.labels = json.loads(dict(attrs)["data-ui-labels"])


class TestLocalization(unittest.TestCase):
    @unittest.skipIf(sys.version_info < (3, 11), "Project TOML loading requires Python 3.11+")
    def test_cli_uses_the_manuscript_project_from_another_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manuscript = root / "sample.md"
            manuscript.write_text("## Eins\n\nIch gehe und ich sehe das Haus.\n", encoding="utf-8")
            (root / "lixity.toml").write_text('language = "de"\ntitle = "My project"\n', encoding="utf-8")
            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(main(["analyze", str(manuscript), "--json"]), 0)
            self.assertEqual(json.loads(output.getvalue())["meta"]["language"], "de")
            for command in ("dashboard", "build"):
                dashboard = root / "dashboard.html"
                arguments = [command, str(manuscript)]
                if command == "dashboard":
                    arguments.extend(["-o", str(dashboard)])
                else:
                    dashboard = root / "exports" / "sample_dashboard.html"
                with redirect_stdout(io.StringIO()):
                    self.assertEqual(main(arguments), 0)
                self.assertIn("<h1>My project</h1>", dashboard.read_text(encoding="utf-8"))

    def test_english_defaults_and_explicit_detection(self):
        text = "## Chapter\n\nIch gehe und ich sehe das Haus. Die Tür ist offen.\n"
        self.assertEqual(CorpusConfig().language, "en")
        self.assertEqual(CorpusAnalyzer().lang.key, "en")
        self.assertEqual(api.analyze(text)["meta"]["language"], "en")
        self.assertEqual(api.analyze(text, language="auto")["meta"]["language"], "de")

    def test_all_supported_profiles_have_complete_resource_keys(self):
        for name in ("LABELS", "METRIC_LABELS", "HELP_TEXTS", "GROUP_LABELS", "LAYER_LABELS", "UI_LABELS", "IDENTITY_LABELS", "GUIDANCE_LABELS", "WORKSPACE_LABELS"):
            table = WORKSPACE_LABELS if name == "WORKSPACE_LABELS" else getattr(language_data, name)
            for language in ("en", "de", "fr", "es", "it", "pt", "nl"):
                with self.subTest(resource=name, language=language):
                    self.assertFalse(set(table["en"]) - set(table[language]))
                    self.assertTrue(all(table[language][key].strip() for key in table["en"]))

    def test_workspace_and_research_controls_follow_all_seven_locales(self):
        for language in ("en", "de", "fr", "es", "it", "pt", "nl"):
            with self.subTest(language=language):
                labels = LANGUAGE_PROFILES[language].labels
                rendered = render_dashboard([], [], controls=True, labels=labels, language_key=language)
                parser = _DashboardBodyParser()
                parser.feed(rendered)
                self.assertEqual(
                    {key: parser.labels[key] for key in WORKSPACE_LABELS[language]},
                    WORKSPACE_LABELS[language],
                )
                self.assertEqual(parser.labels["ctx_provenance_note"], labels["ctx_provenance_note"])
                for key in ("research_tab_claims", "wizard_import_tab", "wizard_open_note"):
                    self.assertTrue(escape(labels[key]) in rendered, key)
                self.assertIn('value="supports"', rendered)
                self.assertNotIn("lixity.json", rendered)

    def test_workspace_labels_are_escaped_in_html_and_json_attribute(self):
        labels = dict(LANGUAGE_PROFILES["en"].labels)
        labels["research_hint"] = '"<img src=x onerror=alert(1)>'
        rendered = render_dashboard([], [], controls=True, labels=labels)
        parser = _DashboardBodyParser()
        parser.feed(rendered)
        self.assertEqual(parser.labels["research_hint"], labels["research_hint"])
        self.assertNotIn('<img src=x onerror=alert(1)>', rendered)

    def test_workspace_template_placeholders_match_across_locales(self):
        def fields(value):
            return set(re.findall(r"\{([a-z_]+)\}", value))

        for key, english in WORKSPACE_LABELS["en"].items():
            for language in ("de", "fr", "es", "it", "pt", "nl"):
                with self.subTest(key=key, language=language):
                    self.assertEqual(fields(WORKSPACE_LABELS[language][key]), fields(english))

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
                self.assertIn(labels["license_sales_notice"], rendered)
                self.assertIn(labels["license_terms"], rendered)
                self.assertIn('href="https://github.com/mfahsold/lixity/blob/main/LICENSE"', rendered)
                self.assertIn('href="mailto:mfahsold@googlemail.com?subject=Lixity%20Commercial%20License"', rendered)
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
