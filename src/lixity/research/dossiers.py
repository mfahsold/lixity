"""Dossier lifecycle, collection, term-profile, and manuscript-draft orchestration."""

import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from pydantic import ValidationError

from . import editorial
from .geography import summarize_geography
from .images import image_descriptions, resolve_dossier_images, resolve_dossier_media
from .manuscript import dossier_manuscript_evidence
from .manuscript_drafts import extract_manuscript_dossier_drafts
from .models import LANGUAGES, Dossier, Language, Passage, Reference, Tombstone
from .repository import Repository, ResearchError, Snapshot
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
    from .api import envelope

    repository = Repository(project)
    snapshot = repository.snapshot()

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


def _draft_matches_existing_dossier(draft: Mapping[str, Any], existing_titles: Sequence[str]) -> bool:
    title_cf = str(draft.get("title") or "").strip().casefold()
    if title_cf and any(t == title_cf for t in existing_titles):
        return True
    kind = str(draft.get("kind") or "")
    if kind == "scene":
        return any(
            t.startswith(("szenenregister", "scene register", "szene:", "scene:"))
            for t in existing_titles
        )
    hints = draft.get("evidence_hints")
    entity_name = str(
        (hints.get("character") or hints.get("location") or hints.get("scene"))
        if isinstance(hints, Mapping)
        else ""
    ).strip()
    if not entity_name:
        return False
    pattern = re.compile(rf"\b{re.escape(entity_name.casefold())}\b")
    return any(bool(pattern.search(t)) for t in existing_titles)


def manuscript_dossier_drafts(
    project: str | Path,
    manuscript: str | Path,
    *,
    language: str | None = None,
    kind: Literal["all", "character", "scene", "location"] = "all",
    exclude_existing: bool = True,
) -> dict[str, Any]:
    """Extract read-only dossier drafts from a manuscript using deterministic metrics."""
    from ..config import read_explicit_project_config

    root = Path(project)
    manuscript_path = Path(manuscript)
    if not manuscript_path.is_file():
        raise ResearchError(f"Manuscript file does not exist: {manuscript_path}")
    settings = read_explicit_project_config(root, maximum_bytes=65536) if root.is_dir() else {}
    resolved_lang = supported_language(
        language or (str(settings.get("language")) if settings.get("language") else "en")
    )
    text = manuscript_path.read_text(encoding="utf-8", errors="replace")
    payload = extract_manuscript_dossier_drafts(
        text,
        language=resolved_lang,
        settings=settings,
        kind=kind,
    )
    skipped_existing = 0
    if exclude_existing and (root / "research").is_dir():
        existing_titles = [
            str(d.get("title") or "").strip().casefold()
            for d in list_dossiers(root).get("dossiers", [])
            if str(d.get("title") or "").strip()
        ]
        if existing_titles:
            kept: list[dict[str, Any]] = []
            for item in payload.get("drafts", []):
                if _draft_matches_existing_dossier(item, existing_titles):
                    skipped_existing += 1
                else:
                    kept.append(item)
            payload["drafts"] = kept
    payload["skipped_existing"] = skipped_existing
    payload["manuscript"] = str(manuscript_path)
    return payload


def create_dossier_from_manuscript(
    project: str | Path,
    manuscript: str | Path,
    *,
    draft_id: str | None = None,
    kind: Literal["all", "character", "scene", "location"] = "character",
    language: str | None = None,
    actor: str = "local-author",
) -> dict[str, Any]:
    """Create a Dossier explicitly from a deterministic manuscript draft."""
    payload = manuscript_dossier_drafts(
        project,
        manuscript,
        language=language,
        kind=kind if draft_id is None else "all",
    )
    drafts = payload.get("drafts", [])
    if not drafts:
        raise ResearchError("No manuscript dossier drafts could be extracted")
    selected: dict[str, Any]
    if draft_id is not None:
        match = next((item for item in drafts if item.get("id") == draft_id), None)
        if match is None:
            raise ResearchError(f"Unknown manuscript dossier draft ID: {draft_id}")
        selected = match
    else:
        selected = drafts[0]
    created = create_dossier(
        project,
        str(selected["title"]),
        str(selected["body"]),
        language=payload["language"],
        tags=list(selected.get("tags", [])),
        actor=actor,
    )
    return {
        **created,
        "draft": selected,
    }
