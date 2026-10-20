"""Accepted purges distinguish incomplete filesystem cleanup from write failure."""

from pathlib import Path
from unittest.mock import patch

import pytest

from lixity.research import api
from lixity.research.models import Reference, SourceVersion
from lixity.research.repository import Repository, ResearchCleanupError, ResearchStorageError
from tests.research_support import capture_research, retained_files


@pytest.fixture
def captured(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic cleanup archive")
    source = tmp_path / "source.txt"
    source.write_text("Synthetic retained source bytes.", encoding="utf-8")
    result = api.ingest(project, source, allow_retention=True)
    api.reindex(project)
    repository = Repository(project)
    snapshot = repository.snapshot()
    version = snapshot.get(Reference(id=result["source_version_id"]), SourceVersion)
    source_entry = next(
        entry for entry in snapshot.manifest.entries if entry.ref.id == result["source_id"]
    )
    paths = {
        "record": repository.record_path(source_entry),
        "blob": project / "research" / "blobs" / version.blob.sha256,
        "cache": project / ".lixity" / "research" / "catalogue.sqlite3",
    }
    return project, source, result, repository, paths


def deny_unlinks(monkeypatch, paths):
    original = Path.unlink

    def unlink(path, *args, **kwargs):
        if path in paths:
            raise PermissionError("Synthetic cleanup access denied")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", unlink)


def test_cleanup_message_is_bounded_while_exact_pending_paths_remain_available(tmp_path):
    paths = [tmp_path / "research" / "blobs" / str(index) for index in range(8)]
    error = ResearchCleanupError("0" * 64, reversed(paths), project_root=tmp_path)
    assert error.pending_paths == tuple(paths)
    message = str(error)
    assert str(tmp_path) not in message
    for index in range(5):
        assert f"research/blobs/{index}" in message
    for index in range(5, 8):
        assert f"research/blobs/{index}" not in message
    assert "8 pending" in message and "3 more" in message


@pytest.mark.parametrize("failure", ["record", "blob", "cache", "all"])
def test_purge_reports_each_pending_artifact_after_acceptance(captured, monkeypatch, failure):
    project, _, source, repository, paths = captured
    blocked = set(paths.values()) if failure == "all" else {paths[failure]}
    before = repository.snapshot().digest
    remaining_bytes = {path: path.read_bytes() for path in blocked}
    deny_unlinks(monkeypatch, blocked)
    with (
        patch("lixity.research.api.Repository", return_value=repository),
        pytest.raises(ResearchStorageError, match=r"committed.*cleanup") as failed,
    ):
        api.purge(project, source["source_id"])
    error = failed.value
    assert error.accepted_snapshot != before
    assert repository._snapshot.digest == error.accepted_snapshot
    assert set(error.pending_paths) == blocked
    assert Repository(project).snapshot().digest == error.accepted_snapshot
    assert {path: path.read_bytes() for path in blocked} == remaining_bytes
    assert api.list_sources(project)["sources"] == []
    assert api.audit(project)["ok"]
    assert "do not repeat" in str(error).lower()
    assert str(project) not in str(error)


def test_cli_purge_exits_nonzero_without_printing_success_for_pending_cleanup(
    captured, monkeypatch
):
    project, _, source, _, paths = captured
    deny_unlinks(monkeypatch, {paths["blob"]})
    status, output, errors = capture_research(
        "purge", "--project", str(project), "--source-id", source["source_id"]
    )
    accepted = Repository(project).snapshot().digest
    assert status == 1 and output == ""
    assert accepted in errors and "committed" in errors and "cleanup" in errors
    assert paths["blob"].is_file()
    assert api.audit(project)["ok"]


def pending_refresh(project, source, source_id, name):
    source.write_text("Synthetic pending refreshed bytes " + name + ".", encoding="utf-8")

    def interrupt(stage, _message):
        if stage == "commit":
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        api.ingest_checkpoint(
            project,
            [source],
            checkpoint=name + ".json",
            source_id=source_id,
            allow_retention=True,
            progress_callback=interrupt,
        )
    checkpoint = project / ".lixity" / "research" / "imports" / (name + ".json")
    objects = checkpoint.with_name(checkpoint.name + ".work") / "objects"
    assert checkpoint.is_file() and list(objects.rglob("*"))
    return checkpoint, objects


@pytest.mark.parametrize(
    "failure", ["blob", "checkpoint-json", "checkpoint-objects", "checkpoint-metadata"]
)
def test_purge_cleans_affected_checkpoints_even_after_accepted_cleanup_failure(
    captured, monkeypatch, failure
):
    project, source_file, source, _, paths = captured
    checkpoint, objects = pending_refresh(project, source_file, source["source_id"], "first")
    other_checkpoint, other_objects = pending_refresh(
        project, source_file, source["source_id"], "second"
    )
    blocked = {paths["blob"]} if failure == "blob" else {checkpoint}
    if failure in ("checkpoint-objects", "checkpoint-metadata"):
        blocked = {next(path for path in objects.rglob("*") if path.is_file())}
    if failure == "checkpoint-metadata":
        original_stat, original_lstat = Path.stat, Path.lstat

        def denied_stat(path, *args, **kwargs):
            if path == objects:
                raise PermissionError("Synthetic checkpoint metadata denied")
            return original_stat(path, *args, **kwargs)

        def denied_lstat(path, *args, **kwargs):
            if path == objects:
                raise PermissionError("Synthetic checkpoint metadata denied")
            return original_lstat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "stat", denied_stat)
        monkeypatch.setattr(Path, "lstat", denied_lstat)
    elif failure == "checkpoint-objects":
        from lixity.research import checkpoints

        original_rmtree = checkpoints.shutil.rmtree

        def denied_objects(path, *args, **kwargs):
            if path == objects:
                raise PermissionError("Synthetic checkpoint object cleanup denied")
            return original_rmtree(path, *args, **kwargs)

        monkeypatch.setattr(checkpoints.shutil, "rmtree", denied_objects)
    else:
        deny_unlinks(monkeypatch, blocked)
    with pytest.raises(ResearchStorageError, match=r"committed.*cleanup") as failed:
        api.purge(project, source["source_id"])
    error = failed.value
    assert error.accepted_snapshot == Repository(project).snapshot().digest
    assert api.audit(project)["ok"]
    assert not other_checkpoint.exists() and not other_objects.exists()
    if failure == "blob":
        assert set(error.pending_paths) == blocked
        assert not checkpoint.exists() and not objects.exists()
    elif failure == "checkpoint-json":
        assert set(error.pending_paths) == {checkpoint}
        assert checkpoint.is_file() and not objects.exists()
    else:
        assert set(error.pending_paths) == {checkpoint, objects}
        assert checkpoint.is_file() and all(path.is_file() for path in blocked)


@pytest.mark.parametrize("failure", ["before-head", "after-head", "head-probe"])
def test_failed_head_publication_reports_known_or_unknown_outcome_without_cleanup(
    captured, monkeypatch, failure
):
    from lixity.research import repository as storage
    from lixity.research.models import Head

    project, source_file, source, repository, _ = captured
    checkpoint, objects = pending_refresh(project, source_file, source["source_id"], "uncertain")
    before = retained_files(project)
    checkpoint_bytes = checkpoint.read_bytes()
    head_path = project / "research" / "HEAD.json"
    old_digest = Head.model_validate_json(before["research/HEAD.json"]).sha256
    real_replace, real_sync, real_read = storage.os.replace, storage.sync_directory, Repository.read
    replaced, sync_failed = False, False

    def replace(staged, destination):
        nonlocal replaced
        if Path(destination) == head_path and failure == "before-head":
            raise OSError("Synthetic failure before HEAD replacement")
        real_replace(staged, destination)
        if Path(destination) == head_path:
            replaced = True

    def sync(directory):
        nonlocal sync_failed
        if replaced and directory == repository.data:
            sync_failed = True
            raise OSError("Synthetic directory durability failure")
        return real_sync(directory)

    def read(instance, path, **kwargs):
        if sync_failed and failure == "head-probe" and path == head_path:
            raise PermissionError("Synthetic unreadable HEAD outcome probe")
        return real_read(instance, path, **kwargs)

    with monkeypatch.context() as faults:
        faults.setattr(storage.os, "replace", replace)
        faults.setattr(storage, "sync_directory", sync)
        faults.setattr(Repository, "read", read)
        with pytest.raises((OSError, ResearchStorageError)) as failed:
            api.purge(project, source["source_id"])

    error = failed.value
    actual = Head.model_validate_json(head_path.read_bytes()).sha256
    if failure == "before-head":
        assert isinstance(error, OSError)
        assert actual == old_digest
    else:
        assert isinstance(error, ResearchStorageError)
        assert error.candidate_snapshot == actual != old_digest
        if failure == "after-head":
            assert error.outcome == "published" and error.published_snapshot == actual
            assert "durability" in str(error).lower()
        else:
            assert error.outcome == "unknown" and error.published_snapshot is None
            assert "unknown" in str(error).lower()
        assert "review" in str(error).lower() and "retry" in str(error).lower()
    assert checkpoint.read_bytes() == checkpoint_bytes
    assert list(objects.rglob("*"))
    # Existing accepted files remain recovery material when publication failed.
    for name, content in before.items():
        if name != "research/HEAD.json":
            assert (project / name).read_bytes() == content
    assert api.audit(project)["ok"]
