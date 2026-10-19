"""Python revisions follow the CLI snapshot ergonomics without losing guards."""

import pytest

from lixity.research import api
from lixity.research.models import Claim
from lixity.research.repository import Repository, ResearchConflictError, ResearchError


def test_python_revision_forwards_the_read_snapshot_when_omitted(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic revision archive")
    claim = api.create_claim(project, title="Gate", statement="The gate opened.", time_period="1923")["claim_id"]

    revised = api.revise_record(
        project, "claim", claim, changes={"title": "Reviewed gate"},
        expected_revision=1, change_kind="correction", reason="Synthetic correction.")

    assert revised["record"]["revision"] == 2
    assert revised["record"]["title"] == "Reviewed gate"
    with pytest.raises(ResearchConflictError, match="reviewed revision is no longer current"):
        api.revise_record(
            project, "claim", claim, changes={"title": "Stale draft"},
            expected_revision=1, change_kind="correction", reason="Synthetic stale attempt.")


def test_python_revision_requires_pins_for_new_associations_without_snapshot(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic revision archive")
    dossier = api.create_dossier(project, "Garden", "Synthetic garden notes.")["dossier_id"]
    claim = api.create_claim(project, title="Gate", statement="The gate opened.")["claim_id"]

    with pytest.raises(ResearchError, match="requires --dossier-revision"):
        api.revise_record(
            project, "claim", claim, changes={"dossier_id": dossier},
            expected_revision=1, change_kind="correction", reason="Synthetic association change.")

    current = api.get_record(project, "claim", claim)
    revised = api.revise_record(
        project, "claim", claim, changes={"dossier_id": dossier},
        expected_snapshot=current["snapshot"], expected_revision=1,
        change_kind="correction", reason="Synthetic reviewed association change.")
    assert revised["record"]["dossier_ref"]["id"] == dossier

def test_snapshot_cache_still_sees_commits_from_other_instances(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic cache archive")
    reader = Repository(project)
    before = reader.snapshot()

    api.create_claim(project, title="Gate", statement="The gate opened.")

    after = reader.snapshot()
    assert after.digest != before.digest
    assert any(isinstance(record, Claim) for record in after.records.values())
    with pytest.raises(ResearchConflictError):
        reader.commit([], {}, before)


def test_exact_write_preview_validates_candidate_without_locking_or_publishing(tmp_path, monkeypatch):
    api.init(tmp_path, title="Synthetic exact write preview")
    claim = api.create_claim(tmp_path, title="Gate", statement="The gate opened.", place="Old harbour")["claim_id"]
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    def unexpected_write(*args, **kwargs):
        pytest.fail("A write preview must not acquire a lock or publish")

    monkeypatch.setattr(Repository, "locked", unexpected_write)
    monkeypatch.setattr(Repository, "commit", unexpected_write)
    preview = api.revise_record(tmp_path, "claim", claim, changes={"place": "New harbour"},
                                expected_revision=1, change_kind="correction", reason="Synthetic correction",
                                dry_run=True)
    assert preview["schema_version"] == "research-revision-write-preview-local/1"
    assert preview["dry_run"] is True and preview["ready"] is True
    assert preview["candidate"]["revision"] == 2
    assert preview["candidate"]["scope"]["place"] == "New harbour"
    assert preview["fields"] == [{"field": "place", "before": "Old harbour", "after": "New harbour"}]
    assert {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()} == before


@pytest.mark.parametrize("operation, expected", [
    ({"expected_revision": 9}, "revision changed"),
    ({"reason": ""}, "reason"),
    ({"change_kind": "guess"}, "correction or supersession"),
    ({"changes": {"unknown": "Value"}}, "unknown or immutable"),
    ({"expected_snapshot": "0" * 64}, "snapshot changed"),
])
@pytest.mark.parametrize("dry_run", [False, True])
def test_exact_preview_and_write_reject_the_same_invalid_operation(tmp_path, operation, expected, dry_run):
    api.init(tmp_path, title="Synthetic shared write validation")
    claim = api.create_claim(tmp_path, title="Gate", statement="The gate opened.")["claim_id"]
    before = Repository(tmp_path).snapshot().digest
    request = {"expected_revision": 1, "change_kind": "correction", "reason": "Synthetic correction",
               "changes": {"title": "New title"}, **operation}
    with pytest.raises(ResearchError, match=expected):
        api.revise_record(tmp_path, "claim", claim, dry_run=dry_run, **request)
    assert Repository(tmp_path).snapshot().digest == before


def test_historical_comparison_preserves_scope_and_reference_revision_changes(tmp_path):
    from tests.research_support import revise_record

    api.init(tmp_path, title="Synthetic historical comparison")
    dossier = api.create_dossier(tmp_path, "Notes", "Body.")["dossier_id"]
    claim = api.create_claim(tmp_path, title="Gate", statement="The gate opened.",
                             place="Old harbour", dossier_id=dossier)["claim_id"]
    revise_record(tmp_path, "dossier", dossier, {"title": "New notes"})
    revise_record(tmp_path, "claim", claim, {"place": "New harbour", "dossier_revision": 2})
    before = Repository(tmp_path).snapshot().digest
    compared = api.compare_record_revisions(tmp_path, "claim", claim, from_revision=1)
    assert compared["from_revision"] == 1 and compared["to_revision"] == 2
    assert compared["fields"] == [
        {"field": "dossier_id", "before": {"id": dossier, "revision": 1}, "after": {"id": dossier, "revision": 2}},
        {"field": "place", "before": "Old harbour", "after": "New harbour"},
    ]
    assert api.compare_record_revisions(tmp_path, "claim", claim, from_revision=1, to_revision=1)["fields"] == []
    assert Repository(tmp_path).snapshot().digest == before


@pytest.mark.parametrize("dry_run", [False, True])
def test_unrelated_revision_preserves_existing_unavailable_evidence(tmp_path, dry_run):
    api.init(tmp_path, title="Synthetic retained evidence history")
    source_file = tmp_path / "source.txt"
    source_file.write_text("Synthetic retained paragraph.", encoding="utf-8")
    source = api.ingest(tmp_path, source_file, allow_retention=True)
    passage = api.get_source(tmp_path, source["source_id"])["passages"][0]["id"]
    dossier = api.create_dossier(tmp_path, "Notes", "Keep authored notes.", evidence_ids=[passage])["dossier_id"]
    api.purge(tmp_path, source["source_id"], reason="Synthetic removal", dry_run=False)
    result = api.revise_record(tmp_path, "dossier", dossier, changes={"title": "Reviewed notes"},
                               expected_revision=1, change_kind="correction", reason="Review title only", dry_run=dry_run)
    record = result["candidate"] if dry_run else result["record"]
    assert record["evidence_refs"] == [{"id": passage, "revision": 1}]


@pytest.mark.parametrize("dry_run", [False, True])
def test_exact_write_preview_preserves_claim_period_warnings(tmp_path, dry_run):
    api.init(tmp_path, title="Synthetic chronology warning")
    claim = api.create_claim(tmp_path, title="Gate", statement="The gate opened.")["claim_id"]
    result = api.revise_record(tmp_path, "claim", claim, changes={"time_period": "present day"},
                               expected_revision=1, change_kind="correction", reason="Describe an uncertain period",
                               dry_run=dry_run)
    assert result["warnings"] and "present day" in result["warnings"][0]


@pytest.mark.parametrize("mode", ["preview", "save", "batch", "reconcile"])
def test_authored_candidates_validate_the_encoded_record_budget_before_publication(tmp_path, monkeypatch, mode):
    from lixity.research import repository
    from tests.research_support import retained_files

    api.init(tmp_path, title="Synthetic size validation")
    identifier = api.create_dossier(tmp_path, "Notes", "Original body.")["dossier_id"]
    before = retained_files(tmp_path)
    # Keep the filesystem reads real and lower only the encoder's publication
    # budget: this candidate is model-valid but cannot become a stored object.
    monkeypatch.setattr(repository, "MAX_RESEARCH_OBJECT_BYTES", 2048)
    with pytest.raises(ResearchError, match="size"):
        if mode == "reconcile":
            api.prepare_record_revision(tmp_path, "dossier", identifier, base_revision=1,
                                        changes={"body": "Reviewed body. " * 300})
        elif mode == "batch":
            api.prepare_record_revisions(tmp_path, [{"kind": "dossier", "id": identifier,
                "expected_revision": 1, "changes": {"body": "Reviewed body. " * 300},
                "change_kind": "correction", "reason": "Synthetic review"}])
        else:
            api.revise_record(tmp_path, "dossier", identifier, changes={"body": "Reviewed body. " * 300},
                expected_revision=1, change_kind="correction", reason="Synthetic review", dry_run=mode == "preview")
    assert retained_files(tmp_path) == before


@pytest.mark.parametrize("mode", ["preview", "save", "batch", "reconcile"])
def test_revision_admission_validates_the_next_manifest_budget_without_writing(tmp_path, monkeypatch, mode):
    from lixity.research import repository
    from tests.research_support import retained_files

    api.init(tmp_path, title="Synthetic manifest admission")
    identifier = api.create_dossier(tmp_path, "Notes", "Original body.")["dossier_id"]
    for number in range(4):
        api.create_dossier(tmp_path, f"Other {number}", "Synthetic note.")
    snapshot = Repository(tmp_path).snapshot()
    before = retained_files(tmp_path)
    # Existing objects and the reviewed snapshot fit; only the appended manifest
    # exceeds the publication budget. The candidate itself remains small.
    monkeypatch.setattr(repository, "MAX_RESEARCH_OBJECT_BYTES", len(repository.encode(snapshot.manifest)) + 100)
    with pytest.raises(ResearchError, match="size"):
        if mode == "reconcile":
            api.prepare_record_revision(tmp_path, "dossier", identifier, base_revision=1,
                                        changes={"title": "Reviewed notes"})
        elif mode == "batch":
            api.prepare_record_revisions(tmp_path, [{"kind": "dossier", "id": identifier,
                "expected_revision": 1, "changes": {"title": "Reviewed notes"},
                "change_kind": "correction", "reason": "Synthetic review"}])
        else:
            api.revise_record(tmp_path, "dossier", identifier, changes={"title": "Reviewed notes"},
                expected_revision=1, change_kind="correction", reason="Synthetic review", dry_run=mode == "preview")
    assert retained_files(tmp_path) == before
    if mode == "reconcile":
        unchanged = api.prepare_record_revision(tmp_path, "dossier", identifier, base_revision=1,
                                               changes={"title": "Notes"})
        assert unchanged["ready"] and not unchanged["has_changes"]
