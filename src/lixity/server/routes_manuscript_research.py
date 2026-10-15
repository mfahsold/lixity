"""Native manual manuscript associations through the shared research API."""

from __future__ import annotations

import re
import warnings
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..config import load_project_config
from ..research import api as research_api
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
        with warnings.catch_warnings():
            warnings.filterwarnings("error", category=UserWarning, module=r"lixity\.config")
            settings = load_project_config(source)
        return root, source, settings

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
            except ResearchConflictError as exc:
                self._json({"ok": False, "code": "stale-archive", "message": str(exc)}, 409)
            except (ResearchError, OSError, ValueError, TypeError, UserWarning) as exc:
                self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_manuscript_claim_review(self) -> None:
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        if (set(query) - {"research_token", "project_token"}
                or any(len(query.get(key, [])) != 1 for key in ("research_token", "project_token"))):
            self._json({"ok": False, "message": "Choose one selected manuscript and research context"}, 400)
            return
        with self._workspace_lock:
            if not self._research_context_matches(query["research_token"][0]):
                return
            try:
                root, source, settings = self._manuscript_context(query["project_token"][0])
                result = research_api.review_manuscript_links(root, source, language=self.language, project_config=settings)
                self._json({"ok": True, **result})
            except ResearchConflictError as exc:
                self._json({"ok": False, "code": "stale-context", "message": str(exc)}, 409)
            except (ResearchError, OSError, ValueError, TypeError, UserWarning) as exc:
                self._json({"ok": False, "message": str(exc)}, 400)

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
                self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_manuscript_claim_links(self) -> None:
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        retracted = query.get("include_retracted", ["false"])
        if (set(query) - {"research_token", "claim_id", "include_retracted"}
                or len(query.get("research_token", [])) != 1
                or len(query.get("claim_id", [])) > 1 or len(retracted) != 1
                or retracted[0] not in ("true", "false")):
            self._json({"ok": False, "message": "Choose one research context and optional claim filter"}, 400)
            return
        with self._workspace_lock:
            if not self._research_context_matches(query["research_token"][0]):
                return
            root = self.get_research_root()
            if root is None or not (root / "research").is_dir():
                self._json({"ok": False, "message": "Research project not initialized"}, 404)
                return
            try:
                self._json({"ok": True, **research_api.list_manuscript_links(
                    root, claim_id=query.get("claim_id", [None])[0], include_retracted=retracted[0] == "true",
                )})
            except (ResearchError, OSError, ValueError, TypeError) as exc:
                self._json({"ok": False, "message": str(exc)}, 400)
