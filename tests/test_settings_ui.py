"""Settings and scientific UI contracts independent of browser presentation."""

import re
import unittest
from html.parser import HTMLParser

from lixity.language import get_language_profile
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.numbers = []
        self.labels = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and attributes.get("type") == "number":
            self.numbers.append(attributes)
        if tag == "label" and "for" in attributes:
            self.labels.add(attributes["for"])


class TestSettingsUi(unittest.TestCase):
    def test_settings_language_matches_analysis_unless_explicitly_overridden(self):
        for language in ("en", "de", "fr", "generic"):
            rendered = render_dashboard([], [], controls=True, language_key=language)
            self.assertIn(f'<option value="{language}" selected>', rendered)
        rendered = render_dashboard([], [], controls=True, language_key="de", current_language="auto")
        self.assertIn('<option value="auto" selected>', rendered)

    def test_controls_have_one_nda_workflow_and_shared_groups(self):
        rendered = render_dashboard([], [], controls=True)
        self.assertNotIn('id="nda-name"', rendered)
        self.assertNotIn('data-action="nda"', rendered)
        self.assertEqual(rendered.count('id="nda-add-btn"'), 1)
        self.assertIn('class="settings-form ctl-group"', rendered)

    def test_localized_settings_keep_machine_readable_number_values(self):
        for language in ("en", "de", "fr", "es", "it", "pt", "nl"):
            with self.subTest(language=language):
                rendered = render_dashboard([], [], controls=True, language_key=language,
                                            labels=get_language_profile(language).labels)
                controls = Controls()
                controls.feed(rendered)
                self.assertEqual(len(controls.numbers), 4)
                for field in controls.numbers:
                    self.assertNotIn(",", field["value"])
                    self.assertGreater(float(field["value"]), 0)
                    self.assertIn(field["id"], controls.labels)
                    self.assertIn("aria-describedby", field)
                self.assertIn('id="settings-form"', rendered)

    def test_matrix_marks_only_the_core_fdr_set(self):
        text = "## One\n\nI walk. I see the rain.\n\n## Two\n\nThe house was sold and the door was closed.\n"
        config, language = resolve_document_config(text, "en")
        result = analyze_document(text, config, FingerprintThresholds())
        result.fingerprint.fdr_flagged = {1: ["asl"]}
        rendered = render_dashboard(result.chapters, result.paragraphs, metrics=result.metrics,
                                    fingerprint=result.fingerprint, labels=language.labels)
        self.assertEqual(len(re.findall(r'class="fdr-marker"', rendered)), 1)
        self.assertIn('id="heatmap-fdr-only"', rendered)
        self.assertIn("Cliff", rendered)

    def test_color_legend_does_not_misrepresent_configured_threshold(self):
        text = "## One\n\nI walk. I see the rain.\n\n## Two\n\nThe house was sold and the door was closed.\n"
        config, language = resolve_document_config(text, "en")
        result = analyze_document(text, config, FingerprintThresholds(z_mild=1.5))
        rendered = render_dashboard(result.chapters, result.paragraphs, metrics=result.metrics,
                                    fingerprint=result.fingerprint, labels=language.labels,
                                    language_key="en")
        self.assertIn('class="z-gradient"></span> −2.5 … +2.5', rendered)
        self.assertIn('|z*| ≥ 1.5', rendered)
