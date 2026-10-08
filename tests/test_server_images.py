"""The raster transport stays explicit, bounded and same-origin."""

import base64
import http.client
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.parse import urlencode
from uuid import uuid4

import pytest

from lixity.research import api
from lixity.research.repository import Repository
from lixity.server import LixityServerHandler
from tests.test_research_images import png


@pytest.fixture
def endpoint(tmp_path):
    class Handler(LixityServerHandler):
        research_dir = str(tmp_path)
        workspace_root = str(tmp_path)
        debug = False

    project_id = api.init(tmp_path, title="Synthetic image HTTP")["project_id"]
    dossier = api.create_dossier(tmp_path, "Synthetic dossier", "Original note.")["dossier_id"]
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(path, *, payload=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            body = json.dumps(payload) if payload is not None else None
            values = {"Content-Type": "application/json"} if body else {}
            values.update(headers or {})
            connection.request("POST" if body else "GET", path, body=body, headers=values)
            response = connection.getresponse()
            return response.status, response.read(), dict(response.getheaders())
        finally:
            connection.close()

    yield tmp_path, project_id, dossier, request
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


def payload(project_id):
    return {"project_id": project_id, "filename": "specimen.png", "content_base64": base64.b64encode(png()).decode(),
            "allow_retention": True, "context": {"provenance_note": "Synthetic local image"}}


def test_registered_image_capture_and_secure_exact_binary_response(endpoint):
    project, project_id, _, request = endpoint
    code, body, _ = request("/api/research-image-ingest", payload=payload(project_id))
    assert code == 200, body
    result = json.loads(body)
    query = urlencode({"project_id": project_id, "source_id": result["source_id"], "version_id": result["source_version_id"]})
    code, body, headers = request("/api/research/image?" + query)
    assert code == 200 and body == png()
    assert headers["Content-Type"] == "image/png"
    assert headers["Cache-Control"] == "no-store"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cross-Origin-Resource-Policy"] == "same-origin"
    for headers in ({"Origin": "https://foreign.invalid"}, {"Sec-Fetch-Site": "cross-site"}):
        assert request("/api/research/image?" + query, headers=headers)[0] == 403
    foreign = urlencode({"project_id": uuid4().urn, "source_id": result["source_id"], "version_id": result["source_version_id"]})
    assert request("/api/research/image?" + foreign)[0] == 400
    assert request("/api/research/image?source_id=" + result["source_id"])[0] == 400
    assert api.audit(project)["ok"]


def test_joint_route_has_exact_cas_and_explicit_project_and_retention(endpoint):
    project, project_id, dossier, request = endpoint
    loaded = api.get_record(project, "dossier", dossier)
    values = {**payload(project_id), "dossier_id": dossier, "expected_snapshot": loaded["snapshot"],
              "expected_revision": 1, "alt": "Synthetic specimen", "caption": "Author supplied caption."}
    for bad in ({"project_id": uuid4().urn}, {"allow_retention": False}, {"content_base64": "%%%"},
                {"expected_snapshot": "0" * 64}, {"expected_revision": 2}):
        code, _, _ = request("/api/research-dossier-image", payload={**values, **bad})
        assert code == (409 if "expected_snapshot" in bad or "expected_revision" in bad else 400)
        assert Repository(project).snapshot().digest == loaded["snapshot"]
    code, body, _ = request("/api/research-dossier-image", payload=values)
    assert code == 200, body
    result = json.loads(body)
    assert result["images"][0]["project_id"] == project_id
    assert result["record"]["change"]["change_kind"] == "supersession"
    assert request("/api/research-dossier-image", payload=values)[0] == 409


def test_image_json_limits_are_route_specific(endpoint):
    _, project_id, _, request = endpoint
    values = {**payload(project_id), "padding": "x" * (5 * 1024 * 1024)}
    assert request("/api/research-image-ingest", payload=values)[0] == 200
    assert request("/api/research-ingest", payload={}, headers={"Content-Length": str(5 * 1024 * 1024 + 1)})[0] == 413
    for route in ("research-image-ingest", "research-dossier-image"):
        assert request("/api/" + route, payload={}, headers={"Content-Length": str(32 * 1024 * 1024 + 1)})[0] == 413
