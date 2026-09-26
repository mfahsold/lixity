"""Tests for research lifecycle: withdrawal, purge, dry-run previews and backup/restore."""

import shutil
import tempfile
import unittest
from pathlib import Path

from lixity.research import api
from lixity.research.models import Tombstone
from lixity.research.repository import Repository, ResearchError


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
        self.assertTrue(api.audit(self.project)["ok"])

        # Search excludes withdrawn versions after reindex
        api.reindex(self.project)
        search_after = api.search(self.project, "Lesesaal")
        self.assertEqual(len(search_after["hits"]), 0)

        # Citation still resolves but reports withdrawn status
        cite_after = api.cite(self.project, passage_id)
        self.assertEqual(cite_after["availability"], "withdrawn")
        self.assertEqual(cite_after["verbatim"], "Der Lesesaal war gut besucht.")

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

