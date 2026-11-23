"""Native manual manuscript associations through the shared research API."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ..research import api as research_api
from ..research.manuscript import ManuscriptLinkExistsError
from ..research.repository import ResearchConflictError, ResearchError
from .pdf_context import manuscript_pdf_token
from .routes_research import ResearchRoutesMixin


class ManuscriptResearchRoutesMixin(ResearchRoutesMixin):
    """Keep displayed selection, archive context and retention explicit."""

    def _manuscript_context(self, token: Any) -> tuple[Path, str, dict[str, Any]]:
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{64}", token):
            raise ResearchError("A selected manuscript context token is required")
        root, source = self.get_research_root(), self.source_input
        if root is None or not (root / "research").is_dir():
            raise ResearchError("Research project not initialized")
        if source is None:
            raise ResearchError("Select a manuscript inside the research project")
        current = manuscript_pdf_token(source, project_root=self.workspace_root,
                                       language=self.language, title=self.title, thresholds=self.thresholds)
        if token != current:
            raise ResearchConflictError("Selected manuscript or settings changed; refresh before continuing")
        return root, source, self._research_manuscript_settings(root)

    def _handle_manuscript_claim_link(self, payload: dict[str, Any]) -> None:
        allowed = {"project_id", "research_token", "project_token", "expected_snapshot",
                   "expected_source_sha256", "claim_id", "claim_revision", "selection",
                   "allow_retention", "note"}
        if (set(payload) - allowed or payload.get("allow_retention") is not True
                or type(payload.get("claim_revision")) is not int
                or payload["claim_revision"] < 1 or not isinstance(payload.get("selection"), dict)
                or any(not isinstance(payload.get(key), str) or not payload[key].strip()
                       for key in ("project_id", "claim_id", "expected_snapshot", "expected_source_sha256"))
                or (payload.get("note") is not None and not isinstance(payload["note"], str))):
            self._json({"ok": False, "message": "Review the selected text and claim, and permit retaining the quote before saving"}, 400)
            return
        # New routes always require both context tokens, including tokenless callers.
        with self._workspace_lock:
            if not self._research_context_matches(payload.get("research_token")):
                return
            try:
                root, source, settings = self._manuscript_context(payload.get("project_token"))
            except ResearchConflictError as exc:
                self._json({"ok": False, "code": "stale-context", "message": str(exc)}, 409)
                return
            except (ResearchError, OSError, ValueError, TypeError, UserWarning) as exc:
                self._json({"ok": False, "message": str(exc)}, 400)
                return
            try:
                result = research_api.link_manuscript_claim(
                    root, source, payload["claim_id"], claim_revision=payload["claim_revision"],
                    selection=payload["selection"], expected_project_id=payload["project_id"],
                    expected_snapshot=payload["expected_snapshot"],
                    expected_source_sha256=payload["expected_source_sha256"], allow_retention=True,
                    note=payload.get("note"), language=self.language, project_config=settings,
                )
                self._json({"ok": True, **result})
            except ManuscriptLinkExistsError as exc:
                self._json({"ok": False, "code": "duplicate-link", "link_id": exc.link_id,
                            "message": str(exc)}, 409)
            except ResearchConflictError as exc:
                self._json({"ok": False, "code": "stale-archive", "message": str(exc)}, 409)
            except (ResearchError, OSError, ValueError, TypeError, UserWarning) as exc:
                self._research_error(exc)

    def _handle_manuscript_claim_review(self) -> None:
        query = self._parse_query(
            required=("research_token", "project_token"),
            error_message="Choose one selected manuscript and research context",
        )
        if query is None:
            return
        with self._workspace_lock:
            if not self._research_context_matches(query["research_token"]):
                return
            try:
                root, source, settings = self._manuscript_context(query["project_token"])
                result = research_api.review_manuscript_links(
                    root, source, language=self.language, project_config=settings, include_context=True,
                )
                self._ok(result)
            except ResearchConflictError as exc:
                self._error(str(exc), 409, error_code="stale-context")
            except (ResearchError, OSError, ValueError, TypeError, UserWarning) as exc:
                self._error(str(exc), 400)

    def _handle_manuscript_terms_review(self) -> None:
        query = self._parse_query(
            required=("research_token", "project_token"),
            optional=("term", "dossier_id"),
            non_empty=("term", "dossier_id"),
            error_message="Choose one selected manuscript and research context",
        )
        if query is None:
            return
        with self._workspace_lock:
            if not self._research_context_matches(query["research_token"]):
                return
            try:
                root, source, settings = self._manuscript_context(query["project_token"])
                result = research_api.review_manuscript_terms(
                    root, source, term=query.get("term"), dossier_id=query.get("dossier_id"),
                    language=self.language, project_config=settings,
                )
                self._ok(result)
            except ResearchConflictError as exc:
                self._error(str(exc), 409, error_code="stale-context")
            except (ResearchError, OSError, ValueError, TypeError, UserWarning) as exc:
                self._error(str(exc), 400)

    def _handle_manuscript_claim_reanchor(self, payload: dict[str, Any]) -> None:
        allowed = {"project_id", "research_token", "project_token", "expected_snapshot",
                   "expected_revision", "expected_source_sha256", "link_id", "actor"}
        if (set(payload) - allowed
                or type(payload.get("expected_revision")) is not int or payload["expected_revision"] < 1
                or any(not isinstance(payload.get(key), str) or not payload[key].strip()
                       for key in ("project_id", "link_id", "expected_snapshot", "expected_source_sha256"))):
            self._json({"ok": False, "message": "Review the moved or adjusted anchor before re-pinning it"}, 400)
            return
        with self._workspace_lock:
            if not self._research_context_matches(payload.get("research_token")):
                return
            try:
                root, source, settings = self._manuscript_context(payload.get("project_token"))
            except ResearchConflictError as exc:
                self._json({"ok": False, "code": "stale-context", "message": str(exc)}, 409)
                return
            except (ResearchError, OSError, ValueError, TypeError, UserWarning) as exc:
                self._json({"ok": False, "message": str(exc)}, 400)
                return
            try:
                result = research_api.reanchor_manuscript_link(
                    root, source, payload["link_id"],
                    expected_project_id=payload["project_id"],
                    expected_snapshot=payload["expected_snapshot"],
                    expected_revision=payload["expected_revision"],
                    expected_source_sha256=payload["expected_source_sha256"],
                    actor=payload.get("actor", "local-author"),
                    language=self.language, project_config=settings,
                )
                self._json({"ok": True, **result})
            except ResearchConflictError as exc:
                self._json({"ok": False, "code": "stale-archive", "message": str(exc)}, 409)
            except (ResearchError, OSError, ValueError, TypeError, UserWarning) as exc:
                self._research_error(exc)

    def _handle_manuscript_claim_links(self) -> None:
        query = self._parse_query(
            required=("research_token",),
            optional=("claim_id", "include_retracted"),
            error_message="Choose one research context and optional claim filter",
        )
        if query is None:
            return
        retracted = query.get("include_retracted", "false")
        if retracted not in ("true", "false"):
            self._error("Choose one research context and optional claim filter", 400)
            return
        with self._workspace_lock:
            if not self._research_context_matches(query["research_token"]):
                return
            root = self._require_research_root()
            if root is None:
                return
            try:
                self._ok(research_api.list_manuscript_links(
                    root, claim_id=query.get("claim_id"), include_retracted=retracted == "true",
                ))
            except (ResearchError, OSError, ValueError, TypeError) as exc:
                self._error(str(exc), 400)
