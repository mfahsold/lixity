"""Resolve a reviewed lexical choice through the existing paragraph citation API."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

from . import api
from .repository import Repository, ResearchConflictError, ResearchError


def resolve_query(
    project: str | Path, query: str, *, pick: int | None = None,
    expected_snapshot: str | None = None,
) -> tuple[dict[str, Any], bool]:
    """Return a citation or unchanged search candidates, never an accepted claim.

    Ordinals refer to the displayed snapshot's source-only, deterministic search
    order. Index refresh happens before acquiring the short final read lock.
    """
    if pick is not None and (type(pick) is not int or not 1 <= pick <= 20):
        raise ResearchError("--pick must select one numbered match from 1 to 20")
    if pick is not None and expected_snapshot is None:
        raise ResearchError("--pick requires the displayed --expected-snapshot and the same query")
    if expected_snapshot is not None and not re.fullmatch(r"[0-9a-f]{64}", expected_snapshot):
        raise ResearchError("--expected-snapshot must be the displayed SHA-256 digest")
    result = api.search(project, query, limit=20, scope="sources", ensure_fresh=True)
    if expected_snapshot is not None and result["snapshot"] != expected_snapshot:
        raise ResearchConflictError("Search snapshot changed; search again before choosing a citation")
    hits = result["hits"]
    if not hits or (pick is None and len(hits) != 1):
        if not hits:
            print("[cite] No retained source passage matches this query", file=sys.stderr)
        else:
            print("[cite] Choose one of these source passages (up to 20 matches):", file=sys.stderr)
            for number, hit in enumerate(hits, 1):
                # JSON escaping keeps newlines/control sequences in imported
                # titles and quotes inert in terminal output.
                title = json.dumps(hit["source_title"], ensure_ascii=False)
                quote = json.dumps(hit["verbatim"][:200], ensure_ascii=False)
                print(f"  {number}. {title}: {quote}", file=sys.stderr)
            print("[cite] Repeat the same query with --pick N --expected-snapshot " + result["snapshot"],
                  file=sys.stderr)
        return result, False
    position = pick - 1 if pick is not None else 0
    if position >= len(hits):
        raise ResearchError("--pick is outside the displayed source matches")
    repository = Repository(project)
    with repository.locked():
        if repository.snapshot().digest != result["snapshot"]:
            raise ResearchConflictError("Search snapshot changed before citation resolution; search again")
        citation = api.cite(project, hits[position]["passage_id"])
        if citation["snapshot"] != result["snapshot"]:
            raise ResearchConflictError("Search snapshot changed during citation resolution; search again")
        if citation["availability"] != "available":
            raise ResearchError("Selected source passage is no longer available; search again")
    return citation, True
