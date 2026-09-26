"""Research adapters reuse the core without turning textual signals into claims."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity import api as core
from lixity import pipeline
from lixity.markdown_parser import parse_markdown_blocks
from lixity.research import api
from lixity.research.repository import ResearchError


class TestResearchAnalysis(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.file = self.root / "source.md"
        self.text = "## Chapter 1\r\n\r\nThe room is quiet. She reads a book.\r\n\r\n## Chapter 2\r\n\r\nThey walked through the town yesterday.\r\n"
        self.file.write_bytes(self.text.encode())
        api.init(self.project, title="Synthetic research")

    def ingest(self, **kwargs):
        return api.ingest(self.project, self.file, allow_retention=True, **kwargs)

    def test_context_refresh_pins_old_citation_without_changing_bytes(self):
        first = self.ingest(context={"created_period": "c. 1924", "depicted_period": "before 1900",
                                     "perspective": "municipal account", "is_translation": False})
        api.reindex(self.project)
        passage = api.search(self.project, "room")["hits"][0]["passage_id"]
        second = self.ingest(source_id=first["source_id"], context={"created_period": "1925?"})
        self.assertFalse(second["unchanged"])
        self.assertNotEqual(first["source_version_id"], second["source_version_id"])
        old = api.cite(self.project, passage)
        self.assertEqual(old["context"]["created_period"], "c. 1924")
        self.assertFalse(old["context"]["is_translation"])
        self.assertEqual(old["verification"], "unreviewed")
        latest = api.analyze_source(self.project, first["source_id"])
        self.assertEqual(latest["provenance"]["context"]["created_period"], "1925?")
        self.assertEqual(old["source_sha256"], latest["provenance"]["source_sha256"])
        self.assertIsNone(latest["provenance"]["context"]["perspective"])
        self.assertTrue(self.ingest(source_id=first["source_id"])["unchanged"])
        pinned = api.analyze_source(self.project, first["source_id"], version_id=first["source_version_id"])
        self.assertEqual(pinned["provenance"]["context"], old["context"])

    def test_adapter_matches_core_once_and_never_reads_ambient_config(self):
        source = self.ingest()
        before = {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()}
        with patch("lixity.config.load_project_config", side_effect=AssertionError("ambient config")), \
                patch("lixity.pipeline.analyze_document", wraps=pipeline.analyze_document) as analyze:
            result = api.analyze_source(self.project, source["source_id"], thresholds={"fdr_method": "by"})
        self.assertEqual(analyze.call_count, 1)
        self.assertEqual(result["metrics"], core.analyze(self.text)["metrics"])
        self.assertEqual(result["style"], core.fingerprint(self.text, project_config={}, fdr_method="by"))
        self.assertEqual(result["meta"]["schema_version"], 2)
        self.assertEqual(result["style"]["meta"]["schema_version"], 4)
        self.assertEqual(result["interpretation"]["scope"], "source_internal")
        self.assertEqual(result["interpretation"]["context_status"], "user_supplied_unverified")
        self.assertEqual(before, {path: path.read_bytes() for path in self.project.rglob("*") if path.is_file()})
        self.assertFalse((self.project / ".lixity/research/catalogue.sqlite3").exists())

    def test_paragraph_evidence_resolves_exact_unicode_crlf_after_comments(self):
        self.text = "## Chapter 1\r\n<!-- hidden\r\ncomment -->\r\n\r\nCafé in Zürich.\r\n\r\nThe room is open.\r\n"
        self.file.write_bytes(self.text.encode())
        source = self.ingest()
        result = api.analyze_source(self.project, source["source_id"])
        paragraph = result["paragraphs"][0]
        self.assertEqual(paragraph["start_line"], 5)
        self.assertNotIn("text", paragraph)
        evidence = paragraph["evidence"]
        self.assertEqual(self.text[evidence["start"]:evidence["end"]], "Café in Zürich.\r\n")
        self.assertEqual(evidence["offset_unit"], "unicode_codepoint")
        self.assertEqual(len(evidence["passage_refs"]), 1)
        citation = api.cite(self.project, evidence["passage_refs"][0]["id"])
        self.assertEqual(citation["verbatim"], "Café in Zürich.")
        self.assertEqual(citation["source_version_id"], source["source_version_id"])

    def test_languages_use_existing_profiles_not_project_default(self):
        for language in ("en", "de", "fr", "es", "it", "pt", "nl", "generic"):
            with self.subTest(language=language):
                source = self.ingest(language=language)
                result = api.analyze_source(self.project, source["source_id"])
                self.assertEqual(result["meta"]["language"], language)
                self.assertEqual(result["metrics"], core.analyze(self.text, language)["metrics"])
                self.assertEqual(result["style"], core.fingerprint(self.text, language, project_config={}))

    def test_short_translation_reports_limits_without_inventing_calibration(self):
        self.file.write_text("A translated note.", encoding="utf-8")
        source = self.ingest(context={"is_translation": True, "original_language": "Historical variety"})
        result = api.analyze_source(self.project, source["source_id"])
        limits = result["interpretation"]["limitations"]
        self.assertIn("insufficient_chapters", limits)
        self.assertIn("translation", limits)
        self.assertIn("historical_language", limits)
        self.assertEqual(result["interpretation"]["baseline_coverage"]["estimable_features"], 0)
        self.assertEqual(result["style"]["fdr_flagged"], {})

    def test_invalid_context_and_thresholds_do_not_mutate_archive(self):
        from pydantic import ValidationError

        source = self.ingest()
        before = api.audit(self.project)["snapshot"]
        for context in ({"truth": 1}, {"is_translation": "yes"}, {"place": "x" * 501}):
            with self.subTest(context=context), self.assertRaises(ValidationError):
                self.ingest(source_id=source["source_id"], context=context)
        for thresholds in ({"min_chapters": 1}, {"fdr_q": float("nan")}, {"fdr_q": 2},
                           {"unknown": 2}, {"z_mild": -1}, {"z_mild": 4, "z_strong": 3}):
            with self.subTest(thresholds=thresholds), self.assertRaises(ValueError):
                api.analyze_source(self.project, source["source_id"], thresholds=thresholds)
        self.assertEqual(api.audit(self.project)["snapshot"], before)

    def test_wrong_source_version_and_tampered_bytes_fail_closed(self):
        first = self.ingest()
        second = self.ingest()
        with self.assertRaises(ResearchError):
            api.analyze_source(self.project, first["source_id"], version_id=second["source_version_id"])
        next((self.project / "research/blobs").iterdir()).write_bytes(b"tampered")
        with self.assertRaises(ResearchError):
            api.analyze_source(self.project, first["source_id"])

    def test_dashboard_uses_shared_components_with_escaped_localized_context(self):
        source = self.ingest(language="de", context={"perspective": '<img src=x onerror="alert(1)">'})
        html = api.source_dashboard(self.project, source["source_id"])
        self.assertIn('id="document-context"', html)
        self.assertIn("Quellenkontext", html)
        self.assertIn("&lt;img", html)
        self.assertNotIn('<img src=x', html)
        self.assertIn('id="license-terms"', html)
        self.assertIn('id="matrix"', html)
        self.assertNotIn('id="controls"', html)
        self.assertIn(source["source_version_id"], html)

    def test_cli_analyze_context_ingest_and_dashboard_stdout(self):
        from lixity.cli import main

        context_file = self.root / "context.json"
        context_file.write_text('{"genre":"diary","created_period":"1924?"}', encoding="utf-8")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["research", "ingest", "--project", str(self.project), "--file", str(self.file),
                         "--context", str(context_file), "--allow-retention"])
        self.assertEqual(code, 0)
        source = json.loads(stdout.getvalue())["source_id"]
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["research", "analyze", "--project", str(self.project), "--source-id", source])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(stdout.getvalue())["provenance"]["context"]["genre"], "diary")
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["research", "dashboard", "--project", str(self.project), "--source-id", source])
        self.assertEqual(code, 0)
        self.assertTrue(stdout.getvalue().startswith("<!DOCTYPE html>"))

    def test_markdown_comments_preserve_original_line_anchors(self):
        blocks = parse_markdown_blocks("# Chapter 1\n<!-- first\nsecond -->\n\nA visible paragraph.\n")
        self.assertEqual(blocks[-1]["start_line"], 5)
        self.assertEqual(blocks[-1]["end_line"], 5)
        self.assertEqual(blocks[-1]["text"], "A visible paragraph.")

    def test_compare_source_to_manuscript_grounding_and_keyness(self):
        source_doc = self.root / "climbing_history.md"
        source_doc.write_text(
            "The expedition reached the high alpine granite ridge. "
            "Rope and ice axes were essential during the stormy ascent. "
            "The glacier was treacherous with deep crevasses and falling rocks. "
            "Climbing higher required great endurance and steady footing.\n",
            encoding="utf-8",
        )
        source = api.ingest(self.project, source_doc, allow_retention=True)

        manuscript_file = self.root / "novel.md"
        manuscript_file.write_text(
            "## Chapter 1: The Ascent\n\n"
            "The guide checked the climbing rope and secured the ice axes. "
            "They climbed toward the cold glacier under gray skies. "
            "Each step on the granite ridge was dangerous.\n\n"
            "## Chapter 2: The Café\n\n"
            "The waiter served warm coffee and fresh bread. "
            "She read the morning newspaper quietly by the window. "
            "Outside, cars and bicycles passed along the crowded street.\n",
            encoding="utf-8",
        )

        res = api.compare_source(self.project, source["source_id"], manuscript_file)
        self.assertEqual(res["schema_version"], "research-comparison-local/1")
        self.assertEqual(res["provenance"]["source_id"], source["source_id"])
        self.assertGreater(res["summary"]["jaccard_similarity"], 0.0)
        self.assertGreater(res["summary"]["shared_types"], 0)

        # Shared terms
        shared_words = [item["word"] for item in res["lexical_overlap"]["top_shared_terms"]]
        self.assertIn("climbing", shared_words)
        self.assertIn("glacier", shared_words)
        self.assertIn("granite", shared_words)
        self.assertIn("rope", shared_words)

        # Chapter grounding
        grounding = res["chapter_grounding"]
        self.assertEqual(len(grounding), 2)
        # Chapter 1 should have high grounding density
        self.assertGreater(grounding[0]["overlap_types"], 0)
        self.assertGreater(grounding[0]["grounding_density"], 0.0)
        # Chapter 2 should have 0 or much lower grounding density
        self.assertLess(grounding[1]["grounding_density"], grounding[0]["grounding_density"])

        # Register contrast
        self.assertIn("asl", res["register_contrast"])
        self.assertIn("guiraud_r", res["register_contrast"])
        self.assertIn("dialogue_pct", res["register_contrast"])

    def test_compare_source_cli_and_validation(self):
        from lixity.cli import main

        source_doc = self.root / "expedition.md"
        source_doc.write_text("Alpine glacier climbing expedition notes.", encoding="utf-8")
        source = api.ingest(self.project, source_doc, allow_retention=True)

        ms_file = self.root / "book.md"
        ms_file.write_text("# Chapter 1\n\nGlacier climbing expedition.", encoding="utf-8")

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main([
                "research", "compare",
                "--project", str(self.project),
                "--source-id", source["source_id"],
                "--manuscript", str(ms_file),
            ])
        self.assertEqual(code, 0)
        data = json.loads(stdout.getvalue())
        self.assertEqual(data["schema_version"], "research-comparison-local/1")

        # Invalid top_n
        with self.assertRaises(ValueError):
            api.compare_source(self.project, source["source_id"], ms_file, top_n=0)

        # Non-existent manuscript path
        with self.assertRaises(ResearchError):
            api.compare_source(self.project, source["source_id"], "nonexistent_file.md")

        # Withdrawn source fails
        api.withdraw(self.project, source["source_id"], reason="testing withdrawal")
        with self.assertRaises(ResearchError):
            api.compare_source(self.project, source["source_id"], ms_file)

