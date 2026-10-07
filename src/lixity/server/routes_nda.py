"""Stateless project-language NDA draft downloads."""

from __future__ import annotations

from typing import Any

from ..nda import draft_document
from ._base import ResponseMixin


class NdaRoutesMixin(ResponseMixin):
    """Validate the five-field form and download a local draft without tracking."""

    def _handle_nda_draft(self, payload: dict[str, Any]) -> None:
        output = payload.get("format", "pdf")
        if output not in ("pdf", "text"):
            self._json({"ok": False, "message": "NDA format must be pdf or text"}, 400)
            return
        try:
            document = draft_document(
                self.workspace_root,
                name=payload.get("name", ""),
                address=payload.get("address", ""),
                project_name=payload.get("project_name"),
                date=payload.get("date"),
                place=payload.get("place", ""),
                language=self.dashboard_info.get("language_key", self.language),
            )
            content = document.pdf() if output == "pdf" else document.text.encode("utf-8")
        except (OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)
            return
        extension = "pdf" if output == "pdf" else "txt"
        self._send(
            200, content, "application/pdf" if output == "pdf" else "text/plain; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="nda.{extension}"',
                     "Content-Language": document.language},
        )
