"""Tests for configured manuscript terms/props and read-only occurrence derivation."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from lixity.cli import main as cli_main
from lixity.config import read_explicit_project_config
from lixity.research import api
from lixity.research.repository import Repository
from lixity.site_export import prepare_site


class ManuscriptTermsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir()
        self.manuscript = self.root / "manuscript.md"
        self.manuscript.write_text(
            "## Chapter 1: Arrival\n\n"
            "Mira carried the brass compass and the old pocket-watch into the harbour.\n\n"
            "She walked down the Straße toward the lantern house.\n\n"
            "## Chapter 2: Departure\n\n"
            "At dawn the mariner's dial and the old pocket-watch lay on the chart table.\n",
            encoding="utf-8",
        )
        api.init(self.root, title="Synthetic Terms Project")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_term_profiles_persist_in_config_without_revising_archive(self) -> None:
        before_snapshot = Repository(self.root).snapshot()
        saved = api.save_term_profile(
            self.root,
            "brass compass",
            aliases=["mariner's dial"],
            scoped_alternatives=[
                {"term": "old pocket-watch", "chapters": [1], "note": "Before repair"}
            ],
        )
        self.assertEqual(saved["schema_version"], "research-terms-config-local/1")
        self.assertEqual([item["term"] for item in saved["terms"]], ["brass compass"])
        after_snapshot = Repository(self.root).snapshot()
        self.assertEqual(after_snapshot.digest, before_snapshot.digest)
        self.assertEqual(len(after_snapshot.revisions), len(before_snapshot.revisions))

        raw_cfg = read_explicit_project_config(self.root)
        self.assertIn("brass compass", raw_cfg["terms"])

        report = api.review_manuscript_terms(self.root, self.manuscript)
        self.assertEqual(report["schema_version"], "research-manuscript-terms-local/1")
        self.assertEqual(report["term_count"], 1)
        self.assertEqual(report["occurrence_count"], 4)

        by_chapter = {
            (occ["chapter_num"], occ["matched_form"]): occ
            for occ in report["occurrences"]
        }
        ch1_pref = by_chapter[(1, "brass compass")]
        self.assertEqual(ch1_pref["variant_kind"], "preferred")
        self.assertEqual(ch1_pref["flags"], [])

        ch1_scoped = by_chapter[(1, "old pocket-watch")]
        self.assertEqual(ch1_scoped["variant_kind"], "scoped_alternative")
        self.assertTrue(ch1_scoped["expected_in_chapter"])
        self.assertEqual(ch1_scoped["flags"], [])

        ch2_alias = by_chapter[(2, "mariner's dial")]
        self.assertEqual(ch2_alias["variant_kind"], "alias")
        self.assertEqual(ch2_alias["flags"], [])

        ch2_out = by_chapter[(2, "old pocket-watch")]
        self.assertEqual(ch2_out["variant_kind"], "out_of_scope_alternative")
        self.assertFalse(ch2_out["expected_in_chapter"])
        self.assertIn("out_of_scope_alternative", ch2_out["flags"])

        deleted = api.delete_term_profile(self.root, "brass compass")
        self.assertEqual(deleted["terms"], [])

    def test_overlapping_terms_and_unicode_ambiguity_are_explicitly_flagged(self) -> None:
        api.set_term_profiles(
            self.root,
            {
                "brass compass": {"aliases": []},
                "compass": {"aliases": []},
                "STRASSE": {"aliases": []},
            },
        )
        report = api.review_manuscript_terms(self.root, self.manuscript)
        occurrences = report["occurrences"]

        overlaps = [occ for occ in occurrences if "overlapping_term" in occ["flags"]]
        self.assertEqual(len(overlaps), 2)
        self.assertEqual({occ["term"] for occ in overlaps}, {"brass compass", "compass"})
        for occ in overlaps:
            self.assertTrue(occ["overlapping_terms"])

        unicode_flagged = [occ for occ in occurrences if "unicode_ambiguity" in occ["flags"]]
        self.assertEqual(len(unicode_flagged), 1)
        self.assertEqual(unicode_flagged[0]["term"], "STRASSE")
        self.assertEqual(unicode_flagged[0]["anchor"]["quote"], "Straße")
        self.assertIn("unicode_casefold_length", unicode_flagged[0]["ambiguity_reasons"])

    def test_cli_terms_and_site_export_include_manuscript_terms(self) -> None:
        set_buf = io.StringIO()
        with redirect_stdout(set_buf):
            code = cli_main(
                [
                    "research",
                    "terms",
                    "--project",
                    str(self.root),
                    "--set-term",
                    "brass compass",
                    "--aliases",
                    "mariner's dial",
                    "--scoped-alternative",
                    "old pocket-watch:1",
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        set_payload = json.loads(set_buf.getvalue())
        self.assertEqual(set_payload["schema_version"], "research-terms-config-local/1")

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli_main(
                [
                    "research",
                    "terms",
                    "--project",
                    str(self.root),
                    "--manuscript",
                    str(self.manuscript),
                    "--format",
                    "json",
                ]
            )
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["occurrence_count"], 4)
        self.assertEqual(payload["out_of_scope_count"], 1)

        text_buf = io.StringIO()
        with redirect_stdout(text_buf):
            code = cli_main(
                [
                    "research",
                    "terms",
                    "--project",
                    str(self.root),
                    "--manuscript",
                    str(self.manuscript),
                    "--format",
                    "text",
                ]
            )
        self.assertEqual(code, 0)
        self.assertIn("brass compass", text_buf.getvalue())

        bundle = prepare_site(self.root, manuscript=self.manuscript, include_research=True)
        site_html = bundle.files["index.html"].decode("utf-8")
        self.assertIn("/api/research/manuscript-terms", site_html)


if __name__ == "__main__":
    unittest.main()
