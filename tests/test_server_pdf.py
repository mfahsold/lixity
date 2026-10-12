"""Native manuscript PDF downloads bind to the selected workspace without writes."""

import http.client
import json
import re
import shutil
import subprocess
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar

import pytest

from lixity.server import LixityServerHandler
from lixity.server.pdf_context import manuscript_pdf_token
from lixity.style_fingerprint import FingerprintThresholds
from tests.test_pdf_export import HAVE_FONTS

pytestmark = pytest.mark.skipif(not HAVE_FONTS, reason="requires the DejaVu font family")


@pytest.fixture
def pdf_server(tmp_path):
    manuscript = tmp_path / "synthetic.md"
    manuscript.write_text(
        "# Manuscript heading\n\n## Über den Fluss\n\n"
        + "ÄÖÜ äöü ß und Grüße begleiten die Erzählung. " * 100 + "\n",
        encoding="utf-8",
    )
    (tmp_path / "lixity.toml").write_text(
        'title = "Configured synthetic title"\nlanguage = "de"\nauthor_name = "Synthetic Author"\n',
        encoding="utf-8",
    )

    class Handler(LixityServerHandler):
        source_input = str(manuscript)
        workspace_root = str(tmp_path)
        exports_dir = str(tmp_path / "exports")
        research_dir = None
        language = "de"
        title = "Configured synthetic title"
        title_custom = False
        thresholds = FingerprintThresholds()
        project_open_overrides: ClassVar[dict[str, str]] = {}
        debug = False

    Handler.refresh()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    token = manuscript_pdf_token(
        Handler.source_input, project_root=Handler.workspace_root, language=Handler.language,
        title=Handler.title, thresholds=Handler.thresholds,
    )
    try:
        yield server.server_port, tmp_path, Handler, token
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(port, payload, *, origin=None, action="manuscript-pdf"):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    headers = {"Content-Type": "application/json"}
    if origin:
        headers["Origin"] = origin
    connection.request("POST", "/api/" + action, json.dumps(payload), headers)
    response = connection.getresponse()
    result = response.status, dict(response.getheaders()), response.read()
    connection.close()
    return result


def file_bytes(project):
    return {str(path.relative_to(project)): path.read_bytes()
            for path in project.rglob("*") if path.is_file()}


@pytest.mark.parametrize("layout,page_size", [
    ("book", b"419.528 595.276"), ("sheet", b"595.276 841.890"),
    ("report", b"595.276 841.890"),
])
def test_each_layout_downloads_a_pdf_without_creating_or_changing_files(pdf_server, layout, page_size):
    port, project, _handler, token = pdf_server
    before = file_bytes(project)
    status, headers, body = request(port, {"layout": layout, "project_token": token})
    assert status == 200, body.decode("utf-8", errors="replace")
    assert body.startswith(b"%PDF-1.4") and body.rstrip().endswith(b"%%EOF")
    assert b"/MediaBox [0 0 " + page_size + b"]" in body
    assert headers["Content-Type"] == "application/pdf"
    assert headers["Content-Disposition"] == f'attachment; filename="synthetic-{layout}.pdf"'
    assert headers["Content-Length"] == str(len(body))
    assert headers["Cache-Control"] == "no-store"
    assert file_bytes(project) == before
    assert not (project / "exports").exists()


@pytest.mark.parametrize("changes", [
    {"layout": "other"}, {"layout": []}, {"project_token": None}, {"path": "/other.md"},
    {"text": "Client text must not be rendered"}, {"author": "Client author"},
])
def test_invalid_or_client_supplied_manuscript_inputs_are_rejected(pdf_server, changes):
    port, project, _handler, token = pdf_server
    before = file_bytes(project)
    status, headers, body = request(port, {"layout": "book", "project_token": token, **changes})
    assert status == 400
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert json.loads(body)["ok"] is False
    assert file_bytes(project) == before


def test_old_project_token_and_cross_origin_downloads_are_rejected(pdf_server):
    port, project, handler, token = pdf_server
    before = file_bytes(project)
    handler.title = "Another selected title"
    status, _headers, body = request(port, {"layout": "book", "project_token": token})
    assert status == 409 and json.loads(body)["ok"] is False
    status, _headers, body = request(
        port, {"layout": "book", "project_token": token}, origin="https://untrusted.example",
    )
    assert status == 403 and json.loads(body)["ok"] is False
    assert file_bytes(project) == before


def test_download_resolves_shared_project_configuration_once(pdf_server, monkeypatch):
    from lixity.server import routes_pdf

    port, project, _handler, token = pdf_server
    calls: list[str | None] = []
    original = routes_pdf.load_project_config

    def counting(start=None):
        calls.append(str(start) if start is not None else None)
        return original(start)

    monkeypatch.setattr(routes_pdf, "load_project_config", counting)
    status, _headers, body = request(port, {"layout": "book", "project_token": token})
    assert status == 200, body.decode("utf-8", errors="replace")
    assert calls == [str(project / "synthetic.md")]


@pytest.mark.parametrize("source_state", ["unselected", "missing", "empty", "headings"])
def test_no_readable_nonempty_selected_manuscript_is_not_exported(pdf_server, source_state):
    port, project, handler, token = pdf_server
    if source_state == "unselected":
        handler.source_input = None
    elif source_state == "missing":
        Path(handler.source_input).unlink()
    elif source_state == "empty":
        Path(handler.source_input).write_text("\n", encoding="utf-8")
    else:
        Path(handler.source_input).write_text("# A title\n\n## A chapter\n", encoding="utf-8")
    before = file_bytes(project)
    status, headers, body = request(port, {"layout": "book", "project_token": token})
    assert status == 400 and json.loads(body)["ok"] is False
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert file_bytes(project) == before
    if source_state == "headings":
        assert "prose" in json.loads(body)["message"]


@pytest.mark.native_pdf
@pytest.mark.skipif(not shutil.which("pdftotext"), reason="requires Poppler pdftotext")
def test_changed_publication_author_reject_old_token_and_fresh_download_uses_new_metadata(
    pdf_server, tmp_path,
):
    port, project, handler, old_token = pdf_server
    config = project / "lixity.toml"
    original = config.read_text(encoding="utf-8")
    for changed, expected in (
        (original.replace('author_name = "Synthetic Author"',
                          'author_name = "Updated Grüße"'), "Updated Grüße"),
        (original + '\n[publication]\nenabled = true\npublisher_name = "Updated Synthetic Publisher"\n',
         "Updated Synthetic Publisher"),
    ):
        config.write_text(changed, encoding="utf-8")
        before = file_bytes(project)
        status, _headers, body = request(port, {"layout": "book", "project_token": old_token})
        assert status == 409 and json.loads(body)["ok"] is False
        fresh = manuscript_pdf_token(
            handler.source_input, project_root=handler.workspace_root, language=handler.language,
            title=handler.title, thresholds=handler.thresholds,
        )
        assert fresh != old_token
        status, headers, body = request(port, {"layout": "book", "project_token": fresh})
        assert status == 200 and headers["Content-Type"] == "application/pdf"
        assert file_bytes(project) == before
        path = tmp_path / "download-check.pdf"
        path.write_bytes(body)
        executable = shutil.which("pdftotext")
        assert executable
        result = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic PDF
            [executable, str(path), "-"], check=True, capture_output=True, text=True,
        )
        assert not result.stderr
        assert expected in result.stdout
        path.unlink()


@pytest.mark.parametrize("malformed", ["source", "config"])
def test_changed_unreadable_source_or_malformed_config_returns_json(pdf_server, malformed):
    port, project, handler, token = pdf_server
    if malformed == "source":
        Path(handler.source_input).write_bytes(b"\xff\xfe\x00\x80")
    else:
        (project / "lixity.toml").write_text('title = "unclosed\n', encoding="utf-8")
    before = file_bytes(project)
    status, headers, body = request(port, {"layout": "book", "project_token": token})
    assert status == (409 if malformed == "config" else 400)
    assert json.loads(body)["ok"] is False
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert file_bytes(project) == before


def test_font_failure_returns_json_without_creating_artifacts(pdf_server, monkeypatch):
    port, project, _handler, token = pdf_server
    before = file_bytes(project)
    missing_font = project / "absent.ttf"
    monkeypatch.setenv("LIXITY_PDF_FONT_TEXT", str(missing_font))
    status, headers, body = request(port, {"layout": "book", "project_token": token})
    assert status == 400
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert "Configured font for text does not exist" in json.loads(body)["message"]
    assert str(missing_font) in json.loads(body)["message"]
    assert file_bytes(project) == before


@pytest.mark.parametrize("change", ["settings", "project-open"])
def test_project_change_during_composition_cancels_the_download(pdf_server, monkeypatch, change):
    from lixity import pdf_export

    port, project, _handler, token = pdf_server
    before = file_bytes(project)
    started, continue_composition = threading.Event(), threading.Event()
    compose = pdf_export.compose_pdf

    def delayed(*args, **kwargs):
        started.set()
        assert continue_composition.wait(timeout=10)
        return compose(*args, **kwargs)

    monkeypatch.setattr(pdf_export, "compose_pdf", delayed)
    results = []
    pending = threading.Thread(target=lambda: results.append(request(
        port, {"layout": "book", "project_token": token},
    )))
    pending.start()
    after_change = before
    try:
        assert started.wait(timeout=5)
        # Real state-changing routes must complete while composition is paused.
        if change == "settings":
            payload = {"title": "Another selected title"}
        else:
            other = project.parent / f"{project.name}-other"
            other.mkdir()
            (other / "manuscript.md").write_text("# Other project\n\nA separate synthetic manuscript.\n")
            payload = {"path": str(other)}
        status, _headers, body = request(port, payload, action=change)
        assert status == 200, body
        after_change = file_bytes(project)
        assert after_change["synthetic.md"] == before["synthetic.md"]
    finally:
        continue_composition.set()
        pending.join(timeout=10)
    assert not pending.is_alive()
    status, headers, body = results[0]
    assert status == 409 and json.loads(body)["ok"] is False
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    # Settings now deliberately persists the title. PDF cancellation must not
    # write anything beyond that authorized state transition.
    assert file_bytes(project) == after_change


def test_rendered_selection_token_is_accepted_with_implicit_title(pdf_server):
    port, _project, handler, _token = pdf_server
    handler.title = None
    handler.refresh()
    token = re.search(
        r'<form\b[^>]*id="manuscript-pdf-form"[^>]*data-project-token="([0-9a-f]{64})"',
        handler.dashboard_html,
    ).group(1)
    status, _headers, body = request(port, {"layout": "book", "project_token": token})
    assert status == 200 and body.startswith(b"%PDF-1.4")


@pytest.mark.native_pdf
@pytest.mark.skipif(not shutil.which("pdftotext"), reason="requires Poppler pdftotext")
def test_download_uses_selected_manuscript_and_project_author(pdf_server, tmp_path):
    port, _project, _handler, token = pdf_server
    status, _headers, body = request(port, {"layout": "book", "project_token": token})
    assert status == 200
    path = tmp_path / "download.pdf"
    path.write_bytes(body)
    result = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic local PDF
        [shutil.which("pdftotext"), "-layout", str(path), "-"],
        check=True, capture_output=True, text=True,
    )
    assert not result.stderr
    assert "Configured synthetic title" in result.stdout
    assert "Synthetic Author" in result.stdout
    assert result.stdout.count("Grüße") == 100
