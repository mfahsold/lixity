"""Read-only review candidates from explicit associations and revision ordering.

These checks do not compare prose meanings or determine whether a choice has
been incorporated. Historical pins may be intentional; every candidate needs
human review. Build the association graph once for each loaded snapshot.
"""

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any

from .acknowledgements import latest_acknowledgements
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
    acknowledgements = latest_acknowledgements(snapshot.records.values())
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
            acknowledgement = acknowledgements.get((decision.id, entry["id"]))
            if acknowledgement is not None:
                current = (acknowledgement.decision_ref.revision == decision.revision
                           and acknowledgement.dossier_ref.revision == entry["current_revision"])
                entry["acknowledgement"] = {"id": acknowledgement.id, "status": acknowledgement.status,
                    "current": current, "note": acknowledgement.note, "actor": acknowledgement.created_by,
                    "created_at": acknowledgement.created_at, "decision_revision": acknowledgement.decision_ref.revision,
                    "dossier_revision": acknowledgement.dossier_ref.revision}
                if not current:
                    flags.append("stale_author_acknowledgement")
                elif acknowledgement.status == "applied":
                    flags[:] = [flag for flag in flags if flag != "decision_after_dossier"]
                else:
                    flags.append("author_review_needed")
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
            acknowledgement = dossier.get("acknowledgement")
            if acknowledgement:
                needed = not acknowledgement["current"] or acknowledgement["status"] == "review_needed"
            reason = (f"Decision '{decision['title']}' was revised (rev {decision['revision']})"
                      if decision["revision"] > 1 else f"Decision '{decision['title']}' was created after dossier")
            if acknowledgement:
                reason = ("Author acknowledgement refers to an earlier decision or dossier revision"
                          if not acknowledgement["current"] else "Author explicitly reopened review")
            review = {"decision_id": decision["id"],
                "title": decision["title"], "revision": decision["revision"],
                "status": "review_needed" if needed else "current", "reason": reason if needed else None,
                "flags": dossier["flags"], "pinned_revisions": dossier["pinned_revisions"],
                "current_revision": dossier["current_revision"]}
            if acknowledgement:
                review["acknowledgement"] = acknowledgement
            reviews.setdefault(dossier["id"], []).append(review)
    return reviews


def decision_impact(project: str | Path, decision_id: str, *, outline: Outline | None = None) -> dict[str, Any]:
    snapshot = Repository(project).snapshot()
    return decision_impact_data(snapshot, decision_id, outline=outline)


def decision_impact_data(snapshot: Snapshot, decision_id: str, *, outline: Outline | None = None) -> dict[str, Any]:
    graph = decision_graph(snapshot, outline=outline, decision_id=decision_id)
    if decision_id not in graph:
        raise ResearchError("Decision not found or has been withdrawn")
    return {"schema_version": "research-decision-impact-local/1", "snapshot": snapshot.digest,
            **graph[decision_id], "scope": SCOPE}


def editorial_review(project: str | Path, *, outline: Outline | None = None) -> dict[str, Any]:
    snapshot = Repository(project).snapshot()
    return editorial_review_data(snapshot, outline=outline)


def editorial_review_data(snapshot: Snapshot, *, outline: Outline | None = None) -> dict[str, Any]:
    graph = decision_graph(snapshot, outline=outline)
    candidates = []
    for impact in graph.values():
        decision = impact["decision"]
        affected = impact["dossiers"] if not impact["unlinked"] else [None]
        for dossier in affected:
            if dossier is not None and not dossier["flags"]:
                continue
            candidate = {"decision_id": decision["id"], "title": decision["title"],
                "decision_revision": decision["revision"], "decision_created_at": decision["created_at"],
                "dossier_id": dossier["id"] if dossier else None, "dossier_title": dossier["title"] if dossier else None,
                "current_revision": dossier["current_revision"] if dossier else None,
                "dossier_created_at": dossier["created_at"] if dossier else None,
                "pinned_revisions": dossier["pinned_revisions"] if dossier else [],
                "sections": dossier["sections"] if dossier else [],
                "flags": dossier["flags"] if dossier else ["no_linked_dossier"]}
            if dossier and dossier.get("acknowledgement"):
                candidate["acknowledgement"] = dossier["acknowledgement"]
            candidates.append(candidate)
    candidates.sort(key=lambda candidate: (candidate["decision_created_at"], candidate["decision_id"]), reverse=True)
    return {"schema_version": "research-editorial-review-local/1", "snapshot": snapshot.digest,
            "decision_count": len(graph), "candidate_count": len(candidates), "candidates": candidates,
            "scope": SCOPE}


def prepare_pin_review_batch(
    project: str | Path,
    actions: Sequence[Mapping[str, Any]],
    *,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Prepare an atomic revision batch packet for explicit pin-review actions.

    Supported action mappings:
      1. {"action": "retarget_dossier", "decision_id": ..., "expected_decision_revision": ...,
          "dossier_id": ..., "target_dossier_revision": ..., "reason": ...}
      2. {"action": "retarget_claim", "decision_id": ..., "expected_decision_revision": ...,
          "claim_id": ..., "target_claim_revision": ..., "reason": ...}
      3. {"action": "acknowledge", "decision_id": ..., "expected_decision_revision": ...,
          "dossier_id": ..., "expected_dossier_revision": ..., "status": "applied"|"review_needed",
          "note": ...}
      4. {"action": "keep_pin", ...} -> intentionally no-op / records kept in history

    Returns a ready research-revision-batch-local/1 packet for revise-batch.
    """
    from .revisions import prepare_record_revisions

    repository = Repository(project)
    snapshot = repository.snapshot()

    decision_ops: dict[str, dict[str, Any]] = {}
    ack_ops: list[dict[str, Any]] = []
    skipped_noops: list[dict[str, Any]] = []

    for item in actions:
        action_kind = item.get("action")
        if action_kind == "keep_pin":
            skipped_noops.append(dict(item))
            continue
        if action_kind == "retarget_dossier":
            dec_id = str(item["decision_id"])
            expected_dec_rev = int(item["expected_decision_revision"])
            dossier_id = str(item["dossier_id"])
            target_rev = int(item["target_dossier_revision"])
            reason = str(item.get("reason") or f"Retarget dossier {dossier_id} to revision {target_rev}")

            if dec_id in decision_ops:
                op = decision_ops[dec_id]
                op["changes"]["dossier_revisions"][dossier_id] = target_rev
                if dossier_id not in op["changes"]["dossier_ids"]:
                    op["changes"]["dossier_ids"].append(dossier_id)
                op["reason"] = f"{op['reason']}; {reason}"
            else:
                dec_rec = snapshot.latest(dec_id, Decision)
                existing_pins = {ref.id: ref.revision for ref in dec_rec.dossier_refs}
                existing_pins[dossier_id] = target_rev
                dossier_ids = [ref.id for ref in dec_rec.dossier_refs]
                if dossier_id not in dossier_ids:
                    dossier_ids.append(dossier_id)

                decision_ops[dec_id] = {
                    "kind": "decision",
                    "id": dec_id,
                    "expected_revision": expected_dec_rev,
                    "changes": {
                        "dossier_ids": dossier_ids,
                        "dossier_revisions": existing_pins,
                    },
                    "change_kind": "correction",
                    "reason": reason,
                }
        elif action_kind == "retarget_claim":
            dec_id = str(item["decision_id"])
            expected_dec_rev = int(item["expected_decision_revision"])
            claim_id = str(item["claim_id"])
            target_rev = int(item["target_claim_revision"])
            reason = str(item.get("reason") or f"Retarget claim {claim_id} to revision {target_rev}")

            if dec_id in decision_ops:
                op = decision_ops[dec_id]
                op["changes"]["claim_id"] = claim_id
                op["changes"]["claim_revision"] = target_rev
                op["reason"] = f"{op['reason']}; {reason}"
            else:
                decision_ops[dec_id] = {
                    "kind": "decision",
                    "id": dec_id,
                    "expected_revision": expected_dec_rev,
                    "changes": {
                        "claim_id": claim_id,
                        "claim_revision": target_rev,
                    },
                    "change_kind": "correction",
                    "reason": reason,
                }
        elif action_kind == "acknowledge":
            dec_id = str(item["decision_id"])
            dossier_id = str(item["dossier_id"])
            expected_dec_rev = int(item["expected_decision_revision"])
            expected_dos_rev = int(item["expected_dossier_revision"])
            status = str(item.get("status", "applied"))
            note = item.get("note")
            ack_ops.append({
                "kind": "decision_acknowledgement",
                "decision_id": dec_id,
                "dossier_id": dossier_id,
                "expected_decision_revision": expected_dec_rev,
                "expected_dossier_revision": expected_dos_rev,
                "status": status,
                "note": str(note) if note is not None else None,
            })
        else:
            raise ResearchError(f"Unsupported pin-review action: {action_kind!r}")

    operations: list[Mapping[str, Any]] = [*decision_ops.values(), *ack_ops]

    packet = prepare_record_revisions(project, operations, actor=actor) if operations else {
        "schema_version": "research-revision-batch-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "operations": [],
        "ready": True,
    }

    return {
        "schema_version": "research-pin-review-batch-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "action_count": len(actions),
        "operation_count": len(operations),
        "kept_pins_count": len(skipped_noops),
        "kept_pins": skipped_noops,
        "batch_packet": packet,
    }

