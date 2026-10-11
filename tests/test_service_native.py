"""Real native lifecycle checks use only disposable servers and synthetic text."""

import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest

from lixity import __version__
from lixity.service import ServiceManager, _write_json, process_birth


@pytest.fixture(autouse=True)
def darwin_startup_traces(tmp_path, monkeypatch):
    """Trace only synthetic macOS children that stall during native startup."""
    if sys.platform != "darwin":
        return
    diagnostics = tmp_path / "startup-diagnostics"
    diagnostics.mkdir()
    (diagnostics / "sitecustomize.py").write_text(
        "import faulthandler\nfaulthandler.dump_traceback_later(10, repeat=True)\n",
        encoding="utf-8",
    )
    inherited = os.environ.get("PYTHONPATH")
    monkeypatch.setenv("PYTHONPATH", str(diagnostics) + (os.pathsep + inherited if inherited else ""))


def free_port():
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def manager(tmp_path, port):
    return ServiceManager(port, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime",
                          backend="process", startup_timeout=30, stop_timeout=10)


def startup_diagnostics(app, result):
    """Expose only disposable fixture records/logs when native startup fails."""
    if isinstance(result, dict) and result.get("ok"):
        return ""
    files = {}
    for path in (app.runtime_file, app.ready_file, app.log_file):
        files[path.name] = path.read_text(encoding="utf-8", errors="replace")[-12000:] if path.exists() else "missing"
    return json.dumps({"result": result, "fixture_files": files}, ensure_ascii=False, indent=2)


def test_native_start_status_restart_and_stop_preserve_explicit_project(tmp_path, monkeypatch):
    for key in ("LIXITY_DIR", "LIXITY_HOST", "LIXITY_PORT"):
        monkeypatch.delenv(key, raising=False)
    project = tmp_path / "A book – Grüße"
    project.mkdir()
    source = project / "manuscript.md"
    source.write_text("# Synthetic title\n\n## Opening\n\nEin Vogel fliegt über den Garten.\n", encoding="utf-8")
    before = source.read_bytes()
    app = manager(tmp_path, free_port())
    opened = []
    monkeypatch.setattr("lixity.service.webbrowser.open", opened.append)
    try:
        started = app.control("start", {"project": str(project), "language": "de"})
        assert started["ok"] and started["state"] == "running", startup_diagnostics(app, started)
        first = started["pid"]
        with urllib.request.urlopen(f"http://127.0.0.1:{app.port}/api", timeout=10) as response:
            data = json.load(response)
        assert data["version"] == __version__ and data["project"]["manuscript_loaded"]
        assert data["project"]["language"] == "de"
        status = app.control("status", {})
        assert status["ok"] and status["pid"] == first
        existing = app.control("start", {"open_browser": True})
        assert existing["ok"] and existing["pid"] == first
        assert opened == [started["url"]], "Daily start --open opens the existing instance without a second process"
        restarted = app.control("restart", {})
        assert restarted["ok"] and restarted["state"] == "running", startup_diagnostics(app, restarted)
        assert restarted["pid"] != first
        with urllib.request.urlopen(f"http://127.0.0.1:{app.port}/api", timeout=10) as response:
            data = json.load(response)
        assert data["project"]["manuscript_loaded"] and data["project"]["language"] == "de"
        assert source.read_bytes() == before
        stopped = app.control("stop", {})
        assert stopped["ok"] and stopped["state"] == "stopped", stopped
        assert not app.runtime_file.exists()
        assert app.settings_file.exists(), "Stop retains explicit restart settings"
        assert not app.control("status", {})["ok"]
    finally:
        app.control("stop", {})


def test_live_owned_unready_process_is_still_stoppable(tmp_path):
    app = manager(tmp_path, free_port())
    token = secrets.token_hex(32)
    child = subprocess.Popen(  # noqa: S603 - synthetic owned child, no source data
        [sys.executable, "-c", "import time; time.sleep(60)", "--_service-token=" + token],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    try:
        _write_json(app.runtime_file, {"schema_version": "lixity-service-runtime/1", "port": app.port,
            "pid": child.pid, "birth": process_birth(child.pid), "token": token, "backend": "process",
            "unit": None, "ready": False, "version": __version__})
        status = app.control("status", {})
        assert status["state"] == "starting" and not status["ok"], status
        stopped = app.control("stop", {})
        assert stopped["ok"] and stopped["state"] == "stopped", stopped
        assert child.wait(timeout=10) is not None
        assert not app.runtime_file.exists()
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=10)


def test_foreign_listener_is_not_claimed_or_stopped(tmp_path):
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        port = listener.getsockname()[1]
        app = manager(tmp_path, port)
        for action in ("status", "start", "stop", "restart"):
            result = app.control(action, {})
            assert result["state"] == "busy" and not result["ok"], result
            assert not app.runtime_file.exists() and not app.settings_file.exists()
        assert listener.getsockname()[1] == port


def test_simultaneous_starts_share_one_owned_child(tmp_path, monkeypatch):
    for key in ("LIXITY_DIR", "LIXITY_HOST", "LIXITY_PORT"):
        monkeypatch.delenv(key, raising=False)
    port = free_port()
    app = manager(tmp_path, port)
    barrier = threading.Barrier(2)

    def start():
        contender = manager(tmp_path, port)
        barrier.wait(timeout=10)
        return contender.control("start", {})

    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: start(), range(2)))
        assert all(result["state"] in ("running", "starting") for result in results), results
        assert any(result["ok"] for result in results), startup_diagnostics(app, results)
        status = app.control("status", {})
        assert status["ok"] and status["state"] == "running", status
        assert all(result["pid"] == status["pid"] for result in results), results
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api", timeout=10) as response:
            assert json.load(response)["version"] == __version__
        assert app.control("stop", {})["ok"]
        assert not app.runtime_file.exists()
    finally:
        app.control("stop", {})
