"""Native manuscript editor, bound to the selected project and source."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from ..manuscript_editing import MAX_TEXT_BYTES, EditConflict
from ..research.models import StrictModel
from ._base import ResponseMixin

# JSON can use six ASCII bytes for a one-byte UTF-8 character in either editor text.
MAX_EDITOR_COMPARISON_PAYLOAD_BYTES = 2 * 6 * MAX_TEXT_BYTES + 1024


class EditorSaveRequest(StrictModel):
    document: str
    revision: str
    operation: str
    text: str


class EditorDiscardRequest(StrictModel):
    document: str
    id: str


class EditorCompareRequest(StrictModel):
    document: str
    revision: str
    base_text: str
    draft_text: str
    settings_sha256: str | None = None


class EditingRoutesMixin(ResponseMixin):
    def _handle_editor_view(self) -> None:
        """Render the existing workspace only for an acknowledged source revision."""
        if not self._require_same_origin():
            return
        query = self._parse_query(
            required=("document", "revision"),
            error_message="Expected one document and revision",
        )
        if query is None:
            return
        try:
            with self._workspace_lock, self._document_lock():
                store = self._editor_store()
                opened = store.open()
                if any(query[key] != opened[key] for key in ("document", "revision")):
                    raise EditConflict("Manuscript changed; return to the editor to review")
                self.refresh_when_source_changed()
                if (self.dashboard_info.get("manuscript_source_sha256") != opened["revision"]
                        or store.open()["revision"] != opened["revision"]
                        or self._refresh_needs_validation):
                    raise EditConflict("Analysis does not match the requested manuscript revision")
                # Values originate in the store, never in arbitrary request text.
                html = self.dashboard_html.replace(
                    "<body", f'<body data-editor-document="{opened["document"]}" '
                    f'data-editor-revision="{opened["revision"]}"', 1,
                )
                # This reading session is bound to one project. Switching projects
                # belongs to the outer workspace, where editor state is visible.
                html = html.replace("</head>", "<style>"
                    "#project-actions,[data-view=project],#view-pane-project,"
                    ".workspace-shell-header,.workspace-shell .project-header,.workspace-product-details "
                    "{display:none!important;}"
                    "</style></head>", 1)
                self._send_dashboard_shell(html, language=self.language, editor_view=True)
        except EditConflict as exc:
            self._error(str(exc), 409)
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._error(str(exc), 400)

    def _handle_editor_open(self) -> None:
        if not self._require_same_origin():
            return
        query = self._parse_query(
            optional=("recovery",),
            non_empty=("recovery",),
            error_message="Expected at most one non-empty recovery identifier",
        )
        if query is None:
            return
        try:
            with self._workspace_lock:
                store = self._editor_store()
                result = store.recover(query["recovery"]) if "recovery" in query else store.open()
                self._ok(result)
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._error(str(exc), 400)

    def _handle_editor_save(self, payload: dict[str, Any]) -> None:
        request = self._validate_model(
            EditorSaveRequest,
            payload,
            error_message="Expected document, revision, operation and text strings",
        )
        if request is None:
            return
        try:
            result = self._editor_store().save(
                document=request.document,
                revision=request.revision,
                operation=request.operation,
                text=request.text,
            )
            self._ok(result)
        except EditConflict as exc:
            self._error(str(exc), 409, extra={"conflict": True})
        except (ValueError, UnicodeError) as exc:
            self._error(str(exc), 400)
        except (OSError, sqlite3.Error) as exc:
            self._error(str(exc), 500)

    def _handle_editor_discard(self, payload: dict[str, Any]) -> None:
        request = self._validate_model(
            EditorDiscardRequest,
            payload,
            error_message="Expected document and recovery identifier",
        )
        if request is None:
            return
        try:
            store = self._editor_store()
            if store.document != request.document:
                raise ValueError("Selected manuscript changed")
            store.discard(request.id)
            self._ok()
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._error(str(exc), 400)

    def _handle_editor_timeline(self) -> None:
        if not self._require_same_origin():
            return
        query = self._parse_query(
            optional=("limit",),
            non_empty=("limit",),
            error_message="Expected at most one non-empty limit parameter",
        )
        if query is None:
            return
        try:
            with self._workspace_lock:
                store = self._editor_store()
                limit = int(query["limit"]) if "limit" in query else 30
                revisions = store.timeline(limit=limit)
                self._ok({"schema_version": "lixity-timeline/1", "document": store.document, "revisions": revisions})
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._error(str(exc), 400)

    def _handle_editor_delta(self) -> None:
        if not self._require_same_origin():
            return
        query = self._parse_query(
            optional=("base", "target", "project_token"),
            non_empty=("base", "target", "project_token"),
            error_message="Expected optional base, target and selected-project token parameters",
        )
        if query is None:
            return
        try:
            with self._workspace_lock:
                token = query.get("project_token")
                context = None
                stale_message = "Selected analysis changed; refresh before comparing"
                if token is not None:
                    context = self._capture_manuscript_context(
                        token, require_readable=False, stale_message=stale_message,
                    )
                    if context is None:
                        return
                store = self._editor_store()
            result = store.delta(
                base_revision=query.get("base"),
                target_revision=query.get("target"),
            )
            if context is not None and not self._manuscript_context_still_current(context, stale_message=stale_message):
                return
            self._ok(result)
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._error(str(exc), 400)

    def _handle_editor_compare(self, payload: dict[str, Any]) -> None:
        request = self._validate_model(
            EditorCompareRequest,
            payload,
            error_message="Expected document, current revision, and comparison texts",
        )
        if request is None:
            return
        try:
            with self._workspace_lock:
                store = self._editor_store()
            if store.document != request.document:
                raise EditConflict("Selected manuscript changed")
            result = store.compare(
                revision=request.revision,
                base_text=request.base_text,
                draft_text=request.draft_text,
                settings_sha256=request.settings_sha256,
            )
            self._ok(result)
        except EditConflict as exc:
            self._error(str(exc), 409, extra={"conflict": True})
        except (ValueError, UnicodeError, OSError) as exc:
            self._error(str(exc), 400)

    def _handle_editor_asset(self) -> None:
        name = "manuscript-editor.js" if self.path.split("?")[0].endswith("editor-bootstrap.js") else "vendor/codemirror-editor.js"
        asset = Path(__file__).parents[1] / "ui" / "assets" / name
        self._send(200, asset.read_bytes(), "application/javascript; charset=utf-8")
