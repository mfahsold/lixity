"""Script-facing service observations remain read-only and exclude local paths."""

import argparse
import errno
import json
import socket
from pathlib import Path

import pytest

from lixity import __version__, api, cli, service


@pytest.fixture
def isolated_status(tmp_path, monkeypatch):
    state, runtime = tmp_path / "state", tmp_path / "runtime"
    monkeypatch.setenv("LIXITY_SERVICE_STATE_DIR", str(state))
    monkeypatch.setenv("LIXITY_SERVICE_RUNTIME_DIR", str(runtime))
    for key in ("LIXITY_DIR", "LIXITY_HOST", "LIXITY_PORT"):
        monkeypatch.delenv(key, raising=False)
    return state, runtime


def arguments(*values):
    parser = argparse.ArgumentParser()
    service.configure(parser)
    return parser.parse_args(list(values))


def snapshot(root):
    return {
        str(path.relative_to(root)): (
            path.lstat().st_mode,
            path.lstat().st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
        for path in root.rglob("*")
    }


def test_stopped_json_succeeds_without_creating_storage_or_changing_human_status(
    tmp_path, isolated_status, capsys
):
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        before = snapshot(tmp_path)
        assert cli.main(["service", "status", "--port", str(port), "--json"]) == 0
        result = json.loads(capsys.readouterr().out)
        assert result == {
            "schema_version": "lixity-service-status/1",
            "ok": True, "running": False, "state": "stopped", "port": port,
            "url": f"http://127.0.0.1:{port}/", "pid": None, "backend": None,
            "installed_version": __version__, "running_version": None,
            "message": "Lixity is stopped",
        }
        assert service.run(arguments("status", "--port", str(port))) == 1
        assert "[--] Lixity is stopped" in capsys.readouterr().out
        assert snapshot(tmp_path) == before


def test_status_json_reports_an_unmanaged_listener_without_adopting_or_writing(
    tmp_path, isolated_status, capsys
):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        before = snapshot(tmp_path)
        assert service.run(arguments("status", "--port", str(port), "--json")) == 0
        result = json.loads(capsys.readouterr().out)
        assert result["ok"] and result["state"] == "busy" and result["running"] is False
        assert result["pid"] is None and result["backend"] is None
        assert snapshot(tmp_path) == before


@pytest.mark.parametrize("version, expected_version", (
    (__version__, __version__),
    ("/synthetic/private-source --credential=synthetic-secret", None),
    ({"source": "synthetic-secret"}, None),
))
def test_pending_status_is_known_but_not_ready_and_preserves_the_record(
    tmp_path, isolated_status, capsys, version, expected_version
):
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        manager = service.ServiceManager(port)
        service._write_json(manager.runtime_file, {
            "schema_version": "lixity-service-runtime/1", "port": port,
            "token": "a" * 64, "pid": None, "birth": None, "backend": "process",
            "unit": None, "ready": False, "version": version,
        })
        before = snapshot(tmp_path)
        assert service.run(arguments("status", "--port", str(port), "--json")) == 0
        text = capsys.readouterr().out
        result = json.loads(text)
        assert result["ok"] and result["state"] == "starting" and result["running"] is False
        assert result["running_version"] == expected_version
        assert "private-source" not in text and "synthetic-secret" not in text
        assert snapshot(tmp_path) == before


@pytest.mark.parametrize("fault", ("malformed", "unsafe", "unreadable", "runtime-unavailable"))
def test_invalid_or_unreadable_status_is_unknown_without_repair_or_path_disclosure(
    tmp_path, isolated_status, monkeypatch, capsys, fault
):
    port = 59971
    manager = service.ServiceManager(port)
    if fault in ("malformed", "unsafe"):
        manager.runtime_dir.mkdir(mode=0o700)
        manager.runtime_file.write_text("synthetic-private-source-secret", encoding="utf-8")
        manager.runtime_file.chmod(0o600)
        if fault == "unsafe":
            manager.runtime_file.chmod(0o644)
    original_lstat = Path.lstat
    if fault in ("unreadable", "runtime-unavailable"):
        inaccessible = manager.runtime_file if fault == "unreadable" else manager.runtime_dir

        def denied(path, *args, **kwargs):
            if path == inaccessible:
                raise PermissionError(errno.EACCES, "synthetic-private-source-secret", str(path))
            return original_lstat(path, *args, **kwargs)

        monkeypatch.setattr(Path, "lstat", denied)
    before = snapshot(tmp_path)
    assert service.run(arguments("status", "--port", str(port), "--json")) == 1
    text = capsys.readouterr().out
    result = json.loads(text)
    assert result["schema_version"] == "lixity-service-status/1"
    assert not result["ok"] and result["running"] is None and result["state"] == "unknown"
    assert result["message"]
    assert str(tmp_path) not in text and "synthetic-private-source-secret" not in text
    assert "log" not in result and "project" not in result
    assert snapshot(tmp_path) == before


def test_invalid_environment_port_is_unknown_and_does_not_echo_input(
    tmp_path, isolated_status, monkeypatch, capsys
):
    monkeypatch.setenv("LIXITY_PORT", "synthetic-private-source-secret")
    before = snapshot(tmp_path)
    assert service.run(arguments("status", "--json")) == 1
    text = capsys.readouterr().out
    result = json.loads(text)
    assert result["port"] is None and result["url"] is None
    assert result["running"] is None and result["state"] == "unknown"
    assert "synthetic-private-source-secret" not in text
    assert snapshot(tmp_path) == before


def test_shared_status_function_and_cli_each_make_one_observation(
    isolated_status, monkeypatch, capsys
):
    observations = []
    original = service.ServiceManager.control

    def inspect(manager, action, overrides):
        observations.append((manager.port, action))
        return original(manager, action, overrides)

    monkeypatch.setattr(service.ServiceManager, "control", inspect)
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
        shared = service.service_status(port)
        assert observations == [(port, "status")]
        assert shared["ok"] and shared["running"] is False
        assert service.run(arguments("status", "--port", str(port), "--json")) == 0
        assert json.loads(capsys.readouterr().out) == shared
        assert observations == [(port, "status"), (port, "status")]


def test_unavailable_home_directory_is_unknown_in_shared_and_cli_results(
    tmp_path, isolated_status, monkeypatch, capsys
):
    def unavailable():
        raise RuntimeError("synthetic-secret: cannot resolve /synthetic/private-home")

    monkeypatch.delenv("XDG_STATE_HOME", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(Path, "home", unavailable)
    before = snapshot(tmp_path)
    shared = service.service_status(59971)
    assert not shared["ok"] and shared["running"] is None and shared["state"] == "unknown"
    assert service.run(arguments("status", "--port", "59971", "--json")) == 1
    text = capsys.readouterr().out
    assert json.loads(text) == shared
    assert "synthetic-secret" not in text and "private-home" not in text
    assert snapshot(tmp_path) == before


@pytest.mark.parametrize("port", (-1, 65536, True))
def test_shared_status_rejects_invalid_ports_without_creating_storage(
    tmp_path, isolated_status, port
):
    before = snapshot(tmp_path)
    result = service.service_status(port)
    assert not result["ok"] and result["running"] is None and result["state"] == "unknown"
    assert result["port"] is None and result["url"] is None
    assert snapshot(tmp_path) == before


def test_service_discovery_distinguishes_status_from_lifecycle_json():
    command = next(item for item in api.about()["commands"] if item["name"] == "service")
    assert command["schema_version"] == "lixity-service-local/1"
    assert command["status_schema_version"] == "lixity-service-status/1"


def test_native_running_status_uses_the_same_projection_without_reading_project_sources(
    tmp_path, isolated_status, monkeypatch, capsys
):
    from tests.test_service_native import start_disposable

    project = tmp_path / "synthetic-project"
    project.mkdir()
    manuscript = project / "manuscript.md"
    manuscript.write_text("# Synthetic title\n\n## Opening\n\nA gate opened.\n", encoding="utf-8")
    app, started = start_disposable(tmp_path, {"project": str(project)})
    try:
        assert started["ok"] and started["state"] == "running"
        before = snapshot(tmp_path)
        original_read = Path.read_bytes

        def protect_source(path):
            if path == manuscript:
                raise AssertionError("Status must not read the manuscript")
            return original_read(path)

        with monkeypatch.context() as guarded:
            guarded.setattr(Path, "read_bytes", protect_source)
            assert service.run(arguments("status", "--port", str(app.port), "--json")) == 0
        text = capsys.readouterr().out
        result = json.loads(text)
        assert result["ok"] and result["running"] is True and result["state"] == "running"
        assert result["pid"] == started["pid"] and result["backend"] == "process"
        assert result["installed_version"] == result["running_version"] == __version__
        assert "log" not in result and str(project) not in text
        assert service.run(arguments("status", "--port", str(app.port))) == 0
        assert "[OK] Lixity is running" in capsys.readouterr().out
        assert snapshot(tmp_path) == before
        # Other lifecycle JSON deliberately retains its established contract and semantics.
        assert service.run(arguments("stop", "--port", str(app.port), "--json")) == 0
        stopped = json.loads(capsys.readouterr().out)
        assert stopped["schema_version"] == "lixity-service-local/1"
        assert stopped["ok"] and stopped["state"] == "stopped"
    finally:
        app.control("stop", {})
