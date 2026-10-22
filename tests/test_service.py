"""Packaged lifecycle ownership and explicit startup configuration."""

import errno
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from lixity import __version__

pytestmark = pytest.mark.portability


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


def test_restart_discards_saved_title_when_switching_projects(tmp_path):
    from lixity.service import resolve_settings

    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    (first / "manuscript.md").write_text("Synthetic manuscript.\n", encoding="utf-8")
    saved = resolve_settings(8765, {"project": str(first), "title": "First title", "language": "de"}, None)
    assert resolve_settings(8765, {"project": str(first)}, saved)["title"] == "First title"
    assert resolve_settings(8765, {"project": str(first / "manuscript.md")}, saved)["title"] == "First title"
    changed = resolve_settings(8765, {"project": str(second)}, saved)
    assert changed.get("title") is None and changed["language"] == "de"
    assert resolve_settings(8765, {"no_project": True}, saved).get("title") is None
    explicit = resolve_settings(8765, {"project": str(second), "title": "Reviewed second title"}, saved)
    assert explicit["title"] == "Reviewed second title"


def test_corrupt_runtime_records_and_unknown_files_are_not_overwritten(tmp_path):
    from lixity.service import ServiceManager

    manager = ServiceManager(59980, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime",
                             backend="process", startup_timeout=0.2)
    manager.runtime_dir.mkdir(mode=0o700)
    manager.runtime_file.write_text('{"not":"a service record"}', encoding="utf-8")
    manager.runtime_file.chmod(0o600)
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


def test_systemd_unit_template_matches_the_managed_cli():
    unit = (Path(__file__).resolve().parents[1] / "scripts" / "lixity.service").read_text(encoding="utf-8")
    assert "Environment=LIXITY_PORT=8765" in unit
    assert "ExecStart=%h/.local/bin/lixity serve --no-project --host 127.0.0.1 --port ${LIXITY_PORT}" in unit
    assert "WantedBy=default.target" in unit
    assert "NoNewPrivileges=true" in unit


def _storage_snapshot(root):
    """Capture observable storage changes without counting read access times."""
    paths = [root, *sorted(root.rglob("*"))]
    return {
        str(path.relative_to(root)): (
            path.lstat().st_mode,
            path.lstat().st_mtime_ns,
            path.read_bytes() if path.is_file() else None,
        )
        for path in paths
    }


@pytest.mark.parametrize("missing", ("both", "state", "runtime"))
def test_status_does_not_create_missing_storage(tmp_path, monkeypatch, missing):
    import lixity.service as service

    monkeypatch.setattr(service, "_port_open", lambda *_: False)
    state, runtime = tmp_path / "state", tmp_path / "runtime"
    if missing == "state":
        runtime.mkdir(mode=0o700)
    elif missing == "runtime":
        state.mkdir(mode=0o700)
    before = _storage_snapshot(tmp_path)
    manager = service.ServiceManager(59979, state_dir=state, runtime_dir=runtime)
    result = manager.control("status", {})
    assert result["state"] == "stopped", result
    assert _storage_snapshot(tmp_path) == before


def test_status_does_not_open_or_wait_for_lifecycle_lock(tmp_path, monkeypatch):
    import time

    import pytest

    import lixity.service as service

    if sys.platform == "win32":
        pytest.skip("POSIX writer-lock contention fixture")
    state, runtime = tmp_path / "state", tmp_path / "runtime"
    state.mkdir(mode=0o700)
    runtime.mkdir(mode=0o700)
    lock = runtime / "service-59979.lock"
    lock.write_bytes(b"synthetic lock\n")
    lock.chmod(0o600)
    child = subprocess.Popen(  # noqa: S603 - disposable fixed Python lock holder
        [sys.executable, "-c", "import fcntl,sys,time; "
         "f=open(sys.argv[1], 'rb'); fcntl.flock(f, fcntl.LOCK_EX); "
         "print('locked', flush=True); time.sleep(30)", str(lock)],
        stdout=subprocess.PIPE, text=True,
    )
    try:
        assert child.stdout.readline().strip() == "locked"
        monkeypatch.setattr(service, "_port_open", lambda *_: False)
        opened = []
        original_open = service.os.open

        def observe_open(path, *args, **kwargs):
            if Path(path) == lock:
                opened.append(path)
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(service.os, "open", observe_open)
        before = _storage_snapshot(tmp_path)
        started = time.monotonic()
        result = service.ServiceManager(
            59979, state_dir=state, runtime_dir=runtime, lock_timeout=2,
        ).control("status", {})
        elapsed = time.monotonic() - started
        assert result["state"] == "stopped", result
        assert opened == []
        assert elapsed < 1, f"Status waited {elapsed:.3f}s for a lifecycle writer"
        assert _storage_snapshot(tmp_path) == before
    finally:
        child.terminate()
        child.wait(timeout=5)
        child.stdout.close()


def test_status_accepts_read_only_private_directories_without_writes(tmp_path, monkeypatch):
    import lixity.service as service

    state, runtime = tmp_path / "state", tmp_path / "runtime"
    state.mkdir(mode=0o500)
    runtime.mkdir(mode=0o500)
    monkeypatch.setattr(service, "_port_open", lambda *_: False)
    before = _storage_snapshot(tmp_path)
    manager = service.ServiceManager(59979, state_dir=state, runtime_dir=runtime)
    result = manager.control("status", {})
    assert result["state"] == "stopped", result
    assert _storage_snapshot(tmp_path) == before


def test_status_rejects_unsafe_directory_modes_without_repair(tmp_path, monkeypatch):
    import pytest

    import lixity.service as service

    if os.name == "nt":
        pytest.skip("POSIX private-directory modes")
    for name in ("state", "runtime"):
        root = tmp_path / name
        root.mkdir()
        state, runtime = root / "state", root / "runtime"
        state.mkdir(mode=0o700)
        runtime.mkdir(mode=0o700)
        (root / name).chmod(0o755)
        monkeypatch.setattr(service, "_port_open", lambda *_: False)
        before = _storage_snapshot(root)
        result = service.ServiceManager(59979, state_dir=state, runtime_dir=runtime).control("status", {})
        assert result["state"] == "unknown" and not result["ok"], result
        assert "private" in result["message"]
        assert _storage_snapshot(root) == before


def test_status_rejects_changed_directory_policy_without_repair(tmp_path, monkeypatch):
    import stat

    import pytest

    import lixity.service as service

    if os.name == "nt":
        pytest.skip("POSIX directory ownership and symlink policy")
    for policy in ("owner", "symlink", "file", "unreadable"):
        root = tmp_path / policy
        root.mkdir()
        state, runtime = root / "state", root / "runtime"
        state.mkdir(mode=0o700)
        runtime.mkdir(mode=0o700)
        manager = service.ServiceManager(59979, state_dir=state, runtime_dir=runtime)
        if policy == "symlink":
            runtime.rmdir()
            target = root / "target"
            target.mkdir(mode=0o700)
            runtime.symlink_to(target, target_is_directory=True)
        elif policy == "file":
            runtime.rmdir()
            runtime.write_bytes(b"synthetic non-directory")
        original_lstat = Path.lstat

        def inspect(path, *args, runtime=runtime, policy=policy, original_lstat=original_lstat, **kwargs):
            if path == runtime:
                if policy == "unreadable":
                    raise PermissionError(errno.EACCES, "synthetic directory denial")
                metadata = original_lstat(path, *args, **kwargs)
                if policy == "owner":
                    fields = list(metadata)
                    fields[4] = os.getuid() + 1
                    return os.stat_result(fields)
                return metadata
            return original_lstat(path, *args, **kwargs)

        monkeypatch.setattr(service, "_port_open", lambda *_: False)
        before = {path: original_lstat(path) for path in (state, runtime)}
        with monkeypatch.context() as scoped:
            scoped.setattr(Path, "lstat", inspect)
            result = manager.control("status", {})
        assert result["state"] == "unknown" and not result["ok"], (policy, result)
        assert result["message"]
        assert {path: original_lstat(path) for path in (state, runtime)} == before
        if policy == "symlink":
            assert stat.S_ISLNK(original_lstat(runtime).st_mode)


def _status_owned_fixture(tmp_path, monkeypatch):
    import lixity.service as service

    manager = service.ServiceManager(59979, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime")
    manager.state_dir.mkdir(mode=0o700, exist_ok=True)
    record = {"schema_version": "lixity-service-runtime/1", "port": manager.port,
        "token": "a" * 64, "pid": 12345, "birth": "original", "backend": "process",
        "unit": None, "ready": True, "version": __version__}
    service._write_json(manager.runtime_file, record)
    service._write_json(manager.ready_file, {"schema_version": "lixity-service-ready/1",
        "token": record["token"], "pid": record["pid"], "birth": record["birth"], "version": __version__})
    monkeypatch.setattr(service, "process_birth", lambda pid: "original" if pid == 12345 else "replacement")
    monkeypatch.setattr(service, "_has_marker", lambda *_: True)
    monkeypatch.setattr(service, "_port_open", lambda *_: True)
    return manager, record


def test_status_retries_a_demonstrable_record_replacement(tmp_path, monkeypatch):
    import lixity.service as service

    manager, record = _status_owned_fixture(tmp_path, monkeypatch)
    replacement = {**record, "token": "b" * 64, "pid": 12346, "birth": "replacement"}
    replaced = False

    def probe(*_):
        nonlocal replaced
        if not replaced:
            replaced = True
            service._write_json(manager.runtime_file, replacement)
        return True

    monkeypatch.setattr(service, "_port_open", probe)
    result = manager.control("status", {})
    assert result["state"] == "starting" and not result["ok"], result
    assert result["pid"] == 12346
    assert json.loads(manager.runtime_file.read_text()) == replacement


def test_status_does_not_accept_settings_replaced_during_probe(tmp_path, monkeypatch):
    import lixity.service as service

    manager, _ = _status_owned_fixture(tmp_path, monkeypatch)
    replacement = {"schema_version": "lixity-service-settings/1",
        "settings": {"port": manager.port, "host": "localhost", "project": None}}
    replaced = False

    def probe(*_):
        nonlocal replaced
        if not replaced:
            replaced = True
            service._write_json(manager.settings_file, replacement)
        return True

    monkeypatch.setattr(service, "_port_open", probe)
    result = manager.control("status", {})
    assert result["state"] == "running" and result["ok"], result
    assert result["url"] == "http://localhost:59979/"


def test_status_reports_disappearing_record_as_unknown(tmp_path, monkeypatch):
    import lixity.service as service

    manager, _ = _status_owned_fixture(tmp_path, monkeypatch)

    def probe(*_):
        manager.runtime_file.unlink()
        return True

    monkeypatch.setattr(service, "_port_open", probe)
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"], result
    assert "disappeared" in result["message"]


def test_status_reports_in_place_record_change_as_unknown(tmp_path, monkeypatch):
    import lixity.service as service

    manager, record = _status_owned_fixture(tmp_path, monkeypatch)

    def probe(*_):
        manager.runtime_file.write_text(json.dumps({**record, "pid": None}), encoding="utf-8")
        return True

    monkeypatch.setattr(service, "_port_open", probe)
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"], result
    assert "changed" in result["message"]


def test_status_bounds_record_replacement_retries(tmp_path, monkeypatch):
    import lixity.service as service

    manager, record = _status_owned_fixture(tmp_path, monkeypatch)
    probes = []

    def probe(*_):
        probes.append(True)
        service._write_json(manager.runtime_file, record)
        return True

    monkeypatch.setattr(service, "_port_open", probe)
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"], result
    assert "changed" in result["message"]
    assert 1 < len(probes) <= 3


def test_status_preserves_process_identity_measurement_errors(tmp_path, monkeypatch):
    import lixity.service as service

    manager, _ = _status_owned_fixture(tmp_path, monkeypatch)
    before = _storage_snapshot(tmp_path)

    def unavailable(*_):
        raise service.ServiceError("Synthetic process birth measurement unavailable")

    monkeypatch.setattr(service, "process_birth", unavailable)
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"], result
    assert "birth measurement unavailable" in result["message"]
    assert _storage_snapshot(tmp_path) == before


@pytest.mark.parametrize("kind", ("settings", "runtime"))
@pytest.mark.parametrize("fault", ("malformed", "unreadable"))
def test_status_keeps_record_read_failures_unknown(tmp_path, monkeypatch, kind, fault):
    import lixity.service as service

    manager, _ = _status_owned_fixture(tmp_path, monkeypatch)
    service._write_json(manager.settings_file, {"schema_version": "lixity-service-settings/1",
        "settings": {"port": manager.port, "host": "127.0.0.1", "project": None}})
    target = manager.settings_file if kind == "settings" else manager.runtime_file
    if fault == "malformed":
        target.write_bytes(b'{"synthetic incomplete record":')
    else:
        original_open = service.os.open

        def denied(path, *args, **kwargs):
            if Path(path) == target:
                raise PermissionError(errno.EACCES, "Synthetic managed record denial")
            return original_open(path, *args, **kwargs)

        monkeypatch.setattr(service.os, "open", denied)
    before = _storage_snapshot(tmp_path)
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"], result
    assert "unreadable" in result["message"] if fault == "malformed" else "denial" in result["message"]
    assert _storage_snapshot(tmp_path) == before


def test_status_rechecks_record_identity_when_open_races_replacement(tmp_path, monkeypatch):
    import lixity.service as service

    manager, record = _status_owned_fixture(tmp_path, monkeypatch)
    replacement = {**record, "token": "b" * 64, "pid": 12346, "birth": "replacement"}
    temporary = manager.runtime_dir / "replacement.json"
    service._write_json(temporary, replacement)
    original_open = service.os.open
    replaced = False

    def open_after_replacement(path, *args, **kwargs):
        nonlocal replaced
        if Path(path) == manager.runtime_file and not replaced:
            replaced = True
            os.replace(temporary, manager.runtime_file)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(service.os, "open", open_after_replacement)
    result = manager.control("status", {})
    assert result["state"] == "starting" and not result["ok"], result
    assert result["pid"] == 12346


def test_status_rejects_a_record_replaced_with_a_symlink_before_open(tmp_path, monkeypatch):
    import lixity.service as service

    manager, _ = _status_owned_fixture(tmp_path, monkeypatch)
    target = tmp_path / "synthetic-untrusted-record.json"
    target.write_text("{}", encoding="utf-8")
    link = tmp_path / "replacement-link"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("Creating symbolic links is unavailable on this host")
    original_open = service.os.open
    replaced = False

    def open_after_replacement(path, *args, **kwargs):
        nonlocal replaced
        if Path(path) == manager.runtime_file and not replaced:
            replaced = True
            os.replace(link, manager.runtime_file)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(service.os, "open", open_after_replacement)
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"], result
    assert manager.runtime_file.is_symlink()
    assert target.read_bytes() == b"{}"


def test_status_preserves_pending_systemd_ownership_without_writes(tmp_path, monkeypatch):
    import lixity.service as service

    manager = service.ServiceManager(59979, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime")
    token = "c" * 64
    service._write_json(manager.runtime_file, {"schema_version": "lixity-service-runtime/1",
        "port": manager.port, "token": token, "pid": None, "birth": None,
        "backend": "systemd", "unit": service._unit_name(manager.port, token), "version": __version__})
    monkeypatch.setattr(service.shutil, "which", lambda _: "/synthetic/systemctl")
    monkeypatch.setattr(service, "_port_open", lambda *_: False)
    monkeypatch.setattr(service, "_run", lambda argv, **_: subprocess.CompletedProcess(
        argv, 0, "MainPID=0\nLoadState=loaded\nActiveState=activating\n", ""))
    before = _storage_snapshot(tmp_path)
    result = manager.control("status", {})
    assert result["state"] == "starting" and not result["ok"], result
    assert "ownership registration" in result["message"]
    assert _storage_snapshot(tmp_path) == before


def test_status_reports_unmanaged_listener_without_creating_storage(tmp_path, monkeypatch):
    import lixity.service as service

    monkeypatch.setattr(service, "_port_open", lambda *_: True)
    before = _storage_snapshot(tmp_path)
    result = service.ServiceManager(59979, state_dir=tmp_path / "state", runtime_dir=tmp_path / "runtime").control("status", {})
    assert result["state"] == "busy" and not result["ok"], result
    assert "unmanaged process" in result["message"]
    assert _storage_snapshot(tmp_path) == before


def test_worker_registration_tolerates_atomic_same_token_record_replacement(tmp_path, monkeypatch):
    import lixity.service as service

    manager, record = _status_owned_fixture(tmp_path, monkeypatch)
    replacement = {**record, "pid": None, "birth": None}
    temporary = manager.runtime_dir / "replacement.json"
    service._write_json(temporary, replacement)
    original_open = service.os.open
    replaced = False

    def open_after_replacement(path, *args, **kwargs):
        nonlocal replaced
        if Path(path) == manager.runtime_file and not replaced:
            replaced = True
            os.replace(temporary, manager.runtime_file)
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(service.os, "open", open_after_replacement)
    monkeypatch.setenv("LIXITY_SERVICE_RECORD", str(manager.runtime_file))
    monkeypatch.setattr(service.signal, "signal", lambda *_: None)
    worker = service.ManagedServe(record["token"], manager.port)
    stored = json.loads(manager.runtime_file.read_text())
    assert stored["token"] == record["token"]
    assert stored["pid"] == worker.pid == os.getpid()
    assert stored["birth"] == worker.birth == "replacement"


def test_status_reports_directory_replacement_during_probe_as_unknown(tmp_path, monkeypatch):
    import lixity.service as service

    manager, _ = _status_owned_fixture(tmp_path, monkeypatch)

    def probe(*_):
        manager.runtime_dir.rename(tmp_path / "preserved-runtime")
        manager.runtime_dir.mkdir(mode=0o700)
        return True

    monkeypatch.setattr(service, "_port_open", probe)
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"], result
    assert "directories changed" in result["message"]
    assert list(manager.runtime_dir.iterdir()) == []
    assert (tmp_path / "preserved-runtime" / manager.runtime_file.name).is_file()


@pytest.mark.parametrize("replacement_check", (1, 2))
def test_status_retries_record_replacement_that_changes_open_inode_ctime(
    tmp_path, monkeypatch, replacement_check
):
    import lixity.service as service

    manager, record = _status_owned_fixture(tmp_path, monkeypatch)
    replacement = {**record, "token": "b" * 64, "pid": 12346, "birth": "replacement"}
    temporary = manager.runtime_dir / "replacement.json"
    service._write_json(temporary, replacement)
    initial = manager.runtime_file.stat()
    original_fstat = service.os.fstat
    reads = 0

    def replace_after_read(descriptor):
        nonlocal reads
        metadata = original_fstat(descriptor)
        if (metadata.st_dev, metadata.st_ino) == (initial.st_dev, initial.st_ino):
            reads += 1
            if reads == replacement_check:
                os.replace(temporary, manager.runtime_file)
                return original_fstat(descriptor)
        return metadata

    monkeypatch.setattr(service.os, "fstat", replace_after_read)
    result = manager.control("status", {})
    assert result["state"] == "starting" and not result["ok"], result
    assert result["pid"] == 12346


def test_record_read_does_not_turn_disappearance_after_replacement_into_absence(tmp_path, monkeypatch):
    import lixity.service as service

    manager, record = _status_owned_fixture(tmp_path, monkeypatch)
    temporary = manager.runtime_dir / "replacement.json"
    service._write_json(temporary, record)
    original_lstat = Path.lstat
    reads = 0

    def replace_then_remove(path, *args, **kwargs):
        nonlocal reads
        if path == manager.runtime_file:
            reads += 1
            if reads == 2:
                os.replace(temporary, path)
            elif reads == 3:
                path.unlink()
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", replace_then_remove)
    with pytest.raises(service.ServiceError, match="disappeared"):
        service._read_json(manager.runtime_file)


@pytest.mark.parametrize("disappearing", ("runtime_and_ready", "ready", "settings", "directory"))
def test_status_preserves_disappearance_uncertainty_across_outer_retries(
    tmp_path, monkeypatch, disappearing
):
    import lixity.service as service

    manager, record = _status_owned_fixture(tmp_path, monkeypatch)
    service._write_json(manager.settings_file, {"schema_version": "lixity-service-settings/1",
        "settings": {"port": manager.port, "host": "127.0.0.1", "project": None}})
    original_metadata = service._metadata
    original_inspect_dir = service._inspect_dir
    replaced = False
    removed = False
    replacement_observations = 0

    def probe(*_):
        nonlocal replaced
        if not replaced:
            service._write_json(manager.runtime_file, record)
            replaced = True
            return True
        return False

    def observe_record(path):
        nonlocal replacement_observations
        if path == manager.runtime_file and replaced:
            replacement_observations += 1
        return original_metadata(path)

    def observe_directory(path):
        nonlocal removed
        if path == manager.runtime_dir and replacement_observations and not removed:
            removed = True
            if disappearing == "directory":
                manager.runtime_dir.rename(tmp_path / "preserved-runtime")
            elif disappearing == "runtime_and_ready":
                manager.runtime_file.unlink()
                manager.ready_file.unlink()
            elif disappearing == "ready":
                manager.ready_file.unlink()
            else:
                manager.settings_file.unlink()
        return original_inspect_dir(path)

    monkeypatch.setattr(service, "_port_open", probe)
    monkeypatch.setattr(service, "_metadata", observe_record)
    monkeypatch.setattr(service, "_inspect_dir", observe_directory)
    result = manager.control("status", {})
    assert result["state"] == "unknown" and not result["ok"], result
    assert "changed" in result["message"] if disappearing == "directory" else "disappeared" in result["message"]
