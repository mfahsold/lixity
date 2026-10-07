"""Synthetic coverage for sequential capture checkpoints and stable PDF bytes."""

import contextlib
import hashlib
import io
import json
from unittest.mock import patch

import pytest
from test_research_ocr import make_synthetic_pdf

from lixity.cli import main
from lixity.research import api
from lixity.research.models import Blob, Extraction, Passage, SourceVersion
from lixity.research.ocr import OCRBlock, OCRExtractionResult
from lixity.research.repository import Repository, ResearchConflictError, ResearchError


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "project"
    api.init(root, title="Synthetic checkpoint project")
    return root


def pdf(tmp_path, name="source.pdf"):
    path = tmp_path / name
    path.write_bytes(make_synthetic_pdf("Synthetic reading room record."))
    return path


def extracted():
    text = "Synthetic reading room record."
    return OCRExtractionResult(pages=[], full_text=text, blocks=[OCRBlock(page_number=1, text=text)],
                               spans=[(0, len(text))], warnings=["Synthetic extraction warning."])


def capture(project, files=None, **kwargs):
    return api.ingest_checkpoint(project, files, checkpoint="library.json", allow_retention=True, **kwargs)


def checkpoint_path(project):
    return project / ".lixity" / "research" / "imports" / "library.json"


def test_resume_skips_accepted_file_after_interrupt(project, tmp_path):
    first, second = pdf(tmp_path, "first.pdf"), pdf(tmp_path, "second.pdf")
    reads = 0

    def interrupt(stage, message):
        nonlocal reads
        if stage == "read":
            reads += 1
            if reads == 2:
                raise KeyboardInterrupt

    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [first, second], progress_callback=interrupt)
    assert len(api.list_sources(project)["sources"]) == 1
    initial_id = api.list_sources(project)["sources"][0]["id"]
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()) as boundary:
        result = capture(project, resume=True)
    assert result["schema_version"] == "research-checkpoint-ingest-local/1"
    assert result["complete"] and result["succeeded"] == 2
    assert len(api.list_sources(project)["sources"]) == 2
    assert result["items"][0]["source_id"] == initial_id
    assert boundary.call_count == 1
    assert api.audit(project)["ok"]


def test_post_extraction_conflict_reuses_only_after_explicit_head_acknowledgement(project, tmp_path):
    source = pdf(tmp_path)

    def racing_extraction(path, **kwargs):
        api.create_dossier(project, title="Concurrent authored edit", body="Synthetic preserved decision context.")
        return extracted()

    with patch("lixity.research.api.extract_pdf_document", side_effect=racing_extraction):
        result = capture(project, [source])
    assert result["failed"] == 1 and not result["complete"]
    assert api.list_sources(project)["sources"] == []
    with patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("retained extraction must be reused")):
        with pytest.raises(ResearchConflictError, match=r"snapshot"):
            capture(project, resume=True)
        head = Repository(project).snapshot().digest
        resumed = capture(project, resume=True, expected_snapshot=head)
    assert resumed["complete"]
    assert resumed["items"][0]["warnings"] == ["Synthetic extraction warning."]
    assert len(api.list_dossiers(project)["dossiers"]) == 1
    assert api.audit(project)["ok"]


def test_lost_receipt_recovers_accepted_capture_without_duplicate(project, tmp_path):
    source = pdf(tmp_path)

    def interrupt(stage, message):
        if stage == "complete":
            raise KeyboardInterrupt

    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [source], progress_callback=interrupt)
    with patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("already accepted")):
        result = capture(project, resume=True)
    assert result["complete"] and len(api.list_sources(project)["sources"]) == 1
    assert api.audit(project)["ok"]


def test_stale_head_before_extraction_does_not_create_checkpoint(project, tmp_path):
    source = pdf(tmp_path)
    old = Repository(project).snapshot().digest
    api.create_dossier(project, title="Later authored edit", body="Synthetic preserved text.")
    with (
        patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("stale request")),
        pytest.raises(ResearchConflictError, match=r"snapshot"),
    ):
        capture(project, [source], expected_snapshot=old)
    assert not checkpoint_path(project).exists()


@pytest.mark.parametrize("change", ["bytes", "metadata", "configuration", "adapter", "pins", "order", "missing"])
def test_changed_input_or_configuration_refuses_resume(project, tmp_path, monkeypatch, change):
    first, second = pdf(tmp_path, "first.pdf"), pdf(tmp_path, "second.pdf")

    def interrupt(stage, message):
        if stage == "commit":
            raise KeyboardInterrupt

    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [first, second], progress_callback=interrupt)
    kwargs = {}
    files = None
    if change == "bytes":
        first.write_bytes(make_synthetic_pdf("Changed synthetic record."))
    elif change == "metadata":
        kwargs["context"] = {"tags": ["changed"]}
    elif change == "configuration":
        monkeypatch.setenv("LIXITY_OCR_TIMEOUT", "19")
    elif change == "adapter":
        monkeypatch.setenv("LIXITY_UNLIMITED_OCR_HOME", "/synthetic-changed-model-home")
    elif change == "pins":
        monkeypatch.setattr("lixity.research.ocr.MODEL_SNAPSHOT", "synthetic-changed-model-snapshot")
    elif change == "order":
        files = [second, first]
    else:
        first.unlink()
    with (
        patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("invalid reuse")),
        pytest.raises((ResearchError, OSError), match=r"changed|missing|file|configuration|order"),
    ):
        capture(project, files, resume=True, **kwargs)
    assert api.list_sources(project)["sources"] == []


def test_refresh_version_change_cannot_be_acknowledged_away(project, tmp_path):
    source = pdf(tmp_path)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        original = api.ingest(project, source, allow_retention=True)
    source.write_bytes(make_synthetic_pdf("Second synthetic record."))

    def interrupt(stage, message):
        if stage == "commit":
            raise KeyboardInterrupt

    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        with pytest.raises(KeyboardInterrupt):
            capture(project, [source], source_id=original["source_id"], progress_callback=interrupt)
        api.ingest(project, source, source_id=original["source_id"], context={"tags": ["concurrent"]},
                   allow_retention=True)
    head = Repository(project).snapshot().digest
    with pytest.raises(ResearchConflictError, match=r"Source|source"):
        capture(project, resume=True, expected_snapshot=head)


def test_retention_and_dry_run_never_create_checkpoint(project, tmp_path):
    source = pdf(tmp_path)
    with pytest.raises(ResearchError, match=r"retention"):
        api.ingest_checkpoint(project, [source], checkpoint="library.json")
    with pytest.raises(ResearchError, match=r"dry.run"):
        capture(project, [source], dry_run=True)
    assert not checkpoint_path(project).exists()


@pytest.mark.parametrize("location", ["outside", "archive", "symlink"])
def test_checkpoint_path_is_confined_and_rejects_symlinks(project, tmp_path, location):
    source = pdf(tmp_path)
    if location == "outside":
        checkpoint = tmp_path / "outside.json"
    elif location == "archive":
        checkpoint = project / "research" / "checkpoint.json"
    else:
        directory = project / ".lixity" / "research" / "imports"
        directory.mkdir(parents=True)
        checkpoint = directory / "linked.json"
        checkpoint.symlink_to(tmp_path / "outside.json")
    with pytest.raises(ResearchError, match=r"checkpoint|Checkpoint|Symlinks"):
        api.ingest_checkpoint(project, [source], checkpoint=checkpoint, allow_retention=True)
    assert not (tmp_path / "outside.json").exists()


def test_corrupt_prepared_blob_refuses_reuse(project, tmp_path):
    source = pdf(tmp_path)

    def interrupt(stage, message):
        if stage == "commit":
            raise KeyboardInterrupt

    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [source], progress_callback=interrupt)
    staged = list(checkpoint_path(project).parent.rglob("objects/*/*"))
    assert staged
    staged[0].write_bytes(b"Corrupted synthetic content")
    with pytest.raises(ResearchError, match=r"checksum|digest|blob"):
        capture(project, resume=True)
    assert api.list_sources(project)["sources"] == []


def test_discard_removes_retained_preparation_without_touching_archive(project, tmp_path):
    source = pdf(tmp_path)

    def interrupt(stage, message):
        if stage == "commit":
            raise KeyboardInterrupt

    before = Repository(project).snapshot().digest
    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [source], progress_callback=interrupt)
    result = api.discard_ingest_checkpoint(project, checkpoint="library.json")
    assert result["schema_version"] == "research-checkpoint-discard-local/1"
    assert not checkpoint_path(project).exists()
    assert not list(checkpoint_path(project).parent.rglob("objects/*/*"))
    assert Repository(project).snapshot().digest == before


def test_purge_invalidates_pending_refresh_checkpoint(project, tmp_path):
    source = pdf(tmp_path)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        original = api.ingest(project, source, allow_retention=True)
    source.write_bytes(make_synthetic_pdf("Changed synthetic bytes."))

    def interrupt(stage, message):
        if stage == "commit":
            raise KeyboardInterrupt

    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [source], source_id=original["source_id"], progress_callback=interrupt)
    api.purge(project, original["source_id"])
    assert not checkpoint_path(project).exists()
    assert not list(checkpoint_path(project).parent.rglob("objects/*/*"))
    with pytest.raises(ResearchError, match=r"missing|exist"):
        capture(project, resume=True)


def test_pdf_extraction_uses_the_exact_retained_input_bytes(project, tmp_path):
    source = pdf(tmp_path)
    original = source.read_bytes()

    def changing_extraction(path, **kwargs):
        source.write_bytes(make_synthetic_pdf("Replacement synthetic record."))
        assert path.read_bytes() == original
        return extracted()

    with patch("lixity.research.api.extract_pdf_document", side_effect=changing_extraction):
        result = api.ingest(project, source, allow_retention=True)
    repository = Repository(project)
    snapshot = repository.snapshot()
    version = snapshot.records[result["source_version_id"]]
    assert isinstance(version, SourceVersion)
    assert repository.read_blob(version.blob) == original
    extraction = next(item for item in snapshot.records.values() if isinstance(item, Extraction))
    assert repository.read_blob(extraction.text_blob).decode("utf-8") == extracted().full_text
    assert any(isinstance(item, Passage) for item in snapshot.records.values())


def test_checkpoint_cli_preserves_json_and_explicit_progress(project, tmp_path):
    source = pdf(tmp_path)
    output, errors = io.StringIO(), io.StringIO()
    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors),
    ):
        status = main(["research", "ingest", "--project", str(project), "--file", str(source),
                       "--checkpoint", "library.json", "--allow-retention", "--progress"])
    assert status == 0
    assert json.loads(output.getvalue())["complete"]
    assert "[checkpoint]" in errors.getvalue()
    assert "[read]" in errors.getvalue() and "[complete]" in errors.getvalue()
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        assert main(["research", "ingest", "--project", str(project), "--checkpoint", "library.json",
                     "--resume", "--allow-retention"]) == 0
    assert json.loads(output.getvalue())["succeeded"] == 1


def test_resume_requires_retention_permission_again(project, tmp_path):
    source = pdf(tmp_path)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        capture(project, [source])
    before = checkpoint_path(project).read_bytes()
    with pytest.raises(ResearchError, match=r"retention"):
        api.ingest_checkpoint(project, checkpoint="library.json", resume=True)
    assert checkpoint_path(project).read_bytes() == before


def test_running_checkpoint_refuses_duplicate_runner_and_discard(project, tmp_path):
    source = pdf(tmp_path)

    def interrupt(stage, message):
        if stage == "read":
            with pytest.raises(ResearchError, match=r"busy"):
                capture(project, resume=True)
            with pytest.raises(ResearchError, match=r"busy"):
                api.discard_ingest_checkpoint(project, checkpoint="library.json")
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        capture(project, [source], progress_callback=interrupt)
    assert checkpoint_path(project).exists()
    assert api.list_sources(project)["sources"] == []


def test_running_refresh_prevents_purge_until_checkpoint_unlocks(project, tmp_path):
    source = pdf(tmp_path)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        original = api.ingest(project, source, allow_retention=True)
    source.write_bytes(make_synthetic_pdf("Changed synthetic bytes."))
    before = Repository(project).snapshot().digest

    def interrupt(stage, message):
        if stage == "read":
            with pytest.raises(ResearchError, match=r"busy"):
                api.purge(project, original["source_id"])
            assert Repository(project).snapshot().digest == before
            raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        capture(project, [source], source_id=original["source_id"], progress_callback=interrupt)
    api.purge(project, original["source_id"])
    assert not checkpoint_path(project).exists()


def test_corrupt_spans_refuse_checkpoint_reuse(project, tmp_path):
    source = pdf(tmp_path)

    def interrupt(stage, message):
        if stage == "commit":
            raise KeyboardInterrupt

    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [source], progress_callback=interrupt)
    state = json.loads(checkpoint_path(project).read_text())
    passage = next(record for record in state["items"][0]["prepared"]["records"] if record["kind"] == "passage")
    passage["verbatim"] = "X" * len(passage["verbatim"])
    checkpoint_path(project).write_text(json.dumps(state))
    with pytest.raises(ResearchError, match=r"spans"):
        capture(project, resume=True)
    assert api.list_sources(project)["sources"] == []


def test_lost_receipt_plus_later_authored_change_still_requires_acknowledgement(project, tmp_path):
    first, second = pdf(tmp_path, "first.pdf"), pdf(tmp_path, "second.pdf")

    def interrupt(stage, message):
        if stage == "complete":
            api.create_dossier(project, title="Later authored edit", body="Synthetic authored content.")
            raise KeyboardInterrupt

    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [first, second], progress_callback=interrupt)
    with pytest.raises(ResearchConflictError, match=r"snapshot"):
        capture(project, resume=True)
    assert len(api.list_sources(project)["sources"]) == 1
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()) as boundary:
        resumed = capture(project, resume=True, expected_snapshot=Repository(project).snapshot().digest)
    assert resumed["complete"] and len(api.list_sources(project)["sources"]) == 2
    assert boundary.call_count == 1
    assert len(api.list_dossiers(project)["dossiers"]) == 1


def test_completed_checkpoint_removes_source_and_extraction_payloads(project, tmp_path):
    source = pdf(tmp_path)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        capture(project, [source])
    assert not list(checkpoint_path(project).parent.rglob("objects/*/*"))
    assert extracted().full_text not in checkpoint_path(project).read_text()
    assert api.audit(project)["ok"]


def test_checkpoint_from_another_project_is_rejected(project, tmp_path):
    source = pdf(tmp_path)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        capture(project, [source])
    other = tmp_path / "another-project"
    api.init(other, title="Another synthetic project")
    destination = checkpoint_path(other)
    destination.parent.mkdir(parents=True)
    destination.write_bytes(checkpoint_path(project).read_bytes())
    with pytest.raises(ResearchError, match=r"another project"):
        capture(other, resume=True)


def test_file_failure_preserves_later_success_and_can_retry_sequentially(project, tmp_path):
    first, second = pdf(tmp_path, "first.pdf"), pdf(tmp_path, "second.pdf")
    first.write_bytes(make_synthetic_pdf("First synthetic record."))
    failing_bytes = first.read_bytes()

    def first_fails(path, **kwargs):
        if path.read_bytes() == failing_bytes:
            raise ResearchError("Synthetic OCR failure")
        return extracted()

    with patch("lixity.research.api.extract_pdf_document", side_effect=first_fails):
        result = capture(project, [first, second])
    assert (result["succeeded"], result["failed"], result["pending"]) == (1, 1, 0)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()) as boundary:
        resumed = capture(project, resume=True)
    assert resumed["complete"] and len(api.list_sources(project)["sources"]) == 2
    assert boundary.call_count == 1


def test_registration_cannot_race_with_purge(project, tmp_path):
    source = pdf(tmp_path)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        original = api.ingest(project, source, allow_retention=True)
    registry = Repository(project)
    registry.cache = project / ".lixity" / "research" / "imports" / ".registry"
    with registry.locked(), pytest.raises(ResearchError, match=r"busy"):
        capture(project, [source], source_id=original["source_id"])
    assert not checkpoint_path(project).exists()


def test_cleanup_failure_preserves_accepted_refresh_receipt(project, tmp_path):
    source = pdf(tmp_path)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        original = api.ingest(project, source, allow_retention=True)
    source.write_bytes(make_synthetic_pdf("Changed synthetic record."))
    outside = tmp_path / "outside.txt"
    outside.write_text("Unrelated synthetic content.")
    injected = None

    def cleanup_failure(stage, message):
        nonlocal injected
        if stage == "complete":
            directory = next(checkpoint_path(project).parent.rglob("objects/0"))
            injected = directory / "untrusted-link"
            injected.symlink_to(outside)

    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        result = capture(project, [source], source_id=original["source_id"], progress_callback=cleanup_failure)
    assert outside.read_text() == "Unrelated synthetic content."
    assert injected is not None
    injected.unlink()
    assert result["complete"] and result["succeeded"] == 1
    assert any("accepted" in warning for warning in result["items"][0]["warnings"])
    with patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("already accepted")):
        resumed = capture(project, resume=True)
    assert resumed["complete"]
    assert not list(checkpoint_path(project).parent.rglob("objects/*/*"))
    assert api.audit(project)["ok"]


def test_oversized_checkpoint_publication_preserves_previous_readable_state(project, tmp_path, monkeypatch):
    source = pdf(tmp_path)
    monkeypatch.setattr("lixity.research.checkpoints.MAX_CHECKPOINT_BYTES", 4096, raising=False)
    text = "Synthetic quoted record. " * 400
    large = OCRExtractionResult(pages=[], full_text=text, blocks=[OCRBlock(page_number=1, text=text)],
                                spans=[(0, len(text))])
    with (
        patch("lixity.research.api.extract_pdf_document", return_value=large),
        pytest.raises(ResearchError, match=r"checkpoint.*size"),
    ):
        capture(project, [source])
    assert len(checkpoint_path(project).read_bytes()) < 4096
    assert api.list_sources(project)["sources"] == []
    monkeypatch.setattr("lixity.research.checkpoints.MAX_CHECKPOINT_BYTES", 64 * 1024 * 1024)
    with patch("lixity.research.api.extract_pdf_document", return_value=large):
        assert capture(project, resume=True)["complete"]
    assert api.audit(project)["ok"]


def test_relative_adapter_home_change_refuses_reuse(project, tmp_path, monkeypatch):
    source = pdf(tmp_path)
    first, second = tmp_path / "first", tmp_path / "second"
    (first / "models").mkdir(parents=True)
    (second / "models").mkdir(parents=True)
    monkeypatch.setenv("LIXITY_UNLIMITED_OCR_HOME", "models")
    monkeypatch.chdir(first)

    def interrupt(stage, message):
        if stage == "commit":
            raise KeyboardInterrupt

    with (
        patch("lixity.research.api.extract_pdf_document", return_value=extracted()),
        pytest.raises(KeyboardInterrupt),
    ):
        capture(project, [source], progress_callback=interrupt)
    monkeypatch.chdir(second)
    with pytest.raises(ResearchError, match=r"configuration"):
        capture(project, resume=True)
    assert api.list_sources(project)["sources"] == []


def test_documented_large_pdf_bound_is_retained_and_auditable(project, tmp_path):
    source = pdf(tmp_path)
    base = source.read_bytes()
    source_bytes = base + b"\n%" + b"0" * (33 * 1024 * 1024 - len(base) - 2)
    source.write_bytes(source_bytes)
    with patch("lixity.research.api.extract_pdf_document", return_value=extracted()):
        capture = api.ingest(project, source, allow_retention=True)
    repository = Repository(project)
    version = repository.snapshot().records[capture["source_version_id"]]
    assert version.blob.byte_length == 33 * 1024 * 1024
    assert version.blob.sha256 == hashlib.sha256(source_bytes).hexdigest()
    assert len(repository.read_blob(version.blob)) == 33 * 1024 * 1024
    assert api.audit(project)["ok"]
    guarded = repository.data / "synthetic-large-object.json"
    guarded.write_bytes(source_bytes)
    with pytest.raises(ResearchError, match=r"supported size"):
        repository.read(guarded)


@pytest.mark.parametrize("length", [-1, 10**12, True])
def test_untrusted_blob_length_is_rejected_before_reading(project, length):
    descriptor = Blob.model_construct(sha256="0" * 64, byte_length=length, media_type="application/pdf")
    with pytest.raises(ResearchError, match=r"blob length"):
        Repository(project).read_blob(descriptor)
