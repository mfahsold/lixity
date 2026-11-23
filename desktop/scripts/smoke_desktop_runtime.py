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
from typing import Any


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


def _http_request(
    port: int,
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], bytes]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10.0)
    try:
        conn.request(method, path, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, {k.lower(): v for k, v in resp.getheaders()}, resp.read()
    finally:
        conn.close()


def verify_bundle(bundle_dir: Path) -> dict[str, Any]:
    manifest_path = bundle_dir / "runtime-bundle-manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing runtime-bundle-manifest.json in {bundle_dir}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    python_exe = (bundle_dir / manifest["python_relpath"]).resolve()
    if not python_exe.is_file():
        raise FileNotFoundError(f"Bundled Python executable missing: {python_exe}")

    python_command = [str(python_exe), "-I", "-B"]
    env = _stripped_env()
    bytecode_before = _bytecode_state(bundle_dir)
    subprocess.run(  # noqa: S603 - explicit bundled interpreter
        [*python_command, "-c", "import sys; assert sys.flags.isolated and sys.flags.dont_write_bytecode"],
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

        # 3. Authenticated desktop-mode server lifecycle + handshake verification
        secret = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        bootstrap = json.dumps({"secret": secret, "handshake_nonce": nonce, "parent_pid": os.getpid()}) + "\n"
        t0 = time.perf_counter()
        with subprocess.Popen(  # noqa: S603 - explicit bundled interpreter
            [
                *python_command,
                "-m",
                "lixity",
                "serve",
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
            stderr=subprocess.PIPE,
            text=True,
        ) as proc:
            try:
                if proc.stdin is None or proc.stdout is None:
                    raise RuntimeError("Subprocess pipes unavailable")
                proc.stdin.write(bootstrap)
                proc.stdin.flush()
                proc.stdin.close()

                ready_line = proc.stdout.readline()
                cold_start_ms = round((time.perf_counter() - t0) * 1000.0, 1)
                if not ready_line:
                    stderr_out = proc.stderr.read() if proc.stderr else ""
                    raise RuntimeError(f"Desktop server failed to emit readiness JSON: {stderr_out}")
                ready = json.loads(ready_line)
                if not ready.get("ready") or not isinstance(ready.get("port"), int):
                    raise AssertionError(f"Invalid ready envelope: {ready}")
                port = ready["port"]

                # Unauthenticated GET must return 403
                st_denied, _, _ = _http_request(port, "GET", "/")
                if st_denied != 403:
                    raise AssertionError(f"Expected 403 unauthenticated, got {st_denied}")

                # Handshake must return 303 + HttpOnly cookie
                st_hs, hs_headers, _ = _http_request(port, "GET", f"/_desktop/handshake?nonce={nonce}")
                if st_hs != 303 or "set-cookie" not in hs_headers:
                    raise AssertionError(f"Unexpected handshake response: {st_hs} {hs_headers}")
                cookie_pair = hs_headers["set-cookie"].split(";", 1)[0]

                # Replay must return 403
                st_replay, _, _ = _http_request(port, "GET", f"/_desktop/handshake?nonce={nonce}")
                if st_replay != 403:
                    raise AssertionError(f"Expected 403 on nonce replay, got {st_replay}")

                # Authenticated dashboard + environment endpoint must succeed
                st_env, _, env_body = _http_request(
                    port,
                    "GET",
                    "/api/desktop/environment",
                    headers={"Cookie": cookie_pair},
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
    result = verify_bundle(args.bundle_dir.resolve())
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
