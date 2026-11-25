#!/usr/bin/env python3
"""Time a counted passage and its return in WKWebView on a synthetic project."""

from __future__ import annotations

import argparse
import json
import os
import platform
import secrets
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.parse import urlencode

from smoke_desktop_runtime import _read_ready_line

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parents[1]
PARAGRAPH = (
    "Mara saw the lantern across the quiet river. The keeper opened the gate before the morning rain. "
    "A lamp burned beside the empty path. She folded the note and let the window close. "
    "The river moved through the garden and down to the harbor."
)


def write_manuscript(path: Path, words: int) -> dict[str, int]:
    count = (words + len(PARAGRAPH.split()) - 1) // len(PARAGRAPH.split())
    per_chapter = (count + 19) // 20
    paragraphs = [PARAGRAPH] * count
    # A single counted passage late in the text makes the first result a distant jump.
    paragraphs[count * 3 // 4] += ' “Wait here,” she said to the keeper.'
    chapters = [
        f"## Chapter {start // per_chapter + 1}\n\n" + "\n\n".join(paragraphs[start:start + per_chapter])
        for start in range(0, count, per_chapter)
    ]
    path.write_text("\n\n".join(chapters) + "\n", encoding="utf-8")
    return {"requested_words": words, "prose_words": sum(len(p.split()) for p in paragraphs), "paragraphs": count}


def measure(project: Path, manuscript: Path, executable: Path) -> dict[str, float | int]:
    profile = project / "profile"
    profile.mkdir()
    # Both the sidecar and the probe get disposable application settings.
    environment = {
        "PATH": os.defpath, "LC_ALL": "C.UTF-8", "PYTHONPATH": str(ROOT / "src"),
        "HOME": str(profile), "XDG_CONFIG_HOME": str(profile / "config"),
        "XDG_CACHE_HOME": str(profile / "cache"), "XDG_STATE_HOME": str(profile / "state"),
    }
    secret, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
    start = time.perf_counter()
    with subprocess.Popen(  # noqa: S603 - explicit local interpreter and fixture path
        [sys.executable, "-B", "-m", "lixity", "serve", str(manuscript), "--_desktop-mode",
         "--host", "127.0.0.1", "--port", "0", "--language", "en"],
        env=environment, cwd=project, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True,
    ) as server:
        try:
            if server.stdin is None or server.stdout is None:
                raise RuntimeError("Desktop server pipes unavailable")
            server.stdin.write(json.dumps({"secret": secret, "handshake_nonce": nonce, "parent_pid": os.getpid()}) + "\n")
            server.stdin.close()
            ready = json.loads(_read_ready_line(server.stdout, timeout=90))
            port = ready.get("port")
            if (ready.get("schema_version") != "lixity-desktop-ready/1" or ready.get("ready") is not True
                    or ready.get("host") != "127.0.0.1" or type(port) is not int or not 0 < port <= 65535):
                raise ValueError("Invalid desktop readiness envelope")
            server_ms = (time.perf_counter() - start) * 1000
            url = f"http://127.0.0.1:{port}/_desktop/handshake?" + urlencode({"nonce": nonce})
            result = subprocess.run(  # noqa: S603 - the local, just-compiled probe
                [str(executable), str(SCRIPTS / "benchmark_reader.js")], input=url + "\n",
                env=environment, check=True, text=True, stdout=subprocess.PIPE, timeout=70,
            )
            return {"sidecar_ready_ms": round(server_ms, 2), **json.loads(result.stdout)}
        finally:
            if server.poll() is None:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait(timeout=5)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--words", type=int, nargs="+", default=[50_000, 150_000, 300_000])
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()
    if sys.platform != "darwin":
        parser.error("the native WKWebView probe requires macOS")
    if args.runs < 1 or any(words < 5_000 for words in args.words):
        parser.error("use at least one run and at least 5,000 words per manuscript")

    revision = subprocess.check_output(
        ["/usr/bin/git", "rev-parse", "HEAD"], cwd=ROOT, text=True, timeout=10,
    ).strip()
    source_changes = subprocess.check_output(
        ["/usr/bin/git", "status", "--porcelain", "--", "src/lixity"], cwd=ROOT, text=True, timeout=10,
    )
    results = []
    with tempfile.TemporaryDirectory(prefix="lixity-reader-benchmark-") as scratch:
        directory = Path(scratch)
        probe = directory / "reader-probe"
        subprocess.run(  # noqa: S603 - known compiler and local source
            ["/usr/bin/swiftc", str(SCRIPTS / "benchmark_macos_reader.swift"), "-o", str(probe)],
            check=True, timeout=90,
        )
        for case, words in enumerate(args.words):
            runs = []
            for run in range(args.runs):
                project = directory / f"project-{case}-{run}"
                project.mkdir()
                manuscript = project / "manuscript.md"
                fixture = write_manuscript(manuscript, words)
                print(f"Measuring {fixture['prose_words']:,} words (run {run + 1}/{args.runs})", file=sys.stderr)
                runs.append(measure(project, manuscript, probe))
            medians = {key: round(statistics.median(row[key] for row in runs), 2) for key in runs[0] if key.endswith("_ms")}
            results.append({**fixture, "median_ms": medians, "runs": runs})
    print(json.dumps({
        "surface": "WKWebView with the authenticated checkout server", "macos": platform.mac_ver()[0],
        "machine": platform.machine(), "python": platform.python_version(), "viewport_css_px": [1200, 780],
        "source_revision": revision, "source_modified": bool(source_changes.strip()), "results": results,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
