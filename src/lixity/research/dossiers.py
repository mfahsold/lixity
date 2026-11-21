"""Dossier lifecycle, collection, term-profile, and manuscript-draft orchestration."""

import json
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal
from unicodedata import normalize

from pydantic import ValidationError

from ..config import read_explicit_project_config
from ..io import FileUtils
from ..project_structure import MAX_CONFIG_BYTES
from . import editorial
from .geography import summarize_geography
from .images import image_descriptions, resolve_dossier_images, resolve_dossier_media
from .manuscript import dossier_manuscript_evidence
from .manuscript_drafts import extract_manuscript_dossier_drafts
from .models import LANGUAGES, Dossier, Language, Passage, Reference, Tombstone
from .repository import Repository, ResearchConflictError, ResearchError, Snapshot, digest
from .revisions import EvidenceCitationReader, dossier_withdrawal, source_updates
from .sections import (
    _editable_section_titles,
    _extract_sections,
    _section_spans,
    _section_subtree_end,
    extract_sections,
    preamble_text,
)


def supported_language(value: object) -> Language:
    """Return the matching project language key or raise a clear error."""
    text = str(value or "").strip().lower()
    for candidate in LANGUAGES:
        if text == candidate:
            return candidate
    raise ResearchError(f"Unsupported language: {value!r}")


def create_dossier(
    project: str | Path,
    title: str,
    body: str,
    *,
    language: str | None = None,
    tags: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    geography: dict[str, Any] | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Create and commit a new Dossier record."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    return _commit_dossier(repository, snapshot, title, body, language=language, tags=tags,
                           evidence_ids=evidence_ids, geography=geography, actor=actor)


def _commit_dossier(
    repository: Repository, snapshot: Snapshot, title: str, body: str, *,
    language: str | None, tags: list[str] | None, actor: str,
    evidence_ids: list[str] | None = None, geography: dict[str, Any] | None = None,
) -> dict[str, Any]:
    from .api import envelope

    title = title.strip()
    if not (1 <= len(title) <= 500):
        raise ResearchError("Dossier title must be between 1 and 500 characters")
    language = supported_language(snapshot.project.language if language is None else language)

    evidence_refs = [Reference(id=eid) for eid in dict.fromkeys(evidence_ids or [])]
    for ref in evidence_refs:
        snapshot.get(ref, Passage)

    values = envelope(snapshot.project.id, actor)
    if geography is not None:
        values["schema_version"] = "research-local/8"
    try:
        dossier = Dossier.model_validate(
            {
                **values,
                "title": title,
                "language": language,
                "tags": tags or [],
                "body": body,
                "evidence_refs": evidence_refs,
                "geography": geography,
            }
        )
    except ValidationError as error:
        raise ResearchError(f"Invalid dossier fields: {error}") from None
    new_snapshot = repository.commit([dossier], {}, snapshot)
    return {
        "schema_version": "research-dossier-local/1",
        "dossier_id": dossier.id,
        "title": dossier.title,
        "snapshot": new_snapshot.digest,
    }


def list_dossiers(
    project: str | Path,
    *,
    collection: str | None = None,
) -> dict[str, Any]:
    """List active dossiers and project-configured dossier collections."""
    repository = Repository(project)
    snapshot = repository.snapshot(
        kinds=frozenset({"dossier", "claim", "decision", "decision_acknowledgement"})
    )
    return _list_dossiers(snapshot, root=repository.root, collection=collection)


def _list_dossiers(
    snapshot: Snapshot,
    *,
    root: Path | None = None,
    settings: Mapping[str, Any] | None = None,
    collection: str | None = None,
) -> dict[str, Any]:
    from ..config import read_explicit_project_config
    from ..dossier_collections import project_dossier_collections

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    purged_passages = {
        record.target_ref
        for record in snapshot.records.values()
        if isinstance(record, Tombstone)
        and record.operation == "purge"
        and record.target_kind == "passage"
    }

    dossier_reviews = editorial.dossier_reviews(snapshot)

    dossiers_list = [
        {
            "id": record.id,
            "title": record.title,
            "language": record.language,
            "tags": record.tags,
            "revision": record.revision,
            "evidence_count": len(record.evidence_refs),
            "unavailable_evidence_count": sum(
                ref in purged_passages for ref in record.evidence_refs
            ),
            "created_at": record.created_at,
            "created_by": record.created_by,
            "excerpt": image_descriptions(record.body)[:300].strip(),
            "sections": list(extract_sections(record.body).keys()),
            "review_needed": any(
                review["status"] == "review_needed" for review in dossier_reviews.get(record.id, [])
            ),
        }
        for record in snapshot.records.values()
        if isinstance(record, Dossier) and record.id not in withdrawn_or_purged
    ]

    dossiers_list.sort(key=lambda d: str(d["created_at"]), reverse=True)
    withdrawn_dossiers = {
        record.id: {"title": record.title, "revision": record.revision}
        for record in snapshot.records.values()
        if isinstance(record, Dossier) and record.id in withdrawn_or_purged
    }
    try:
        raw_collections = (
            settings.get("dossier_collections")
            if settings is not None
            else read_explicit_project_config(root, maximum_bytes=65536).get("dossier_collections")
            if root is not None
            else None
        )
        collections, unassigned_ids, memberships = project_dossier_collections(
            raw_collections, dossiers_list, withdrawn_dossiers=withdrawn_dossiers
        )
    except (ValidationError, ValueError) as error:
        raise ResearchError(f"Invalid dossier collections configuration: {error}") from error

    for item in dossiers_list:
        item["collections"] = memberships.get(str(item["id"]), [])

    if collection is not None:
        selected = collection.strip()
        if not selected:
            raise ResearchError("Collection filter requires a nonblank collection ID")
        if selected == "all":
            pass
        elif selected == "unassigned":
            unassigned_set = set(unassigned_ids)
            dossiers_list = [item for item in dossiers_list if item["id"] in unassigned_set]
        else:
            matched = next((entry for entry in collections if entry["id"] == selected), None)
            if matched is None:
                raise ResearchError(f"Unknown dossier collection: {selected!r}")
            by_id = {str(item["id"]): item for item in dossiers_list}
            dossiers_list = [by_id[did] for did in matched["dossier_ids"] if did in by_id]
        return {
            "schema_version": "research-dossiers-local/1",
            "dossiers": dossiers_list,
            "collections": collections,
            "unassigned_dossier_ids": unassigned_ids,
            "selected_collection": selected,
        }

    return {
        "schema_version": "research-dossiers-local/1",
        "dossiers": dossiers_list,
        "collections": collections,
        "unassigned_dossier_ids": unassigned_ids,
    }


def save_dossier_collection(
    project: str | Path,
    collection_id: str,
    *,
    name: str,
    dossier_ids: list[str] | tuple[str, ...],
    expected_config_snapshot: tuple[tuple[int, ...] | None, bytes] | None = None,
) -> dict[str, Any]:
    """Create or update one named dossier collection in lixity.toml without revising dossiers."""
    from ..config import (
        prepare_project_settings,
        project_config_snapshot,
        read_explicit_project_config,
    )
    from ..dossier_collections import (
        DossierCollection,
        parse_dossier_collections,
        validate_collection_key,
    )

    repository = Repository(project)
    snapshot = repository.snapshot(
        kinds=frozenset({"dossier", "claim", "decision", "decision_acknowledgement"})
    )
    try:
        key = validate_collection_key(collection_id)
        updated_collection = DossierCollection(name=name, dossier_ids=list(dossier_ids))
        observed_config = project_config_snapshot(
            repository.root / "lixity.toml", maximum_bytes=65536
        )
        if expected_config_snapshot is not None and observed_config != expected_config_snapshot:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        current_settings = read_explicit_project_config(repository.root, maximum_bytes=65536)
        collections = dict(parse_dossier_collections(current_settings.get("dossier_collections")))
        collections[key] = updated_collection
        serialized = {cid: item.model_dump() for cid, item in collections.items()}
        prepared = prepare_project_settings(repository.root, {"dossier_collections": serialized})
        if prepared.original != observed_config:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        prepared.commit()
    except (ValidationError, ValueError) as error:
        raise ResearchError(f"Invalid dossier collection: {error}") from error
    return _list_dossiers(snapshot, settings={"dossier_collections": serialized}, collection=key)


def delete_dossier_collection(
    project: str | Path,
    collection_id: str,
    *,
    expected_config_snapshot: tuple[tuple[int, ...] | None, bytes] | None = None,
) -> dict[str, Any]:
    """Remove one named dossier collection from lixity.toml without revising dossiers."""
    from ..config import (
        prepare_project_settings,
        project_config_snapshot,
        read_explicit_project_config,
    )
    from ..dossier_collections import parse_dossier_collections, validate_collection_key

    repository = Repository(project)
    snapshot = repository.snapshot(
        kinds=frozenset({"dossier", "claim", "decision", "decision_acknowledgement"})
    )
    try:
        key = validate_collection_key(collection_id)
        observed_config = project_config_snapshot(
            repository.root / "lixity.toml", maximum_bytes=65536
        )
        if expected_config_snapshot is not None and observed_config != expected_config_snapshot:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        current_settings = read_explicit_project_config(repository.root, maximum_bytes=65536)
        collections = dict(parse_dossier_collections(current_settings.get("dossier_collections")))
    except (ValidationError, ValueError) as error:
        raise ResearchError(f"Invalid dossier collection: {error}") from error
    if key not in collections:
        raise ResearchError(f"Unknown dossier collection: {key!r}")
    del collections[key]
    serialized = {cid: item.model_dump() for cid, item in collections.items()}
    try:
        prepared = prepare_project_settings(repository.root, {"dossier_collections": serialized})
        if prepared.original != observed_config:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        prepared.commit()
    except ValueError as error:
        raise ResearchError(f"Could not update dossier collections: {error}") from error
    return _list_dossiers(snapshot, settings={"dossier_collections": serialized})


def set_dossier_collections(
    project: str | Path,
    collections: object,
    *,
    expected_config_snapshot: tuple[tuple[int, ...] | None, bytes] | None = None,
) -> dict[str, Any]:
    """Replace all configured dossier collections in lixity.toml without revising dossiers."""
    from ..config import prepare_project_settings
    from ..dossier_collections import parse_dossier_collections

    repository = Repository(project)
    snapshot = repository.snapshot(
        kinds=frozenset({"dossier", "claim", "decision", "decision_acknowledgement"})
    )
    try:
        parsed = parse_dossier_collections(collections)
        serialized = {cid: item.model_dump() for cid, item in parsed.items()}
        prepared = prepare_project_settings(repository.root, {"dossier_collections": serialized})
        if expected_config_snapshot is not None and prepared.original != expected_config_snapshot:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        prepared.commit()
    except (ValidationError, ValueError) as error:
        raise ResearchError(f"Invalid dossier collections: {error}") from error
    return _list_dossiers(snapshot, settings={"dossier_collections": serialized})


def save_term_profile(
    project: str | Path,
    term: str,
    *,
    aliases: list[str] | tuple[str, ...] = (),
    scoped_alternatives: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
    case_sensitive: bool = False,
    strict_boundaries: bool | None = None,
    match_compounds: bool = False,
    dossier_id: str | None = None,
    claim_id: str | None = None,
    expected_config_snapshot: tuple[tuple[int, ...] | None, bytes] | None = None,
) -> dict[str, Any]:
    """Create or update one author-chosen term/prop profile in lixity.toml without archive writes."""
    from ..config import (
        prepare_project_settings,
        project_config_snapshot,
        read_explicit_project_config,
    )
    from ..terms import parse_terms

    repository = Repository(project)
    snapshot = repository.snapshot()
    try:
        observed_config = project_config_snapshot(
            repository.root / "lixity.toml", maximum_bytes=65536
        )
        if expected_config_snapshot is not None and observed_config != expected_config_snapshot:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        current_settings = read_explicit_project_config(repository.root, maximum_bytes=65536)
        terms_map = {
            name: profile.model_dump(exclude_none=True)
            for name, profile in parse_terms(current_settings.get("terms")).items()
        }
        candidate_entry: dict[str, Any] = {
            "aliases": list(aliases),
            "scoped_alternatives": list(scoped_alternatives),
            "case_sensitive": case_sensitive,
            "strict_boundaries": strict_boundaries,
            "match_compounds": match_compounds,
        }
        if dossier_id:
            candidate_entry["dossier_id"] = dossier_id
        if claim_id:
            candidate_entry["claim_id"] = claim_id
        terms_map[term] = candidate_entry
        validated = parse_terms(terms_map)
        serialized = {
            name: profile.model_dump(exclude_none=True) for name, profile in validated.items()
        }
        prepared = prepare_project_settings(repository.root, {"terms": serialized})
        if prepared.original != observed_config:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        prepared.commit()
    except (ValidationError, ValueError) as error:
        raise ResearchError(f"Invalid term profile: {error}") from error
    return {
        "schema_version": "research-terms-config-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "term": term,
        "terms": [
            {"term": name, **profile.model_dump(mode="json")} for name, profile in validated.items()
        ],
    }


def delete_term_profile(
    project: str | Path,
    term: str,
    *,
    expected_config_snapshot: tuple[tuple[int, ...] | None, bytes] | None = None,
) -> dict[str, Any]:
    """Delete one configured term/prop profile from lixity.toml without archive writes."""
    from ..config import (
        prepare_project_settings,
        project_config_snapshot,
        read_explicit_project_config,
    )
    from ..terms import parse_terms

    repository = Repository(project)
    snapshot = repository.snapshot()
    try:
        observed_config = project_config_snapshot(
            repository.root / "lixity.toml", maximum_bytes=65536
        )
        if expected_config_snapshot is not None and observed_config != expected_config_snapshot:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        current_settings = read_explicit_project_config(repository.root, maximum_bytes=65536)
        terms_map = dict(parse_terms(current_settings.get("terms")))
    except (ValidationError, ValueError) as error:
        raise ResearchError(f"Invalid term configuration: {error}") from error
    if term not in terms_map:
        raise ResearchError(f"Unknown configured term: {term!r}")
    del terms_map[term]
    serialized = {
        name: profile.model_dump(exclude_none=True) for name, profile in terms_map.items()
    }
    try:
        prepared = prepare_project_settings(repository.root, {"terms": serialized})
        if prepared.original != observed_config:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        prepared.commit()
    except ValueError as error:
        raise ResearchError(f"Could not update term configuration: {error}") from error
    return {
        "schema_version": "research-terms-config-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "deleted_term": term,
        "terms": [
            {"term": name, **profile.model_dump(mode="json")} for name, profile in terms_map.items()
        ],
    }


def set_term_profiles(
    project: str | Path,
    terms: object,
    *,
    expected_config_snapshot: tuple[tuple[int, ...] | None, bytes] | None = None,
) -> dict[str, Any]:
    """Replace all configured term/prop profiles in lixity.toml without archive writes."""
    from ..config import prepare_project_settings
    from ..terms import parse_terms

    repository = Repository(project)
    snapshot = repository.snapshot()
    try:
        validated = parse_terms(terms)
        serialized = {
            name: profile.model_dump(exclude_none=True) for name, profile in validated.items()
        }
        prepared = prepare_project_settings(repository.root, {"terms": serialized})
        if expected_config_snapshot is not None and prepared.original != expected_config_snapshot:
            raise ValueError("Project config changed while saving; nothing was overwritten")
        prepared.commit()
    except (ValidationError, ValueError) as error:
        raise ResearchError(f"Invalid term configuration: {error}") from error
    return {
        "schema_version": "research-terms-config-local/1",
        "project_id": snapshot.project.id,
        "snapshot": snapshot.digest,
        "terms": [
            {"term": name, **profile.model_dump(mode="json")} for name, profile in validated.items()
        ],
    }


def get_dossier(
    project: str | Path,
    dossier_id: str,
    *,
    section: str | None = None,
    preamble: bool = False,
    revision: int | None = None,
    summary: bool = False,
    include_citations: bool = True,
    manuscript: str | Path | None = None,
    include_character_binding: bool = False,
) -> dict[str, Any]:
    """Retrieve details of a specific dossier with optional section or summary bounding."""
    repository = Repository(project)
    snapshot = repository.snapshot()
    return _get_dossier(
        repository,
        snapshot,
        dossier_id,
        section=section,
        preamble=preamble,
        revision=revision,
        summary=summary,
        include_citations=include_citations,
        manuscript=manuscript,
        include_character_binding=include_character_binding,
    )


def _get_dossier(
    repository: Repository,
    snapshot: Snapshot,
    dossier_id: str,
    *,
    section: str | None = None,
    revision: int | None = None,
    summary: bool = False,
    include_citations: bool = True,
    preamble: bool = False,
    manuscript: str | Path | None = None,
    include_character_binding: bool = False,
) -> dict[str, Any]:
    """Build native dossier detail against one accepted snapshot."""
    if revision is not None and (type(revision) is not int or revision < 1):
        raise ResearchError("Revision must be a positive integer")
    if type(preamble) is not bool or (preamble and (section is not None or summary)):
        raise ResearchError("Choose a preamble, section or summary read")
    dossier = (
        snapshot.latest(dossier_id, Dossier)
        if revision is None
        else snapshot.get(Reference(id=dossier_id, revision=revision), Dossier)
    )
    availability = dossier_withdrawal(snapshot, dossier.id)

    withdrawn_or_purged = {
        record.target_ref.id
        for record in snapshot.records.values()
        if isinstance(record, Tombstone) and record.operation in ("withdraw", "purge")
    }
    if dossier.id in withdrawn_or_purged and not (revision is not None and availability):
        raise ResearchError("Dossier has been withdrawn or purged")

    decision_reviews = editorial.dossier_reviews(snapshot).get(dossier.id, [])

    spans = _section_spans(dossier.body)
    sections = _extract_sections(dossier.body, spans)
    editable_sections = [] if availability else _editable_section_titles(spans)
    if preamble:
        content = preamble_text(dossier.body)
        res = {
            "id": dossier.id,
            **availability,
            "project_id": snapshot.project.id,
            "snapshot": snapshot.digest,
            "title": dossier.title,
            "revision": dossier.revision,
            "preamble": True,
            "section": None,
            "section_level": None,
            "content": content,
            "images": resolve_dossier_images(snapshot, content),
            "media": resolve_dossier_media(snapshot, content),
            "editable_sections": editable_sections,
        }
        if manuscript is not None:
            res["manuscript_evidence"] = dossier_manuscript_evidence(
                repository.root, dossier.id, manuscript=manuscript
            )
        return res
    if summary:
        reader = EvidenceCitationReader(repository, snapshot)
        resolved_citations = (
            [reader.read(ref) for ref in dossier.evidence_refs] if include_citations else []
        )
        res = {
            "id": dossier.id,
            **availability,
            "project_id": snapshot.project.id,
            "images": resolve_dossier_images(snapshot, dossier.body),
            "media": resolve_dossier_media(snapshot, dossier.body),
            "title": dossier.title,
            "language": dossier.language,
            "tags": dossier.tags,
            "revision": dossier.revision,
            "snapshot": snapshot.digest,
            "created_at": dossier.created_at,
            "created_by": dossier.created_by,
            "body_length": len(dossier.body),
            "sections": list(sections.keys()),
            "editable_sections": editable_sections,
            "citation_count": len(dossier.evidence_refs),
            "geography_feature_count": len(dossier.geography.features) if dossier.geography else 0,
            "geography_summary": summarize_geography(dossier.geography),
            "excerpt": dossier.body[:500] + ("..." if len(dossier.body) > 500 else ""),
            "decision_reviews": decision_reviews,
            "review_needed": any(r["status"] == "review_needed" for r in decision_reviews),
            "source_updates": source_updates(resolved_citations) if include_citations else [],
        }
        if manuscript is not None:
            res["manuscript_evidence"] = dossier_manuscript_evidence(
                repository.root, dossier.id, manuscript=manuscript
            )
        return res

    if section is not None:
        matches = [span for span in spans if span.title.casefold() == section.strip().casefold()]
        if len(matches) > 1:
            raise ResearchError(
                f"Section '{section}' is ambiguous: {len(matches)} headings share this title; read the full dossier"
            )
        matched = next((k for k in sections if k.casefold() == section.strip().casefold()), None)
        if matched is None:
            raise ResearchError(
                f"Section '{section}' not found in dossier; available: {', '.join(sections.keys()) or 'none'}"
            )
        selected_content = (
            dossier.body[
                matches[0].content_start : _section_subtree_end(
                    spans, matches[0], len(dossier.body)
                )
            ].strip("\r\n")
            if matches
            else sections[matched]
        )
        res = {
            "id": dossier.id,
            **availability,
            "project_id": snapshot.project.id,
            "images": resolve_dossier_images(snapshot, selected_content),
            "media": resolve_dossier_media(snapshot, selected_content),
            "title": dossier.title,
            "revision": dossier.revision,
            "snapshot": snapshot.digest,
            "section": matched,
            "section_level": matches[0].level if matches else None,
            "editable_sections": editable_sections,
            "content": selected_content,
            "decision_reviews": decision_reviews,
            "review_needed": any(r["status"] == "review_needed" for r in decision_reviews),
        }
        if manuscript is not None:
            res["manuscript_evidence"] = dossier_manuscript_evidence(
                repository.root, dossier.id, manuscript=manuscript
            )
        return res

    reader = EvidenceCitationReader(repository, snapshot)
    resolved_citations = (
        [reader.read(ref) for ref in dossier.evidence_refs] if include_citations else []
    )

    res = {
        "id": dossier.id,
        **availability,
        "project_id": snapshot.project.id,
        "images": resolve_dossier_images(snapshot, dossier.body),
        "media": resolve_dossier_media(snapshot, dossier.body),
        "title": dossier.title,
        "language": dossier.language,
        "tags": dossier.tags,
        "body": dossier.body,
        "geography": dossier.geography.model_dump(mode="json") if dossier.geography else None,
        "geography_summary": summarize_geography(dossier.geography),
        "sections": list(sections.keys()),
        "editable_sections": editable_sections,
        "section_map": sections,
        "created_at": dossier.created_at,
        "created_by": dossier.created_by,
        "citations": resolved_citations,
        "revision": dossier.revision,
        "snapshot": snapshot.digest,
        "source_updates": source_updates(resolved_citations),
        "decision_reviews": decision_reviews,
        "review_needed": any(r["status"] == "review_needed" for r in decision_reviews),
    }
    if manuscript is not None:
        res["manuscript_evidence"] = dossier_manuscript_evidence(
            repository.root, dossier.id, manuscript=manuscript
        )
    if include_character_binding and revision is None and _generated_character_name(snapshot, dossier.id):
        res["character_analysis_available"] = True
    return res


def _generated_character_name(snapshot: Snapshot, dossier_id: str) -> str | None:
    """Resolve the generated binding from the immutable original dossier."""
    if any(identifier == dossier_id and operation in ("withdraw", "purge")
           for operation, _kind, identifier in snapshot.lifecycle):
        return None
    original = snapshot.revisions.get((dossier_id, 1))
    if not isinstance(original, Dossier) or not {"character", "manuscript-draft"}.issubset(original.tags):
        return None
    for prefix in ("Figur: ", "Character: "):
        if original.title.startswith(prefix):
            return original.title.removeprefix(prefix).strip() or None
    return None


def generated_character_binding(project: str | Path, dossier_id: str) -> tuple[str, str] | None:
    """Read the archive ID and captured label from the same snapshot."""
    snapshot = Repository(project).snapshot(kinds=frozenset({"dossier", "tombstone"}))
    name = _generated_character_name(snapshot, dossier_id)
    return (snapshot.project.id, name) if name is not None else None


DraftKind = Literal["all", "character", "scene", "location"]
_DRAFT_ORIGIN_TAG = "manuscript-draft:"
_DRAFT_TITLE_PREFIXES = {
    "character": ("figur:", "character:"),
    "location": ("ort:", "location:"),
    "scene": ("szene:", "scene:"),
}


def _draft_label(value: str) -> str:
    return normalize("NFC", value.strip().casefold())


def _draft_legacy_key(draft: Mapping[str, Any]) -> tuple[str, str]:
    if draft["id"] == "scenes:manuscript":
        return "register", ""
    kind = str(draft["kind"])
    return kind, _draft_label(str(draft["evidence_hints"][kind]))


def _draft_digest(value: Any) -> str:
    return digest(json.dumps(value, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8"))


def _draft_origin(draft: Mapping[str, Any], root: Path, manuscript: Path) -> str:
    kind, label = _draft_legacy_key(draft)
    identity = [kind, label]
    if kind in ("scene", "register"):
        label = manuscript.relative_to(root).as_posix() if manuscript.is_relative_to(root) else manuscript.as_posix()
        identity = [kind, label, draft["id"]]
    if kind == "scene":
        hints = draft["evidence_hints"]
        identity.extend([hints.get("scene_scope"), hints.get("scene_source_sha256")])
    return _DRAFT_ORIGIN_TAG + _draft_digest(identity)[:32]


def _saved_draft_keys(snapshot: Snapshot) -> tuple[dict[str, list[Dossier]], dict[tuple[str, str], list[Dossier]]]:
    """Use accepted origin tags, with exact legacy names only within one kind."""
    retired = {identifier for operation, kind, identifier in snapshot.lifecycle
               if kind == "dossier" and operation in ("withdraw", "purge")}
    origins: dict[str, list[Dossier]] = {}
    legacy: dict[tuple[str, str], list[Dossier]] = {}
    for record in snapshot.records.values():
        if not isinstance(record, Dossier) or record.id in retired:
            continue
        original = snapshot.get(Reference(id=record.id, revision=1), Dossier)
        tags = {_draft_label(tag) for tag in original.tags}
        generated = "manuscript-draft" in tags
        identity = {tag for tag in tags if tag.startswith(_DRAFT_ORIGIN_TAG)
                    and re.fullmatch(r"[0-9a-f]{32}", tag.removeprefix(_DRAFT_ORIGIN_TAG))}
        if generated and identity:
            for tag in identity:
                origins.setdefault(tag, []).append(record)
            continue
        title = _draft_label(original.title if generated else record.title)
        if generated and "scenes" in tags and title.startswith(("szenenregister (", "scene register (")):
            legacy.setdefault(("register", ""), []).append(record)
            continue
        for kind, prefixes in _DRAFT_TITLE_PREFIXES.items():
            if kind == "scene" and not (generated and "scene" in tags):
                continue
            prefix = next((value for value in prefixes if title.startswith(value)), None)
            if prefix is not None:
                legacy.setdefault((kind, title.removeprefix(prefix).strip()), []).append(record)
                break
    return origins, legacy


def _covered_drafts(
    drafts: Sequence[Mapping[str, Any]], snapshot: Snapshot, root: Path, manuscript: Path,
) -> dict[str, list[Dossier]]:
    origins, legacy = _saved_draft_keys(snapshot)
    labels = Counter(_draft_legacy_key(item) for item in drafts)
    covered: dict[str, list[Dossier]] = {}
    for item in drafts:
        key = _draft_legacy_key(item)
        matches = origins.get(_draft_origin(item, root, manuscript), [])
        if labels[key] == 1:
            matches = [*matches, *legacy.get(key, [])]
        if matches:
            covered[str(item["id"])] = matches
    return covered


def _draft_report(
    root: Path, manuscript: Path, *, language: str | None, kind: DraftKind, snapshot: Snapshot | None,
) -> dict[str, Any]:
    settings = read_explicit_project_config(root, maximum_bytes=MAX_CONFIG_BYTES) if root.is_dir() else {}
    requested = language or (str(settings.get("language")) if settings.get("language") else "en")
    language = "auto" if requested.strip().lower() == "auto" else supported_language(requested)
    text, source_sha256 = FileUtils.read_source_snapshot(str(manuscript))
    payload = extract_manuscript_dossier_drafts(text, language=language, settings=settings, kind=kind)
    project_id = snapshot.project.id if snapshot is not None else None
    analysis = _draft_digest([str(root), project_id, str(manuscript), source_sha256, settings, language])
    for item in payload["drafts"]:
        item["preview_sha256"] = _draft_digest([analysis, item])
    if project_id is not None:
        payload["project_id"] = project_id
    return payload


def manuscript_dossier_drafts(
    project: str | Path,
    manuscript: str | Path,
    *,
    language: str | None = None,
    kind: DraftKind = "all",
    exclude_existing: bool = True,
) -> dict[str, Any]:
    """Extract read-only dossier drafts from a manuscript using deterministic metrics."""
    repository = Repository(project)
    source = Path(manuscript).expanduser().resolve()
    snapshot = repository.snapshot(kinds=frozenset({"dossier"})) if repository.data.is_dir() else None
    payload = _draft_report(repository.root, source, language=language, kind=kind, snapshot=snapshot)
    drafts = payload["drafts"]
    if snapshot is not None:
        covered = _covered_drafts(drafts, snapshot, repository.root, source)
        if exclude_existing:
            payload["drafts"] = [item for item in drafts if item["id"] not in covered]
        else:
            for item in drafts:
                records = covered.get(item["id"])
                if not records:
                    continue
                item["already_covered"] = True
                if item["kind"] == "character" and len(records) == 1:
                    record = records[0]
                    original_name = _generated_character_name(snapshot, record.id)
                    if original_name is not None and _draft_label(original_name) == _draft_legacy_key(item)[1]:
                        item["existing_dossier"] = {"id": record.id, "title": record.title, "revision": record.revision,
                                                   "project_id": snapshot.project.id, "snapshot": snapshot.digest}
    payload["skipped_existing"] = len(drafts) - len(payload["drafts"])
    payload["manuscript"] = str(manuscript)
    return payload


def create_dossier_from_manuscript(
    project: str | Path,
    manuscript: str | Path,
    *,
    draft_id: str | None = None,
    kind: DraftKind = "character",
    language: str | None = None,
    actor: str = "local-author",
    preview_sha256: str | None = None,
    expected_project_id: str | None = None,
) -> dict[str, Any]:
    """Create a Dossier explicitly from a deterministic manuscript draft."""
    if preview_sha256 is not None and (not draft_id or not re.fullmatch(r"[0-9a-f]{64}", preview_sha256)):
        raise ResearchError("A draft ID and valid preview digest are required to confirm a manuscript draft")
    if draft_id is not None:
        prefix = draft_id.partition(":")[0]
        if prefix in ("scene", "scenes"):
            kind = "scene"
        elif prefix == "character":
            kind = "character"
        elif prefix == "location":
            kind = "location"
        else:
            raise ResearchError(f"Unknown manuscript dossier draft ID: {draft_id}")
    repository = Repository(project)
    snapshot = repository.snapshot()
    if expected_project_id is not None and expected_project_id != snapshot.project.id:
        raise ResearchConflictError("Selected research project changed; reload manuscript suggestions")
    source = Path(manuscript).expanduser().resolve()
    try:
        payload = _draft_report(repository.root, source, language=language, kind=kind, snapshot=snapshot)
    except (OSError, ValueError) as exc:
        if preview_sha256 is None:
            raise
        raise ResearchConflictError(f"Could not verify the manuscript draft; reload suggestions: {exc}") from exc
    drafts = payload["drafts"]
    covered = _covered_drafts(drafts, snapshot, repository.root, source)
    if draft_id is None:
        candidates = [item for item in drafts if item["id"] not in covered]
        if not candidates:
            raise ResearchError("No new manuscript dossier drafts could be extracted")
        selected = candidates[0]
    elif preview_sha256 is not None:
        match = next((item for item in drafts if item["id"] == draft_id and item["preview_sha256"] == preview_sha256), None)
        if match is None:
            raise ResearchConflictError("Manuscript draft changed; reload the suggestions before saving")
        selected = match
    else:
        candidates = [item for item in drafts if item["id"] == draft_id or item.get("legacy_id") == draft_id]
        if len(candidates) != 1:
            raise ResearchError(f"Unknown or ambiguous manuscript dossier draft ID: {draft_id}")
        selected = candidates[0]
    if selected["id"] in covered:
        raise ResearchConflictError("A dossier for this manuscript suggestion already exists")
    created = _commit_dossier(
        repository, snapshot,
        str(selected["title"]),
        str(selected["body"]),
        language=payload["language"],
        tags=[*selected["tags"], _draft_origin(selected, repository.root, source)],
        actor=actor,
    )
    return {
        **created,
        "project_id": snapshot.project.id,
        "draft": selected,
    }
