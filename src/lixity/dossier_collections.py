"""Explicit project-configured dossier collections and reading order."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

from .publication import validate_metadata_text
from .research.models import Identifier

MAX_COLLECTIONS = 64
MAX_COLLECTION_DOSSIERS = 500
MAX_COLLECTION_NAME_CHARS = 500
RESERVED_COLLECTION_KEYS = frozenset({"all", "unassigned"})

CollectionKey = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")]


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class DossierCollection(_StrictModel):
    """Named dossier collection with an explicit reading order."""

    name: str
    dossier_ids: list[Identifier] = Field(default_factory=list, max_length=MAX_COLLECTION_DOSSIERS)

    @field_validator("name")
    @classmethod
    def _validate_name(cls, value: str) -> str:
        text = validate_metadata_text(value, "Dossier collection name", MAX_COLLECTION_NAME_CHARS)
        if not text:
            raise ValueError("Dossier collection name is required")
        return text

    @model_validator(mode="after")
    def _validate_unique_dossiers(self) -> DossierCollection:
        if len(set(self.dossier_ids)) != len(self.dossier_ids):
            raise ValueError("Dossier collection entries must be unique within a collection")
        return self


_COLLECTION_KEY = TypeAdapter(CollectionKey)
_COLLECTIONS_MAP = TypeAdapter(
    Annotated[dict[CollectionKey, DossierCollection], Field(max_length=MAX_COLLECTIONS)]
)


def validate_collection_key(value: object) -> str:
    """Validate one stable collection identifier."""
    key = _COLLECTION_KEY.validate_python(value, strict=True)
    if key in RESERVED_COLLECTION_KEYS:
        raise ValueError(f"Collection identifier {key!r} is reserved")
    return key


def parse_dossier_collections(raw: object) -> dict[str, DossierCollection]:
    """Validate configured dossier collections without mutating authored records."""
    if raw is None:
        return {}
    if isinstance(raw, list):
        mapped: dict[str, Any] = {}
        for item in raw:
            if not isinstance(item, Mapping):
                raise ValueError("Each dossier collection entry must be an object")
            key = validate_collection_key(item.get("id"))
            if key in mapped:
                raise ValueError(f"Duplicate dossier collection identifier: {key!r}")
            mapped[key] = {k: v for k, v in item.items() if k != "id"}
        raw = mapped
    if not isinstance(raw, Mapping):
        raise ValueError("dossier_collections must be a table of named collections")
    for key in raw:
        validate_collection_key(key)
    return _COLLECTIONS_MAP.validate_python(dict(raw), strict=True)


def project_dossier_collections(
    raw: object,
    active_dossiers: list[dict[str, Any]],
    *,
    withdrawn_dossiers: Mapping[str, Mapping[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[str], dict[str, list[dict[str, Any]]]]:
    """Project configured collections against active and withdrawn dossier state."""
    collections = parse_dossier_collections(raw)
    active_by_id = { str(item["id"]): item for item in active_dossiers }
    withdrawn_by_id = dict(withdrawn_dossiers or {})
    memberships: dict[str, list[dict[str, Any]]] = {did: [] for did in active_by_id}
    assigned_active: set[str] = set()
    projected: list[dict[str, Any]] = []

    for cid, collection in collections.items():
        entries: list[dict[str, Any]] = []
        for position, did in enumerate(collection.dossier_ids, start=1):
            active = active_by_id.get(did)
            if active is not None:
                assigned_active.add(did)
                memberships.setdefault(did, []).append(
                    {"id": cid, "name": collection.name, "position": position}
                )
                entries.append(
                    {
                        "dossier_id": did,
                        "position": position,
                        "status": "available",
                        "title": active["title"],
                        "revision": active["revision"],
                        "tags": list(active.get("tags", [])),
                        "updated_at": active.get("updated_at"),
                    }
                )
            elif did in withdrawn_by_id:
                withdrawn = withdrawn_by_id[did]
                entries.append(
                    {
                        "dossier_id": did,
                        "position": position,
                        "status": "withdrawn",
                        "title": withdrawn.get("title"),
                        "revision": withdrawn.get("revision"),
                    }
                )
            else:
                entries.append(
                    {
                        "dossier_id": did,
                        "position": position,
                        "status": "missing",
                        "title": None,
                        "revision": None,
                    }
                )
        available_count = sum(1 for entry in entries if entry["status"] == "available")
        projected.append(
            {
                "id": cid,
                "name": collection.name,
                "dossier_ids": list(collection.dossier_ids),
                "available_count": available_count,
                "unavailable_count": len(entries) - available_count,
                "entries": entries,
            }
        )

    unassigned = [str(item["id"]) for item in active_dossiers if str(item["id"]) not in assigned_active]
    return projected, unassigned, memberships


def dossier_collections_schema() -> dict[str, Any]:
    """Export the JSON Schema for [tool.lixity.dossier_collections]."""
    schema = _COLLECTIONS_MAP.json_schema()
    schema["$comment"] = (
        "Project-only dossier collections keyed by collection identifier. "
        "Each collection defines a human-readable name and an explicit reading order of dossier UUID URNs."
    )
    return schema
