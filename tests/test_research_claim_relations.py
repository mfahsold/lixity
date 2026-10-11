"""Causal links are pinned, authored records without factual or transitive inference."""

from uuid import uuid4

import pytest

from lixity.research import api
from lixity.research.models import Claim, ClaimRelation, Reference
from lixity.research.repository import Repository, ResearchConflictError, ResearchError, encode


@pytest.fixture
def archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic causal archive")
    first = api.create_claim(project, title="Gate", statement="The gate opened.", time_period="1912")["claim_id"]
    second = api.create_claim(project, title="Garden", statement="The garden was visited.", time_period="1913")["claim_id"]
    return project, first, second


def revise(project, kind, identifier, changes):
    current = api.get_record(project, kind, identifier)
    return api.revise_record(project, kind, identifier, changes=changes,
                             expected_snapshot=current["snapshot"], expected_revision=current["record"]["revision"],
                             change_kind="correction", reason="Explicit synthetic author correction.")


def test_first_relation_write_promotes_only_manifest_and_keeps_old_record_bytes(archive):
    project, first, second = archive
    repository = Repository(project)
    before = repository.snapshot()
    records = {entry.ref: repository.record_path(entry).read_bytes() for entry in before.manifest.entries}
    result = api.create_claim_relation(project, first, second, relation="results_in", rationale="Author interpretation.",
                                       from_claim_revision=1, to_claim_revision=1, expected_snapshot=before.digest,
                                       expected_project_id=before.project.id)
    assert result["schema_version"] == "research-claim-relation-local/1"
    assert result["relation"] == "causes"
    after = repository.snapshot()
    assert after.manifest.schema_version == "research-manifest-local/6"
    edge = after.records[result["relation_id"]]
    assert edge.kind == "claim_relation" and edge.schema_version == "research-local/6"
    assert edge.from_claim_ref == Reference(id=first) and edge.to_claim_ref == Reference(id=second)
    for entry in before.manifest.entries:
        assert repository.record_path(entry).read_bytes() == records[entry.ref]
    assert api.audit(project)["ok"]


def test_endpoint_edits_mark_review_needed_without_retargeting_relation(archive):
    project, first, second = archive
    result = api.create_claim_relation(project, first, second)
    revise(project, "claim", first, {"title": "Revised gate", "time_period": "1910"})
    listed = api.list_claim_relations(project)["relations"][0]
    assert listed["relation_id"] == result["relation_id"] and listed["review_needed"]
    assert listed["from_claim"] == {"claim_id": first, "revision": 1, "current_revision": 2,
                                     "title": "Gate", "time_period": "1912", "confidence": "hypothetical"}
    assert listed["to_claim"]["revision"] == listed["to_claim"]["current_revision"] == 1
    inspected = api.get_record(project, "claim_relation", result["relation_id"])
    assert inspected["reference_updates"] == [{"kind": "claim", "id": first, "pinned_revision": 1,
                                               "latest_revision": 2, "role": "from"}]


def test_relation_revision_retraction_and_history_reuse_shared_mechanisms(archive):
    project, first, second = archive
    identifier = api.create_claim_relation(project, first, second)["relation_id"]
    original = api.get_record(project, "claim_relation", identifier)
    original_bytes = encode(Repository(project).snapshot().records[identifier])
    changed = revise(project, "claim_relation", identifier, {"state": "retracted", "rationale": "Author reconsidered."})
    assert changed["record"]["revision"] == 2 and changed["record"]["schema_version"] == "research-local/6"
    assert changed["record"]["change"]["previous_revision"] == 1
    assert api.list_claim_relations(project)["relations"] == []
    assert api.list_claim_relations(project, include_retracted=True)["relations"][0]["state"] == "retracted"
    historical = Repository(project).snapshot().revisions[(identifier, 1)]
    assert encode(historical) == original_bytes
    assert api.get_record(project, "claim_relation", identifier, revision=1)["record"] == original["record"]
    assert [row["revision"] for row in api.record_history(project, "claim_relation", identifier)["revisions"]] == [2, 1]


def test_unchanged_endpoint_form_preserves_pin_and_preview_is_read_only(archive):
    project, first, second = archive
    identifier = api.create_claim_relation(project, first, second)["relation_id"]
    revise(project, "claim", first, {"statement": "The gate may have opened."})
    before = Repository(project).snapshot()
    preview = api.prepare_record_revision(project, "claim_relation", identifier, base_revision=1,
                                           changes={"from_claim_id": first, "rationale": "Reviewed old assertion."})
    assert preview["ready"] and preview["changes"] == {"rationale": "Reviewed old assertion."}
    assert Repository(project).snapshot().digest == before.digest
    changed = revise(project, "claim_relation", identifier, preview["changes"])
    assert changed["record"]["from_claim_ref"] == {"id": first, "revision": 1}
    assert changed["record"]["schema_version"] == "research-local/6"


def test_cycles_are_retained_as_explicit_assertions_without_inferred_edges(archive):
    project, first, second = archive
    third = api.create_claim(project, title="Bird", statement="A bird arrived.")["claim_id"]
    api.create_claim_relation(project, first, second)
    api.create_claim_relation(project, second, third)
    api.create_claim_relation(project, third, first)
    rows = api.list_claim_relations(project)["relations"]
    assert {(row["from_claim"]["claim_id"], row["to_claim"]["claim_id"]) for row in rows} == {
        (first, second), (second, third), (third, first)}
    assert len(api.list_claim_relations(project, claim_id=first)["relations"]) == 2
    assert api.audit(project)["ok"]


@pytest.mark.parametrize("problem", ["self", "missing", "wrong_kind", "foreign", "future_revision", "relation", "snapshot"])
def test_invalid_or_stale_relation_does_not_publish_or_upgrade(archive, tmp_path, problem):
    project, first, second = archive
    kwargs = {}
    if problem == "self":
        second = first
    elif problem == "missing":
        second = f"urn:uuid:{uuid4()}"
    elif problem == "wrong_kind":
        second = api.create_dossier(project, "Notes", "Synthetic notes.")["dossier_id"]
    elif problem == "foreign":
        foreign = tmp_path / "foreign"
        api.init(foreign, title="Other synthetic project")
        second = api.create_claim(foreign, title="Other", statement="A synthetic claim.")["claim_id"]
    elif problem == "future_revision":
        kwargs["from_claim_revision"] = 2
    elif problem == "relation":
        kwargs["relation"] = "precedes"
    elif problem == "snapshot":
        kwargs["expected_snapshot"] = "0" * 64
    repository = Repository(project)
    before = repository.snapshot()
    files = {path: path.read_bytes() for path in (project / "research").rglob("*") if path.is_file()}
    with pytest.raises(ResearchError):
        api.create_claim_relation(project, first, second, **kwargs)
    assert repository.snapshot().digest == before.digest
    assert repository.snapshot().manifest.schema_version == "research-manifest-local/1"
    assert files == {path: path.read_bytes() for path in (project / "research").rglob("*") if path.is_file()}


def test_relation_batch_is_atomic_and_guarded_against_stale_head(archive):
    project, first, second = archive
    identifier = api.create_claim_relation(project, first, second)["relation_id"]
    operation = {"kind": "claim_relation", "id": identifier, "expected_revision": 1,
                 "changes": {"rationale": "Reviewed cause."}, "change_kind": "correction", "reason": "Reviewed."}
    preview = api.prepare_record_revisions(project, [operation])
    revise(project, "claim", first, {"place": "Garden"})
    with pytest.raises(ResearchConflictError):
        api.apply_record_revisions(project, [operation], expected_snapshot=preview["snapshot"])
    assert api.get_record(project, "claim_relation", identifier)["record"]["revision"] == 1
    preview = api.prepare_record_revisions(project, [operation])
    applied = api.apply_record_revisions(project, [operation], expected_snapshot=preview["snapshot"])
    assert applied["records"] == [{"kind": "claim_relation", "id": identifier, "revision": 2}]
    assert api.get_record(project, "claim_relation", identifier)["record"]["schema_version"] == "research-local/6"


def test_new_relations_round_trip_through_existing_archive_and_do_not_change_search_contract(archive, tmp_path):
    project, first, second = archive
    identifier = api.create_claim_relation(project, first, second, rationale="Causalword author rationale.")["relation_id"]
    revise(project, "claim_relation", identifier, {"rationale": "Revised causalword rationale."})
    api.reindex(project)
    assert api.search(project, "causalword", scope="all")["hits"] == []
    assert api.search(project, "gate", scope="claims")["schema_version"] == "research-search-local/2"
    output = tmp_path / "synthetic-archive.tar.gz"
    api.export_archive(project, output)
    restored = tmp_path / "restored"
    api.restore_archive(output, restored)
    before, after = Repository(project).snapshot(), Repository(restored).snapshot()
    assert after.manifest.schema_version == "research-manifest-local/6"
    assert after.digest == before.digest
    assert after.revisions[(identifier, 1)] == before.revisions[(identifier, 1)]
    assert after.records[identifier] == before.records[identifier]
    assert api.audit(restored)["ok"]
    assert after.get(Reference(id=first), Claim).title == "Gate"


@pytest.mark.parametrize("field,value", [
    ("from_claim_id", []), ("to_claim_id", {}), ("rationale", 42), ("relation", None),
    ("from_claim_revision", True), ("to_claim_revision", "1"), ("expected_snapshot", []),
])
def test_invalid_python_input_types_are_reported_without_unexpected_exceptions(archive, field, value):
    project, first, second = archive
    kwargs = {"from_claim_id": first, "to_claim_id": second, field: value}
    before = Repository(project).snapshot().digest
    with pytest.raises(ResearchError):
        api.create_claim_relation(project, **kwargs)
    assert Repository(project).snapshot().digest == before


def test_relation_endpoint_and_revision_reconcile_together_without_silent_repin(archive):
    project, first, second = archive
    third = api.create_claim(project, title="Bird", statement="A bird arrived.")["claim_id"]
    identifier = api.create_claim_relation(project, first, second)["relation_id"]
    revise(project, "claim", third, {"title": "Revised bird"})
    revise(project, "claim_relation", identifier, {"to_claim_id": third, "to_claim_revision": 1})
    before = Repository(project).snapshot()
    preview = api.prepare_record_revision(project, "claim_relation", identifier, base_revision=1,
                                           changes={"to_claim_id": third, "to_claim_revision": 2})
    assert preview["conflicts"] == [{"field": "to_claim_id", "base": {"id": second, "revision": 1},
                                      "current": {"id": third, "revision": 1}, "mine": {"id": third, "revision": 2}}]
    assert not preview["ready"] and Repository(project).snapshot().digest == before.digest
    resolved = api.prepare_record_revision(project, "claim_relation", identifier, base_revision=1,
                                            changes={"to_claim_id": third, "to_claim_revision": 2},
                                            resolutions={"to_claim_id": "mine"})
    assert resolved["changes"] == {"to_claim_id": third, "to_claim_revision": 2}
    changed = revise(project, "claim_relation", identifier, resolved["changes"])
    assert changed["record"]["to_claim_ref"] == {"id": third, "revision": 2}
    assert changed["record"]["revision"] == 3


def test_relation_retraction_revisions_reject_invalid_state_and_keep_history(archive):
    project, first, second = archive
    identifier = api.create_claim_relation(project, first, second)["relation_id"]
    before = Repository(project).snapshot().digest
    with pytest.raises(ResearchError):
        revise(project, "claim_relation", identifier, {"state": "verified"})
    assert Repository(project).snapshot().digest == before
    changed = revise(project, "claim_relation", identifier, {"relation": "results_in", "rationale": "Same directed assertion."})
    assert changed["record"]["relation"] == "causes"
    assert len(api.list_claim_relations(project)["relations"]) == 1


def test_unresolved_endpoint_conflict_returns_choices_before_validating_partial_merge(archive):
    project, first, second = archive
    third = api.create_claim(project, title="Bird", statement="A bird arrived.")["claim_id"]
    identifier = api.create_claim_relation(project, first, second)["relation_id"]
    revise(project, "claim_relation", identifier, {"from_claim_id": third})
    before = Repository(project).snapshot().digest
    draft = {"from_claim_id": second, "to_claim_id": third}
    preview = api.prepare_record_revision(project, "claim_relation", identifier, base_revision=1, changes=draft)
    assert not preview["ready"]
    assert preview["conflicts"] == [{"field": "from_claim_id", "base": {"id": first, "revision": 1},
                                      "current": {"id": third, "revision": 1}, "mine": {"id": second, "revision": 1}}]
    assert Repository(project).snapshot().digest == before
    resolved = api.prepare_record_revision(project, "claim_relation", identifier, base_revision=1, changes=draft,
                                            resolutions={"from_claim_id": "mine"})
    assert resolved["ready"]
    changed = revise(project, "claim_relation", identifier, resolved["changes"])
    assert changed["record"]["from_claim_ref"] == {"id": second, "revision": 1}
    assert changed["record"]["to_claim_ref"] == {"id": third, "revision": 1}


def test_wrong_reviewed_project_does_not_create_relation_or_upgrade(archive):
    project, first, second = archive
    before = Repository(project).snapshot().digest
    with pytest.raises(ResearchConflictError):
        api.create_claim_relation(project, first, second, expected_project_id=f"urn:uuid:{uuid4()}")
    assert Repository(project).snapshot().digest == before
    assert Repository(project).snapshot().manifest.schema_version == "research-manifest-local/1"


def test_repository_rejects_invalid_causal_pins_and_project_even_without_api(archive):
    project, first, second = archive
    dossier = api.create_dossier(project, "Notes", "Synthetic notes.")["dossier_id"]
    repository = Repository(project)
    before = repository.snapshot()
    edge = ClaimRelation(**api.envelope(before.project.id, "synthetic-author"),
                         from_claim_ref=Reference(id=first), to_claim_ref=Reference(id=second))
    for changes in ({"to_claim_ref": Reference(id=dossier)},
                    {"from_claim_ref": Reference(id=first, revision=99)},
                    {"project_id": f"urn:uuid:{uuid4()}"}, {"schema_version": "research-local/5"}):
        with pytest.raises(ResearchError):
            repository.commit([edge.model_copy(update=changes)], {}, before)
        assert repository.snapshot().digest == before.digest
        assert repository.snapshot().manifest.schema_version == "research-manifest-local/1"


def test_commit_race_does_not_promote_archive_or_publish_relation(archive, monkeypatch):
    project, first, second = archive
    commit = Repository.commit
    interfered = []

    def changed_before_publication(repository, additions, blobs, expected, *args, **kwargs):
        if not interfered and any(isinstance(record, ClaimRelation) for record in additions):
            interfered.append(True)
            api.create_claim(project, title="Concurrent", statement="Another explicit author assertion.")
        return commit(repository, additions, blobs, expected, *args, **kwargs)

    monkeypatch.setattr(Repository, "commit", changed_before_publication)
    with pytest.raises(ResearchConflictError):
        api.create_claim_relation(project, first, second)
    snapshot = Repository(project).snapshot()
    assert snapshot.manifest.schema_version == "research-manifest-local/1"
    assert not any(isinstance(record, ClaimRelation) for record in snapshot.records.values())
    assert any(isinstance(record, Claim) and record.title == "Concurrent" for record in snapshot.records.values())


def test_legacy_authored_claim_wire_bytes_are_unchanged():
    claim = Claim(id="urn:uuid:00000000-0000-4000-8000-000000000001",
                  project_id="urn:uuid:00000000-0000-4000-8000-000000000002",
                  created_at="2000-01-01T00:00:00.000000Z", created_by="synthetic-author",
                  title="Gate", statement="The gate opened.")
    assert encode(claim) == (
        b'{"confidence":"hypothetical","created_at":"2000-01-01T00:00:00.000000Z",'
        b'"created_by":"synthetic-author","dossier_ref":null,"id":"urn:uuid:00000000-0000-4000-8000-000000000001",'
        b'"kind":"claim","project_id":"urn:uuid:00000000-0000-4000-8000-000000000002","revision":1,'
        b'"schema_version":"research-local/1","scope":{"actors":[],"place":null,"time_period":null},'
        b'"statement":"The gate opened.","tags":[],"title":"Gate"}\n'
    )
