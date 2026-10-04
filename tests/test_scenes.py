"""Scene/register analysis contracts, using synthetic prose only."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity import api
from lixity.analyzer import CorpusAnalyzer
from lixity.cli import main
from lixity.pipeline import resolve_document_config
from lixity.scenes import scene_report, scene_report_for_display
from lixity.server.views import build_server_dashboard
from lixity.style_fingerprint import FEATURES

TEXT = "## First\n\nI see rain. I might leave.\n\n---\n\nThe door closes.\n\n## Second\n\n" + (
    "A report was written and the decision was recorded. " * 14
)
SETTINGS = {"scene_analysis": {
    "assignments": {"1:1": "close", "1:2": "close", "2:1": "formal"},
    "groups": {
        "close": {"targets": {"asl": [2, 6], "hd_d": [0.4, 0.9]}},
        "formal": {"targets": {"passive_density": [1, None]}},
    },
}}


class SceneContracts(unittest.TestCase):
    def test_display_reuses_whole_chapter_metrics_without_resampling(self):
        text = "## First\n\nI see rain. I might leave.\n\n## Second\n\n" + (
            "A report was written and the decision was recorded. " * 14
        )
        settings = {"assignments": {"1:1": "voice", "2:1": "voice"},
                    "groups": {"voice": {"targets": {"asl": [2, 6]}}}}
        for configuration in ({}, {"word_regex": r"\b[A-Z][a-z]*\b"}, {"language": "de"}):
            with self.subTest(configuration=configuration):
                config, _ = resolve_document_config(text, **configuration)
                metrics = CorpusAnalyzer(config).analyze_text(text)
                before = metrics.model_dump()
                expected = scene_report(text, config, settings)
                with patch.object(CorpusAnalyzer, "measure_unit") as measure:
                    actual = scene_report_for_display(text, config, settings,
                                                      premeasured_chapters=metrics.chapters)
                measure.assert_not_called()
                self.assertEqual(actual, expected)
                self.assertEqual(metrics.model_dump(), before)

    def test_display_reuses_only_unsplit_chapters_in_a_mixed_manuscript(self):
        config, _ = resolve_document_config(TEXT)
        metrics = CorpusAnalyzer(config).analyze_text(TEXT)
        expected = scene_report(TEXT, config, SETTINGS["scene_analysis"])
        original = CorpusAnalyzer.measure_unit
        with patch.object(CorpusAnalyzer, "measure_unit", autospec=True, side_effect=original) as measure:
            actual = scene_report_for_display(TEXT, config, SETTINGS["scene_analysis"],
                                              premeasured_chapters=metrics.chapters)
        self.assertEqual(measure.call_count, 2)
        self.assertTrue(all("A report was written" not in call.args[1] for call in measure.call_args_list))
        self.assertEqual(actual, expected)

    def test_dashboard_entrypoints_do_not_measure_whole_chapters_twice(self):
        text = "## First\n\nI see rain. I might leave.\n\n## Second\n\nA report was written."
        original = CorpusAnalyzer.measure_unit
        with tempfile.TemporaryDirectory() as root:
            manuscript = Path(root, "sample.md")
            manuscript.write_text(text, encoding="utf-8")
            entrypoints = (
                ("api", lambda: api.dashboard(text, project_config={})),
                ("server", lambda: build_server_dashboard(str(manuscript))),
                ("cli-dashboard", lambda: main(["dashboard", str(manuscript), "--output", str(Path(root, "report.html"))])),
                ("cli-build", lambda: main(["build", str(manuscript), "--dry-run"])),
            )
            for name, run in entrypoints:
                with self.subTest(name=name), contextlib.redirect_stdout(io.StringIO()), \
                        patch.object(CorpusAnalyzer, "measure_unit", autospec=True, side_effect=original) as measure:
                    run()
                    measure.assert_not_called()
            with patch.object(CorpusAnalyzer, "measure_unit", autospec=True, side_effect=original) as measure:
                standalone = api.scenes(text, project_config={})
            self.assertEqual(measure.call_count, 2)
            self.assertEqual(len(standalone["scenes"]["items"]), 2)

    def test_display_does_not_reuse_metrics_for_explicit_single_part_dividers(self):
        text = "## One\n\n---\n\nA door closes.\n\n```text\n***\n```"
        config, _ = resolve_document_config(text)
        metrics = CorpusAnalyzer(config).analyze_text(text)
        original = CorpusAnalyzer.measure_unit
        with patch.object(CorpusAnalyzer, "measure_unit", autospec=True, side_effect=original) as measure:
            actual = scene_report_for_display(text, config, premeasured_chapters=metrics.chapters)
        self.assertEqual(measure.call_count, 1)
        self.assertEqual(actual, scene_report(text, config))

    def test_counts_ranges_and_separate_group_baselines(self):
        report = api.scenes(TEXT, project_config=SETTINGS)
        self.assertEqual(report["meta"]["schema_version"], 1)
        self.assertEqual(report["meta"]["language"], "en")
        scenes = report["scenes"]["items"]
        self.assertEqual([s["id"] for s in scenes], ["1:1", "1:2", "2:1"])
        self.assertEqual([s["group"] for s in scenes], ["close", "close", "formal"])
        self.assertEqual(scenes[0]["targets"]["asl"]["position"], "within")
        self.assertEqual(scenes[0]["targets"]["hd_d"]["position"], "unavailable")
        self.assertIsNone(scenes[0]["features"]["hd_d"])
        self.assertIsNone(scenes[1]["features"]["sentence_cv"])
        self.assertNotIn("hd_d", scenes[2]["standard_errors"])
        self.assertGreaterEqual(scenes[2]["features"]["hd_d"], 0)
        self.assertLessEqual(scenes[2]["features"]["hd_d"], 1)
        baseline = report["scenes"]["baselines"]
        self.assertEqual(baseline["close"]["asl"]["n"], 2)
        self.assertIsNone(baseline["formal"]["asl"]["median"])
        self.assertNotIn("body", json.dumps(report))
        self.assertNotIn("A report was written", json.dumps(report))

    def test_empty_unassigned_and_invalid_project_targets(self):
        self.assertEqual(api.scenes("", project_config={})["scenes"]["items"], [])
        default = api.scenes(TEXT, project_config={})["scenes"]
        self.assertTrue(all(s["group"] is None for s in default["items"]))
        for settings in (
            {"assignments": {"9:1": "close"}, "groups": {"close": {}}},
            {"groups": {"a": {"targets": {"hd_d": [28, 48]}}}},
            {"groups": {"a": {"targets": {"asl": [6, 2]}}}},
            {"groups": {"a": {"targets": {"feat_filter": [1, 2]}}}},
            {"groups": {"a": {"targets": {"asl": [True, 2]}}}},
        ):
            with self.subTest(settings=settings), self.assertRaises(ValueError):
                api.scenes(TEXT, project_config={"scene_analysis": settings})

    def test_cli_config_and_dashboard_are_wired(self):
        with tempfile.TemporaryDirectory() as root:
            manuscript = Path(root, "sample.md")
            manuscript.write_text(TEXT, encoding="utf-8")
            Path(root, "lixity.toml").write_text(
                '[scene_analysis.assignments]\n"1:1" = "close"\n'
                '[scene_analysis.groups.close.targets]\nasl = [2, 6]\n',
                encoding="utf-8",
            )
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.assertEqual(main(["scenes", str(manuscript), "--json"]), 0)
            self.assertEqual(json.loads(out.getvalue())["scenes"]["items"][0]["group"], "close")
            html = api.dashboard(TEXT, project_config=SETTINGS)
            self.assertIn('id="scenes"', html)
            self.assertIn("formal", html)
            self.assertIn("Standard error", html)

    def test_language_and_configured_tokenizer_reused(self):
        result = api.scenes("## Eins\n\nIch sehe das Licht.\n\n***\n\nDas Haus wurde verkauft.",
                            language="de", project_config={}, word_regex=r"\b[A-ZÄÖÜ][a-zäöüß]+\b")
        self.assertEqual(result["meta"]["language"], "de")
        self.assertEqual([s["words"] for s in result["scenes"]["items"]], [2, 2])

    def test_actual_text_changes_and_shared_project_structure(self):
        settings = {"chapter_regex": r"(?m)^###\s+", "appendix_marker": "### Notes"}
        text = "### One\n\nA door shuts.\n\n### Two\n\n" + "The report was recorded. " * 25 + "\n\n### Notes\n\nIgnore this appendix."
        report = api.scenes(text, project_config=settings)["scenes"]
        self.assertEqual([s["chapter_title"] for s in report["items"]], ["One", "Two"])
        self.assertEqual([s["words"] for s in report["items"]], [3, 100])
        self.assertEqual(report["items"][0]["features"]["passive_density"], 0)
        self.assertGreater(report["items"][1]["features"]["passive_density"], 0)
        html = api.dashboard(text, project_config=settings)
        self.assertNotIn("Ignore this appendix", html)
        self.assertTrue('id="ch-2"' in html, "The dashboard must use the configured chapter boundaries")

    def test_unit_engine_matches_full_analysis_without_corpus_recalculation(self):
        prose = "A window opens. The report was recorded. " * 15
        config, _ = resolve_document_config(prose)
        analyzer = CorpusAnalyzer(config)
        unit = analyzer.measure_unit(prose)
        full = analyzer.analyze_text("## Example\n\n" + prose).chapters[0]
        for field, _, _ in FEATURES:
            with self.subTest(field=field):
                self.assertEqual(getattr(unit, field), getattr(full, field))
        self.assertEqual(unit.style_se, full.style_se)

    def test_headerless_prose_keeps_every_paragraph_and_original_anchors(self):
        cases = (
            ("A door closes. The report was recorded.", "", [1]),
            ("A door closes.\n\nThe report was recorded.", "", [1, 3]),
            ("# Sample\n\nA door closes.\n\nThe report was recorded.", "Sample", [3, 5]),
            ("\n<!-- Draft\nkept -->\n# Sample\n\nA door closes.\n\nThe report was recorded.",
             "Sample", [6, 8]),
        )
        for text, title, lines in cases:
            with self.subTest(text=text):
                metrics = api.analyze(text)["metrics"]
                self.assertEqual(metrics["tokens"], 7)
                self.assertEqual([(chapter["num"], chapter["title"], chapter["words"])
                                  for chapter in metrics["chapters"]], [(1, title, 7)])
                profile = api.profile(text, project_config={})
                self.assertEqual([(chapter["num"], chapter["title"], chapter["words"])
                                  for chapter in profile["chapters"]], [(1, title, 7)])
                self.assertEqual([paragraph["start_line"] for paragraph in profile["paragraphs"]], lines)
                self.assertEqual([paragraph["chapter_num"] for paragraph in profile["paragraphs"]], [1] * len(lines))
                self.assertEqual(profile["paragraphs"][0]["words"], 7 if len(lines) == 1 else 3)
                scenes = api.scenes(text)["scenes"]["items"]
                self.assertEqual([(scene["id"], scene["chapter_title"], scene["words"])
                                  for scene in scenes], [("1:1", title, 7)])
                self.assertEqual(api.pacing(text)["pacing"]["scenes"], 1)

    def test_headerless_scene_dividers_and_wordless_inputs_share_segmentation(self):
        text = "A door closes.\n\n---\n\nThe report was recorded."
        self.assertEqual([(scene["id"], scene["words"])
                          for scene in api.scenes(text)["scenes"]["items"]], [("1:1", 3), ("1:2", 4)])
        self.assertEqual(api.pacing(text)["pacing"]["scenes"], 2)
        self.assertEqual([paragraph["start_line"]
                          for paragraph in api.profile(text, project_config={})["paragraphs"]], [1, 5])
        for text in ("", "# Sample", "<!-- Draft. -->\n!!!"):
            with self.subTest(text=text):
                self.assertEqual(api.analyze(text)["metrics"]["chapters"], [])
                self.assertEqual(api.profile(text, project_config={})["chapters"], [])
                self.assertEqual(api.scenes(text)["scenes"]["items"], [])

    def test_implicit_chapter_does_not_admit_chaptered_frontmatter(self):
        for settings, heading in (({}, "## One"), ({"chapter_regex": r"(?m)^CHAPTER\s+"}, "CHAPTER One")):
            text = "# Sample\n\nA preface remains outside chapters.\n\n" + heading + "\n\nA door closes."
            with self.subTest(settings=settings):
                self.assertEqual([(scene["chapter_title"], scene["words"])
                                  for scene in api.scenes(text, project_config=settings)["scenes"]["items"]], [("One", 3)])
                profile = api.profile(text, project_config=settings)
                self.assertEqual([paragraph["words"] for paragraph in profile["paragraphs"]], [3])
                self.assertEqual(profile["paragraphs"][0]["start_line"], 7)

    def test_full_heading_patterns_preserve_prose_titles_and_anchors(self):
        cases = (
            (r"(?m)^CHAPTER\s+", "CHAPTER ", ["One", "Two"]),
            (r"(?m)^CHAPTER [^\r\n]+$", "CHAPTER ", ["CHAPTER One", "CHAPTER Two"]),
            (r"(?m)^CHAPTER [^\r\n]+\r?\n", "CHAPTER ", ["CHAPTER One", "CHAPTER Two"]),
            (r"(?m)^##[^\r\n]*$", "## ", ["One", "Two"]),
        )
        for newline in ("\n", "\r\n"):
            for pattern, marker, titles in cases:
                text = newline.join((marker + "One", "", "A door closes.", "", marker + "Two", "", "The report was recorded."))
                with self.subTest(pattern=pattern, newline=newline):
                    settings = {"chapter_regex": pattern}
                    metrics = api.analyze(text, project_config=settings)["metrics"]
                    self.assertEqual(metrics["tokens"], 7)
                    self.assertEqual([chapter["words"] for chapter in metrics["chapters"]], [3, 4])
                    scenes = api.scenes(text, project_config=settings)["scenes"]["items"]
                    self.assertEqual([(scene["id"], scene["chapter_title"], scene["words"])
                                      for scene in scenes], [("1:1", titles[0], 3), ("2:1", titles[1], 4)])
                    profile = api.profile(text, project_config=settings)
                    self.assertEqual([(chapter["title"], chapter["words"]) for chapter in profile["chapters"]],
                                     [(titles[0], 3), (titles[1], 4)])
                    self.assertEqual([paragraph["start_line"] for paragraph in profile["paragraphs"]], [3, 7])

    def test_empty_heading_cannot_consume_first_prose_line(self):
        for newline in ("\n", "\r\n"):
            text = newline.join(("## ", "", "A door closes.", "", "The report was recorded."))
            with self.subTest(newline=newline):
                scenes = api.scenes(text)["scenes"]["items"]
                self.assertEqual([(scene["chapter_title"], scene["words"]) for scene in scenes], [("", 7)])
                profile = api.profile(text, project_config={})
                self.assertEqual([paragraph["start_line"] for paragraph in profile["paragraphs"]], [3, 5])
                self.assertEqual(sum(paragraph["words"] for paragraph in profile["paragraphs"]), 7)

    def test_invalid_assignment_preserves_dashboard_and_is_visible(self):
        settings = {"scene_analysis": {"assignments": {"5:1": "voice"}, "groups": {"voice": {}}}}
        html = api.dashboard(TEXT, project_config=settings)
        self.assertTrue("Scene assignments no longer match" in html)
        self.assertTrue('id="ch-1"' in html)

    def test_custom_chapter_markers_end_list_and_footnote_continuations(self):
        settings = {"chapter_regex": r"(?m)^CHAPTER\s+"}
        for continuation in ("- A door closes.", "[^note]: A source note."):
            text = "CHAPTER One\n\nFirst prose remains.\n\n" + continuation + "\nCHAPTER Two\n\nA report follows."
            with self.subTest(continuation=continuation):
                profile = api.profile(text, project_config=settings)
                self.assertEqual([(c["num"], c["title"]) for c in profile["chapters"]],
                                 [(1, "One"), (2, "Two")])
                self.assertEqual(profile["paragraphs"][-1]["chapter_num"], 2)
                self.assertEqual(profile["paragraphs"][-1]["start_line"], 8)

    def test_accepted_chapter_numbers_align_after_empty_units_and_quotes(self):
        text = ("## Empty\n\n## Comment\n\n<!-- Reserved. -->\n\n## Symbols\n\n!!!\n\n"
                "## Quotation\n\n> A source speaks.\n\n## Prose\n\nA door closes.")
        self.assertEqual([(c["num"], c["title"]) for c in api.analyze(text)["metrics"]["chapters"]],
                         [(1, "Quotation"), (2, "Prose")])
        profile = api.profile(text, project_config={})
        self.assertEqual([(c["num"], c["title"]) for c in profile["chapters"]], [(2, "Prose")])
        self.assertEqual([p["chapter_num"] for p in profile["paragraphs"]], [2])
        self.assertEqual([(s["id"], s["chapter_title"]) for s in api.scenes(text)["scenes"]["items"]],
                         [("1:1", "Quotation"), ("2:1", "Prose")])
        self.assertEqual([(c["chapter_num"], c["title"]) for c in api.pacing(text)["pacing"]["chapter_list"]],
                         [(1, "Quotation"), (2, "Prose")])

    def test_accepted_chapters_use_the_configured_word_tokenizer(self):
        settings = {"word_regex": r"\b[A-Z][a-z]+\b"}
        text = "## Lower\n\nall lower words.\n\n## Upper\n\nDoor closes."
        self.assertEqual([(c["num"], c["title"]) for c in api.analyze(text, project_config=settings)["metrics"]["chapters"]],
                         [(1, "Upper")])
        self.assertEqual([(c["num"], c["title"]) for c in api.profile(text, project_config=settings)["chapters"]],
                         [(1, "Upper")])
        self.assertEqual([s["id"] for s in api.scenes(text, project_config=settings)["scenes"]["items"]], ["1:1"])

    def test_scene_dividers_inside_fences_do_not_split_either_report(self):
        for fenced in ("````md\n---\n```\n***\n````", "   ~~~text\n___\n   ~~~"):
            text = "## One\n\nA door closes.\n\n" + fenced + "\n\nA report follows.\n\n---\n\nA return follows."
            with self.subTest(fenced=fenced):
                scenes = api.scenes(text)["scenes"]
                self.assertEqual([s["id"] for s in scenes["items"]], ["1:1", "1:2"])
                self.assertEqual(scenes["explicit_scene_breaks"], 1)
                pacing = api.pacing(text)["pacing"]
                self.assertEqual(pacing["scenes"], 2)
                self.assertEqual(pacing["explicit_scene_breaks"], 1)

    def test_unclosed_fence_keeps_remaining_dividers_inside_one_scene(self):
        text = "## One\n\nA door closes.\n\n```text\n---\n\nA stored example.\n\n***"
        scenes = api.scenes(text)["scenes"]
        self.assertEqual([s["id"] for s in scenes["items"]], ["1:1"])
        self.assertEqual(scenes["explicit_scene_breaks"], 0)
        self.assertEqual(api.pacing(text)["pacing"]["explicit_scene_breaks"], 0)

    def test_toml_compatible_open_bounds_and_strict_engine_units(self):
        settings = {"scene_analysis": {"assignments": {"1:1": "voice"}, "groups": {
            "voice": {"targets": {"asl": {"upper": 2}, "hd_d": {"lower": 0.2}}},
        }}}
        item = api.scenes(TEXT, project_config=settings)["scenes"]["items"][0]
        self.assertEqual(item["targets"]["asl"]["position"], "above")
        self.assertEqual(item["targets"]["hd_d"]["position"], "unavailable")


if __name__ == "__main__":
    unittest.main()
