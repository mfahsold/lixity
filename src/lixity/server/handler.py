"""The Lixity request handler: shared state, routing table and dispatch.

Route groups live in sibling modules and are composed below. Registered path
tables drive both dispatch and the content-free API index.
"""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler
from typing import Any, ClassVar
from urllib.parse import parse_qs, urlparse

from ..research import api as research_api
from .constants import MAX_IMAGE_PAYLOAD_BYTES, MAX_PAYLOAD_BYTES, MIME_TYPES
from .discovery import api_index
from .routes_markers import MarkerRoutesMixin
from .routes_nda import NdaRoutesMixin
from .routes_project import ProjectRoutesMixin
from .routes_research import ResearchRoutesMixin


class LixityServerHandler(
    ProjectRoutesMixin,
    MarkerRoutesMixin,
    ResearchRoutesMixin,
    NdaRoutesMixin,
    BaseHTTPRequestHandler,
):
    """Serves the dashboard and the workspace action endpoints."""


    #: GET routes: exact path -> handler method name.
    GET_ROUTES: ClassVar[dict[str, str]] = {
        "/api": "_handle_api_index",
        "/api/": "_handle_api_index",
        "/api/project-paths": "_handle_project_paths",
        "/api/research/status": "_handle_research_status",
        "/api/research/sources": "_handle_research_sources",
        "/api/research/image": "_handle_research_image",
        "/api/research/dossiers": "_handle_research_dossiers",
        "/api/research/claims": "_handle_research_claims",
        "/api/research/decisions": "_handle_research_decisions",
        "/api/research/matrix": "_handle_research_matrix",
        "/api/research/record": "_handle_research_record",
        "/api/research/history": "_handle_research_history",
        "/api/research/ocr-status": "_handle_research_ocr_status",
        "/api/research/zotero-status": "_handle_zotero_status",
        "/api/research/decision-impact": "_handle_research_decision_impact",
        "/api/research/review": "_handle_research_review",
    }

    #: POST actions under /api/ : exact action -> handler method name.
    POST_ROUTES: ClassVar[dict[str, str]] = {
        "nda-draft": "_handle_nda_draft",
        "analyze": "_handle_refresh",
        "rebuild": "_handle_refresh",
        "marker-add": "_handle_marker_add",
        "marker-resolve": "_handle_marker_resolve",
        "research-zotero": "_handle_zotero_browse",
        "research-zotero-ingest": "_handle_zotero_capture",
        "settings": "_handle_settings",
        "load": "_handle_load",
        "project-create": "_handle_project_create",
        "project-open": "_handle_project_open",
        "research-init": "_handle_research_init",
        "research-ingest": "_handle_research_ingest",
        "research-image-ingest": "_handle_research_image_ingest",
        "research-dossier-image": "_handle_research_dossier_image",
        "research-search": "_handle_research_search",
        "research-dossier": "_handle_research_dossier",
        "research-compare": "_handle_research_compare",
        "research-claim-add": "_handle_research_claim_add",
        "research-evidence-link": "_handle_research_evidence_link",
        "research-decision-add": "_handle_research_decision_add",
        "research-decision-acknowledge": "_handle_research_decision_acknowledge",
        "research-record-revise": "_handle_research_record_revise",
        "research-record-prepare": "_handle_research_record_prepare",
        "research-revision-batch-prepare": "_handle_research_revision_batch_prepare",
        "research-revision-batch-apply": "_handle_research_revision_batch_apply",
    }

    #: Actions deliberately not implemented by the standalone server.
    UNSUPPORTED_ACTIONS: ClassVar[frozenset[str]] = frozenset(
        {"export", "sync", "audit", "prune", "gdrive"}
    )

    def do_GET(self) -> None:
        if not self._trusted_host():
            self._json({"ok": False, "message": "Untrusted Host forbidden"}, 403)
            return

        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            self._send(200, self.dashboard_html.encode("utf-8"), "text/html; charset=utf-8")
            return

        if path.startswith("/artifact/"):
            self._serve_artifact(path[len("/artifact/"):])
            return

        if path == "/api/project-paths" and not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return
        handler_name = self.GET_ROUTES.get(path)
        if handler_name is not None:
            getattr(self, handler_name)()
            return

        self._json({"ok": False, "message": "Not found"}, 404)

    def _handle_api_index(self) -> None:
        root = self.get_research_root()
        self._json(api_index(self.GET_ROUTES, self.POST_ROUTES,
                             manuscript_loaded=self.source_input is not None,
                             research_configured=root is not None,
                             research_store_present=bool(root and (root / "research").is_dir()),
                             language=self.language))

    def _handle_research_ocr_status(self) -> None:
        probe = parse_qs(urlparse(self.path).query).get("probe", ["0"])[0] in ("1", "true")
        self._json({"ok": True, **research_api.ocr_status(probe=probe)})

    def _handle_research_record(self) -> None:
        self._handle_research_record_read(history=False)

    def _handle_research_history(self) -> None:
        self._handle_research_record_read(history=True)

    def _handle_refresh(self, _payload: dict[str, Any]) -> None:
        try:
            self.refresh()
        except (OSError, ValueError, RuntimeError) as exc:
            self._json({"ok": False, "message": str(exc)}, 500)
            return
        action = self.path.split("?", 1)[0].rstrip("/").rsplit("/", 1)[-1]
        done = "Dashboard analyzed" if action == "analyze" else "Dashboard rebuilt"
        self._json({"ok": True, "message": done, "reload": True})

    def _handle_marker_add(self, payload: dict[str, Any]) -> None:
        self._handle_marker("marker-add", payload)

    def _handle_marker_resolve(self, payload: dict[str, Any]) -> None:
        self._handle_marker("marker-resolve", payload)

    def _handle_zotero_browse(self, payload: dict[str, Any]) -> None:
        self._handle_research_zotero(payload, capture=False)

    def _handle_zotero_capture(self, payload: dict[str, Any]) -> None:
        self._handle_research_zotero(payload, capture=True)

    def _serve_artifact(self, raw_name: str) -> None:
        """Stream a generated artifact, refusing any path outside exports/."""
        name = os.path.basename(raw_name.strip("/"))
        target = os.path.realpath(os.path.join(self.exports_dir, name))
        real_exports = os.path.realpath(self.exports_dir)
        if not target.startswith(real_exports + os.sep) or not os.path.isfile(target):
            self._json({"ok": False, "message": "Artifact not found"}, 404)
            return

        ctype = MIME_TYPES.get(os.path.splitext(target)[1].lower(), "application/octet-stream")
        try:
            with open(target, "rb") as handle:
                content = handle.read()
        except OSError:
            self._json({"ok": False, "message": "Failed to read artifact"}, 500)
            return
        self._send(200, content, ctype)

    def do_POST(self) -> None:
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/"):
            self._json({"ok": False, "message": "Not found"}, 404)
            return
        if not self._trusted_host():
            self._json({"ok": False, "message": "Untrusted Host forbidden"}, 403)
            return
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return

        action = path[len("/api/"):].strip("/")
        maximum = MAX_IMAGE_PAYLOAD_BYTES if action in {"research-image-ingest", "research-dossier-image"} else MAX_PAYLOAD_BYTES
        payload = self._read_json_body(maximum=maximum)
        if payload is None:
            return

        handler_name = self.POST_ROUTES.get(action)
        if handler_name is not None:
            getattr(self, handler_name)(payload)
            return

        if action.startswith("marker-"):
            self._handle_marker(action, payload)
            return
        if action.startswith("research-zotero"):
            self._handle_research_zotero(payload, capture=action.endswith("-ingest"))
            return
        if action in self.UNSUPPORTED_ACTIONS:
            self._json(
                {"ok": False, "message": f"Action '{action}' is not supported by the standalone server"},
                501,
            )
            return

        self._json({"ok": False, "message": f"Unknown action: {action}"}, 400)

    def _read_json_body(self, *, maximum: int = MAX_PAYLOAD_BYTES) -> dict[str, Any] | None:
        """Validate the request envelope and return the decoded JSON object.

        Responds with the appropriate 4xx status and returns ``None`` when the
        body cannot be used, so callers can simply bail out.
        """
        content_type = self.headers.get("Content-Type", "")
        if not content_type.startswith("application/json"):
            self._json({"ok": False, "message": "Content-Type application/json required"}, 415)
            return None
        if self.headers.get("Transfer-Encoding"):
            self._json({"ok": False, "message": "Transfer-Encoding not supported"}, 400)
            return None
        try:
            length = int(self.headers.get("Content-Length", ""))
        except ValueError:
            self._json({"ok": False, "message": "Invalid Content-Length"}, 400)
            return None
        if not 0 <= length <= maximum:
            self._json({"ok": False, "message": "Payload too large or invalid"}, 413)
            return None

        self.connection.settimeout(15)
        try:
            body = self.rfile.read(length) if length > 0 else b"{}"
            payload = json.loads(body)
            if not isinstance(payload, dict):
                raise ValueError("JSON object required")
        except (ValueError, UnicodeError, TimeoutError):
            self._json({"ok": False, "message": "Invalid JSON body"}, 400)
            return None
        return payload

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging unless debug mode is active."""
        if not self.debug:
            return
        self._debug_log(f"{self.address_string()} - {format % args}")
