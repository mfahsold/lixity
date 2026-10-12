"""Marker write failures return JSON and preserve synthetic manuscript bytes."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from lixity.server.routes_markers import MarkerRoutesMixin
from tests.support import LoopbackServer, make_handler


class RecordingMarkerHandler(MarkerRoutesMixin):
    def __init__(self, source):
        self.source_input = str(source)
        self.responses = []
        self.refreshed = False

    def _json(self, payload, code=200):
        self.responses.append((code, payload))

    def refresh(self):
        self.refreshed = True


@pytest.mark.parametrize("action,payload", [
    ("marker-add", {"line": 2, "kind": "todo", "note": "Synthetic note"}),
    ("marker-resolve", {"id": "example1"}),
])
def test_marker_write_failure_returns_500_and_preserves_source(tmp_path, action, payload):
    source = tmp_path / "manuscript.md"
    original = (
        b'<!-- LIXITY-MARKER id="example1" kind="todo" note="Synthetic note" -->\n'
        b"Synthetic paragraph.\n"
    )
    source.write_bytes(original)
    handler = RecordingMarkerHandler(source)
    with patch("lixity.io.os.replace", side_effect=OSError("replacement unavailable")):
        handler._handle_marker(action, payload)
    assert len(handler.responses) == 1
    code, body = handler.responses[0]
    assert code == 500
    assert body["ok"] is False
    assert "write manuscript" in body["message"].lower()
    assert not handler.refreshed
    assert source.read_bytes() == original
    assert sorted(path.name for path in tmp_path.iterdir()) == ["manuscript.md"]


def test_marker_decode_failure_returns_500_without_changing_source(tmp_path):
    source = tmp_path / "manuscript.md"
    original = b"Synthetic invalid UTF-8: \xff\n"
    source.write_bytes(original)
    handler = RecordingMarkerHandler(source)
    handler._handle_marker("marker-add", {"line": 1, "kind": "todo"})
    code, body = handler.responses[0]
    assert code == 500
    assert body["ok"] is False
    assert "utf-8" in body["message"]
    assert not handler.refreshed
    assert source.read_bytes() == original


@pytest.mark.parametrize("action,payload", [
    ("marker-add", {"line": 2, "kind": "todo", "note": "Synthetic note"}),
    ("marker-resolve", {"id": "example1"}),
])
def test_marker_http_replacement_failure_returns_json_500(tmp_path, action, payload):
    source = tmp_path / "manuscript.md"
    original = (
        b'<!-- LIXITY-MARKER id="example1" kind="todo" note="Synthetic note" -->\n'
        b"Synthetic paragraph.\n"
    )
    source.write_bytes(original)

    with LoopbackServer(make_handler(tmp_path, source_input=source)) as server:
        with patch("lixity.io.os.replace", side_effect=OSError("replacement unavailable")):
            response = server.request(f"/api/{action}", payload=payload)
        assert response.status == 500
        assert response.headers["content-type"] == "application/json; charset=utf-8"
        body = response.json
        assert body["ok"] is False
        assert "write manuscript" in body["message"].lower()
        assert source.read_bytes() == original
        assert sorted(path.name for path in tmp_path.iterdir()) == ["manuscript.md"]
