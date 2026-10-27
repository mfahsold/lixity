"""Guarded, project-local author decisions; no manuscript edits or task creation."""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

from pydantic import ValidationError

from ..analysis_review import ReviewStatus, record_analysis_review, review_analysis
from ..research.models import Digest, StrictModel
from ..research.repository import ResearchConflictError
from ._base import ResponseMixin
from .pdf_context import manuscript_pdf_token


class ReviewRequest(StrictModel):
    project_token: Digest
    observation_id: Digest
    status: ReviewStatus
    expected_source_sha256: Digest
    expected_analysis_sha256: Digest
    expected_review_sha256: Digest


class AnalysisReviewRoutesMixin(ResponseMixin):
    def _review_context(self, token: str) -> bool:
        current = manuscript_pdf_token(self.source_input, project_root=self.workspace_root,
            language=self.language, title=self.title, thresholds=self.thresholds)
        if not current or current != token:
            self._json({"ok": False, "message": "Selected analysis changed; refresh before reviewing"}, 409)
            return False
        return True

    def _handle_analysis_review(self) -> None:
        if not self._same_origin():
            self._json({"ok": False, "message": "Cross-origin review forbidden"}, 403)
            return
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if set(query) != {"project_token"} or len(query["project_token"]) != 1:
            self._json({"ok": False, "message": "One selected-project token is required"}, 400)
            return
        with self._workspace_lock:
            if not self._review_context(query["project_token"][0]):
                return
            try:
                result = review_analysis(self.workspace_root, manuscript=self.source_input,
                                        language=self.language, thresholds=self.thresholds,
                                        tense_model=self.project_open_overrides.get("tense_model"),
                                        tense_scope=self.project_open_overrides.get("tense_scope"))
                if result["source_sha256"] != self.dashboard_info.get("manuscript_source_sha256"):
                    raise ResearchConflictError("Manuscript differs from the displayed analysis; update analysis first")
                self._json({"ok": True, **result})
            except (OSError, ValueError, RuntimeError) as error:
                self._log.warning("Analysis review stage=read_failed error=%s", type(error).__name__)
                self._json({"ok": False, "message": str(error)}, 409 if isinstance(error, ResearchConflictError) else 400)

    def _handle_analysis_review_save(self, payload: dict[str, Any]) -> None:
        try:
            request = ReviewRequest.model_validate(payload)
        except ValidationError:
            self._json({"ok": False, "message": "Exact analysis, source and review identities are required"}, 400)
            return
        with self._workspace_lock:
            if not self._review_context(request.project_token):
                return
            try:
                result = record_analysis_review(self.workspace_root, request.observation_id, request.status,
                    manuscript=self.source_input, language=self.language, thresholds=self.thresholds,
                    tense_model=self.project_open_overrides.get("tense_model"),
                    tense_scope=self.project_open_overrides.get("tense_scope"),
                    expected_source_sha256=request.expected_source_sha256,
                    expected_analysis_sha256=request.expected_analysis_sha256,
                    expected_review_sha256=request.expected_review_sha256)
                self._log.info("Analysis review stage=saved status=%s", request.status)
                self._json({"ok": True, **result})
            except (OSError, ValueError, RuntimeError) as error:
                self._log.warning("Analysis review stage=save_failed error=%s", type(error).__name__)
                self._json({"ok": False, "message": str(error)}, 409 if isinstance(error, ResearchConflictError) else 400)
