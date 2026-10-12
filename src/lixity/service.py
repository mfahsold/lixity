"""One packaged controller for explicitly owned local dashboard processes.

Launch settings persist separately from process ownership. A child records
readiness only after its own HTTP socket is bound; another listener cannot make
a launch succeed. Runtime records and logs never contain manuscript text.
"""

from __future__ import annotations

import argparse
import base64
import contextlib
import errno
import json
import os
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from . import __version__
from .config import resolve_thresholds
from .workspace import discover

_OPTIONS = ("language", "title", "research_project", "debug", "open_browser", "z_mild",
            "z_strong", "fdr_q", "fdr_method", "min_chapters", "dim_threshold", "flag_min_severity")
_CHILDREN: dict[int, subprocess.Popen[bytes]] = {}


class ServiceError(ValueError):
    """An invalid or unverifiable lifecycle operation, without guessed ownership."""

    def __init__(self, message: str, state: str = "unknown") -> None:
        super().__init__(message)
        self.state = state


def _validate_settings(settings: Mapping[str, Any]) -> None:
    strings = ("project", "language", "title", "research_project", "fdr_method")
    if any(settings.get(key) is not None and not isinstance(settings[key], str) for key in strings):
        raise ServiceError("Launch setting strings are invalid")
    if any(isinstance(settings.get(key), str) and "\0" in settings[key] for key in strings):
        raise ServiceError("Launch settings must not contain NUL characters")
    if any(settings.get(key) is not None and type(settings[key]) is not bool for key in ("debug", "open_browser")):
        raise ServiceError("Launch setting switches must be booleans")
    if settings.get("language") is not None and settings["language"] not in ("auto", "de", "en", "fr", "es", "it", "pt", "nl", "generic"):
        raise ServiceError("Unknown startup language")
    if any(settings.get(key) is not None and type(settings[key]) is not int
           for key in ("min_chapters", "flag_min_severity")):
        raise ServiceError("Startup chapter/severity values must be integers")
    for key in ("z_mild", "z_strong", "fdr_q", "dim_threshold"):
        if settings.get(key) is not None and type(settings[key]) not in (int, float):
            raise ServiceError("Startup thresholds must be numbers")
    resolve_thresholds(project_config={}, z_mild=settings.get("z_mild"), z_strong=settings.get("z_strong"),
                       fdr_q=settings.get("fdr_q"), fdr_method=settings.get("fdr_method"),
                       min_chapters=settings.get("min_chapters"), flag_min_severity=settings.get("flag_min_severity"),
                       dim_score_threshold=settings.get("dim_threshold"))


def configure(parser: argparse.ArgumentParser) -> None:
    """Register the four managed lifecycle actions and explicit startup options."""
    parser.add_argument("action", choices=("start", "stop", "restart", "status"))
    parser.add_argument("project", nargs="?", help="Explicit project or manuscript for start/restart")
    parser.add_argument("--port", type=int, default=None, help="Port (default: LIXITY_PORT or 8765)")
    parser.add_argument("--host", default=None, help="Loopback host (default: LIXITY_HOST or 127.0.0.1)")
    parser.add_argument("--no-project", action="store_true", default=None, help="Start an empty workspace")
    parser.add_argument("--open", dest="open_browser", action="store_true", default=None)
    parser.add_argument("--language", choices=("auto", "de", "en", "fr", "es", "it", "pt", "nl", "generic"))
    parser.add_argument("--title")
    parser.add_argument("--research-project")
    parser.add_argument("--debug", action="store_true", default=None)
    parser.add_argument("--backend", choices=("auto", "process", "systemd"), default="auto",
                        help="auto prefers an available Linux systemd user manager")
    parser.add_argument("--json", action="store_true", help="Machine-readable lifecycle result")
    for flag in ("z-mild", "z-strong", "fdr-q", "dim-threshold"):
        parser.add_argument("--" + flag, type=float)
    parser.add_argument("--fdr-method", choices=("bh", "by"))
    parser.add_argument("--min-chapters", type=int)
    parser.add_argument("--flag-min-severity", type=int, choices=(1, 2, 3))


def _workspace_scope(selector: str | None) -> Path | None:
    """Use the shared file-to-workspace resolution without reading manuscript text."""
    if not selector:
        return None
    path = Path(selector).expanduser().resolve()
    return Path(discover(explicit=str(path)).root) if path.is_file() else path


def resolve_settings(port: int, overrides: Mapping[str, Any], saved: Mapping[str, Any] | None) -> dict[str, Any]:
    """Resolve explicit startup choices; a plain restart retains saved choices."""
    if not 1 <= port <= 65535:
        raise ServiceError("Port must be between 1 and 65535")
    settings: dict[str, Any] = dict(saved) if saved is not None else {
        "port": port, "host": os.environ.get("LIXITY_HOST") or "127.0.0.1",
        "project": os.environ.get("LIXITY_DIR") or None,
    }
    new_project = overrides.get("project")
    previous_project = settings.get("project")
    settings["port"] = port
    for key in ("host", "project", *_OPTIONS):
        if overrides.get(key) is not None:
            settings[key] = overrides[key]
    if overrides.get("no_project"):
        if overrides.get("project") is not None:
            raise ServiceError("Choose a project or --no-project, not both")
        settings["project"] = None
    if settings["host"] not in ("127.0.0.1", "localhost"):
        raise ServiceError("Only loopback hosts 127.0.0.1 and localhost are permitted")
    _validate_settings(settings)
    for key in ("project", "research_project"):
        if settings.get(key):
            settings[key] = str(Path(settings[key]).expanduser().resolve())
    changed_project = new_project is not None and _workspace_scope(settings.get("project")) != _workspace_scope(previous_project)
    if (changed_project or overrides.get("no_project")) and overrides.get("title") is None:
        settings.pop("title", None)
    if settings.get("min_chapters") is not None and settings["min_chapters"] < 2:
        raise ServiceError("--min-chapters must be at least 2")
    return settings


def worker_argv(settings: Mapping[str, Any], token: str) -> list[str]:
    """Invoke this installation, preserving every user value as one argument."""
    argv = [sys.executable, "-m", "lixity", "serve",
            f"--host={settings['host']}", f"--port={settings['port']}"]
    if settings.get("project"):
        argv.append(str(settings["project"]))
    else:
        argv.append("--no-project")
    for key in _OPTIONS:
        value = settings.get(key)
        if key == "open_browser" or value is None:
            continue
        if key == "debug":
            if value:
                argv.append("--debug")
        else:
            argv.append(f"--{key.replace('_', '-')}={value}")
    argv.append("--_service-token=" + token)
    return argv


def _private_dir(path: Path) -> None:
    if path.is_symlink():
        raise ServiceError("Managed state directories must not be symbolic links")
    path.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name != "nt":
        if path.stat().st_uid != os.getuid():
            raise ServiceError("Managed state directory belongs to another user")
        path.chmod(0o700)


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists() and not path.is_symlink():
        return None
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or path.is_symlink():
        raise ServiceError("Managed record is not a regular file")
    if os.name != "nt" and (metadata.st_uid != os.getuid() or metadata.st_mode & 0o077):
        raise ServiceError("Managed record must be private to the current user")
    with path.open("rb") as handle:
        raw = handle.read(65537)
    if len(raw) > 65536:
        raise ServiceError("Managed record exceeds its size limit")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise ServiceError("Managed record is unreadable; preserve it for inspection") from exc
    if not isinstance(value, dict):
        raise ServiceError("Managed record must be a JSON object")
    return value


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    _private_dir(path.parent)
    if path.is_symlink():
        raise ServiceError("Managed records must not be symbolic links")
    fd, temporary = tempfile.mkstemp(prefix=".service-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(value, handle, ensure_ascii=False, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            Path(temporary).unlink()


def _run(argv: Sequence[str], *, timeout: float = 5,
         env: Mapping[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603 - fixed OS utilities and validated argument arrays
        list(argv), capture_output=True, text=True, timeout=timeout, check=False, env=env,
    )


def process_birth(pid: int) -> str | None:
    """Return a process birth identity; unreadable is an error, not absence."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return None
            raise ServiceError("Cannot inspect the recorded Windows process")
        try:
            kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                              ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
                                              ctypes.POINTER(wintypes.FILETIME))
            kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
            code = wintypes.DWORD()
            if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)):
                raise ServiceError("Cannot inspect the recorded Windows process state")
            if code.value != 259:
                return None
            created, exited, user, system = (wintypes.FILETIME() for _ in range(4))
            if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                          ctypes.byref(user), ctypes.byref(system)):
                raise ServiceError("Cannot determine the recorded Windows process birth")
            return f"windows:{(created.dwHighDateTime << 32) | created.dwLowDateTime}"
        finally:
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError as exc:
        raise ServiceError("Cannot inspect the recorded process") from exc
    if sys.platform.startswith("linux"):
        try:
            parts = Path(f"/proc/{pid}/stat").read_text().rpartition(")")[2].split()
            if parts[0] in ("Z", "X"):
                return None
            boot = Path("/proc/sys/kernel/random/boot_id").read_text().strip()
            return f"linux:{boot}:{parts[19]}"
        except FileNotFoundError as exc:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                return None
            raise ServiceError("Cannot determine the live recorded process birth") from exc
        except (OSError, IndexError) as exc:
            raise ServiceError("Cannot determine the recorded process birth") from exc
    ps = shutil.which("ps")
    if not ps:
        raise ServiceError("Process birth inspection requires ps on this platform")
    result = _run([ps, "-ww", "-p", str(pid), "-o", "lstart=", "-o", "stat="],
                  env={"LC_ALL": "C", "TZ": "UTC"})
    if result.returncode != 0 or not result.stdout.strip():
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return None
        raise ServiceError("Cannot determine the live recorded process birth")
    line = result.stdout.strip()
    if line[24:].strip().startswith("Z"):
        return None
    return "posix:" + line[:24]


def _has_marker(pid: int, token: str) -> bool:
    marker = "--_service-token=" + token
    if sys.platform.startswith("linux"):
        try:
            args = Path(f"/proc/{pid}/cmdline").read_bytes().rstrip(b"\0").split(b"\0")
            return bool(args and args[-1] == marker.encode())
        except FileNotFoundError:
            return False
        except OSError as exc:
            raise ServiceError("Cannot verify the recorded process command") from exc
    if sys.platform == "win32":
        powershell = shutil.which("powershell.exe") or shutil.which("pwsh.exe")
        if not powershell:
            raise ServiceError("Windows ownership inspection requires PowerShell")
        command = (f'$line=(Get-CimInstance Win32_Process -Filter "ProcessId={pid}").CommandLine;'
                   '[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes([string]$line))')
        result = _run([powershell, "-NoProfile", "-NonInteractive", "-Command", command])
        if result.returncode != 0 or not result.stdout.strip():
            raise ServiceError("Cannot verify the recorded Windows process command")
        import ctypes
        from ctypes import wintypes

        try:
            text = base64.b64decode(result.stdout.strip(), validate=True).decode("utf-16-le")
        except (ValueError, UnicodeError) as exc:
            raise ServiceError("Cannot decode the recorded Windows process command") from exc
        shell = ctypes.WinDLL("shell32", use_last_error=True)
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        shell.CommandLineToArgvW.argtypes = (wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int))
        shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
        count = ctypes.c_int()
        values = shell.CommandLineToArgvW(text, ctypes.byref(count))
        if not values:
            raise ServiceError("Cannot parse the recorded Windows argument boundaries")
        try:
            return bool(count.value and values[count.value - 1] == marker)
        finally:
            kernel.LocalFree.argtypes = (wintypes.HLOCAL,)
            kernel.LocalFree(values)
    elif sys.platform == "darwin":
        import ctypes

        library = ctypes.CDLL(None, use_errno=True)
        name = (ctypes.c_int * 3)(1, 49, pid)  # CTL_KERN, KERN_PROCARGS2, owned PID
        length = ctypes.c_size_t()
        if library.sysctl(name, 3, None, ctypes.byref(length), None, 0) != 0 or not 4 <= length.value <= 1024 * 1024:
            raise ServiceError("Cannot inspect the recorded macOS argument boundaries")
        buffer = ctypes.create_string_buffer(length.value)
        if library.sysctl(name, 3, buffer, ctypes.byref(length), None, 0) != 0:
            raise ServiceError("Cannot inspect the recorded macOS arguments")
        count = int.from_bytes(buffer.raw[:4], sys.byteorder)
        position = buffer.raw.find(b"\0", 4) + 1  # skip executable path and alignment padding
        while position < length.value and buffer.raw[position] == 0:
            position += 1
        args = []
        for _ in range(count):
            end = buffer.raw.find(b"\0", position)
            if end < position:
                raise ServiceError("The recorded macOS argument vector is incomplete")
            args.append(buffer.raw[position:end])
            position = end + 1
        # Environment bytes after argc arguments are neither decoded nor retained.
        return bool(args and args[-1] == marker.encode())
    else:
        ps = shutil.which("ps")
        if not ps:
            raise ServiceError("Process ownership inspection requires ps")
        result = _run([ps, "-ww", "-p", str(pid), "-o", "command="], env={"LC_ALL": "C", "TZ": "UTC"})
    if result.returncode != 0 or not result.stdout.strip():
        raise ServiceError("Cannot verify the recorded process command")
    return result.stdout.rstrip().endswith(" " + marker)


def _signal_process(pid: int, number: int, birth: str, token: str | None = None) -> None:
    """Recheck identity immediately before signalling, using pidfd where available."""
    if hasattr(os, "pidfd_open") and hasattr(signal, "pidfd_send_signal"):
        try:
            descriptor = os.pidfd_open(pid)
        except ProcessLookupError:
            return
        except OSError as exc:
            if exc.errno not in (errno.ENOSYS, errno.ENOTSUP):
                raise
            if token is None:
                raise ServiceError("This kernel cannot signal a process with verified ownership") from exc
            if process_birth(pid) == birth and _has_marker(pid, token):
                with contextlib.suppress(ProcessLookupError):
                    os.kill(pid, number)
            return
        try:
            if process_birth(pid) == birth and (token is None or _has_marker(pid, token)):
                try:
                    signal.pidfd_send_signal(descriptor, number)
                except ProcessLookupError:
                    return
                except OSError as exc:
                    if exc.errno not in (errno.ENOSYS, errno.ENOTSUP):
                        raise
                    if token is None:
                        raise ServiceError("This kernel cannot signal a process with verified ownership") from exc
                    if process_birth(pid) == birth and _has_marker(pid, token):
                        with contextlib.suppress(ProcessLookupError):
                            os.kill(pid, number)
        finally:
            os.close(descriptor)
    elif sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        handle = kernel.OpenProcess(0x1001, False, pid)
        if not handle:
            if ctypes.get_last_error() == 87:
                return
            raise ServiceError("Cannot open the owned Windows process for termination")
        try:
            kernel.GetProcessTimes.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.FILETIME),
                                              ctypes.POINTER(wintypes.FILETIME), ctypes.POINTER(wintypes.FILETIME),
                                              ctypes.POINTER(wintypes.FILETIME))
            created, exited, user, system = (wintypes.FILETIME() for _ in range(4))
            if not kernel.GetProcessTimes(handle, ctypes.byref(created), ctypes.byref(exited),
                                          ctypes.byref(user), ctypes.byref(system)):
                raise ServiceError("Cannot verify the owned Windows process before termination")
            current = f"windows:{(created.dwHighDateTime << 32) | created.dwLowDateTime}"
            if current == birth:
                kernel.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
                if not kernel.TerminateProcess(handle, 0):
                    kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
                    code = wintypes.DWORD()
                    if not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259:
                        raise ServiceError("Cannot terminate the owned Windows process")
        finally:
            kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
            kernel.CloseHandle(handle)
    elif process_birth(pid) == birth and token is not None and _has_marker(pid, token):
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, number)


def _port_open(host: str, port: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout=0.2):
            return True
    except OSError:
        return False


def _unit_name(port: int, token: str) -> str:
    return f"lixity-managed-{port}-{token[:16]}.service"


def _runtime_record(path: Path, port: int) -> dict[str, Any] | None:
    record = _read_json(path)
    if record is None:
        return None
    if (record.get("schema_version") != "lixity-service-runtime/1" or record.get("port") != port
            or not isinstance(record.get("token"), str) or not re.fullmatch(r"[0-9a-f]{64}", record["token"])
            or record.get("backend") not in ("process", "systemd")
            or (record.get("pid") is not None and (type(record["pid"]) is not int or not 0 < record["pid"] <= 2**31 - 1))
            or (record.get("birth") is not None and not isinstance(record["birth"], str))
            or (record["backend"] == "process" and record.get("unit") is not None)
            or (record["backend"] == "systemd" and record.get("unit") != _unit_name(port, record["token"]))):
        raise ServiceError("Unrecognized managed process record; it was left unchanged")
    return record


def _locations() -> tuple[Path, Path]:
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        configured = os.environ.get("XDG_STATE_HOME")
        base = Path(configured) if configured and Path(configured).is_absolute() else Path.home() / ".local" / "state"
    state = Path(os.environ.get("LIXITY_SERVICE_STATE_DIR") or base / "lixity" / "service")
    configured_runtime = os.environ.get("XDG_RUNTIME_DIR")
    runtime_base = Path(configured_runtime) if configured_runtime and Path(configured_runtime).is_absolute() else state / "runtime"
    runtime = Path(os.environ.get("LIXITY_SERVICE_RUNTIME_DIR") or runtime_base / "lixity-service")
    return state, runtime


class ServiceManager:
    """Manage one port without adopting other processes or service managers."""

    def __init__(self, port: int, *, state_dir: Path | None = None, runtime_dir: Path | None = None,
                 backend: str = "auto", startup_timeout: float = 15, stop_timeout: float = 5,
                 lock_timeout: float = 3) -> None:
        if not 1 <= port <= 65535:
            raise ServiceError("Port must be between 1 and 65535")
        state, runtime = _locations()
        self.port, self.backend = port, backend
        state_path, runtime_path = (state_dir or state).expanduser(), (runtime_dir or runtime).expanduser()
        if state_path.is_symlink() or runtime_path.is_symlink():
            raise ServiceError("Managed state directories must not be symbolic links")
        self.state_dir, self.runtime_dir = state_path.resolve(), runtime_path.resolve()
        self.startup_timeout, self.stop_timeout, self.lock_timeout = startup_timeout, stop_timeout, lock_timeout
        _private_dir(self.state_dir)
        _private_dir(self.runtime_dir)
        self.runtime_file = self.runtime_dir / f"service-{port}.json"
        self.ready_file = self.runtime_dir / f"service-{port}.ready.json"
        self.settings_file = self.state_dir / f"service-{port}.json"
        self.log_file = self.state_dir / f"service-{port}.log"
        self.work_dir = self.state_dir / f"workspace-{port}"

    @contextlib.contextmanager
    def _locked(self) -> Iterator[None]:
        flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(self.runtime_dir / f"service-{self.port}.lock", flags, 0o600)
        deadline = time.monotonic() + self.lock_timeout
        try:
            if sys.platform == "win32" and os.fstat(descriptor).st_size == 0:
                os.write(descriptor, b"0")
            while True:
                try:
                    if sys.platform == "win32":
                        import msvcrt
                        os.lseek(descriptor, 0, os.SEEK_SET)
                        msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise ServiceError("Another lifecycle operation is busy; retry shortly", "busy") from exc
                    time.sleep(0.05)
            yield
        finally:
            if sys.platform == "win32":
                with contextlib.suppress(OSError):
                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _settings(self) -> dict[str, Any] | None:
        stored = _read_json(self.settings_file)
        if stored is None:
            return None
        if stored.get("schema_version") != "lixity-service-settings/1" or not isinstance(stored.get("settings"), dict):
            raise ServiceError("Unrecognized launch settings; they were left unchanged")
        settings = stored["settings"]
        if (settings.get("port") != self.port or settings.get("host") not in ("127.0.0.1", "localhost")
                or set(settings) - {"port", "host", "project", *_OPTIONS}):
            raise ServiceError("Invalid saved launch settings; they were left unchanged")
        if any(settings.get(key) is not None and not isinstance(settings[key], str)
               for key in ("project", "language", "title", "research_project", "fdr_method")):
            raise ServiceError("Invalid saved launch setting types; they were left unchanged")
        _validate_settings(settings)
        return dict(settings)

    def _unit_pid(self, record: Mapping[str, Any]) -> int:
        executable = shutil.which("systemctl")
        if not executable:
            raise ServiceError("The recorded user-service backend is unavailable")
        result = _run([executable, "--user", "show", str(record["unit"]), "--property=MainPID", "--value"])
        if result.returncode != 0:
            raise ServiceError("Cannot inspect the recorded user service")
        return int(result.stdout.strip() or "0")

    def _unit_has_no_child(self, record: Mapping[str, Any]) -> bool:
        executable = shutil.which("systemctl")
        if not executable:
            raise ServiceError("The recorded user-service backend is unavailable")
        result = _run([executable, "--user", "show", str(record["unit"]),
                       "--property=MainPID", "--property=LoadState", "--property=ActiveState"])
        if result.returncode != 0:
            raise ServiceError("Cannot determine whether the pending user service still owns a child")
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        return bool(values.get("MainPID") == "0" and
                    (values.get("LoadState") == "not-found" or values.get("ActiveState") in ("inactive", "failed")))

    def _owned(self, record: Mapping[str, Any]) -> bool:
        pid, birth = record.get("pid"), record.get("birth")
        if not pid or not birth or process_birth(pid) != birth:
            return False
        if not _has_marker(pid, str(record["token"])):
            return False
        return bool(record["backend"] != "systemd" or self._unit_pid(record) == pid)

    def _result(self, state: str, settings: Mapping[str, Any], record: Mapping[str, Any] | None = None,
                *, ok: bool = False, message: str = "") -> dict[str, Any]:
        return {"schema_version": "lixity-service-local/1", "ok": ok, "state": state,
                "url": f"http://{settings['host']}:{self.port}/", "pid": record.get("pid") if record else None,
                "backend": record.get("backend") if record else None, "installed_version": __version__,
                "running_version": record.get("version") if record and state in ("running", "starting") else None,
                "log": str(self.log_file), "message": message}

    def _status(self, settings: Mapping[str, Any], *, expected_token: str | None = None) -> dict[str, Any]:
        record = _runtime_record(self.runtime_file, self.port)
        if expected_token is not None and (record is None or record["token"] != expected_token):
            return self._result("stopped", settings,
                                message="This launch was superseded by another lifecycle operation")
        pending = bool(record and (record.get("pid") is None or
                       (record.get("birth") is None and process_birth(record["pid"]) is not None)))
        if pending and record and record["backend"] == "systemd" and self._unit_has_no_child(record):
            pending = False
        if pending:
            return self._result("starting", settings, record,
                                message="Launch is awaiting ownership registration; its record was retained")
        if record and self._owned(record):
            ready = _read_json(self.ready_file)
            listening = bool(ready and ready.get("schema_version") == "lixity-service-ready/1"
                             and ready.get("token") == record["token"] and ready.get("pid") == record["pid"]
                             and ready.get("birth") == record["birth"] and _port_open(str(settings["host"]), self.port))
            state = "running" if listening else "starting"
            return self._result(state, settings, record, ok=listening,
                                message="Lixity is running" if listening else "Owned Lixity process is still starting")
        if _port_open(str(settings["host"]), self.port):
            return self._result("busy", settings, message="Port is occupied by an unmanaged process; it will not be stopped")
        return self._result("stopped", settings, message="Lixity is stopped")

    def _remove_ready(self, token: str) -> None:
        ready = _read_json(self.ready_file)
        if ready and ready.get("schema_version") == "lixity-service-ready/1" and ready.get("token") == token:
            self.ready_file.unlink()

    def _stop(self, settings: Mapping[str, Any]) -> dict[str, Any]:
        record = _runtime_record(self.runtime_file, self.port)
        if not record or not self._owned(record):
            result = self._status(settings)
            if result["state"] == "stopped":
                if record:
                    self._remove_ready(str(record["token"]))
                    self.runtime_file.unlink()
                result["ok"] = True
            return result
        pid, birth = int(record["pid"]), str(record["birth"])
        if record["backend"] == "systemd":
            executable = shutil.which("systemctl")
            if not executable or _run([executable, "--user", "stop", str(record["unit"])], timeout=10).returncode:
                raise ServiceError("Could not stop the owned user service")
        else:
            _signal_process(pid, signal.SIGTERM if os.name == "nt" else signal.SIGINT, birth, str(record["token"]))
        deadline = time.monotonic() + self.stop_timeout
        while process_birth(pid) == birth and time.monotonic() < deadline:
            time.sleep(0.05)
        if process_birth(pid) == birth:
            if record["backend"] == "systemd":
                raise ServiceError("The owned user service has not stopped")
            _signal_process(pid, signal.SIGTERM if os.name == "nt" else signal.SIGKILL, birth, str(record["token"]))
            time.sleep(0.1)
        if process_birth(pid) == birth:
            raise ServiceError("The owned process has not stopped")
        child = _CHILDREN.get(pid)
        if child is not None:
            child.wait(timeout=2)
        self._remove_ready(str(record["token"]))
        self.runtime_file.unlink()
        return self._result("stopped", settings, ok=True, message="Owned Lixity process stopped")

    def _systemd_available(self) -> bool:
        executable, runner = shutil.which("systemctl"), shutil.which("systemd-run")
        return bool(sys.platform.startswith("linux") and executable and runner
                    and _run([executable, "--user", "is-active", "default.target"]).returncode == 0
                    and "--expand-environment" in _run([runner, "--help"]).stdout)

    def _start(self, settings: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
        for key in ("project", "research_project"):
            if settings.get(key) and not Path(settings[key]).exists():
                raise ServiceError("Explicit startup project path does not exist")
        status = self._status(self._settings() or settings)
        if status["state"] in ("running", "starting", "busy"):
            return status, None
        previous = _runtime_record(self.runtime_file, self.port)
        if previous:
            self._remove_ready(str(previous["token"]))
        elif self.ready_file.exists():
            raise ServiceError("Orphan readiness record was left unchanged; inspect it before starting")
        token = secrets.token_hex(32)
        use_systemd = self.backend != "process" and self._systemd_available()
        if self.backend == "systemd" and not use_systemd:
            raise ServiceError("No usable systemd user manager is available")
        backend = "systemd" if use_systemd else "process"
        record: dict[str, Any] = {"schema_version": "lixity-service-runtime/1", "port": self.port,
            "token": token, "pid": None, "birth": None, "backend": backend,
            "unit": _unit_name(self.port, token) if use_systemd else None,
            "ready": False, "version": __version__}
        _private_dir(self.work_dir)
        if self.log_file.exists() and self._settings() is None:
            raise ServiceError("An unrecognized existing log was left unchanged")
        _write_json(self.settings_file, {"schema_version": "lixity-service-settings/1", "settings": settings})
        _write_json(self.runtime_file, record)
        argv = worker_argv(settings, token)
        package_parent = str(Path(__file__).resolve().parent.parent)
        inherited = [str(Path(part).expanduser().resolve()) for part in os.environ.get("PYTHONPATH", "").split(os.pathsep) if part]
        python_path = os.pathsep.join([package_parent, *inherited])
        environment = {**os.environ, "LIXITY_SERVICE_RECORD": str(self.runtime_file),
                       "PYTHONUNBUFFERED": "1", "PYTHONPATH": python_path}
        log_fd = os.open(self.log_file, os.O_CREAT | os.O_WRONLY | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0), 0o600)
        os.close(log_fd)
        if use_systemd:
            executable = shutil.which("systemd-run")
            if executable is None:
                raise ServiceError("The systemd-run executable disappeared before launch")
            command = [executable, "--user", "--quiet", "--collect", "--unit=" + str(record["unit"]),
                       "--property=Type=exec", "--property=KillMode=control-group", "--property=Restart=no",
                       "--expand-environment=no",
                       "--property=StandardOutput=append:" + str(self.log_file),
                       "--property=StandardError=append:" + str(self.log_file),
                       "--working-directory=" + str(self.work_dir),
                       "--setenv=LIXITY_SERVICE_RECORD=" + str(self.runtime_file), "--setenv=PYTHONUNBUFFERED=1",
                       "--setenv=PYTHONPATH=" + python_path]
            # Pass app environment by name; never serialize its values or place
            # OCR configuration/credentials in command-line arguments or records.
            command.extend("--setenv=" + key for key in os.environ
                           if key.startswith("LIXITY_") and key != "LIXITY_SERVICE_RECORD")
            command.extend(["--", *argv])
            if _run(command, timeout=10).returncode:
                latest = _runtime_record(self.runtime_file, self.port)
                if latest and latest["token"] == token and self._unit_has_no_child(latest):
                    self._remove_ready(token)
                    self.runtime_file.unlink()
                raise ServiceError("The managed user service failed to start; inspect the service log")
            pid = self._unit_pid(record)
        else:
            with self.log_file.open("ab") as log:
                options: dict[str, Any] = {"start_new_session": True}
                if sys.platform == "win32":
                    options = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS}
                try:
                    child = subprocess.Popen(  # noqa: S603 - current interpreter and validated argument array
                        argv, cwd=self.work_dir, env=environment, stdin=subprocess.DEVNULL,
                        stdout=log, stderr=log, **options,
                    )
                except (OSError, ValueError):
                    # Popen did not return a child: this is positively known
                    # failure, unlike an interrupted or timed-out publication.
                    pending = _runtime_record(self.runtime_file, self.port)
                    if pending and pending["token"] == token and pending.get("pid") is None:
                        self.runtime_file.unlink()
                    raise
            pid = child.pid
            _CHILDREN[pid] = child

            def reap() -> None:
                child.wait()
                _CHILDREN.pop(pid, None)

            threading.Thread(target=reap, daemon=True).start()
        if pid:
            birth = process_birth(pid)
            latest = _runtime_record(self.runtime_file, self.port)
            if latest and latest["token"] == token:
                latest.update(pid=pid, birth=birth)
                _write_json(self.runtime_file, latest)
        return self._result("starting", settings, record, message="Lixity is starting"), token

    def control(self, action: str, overrides: Mapping[str, Any]) -> dict[str, Any]:
        settings: dict[str, Any] = {"port": self.port, "host": "127.0.0.1", "project": None}
        try:
            if action not in ("start", "stop", "restart", "status"):
                raise ServiceError("Unknown lifecycle action")
            with self._locked():
                saved = self._settings()
                settings = resolve_settings(self.port, overrides, saved if action != "start" else None)
                if action == "status":
                    return self._status(saved or settings)
                if action == "stop":
                    return self._stop(saved or settings)
                if action == "restart":
                    stopped = self._stop(saved or settings)
                    if not stopped["ok"]:
                        return stopped
                result, token = self._start(settings)
            if token is None:
                if result["state"] == "running" and overrides.get("open_browser"):
                    webbrowser.open(str(result["url"]))
                return result
            deadline = time.monotonic() + self.startup_timeout
            while time.monotonic() < deadline:
                result = self._status(settings, expected_token=token)
                if result["state"] != "starting":
                    break
                time.sleep(0.1)
            if result["state"] == "running" and settings.get("open_browser"):
                webbrowser.open(str(result["url"]))
            if result["state"] == "stopped" and "superseded" not in result["message"]:
                result["message"] = "Managed server exited during startup; inspect the service log"
            return result
        except (ServiceError, OSError, ValueError, subprocess.SubprocessError) as exc:
            return self._result(exc.state if isinstance(exc, ServiceError) else "unknown", settings,
                                message=str(exc))


class ManagedServe:
    """Private child-side registration, readiness and signal setup."""

    def __init__(self, token: str, port: int) -> None:
        path = os.environ.get("LIXITY_SERVICE_RECORD")
        if not path:
            raise ServiceError("Managed launch record is missing")
        self.path, self.token, self.port = Path(path), token, port
        record = _runtime_record(self.path, port)
        if not record or record["token"] != token:
            raise ServiceError("Managed launch token does not match its private record")
        self.pid = os.getpid()
        self.birth = process_birth(self.pid)
        record.update(pid=self.pid, birth=self.birth)
        _write_json(self.path, record)
        if os.name != "nt":
            signal.signal(signal.SIGINT, signal.default_int_handler)
            signal.signal(signal.SIGTERM, signal.default_int_handler)

    def ready(self) -> None:
        record = _runtime_record(self.path, self.port)
        if record and record["token"] == self.token:
            path = self.path.with_name(f"service-{self.port}.ready.json")
            old = _read_json(path)
            if old and (old.get("schema_version") != "lixity-service-ready/1"
                        or old.get("token") != self.token):
                raise ServiceError("Unrecognized readiness file was left unchanged")
            _write_json(path, {
                "schema_version": "lixity-service-ready/1", "token": self.token,
                "pid": self.pid, "birth": self.birth, "version": __version__,
            })

    def close(self) -> None:
        ready_path = self.path.with_name(f"service-{self.port}.ready.json")
        with contextlib.suppress(ServiceError, OSError):
            ready = _read_json(ready_path)
            if ready and ready.get("token") == self.token and ready.get("pid") == self.pid:
                ready_path.unlink()


def run(args: argparse.Namespace) -> int:
    """Print a lifecycle result without interpreting project/source text."""
    try:
        port = args.port if args.port is not None else int(os.environ.get("LIXITY_PORT") or "8765")
        manager = ServiceManager(port, backend=args.backend)
        choices = {key: getattr(args, key, None) for key in ("host", "project", "no_project", *_OPTIONS)}
        result = manager.control(args.action, choices)
    except (ServiceError, OSError, ValueError) as exc:
        result = {"schema_version": "lixity-service-local/1", "ok": False, "state": "unknown", "message": str(exc)}
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        prefix = "[OK]" if result["ok"] else "[--]"
        print(f"{prefix} {result['message']}" + (f" → {result['url']}" if result.get("url") else ""))
        if result.get("log") and args.action in ("start", "restart"):
            print(f"Log: {result['log']}")
    return 0 if result["ok"] else 1
