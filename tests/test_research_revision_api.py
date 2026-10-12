"""Python revisions follow the CLI snapshot ergonomics without losing guards."""

import pytest

from lixity.research import api
from lixity.research.repository import ResearchConflictError, ResearchError


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
