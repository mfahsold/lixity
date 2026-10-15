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
from lixity.markdown_parser import parse_markdown_blocks
from lixity.models import CorpusConfig
from lixity.style_profile import ParagraphProfiler
from lixity.ui.components import help_term, label
from lixity.ui.dashboard import render_dashboard
from lixity.workspace_labels import WORKSPACE_LABELS
from tests.support import LOCALES


class _DashboardBodyParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.labels = {}
        self.help_texts = set()
        self.elements = {}

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "body":
            self.labels = json.loads(attributes["data-ui-labels"])
        if "data-help" in attributes:
            self.help_texts.add(attributes["data-help"])
        if "id" in attributes:
            self.elements[attributes["id"]] = attributes


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
        for name in ("LABELS", "METRIC_LABELS", "HELP_TEXTS", "GROUP_LABELS", "LAYER_LABELS", "UI_LABELS", "IDENTITY_LABELS", "GUIDANCE_LABELS", "SCENE_LABELS", "WORKSPACE_LABELS"):
            table = WORKSPACE_LABELS if name == "WORKSPACE_LABELS" else getattr(language_data, name)
            for language in LOCALES:
                with self.subTest(resource=name, language=language):
                    self.assertFalse(set(table["en"]) - set(table[language]))
                    self.assertTrue(all(table[language][key].strip() for key in table["en"]))

    def test_workspace_and_research_controls_follow_all_seven_locales(self):
        for language in LOCALES:
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
                for key in ("research_tab_claims", "wizard_import_tab", "wizard_open_note",
                    "welcome_example",
                            "wizard_choose_action", "welcome_dismiss", "welcome_show"):
                    self.assertTrue(escape(labels[key]) in rendered, key)
                self.assertIn(f'<p class="ctl-note">{escape(labels["wizard_choose_location"])}</p>', rendered)
                for key in ("help_open_existing", "help_import_manuscript", "help_language",
                            "help_research_init", "help_research_ingest", "help_research_search",
                            "help_research_dossier", "help_research_claim", "help_research_confidence",
                            "help_research_evidence", "help_research_passage", "help_research_relation",
                            "help_research_decision", "help_research_deviation",
                            "help_research_comparison"):
                    self.assertIn(labels[key], parser.help_texts, key)
                self.assertEqual(parser.elements["r-claim-confidence"]["aria-label"],
                                 labels["research_confidence_field"])
                self.assertEqual(parser.elements["r-link-relation"]["aria-label"],
                                 labels["research_relation_field"])
                self.assertIn('id="modal-research-revision"', rendered)
                self.assertIn('id="research-revision-title">' + escape(labels["research_revision_title"]), rendered)
                for key in ("research_revision_correction_desc", "research_revision_supersession_desc",
                            "research_revision_reason", "research_revision_save"):
                    self.assertIn(escape(labels[key]), rendered)
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

    def test_hd_d_help_describes_the_42_token_estimator_in_all_locales(self):
        for language in LOCALES:
            with self.subTest(language=language):
                labels = LANGUAGE_PROFILES[language].labels
                help_text = labels["help_hd_d"]
                self.assertIn("42", help_text)
                self.assertIn(escape(help_text, quote=True), help_term(labels, "hd_d", "HD-D"))

    def test_units_use_singular_forms_and_the_footer_keeps_a_separator(self):
        paragraphs, chapters = ParagraphProfiler(CorpusConfig(language="de")).profile_blocks(
            parse_markdown_blocks("## Kapitel\n\nEin einzelner Satz steht hier.\n")
        )
        html = render_dashboard(chapters, paragraphs, controls=False,
                                labels=LANGUAGE_PROFILES["de"].labels, language_key="de",
                                title="Synthetic title")
        self.assertIn("1 Absatz", html)
        self.assertNotIn("1 Abs\u00e4tze", html)
        self.assertIn("0 Auff\u00e4lligkeiten", html)
        self.assertIn("</span> \u00b7 <span>", html)

    def test_workspace_actions_remain_available_without_guidance_or_legacy_actions(self):
        paragraphs, chapters = ParagraphProfiler(CorpusConfig()).profile_blocks(
            parse_markdown_blocks("## Chapter\n\nThe door opened. The room was quiet.")
        )
        html = render_dashboard(chapters, paragraphs, controls=True,
                                enabled_actions=("analyze", "rebuild"))
        self.assertLess(html.index('class="workspace-bar"'), html.index('id="welcome-hero"'))
        self.assertLess(html.index('class="workspace-bar"'), html.index('id="controls"'))
        self.assertEqual(html.count('id="btn-modal-open-project"'), 1)
        self.assertIn('id="welcome-show" aria-controls="welcome-hero" aria-expanded="false"', html)
        self.assertIn('id="welcome-hero" hidden', html)
        for hidden_action in ('data-action="load"', 'data-action="export"',
                              'data-action="sync"', 'id="nda-manager"'):
            self.assertNotIn(hidden_action, html.split("<script>", 1)[0])
        for visible_action in ('data-action="analyze"', 'data-action="rebuild"',
                               'id="research-manager"'):
            self.assertIn(visible_action, html)

        legacy = render_dashboard([], [], controls=True)
        for legacy_action in ('data-action="load"', 'data-action="export"'):
            self.assertIn(legacy_action, legacy)
        self.assertNotIn('id="nda-draft-form"', legacy)

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

        for language in LOCALES:
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


def test_documented_claim_time_examples_parse_in_every_locale():
    """Every example in the claim-time hint must be accepted by the chronology."""
    from lixity.research.timeline import parse_period

    token = re.compile(r"\b\d{4}(?:-\d{2}-\d{2}|[–-]\d{4}|-\d{2})?\b")
    for language in LOCALES:
        hint = WORKSPACE_LABELS[language]["research_claim_time_hint"]
        examples = token.findall(hint)
        assert examples, language
        for example in examples:
            period, reason = parse_period(example)
            assert period is not None, (language, example, reason)


def test_cli_report_text_packs_share_keys_and_placeholders():
    """The terminal text packs stay parallel; placeholders must match keys."""
    from lixity.cli import CLI_TEXTS

    def fields(value: str) -> set[str]:
        return set(re.findall(r"\{([a-z_]+)\}", value))

    assert set(CLI_TEXTS["en"]) == set(CLI_TEXTS["de"])
    for key, english in CLI_TEXTS["en"].items():
        assert fields(CLI_TEXTS["de"][key]) == fields(english), key


def test_manuscript_review_codes_have_workspace_labels():
    """Every review state and displayed flag resolves to a workspace label."""
    from lixity.status import ManuscriptFlag, ManuscriptState

    def state_key(state: ManuscriptState) -> str:
        if state is ManuscriptState.UNAVAILABLE:
            return "manuscript_link_unavailable_anchor"
        return f"manuscript_link_{state.value}"

    displayed_flags = (
        ManuscriptFlag.SOURCE_CHANGED,
        ManuscriptFlag.CLAIM_CHANGED,
        ManuscriptFlag.CLAIM_WITHDRAWN,
    )
    for language in LOCALES:
        labels = WORKSPACE_LABELS[language]
        for state in ManuscriptState:
            key = state_key(state)
            assert labels.get(key, "").strip(), (language, state, key)
        for flag in displayed_flags:
            key = f"manuscript_link_{flag.value}"
            assert labels.get(key, "").strip(), (language, flag, key)


def test_count_labels_carry_singular_forms():
    """Every count-noun template has a `_one` row for exactly one item."""
    # Parenthetical counters ("({count})") and count-free adjectives keep one row.
    parenthetical = re.compile(r"\(\{count\}\)")
    invariant = {"status_markers_open"}
    for key, english in WORKSPACE_LABELS["en"].items():
        if "{count}" not in english or key.endswith("_one") or key in invariant:
            continue
        if parenthetical.search(english):
            continue
        for language in LOCALES:
            assert f"{key}_one" in WORKSPACE_LABELS[language], (key, language)


def test_default_labels_cover_the_scene_pack():
    for key, value in language_data.SCENE_LABELS["en"].items():
        assert label(None, key) == value
