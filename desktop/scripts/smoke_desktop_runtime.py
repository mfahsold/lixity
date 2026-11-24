#!/usr/bin/env python3
"""Verify an isolated Lixity desktop runtime bundle with zero host-Python leakage.

Runs CLI analysis and an end-to-end authenticated desktop-mode HTTP handshake
against the bundled Python interpreter under a stripped environment.
"""

from __future__ import annotations

import argparse
import http.client
import json
import os
import secrets
import subprocess
import tempfile
import time
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from typing import Any, TextIO

READY_TIMEOUT_SECONDS = 30.0
MAX_READY_CHARS = 4096


def _stripped_env() -> dict[str, str]:
    env: dict[str, str] = {"LC_ALL": "C.UTF-8"}
    if os.name == "nt":
        for key in ("SYSTEMROOT", "TEMP", "TMP", "USERPROFILE"):
            if key in os.environ:
                env[key] = os.environ[key]
    else:
        for key in ("HOME", "TMPDIR"):
            if key in os.environ:
                env[key] = os.environ[key]
        env["PATH"] = ""
    return env


def _bytecode_state(bundle_dir: Path) -> dict[Path, int]:
    return {path: path.stat().st_mtime_ns for path in bundle_dir.rglob("*.pyc")}


def _read_ready_line(stdout: TextIO, timeout: float = READY_TIMEOUT_SECONDS) -> str:
    result: Queue[str | OSError | ValueError] = Queue(maxsize=1)

    def read() -> None:
        try:
            result.put(stdout.readline(MAX_READY_CHARS + 1))
        except (OSError, ValueError) as exc:
            result.put(exc)

    Thread(target=read, name="lixity-bundle-ready", daemon=True).start()
    try:
        line = result.get(timeout=timeout)
    except Empty:
        raise TimeoutError(f"Desktop server did not report readiness within {timeout:g}s") from None
    if isinstance(line, Exception):
        raise line
    if not line:
        raise RuntimeError("Desktop server exited before reporting readiness")
    if len(line) > MAX_READY_CHARS or not line.endswith("\n"):
        raise ValueError("Desktop server emitted an incomplete or oversized readiness frame")
    return line


def _http_request(
    port: int,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    body: bytes | None = None,
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10.0)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


def verify_bundle(bundle_dir: Path) -> dict[str, Any]:
    bundle_dir = bundle_dir.resolve()
    manifest_path = bundle_dir / "runtime-bundle-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing runtime-bundle-manifest.json in {bundle_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    python_exe = (bundle_dir / manifest["python_relpath"]).resolve()
    if not python_exe.is_relative_to(bundle_dir):
        raise ValueError("Bundled Python executable resolves outside the runtime directory")
    if not python_exe.is_file():
        raise FileNotFoundError(f"Bundled Python executable missing: {python_exe}")

    python_command = [str(python_exe), "-I", "-B"]
    env = _stripped_env()
    bytecode_before = _bytecode_state(bundle_dir)
    probe = (
        "import sys\n"
        "from pathlib import Path\n"
        "import lixity\n"
        "assert sys.flags.isolated and sys.flags.dont_write_bytecode\n"
        "root = Path(sys.argv[1])\n"
        "for source in (sys.executable, sys.prefix, lixity.__file__):\n"
        "    assert Path(source).resolve().is_relative_to(root), 'Python or Lixity loaded outside the bundle'\n"
    )
    subprocess.run(  # noqa: S603 - explicit bundled interpreter
        [*python_command, "-c", probe, str(bundle_dir)],
        env=env,
        check=True,
        timeout=20,
    )

    # 1. Version check under stripped environment
    ver_proc = subprocess.run(  # noqa: S603 - explicit bundled interpreter
        [*python_command, "-m", "lixity", "--version"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
        timeout=20,
    )
    reported_version = ver_proc.stdout.strip()

    with tempfile.TemporaryDirectory(prefix="lixity-bundle-smoke-") as tmp:
        tmp_path = Path(tmp)
        test_home = tmp_path / "author-home"
        test_home.mkdir()
        env["USERPROFILE" if os.name == "nt" else "HOME"] = str(test_home)
        manuscript = tmp_path / "kapitel.md"
        manuscript.write_text(
            "# Kapitel 1\n\nDer Regen fiel leise auf das Pflaster. Mara blieb stehen.\n\n"
            "# Kapitel 2\n\nAm Hafen klapperte ein loses Brett im Wind.\n",
            encoding="utf-8",
        )

        # 2. Deterministic offline analysis check
        analyze_proc = subprocess.run(  # noqa: S603 - explicit bundled interpreter
            [
                *python_command,
                "-m",
                "lixity",
                "analyze",
                str(manuscript),
                "--language",
                "de",
                "--json",
            ],
            env=env,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            check=True,
            timeout=30,
        )
        analysis = json.loads(analyze_proc.stdout)
        meta = analysis.get("meta", {})
        if meta.get("language") != "de" or meta.get("tool") != "lixity":
            raise AssertionError(f"Unexpected analysis meta envelope: {meta!r}")

        # 3. Authenticated desktop startup and import from an empty workspace.
        secret = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        bootstrap = (
            json.dumps({"secret": secret, "handshake_nonce": nonce, "parent_pid": os.getpid()})
            + "\n"
        )
        t0 = time.perf_counter()
        with subprocess.Popen(  # noqa: S603 - explicit bundled interpreter
            [
                *python_command,
                "-m",
                "lixity",
                "serve",
                "--no-project",
                "--_desktop-mode",
                "--host",
                "127.0.0.1",
                "--port",
                "0",
            ],
            env=env,
            cwd=str(tmp_path),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        ) as proc:
            try:
                if proc.stdin is None or proc.stdout is None:
                    raise RuntimeError("Subprocess pipes unavailable")
                proc.stdin.write(bootstrap)
                proc.stdin.flush()
                proc.stdin.close()

                ready_line = _read_ready_line(proc.stdout)
                cold_start_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                ready = json.loads(ready_line)
                if not isinstance(ready, dict):
                    raise AssertionError("Invalid desktop readiness envelope")
                port = ready.get("port")
                if (
                    ready.get("schema_version") != "lixity-desktop-ready/1"
                    or ready.get("ready") is not True
                    or ready.get("host") != "127.0.0.1"
                    or f"lixity {ready.get('version')}" != reported_version
                    or type(port) is not int
                    or not 0 < port <= 65535
                ):
                    raise AssertionError("Invalid desktop readiness envelope")

                # Unauthenticated GET must return 403
                st_denied, _, _ = _http_request(port, "GET", "/")
                if st_denied != 403:
                    raise AssertionError(f"Expected 403 unauthenticated, got {st_denied}")

                # Handshake must return 303 + HttpOnly cookie
                st_hs, hs_headers, _ = _http_request(
                    port, "GET", f"/_desktop/handshake?nonce={nonce}"
                )
                cookie_pair, *attrs = hs_headers.get("set-cookie", "").split(";")
                if (
                    st_hs != 303
                    or not cookie_pair
                    or "httponly" not in {attr.strip().lower() for attr in attrs}
                ):
                    raise AssertionError(
                        f"Desktop handshake did not issue an HttpOnly session cookie: {st_hs}"
                    )

                # Replay must return 403
                st_replay, _, _ = _http_request(port, "GET", f"/_desktop/handshake?nonce={nonce}")
                if st_replay != 403:
                    raise AssertionError(f"Expected 403 on nonce replay, got {st_replay}")

                # Authenticated dashboard + environment endpoint must succeed
                headers = {"Cookie": cookie_pair}
                st_redirect, dashboard_headers, _ = _http_request(port, "GET", "/", headers=headers)
                workspace = dashboard_headers.get("location", "")
                if st_redirect != 303 or not workspace.startswith("/w/"):
                    raise AssertionError("Desktop dashboard did not redirect to a local workspace")
                st_dashboard, _, welcome = _http_request(port, "GET", workspace, headers=headers)
                if st_dashboard != 200 or b'id="hero-btn-write"' not in welcome:
                    raise AssertionError("Desktop welcome screen is unavailable")
                project_base = test_home.resolve() / "Lixity"
                if project_base.exists():
                    raise AssertionError("Opening the welcome screen created the project directory")
                content = manuscript.read_text(encoding="utf-8")
                create_status, _, result = _http_request(
                    port,
                    "POST",
                    workspace + "api/project-create",
                    headers={**headers, "Content-Type": "application/json"},
                    body=json.dumps({"title": "First draft", "language": "de", "content": content}).encode(),
                )
                imported = project_base / "first-draft" / "manuscript.md"
                if create_status != 200 or json.loads(result).get("path") != str(imported.parent):
                    raise AssertionError(f"Desktop import into the default folder failed (HTTP {create_status})")
                if imported.read_text(encoding="utf-8") != content:
                    raise AssertionError("Desktop import changed the synthetic manuscript")
                st_env, _, env_body = _http_request(
                    port,
                    "GET",
                    "/api/desktop/environment",
                    headers=headers,
                )
                if st_env != 200:
                    raise AssertionError(f"Expected 200 on environment endpoint, got {st_env}")
                env_payload = json.loads(env_body.decode("utf-8"))
                if not env_payload.get("app", {}).get("desktop_mode"):
                    raise AssertionError(f"desktop_mode was not true: {env_payload}")
            finally:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=5)

    if _bytecode_state(bundle_dir) != bytecode_before:
        raise AssertionError("Desktop runtime modified bytecode inside its signed resources")

    return {
        "ok": True,
        "bundle": str(bundle_dir),
        "target": manifest["target"],
        "version": reported_version,
        "cold_start_ms": cold_start_ms,
        "uncompressed_mib": round(manifest["uncompressed_bytes"] / (1024 * 1024), 1),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle_dir", type=Path, help="Path to built runtime bundle directory")
    args = parser.parse_args(argv)
    result = verify_bundle(args.bundle_dir)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
