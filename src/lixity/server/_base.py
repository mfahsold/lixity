"""Shared HTTP response helpers and request guards for the Lixity server.

Kept separate from the handler so every route group inherits exactly the same
response and trust behaviour.
"""

from __future__ import annotations

import json
import secrets
from collections.abc import Mapping
from typing import Any

from ..log import get_logger
from ._state import WorkspaceState
from .constants import DEFAULT_PORT


class ResponseMixin(WorkspaceState):
    """Response helpers and origin/host guards shared by all route groups.

    Inherits the workspace state so every route group sees the same attributes.
    """

    _log = get_logger("server")

    def _debug_log(self, message: str) -> None:
        """Record request and error diagnostics on the shared logger.

        The call sites gate on ``debug``; the logger level decides whether a
        record is written. Messages never contain query strings or content.
        """
        self._log.debug(message)

    def _send(
        self, code: int, body: bytes, content_type: str, *, headers: Mapping[str, str] | None = None
    ) -> None:
        extra = dict(headers or {})
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            extra.pop("Content-Security-Policy", "frame-ancestors 'none'"),
        )
        self.send_header("Referrer-Policy", "no-referrer")
        for name, value in extra.items():
            self.send_header(name, value)
        try:
            self.end_headers()
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # A cancelled request cannot receive another response. Keep transport
            # errors out of route processing handlers, which might retry as 500.
            self.close_connection = True
            self._debug_log(f"Client disconnected while sending HTTP {code} response")

    def _send_dashboard_shell(self, html: str) -> None:
        """Serve the dashboard with a per-response script nonce and strict CSP.

        The shell is self-contained: scripts come only from the bundled inline
        block (nonce), styles stay inline, and everything else is default-deny.
        A request nonce blocks injected scripts from manuscript or project text,
        so escaping tests and CSP protect the same boundary.
        """
        nonce = secrets.token_urlsafe(16)
        body = html.replace("<script>", f'<script nonce="{nonce}">')
        policy = "; ".join(
            (
                "default-src 'none'",
                f"script-src 'nonce-{nonce}'",
                "style-src 'unsafe-inline'",
                "img-src 'self' data: blob:",
                "font-src 'self' data:",
                "media-src 'self' blob:",
                "connect-src 'self'",
                "base-uri 'none'",
                "form-action 'none'",
                "frame-ancestors 'none'",
            )
        )
        self._send(
            200,
            body.encode("utf-8"),
            "text/html; charset=utf-8",
            headers={
                "Content-Security-Policy": policy,
                "Cross-Origin-Opener-Policy": "same-origin",
                "Permissions-Policy": "camera=(), microphone=(), geolocation=(), usb=(), serial=()",
            },
        )

    def _json(self, payload: Mapping[str, Any], code: int = 200) -> None:
        if self.debug and code >= 400:
            msg = payload.get("message", "")
            # Log the route without its query string: context tokens and other
            # selectors travel there and must not reach diagnostics.
            route = self.path.split("?", 1)[0]
            self._debug_log(f"HTTP {code} on {self.command} {route}: {msg}")
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

    def _server_port(self) -> int:
        return int(getattr(self.server, "server_port", DEFAULT_PORT))

    def _trusted_host(self) -> bool:
        host = self.headers.get("Host", "")
        server_port = self._server_port()
        allowed = {
            f"127.0.0.1:{server_port}",
            f"localhost:{server_port}",
            "127.0.0.1",
            "localhost",
            f"[::1]:{server_port}",
            "[::1]",
        }
        return host in allowed

    def _reject_untrusted_host(self) -> None:
        """Refuse a non-loopback Host header with the readable endpoint hint."""
        port = self._server_port()
        self._json(
            {
                "ok": False,
                "message": (
                    f"Untrusted Host forbidden; open http://127.0.0.1:{port}/ "
                    f"or http://localhost:{port}/"
                ),
            },
            403,
        )
