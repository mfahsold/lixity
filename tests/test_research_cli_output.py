"""Human research output preserves machine contracts and treats metadata as data."""

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api, cli


class TestResearchCliOutput(unittest.TestCase):
    def parse(self, *arguments: str) -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        cli.configure(parser)
        return parser.parse_args(arguments)

    def capture(self, *arguments: str) -> tuple[int, str, str]:
        output, errors = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
            status = cli.run(self.parse(*arguments))
        return status, output.getvalue(), errors.getvalue()

    def source(self, number: int = 0) -> dict:
        return {
            "id": f"urn:uuid:00000000-0000-4000-8000-{number:012d}",
            "version_id": f"urn:uuid:10000000-0000-4000-8000-{number:012d}",
            "title": f"Synthetic source {number}", "language": "de", "sequence": 2,
            "passages": 3, "tags": ["harbour", "history"],
            "context": {"origin_url": "https://example.test/archive?item=7"},
        }

    def listing(self, count: int = 1) -> dict:
        return {
            "schema_version": "research-sources-local/1", "project_id": "urn:uuid:project",
            "project_title": "Synthetic archive", "project_language": "de",
            "sources": [self.source(number) for number in range(count)],
        }

    def test_default_and_explicit_json_preserve_exact_output(self):
        audit = {"ok": False, "records": 4, "snapshot": "a" * 64,
                 "errors": ["Synthetic invalid record"], "scope": "retained records"}
        detail = {**self.source(), "passages": [{"id": "urn:uuid:passage", "verbatim": "Synthetic text"}],
                  "text": "Synthetic text"}
        for command, name, result, extra in (
            ("sources", "list_sources", self.listing(), ()),
            ("sources", "get_source", detail, ("--source-id", self.source()["id"])),
            ("audit", "audit", audit, ()),
        ):
            with self.subTest(command=command, detail=bool(extra)), patch.object(api, name, return_value=result):
                for flags in ((), ("--format", "json")):
                    status, output, errors = self.capture(command, "--project", "/synthetic", *extra, *flags)
                    self.assertEqual(status, 1 if result.get("ok") is False else 0)
                    self.assertEqual(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
                    self.assertEqual(errors, "")

    def test_human_sources_show_verified_metadata_without_source_body(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic archive", language="de")
            source = Path(td) / "source.txt"
            source.write_text("Der Hafen lag still. Die Wache öffnete das Register.", encoding="utf-8")
            capture = api.ingest(project, source, title="Harbour record", allow_retention=True,
                                 context={"tags": ["harbour", "history"],
                                          "origin_url": "https://example.test/harbour"})
            version_id = api.get_source(project, capture["source_id"])["version_id"]
            for output_format in ("text", "md"):
                for extra in ((), ("--source-id", capture["source_id"])):
                    with self.subTest(format=output_format, detail=bool(extra)):
                        status, output, errors = self.capture("sources", "--project", str(project),
                                                             "--format", output_format, *extra)
                        self.assertEqual(status, 0)
                        self.assertEqual(errors, "")
                        for value in ("Harbour record", capture["source_id"], version_id,
                                      "Active", "harbour", "history", "https://example.test/harbour"):
                            self.assertIn(value, output)
                        self.assertNotIn("Der Hafen lag still", output)
                        self.assertIn("Passages", output)

    def test_hostile_titles_tags_and_controls_remain_inert(self):
        listing = self.listing()
        title = '[red]Title[/red] | <script>alert(1)</script>\x1b[31m\x1b]52;c;secret\x07\u202e'
        listing["project_title"] = title
        listing["sources"][0]["title"] = title
        listing["sources"][0]["tags"] = ['[link=javascript:alert(1)]tag[/link]\nNext']
        with patch.object(api, "list_sources", return_value=listing):
            _, plain, _ = self.capture("sources", "--project", "/synthetic", "--format", "text")
            self.assertIn('[red]Title[/red] | <script>alert(1)</script>', plain)
            self.assertIn(r"\x1b[31m", plain)
            self.assertIn(r"\u202e", plain)
            self.assertNotIn("\x1b", plain)
            self.assertNotIn("\x07", plain)
            _, markdown, _ = self.capture("sources", "--project", "/synthetic", "--format", "md")
            self.assertIn(r"\[red\]Title\[/red\]", markdown)
            self.assertIn("&lt;script&gt;", markdown)
            self.assertIn(r"\|", markdown)
            self.assertNotIn("<script>", markdown)

    def test_human_listing_is_bounded_and_reports_total_and_offset(self):
        listing = self.listing(500)
        with patch.object(api, "list_sources", return_value=listing):
            status, output, _ = self.capture("sources", "--project", "/synthetic", "--format", "text",
                                            "--limit", "2", "--offset", "497")
            self.assertEqual(status, 0)
            self.assertIn("498–499 of 500", output)
            self.assertIn("--offset 499", output)
            self.assertIn(self.source(497)["id"], output)
            self.assertIn(self.source(498)["id"], output)
            self.assertNotIn(self.source(496)["id"], output)
            self.assertNotIn(self.source(499)["id"], output)
            self.assertLess(len(output), 3000)
            _, default_page, _ = self.capture("sources", "--project", "/synthetic", "--format", "text")
            self.assertIn("1–50 of 500", default_page)
            self.assertNotIn(self.source(50)["id"], default_page)
            _, beyond, _ = self.capture("sources", "--project", "/synthetic", "--format", "md", "--offset", "500")
            self.assertIn("No sources at offset 500", beyond)

    def test_invalid_paging_and_json_pager_do_not_call_archive(self):
        with patch.object(api, "list_sources") as listing, patch.object(api, "audit") as audit:
            for arguments in (("sources", "--limit", "1"), ("sources", "--offset", "1"),
                              ("sources", "--pager"), ("audit", "--pager"),
                              ("sources", "--source-id", "urn:uuid:source", "--format", "text", "--limit", "1")):
                with self.subTest(arguments=arguments):
                    command, *flags = arguments
                    status, output, errors = self.capture(command, "--project", "/synthetic", *flags)
                    self.assertEqual(status, 2)
                    self.assertEqual(output, "")
                    self.assertTrue(errors)
            listing.assert_not_called()
            audit.assert_not_called()
        for flags in (("--limit", "0"), ("--limit", "101"), ("--offset", "-1")):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
                self.parse("sources", "--project", "/synthetic", "--format", "text", *flags)
            self.assertEqual(error.exception.code, 2)

    def test_pager_is_opt_in_and_never_starts_for_pipes(self):
        from rich.console import Console

        with patch.object(api, "list_sources", return_value=self.listing()), patch.object(Console, "pager") as pager:
            for output_format in ("text", "md"):
                _, direct, _ = self.capture("sources", "--project", "/synthetic", "--format", output_format)
                _, requested, _ = self.capture("sources", "--project", "/synthetic", "--format", output_format, "--pager")
                self.assertEqual(direct, requested)
            pager.assert_not_called()

    def test_explicit_interactive_pager_uses_plain_rich_output(self):
        from rich.console import Console

        class Terminal(io.StringIO):
            def isatty(self):
                return True

        with patch.object(api, "list_sources", return_value=self.listing()), \
                patch.object(Console, "pager", return_value=contextlib.nullcontext()) as pager, \
                patch("sys.stdin", Terminal()), patch("sys.stdout", Terminal()):
            self.assertEqual(cli.run(self.parse("sources", "--project", "/synthetic", "--format", "text")), 0)
            pager.assert_not_called()
            self.assertEqual(cli.run(self.parse("sources", "--project", "/synthetic", "--format", "text", "--pager")), 0)
            pager.assert_called_once_with(styles=False, links=False)

    def test_failed_audit_summary_is_actionable_bounded_and_keeps_exit_one(self):
        result = {"ok": False, "records": 14875, "snapshot": "a" * 64,
                  "scope": "retained records and citations; not factual accuracy or index freshness",
                  "errors": [f"Invalid synthetic record {number} \x1b[31m" for number in range(25)]}
        with patch.object(api, "audit", return_value=result):
            for output_format in ("text", "md"):
                status, output, errors = self.capture("audit", "--project", "/synthetic", "--format", output_format)
                self.assertEqual(status, 1)
                self.assertEqual(errors, "")
                for value in ("FAILED", "14875", "a" * 64, "25", "not factual accuracy", "verified backup", "--format json"):
                    self.assertIn(value, output)
                self.assertIn("Invalid synthetic record 19", output)
                self.assertNotIn("Invalid synthetic record 20", output)
                self.assertNotIn("\x1b", output)

    def test_empty_listing_and_successful_audit_explain_their_scope(self):
        with patch.object(api, "list_sources", return_value=self.listing(0)):
            self.assertIn("No active sources", self.capture("sources", "--project", "/synthetic", "--format", "text")[1])
        with patch.object(api, "audit", return_value={"ok": True, "records": 1, "snapshot": "b" * 64,
                                                     "errors": [], "scope": "not factual accuracy or index freshness"}):
            status, output, errors = self.capture("audit", "--project", "/synthetic", "--format", "text")
            self.assertEqual(status, 0)
            self.assertEqual(errors, "")
            self.assertIn("PASSED", output)
            self.assertIn("Findings: 0", output)
            self.assertIn("not factual accuracy or index freshness", output)

    def test_batch_cli_previews_then_requires_an_explicit_snapshot_to_apply(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic group review")
            identifiers = [api.create_dossier(project, f"Note {i}", "Original.")["dossier_id"] for i in range(2)]
            operations = [{"kind": "dossier", "id": identifier, "expected_revision": 1,
                           "changes": {"body": f"Reviewed note {i}."}, "change_kind": "correction",
                           "reason": "Reviewed together."} for i, identifier in enumerate(identifiers)]
            batch_file = Path(td) / "changes.json"
            batch_file.write_text(json.dumps(operations), encoding="utf-8")
            before = api.audit(project)["snapshot"]
            status, output, errors = self.capture("revise-batch", "--project", str(project), "--file", str(batch_file))
            self.assertEqual((status, errors), (0, ""))
            preview = json.loads(output)
            self.assertEqual(preview["snapshot"], before)
            self.assertEqual(api.audit(project)["snapshot"], before)
            batch_file.write_text(output, encoding="utf-8")
            for flags in (("--apply",), ("--expected-snapshot", before), ("--expected-snapshot", "")):
                status, output, errors = self.capture("revise-batch", "--project", str(project),
                                                      "--file", str(batch_file), *flags)
                self.assertEqual(status, 2)
                self.assertEqual(output, "")
                self.assertIn("--apply", errors)
                self.assertEqual(api.audit(project)["snapshot"], before)
            status, output, errors = self.capture("revise-batch", "--project", str(project),
                "--file", str(batch_file), "--apply", "--expected-snapshot", before, "--actor", "reviewing-author")
            self.assertEqual((status, errors), (0, ""))
            self.assertEqual(len(json.loads(output)["records"]), 2)
            for identifier in identifiers:
                record = api.get_record(project, "dossier", identifier)["record"]
                self.assertEqual(record["revision"], 2)
                self.assertEqual(record["created_by"], "reviewing-author")
            status, output, errors = self.capture("revise-batch", "--project", str(project),
                "--file", str(batch_file), "--apply", "--expected-snapshot", before)
            self.assertEqual(status, 1)
            self.assertEqual(output, "")
            self.assertTrue(errors)

    def test_batch_cli_rejects_other_json_envelopes_without_calling_revision_api(self):
        with tempfile.TemporaryDirectory() as td, patch.object(api, "prepare_record_revisions") as prepare:
            path = Path(td) / "changes.json"
            for payload in ({"operations": []}, {"schema_version": "other/1", "operations": []}, "instructions"):
                with self.subTest(payload=payload):
                    path.write_text(json.dumps(payload), encoding="utf-8")
                    status, output, errors = self.capture("revise-batch", "--project", "/synthetic", "--file", str(path))
                    self.assertEqual(status, 1)
                    self.assertEqual(output, "")
                    self.assertIn("operations", errors)
            prepare.assert_not_called()

    def editorial_results(self) -> tuple[dict, dict]:
        impact = {"schema_version": "research-decision-impact-local/1", "snapshot": "a" * 64,
                  "scope": "Explicit associations and revision ordering; human review only.",
                  "decision": {"id": "decision-1", "title": "Review the date", "revision": 2}, "unlinked": False,
                  "dossiers": [{"id": "dossier-1", "title": "Opening date", "current_revision": 3,
                                "pinned_revisions": [1], "sections": ["Evidence", "Uncertainty"],
                                "flags": ["stale_dossier_pin"],
                                "links": [{"via": "claim", "pinned_revision": 1, "claim_id": "claim-1",
                                           "claim_revision": 2, "claim_current_revision": 3}]}]}
        review = {"schema_version": "research-editorial-review-local/1", "snapshot": "a" * 64,
                  "scope": impact["scope"], "decision_count": 1, "candidate_count": 1,
                  "candidates": [{"decision_id": "decision-1", "title": "Review the date", "decision_revision": 2,
                                  "dossier_id": "dossier-1", "dossier_title": "Opening date", "current_revision": 3,
                                  "pinned_revisions": [1], "sections": ["Evidence", "Uncertainty"],
                                  "flags": ["stale_dossier_pin"]}]}
        return impact, review

    def test_editorial_commands_default_to_readable_text_and_preserve_explicit_json(self):
        impact, review = self.editorial_results()
        for command, name, result, flags in (("decision-impact", "decision_impact", impact, ("--decision-id", "decision-1")),
                                            ("review", "editorial_review", review, ())):
            with self.subTest(command=command), patch.object(api, name, return_value=result) as report:
                for output_format in (None, "text", "md"):
                    format_flags = ("--format", output_format) if output_format else ()
                    status, output, errors = self.capture(command, "--project", "/synthetic", *flags, *format_flags)
                    self.assertEqual((status, errors), (0, ""))
                    for value in ("decision-1", "dossier-1", "Review the date", "Opening date", "older", "human review", "not semantic"):
                        self.assertIn(value, output)
                status, output, errors = self.capture(command, "--project", "/synthetic", *flags, "--format", "json")
                self.assertEqual((status, errors), (0, ""))
                self.assertEqual(output, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
                report.assert_called_with("/synthetic", *(flags[1:] if flags else ()))

    def test_editorial_text_bounds_candidates_and_escapes_untrusted_metadata(self):
        _, review = self.editorial_results()
        review["candidates"][0]["title"] = '[red]<script>title</script>\x1b[31m\u202e'
        review["candidates"] *= 100
        review["candidate_count"] = 100
        with patch.object(api, "editorial_review", return_value=review):
            status, output, errors = self.capture("review", "--project", "/synthetic", "--format", "md")
            self.assertEqual((status, errors), (0, ""))
            self.assertIn("&lt;script&gt;", output)
            self.assertNotIn("<script>", output)
            self.assertNotIn("\x1b", output)
            self.assertNotIn("\u202e", output)
            self.assertIn("50 further", output)
            self.assertIn("--format json", output)

    def test_empty_editorial_review_does_not_imply_semantic_approval(self):
        impact, review = self.editorial_results()
        impact.update(dossiers=[], unlinked=True)
        review.update(candidates=[], candidate_count=0)
        with patch.object(api, "editorial_review", return_value=review):
            _, output, _ = self.capture("review", "--project", "/synthetic")
            self.assertIn("No structural review candidates", output)
            self.assertIn("not semantic", output)
        with patch.object(api, "decision_impact", return_value=impact):
            _, output, _ = self.capture("decision-impact", "--project", "/synthetic", "--decision-id", "decision-1")
            self.assertIn("No explicitly linked dossiers", output)

    def test_editorial_commands_inspect_real_synthetic_links_without_writing(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic editorial review")
            dossier = api.create_dossier(project, "Opening date", "## Evidence\nA dated register.")["dossier_id"]
            decision = api.record_decision(project, title="Keep the date", rationale="Use the dated record.",
                                           dossier_ids=[dossier])["decision_id"]
            loaded = api.get_record(project, "dossier", dossier)
            api.revise_record(project, "dossier", dossier, changes={"body": "## Evidence\nA reviewed register.\n## Uncertainty\nName missing."},
                              expected_snapshot=loaded["snapshot"], expected_revision=1,
                              change_kind="correction", reason="Review the source.")
            before = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
            for command, flags in (("review", ()), ("decision-impact", ("--decision-id", decision))):
                status, output, errors = self.capture(command, "--project", str(project), *flags)
                self.assertEqual((status, errors), (0, ""))
                for value in (decision, dossier, "Opening date", "Evidence", "Uncertainty", "older"):
                    self.assertIn(value, output)
            self.assertEqual(before, {p: p.read_bytes() for p in project.rglob("*") if p.is_file()})
