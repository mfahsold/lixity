"""Inline work-marker routes (``marker-add`` / ``marker-resolve``)."""

from __future__ import annotations

import os
from typing import Any

from ..io import FileUtils
from ..markers import add_marker, resolve_marker
from ._base import ResponseMixin


class MarkerRoutesMixin(ResponseMixin):
    """Handlers for author work markers stored beside the manuscript."""

    def _handle_marker(self, action: str, payload: dict[str, Any]) -> None:
        src = self.source_input
        if not src or not os.path.isfile(src):
            self._json({"ok": False, "message": "No writable manuscript loaded"}, 400)
            return

        try:
            with open(src, encoding="utf-8") as f:
                text = f.read()
        except OSError as exc:
            self._json({"ok": False, "message": f"Failed to read manuscript: {exc}"}, 500)
            return

        if action == "marker-add":
            kind = str(payload.get("kind") or "pruefen").strip().lower()
            try:
                line = int(payload.get("line") or 0)
            except ValueError:
                line = 0
            note = str(payload.get("note") or "").strip()
            if line < 1:
                self._json({"ok": False, "message": "Valid line number required"}, 400)
                return

            new_text, marker = add_marker(text, kind, note, line)
            FileUtils.atomic_write_if_changed(src, new_text)
            self.refresh()
            self._json(
                {
                    "ok": True,
                    "message": f"Marker added: {marker.id} ({kind}) before line {line}",
                    "reload": True,
                }
            )
            return

        if action == "marker-resolve":
            marker_id = str(payload.get("id") or "").strip()
            if not marker_id:
                self._json({"ok": False, "message": "Marker ID missing"}, 400)
                return

            new_text = resolve_marker(text, marker_id)
            FileUtils.atomic_write_if_changed(src, new_text)
            self.refresh()
            self._json({"ok": True, "message": f"Marker {marker_id} resolved", "reload": True})
            return

        self._json({"ok": False, "message": f"Unknown marker action: {action}"}, 400)

