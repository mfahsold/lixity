"""Unchanged authored edits preserve archive history without bypassing guards."""

import hashlib
from contextlib import contextmanager

import pytest

from lixity.research import api
from lixity.research.repository import Repository, ResearchConflictError, ResearchError
from tests.research_support import retained_files, revise_record


@pytest.fixture
def archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic unchanged edits")
    source = tmp_path / "source.txt"
    source.write_bytes(b"A synthetic reading room opened.\n")
    capture = api.ingest(project, source, allow_retention=True)
    passage = api.get_source(project, capture["source_id"])["passages"][0]["id"]
    dossier = api.create_dossier(project, "Notes", "Synthetic notes.", evidence_ids=[passage])["dossier_id"]
    claim = api.create_claim(project, title="Gate", statement="The gate opened.", dossier_id=dossier)["claim_id"]
    other = api.create_claim(project, title="Garden", statement="The garden opened.")["claim_id"]
    evidence = api.link_evidence(project, claim_id=claim, passage_id=passage)["evidence_link_id"]
    relation = api.create_claim_relation(project, claim, other)["relation_id"]
    decision = api.record_decision(project, title="Keep date", rationale="Follow the note.",
                                   claim_id=claim, dossier_ids=[dossier])["decision_id"]
    manuscript = project / "draft.md"
    manuscript.write_bytes(b"## Chapter One\n\nThe gate opened.\n")
    snapshot = Repository(project).snapshot()
    linked = api.link_manuscript_claim(project, manuscript, claim, claim_revision=1,
        selection={"start_line": 3, "end_line": 3,
                   "paragraph_sha256": hashlib.sha256(b"The gate opened.").hexdigest(),
                   "start": 0, "end": 16, "quote": "The gate opened."},
        expected_project_id=snapshot.project.id, expected_snapshot=snapshot.digest,
        expected_source_sha256=hashlib.sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True)
    return project, {"dossier": dossier, "claim": claim, "evidence_link": evidence,
                     "claim_relation": relation, "decision": decision,
                     "manuscript_claim_link": linked["link_id"]}


@pytest.mark.parametrize("kind,changes", [
    ("dossier", {"title": " Notes "}),
    ("dossier", {"body": "Synthetic notes."}),
    ("claim", {"place": "   "}),
    ("evidence_link", {"rationale": "   "}),
    ("claim_relation", {"relation": "results_in"}),
    ("decision", {"impact_on_plot": "   "}),
    ("manuscript_claim_link", {"state": "active"}),
])
@pytest.mark.parametrize("dry_run", [False, True])
def test_normalized_unchanged_edits_preserve_bytes_index_and_pinned_review_state(archive, kind, changes, dry_run):
    project, identifiers = archive
    api.reindex(project)
    current = api.get_record(project, kind, identifiers[kind])
    linked_claim = api.get_record(project, "claim", identifiers["claim"])
    before = retained_files(project)
    index = project / ".lixity" / "research" / "catalogue.sqlite3"
    index_state = index.read_bytes(), index.stat().st_mtime_ns

    result = api.revise_record(project, kind, identifiers[kind], changes=changes,
        expected_snapshot=current["snapshot"], expected_revision=1, change_kind="correction",
        reason="Reapply the reviewed value.", dry_run=dry_run)

    assert result["snapshot"] == current["snapshot"]
    if dry_run:
        assert result["schema_version"] == "research-revision-write-preview-local/1"
        assert result["candidate"] == current["record"]
        assert result["fields"] == [] and result["ready"]
    else:
        assert result == {**current, **({"warnings": []} if kind == "claim" else {})}
    assert retained_files(project) == before
    assert (index.read_bytes(), index.stat().st_mtime_ns) == index_state
    assert api.get_record(project, "claim", identifiers["claim"]) == linked_claim
    assert len(api.record_history(project, kind, identifiers[kind])["revisions"]) == 1


def operation(kind, identifier, changes, **overrides):
    return {"kind": kind, "id": identifier, "expected_revision": 1, "changes": changes,
            "change_kind": "correction", "reason": "Reviewed synthetic edit.", **overrides}


@pytest.mark.parametrize("changed", [False, True])
def test_unchanged_batch_members_keep_their_revision_and_only_changed_records_are_published(archive, changed):
    project, identifiers = archive
    snapshot = Repository(project).snapshot()
    before = retained_files(project)
    operations = [operation("dossier", identifiers["dossier"], {"title": " Notes "}),
                  operation("claim", identifiers["claim"],
                            {"statement": "The gate closed."} if changed else {"place": "   "})]
    preview = api.prepare_record_revisions(project, operations)
    assert preview["operations"] == operations
    assert retained_files(project) == before

    result = api.apply_record_revisions(project, preview, expected_snapshot=snapshot.digest)

    assert result["records"] == [
        {"kind": "dossier", "id": identifiers["dossier"], "revision": 1},
        {"kind": "claim", "id": identifiers["claim"], "revision": 2 if changed else 1},
    ]
    after = Repository(project).snapshot()
    assert after.manifest.generation == snapshot.manifest.generation + int(changed)
    assert len(after.manifest.entries) == len(snapshot.manifest.entries) + int(changed)
    assert api.get_record(project, "claim", identifiers["claim"])["reference_updates"] == []
    if changed:
        assert result["snapshot"] != snapshot.digest
        assert api.get_record(project, "claim", identifiers["claim"])["record"]["statement"] == "The gate closed."
        for path, content in before.items():
            if path != "research/HEAD.json":
                assert (project / path).read_bytes() == content
    else:
        assert result["snapshot"] == snapshot.digest
        assert retained_files(project) == before


@pytest.mark.parametrize("overrides", [
    {"reason": ""}, {"reason": "x" * 2001}, {"actor": ""}, {"actor": "x" * 201},
    {"change_kind": "unreviewed"}, {"expected_revision": 2},
    {"changes": {"dossier_id": "invalid"}},
    {"changes": {"dossier_revision": 99}},
])
@pytest.mark.parametrize("dry_run", [False, True])
def test_unchanged_edit_validates_metadata_revision_and_associations_before_returning(archive, overrides, dry_run):
    project, identifiers = archive
    before = retained_files(project)
    arguments = {"changes": {"title": " Gate "}, "expected_revision": 1,
                 "change_kind": "correction", "reason": "Reviewed unchanged value.", **overrides}
    with pytest.raises(ResearchError):
        api.revise_record(project, "claim", identifiers["claim"], dry_run=dry_run, **arguments)
    assert retained_files(project) == before


@pytest.mark.parametrize("mode", ["save", "preview", "batch"])
def test_unchanged_edit_rejects_an_explicit_stale_snapshot(archive, mode):
    project, identifiers = archive
    previous = Repository(project).snapshot()
    revise_record(project, "decision", identifiers["decision"], {"title": "Reviewed date"})
    before = retained_files(project)
    with pytest.raises(ResearchConflictError, match="snapshot changed"):
        if mode == "batch":
            api.apply_record_revisions(project,
                [operation("dossier", identifiers["dossier"], {"title": " Notes "})],
                expected_snapshot=previous.digest)
        else:
            api.revise_record(project, "dossier", identifiers["dossier"], changes={"title": " Notes "},
                expected_snapshot=previous.digest, expected_revision=1, change_kind="correction",
                reason="Reviewed unchanged value.", dry_run=mode == "preview")
    assert retained_files(project) == before


@pytest.mark.parametrize("mode", ["save", "batch"])
def test_unchanged_write_rechecks_head_under_the_writer_lock(archive, monkeypatch, mode):
    project, identifiers = archive
    observed = Repository(project).snapshot()
    original = Repository.locked
    raced = False

    @contextmanager
    def concurrent_writer(repository):
        nonlocal raced
        if not raced:
            raced = True
            api.create_dossier(project, "Concurrent notes", "Synthetic accepted concurrent edit.")
        with original(repository):
            yield

    monkeypatch.setattr(Repository, "locked", concurrent_writer)
    with pytest.raises(ResearchConflictError, match="snapshot changed"):
        if mode == "batch":
            api.apply_record_revisions(project,
                [operation("dossier", identifiers["dossier"], {"title": " Notes "})],
                expected_snapshot=observed.digest)
        else:
            api.revise_record(project, "dossier", identifiers["dossier"], changes={"title": " Notes "},
                expected_snapshot=observed.digest, expected_revision=1, change_kind="correction",
                reason="Reviewed unchanged value.")
    current = api.get_record(project, "dossier", identifiers["dossier"])
    assert current["record"]["revision"] == 1
    assert len(api.list_dossiers(project)["dossiers"]) == 2


@pytest.mark.parametrize("apply", [False, True])
def test_invalid_later_unchanged_batch_member_prevents_all_writes(archive, apply):
    project, identifiers = archive
    snapshot = Repository(project).snapshot()
    before = retained_files(project)
    operations = [operation("dossier", identifiers["dossier"], {"title": "Reviewed notes"}),
                  operation("claim", identifiers["claim"], {"title": " Gate "}, reason="")]
    with pytest.raises(ResearchError, match="reason"):
        if apply:
            api.apply_record_revisions(project, operations, expected_snapshot=snapshot.digest)
        else:
            api.prepare_record_revisions(project, operations)
    assert retained_files(project) == before


def test_empty_repository_commit_retains_head_and_disposable_index(archive):
    project, _ = archive
    api.reindex(project)
    repository = Repository(project)
    snapshot = repository.snapshot()
    before = retained_files(project)
    index = project / ".lixity" / "research" / "catalogue.sqlite3"
    index_bytes = index.read_bytes()

    accepted = repository.commit([], {}, snapshot)

    assert accepted.digest == snapshot.digest
    assert retained_files(project) == before
    assert index.read_bytes() == index_bytes


def test_unchanged_association_preserves_an_old_pin_but_explicit_repin_creates_a_revision(archive):
    project, identifiers = archive
    revise_record(project, "dossier", identifiers["dossier"], {"body": "Reviewed notes."})
    current = api.get_record(project, "claim", identifiers["claim"])
    before = retained_files(project)

    unchanged = api.revise_record(project, "claim", identifiers["claim"],
        changes={"dossier_id": identifiers["dossier"], "dossier_revision": 1},
        expected_revision=1, change_kind="supersession", reason="Reapply the reviewed historical pin.")

    assert unchanged["record"] == current["record"]
    assert unchanged["reference_updates"] == [
        {"kind": "dossier", "id": identifiers["dossier"], "pinned_revision": 1, "latest_revision": 2}]
    assert retained_files(project) == before
    repinned = revise_record(project, "claim", identifiers["claim"], {"dossier_revision": 2})
    assert repinned["record"]["revision"] == 2
    assert repinned["record"]["dossier_ref"] == {"id": identifiers["dossier"], "revision": 2}
    assert repinned["reference_updates"] == []
