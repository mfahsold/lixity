"""Native research CLI revision modes preserve the existing entity commands."""

import argparse
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api, cli


class TestResearchRevisionCli(unittest.TestCase):
    def parse(self, *args: str) -> argparse.Namespace:
        parser = argparse.ArgumentParser()
        cli.configure(parser)
        return parser.parse_args(args)

    def run_json(self, *args: str) -> tuple[int, dict]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = cli.run(self.parse(*args))
        return status, json.loads(output.getvalue())

    def test_dossier_update_only_sends_supplied_fields(self):
        with patch.object(api, "revise_record", create=True, return_value={"revision": 2}) as revise:
            status, result = self.run_json(
                "dossier", "--project", "/synthetic", "--dossier-id", "urn:uuid:dossier",
                "--update", "--title", "Corrected title", "--tags", "",
                "--expected-snapshot", "a" * 64, "--expected-revision", "1",
                "--change-kind", "correction", "--reason", "Correct a label",
            )
        self.assertEqual(status, 0)
        self.assertEqual(result["revision"], 2)
        revise.assert_called_once_with(
            "/synthetic", "dossier", "urn:uuid:dossier",
            changes={"title": "Corrected title", "tags": []},
            expected_snapshot="a" * 64, expected_revision=1,
            change_kind="correction", reason="Correct a label", actor="local-author",
        )

    def test_claim_update_clears_optional_association_without_default_confidence(self):
        with patch.object(api, "revise_record", create=True, return_value={"revision": 2}) as revise:
            status, _ = self.run_json(
                "claim", "--project", "/synthetic", "--claim-id", "urn:uuid:claim",
                "--update", "--dossier-id", "", "--place", "",
                "--expected-snapshot", "b" * 64, "--expected-revision", "1",
                "--change-kind", "supersession", "--reason", "New interpretation",
            )
        self.assertEqual(status, 0)
        self.assertEqual(revise.call_args.kwargs["changes"], {"dossier_id": None, "place": None})

    def test_decision_update_can_clear_deviation(self):
        with patch.object(api, "revise_record", create=True, return_value={"revision": 2}) as revise:
            status, _ = self.run_json(
                "decision", "--project", "/synthetic", "--decision-id", "urn:uuid:decision",
                "--update", "--no-deviation-from-fact", "--impact-on-plot", "",
                "--expected-snapshot", "c" * 64, "--expected-revision", "1",
                "--change-kind", "correction", "--reason", "Correct classification",
            )
        self.assertEqual(status, 0)
        self.assertEqual(revise.call_args.kwargs["changes"], {
            "deviation_from_fact": False, "impact_on_plot": None,
        })

    def test_evidence_history_and_pinned_inspection(self):
        with patch.object(api, "record_history", create=True, return_value={"revisions": []}) as history:
            status, _ = self.run_json(
                "link-evidence", "--project", "/synthetic",
                "--evidence-link-id", "urn:uuid:link", "--history",
            )
        self.assertEqual(status, 0)
        history.assert_called_once_with("/synthetic", "evidence_link", "urn:uuid:link")
        with patch.object(api, "get_record", create=True, return_value={"revision": 1}) as get_record:
            status, _ = self.run_json(
                "link-evidence", "--project", "/synthetic",
                "--evidence-link-id", "urn:uuid:link", "--revision", "1",
            )
        self.assertEqual(status, 0)
        get_record.assert_called_once_with("/synthetic", "evidence_link", "urn:uuid:link", revision=1)

    def test_explicit_reference_revision_flags_are_update_only(self):
        cases = (
            ("claim", "--claim-id", "urn:uuid:claim", "--dossier-revision", "dossier_revision"),
            ("link-evidence", "--evidence-link-id", "urn:uuid:link", "--claim-revision", "claim_revision"),
            ("decision", "--decision-id", "urn:uuid:decision", "--claim-revision", "claim_revision"),
        )
        for command, id_flag, record_id, revision_flag, revision_key in cases:
            with self.subTest(command=command), patch.object(api, "revise_record", return_value={"revision": 2}) as revise:
                status, _ = self.run_json(
                    command, "--project", "/synthetic", id_flag, record_id,
                    "--update", revision_flag, "2", "--expected-snapshot", "d" * 64,
                    "--expected-revision", "1", "--change-kind", "supersession",
                    "--reason", "Use corrected association",
                )
                self.assertEqual(status, 0)
                self.assertEqual(revise.call_args.kwargs["changes"], {revision_key: 2})
            with self.subTest(command=command, mode="without update"):
                errors = io.StringIO()
                with contextlib.redirect_stderr(errors):
                    status, output = self.run_json_on_error(
                        command, "--project", "/synthetic", id_flag, record_id,
                        revision_flag, "2",
                    )
                self.assertEqual(status, 1)
                self.assertEqual(output, "")
                self.assertIn("requires --update", errors.getvalue())

    def test_existing_claim_inspection_still_lists_links(self):
        with patch.object(api, "list_evidence_links", return_value={"evidence_links": []}) as links:
            status, _ = self.run_json("claim", "--project", "/synthetic", "--claim-id", "urn:uuid:claim")
        self.assertEqual(status, 0)
        links.assert_called_once_with("/synthetic", claim_id="urn:uuid:claim")

    def test_creation_actor_is_recorded_for_each_entity(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            source_file = Path(td) / "source.txt"
            source_file.write_text("A synthetic archive opened in 1924.", encoding="utf-8")
            api.init(project, title="Synthetic research")
            source = api.ingest(project, source_file, allow_retention=True)
            passage_id = api.get_source(project, source["source_id"])["passages"][0]["id"]

            status, dossier = self.run_json(
                "dossier", "--project", str(project), "--title", "Archive note",
                "--file", "Synthetic note.", "--actor", "dossier-author",
            )
            self.assertEqual(status, 0)
            status, claim = self.run_json(
                "claim", "--project", str(project), "--title", "Opening year",
                "--statement", "Opened in 1924.", "--dossier-id", dossier["dossier_id"],
                "--actor", "claim-author",
            )
            self.assertEqual(status, 0)
            status, link = self.run_json(
                "link-evidence", "--project", str(project), "--claim-id", claim["claim_id"],
                "--passage-id", passage_id, "--actor", "link-author",
            )
            self.assertEqual(status, 0)
            status, decision = self.run_json(
                "decision", "--project", str(project), "--title", "Use opening year",
                "--rationale", "The retained source supports it.", "--claim-id", claim["claim_id"],
                "--actor", "decision-author",
            )
            self.assertEqual(status, 0)
            for kind, record_id, actor in (
                ("dossier", dossier["dossier_id"], "dossier-author"),
                ("claim", claim["claim_id"], "claim-author"),
                ("evidence_link", link["evidence_link_id"], "link-author"),
                ("decision", decision["decision_id"], "decision-author"),
            ):
                with self.subTest(kind=kind):
                    self.assertEqual(api.get_record(project, kind, record_id)["record"]["created_by"], actor)

    def test_dossier_update_history_and_stale_write_against_real_archive(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Synthetic research")
            created = api.create_dossier(project, title="Initial", body="Initial note.")
            dossier_id = created["dossier_id"]
            current = api.get_record(project, "dossier", dossier_id)
            update = (
                "dossier", "--project", str(project), "--dossier-id", dossier_id,
                "--update", "--file", "Corrected note.",
                "--expected-snapshot", current["snapshot"], "--expected-revision", "1",
                "--change-kind", "correction", "--reason", "Correct the note",
            )
            status, revised = self.run_json(*update)
            self.assertEqual(status, 0)
            self.assertEqual(revised["record"]["id"], dossier_id)
            self.assertEqual(revised["record"]["revision"], 2)
            self.assertEqual(revised["record"]["body"], "Corrected note.")
            status, history = self.run_json(
                "dossier", "--project", str(project), "--dossier-id", dossier_id, "--history",
            )
            self.assertEqual(status, 0)
            self.assertEqual([entry["revision"] for entry in history["revisions"]], [2, 1])
            status, old = self.run_json(
                "dossier", "--project", str(project), "--dossier-id", dossier_id, "--revision", "1",
            )
            self.assertEqual(status, 0)
            self.assertEqual(old["record"]["body"], "Initial note.")
            with contextlib.redirect_stderr(io.StringIO()):
                stale_status, _ = self.run_json_on_error(*update)
            self.assertEqual(stale_status, 1)
            self.assertTrue(api.audit(project)["ok"])

    def test_evidence_update_repins_claim_without_rewriting_old_link(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            source_file = Path(td) / "source.txt"
            source_file.write_text("The archive opened in 1924.", encoding="utf-8")
            api.init(project, title="Synthetic research")
            source = api.ingest(project, source_file, allow_retention=True)
            passage_id = api.get_source(project, source["source_id"])["passages"][0]["id"]
            claim = api.create_claim(project, title="Opening year", statement="Opened in 1924.")
            link = api.link_evidence(
                project, claim_id=claim["claim_id"], passage_id=passage_id, relation="supports",
            )
            claim_view = api.get_record(project, "claim", claim["claim_id"])
            api.revise_record(
                project, "claim", claim["claim_id"], changes={"statement": "Possibly opened in 1924."},
                expected_snapshot=claim_view["snapshot"], expected_revision=1,
                change_kind="supersession", reason="Reassess the date",
            )
            before = api.get_record(project, "evidence_link", link["evidence_link_id"])
            self.assertEqual(before["record"]["claim_ref"]["revision"], 1)
            status, updated = self.run_json(
                "link-evidence", "--project", str(project),
                "--evidence-link-id", link["evidence_link_id"], "--update",
                "--claim-revision", "2", "--expected-snapshot", before["snapshot"],
                "--expected-revision", "1", "--change-kind", "supersession",
                "--reason", "Attach to corrected claim",
            )
            self.assertEqual(status, 0)
            self.assertEqual(updated["record"]["id"], link["evidence_link_id"])
            self.assertEqual(updated["record"]["claim_ref"]["revision"], 2)
            original = api.get_record(project, "evidence_link", link["evidence_link_id"], revision=1)
            self.assertEqual(original["record"]["claim_ref"]["revision"], 1)
            self.assertTrue(api.audit(project)["ok"])

    def test_cli_batch_ingest_and_progress(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            f1 = Path(td) / "doc1.txt"
            f2 = Path(td) / "doc2.txt"
            f1.write_text("First document content.", encoding="utf-8")
            f2.write_text("Second document content.", encoding="utf-8")
            api.init(project, title="Batch Project")

            stderr_buf = io.StringIO()
            with contextlib.redirect_stderr(stderr_buf):
                status, batch_res = self.run_json(
                    "ingest", "--project", str(project),
                    "--file", str(f1), str(f2),
                    "--allow-retention", "--progress",
                )
            self.assertEqual(status, 0)
            self.assertEqual(batch_res["schema_version"], "research-batch-ingest-local/1")
            self.assertEqual(batch_res["succeeded"], 2)
            self.assertEqual(batch_res["failed"], 0)
            self.assertEqual(len(batch_res["items"]), 2)
            self.assertTrue(batch_res["items"][0]["ok"])
            self.assertTrue(batch_res["items"][1]["ok"])
            # stderr contains progress phases
            self.assertIn("[read]", stderr_buf.getvalue())
            self.assertIn("[complete]", stderr_buf.getvalue())

    def test_cli_search_auto_fresh_and_strict(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            f1 = Path(td) / "doc.txt"
            f1.write_text("A distinctive keyword appears here.", encoding="utf-8")
            api.init(project, title="Search Project")
            api.ingest(project, f1, allow_retention=True)
            # Do NOT manually reindex; test that CLI search automatically refreshes
            status, res = self.run_json(
                "search", "--project", str(project),
                "--query", "distinctive",
            )
            self.assertEqual(status, 0)
            self.assertEqual(len(res["hits"]), 1)

            # Test that --strict fails if index is stale
            f2 = Path(td) / "doc2.txt"
            f2.write_text("Another text file added.", encoding="utf-8")
            api.ingest(project, f2, allow_retention=True)

            err_buf = io.StringIO()
            with contextlib.redirect_stderr(err_buf):
                status2 = cli.run(self.parse(
                    "search", "--project", str(project),
                    "--query", "Another", "--strict",
                ))
            self.assertNotEqual(status2, 0)
            self.assertIn("stale", err_buf.getvalue())

    def test_cli_dossier_summary_section_and_section_update(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Dossier Project")
            body = "# Overview\n\nInitial facts.\n\n## Section A\n\nContent of A.\n\n## Section B\n\nContent of B."
            dossier = api.create_dossier(project, "Doc Dossier", body)
            did = dossier["dossier_id"]

            # CLI --summary
            status, summary = self.run_json(
                "dossier", "--project", str(project),
                "--dossier-id", did, "--summary",
            )
            self.assertEqual(status, 0)
            self.assertEqual(summary["sections"], ["Overview", "Section A", "Section B"])
            self.assertIn("Initial facts", summary["excerpt"])

            # CLI --section
            status, sec = self.run_json(
                "dossier", "--project", str(project),
                "--dossier-id", did, "--section", "Section A",
            )
            self.assertEqual(status, 0)
            self.assertEqual(sec["content"], "Content of A.")

            # CLI --update --section
            new_sec = Path(td) / "new_sec.txt"
            new_sec.write_text("Revised content of A.", encoding="utf-8")
            snap = api.get_dossier(project, did)["snapshot"]
            status, updated = self.run_json(
                "dossier", "--project", str(project),
                "--dossier-id", did, "--update",
                "--section", "Section A", "--file", str(new_sec),
                "--expected-snapshot", snap, "--expected-revision", "1",
                "--change-kind", "correction", "--reason", "Update Section A",
            )
            self.assertEqual(status, 0)
            self.assertIn("Revised content of A.", updated["record"]["body"])
            self.assertIn("Content of B.", updated["record"]["body"])

            # CLI --update --section without --file should fail with clear error
            err_buf = io.StringIO()
            with contextlib.redirect_stderr(err_buf):
                err_status = cli.run(self.parse(
                    "dossier", "--project", str(project),
                    "--dossier-id", did, "--update",
                    "--section", "Section B",
                    "--expected-snapshot", updated["snapshot"], "--expected-revision", "2",
                    "--change-kind", "correction", "--reason", "Missing file",
                ))
            self.assertNotEqual(err_status, 0)
            self.assertIn("requires --file", err_buf.getvalue())

    def test_cli_decision_with_dossier_link(self):
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "project"
            api.init(project, title="Decision Project")
            dossier1 = api.create_dossier(project, "Dossier 1", "Body text")
            dossier2 = api.create_dossier(project, "Dossier 2", "Second body")
            did1 = dossier1["dossier_id"]
            did2 = dossier2["dossier_id"]

            status, dec = self.run_json(
                "decision", "--project", str(project),
                "--title", "Dramaturgical adjustment",
                "--rationale", "Enhance pacing",
                "--dossier-id", did1,
            )
            self.assertEqual(status, 0)
            self.assertEqual(dec["dossier_ids"], [did1])
            dec_id = dec["decision_id"]

            # Inspect dossier 1 via CLI: should have review_needed
            status, d_info = self.run_json(
                "dossier", "--project", str(project),
                "--dossier-id", did1,
            )
            self.assertEqual(status, 0)
            self.assertTrue(d_info["review_needed"])
            self.assertEqual(len(d_info["decision_reviews"]), 1)

            # Update decision to link both dossiers
            snap = d_info["snapshot"]
            status, updated_dec = self.run_json(
                "decision", "--project", str(project),
                "--decision-id", dec_id, "--update",
                "--dossiers", f"{did1},{did2}",
                "--expected-snapshot", snap, "--expected-revision", "1",
                "--change-kind", "correction", "--reason", "Link second dossier",
            )
            self.assertEqual(status, 0)
            self.assertEqual(updated_dec["record"]["dossier_refs"][0]["id"], did1)
            self.assertEqual(updated_dec["record"]["dossier_refs"][1]["id"], did2)

    def run_json_on_error(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = cli.run(self.parse(*args))
        return status, output.getvalue()


if __name__ == "__main__":
    unittest.main()

