"""Research archive routes: sources, dossiers, claims, evidence, decisions, search.

Every handler delegates the domain work to :mod:`lixity.research.api`; this
module owns only request parsing, response envelopes and the explicit HTTP status
mapping. Storage, revisions and retention rules live in the research package.
"""

from __future__ import annotations

import base64
import binascii
import contextlib
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from ..research import api as research_api
from ..research.repository import ResearchConflictError, ResearchError
from ._base import ResponseMixin

RESEARCH_RECORD_KINDS = frozenset(("dossier", "claim", "evidence_link", "decision"))


class ResearchRoutesMixin(ResponseMixin):
    """Handlers for the explicit-project research workspace."""

    def _handle_research_status(self) -> None:
        root = self.get_research_root()
        ocr_diag = research_api.ocr_status()
        if not root or not (root / "research").is_dir():
            self._json(
                {
                    "ok": True,
                    "initialized": False,
                    "project_root": str(root or self.workspace_root or ""),
                    "ocr": ocr_diag,
                }
            )
            return
        try:
            src_data = research_api.list_sources(root)
            dos_data = research_api.list_dossiers(root)
            claims_data = research_api.list_claims(root)
            decisions_data = research_api.list_decisions(root)
            self._json(
                {
                    "ok": True,
                    "initialized": True,
                    "project_root": str(root),
                    "project_id": src_data.get("project_id", ""),
                    "project_title": src_data.get("project_title", ""),
                    "project_language": src_data.get("project_language", ""),
                    "sources": src_data.get("sources", []),
                    "dossiers": dos_data.get("dossiers", []),
                    "claims": claims_data.get("claims", []),
                    "decisions": decisions_data.get("decisions", []),
                    "sources_count": len(src_data.get("sources", [])),
                    "dossiers_count": len(dos_data.get("dossiers", [])),
                    "claims_count": len(claims_data.get("claims", [])),
                    "decisions_count": len(decisions_data.get("decisions", [])),
                    "ocr": ocr_diag,
                }
            )
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 500)

    def _handle_research_sources(self) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        source_id = parse_qs(urlparse(self.path).query).get("id", [None])[0]
        try:
            if source_id:
                data = research_api.get_source(root, source_id)
            else:
                data = research_api.list_sources(root)
            self._json({"ok": True, **data})
        except (ResearchError, KeyError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_dossiers(self) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        dossier_id = parse_qs(urlparse(self.path).query).get("id", [None])[0]
        try:
            if dossier_id:
                data = research_api.get_dossier(root, dossier_id)
            else:
                data = research_api.list_dossiers(root)
            self._json({"ok": True, **data})
        except (ResearchError, KeyError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_claims(self) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        dossier_id = None
        claim_id = None
        if "?" in self.path:
            parsed_qs = parse_qs(urlparse(self.path).query)
            dossier_id = parsed_qs.get("dossier_id", [None])[0]
            claim_id = parsed_qs.get("claim_id", [None])[0]
        try:
            if claim_id:
                data = research_api.list_evidence_links(root, claim_id=claim_id)
            else:
                data = research_api.list_claims(root, dossier_id=dossier_id)
            self._json({"ok": True, **data})
        except (ResearchError, KeyError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_decisions(self) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        try:
            data = research_api.list_decisions(root)
            self._json({"ok": True, **data})
        except (ResearchError, KeyError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_matrix(self) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        fmt = query.get("format", ["json"])[0].lower()
        if fmt not in ("json", "md", "csv"):
            fmt = "json"
        try:
            matrix = research_api.claim_matrix_data(root)
            if fmt == "json":
                self._json({"ok": True, **matrix})
                return
            if fmt == "csv":
                rendered = research_api.render_claim_matrix(matrix, format="csv")
                self._send(200, rendered.encode("utf-8"), "text/csv; charset=utf-8")
                return
            rendered = research_api.render_claim_matrix(matrix, format="md")
            self._send(200, rendered.encode("utf-8"), "text/markdown; charset=utf-8")
        except (ResearchError, KeyError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_record_read(self, *, history: bool) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        query = parse_qs(urlparse(self.path).query, keep_blank_values=True)
        kind = query.get("kind", [""])[0]
        record_id = query.get("id", [""])[0]
        if kind not in RESEARCH_RECORD_KINDS or not record_id:
            self._json({"ok": False, "message": "A valid kind and record ID are required"}, 400)
            return
        revision: int | None = None
        if not history and "revision" in query:
            raw_revision = query["revision"][0]
            if len(raw_revision) > 9 or not raw_revision.isdecimal() or int(raw_revision) < 1:
                self._json({"ok": False, "message": "Revision must be a positive integer"}, 400)
                return
            revision = int(raw_revision)
        try:
            result = (
                research_api.record_history(root, kind, record_id)
                if history
                else research_api.get_record(root, kind, record_id, revision=revision)
            )
            self._json({"ok": True, **result})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_record_revise(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        kind = payload.get("kind")
        record_id = payload.get("id")
        changes = payload.get("changes")
        snapshot = payload.get("expected_snapshot")
        revision = payload.get("expected_revision")
        change_kind = payload.get("change_kind")
        reason = payload.get("reason")
        actor = payload.get("actor", "local-author")
        if (
            not isinstance(kind, str)
            or kind not in RESEARCH_RECORD_KINDS
            or not isinstance(record_id, str)
            or not record_id.strip()
            or not isinstance(changes, dict)
            or not changes
            or not isinstance(snapshot, str)
            or not snapshot.strip()
            or type(revision) is not int
            or revision < 1
            or change_kind not in ("correction", "supersession")
            or not isinstance(reason, str)
            or not reason.strip()
            or not isinstance(actor, str)
            or not actor.strip()
        ):
            self._json({"ok": False, "message": "Invalid research revision request"}, 400)
            return
        try:
            result = research_api.revise_record(
                root,
                kind,
                record_id,
                changes=changes,
                expected_snapshot=snapshot,
                expected_revision=revision,
                change_kind=change_kind,
                reason=reason,
                actor=actor,
            )
            self._json({"ok": True, **result})
        except ResearchConflictError as exc:
            self._json({"ok": False, "message": str(exc)}, 409)
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_init(self, payload: dict[str, Any]) -> None:
        target_root = Path(self.research_dir or self.workspace_root or ".").resolve()
        title = str(payload.get("title") or target_root.name or "Research").strip()
        lang = str(payload.get("language") or "en").strip().lower()
        try:
            res = research_api.init(target_root, title=title, language=lang)
            self.__class__.research_dir = str(target_root)
            self._json({"ok": True, "message": f"Research initialized for '{title}'", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_ingest(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        if payload.get("allow_retention") is not True:
            self._json({"ok": False, "message": "Explicit retention permission is required (allow_retention: true)"}, 400)
            return

        content = payload.get("content") or payload.get("text")
        content_base64 = payload.get("content_base64")
        filename = str(payload.get("filename") or "").strip()
        file_path = payload.get("file")
        title = payload.get("title") or (Path(filename).name if filename else (Path(str(file_path)).name if file_path else "Untitled Source"))
        language = payload.get("language") or None
        raw_tags = payload.get("tags")
        tags: list[str] = []
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        context = {"tags": tags} if tags else None

        def ingest_file(path: str) -> dict[str, Any]:
            return research_api.ingest(
                root, path, allow_retention=True, title=title, language=language,
                context=context, origin_url=payload.get("origin_url"),
            )

        def ingest_bytes(data: bytes, suffix: str) -> dict[str, Any]:
            with tempfile.NamedTemporaryFile("wb", suffix=suffix, delete=False) as upload:
                upload.write(data)
                temp_path = upload.name
            try:
                return ingest_file(temp_path)
            finally:
                with contextlib.suppress(OSError):
                    os.unlink(temp_path)

        try:
            if content_base64 is not None:
                try:
                    raw_bytes = base64.b64decode(content_base64)
                except (ValueError, binascii.Error) as exc:
                    self._json({"ok": False, "message": f"Invalid base64 payload: {exc}"}, 400)
                    return
                if not raw_bytes:
                    self._json({"ok": False, "message": "Source content cannot be empty"}, 400)
                    return
                ext = Path(filename).suffix.lower() if filename and Path(filename).suffix else ".pdf"
                res = ingest_bytes(raw_bytes, ext)
            elif content is not None:
                if not isinstance(content, str) or not content.strip():
                    self._json({"ok": False, "message": "Source content cannot be empty"}, 400)
                    return
                ext = (
                    Path(filename).suffix.lower() if filename and Path(filename).suffix else ".txt"
                )
                res = ingest_bytes(content.encode("utf-8"), ext)
            elif file_path:
                res = ingest_file(str(file_path))
            else:
                self._json(
                    {
                        "ok": False,
                        "message": "Either 'content', 'content_base64' or 'file' must be provided",
                    },
                    400,
                )
                return

            with contextlib.suppress(ResearchError, OSError, ValueError):
                research_api.reindex(root)

            self._json({"ok": True, "message": f"Source '{title}' ingested successfully", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_zotero(self, payload: dict[str, Any], *, capture: bool) -> None:
        from ..research import zotero
        from ..research.repository import Repository

        root = self.get_research_root()
        try:
            if not root or not (root / "research").is_dir():
                raise ResearchError("Research project not initialized")
            snapshot = Repository(root).snapshot()
            if payload.get("project_id") != snapshot.project.id:
                raise ResearchError("Research project changed; reload the Zotero selection")
            library = payload.get("library", "")
            if capture:
                if payload.get("allow_retention") is not True:
                    raise ResearchError("Explicit local retention permission is required")
                if (
                    not isinstance(payload.get("expected_server_id"), str)
                    or not payload["expected_server_id"]
                ):
                    raise ResearchError("Preview a Zotero instance before capture")
                if payload.get("item_key") and not payload.get("attachment_key"):
                    result = zotero.ingest_item(
                        root,
                        library=library,
                        item_key=payload["item_key"],
                        allow_retention=True,
                        expected_server_id=payload["expected_server_id"],
                    )
                else:
                    result = zotero.ingest(
                        root,
                        library=library,
                        attachment_key=payload.get("attachment_key", ""),
                        source_id=payload.get("source_id"),
                        allow_retention=True,
                        expected_server_id=payload["expected_server_id"],
                    )
            elif payload.get("mode") == "collections":
                result = zotero.collections(root, library=library, start=payload.get("start", 0))
            else:
                result = zotero.browse(
                    root,
                    library=library,
                    query=payload.get("query", ""),
                    item_key=payload.get("item_key"),
                    collection_key=payload.get("collection_key"),
                    limit=payload.get("limit", 20),
                    start=payload.get("start", 0),
                )
                sources = research_api.list_sources(root)["sources"]
                result["captures"] = [
                    {"source_id": source["id"], **source["context"]["external_reference"]}
                    for source in sources
                    if source["context"].get("external_reference")
                ]
            self._json({"ok": True, **result})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_search(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        query = str(payload.get("query") or "").strip()
        if not query:
            self._json({"ok": False, "message": "Empty query"}, 400)
            return
        limit = payload.get("limit", 20)
        scope = payload.get("scope", "sources")
        try:
            res = research_api.search(root, query, limit=limit, scope=scope, ensure_fresh=True)
            self._json({"ok": True, **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_dossier(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        title = str(payload.get("title") or "").strip()
        body = str(payload.get("body") or "").strip()
        if not title:
            self._json({"ok": False, "message": "Dossier title is required"}, 400)
            return
        lang = str(payload.get("language") or "en").strip().lower()
        raw_tags = payload.get("tags")
        tags: list[str] = []
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        raw_eids = payload.get("evidence_ids")
        evidence_ids: list[str] = []
        if isinstance(raw_eids, list):
            evidence_ids = [str(e).strip() for e in raw_eids if str(e).strip()]

        try:
            res = research_api.create_dossier(
                root, title=title, body=body, language=lang, tags=tags, evidence_ids=evidence_ids
            )
            self._json({"ok": True, "message": f"Dossier '{title}' created", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_compare(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 404)
            return
        source_id = str(payload.get("source_id") or "").strip()
        if not source_id:
            self._json({"ok": False, "message": "source_id is required"}, 400)
            return
        manuscript = payload.get("manuscript") or self.source_input
        if not manuscript:
            self._json(
                {"ok": False, "message": "No manuscript loaded or specified for comparison"}, 400
            )
            return
        try:
            res = research_api.compare_source(root, source_id, manuscript, language=self.language)
            self._json({"ok": True, **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_claim_add(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        title = str(payload.get("title") or "").strip()
        statement = str(payload.get("statement") or "").strip()
        if not title or not statement:
            self._json({"ok": False, "message": "Claim title and statement are required"}, 400)
            return
        raw_conf = str(payload.get("confidence") or "hypothetical").strip().lower()
        confidence = (
            raw_conf if raw_conf in ("hypothetical", "evidenced", "disputed") else "hypothetical"
        )
        time_period = str(payload.get("time_period") or "").strip() or None
        place = str(payload.get("place") or "").strip() or None
        raw_actors = payload.get("actors")
        actors: list[str] = []
        if isinstance(raw_actors, str):
            actors = [a.strip() for a in raw_actors.split(",") if a.strip()]
        elif isinstance(raw_actors, list):
            actors = [str(a).strip() for a in raw_actors if str(a).strip()]
        dossier_id = str(payload.get("dossier_id") or "").strip() or None
        raw_tags = payload.get("tags")
        tags: list[str] = []
        if isinstance(raw_tags, str):
            tags = [t.strip() for t in raw_tags.split(",") if t.strip()]
        elif isinstance(raw_tags, list):
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
        try:
            res = research_api.create_claim(
                root,
                title=title,
                statement=statement,
                confidence=confidence,  # type: ignore[arg-type]
                time_period=time_period,
                place=place,
                actors=actors,
                dossier_id=dossier_id,
                tags=tags,
            )
            self._json({"ok": True, "message": f"Claim '{title}' created", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_evidence_link(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        claim_id = str(payload.get("claim_id") or "").strip()
        passage_id = str(payload.get("passage_id") or "").strip()
        if not claim_id or not passage_id:
            self._json({"ok": False, "message": "claim_id and passage_id are required"}, 400)
            return
        raw_rel = str(payload.get("relation") or "supports").strip().lower()
        relation = (
            raw_rel
            if raw_rel in ("supports", "contradicts", "qualifies", "contextualizes")
            else "supports"
        )
        rationale = str(payload.get("rationale") or "").strip() or None
        reviewer = str(payload.get("reviewer") or "author").strip()
        try:
            res = research_api.link_evidence(
                root,
                claim_id=claim_id,
                passage_id=passage_id,
                relation=relation,  # type: ignore[arg-type]
                rationale=rationale,
                reviewer=reviewer,
            )
            self._json({"ok": True, "message": "Evidence linked", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

    def _handle_research_decision_add(self, payload: dict[str, Any]) -> None:
        root = self.get_research_root()
        if not root or not (root / "research").is_dir():
            self._json({"ok": False, "message": "Research project not initialized"}, 400)
            return
        title = str(payload.get("title") or "").strip()
        rationale = str(payload.get("rationale") or "").strip()
        if not title or not rationale:
            self._json({"ok": False, "message": "Decision title and rationale are required"}, 400)
            return
        claim_id = str(payload.get("claim_id") or "").strip() or None
        deviation_from_fact = bool(payload.get("deviation_from_fact", False))
        impact_on_plot = str(payload.get("impact_on_plot") or "").strip() or None
        try:
            res = research_api.record_decision(
                root,
                title=title,
                rationale=rationale,
                claim_id=claim_id,
                deviation_from_fact=deviation_from_fact,
                impact_on_plot=impact_on_plot,
            )
            self._json({"ok": True, "message": f"Decision '{title}' recorded", **res})
        except (ResearchError, OSError, ValueError) as exc:
            self._json({"ok": False, "message": str(exc)}, 400)

