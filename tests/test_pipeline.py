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

    def test_supplementary_reports_match_configured_reports_and_reuse_analysis(self):
        from lixity import pipeline
        from lixity.analyzer import CorpusAnalyzer
        from lixity.dialogue import dialogue_report
        from lixity.motifs import motif_report
        from lixity.pacing import pacing_report
        from lixity.scenes import scene_report
        from lixity.showing import showing_report

        for divider, scene_count in (("", 0), ("\n\n---\n\n", 2)):
            with self.subTest(divider=bool(divider)):
                text = '## One\n\nMara sees rain. "Stay here," she says.' + divider + ' Rain falls.\n'
                settings = {"assignments": {"1:1": "quiet"},
                            "groups": {"quiet": {"targets": {"asl": [2, 8]}}}}
                config, _ = resolve_document_config(text, project_config={"motifs": {"Weather": "rain"}})
                analysis = analyze_document(text, config, resolve_thresholds(project_config={}))
                before = analysis.metrics.model_dump()
                expected = {
                    "dialogue": dialogue_report(text, config).to_dict(),
                    "pacing": pacing_report(text, config).to_dict(),
                    "motifs": motif_report(text, config=config).to_dict(),
                    "showing": showing_report(text, config, metrics=analysis.metrics).to_dict(),
                    "scenes": scene_report(text, config, settings),
                }
                original = CorpusAnalyzer.measure_unit
                with patch.object(CorpusAnalyzer, "analyze_text", side_effect=AssertionError("reanalysis")), \
                        patch.object(CorpusAnalyzer, "measure_unit", autospec=True, side_effect=original) as measure:
                    actual = pipeline.supplementary_reports(text, config, analysis, scene_settings=settings)
                self.assertEqual(actual, expected)
                self.assertEqual(measure.call_count, scene_count)
                self.assertEqual(analysis.metrics.model_dump(), before)
                self.assertEqual(actual["motifs"]["motifs"][0]["name"], "Weather")
                self.assertEqual(actual["scenes"]["items"][0]["group"], "quiet")

    def test_supplementary_reports_keep_invalid_scene_settings_visible(self):
        from lixity import pipeline

        text = "## One\n\nRain falls.\n"
        config, _ = resolve_document_config(text, project_config={})
        analysis = analyze_document(text, config, resolve_thresholds(project_config={}))
        reports = pipeline.supplementary_reports(text, config, analysis,
                                                 scene_settings={"assignments": {"1:1": "missing"}})
        self.assertIn("Unknown register", reports["scenes"]["error"])
        self.assertTrue(reports["dialogue"])
