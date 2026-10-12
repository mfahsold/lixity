"""Native research chronology keeps explicit selected roots and reviewed writes."""

import json
import shutil
import threading
import urllib.error
import urllib.request
from typing import ClassVar

import pytest

from lixity.research import api
from lixity.research.repository import Repository
from lixity.server import LixityServerHandler
from lixity.server.pdf_context import research_context_token
from lixity.server.runtime import _LoopbackHTTPServer


@pytest.fixture
def workspace(tmp_path):
    project = tmp_path / "research-only"
    api.init(project, title="Synthetic archive", language="en")
    first = api.create_claim(project, title="First cause", statement="A synthetic cause", time_period="1910")
    second = api.create_claim(project, title="Later outcome", statement="A synthetic outcome", time_period="1920")

    class Handler(LixityServerHandler):
        source_input = None
        workspace_root = str(project)
        research_dir = str(project)
        exports_dir = str(project / "exports")
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
        message = urllib.request.Request(base + route, headers=headers,  # noqa: S310 - explicit disposable loopback server
            data=json.dumps(body).encode() if body is not None else None)
        try:
            with urllib.request.urlopen(message, timeout=10) as response:  # noqa: S310 - explicit disposable loopback server
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                return error.code, json.load(error)

    try:
        yield project, Handler, first["claim_id"], second["claim_id"], request
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def relation_body(project, first, second):
    snapshot = Repository(project).snapshot()
    return {"project_id": snapshot.project.id, "research_token": research_context_token(project),
            "expected_snapshot": snapshot.digest, "from_claim_id": first, "to_claim_id": second,
            "from_claim_revision": 1, "to_claim_revision": 1, "rationale": "An explicit synthetic interpretation"}


def test_research_only_renderer_and_claim_list_share_one_current_contract(workspace):
    project, handler, first, second, request = workspace
    token = research_context_token(project)
    before = Repository(project).snapshot()
    assert f'data-research-token="{token}"' in handler.dashboard_html
    status, current = request("/api/research/claims")
    assert status == 200 and set(current) == {"ok", "schema_version", "claims", "project_id", "snapshot"}
    assert current["schema_version"] == "research-claims-local/2"
    status, reviewed = request("/api/research/claims?research_token=" + token)
    assert status == 200 and reviewed == current
    assert reviewed["snapshot"] == before.digest and reviewed["project_id"] == before.project.id
    status, chronology = request("/api/research/timeline?research_token=" + token)
    assert status == 200 and chronology["schema_version"] == "research-timeline-local/1"
    assert [item["claim_id"] for item in chronology["dated"]] == [first, second]
    status, relations = request("/api/research/claim-relations?research_token=" + token)
    assert status == 200 and relations["relations"] == []
    after = Repository(project).snapshot()
    assert after.digest == before.digest and after.manifest == before.manifest


def test_relation_write_requires_reviewed_context_and_only_then_upgrades(workspace):
    project, _, first, second, request = workspace
    body = relation_body(project, first, second)
    before = Repository(project).snapshot()
    status, result = request("/api/research-claim-relation", {key: value for key, value in body.items() if key != "research_token"})
    assert status == 400 and not result["ok"]
    assert Repository(project).snapshot().digest == before.digest
    status, result = request("/api/research-claim-relation", body)
    assert status == 200 and result["ok"]
    assert result["from_claim_revision"] == result["to_claim_revision"] == 1
    assert Repository(project).snapshot().manifest.schema_version == "research-manifest-local/6"
    status, stale = request("/api/research-claim-relation", body)
    assert status == 409 and not stale["ok"]


def test_restored_copy_with_same_project_and_snapshot_rejects_previous_root_token(workspace, tmp_path):
    project, handler, first, second, request = workspace
    body = relation_body(project, first, second)
    copied = tmp_path / "restored-copy"
    shutil.copytree(project, copied)
    assert Repository(copied).snapshot().digest == body["expected_snapshot"]
    assert Repository(copied).snapshot().project.id == body["project_id"]
    handler.research_dir = str(copied)
    handler.workspace_root = str(copied)
    before = Repository(copied).snapshot().digest
    for route, payload in (("/api/research-claim-relation", body),
                           ("/api/research-search", {"query": "synthetic", "research_token": body["research_token"]})):
        status, result = request(route, payload)
        assert status == 409 and not result["ok"]
    status, result = request("/api/research/timeline?research_token=" + body["research_token"])
    assert status == 409 and not result["ok"]
    assert Repository(copied).snapshot().digest == before
    status, result = request("/api/research-claim-relation", {**body, "research_token": research_context_token(copied)})
    assert status == 200 and result["ok"]


@pytest.mark.parametrize("field,value", [("from_claim_revision", True), ("to_claim_revision", 0),
                                         ("expected_snapshot", "unknown"), ("actor", []),
                                         ("relation", "supports"), ("rationale", 23)])
def test_malformed_relation_envelopes_do_not_write(workspace, field, value):
    project, _, first, second, request = workspace
    body = relation_body(project, first, second)
    before = Repository(project).snapshot().digest
    status, result = request("/api/research-claim-relation", {**body, field: value})
    assert status == 400 and not result["ok"]
    assert Repository(project).snapshot().digest == before


@pytest.mark.parametrize("token", [None, False, "", "not-a-token", []])
def test_present_malformed_tokens_cannot_become_unbound_requests(workspace, token):
    project, _, first, second, request = workspace
    before = Repository(project).snapshot().digest
    for route, body in (("/api/research-search", {"query": "synthetic"}),
                        ("/api/research-record-revise", {"kind": "claim", "id": first,
                         "changes": {"title": "Unexpected edit"}, "expected_snapshot": before,
                         "expected_revision": 1, "change_kind": "correction", "reason": "Synthetic edit"}),
                        ("/api/research-claim-relation", relation_body(project, first, second))):
        status, result = request(route, {**body, "research_token": token})
        assert status == 400 and not result["ok"]
    assert Repository(project).snapshot().digest == before


@pytest.mark.parametrize("route,payload", [
    ("research-claim-add", {"title": "Synthetic claim", "statement": "A synthetic claim."}),
    ("research-dossier", {"title": "Synthetic dossier", "body": "A synthetic dossier."}),
    ("research-decision-add", {"title": "Synthetic decision", "rationale": "A synthetic decision."}),
    ("research-ingest", {"title": "Synthetic source", "text": "A retained synthetic source.", "allow_retention": True}),
])
def test_authored_create_refuses_stale_root_before_writing_and_accepts_current_root(workspace, tmp_path, route, payload):
    project, handler, _, _, request = workspace
    old_token = research_context_token(project)
    copied = tmp_path / "restored-authored-copy"
    shutil.copytree(project, copied)
    handler.workspace_root = str(copied)
    handler.research_dir = str(copied)
    before = Repository(copied).snapshot().digest
    original = Repository(project).snapshot().digest
    status, result = request("/api/" + route, {**payload, "research_token": old_token})
    assert status == 409 and not result["ok"]
    assert Repository(copied).snapshot().digest == before
    assert Repository(project).snapshot().digest == original
    status, result = request("/api/" + route, {**payload, "research_token": None})
    assert status == 400 and not result["ok"]
    assert Repository(copied).snapshot().digest == before
    status, result = request("/api/" + route, {**payload, "research_token": research_context_token(copied)})
    assert status == 200 and result["ok"]
    assert Repository(copied).snapshot().digest != before
    assert Repository(project).snapshot().digest == original
