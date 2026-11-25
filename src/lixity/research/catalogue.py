"""Rebuildable lexical search; canonical snapshots remain the authority."""

import os
import re
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any

from .models import Claim, Decision, Dossier, Extraction, Passage, Source, SourceVersion
from .repository import Repository, ResearchError, Snapshot, sync_directory

SEARCH_SCOPES = {"sources": "passage", "dossiers": "dossier", "claims": "claim", "decisions": "decision", "all": None}


def authored_text(record: Dossier | Claim | Decision) -> str:
    """Search only current authored content, not revision reasons or old references."""
    if isinstance(record, Dossier):
        parts = [record.body, *record.tags]
        if record.geography:
            for feature in record.geography.features:
                properties = feature.properties
                parts.extend([properties.label, properties.description or "", properties.time_period or "",
                              properties.feature_type or "", properties.transport or "",
                              *properties.actors, *properties.waypoint_labels])
        return "\n".join(parts)
    if isinstance(record, Claim):
        return "\n".join([record.statement, *record.tags, record.scope.time_period or "",
                          record.scope.place or "", *record.scope.actors])
    return "\n".join([record.rationale, record.impact_on_plot or ""])


def excerpt(text: str, terms: list[str]) -> str:
    """Return a bounded plain-text preview near the first matching term."""
    lower = text.lower()
    positions = (lower.find(term.lower()) for term in terms)
    position = min((index for index in positions if index >= 0), default=0)
    if position > 100 and len(lower) != len(text):
        # Lowercasing can expand a codepoint, for example U+0130.
        for offset, char in enumerate(text):
            position -= len(char.lower())
            if position < 0:
                position = offset
                break
    start = max(0, position - 100)
    return ("…" if start else "") + text[start:start + 500] + ("…" if len(text) > start + 500 else "")


def _unavailable_ids(snapshot: Snapshot) -> set[str]:
    return {
        target_id
        for operation, _kind, target_id in snapshot.lifecycle
        if operation in ("withdraw", "purge")
    }


def current_versions(snapshot: Snapshot, unavailable: set[str] | None = None) -> set[str]:
    withdrawn_or_purged = _unavailable_ids(snapshot) if unavailable is None else unavailable
    latest: dict[str, SourceVersion] = {}
    for record in snapshot.records.values():
        if isinstance(record, SourceVersion):
            if record.id in withdrawn_or_purged or record.source_ref.id in withdrawn_or_purged:
                continue
            previous = latest.get(record.source_ref.id)
            if previous is None or record.sequence > previous.sequence:
                latest[record.source_ref.id] = record
    return {version.id for version in latest.values()}


def _index_path(repository: Repository) -> Path:
    path = repository.safe(repository.cache / "catalogue.sqlite3")
    if path.exists() and not path.is_file():
        raise ResearchError("Search index is not a regular file; check storage and run research reindex")
    return path


def _reindex_snapshot(repository: Repository) -> tuple[dict[str, Any], Snapshot]:
    with repository.locked():
        destination = _index_path(repository)
        snapshot = repository.snapshot()
        unavailable = _unavailable_ids(snapshot)
        selected = current_versions(snapshot, unavailable)
        descriptor, temporary = tempfile.mkstemp(dir=destination.parent, prefix=".index-")
        os.close(descriptor)
        count = 0
        try:
            with closing(sqlite3.connect(temporary)) as connection, connection:
                connection.execute("CREATE TABLE metadata (snapshot TEXT NOT NULL)")
                connection.execute("INSERT INTO metadata VALUES (?)", (snapshot.digest,))
                connection.execute("CREATE VIRTUAL TABLE passages USING fts5(passage_id UNINDEXED, content, tokenize='unicode61 remove_diacritics 0')")
                connection.execute("CREATE VIRTUAL TABLE documents USING fts5(record_id UNINDEXED, revision UNINDEXED, kind UNINDEXED, title, content, tokenize='unicode61 remove_diacritics 0')")
                for record in snapshot.records.values():
                    if isinstance(record, Passage):
                        extraction = snapshot.get(record.extraction_ref, Extraction)
                        if extraction.source_version_ref.id in selected:
                            repository.quote(snapshot, record)
                            connection.execute("INSERT INTO passages VALUES (?, ?)", (record.id, record.verbatim))
                            version = snapshot.get(extraction.source_version_ref, SourceVersion)
                            source = snapshot.get(version.source_ref, Source)
                            connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                                               (record.id, record.revision, record.kind, source.title, record.verbatim))
                            count += 1
                    elif isinstance(record, (Dossier, Claim, Decision)) and record.id not in unavailable:
                        connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                                           (record.id, record.revision, record.kind, record.title, authored_text(record)))
            with open(temporary, "r+b") as stream:
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            sync_directory(destination.parent)
        except sqlite3.Error as exc:
            raise ResearchError(f"Catalogue rebuild failed at {destination}: {exc}") from exc
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        summary = {"schema_version": "research-index-local/1", "snapshot": snapshot.digest, "passages": count}
        return summary, snapshot


def reindex(repository: Repository) -> dict[str, Any]:
    summary, _ = _reindex_snapshot(repository)
    return summary


def _matching_rows(
    repository: Repository, path: Path, snapshot: Snapshot, expression: str, scope: str, limit: int,
) -> tuple[Snapshot, list[sqlite3.Row]] | None:
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA trusted_schema=OFF")
        connection.execute("BEGIN")
        metadata = [row["snapshot"] for row in connection.execute("SELECT snapshot FROM metadata LIMIT 2")]
        if metadata != [snapshot.digest]:
            if len(metadata) != 1:
                return None
            # Another reader may have published a newer index between our
            # snapshot read and this open. Recheck the canonical HEAD first.
            snapshot = repository.snapshot()
            if metadata != [snapshot.digest]:
                return None
        if not expression:
            return snapshot, []
        if scope == "sources":
            return snapshot, connection.execute(
                "SELECT passage_id AS record_id, bm25(passages) AS rank FROM passages WHERE passages MATCH ? "
                "ORDER BY rank, passage_id LIMIT ?",
                (expression, limit),
            ).fetchall()
        return snapshot, connection.execute(
            "SELECT record_id, revision, kind, bm25(documents, 0, 0, 0, 4, 1) AS rank FROM documents "
            "WHERE documents MATCH ? AND (? IS NULL OR kind = ?) ORDER BY rank, record_id LIMIT ?",
            (expression, SEARCH_SCOPES[scope], SEARCH_SCOPES[scope], limit),
        ).fetchall()


def _verified_hits(
    repository: Repository, snapshot: Snapshot, rows: list[sqlite3.Row], scope: str, terms: list[str],
) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    unavailable = _unavailable_ids(snapshot)
    selected: set[str] | None = None
    for row in rows:
        record = snapshot.records.get(row["record_id"])
        if (not isinstance(record, (Passage, Dossier, Claim, Decision))
                or record.id in unavailable
                or (scope == "sources" and not isinstance(record, Passage))
                or (scope != "sources" and (record.revision != row["revision"] or record.kind != row["kind"]))):
            raise ResearchError("Invalid index reference; run research reindex")
        if isinstance(record, Passage):
            extraction = snapshot.get(record.extraction_ref, Extraction)
            if selected is None:
                selected = current_versions(snapshot, unavailable)
            if extraction.source_version_ref.id not in selected:
                raise ResearchError("Obsolete source in search index; run research reindex")
            hit = repository.citation(snapshot, record)
        else:
            hit = {"record_id": record.id, "revision": record.revision,
                   "title": record.title, "excerpt": excerpt(authored_text(record), terms)}
            if isinstance(record, Claim):
                hit["confidence"] = record.confidence
            elif isinstance(record, Decision):
                hit["deviation_from_fact"] = record.deviation_from_fact
        if scope != "sources":
            hit["kind"] = record.kind
        hit.update({"rank_score": row["rank"], "score_type": "fts5_bm25", "route": "lexical"})
        hits.append(hit)
    return hits


def search(
    repository: Repository,
    query: str,
    *,
    limit: int = 20,
    scope: str = "sources",
    ensure_fresh: bool = False,
    refreshed: bool = False,
) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ResearchError("Search requires 1–1000 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ResearchError("Search limit must be an integer from 1 to 100")
    if not isinstance(scope, str) or scope not in SEARCH_SCOPES:
        raise ResearchError("Search scope must be sources, dossiers, claims, decisions or all")
    path = _index_path(repository)
    if not path.is_file():
        if not ensure_fresh:
            # Distinguish "never built" from "unusable". Without this the missing
            # file surfaces as sqlite's "unable to open database file", which the
            # handler below reports as an FTS5 problem the user cannot act on.
            raise ResearchError("Search index not built; run research reindex")
        _, snapshot = _reindex_snapshot(repository)
        refreshed = True
    else:
        snapshot = repository.snapshot()

    terms = re.findall(r"[^\W_]+", query, re.UNICODE)
    expression = " AND ".join('"' + term + '"' for term in terms)
    # Retry once after a rebuild. A second mismatch belongs to the caller.
    while True:
        try:
            result = _matching_rows(repository, path, snapshot, expression, scope, limit)
        except sqlite3.Error as exc:
            if not ensure_fresh or refreshed:
                raise ResearchError(f"Search index unavailable at {path}: {exc}; check storage and run research reindex") from exc
        else:
            if result is not None:
                snapshot, rows = result
                break
            if not ensure_fresh or refreshed:
                raise ResearchError("Search index is stale; run research reindex")
        _, snapshot = _reindex_snapshot(repository)
        refreshed = True

    hits = _verified_hits(repository, snapshot, rows, scope, terms)
    warnings = ["Search index was refreshed to current project snapshot"] if refreshed else []
    if scope != "sources":
        return {"schema_version": "research-search-local/2", "project_id": snapshot.project.id,
                "snapshot": snapshot.digest, "mode": "lexical", "scope": scope,
                "hits": hits, "completeness": "complete", "warnings": warnings}
    if scope == "sources" and not hits:
        warnings.append("No source passage matches found; try --scope all to search dossiers, claims, and decisions.")
    return {"schema_version": "research-search-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "mode": "lexical", "hits": hits,
            "completeness": "complete", "warnings": warnings}
