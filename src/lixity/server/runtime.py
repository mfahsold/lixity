"""Server lifecycle: bind checks, project resolution and shutdown."""

from __future__ import annotations

import os
import socket
import sys
import webbrowser
from collections.abc import Mapping
from http.server import ThreadingHTTPServer
from typing import Any

from ..style_fingerprint import FingerprintThresholds
from ..workspace import discover
from .constants import DEFAULT_HOST, DEFAULT_PORT
from .handler import LixityServerHandler


def run_server(
    target_path: str | None = None,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    language: str = "en",
    title: str | None = None,
    no_project: bool = False,
    thresholds: FingerprintThresholds | None = None,
    open_browser: bool = False,
    research_dir: str | None = None,
    project_open_overrides: Mapping[str, Any] | None = None,
    debug: bool = False,
) -> None:
    """Runs the Lixity dashboard development server on loopback."""
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("Only loopback addresses (127.0.0.1, localhost) are permitted")

    # Probe whether the port is already occupied before doing any setup work.
    # A quick connect attempt is the most reliable cross-platform check.
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as _probe:
        _probe.settimeout(0.5)
        _in_use = _probe.connect_ex((host, port)) == 0
    if _in_use:
        print(
            f"[ERR] Port {port} is already in use.\n"
            f"      If Lixity is already running, open http://{host}:{port}/ in your browser.\n"
            f"      To start on a different port:  lixity serve --port <PORT>\n"
            f"      To stop an existing instance:  kill $(lsof -ti :{port})  # macOS/Linux\n"
            f"                                     Stop-Process -Id (Get-NetTCPConnection -LocalPort {port}).OwningProcess  # Windows",
            file=sys.stderr,
        )
        sys.exit(1)

    is_debug = bool(debug or os.environ.get("LIXITY_DEBUG", "").lower() in ("1", "true", "yes"))
    source_input: str | None = None
    workspace_root: str = os.getcwd()
    exports_dir: str = os.path.join(workspace_root, "exports")

    if not no_project and target_path:
        target_abs = os.path.abspath(target_path)
        if os.path.isfile(target_abs):
            source_input = target_abs
            workspace_root = os.path.dirname(target_abs)
            exports_dir = os.path.join(workspace_root, "exports")
        elif os.path.isdir(target_abs):
            try:
                ws = discover(root=target_abs)
                source_input = ws.manuscript
                workspace_root = ws.root
                exports_dir = ws.exports_dir
            except (FileNotFoundError, ValueError):
                workspace_root = target_abs
                exports_dir = os.path.join(workspace_root, "exports")
                source_input = None
    elif not no_project:
        # Attempt ambient discovery in current working directory
        try:
            ws = discover(root=workspace_root)
            source_input = ws.manuscript
            workspace_root = ws.root
            exports_dir = ws.exports_dir
        except (FileNotFoundError, ValueError):
            source_input = None

    os.makedirs(exports_dir, exist_ok=True)

    LixityServerHandler.debug = is_debug
    LixityServerHandler.source_input = source_input
    LixityServerHandler.workspace_root = workspace_root
    LixityServerHandler.exports_dir = exports_dir
    LixityServerHandler.research_dir = research_dir
    LixityServerHandler.language = language
    LixityServerHandler.title = title
    overrides = dict(project_open_overrides or {})
    if project_open_overrides is None and title is not None:
        overrides["title"] = title
    LixityServerHandler.title_custom = "title" in overrides
    LixityServerHandler.project_open_overrides = overrides
    LixityServerHandler.thresholds = thresholds or FingerprintThresholds()
    LixityServerHandler.refresh()

    server = ThreadingHTTPServer((host, port), LixityServerHandler)
    url = f"http://{host}:{port}/"
    info = LixityServerHandler.dashboard_info
    debug_tag = " (debug mode active)" if is_debug else ""

    print(
        f"[OK] Lixity server running: {url}{debug_tag}\n"
        f"     {info.get('chapters')} chapters · {info.get('paragraphs')} paragraphs · "
        f"{info.get('artifacts')} artifacts (profile: {info.get('language')})\n"
        f"     Stop with Ctrl+C"
    )

    if open_browser:
        webbrowser.open(url)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[OK] Lixity server stopped.")
    finally:
        server.server_close()
