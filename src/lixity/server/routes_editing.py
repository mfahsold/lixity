"""Native manuscript editor, bound to the selected project and source."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..manuscript_editing import SOURCE_WRITE_LOCK, EditConflict, ManuscriptStore
from ._base import ResponseMixin


class EditingRoutesMixin(ResponseMixin):
    def _handle_editor_view(self) -> None:
        """Render the existing workspace only for an acknowledged source revision."""
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return
        try:
            query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
            if set(query) != {"document", "revision"} or any(len(value) != 1 for value in query.values()):
                raise ValueError("Expected one document and revision")
            with self._workspace_lock, SOURCE_WRITE_LOCK:
                store = self._editor_store()
                opened = store.open()
                if any(query[key][0] != opened[key] for key in ("document", "revision")):
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
            self._json({"ok": False, "message": str(exc)}, 409)
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _editor_store(self) -> ManuscriptStore:
        if not self.source_input:
            raise ValueError("No manuscript selected")
        language = getattr(self, "language", "en") or "en"
        return ManuscriptStore(Path(self.workspace_root), Path(self.source_input), language=language)

    def _handle_editor_open(self) -> None:
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return
        try:
            with self._workspace_lock:
                store = self._editor_store()
                query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
                if set(query) - {"recovery"} or any(len(value) != 1 or not value[0] for value in query.values()):
                    raise ValueError("Expected at most one non-empty recovery identifier")
                result = store.recover(query["recovery"][0]) if "recovery" in query else store.open()
                self._json({"ok": True, **result})
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_editor_save(self, payload: dict[str, Any]) -> None:
        try:
            if set(payload) != {"document", "revision", "operation", "text"} or not all(isinstance(value, str) for value in payload.values()):
                raise ValueError("Expected document, revision, operation and text strings")
            result = self._editor_store().save(**payload)
            self._json({"ok": True, **result})
        except EditConflict as exc:
            self._json({"ok": False, "message": str(exc), "conflict": True}, 409)
        except (ValueError, UnicodeError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)
        except (OSError, sqlite3.Error) as exc:
            self._json({"ok": False, "message": str(exc)}, 500)

    def _handle_editor_discard(self, payload: dict[str, Any]) -> None:
        try:
            if set(payload) != {"document", "id"} or not all(isinstance(value, str) for value in payload.values()):
                raise ValueError("Expected document and recovery identifier")
            store = self._editor_store()
            if store.document != payload["document"]:
                raise ValueError("Selected manuscript changed")
            store.discard(payload["id"])
            self._json({"ok": True})
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_editor_timeline(self) -> None:
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return
        try:
            with self._workspace_lock:
                store = self._editor_store()
                query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
                if set(query) - {"limit"} or any(len(value) != 1 or not value[0] for value in query.values()):
                    raise ValueError("Expected at most one non-empty limit parameter")
                limit = int(query["limit"][0]) if "limit" in query else 30
                revisions = store.timeline(limit=limit)
                self._json({"ok": True, "schema_version": "lixity-timeline/1", "document": store.document, "revisions": revisions})
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_editor_delta(self) -> None:
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin request forbidden"}, 403)
            return
        try:
            with self._workspace_lock:
                store = self._editor_store()
                query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
                if set(query) - {"base", "target"} or any(len(value) != 1 or not value[0] for value in query.values()):
                    raise ValueError("Expected optional base and target revision parameters")
                result = store.delta(
                    base_revision=query["base"][0] if "base" in query else None,
                    target_revision=query["target"][0] if "target" in query else None,
                )
                self._json({"ok": True, **result})
        except (ValueError, OSError, sqlite3.Error) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_editor_asset(self) -> None:
        name = "manuscript-editor.js" if self.path.split("?")[0].endswith("editor-bootstrap.js") else "vendor/codemirror-editor.js"
        asset = Path(__file__).parents[1] / "ui" / "assets" / name
        self._send(200, asset.read_bytes(), "application/javascript; charset=utf-8")
