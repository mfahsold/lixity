"""Security and lifecycle contract tests for the authenticated desktop loopback mode."""

from __future__ import annotations

import io
import json
import os
import secrets
import subprocess
import sys
import threading
from contextlib import redirect_stderr

import pytest

from lixity import __version__, log
from lixity.server.desktop import (
    DESKTOP_ENV_SCHEMA,
    DESKTOP_READY_SCHEMA,
    DESKTOP_SECRET_HEADER,
    DESKTOP_SESSION_COOKIE,
    DesktopSession,
)
from tests.support import LoopbackServer, make_handler, send


def _fresh_tokens() -> tuple[str, str]:
    return secrets.token_urlsafe(32), secrets.token_urlsafe(32)


def test_desktop_session_from_stdin_validates_strict_envelope():
    secret, nonce = _fresh_tokens()
    stream = io.StringIO(
        json.dumps({"secret": secret, "handshake_nonce": nonce, "parent_pid": os.getpid()}) + "\n"
    )
    session = DesktopSession.from_stdin(stream)
    assert session.parent_pid == os.getpid()
    assert session.is_host_secret({DESKTOP_SECRET_HEADER: secret})
    assert not session.is_host_secret({DESKTOP_SECRET_HEADER: "wrong" * 10})


@pytest.mark.parametrize(
    "raw,match",
    [
        ("", "requires bootstrap JSON"),
        ("x" * 5000 + "\n", "exceeds size limit"),
        ("{invalid\n", "valid JSON"),
        ("[]\n", "JSON object"),
        (json.dumps({"secret": "a" * 40, "handshake_nonce": "b" * 40, "extra": 1}) + "\n", "unsupported fields"),
        (json.dumps({"secret": "short", "handshake_nonce": "b" * 40}) + "\n", "secret"),
        (json.dumps({"secret": "a" * 40, "handshake_nonce": "bad space " * 4}) + "\n", "handshake_nonce"),
        (json.dumps({"secret": "a" * 40, "handshake_nonce": "b" * 40, "parent_pid": True}) + "\n", "parent_pid"),
        (json.dumps({"secret": "a" * 40, "handshake_nonce": "b" * 40, "parent_pid": 0}) + "\n", "parent_pid"),
    ],
)
def test_desktop_session_from_stdin_rejects_malformed_inputs(raw, match):
    with pytest.raises(ValueError, match=match):
        DesktopSession.from_stdin(io.StringIO(raw))


@pytest.mark.parametrize(
    "raw_next,expected",
    [
        (None, "/"),
        ("", "/"),
        ("/", "/"),
        ("/w/" + "a" * 32 + "/", "/w/" + "a" * 32 + "/"),
    ],
)
def test_validate_next_path_accepts_safe_targets(raw_next, expected):
    assert DesktopSession.validate_next_path(raw_next) == expected


@pytest.mark.parametrize(
    "bad_next",
    [
        "https://example.com/",
        "//example.com/",
        "/api/settings",
        "/w/not-hex/",
        "/w/" + "a" * 32 + "/api/settings",
    ],
)
def test_validate_next_path_rejects_open_redirects(bad_next):
    with pytest.raises(ValueError, match="Invalid desktop handshake destination"):
        DesktopSession.validate_next_path(bad_next)


def test_normal_mode_hides_desktop_routes_and_keeps_strict_csp(tmp_path):
    handler = make_handler(
        tmp_path,
        dashboard_html="<!doctype html><script>void 0;</script><title>Synthetic</title>",
    )
    with LoopbackServer(handler) as server:
        assert server.request("/_desktop/handshake?nonce=" + "a" * 40).status == 404
        assert server.request("/_desktop/nonce", method="POST", body=b"{}").status == 404

        page = server.request("/")
        assert page.status == 200
        csp = page.headers["content-security-policy"]
        assert "connect-src 'self';" in csp
        assert "ipc.localhost" not in csp

        status, env = server.request_json("/api/desktop/environment")
        assert status == 200
        assert env["ok"] is True
        assert env["schema_version"] == DESKTOP_ENV_SCHEMA
        assert env["app"]["desktop_mode"] is False
        assert env["app"]["version"] == __version__
        assert env["zotero"] == {"checked": False, "available": None}
        assert all(isinstance(v, bool) for v in env["tools"].values())


def test_desktop_mode_requires_handshake_cookie_or_host_secret(tmp_path):
    secret, nonce = _fresh_tokens()
    session = DesktopSession(secret=secret, handshake_nonce=nonce)
    handler = make_handler(
        tmp_path,
        dashboard_html="<!doctype html><script>void 0;</script><title>Desktop</title>",
    )
    with LoopbackServer(handler) as server:
        server._server.desktop_session = session

        # Unauthenticated clients are blocked everywhere.
        assert server.request("/").status == 403
        assert server.request("/api").status == 403
        assert server.request("/api/desktop/environment").status == 403
        assert server.request("/api/settings", payload={}).status == 403

        # Open-redirect destination is rejected before consuming the valid nonce.
        bad_redirect = server.request(f"/_desktop/handshake?nonce={nonce}&next=https://evil.example/")
        assert bad_redirect.status == 400

        # Valid single-use handshake succeeds and issues an HttpOnly SameSite=Strict cookie.
        handshake = server.request(f"/_desktop/handshake?nonce={nonce}")
        assert handshake.status == 303
        assert handshake.headers["location"] == "/"
        cookie_header = handshake.headers["set-cookie"]
        assert f"{DESKTOP_SESSION_COOKIE}=" in cookie_header
        assert "HttpOnly" in cookie_header
        assert "SameSite=Strict" in cookie_header

        # Replaying the consumed nonce is forbidden.
        assert server.request(f"/_desktop/handshake?nonce={nonce}").status == 403

        # Cookie authorizes dashboard and API calls, and enables Tauri IPC connect-src.
        cookie_pair = cookie_header.split(";", 1)[0]
        page = server.request("/", headers={"Cookie": cookie_pair})
        assert page.status == 200
        csp = page.headers["content-security-policy"]
        assert "script-src 'nonce-" in csp
        assert "connect-src 'self' ipc: http://ipc.localhost https://ipc.localhost;" in csp

        status, env = server.request_json("/api/desktop/environment", headers={"Cookie": cookie_pair})
        assert status == 200
        assert env["app"]["desktop_mode"] is True

        # Only the host secret may mint additional window nonces; cookie alone is rejected.
        assert server.request("/_desktop/nonce", method="POST", headers={"Cookie": cookie_pair}).status == 403
        minted = server.request(
            "/_desktop/nonce",
            method="POST",
            headers={DESKTOP_SECRET_HEADER: secret},
        )
        assert minted.status == 200
        second_nonce = minted.json["nonce"]
        workspace_next = "/w/" + "f" * 32 + "/"
        second_handshake = server.request(
            f"/_desktop/handshake?nonce={second_nonce}&next={workspace_next}"
        )
        assert second_handshake.status == 303
        assert second_handshake.headers["location"] == workspace_next


def test_desktop_debug_logging_never_leaks_handshake_nonce(tmp_path):
    secret, nonce = _fresh_tokens()
    session = DesktopSession(secret=secret, handshake_nonce=nonce)
    log.configure(level="DEBUG", force=True)
    try:
        handler = make_handler(
            tmp_path,
            debug=True,
            dashboard_html="<!doctype html><title>Debug</title>",
        )
        with LoopbackServer(handler) as server:
            server._server.desktop_session = session
            output = io.StringIO()
            with redirect_stderr(output):
                res = server.request(f"/_desktop/handshake?nonce={nonce}")
            assert res.status == 303
            logged = output.getvalue()
            assert nonce not in logged
            assert "/_desktop/handshake" in logged
    finally:
        log.configure(level="INFO", force=True)


def test_parent_watchdog_triggers_shutdown_when_parent_gone(monkeypatch):
    secret, nonce = _fresh_tokens()
    session = DesktopSession(secret=secret, handshake_nonce=nonce, parent_pid=999_999)
    monkeypatch.setattr("lixity.server.desktop._pid_alive", lambda _pid: False)
    triggered = threading.Event()
    stop = threading.Event()
    thread = session.start_parent_watchdog(triggered.set, stop_event=stop, poll_interval=0.05)
    assert thread is not None
    assert triggered.wait(timeout=2.0)
    stop.set()
    thread.join(timeout=2.0)


def test_cli_serve_desktop_mode_end_to_end_subprocess(tmp_path):
    secret, nonce = _fresh_tokens()
    bootstrap = json.dumps({"secret": secret, "handshake_nonce": nonce}) + "\n"
    with subprocess.Popen(
        [
            sys.executable,
            "-m",
            "lixity",
            "serve",
            "--_desktop-mode",
            "--host",
            "127.0.0.1",
            "--port",
            "0",
        ],
        cwd=str(tmp_path),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    ) as proc:
        try:
            assert proc.stdin is not None and proc.stdout is not None
            proc.stdin.write(bootstrap)
            proc.stdin.flush()
            proc.stdin.close()

            ready_line = proc.stdout.readline()
            assert ready_line, f"Expected readiness JSON; stderr={proc.stderr.read() if proc.stderr else ''}"
            ready = json.loads(ready_line)
            assert ready["schema_version"] == DESKTOP_READY_SCHEMA
            assert ready["ready"] is True
            assert ready["host"] == "127.0.0.1"
            assert isinstance(ready["port"], int) and ready["port"] > 0
            assert ready["version"] == __version__

            port = ready["port"]
            # Unauthenticated request must fail with 403.
            denied = send(port, "/api/desktop/environment", timeout=5.0)
            assert denied.status == 403

            # Authenticated host-secret request succeeds.
            allowed = send(
                port,
                "/api/desktop/environment",
                headers={DESKTOP_SECRET_HEADER: secret},
                timeout=5.0,
            )
            assert allowed.status == 200
            assert allowed.json["app"]["desktop_mode"] is True
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=5)
