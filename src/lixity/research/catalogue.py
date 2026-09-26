"""Rebuildable lexical search; canonical snapshots remain the authority."""

import os
import re
import sqlite3
import tempfile
from contextlib import closing
from typing import Any

from .models import Extraction, Passage, SourceVersion, Tombstone
from .repository import Repository, ResearchError, Snapshot, sync_directory


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
                for record in snapshot.records.values():
                    if isinstance(record, Passage):
                        extraction = snapshot.get(record.extraction_ref, Extraction)
                        if extraction.source_version_ref.id in selected:
                            repository.quote(snapshot, record)
                            connection.execute("INSERT INTO passages VALUES (?, ?)", (record.id, record.verbatim))
                            count += 1
            with open(temporary, "rb") as stream:
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
            sync_directory(destination.parent)
        except sqlite3.Error:
            raise ResearchError("Catalogue rebuild failed; SQLite with FTS5 support is required") from None
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)
        return {"schema_version": "research-index-local/1", "snapshot": snapshot.digest, "passages": count}


def search(repository: Repository, query: str, *, limit: int = 20) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip() or len(query) > 1000:
        raise ResearchError("Search requires 1–1000 characters")
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ResearchError("Search limit must be an integer from 1 to 100")
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
