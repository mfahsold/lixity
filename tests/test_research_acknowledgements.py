"""Explicit author acknowledgements are immutable and pinned to reviewed revisions."""

import contextlib
import io
import json
from uuid import uuid4

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.research.models import Reference, Tombstone
from lixity.research.repository import Repository, ResearchConflictError, ResearchError, encode


@pytest.fixture
def records(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic acknowledgement project")
    first = api.create_dossier(project, "First dossier", "Synthetic unchanged body.")["dossier_id"]
    second = api.create_dossier(project, "Second dossier", "Another unchanged body.")["dossier_id"]
    decision = api.record_decision(project, title="Synthetic choice", rationale="Author supplied rationale.",
                                   dossier_ids=[first, second])["decision_id"]
    return project, decision, first, second


def acknowledge(records, *, dossier=None, status="applied", **kwargs):
    project, decision, first, _ = records
    repository = Repository(project)
    snapshot = repository.snapshot()
    return api.acknowledge_decision(project, decision, dossier or first,
                                    expected_snapshot=snapshot.digest,
                                    expected_decision_revision=snapshot.records[decision].revision,
                                    expected_dossier_revision=snapshot.records[dossier or first].revision,
                                    status=status, **kwargs)


def revise(project, kind, identifier, changes):
    loaded = api.get_record(project, kind, identifier)
    return api.revise_record(project, kind, identifier, changes=changes,
                             expected_snapshot=loaded["snapshot"], expected_revision=loaded["record"]["revision"],
                             change_kind="correction", reason="Explicit synthetic revision.")


def test_acknowledgement_clears_only_matching_date_request_without_editing_content(records, tmp_path):
    project, decision, first, second = records
    manuscript = tmp_path / "synthetic.md"
    manuscript.write_text("Synthetic manuscript remains untouched.")
    before = Repository(project).snapshot()
    protected = {identifier: encode(before.records[identifier]) for identifier in (decision, first, second)}
    assert api.editorial_review(project)["candidate_count"] == 2
    result = acknowledge(records, note="I applied the choice to this dossier revision.", actor="synthetic-author")
    assert result["schema_version"] == "research-decision-acknowledgement-local/1"
    assert result["status"] == "applied" and result["supersedes_id"] is None
    review = api.editorial_review(project)
    assert [candidate["dossier_id"] for candidate in review["candidates"]] == [second]
    assert not api.get_dossier(project, first)["review_needed"]
    after = Repository(project).snapshot()
    assert after.manifest.schema_version == "research-manifest-local/5"
    event = after.records[result["acknowledgement_id"]]
    assert event.schema_version == "research-local/5" and event.revision == 1
    assert event.created_by == "synthetic-author"
    assert all(encode(after.records[identifier]) == content for identifier, content in protected.items())
    assert manuscript.read_text() == "Synthetic manuscript remains untouched."
    assert api.audit(project)["ok"]


def test_reading_old_archive_does_not_upgrade_or_write(records):
    project, decision, _, _ = records
    before = {path: path.read_bytes() for path in (project / "research").rglob("*") if path.is_file()}
    assert Repository(project).snapshot().manifest.schema_version == "research-manifest-local/1"
    api.editorial_review(project)
    api.decision_impact(project, decision)
    assert before == {path: path.read_bytes() for path in (project / "research").rglob("*") if path.is_file()}


@pytest.mark.parametrize("kind", ["decision", "dossier"])
def test_changed_reviewed_revision_resurfaces_candidate(records, kind):
    project, decision, first, _ = records
    acknowledge(records)
    identifier, changes = (decision, {"rationale": "Explicitly changed choice."}) if kind == "decision" else (
        first, {"body": "Explicitly changed dossier body."})
    revise(project, kind, identifier, changes)
    review = api.editorial_review(project)
    candidate = next(candidate for candidate in review["candidates"] if candidate["dossier_id"] == first)
    assert "stale_author_acknowledgement" in candidate["flags"]
    assert candidate["acknowledgement"]["current"] is False
    assert api.get_dossier(project, first)["review_needed"]


def test_reopen_supersedes_prior_ack_even_with_reversed_timestamps(records, monkeypatch):
    project, decision, first, _ = records
    applied = acknowledge(records)
    original = api.envelope

    def clock_skew(project_id, actor):
        values = original(project_id, actor)
        values["created_at"] = "2000-01-01T00:00:00.000000Z"
        return values

    monkeypatch.setattr(api, "envelope", clock_skew)
    reopened = acknowledge(records, status="review_needed", note="I need another review.")
    assert reopened["supersedes_id"] == applied["acknowledgement_id"]
    impact = api.decision_impact(project, decision)
    row = next(row for row in impact["dossiers"] if row["id"] == first)
    assert row["acknowledgement"]["id"] == reopened["acknowledgement_id"]
    assert row["acknowledgement"]["status"] == "review_needed"
    assert row["acknowledgement"]["current"] is True
    assert api.get_dossier(project, first)["review_needed"]
    assert len([record for record in Repository(project).snapshot().records.values()
                if record.kind == "decision_acknowledgement"]) == 2


def test_manual_reopen_reason_does_not_invent_date_order(records):
    project, _decision, first, _ = records
    revise(project, "dossier", first, {"body": "A newer synthetic dossier revision."})
    acknowledge(records, status="review_needed")
    review = api.get_dossier(project, first)["decision_reviews"][0]
    assert "author" in review["reason"].lower() and "reopen" in review["reason"].lower()


def test_human_impact_report_labels_author_acknowledgement(records):
    project, decision, _, _ = records
    acknowledge(records)
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main(["research", "decision-impact", "--project", str(project), "--decision-id", decision]) == 0
    assert "Author marked applied to these revisions" in output.getvalue()


def test_applied_status_keeps_stale_pins_and_withdrawal_candidates(records):
    project, _decision, first, _ = records
    revise(project, "dossier", first, {"body": "A newer synthetic dossier."})
    snapshot = Repository(project).snapshot()
    tombstone = Tombstone(**api.envelope(snapshot.project.id, "synthetic-author"),
                          target_ref=Reference(id=first, revision=2), target_kind="dossier",
                          operation="withdraw", reason="Synthetic withdrawn dossier.")
    Repository(project).commit([tombstone], {}, snapshot)
    acknowledge(records)
    candidate = next(candidate for candidate in api.editorial_review(project)["candidates"]
                     if candidate["dossier_id"] == first)
    assert "stale_dossier_pin" in candidate["flags"] and "withdrawn_dossier" in candidate["flags"]
    assert candidate["acknowledgement"]["status"] == "applied"


@pytest.mark.parametrize("stale", ["snapshot", "decision", "dossier"])
def test_stale_tokens_accept_no_acknowledgement(records, stale):
    project, decision, first, _ = records
    before = Repository(project).snapshot().digest
    values = {"expected_snapshot": before, "expected_decision_revision": 1, "expected_dossier_revision": 1}
    if stale == "snapshot":
        values["expected_snapshot"] = "0" * 64
    else:
        values[f"expected_{stale}_revision"] = 2
    with pytest.raises(ResearchConflictError):
        api.acknowledge_decision(project, decision, first, status="applied", **values)
    assert Repository(project).snapshot().digest == before
    assert not any(record.kind == "decision_acknowledgement" for record in Repository(project).snapshot().records.values())


def test_foreign_unassociated_or_invalid_targets_accept_nothing(records, tmp_path):
    project, decision, _first, _ = records
    other = tmp_path / "other"
    api.init(other, title="Another synthetic project")
    foreign = api.create_dossier(other, "Foreign dossier", "Synthetic foreign body.")["dossier_id"]
    unassociated = api.create_dossier(project, "Unassociated dossier", "Synthetic separate topic.")["dossier_id"]
    before = Repository(project).snapshot().digest
    for dossier in (foreign, unassociated, "invalid-identifier"):
        with pytest.raises(ResearchError):
            api.acknowledge_decision(project, decision, dossier, expected_snapshot=before,
                                     expected_decision_revision=1, expected_dossier_revision=1, status="applied")
    assert Repository(project).snapshot().digest == before


def test_supersedes_forks_or_multiple_roots_fail_closed(records):
    project, _, _, _ = records
    first = acknowledge(records)
    acknowledge(records, status="review_needed")
    repository = Repository(project)
    snapshot = repository.snapshot()
    initial = snapshot.records[first["acknowledgement_id"]]
    for previous in (None, Reference(id=initial.id)):
        values = initial.model_dump()
        values.update(id=uuid4().urn, supersedes_ref=previous)
        event = type(initial).model_validate(values)
        with pytest.raises(ResearchError, match=r"acknowledgement|Acknowledgement"):
            repository.commit([event], {}, snapshot)
        assert repository.snapshot().digest == snapshot.digest


def test_supersedes_cycles_and_other_pairs_fail_closed(records):
    project, _, _, second = records
    first = acknowledge(records)
    other = acknowledge(records, dossier=second)
    repository = Repository(project)
    snapshot = repository.snapshot()
    initial = snapshot.records[first["acknowledgement_id"]]
    for previous in ("self", other["acknowledgement_id"]):
        identifier = uuid4().urn
        values = initial.model_dump()
        values.update(id=identifier, supersedes_ref=Reference(id=identifier if previous == "self" else previous))
        event = type(initial).model_validate(values)
        with pytest.raises(ResearchError, match=r"acknowledgement|Acknowledgement"):
            repository.commit([event], {}, snapshot)
        assert repository.snapshot().digest == snapshot.digest


def test_acknowledgement_history_cannot_be_removed(records):
    project, _, _, _ = records
    result = acknowledge(records)
    repository = Repository(project)
    snapshot = repository.snapshot()
    with pytest.raises(ResearchError, match=r"history cannot be removed"):
        repository.commit([], {}, snapshot, removals={result["acknowledgement_id"]})
    assert repository.snapshot().digest == snapshot.digest


def test_second_snapshot_race_fails_without_rebasing_acknowledgement(records, monkeypatch):
    project, _, _, _ = records
    original = api.envelope
    changed = False

    def concurrent_edit(project_id, actor):
        nonlocal changed
        values = original(project_id, actor)
        if not changed:
            changed = True
            api.create_dossier(project, "Concurrent synthetic dossier", "Explicit concurrently accepted content.")
        return values

    monkeypatch.setattr(api, "envelope", concurrent_edit)
    with pytest.raises(ResearchConflictError):
        acknowledge(records)
    snapshot = Repository(project).snapshot()
    assert not any(record.kind == "decision_acknowledgement" for record in snapshot.records.values())
    assert snapshot.manifest.schema_version == "research-manifest-local/1"
    assert len(api.list_dossiers(project)["dossiers"]) == 3


def test_acknowledgements_survive_verified_archive_export_restore(records, tmp_path):
    project, decision, first, _ = records
    result = acknowledge(records, note="Synthetic durable author acknowledgement.")
    bundle = tmp_path / "archive.tar.gz"
    api.export_archive(project, bundle)
    restored = tmp_path / "restored"
    api.restore_archive(bundle, restored)
    row = next(row for row in api.decision_impact(restored, decision)["dossiers"] if row["id"] == first)
    assert row["acknowledgement"]["id"] == result["acknowledgement_id"]
    assert row["acknowledgement"]["current"]
    assert api.audit(restored)["ok"]


@pytest.mark.parametrize("command,status", [("mark-applied", "applied"), ("reopen", "review_needed")])
def test_cli_requires_pinned_tokens_and_emits_event_json(records, command, status):
    project, decision, first, _ = records
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        code = main(["research", command, "--project", str(project), "--decision-id", decision,
                     "--dossier-id", first, "--expected-snapshot", Repository(project).snapshot().digest,
                     "--expected-decision-revision", "1", "--expected-dossier-revision", "1"])
    assert code == 0 and json.loads(output.getvalue())["status"] == status
