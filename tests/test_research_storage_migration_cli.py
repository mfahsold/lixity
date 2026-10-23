"""Migration is an explicit project operation with a non-overwriting backup."""

import json

from lixity.cli import main
from lixity.research import api
from lixity.research.repository import Repository
from tests.test_research_storage_migration import legacy_copy


def test_cli_migration_uses_explicit_project_and_preserves_snapshot(tmp_path, capsys):
    project = tmp_path / "project"
    api.init(project, title="Synthetic migration")
    expected = Repository(project).snapshot().digest
    legacy_copy(project)
    backup = tmp_path / "before.tar.gz"
    assert main(["research", "migrate-storage", "--project", str(project), "--backup", str(backup),
                 "--expected-snapshot", expected, "--json"]) == 0
    receipt = json.loads(capsys.readouterr().out)
    assert receipt["snapshot"] == expected and not receipt["already_current"]
    assert backup.is_file() and api.audit(project)["ok"]
