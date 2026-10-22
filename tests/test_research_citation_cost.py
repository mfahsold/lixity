"""Citation batches preserve pinned bytes without rescanning the archive per hit."""

from dataclasses import replace

import pytest

from lixity.research import api
from lixity.research.models import Dossier, Reference, Tombstone
from lixity.research.repository import Repository
from lixity.research.revisions import EvidenceCitationReader, _view


class CountedRecords(dict):
    """Observe complete archive traversals without replacing their contents."""

    scans = 0

    def values(self):
        self.scans += 1
        return super().values()


@pytest.fixture
def citation_batch(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic citation batch")
    source = tmp_path / "source.txt"
    source.write_text("\n\n".join(f"The archived station note {n} was retained." for n in range(12)))
    ingested = api.ingest(project, source, allow_retention=True)
    passages = api.get_source(project, ingested["source_id"])["passages"]
    identifier = api.create_dossier(project, "Station archive", "## Notes\nSynthetic notes.",
                                    evidence_ids=[p["id"] for p in passages])["dossier_id"]
    claim = api.create_claim(project, title="Station notes", statement="Twelve records were retained.")["claim_id"]
    for passage in passages:
        api.link_evidence(project, claim_id=claim, passage_id=passage["id"])
    repository = Repository(project)
    snapshot = repository.snapshot()
    records = CountedRecords(snapshot.records)
    snapshot = replace(snapshot, records=records)
    return repository, snapshot, identifier, records, passages


@pytest.mark.parametrize("view", ["dossier", "summary", "record", "links", "matrix"])
def test_citation_batch_has_bounded_archive_scans(citation_batch, view):
    repository, snapshot, identifier, records, passages = citation_batch
    records.scans = 0
    if view == "links":
        data = api._list_evidence_links(repository, snapshot)
        assert {item["citation"]["verbatim"] for item in data["evidence_links"]} == {p["verbatim"] for p in passages}
    elif view == "matrix":
        data = api._claim_matrix_data(repository, snapshot)
        assert len(data["claims"]) == 1
        assert len(data["claims"][0]["evidence"]) == len(passages)
    elif view == "record":
        data = _view(repository, snapshot, snapshot.latest(identifier, Dossier))
    else:
        data = api._get_dossier(repository, snapshot, identifier, summary=view == "summary")
    if view in {"dossier", "record"}:
        assert [c["verbatim"] for c in data["citations"]] == [p["verbatim"] for p in passages]
        assert all(c["source_sequence"] == c["latest_source_sequence"] == 1 for c in data["citations"])
    elif view == "summary":
        assert data["citation_count"] == len(passages)
        assert data["source_updates"] == []
    assert records.scans <= 10, f"{records.scans} archive scans for {len(passages)} citations"


def test_public_citation_batches_reobserve_source_versions_and_withdrawals(citation_batch):
    repository, _snapshot, identifier, _records, passages = citation_batch
    initial = api.get_dossier(repository.root, identifier)
    source_id = initial["citations"][0]["source_id"]
    cited_version = initial["citations"][0]["source_version_id"]
    source = repository.root.parent / "source.txt"
    source.write_text("A revised station note with a different conclusion.")
    refreshed = api.ingest(repository.root, source, source_id=source_id, allow_retention=True)

    current = api.get_dossier(repository.root, identifier)
    assert [c["verbatim"] for c in current["citations"]] == [p["verbatim"] for p in passages]
    assert all(c["source_version_id"] == cited_version for c in current["citations"])
    assert all(c["latest_source_version_id"] == refreshed["source_version_id"] for c in current["citations"])
    assert all(c["newer_source_available"] for c in current["citations"])

    api.withdraw(repository.root, source_id, version_id=refreshed["source_version_id"])
    withdrawn = api.get_dossier(repository.root, identifier)
    assert all(c["latest_source_version_id"] == cited_version for c in withdrawn["citations"])
    assert withdrawn["source_updates"] == []

    api.withdraw(repository.root, source_id)
    unavailable = api.get_dossier(repository.root, identifier)
    assert all(c["availability"] == "withdrawn" for c in unavailable["citations"])
    assert all(c["latest_source_version_id"] == cited_version for c in unavailable["citations"])
    assert unavailable["source_updates"] == []


def test_new_public_read_reverifies_retained_quote_bytes(citation_batch):
    repository, _snapshot, identifier, _records, _passages = citation_batch
    accepted = api.get_dossier(repository.root, identifier)
    assert all("verbatim" in citation for citation in accepted["citations"])
    blob = next((repository.data / "blobs").iterdir())
    original = blob.read_bytes()
    try:
        blob.write_bytes(b"Changed retained source bytes.")
        unavailable = api.get_dossier(repository.root, identifier)
        assert all("error" in citation and "verbatim" not in citation for citation in unavailable["citations"])
    finally:
        blob.write_bytes(original)
    assert api.get_dossier(repository.root, identifier) == accepted


def test_purged_citation_batch_retains_exact_unavailable_state_with_bounded_scans(citation_batch):
    repository, _snapshot, identifier, _records, passages = citation_batch
    source_id = api.get_dossier(repository.root, identifier)["citations"][0]["source_id"]
    api.purge(repository.root, source_id)
    snapshot = Repository(repository.root).snapshot()
    records = CountedRecords(snapshot.records)
    snapshot = replace(snapshot, records=records)
    records.scans = 0

    result = api._get_dossier(repository, snapshot, identifier)
    assert [citation["passage_id"] for citation in result["citations"]] == [p["id"] for p in passages]
    assert all(citation["availability"] == "purged" for citation in result["citations"])
    assert all("verbatim" not in citation for citation in result["citations"])
    assert result["source_updates"] == []
    assert records.scans <= 10


def test_purged_citation_projection_preserves_full_reference_and_kind(citation_batch):
    repository, _snapshot, identifier, _records, passages = citation_batch
    source_id = api.get_dossier(repository.root, identifier)["citations"][0]["source_id"]
    api.purge(repository.root, source_id)
    snapshot = repository.snapshot()
    wrong_kind = next(record.id for record in snapshot.records.values() if record.kind == "claim")
    tombstone = Tombstone(**api.envelope(snapshot.project.id, "synthetic-author"),
                          target_kind="claim", target_ref=Reference(id=wrong_kind),
                          operation="purge", reason="Synthetic retained lifecycle")
    snapshot = repository.commit([tombstone], {}, snapshot)
    reader = EvidenceCitationReader(repository, snapshot)
    assert reader.read(Reference(id=passages[0]["id"]))["availability"] == "purged"
    assert "availability" not in reader.read(Reference(id=passages[0]["id"], revision=2))
    assert "availability" not in reader.read(Reference(id=wrong_kind))
