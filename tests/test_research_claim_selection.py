"""Claim selection metadata always binds forms to one coherent accepted snapshot."""

from unittest.mock import patch

from lixity.research import api
from lixity.research.repository import Repository


def test_claim_selection_context_matches_one_snapshot_and_dossier_filter(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic claim selection")
    dossier = api.create_dossier(project, "Garden", "Synthetic garden notes.")["dossier_id"]
    claim = api.create_claim(project, title="Gate", statement="The gate opened.", dossier_id=dossier)["claim_id"]
    api.create_claim(project, title="Other", statement="Another author assertion.")
    accepted = Repository(project).snapshot()
    read = Repository.snapshot
    with patch.object(Repository, "snapshot", autospec=True, side_effect=read) as snapshots:
        selected = api.list_claims(project, dossier_id=dossier)
    assert snapshots.call_count == 1
    assert set(selected) == {"schema_version", "claims", "project_id", "snapshot"}
    assert selected["schema_version"] == "research-claims-local/2"
    assert selected["project_id"] == accepted.project.id
    assert selected["snapshot"] == accepted.digest
    assert len(selected["claims"]) == 1
    assert selected["claims"][0]["id"] == claim


def test_selection_context_does_not_upgrade_or_change_empty_archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic empty selection")
    before = {path: path.read_bytes() for path in (project / "research").rglob("*") if path.is_file()}
    result = api.list_claims(project)
    assert result["claims"] == [] and result["project_id"]
    assert Repository(project).snapshot().manifest.schema_version == "research-manifest-local/1"
    assert before == {path: path.read_bytes() for path in (project / "research").rglob("*") if path.is_file()}
