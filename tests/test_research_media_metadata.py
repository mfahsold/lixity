"""Metadata corrections retain media bytes and exact historical attachment pins."""

import json
from uuid import uuid4

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.research.media_metadata import update_dossier_media_context
from lixity.research.models import Extraction, Source, SourceVersion
from lixity.research.repository import Repository, ResearchConflictError, ResearchError
from tests.research_support import retained_files
from tests.test_research_images import png
from tests.test_research_media import mp4
from tests.test_research_ocr import make_synthetic_pdf


@pytest.fixture
def attachment(tmp_path):
    api.init(tmp_path, title="Synthetic metadata")
    capture = api.ingest_image(tmp_path, png(), filename="sample.png", allow_retention=True,
        context={"provenance_note": "Original note", "place": "Synthetic place"})
    marker = f'![Original \\[alt\\]](lixity:image/{capture["source_id"]}/{capture["source_version_id"]})'
    body = f"Before.\r\n\r\n{marker}\r\n\r\nCaption remains.\r\n\r\n~~~\r\n{marker}\r\n~~~\r\n\r\nAfter."
    dossier = api.create_dossier(tmp_path, "Notes", body)["dossier_id"]
    return tmp_path, dossier, capture, body, marker


def correct(project, dossier, capture, **overrides):
    loaded = api.get_record(project, "dossier", dossier)
    values = {"expected_snapshot": loaded["snapshot"], "expected_revision": loaded["record"]["revision"],
              "context": {"origin_url": "https://example.org/source", "provenance_note": "Reviewed attribution; rights unverified."},
              "reason": "Correct source attribution."}
    values.update(overrides)
    return update_dossier_media_context(project, dossier, capture["source_id"], capture["source_version_id"], **values)


def test_correction_preserves_source_blob_history_and_exact_outside_bytes(attachment):
    project, dossier, capture, body, marker = attachment
    before = Repository(project).snapshot()
    files = retained_files(project)
    result = correct(project, dossier, capture)
    after = Repository(project).snapshot()
    old = before.records[capture["source_version_id"]]
    new = after.records[result["source_version_id"]]
    assert result["schema_version"] == "research-media-context-local/1"
    assert result["changed"] and not result["dry_run"] and result["references_updated"] == 1
    assert new.source_ref == old.source_ref and new.blob == old.blob and new.sequence == old.sequence + 1
    assert new.context.place == "Synthetic place"
    assert old.context.provenance_note == "Original note"
    assert after.records[old.id] == old
    assert sum(isinstance(r, Source) for r in after.records.values()) == 1
    assert sum(isinstance(r, SourceVersion) for r in after.records.values()) == 2
    new_body = api.get_record(project, "dossier", dossier)["record"]["body"]
    assert new_body == body.replace(marker, marker.replace(old.id, new.id), 1)
    assert api.get_record(project, "dossier", dossier, revision=1)["record"]["body"] == body
    assert {p: b for p, b in retained_files(project).items() if "/blobs/" in p} == {
        p: b for p, b in files.items() if "/blobs/" in p}
    assert api.audit(project)["ok"]


def test_repeat_is_noop_and_second_dossier_reuses_corrected_version(attachment):
    project, dossier, capture, body, _ = attachment
    second = api.create_dossier(project, "Second", body)["dossier_id"]
    result = correct(project, dossier, capture)
    current = {**capture, "source_version_id": result["source_version_id"]}
    files = retained_files(project)
    repeated = correct(project, dossier, current)
    assert not repeated["changed"] and repeated["references_updated"] == 0
    assert retained_files(project) == files
    second_result = correct(project, second, capture)
    assert second_result["source_version_id"] == result["source_version_id"]
    assert second_result["references_updated"] == 1
    assert sum(isinstance(r, SourceVersion) for r in Repository(project).snapshot().records.values()) == 2


def test_preview_and_clears_preserve_other_metadata(attachment):
    project, dossier, capture, _, _ = attachment
    files = retained_files(project)
    result = correct(project, dossier, capture, dry_run=True,
                     context={"origin_url": None, "provenance_note": None})
    assert result["schema_version"] == "research-media-context-preview-local/1"
    assert result["changed"] and result["dry_run"]
    assert set(result["context_after"]) <= {"origin_url", "provenance_note"}
    assert result["context_after"]["provenance_note"] is None
    assert retained_files(project) == files


@pytest.mark.parametrize("overrides", [
    {"expected_snapshot": "0" * 64}, {"expected_revision": 99},
    {"context": {"license": "Public domain"}}, {"context": {"place": "Changed"}},
    {"context": {"origin_url": "javascript:alert(1)"}}, {"reason": " "},
    {"context": {"provenance_note": ""}}, {"expected_revision": True},
])
def test_invalid_or_stale_operation_writes_nothing(attachment, overrides):
    project, dossier, capture, _, _ = attachment
    files = retained_files(project)
    with pytest.raises((ResearchError, ResearchConflictError)):
        correct(project, dossier, capture, **overrides)
    assert retained_files(project) == files


@pytest.mark.parametrize("target", ["source", "version", "dossier", "foreign"])
def test_unavailable_or_foreign_target_is_rejected(attachment, target):
    project, dossier, capture, _, _ = attachment
    if target == "source":
        api.withdraw(project, capture["source_id"])
    elif target == "version":
        api.withdraw(project, capture["source_id"], version_id=capture["source_version_id"])
    elif target == "dossier":
        api.withdraw(project, dossier_id=dossier, expected_revision=1,
                     expected_snapshot=Repository(project).snapshot().digest, reason="Synthetic withdrawal")
    else:
        capture = {**capture, "source_id": uuid4().urn}
    files = retained_files(project)
    with pytest.raises(ResearchError):
        correct(project, dossier, capture)
    assert retained_files(project) == files


def test_newer_bytes_are_not_silently_replaced(attachment):
    project, dossier, capture, _, _ = attachment
    api.ingest_image(project, png(width=2), filename="changed.png", allow_retention=True,
                     source_id=capture["source_id"])
    files = retained_files(project)
    with pytest.raises(ResearchError, match="bytes"):
        correct(project, dossier, capture)
    assert retained_files(project) == files


def test_patch_uses_selected_context_and_counts_only_active_matching_pins(attachment):
    project, dossier, capture, body, marker = attachment
    latest = api.ingest_image(project, png(), filename="sample.png", allow_retention=True,
        source_id=capture["source_id"], context={"place": "Other context", "provenance_note": "Latest note"})
    second = api.create_dossier(project, "Repeated pins", body + "\n\n" + marker + "\n\n`" + marker + "`")["dossier_id"]
    result = correct(project, second, capture)
    snapshot = Repository(project).snapshot()
    version = snapshot.records[result["source_version_id"]]
    assert version.id != latest["source_version_id"] and version.sequence == 3
    assert version.context.place == "Synthetic place"
    assert result["references_updated"] == 2
    assert api.get_record(project, "dossier", second)["record"]["body"].count(result["source_version_id"]) == 2
    assert api.get_record(project, "dossier", second)["record"]["body"].count(capture["source_version_id"]) == 2
    assert api.get_record(project, "dossier", dossier)["record"]["body"] == body


def test_missing_active_pin_is_rejected(attachment):
    project, _, capture, _, marker = attachment
    dossier = api.create_dossier(project, "Literal only", "~~~\n" + marker + "\n~~~")["dossier_id"]
    files = retained_files(project)
    with pytest.raises(ResearchError, match="no active"):
        correct(project, dossier, capture)
    assert retained_files(project) == files


@pytest.mark.parametrize("filename,content", [("retained.pdf", make_synthetic_pdf("Synthetic retained PDF.")),
                                             ("retained.mp4", mp4())])
def test_retained_pdf_and_video_correction_preview_and_save(tmp_path, filename, content):
    api.init(tmp_path, title="Synthetic retained media")
    capture = api.ingest_media(tmp_path, content, filename=filename, allow_retention=True)
    body = f'![Media](lixity:media/{capture["source_id"]}/{capture["source_version_id"]})'
    dossier = api.create_dossier(tmp_path, "Notes", body)["dossier_id"]
    before = retained_files(tmp_path)
    preview = correct(tmp_path, dossier, capture, dry_run=True)
    assert preview["references_updated"] == 1 and retained_files(tmp_path) == before
    result = correct(tmp_path, dossier, capture)
    assert result["source_sha256"] == Repository(tmp_path).snapshot().records[capture["source_version_id"]].blob.sha256
    assert not any(isinstance(r, Extraction) for r in Repository(tmp_path).snapshot().records.values())


def test_extracted_pdf_is_rejected_without_writes(tmp_path):
    api.init(tmp_path, title="Synthetic extracted PDF")
    path = tmp_path / "extracted.pdf"
    path.write_bytes(make_synthetic_pdf("Synthetic extractable document."))
    capture = api.ingest(tmp_path, path, allow_retention=True, allow_fallback=True)
    dossier = api.create_dossier(tmp_path, "Notes",
        f'![Document](lixity:media/{capture["source_id"]}/{capture["source_version_id"]})')["dossier_id"]
    before = retained_files(tmp_path)
    with pytest.raises(ResearchError, match="extract"):
        correct(tmp_path, dossier, capture)
    assert retained_files(tmp_path) == before


@pytest.mark.parametrize("overrides", [{"actor": ""}, {"actor": "x" * 201}, {"actor": None},
                                       {"dry_run": 1}, {"dry_run": "true"}])
def test_invalid_actor_and_preview_flag_are_rejected_even_for_noop(attachment, overrides):
    project, dossier, capture, _, _ = attachment
    files = retained_files(project)
    with pytest.raises(ResearchError):
        correct(project, dossier, capture, context={}, **overrides)
    assert retained_files(project) == files


def test_cli_context_preview_save_and_conflict_keep_attachment_identity(attachment, capsys):
    project, dossier, capture, body, marker = attachment
    initial = Repository(project).snapshot()
    before = retained_files(project)
    args = ["research", "media-context", "--project", str(project), "--dossier-id", dossier,
            "--source-id", capture["source_id"], "--source-version-id", capture["source_version_id"],
            "--expected-snapshot", initial.digest, "--expected-revision", "1", "--context",
            json.dumps({"origin_url": "https://example.org/attribution", "provenance_note": "Reviewed source context."}),
            "--reason", "Correct attribution without replacing attachment.", "--actor", "synthetic-reviewer"]
    assert main([*args, "--dry-run"]) == 0
    preview = json.loads(capsys.readouterr().out)
    assert preview["schema_version"] == "research-media-context-preview-local/1"
    assert preview["changed"] and preview["references_updated"] == 1
    assert retained_files(project) == before
    assert main(args) == 0
    saved = json.loads(capsys.readouterr().out)
    assert saved["schema_version"] == "research-media-context-local/1"
    assert saved["source_id"] == capture["source_id"]
    snapshot = Repository(project).snapshot()
    assert sum(isinstance(r, Source) for r in snapshot.records.values()) == 1
    assert sum(isinstance(r, SourceVersion) for r in snapshot.records.values()) == 2
    assert snapshot.records[saved["source_version_id"]].created_by == "synthetic-reviewer"
    record = api.get_record(project, "dossier", dossier)["record"]
    assert record["created_by"] == "synthetic-reviewer" and record["revision"] == 2
    assert record["body"] == body.replace(marker, marker.replace(capture["source_version_id"], saved["source_version_id"]), 1)
    assert {p: b for p, b in retained_files(project).items() if "/blobs/" in p} == {
        p: b for p, b in before.items() if "/blobs/" in p}
    accepted = retained_files(project)
    assert main(args) == 1
    assert "changed" in capsys.readouterr().err
    assert retained_files(project) == accepted
