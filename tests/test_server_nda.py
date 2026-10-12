"""The simple NDA endpoint downloads drafts without a recipient database."""

import json

import pytest

from tests.support import LoopbackServer, make_handler, send


@pytest.fixture
def workspace_server(tmp_path):
    manuscript = tmp_path / "manuscript.md"
    manuscript.write_text("## Example\n\nA door opens.", encoding="utf-8")
    (tmp_path / "lixity.toml").write_text('language = "de"\ntitle = "Synthetic project"\n', encoding="utf-8")
    handler = make_handler(tmp_path, source_input=manuscript, language="de", title="Synthetic project")
    handler.refresh()
    with LoopbackServer(handler) as server:
        yield server.port, tmp_path


def request(port, payload, action="nda-draft", origin=None):
    headers = {"Origin": origin} if origin else None
    response = send(port, "/api/" + action, payload=payload, headers=headers)
    return response.status, response.headers, response.body


def fields(**extra):
    return {"name": "Example Reader", "address": "Musterstraße 12", "project_name": "Synthetic project",
            "date": "2026-10-06", "place": "Example City", **extra}


@pytest.mark.parametrize("output,content_type", [("pdf", "application/pdf"), ("text", "text/plain; charset=utf-8")])
def test_download_is_complete_localized_and_has_no_store_side_effect(workspace_server, output, content_type):
    port, project = workspace_server
    before = set(project.rglob("*"))
    status, headers, body = request(port, fields(format=output))
    assert status == 200, body.decode("utf-8", errors="replace")
    assert headers["content-type"] == content_type
    assert headers["cache-control"] == "no-store"
    assert "attachment" in headers["content-disposition"]
    text = body.decode("cp1252" if output == "pdf" else "utf-8")
    assert "Vertraulichkeitsvereinbarung" in text
    assert "Example Reader" in text and "Musterstraße 12" in text
    assert "Example City" in text and "2026-10-06" in text
    assert set(project.rglob("*")) == before
    assert not (project / "nda").exists()


@pytest.mark.parametrize("payload", [fields(name=""), fields(project_name=""), fields(date="2026-02-30"), fields(format="exe")])
def test_invalid_draft_returns_json_error_without_files(workspace_server, payload):
    port, project = workspace_server
    status, headers, body = request(port, payload)
    assert status == 400 and headers["content-type"] == "application/json; charset=utf-8"
    assert json.loads(body)["ok"] is False
    assert not (project / "nda").exists()


def test_cross_origin_draft_is_rejected(workspace_server):
    port, project = workspace_server
    status, _, body = request(port, fields(), origin="https://untrusted.example")
    assert status == 403 and json.loads(body)["ok"] is False
    assert not (project / "nda").exists()


def test_retired_recipient_management_is_not_supported(workspace_server):
    port, project = workspace_server
    for action in ("nda-list", "nda-unlock", "nda-add", "nda-update", "nda-export", "nda-delete"):
        status, _, body = request(port, {}, action=action)
        assert status == 400 and json.loads(body)["ok"] is False
    assert not (project / "nda").exists()
