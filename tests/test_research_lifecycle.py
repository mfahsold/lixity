"""Tests for research lifecycle: withdrawal, purge, dry-run previews and backup/restore."""

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api
from lixity.research.models import Dossier, Tombstone
from lixity.research.repository import Repository, ResearchConflictError, ResearchError
from tests.research_support import retained_files, revise_record


class TestResearchLifecycle(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.file = self.root / "source.txt"
        self.text = "In Zürich regnete es im Frühling 1924.\r\n\r\nDer Lesesaal war gut besucht.\r\n"
        self.file.write_bytes(self.text.encode())
        api.init(self.project, title="Archivtest")

    def ingest(self, **kwargs):
        return api.ingest(self.project, self.file, allow_retention=True, **kwargs)

    def test_withdraw_source_version_marks_citations_and_excludes_from_search(self):
        source = self.ingest()
        self.assertEqual(len(api.get_source(self.project, source["source_id"])["passages"]), 2)
        api.reindex(self.project)
        search_before = api.search(self.project, "Lesesaal")
        self.assertEqual(len(search_before["hits"]), 1)
        passage_id = search_before["hits"][0]["passage_id"]

        cite_before = api.cite(self.project, passage_id)
        self.assertEqual(cite_before["availability"], "available")

        # Withdraw version
        withdraw_res = api.withdraw(
            self.project,
            source["source_id"],
            version_id=source["source_version_id"],
            reason="Lizenzrechte widerrufen",
        )
        self.assertEqual(withdraw_res["operation"], "withdraw")
        self.assertEqual(set(withdraw_res), {"schema_version", "operation", "source_id", "target_id",
                                           "target_kind", "reason", "snapshot"})
        self.assertEqual(withdraw_res["schema_version"], "research-withdraw-local/1")
        self.assertTrue(api.audit(self.project)["ok"])

        # Search excludes withdrawn versions after reindex
        api.reindex(self.project)
        search_after = api.search(self.project, "Lesesaal")
        self.assertEqual(len(search_after["hits"]), 0)

        # Citation still resolves but reports withdrawn status
        cite_after = api.cite(self.project, passage_id)
        self.assertEqual(cite_after["availability"], "withdrawn")
        self.assertEqual(cite_after["verbatim"], "Der Lesesaal war gut besucht.")
        with self.assertRaises(ResearchError):
            api.get_source(self.project, source["source_id"])

        # Analysis fails closed for withdrawn sources
        with self.assertRaises(ResearchError):
            api.analyze_source(self.project, source["source_id"])

    def test_purge_dry_run_previews_without_mutating_store(self):
        source = self.ingest()
        before_files = {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        audit_before = api.audit(self.project)

        preview = api.purge(self.project, source["source_id"], dry_run=True)
        self.assertTrue(preview["dry_run"])
        self.assertEqual(preview["purged_passages"], 2)
        self.assertEqual(len(preview["deleted_blobs"]), 1)

        after_files = {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before_files, after_files)
        self.assertEqual(api.audit(self.project)["snapshot"], audit_before["snapshot"])

    def test_dossier_withdrawal_preserves_pins_history_evidence_and_archive(self):
        source = self.ingest()
        passage = api.get_source(self.project, source["source_id"])["passages"][0]["id"]
        identifier = api.create_dossier(self.project, "Notes", "Original notes.", evidence_ids=[passage])["dossier_id"]
        claim = api.create_claim(self.project, title="Claim", statement="A reviewed assertion.", dossier_id=identifier)["claim_id"]
        decision = api.record_decision(self.project, title="Choice", rationale="An author choice.", dossier_ids=[identifier])["decision_id"]
        revise_record(self.project, "dossier", identifier, {"body": "Revised notes."})
        repository = Repository(self.project)
        snapshot = repository.snapshot()
        before = retained_files(self.project)
        arguments = {"dossier_id": identifier, "expected_snapshot": snapshot.digest,
                     "expected_revision": 2, "reason": "Consolidated author notes"}
        with (patch.object(Repository, "locked", side_effect=AssertionError("Preview must not lock")),
              patch.object(Repository, "commit", side_effect=AssertionError("Preview must not write"))):
            preview = api.withdraw(self.project, dry_run=True, **arguments)
        self.assertEqual(preview["schema_version"], "research-dossier-withdraw-preview-local/1")
        self.assertTrue(preview["ready"] and preview["dry_run"])
        self.assertEqual((preview["target_id"], preview["target_revision"], preview["snapshot"]),
                         (identifier, 2, snapshot.digest))
        self.assertEqual(retained_files(self.project), before)
        result = api.withdraw(self.project, **arguments)
        self.assertEqual(result["schema_version"], "research-dossier-withdraw-local/1")
        self.assertNotIn("source_id", result)
        accepted = repository.snapshot()
        self.assertEqual(accepted.manifest.schema_version, snapshot.manifest.schema_version)
        tombstone = next(record for record in accepted.records.values()
                         if isinstance(record, Tombstone) and record.target_ref.id == identifier)
        self.assertEqual((tombstone.schema_version, tombstone.target_kind, tombstone.target_ref.revision),
                         ("research-local/1", "dossier", 2))
        self.assertEqual(api.list_dossiers(self.project)["dossiers"], [])
        self.assertEqual(api.project_overview(self.project)["dossiers"], [])
        for read in (lambda: api.get_dossier(self.project, identifier),
                     lambda: api.get_record(self.project, "dossier", identifier)):
            with self.assertRaisesRegex(ResearchError, "withdrawn"):
                read()
        for revision, body in ((1, "Original notes."), (2, "Revised notes.")):
            historical = api.get_record(self.project, "dossier", identifier, revision=revision)
            self.assertEqual(historical["record"]["body"], body)
            self.assertEqual(historical["availability"], "withdrawn")
            self.assertEqual(historical["withdrawal"]["reason"], arguments["reason"])
            bounded = api.get_dossier(self.project, identifier, revision=revision, summary=True)
            self.assertEqual(bounded["availability"], "withdrawn")
            self.assertEqual(bounded["editable_sections"], [])
        history = api.record_history(self.project, "dossier", identifier)
        self.assertEqual([record["revision"] for record in history["revisions"]], [2, 1])
        self.assertEqual(history["availability"], "withdrawn")
        compared = api.compare_record_revisions(self.project, "dossier", identifier, from_revision=1)
        self.assertEqual(compared["fields"], [{"field": "body", "before": "Original notes.", "after": "Revised notes."}])
        self.assertEqual(compared["availability"], "withdrawn")
        self.assertEqual(api.get_record(self.project, "claim", claim)["record"]["dossier_ref"], {"id": identifier, "revision": 1})
        self.assertEqual(api.get_record(self.project, "decision", decision)["record"]["dossier_refs"], [{"id": identifier, "revision": 1}])
        self.assertEqual(api.cite(self.project, passage)["availability"], "available")
        for path, content in before.items():
            if path != "research/HEAD.json":
                self.assertEqual((self.project / path).read_bytes(), content)
        archive, restored = self.root / "retired.tar.gz", self.root / "restored"
        api.export_archive(self.project, archive)
        api.restore_archive(archive, restored)
        self.assertTrue(api.audit(restored)["ok"])
        self.assertEqual(api.get_record(restored, "dossier", identifier, revision=1)["record"]["body"], "Original notes.")
        self.assertEqual(accepted.latest(identifier, Dossier).revision, 2)

    def test_dossier_withdrawal_requires_exact_reviewed_guards_and_rejects_races(self):
        identifier = api.create_dossier(self.project, "Notes", "Synthetic notes.")["dossier_id"]
        snapshot = Repository(self.project).snapshot()
        arguments = {"dossier_id": identifier, "expected_snapshot": snapshot.digest, "expected_revision": 1}
        for changes in ({"expected_snapshot": None}, {"expected_snapshot": "not a digest"},
                        {"expected_snapshot": "0" * 64}, {"expected_revision": None},
                        {"expected_revision": True}, {"expected_revision": 0}, {"expected_revision": 2},
                        {"source_id": identifier}, {"version_id": identifier}, {"dry_run": 1}):
            before = retained_files(self.project)
            with self.subTest(changes=changes), self.assertRaises(ResearchError):
                api.withdraw(self.project, **{**arguments, **changes})
            self.assertEqual(retained_files(self.project), before)
        commit = Repository.commit

        def concurrent(repository, additions, blobs, expected, *args, **kwargs):
            with patch.object(Repository, "commit", commit):
                api.create_dossier(self.project, "Concurrent", "Another author's notes.")
            return commit(repository, additions, blobs, expected, *args, **kwargs)

        with patch.object(Repository, "commit", concurrent), self.assertRaises(ResearchConflictError):
            api.withdraw(self.project, **arguments)
        self.assertEqual(api.get_dossier(self.project, identifier)["revision"], 1)
        current = Repository(self.project).snapshot()
        api.withdraw(self.project, **{**arguments, "expected_snapshot": current.digest})
        before = retained_files(self.project)
        with self.assertRaisesRegex(ResearchError, "withdrawn"):
            api.withdraw(self.project, **{**arguments, "expected_snapshot": Repository(self.project).snapshot().digest})
        self.assertEqual(retained_files(self.project), before)

    def test_dossier_withdrawal_excludes_retired_matches_before_search_limits(self):
        retired = [api.create_dossier(self.project, "Needleword", "Needleword notes.")["dossier_id"]
                   for _ in range(3)]
        active = api.create_dossier(self.project, "Current needleword", "Active notes.")["dossier_id"]
        for identifier in retired:
            api.withdraw(self.project, dossier_id=identifier, expected_revision=1,
                         expected_snapshot=Repository(self.project).snapshot().digest)
        api.reindex(self.project)
        for scope in ("dossiers", "all"):
            for limit in (1, 100):
                with self.subTest(scope=scope, limit=limit):
                    hits = api.search(self.project, "Needleword", scope=scope, limit=limit)["hits"]
                    self.assertEqual([hit["record_id"] for hit in hits], [active])

    def test_cli_dossier_withdrawal_requires_guards_and_can_preview_without_writing(self):
        import json

        from tests.research_support import capture_research

        identifier = api.create_dossier(self.project, "Notes", "Synthetic notes.")["dossier_id"]
        before = retained_files(self.project)
        status, output, errors = capture_research("withdraw", "--project", str(self.project),
                                                  "--dossier-id", identifier)
        self.assertEqual((status, output), (1, ""))
        self.assertIn("snapshot", errors)
        self.assertEqual(retained_files(self.project), before)
        arguments = ("withdraw", "--project", str(self.project), "--dossier-id", identifier[9:],
                     "--expected-snapshot", Repository(self.project).snapshot().digest, "--expected-revision", "1")
        status, output, errors = capture_research(*arguments, "--dry-run")
        self.assertEqual((status, errors), (0, ""))
        self.assertTrue(json.loads(output)["dry_run"])
        self.assertEqual(retained_files(self.project), before)
        status, output, errors = capture_research(*arguments)
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(json.loads(output)["schema_version"], "research-dossier-withdraw-local/1")
        status, output, errors = capture_research("dossier", identifier, "--project", str(self.project), "--history")
        self.assertEqual((status, errors), (0, ""))
        self.assertEqual(json.loads(output)["availability"], "withdrawn")

    def test_purge_deletes_bytes_and_invalidates_citations_and_search(self):
        source = self.ingest()
        api.reindex(self.project)
        passage_id = api.search(self.project, "Zürich")["hits"][0]["passage_id"]

        repo = Repository(self.project)
        blob_path = repo.safe(repo.data / "blobs" / repo.snapshot().records[source["source_version_id"]].blob.sha256)
        self.assertTrue(blob_path.exists())

        purge_res = api.purge(self.project, source["source_id"], reason="Datenschutzanfrage gelöscht")
        self.assertFalse(purge_res["dry_run"])
        self.assertEqual(purge_res["purged_passages"], 2)

        # Blob is physically removed from storage
        self.assertFalse(blob_path.exists())

        # Citation on purged passage fails closed
        with self.assertRaises(ResearchError):
            api.cite(self.project, passage_id)

        # Search index is cleaned up
        api.reindex(self.project)
        self.assertEqual(len(api.search(self.project, "Zürich")["hits"]), 0)

        # Store remains fully valid under audit
        audit = api.audit(self.project)
        self.assertTrue(audit["ok"])
        # Contains Project + Tombstone
        self.assertTrue(any(isinstance(r, Tombstone) for r in repo.snapshot().records.values()))

    def test_purge_retains_authored_records_with_unavailable_evidence(self):
        source = self.ingest()
        passage_id = api.get_source(self.project, source["source_id"])["passages"][0]["id"]
        dossier = api.create_dossier(
            self.project, "Reading Room File", "The opening year is noted.",
            evidence_ids=[passage_id],
        )
        claim = api.create_claim(
            self.project, title="Opening year", statement="The room opened in 1924.",
            confidence="evidenced", dossier_id=dossier["dossier_id"],
        )
        link = api.link_evidence(
            self.project, claim_id=claim["claim_id"], passage_id=passage_id,
            relation="supports",
        )
        decision = api.record_decision(
            self.project, title="Move opening date", rationale="Plot timing",
            claim_id=claim["claim_id"], deviation_from_fact=True,
        )
        repository = Repository(self.project)
        before_purge = repository.snapshot()
        sha = before_purge.records[source["source_version_id"]].blob.sha256
        blob_path = repository.safe(repository.data / "blobs" / sha)
        passage_entry = next(entry for entry in before_purge.manifest.entries if entry.ref.id == passage_id)
        passage_path = repository.record_path(passage_entry)

        api.withdraw(self.project, source["source_id"], reason="Source withdrawn")
        self.assertEqual(api.get_dossier(self.project, dossier["dossier_id"])["citations"][0]["availability"],
                         "withdrawn")

        result = api.purge(self.project, source["source_id"], reason="Remove retained source")
        self.assertEqual(result["purged_passages"], 2)
        self.assertIn(sha, result["deleted_blobs"])
        self.assertFalse(blob_path.exists())
        self.assertFalse(passage_path.exists())
        self.assertTrue(api.audit(self.project)["ok"])
        with self.assertRaises(ResearchError):
            api.cite(self.project, passage_id)

        listed_dossier = api.list_dossiers(self.project)["dossiers"][0]
        self.assertEqual(listed_dossier["id"], dossier["dossier_id"])
        self.assertEqual(listed_dossier["unavailable_evidence_count"], 1)
        resolved = api.get_dossier(self.project, dossier["dossier_id"])["citations"][0]
        self.assertEqual(resolved["passage_id"], passage_id)
        self.assertEqual(resolved["availability"], "purged")
        self.assertNotIn("verbatim", resolved)

        listed_link = api.list_evidence_links(self.project, claim_id=claim["claim_id"])["evidence_links"][0]
        self.assertEqual(listed_link["id"], link["evidence_link_id"])
        self.assertEqual(listed_link["citation"]["passage_id"], passage_id)
        self.assertEqual(listed_link["citation"]["availability"], "purged")
        self.assertNotIn("verbatim", listed_link["citation"])
        self.assertEqual(api.list_claims(self.project)["claims"][0]["id"], claim["claim_id"])
        self.assertEqual(api.list_decisions(self.project)["decisions"][0]["id"], decision["decision_id"])
        self.assertEqual(self.file.read_bytes(), self.text.encode())
        with self.assertRaises(ResearchError):
            api.create_dossier(
                self.project, "Invalid new file", "Cannot cite purged text.",
                evidence_ids=[passage_id],
            )
        with self.assertRaises(ResearchError):
            api.link_evidence(
                self.project, claim_id=claim["claim_id"], passage_id=passage_id,
            )

    def test_purge_tombstone_cannot_target_an_absent_passage(self):
        from uuid import uuid4

        from lixity.research.models import Reference

        repository = Repository(self.project)
        snapshot = repository.snapshot()
        tombstone = Tombstone(
            **api.envelope(snapshot.project.id, "tester"),
            target_ref=Reference(id=uuid4().urn),
            target_kind="passage",
            operation="purge",
            reason="Invalid target",
        )
        with self.assertRaises(ResearchError):
            repository.commit([tombstone], {}, snapshot)

    def test_purge_preserves_shared_blob_until_last_reference_is_purged(self):
        first = self.ingest()
        second = self.ingest()  # distinct source, but identical content/blob

        repo = Repository(self.project)
        sha = repo.snapshot().records[first["source_version_id"]].blob.sha256
        blob_path = repo.safe(repo.data / "blobs" / sha)
        self.assertTrue(blob_path.exists())

        # Purge first source: blob is still referenced by second source
        res1 = api.purge(self.project, first["source_id"])
        self.assertIn(sha, res1["retained_shared_blobs"])
        self.assertNotIn(sha, res1["deleted_blobs"])
        self.assertTrue(blob_path.exists())

        # Purge second source: now the blob has no remaining references and is purged
        res2 = api.purge(self.project, second["source_id"])
        self.assertIn(sha, res2["deleted_blobs"])
        self.assertFalse(blob_path.exists())
        self.assertTrue(api.audit(self.project)["ok"])

    def test_backup_and_restore_cycle(self):
        self.ingest()
        api.reindex(self.project)
        passage_id = api.search(self.project, "Zürich")["hits"][0]["passage_id"]

        # Back up the research directory
        backup_dir = self.root / "backup_project"
        shutil.copytree(self.project / "research", backup_dir / "research")

        # Restored project passes audit
        audit_res = api.audit(backup_dir)
        self.assertTrue(audit_res["ok"])

        # Reindex and search work on restored backup
        api.reindex(backup_dir)
        results = api.search(backup_dir, "Zürich")
        self.assertEqual(len(results["hits"]), 1)
        self.assertEqual(api.cite(backup_dir, passage_id)["verbatim"], "In Zürich regnete es im Frühling 1924.")

    def test_cli_withdraw_and_purge(self):
        from lixity.cli import main

        source = self.ingest()
        code = main([
            "research",
            "withdraw",
            "--project",
            str(self.project),
            "--source-id",
            source["source_id"],
            "--reason",
            "CLI withdrawal test",
        ])
        self.assertEqual(code, 0)

        # Purge dry-run via CLI
        code = main([
            "research",
            "purge",
            "--project",
            str(self.project),
            "--source-id",
            source["source_id"],
            "--dry-run",
        ])
        self.assertEqual(code, 0)

        # Actual purge via CLI
        code = main([
            "research",
            "purge",
            "--project",
            str(self.project),
            "--source-id",
            source["source_id"],
            "--reason",
            "CLI purge test",
        ])
        self.assertEqual(code, 0)
