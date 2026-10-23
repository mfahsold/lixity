"""Verified reads retain strict boundaries without repeated filesystem work."""

import io
import os.path
import tracemalloc
from collections import Counter
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import ValidationError

from lixity.research import api
from lixity.research.limits import MAX_RESEARCH_OBJECT_BYTES
from lixity.research.models import Passage, Project, Reference, Tombstone
from lixity.research.repository import Repository, ResearchStorageError, Snapshot, digest

pytestmark = pytest.mark.portability


@pytest.fixture
def archive(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic archive", language="en")
    api.create_dossier(project, "Synthetic dossier", "Synthetic body.", language="en")
    return project


def test_snapshot_checks_each_revision_path_once(archive, monkeypatch):
    """A verified revision read needs one complete containment walk."""
    checks = Counter()
    original = os.path.islink

    def islink(path):
        checks[os.fspath(path)] += 1
        return original(path)

    monkeypatch.setattr(os.path, "islink", islink)
    repository = Repository(archive)
    snapshot = repository.snapshot()

    assert snapshot.project.title == "Synthetic archive"
    assert len(snapshot.revisions) == 2
    # Each revision path has five internal components; HEAD, compressed manifest,
    # layout marker and project.json contribute nine more checks in this archive.
    assert sum(checks.values()) <= 19
    for entry in snapshot.manifest.entries:
        assert checks[os.fspath(repository._record_path(entry))] == 1


def test_small_object_read_avoids_requesting_the_entire_byte_ceiling(archive, monkeypatch):
    path = archive / "synthetic.bin"
    path.write_bytes(b"synthetic")
    requested = []
    original = Path.open

    class RecordingStream:
        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def read(self, size):
            requested.append(size)
            return self.stream.read(size)

    def open_stream(path, *args, **kwargs):
        return RecordingStream(original(path, *args, **kwargs))

    monkeypatch.setattr(Path, "open", open_stream)

    assert Repository(archive).read(path) == b"synthetic"
    assert requested and max(requested) <= 8192


def test_large_seekable_object_read_keeps_one_payload_allocation(archive):
    if tracemalloc.is_tracing():
        pytest.skip("Allocation budget requires an isolated tracemalloc session")
    maximum = 2 * 1024 * 1024
    path = archive / "synthetic.bin"
    path.write_bytes(b"x" * maximum)
    repository = Repository(archive)

    tracemalloc.start()
    try:
        content = repository.read(path, maximum=maximum)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    assert len(content) == maximum
    assert peak <= maximum + 256 * 1024


def test_default_object_ceiling_rejects_a_final_extra_byte(archive):
    path = archive / "synthetic.bin"
    with path.open("wb") as stream:
        stream.truncate(MAX_RESEARCH_OBJECT_BYTES + 1)

    with pytest.raises(ResearchStorageError, match="exceeds the supported size"):
        Repository(archive).read(path)


@pytest.mark.parametrize("change", ["grow", "tamper"])
def test_large_seekable_read_still_checks_growth_and_content(archive, monkeypatch, change):
    maximum = 32768
    content = b"x" * maximum
    path = archive / "synthetic.bin"
    path.write_bytes(content)
    original = Path.open

    class ChangingStream:
        changed = False

        def __init__(self, stream):
            self.stream = stream

        def __enter__(self):
            self.stream.__enter__()
            return self

        def __exit__(self, *args):
            return self.stream.__exit__(*args)

        def seekable(self):
            return self.stream.seekable()

        def seek(self, *args):
            return self.stream.seek(*args)

        def read(self, size):
            data = self.stream.read(size)
            if not self.changed:
                self.changed = True
                with original(path, "r+b") as writer:
                    if change == "grow":
                        writer.seek(0, 2)
                    else:
                        writer.seek(maximum - 1)
                    writer.write(b"y")
            return data

    def open_stream(selected, *args, **kwargs):
        if selected == path:
            # Keep the changed tail outside the initial buffer on every platform.
            return ChangingStream(original(selected, *args, buffering=1024, **kwargs))
        return original(selected, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_stream)
    error = "exceeds the supported size" if change == "grow" else "checksum mismatch"
    with pytest.raises(ResearchStorageError, match=error):
        Repository(archive).verified(path, digest(content), maximum=maximum)


@pytest.mark.parametrize("maximum", [0, 1, 8191, 8192, 8193, 65536])
@pytest.mark.parametrize("difference", [-1, 0, 1])
def test_object_reads_preserve_exact_byte_ceiling(archive, maximum, difference):
    content = b"x" * max(0, maximum + difference)
    path = archive / "synthetic.bin"
    path.write_bytes(content)
    repository = Repository(archive)

    if len(content) > maximum:
        with pytest.raises(ResearchStorageError, match="exceeds the supported size"):
            repository.read(path, maximum=maximum)
    else:
        assert repository.read(path, maximum=maximum) == content


@pytest.mark.parametrize(("maximum", "length"), [
    (0, 0), (0, 1), (100, 20), (8192, 8192), (8192, 8193), (65536, 20000),
])
def test_object_reads_preserve_buffered_short_raw_read_behavior(archive, monkeypatch, maximum, length):
    content = b"x" * length
    path = archive / "synthetic.bin"
    path.write_bytes(content)
    original = Path.open

    class ShortRaw(io.RawIOBase):
        def __init__(self):
            self.source = io.BytesIO(content)

        def readable(self):
            return True

        def readinto(self, target):
            data = self.source.read(min(3, len(target)))
            target[:len(data)] = data
            return len(data)

    def open_stream(selected, *args, **kwargs):
        if selected == path:
            return io.BufferedReader(ShortRaw())
        return original(selected, *args, **kwargs)

    monkeypatch.setattr(Path, "open", open_stream)
    repository = Repository(archive)
    if length > maximum:
        with pytest.raises(ResearchStorageError, match="exceeds the supported size"):
            repository.read(path, maximum=maximum)
    else:
        assert repository.read(path, maximum=maximum) == content


@pytest.mark.parametrize("depth", [1, 2, 3, 4, 5])
def test_verified_revision_read_rejects_each_symlinked_component(archive, depth):
    repository = Repository(archive)
    snapshot = repository.snapshot()
    entry = next(entry for entry in snapshot.manifest.entries if entry.kind == "dossier")
    path = repository.record_path(entry)
    relative = path.relative_to(archive)
    selected = archive.joinpath(*relative.parts[:depth])
    retained = archive.parent / "retained"
    selected.rename(retained)
    try:
        selected.symlink_to(retained, target_is_directory=retained.is_dir())
    except (OSError, NotImplementedError) as exc:
        pytest.skip(f"Symlinks unavailable: {exc}")

    with pytest.raises(ResearchStorageError, match="Symlinks"):
        repository.record_path(entry)
    with pytest.raises(ResearchStorageError, match="Symlinks"):
        Repository(archive).snapshot()


class _CountingRecords(dict):
    scans = 0

    def values(self):
        self.scans += 1
        return super().values()


def test_citation_uses_snapshot_lifecycle_without_rescanning_records(archive):
    source = archive.parent / "source.txt"
    source.write_text("Synthetic retained source.", encoding="utf-8")
    api.ingest(archive, source, allow_retention=True)
    repository = Repository(archive)
    original = repository.snapshot()
    passage = next(record for record in original.records.values() if isinstance(record, Passage))
    records = _CountingRecords(original.records)
    snapshot = Snapshot(original.digest, original.manifest, records, revisions=original.revisions)
    records.scans = 0

    citation = repository.citation(snapshot, passage)

    assert citation["verbatim"] == "Synthetic retained source."
    assert citation["availability"] == "available"
    assert records.scans == 0


@pytest.mark.parametrize("operation", ["withdraw", "purge"])
@pytest.mark.parametrize("target", ["source", "source_version"])
def test_citation_lifecycle_retains_target_identity_semantics(archive, operation, target):
    source = archive.parent / "source.txt"
    source.write_text("Synthetic retained source.", encoding="utf-8")
    captured = api.ingest(archive, source, allow_retention=True)
    repository = Repository(archive)
    snapshot = repository.snapshot()
    passage = next(record for record in snapshot.records.values() if isinstance(record, Passage))
    tombstone = Tombstone(id=f"urn:uuid:{uuid4()}", project_id=snapshot.project.id,
                          created_at="2024-01-01T00:00:00.000000Z", created_by="synthetic-author",
                          # Accepted tombstones historically match these citation
                          # identities independently of target kind or revision.
                          target_ref=Reference(id=captured[f"{target}_id"], revision=2),
                          target_kind="claim", operation=operation, reason="Synthetic lifecycle")
    accepted = repository.commit([tombstone], {}, snapshot)

    assert repository.citation(accepted, passage)["availability"] == "withdrawn"


@pytest.mark.parametrize("created_at", [
    "0001-01-01T00:00:00.000000Z",
    "2000-02-29T23:59:59.999999Z",
    "2024-02-29T12:34:56.123456Z",
    "9999-12-31T23:59:59.999999Z",
    "٢024-02-29T12:34:56.123456Z",
    "2024-02-2٩T12:34:56.123456Z",
])
def test_record_timestamp_preserves_valid_utc_calendar_values(created_at):
    identifier = f"urn:uuid:{uuid4()}"
    project = Project(id=identifier, project_id=identifier, created_at=created_at,
                      created_by="synthetic-author", title="Synthetic project")
    assert project.created_at == created_at


@pytest.mark.parametrize("created_at", [
    "0000-01-01T00:00:00.000000Z",
    "1900-02-29T00:00:00.000000Z",
    "2023-02-29T00:00:00.000000Z",
    "2024-04-31T00:00:00.000000Z",
    "2024-00-01T00:00:00.000000Z",
    "2024-13-01T00:00:00.000000Z",
    "2024-01-00T00:00:00.000000Z",
    "2024-01-01T24:00:00.000000Z",
    "2024-01-01T00:60:00.000000Z",
    "2024-01-01T00:00:60.000000Z",
    "2024-01-01 00:00:00.000000Z",
    "2024-01-01T00:00:00.00000Z",
    "2024-01-01T00:00:00.0000000Z",
    "2024-01-01T00:00:00.000000+00:00",
    "2024-01-01T00:00:00.000000z",
    "2024-01-01T00:00:00.000000Z\n",
])
def test_record_timestamp_rejects_invalid_calendar_or_syntax(created_at):
    identifier = f"urn:uuid:{uuid4()}"
    with pytest.raises(ValidationError):
        Project(id=identifier, project_id=identifier, created_at=created_at,
                created_by="synthetic-author", title="Synthetic project")
