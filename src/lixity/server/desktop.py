"""Authenticated loopback session and environment diagnostics for the desktop host.

The desktop host (Rust/Tauri) starts Lixity on an ephemeral loopback port and
passes a per-launch secret plus initial single-use handshake nonce over stdin
(never CLI arguments). Every HTTP request in desktop mode requires either the
HttpOnly session cookie obtained through ``/_desktop/handshake`` or the host
secret header for privileged loopback operations (streaming downloads, minting
a nonce for an additional window).
"""

from __future__ import annotations

import hashlib
import hmac
import importlib.util
import json
import os
import platform
import re
import secrets
import shutil
import sys
import threading
from collections.abc import Callable, Mapping
from http.cookies import SimpleCookie
from typing import IO, Any

from .. import __version__
from ..research import api as research_api
from ..speech_status import native_worker_inventory

DESKTOP_SESSION_COOKIE = "lixity_desktop_session"
DESKTOP_SECRET_HEADER = "X-Lixity-Desktop-Secret"  # noqa: S105 - HTTP header name
DESKTOP_READY_SCHEMA = "lixity-desktop-ready/1"
DESKTOP_ENV_SCHEMA = "lixity-desktop-env/1"

_MAX_HANDSHAKE_STDIN_BYTES = 4096
_MAX_PENDING_NONCES = 16
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{32,256}$")
_NEXT_WORKSPACE_RE = re.compile(r"^/w/[0-9a-f]{32}/$")


def _validate_token(value: Any, name: str) -> str:
    if not isinstance(value, str) or not _TOKEN_RE.fullmatch(value):
        raise ValueError(f"Desktop {name} must be a 32-256 character ASCII token")
    return value


def _derive_session_cookie(secret: str) -> str:
    return hmac.new(
        secret.encode("ascii"),
        b"lixity-desktop-session/1",
        hashlib.sha256,
    ).hexdigest()


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        import ctypes

        process_query_limited = 0x1000
        still_active = 259
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.OpenProcess(process_query_limited, False, pid)
        if not handle:
            return False
        try:
            exit_code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                return False
            return int(exit_code.value) == still_active
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


class DesktopSession:
    """Per-launch desktop host authentication and parent-process guard."""

    def __init__(
        self,
        *,
        secret: str,
        handshake_nonce: str,
        parent_pid: int | None = None,
    ) -> None:
        self._secret = _validate_token(secret, "secret")
        initial_nonce = _validate_token(handshake_nonce, "handshake_nonce")
        if parent_pid is not None and (type(parent_pid) is not int or parent_pid <= 0):
            raise ValueError("Desktop parent_pid must be a positive integer")
        self.parent_pid: int | None = parent_pid
        self._cookie_value = _derive_session_cookie(self._secret)
        self._lock = threading.Lock()
        self._pending_nonces: list[str] = [initial_nonce]

    @classmethod
    def from_stdin(cls, stream: IO[str] | None = None) -> DesktopSession:
        """Read one bounded JSON bootstrap line from stdin."""
        source = sys.stdin if stream is None else stream
        raw = source.readline(_MAX_HANDSHAKE_STDIN_BYTES + 1)
        if not raw:
            raise ValueError("Desktop mode requires bootstrap JSON on stdin")
        if len(raw.encode("utf-8")) > _MAX_HANDSHAKE_STDIN_BYTES:
            raise ValueError("Desktop bootstrap payload exceeds size limit")
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            raise ValueError("Desktop bootstrap payload must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("Desktop bootstrap payload must be a JSON object")
        unknown = set(payload) - {"secret", "handshake_nonce", "parent_pid"}
        if unknown:
            raise ValueError("Desktop bootstrap payload contains unsupported fields")
        raw_parent = payload.get("parent_pid")
        if raw_parent is not None and (type(raw_parent) is not int or raw_parent <= 0):
            raise ValueError("Desktop parent_pid must be a positive integer")
        return cls(
            secret=_validate_token(payload.get("secret"), "secret"),
            handshake_nonce=_validate_token(payload.get("handshake_nonce"), "handshake_nonce"),
            parent_pid=raw_parent,
        )

    def is_host_secret(self, headers: Mapping[str, str]) -> bool:
        """True only when the privileged desktop-host secret header matches."""
        supplied = headers.get(DESKTOP_SECRET_HEADER)
        if not isinstance(supplied, str) or not supplied:
            return False
        return hmac.compare_digest(supplied, self._secret)

    def has_session_cookie(self, headers: Mapping[str, str]) -> bool:
        """True when the request carries the valid HttpOnly desktop session cookie."""
        raw_cookie = headers.get("Cookie")
        if not isinstance(raw_cookie, str) or not raw_cookie:
            return False
        jar: SimpleCookie = SimpleCookie()
        try:
            jar.load(raw_cookie)
        except ValueError:
            return False
        morsel = jar.get(DESKTOP_SESSION_COOKIE)
        if morsel is None:
            return False
        return hmac.compare_digest(morsel.value, self._cookie_value)

    def is_authorized(self, headers: Mapping[str, str]) -> bool:
        """True when either the desktop session cookie or host secret matches."""
        return self.is_host_secret(headers) or self.has_session_cookie(headers)

    def issue_handshake_nonce(self) -> str:
        """Mint one bounded single-use handshake nonce for another desktop window."""
        nonce = secrets.token_urlsafe(32)
        with self._lock:
            self._pending_nonces.append(nonce)
            if len(self._pending_nonces) > _MAX_PENDING_NONCES:
                self._pending_nonces = self._pending_nonces[-_MAX_PENDING_NONCES:]
        return nonce

    def consume_handshake(self, nonce: str | None) -> str | None:
        """Consume a pending single-use nonce and return the session cookie value."""
        if not isinstance(nonce, str) or not _TOKEN_RE.fullmatch(nonce):
            return None
        with self._lock:
            matched_index: int | None = None
            for index, candidate in enumerate(self._pending_nonces):
                if hmac.compare_digest(nonce, candidate):
                    matched_index = index
            if matched_index is None:
                return None
            self._pending_nonces.pop(matched_index)
            return self._cookie_value

    def session_cookie_header(self) -> str:
        """Build the strict loopback Set-Cookie header value."""
        return (
            f"{DESKTOP_SESSION_COOKIE}={self._cookie_value}; "
            "HttpOnly; SameSite=Strict; Path=/"
        )

    @staticmethod
    def validate_next_path(raw_next: str | None) -> str:
        """Allow only root or an explicit workspace prefix as a post-handshake target."""
        if raw_next is None or raw_next in ("", "/"):
            return "/"
        if _NEXT_WORKSPACE_RE.fullmatch(raw_next):
            return raw_next
        raise ValueError("Invalid desktop handshake destination")

    @staticmethod
    def ready_payload(host: str, port: int) -> dict[str, Any]:
        """Structured readiness envelope emitted once after the loopback socket binds."""
        return {
            "schema_version": DESKTOP_READY_SCHEMA,
            "ready": True,
            "host": host,
            "port": port,
            "version": __version__,
        }

    def start_parent_watchdog(
        self,
        shutdown_callback: Callable[[], None],
        *,
        stop_event: threading.Event | None = None,
        poll_interval: float = 1.0,
    ) -> threading.Thread | None:
        """Shut the loopback server down if the supervising desktop host exits."""
        parent_pid = self.parent_pid
        if parent_pid is None:
            return None
        stop = stop_event or threading.Event()
        interval = max(0.05, float(poll_interval))

        def _watch() -> None:
            while not stop.wait(interval):
                reparented = (
                    os.name != "nt"
                    and hasattr(os, "getppid")
                    and os.getppid() != parent_pid
                )
                if reparented or not _pid_alive(parent_pid):
                    shutdown_callback()
                    return

        thread = threading.Thread(target=_watch, name="lixity-desktop-watchdog", daemon=True)
        thread.start()
        return thread


def desktop_environment_summary(
    *,
    desktop_mode: bool = False,
    probe_zotero: bool = False,
    probe_ocr: bool = False,
) -> dict[str, Any]:
    """Return a content-free, path-redacted capability inventory for the desktop UI."""
    ocr_info = research_api.ocr_status(probe=probe_ocr)
    zotero_info: dict[str, Any]
    if probe_zotero:
        from ..research.zotero import connection_status

        zotero_info = dict(connection_status())
    else:
        zotero_info = {"checked": False, "available": None}
    return {
        "ok": True,
        "schema_version": DESKTOP_ENV_SCHEMA,
        "app": {
            "version": __version__,
            "python": platform.python_version(),
            "platform": sys.platform,
            "machine": platform.machine(),
            "desktop_mode": desktop_mode,
        },
        "tools": {
            "pdftotext": shutil.which("pdftotext") is not None,
            "pdftoppm": shutil.which("pdftoppm") is not None,
            "tesseract": shutil.which("tesseract") is not None,
            "ffmpeg": shutil.which("ffmpeg") is not None,
            "spacy": importlib.util.find_spec("spacy") is not None,
            "stanza": importlib.util.find_spec("stanza") is not None,
        },
        "ocr": ocr_info,
        "zotero": zotero_info,
        "audio_workers": native_worker_inventory(),
    }
