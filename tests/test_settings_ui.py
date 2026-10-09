"""Settings and scientific UI contracts independent of browser presentation."""

import html
import re
import unittest
from html.parser import HTMLParser

from lixity.language import get_language_profile
from lixity.pipeline import analyze_document, resolve_document_config
from lixity.style_fingerprint import FingerprintThresholds
from lixity.ui import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS


class Controls(HTMLParser):
    def __init__(self):
        super().__init__()
        self.numbers = []
        self.inputs = {}
        self.labels = set()

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "input" and attributes.get("id"):
            self.inputs[attributes["id"]] = attributes
        if tag == "input" and attributes.get("type") == "number":
            self.numbers.append(attributes)
        if tag == "label" and "for" in attributes:
            self.labels.add(attributes["for"])


class TestSettingsUi(unittest.TestCase):
    def test_author_setting_requires_an_explicit_active_project_capability(self):
        author = 'Synthetic Writer "<img src=x onerror=alert(1)>"'
        for enabled in (False, True):
            with self.subTest(enabled=enabled):
                rendered = render_dashboard([], [], controls=True, project_author=author,
                                            author_setting_enabled=enabled)
                controls = Controls()
                controls.feed(rendered)
                field = controls.inputs["set-author-name"]
                self.assertEqual(field["value"], author)
                self.assertEqual(field["maxlength"], "500")
                self.assertEqual("disabled" in field, not enabled)
                self.assertIn("set-author-name", controls.labels)
                self.assertIn("aria-describedby", field)
                self.assertNotIn('<img src=x onerror=alert(1)>', rendered)

    def test_identity_check_statuses_are_localized_and_values_are_inert(self):
        for language, labels in WORKSPACE_LABELS.items():
            for status in ("matched", "mismatch", "missing", "unsupported", "unavailable"):
                with self.subTest(language=language, status=status):
                    checks = {key: {"status": status, "value": '<script>synthetic()</script>',
                                    "source": 'metadata "<img src=x>"'}
                              for key in ("title", "author_name")}
                    rendered = render_dashboard([], [], controls=True, labels=labels,
                                                project_author="Synthetic Writer",
                                                identity_check=checks, author_setting_enabled=True)
                    self.assertIn(f'data-identity-status="{status}"', rendered)
                    self.assertIn(html.escape(labels["project_identity_" + status]), rendered)
                    self.assertNotIn('<script>synthetic()</script>', rendered)
                    self.assertIn('&lt;script&gt;synthetic()&lt;/script&gt;', rendered)
                    self.assertIn(html.escape(labels["project_identity_hint"]), rendered)

    def test_artifact_links_reject_executable_url_schemes(self):
        for href in ("javascript:alert(1)", "java\nscript:alert(1)", "data:text/html,bad"):
            with self.subTest(href=href):
                rendered = render_dashboard([], [], artifacts=[{"name": "Sample", "href": href}])
                artifacts = rendered.split('<div class="artifacts">', 1)[1].split('</section>', 1)[0]
                self.assertNotIn('<a ', artifacts)
        rendered = render_dashboard([], [], artifacts=[{"name": "Sample", "href": "exports/book.pdf"}])
        self.assertIn('href="exports/book.pdf"', rendered)

    def test_chapter_matrix_explains_every_column_in_each_language(self):
        text = "## One\n\nI walk. I see the rain.\n\n## Two\n\nThe door was closed.\n"
        config, _language = resolve_document_config(text)
        result = analyze_document(text, config, FingerprintThresholds())
        for language in ("en", "de", "fr", "es", "it", "pt", "nl"):
            with self.subTest(language=language):
                labels = get_language_profile(language).labels
                rendered = render_dashboard(result.chapters, result.paragraphs,
                                            fingerprint=result.fingerprint, labels=labels,
                                            language_key=language)
                matrix = rendered.split('id="matrix">', 1)[1].split('</thead>', 1)[0]
                self.assertEqual(matrix.count('scope="col"'), 9)
                self.assertEqual(matrix.count('data-help='), 9)
                self.assertNotIn('help_chapter_', matrix)

    def test_settings_language_matches_analysis_unless_explicitly_overridden(self):
        for language in ("en", "de", "fr", "generic"):
            rendered = render_dashboard([], [], controls=True, language_key=language)
            self.assertIn(f'<option value="{language}" selected>', rendered)
        rendered = render_dashboard([], [], controls=True, language_key="de", current_language="auto")
        self.assertIn('<option value="auto" selected>', rendered)

    def test_controls_have_one_nda_workflow_and_shared_groups(self):
        rendered = render_dashboard([], [], controls=True, enabled_actions=("nda-draft",))
        self.assertEqual(rendered.count('id="nda-name"'), 1)
        self.assertNotIn('data-action="nda"', rendered)
        self.assertEqual(rendered.count('id="nda-draft-form"'), 1)
        self.assertNotIn('id="nda-add-btn"', rendered)
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
