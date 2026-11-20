"""Guarded, project-local author decisions; no manuscript edits or task creation."""

from __future__ import annotations

from typing import Any

from ..analysis_review import ReviewStatus, record_analysis_review, review_analysis
from ..research.models import Digest, StrictModel
from ..research.repository import ResearchConflictError
from ._base import ResponseMixin


class ReviewRequest(StrictModel):
    project_token: Digest
    observation_id: Digest
    status: ReviewStatus
    expected_source_sha256: Digest
    expected_analysis_sha256: Digest
    expected_review_sha256: Digest


class AnalysisReviewRoutesMixin(ResponseMixin):
    def _handle_analysis_review(self) -> None:
        if not self._require_same_origin("Cross-origin review forbidden"):
            return
        query = self._parse_query(
            required=("project_token",),
            error_message="One selected-project token is required",
        )
        if query is None:
            return
        with self._workspace_lock:
            stale_message = "Selected analysis changed; refresh before reviewing"
            ctx = self._capture_manuscript_context(
                query["project_token"],
                require_readable=False,
                stale_message=stale_message,
            )
            if ctx is None:
                return
            try:
                result = review_analysis(
                    ctx.root,
                    manuscript=ctx.source,
                    language=ctx.language,
                    thresholds=ctx.thresholds,
                    tense_model=ctx.analysis_overrides.get("tense_model"),
                    tense_scope=ctx.analysis_overrides.get("tense_scope"),
                )
                if result["source_sha256"] != ctx.info.get("manuscript_source_sha256"):
                    raise ResearchConflictError("Manuscript differs from the displayed analysis; update analysis first")
                if not self._manuscript_context_still_current(ctx, stale_message=stale_message):
                    return
                self._ok(result)
            except (OSError, ValueError, RuntimeError) as error:
                self._log.warning("Analysis review stage=read_failed error=%s", type(error).__name__)
                self._research_error(error)

    def _handle_analysis_review_save(self, payload: dict[str, Any]) -> None:
        request = self._validate_model(
            ReviewRequest,
            payload,
            error_message="Exact analysis, source and review identities are required",
        )
        if request is None:
            return
        with self._workspace_lock:
            ctx = self._capture_manuscript_context(
                request.project_token,
                require_readable=False,
                stale_message="Selected analysis changed; refresh before reviewing",
            )
            if ctx is None:
                return
            try:
                result = record_analysis_review(
                    ctx.root,
                    request.observation_id,
                    request.status,
                    manuscript=ctx.source,
                    language=ctx.language,
                    thresholds=ctx.thresholds,
                    tense_model=ctx.analysis_overrides.get("tense_model"),
                    tense_scope=ctx.analysis_overrides.get("tense_scope"),
                    expected_source_sha256=request.expected_source_sha256,
                    expected_analysis_sha256=request.expected_analysis_sha256,
                    expected_review_sha256=request.expected_review_sha256,
                )
                self._log.info("Analysis review stage=saved status=%s", request.status)
                self._ok(result)
            except (OSError, ValueError, RuntimeError) as error:
                self._log.warning("Analysis review stage=save_failed error=%s", type(error).__name__)
                self._research_error(error)
