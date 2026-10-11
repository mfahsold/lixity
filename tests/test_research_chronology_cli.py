"""The CLI reuses read-only chronology and explicit authored relation revisions."""

import json

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.research.repository import Repository


@pytest.fixture
def archive(tmp_path, monkeypatch):
    project = tmp_path / "archive"
    api.init(project, title="Synthetic chronology", language="en")
    later = api.create_claim(project, title="Later", statement="A later synthetic event", time_period="1910–1920")
    early = api.create_claim(project, title="Earlier", statement="An earlier synthetic event", time_period="1900")
    missing = api.create_claim(project, title="Unplaced", statement="A synthetic undated statement")
    monkeypatch.chdir(project)
    return project, early["claim_id"], later["claim_id"], missing["claim_id"]


def invoke(capsys, *arguments):
    code = main(["research", *arguments])
    output = capsys.readouterr()
    return code, output.out, output.err


def test_chronology_cli_uses_initialized_cwd_and_preserves_archive(archive, capsys):
    project, early, later, missing = archive
    before = Repository(project).snapshot()
    code, output, error = invoke(capsys, "timeline")
    assert code == 0, error
    result = json.loads(output)
    assert [item["claim_id"] for item in result["dated"]] == [early, later]
    assert [item["claim_id"] for item in result["unplaced"]] == [missing]
    assert Repository(project).snapshot().manifest == before.manifest
    assert Repository(project).snapshot().digest == before.digest


@pytest.mark.parametrize("format_name", ["text", "md"])
def test_human_chronology_preserves_periods_and_unplaced_claims(archive, capsys, format_name):
    code, output, error = invoke(capsys, "timeline", "--format", format_name)
    assert code == 0, error
    assert output.index("Earlier") < output.index("Later")
    assert "1910–1920" in output and "Unplaced" in output
    assert "author" in output.lower()


def test_positional_relation_alias_and_shared_retraction_history(archive, capsys):
    project, early, later, _ = archive
    code, output, error = invoke(capsys, "relate", early, later, "--relation", "results_in",
                                 "--rationale", "An authored synthetic interpretation")
    assert code == 0, error
    created = json.loads(output)
    assert created["relation"] == "causes"
    assert Repository(project).snapshot().manifest.schema_version == "research-manifest-local/6"
    code, output, error = invoke(capsys, "relate")
    assert code == 0, error
    assert json.loads(output)["relations"][0]["relation_id"] == created["relation_id"]
    code, output, error = invoke(capsys, "relate", "--relation-id", created["relation_id"], "--update",
        "--state", "retracted", "--expected-snapshot", created["snapshot"], "--expected-revision", "1",
        "--change-kind", "correction", "--reason", "Withdraw the synthetic interpretation")
    assert code == 0, error
    assert json.loads(output)["record"]["revision"] == 2
    code, output, error = invoke(capsys, "relate", "--relation-id", created["relation_id"], "--history")
    assert code == 0, error
    history = json.loads(output)
    assert len(history["revisions"]) == 2
    assert api.list_claim_relations(project)["relations"] == []
