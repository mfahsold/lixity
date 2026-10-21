"""Disposable catalogue failures retain their cause and accepted archive bytes."""

import sqlite3

import pytest

from lixity.research import api, catalogue
from lixity.research.repository import ResearchError
from tests.research_support import capture_research, retained_files


@pytest.fixture
def indexed_project(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic catalogue recovery")
    api.create_dossier(project, "Original note", "Original synthetic text.")
    api.reindex(project)
    return project


@pytest.mark.parametrize("stage,message", [
    ("insert", "database or disk is full"),
    ("fts_schema", "no such module: fts5"),
])
def test_rebuild_preserves_sqlite_cause_and_old_index(indexed_project, monkeypatch, stage, message):
    project = indexed_project
    index = project / ".lixity/research/catalogue.sqlite3"
    old_index = index.read_bytes()
    api.create_dossier(project, "New note", "A synthetic needle.")
    before = retained_files(project)
    failure = sqlite3.OperationalError(message)
    connect = sqlite3.connect

    class FailedConnection(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if ((stage == "insert" and sql.startswith("INSERT INTO documents"))
                    or (stage == "fts_schema" and sql.startswith("CREATE VIRTUAL TABLE"))):
                raise failure
            return super().execute(sql, parameters)

    with monkeypatch.context() as fault:
        fault.setattr(catalogue.sqlite3, "connect",
                      lambda *args, **kwargs: connect(*args, **kwargs, factory=FailedConnection))
        with pytest.raises(ResearchError) as caught:
            api.reindex(project)

    # These checks also guard against replacing a usable old index with a
    # partially built candidate or changing canonical records on rebuild.
    assert index.read_bytes() == old_index
    assert retained_files(project) == before
    assert list(index.parent.glob(".index-*")) == []
    assert message in str(caught.value)
    assert str(index) in str(caught.value)
    assert caught.value.__cause__ is failure
    if stage == "insert":
        assert "fts5" not in str(caught.value).lower()
    with pytest.raises(ResearchError, match="stale"):
        api.search(project, "needle", scope="dossiers")
    api.reindex(project)
    assert len(api.search(project, "needle", scope="dossiers")["hits"]) == 1
    assert retained_files(project) == before


def test_malformed_index_reports_sqlite_cause_then_explicit_refresh_recovers(indexed_project):
    project = indexed_project
    index = project / ".lixity/research/catalogue.sqlite3"
    malformed = b"Synthetic bytes that are not a SQLite database."
    index.write_bytes(malformed)
    before = retained_files(project)

    with pytest.raises(ResearchError) as caught:
        api.search(project, "original", scope="dossiers")

    assert index.read_bytes() == malformed
    assert retained_files(project) == before
    assert "fts5" not in str(caught.value).lower()
    assert str(index) in str(caught.value)
    assert isinstance(caught.value.__cause__, sqlite3.DatabaseError)
    assert str(caught.value.__cause__) in str(caught.value)
    assert "reindex" in str(caught.value)

    result = api.search(project, "original", scope="dossiers", ensure_fresh=True)
    assert len(result["hits"]) == 1
    assert result["warnings"] == ["Search index was refreshed to current project snapshot"]
    assert retained_files(project) == before


def test_strict_search_cli_keeps_failure_exit_code_and_actual_diagnostic(indexed_project):
    project = indexed_project
    index = project / ".lixity/research/catalogue.sqlite3"
    index.write_bytes(b"Synthetic malformed SQLite file.")
    before = retained_files(project)

    code, output, errors = capture_research("search", "--project", str(project),
                                           "--query", "original", "--scope", "dossiers", "--strict")

    assert code == 1
    assert output == ""
    assert "fts5" not in errors.lower()
    assert str(index) in errors
    assert "not a database" in errors
    assert retained_files(project) == before
