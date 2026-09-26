"""Tests for research archive export, restoration, integrity checks, and security."""

import io
import json
import tarfile
import tempfile
import unittest
from pathlib import Path

from lixity.cli import main
from lixity.research import api
from lixity.research.archive import export_archive, restore_archive
from lixity.research.repository import ResearchError


class TestResearchArchive(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.project = self.root / "orig_project"
        self.source_file = self.root / "source.txt"
        self.source_file.write_bytes(
            b"The reading room opened in 1924.\r\n\r\nArchive records were preserved.\r\n"
        )
        api.init(self.project, title="Original Archive", language="en")
        self.ingested = api.ingest(self.project, self.source_file, allow_retention=True)

        # Create authored records
        src_detail = api.get_source(self.project, self.ingested["source_id"])
        self.passage_id = src_detail["passages"][0]["id"]
        dossier = api.create_dossier(
            self.project,
            "Initial Dossier",
            "Body of dossier note.",
            evidence_ids=[self.passage_id],
        )
        self.dossier_id = dossier["dossier_id"]

        # Revise dossier to revision 2
        d_rec = api.get_record(self.project, "dossier", self.dossier_id)
        api.revise_record(
            self.project,
            "dossier",
            self.dossier_id,
            changes={"body": "Revised body note."},
            expected_snapshot=d_rec["snapshot"],
            expected_revision=d_rec["record"]["revision"],
            change_kind="correction",
            reason="Fix note text",
        )

        claim = api.create_claim(
            self.project,
            title="1924 Opening",
            statement="Opened in 1924.",
            confidence="evidenced",
            dossier_id=self.dossier_id,
        )
        self.claim_id = claim["claim_id"]

        link = api.link_evidence(
            self.project,
            claim_id=self.claim_id,
            passage_id=self.passage_id,
            relation="supports",
            rationale="Passage confirms date",
        )
        self.link_id = link["evidence_link_id"]

        api.record_decision(
            self.project,
            title="Keep 1924 setting",
            rationale="Historically evidenced",
            claim_id=self.claim_id,
            deviation_from_fact=False,
        )

    def test_export_and_restore_full_roundtrip(self) -> None:
        archive_path = self.root / "backup.tar.gz"
        export_meta = export_archive(self.project, archive_path)
        self.assertTrue(archive_path.is_file())
        self.assertEqual(export_meta["schema_version"], "research-export-local/1")
        self.assertGreater(export_meta["record_count"], 0)
        self.assertGreater(export_meta["blob_count"], 0)

        # Verify archive internal structure
        with tarfile.open(archive_path, mode="r:gz") as tar:
            names = tar.getnames()
            self.assertIn("EXPORT_MANIFEST.json", names)
            self.assertIn("research/HEAD.json", names)
            self.assertIn("research/project.json", names)

            manifest_member = tar.extractfile("EXPORT_MANIFEST.json")
            self.assertIsNotNone(manifest_member)
            manifest_json = json.loads(manifest_member.read().decode("utf-8"))  # type: ignore[union-attr]
            self.assertEqual(manifest_json["project_id"], export_meta["project_id"])
            self.assertEqual(manifest_json["snapshot"], export_meta["snapshot"])

        # Restore into a fresh directory
        target_dir = self.root / "restored_project"
        restore_meta = restore_archive(archive_path, target_dir)
        self.assertEqual(restore_meta["schema_version"], "research-export-local/1")
        self.assertEqual(restore_meta["snapshot"], export_meta["snapshot"])

        # Audit restored archive
        audit = api.audit(target_dir)
        self.assertTrue(audit["ok"])
        self.assertEqual(audit["snapshot"], export_meta["snapshot"])

        # Reindex and search
        api.reindex(target_dir)
        hits = api.search(target_dir, "reading room")["hits"]
        self.assertEqual(len(hits), 1)

        # Resolve citation
        cite = api.cite(target_dir, self.passage_id)
        self.assertEqual(cite["verbatim"], "The reading room opened in 1924.")

        # Resolve revision history on restored project
        history = api.record_history(target_dir, "dossier", self.dossier_id)
        self.assertEqual(len(history["revisions"]), 2)
        v1 = api.get_record(target_dir, "dossier", self.dossier_id, revision=1)
        v2 = api.get_record(target_dir, "dossier", self.dossier_id, revision=2)
        self.assertEqual(v1["record"]["body"], "Body of dossier note.")
        self.assertEqual(v2["record"]["body"], "Revised body note.")

    def test_restore_refuses_to_overwrite_existing_research_store(self) -> None:
        archive_path = self.root / "backup.tar.gz"
        export_archive(self.project, archive_path)

        with self.assertRaises(ResearchError):
            restore_archive(archive_path, self.project)

    def test_restore_refuses_non_empty_target(self) -> None:
        archive_path = self.root / "backup.tar.gz"
        export_archive(self.project, archive_path)

        dirty_target = self.root / "dirty"
        dirty_target.mkdir()
        (dirty_target / "existing.txt").write_text("pre-existing content", encoding="utf-8")

        with self.assertRaises(ResearchError):
            restore_archive(archive_path, dirty_target)

    def test_restore_rejects_tampered_checksum(self) -> None:
        archive_path = self.root / "backup.tar.gz"
        export_archive(self.project, archive_path)

        # Unpack, modify a file, and repack
        tampered_archive = self.root / "tampered.tar.gz"
        unpack_dir = self.root / "tamper_unpack"
        unpack_dir.mkdir()
        with tarfile.open(archive_path, "r:gz") as tar:
            tar.extractall(path=unpack_dir)  # noqa: S202

        # Find a revision file and tamper with its bytes
        rev_files = list(unpack_dir.glob("research/revisions/**/*.json"))
        self.assertTrue(len(rev_files) > 0)
        rev_files[0].write_bytes(b'{"tampered": true}')

        with tarfile.open(tampered_archive, "w:gz") as tar:
            for item in unpack_dir.iterdir():
                tar.add(item, arcname=item.name)

        target_dir = self.root / "tamper_target"
        with self.assertRaises(ResearchError) as cm:
            restore_archive(tampered_archive, target_dir)
        self.assertIn("Checksum mismatch", str(cm.exception))
        self.assertFalse((target_dir / "research").exists())

    def test_restore_rejects_path_traversal(self) -> None:
        malicious_archive = self.root / "malicious.tar.gz"
        with tarfile.open(malicious_archive, "w:gz") as tar:
            ti = tarfile.TarInfo(name="../escaped.txt")
            content = b"escape"
            ti.size = len(content)
            tar.addfile(ti, io.BytesIO(content))

        target_dir = self.root / "escape_target"
        with self.assertRaises(ResearchError) as cm:
            restore_archive(malicious_archive, target_dir)
        self.assertIn("Dangerous archive entry", str(cm.exception))

    def test_cli_export_and_restore(self) -> None:
        archive_path = self.root / "cli_backup.tar.gz"
        code = main([
            "research",
            "export",
            "--project",
            str(self.project),
            "--output",
            str(archive_path),
        ])
        self.assertEqual(code, 0)
        self.assertTrue(archive_path.is_file())

        restored_dir = self.root / "cli_restored"
        code = main([
            "research",
            "restore",
            "--from",
            str(archive_path),
            "--to",
            str(restored_dir),
        ])
        self.assertEqual(code, 0)
        self.assertTrue((restored_dir / "research" / "HEAD.json").is_file())
        self.assertTrue(api.audit(restored_dir)["ok"])
