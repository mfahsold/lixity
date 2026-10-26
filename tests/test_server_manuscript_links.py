"""Manual manuscript associations bind native selection and reviewed archive state."""

import hashlib
import os
import shutil

import pytest

from lixity.pipeline import paragraph_identity, profile_document, resolve_document_config
from lixity.research import api
from lixity.research.repository import Repository
from lixity.server.pdf_context import manuscript_pdf_token, research_context_token
from lixity.style_fingerprint import FingerprintThresholds
from tests.support import LoopbackServer, make_handler


def test_duplicate_selection_is_distinct_from_stale_archive(workspace):
    project, _manuscript, _handler, body, request = workspace
    status, saved = request("/api/research-manuscript-link", body)
    assert status == 200
    body["expected_snapshot"] = saved["snapshot"]
    status, duplicate = request("/api/research-manuscript-link", body)
    assert status == 409 and duplicate["code"] == "duplicate-link"
    assert duplicate["link_id"] == saved["link_id"]
    assert Repository(project).snapshot().digest == saved["snapshot"]


@pytest.fixture
def workspace(tmp_path):
    project = tmp_path / "synthetic-project"
    api.init(project, title="Synthetic archive", language="en")
    manuscript = project / "manuscript.md"
    text = "# Synthetic manuscript\n\n## Morning\n\nMaya watched the bird. She opened the gate.\n"
    manuscript.write_text(text, encoding="utf-8")
    claim = api.create_claim(project, title="A morning bird", statement="A synthetic observation.")

    handler = make_handler(project, source_input=manuscript, research_dir=project)
    handler.refresh()
    with LoopbackServer(handler) as server:
        def request(route, body=None):
            headers = {"Origin": server.base}
            response = (server.request(route, payload=body, headers=headers) if body is not None
                        else server.request(route, headers=headers))
            return response.status, response.json

        config, _ = resolve_document_config(text, "en")
        paragraph = profile_document(text, config, FingerprintThresholds())[0][0]
        snapshot = Repository(project).snapshot()
        body = {"project_id": snapshot.project.id, "research_token": research_context_token(project),
                "project_token": manuscript_pdf_token(str(manuscript), project_root=str(project), language="en", title=None, thresholds=handler.thresholds),
                "expected_snapshot": snapshot.digest, "expected_source_sha256": hashlib.sha256(manuscript.read_bytes()).hexdigest(),
                "claim_id": claim["claim_id"], "claim_revision": 1, "allow_retention": True,
                "selection": {**paragraph_identity(paragraph), "start": 0, "end": 22, "quote": paragraph.text[:22]}}
        yield project, manuscript, handler, body, request


def review_route(body):
    return "/api/research/manuscript-review?research_token=" + body["research_token"] + "&project_token=" + body["project_token"]


def test_explicit_save_and_review_use_selected_manuscript(workspace):
    project, manuscript, handler, body, request = workspace
    assert body["expected_source_sha256"] in handler.dashboard_html
    assert body["selection"]["paragraph_sha256"] in handler.dashboard_html
    before = Repository(project).snapshot().digest
    status, reviewed = request(review_route(body))
    assert status == 200 and reviewed["ok"] and reviewed["links"] == []
    assert reviewed["passage_context"] == {"schema_version": "research-passage-context-local/1", "paragraphs": []}
    assert Repository(project).snapshot().digest == before
    status, created = request("/api/research-manuscript-link", body)
    assert status == 200 and created["ok"] and created["claim_revision"] == 1
    status, reviewed = request(review_route(body))
    assert status == 200 and reviewed["links"][0]["anchor_state"] == "resolved"
    assert reviewed["links"][0]["anchor"]["quote"] == body["selection"]["quote"]
    context = reviewed["passage_context"]["paragraphs"][0]
    assert context["state"] == "ready" and context["shown"] == context["total"] == 1
    assert context["groups"][0]["claims"][0]["versions"][0]["pinned"]["id"] == body["claim_id"]
    assert context["groups"][0]["claims"][0]["versions"][0]["associations"][0]["link_id"] == created["link_id"]
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
    assert status == 409 and not result["ok"] and result.get("code") == "stale-archive"
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
    assert status == 409 and not result["ok"] and result.get("code") == "stale-context"
    status, result = request(review_route(body))
    assert status == 409 and not result["ok"] and result.get("code") == "stale-context"
    assert Repository(copied).snapshot().digest == before
    current = {**body, "research_token": research_context_token(copied)}
    status, result = request("/api/research-manuscript-link", current)
    assert status == 409 and not result["ok"] and result.get("code") == "stale-context"


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


def test_reanchor_route_repins_unique_moved_anchor(workspace):
    _project, manuscript, _, body, request = workspace
    status, created = request("/api/research-manuscript-link", body)
    assert status == 200
    text = manuscript.read_text(encoding="utf-8")
    manuscript.write_text(text.replace("## Morning\n\n", "## Morning\n\nA new note.\n\n"), encoding="utf-8")
    status, reviewed = request(review_route(body))
    row = reviewed["links"][0]
    assert row["anchor_state"] == "moved" and row["candidate_lines"] == [7]
    payload = {"project_id": body["project_id"], "research_token": body["research_token"],
               "project_token": body["project_token"], "link_id": created["link_id"],
               "expected_snapshot": reviewed["snapshot"], "expected_revision": row["revision"],
               "expected_source_sha256": hashlib.sha256(manuscript.read_bytes()).hexdigest()}
    status, result = request("/api/research-manuscript-reanchor", payload)
    assert status == 200 and result["ok"] and result["record"]["revision"] == 2
    assert result["record"]["anchor"]["start_line"] == 7
    status, stale = request("/api/research-manuscript-reanchor", payload)
    assert status == 409 and not stale["ok"] and stale.get("code") == "stale-archive"
