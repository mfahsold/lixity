"""Read-only downloads of PDFs composed from the selected manuscript."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .. import pdf_export
from ..io import FileUtils
from ..pdf_document import PdfError
from ..workspace import slugify
from ._base import ResponseMixin
from .middleware import load_selected_project_config


class ManuscriptPdfRoutesMixin(ResponseMixin):
    """Compose one selected manuscript in memory and download its PDF bytes."""

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
        self._send(
            200, content, "application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
