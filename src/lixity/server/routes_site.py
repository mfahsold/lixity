"""Download a static reading website for the explicitly selected project."""

from __future__ import annotations

from logging import INFO, WARNING
from pathlib import Path
from secrets import token_hex
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from ..site_contracts import SiteExportReport, SiteExportRequest
from ..workspace import slugify
from ._base import ResponseMixin
from .constants import MAX_ARTIFACT_BYTES
from .pdf_context import manuscript_pdf_token


class SiteExportRoutesMixin(ResponseMixin):
    """Assemble an in-memory ZIP without publishing or changing project files."""

    def _handle_site_export(self, payload: dict[str, Any]) -> None:
        export_id = token_hex(16)
        started = perf_counter()
        self._log.info("Website export id=%s stage=request", export_id)
        try:
            request = SiteExportRequest.model_validate(payload)
        except ValidationError as exc:
            self._log.warning("Website export id=%s stage=validation_failed", export_id)
            message = "; ".join(str(error["msg"]).removeprefix("Value error, ")
                                for error in exc.errors(include_url=False, include_input=False))
            self._json({"ok": False, "message": message}, 400)
            return
        expected = request.project_token
        try:
            with self._workspace_lock:
                source = self.source_input
                if not source or not Path(source).is_file():
                    raise ValueError("No readable manuscript is selected")
                root = self.workspace_root
                language, title, thresholds = self.language, self.title, self.thresholds
                info = self.dashboard_info
                token = manuscript_pdf_token(source, project_root=root, language=language,
                                             title=title, thresholds=thresholds)
                if token != expected:
                    self._log.warning("Website export id=%s stage=context_changed", export_id)
                    self._json({"ok": False, "message": "The selected project changed; reload before downloading"}, 409)
                    return
                research_root = self.get_research_root()
                if (request.include_research and research_root is not None
                        and research_root.resolve() != Path(root).resolve()):
                    raise ValueError("The selected research belongs to another project; open that project before exporting it")

            from ..site_export import prepare_site

            bundle = prepare_site(
                root, manuscript=source, language=language, title=title, thresholds=thresholds,
                **request.export_options().model_dump(exclude_defaults=True),
            )
            content = bundle.to_zip()
            if len(content) > MAX_ARTIFACT_BYTES:
                self._log.warning("Website export id=%s stage=download_limit", export_id)
                self._json({"ok": False, "message": "Website ZIP exceeds the download limit; use export-site to a local directory"}, 413)
                return
        except (OSError, ValueError, RuntimeError) as exc:
            self._log.warning("Website export id=%s stage=preparation_failed error=%s",
                              export_id, type(exc).__name__)
            self._json({"ok": False, "message": str(exc)}, 400)
            return
        with self._workspace_lock:
            current = manuscript_pdf_token(self.source_input, project_root=self.workspace_root,
                                           language=self.language, title=self.title,
                                           thresholds=self.thresholds)
            if current != token or info is not self.dashboard_info:
                self._log.warning("Website export id=%s stage=context_changed", export_id)
                self._json({"ok": False, "message": "The selected project changed; reload before downloading"}, 409)
                return
            filename = slugify(bundle.manifest["project"]["title"]) + "-reading-website.zip"
            self._log.info("Website export id=%s stage=prepared bytes=%d duration_ms=%d",
                           export_id, len(content), round((perf_counter() - started) * 1000))
            sent = self._send(200, content, "application/zip",
                              headers={"Content-Disposition": f'attachment; filename="{filename}"',
                                       "X-Lixity-Export-ID": export_id})
            self._log.log(INFO if sent else WARNING, "Website export id=%s stage=%s",
                          export_id, "body_written" if sent else "client_disconnected")

    def _handle_site_export_report(self, payload: dict[str, Any]) -> None:
        try:
            report = SiteExportReport.model_validate(payload)
        except ValidationError:
            self._json({"ok": False, "message": "Invalid export receipt"}, 400)
            return
        self._log.log(WARNING if report.error_name else INFO,
                      "Website export browser receipt id=%s stage=%s error=%s",
                      report.export_id, report.stage, report.error_name or "none")
        self._json({"ok": True})
