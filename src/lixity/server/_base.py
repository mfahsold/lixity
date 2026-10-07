"""Shared HTTP response helpers and request guards for the Lixity server.

Kept separate from the handler so every route group inherits exactly the same
response and trust behaviour.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from ._state import WorkspaceState
from .constants import DEFAULT_PORT


class ResponseMixin(WorkspaceState):
    """Response helpers and origin/host guards shared by all route groups.

    Inherits the workspace state so every route group sees the same attributes.
    """

    def _debug_log(self, message: str) -> None:
        """Write request and error diagnostics with the same UTC prefix."""
        if not self.debug:
            return
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        sys.stderr.write(f"[{now}] [server:debug] {message}\n")
        sys.stderr.flush()

    def _send(self, code: int, body: bytes, content_type: str, *,
              headers: Mapping[str, str] | None = None) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in (headers or {}).items():
            self.send_header(name, value)
        try:
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # A cancelled request cannot receive another response. Keep transport
            # errors out of route processing handlers, which might retry as 500.
            self.close_connection = True
            self._debug_log(f"Client disconnected while sending HTTP {code} response")

    def _json(self, payload: Mapping[str, Any], code: int = 200) -> None:
        if self.debug and code >= 400:
            msg = payload.get("message", "")
            self._debug_log(f"HTTP {code} on {self.command} {self.path}: {msg}")
        self._send(
            code,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _same_origin(self) -> bool:
        """True when the request carries no Origin, or one matching its own Host.

        A missing Origin is accepted because non-browser clients (the CLI, the
        Task Scheduler launcher) do not send one; the loopback-only bind and the
        Host check are what constrain reachability.
        """
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        host = self.headers.get("Host", "")
        return origin in (f"http://{host}", f"https://{host}")

    def _trusted_host(self) -> bool:
        host = self.headers.get("Host", "")
        server_port = getattr(self.server, "server_port", DEFAULT_PORT)
        allowed = {f"127.0.0.1:{server_port}", f"localhost:{server_port}", "127.0.0.1", "localhost"}
        return host in allowed
