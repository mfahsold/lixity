"""Decision dossier pins are checked at commit and untrusted restore boundaries."""

import io
import json
import tarfile
from uuid import uuid4

import pytest

from lixity.research import api
from lixity.research.archive import export_archive, restore_archive
from lixity.research.models import Decision, Dossier, Head, Manifest, Reference
from lixity.research.repository import Repository, ResearchError, digest, encode
from tests.research_support import retained_files, revise_record


@pytest.fixture
def archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic decision reference archive")
    dossier = api.create_dossier(project, "Synthetic notes", "Original notes.")["dossier_id"]
    claim = api.create_claim(
        project, title="Synthetic claim", statement="An authored observation."
    )["claim_id"]
    foreign_project = tmp_path / "other-project"
    api.init(foreign_project, title="Other explicit project")
    foreign = api.create_dossier(foreign_project, "Foreign notes", "Separate retained notes.")[
        "dossier_id"
    ]
    return project, dossier, claim, foreign


def invalid_reference(kind, dossier, claim, foreign):
    if kind == "missing":
        return Reference(id=uuid4().urn)
    if kind == "wrong-kind":
        return Reference(id=claim)
    if kind == "missing-revision":
        return Reference(id=dossier, revision=7)
    return Reference(id=foreign)


@pytest.mark.parametrize("kind", ["missing", "wrong-kind", "missing-revision", "foreign-project"])
def test_typed_decision_commit_rejects_invalid_dossier_pins_without_writes(archive, kind):
    project, dossier, claim, foreign = archive
    repository = Repository(project)
    snapshot = repository.snapshot()
    decision = Decision(
        **api.envelope(snapshot.project.id, "synthetic-author"),
        title="Synthetic decision",
        rationale="An authored choice.",
        dossier_refs=[invalid_reference(kind, dossier, claim, foreign)],
    )
    before = retained_files(project)
    with pytest.raises(ResearchError, match="Missing or incompatible pinned reference"):
        repository.commit([decision], {}, snapshot)
    assert Repository(project).snapshot().digest == snapshot.digest
    assert retained_files(project) == before


def replace_archive_decision_pin(source, target, decision_id, ref):
    """Make all byte checks valid so restore must validate the reference graph."""
    with tarfile.open(source, "r:gz") as archive:
        files = {
            entry.name: archive.extractfile(entry).read()
            for entry in archive.getmembers()
            if entry.isfile()
        }
    metadata = json.loads(files.pop("EXPORT_MANIFEST.json"))
    old_head = Head.model_validate_json(files["research/HEAD.json"])
    old_manifest_path = f"research/manifests/{old_head.sha256}.json"
    manifest = json.loads(files.pop(old_manifest_path))
    decision_path = f"research/revisions/decision/{decision_id[9:]}/1.json"
    decision = json.loads(files[decision_path])
    decision["dossier_refs"] = [ref.model_dump()]
    files[decision_path] = json.dumps(decision).encode()
    for entry in manifest["entries"]:
        if entry["ref"]["id"] == decision_id:
            entry["sha256"] = digest(files[decision_path])
    manifest_bytes = encode(Manifest.model_validate(manifest))
    new_digest = digest(manifest_bytes)
    files[f"research/manifests/{new_digest}.json"] = manifest_bytes
    files["research/HEAD.json"] = encode(Head(sha256=new_digest))
    metadata["snapshot"] = new_digest
    metadata["files"] = {
        name: {"sha256": digest(content), "byte_length": len(content)}
        for name, content in files.items()
    }
    files["EXPORT_MANIFEST.json"] = json.dumps(metadata).encode()
    with tarfile.open(target, "w:gz") as archive:
        for name, content in files.items():
            entry = tarfile.TarInfo(name)
            entry.size = len(content)
            archive.addfile(entry, io.BytesIO(content))


@pytest.mark.parametrize("kind", ["missing", "wrong-kind", "missing-revision", "foreign-project"])
def test_restore_rejects_checksum_valid_invalid_decision_dossier_pins(archive, tmp_path, kind):
    project, dossier, claim, foreign = archive
    decision = api.record_decision(
        project, title="Synthetic decision", rationale="A reviewed choice.", dossier_ids=[dossier]
    )["decision_id"]
    original = tmp_path / "valid.tar.gz"
    modified = tmp_path / "invalid-reference.tar.gz"
    export_archive(project, original)
    replace_archive_decision_pin(
        original, modified, decision, invalid_reference(kind, dossier, claim, foreign)
    )
    target = tmp_path / "restored"
    before = retained_files(project)
    with pytest.raises(ResearchError, match="Missing or incompatible pinned reference"):
        restore_archive(modified, target)
    assert not (target / "research").exists()
    assert list(target.iterdir()) == []
    assert retained_files(project) == before


def test_valid_historical_and_withdrawn_decision_dossier_pins_survive_restore(archive, tmp_path):
    project, dossier, _, _ = archive
    decision = api.record_decision(
        project,
        title="Synthetic decision",
        rationale="Preserve its original context.",
        dossier_ids=[dossier],
    )["decision_id"]
    revise_record(project, "dossier", dossier, {"body": "Revised synthetic notes."})
    snapshot = Repository(project).snapshot()
    api.withdraw(
        project, dossier_id=dossier, expected_snapshot=snapshot.digest, expected_revision=2
    )
    revise_record(project, "decision", decision, {"title": "Retained historical association"})
    snapshot = Repository(project).snapshot()
    pin = snapshot.latest(decision, Decision).dossier_refs[0]
    assert pin == Reference(id=dossier, revision=1)
    assert snapshot.get(pin, Dossier).body == "Original notes."
    # A narrowed snapshot deliberately excludes cross-kind lookup targets.
    filtered = Repository(project).snapshot(kinds=frozenset({"decision"}))
    assert filtered.latest(decision, Decision).dossier_refs == [pin]
    assert not any(isinstance(record, Dossier) for record in filtered.records.values())
    exported = tmp_path / "historical.tar.gz"
    restored = tmp_path / "restored"
    export_archive(project, exported)
    restore_archive(exported, restored)
    assert api.get_record(restored, "decision", decision)["record"]["dossier_refs"] == [
        {"id": dossier, "revision": 1}
    ]
    assert api.get_record(restored, "dossier", dossier, revision=1)["availability"] == "withdrawn"
    assert api.audit(restored)["ok"]
