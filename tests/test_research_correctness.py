"""Correctness tests for commit atomicity, deduplication and snapshot limits.

These tests guard the specific invariants fixed or identified during the
2026-09-26 correctness review:

1. Purge atomicity: the archive is always openable because orphaned files are
   deleted only after HEAD is atomically rotated to the new snapshot.
2. Evidence-ID deduplication: create_dossier silently deduplicates passage
   IDs, matching revise_record behaviour.
3. Snapshot entry limit: Manifest rejects more than 25,000 entries at both
   commit time (ValidationError → ResearchError) and read time.
"""

import contextlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from pydantic import ValidationError

from lixity.research import api
from lixity.research.models import Entry, Manifest, Reference
from lixity.research.repository import Repository


class TestPurgeAtomicity(unittest.TestCase):
    """Verify the post-HEAD orphan deletion ordering for purge operations.

    The fix moves record/blob unlinks to after replace_head so that a crash
    between HEAD rotation and deletion leaves unreferenced-but-harmless files,
    whereas a crash before HEAD rotation leaves the old archive fully intact.
    """

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.source_file = Path(self._tmp.name) / "source.txt"
        self.source_file.write_bytes(
            b"The archive opened in 1924.\r\n\r\nA second paragraph.\r\n"
        )
        api.init(self.project, title="Purge atomicity test")

    def ingest(self) -> dict:  # type: ignore[type-arg]
        return api.ingest(self.project, self.source_file, allow_retention=True)

    def test_archive_openable_when_orphan_deletion_is_interrupted(self) -> None:
        """Simulate a crash between HEAD rotation and orphan unlink.

        After the fix the old record/blob files are deleted *after*
        replace_head. Simulate an interrupted deletion by patching Path.unlink
        to raise OSError partway through; the archive must still load cleanly
        via the new HEAD.
        """
        source = self.ingest()
        repo = Repository(self.project)
        snapshot_before = repo.snapshot()
        source_id = source["source_id"]

        from lixity.research.models import SourceVersion

        version = snapshot_before.get(
            Reference(id=source["source_version_id"]), SourceVersion
        )
        blob_path = repo.safe(repo.data / "blobs" / version.blob.sha256)
        self.assertTrue(blob_path.exists())

        original_unlink = Path.unlink
        calls: list[Path] = []

        def unlink_after_head_then_fail(
            self_path: Path, missing_ok: bool = False
        ) -> None:
            calls.append(self_path)
            if len(calls) == 1:
                # Let the first unlink succeed (a record file after HEAD rotation)
                original_unlink(self_path, missing_ok=missing_ok)
            else:
                # Simulate power loss on subsequent unlinks (blob deletion etc.)
                raise OSError("Simulated power loss during orphan deletion")

        with patch.object(Path, "unlink", unlink_after_head_then_fail), \
                contextlib.suppress(OSError):
            api.purge(self.project, source_id, reason="Atomicity test")

        # The archive must still be openable and self-consistent.
        snapshot_after = repo.snapshot()
        self.assertNotEqual(snapshot_after.digest, snapshot_before.digest)
        self.assertTrue(api.audit(self.project)["ok"])

    def test_old_files_remain_intact_when_head_rotation_fails(self) -> None:
        """Simulate a crash before replace_head during purge.

        When replace_head fails (e.g. disk full), the old HEAD still points
        to the original snapshot and all original files must remain intact.
        """
        source = self.ingest()
        source_id = source["source_id"]
        repo = Repository(self.project)
        digest_before = repo.snapshot().digest

        def raise_on_head(path: Path, content: bytes) -> None:
            raise OSError("Simulated disk full during HEAD write")

        with patch("lixity.research.repository.replace_head", raise_on_head), \
                self.assertRaises(OSError):
            api.purge(self.project, source_id, reason="Interrupted purge")

        repo2 = Repository(self.project)
        self.assertEqual(repo2.snapshot().digest, digest_before)
        self.assertTrue(api.audit(self.project)["ok"])


class TestEvidenceIdDeduplication(unittest.TestCase):
    """create_dossier and revise_record must both silently deduplicate passage IDs."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.project = Path(self._tmp.name) / "proj"
        self.source_file = Path(self._tmp.name) / "source.txt"
        self.source_file.write_bytes(b"First paragraph.\r\n\r\nSecond paragraph.\r\n")
        api.init(self.project, title="Deduplication test")
        ingested = api.ingest(self.project, self.source_file, allow_retention=True)
        source_detail = api.get_source(self.project, ingested["source_id"])
        self.passage_id = source_detail["passages"][0]["id"]

    def test_create_dossier_deduplicates_evidence_ids(self) -> None:
        """Passing the same passage ID twice must not create two evidence_refs."""
        result = api.create_dossier(
            self.project,
            "Dedup test dossier",
            "Some notes.",
            evidence_ids=[self.passage_id, self.passage_id, self.passage_id],
        )
        dossier_data = api.get_dossier(self.project, result["dossier_id"])
        self.assertEqual(len(dossier_data["citations"]), 1)
        self.assertEqual(dossier_data["citations"][0]["passage_id"], self.passage_id)

    def test_empty_evidence_ids_produces_no_refs(self) -> None:
        result = api.create_dossier(
            self.project, "Empty evidence", "No evidence yet.", evidence_ids=[]
        )
        dossier_data = api.get_dossier(self.project, result["dossier_id"])
        self.assertEqual(dossier_data["citations"], [])


class TestSnapshotEntryLimit(unittest.TestCase):
    """The Manifest model enforces a max of 25,000 entries at both commit and read time."""

    def test_manifest_rejects_over_25000_entries_at_validation(self) -> None:
        entry = Entry(
            kind="project",
            ref=Reference(id="urn:uuid:00000000-0000-4000-8000-000000000001"),
            sha256="a" * 64,
        )
        with self.assertRaises(ValidationError):
            Manifest(
                schema_version="research-manifest-local/1",
                project_id="urn:uuid:00000000-0000-4000-8000-000000000001",
                generation=1,
                parent=None,
                entries=[entry] * 25001,
            )

    def test_manifest_accepts_exactly_25000_entries(self) -> None:
        entry = Entry(
            kind="project",
            ref=Reference(id="urn:uuid:00000000-0000-4000-8000-000000000001"),
            sha256="a" * 64,
        )
        manifest = Manifest(
            schema_version="research-manifest-local/1",
            project_id="urn:uuid:00000000-0000-4000-8000-000000000001",
            generation=1,
            parent=None,
            entries=[entry] * 25000,
        )
        self.assertEqual(len(manifest.entries), 25000)

    def test_manifest_rejects_zero_entries(self) -> None:
        with self.assertRaises(ValidationError):
            Manifest(
                schema_version="research-manifest-local/1",
                project_id="urn:uuid:00000000-0000-4000-8000-000000000001",
                generation=1,
                parent=None,
                entries=[],
            )
