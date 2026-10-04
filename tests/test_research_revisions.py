"""Public revision workflows use synthetic records and preserve pinned evidence."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api
from lixity.research.models import Claim, Decision, Reference
from lixity.research.repository import Repository, ResearchConflictError, ResearchError


class TestResearchRevisions(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name) / "project"
        api.init(self.project, title="Synthetic revision project")
        self.source_file = Path(self.temp.name) / "source.txt"
        self.source_file.write_text("The reading room opened in 1924.", encoding="utf-8")
        self.source = api.ingest(self.project, self.source_file, allow_retention=True)
        self.passage = api.get_source(self.project, self.source["source_id"])["passages"][0]["id"]
        self.dossier = api.create_dossier(self.project, "Reading room", "Original note.", evidence_ids=[self.passage])["dossier_id"]
        self.claim = api.create_claim(self.project, title="Opening date", statement="Opened in 1924.", dossier_id=self.dossier)["claim_id"]
        self.link = api.link_evidence(self.project, claim_id=self.claim, passage_id=self.passage)["evidence_link_id"]
        self.decision = api.record_decision(self.project, title="Keep date", rationale="Follow the cited date.", claim_id=self.claim)["decision_id"]

    def revise(self, kind, identifier, changes, change_kind="correction"):
        loaded = api.get_record(self.project, kind, identifier)
        return api.revise_record(
            self.project, kind, identifier, changes=changes,
            expected_snapshot=loaded["snapshot"], expected_revision=loaded["record"]["revision"],
            change_kind=change_kind, reason="Author reviewed this change.", actor="test-author",
        )

    def test_prepare_revision_reconciles_unrelated_changes_without_writing(self):
        self.revise("claim", self.claim, {"place": "Reading room"})
        before = {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        preview = api.prepare_record_revision(self.project, "dossier", self.dossier,
                                              base_revision=1, changes={"body": "My draft."})
        self.assertEqual(preview["schema_version"], "research-revision-preview-local/1")
        self.assertTrue(preview["ready"])
        self.assertEqual(preview["conflicts"], [])
        self.assertEqual(preview["changes"], {"body": "My draft."})
        self.assertEqual(before, {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()})
        self.assertEqual(api.get_record(self.project, "dossier", self.dossier)["record"]["revision"], 1)

    def test_prepare_revision_preserves_nonoverlapping_changes_for_all_authored_types(self):
        for kind, identifier, concurrent, draft in (
            ("dossier", self.dossier, {"title": "Current title"}, {"body": "My note."}),
            ("claim", self.claim, {"place": "Library"}, {"statement": "A reviewed statement."}),
            ("evidence_link", self.link, {"relation": "qualifies"}, {"rationale": "My rationale."}),
            ("decision", self.decision, {"title": "Current decision"}, {"rationale": "My reason."}),
        ):
            with self.subTest(kind=kind):
                self.revise(kind, identifier, concurrent)
                preview = api.prepare_record_revision(self.project, kind, identifier,
                                                      base_revision=1, changes=draft)
                self.assertTrue(preview["ready"])
                current = preview["current"]
                saved = api.revise_record(self.project, kind, identifier, changes=preview["changes"],
                    expected_snapshot=current["snapshot"], expected_revision=current["record"]["revision"],
                    change_kind="correction", reason="Reviewed reconciliation", actor="second-author")
                self.assertEqual(saved["record"]["revision"], 3)
                self.assertEqual(saved["record"]["created_by"], "second-author")
                self.assertEqual(saved["record"]["change"]["previous_revision"], 2)
                for key, value in {**concurrent, **draft}.items():
                    self.assertEqual(saved["record"]["scope"].get(key) if key == "place" else saved["record"][key], value)
                self.assertEqual(api.get_record(self.project, kind, identifier, revision=1)["record"]["revision"], 1)

    def test_prepare_revision_requires_explicit_same_field_choice(self):
        self.revise("dossier", self.dossier, {"title": "Current title"})
        draft = {"title": "My title", "body": "My note."}
        preview = api.prepare_record_revision(self.project, "dossier", self.dossier,
                                              base_revision=1, changes=draft)
        self.assertFalse(preview["ready"])
        self.assertEqual(preview["conflicts"], [{"field": "title", "base": "Reading room",
                                              "current": "Current title", "mine": "My title"}])
        self.assertEqual(preview["changes"], {"body": "My note."})
        for choice in ("current", "mine"):
            resolved = api.prepare_record_revision(self.project, "dossier", self.dossier,
                base_revision=1, changes=draft, resolutions={"title": choice})
            self.assertTrue(resolved["ready"])
            self.assertEqual(resolved["changes"], {"body": "My note.", **({"title": "My title"} if choice == "mine" else {})})

    def test_decision_dossier_list_edits_and_batches_preserve_retained_pins(self):
        other = api.create_dossier(self.project, "Other note", "Other evidence.")["dossier_id"]
        decision = api.record_decision(self.project, title="Linked decision", rationale="Review the note.",
                                       dossier_ids=[self.dossier])["decision_id"]
        self.revise("dossier", self.dossier, {"body": "Current evidence."})
        self.revise("decision", decision, {"title": "Current decision title"})
        preview = api.prepare_record_revision(self.project, "decision", decision, base_revision=1,
                                              changes={"dossier_ids": [self.dossier, other]})
        self.assertTrue(preview["ready"])
        self.assertEqual(preview["current"]["record"]["dossier_refs"], [{"id": self.dossier, "revision": 1}])
        current = preview["current"]
        saved = api.revise_record(self.project, "decision", decision, changes=preview["changes"],
                                  expected_snapshot=current["snapshot"], expected_revision=2,
                                  change_kind="correction", reason="Reviewed the association list.")
        expected = [{"id": self.dossier, "revision": 1}, {"id": other, "revision": 1}]
        self.assertEqual(saved["record"]["dossier_refs"], expected)
        self.assertEqual(saved["record"]["title"], "Current decision title")
        operations = [{"kind": "decision", "id": decision, "expected_revision": 3,
                       "changes": {"dossier_ids": [self.dossier, other], "rationale": "Revisited the linked notes."},
                       "change_kind": "correction", "reason": "Reviewed together."}]
        group = api.prepare_record_revisions(self.project, operations)
        api.apply_record_revisions(self.project, group["operations"], expected_snapshot=group["snapshot"])
        self.assertEqual(api.get_record(self.project, "decision", decision)["record"]["dossier_refs"], expected)

    def test_decision_reconciliation_restores_reviewed_historical_list_pins(self):
        other = api.create_dossier(self.project, "Other note", "Other evidence.")["dossier_id"]
        decision = api.record_decision(self.project, title="Linked decision", rationale="Review the note.",
                                       dossier_ids=[self.dossier])["decision_id"]
        self.revise("dossier", self.dossier, {"body": "Current evidence."})
        self.revise("decision", decision, {"dossier_ids": []})
        changes = {"dossier_ids": [self.dossier, other]}
        before = {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        preview = api.prepare_record_revision(self.project, "decision", decision, base_revision=1, changes=changes)
        self.assertEqual(preview["conflicts"][0]["base"], [{"id": self.dossier, "revision": 1}])
        self.assertEqual(preview["conflicts"][0]["mine"], [{"id": self.dossier, "revision": 1}, {"id": other, "revision": 1}])
        resolved = api.prepare_record_revision(self.project, "decision", decision, base_revision=1,
            changes=changes, resolutions={"dossier_ids": "mine"})
        self.assertEqual(resolved["changes"]["dossier_revisions"], {self.dossier: 1, other: 1})
        self.assertEqual(before, {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()})
        saved = api.revise_record(self.project, "decision", decision, changes=resolved["changes"],
            expected_snapshot=resolved["current"]["snapshot"], expected_revision=2,
            change_kind="correction", reason="Restore the explicitly reviewed links.")
        self.assertEqual(saved["record"]["dossier_refs"], [{"id": self.dossier, "revision": 1}, {"id": other, "revision": 1}])
        self.assertEqual(api.get_record(self.project, "decision", decision, revision=1)["record"]["dossier_refs"], [{"id": self.dossier, "revision": 1}])
        for pins in ({other: 99}, {"unknown": 1}, {other: True}, [], {other: 0}):
            with self.subTest(pins=pins), self.assertRaises(ResearchError):
                api.prepare_record_revision(self.project, "decision", decision, base_revision=3,
                    changes={"dossier_ids": [other], "dossier_revisions": pins})

    def test_prepare_revision_treats_association_and_pin_as_one_choice(self):
        other = api.create_claim(self.project, title="Other date", statement="Possibly 1925.")["claim_id"]
        self.revise("claim", self.claim, {"statement": "Reviewed original claim."})
        self.revise("evidence_link", self.link, {"claim_revision": 2})
        preview = api.prepare_record_revision(self.project, "evidence_link", self.link,
            base_revision=1, changes={"claim_id": other})
        self.assertFalse(preview["ready"])
        self.assertEqual(preview["conflicts"][0]["field"], "claim_id")
        self.assertEqual(preview["conflicts"][0]["current"], {"id": self.claim, "revision": 2})
        resolved = api.prepare_record_revision(self.project, "evidence_link", self.link,
            base_revision=1, changes={"claim_id": other}, resolutions={"claim_id": "mine"})
        self.assertEqual(resolved["changes"], {"claim_id": other, "claim_revision": 1})

    def test_prepared_revision_still_rejects_a_second_race(self):
        preview = api.prepare_record_revision(self.project, "dossier", self.dossier,
            base_revision=1, changes={"body": "My draft."})
        self.revise("claim", self.claim, {"place": "Changed after preview"})
        with self.assertRaises(ResearchConflictError):
            api.revise_record(self.project, "dossier", self.dossier, changes=preview["changes"],
                expected_snapshot=preview["current"]["snapshot"], expected_revision=1,
                change_kind="correction", reason="Reviewed preview")
        self.assertEqual(api.get_record(self.project, "dossier", self.dossier)["record"]["body"], "Original note.")

    def test_prepare_revision_rejects_immutable_invalid_and_missing_evidence(self):
        for changes, resolutions in (({"revision": 100}, {}), ({"title": 42}, {}),
            ({"evidence_ids": ["urn:uuid:00000000-0000-0000-0000-000000000001"]}, {}),
            ({"body": "Draft"}, {"body": "overwrite"}), ({"body": "Draft"}, {"created_by": "mine"})):
            with self.subTest(changes=changes), self.assertRaises(ResearchError):
                api.prepare_record_revision(self.project, "dossier", self.dossier,
                    base_revision=1, changes=changes, resolutions=resolutions)

    def batch(self):
        dossiers = [self.dossier] + [api.create_dossier(self.project, f"Note {i}", "Original.")["dossier_id"] for i in range(4)]
        return [{"kind": "dossier", "id": identifier, "expected_revision": 1,
                 "changes": {"body": f"Reviewed note {i}."}, "change_kind": "correction", "reason": "Reviewed together."}
                for i, identifier in enumerate(dossiers)] + [{"kind": "decision", "id": self.decision,
                 "expected_revision": 1, "changes": {"rationale": "Reflect the five reviewed dossiers."},
                 "change_kind": "supersession", "reason": "Reviewed together."}]

    def test_batch_preview_and_apply_use_one_snapshot_without_partial_writes(self):
        operations = self.batch()
        before = {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        preview = api.prepare_record_revisions(self.project, operations)
        self.assertEqual(preview["schema_version"], "research-revision-batch-local/1")
        self.assertEqual(len(preview["operations"]), 6)
        self.assertEqual(before, {p: p.read_bytes() for p in self.project.rglob("*") if p.is_file()})
        generation = Repository(self.project).snapshot().manifest.generation
        result = api.apply_record_revisions(self.project, preview["operations"], expected_snapshot=preview["snapshot"], actor="reviewing-author")
        self.assertEqual(Repository(self.project).snapshot().manifest.generation, generation + 1)
        self.assertEqual(len(result["records"]), 6)
        for operation in operations:
            record = api.get_record(self.project, operation["kind"], operation["id"])["record"]
            self.assertEqual(record["revision"], 2)
            self.assertEqual(record["created_by"], "reviewing-author")
            self.assertEqual(record["change"]["reason"], "Reviewed together.")
            self.assertEqual(record["change"]["previous_revision"], 1)
            for name, value in operation["changes"].items():
                self.assertEqual(record[name], value)
            self.assertEqual(api.get_record(self.project, operation["kind"], operation["id"], revision=1)["record"]["revision"], 1)

    def test_batch_invalid_later_operation_and_second_race_leave_all_records_unchanged(self):
        operations = self.batch()
        snapshot = api.audit(self.project)["snapshot"]
        invalid = [*operations[:-1], {**operations[-1], "changes": {"claim_id": "urn:uuid:00000000-0000-0000-0000-000000000001"}}]
        with self.assertRaises(ResearchError):
            api.apply_record_revisions(self.project, invalid, expected_snapshot=snapshot)
        self.assertEqual(api.audit(self.project)["snapshot"], snapshot)
        preview = api.prepare_record_revisions(self.project, operations)
        self.revise("claim", self.claim, {"place": "Concurrent edit"})
        with self.assertRaises(ResearchConflictError):
            api.apply_record_revisions(self.project, operations, expected_snapshot=preview["snapshot"])
        for operation in operations:
            self.assertEqual(api.get_record(self.project, operation["kind"], operation["id"])["record"]["revision"], 1)

    def test_batch_rejects_duplicates_stale_revisions_and_future_pins(self):
        operation = {"kind": "decision", "id": self.decision, "expected_revision": 1,
                     "changes": {"title": "Draft"}, "change_kind": "correction", "reason": "Reviewed"}
        for operations in ([operation, operation], [{**operation, "expected_revision": 99}],
                           [{**operation, "changes": {"claim_revision": 2}}],
                           [{**operation, "created_by": "overwritten"}]):
            with self.subTest(operations=operations), self.assertRaises(ResearchError):
                api.prepare_record_revisions(self.project, operations)

    def test_batch_reads_snapshot_once_for_preview_and_only_rechecks_under_commit_lock(self):
        operations = self.batch()
        read = Repository.snapshot
        with patch.object(Repository, "snapshot", autospec=True, side_effect=read) as snapshots:
            preview = api.prepare_record_revisions(self.project, operations)
            self.assertEqual(snapshots.call_count, 1)
            snapshots.reset_mock()
            api.apply_record_revisions(self.project, operations, expected_snapshot=preview["snapshot"])
            self.assertEqual(snapshots.call_count, 2)

    def test_batch_head_failure_never_accepts_a_partial_group(self):
        operations = self.batch()
        preview = api.prepare_record_revisions(self.project, operations)
        with patch("lixity.research.repository.replace_head", side_effect=OSError("Synthetic publication failure")), self.assertRaises(OSError):
            api.apply_record_revisions(self.project, operations, expected_snapshot=preview["snapshot"])
        self.assertEqual(api.audit(self.project)["snapshot"], preview["snapshot"])
        for operation in operations:
            self.assertEqual(api.get_record(self.project, operation["kind"], operation["id"])["record"]["revision"], 1)

    def test_search_finds_latest_authored_records_without_turning_them_into_citations(self):
        self.revise("dossier", self.dossier, {"body": "Retiredword"})
        self.revise("dossier", self.dossier, {"body": "Currentword in the reading room."})
        self.revise("decision", self.decision, {"impact_on_plot": "Currentword changes the opening."})
        self.revise("claim", self.claim, {"actors": ["Currentword"]})
        api.reindex(self.project)
        self.assertEqual(api.search(self.project, "Currentword")["hits"], [])
        found = api.search(self.project, "Currentword", scope="all")
        self.assertEqual(found["schema_version"], "research-search-local/2")
        self.assertEqual({hit["kind"] for hit in found["hits"]}, {"dossier", "claim", "decision"})
        dossier = next(hit for hit in found["hits"] if hit["kind"] == "dossier")
        self.assertEqual((dossier["record_id"], dossier["revision"]), (self.dossier, 3))
        self.assertIn("Currentword", dossier["excerpt"])
        self.assertNotIn("passage_id", dossier)
        self.assertEqual(api.search(self.project, "Retiredword", scope="all")["hits"], [])
        self.assertEqual(len(api.search(self.project, "Currentword", scope="decisions")["hits"]), 1)
        self.assertEqual(len(api.search(self.project, "Currentword", scope="all", limit=1)["hits"]), 1)
        combined = api.search(self.project, "reading room", scope="all")["hits"]
        self.assertIn("passage", {hit["kind"] for hit in combined})
        self.assertIn("dossier", {hit["kind"] for hit in combined})
        source = next(hit for hit in combined if hit["kind"] == "passage")
        self.assertEqual(api.cite(self.project, source["passage_id"])["verbatim"], source["verbatim"])
        self.assertEqual(api.search(self.project, '" OR NOT () *', scope="all")["hits"], [])
        with self.assertRaises(ResearchError):
            api.search(self.project, "room", scope="invalid")
        self.revise("dossier", self.dossier, {"body": "Freshword"})
        with self.assertRaisesRegex(ResearchError, "stale"):
            api.search(self.project, "Currentword", scope="all")
        api.reindex(self.project)
        self.assertEqual(api.search(self.project, "Currentword", scope="dossiers")["hits"], [])
        self.assertEqual(len(api.search(self.project, "Freshword", scope="dossiers")["hits"]), 1)

    def test_dossier_revision_preserves_identity_history_and_links(self):
        before = Repository(self.project).snapshot()
        original_path = Repository(self.project).record_path(next(e for e in before.manifest.entries if e.ref.id == self.dossier))
        original_bytes = original_path.read_bytes()
        changed = self.revise("dossier", self.dossier, {"title": "Revised reading room", "body": "  Revised note.\r\n", "tags": ["checked"]})
        self.assertEqual(changed["record"]["id"], self.dossier)
        self.assertEqual(changed["record"]["revision"], 2)
        self.assertEqual(changed["record"]["body"], "  Revised note.\r\n")
        self.assertEqual(original_path.read_bytes(), original_bytes)
        self.assertEqual(len(api.list_dossiers(self.project)["dossiers"]), 1)
        self.assertEqual(api.get_dossier(self.project, self.dossier)["title"], "Revised reading room")
        old = api.get_record(self.project, "dossier", self.dossier, revision=1)
        self.assertEqual(old["record"]["body"], "Original note.")
        self.assertFalse(old["is_latest"])
        self.assertEqual(old["citations"][0]["verbatim"], "The reading room opened in 1924.")
        self.assertEqual([r["revision"] for r in api.record_history(self.project, "dossier", self.dossier)["revisions"]], [2, 1])
        claim = Repository(self.project).snapshot().get(Reference(id=self.claim), Claim)
        self.assertEqual(claim.dossier_ref.revision, 1)
        self.assertTrue(api.audit(self.project)["ok"])

    def test_claim_evidence_and_decision_corrections_and_supersession(self):
        claim = self.revise("claim", self.claim, {"statement": "Possibly opened in 1924.", "confidence": "disputed", "place": "Reading room", "actors": ["Librarian"]})
        self.assertEqual(claim["record"]["scope"]["actors"], ["Librarian"])
        link = self.revise("evidence_link", self.link, {"relation": "qualifies", "rationale": "Date needs review."})
        self.assertEqual(link["record"]["relation"], "qualifies")
        self.assertEqual(link["record"]["claim_ref"]["revision"], 1)
        decision = self.revise("decision", self.decision, {"title": "Move date", "rationale": "Change the narrative chronology.", "deviation_from_fact": True}, "supersession")
        self.assertEqual(decision["record"]["change"]["change_kind"], "supersession")
        self.assertEqual(api.get_record(self.project, "decision", self.decision, revision=1)["record"]["title"], "Keep date")
        self.assertEqual(len(api.list_claims(self.project)["claims"]), 1)
        self.assertEqual(len(api.list_evidence_links(self.project)["evidence_links"]), 1)
        self.assertEqual(len(api.list_decisions(self.project)["decisions"]), 1)
        self.assertTrue(api.audit(self.project)["ok"])

    def test_conflicts_invalid_changes_and_foreign_identity_do_not_write(self):
        loaded = api.get_record(self.project, "dossier", self.dossier)
        self.revise("dossier", self.dossier, {"title": "Current title"})
        current = Repository(self.project).snapshot().digest
        for overrides in (
            {"expected_snapshot": loaded["snapshot"]},
            {"expected_revision": 1}, {"expected_revision": True},
            {"changes": {"id": self.claim}}, {"changes": {"unsupported": "value"}},
            {"changes": {"title": ""}}, {"changes": {"title": "  "}}, {"reason": "  "},
            {"change_kind": "automatic"}, {"changes": {"tags": "not-a-list"}},
        ):
            kwargs = {"changes": {"title": "Rejected"}, "expected_snapshot": current, "expected_revision": 2,
                      "change_kind": "correction", "reason": "Test validation"}
            kwargs.update(overrides)
            with self.subTest(overrides=overrides), self.assertRaises(ResearchError):
                api.revise_record(self.project, "dossier", self.dossier, **kwargs)
            self.assertEqual(Repository(self.project).snapshot().digest, current)
        other = Path(self.temp.name) / "other"
        api.init(other, title="Other project")
        with self.assertRaises(ResearchError):
            api.get_record(other, "dossier", self.dossier)

    def test_source_refresh_is_visible_without_rewriting_authored_text(self):
        self.source_file.write_text("The opening may have been in 1925.", encoding="utf-8")
        latest = api.ingest(self.project, self.source_file, source_id=self.source["source_id"], allow_retention=True)
        loaded = api.get_record(self.project, "dossier", self.dossier)
        self.assertEqual(loaded["record"]["body"], "Original note.")
        self.assertEqual(loaded["record"]["revision"], 1)
        self.assertEqual(loaded["citations"][0]["verbatim"], "The reading room opened in 1924.")
        self.assertEqual(loaded["source_updates"][0]["latest_version_id"], latest["source_version_id"])
        self.assertEqual(loaded["source_updates"][0]["cited_version_id"], self.source["source_version_id"])

    def test_optional_fields_clear_and_new_links_pin_latest_revision(self):
        self.revise("dossier", self.dossier, {"body": "New dossier text."})
        claim = api.create_claim(self.project, title="Another claim", statement="A different note.", dossier_id=self.dossier)
        record = Repository(self.project).snapshot().get(Reference(id=claim["claim_id"]), Claim)
        self.assertEqual(record.dossier_ref.revision, 2)
        self.revise("claim", self.claim, {"statement": "Changed statement."})
        decision = api.record_decision(self.project, title="Another decision", rationale="Reviewed", claim_id=self.claim)
        record = Repository(self.project).snapshot().get(Reference(id=decision["decision_id"]), Decision)
        self.assertEqual(record.claim_ref.revision, 2)
        cleared = self.revise("claim", self.claim, {"dossier_id": None, "tags": [], "actors": [], "place": None})
        self.assertIsNone(cleared["record"]["dossier_ref"])
        self.assertEqual(cleared["record"]["tags"], [])

    def test_repin_is_explicit_and_history_keeps_original_associations(self):
        self.revise("claim", self.claim, {"statement": "The date needs review."})
        current = api.get_record(self.project, "evidence_link", self.link)
        self.assertEqual(current["reference_updates"][0]["latest_revision"], 2)
        repinned = self.revise("evidence_link", self.link, {"claim_revision": 2, "relation": "qualifies"})
        self.assertEqual(repinned["record"]["claim_ref"]["revision"], 2)
        self.assertEqual(api.get_record(self.project, "evidence_link", self.link, revision=1)["record"]["claim_ref"]["revision"], 1)
        claim = api.get_record(self.project, "claim", self.claim)
        self.assertEqual(claim["citation_scope"], "current_links_to_pinned_claim_revision")
        self.assertEqual(claim["citations"][0]["evidence_link_revision"], 2)
        self.assertEqual(claim["citations"][0]["claim_revision"], 2)
        with self.assertRaises(ResearchError):
            self.revise("evidence_link", self.link, {"claim_revision": 99})
        with self.assertRaises(ResearchError):
            self.revise("evidence_link", self.link, {"claim_revision": True})

    def test_purged_evidence_can_be_retained_but_not_newly_attached(self):
        api.purge(self.project, self.source["source_id"])
        changed = self.revise("dossier", self.dossier, {"title": "Historical note"})
        self.assertEqual(changed["citations"][0]["availability"], "purged")
        self.revise("evidence_link", self.link, {"rationale": "Historical unavailable evidence."})
        empty = api.create_dossier(self.project, "Unlinked", "No evidence.")["dossier_id"]
        with self.assertRaises(ResearchError):
            self.revise("dossier", empty, {"evidence_ids": [self.passage]})
        self.assertTrue(api.audit(self.project)["ok"])
