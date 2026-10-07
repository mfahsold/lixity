"""Resolve explicit acknowledgement supersedes chains without using clock order."""

from collections.abc import Iterable

from .models import DecisionAcknowledgement, Entity


def latest_acknowledgements(records: Iterable[Entity]) -> dict[tuple[str, str], DecisionAcknowledgement]:
    """Validate one unbranched accepted chain for each logical decision/dossier pair."""
    groups: dict[tuple[str, str], dict[str, DecisionAcknowledgement]] = {}
    for record in records:
        if isinstance(record, DecisionAcknowledgement):
            pair = (record.decision_ref.id, record.dossier_ref.id)
            groups.setdefault(pair, {})[record.id] = record
    latest = {}
    for pair, events in groups.items():
        roots = []
        children = {}
        for event in events.values():
            previous = event.supersedes_ref
            if previous is None:
                roots.append(event)
            elif previous.id not in events or previous.revision != 1:
                raise ValueError("Acknowledgement supersedes reference must belong to the same decision/dossier pair")
            elif previous.id in children:
                raise ValueError("Acknowledgement supersedes history cannot fork")
            else:
                children[previous.id] = event
        if len(roots) != 1:
            raise ValueError("Acknowledgement history requires exactly one initial event per pair")
        event = roots[0]
        visited = {event.id}
        while event.id in children:
            event = children[event.id]
            if event.id in visited:
                raise ValueError("Acknowledgement supersedes history cannot cycle")
            visited.add(event.id)
        if len(visited) != len(events):
            raise ValueError("Acknowledgement history must be one connected supersedes chain")
        latest[pair] = event
    return latest
