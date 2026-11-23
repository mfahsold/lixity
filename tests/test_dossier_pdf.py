"""Native dossier exports read one accepted revision from the selected archive."""

import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from lixity.research import api
from lixity.research.models import Activity, Extraction, Head, Passage, Reference, reference
from lixity.research.repository import Repository, ResearchStorageError, digest, encode, publish
from lixity.server.pdf_context import research_context_token
from tests.support import LoopbackServer, make_handler
from tests.test_pdf_export import HAVE_FONTS
from tests.test_server_pdf import file_bytes


@pytest.fixture
def dossier_project(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    archive = tmp_path / "archive"
    api.init(archive, title="Synthetic dossier archive")
    source = tmp_path / "field-notes.txt"
    source.write_text("The original signal was a blue lantern.\n", encoding="utf-8")
    capture = api.ingest(archive, source, title="Synthetic field notes", allow_retention=True)
    passage = api.get_source(archive, capture["source_id"])["passages"][0]["id"]
    rows = "\n".join(f"| {chapter} | {chapter % 2} |" for chapter in range(1, 81))
    excerpts = "\n\n".join(
        f"### Passage {number}\n\n> Before passage {number}.\n> The character waits by the gate.\n> After passage {number}."
        for number in range(1, 51)
    )
    dossier = api.create_dossier(
        archive, "Original dossier",
        "## Chapter distribution\n\n| **Chapter** | `mention_count` |\n| --- | ---: |\n"
        + rows + "\n\n## Complete excerpts\n\n" + excerpts + "\n\nFinal archive paragraph.",
        language="en", evidence_ids=[passage],
    )
    source.write_text("The revised signal was a brass bell.\n", encoding="utf-8")
    api.ingest(archive, source, source_id=capture["source_id"], allow_retention=True)
    api.revise_record(
        archive, "dossier", dossier["dossier_id"], expected_revision=1,
        change_kind="correction", reason="Synthetic review of the saved dossier.",
        changes={"title": "Current dossier", "language": "de", "body": "Überarbeitete Notiz."},
    )
    return workspace, archive, dossier["dossier_id"]


def pdf_path(identifier, archive, revision=1, **changes):
    params = {"id": identifier, "revision": revision, "research_token": research_context_token(archive)}
    params.update(changes)
    return "/api/research/dossier-pdf?" + urlencode(params, doseq=True)


def test_pdf_rejects_inconsistent_extraction_provenance(dossier_project, monkeypatch):
    workspace, archive, identifier = dossier_project
    repository = Repository(archive)
    snapshot = repository.snapshot()
    first = api.get_dossier(archive, identifier, revision=1)["citations"][0]
    passage = snapshot.get(Reference(id=first["passage_id"]), Passage)
    extraction = snapshot.get(passage.extraction_ref, Extraction)
    unrelated = next(record for record in snapshot.records.values()
                     if isinstance(record, Activity) and record.source_version_ref != extraction.source_version_ref)

    # Simulate an inconsistent imported archive whose hashes and original quote
    # remain valid, but whose extraction activity belongs to a different version.
    altered = encode(extraction.model_copy(update={"activity_ref": reference(unrelated)}))
    previous = next(entry for entry in snapshot.manifest.entries if entry.ref == passage.extraction_ref)
    publish(repository.record_path(previous), altered, replace=True)
    changed = previous.model_copy(update={"sha256": digest(altered)})
    entries = [changed if entry is previous else entry for entry in snapshot.manifest.entries]
    manifest = encode(snapshot.manifest.model_copy(update={"entries": entries}))
    checksum = digest(manifest)
    repository.write_manifest(checksum, manifest)
    publish(repository.data / "HEAD.json", encode(Head(sha256=checksum)), replace=True)

    with pytest.raises(ResearchStorageError, match="Extraction provenance does not match source bytes"):
        api.get_dossier(archive, identifier, revision=1)
    monkeypatch.setattr("lixity.research.dossier_pdf.dossier_pdf", lambda **_: b"%PDF synthetic")
    before = file_bytes(workspace.parent)
    with LoopbackServer(make_handler(workspace, research_dir=archive)) as server:
        response = server.request(pdf_path(identifier, archive))
    assert response.status == 400
    assert response.json["message"] == "Extraction provenance does not match source bytes"
    assert file_bytes(workspace.parent) == before


@pytest.mark.skipif(not HAVE_FONTS, reason="requires the DejaVu font family")
def test_download_serves_exact_dossier_revisions_without_writing(dossier_project):
    workspace, archive, identifier = dossier_project
    handler = make_handler(workspace, research_dir=archive, language="fr")
    before = file_bytes(workspace.parent)
    with LoopbackServer(handler) as server:
        original = server.request(pdf_path(identifier, archive, 1))
        current = server.request(pdf_path(identifier, archive, 2))
    for response, filename in ((original, "Original_dossier-v1.pdf"), (current, "Current_dossier-v2.pdf")):
        assert response.status == 200, response.body.decode("utf-8", errors="replace")
        assert response.body.startswith(b"%PDF-") and response.body.rstrip().endswith(b"%%EOF")
        assert b"/MediaBox [0 0 595.276 841.890]" in response.body
        assert response.headers["content-type"] == "application/pdf"
        assert response.headers["content-disposition"] == f'attachment; filename="{filename}"'
        assert response.headers["content-length"] == str(len(response.body))
        assert response.headers["cache-control"] == "no-store"
    assert original.body != current.body
    assert file_bytes(workspace.parent) == before
    assert not (workspace / "exports").exists()
    assert not (archive / "exports").exists()


@pytest.mark.native_pdf
@pytest.mark.skipif(not HAVE_FONTS, reason="requires the DejaVu font family")
@pytest.mark.skipif(not shutil.which("pdftotext"), reason="requires Poppler pdftotext")
def test_pdf_keeps_tables_complete_quotes_and_pinned_citations(dossier_project, tmp_path):
    workspace, archive, identifier = dossier_project
    executable = shutil.which("pdftotext")
    assert executable
    with LoopbackServer(make_handler(workspace, research_dir=archive, language="fr")) as server:
        def extract(revision):
            response = server.request(pdf_path(identifier, archive, revision))
            assert response.status == 200, response.body.decode("utf-8", errors="replace")
            path = tmp_path / f"dossier-{revision}.pdf"
            path.write_bytes(response.body)
            result = subprocess.run(  # noqa: S603 - resolved Poppler executable and a synthetic PDF
                [executable, "-layout", str(path), "-"], check=True, capture_output=True, text=True,
            )
            assert not result.stderr
            return result.stdout

        original, current = extract(1), extract(2)
        dossier = api.get_dossier(archive, identifier, revision=1)
        api.withdraw(archive, source_id=dossier["citations"][0]["source_id"])
        after_withdrawal = extract(1)

    for item in (
        "Original dossier", "Version 1", "Chapter distribution", "Complete excerpts",
        "Before passage 1.", "The character waits by the gate.", "After passage 1.",
        "Before passage 50.", "After passage 50.", "Final archive paragraph.",
        "Source quotations", "Synthetic field notes", "The original signal was a blue lantern.",
    ):
        assert item in original
    assert "The revised signal was a brass bell." not in original
    assert "Current dossier" not in original
    assert original.count("Version 1") == 2, "The citation names the pinned source version"
    assert re.search(r"(?m)^\s*2\s+0\s*$", original)
    assert re.search(r"(?m)^\s*80\s+0\s*$", original)
    assert original.count("mention_count") > 1, "Chapter table headers repeat across pages"
    assert not re.search(r"(?m)^\s*[>|#]", original), "Structure should render as formatted text"
    assert original.count("The character waits by the gate.") == 50
    assert "Current dossier" in current and "Fassung 2" in current and "Überarbeitete Notiz." in current
    assert "Original dossier" not in current and "Final archive paragraph." not in current
    assert "Evidence unavailable" in after_withdrawal
    assert "The original signal was a blue lantern." not in after_withdrawal


def test_export_rejects_invalid_parameters_other_roots_and_cross_origin(dossier_project):
    workspace, archive, identifier = dossier_project
    own_path = pdf_path(identifier, archive)
    query = own_path.split("?", maxsplit=1)[1]
    before = file_bytes(workspace.parent)
    examples = [
        ("/api/research/dossier-pdf", 400),
        ("/api/research/dossier-pdf?" + query.split("&research_token=")[0], 400),
        (pdf_path(identifier, archive, []), 400),
        (pdf_path(identifier, archive, 0), 400),
        (pdf_path(identifier, archive, [1, 2]), 400),
        (pdf_path(identifier, archive, "later"), 400),
        (pdf_path(identifier, archive, research_token=""), 400),
        (pdf_path(identifier, archive, path=workspace / "other.md"), 400),
        (pdf_path(identifier, workspace), 409),
        (pdf_path(identifier, archive, 99), 404),
        (pdf_path(uuid4().urn, archive), 404),
    ]
    with LoopbackServer(make_handler(workspace, research_dir=archive)) as server:
        for path, expected in examples:
            status, data = server.request_json(path)
            assert status == expected, data
            assert data["ok"] is False
        status, data = server.request_json(own_path, headers={"Origin": "https://untrusted.example"})
        assert status == 403 and data["ok"] is False
    assert file_bytes(workspace.parent) == before


def test_withdrawn_dossier_cannot_be_exported_from_history(dossier_project):
    workspace, archive, identifier = dossier_project
    saved = api.get_dossier(archive, identifier)
    api.withdraw(archive, dossier_id=identifier, expected_snapshot=saved["snapshot"], expected_revision=2)
    before = file_bytes(workspace.parent)
    with LoopbackServer(make_handler(workspace, research_dir=archive)) as server:
        for revision in (1, 2):
            status, data = server.request_json(pdf_path(identifier, archive, revision))
            assert status == 404 and data["ok"] is False
    assert file_bytes(workspace.parent) == before


def test_inflight_export_releases_workspace_lock_and_rechecks_selection(dossier_project, monkeypatch):
    workspace, archive, identifier = dossier_project
    handler = make_handler(workspace, research_dir=archive)
    entered, resume = Event(), Event()

    def held_render(project, ref):
        assert project == archive.resolve() and ref.revision == 2
        entered.set()
        assert resume.wait(5)
        return "Synthetic dossier", b"%PDF-1.4\n%%EOF"

    monkeypatch.setattr("lixity.server.routes_pdf.compose_dossier_pdf", held_render)
    with LoopbackServer(handler) as server, ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(server.request_json, pdf_path(identifier, archive, 2))
        try:
            assert entered.wait(5)
            assert handler._workspace_lock.acquire(blocking=False)
            try:
                handler.research_dir = str(workspace)
            finally:
                handler._workspace_lock.release()
        finally:
            resume.set()
        status, data = pending.result(timeout=5)
    assert status == 409 and data["code"] == "stale-context"
