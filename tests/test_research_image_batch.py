"""Explicit image batches retain all captures and one dossier revision, or none."""

import json
from unittest.mock import patch

import pytest

from lixity.cli import main
from lixity.research import api
from lixity.research.repository import Repository, ResearchConflictError, ResearchError
from tests.research_support import retained_files
from tests.test_research_images import JPEG, png
from tests.test_research_ocr import make_synthetic_pdf


@pytest.fixture
def batch(tmp_path):
    project = tmp_path / "project"
    api.init(project, title="Synthetic batch")
    dossier = api.create_dossier(project, "Batch notes",
        "## Plans\n\n![Plan](images/plan.png)\n\n## Details\n\nKeep this text.\n")["dossier_id"]
    (tmp_path / "plan.png").write_bytes(png())
    (tmp_path / "detail.jpg").write_bytes(JPEG)
    items = [{"file": str(tmp_path / "plan.png"), "alt": "Plan", "replace_reference": "![Plan](images/plan.png)"},
             {"file": str(tmp_path / "detail.jpg"), "alt": "Detail", "section": "Details",
              "context": {"provenance_note": "Synthetic specimen, not a license determination."}}]
    loaded = api.get_record(project, "dossier", dossier)
    options = {"expected_snapshot": loaded["snapshot"], "expected_revision": 1, "allow_retention": True}
    return project, dossier, items, options


def test_batch_preview_is_read_only_and_save_is_one_revision(batch):
    project, dossier, items, options = batch
    before = retained_files(project)
    preview = api.attach_dossier_images(project, dossier, items, dry_run=True, **options)
    assert preview["ready"] and preview["dry_run"] and preview["attachment_count"] == 2
    assert preview["candidate_revision"] == 2
    assert retained_files(project) == before
    pinned = [{**item, "sha256": receipt["sha256"]} for item, receipt in zip(items, preview["placements"], strict=True)]
    result = api.attach_dossier_images(project, dossier, pinned, **options)
    assert result["record"]["revision"] == 2 and len(result["images"]) == 2
    assert len(result["captures"]) == 2
    assert api.record_history(project, "dossier", dossier)["latest_revision"] == 2
    assert "images/plan.png" not in result["record"]["body"]
    assert "Keep this text." in result["record"]["body"]
    assert {row["section"] for row in api.list_dossier_images(project)["images"]} == {"Plans", "Details"}
    assert api.audit(project)["ok"]
    with pytest.raises(ResearchConflictError):
        api.attach_dossier_images(project, dossier, items, **options)


def test_invalid_later_item_accepts_no_capture_or_revision(batch):
    project, dossier, items, options = batch
    before = retained_files(project)
    for changes in ({"section": "Missing"}, {"file": "missing.png"}, {"sha256": "0" * 64}):
        with pytest.raises((ResearchError, OSError)):
            api.attach_dossier_images(project, dossier, [items[0], {**items[1], **changes}], **options)
        assert retained_files(project) == before
    with pytest.raises(ResearchError, match="retention"):
        api.attach_dossier_images(project, dossier, items, **{**options, "allow_retention": False})
    assert retained_files(project) == before


def test_external_writer_conflict_accepts_no_batch_sources(batch):
    project, dossier, items, options = batch
    original = Repository.commit

    def concurrent(repository, additions, blobs, expected, **kwargs):
        with patch.object(Repository, "commit", original):
            api.create_dossier(project, "Concurrent note", "Independent accepted text.")
        return original(repository, additions, blobs, expected, **kwargs)

    with patch.object(Repository, "commit", concurrent), pytest.raises(ResearchConflictError):
        api.attach_dossier_images(project, dossier, items, **options)
    assert api.list_sources(project)["sources"] == []
    assert api.get_record(project, "dossier", dossier)["record"]["revision"] == 1


def test_cli_batch_relative_paths_preview_and_apply(batch, tmp_path, capsys):
    project, dossier, items, options = batch
    manifest = tmp_path / "batch.json"
    manifest.write_text(json.dumps({"schema_version": "research-dossier-image-batch/1",
        "items": [{**item, "file": item["file"].rsplit("/", 1)[1]} for item in items]}))
    args = ["research", "dossier-image", "--project", str(project), "--dossier-id", dossier,
            "--expected-snapshot", options["expected_snapshot"], "--expected-revision", "1",
            "--allow-retention", "--batch", str(manifest)]
    assert main([*args, "--dry-run"]) == 0
    assert json.loads(capsys.readouterr().out)["ready"]
    assert api.list_sources(project)["sources"] == []
    assert main(args) == 0
    assert len(json.loads(capsys.readouterr().out)["images"]) == 2
    assert api.audit(project)["ok"]


def test_cli_pdf_attachment_uses_shared_source_and_dossier_transaction(batch, tmp_path, capsys):
    project, dossier, _, options = batch
    pdf = tmp_path / "note.pdf"
    pdf.write_bytes(make_synthetic_pdf("Synthetic retained document."))
    args = ["research", "dossier-media", "--project", str(project), "--dossier-id", dossier,
            "--expected-snapshot", options["expected_snapshot"], "--expected-revision", "1",
            "--allow-retention", "--file", str(pdf), "--section", "Details", "--alt", "Document"]
    assert main(args) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["record"]["revision"] == 2
    assert result["media"][0]["media_type"] == "application/pdf"
    assert result["capture"]["passages"] == 0
    assert api.audit(project)["ok"]
