"""Optional dossier reads remain bound to the manuscript shown in an older tab."""

import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from typing import ClassVar
from urllib.parse import urlencode

import pytest

from lixity.research import api
from lixity.server import LixityServerHandler
from lixity.server.pdf_context import manuscript_pdf_token
from lixity.style_fingerprint import FingerprintThresholds


@pytest.fixture
def reader_server(tmp_path):
    api.init(tmp_path, title="Synthetic project", language="en")
    dossier = api.create_dossier(tmp_path, title="Synthetic dossier", body="Synthetic research notes.")
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("# Synthetic novel\n\n## Chapter\n\nA synthetic manuscript paragraph.\n")

    class Handler(LixityServerHandler):
        source_input = str(manuscript)
        workspace_root = str(tmp_path)
        research_dir = str(tmp_path)
        exports_dir = str(tmp_path / "exports")
        language = "en"
        title = "Synthetic project"
        thresholds = FingerprintThresholds()
        project_open_overrides: ClassVar[dict] = {}

    Handler.refresh()
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    token = manuscript_pdf_token(Handler.source_input, project_root=Handler.workspace_root,
        language=Handler.language, title=Handler.title, thresholds=Handler.thresholds)
    try:
        yield server.server_port, tmp_path, Handler, token, dossier["dossier_id"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def read(port, query):
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    connection.request("GET", "/api/research/dossiers?" + urlencode(query, doseq=True))
    response = connection.getresponse()
    status, data = response.status, json.loads(response.read())
    connection.close()
    return status, data


def contents(project):
    return {str(path.relative_to(project)): path.read_bytes() for path in project.rglob("*") if path.is_file()}


def test_context_bound_dossier_list_and_reader_preserve_legacy_data_and_files(reader_server):
    port, project, _handler, token, dossier_id = reader_server
    before = contents(project)
    legacy_status, legacy = read(port, {})
    status, data = read(port, {"project_token": token})
    assert legacy_status == status == 200 and data == legacy
    legacy_status, legacy = read(port, {"id": dossier_id})
    status, data = read(port, {"id": dossier_id, "project_token": token})
    assert legacy_status == status == 200 and data == legacy
    assert data["body"] == "Synthetic research notes."
    assert contents(project) == before


def test_old_tab_cannot_mix_its_manuscript_with_another_selection(reader_server):
    port, project, handler, token, dossier_id = reader_server
    before = contents(project)
    with handler._workspace_lock:
        handler.title = "Another selected title"
    for query in ({"project_token": token}, {"id": dossier_id, "project_token": token}):
        status, data = read(port, query)
        assert status == 409 and not data["ok"]
        assert "dossiers" not in data and "body" not in data
    assert read(port, {"id": dossier_id})[0] == 200
    assert contents(project) == before


@pytest.mark.parametrize("token", ["", "not-a-token", ["a" * 64, "b" * 64]])
def test_malformed_context_token_is_an_explicit_error(reader_server, token):
    port, project, _handler, _token, _dossier_id = reader_server
    before = contents(project)
    status, data = read(port, {"project_token": token})
    assert status == 400 and not data["ok"]
    assert contents(project) == before
