"""Route discovery and explicit CLI JSON selection use synthetic local projects."""

import contextlib
import http.client
import io
import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from lixity import __version__, api
from lixity.cli import main
from lixity.research import api as research
from lixity.research import cli as research_cli
from lixity.research.repository import Repository
from lixity.server import LixityServerHandler


@pytest.fixture
def endpoint(tmp_path):
    class Handler(LixityServerHandler):
        workspace_root = str(tmp_path)
        source_input = None
        research_dir = None
        debug = False

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def request(path, headers=None, *, method="GET", body=None):
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, response.read(), response.getheader("Content-Type")
        finally:
            connection.close()

    yield Handler, request
    server.shutdown()
    server.server_close()
    thread.join(timeout=2)


@pytest.mark.parametrize("path", ["/api", "/api/"])
def test_api_index_without_a_loaded_project(endpoint, path):
    _, request = endpoint
    status, body, content_type = request(path)
    assert status == 200 and content_type.startswith("application/json")
    data = json.loads(body)
    assert data["schema_version"] == "lixity-api-index/1"
    assert data["version"] == __version__
    assert data["project"]["manuscript_loaded"] is False
    assert data["project"]["research_store_present"] is False
    assert data["documentation"] == "https://mfahsold.github.io/lixity/AGENTS.md"
    assert "/api/research/record" in data["routes"]["GET"]
    assert "/api/research/history" in data["routes"]["GET"]
    assert "/api/research/ocr-status" in data["routes"]["GET"]
    for route in ("analyze", "rebuild", "marker-add", "marker-resolve", "research-zotero", "research-zotero-ingest"):
        assert f"/api/{route}" in data["routes"]["POST"]
    assert "/api/export" not in data["routes"]["POST"]
    assert not any(route in data["routes"]["POST"] for route in ("/api/nda-list", "/api/nda-unlock", "/api/nda-add"))


def test_index_reflects_registered_routes_without_archive_or_source_reads(endpoint, tmp_path, monkeypatch):
    handler, request = endpoint
    manuscript = tmp_path / "synthetic.md"
    manuscript.write_text("Synthetic manuscript sentinel; excluded from discovery.")
    research.init(tmp_path, title="Synthetic archive title excluded from discovery")
    handler.source_input = str(manuscript)
    handler.research_dir = str(tmp_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Discovery must not read source or archive records")

    monkeypatch.setattr(Repository, "snapshot", forbidden)
    monkeypatch.setattr(type(manuscript), "read_text", forbidden)
    monkeypatch.setattr(type(manuscript), "read_bytes", forbidden)
    status, body, _ = request("/api")
    assert status == 200
    data = json.loads(body)
    assert data["project"]["manuscript_loaded"] and data["project"]["research_store_present"]
    assert "Synthetic manuscript sentinel" not in body.decode()
    assert "Synthetic archive title" not in body.decode()
    assert str(tmp_path) not in body.decode()
    assert set(data["routes"]["GET"]) == set(handler.GET_ROUTES)
    assert set(data["routes"]["POST"]) == {f"/api/{action}" for action in handler.POST_ROUTES}


def test_index_keeps_the_existing_host_guard(endpoint):
    _, request = endpoint
    status, body, _ = request("/api", {"Host": "untrusted.example"})
    assert status == 403 and json.loads(body)["ok"] is False


def test_index_tracks_the_same_registry_used_by_dispatch(endpoint):
    handler, request = endpoint

    def synthetic_route(self):
        self._json({"ok": True, "synthetic": True})

    handler._synthetic_discovery_route = synthetic_route
    handler.GET_ROUTES = {**handler.GET_ROUTES, "/api/synthetic-discovery": "_synthetic_discovery_route"}
    status, body, _ = request("/api")
    assert status == 200 and "/api/synthetic-discovery" in json.loads(body)["routes"]["GET"]
    status, body, _ = request("/api/synthetic-discovery")
    assert status == 200 and json.loads(body)["synthetic"] is True


def test_implicit_research_root_is_the_project_not_its_archive(endpoint, tmp_path):
    handler, request = endpoint
    research.init(tmp_path, title="Synthetic default research root")
    assert handler.get_research_root() == tmp_path
    status, body, _ = request("/api/research/status")
    assert status == 200 and json.loads(body)["initialized"] is True
    assert json.loads(body)["project_root"] == str(tmp_path)


@pytest.mark.parametrize("command", ["sources", "audit", "review", "decision-impact", "compare", "matrix"])
def test_json_alias_selects_real_cli_machine_output(tmp_path, command):
    project = tmp_path / "project"
    research.init(project, title="Synthetic CLI project")
    flags = []
    if command == "decision-impact":
        decision = research.record_decision(project, title="Synthetic decision", rationale="Author supplied rationale.")
        flags = ["--decision-id", decision["decision_id"]]
    elif command == "compare":
        source = tmp_path / "source.txt"
        source.write_text("Synthetic archive record about a reading room. " * 100)
        captured = research.ingest(project, source, allow_retention=True)
        manuscript = tmp_path / "manuscript.md"
        manuscript.write_text("# Synthetic manuscript\n\n## Chapter One\n\n" + "A reader entered the quiet reading room. " * 100)
        flags = ["--source-id", captured["source_id"], "--manuscript", str(manuscript)]
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        status = main(["research", command, "--project", str(project), *flags, "--json"])
    assert status == 0 and isinstance(json.loads(output.getvalue()), dict)


def test_json_alias_is_exclusive_with_other_output_formats(tmp_path):
    errors = io.StringIO()
    with contextlib.redirect_stderr(errors), pytest.raises(SystemExit) as failure:
        main(["research", "review", "--project", str(tmp_path), "--json", "--format", "md"])
    assert failure.value.code == 2
    assert "not allowed with argument" in errors.getvalue()


def test_about_reports_research_formats_from_the_command_parser():
    research_command = next(command for command in api.about()["commands"] if command["name"] == "research")
    commands = {command["name"]: command for command in research_command["subcommands"]}
    assert commands["review"]["default_output"] == "text"
    assert commands["decision-impact"]["json_flag"] == "--json"
    assert commands["matrix"]["default_output"] == "md"
    assert commands["dashboard"]["output_formats"] == ["html"]
    assert commands["sources"]["default_output"] == "json"


def test_about_format_metadata_tracks_parser_configuration(monkeypatch):
    monkeypatch.setitem(research_cli.OUTPUT_FORMATS, "review", (("text", "md", "json"), "md"))
    research_command = next(command for command in api.about()["commands"] if command["name"] == "research")
    review = next(command for command in research_command["subcommands"] if command["name"] == "review")
    assert review["default_output"] == "md"


def test_about_reports_supported_research_record_and_manifest_versions():
    research_command = next(command for command in api.about()["commands"] if command["name"] == "research")
    assert "research-local/5" in research_command["record_schema_versions"]
    assert "research-manifest-local/5" in research_command["manifest_schema_versions"]


@pytest.mark.parametrize("status", ["applied", "review_needed"])
def test_acknowledgement_http_route_uses_explicit_revision_tokens(endpoint, tmp_path, status):
    handler, request = endpoint
    research.init(tmp_path, title="Synthetic HTTP acknowledgement")
    dossier = research.create_dossier(tmp_path, "Synthetic dossier", "Synthetic untouched dossier.")["dossier_id"]
    decision = research.record_decision(tmp_path, title="Synthetic decision", rationale="Synthetic unchanged rationale.",
                                        dossier_ids=[dossier])["decision_id"]
    handler.research_dir = str(tmp_path)
    snapshot = Repository(tmp_path).snapshot()
    payload = {"decision_id": decision, "dossier_id": dossier, "expected_snapshot": snapshot.digest,
               "expected_decision_revision": 1, "expected_dossier_revision": 1, "status": status,
               "note": "Synthetic author statement."}
    code, body, _ = request("/api/research-decision-acknowledge", {"Content-Type": "application/json"},
                             method="POST", body=json.dumps(payload))
    data = json.loads(body)
    assert code == 200 and data["ok"] is True and data["status"] == status
    assert data["decision_revision"] == 1 and data["dossier_revision"] == 1
    assert data["snapshot"] != snapshot.digest
    assert research.get_dossier(tmp_path, dossier)["body"] == "Synthetic untouched dossier."


@pytest.mark.parametrize("invalid", ["snapshot", "decision", "dossier", "missing", "status"])
def test_acknowledgement_http_conflict_or_invalid_body_writes_nothing(endpoint, tmp_path, invalid):
    handler, request = endpoint
    research.init(tmp_path, title="Synthetic HTTP acknowledgement")
    dossier = research.create_dossier(tmp_path, "Synthetic dossier", "Synthetic unchanged body.")["dossier_id"]
    decision = research.record_decision(tmp_path, title="Synthetic decision", rationale="Synthetic rationale.",
                                        dossier_ids=[dossier])["decision_id"]
    handler.research_dir = str(tmp_path)
    before = Repository(tmp_path).snapshot().digest
    payload = {"decision_id": decision, "dossier_id": dossier, "expected_snapshot": before,
               "expected_decision_revision": 1, "expected_dossier_revision": 1, "status": "applied"}
    if invalid == "snapshot":
        payload["expected_snapshot"] = "0" * 64
    elif invalid in ("decision", "dossier"):
        payload[f"expected_{invalid}_revision"] = 2
    elif invalid == "missing":
        del payload["expected_snapshot"]
    else:
        payload["status"] = "verified"
    code, body, _ = request("/api/research-decision-acknowledge", {"Content-Type": "application/json"},
                             method="POST", body=json.dumps(payload))
    assert code == (409 if invalid in ("snapshot", "decision", "dossier") else 400)
    assert json.loads(body)["ok"] is False
    assert Repository(tmp_path).snapshot().digest == before
