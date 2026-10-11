"""Reviewed evidence drafts never silently pin a changed claim or project snapshot."""

from uuid import uuid4

import pytest

from lixity.research import api
from lixity.research.repository import Repository, ResearchConflictError, ResearchError


@pytest.fixture
def draft(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic reviewed citation")
    source = tmp_path / "synthetic-source.txt"
    source.write_text("A synthetic note records an opened gate.\n", encoding="utf-8")
    capture = api.ingest(project, source, allow_retention=True)
    passage = api.get_source(project, capture["source_id"])["passages"][0]["id"]
    claim = api.create_claim(project, title="Gate", statement="The gate opened.")["claim_id"]
    return project, claim, passage, capture["source_id"]


def test_matching_reviewed_preconditions_keep_legacy_output_shape(draft):
    project, claim, passage, _ = draft
    snapshot = Repository(project).snapshot()
    result = api.link_evidence(project, claim_id=claim, passage_id=passage,
                               expected_snapshot=snapshot.digest, expected_claim_revision=1,
                               expected_project_id=snapshot.project.id)
    assert set(result) == {"schema_version", "evidence_link_id", "claim_id", "passage_id", "relation", "snapshot"}
    assert api.list_evidence_links(project)["evidence_links"][0]["claim_revision"] == 1


@pytest.mark.parametrize("guard", ["snapshot", "revision"])
def test_changed_reviewed_claim_is_rejected_without_creating_link(draft, guard):
    project, claim, passage, _ = draft
    current = api.get_record(project, "claim", claim)
    api.revise_record(project, "claim", claim, changes={"statement": "The gate may have opened."},
                      expected_snapshot=current["snapshot"], expected_revision=1,
                      change_kind="correction", reason="Author reviewed uncertainty.")
    before = Repository(project).snapshot()
    kwargs = {"expected_snapshot": current["snapshot"]} if guard == "snapshot" else {"expected_claim_revision": 1}
    with pytest.raises(ResearchConflictError):
        api.link_evidence(project, claim_id=claim, passage_id=passage, **kwargs)
    assert Repository(project).snapshot().digest == before.digest
    assert api.list_evidence_links(project)["evidence_links"] == []


@pytest.mark.parametrize("kwargs", [{"expected_claim_revision": True}, {"expected_claim_revision": 0},
                                    {"expected_claim_revision": "1"}, {"expected_snapshot": "invalid"}])
def test_invalid_review_preconditions_do_not_publish(draft, kwargs):
    project, claim, passage, _ = draft
    before = Repository(project).snapshot()
    with pytest.raises(ResearchError):
        api.link_evidence(project, claim_id=claim, passage_id=passage, **kwargs)
    assert Repository(project).snapshot().digest == before.digest


def test_unguarded_legacy_call_still_pins_latest_claim_revision(draft):
    project, claim, passage, _ = draft
    current = api.get_record(project, "claim", claim)
    api.revise_record(project, "claim", claim, changes={"place": "Garden"},
                      expected_snapshot=current["snapshot"], expected_revision=1,
                      change_kind="correction", reason="Author supplied scope.")
    api.link_evidence(project, claim_id=claim, passage_id=passage)
    assert api.list_evidence_links(project)["evidence_links"][0]["claim_revision"] == 2


def test_wrong_reviewed_project_does_not_create_evidence_link(draft):
    project, claim, passage, _ = draft
    before = Repository(project).snapshot().digest
    with pytest.raises(ResearchConflictError):
        api.link_evidence(project, claim_id=claim, passage_id=passage, expected_project_id=f"urn:uuid:{uuid4()}")
    assert Repository(project).snapshot().digest == before


def test_reviewed_link_refuses_unavailable_source_while_legacy_behavior_stays_explicit(draft):
    project, claim, passage, source = draft
    api.withdraw(project, source)
    snapshot = Repository(project).snapshot()
    with pytest.raises(ResearchError):
        api.link_evidence(project, claim_id=claim, passage_id=passage, expected_snapshot=snapshot.digest)
    assert Repository(project).snapshot().digest == snapshot.digest
    api.link_evidence(project, claim_id=claim, passage_id=passage)
    assert api.list_evidence_links(project)["evidence_links"][0]["citation"]["availability"] == "withdrawn"
