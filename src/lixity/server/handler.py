"""The Lixity request handler: shared state, routing table and dispatch.

Route groups live in sibling modules and are composed below. Registered path
tables drive both dispatch and the content-free API index.
"""

from __future__ import annotations

import json
import os
import stat
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import parse_qs, unquote, urlparse

from ..project_structure import MAX_CONFIG_BYTES, project_artifact_path
from ..research import api as research_api
from ..speech_qwen import worker_health
from ..workspace_labels import WORKSPACE_LABELS
from ._state import RefreshOutcome
from .constants import (
    MAX_ARTIFACT_BYTES,
    MAX_IMAGE_PAYLOAD_BYTES,
    MAX_MEDIA_PAYLOAD_BYTES,
    MAX_PAYLOAD_BYTES,
    MIME_TYPES,
)
from .discovery import api_index
from .pdf_context import project_settings_token
from .routes_analysis_review import AnalysisReviewRoutesMixin
from .routes_manuscript_research import ManuscriptResearchRoutesMixin
from .routes_markers import MarkerRoutesMixin
from .routes_nda import NdaRoutesMixin
from .routes_pdf import ManuscriptPdfRoutesMixin
from .routes_project import ProjectRoutesMixin
from .routes_site import SiteExportRoutesMixin
from .routes_speech import SpeechRoutesMixin


class LixityServerHandler(
    AnalysisReviewRoutesMixin,
    ProjectRoutesMixin,
    MarkerRoutesMixin,
    ManuscriptResearchRoutesMixin,
    NdaRoutesMixin,
    ManuscriptPdfRoutesMixin,
    SiteExportRoutesMixin,
    SpeechRoutesMixin,
    BaseHTTPRequestHandler,
):
    """Serves the dashboard and the workspace action endpoints."""


    #: GET routes: exact path -> handler method name.
    GET_ROUTES: ClassVar[dict[str, str]] = {
        "/api": "_handle_api_index",
        "/api/": "_handle_api_index",
        "/api/runtime": "_handle_runtime",
        "/api/speech": "_handle_speech",
        "/api/speech-job": "_handle_speech_job",
        "/api/speech-audio": "_handle_speech_audio",
        "/api/project-structure": "_handle_project_structure",
        "/api/project-paths": "_handle_project_paths",
        "/api/analysis-review": "_handle_analysis_review",
        "/api/research/status": "_handle_research_status",
        "/api/research/sources": "_handle_research_sources",
        "/api/research/image": "_handle_research_image",
        "/api/research/images": "_handle_research_images",
        "/api/research/media": "_handle_research_media",
        "/api/research/dossiers": "_handle_research_dossiers",
        "/api/research/claims": "_handle_research_claims",
        "/api/research/timeline": "_handle_research_timeline",
        "/api/research/claim-relations": "_handle_research_claim_relations",
        "/api/research/decisions": "_handle_research_decisions",
        "/api/research/matrix": "_handle_research_matrix",
        "/api/research/record": "_handle_research_record",
        "/api/research/history": "_handle_research_history",
        "/api/research/ocr-status": "_handle_research_ocr_status",
        "/api/research/zotero-status": "_handle_zotero_status",
        "/api/research/decision-impact": "_handle_research_decision_impact",
        "/api/research/review": "_handle_research_review",
        "/api/research/manuscript-review": "_handle_manuscript_claim_review",
        "/api/research/manuscript-terms": "_handle_manuscript_terms_review",
        "/api/research/manuscript-links": "_handle_manuscript_claim_links",
    }

    #: POST actions under /api/ : exact action -> handler method name.
    POST_ROUTES: ClassVar[dict[str, str]] = {
        "workspace-close": "_handle_workspace_close",
        "speech-render": "_handle_speech_render",
        "speech-plan": "_handle_speech_plan",
        "speech-direction": "_handle_speech_direction",
        "speech-cancel": "_handle_speech_cancel",
        "nda-draft": "_handle_nda_draft",
        "manuscript-pdf": "_handle_manuscript_pdf",
        "site-export": "_handle_site_export",
        "site-preflight": "_handle_site_preflight",
        "site-export-report": "_handle_site_export_report",
        "analysis-review": "_handle_analysis_review_save",
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
        "research-media-ingest": "_handle_research_media_ingest",
        "research-dossier-media": "_handle_research_dossier_media",
        "research-search": "_handle_research_search",
        "research-dossier": "_handle_research_dossier",
        "research-compare": "_handle_research_compare",
        "research-claim-add": "_handle_research_claim_add",
        "research-manuscript-link": "_handle_manuscript_claim_link",
        "research-manuscript-reanchor": "_handle_manuscript_claim_reanchor",
        "research-claim-relation": "_handle_research_claim_relation_add",
        "research-evidence-link": "_handle_research_evidence_link",
        "research-decision-add": "_handle_research_decision_add",
        "research-decision-acknowledge": "_handle_research_decision_acknowledge",
        "research-record-revise": "_handle_research_record_revise",
        "research-record-prepare": "_handle_research_record_prepare",
        "research-revision-batch-prepare": "_handle_research_revision_batch_prepare",
        "research-revision-batch-apply": "_handle_research_revision_batch_apply",
        "manuscript-import-preview": "_handle_manuscript_import_preview",
        "manuscript-import-convert": "_handle_manuscript_import_convert",
    }

    #: Actions deliberately not implemented by the standalone server.
    UNSUPPORTED_ACTIONS: ClassVar[frozenset[str]] = frozenset(
        {"export", "sync", "audit", "prune", "gdrive"}
    )

    # Serialize selection/settings commits, manuscript writes and token-bound
    # research requests. PDF composition and unbound research work remain outside.
    WORKSPACE_MUTATING_ACTIONS: ClassVar[frozenset[str]] = frozenset({
        "settings", "load", "project-create", "project-open", "analyze", "rebuild",
        "marker-add", "marker-resolve", "research-init",
    })

    def do_GET(self) -> None:
        if not self._trusted_host():
            self._reject_untrusted_host()
            return

        registry = getattr(self.server, "workspaces", None)
        if registry is not None and not getattr(self, "_workspace_dispatched", False) and registry.dispatch(self, "GET"):
            return
        path = self.path.split("?", 1)[0]
        if path in ("/", "/index.html"):
            with self._workspace_lock:
                outcome = self.refresh_when_source_changed()
                html = self.dashboard_html
                language = self.dashboard_info.get("language_key", self.language)
                if not self.dashboard_info.get("manuscript_source_sha256"):
                    outcome = RefreshOutcome.UNKNOWN  # no last-good manuscript to label
            self._send_dashboard_shell(html, freshness=outcome, language=language)
            return

        if path.startswith("/artifact/"):
            self._serve_artifact(path[len("/artifact/"):])
            return

        if path in ("/api/project-paths", "/api/project-structure") and not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return
        handler_name = self.GET_ROUTES.get(path)
        if handler_name is not None:
            query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            if path.startswith("/api/research/") and "research_token" in query:
                tokens = query["research_token"]
                with self._workspace_lock:
                    if len(tokens) != 1:
                        self._json({"ok": False, "message": "Choose one selected research context token"}, 400)
                    elif self._research_context_matches(tokens[0]):
                        getattr(self, handler_name)()
            else:
                getattr(self, handler_name)()
            return

        self._json({"ok": False, "message": "Not found"}, 404)

    def _handle_workspace_close(self, payload: dict[str, Any]) -> None:
        registry = getattr(self.server, "workspaces", None)
        if registry is None or set(payload) != {"id"} or not isinstance(payload["id"], str):
            self._json({"ok": False, "message": "Choose an open workspace"}, 400)
            return
        if any(job["state"] in ("pending", "running") for job in self._speech_manager().overview()):
            self._json({"ok": False, "message": "Wait for audio jobs before closing workspaces"}, 409)
            return
        try:
            registry.close(payload["id"])
        except ValueError as exc:
            self._json({"ok": False, "message": str(exc)}, 409)
            return
        self._json({"ok": True})

    def _handle_runtime(self) -> None:
        """Observe the app and actual audio workers without exposing manuscript bindings."""
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return
        registry = getattr(self.server, "workspaces", None)
        manager = self._speech_manager()
        manager.cancel_stale()
        with ThreadPoolExecutor(max_workers=2) as pool:
            targets = list(pool.map(worker_health, ("local", "jetson")))
        self._json({"ok": True, "schema_version": "lixity-runtime-local/1",
                    "app": {"state": "ready"}, "workspaces": registry.items() if registry else [],
                    "audio": {"targets": targets, "jobs": manager.overview()}})

    def _handle_api_index(self) -> None:
        root = self.get_research_root()
        self._json({**api_index(self.GET_ROUTES, self.POST_ROUTES,
                             manuscript_loaded=self.source_input is not None,
                             research_configured=root is not None,
                             research_store_present=bool(root and (root / "research").is_dir()),
                             language=self.language), "api_base": self.api_base})

    def _handle_research_ocr_status(self) -> None:
        probe = parse_qs(urlparse(self.path).query).get("probe", ["0"])[0] in ("1", "true")
        self._json({"ok": True, **research_api.ocr_status(probe=probe)})

    def _handle_research_record(self) -> None:
        self._handle_research_record_read(history=False)

    def _handle_research_history(self) -> None:
        self._handle_research_record_read(history=True)

    def _handle_refresh(self, _payload: dict[str, Any]) -> None:
        try:
            self.refresh(strict_source=True)
        except (OSError, ValueError, RuntimeError, UserWarning):
            language = self.dashboard_info.get("language_key", self.language)
            labels = WORKSPACE_LABELS.get(language, WORKSPACE_LABELS["en"])
            self._json({"ok": False, "message": labels["status_refresh_error"]}, 500)
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
        """Read one contained output with fresh identity and optional context guards."""
        try:
            name = unquote(raw_name, errors="strict")
        except UnicodeError:
            self._json({"ok": False, "message": "Artifact not found"}, 404)
            return
        tokens = parse_qs(urlparse(self.path).query, keep_blank_values=True).get("project_token")
        if tokens is not None and (len(tokens) != 1 or not tokens[0]):
            self._json({"ok": False, "message": "Choose one current project context token"}, 400)
            return
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return
        with self._workspace_lock:
            selected_root = self.get_author_project_root()
            root = selected_root or Path(self.workspace_root)
            source = self.source_input
            if tokens is not None and (selected_root is None or tokens[0] != project_settings_token(root, source, maximum_config_bytes=MAX_CONFIG_BYTES)):
                self._json({"ok": False, "message": "Project context changed; reopen the project view"}, 409)
                return
        try:
            target = project_artifact_path(root, name, selected_manuscript=source)
            flags = os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
            with os.fdopen(os.open(target, flags), "rb") as handle:
                opened = os.fstat(handle.fileno())
                if not stat.S_ISREG(opened.st_mode):
                    raise ValueError("Artifact is no longer a regular file")
                if opened.st_size > MAX_ARTIFACT_BYTES:
                    self._json({"ok": False, "message": "Artifact exceeds the serving limit"}, 413)
                    return
                # The observed length bounds allocation even for tiny outputs.
                # Growth is detected by the extra byte and fresh descriptor stats.
                content = handle.read(opened.st_size + 1)
                after = os.fstat(handle.fileno())
            if len(content) != opened.st_size or any(
                getattr(opened, field) != getattr(after, field)
                for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")
            ):
                raise ValueError("Artifact changed while reading")
            checked = project_artifact_path(root, name, selected_manuscript=source)
            final = checked.stat()
            if checked != target or any(getattr(after, field) != getattr(final, field)
                for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns", "st_ctime_ns")):
                raise ValueError("Artifact identity changed")
        except (OSError, RuntimeError, ValueError):
            self._json({"ok": False, "message": "Artifact not found or no longer available"}, 404)
            return
        if tokens is not None:
            with self._workspace_lock:
                current_root = self.get_author_project_root()
                if current_root != root or tokens[0] != project_settings_token(current_root, self.source_input, maximum_config_bytes=MAX_CONFIG_BYTES):
                    self._json({"ok": False, "message": "Project context changed; reopen the project view"}, 409)
                    return
        ctype = MIME_TYPES.get(target.suffix.lower(), "application/octet-stream")
        self._send(200, content, ctype)

    def do_POST(self) -> None:
        registry = getattr(self.server, "workspaces", None)
        if registry is not None and not getattr(self, "_workspace_dispatched", False):
            if not self._trusted_host() or not self._same_origin():
                self._json({"ok": False, "message": "Untrusted request"}, 403)
                return
            if registry.dispatch(self, "POST"):
                return
        path = self.path.split("?", 1)[0]
        if not path.startswith("/api/"):
            self._json({"ok": False, "message": "Not found"}, 404)
            return
        if not self._trusted_host():
            self._reject_untrusted_host()
            return
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return

        action = path[len("/api/"):].strip("/")
        maximum = (MAX_MEDIA_PAYLOAD_BYTES if action in {"research-media-ingest", "research-dossier-media"}
                   else MAX_IMAGE_PAYLOAD_BYTES if action in {"research-image-ingest", "research-dossier-image"}
                   else MAX_PAYLOAD_BYTES)
        payload = self._read_json_body(maximum=maximum)
        if payload is None:
            return

        handler_name = self.POST_ROUTES.get(action)
        if handler_name is not None:
            relation_write = (action == "research-claim-relation"
                              or (action == "research-record-revise" and payload.get("kind") == "claim_relation")
                              or (action == "research-revision-batch-apply" and isinstance(payload.get("operations"), list)
                                  and any(isinstance(op, dict) and op.get("kind") == "claim_relation"
                                          for op in payload["operations"])))
            bound_research = action.startswith("research-") and ("research_token" in payload or relation_write)
            if action in self.WORKSPACE_MUTATING_ACTIONS or bound_research:
                with self._workspace_lock:
                    if bound_research and not self._research_context_matches(payload.get("research_token")):
                        return
                    getattr(self, handler_name)(payload)
            else:
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

    def log_request(self, code: int | str = "-", size: int | str = "-") -> None:
        """Access-log the route without its query string.

        Context tokens and other selectors travel in query strings; debug logs
        keep the route for diagnosis and leave the values out.
        """
        if not self.debug:
            return
        method, _, remainder = self.requestline.partition(" ")
        path, _, version = remainder.partition(" ")
        self._debug_log(
            f'{self.address_string()} - "{method} {path.split("?", 1)[0]} '
            f'{version or "HTTP/1.0"}" {code} {size}'
        )

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default request logging unless debug mode is active."""
        if not self.debug:
            return
        self._debug_log(f"{self.address_string()} - {format % args}")
