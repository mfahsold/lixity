"""Neutral foreground startup does not discover or write into the caller's project."""

from unittest.mock import MagicMock, patch

import pytest

from lixity.server import LixityServerHandler
from lixity.server.runtime import run_server


def test_no_project_start_does_not_create_exports_or_analyze_cwd(tmp_path, monkeypatch):
    source = tmp_path / "manuscript.md"
    source.write_text("# Synthetic manuscript\n\nA bird crosses the garden.\n")
    monkeypatch.chdir(tmp_path)
    for key in ("source_input", "workspace_root", "exports_dir", "research_dir", "language", "title",
                "title_custom", "thresholds", "project_open_overrides", "dashboard_html", "dashboard_info", "debug"):
        monkeypatch.setattr(LixityServerHandler, key, getattr(LixityServerHandler, key))
    before = source.read_bytes()
    server = MagicMock()
    server.serve_forever.side_effect = KeyboardInterrupt()
    with patch("lixity.server.runtime.socket.socket") as probe, \
         patch("lixity.server.runtime.ThreadingHTTPServer", return_value=server), \
         patch("lixity.server.runtime.discover") as discover:
        probe.return_value.__enter__.return_value.connect_ex.return_value = 1
        run_server(no_project=True)
    discover.assert_not_called()
    assert LixityServerHandler.source_input is None
    assert LixityServerHandler.dashboard_info["is_empty"]
    assert not (tmp_path / "exports").exists()
    assert source.read_bytes() == before
    server.server_close.assert_called_once()


def test_readiness_callback_runs_after_bind_and_failure_closes_the_socket(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    for key in ("source_input", "workspace_root", "exports_dir", "research_dir", "language", "title",
                "title_custom", "thresholds", "project_open_overrides", "dashboard_html", "dashboard_info", "debug"):
        monkeypatch.setattr(LixityServerHandler, key, getattr(LixityServerHandler, key))
    events = []
    server = MagicMock()

    def bound(*_args):
        events.append("bound")
        return server

    def ready():
        events.append("ready")
        raise OSError("Synthetic readiness write failure")

    with patch("lixity.server.runtime.socket.socket") as probe, \
         patch("lixity.server.runtime.ThreadingHTTPServer", side_effect=bound):
        probe.return_value.__enter__.return_value.connect_ex.return_value = 1
        with pytest.raises(OSError, match="Synthetic readiness"):
            run_server(no_project=True, on_ready=ready)
    assert events == ["bound", "ready"]
    server.serve_forever.assert_not_called()
    server.server_close.assert_called_once()
