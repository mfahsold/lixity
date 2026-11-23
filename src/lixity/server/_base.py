"""Shared HTTP response helpers and request guards for the Lixity server.

Kept separate from the handler so every route group inherits exactly the same
response and trust behaviour.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from collections.abc import Collection, Mapping
from html import escape
from logging import DEBUG, WARNING
from pathlib import Path
from threading import RLock
from typing import Any, BinaryIO, TypeVar

from pydantic import BaseModel, ValidationError

from ..log import get_logger
from ..manuscript_editing import SOURCE_WRITE_LOCK, ManuscriptStore, document_lock
from ..research.repository import (
    ResearchCleanupError,
    ResearchConflictError,
    ResearchPublicationError,
)
from ..ui.components import status_strip
from ..workspace_labels import workspace_labels_for
from ._state import RefreshOutcome, WorkspaceState
from .constants import AUDIO_CAPTURE_ROUTE, DEFAULT_PORT
from .middleware import (
    SelectedManuscriptContext,
    analysis_open_overrides,
    build_manuscript_store,
    format_validation_error,
    parse_single_query_params,
)
from .pdf_context import manuscript_pdf_token, research_context_token

_ModelT = TypeVar("_ModelT", bound=BaseModel)


class ResponseMixin(WorkspaceState):
    """Response helpers and origin/host guards shared by all route groups.

    Inherits the workspace state so every route group sees the same attributes.
    """

    _log = get_logger("server")

    def _safe_debug_route(self, raw_path: str) -> str:
        """Keep known route names without retaining user-controlled path data."""
        path = raw_path.split("?", 1)[0]
        if path.startswith("/w/"):
            pieces = path.split("/", 3)
            if len(pieces) < 4 or len(pieces[2]) != 32 or any(c not in "0123456789abcdef" for c in pieces[2]):
                return "unknown"
            path = "/" + pieces[3]
        if path in ("/", "/index.html"):
            return "/"
        if path in ("/_desktop/handshake", "/_desktop/nonce"):
            return path
        if path in getattr(self, "GET_ROUTES", {}):
            return path
        if path.startswith("/api/") and path[len("/api/"):] in getattr(self, "POST_ROUTES", {}):
            return path
        if path.startswith("/artifact/"):
            return "/artifact/<redacted>"
        return "unknown"

    @staticmethod
    def _safe_debug_method(method: str) -> str:
        return method if method in ("GET", "POST", "HEAD", "OPTIONS") else "OTHER"

    def _debug_log(self, message: str) -> None:
        """Record request and error diagnostics on the shared logger.

        The call sites gate on ``debug``; the logger level decides whether a
        record is written. Messages never contain query strings or content.
        """
        self._log.debug(message)

    def _write_response_headers(
        self, code: int, content_length: int, content_type: str, *, headers: Mapping[str, str] | None = None
    ) -> None:
        extra = dict(headers or {})
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(content_length))
        self.send_header("Cache-Control", extra.pop("Cache-Control", "no-store"))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Content-Security-Policy",
            extra.pop("Content-Security-Policy", "frame-ancestors 'none'"),
        )
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header(
            "Permissions-Policy",
            extra.pop("Permissions-Policy", "camera=(), microphone=(), geolocation=(), usb=(), serial=()"),
        )
        for name, value in extra.items():
            self.send_header(name, value)

    def _send(
        self, code: int, body: bytes, content_type: str, *, headers: Mapping[str, str] | None = None
    ) -> bool:
        self._write_response_headers(code, len(body), content_type, headers=headers)
        try:
            self.end_headers()
            self.wfile.write(body)
            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            # A cancelled request cannot receive another response. Keep transport
            # errors out of route processing handlers, which might retry as 500.
            self.close_connection = True
            self._log.log(WARNING if code >= 500 else DEBUG,
                          "Client disconnected while sending HTTP %d response", code)
            return False

    def _send_stream(
        self,
        code: int,
        stream: BinaryIO,
        byte_count: int,
        content_type: str,
        *,
        headers: Mapping[str, str] | None = None,
        chunk_size: int = 65536,
    ) -> bool:
        self._write_response_headers(code, byte_count, content_type, headers=headers)
        try:
            self.end_headers()
            remaining = byte_count
            while remaining > 0:
                chunk = stream.read(min(chunk_size, remaining))
                if not chunk:
                    self.close_connection = True
                    return False
                self.wfile.write(chunk)
                remaining -= len(chunk)
            return True
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.close_connection = True
            self._log.warning("Client disconnected while streaming HTTP %d response", code)
            return False

    def _send_dashboard_shell(
        self, html: str, *, freshness: RefreshOutcome = RefreshOutcome.UNKNOWN, language: str = "en",
        allow_microphone: bool = False,
        editor_view: bool = False,
    ) -> None:
        """Serve the dashboard with a per-response script nonce and strict CSP.

        Nonced scripts and inline styles retain the default-deny policy. A
        microphone-enabled page can also load its exact packaged AudioWorklet URL.
        """
        notice_keys = {
            RefreshOutcome.MISSING: "status_source_missing",
            RefreshOutcome.UNREADABLE: "status_source_unreadable",
            RefreshOutcome.REFRESH_FAILED: "status_refresh_failed",
        }
        if freshness in notice_keys:
            labels = workspace_labels_for(language)
            notice = status_strip(labels, [{
                "key": "freshness", "state": "warn", "detail": labels[notice_keys[freshness]],
            }])
            notice = notice.replace(
                '<div class="status-strip">',
                f'<div class="status-strip" id="dashboard-freshness" '
                f'data-dashboard-freshness="{freshness.value}" role="status" aria-live="polite">',
                1,
            )
            retry = f'<a class="ctl" href="{escape(self.api_base.removesuffix("/api") + "/")}">{escape(labels["status_retry_refresh"])}</a>'
            notice = notice.removesuffix("</div>") + retry + "</div>"
            html = html.replace("<!--dashboard-freshness-->", notice, 1)
        nonce = secrets.token_urlsafe(16)
        body = html.replace("<script>", f'<script nonce="{nonce}">')
        if self.source_input and not editor_view:
            bootstrap = (f'<script nonce="{nonce}" src="{escape(self.api_base)}/editor-bootstrap.js"></script>')
            body = body.replace("</body>", bootstrap + "</body>")
        script_policy = f"script-src 'nonce-{nonce}'"
        if allow_microphone and self._trusted_host():
            # AudioWorklet loads through script-src and cannot attach a document nonce.
            worklet = self.api_base.removesuffix("/api") + AUDIO_CAPTURE_ROUTE
            script_policy += f" http://{self.headers['Host']}{worklet}"
        connect_src = (
            "connect-src 'self' ipc: http://ipc.localhost https://ipc.localhost"
            if self._desktop_session() is not None
            else "connect-src 'self'"
        )
        policy = "; ".join(
            (
                "default-src 'none'",
                script_policy,
                "style-src 'unsafe-inline'",
                "img-src 'self' data: blob: https://tile.openstreetmap.org",
                "font-src 'self' data:",
                "media-src 'self' blob:",
                connect_src,
                "frame-src 'self'" if self.source_input and not editor_view else "frame-src 'none'",
                "base-uri 'none'",
                "form-action 'none'",
                "frame-ancestors 'self'" if editor_view else "frame-ancestors 'none'",
            )
        )
        self._send(
            200,
            body.encode("utf-8"),
            "text/html; charset=utf-8",
            headers={
                "Content-Security-Policy": policy,
                "Cross-Origin-Opener-Policy": "same-origin",
                "Permissions-Policy": "camera=(), microphone=" + ("(self)" if allow_microphone else "()")
                + ", geolocation=(), usb=(), serial=()",
            },
        )

    def _json(self, payload: Mapping[str, Any], code: int = 200) -> None:
        if getattr(self, "_workspace_selection", False) and code < 300 and payload.get("ok"):
            self.server.workspaces.publish(type(self))
            self._workspace_selection_ok = True
            payload = {**payload, "workspace_url": self.api_base.removesuffix("/api") + "/"}
        if self.debug and code >= 400:
            route = self._safe_debug_route(self.path)
            self._debug_log(f"HTTP {code} on {self._safe_debug_method(self.command)} {route}")
        self._send(
            code,
            json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            "application/json; charset=utf-8",
        )

    def _ok(self, payload: Mapping[str, Any] | None = None, code: int = 200) -> None:
        self._json({"ok": True, **(payload or {})}, code)

    def _error(
        self,
        message: str,
        code: int = 400,
        *,
        error_code: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        payload: dict[str, Any] = {"ok": False, "message": str(message)}
        if error_code is not None:
            payload["code"] = error_code
        if extra:
            payload.update(extra)
        self._json(payload, code)

    def _parse_query(
        self,
        *,
        required: Collection[str] = (),
        optional: Collection[str] = (),
        non_empty: Collection[str] = (),
        error_message: str | None = None,
    ) -> dict[str, str] | None:
        try:
            return parse_single_query_params(
                self.path,
                required=required,
                optional=optional,
                non_empty=non_empty,
                error_message=error_message,
            )
        except ValueError as exc:
            self._error(str(exc), 400)
            return None

    def _validate_model(
        self,
        model_cls: type[_ModelT],
        payload: Mapping[str, Any],
        *,
        error_message: str | None = None,
    ) -> _ModelT | None:
        try:
            return model_cls.model_validate(payload)
        except ValidationError as exc:
            self._error(error_message or format_validation_error(exc), 400)
            return None

    def _document_lock(self) -> RLock:
        return document_lock(self.source_input) if self.source_input else SOURCE_WRITE_LOCK

    def _editor_store(self) -> ManuscriptStore:
        return build_manuscript_store(
            self.workspace_root,
            self.source_input,
            language=getattr(self, "language", "en") or "en",
            project_root=self.get_author_project_root(),
            overrides=getattr(self, "project_open_overrides", None),
        )

    def _require_selected_manuscript(
        self,
        *,
        readable: bool = False,
        missing_message: str = "No readable manuscript is selected",
    ) -> str | None:
        source = self.source_input
        if not source or (readable and not os.path.isfile(source)):
            self._error(missing_message, 400)
            return None
        return source

    def _capture_manuscript_context(
        self,
        expected_token: str | None = None,
        *,
        require_readable: bool = True,
        missing_message: str = "No readable manuscript is selected",
        stale_message: str = "The selected project changed; reload before continuing",
    ) -> SelectedManuscriptContext | None:
        with self._workspace_lock:
            source = self.source_input
            if not source or (require_readable and not Path(source).is_file()):
                self._error(missing_message, 400)
                return None
            root = self.workspace_root
            language, title, thresholds = self.language, self.title, self.thresholds
            token = manuscript_pdf_token(
                source,
                project_root=root,
                language=language,
                title=title,
                thresholds=thresholds,
            )
            if expected_token is not None and (not token or token != expected_token):
                self._error(stale_message, 409)
                return None
            return SelectedManuscriptContext(
                source=source,
                root=root,
                language=language,
                title=title,
                thresholds=thresholds,
                info=self.dashboard_info,
                token=token,
                analysis_overrides=analysis_open_overrides(self.project_open_overrides),
            )

    def _manuscript_context_still_current(
        self,
        context: SelectedManuscriptContext,
        *,
        stale_message: str = "The selected project changed; reload before downloading",
    ) -> bool:
        with self._workspace_lock:
            current = manuscript_pdf_token(
                self.source_input,
                project_root=self.workspace_root,
                language=self.language,
                title=self.title,
                thresholds=self.thresholds,
            )
            if current != context.token or self.dashboard_info is not context.info:
                self._error(stale_message, 409)
                return False
            return True

    def _research_error(self, error: Exception, code: int = 400, *, message: str | None = None) -> None:
        """Preserve conflict as 409 and publication/cleanup recovery messages as 500."""
        if isinstance(error, ResearchConflictError):
            code = 409
        elif isinstance(error, (ResearchPublicationError, ResearchCleanupError)):
            code = 500
        self._error(str(error) if message is None else message, code)

    def _research_context_matches(self, token: Any) -> bool:
        """Keep token-bound requests in the selected root, including restored copies."""
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token):
            self._error("A selected research context token is required", 400)
            return False
        root = self.get_research_root()
        if root is None and self.source_input:
            root = Path(self.workspace_root)
        if token != research_context_token(root):
            self._error("Selected research project changed; refresh before continuing", 409, error_code="stale-context")
            return False
        return True

    def _require_research_root(self, *, missing_status: int = 404) -> Path | None:
        """Return the initialized research root or respond with the expected 4xx status."""
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._error("Research project not initialized", missing_status)
            return None
        return root

    def _same_origin(self) -> bool:
        """True when Sec-Fetch-Site and Origin are consistent with same-origin access.

        A missing Origin is accepted because non-browser clients (the CLI, the
        Task Scheduler launcher) do not send one; the loopback-only bind,
        Sec-Fetch-Site check, and Host check constrain reachability.
        """
        sec_fetch_site = self.headers.get("Sec-Fetch-Site")
        if sec_fetch_site is not None and sec_fetch_site.strip().lower() not in ("same-origin", "none"):
            return False
        origin = self.headers.get("Origin")
        if origin is None:
            return True
        host = self.headers.get("Host", "")
        return origin in (f"http://{host}", f"https://{host}")

    def _require_same_origin(self, message: str = "Cross-origin request forbidden") -> bool:
        """Reject cross-origin or cross-site requests with HTTP 403."""
        if self._same_origin():
            return True
        self._json({"ok": False, "message": message}, 403)
        return False

    def _desktop_session(self) -> Any:
        return getattr(self.server, "desktop_session", None)

    def _require_desktop_session(self) -> bool:
        """Require authenticated desktop cookie or host secret when running in desktop mode."""
        session = self._desktop_session()
        if session is None or session.is_authorized(self.headers):
            return True
        self._json({"ok": False, "message": "Desktop session authentication required"}, 403)
        return False

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
