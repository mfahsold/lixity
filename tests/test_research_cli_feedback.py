"""CLI receipts and exact source reads use consistent dossier controls."""

import contextlib
import io
import json

import pytest

from lixity.research import api, cli
from tests.research_support import capture_research, parse_research_args
from tests.test_research_images import png
from tests.test_research_media import mp4


@pytest.fixture
def dossier(tmp_path):
    api.init(tmp_path, title="Synthetic CLI feedback")
    identifier = api.create_dossier(tmp_path, "Notebook", "## Notes\n\nOriginal.")["dossier_id"]
    return tmp_path, identifier


def test_image_inventory_accepts_explicit_json(dossier):
    project, identifier = dossier
    status, output, errors = capture_research("dossier-images", "--project", str(project),
                                            "--dossier-id", identifier, "--json")
    assert (status, errors) == (0, "")
    assert json.loads(output)["images"] == []


@pytest.mark.parametrize(("command", "filename", "content"), (
    ("dossier-image", "sample.png", png()),
    ("dossier-media", "sample.mp4", mp4()),
))
def test_attachment_compact_receipt_reports_saved_revision(dossier, command, filename, content):
    project, identifier = dossier
    path = project / filename
    path.write_bytes(content)
    before = api.get_record(project, "dossier", identifier)
    status, output, errors = capture_research(command, "--project", str(project),
        "--dossier-id", identifier, "--file", str(path), "--allow-retention",
        "--expected-snapshot", before["snapshot"], "--expected-revision", "1", "--compact")
    assert (status, errors) == (0, "")
    receipt = json.loads(output)
    assert receipt["schema_version"] == "research-revision-write-summary-local/1"
    assert (receipt["base_revision"], receipt["revision"], receipt["changed"]) == (1, 2, True)
    assert "record" not in receipt and "body" not in receipt
    saved = api.get_record(project, "dossier", identifier)
    assert saved["record"]["revision"] == 2
    assert "Original." in saved["record"]["body"]


def test_whole_body_terminal_controls_still_require_redirection(dossier):
    project, identifier = dossier
    from tests.research_support import revise_record

    revise_record(project, "dossier", identifier, {"body": "Literal \u202e data."})

    class Terminal(io.StringIO):
        def isatty(self):
            return True

    output, errors = Terminal(), io.StringIO()
    args = parse_research_args("dossier", identifier, "--project", str(project),
                               "--format", "text", "--body-only")
    with contextlib.redirect_stdout(output), contextlib.redirect_stderr(errors):
        status = cli.run(args)
    assert status == 1 and output.getvalue() == ""
    assert "terminal controls or Unicode formatting" in errors.getvalue()


@pytest.mark.parametrize("flags", ((), ("--section", "Notes"), ("--summary",), ("--history",)))
def test_dossier_text_uses_revision_term(dossier, flags):
    project, identifier = dossier
    status, output, errors = capture_research("dossier", identifier, "--project", str(project),
                                            "--format", "text", *flags)
    assert (status, errors) == (0, "")
    assert "Revision 1" in output
    assert "Version 1" not in output


@pytest.mark.parametrize("dry_run", (True, False))
def test_batch_attachment_compact_preserves_preview_and_summarizes_save(dossier, dry_run):
    project, identifier = dossier
    (project / "sample.png").write_bytes(png())
    manifest = project / "batch.json"
    manifest.write_text(json.dumps({"schema_version": "research-dossier-image-batch/1",
                                   "items": [{"file": "sample.png", "section": "Notes"}]}))
    before = api.get_record(project, "dossier", identifier)
    flags = ("--dry-run",) if dry_run else ()
    status, output, errors = capture_research("dossier-image", "--project", str(project),
        "--dossier-id", identifier, "--batch", str(manifest), "--allow-retention",
        "--expected-snapshot", before["snapshot"], "--expected-revision", "1", "--compact", *flags)
    assert (status, errors) == (0, "")
    receipt = json.loads(output)
    assert receipt["dry_run"] is dry_run
    assert "record" not in receipt and "body" not in receipt
    if dry_run:
        assert receipt["schema_version"] == "research-dossier-images-preview-local/1"
        assert receipt["attachment_count"] == 1
        assert api.get_record(project, "dossier", identifier)["snapshot"] == before["snapshot"]
    else:
        assert receipt["schema_version"] == "research-revision-write-summary-local/1"
        assert receipt["revision"] == 2
