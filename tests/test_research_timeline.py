"""Chronology is a conservative read-only view of author-entered claim periods."""

import pytest

from lixity.research import api
from lixity.research.models import Activity, Reference
from lixity.research.repository import Repository


def authoritative_bytes(project):
    return {path.relative_to(project): path.read_bytes()
            for path in (project / "research").rglob("*") if path.is_file()}


def advance_archive(project, target):
    dossier = api.create_dossier(project, "Synthetic notes", "Synthetic unchanged notes.")["dossier_id"]
    claim = api.create_claim(project, title="Synthetic claim", statement="The gate opened.", time_period="1912",
                             dossier_id=dossier)["claim_id"]
    if target >= 2:
        current = api.get_record(project, "claim", claim)
        api.revise_record(project, "claim", claim, changes={"place": "Garden"},
                          expected_snapshot=current["snapshot"], expected_revision=1,
                          change_kind="correction", reason="Synthetic scope correction.")
    if target >= 3:
        source = project / "synthetic-source.txt"
        source.write_text("A synthetic note records an opened gate.\n", encoding="utf-8")
        captured = api.ingest(project, source, allow_retention=True, context={"external_reference": {
            "provider": "zotero", "server_id": "synthetic-server", "library": "users/0",
            "item_key": "ABCDEFGH", "attachment_key": "IJKLMNOP", "item_version": 1, "attachment_version": 1,
        }})
    if target >= 4:
        repository = Repository(project)
        snapshot = repository.snapshot()
        activity = Activity(**api.envelope(snapshot.project.id, "synthetic-author"),
                            schema_version="research-local/4",
                            source_version_ref=Reference(id=captured["source_version_id"]),
                            operation="extract_ocr", implementation="tesseract-cli/1")
        repository.commit([activity], {}, snapshot)
    if target >= 5:
        decision = api.record_decision(project, title="Synthetic choice", rationale="Keep the garden scene.",
                                       dossier_ids=[dossier])["decision_id"]
        snapshot = Repository(project).snapshot()
        api.acknowledge_decision(project, decision, dossier, expected_snapshot=snapshot.digest,
                                expected_decision_revision=1, expected_dossier_revision=1, status="applied")
    return dossier, claim


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_reading_timeline_and_relations_preserves_legacy_archive_bytes(tmp_path, version):
    project = tmp_path / "project"
    api.init(project, title="Synthetic chronology archive")
    dossier, claim = advance_archive(project, version)
    repository = Repository(project)
    assert repository.snapshot().manifest.schema_version == f"research-manifest-local/{version}"
    before = authoritative_bytes(project)
    timeline = api.timeline(project, dossier_id=dossier)
    relations = api.list_claim_relations(project)
    assert timeline["dated"][0]["claim_id"] == claim
    assert relations["relations"] == []
    assert relations["archive_schema_version"] == f"research-manifest-local/{version}"
    assert authoritative_bytes(project) == before


@pytest.mark.parametrize("label,start,end,precision", [
    ("0001", "0001-01-01", "0001-12-31", "year"),
    ("1912", "1912-01-01", "1912-12-31", "year"),
    ("1912–1914", "1912-01-01", "1914-12-31", "year"),
    ("1912 - 1914", "1912-01-01", "1914-12-31", "year"),
    ("2000-02-29", "2000-02-29", "2000-02-29", "day"),
    ("1912-05-01 / 1912-05-03", "1912-05-01", "1912-05-03", "day"),
    ("1912-05-01 - 1912-05-03", "1912-05-01", "1912-05-03", "day"),
])
def test_explicit_calendar_periods_keep_label_and_precision(tmp_path, label, start, end, precision):
    project = tmp_path / "project"
    api.init(project, title="Synthetic chronology archive")
    api.create_claim(project, title="Gate", statement="The gate opened.", time_period=label)
    row = api.timeline(project)["dated"][0]
    assert row["time_period"] == label
    assert row["period"] == {"start": start, "end": end, "precision": precision}


@pytest.mark.parametrize("label,reason", [
    (None, "missing"), ("autumn 1912", "unrecognized"), ("44 BCE", "unrecognized"),
    ("1912-05", "unrecognized"), ("2019-02-29", "invalid"), ("0000", "invalid"),
    ("1914–1912", "invalid"), ("1912-05-03 / 1912-05-01", "invalid"),
])
def test_unplaced_periods_remain_visible_without_created_date_fallback(tmp_path, label, reason):
    project = tmp_path / "project"
    api.init(project, title="Synthetic chronology archive")
    identifier = api.create_claim(project, title="Gate", statement="The gate opened.", time_period=label)["claim_id"]
    result = api.timeline(project)
    assert result["dated"] == []
    assert result["unplaced"][0]["claim_id"] == identifier
    assert result["unplaced"][0]["time_period"] == label
    assert result["unplaced"][0]["reason"] == reason


def test_chronology_uses_latest_claim_scope_and_period_order_not_creation_order(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic chronology archive")
    dossier = api.create_dossier(project, "Garden", "Synthetic garden notes.")["dossier_id"]
    late = api.create_claim(project, title="Later", statement="The leaves fell.", time_period="1914",
                            dossier_id=dossier)["claim_id"]
    early = api.create_claim(project, title="Earlier", statement="The gate opened.", time_period="1912",
                             dossier_id=dossier)["claim_id"]
    api.create_claim(project, title="Other dossier", statement="The rain stopped.", time_period="1900")
    current = api.get_record(project, "claim", late)
    api.revise_record(project, "claim", late, changes={"time_period": "1910", "actors": ["Gardener"]},
                      expected_snapshot=current["snapshot"], expected_revision=1,
                      change_kind="correction", reason="Author revised the period.")
    before = authoritative_bytes(project)
    result = api.timeline(project, dossier_id=dossier)
    assert [row["claim_id"] for row in result["dated"]] == [late, early]
    assert result["dated"][0]["revision"] == 2
    assert result["dated"][0]["actors"] == ["Gardener"]
    assert result["dated"][0]["dossier_id"] == dossier
    assert result["dated"][0]["dossier_revision"] == 1
    assert authoritative_bytes(project) == before
