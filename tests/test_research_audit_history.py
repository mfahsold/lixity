"""Explicit audits cover accepted manifest ancestry and revision-entry capacity."""

from unittest.mock import patch

import pytest

from lixity.research import api
from lixity.research.models import Manifest
from lixity.research.repository import Repository
from tests.research_support import revise_record


@pytest.fixture
def project(tmp_path):
    project = tmp_path / "synthetic-project"
    api.init(project, title="Synthetic ancestry audit")
    dossier = api.create_dossier(project, "Synthetic dossier", "Synthetic original.")
    revise_record(project, "dossier", dossier["dossier_id"], {"body": "Synthetic correction."})
    return project


@pytest.mark.parametrize("damage", ["missing", "modified"])
def test_audit_rejects_damaged_parent_manifest(project, damage):
    snapshot = Repository(project).snapshot()
    parent = Repository(project).manifest_path(snapshot.manifest.parent)
    if damage == "missing":
        parent.unlink()
    else:
        parent.write_bytes(b"Modified synthetic ancestor")
    result = api.audit(project)
    assert not result["ok"]
    assert result["errors"]
    assert result["snapshot"] == snapshot.digest
    assert result["manifest_history_checked"] is None


def test_audit_reports_history_and_capacity_for_revision_entries(project):
    snapshot = Repository(project).snapshot()
    result = api.audit(project)
    assert result["ok"]
    assert result["manifest_history_checked"] == snapshot.manifest.generation
    assert result["manifest_capacity"] == {
        "entries_used": 3, "entries_max": 100000, "entries_remaining": 99997,
    }
    assert result["records"] == 3  # Three revision objects, two current identities.
    assert len(snapshot.records) == 2
    assert result["warnings"] == []
    assert "manifest ancestry" in result["scope"]
    assert "revision objects" in result["scope"]


def test_audit_reports_unknown_capacity_when_snapshot_is_unavailable(tmp_path):
    result = api.audit(tmp_path / "missing-project")
    assert not result["ok"]
    assert result["manifest_capacity"] == {
        "entries_used": None, "entries_max": 100000, "entries_remaining": None,
    }
    assert result["manifest_history_checked"] is None


@pytest.mark.parametrize("used,warning", [(89999, False), (90000, True), (100000, True)])
def test_capacity_warning_threshold_is_advisory(project, used, warning):
    snapshot = Repository(project).snapshot()
    # Capacity accounting consumes a verified snapshot. Exercise the boundary
    # without creating thousands of unrelated filesystem objects in this test.
    manifest = Manifest.model_construct(**{
        **snapshot.manifest.model_dump(),
        "entries": [snapshot.manifest.entries[0]] * used,
    })
    enlarged = type(snapshot)(snapshot.digest, manifest, snapshot.records, revisions=snapshot.revisions)
    with (patch.object(Repository, "snapshot", return_value=enlarged),
          patch("lixity.research.api._manifest_history", return_value=[])):
        result = api.audit(project)
    assert result["ok"]
    assert bool(result["warnings"]) is warning
    assert result["manifest_capacity"]["entries_remaining"] == 100000 - used
    if warning:
        assert str(used) in result["warnings"][0]
        assert "revision" in result["warnings"][0]


@pytest.mark.parametrize("markdown", [False, True])
def test_human_audit_shows_capacity_history_and_advisory_warnings(project, markdown):
    from lixity.research.presentation import audit_report

    result = api.audit(project)
    result["warnings"] = ["Manifest capacity is near its limit."]
    report = audit_report(result, markdown=markdown)
    assert "Research integrity audit: PASSED" in report
    assert "Checked revision objects: 3" in report
    assert "Manifest entries: 3 / 100000 used; 99997 remaining" in report
    assert "Checked manifests: 3" in report
    assert "Warnings: 1" in report
    assert "Manifest capacity is near its limit." in report
    assert "Findings: 0" in report


@pytest.mark.parametrize("markdown", [False, True])
def test_human_audit_preserves_unknown_capacity_and_history(tmp_path, markdown):
    from lixity.research.presentation import audit_report

    report = audit_report(api.audit(tmp_path / "missing-project"), markdown=markdown)
    assert "Research integrity audit: FAILED" in report
    assert "Manifest entries: Unavailable / 100000 used; Unavailable remaining" in report
    assert "Checked manifests: Unavailable" in report


@pytest.mark.parametrize("markdown", [False, True])
def test_human_audit_bounds_and_escapes_warnings(project, markdown):
    from lixity.research.presentation import audit_report

    result = api.audit(project)
    result["warnings"] = ["<script>[unsafe]\x1b[31m" + "x" * 1100] * 21
    report = audit_report(result, markdown=markdown)
    assert "Warnings: 21" in report
    assert "1 further warnings omitted; use --format json for full details." in report
    assert "truncated; use --format json for full details" in report
    assert "x" * 1001 not in report
    assert "\x1b" not in report
    if markdown:
        assert "<script>" not in report
        assert r"\[unsafe\]" in report
