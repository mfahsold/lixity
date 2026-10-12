"""Manual manuscript associations bind native selection and reviewed archive state."""

import hashlib
import json
import os
import shutil
import threading
import urllib.error
import urllib.request
from typing import ClassVar

import pytest

from lixity.pipeline import paragraph_identity, profile_document, resolve_document_config
from lixity.research import api
from lixity.research.repository import Repository
from lixity.server import LixityServerHandler
from lixity.server.pdf_context import manuscript_pdf_token, research_context_token
from lixity.server.runtime import _LoopbackHTTPServer
from lixity.style_fingerprint import FingerprintThresholds


@pytest.fixture
def workspace(tmp_path):
    project = tmp_path / "synthetic-project"
    api.init(project, title="Synthetic archive", language="en")
    manuscript = project / "manuscript.md"
    text = "# Synthetic manuscript\n\n## Morning\n\nMaya watched the bird. She opened the gate.\n"
    manuscript.write_text(text, encoding="utf-8")
    claim = api.create_claim(project, title="A morning bird", statement="A synthetic observation.")

    class Handler(LixityServerHandler):
        source_input = str(manuscript)
        workspace_root = str(project)
        research_dir = str(project)
        exports_dir = str(project / "exports")
        language = "en"
        title = None
        thresholds = FingerprintThresholds()
        dashboard_html = ""
        dashboard_info: ClassVar[dict] = {}
        debug = False

    Handler.refresh()
    server = _LoopbackHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def request(route, body=None):
        headers = {"Origin": base}
        if body is not None:
            headers["Content-Type"] = "application/json"
        message = urllib.request.Request(base + route, headers=headers,  # noqa: S310 - disposable loopback
            data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(message, timeout=10) as response:  # noqa: S310 - disposable loopback
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.load(error)

    config, _ = resolve_document_config(text, "en")
    paragraph = profile_document(text, config, FingerprintThresholds())[0][0]
    snapshot = Repository(project).snapshot()
    body = {"project_id": snapshot.project.id, "research_token": research_context_token(project),
            "project_token": manuscript_pdf_token(str(manuscript), project_root=str(project), language="en", title=None, thresholds=Handler.thresholds),
            "expected_snapshot": snapshot.digest, "expected_source_sha256": hashlib.sha256(manuscript.read_bytes()).hexdigest(),
            "claim_id": claim["claim_id"], "claim_revision": 1, "allow_retention": True,
            "selection": {**paragraph_identity(paragraph), "start": 0, "end": 22, "quote": paragraph.text[:22]}}
    try:
        yield project, manuscript, Handler, body, request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def review_route(body):
    return "/api/research/manuscript-review?research_token=" + body["research_token"] + "&project_token=" + body["project_token"]


def test_explicit_save_and_review_use_selected_manuscript(workspace):
    project, manuscript, handler, body, request = workspace
    assert body["expected_source_sha256"] in handler.dashboard_html
    assert body["selection"]["paragraph_sha256"] in handler.dashboard_html
    before = Repository(project).snapshot().digest
    status, reviewed = request(review_route(body))
    assert status == 200 and reviewed["ok"] and reviewed["links"] == []
    assert Repository(project).snapshot().digest == before
    status, created = request("/api/research-manuscript-link", body)
    assert status == 200 and created["ok"] and created["claim_revision"] == 1
    status, reviewed = request(review_route(body))
    assert status == 200 and reviewed["links"][0]["anchor_state"] == "resolved"
    assert reviewed["links"][0]["anchor"]["quote"] == body["selection"]["quote"]
    status, listed = request("/api/research/manuscript-links?research_token=" + body["research_token"])
    assert status == 200 and listed["schema_version"] == "research-manuscript-links-local/1"
    assert listed["links"][0]["link_id"] == created["link_id"]
    assert manuscript.read_text(encoding="utf-8").endswith("She opened the gate.\n")


@pytest.mark.parametrize("field,value", [("research_token", None), ("project_token", "0" * 64),
    ("allow_retention", False), ("allow_retention", 1), ("claim_revision", True),
    ("expected_source_sha256", "0" * 64), ("selection", {}), ("source_path", "other.md")])
def test_unreviewed_or_malformed_writes_leave_archive_unchanged(workspace, field, value):
    project, _, _, body, request = workspace
    before = Repository(project).snapshot().digest
    status, result = request("/api/research-manuscript-link", {**body, field: value})
    assert status in (400, 409) and not result["ok"]
    assert Repository(project).snapshot().digest == before


def test_source_edit_requires_refresh_and_reports_review_without_reanchoring(workspace):
    project, manuscript, _, body, request = workspace
    status, _ = request("/api/research-manuscript-link", body)
    assert status == 200
    before = Repository(project).snapshot().digest
    manuscript.write_text(manuscript.read_text().replace("bird", "cloud"), encoding="utf-8")
    status, result = request("/api/research-manuscript-link", {**body, "expected_snapshot": before})
    assert status == 409 and not result["ok"]
    status, result = request(review_route(body))
    assert status == 200 and result["links"][0]["anchor_state"] == "changed"
    assert result["review_needed_count"] == 1
    assert Repository(project).snapshot().digest == before


def test_restored_copy_and_other_manuscript_refuse_original_context(workspace, tmp_path):
    project, _, handler, body, request = workspace
    copied = tmp_path / "copied-project"
    shutil.copytree(project, copied)
    handler.workspace_root = handler.research_dir = str(copied)
    handler.source_input = str(copied / "manuscript.md")
    before = Repository(copied).snapshot().digest
    status, result = request("/api/research-manuscript-link", body)
    assert status == 409 and not result["ok"]
    status, result = request(review_route(body))
    assert status == 409 and not result["ok"]
    assert Repository(copied).snapshot().digest == before
    current = {**body, "research_token": research_context_token(copied)}
    status, result = request("/api/research-manuscript-link", current)
    assert status == 409 and not result["ok"]


def test_native_read_and_write_require_context_tokens(workspace):
    project, _, _, body, request = workspace
    before = Repository(project).snapshot().digest
    status, result = request("/api/research/manuscript-review")
    assert status == 400 and not result["ok"]
    status, result = request("/api/research/manuscript-links")
    assert status == 400 and not result["ok"]
    status, result = request("/api/research-manuscript-link", {k: v for k, v in body.items() if k != "research_token"})
    assert status == 400 and not result["ok"]
    assert Repository(project).snapshot().digest == before


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="POSIX FIFO required")
def test_special_node_replacement_returns_unreadable_and_releases_workspace_lock(workspace):
    project, manuscript, _, body, request = workspace
    status, _ = request("/api/research-manuscript-link", body)
    assert status == 200
    before = Repository(project).snapshot().digest
    manuscript.unlink()
    os.mkfifo(manuscript)
    status, result = request(review_route(body))
    assert status == 200 and result["source_state"] == "unreadable"
    assert result["links"][0]["flags"] == ["source_unreadable"]
    status, selected = request("/api/research/claims?research_token=" + body["research_token"])
    assert status == 200 and selected["ok"]
    assert Repository(project).snapshot().digest == before
