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

    def run_json_on_error(self, *args: str) -> tuple[int, str]:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = cli.run(self.parse(*args))
        return status, output.getvalue()


if __name__ == "__main__":
    unittest.main()
