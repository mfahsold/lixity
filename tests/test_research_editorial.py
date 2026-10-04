"""Editorial review follows explicit revision pins without interpreting prose."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api
from lixity.research.models import Reference, Tombstone
from lixity.research.repository import Repository, ResearchError


class EditorialReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Path(self.tmp.name)
        api.init(self.project, title="Synthetic editorial archive")
        self.dossier = api.create_dossier(self.project, "Synthetic dossier", "## Voice\nQuiet prose.\n\n## Timeline\n1924.")["dossier_id"]
        self.claim = api.create_claim(self.project, title="Synthetic date", statement="1924.", dossier_id=self.dossier)["claim_id"]
        self.decision = api.record_decision(self.project, title="Use 1914", rationale="An intentional fictional date.",
                                           claim_id=self.claim, dossier_ids=[self.dossier])["decision_id"]

    def revise(self, kind, identifier, changes):
        loaded = api.get_record(self.project, kind, identifier)
        return api.revise_record(self.project, kind, identifier, changes=changes,
            expected_snapshot=loaded["snapshot"], expected_revision=loaded["record"]["revision"],
            change_kind="correction", reason="Synthetic reviewed revision.")

    def test_explicit_direct_and_claim_links_share_one_affected_dossier(self):
        result = api.decision_impact(self.project, self.decision)
        self.assertEqual(result["schema_version"], "research-decision-impact-local/1")
        self.assertEqual(len(result["dossiers"]), 1)
        dossier = result["dossiers"][0]
        self.assertEqual(dossier["id"], self.dossier)
        self.assertEqual({link["via"] for link in dossier["links"]}, {"direct", "claim"})
        self.assertEqual(dossier["sections"], ["Voice", "Timeline"])
        self.assertEqual(dossier["flags"], ["decision_after_dossier"])
        self.assertNotIn("contradiction", str(result))

    def test_stale_pins_remain_visible_when_dossier_is_newer(self):
        self.revise("dossier", self.dossier, {"body": "## Reviewed voice\nA different register."})
        self.revise("claim", self.claim, {"statement": "A reviewed date."})
        dossier = api.decision_impact(self.project, self.decision)["dossiers"][0]
        self.assertEqual(dossier["current_revision"], 2)
        self.assertEqual(dossier["pinned_revisions"], [1])
        self.assertFalse(dossier["decision_after_dossier"])
        self.assertEqual(dossier["sections"], ["Reviewed voice"])
        self.assertEqual(set(dossier["flags"]), {"stale_dossier_pin", "stale_claim_pin"})
        # Existing date-order review semantics remain compatible.
        self.assertFalse(api.get_dossier(self.project, self.dossier)["review_needed"])
        self.assertEqual(api.editorial_review(self.project)["candidate_count"], 1)

    def test_pinned_claim_does_not_invent_link_to_its_new_dossier(self):
        other = api.create_dossier(self.project, "Other dossier", "Other topic.")["dossier_id"]
        decision = api.record_decision(self.project, title="Claim-only choice", rationale="Use its pinned claim.", claim_id=self.claim)["decision_id"]
        self.revise("claim", self.claim, {"dossier_id": other})
        impact = api.decision_impact(self.project, decision)
        self.assertEqual([item["id"] for item in impact["dossiers"]], [self.dossier])
        self.assertIn("stale_claim_pin", impact["dossiers"][0]["flags"])
        self.assertEqual(api.get_dossier(self.project, other)["decision_reviews"], [])

    def test_unlinked_and_withdrawn_targets_are_review_candidates(self):
        orphan = api.record_decision(self.project, title="Unlinked choice", rationale="No association supplied.")["decision_id"]
        repository = Repository(self.project)
        snapshot = repository.snapshot()
        tombstone = Tombstone(**api.envelope(snapshot.project.id, "test-author"),
                              target_ref=Reference(id=self.dossier), target_kind="dossier",
                              operation="withdraw", reason="Synthetic withdrawal.")
        repository.commit([tombstone], {}, snapshot)
        dossier = api.decision_impact(self.project, self.decision)["dossiers"][0]
        self.assertIn("withdrawn_dossier", dossier["flags"])
        report = api.editorial_review(self.project)
        self.assertEqual(report["candidate_count"], 2)
        unlinked = next(item for item in report["candidates"] if item["decision_id"] == orphan)
        self.assertIsNone(unlinked["dossier_id"])
        self.assertEqual(unlinked["flags"], ["no_linked_dossier"])

    def test_reads_do_not_write_and_graph_is_built_once(self):
        for number in range(4):
            api.record_decision(self.project, title=f"Choice {number}", rationale="Synthetic choice.", dossier_ids=[self.dossier])
        before = {file: file.read_bytes() for file in self.project.rglob("*") if file.is_file()}
        original_snapshot = Repository.snapshot
        with (patch.object(Repository, "snapshot", autospec=True, side_effect=original_snapshot) as snapshot,
              patch("lixity.research.api.extract_sections", wraps=api.extract_sections) as outline):
            report = api.editorial_review(self.project)
        self.assertEqual(snapshot.call_count, 1)
        self.assertEqual(outline.call_count, 1)
        self.assertEqual(report["decision_count"], 5)
        self.assertEqual(report["candidate_count"], 5)
        self.assertEqual(before, {file: file.read_bytes() for file in self.project.rglob("*") if file.is_file()})

    def test_missing_decision_is_an_error(self):
        with self.assertRaises(ResearchError):
            api.decision_impact(self.project, self.dossier)


if __name__ == "__main__":
    unittest.main()
