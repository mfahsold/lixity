"""Tests for research archive export, restoration, integrity checks, and security."""

import hashlib
import io
import json
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path

from lixity.cli import main
from lixity.research import api
from lixity.research.archive import export_archive, restore_archive
from lixity.research.models import Head
from lixity.research.repository import Repository, ResearchError, digest, encode


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
        self.ingested = api.ingest(self.project, self.source_file, allow_retention=True,
                                   origin_url="https://example.org/synthetic-archive")

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

    def replace_parent(self, project: Path, changes: dict) -> None:
        """Keep the current snapshot valid while replacing its ancestor fixture."""
        repository = Repository(project)
        snapshot = repository.snapshot()
        parent_path = repository.data / "manifests" / f"{snapshot.manifest.parent}.json"
        parent = json.loads(parent_path.read_bytes())
        parent.update(changes)
        parent_bytes = json.dumps(parent).encode("utf-8")
        parent_digest = digest(parent_bytes)
        (repository.data / "manifests" / f"{parent_digest}.json").write_bytes(parent_bytes)
        current = snapshot.manifest.model_copy(update={"parent": parent_digest})
        current_bytes = encode(current)
        current_digest = digest(current_bytes)
        (repository.data / "manifests" / f"{current_digest}.json").write_bytes(current_bytes)
        (repository.data / "HEAD.json").write_bytes(encode(Head(sha256=current_digest)))
        self.assertEqual(Repository(project).snapshot().digest, current_digest)

    def test_export_rejects_invalid_ancestor_contracts_without_replacing_output(self) -> None:
        changes = (
            {"parent": "../invalid-selector"},
            {"schema_version": "research-manifest-local/99"},
            {"project_id": "urn:uuid:00000000-0000-4000-8000-000000000000"},
            {"generation": 1},
            {"parent": None},
        )
        for index, change in enumerate(changes):
            with self.subTest(change=change):
                project = self.root / f"invalid-{index}"
                shutil.copytree(self.project, project)
                self.replace_parent(project, change)
                output = self.root / f"existing-{index}.tar.gz"
                output.write_bytes(b"existing backup")
                with self.assertRaises(ResearchError):
                    export_archive(project, output)
                self.assertEqual(output.read_bytes(), b"existing backup")

    def test_export_rejects_missing_or_checksum_damaged_ancestors(self) -> None:
        for missing in (True, False):
            with self.subTest(missing=missing):
                project = self.root / f"damaged-{missing}"
                shutil.copytree(self.project, project)
                repository = Repository(project)
                snapshot = repository.snapshot()
                ancestor = repository.data / "manifests" / f"{snapshot.manifest.parent}.json"
                if missing:
                    ancestor.unlink()
                else:
                    ancestor.write_bytes(ancestor.read_bytes() + b" ")
                output = self.root / f"damaged-{missing}.tar.gz"
                with self.assertRaises(ResearchError):
                    export_archive(project, output)
                self.assertFalse(output.exists())

    def test_restore_rejects_invalid_history_even_with_matching_inventory(self) -> None:
        valid = self.root / "valid.tar.gz"
        export_archive(self.project, valid)
        with tarfile.open(valid, "r:gz") as archive:
            member = archive.extractfile("EXPORT_MANIFEST.json")
            assert member is not None
            inventory = json.loads(member.read())
        self.replace_parent(self.project, {"parent": "../invalid-selector"})
        payloads = {}
        for path in (self.project / "research").rglob("*"):
            relative = path.relative_to(self.project).as_posix()
            if path.is_file() and not relative.startswith("research/.cache/"):
                payloads[relative] = path.read_bytes()
        inventory["snapshot"] = Repository(self.project).snapshot().digest
        inventory["files"] = {
            name: {"sha256": hashlib.sha256(content).hexdigest(), "byte_length": len(content)}
            for name, content in payloads.items()
        }
        inventory["file_count"] = len(payloads)
        payloads["EXPORT_MANIFEST.json"] = json.dumps(inventory).encode("utf-8")
        invalid = self.root / "invalid-history.tar.gz"
        with tarfile.open(invalid, "w:gz") as archive:
            for name, content in payloads.items():
                member = tarfile.TarInfo(name=name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        target = self.root / "invalid-history-target"
        with self.assertRaises(ResearchError):
            restore_archive(invalid, target)
        self.assertFalse((target / "research").exists())
        self.assertEqual(list(target.iterdir()), [])

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
            if manifest_member is None:
                self.fail("EXPORT_MANIFEST.json is missing from the archive")
            manifest_json = json.loads(manifest_member.read().decode("utf-8"))
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
        self.assertEqual(cite["context"]["origin_url"], "https://example.org/synthetic-archive")

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
            for member in tar.getmembers():
                if member.isfile():
                    target = unpack_dir / member.name
                    self.assertTrue(target.resolve().is_relative_to(unpack_dir.resolve()))
                    target.parent.mkdir(parents=True, exist_ok=True)
                    stream = tar.extractfile(member)
                    assert stream is not None
                    with stream:
                        target.write_bytes(stream.read())

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

    def test_restore_rejects_parent_paths_in_inventory_before_reading_files(self) -> None:
        archive_path = self.root / "valid-inventory.tar.gz"
        export_archive(self.project, archive_path)
        payloads = {}
        with tarfile.open(archive_path, "r:gz") as archive:
            for member in archive.getmembers():
                stream = archive.extractfile(member)
                assert stream is not None
                payloads[member.name] = stream.read()
        inventory = json.loads(payloads["EXPORT_MANIFEST.json"])
        outside = self.root / "outside-inventory.json"
        outside.write_bytes(b"synthetic inventory boundary")
        inventory["files"]["../../outside-inventory.json"] = {
            "sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
            "byte_length": outside.stat().st_size,
        }
        payloads["EXPORT_MANIFEST.json"] = json.dumps(inventory).encode("utf-8")
        invalid = self.root / "invalid-inventory.tar.gz"
        with tarfile.open(invalid, "w:gz") as archive:
            for name, content in payloads.items():
                member = tarfile.TarInfo(name=name)
                member.size = len(content)
                archive.addfile(member, io.BytesIO(content))
        target = self.root / "invalid-inventory-target"
        with self.assertRaisesRegex(ResearchError, "traversal"):
            restore_archive(invalid, target)
        self.assertFalse((target / "research").exists())

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
