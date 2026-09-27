"""Rebuildable lexical search; canonical snapshots remain the authority."""

import os
import re
import sqlite3
import tempfile
from contextlib import closing
from typing import Any

from .models import Claim, Decision, Dossier, Extraction, Passage, Source, SourceVersion, Tombstone
from .repository import Repository, ResearchError, Snapshot, sync_directory

SEARCH_SCOPES = {"sources": "passage", "dossiers": "dossier", "claims": "claim", "decisions": "decision", "all": None}


def authored_text(record: Dossier | Claim | Decision) -> str:
    """Search only current authored content, not revision reasons or old references."""
    if isinstance(record, Dossier):
        return "\n".join([record.body, *record.tags])
    if isinstance(record, Claim):
        return "\n".join([record.statement, *record.tags, record.scope.time_period or "",
                          record.scope.place or "", *record.scope.actors])
    return "\n".join([record.rationale, record.impact_on_plot or ""])


def excerpt(text: str, terms: list[str]) -> str:
    """Return a bounded plain-text preview near the first matching term."""
    positions = [text.lower().find(term.lower()) for term in terms]
    start = max(0, min((position for position in positions if position >= 0), default=0) - 100)
    return ("…" if start else "") + text[start:start + 500] + ("…" if len(text) > start + 500 else "")


def current_versions(snapshot: Snapshot) -> set[str]:
    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    latest: dict[str, SourceVersion] = {}
    for record in snapshot.records.values():
        if isinstance(record, SourceVersion):
            if record.id in withdrawn_or_purged or record.source_ref.id in withdrawn_or_purged:
                continue
            previous = latest.get(record.source_ref.id)
            if previous is None or record.sequence > previous.sequence:
                latest[record.source_ref.id] = record
    return {version.id for version in latest.values()}


def reindex(repository: Repository) -> dict[str, Any]:
    with repository.locked():
        snapshot = repository.snapshot()
        selected = current_versions(snapshot)
        destination = repository.safe(repository.cache / "catalogue.sqlite3")
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
                    elif isinstance(record, (Dossier, Claim, Decision)):
                        connection.execute("INSERT INTO documents VALUES (?, ?, ?, ?, ?)",
                                           (record.id, record.revision, record.kind, record.title, authored_text(record)))
            with open(temporary, "r+b") as stream:
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            sync_directory(destination.parent)
        except sqlite3.Error:
            raise ResearchError("Catalogue rebuild failed; SQLite with FTS5 support is required") from None
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"schema_version": "research-index-local/1", "snapshot": snapshot.digest, "passages": count}


def search(repository: Repository, query: str, *, limit: int = 20, scope: str = "sources") -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ResearchError("Search requires 1–1000 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ResearchError("Search limit must be an integer from 1 to 100")
    if not isinstance(scope, str) or scope not in SEARCH_SCOPES:
        raise ResearchError("Search scope must be sources, dossiers, claims, decisions or all")
    snapshot = repository.snapshot()
    selected = current_versions(snapshot)
    path = repository.safe(repository.cache / "catalogue.sqlite3")
    terms = re.findall(r"[^\W_]+", query, re.UNICODE)
    expression = " AND ".join('"' + term + '"' for term in terms)
    hits: list[dict[str, Any]] = []
    try:
        connection = sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)
        try:
            connection.execute("PRAGMA trusted_schema=OFF")
            metadata = connection.execute("SELECT snapshot FROM metadata").fetchall()
            if metadata != [(snapshot.digest,)]:
                raise ResearchError("Search index is stale; run research reindex")
            if scope != "sources":
                rows = connection.execute(
                    "SELECT record_id, revision, kind, bm25(documents, 0, 0, 0, 4, 1) FROM documents "
                    "WHERE documents MATCH ? AND (? IS NULL OR kind = ?) "
                    "ORDER BY bm25(documents, 0, 0, 0, 4, 1), record_id LIMIT ?",
                    (expression, SEARCH_SCOPES[scope], SEARCH_SCOPES[scope], limit),
                ).fetchall() if expression else []
                for identifier, revision, kind, rank in rows:
                    record = snapshot.records.get(identifier)
                    if (not isinstance(record, (Passage, Dossier, Claim, Decision))
                            or record.revision != revision or record.kind != kind):
                        raise ResearchError("Invalid index reference; run research reindex")
                    if isinstance(record, Passage):
                        extraction = snapshot.get(record.extraction_ref, Extraction)
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
                    hit.update({"kind": kind, "rank_score": rank, "score_type": "fts5_bm25", "route": "lexical"})
                    hits.append(hit)
                return {"schema_version": "research-search-local/2", "project_id": snapshot.project.id,
                        "snapshot": snapshot.digest, "mode": "lexical", "scope": scope,
                        "hits": hits, "completeness": "complete", "warnings": []}
            rows = connection.execute(
                "SELECT passage_id, bm25(passages) FROM passages WHERE passages MATCH ? ORDER BY bm25(passages), passage_id LIMIT ?",
                (expression, limit),
            ).fetchall() if expression else []
            for identifier, rank in rows:
                record = snapshot.records.get(identifier)
                if not isinstance(record, Passage):
                    raise ResearchError("Invalid index reference; run research reindex")
                extraction = snapshot.get(record.extraction_ref, Extraction)
                if extraction.source_version_ref.id not in selected:
                    raise ResearchError("Obsolete source in search index; run research reindex")
                citation = repository.citation(snapshot, record)
                citation.update({"rank_score": rank, "score_type": "fts5_bm25", "route": "lexical"})
                hits.append(citation)
        finally:
            connection.close()
    except sqlite3.Error:
        raise ResearchError("Search index unavailable; run research reindex with an FTS5-enabled SQLite") from None
    return {"schema_version": "research-search-local/1", "project_id": snapshot.project.id,
            "snapshot": snapshot.digest, "mode": "lexical", "hits": hits,
            "completeness": "complete", "warnings": []}
