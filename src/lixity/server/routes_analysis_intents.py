"""Local author intentions over the selected manuscript's measured scenes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..analysis_intents import (
    IntentContext,
    IntentMutation,
    read_scene_intents,
    write_scene_intents,
)
from ..research.models import Digest, StrictModel
from ..research.repository import ResearchConflictError
from ._base import ResponseMixin
from .middleware import SelectedManuscriptContext
from .pdf_context import project_settings_token


class IntentRequest(StrictModel):
    project_token: Digest
    mutation: IntentMutation


def _require_displayed_settings(context: SelectedManuscriptContext) -> None:
    if context.info.get("project_settings_token") != project_settings_token(context.root, context.source):
        raise ResearchConflictError("Project settings differ from the displayed analysis; refresh before reviewing")


class AnalysisIntentRoutesMixin(ResponseMixin):
    def _capture_intent_context(self, token: str) -> tuple[SelectedManuscriptContext, IntentContext] | None:
        selected = self._capture_manuscript_context(token)
        if selected is None:
            return None
        context = selected.info.get("scene_intent_context")
        if not isinstance(context, IntentContext):
            self._error("Open a manuscript with measured scenes before reviewing intentions", 400)
            return None
        return selected, context

    def _handle_analysis_intents(self) -> None:
        query = self._parse_query(required=("project_token",), error_message="One selected-project token is required")
        if query is None:
            return
        with self._workspace_lock:
            captured = self._capture_intent_context(query["project_token"])
            if captured is None:
                return
            selected, context = captured
            try:
                result = read_scene_intents(selected.root, Path(selected.source).resolve(), context)
                _require_displayed_settings(selected)
                if self._manuscript_context_still_current(selected):
                    self._ok(result)
            except ResearchConflictError as error:
                self._error(str(error), 409)
            except (OSError, ValueError, RuntimeError) as error:
                self._log.warning("Analysis intentions stage=read_failed error=%s", type(error).__name__)
                self._error("The saved intentions or displayed manuscript could not be read", 400)

    def _handle_analysis_intents_save(self, payload: dict[str, Any]) -> None:
        request = self._validate_model(IntentRequest, {
            "project_token": payload.get("project_token"),
            "mutation": {key: value for key, value in payload.items() if key != "project_token"},
        }, error_message="A valid intention action and exact project, source, analysis and state identities are required")
        if request is None:
            return
        with self._workspace_lock, self._document_lock():
            captured = self._capture_intent_context(request.project_token)
            if captured is None:
                return
            selected, context = captured
            try:
                result = write_scene_intents(
                    selected.root, Path(selected.source).resolve(), context, request.mutation,
                    require_settings=lambda: _require_displayed_settings(selected),
                )
                self._ok(result)
            except ResearchConflictError as error:
                self._error(str(error), 409)
            except (OSError, ValueError, RuntimeError) as error:
                self._log.warning("Analysis intentions stage=save_failed error=%s", type(error).__name__)
                self._error("The intention change could not be saved for this manuscript", 400)
