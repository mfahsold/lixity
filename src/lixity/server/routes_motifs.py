"""Project-bound manuscript motif and phrase search route."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from ..io import FileUtils
from ..motifs import InvalidSearchPattern, search_manuscript
from ..pipeline import resolve_document_config
from ..research.models import Digest, StrictModel
from ._base import ResponseMixin
from .middleware import load_selected_project_config
from .pdf_context import manuscript_pdf_token


class MotifSearchRequest(StrictModel):
    query: str
    regex: bool = False
    case_sensitive: bool = False
    limit: int = Field(default=500, ge=1, le=2000)
    project_token: Digest | None = None


class MotifRoutesMixin(ResponseMixin):
    """Search the selected manuscript in Python without accepting prose from HTTP clients."""

    def _handle_motif_search(self, payload: dict[str, Any]) -> None:
        request = self._validate_model(
            MotifSearchRequest,
            payload,
            error_message="Provide a non-empty search query and valid search options",
        )
        if request is None:
            return

        with self._workspace_lock:
            source = self._require_selected_manuscript(
                readable=True,
                missing_message="No readable manuscript is selected",
            )
            if source is None:
                return
            if request.project_token is not None:
                current_token = manuscript_pdf_token(
                    source,
                    project_root=self.workspace_root,
                    language=self.language,
                    title=self.title,
                    thresholds=self.thresholds,
                )
                if request.project_token != current_token:
                    self._error(
                        "The selected project changed; reload before searching",
                        409,
                        error_code="stale-context",
                    )
                    return
            try:
                text, source_sha256 = FileUtils.read_source_snapshot(source)
                settings = load_selected_project_config(
                    source,
                    project_root=self.get_author_project_root(),
                    strict_warnings=True,
                    overrides=self.project_open_overrides,
                )
            except (OSError, ValueError, UserWarning) as exc:
                self._error(str(exc), 400)
                return
            language = self.language

        try:
            config, _resolved = resolve_document_config(
                text, language, project_config=settings
            )
            result = search_manuscript(
                text,
                request.query,
                config,
                is_regex=request.regex,
                case_sensitive=request.case_sensitive,
                limit=request.limit,
            )
        except InvalidSearchPattern as exc:
            self._error(str(exc), 400, error_code="invalid-regex")
            return
        except (ValueError, RuntimeError) as exc:
            self._error(str(exc), 400)
            return

        self._ok({"source_sha256": source_sha256, **result})
