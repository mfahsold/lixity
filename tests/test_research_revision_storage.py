"""Immutable authored revisions preserve accepted references and snapshot history."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

from pydantic import ValidationError

from lixity.research import api
from lixity.research.models import (
    Claim,
    Dossier,
    Manifest,
    Reference,
    RevisionChange,
    Source,
    reference,
)
from lixity.research.repository import Repository, ResearchConflictError, ResearchError, encode


class TestResearchRevisionStorage(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "project"
        api.init(self.project, title="Synthetic revision archive")
        result = api.create_dossier(self.project, "Original", "Original interpretation.")
        self.repository = Repository(self.project)
        self.original = self.repository.snapshot().get(Reference(id=result["dossier_id"]), Dossier)

    def revision(self, previous, **changes):
        values = previous.model_dump()
        values.update(schema_version="research-local/2", revision=previous.revision + 1,
                      change=RevisionChange(change_kind="correction", reason="Correct synthetic text.",
                                            previous_revision=previous.revision))
        values.update(changes)
        return type(previous).model_validate(values)

    def test_v1_bytes_unchanged_and_pinned_history_resolves_after_edit(self):
        original = self.repository.snapshot()
        before = {entry.ref: self.repository.record_path(entry).read_bytes() for entry in original.manifest.entries}
        self.assertEqual(original.manifest.schema_version, "research-manifest-local/1")
        self.assertNotIn(b'"change"', encode(self.original))
        second = self.revision(self.original, title="Corrected")
        changed = self.repository.commit([second], {}, original)
        loaded = self.repository.snapshot()
        self.assertEqual(changed.digest, loaded.digest)
        self.assertEqual(loaded.manifest.schema_version, "research-manifest-local/2")
        self.assertEqual(len(loaded.records), len(original.records))
        self.assertEqual(len(loaded.revisions), len(original.records) + 1)
        self.assertEqual(loaded.latest(self.original.id, Dossier), second)
        self.assertEqual(loaded.get(reference(self.original), Dossier), self.original)
        self.assertEqual(loaded.revisions[(second.id, 2)], second)
        for entry in original.manifest.entries:
            self.assertEqual(self.repository.record_path(entry).read_bytes(), before[entry.ref])
        self.assertTrue(api.audit(self.project)["ok"])

    def test_claim_keeps_original_dossier_pin_when_dossier_changes(self):
        claim_result = api.create_claim(self.project, title="Claim", statement="Synthetic claim.",
                                        dossier_id=self.original.id)
        before = self.repository.snapshot()
        claim = before.get(Reference(id=claim_result["claim_id"]), Claim)
        changed = self.repository.commit([self.revision(self.original, body="Revised interpretation.")], {}, before)
        self.assertEqual(changed.get(claim.dossier_ref, Dossier).body, "Original interpretation.")
        self.assertEqual(changed.latest(self.original.id, Dossier).body, "Revised interpretation.")

    def test_rejects_gap_overwrite_kind_change_and_stale_head(self):
        before = self.repository.snapshot()
        second = self.revision(self.original)
        with self.assertRaises(ResearchError):
            self.repository.commit([self.original], {}, before)
        gap = self.revision(second)
        with self.assertRaises(ResearchError):
            self.repository.commit([gap], {}, before)
        foreign_kind = Claim(**{key: value for key, value in self.original.model_dump().items()
                              if key in ("id", "revision", "project_id", "created_at", "created_by")},
                             title="Changed kind", statement="Invalid identity reuse.")
        with self.assertRaises(ResearchError):
            self.repository.commit([foreign_kind], {}, before)
        self.repository.commit([second], {}, before)
        with self.assertRaises(ResearchConflictError):
            self.repository.commit([self.revision(second)], {}, before)
        self.assertEqual(self.repository.snapshot().latest(self.original.id, Dossier).revision, 2)

    def test_revision_contract_rejects_invalid_metadata_and_immutable_kinds(self):
        values = self.original.model_dump()
        for update in (
            {"revision": 2},
            {"schema_version": "research-local/2"},
            {"revision": 2, "schema_version": "research-local/2"},
            {"revision": 2, "schema_version": "research-local/2",
             "change": {"change_kind": "correction", "reason": " ", "previous_revision": 1}},
            {"revision": 2, "schema_version": "research-local/2",
             "change": {"change_kind": "supersession", "reason": "A reason", "previous_revision": 2}},
        ):
            with self.subTest(update=update), self.assertRaises(ValidationError):
                Dossier.model_validate({**values, **update})
        with self.assertRaises(ValidationError):
            Source(**{key: value for key, value in values.items()
                      if key in ("id", "project_id", "created_at", "created_by")},
                   revision=2, title="Source", language="en")

    def test_failed_publication_keeps_head_and_cleans_only_its_unaccepted_revision(self):
        before = self.repository.snapshot()
        with patch("lixity.research.repository.replace_head", side_effect=OSError("interrupted")), self.assertRaises(OSError):
            self.repository.commit([self.revision(self.original, title="Unpublished")], {}, before)
        self.assertEqual(self.repository.snapshot().digest, before.digest)
        retry = self.revision(self.original, title="Successful retry")
        self.repository.commit([retry], {}, before)
        self.assertEqual(self.repository.snapshot().latest(self.original.id, Dossier), retry)

    def test_crash_orphan_is_preserved_before_a_different_revision_is_saved(self):
        before = self.repository.snapshot()
        second = self.revision(self.original, title="Previously written")
        from lixity.research.models import Entry
        from lixity.research.repository import digest
        entry = Entry(kind=second.kind, ref=reference(second), sha256=digest(encode(second)))
        path = self.repository.record_path(entry)
        path.write_bytes(encode(second))
        corrected = self.revision(self.original, title="Different edit")
        self.repository.commit([corrected], {}, before)
        preserved = path.with_name(f"2.{digest(encode(second))}.unpublished")
        self.assertEqual(preserved.read_bytes(), encode(second))
        self.assertEqual(path.read_bytes(), encode(corrected))
        self.assertEqual(self.repository.snapshot().latest(self.original.id, Dossier), corrected)
        self.assertTrue(api.audit(self.project)["ok"])

    def test_orphan_after_manifest_publication_recovers_without_accepting_old_draft(self):
        from lixity.research.models import Entry
        from lixity.research.repository import digest
        before = self.repository.snapshot()
        orphan = self.revision(self.original, title="Unaccepted draft")
        entry = Entry(kind=orphan.kind, ref=reference(orphan), sha256=digest(encode(orphan)))
        self.repository.record_path(entry).write_bytes(encode(orphan))
        manifest = Manifest(schema_version="research-manifest-local/2", project_id=before.project.id,
                            generation=before.manifest.generation + 1, parent=before.digest,
                            entries=[*before.manifest.entries, entry])
        manifest_content = encode(manifest)
        (self.project / "research" / "manifests" / f"{digest(manifest_content)}.json").write_bytes(manifest_content)
        replacement = self.revision(self.original, title="Reviewed replacement")
        self.repository.commit([replacement], {}, before)
        self.assertEqual(self.repository.snapshot().latest(self.original.id, Dossier), replacement)
        self.assertEqual(len(self.repository.snapshot().revisions), len(before.revisions) + 1)

    def test_invalid_or_foreign_orphans_fail_closed_without_moving_bytes(self):
        from lixity.research.models import Entry
        from lixity.research.repository import digest
        before = self.repository.snapshot()
        orphan = self.revision(self.original)
        entry = Entry(kind=orphan.kind, ref=reference(orphan), sha256=digest(encode(orphan)))
        path = self.repository.record_path(entry)
        for content in (b"invalid", encode(orphan.model_copy(update={"project_id": f"urn:uuid:{uuid4()}"})),
                        encode(orphan.model_copy(update={"id": f"urn:uuid:{uuid4()}"}))):
            path.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(ResearchError):
                self.repository.commit([self.revision(self.original, title="Rejected")], {}, before)
            self.assertEqual(path.read_bytes(), content)
            self.assertEqual(self.repository.snapshot().digest, before.digest)
        self.assertEqual(list(path.parent.glob("*.unpublished")), [])

    def test_interruption_during_orphan_preservation_or_replacement_is_retryable(self):
        from lixity.research.models import Entry
        from lixity.research.repository import digest, publish
        before = self.repository.snapshot()
        orphan = self.revision(self.original, title="Original crash orphan")
        replacement = self.revision(self.original, title="Retry after interruption")
        entry = Entry(kind=orphan.kind, ref=reference(orphan), sha256=digest(encode(orphan)))
        path = self.repository.record_path(entry)
        path.write_bytes(encode(orphan))
        preserved = path.with_name(f"2.{digest(encode(orphan))}.unpublished")

        def preserve_then_interrupt(target, content, **kwargs):
            publish(target, content, **kwargs)
            if target == preserved:
                raise OSError("Interrupted after preserving original bytes")

        with patch("lixity.research.repository.publish", side_effect=preserve_then_interrupt), self.assertRaises(OSError):
            self.repository.commit([replacement], {}, before)
        self.assertEqual(path.read_bytes(), encode(orphan))
        self.assertEqual(preserved.read_bytes(), encode(orphan))

        def replace_then_interrupt(target, content, **kwargs):
            publish(target, content, **kwargs)
            if target == path:
                raise OSError("Interrupted after publishing replacement")

        with patch("lixity.research.repository.publish", side_effect=replace_then_interrupt), self.assertRaises(OSError):
            self.repository.commit([replacement], {}, before)
        self.assertFalse(path.exists())
        self.assertEqual(preserved.read_bytes(), encode(orphan))
        self.assertEqual(self.repository.snapshot().digest, before.digest)
        self.repository.commit([replacement], {}, before)
        self.assertEqual(self.repository.snapshot().latest(self.original.id, Dossier), replacement)
        self.assertTrue(api.audit(self.project)["ok"])

    def test_error_after_head_publication_does_not_delete_accepted_revision(self):
        from lixity.research.repository import replace_head

        def published_then_failed(path, content):
            replace_head(path, content)
            raise OSError("Directory sync failed after replacement")

        second = self.revision(self.original, title="Accepted despite response failure")
        with patch("lixity.research.repository.replace_head", side_effect=published_then_failed), self.assertRaises(OSError):
            self.repository.commit([second], {}, self.repository.snapshot())
        self.assertEqual(self.repository.snapshot().latest(self.original.id, Dossier), second)
        self.assertTrue(api.audit(self.project)["ok"])

    def test_revision_cleanup_does_not_remove_failed_purge_recovery_artifacts(self):
        source_file = Path(self.temporary.name) / "source.txt"
        source_file.write_text("Synthetic source for purge recovery.", encoding="utf-8")
        source = api.ingest(self.project, source_file, allow_retention=True)
        original_head = (self.project / "research" / "HEAD.json").read_bytes()
        with patch("lixity.research.repository.replace_head", side_effect=OSError("interrupted")), self.assertRaises(OSError):
            api.purge(self.project, source["source_id"])
        # Purge's existing delete-before-HEAD recovery behavior is outside this
        # revision change. Do not make it worse by deleting its new tombstones.
        tombstones = list((self.project / "research" / "revisions" / "tombstone").glob("*/*.json"))
        self.assertEqual(len(tombstones), 2)
        self.assertEqual((self.project / "research" / "HEAD.json").read_bytes(), original_head)

    def test_all_history_is_validated_and_v1_cannot_accept_revisions(self):
        before = self.repository.snapshot()
        self.repository.commit([self.revision(self.original)], {}, before)
        current = self.repository.snapshot()
        values = current.manifest.model_dump()
        values["schema_version"] = "research-manifest-local/1"
        invalid = Manifest.model_validate(values)
        from lixity.research.repository import Snapshot
        with self.assertRaises(ResearchError):
            self.repository.validate(Snapshot(current.digest, invalid, current.records,
                                              revisions=current.revisions))
        invalid_original = Dossier.model_validate({**self.original.model_dump(),
                                                   "evidence_refs": [Reference(id=f"urn:uuid:{uuid4()}")]})
        invalid_history = {**current.revisions, (self.original.id, 1): invalid_original}
        with self.assertRaisesRegex(ResearchError, "pinned reference"):
            self.repository.validate(Snapshot(current.digest, current.manifest, current.records,
                                              revisions=invalid_history))
        historical_entry = next(entry for entry in current.manifest.entries if entry.ref == reference(self.original))
        self.repository.record_path(historical_entry).write_bytes(b"tampered historical record")
        self.assertFalse(api.audit(self.project)["ok"])

    def test_purge_keeps_history_and_only_allows_already_accepted_missing_refs(self):
        source_file = Path(self.temporary.name) / "source.txt"
        source_file.write_text("Synthetic retained source.", encoding="utf-8")
        source = api.ingest(self.project, source_file, allow_retention=True)
        api.reindex(self.project)
        passage_id = api.search(self.project, "retained")["hits"][0]["passage_id"]
        with_evidence = self.revision(self.original, evidence_refs=[Reference(id=passage_id)])
        self.repository.commit([with_evidence], {}, self.repository.snapshot())
        api.purge(self.project, source["source_id"])
        after_purge = self.repository.snapshot()
        self.repository.commit([self.revision(with_evidence, title="Edit after purge")], {}, after_purge)
        self.assertTrue(api.audit(self.project)["ok"])
        current = self.repository.snapshot()
        removed_evidence = self.revision(current.latest(self.original.id, Dossier), evidence_refs=[])
        current = self.repository.commit([removed_evidence], {}, current)
        with self.assertRaises(ResearchError):
            self.repository.commit([self.revision(removed_evidence, evidence_refs=[Reference(id=passage_id)])], {}, current)
        with self.assertRaises(ResearchError):
            self.repository.commit([], {}, current, removals={self.original.id})
