"""Neutral foreground startup does not discover or write into the caller's project."""

from unittest.mock import MagicMock, patch

import pytest

from lixity.research import api as research_api
from lixity.server import LixityServerHandler
from lixity.server.runtime import run_server
from tests.support import monkeypatch_handler_state, snapshot_handler_state


@pytest.mark.parametrize("target_path", [None, "missing-project"])
def test_no_project_start_does_not_create_exports_or_analyze_cwd(
    tmp_path, monkeypatch, target_path
):
    source = tmp_path / "manuscript.md"
    source.write_text("# Synthetic manuscript\n\nA bird crosses the garden.\n")
    monkeypatch.chdir(tmp_path)
    monkeypatch_handler_state(monkeypatch)
    before = source.read_bytes()
    server = MagicMock()
    server.serve_forever.side_effect = KeyboardInterrupt()
    with patch("lixity.server.runtime.socket.socket") as probe, \
         patch("lixity.server.runtime._LoopbackHTTPServer", return_value=server), \
         patch("lixity.server.runtime.resolve_project_target") as resolve:
        probe.return_value.__enter__.return_value.connect_ex.return_value = 1
        run_server(target_path, no_project=True)
    resolve.assert_not_called()
    assert LixityServerHandler.source_input is None
    assert LixityServerHandler.dashboard_info["is_empty"]
    assert not (tmp_path / "exports").exists()
    assert source.read_bytes() == before
    server.server_close.assert_called_once()


def test_invalid_explicit_target_does_not_select_cwd_archive(tmp_path, monkeypatch):
    research_api.init(tmp_path, title="Synthetic caller archive")
    monkeypatch.chdir(tmp_path)
    monkeypatch_handler_state(monkeypatch)
    previous_state = snapshot_handler_state()
    archive_files = {
        path.relative_to(tmp_path): path.read_bytes()
        for path in (tmp_path / "research").rglob("*")
        if path.is_file()
    }
    server = MagicMock()
    server.serve_forever.side_effect = KeyboardInterrupt()
    ready = MagicMock()

    with patch("lixity.server.runtime.socket.socket") as probe, \
         patch("lixity.server.runtime._LoopbackHTTPServer", return_value=server) as bind:
        probe.return_value.__enter__.return_value.connect_ex.return_value = 1
        with pytest.raises(ValueError, match="Project path must be a folder or manuscript file"):
            run_server(str(tmp_path / "missing-project"), on_ready=ready)

    bind.assert_not_called()
    ready.assert_not_called()
    assert snapshot_handler_state() == previous_state
    assert not (tmp_path / "exports").exists()
    assert {
        path.relative_to(tmp_path): path.read_bytes()
        for path in (tmp_path / "research").rglob("*")
        if path.is_file()
    } == archive_files


@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("ambiguous", [False, True])
def test_neutral_start_preserves_selected_directory(tmp_path, monkeypatch, explicit, ambiguous):
    project = tmp_path / "project"
    project.mkdir()
    caller = tmp_path / "caller" if explicit else project
    caller.mkdir(exist_ok=True)
    if ambiguous:
        (project / "one.md").write_text("# One\n\nA synthetic note.\n", encoding="utf-8")
        (project / "two.md").write_text("# Two\n\nAnother synthetic note.\n", encoding="utf-8")
    monkeypatch.chdir(caller)
    monkeypatch_handler_state(monkeypatch)
    server = MagicMock()
    server.serve_forever.side_effect = KeyboardInterrupt()

    with patch("lixity.server.runtime.socket.socket") as probe, \
         patch("lixity.server.runtime._LoopbackHTTPServer", return_value=server):
        probe.return_value.__enter__.return_value.connect_ex.return_value = 1
        run_server(str(project) if explicit else None)

    assert LixityServerHandler.workspace_root == str(project)
    assert LixityServerHandler.source_input is None
    assert LixityServerHandler.dashboard_info["is_empty"]
    assert (project / "exports").is_dir()
    if explicit:
        assert not (caller / "exports").exists()
    server.server_close.assert_called_once()


def test_readiness_callback_runs_after_bind_and_failure_closes_the_socket(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch_handler_state(monkeypatch)
    events = []
    server = MagicMock()

    def bound(*_args):
        events.append("bound")
        return server

    def ready():
        events.append("ready")
        raise OSError("Synthetic readiness write failure")

    with patch("lixity.server.runtime.socket.socket") as probe, \
         patch("lixity.server.runtime._LoopbackHTTPServer", side_effect=bound):
        probe.return_value.__enter__.return_value.connect_ex.return_value = 1
        with pytest.raises(OSError, match="Synthetic readiness"):
            run_server(no_project=True, on_ready=ready)
    assert events == ["bound", "ready"]
    server.serve_forever.assert_not_called()
    server.server_close.assert_called_once()


@pytest.mark.parametrize("host", ["127.0.0.1", "localhost"])
def test_local_start_binds_without_reverse_dns(tmp_path, monkeypatch, host):
    import socket

    monkeypatch.chdir(tmp_path)
    monkeypatch_handler_state(monkeypatch)
    bound = []

    def serve(server):
        assert server.server_name == host
        assert server.server_port == server.server_address[1] > 0
        with socket.create_connection((host, server.server_port), timeout=2):
            pass
        bound.append(server.server_port)
        raise KeyboardInterrupt()

    with patch("socket.getfqdn", side_effect=AssertionError("Local startup must not reverse-resolve")) as fqdn, \
         patch("socket.gethostbyaddr", side_effect=AssertionError("Reverse DNS is unavailable")) as reverse, \
         patch("lixity.server.runtime.ThreadingHTTPServer.serve_forever", new=serve):
        run_server(no_project=True, host=host, port=0)
    fqdn.assert_not_called()
    reverse.assert_not_called()
    assert len(bound) == 1
