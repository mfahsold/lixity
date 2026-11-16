"""Neutral foreground startup does not discover or write into the caller's project."""

import errno
import socket
from http.server import BaseHTTPRequestHandler
from unittest.mock import MagicMock, patch

import pytest

from lixity.research import api as research_api
from lixity.server import LixityServerHandler
from lixity.server.runtime import _LoopbackHTTPServer, run_server
from tests.support import monkeypatch_handler_state, snapshot_handler_state


def test_loopback_listener_rejects_a_second_server_on_its_live_port():
    """The bind must remain exclusive even if two startup probes both succeeded."""
    with _LoopbackHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as first:
        with pytest.raises(OSError) as caught, \
             _LoopbackHTTPServer(first.server_address, BaseHTTPRequestHandler):
            pass
        assert caught.value.errno == errno.EADDRINUSE


@pytest.mark.parametrize("competitor", ["lixity", "reuse_socket"])
def test_windows_listener_reserves_its_live_address(monkeypatch, competitor):
    """Windows REUSEADDR must not permit another listener to share the port."""
    # The platform boundary models documented Winsock bind semantics. Keep the
    # real server constructor/bind policy; Linux cannot execute Winsock itself.
    exclusive_option = 987654
    bindings = {}

    class WinsockSocket:
        def __init__(self, *_args):
            self.address = None
            self.reuse = False
            self.exclusive = False

        def setsockopt(self, _level, option, value):
            if option == socket.SO_REUSEADDR:
                self.reuse = bool(value)
            elif option == exclusive_option:
                self.exclusive = bool(value)

        def bind(self, address):
            occupants = bindings.get(address, [])
            if occupants and (self.exclusive or not self.reuse
                              or any(item.exclusive for item in occupants)):
                raise OSError(errno.EADDRINUSE, "Address already owned")
            if self.exclusive and self.reuse:
                raise OSError(errno.EINVAL, "Conflicting Winsock bind options")
            self.address = address
            bindings.setdefault(address, []).append(self)

        def getsockname(self):
            return self.address

        def listen(self, _backlog):
            pass

        def close(self):
            if self.address is not None:
                bindings[self.address].remove(self)
                self.address = None

    monkeypatch.setattr(socket, "SO_EXCLUSIVEADDRUSE", exclusive_option, raising=False)
    monkeypatch.setattr(socket, "socket", WinsockSocket)
    address = ("127.0.0.1", 8765)
    with _LoopbackHTTPServer(address, BaseHTTPRequestHandler):
        if competitor == "lixity":
            with pytest.raises(OSError) as caught, \
                 _LoopbackHTTPServer(address, BaseHTTPRequestHandler):
                pass
        else:
            other = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            other.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                with pytest.raises(OSError) as caught:
                    other.bind(address)
            finally:
                other.close()
        assert caught.value.errno == errno.EADDRINUSE


def test_loopback_listener_rejects_a_reusing_socket_on_its_live_port():
    """An unrelated socket cannot take over the bound address via REUSEADDR."""
    with _LoopbackHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as first, \
         socket.socket(socket.AF_INET, socket.SOCK_STREAM) as other:
        other.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        with pytest.raises(OSError) as caught:
            other.bind(first.server_address)
        assert (caught.value.errno in (errno.EADDRINUSE, errno.EACCES)
                or getattr(caught.value, "winerror", None) in (10048, 10013))


def test_loopback_listener_can_rebind_after_close():
    """Restart needs address reuse, without sharing the active listener."""
    with _LoopbackHTTPServer(("127.0.0.1", 0), BaseHTTPRequestHandler) as first:
        address = first.server_address
    with _LoopbackHTTPServer(address, BaseHTTPRequestHandler) as restarted:
        assert restarted.server_address == address


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
