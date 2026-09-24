"""Shared orchestration and explicit project isolation contracts."""

import unittest
from unittest.mock import patch

from lixity.config import resolve_thresholds
from lixity.pipeline import analyze_document, resolve_document_config


class TestDocumentPipeline(unittest.TestCase):
    def test_document_analysis_reuses_metrics(self):
        text = "## Chapter\n\nThe door was open. I walked into the room.\n"
        config, resolved = resolve_document_config(text, "en", chapter_regex=r"(?m)^##\s+")
        thresholds = resolve_thresholds(flag_min_severity=3, project_config={})
        from lixity.analyzer import CorpusAnalyzer

        analyzer = CorpusAnalyzer(config)
        with patch("lixity.pipeline.CorpusAnalyzer", return_value=analyzer), patch.object(
            analyzer, "analyze_text", wraps=analyzer.analyze_text
        ) as analyze, patch(
            "lixity.pipeline.lexical_structural_diagnostics", return_value={"cooccurrence": {}}
        ) as diagnostics:
            result = analyze_document(text, config, thresholds)
        analyze.assert_called_once_with(text)
        diagnostics.assert_called_once_with(text, config)
        self.assertEqual(resolved.key, "en")
        self.assertTrue(result.chapters)
        self.assertEqual({paragraph.flag_min for paragraph in result.paragraphs}, {3})
        self.assertIn("cooccurrence", result.fingerprint.structural_diagnostics)

    def test_explicit_project_config_never_reads_working_directory(self):
        with patch("lixity.config.load_project_config", side_effect=AssertionError("implicit IO")):
            first = resolve_thresholds(project_config={"z_mild": 1.5}, flag_min_severity=3)
            second = resolve_thresholds(project_config={"z_mild": 3.0}, z_mild=2.0)
            defaults = resolve_thresholds(project_config={})
        self.assertEqual(first.z_mild, 1.5)
        self.assertEqual(first.flag_min_severity, 3)
        self.assertEqual(second.z_mild, 2.0)
        self.assertEqual(defaults.z_mild, 2.5)

    def test_language_resolution_keeps_project_overrides(self):
        config, resolved = resolve_document_config(
            "The room was empty.", "en", chapter_regex=r"(?m)^#\s+", appendix_marker="END"
        )
        self.assertEqual(config.language, resolved.key)
        self.assertEqual(config.chapter_regex, r"(?m)^#\s+")
        self.assertEqual(config.appendix_marker, "END")
