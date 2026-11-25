"""Disposable catalogue failures retain their cause and accepted archive bytes."""

import sqlite3

import pytest

from lixity.research import api, catalogue
from lixity.research.repository import Repository, ResearchError
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


def test_search_rechecks_accepted_revisions_when_head_and_index_are_unchanged(indexed_project):
    project = indexed_project
    other = api.create_dossier(project, "Other note", "An unrelated synthetic watchdog.")["dossier_id"]
    api.reindex(project)
    assert len(api.search(project, "original", scope="dossiers")["hits"]) == 1

    repository = Repository(project)
    snapshot = repository.snapshot()
    entry = next(entry for entry in snapshot.manifest.entries if entry.ref.id == other)
    record = repository.record_path(entry)
    record.write_bytes(record.read_bytes().replace(b"watchdog", b"elephant"))

    with pytest.raises(ResearchError, match="Research object checksum mismatch"):
        api.search(project, "original", scope="dossiers", ensure_fresh=True)


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


@pytest.mark.parametrize("ensure_fresh", [False, True])
def test_search_uses_new_index_published_between_snapshot_and_open(indexed_project, monkeypatch, ensure_fresh):
    connect = sqlite3.connect
    reindex = catalogue._reindex_snapshot
    published = {}
    rebuilds = 0

    def count_reindex(repository):
        nonlocal rebuilds
        rebuilds += 1
        return reindex(repository)

    def open_after_publication(database, *args, **kwargs):
        if kwargs.get("uri") and not published:
            published.update(api.create_dossier(indexed_project, "New note", "A newly visible synthetic record."))
            published.update(api.reindex(indexed_project))
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(catalogue, "_reindex_snapshot", count_reindex)
    monkeypatch.setattr(catalogue.sqlite3, "connect", open_after_publication)
    result = api.search(indexed_project, "visible", scope="all", ensure_fresh=ensure_fresh)
    assert [hit["record_id"] for hit in result["hits"]] == [published["dossier_id"]]
    assert result["snapshot"] == published["snapshot"]
    assert rebuilds == 1
    assert result["warnings"] == []


def test_search_finishes_index_transaction_before_verifying_citations(indexed_project, monkeypatch):
    source = indexed_project / "synthetic.txt"
    source.write_text("The safety lantern hangs above the doorway.", encoding="utf-8")
    api.ingest(indexed_project, source, allow_retention=True)
    api.reindex(indexed_project)
    connect = sqlite3.connect
    citation = Repository.citation
    observed = []

    class ReadConnection(sqlite3.Connection):
        def execute(self, sql, parameters=(), /):
            if sql.startswith("SELECT"):
                assert self.in_transaction
                observed.append("query")
            return super().execute(sql, parameters)

        def close(self):
            super().close()
            observed.append("closed")

    def verify(repository, snapshot, passage):
        assert observed == ["query", "query", "closed"]
        return citation(repository, snapshot, passage)

    monkeypatch.setattr(catalogue.sqlite3, "connect",
                        lambda *args, **kwargs: connect(*args, **kwargs, factory=ReadConnection))
    monkeypatch.setattr(Repository, "citation", verify)
    assert len(api.search(indexed_project, "lantern")["hits"]) == 1


def test_nonregular_catalogue_is_not_replaced(indexed_project):
    index = indexed_project / ".lixity/research/catalogue.sqlite3"
    index.unlink()
    index.mkdir()
    before = retained_files(indexed_project)

    with pytest.raises(ResearchError, match="not a regular file"):
        api.search(indexed_project, "original", ensure_fresh=True)
    with pytest.raises(ResearchError, match="not a regular file"):
        api.reindex(indexed_project)

    assert index.is_dir()
    assert retained_files(indexed_project) == before
    assert list(index.parent.glob(".index-*")) == []


def test_excerpt_keeps_match_in_view_when_lowercasing_expands_unicode():
    text = "İ" * 600 + "Needle finishes this note."
    assert catalogue.excerpt(text, ["needle"]) == "…" + "İ" * 100 + "Needle finishes this note."
