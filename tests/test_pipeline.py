"""Shared orchestration and explicit project isolation contracts."""

import unittest
from math import inf, nextafter
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
        analyze.assert_called_once()
        self.assertEqual(analyze.call_args.args, (text,))
        self.assertEqual(analyze.call_args.kwargs["projection"].text, "The door was open. I walked into the room.")
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
                config, _ = resolve_document_config(
                    text, project_config={"motifs": {"Weather": "rain"}}, sticky_min_words=9, sticky_glue_pct=55.5,
                    short_sentence_max=7,
                )
                analysis = analyze_document(text, config, resolve_thresholds(project_config={}))
                before = analysis.metrics.model_dump()
                expected = {
                    "dialogue": {**dialogue_report(text, config).to_dict(),
                                 "short_turn_max_words": config.short_turn_max_words,
                                 "long_turn_min_words": config.long_turn_min_words},
                    "pacing": {**pacing_report(text, config).to_dict(),
                               "hook_short_sentence": config.hook_short_sentence,
                               "monotony_min_run": config.monotony_min_run,
                               "sticky_rule": {"min_words": 9, "min_pct": 55.5},
                               "rhythm_word_bounds": (7, 20)},
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

    def test_sticky_jumps_use_complete_unique_sentences_after_ranking(self):
        from lixity import pipeline
        from lixity.pacing import pacing_report

        prefix = "The gate and the door " * 5
        first, second = prefix + "open.", prefix + "close."
        stronger = "It is on the wall and it is by the door."
        ambiguous = "She was in the hall and it was by the door."
        text = f"## One\n\n{first}\n\n{second}\n\n{stronger}\n\n{ambiguous}\n\n> {ambiguous}\n"
        config, _ = resolve_document_config(text, "en")
        analysis = analyze_document(text, config, resolve_thresholds(project_config={}), include_evidence=True)
        reports = pipeline.supplementary_reports(text, config, analysis)
        rows = reports["pacing"]["sticky_items"]
        self.assertLess(
            next(i for i, row in enumerate(rows) if row.get("paragraph_id") == "p-2"),
            next(i for i, row in enumerate(rows) if row.get("paragraph_id") == "p-0"),
        )
        self.assertEqual(
            [row.get("paragraph_id") for row in rows if row["preview"] == prefix[:80]], ["p-0", "p-1"],
        )
        self.assertEqual(
            [row.get("paragraph_id") for row in rows if row["preview"] == ambiguous], [None, None],
        )
        self.assertEqual(
            pacing_report(text, config, _include_sticky_identity=True).to_dict(),
            pacing_report(text, config).to_dict(),
        )

    def test_sticky_jump_matches_canonical_text_and_keeps_the_literal_evidence(self):
        from lixity.pipeline import supplementary_reports

        sentence = "I want to go to the cafe\u0301."
        composed = "I want to go to the café."
        thresholds = resolve_thresholds(project_config={})
        for prose, expected_targets in ((sentence, ["p-0"]), (sentence + "\n\n> " + composed, [None, None])):
            with self.subTest(prose=prose):
                text = f"## One\n\n{prose}\n"
                config, _ = resolve_document_config(text, "en", sticky_min_words=3)
                analysis = analyze_document(text, config, thresholds, include_evidence=True)
                rows = supplementary_reports(text, config, analysis)["pacing"]["sticky_items"]
                self.assertEqual([row["preview"] for row in rows], [composed] * len(expected_targets))
                self.assertEqual([row.get("paragraph_id") for row in rows], expected_targets)
                if expected_targets == ["p-0"]:
                    self.assertEqual((rows[0]["start_line"], rows[0]["span_index"]), (3, 0))
                assert analysis.evidence is not None
                paragraph = analysis.paragraphs[0]
                span = analysis.evidence[0]["layers"]["sticky"]["spans"][0]
                self.assertEqual(paragraph.text[span["start"]:span["end"]], sentence)

    def test_sticky_threshold_agrees_in_evidence_pacing_and_revisions(self):
        from lixity.manuscript_editing import analyze_manuscript_snapshot
        from lixity.pacing import pacing_report

        text = ("## Divided chapter\n\nThe path and the bridge.\n\n---\n\nI will wait for you.\n\n"
                "## Undivided chapter\n\nThe path and the bridge. It is.")
        thresholds = resolve_thresholds(project_config={})
        for min_words, min_pct, expected in ((5, 60.0, [3, 4, 3]), (5, 60.01, [4]), (6, 60.0, [])):
            with self.subTest(sticky_min_words=min_words, sticky_glue_pct=min_pct):
                config, _ = resolve_document_config(text, "en", sticky_min_words=min_words, sticky_glue_pct=min_pct)
                analysis = analyze_document(text, config, thresholds, include_evidence=True)
                assert analysis.evidence is not None
                hits = [span["function_words"] for item in analysis.evidence.values()
                        for span in item["layers"]["sticky"]["spans"]]
                self.assertEqual(hits, expected)
                pacing = pacing_report(text, config).to_dict()
                self.assertCountEqual([item["glue_words"] for item in pacing["sticky_items"]], expected)
                self.assertEqual(pacing["sticky_sentence_pct"], len(expected) * 25.0)
                snapshot = analyze_manuscript_snapshot(text, config=config)
                self.assertEqual(snapshot["sticky_pct"], pacing["sticky_sentence_pct"])

    def test_sticky_uses_the_inclusive_percentage_boundary_in_shared_reports(self):
        from lixity.manuscript_editing import analyze_manuscript_snapshot
        from lixity.pacing import pacing_report

        text = "## One\n\n" + " ".join(["the"] * 29 + ["cedar"] * 71) + "."
        thresholds = resolve_thresholds(project_config={})
        for limit, expected_hits in ((29.0, 1), (nextafter(29.0, inf), 0)):
            config, _ = resolve_document_config(text, "en", sticky_glue_pct=limit)
            analysis = analyze_document(text, config, thresholds, include_evidence=True)
            assert analysis.evidence is not None
            hits = analysis.evidence[0]["layers"]["sticky"]["spans"]
            self.assertEqual(len(hits), expected_hits)
            report = pacing_report(text, config)
            self.assertEqual(report.sticky_sentences, expected_hits)
            self.assertEqual(analyze_manuscript_snapshot(text, config=config)["sticky_pct"],
                             expected_hits * 100.0)

    def test_supplementary_reports_precomputes_sentence_group_matches_with_evidence(self):
        from lixity import pipeline

        text = (
            "## One\n\n"
            "Short sentence. A medium length sentence with several words here. "
            "This much longer sentence keeps extending across many different words until it crosses the long boundary easily and continues beyond twenty words.\n"
        )
        config, _ = resolve_document_config(
            text, project_config={}, short_sentence_max=3, medium_sentence_max=10, long_sentence_max=15
        )
        analysis = analyze_document(
            text, config, resolve_thresholds(project_config={}), include_evidence=True
        )
        reports = pipeline.supplementary_reports(text, config, analysis)
        matches = reports["pacing"]["sentence_group_matches"]
        self.assertEqual(matches["rhythm"]["short"], [{"paragraph_id": "p-0", "span_index": 0}])
        self.assertEqual(matches["rhythm"]["medium"], [{"paragraph_id": "p-0", "span_index": 1}])
        self.assertEqual(matches["rhythm"]["long"], [{"paragraph_id": "p-0", "span_index": 2}])
        self.assertEqual(matches["distribution"]["short"], [{"paragraph_id": "p-0", "span_index": 0}])
        self.assertEqual(matches["distribution"]["medium"], [{"paragraph_id": "p-0", "span_index": 1}])
        self.assertEqual(matches["distribution"]["very_long"], [{"paragraph_id": "p-0", "span_index": 2}])

    def test_appendix_marker_inside_comments_or_fences_keeps_later_evidence(self):
        from lixity.manuscript_editing import analyze_manuscript_snapshot
        from lixity.pipeline import supplementary_reports

        marker = "## Anmerkungen und Literaturverzeichnis"
        text = (
            f"## First\n\nRain falls.\n\n<!--\n{marker}\n-->\n\n```markdown\n{marker}\n```\n\n"
            f"## Next\n\nRain stays.\n\n{marker}\n\nRain excluded.\n"
        )
        for source in (text, text.replace("\n", "\r\n")):
            with self.subTest(crlf="\r" in source):
                config, _ = resolve_document_config(source, motif_regexes={"Rain": "rain"})
                analysis = analyze_document(source, config, resolve_thresholds(project_config={}), include_evidence=True)
                reports = supplementary_reports(source, config, analysis)
                self.assertEqual(analysis.metrics.tokens, 4)
                self.assertEqual([chapter.title for chapter in analysis.chapters], ["First", "Next"])
                self.assertEqual([(p.start_line, p.text) for p in analysis.paragraphs],
                                 [(3, "Rain falls."), (15, "Rain stays.")])
                self.assertEqual(reports["pacing"]["chapters"], 2)
                self.assertEqual(reports["pacing"]["sentence_group_matches"]["distribution"]["short"],
                                 [{"paragraph_id": "p-0", "span_index": 0},
                                  {"paragraph_id": "p-1", "span_index": 0}])
                occurrences = reports["motifs"]["motifs"][0]["occurrences"]
                self.assertEqual([(match["start_line"], match["start"], match["end"], match["quote"])
                                  for match in occurrences], [(3, 0, 4, "Rain"), (15, 0, 4, "Rain")])
                snapshot = analyze_manuscript_snapshot(source, config=config)
                self.assertEqual(snapshot["sentences"], 2)
                self.assertEqual([chapter["title"] for chapter in snapshot["chapter_metrics"]], ["First", "Next"])

    def test_explicit_appendix_markers_preserve_literal_boundaries(self):
        from lixity.markdown_parser import before_appendix

        for marker in ("STOP HERE", "<!-- STOP HERE -->"):
            with self.subTest(marker=marker):
                prefix = f"## Main\n\nRain falls.\n\n~~~\n{marker}\n~~~\n\nRain stays. "
                source = prefix + marker + " Rain excluded."
                config, _ = resolve_document_config(source, appendix_marker=marker)
                self.assertEqual(before_appendix(source, config), prefix)

    def test_fenced_comment_text_and_comment_contained_fences_keep_real_boundaries(self):
        from lixity.manuscript_editing import analyze_manuscript_snapshot
        from lixity.markdown_parser import before_appendix
        from lixity.pipeline import supplementary_reports

        marker = "## Anmerkungen und Literaturverzeichnis"
        body = (
            f"## One\n\nRain falls.\n\n<!-- note\n~~~unclosed\n{marker}\n-->\n\n"
            f"```html\n<!--\n{marker}\n```\n\n## Two\n\nRain stays.\n\n"
        )
        text = f"{body}{marker}\n\nRain excluded.\n\n<!-- later note -->\n"
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=repr(newline)):
                source = text.replace("\n", newline)
                config, _ = resolve_document_config(source, motif_regexes={"Rain": "rain"})
                self.assertEqual(before_appendix(source, config), body.replace("\n", newline))
                analysis = analyze_document(source, config, resolve_thresholds(project_config={}), include_evidence=True)
                self.assertEqual(analysis.metrics.tokens, 4)
                self.assertEqual([(ch.num, ch.title) for ch in analysis.chapters], [(1, "One"), (2, "Two")])
                self.assertEqual([(p.start_line, p.text) for p in analysis.paragraphs],
                                 [(3, "Rain falls."), (17, "Rain stays.")])
                reports = supplementary_reports(source, config, analysis)
                self.assertEqual(reports["pacing"]["chapter_list"][1]["words"], 2)
                self.assertEqual(reports["motifs"]["motifs"][0]["occurrences"][1]["start_line"], 17)
                snapshot = analyze_manuscript_snapshot(source, config=config)
                self.assertEqual(snapshot["words"], analysis.metrics.clean_words)
                self.assertEqual(snapshot["sentences"], 2)

    def test_opening_prose_is_counted_and_anchored_before_first_heading(self):
        from lixity.pipeline import supplementary_reports

        text = "The birds sing.\n\nThe moon shines.\n\n## Chapter\n\nA fox runs.\n"
        for source in (text, text.replace("\n", "\r\n")):
            with self.subTest(crlf="\r" in source):
                config, _ = resolve_document_config(source)
                analysis = analyze_document(source, config, resolve_thresholds(project_config={}), include_evidence=True)
                reports = supplementary_reports(source, config, analysis)
                self.assertEqual(analysis.metrics.tokens, 9)
                self.assertEqual([(chapter.num, chapter.title, chapter.words) for chapter in analysis.metrics.chapters],
                                 [(1, "", 6), (2, "Chapter", 3)])
                self.assertEqual([(p.chapter_num, p.start_line, p.text) for p in analysis.paragraphs],
                                 [(1, 1, "The birds sing."), (1, 3, "The moon shines."), (2, 7, "A fox runs.")])
                self.assertEqual([chapter["words"] for chapter in reports["pacing"]["chapter_list"]], [6, 3])
                self.assertEqual(reports["pacing"]["sentence_group_matches"]["distribution"]["short"],
                                 [{"paragraph_id": "p-0", "span_index": 0}, {"paragraph_id": "p-1", "span_index": 0},
                                  {"paragraph_id": "p-2", "span_index": 0}])

    def test_soft_wrapped_opening_prose_keeps_its_evidence_range(self):
        from lixity.pipeline import supplementary_reports

        for opening in ("Mara\nsaw the quiet river.", "Mara ran to\nBerlin."):
            with self.subTest(opening=opening):
                text = f"{opening}\n\n## Chapter\n\nA fox runs.\n"
                config, _ = resolve_document_config(text)
                analysis = analyze_document(text, config, resolve_thresholds(project_config={}), include_evidence=True)
                self.assertEqual(analysis.metrics.chapters[0].title, "")
                first = analysis.paragraphs[0]
                self.assertEqual((first.chapter_num, first.start_line, first.end_line), (1, 1, 2))
                self.assertEqual(first.text, opening.replace("\n", " "))
                reports = supplementary_reports(text, config, analysis)
                self.assertEqual(reports["pacing"]["sentence_group_matches"]["distribution"]["short"][0],
                                 {"paragraph_id": "p-0", "span_index": 0})
