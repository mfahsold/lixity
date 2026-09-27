"""Public revision workflows use synthetic records and preserve pinned evidence."""

import tempfile
import unittest
from pathlib import Path

from lixity.research import api
from lixity.research.models import Claim, Decision, Reference
from lixity.research.repository import Repository, ResearchError


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
