"""Read-only downloads of PDFs composed from the selected manuscript."""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any

from .. import pdf_export
from ..config import load_project_config, read_explicit_project_config
from ..io import FileUtils
from ..pdf_document import PdfError
from ..workspace import slugify
from ._base import ResponseMixin
from .pdf_context import manuscript_pdf_token


class ManuscriptPdfRoutesMixin(ResponseMixin):
    """Compose one selected manuscript in memory and download its PDF bytes."""

    def _handle_manuscript_pdf(self, payload: dict[str, Any]) -> None:
        layout, expected_token = payload.get("layout"), payload.get("project_token")
        if (set(payload) != {"layout", "project_token"}
                or layout not in pdf_export.PDF_LAYOUTS
                or not isinstance(expected_token, str)
                or not re.fullmatch(r"[0-9a-f]{64}", expected_token)):
            self._json({"ok": False, "message": "A PDF layout and selected project token are required"}, 400)
            return

        try:
            with self._workspace_lock:
                source = self.source_input
                if not source or not Path(source).is_file():
                    raise ValueError("No readable manuscript is selected")
                project_root = self.workspace_root
                language, title, thresholds = self.language, self.title, self.thresholds
                info = self.dashboard_info
                token = manuscript_pdf_token(
                    source, project_root=project_root, language=language,
                    title=title, thresholds=thresholds,
                )
                if expected_token != token:
                    self._json({"ok": False, "message": "The selected project changed; reload before downloading"}, 409)
                    return
                text = FileUtils.read_file(source)
                if not text.strip():
                    raise ValueError("The selected manuscript is empty")
                if project_root is not None:
                    settings = read_explicit_project_config(project_root)
                else:
                    # Legacy ambient downloads must still fail on bad config.
                    with warnings.catch_warnings():
                        warnings.filterwarnings("error", category=UserWarning, module=r"lixity\.config")
                        settings = load_project_config(source)
                identity = settings

            content = pdf_export.compose_pdf(
                text, manuscript=source, layout=layout, language=language,
                project_config=settings, title=title, identity_config=identity,
                thresholds=thresholds, require_prose=True,
            )
        except (OSError, ValueError, RuntimeError, PdfError, UserWarning) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)
            return

        with self._workspace_lock:
            current_token = manuscript_pdf_token(
                self.source_input, project_root=self.workspace_root,
                language=self.language, title=self.title, thresholds=self.thresholds,
            )
            if token != current_token or info is not self.dashboard_info:
                self._json({"ok": False, "message": "The selected project changed; reload before downloading"}, 409)
                return
            filename = f"{slugify(Path(source).stem)}-{layout}.pdf"
            self._send(
                200, content, "application/pdf",
                headers={"Content-Disposition": f'attachment; filename="{filename}"'},
            )
