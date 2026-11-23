"""Native PDF downloads for manuscripts and saved research dossiers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import pdf_export
from ..io import FileUtils
from ..pdf_document import PdfError
from ..research.dossier_pdf import compose_dossier_pdf
from ..research.models import Reference
from ..workspace import slugify
from ._base import ResponseMixin
from .middleware import load_selected_project_config

DOSSIER_PDF_PATH = "/api/research/dossier-pdf"


class PdfRoutesMixin(ResponseMixin):
    """Compose selected documents in memory and download their PDF bytes."""

    def _handle_manuscript_pdf(self, payload: dict[str, Any]) -> None:
        layout, expected_token = payload.get("layout"), payload.get("project_token")
        if (set(payload) != {"layout", "project_token"}
                or layout not in pdf_export.PDF_LAYOUTS
                or not isinstance(expected_token, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_token)):
            self._error("A PDF layout and selected project token are required", 400)
            return

        ctx = self._capture_manuscript_context(
            expected_token,
            require_readable=True,
            stale_message="The selected project changed; reload before downloading",
        )
        if ctx is None:
            return

        try:
            with self._workspace_lock:
                text = FileUtils.read_file(ctx.source)
                if not text.strip():
                    raise ValueError("The selected manuscript is empty")
                identity = load_selected_project_config(
                    ctx.source,
                    project_root=ctx.root,
                    strict_warnings=True,
                )
                settings = {**identity, **ctx.analysis_overrides}

            content = pdf_export.compose_pdf(
                text, manuscript=ctx.source, layout=layout, language=ctx.language,
                project_config=settings, title=ctx.title, identity_config=identity,
                thresholds=ctx.thresholds, require_prose=True,
            )
        except (OSError, ValueError, RuntimeError, PdfError, UserWarning) as exc:
            self._error(str(exc), 400)
            return

        if not self._manuscript_context_still_current(
            ctx, stale_message="The selected project changed; reload before downloading"
        ):
            return
        filename = f"{slugify(Path(ctx.source).stem)}-{layout}.pdf"
        self._send_pdf(content, filename)

    def _handle_research_dossier_pdf(self) -> None:
        query = self._parse_query(required=("id", "revision", "research_token"))
        if query is None:
            return
        try:
            revision = int(query["revision"])
        except ValueError:
            self._error("Revision must be a positive integer", 400)
            return
        ref = self._validate_model(Reference, {"id": query["id"], "revision": revision})
        if ref is None:
            return
        token = query["research_token"]
        with self._workspace_lock:
            if not self._research_context_matches(token):
                return
            root = self._require_research_root()
            if root is None:
                return
            root = root.resolve()
        try:
            result = compose_dossier_pdf(root, ref)
        except (OSError, ValueError, RuntimeError, PdfError, UserWarning) as exc:
            self._research_error(exc)
            return
        with self._workspace_lock:
            if not self._research_context_matches(token):
                return
            registry = getattr(self.server, "workspaces", None)
            if registry is not None and not registry.contains(type(self)):
                self._error("Workspace expired; reopen the project from the app home.", 410, error_code="stale-context")
                return
        if result is None:
            self._error("Dossier revision unavailable", 404)
            return
        title, content = result
        self._send_pdf(content, f"{slugify(title, fallback='dossier')[:120]}-v{ref.revision}.pdf")

    def _send_pdf(self, content: bytes, filename: str) -> None:
        self._send(
            200, content, "application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
