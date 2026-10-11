"""Packaged lifecycle ownership and explicit startup configuration."""

import errno
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

from lixity import __version__


def test_package_module_entrypoint_uses_the_installed_cli(tmp_path):
    source = Path(__file__).resolve().parents[1] / "src"
    result = subprocess.run(
        [sys.executable, "-m", "lixity", "--version"], cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(source)}, capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == f"lixity {__version__}"


def test_service_defaults_are_explicit_empty_and_do_not_touch_cwd_projects(tmp_path, monkeypatch):
    from lixity.service import resolve_settings

    project = tmp_path / "private-project"
    project.mkdir()
    (project / "manuscript.md").write_text("Synthetic manuscript must not be discovered.\n")
    monkeypatch.chdir(project)
    for key in ("LIXITY_DIR", "LIXITY_PORT", "LIXITY_HOST"):
        monkeypatch.delenv(key, raising=False)
    settings = resolve_settings(8765, {}, None)
    assert settings["project"] is None and settings["host"] == "127.0.0.1"
    assert list(project.iterdir()) == [project / "manuscript.md"]


def test_explicit_settings_win_over_environment_and_restart_preserves_saved_values(tmp_path, monkeypatch):
    from lixity.service import resolve_settings

    monkeypatch.setenv("LIXITY_DIR", str(tmp_path / "environment-project"))
    monkeypatch.setenv("LIXITY_HOST", "localhost")
    saved = resolve_settings(9000, {"project": str(tmp_path / "explicit project"),
                                   "host": "127.0.0.1", "language": "de", "title": "Über den Fluss"}, None)
    assert saved["project"] == str(tmp_path / "explicit project")
    assert saved["host"] == "127.0.0.1"
    assert resolve_settings(9000, {}, saved) == saved
    changed = resolve_settings(9000, {"title": "Another title"}, saved)
    assert changed["project"] == saved["project"] and changed["title"] == "Another title"
    assert resolve_settings(9000, {"no_project": True}, saved)["project"] is None


def test_corrupt_runtime_records_and_unknown_files_are_not_overwritten(tmp_path):
    from lixity.service import ServiceManager

    manager = ServiceManager(59980, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime",
                             backend="process", startup_timeout=0.2)
    manager.runtime_file.write_text('{"not":"a service record"}', encoding="utf-8")
    unknown = manager.runtime_file.parent / "unrelated.txt"
    unknown.write_text("Synthetic unrelated data", encoding="utf-8")
    before = manager.runtime_file.read_bytes()
    result = manager.control("stop", {})
    assert not result["ok"] and result["state"] == "unknown"
    assert manager.runtime_file.read_bytes() == before
    assert unknown.read_text() == "Synthetic unrelated data"
    assert not manager.settings_file.exists()


def test_recycled_pid_is_not_signalled(tmp_path, monkeypatch):
    import lixity.service as service

    manager = service.ServiceManager(59981, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime",
                                     backend="process")
    service._write_json(manager.runtime_file, {
        "schema_version": "lixity-service-runtime/1", "port": 59981,
        "token": "a" * 64, "pid": 12345, "birth": "original", "backend": "process",
        "unit": None, "ready": False, "version": __version__,
    })
    monkeypatch.setattr(service, "process_birth", lambda _pid: "recycled")
    signals = []
    monkeypatch.setattr(service, "_signal_process", lambda *args: signals.append(args))
    result = manager.control("stop", {})
    assert result["ok"] and result["state"] == "stopped"
    assert signals == []
    assert not manager.runtime_file.exists()


def test_worker_argv_keeps_unicode_spaces_and_the_invoking_interpreter():
    from lixity.service import worker_argv

    settings = {"port": 9000, "host": "127.0.0.1", "project": "/Synthetic project/Überall.md",
                "language": "de", "title": "ÄÖÜ title"}
    argv = worker_argv(settings, "a" * 64)
    assert argv[:4] == [sys.executable, "-m", "lixity", "serve"]
    assert "/Synthetic project/Überall.md" in argv
    assert "--title=ÄÖÜ title" in argv
    assert "--language=de" in argv
    assert "--_service-token=" + "a" * 64 in argv


def test_missing_owned_service_status_returns_stopped_machine_contract(tmp_path, monkeypatch):
    import lixity.service as service

    monkeypatch.setattr(service, "_port_open", lambda *args: False)
    manager = service.ServiceManager(59982, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime",
                                     backend="process")
    result = manager.control("status", {})
    assert result["schema_version"] == "lixity-service-local/1"
    assert result["state"] == "stopped" and not result["ok"]
    assert result["url"] == "http://127.0.0.1:59982/" and result["pid"] is None
    json.dumps(result)


def test_pending_launch_record_is_retained_and_does_not_spawn_again(tmp_path, monkeypatch):
    import lixity.service as service

    manager = service.ServiceManager(59983, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime",
                                     backend="process")
    service._write_json(manager.runtime_file, {
        "schema_version": "lixity-service-runtime/1", "port": 59983, "token": "b" * 64,
        "pid": None, "birth": None, "backend": "process", "unit": None,
        "ready": False, "version": __version__,
    })
    before = manager.runtime_file.read_bytes()
    monkeypatch.setattr(service, "_port_open", lambda *args: False)
    with patch.object(service.subprocess, "Popen", side_effect=AssertionError("must not create a second child")):
        result = manager.control("start", {})
    assert result["state"] == "starting" and not result["ok"]
    assert manager.runtime_file.read_bytes() == before


def test_pidfd_exit_race_does_not_turn_completed_stop_into_an_error(monkeypatch):
    import lixity.service as service

    monkeypatch.setattr(service.os, "pidfd_open", lambda _pid: 101, raising=False)
    monkeypatch.setattr(service.os, "close", lambda _fd: None)
    monkeypatch.setattr(service, "process_birth", lambda _pid: "owned")

    def gone(*args):
        raise ProcessLookupError()

    monkeypatch.setattr(service.signal, "pidfd_send_signal", gone, raising=False)
    service._signal_process(12345, 2, "owned")


def test_relative_managed_directories_are_anchored_before_child_cwd_changes(tmp_path, monkeypatch):
    from lixity.service import ServiceManager

    monkeypatch.chdir(tmp_path)
    manager = ServiceManager(59984, state_dir=Path("state"), runtime_dir=Path("runtime"), backend="process")
    assert manager.runtime_file == tmp_path / "runtime" / "service-59984.json"
    assert manager.work_dir == tmp_path / "state" / "workspace-59984"


def test_invalid_saved_numeric_settings_and_pid_range_are_preserved(tmp_path):
    import lixity.service as service

    manager = service.ServiceManager(59985, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime")
    service._write_json(manager.settings_file, {"schema_version": "lixity-service-settings/1",
        "settings": {"port": 59985, "host": "127.0.0.1", "project": None, "min_chapters": "bad"}})
    before = manager.settings_file.read_bytes()
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"]
    assert manager.settings_file.read_bytes() == before
    manager.settings_file.unlink()
    service._write_json(manager.runtime_file, {"schema_version": "lixity-service-runtime/1",
        "port": 59985, "token": "c" * 64, "pid": 2**64, "birth": "owned", "backend": "process",
        "unit": None, "ready": False, "version": __version__})
    before = manager.runtime_file.read_bytes()
    result = manager.control("stop", {})
    assert result["state"] == "unknown" and not result["ok"]
    assert manager.runtime_file.read_bytes() == before


def test_missing_explicit_project_is_rejected_before_settings_or_spawn(tmp_path):
    from lixity.service import ServiceManager

    manager = ServiceManager(59986, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime")
    result = manager.control("start", {"project": str(tmp_path / "missing")})
    assert not result["ok"] and "exist" in result["message"]
    assert not manager.settings_file.exists() and not manager.runtime_file.exists()


def test_start_wait_cannot_report_a_superseding_child_as_its_own(tmp_path, monkeypatch):
    import lixity.service as service

    manager = service.ServiceManager(59987, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime")
    settings = {"port": manager.port, "host": "127.0.0.1", "project": None, "open_browser": True}
    original = {"schema_version": "lixity-service-runtime/1", "port": manager.port,
        "token": "a" * 64, "pid": 101, "birth": "a", "backend": "process", "unit": None, "version": __version__}
    replacement = {**original, "token": "b" * 64, "pid": 102, "birth": "b"}
    service._write_json(manager.ready_file, {"schema_version": "lixity-service-ready/1",
        "token": replacement["token"], "pid": 102, "birth": "b", "version": __version__})
    reads = iter((original, replacement))
    monkeypatch.setattr(service, "_runtime_record", lambda *_: next(reads, replacement))
    monkeypatch.setattr(manager, "_start", lambda _: (manager._result("starting", settings, original), original["token"]))
    monkeypatch.setattr(manager, "_owned", lambda _: True)
    monkeypatch.setattr(service, "_port_open", lambda *_: True)
    opened = []
    monkeypatch.setattr(service.webbrowser, "open", opened.append)
    result = manager.control("start", {"open_browser": True})
    assert not result["ok"] and result["state"] == "stopped", result
    assert "superseded" in result["message"] and opened == []


def test_unsupported_pidfd_send_uses_fresh_birth_and_marker_but_permission_denial_never_falls_back(monkeypatch):
    import pytest

    import lixity.service as service

    monkeypatch.setattr(service.os, "pidfd_open", lambda _: 101, raising=False)
    monkeypatch.setattr(service.os, "close", lambda _: None)
    monkeypatch.setattr(service, "process_birth", lambda _: "owned")
    monkeypatch.setattr(service, "_has_marker", lambda *_: True)
    sent = []
    monkeypatch.setattr(service.os, "kill", lambda *args: sent.append(args))

    def unavailable(*_):
        raise OSError(errno.ENOSYS, "unsupported kernel")

    monkeypatch.setattr(service.signal, "pidfd_send_signal", unavailable, raising=False)
    service._signal_process(12345, 2, "owned", "a" * 64)
    assert sent == [(12345, 2)]
    sent.clear()
    monkeypatch.setattr(service, "_has_marker", lambda *_: False)
    service._signal_process(12345, 2, "owned", "a" * 64)
    assert sent == []

    def denied(*_):
        raise PermissionError(errno.EPERM, "refused")

    monkeypatch.setattr(service, "_has_marker", lambda *_: True)
    monkeypatch.setattr(service.signal, "pidfd_send_signal", denied)
    with pytest.raises(PermissionError):
        service._signal_process(12345, 2, "owned", "a" * 64)
    assert sent == []


def test_pending_native_unit_is_only_stopped_when_exact_unit_has_no_child(tmp_path, monkeypatch):
    import lixity.service as service

    app = service.ServiceManager(59988, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime")
    token = "d" * 64
    record = {"schema_version": "lixity-service-runtime/1", "port": app.port,
        "token": token, "pid": None, "birth": None, "backend": "systemd",
        "unit": service._unit_name(app.port, token), "version": __version__}
    service._write_json(app.runtime_file, record)
    monkeypatch.setattr(service.shutil, "which", lambda _: "/synthetic/systemctl")
    monkeypatch.setattr(service, "_port_open", lambda *_: False)
    inspected = []

    def unit_state(argv, **_):
        inspected.append(argv)
        return subprocess.CompletedProcess(argv, 0, "MainPID=0\nLoadState=loaded\nActiveState=activating\n", "")

    monkeypatch.setattr(service, "_run", unit_state)
    before = app.runtime_file.read_bytes()
    result = app.control("stop", {})
    assert result["state"] == "starting" and not result["ok"]
    assert app.runtime_file.read_bytes() == before
    assert all(record["unit"] in argv for argv in inspected)
    monkeypatch.setattr(service, "_run", lambda argv, **_: subprocess.CompletedProcess(
        argv, 0, "MainPID=0\nLoadState=loaded\nActiveState=failed\n", ""))
    result = app.control("stop", {})
    assert result["state"] == "stopped" and result["ok"]
    assert not app.runtime_file.exists()


def test_windows_exit_during_termination_uses_the_same_handle_and_only_accepts_known_exit(monkeypatch):
    import ctypes
    from types import SimpleNamespace
    from unittest.mock import Mock

    import pytest

    import lixity.service as service

    monkeypatch.delattr(service.os, "pidfd_open", raising=False)
    monkeypatch.setattr(service.sys, "platform", "win32")

    def times(handle, created, *_):
        assert handle == 101
        created._obj.dwLowDateTime = 42
        return True

    def exited(handle, code):
        assert handle == 101
        code._obj.value = 0
        return True

    kernel = SimpleNamespace(OpenProcess=Mock(return_value=101), GetProcessTimes=Mock(side_effect=times),
        TerminateProcess=Mock(return_value=False), GetExitCodeProcess=Mock(side_effect=exited), CloseHandle=Mock())
    monkeypatch.setattr(ctypes, "WinDLL", lambda *_args, **_kwargs: kernel, raising=False)
    service._signal_process(12345, 15, "windows:42", "a" * 64)
    kernel.OpenProcess.assert_called_once()
    kernel.TerminateProcess.assert_called_once_with(101, 0)
    kernel.CloseHandle.assert_called_once_with(101)

    def still_running(handle, code):
        code._obj.value = 259
        return True

    kernel.GetExitCodeProcess.side_effect = still_running
    with pytest.raises(service.ServiceError, match="Cannot terminate"):
        service._signal_process(12345, 15, "windows:42", "a" * 64)
