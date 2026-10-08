"""Synthetic raster captures preserve exact identity and authored history."""

import contextlib
import io
import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from lixity.cli import main
from lixity.research import api
from lixity.research.models import Extraction, Passage, Reference, Source, Tombstone
from lixity.research.repository import Repository, ResearchConflictError, ResearchError


def png(width=1, height=1):
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00")) + chunk(b"IEND", b""))


# A public-format, synthetic one-pixel JPEG; no manuscript or external fixture.
JPEG = bytes.fromhex(
    "ffd8ffe000104a46494600010100000100010000"
    "ffdb004300" + "01" * 64 +
    "ffc0000b080001000101011100"
    "ffc40014000100000000000000000000000000000000"
    "ffc40014100100000000000000000000000000000000"
    "ffda0008010100003f003fffd9"
)


class TestResearchImages(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        self.project_id = api.init(self.project, title="Synthetic image project")["project_id"]
        self.file = Path(self.temp.name) / "picture.png"
        self.file.write_bytes(png())
        self.dossier = api.create_dossier(self.project, "Image note", "# Notes\n\nOriginal note.")["dossier_id"]

    def capture(self, **kwargs):
        return api.ingest(self.project, self.file, allow_retention=True, **kwargs)

    def attach(self, **kwargs):
        loaded = api.get_record(self.project, "dossier", self.dossier)
        args = {"filename": "picture.png", "expected_snapshot": loaded["snapshot"],
                "expected_revision": loaded["record"]["revision"], "allow_retention": True, "alt": "Synthetic image"}
        args.update(kwargs)
        return api.attach_dossier_image(self.project, self.dossier, png(), **args)

    def test_png_capture_has_no_fictional_text_records(self):
        captured = self.capture(context={"provenance_note": "Synthetic specimen"})
        snapshot = Repository(self.project).snapshot()
        version = snapshot.records[captured["source_version_id"]]
        self.assertEqual(version.blob.media_type, "image/png")
        self.assertEqual(captured["passages"], 0)
        self.assertFalse(any(isinstance(record, (Extraction, Passage)) for record in snapshot.records.values()))
        self.assertEqual(api.get_source(self.project, captured["source_id"])["media_type"], "image/png")
        self.assertEqual(api.list_sources(self.project)["sources"][0]["media_type"], "image/png")
        self.assertTrue(api.audit(self.project)["ok"])

    def test_jpeg_capture_and_exact_reader(self):
        result = api.ingest_image(self.project, JPEG, filename="one.jpeg", allow_retention=True)
        image = api.read_image(self.project, project_id=self.project_id, source_id=result["source_id"],
                               version_id=result["source_version_id"])
        self.assertEqual(image["content"], JPEG)
        self.assertEqual(image["media_type"], "image/jpeg")

    def test_retention_is_explicit_for_both_image_operations(self):
        with self.assertRaisesRegex(ResearchError, "retention"):
            api.ingest_image(self.project, png(), filename="one.png")
        with self.assertRaisesRegex(ResearchError, "retention"):
            self.attach(allow_retention=False)

    def test_bad_formats_dimensions_extensions_and_bounded_size(self):
        for data, filename in ((b"<svg></svg>", "one.png"), (png(0, 1), "one.png"),
                               (png(8001, 8000), "one.png"), (png(), "one.jpg"),
                               (png()[:-1], "one.png"), (JPEG[:-2], "one.jpg"),
                               (b"x" * (16 * 1024 * 1024 + 1), "one.png")):
            with self.subTest(filename=filename, length=len(data)), self.assertRaises(ResearchError):
                api.ingest_image(self.project, data, filename=filename, allow_retention=True)

    def test_reader_rejects_foreign_project_wrong_source_text_and_corrupt_blob(self):
        first = self.capture()
        other = api.ingest_image(self.project, JPEG, filename="one.jpg", allow_retention=True)
        for project_id, source_id, version_id in ((uuid4().urn, first["source_id"], first["source_version_id"]),
                                                 (self.project_id, other["source_id"], first["source_version_id"])):
            with self.assertRaises(ResearchError):
                api.read_image(self.project, project_id=project_id, source_id=source_id, version_id=version_id)
        text = Path(self.temp.name) / "one.txt"
        text.write_text("Synthetic text", encoding="utf-8")
        captured = api.ingest(self.project, text, allow_retention=True)
        with self.assertRaisesRegex(ResearchError, "image"):
            api.read_image(self.project, project_id=self.project_id, source_id=captured["source_id"],
                           version_id=captured["source_version_id"])
        version = Repository(self.project).snapshot().records[first["source_version_id"]]
        (self.project / "research" / "blobs" / version.blob.sha256).write_bytes(b"corrupt")
        with self.assertRaises(ResearchError):
            api.read_image(self.project, project_id=self.project_id, source_id=first["source_id"],
                           version_id=first["source_version_id"])
        self.assertFalse(api.audit(self.project)["ok"])

    def test_image_analysis_and_comparison_refuse_nontext(self):
        captured = self.capture()
        with self.assertRaisesRegex(ResearchError, "textual analysis"):
            api.analyze_source(self.project, captured["source_id"])
        with self.assertRaisesRegex(ResearchError, "textual analysis"):
            api.compare_source(self.project, captured["source_id"], "Synthetic manuscript.")

    def test_atomic_attachment_read_section_history_and_default_reason(self):
        result = self.attach(section="Notes", caption="A local specimen.", origin_url="https://example.org/specimen")
        self.assertEqual(result["record"]["revision"], 2)
        self.assertIn("![Synthetic image](lixity:image/", result["record"]["body"])
        self.assertTrue(result["record"]["change"]["reason"].startswith("Attached image "))
        self.assertEqual(result["project_id"], self.project_id)
        self.assertEqual(result["images"][0]["context"]["origin_url"], "https://example.org/specimen")
        full = api.get_dossier(self.project, self.dossier)
        section = api.get_dossier(self.project, self.dossier, section="Notes")
        self.assertEqual(full["project_id"], self.project_id)
        self.assertEqual(section["images"], full["images"])
        self.assertEqual(api.get_record(self.project, "dossier", self.dossier, revision=1)["images"], [])
        self.assertEqual(api.record_history(self.project, "dossier", self.dossier)["revisions"][0]["images"], full["images"])

    def test_attachment_preserves_existing_dossier_bytes(self):
        original = "# Notes\r\n\r\nOriginal note.  \r\n\r\n"
        self.dossier = api.create_dossier(self.project, "Exact original body", original)["dossier_id"]
        result = self.attach(caption="Synthetic caption.\r\nSecond line.")
        self.assertTrue(result["record"]["body"].startswith(original))
        self.assertNotIn("\r\r", result["record"]["body"])
        self.assertNotIn("\n", result["record"]["body"].replace("\r\n", ""))

    def test_failed_or_stale_joint_save_accepts_neither_capture_nor_revision(self):
        before = Repository(self.project).snapshot()
        with self.assertRaises(ResearchConflictError):
            self.attach(expected_snapshot="0" * 64)
        with self.assertRaises(ResearchError):
            self.attach(section="Missing")
        with patch("lixity.research.repository.replace_head", side_effect=OSError("Synthetic publication failure")), self.assertRaises(OSError):
            self.attach()
        after = Repository(self.project).snapshot()
        self.assertEqual(before.digest, after.digest)
        self.assertEqual(before.revisions, after.revisions)
        self.assertFalse(any(isinstance(record, Source) for record in after.records.values()))

    def test_attachment_inside_unclosed_code_block_cannot_accept_orphan_image(self):
        self.dossier = api.create_dossier(self.project, "Unclosed literal", "# Notes\n\n```\nLiteral data.")["dossier_id"]
        before = Repository(self.project).snapshot()
        with self.assertRaisesRegex(ResearchError, "code"):
            self.attach()
        self.assertEqual(Repository(self.project).snapshot().digest, before.digest)
        self.assertEqual(api.list_sources(self.project)["sources"], [])

    def test_legacy_missing_and_malformed_image_data_remains_readable_and_auditable(self):
        missing = f"![Unknown](lixity:image/{uuid4().urn}/{uuid4().urn})"
        malformed = "![Old literal](lixity:image/not-an-id/old-version)"
        # Release 2.0 retained these body bytes as inert data. Build that exact
        # former-release fixture, then exercise current reads without patches.
        with (patch("lixity.research.images.validate_image_changes"),
              patch("lixity.research.images.resolve_dossier_images", return_value=[])):
            legacy = api.create_dossier(self.project, "Legacy data", missing + "\n\n" + malformed)["dossier_id"]
        view = api.get_record(self.project, "dossier", legacy)
        self.assertEqual(view["images"][0]["availability"], "missing")
        self.assertIsNone(view["images"][0]["url"])
        self.assertIsNone(view["images"][0]["title"])
        self.assertFalse(api.audit(self.project)["ok"])
        api.revise_record(self.project, "dossier", legacy, changes={"title": "Renamed legacy data"},
                          expected_snapshot=view["snapshot"], expected_revision=1,
                          change_kind="correction", reason="Preserve old body data.")
        self.assertEqual(api.get_record(self.project, "dossier", legacy)["record"]["body"], missing + "\n\n" + malformed)
        with self.assertRaises(ResearchError):
            api.create_dossier(self.project, "New missing pin", missing)
        with self.assertRaises(ResearchError):
            api.create_dossier(self.project, "New malformed pin", malformed)

    def test_reference_literals_and_invalid_or_foreign_references(self):
        from lixity.research.images import extract_image_references
        captured = self.capture()
        literal = f"![alt](lixity:image/{captured['source_id']}/{captured['source_version_id']})"
        self.assertEqual(len(extract_image_references(literal)), 1)
        for body in (f"`{literal}`", f"``{literal}``", f"```md\n{literal}\n```", f"~~~\n{literal}\n~~~", "\\" + literal):
            self.assertEqual(extract_image_references(body), [])
        for target in ("not-a-uuid/" + captured["source_version_id"], captured["source_id"] + "/" + uuid4().urn):
            with self.assertRaises(ResearchError):
                api.create_dossier(self.project, "Invalid ref", f"![alt](lixity:image/{target})")
        self.assertEqual(len(extract_image_references(f"``code ` token`` {literal}")), 1)

    def test_alternative_text_preserves_brackets_backslashes_and_code_punctuation(self):
        alt = r"Specimen [A] \archive `label`"
        result = self.attach(alt=alt)
        self.assertEqual(result["images"][0]["alt"], alt)

    def test_dossier_excerpt_describes_image_without_changing_body_or_code_literals(self):
        result = self.attach(alt=r"Synthetic [A] \archive")
        identifier = self.dossier
        original = result["record"]["body"]
        excerpt = next(row["excerpt"] for row in api.list_dossiers(self.project)["dossiers"] if row["id"] == identifier)
        self.assertIn(r"Synthetic [A] \archive", excerpt)
        self.assertNotIn("lixity:image/", excerpt)
        self.assertNotIn("urn:uuid:", excerpt)
        self.assertEqual(api.get_record(self.project, "dossier", identifier)["record"]["body"], original)
        self.assertEqual(api.get_record(self.project, "dossier", identifier, revision=1)["record"]["body"], "# Notes\n\nOriginal note.")
        image = result["images"][0]
        token = f"![literal](lixity:image/{image['source_id']}/{image['source_version_id']})"
        for body in (f"`{token}`", f"~~~\n{token}\n~~~", "\\" + token):
            dossier = api.create_dossier(self.project, "Literal note", body)["dossier_id"]
            row = next(row for row in api.list_dossiers(self.project)["dossiers"] if row["id"] == dossier)
            self.assertEqual(row["excerpt"], body)

    def test_png_crc_and_animation_rejection(self):
        invalid = bytearray(png())
        invalid[29] ^= 1
        animation = b"acTL" + struct.pack(">II", 100, 0)
        animated = (png()[:33] + struct.pack(">I", 8) + animation
                    + struct.pack(">I", zlib.crc32(animation)) + png()[33:])
        for content in (bytes(invalid), animated):
            with self.assertRaises(ResearchError):
                api.ingest_image(self.project, content, filename="one.png", allow_retention=True)

    def test_source_purge_retains_history_placeholders_and_cannot_create_new_purged_pins(self):
        result = self.attach()
        image = result["images"][0]
        body = result["record"]["body"]
        api.purge(self.project, image["source_id"])
        tombstone = Repository(self.project).snapshot().lifecycle[("purge", "source_version", image["source_version_id"])]
        self.assertEqual(tombstone.schema_version, "research-local/2")
        self.assertEqual(tombstone.source_ref, Reference(id=image["source_id"]))
        self.assertEqual(api.get_record(self.project, "dossier", self.dossier)["images"][0]["availability"], "purged")
        loaded = api.get_record(self.project, "dossier", self.dossier)
        api.revise_record(self.project, "dossier", self.dossier, changes={"title": "Retained historical pin"},
                          expected_snapshot=loaded["snapshot"], expected_revision=2,
                          change_kind="correction", reason="Rename while retaining the source pin.")
        self.assertTrue(api.audit(self.project)["ok"])
        with self.assertRaisesRegex(ResearchError, "purged"):
            api.create_dossier(self.project, "New purged pin", body)

    def test_prepare_rejects_new_mismatched_or_purged_pins_before_save(self):
        captured = self.capture()
        other = api.ingest_image(self.project, JPEG, filename="other.jpg", allow_retention=True)
        body = f"![wrong owner](lixity:image/{other['source_id']}/{captured['source_version_id']})"
        with self.assertRaisesRegex(ResearchError, "match"):
            api.prepare_record_revision(self.project, "dossier", self.dossier, base_revision=1, changes={"body": body})
        api.purge(self.project, captured["source_id"])
        body = f"![purged](lixity:image/{captured['source_id']}/{captured['source_version_id']})"
        with self.assertRaisesRegex(ResearchError, "purged"):
            api.prepare_record_revision(self.project, "dossier", self.dossier, base_revision=1, changes={"body": body})

    def test_cli_image_ingest_and_sources_details_are_native(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["research", "ingest", "--project", str(self.project), "--file", str(self.file), "--allow-retention"])
        self.assertEqual(status, 0)
        captured = json.loads(output.getvalue())
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["research", "sources", "--project", str(self.project), "--source-id", captured["source_id"]])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["media_type"], "image/png")

    def test_image_checkpoint_can_resume_verified_binary_without_extraction(self):
        def interrupted(stage, message):
            if stage == "commit":
                raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            api.ingest_checkpoint(self.project, [self.file], checkpoint="image.json", allow_retention=True,
                                  progress_callback=interrupted)
        result = api.ingest_checkpoint(self.project, checkpoint="image.json", resume=True, allow_retention=True)
        self.assertTrue(result["complete"])
        self.assertEqual(result["items"][0]["passages"], 0)
        self.assertTrue(api.audit(self.project)["ok"])

    def test_image_checkpoint_recovers_lost_receipt_without_duplicate(self):
        def interrupted(stage, message):
            if stage == "complete":
                raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            api.ingest_checkpoint(self.project, [self.file], checkpoint="image.json", allow_retention=True,
                                  progress_callback=interrupted)
        head = Repository(self.project).snapshot().digest
        result = api.ingest_checkpoint(self.project, checkpoint="image.json", resume=True, allow_retention=True)
        self.assertTrue(result["complete"])
        self.assertEqual(Repository(self.project).snapshot().digest, head)
        self.assertEqual(len(api.list_sources(self.project)["sources"]), 1)

    def test_image_checkpoint_rejects_corrupt_prepared_media_type(self):
        def interrupted(stage, message):
            if stage == "commit":
                raise KeyboardInterrupt
        with self.assertRaises(KeyboardInterrupt):
            api.ingest_checkpoint(self.project, [self.file], checkpoint="image.json", allow_retention=True,
                                  progress_callback=interrupted)
        checkpoint = self.project / ".lixity" / "research" / "imports" / "image.json"
        data = json.loads(checkpoint.read_text(encoding="utf-8"))
        prepared = data["items"][0]["prepared"]
        for record in prepared["records"]:
            if record["kind"] == "source_version":
                record["blob"]["media_type"] = "image/jpeg"
        prepared["blobs"][0]["media_type"] = "image/jpeg"
        checkpoint.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaisesRegex(ResearchError, "media type"):
            api.ingest_checkpoint(self.project, checkpoint="image.json", resume=True, allow_retention=True)
        self.assertEqual(api.list_sources(self.project)["sources"], [])

    def test_image_capture_does_not_retry_an_external_publication_conflict(self):
        original_commit = Repository.commit
        raced = False

        def racing_commit(repository, additions, blobs, expected, **kwargs):
            nonlocal raced
            if not raced and blobs:
                raced = True
                api.create_dossier(self.project, "Concurrent note", "Synthetic external edit.")
            return original_commit(repository, additions, blobs, expected, **kwargs)

        with patch.object(Repository, "commit", racing_commit), self.assertRaises(ResearchConflictError):
            api.ingest_image(self.project, png(), filename="one.png", allow_retention=True)
        self.assertEqual(api.list_sources(self.project)["sources"], [])

    def test_ordinary_raster_capture_does_not_retry_an_external_publication_conflict(self):
        original_commit = Repository.commit
        for name, content in (("one.png", png()), ("one.jpeg", JPEG)):
            with self.subTest(name=name):
                file = Path(self.temp.name) / name
                file.write_bytes(content)
                raced = False

                def racing_commit(repository, additions, blobs, expected, **kwargs):
                    nonlocal raced
                    if not raced and blobs:
                        raced = True
                        api.create_dossier(self.project, "Concurrent note", "Synthetic external edit.")
                    return original_commit(repository, additions, blobs, expected, **kwargs)

                with patch.object(Repository, "commit", racing_commit), self.assertRaises(ResearchConflictError):
                    api.ingest(self.project, file, allow_retention=True)
                self.assertEqual(api.list_sources(self.project)["sources"], [])

    def test_cli_raster_capture_reports_publication_conflict_without_accepting_source(self):
        original_commit = Repository.commit
        raced = False

        def racing_commit(repository, additions, blobs, expected, **kwargs):
            nonlocal raced
            if not raced and blobs:
                raced = True
                api.create_dossier(self.project, "Concurrent note", "Synthetic external edit.")
            return original_commit(repository, additions, blobs, expected, **kwargs)

        output = io.StringIO()
        error = io.StringIO()
        with patch.object(Repository, "commit", racing_commit), contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            status = main(["research", "ingest", "--project", str(self.project), "--file", str(self.file), "--allow-retention"])
        self.assertEqual(status, 1)
        self.assertIn("snapshot", error.getvalue().lower())
        self.assertEqual(api.list_sources(self.project)["sources"], [])

    def test_ordinary_text_capture_keeps_its_existing_unrelated_write_retry(self):
        text = Path(self.temp.name) / "one.txt"
        text.write_text("Synthetic original text.", encoding="utf-8")
        original_commit = Repository.commit
        raced = False

        def racing_commit(repository, additions, blobs, expected, **kwargs):
            nonlocal raced
            if not raced and blobs:
                raced = True
                api.create_dossier(self.project, "Concurrent note", "Synthetic external edit.")
            return original_commit(repository, additions, blobs, expected, **kwargs)

        with patch.object(Repository, "commit", racing_commit):
            result = api.ingest(self.project, text, allow_retention=True)
        self.assertEqual(result["passages"], 1)
        self.assertEqual(len(api.list_sources(self.project)["sources"]), 1)

    def test_legacy_mismatched_pin_does_not_gain_another_sources_purge_reason(self):
        first = self.capture()
        other = api.ingest_image(self.project, JPEG, filename="other.jpg", allow_retention=True)
        wrong = f"![Legacy mismatch](lixity:image/{other['source_id']}/{first['source_version_id']})"
        with patch("lixity.research.images.validate_image_changes"):
            legacy = api.create_dossier(self.project, "Former-release literal", wrong)["dossier_id"]
        before = api.get_record(self.project, "dossier", legacy)["images"][0]
        self.assertEqual(before["availability"], "missing")
        api.purge(self.project, first["source_id"], reason="Synthetic first-source-only reason")
        after = api.get_record(self.project, "dossier", legacy)["images"][0]
        self.assertEqual(after["availability"], "missing")
        self.assertIsNone(after["reason"])
        self.assertIsNone(after["url"])

    def test_purge_publication_rejects_forged_source_ownership(self):
        first = self.capture()
        other = api.ingest_image(self.project, JPEG, filename="other.jpg", allow_retention=True)
        repository = Repository(self.project)
        before = repository.snapshot()
        forged = Tombstone(**api.envelope(self.project_id, "test-author"), schema_version="research-local/2",
                           target_ref=Reference(id=first["source_version_id"]), source_ref=Reference(id=other["source_id"]),
                           target_kind="source_version", operation="purge", reason="Forged owner")
        with self.assertRaisesRegex(ResearchError, "ownership"):
            repository.commit([forged], {}, before, removals={first["source_version_id"]})
        self.assertEqual(repository.snapshot().digest, before.digest)
        self.assertEqual(api.read_image(self.project, project_id=self.project_id, source_id=first["source_id"],
                                        version_id=first["source_version_id"])["content"], png())

    def test_owner_bearing_purge_upgrades_manifest_and_restores_through_registry(self):
        first = self.capture()
        self.assertEqual(Repository(self.project).snapshot().manifest.schema_version, "research-manifest-local/1")
        api.purge(self.project, first["source_id"], version_id=first["source_version_id"])
        snapshot = Repository(self.project).snapshot()
        self.assertEqual(snapshot.manifest.schema_version, "research-manifest-local/2")
        tombstone = snapshot.lifecycle[("purge", "source_version", first["source_version_id"])]
        self.assertEqual(tombstone.schema_version, "research-local/2")
        self.assertEqual(tombstone.source_ref, Reference(id=first["source_id"]))
        archive = Path(self.temp.name) / "owner-v2.tar"
        api.export_archive(self.project, archive)
        restored = Path(self.temp.name) / "restored-v2"
        api.restore_archive(archive, restored)
        self.assertEqual(Repository(restored).snapshot().lifecycle[("purge", "source_version", first["source_version_id"])], tombstone)
        self.assertTrue(api.audit(restored)["ok"])

    def test_legacy_ownerless_purge_is_missing_and_keeps_old_encoding(self):
        first = self.capture()
        body = f"![Original pin](lixity:image/{first['source_id']}/{first['source_version_id']})"
        dossier = api.create_dossier(self.project, "Old image data", body)["dossier_id"]
        repository = Repository(self.project)
        before = repository.snapshot()
        old = Tombstone(**api.envelope(self.project_id, "old-author"), target_ref=Reference(id=first["source_version_id"]),
                        target_kind="source_version", operation="purge", reason="Legacy unknown ownership")
        self.assertNotIn("source_ref", old.model_dump(mode="json"))
        repository.commit([old], {}, before, removals={first["source_version_id"]})
        image = api.get_record(self.project, "dossier", dossier)["images"][0]
        self.assertEqual(image["availability"], "missing")
        self.assertIsNone(image["reason"])
        self.assertIsNone(image["url"])

    def test_purge_owner_field_requires_its_exact_versioned_contract(self):
        base = {**api.envelope(self.project_id, "test-author"), "target_ref": Reference(id=uuid4().urn),
                "target_kind": "source_version", "operation": "purge", "reason": "Synthetic owner check"}
        for changes in ({"source_ref": Reference(id=uuid4().urn)}, {"schema_version": "research-local/2"},
                        {"schema_version": "research-local/2", "source_ref": Reference(id=uuid4().urn), "operation": "withdraw"},
                        {"schema_version": "research-local/2", "source_ref": Reference(id=uuid4().urn), "target_kind": "source"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                Tombstone(**{**base, **changes})

    def test_refresh_history_withdrawal_purge_and_backup(self):
        result = self.attach()
        image = result["images"][0]
        first_version = image["source_version_id"]
        refreshed = api.ingest_image(self.project, JPEG, filename="one.jpg", source_id=image["source_id"], allow_retention=True)
        self.assertNotEqual(first_version, refreshed["source_version_id"])
        self.assertEqual(api.get_record(self.project, "dossier", self.dossier)["images"][0]["source_version_id"], first_version)
        api.withdraw(self.project, image["source_id"], version_id=first_version)
        self.assertEqual(api.get_record(self.project, "dossier", self.dossier)["images"][0]["availability"], "withdrawn")
        self.assertIsNone(api.get_record(self.project, "dossier", self.dossier)["images"][0]["url"])
        self.assertEqual(api.read_image(self.project, project_id=self.project_id, source_id=image["source_id"],
                                        version_id=first_version)["content"], png())
        api.purge(self.project, image["source_id"], version_id=first_version)
        tombstone = Repository(self.project).snapshot().lifecycle[("purge", "source_version", first_version)]
        self.assertEqual(tombstone.schema_version, "research-local/2")
        self.assertEqual(tombstone.source_ref, Reference(id=image["source_id"]))
        view = api.get_record(self.project, "dossier", self.dossier)
        self.assertEqual(view["images"][0]["availability"], "purged")
        self.assertIsNone(view["images"][0]["url"])
        self.assertTrue(api.audit(self.project)["ok"])
        archive = Path(self.temp.name) / "backup.tar"
        api.export_archive(self.project, archive)
        restored = Path(self.temp.name) / "restored"
        api.restore_archive(archive, restored)
        restored_tombstone = Repository(restored).snapshot().lifecycle[("purge", "source_version", first_version)]
        self.assertEqual(restored_tombstone, tombstone)
        self.assertEqual(api.get_record(restored, "dossier", self.dossier)["images"], view["images"])
        self.assertTrue(api.audit(restored)["ok"])
