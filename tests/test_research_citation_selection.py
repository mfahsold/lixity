"""Keyword citation selection keeps exact retained paragraphs and reviewed snapshots."""

import json
from unittest.mock import patch

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.research.repository import Repository


@pytest.fixture
def archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic research", language="en")
    source = tmp_path / "source.txt"
    source.write_bytes("Café 🕯 lantern uniqueone.\r\n\r\nA second lantern in the reading room.\r\n".encode())
    captured = api.ingest(project, source, allow_retention=True)
    return project, source, captured


def canonical_files(project):
    return {str(path.relative_to(project)): path.read_bytes()
            for path in (project / "research").rglob("*") if path.is_file()}


def invoke(project, capsys, *arguments):
    code = main(["research", "cite", "--project", str(project), *arguments])
    captured = capsys.readouterr()
    return code, json.loads(captured.out) if captured.out.strip() else None, captured.err


def test_unique_query_returns_unchanged_full_paragraph_citation_without_archive_writes(archive, capsys):
    project, _, captured = archive
    before = canonical_files(project)
    match = api.search(project, "uniqueone", ensure_fresh=True)["hits"][0]
    code, result, error = invoke(project, capsys, "--query", "uniqueone")
    assert code == 0, error
    assert result == api.cite(project, match["passage_id"])
    assert result["schema_version"] == "research-citation-local/1"
    assert result["verbatim"] == "Café 🕯 lantern uniqueone."
    assert result["source_id"] == captured["source_id"]
    assert result["end"] - result["start"] == len(result["verbatim"])
    assert canonical_files(project) == before


def test_ambiguous_query_requires_numbered_choice_and_its_snapshot(archive, capsys):
    project, _, _ = archive
    before = canonical_files(project)
    code, candidates, error = invoke(project, capsys, "--query", "lantern")
    assert code == 1 and candidates["schema_version"] == "research-search-local/1"
    assert len(candidates["hits"]) == 2
    assert "--pick" in error and "--expected-snapshot" in error
    code, result, error = invoke(project, capsys, "--query", "lantern", "--pick", "2",
                                 "--expected-snapshot", candidates["snapshot"])
    assert code == 0, error
    assert result == api.cite(project, candidates["hits"][1]["passage_id"])
    assert canonical_files(project) == before


def test_choice_without_reviewed_snapshot_and_invalid_choices_are_rejected(archive, capsys):
    project, _, _ = archive
    before = canonical_files(project)
    code, result, error = invoke(project, capsys, "--query", "lantern", "--pick", "1")
    assert code != 0 and result is None and "--expected-snapshot" in error
    snapshot = Repository(project).snapshot().digest
    code, result, error = invoke(project, capsys, "--query", "lantern", "--pick", "3",
                                 "--expected-snapshot", snapshot)
    assert code == 1 and result is None
    assert canonical_files(project) == before


@pytest.mark.parametrize("change", ["refresh", "withdraw", "purge", "metadata"])
def test_archive_changes_between_search_and_resolution_are_rejected(archive, capsys, change):
    project, source, captured = archive
    original = api.search

    def changed(*args, **kwargs):
        candidates = original(*args, **kwargs)
        if change == "refresh":
            source.write_text("A replacement uniqueone paragraph.", encoding="utf-8")
            api.ingest(project, source, source_id=captured["source_id"], allow_retention=True)
        elif change == "withdraw":
            api.withdraw(project, captured["source_id"], reason="Synthetic withdrawal")
        elif change == "purge":
            api.purge(project, captured["source_id"], reason="Synthetic purge", dry_run=False)
        else:
            api.create_claim(project, title="A new note", statement="An authored synthetic statement")
        return candidates

    with patch.object(api, "search", side_effect=changed):
        code, result, error = invoke(project, capsys, "--query", "uniqueone")
    assert code == 1 and result is None
    assert "snapshot" in error.lower() or "changed" in error.lower()


def test_busy_writer_does_not_resolve_or_write(archive, capsys):
    project, _, _ = archive
    api.search(project, "uniqueone", ensure_fresh=True)
    before = canonical_files(project)
    with Repository(project).locked():
        code, result, error = invoke(project, capsys, "--query", "uniqueone")
    assert code == 1 and result is None and "busy" in error
    assert canonical_files(project) == before


def test_legacy_passage_citation_still_returns_withdrawn_historical_reference(archive, capsys):
    project, _, captured = archive
    passage = api.search(project, "uniqueone", ensure_fresh=True)["hits"][0]["passage_id"]
    api.withdraw(project, captured["source_id"], reason="Synthetic withdrawal")
    code, result, error = invoke(project, capsys, "--passage", passage)
    assert code == 0, error
    assert result == api.cite(project, passage) and result["availability"] == "withdrawn"
