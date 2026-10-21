"""Tests for research archive export, restoration, integrity checks, and security."""

import contextlib
import hashlib
import io
import json
import shutil
import subprocess
import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.cli import main
from lixity.research import api, archive
from lixity.research.archive import export_archive, restore_archive
from lixity.research.models import Head
from lixity.research.repository import (
    Repository,
    ResearchError,
    ResearchStorageError,
    digest,
    encode,
)


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

    def test_export_stays_restorable_when_author_commit_races_history(self) -> None:
        original = archive._manifest_history
        attempted = []

        def competing_commit(repository, snapshot):
            history = original(repository, snapshot)
            try:
                api.create_dossier(self.project, "Concurrent", "Synthetic note.")
                attempted.append("committed")
            except ResearchStorageError as error:
                if not str(error).startswith("Research writer is busy; retry after it finishes:"):
                    raise
                attempted.append("busy")
            return history

        output = self.root / "race.tar.gz"
        with patch.object(archive, "_manifest_history", side_effect=competing_commit):
            exported = export_archive(self.project, output)
        restored = restore_archive(output, self.root / "restored-race")
        self.assertEqual(restored["snapshot"], exported["snapshot"])
        self.assertEqual(restored["project_id"], exported["project_id"])
        self.assertEqual(attempted, ["busy"])

    def test_export_serializes_second_process_commit_and_purge(self) -> None:
        original = archive._manifest_history
        outcomes = []
        script = """
import sys
from lixity.research import api
from lixity.research.repository import ResearchStorageError
try:
    if sys.argv[2] == "commit":
        api.create_dossier(sys.argv[1], "Concurrent", "Synthetic note.")
    else:
        api.purge(sys.argv[1], sys.argv[3])
except ResearchStorageError as error:
    if not str(error).startswith("Research writer is busy; retry after it finishes:"):
        raise
    print("busy")
else:
    print("committed")
"""

        def competing_writers(repository, snapshot):
            history = original(repository, snapshot)
            for operation in ("commit", "purge"):
                result = subprocess.run(  # noqa: S603 - fixed interpreter and synthetic test arguments
                    [sys.executable, "-c", script, str(self.project), operation,
                     self.ingested["source_id"]], capture_output=True, text=True, timeout=30,
                    check=True,
                )
                outcomes.append(result.stdout.strip())
            return history

        output = self.root / "process-race.tar.gz"
        with patch.object(archive, "_manifest_history", side_effect=competing_writers):
            exported = export_archive(self.project, output)
        restored = restore_archive(output, self.root / "restored-process-race")
        self.assertEqual(restored["snapshot"], exported["snapshot"])
        self.assertEqual(outcomes, ["busy", "busy"])
        self.assertEqual(api.cite(self.root / "restored-process-race", self.passage_id)["verbatim"],
                         "The reading room opened in 1924.")

    def test_export_rejects_store_and_cache_destinations_without_mutation(self) -> None:
        original = Repository(self.project)
        snapshot = original.snapshot()
        destinations = (
            Path("research"),
            Path("research/HEAD.json"),
            Path("research/project.json"),
            Path(f"research/manifests/{snapshot.digest}.json"),
            original.record_path(snapshot.manifest.entries[0]).relative_to(self.project),
            next((original.data / "blobs").iterdir()).relative_to(self.project),
            Path("research/new/nested/backup.tar.gz"),
            Path(".lixity/research"),
            Path(".lixity/research/writer.lock"),
            Path(".lixity/research/new/nested/backup.tar.gz"),
        )
        for index, relative in enumerate(destinations):
            with self.subTest(destination=relative):
                project = self.root / f"protected-{index}"
                shutil.copytree(self.project, project)
                before = {path.relative_to(project): path.read_bytes() if path.is_file() else None
                          for path in project.rglob("*")}
                lock = project / ".lixity/research/writer.lock"
                lock_inode = lock.stat().st_ino
                with self.assertRaisesRegex(ResearchError, "outside.*research store.*cache"):
                    export_archive(project, project / relative)
                after = {path.relative_to(project): path.read_bytes() if path.is_file() else None
                         for path in project.rglob("*")}
                self.assertEqual(after, before)
                self.assertEqual(lock.stat().st_ino, lock_inode)
                self.assertEqual(list(project.rglob(".tmp-export-*")), [])

    def test_export_rejects_symlink_aliases_into_store_and_cache(self) -> None:
        for index, relative in enumerate(("research", ".lixity/research", "research/HEAD.json")):
            with self.subTest(target=relative):
                project = self.root / f"alias-project-{index}"
                shutil.copytree(self.project, project)
                protected = project / relative
                alias = self.root / f"output-alias-{index}"
                alias.symlink_to(protected, target_is_directory=protected.is_dir())
                output = alias / "new/backup.tar.gz" if protected.is_dir() else alias
                before = {path.relative_to(project): path.read_bytes() if path.is_file() else None
                          for path in project.rglob("*")}
                with self.assertRaisesRegex(ResearchError, "outside.*research store.*cache"):
                    export_archive(project, output)
                after = {path.relative_to(project): path.read_bytes() if path.is_file() else None
                         for path in project.rglob("*")}
                self.assertEqual(after, before)
                self.assertTrue(alias.is_symlink())
                self.assertEqual(list(project.rglob(".tmp-export-*")), [])

    def test_export_allows_project_root_backup_and_overwrite(self) -> None:
        output = self.project / "backup.tar.gz"
        first = export_archive(self.project, output)
        api.create_dossier(self.project, "Later note", "Synthetic update.")
        second = export_archive(self.project, output)
        self.assertNotEqual(second["snapshot"], first["snapshot"])
        restored = restore_archive(output, self.root / "root-backup-restored")
        self.assertEqual(restored["snapshot"], second["snapshot"])
        sibling = self.project / "research-backups" / "backup.tar.gz"
        exported = export_archive(self.project, sibling)
        restored = restore_archive(sibling, self.root / "sibling-backup-restored")
        self.assertEqual(restored["snapshot"], exported["snapshot"])

    def test_export_matches_restore_uncompressed_size_boundary(self) -> None:
        output = self.root / "size-boundary.tar.gz"
        export_archive(self.project, output)
        with tarfile.open(output) as packed:
            # Measure actual regular member payloads, independently of the inventory.
            total = sum(member.size for member in packed.getmembers() if member.isfile())
            metadata_size = packed.getmember("EXPORT_MANIFEST.json").size
        self.assertGreater(metadata_size, 1)

        for limit in (total + 1, total):
            with self.subTest(limit=limit), patch.object(archive, "MAX_UNCOMPRESSED_BYTES", limit):
                exported = export_archive(self.project, output)
                restored = restore_archive(output, self.root / f"size-restored-{limit}")
                self.assertEqual(restored["snapshot"], exported["snapshot"])
                with tarfile.open(output) as packed:
                    self.assertEqual(sum(member.size for member in packed.getmembers()
                                         if member.isfile()), total)

        previous = output.read_bytes()
        for limit in (total - 1, total - metadata_size):
            with (
                self.subTest(limit=limit),
                patch.object(archive, "MAX_UNCOMPRESSED_BYTES", limit),
                self.assertRaisesRegex(ResearchError, "uncompressed size safety ceiling"),
            ):
                export_archive(self.project, output)
            self.assertEqual(output.read_bytes(), previous)
            self.assertEqual(list(self.root.glob(".tmp-export-*")), [])

    def test_export_rejects_oversize_before_candidate_creation(self) -> None:
        output = self.root / "oversize.tar.gz"
        export_archive(self.project, output)
        previous = output.read_bytes()
        with (
            patch.object(archive, "MAX_UNCOMPRESSED_BYTES", 1),
            patch.object(archive.tempfile, "mkstemp", side_effect=OSError("candidate allocation failed")),
            self.assertRaisesRegex(ResearchError, "uncompressed size safety ceiling"),
        ):
            export_archive(self.project, output)
        self.assertEqual(output.read_bytes(), previous)
        self.assertEqual(list(self.root.glob(".tmp-export-*")), [])

    def test_export_prepublication_failures_preserve_existing_archive(self) -> None:
        output = self.root / "existing-valid.tar.gz"
        exported = export_archive(self.project, output)
        previous = output.read_bytes()
        failures = (
            patch.object(tarfile.TarFile, "addfile", side_effect=OSError("tar write failed")),
            patch.object(archive, "_file_digest_and_size", side_effect=OSError("source read failed")),
            patch.object(archive._HashingReader, "read", side_effect=OSError("source copy failed")),
            patch.object(archive.os, "fsync", side_effect=OSError("candidate sync failed")),
            patch.object(archive.os, "replace", side_effect=OSError("replace failed")),
        )
        for index, failure in enumerate(failures):
            with self.subTest(failure=index), failure, self.assertRaises((OSError, ResearchStorageError)):
                export_archive(self.project, output)
            self.assertEqual(output.read_bytes(), previous)
            self.assertEqual(list(self.root.glob(".tmp-export-*")), [])
        restored = restore_archive(output, self.root / "restored-existing")
        self.assertEqual(restored["snapshot"], exported["snapshot"])

    def test_export_interrupt_preserves_output_and_propagates(self) -> None:
        output = self.root / "interrupted.tar.gz"
        export_archive(self.project, output)
        previous = output.read_bytes()
        with (
            patch.object(tarfile.TarFile, "addfile", side_effect=KeyboardInterrupt),
            self.assertRaises(KeyboardInterrupt),
        ):
            export_archive(self.project, output)
        self.assertEqual(output.read_bytes(), previous)
        self.assertEqual(list(self.root.glob(".tmp-export-*")), [])
        # The exception must release the writer lock as well as clean the candidate.
        api.create_dossier(self.project, "After interrupt", "Synthetic note.")

    def test_export_directory_sync_failure_reports_published_uncertainty(self) -> None:
        output = self.root / "published.tar.gz"
        export_archive(self.project, output)
        changed = api.create_dossier(self.project, "New note", "Synthetic note.")
        with (
            patch.object(archive, "sync_directory", side_effect=OSError("directory sync failed")),
            self.assertRaisesRegex(ResearchStorageError, "published.*durability"),
        ):
            export_archive(self.project, output)
        restored = restore_archive(output, self.root / "restored-published")
        self.assertEqual(restored["snapshot"], changed["snapshot"])
        self.assertEqual(list(self.root.glob(".tmp-export-*")), [])

    def test_export_rejects_damaged_content_addressed_blob(self) -> None:
        output = self.root / "before-damage.tar.gz"
        export_archive(self.project, output)
        previous = output.read_bytes()
        blob = next((self.project / "research" / "blobs").iterdir())
        blob.write_bytes(b"Damaged synthetic retained bytes.")
        with self.assertRaisesRegex(ResearchStorageError, "checksum"):
            export_archive(self.project, output)
        self.assertEqual(output.read_bytes(), previous)
        self.assertEqual(list(self.root.glob(".tmp-export-*")), [])

    def test_export_rejects_bytes_changed_after_inventory(self) -> None:
        output = self.root / "stable.tar.gz"
        export_archive(self.project, output)
        previous = output.read_bytes()
        original = archive._file_digest_and_size

        def change_after_checksum(path):
            result = original(path)
            if "revisions" in path.parts:
                path.write_bytes(path.read_bytes()[:-1] + b" ")
            return result

        with (
            patch.object(archive, "_file_digest_and_size", side_effect=change_after_checksum),
            self.assertRaisesRegex(ResearchError, "checksum|changed"),
        ):
            export_archive(self.project, output)
        self.assertEqual(output.read_bytes(), previous)
        self.assertEqual(list(self.root.glob(".tmp-export-*")), [])

    def write_manifest_archive(self, name: str, payload: bytes) -> Path:
        source = self.root / name
        with tarfile.open(source, "w") as target:
            member = tarfile.TarInfo("EXPORT_MANIFEST.json")
            member.size = len(payload)
            target.addfile(member, io.BytesIO(payload))
        return source

    def test_restore_rejects_non_object_export_manifest(self) -> None:
        for index, value in enumerate((None, [], "text", 7, True)):
            with self.subTest(value=value):
                source = self.write_manifest_archive(f"bad-shape-{index}.tar", json.dumps(value).encode())
                destination = self.root / f"bad-target-{index}"
                with self.assertRaisesRegex(ResearchError, "manifest.*object|object.*manifest"):
                    restore_archive(source, destination)
                self.assertFalse((destination / "research").exists())
                self.assertEqual(list(destination.glob(".restore-stage-*")), [])

    def test_cli_restore_rejects_non_object_manifest_without_traceback(self) -> None:
        source = self.write_manifest_archive("bad-cli.tar", b"null")
        destination = self.root / "bad-cli-target"
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            code = main(["research", "restore", "--from", str(source), "--to", str(destination)])
        self.assertEqual(code, 1)
        self.assertNotIn("Traceback", stderr.getvalue())
        self.assertIn("object", stderr.getvalue())
        self.assertFalse((destination / "research").exists())
        self.assertEqual(list(destination.glob(".restore-stage-*")), [])

    def test_restore_validates_envelope_fields_before_reading_inventory_paths(self) -> None:
        snapshot = Repository(self.project).snapshot()
        envelope = {
            "schema_version": "research-export-local/1",
            "project_id": snapshot.project.id,
            "snapshot": snapshot.digest,
            "files": {"research/missing": {"sha256": "0" * 64, "byte_length": 1}},
        }
        cases = [
            ({"files": value}, "no file entries") for value in (None, [], {}, "text", True)
        ]
        cases += [({"files": {"research/missing": value}}, "Invalid.*metadata")
                  for value in (None, [], "text", 7, True)]
        cases += [({"files": {"research/missing": value}}, "Invalid.*digest")
                  for value in ({}, {"sha256": None}, {"sha256": 7},
                                {"sha256": "g" * 64}, {"sha256": "0" * 63})]
        cases += [({"files": {"research/missing": {"sha256": "0" * 64, "byte_length": value}}},
                   "Invalid.*byte_length") for value in (True, -1, 1.5, "1", None)]
        cases += [({"snapshot": value}, "Invalid.*snapshot")
                  for value in (None, True, [], "../bad", "g" * 64)]
        cases += [({"project_id": value}, "Invalid.*project")
                  for value in (None, True, [], "urn:uuid:bad")]
        cases += [({"schema_version": value}, "Unsupported export schema")
                  for value in (None, [], "research-export-local/99")]
        for index, (changes, message) in enumerate(cases):
            with self.subTest(changes=changes):
                source = self.write_manifest_archive(f"invalid-fields-{index}.tar",
                                                     json.dumps(envelope | changes).encode())
                destination = self.root / f"invalid-fields-{index}"
                with self.assertRaisesRegex(ResearchError, message):
                    restore_archive(source, destination)
                self.assertFalse((destination / "research").exists())
                self.assertEqual(list(destination.iterdir()), [])

    def test_restore_rejects_invalid_json_and_encoding(self) -> None:
        for index, content in enumerate((b'{"schema_version":', b"{bad json}", b"\xff")):
            with self.subTest(content=content):
                source = self.write_manifest_archive(f"invalid-json-{index}.tar", content)
                destination = self.root / f"invalid-json-{index}"
                with self.assertRaisesRegex(ResearchError, "Invalid or unreadable"):
                    restore_archive(source, destination)
                self.assertEqual(list(destination.iterdir()), [])

    def test_restore_rejects_duplicate_manifest_members(self) -> None:
        source = self.root / "duplicate.tar.gz"
        export_archive(self.project, source)
        duplicate = self.root / "duplicate.tar"
        with tarfile.open(source) as original, tarfile.open(duplicate, "w") as target:
            for member in original.getmembers():
                stream = original.extractfile(member)
                assert stream is not None
                content = stream.read()
                target.addfile(member, io.BytesIO(content))
                if member.name == "EXPORT_MANIFEST.json":
                    target.addfile(member, io.BytesIO(content))
        destination = self.root / "duplicate-target"
        with self.assertRaisesRegex(ResearchError, "Duplicate"):
            restore_archive(duplicate, destination)
        self.assertEqual(list(destination.iterdir()), [])

    def test_restore_rejects_nonregular_manifest_member(self) -> None:
        for index, kind in enumerate((tarfile.DIRTYPE, tarfile.SYMTYPE, tarfile.FIFOTYPE)):
            source = self.root / f"nonregular-{index}.tar"
            with tarfile.open(source, "w") as target:
                member = tarfile.TarInfo("EXPORT_MANIFEST.json")
                member.type = kind
                member.linkname = "research/project.json" if kind == tarfile.SYMTYPE else ""
                target.addfile(member)
            destination = self.root / f"nonregular-{index}"
            with self.assertRaisesRegex(ResearchError, "regular file|Unsupported archive member"):
                restore_archive(source, destination)
            self.assertEqual(list(destination.iterdir()), [])

    def test_restore_accepts_legacy_inventory_without_byte_lengths(self) -> None:
        source = self.root / "lengths.tar.gz"
        exported = export_archive(self.project, source)
        legacy = self.root / "legacy.tar"
        with tarfile.open(source) as original, tarfile.open(legacy, "w") as target:
            for member in original.getmembers():
                stream = original.extractfile(member)
                assert stream is not None
                content = stream.read()
                if member.name == "EXPORT_MANIFEST.json":
                    envelope = json.loads(content)
                    for entry in envelope["files"].values():
                        del entry["byte_length"]
                    content = json.dumps(envelope).encode()
                    member.size = len(content)
                target.addfile(member, io.BytesIO(content))
        restored = restore_archive(legacy, self.root / "legacy-target")
        self.assertEqual(restored["snapshot"], exported["snapshot"])

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
        self.assertFalse((target_dir / "research" / ".cache").exists())
        for relative in manifest_json["files"]:
            self.assertEqual((target_dir / relative).read_bytes(),
                             (self.project / relative).read_bytes())

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
