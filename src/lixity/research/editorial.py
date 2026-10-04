"""Read-only review candidates from explicit associations and revision ordering.

These checks do not compare prose meanings or determine whether a choice has
been incorporated. Historical pins may be intentional; every candidate needs
human review. Build the association graph once for each loaded snapshot.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from .models import Claim, Decision, Dossier, Reference, Tombstone
from .repository import Repository, ResearchError, Snapshot

Outline = Callable[[str], list[str]]
SCOPE = "Explicit decision/dossier associations, pinned revisions and timestamp ordering; human review only."


def decision_graph(snapshot: Snapshot, *, outline: Outline | None = None,
                   decision_id: str | None = None) -> dict[str, dict[str, Any]]:
    withdrawn = {record.target_ref.id for record in snapshot.records.values()
                 if isinstance(record, Tombstone) and record.operation in {"withdraw", "purge"}}
    outlines: dict[str, list[str]] = {}
    graph: dict[str, dict[str, Any]] = {}
    for decision in snapshot.records.values():
        if (not isinstance(decision, Decision) or decision.id in withdrawn
                or (decision_id is not None and decision.id != decision_id)):
            continue
        associations: list[tuple[Reference, dict[str, Any]]] = [
            (ref, {"via": "direct", "pinned_revision": ref.revision}) for ref in decision.dossier_refs]
        if decision.claim_ref:
            claim = snapshot.get(decision.claim_ref, Claim)
            current_claim = snapshot.latest(claim.id, Claim)
            if claim.dossier_ref:
                associations.append((claim.dossier_ref, {"via": "claim", "pinned_revision": claim.dossier_ref.revision,
                    "claim_id": claim.id, "claim_revision": claim.revision,
                    "claim_current_revision": current_claim.revision, "claim_withdrawn": claim.id in withdrawn}))
        affected: dict[str, dict[str, Any]] = {}
        for reference, link in associations:
            dossier = snapshot.latest(reference.id, Dossier)
            link["pinned_created_at"] = snapshot.get(reference, Dossier).created_at
            if dossier.id not in affected:
                if outline is not None and dossier.id not in outlines:
                    outlines[dossier.id] = outline(dossier.body)
                affected[dossier.id] = {"id": dossier.id, "title": dossier.title,
                    "current_revision": dossier.revision, "pinned_revisions": [], "created_at": dossier.created_at,
                    "decision_after_dossier": decision.created_at > dossier.created_at,
                    "withdrawn": dossier.id in withdrawn, "sections": outlines.get(dossier.id, []),
                    "links": [], "flags": []}
            affected[dossier.id]["links"].append(link)
            affected[dossier.id]["pinned_revisions"].append(reference.revision)
        for entry in affected.values():
            entry["pinned_revisions"] = sorted(set(entry["pinned_revisions"]))
            flags = entry["flags"]
            if entry["decision_after_dossier"]:
                flags.append("decision_after_dossier")
            if any(pin < entry["current_revision"] for pin in entry["pinned_revisions"]):
                flags.append("stale_dossier_pin")
            if any(link.get("claim_revision", 0) < link.get("claim_current_revision", 0) for link in entry["links"]):
                flags.append("stale_claim_pin")
            if entry["withdrawn"]:
                flags.append("withdrawn_dossier")
            if any(link.get("claim_withdrawn") for link in entry["links"]):
                flags.append("withdrawn_claim")
        graph[decision.id] = {"decision": {"id": decision.id, "title": decision.title,
                                          "revision": decision.revision, "created_at": decision.created_at},
                              "dossiers": sorted(affected.values(), key=lambda value: (value["title"], value["id"])),
                              "unlinked": not affected}
    return graph


def dossier_reviews(snapshot: Snapshot) -> dict[str, list[dict[str, Any]]]:
    """Keep the existing date-based review status, adding explicit pin context."""
    reviews: dict[str, list[dict[str, Any]]] = {}
    for impact in decision_graph(snapshot).values():
        decision = impact["decision"]
        for dossier in impact["dossiers"]:
            needed = dossier["decision_after_dossier"]
            reason = (f"Decision '{decision['title']}' was revised (rev {decision['revision']})"
                      if decision["revision"] > 1 else f"Decision '{decision['title']}' was created after dossier")
            reviews.setdefault(dossier["id"], []).append({"decision_id": decision["id"],
                "title": decision["title"], "revision": decision["revision"],
                "status": "review_needed" if needed else "current", "reason": reason if needed else None,
                "flags": dossier["flags"], "pinned_revisions": dossier["pinned_revisions"],
                "current_revision": dossier["current_revision"]})
    return reviews


def decision_impact(project: str | Path, decision_id: str, *, outline: Outline | None = None) -> dict[str, Any]:
    snapshot = Repository(project).snapshot()
    graph = decision_graph(snapshot, outline=outline, decision_id=decision_id)
    if decision_id not in graph:
        raise ResearchError("Decision not found or has been withdrawn")
    return {"schema_version": "research-decision-impact-local/1", "snapshot": snapshot.digest,
            **graph[decision_id], "scope": SCOPE}


def editorial_review(project: str | Path, *, outline: Outline | None = None) -> dict[str, Any]:
    snapshot = Repository(project).snapshot()
    graph = decision_graph(snapshot, outline=outline)
    candidates = []
    for impact in graph.values():
        decision = impact["decision"]
        affected = impact["dossiers"] if not impact["unlinked"] else [None]
        for dossier in affected:
            if dossier is not None and not dossier["flags"]:
                continue
            candidates.append({"decision_id": decision["id"], "title": decision["title"],
                "decision_revision": decision["revision"], "decision_created_at": decision["created_at"],
                "dossier_id": dossier["id"] if dossier else None, "dossier_title": dossier["title"] if dossier else None,
                "current_revision": dossier["current_revision"] if dossier else None,
                "dossier_created_at": dossier["created_at"] if dossier else None,
                "pinned_revisions": dossier["pinned_revisions"] if dossier else [],
                "sections": dossier["sections"] if dossier else [],
                "flags": dossier["flags"] if dossier else ["no_linked_dossier"]})
    candidates.sort(key=lambda candidate: (candidate["decision_created_at"], candidate["decision_id"]), reverse=True)
    return {"schema_version": "research-editorial-review-local/1", "snapshot": snapshot.digest,
            "decision_count": len(graph), "candidate_count": len(candidates), "candidates": candidates,
            "scope": SCOPE}
