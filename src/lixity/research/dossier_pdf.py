"""Read and render one exact active dossier revision for a private download."""

from __future__ import annotations

from pathlib import Path

from ..format import num, precise_num
from ..manuscript_document import BlockKind, ManuscriptBlock, TextRun
from ..pdf_layouts import dossier_pdf
from ..workspace_labels import workspace_labels_for
from .dossier_analysis import dossier_display_body
from .geography import summarize_geography
from .models import Dossier, GeographicPoint, Reference
from .repository import Repository
from .revisions import EvidenceCitationReader


def _literal_block(kind: BlockKind, text: str, level: int = 3) -> ManuscriptBlock:
    return ManuscriptBlock(kind, text, level, (TextRun(text),))


def _geography_blocks(dossier: Dossier, labels: dict[str, str]) -> list[ManuscriptBlock]:
    geography = dossier.geography
    summary = summarize_geography(geography)
    if geography is None or summary is None:
        return []
    blocks = [_literal_block("heading", labels["geography_title"], 2)]
    if not geography.features:
        return [*blocks, _literal_block("paragraph", labels["geography_empty"])]
    language = dossier.language
    count = summary["feature_count"]
    overview = "geography_overview_one" if count == 1 else "geography_overview"
    blocks.append(_literal_block("paragraph", labels[overview].format(
        count=count, located=summary["located_feature_count"],
        unlocated=summary["unlocated_feature_count"],
    )))
    for feature, facts in zip(geography.features, summary["features"], strict=True):
        props, geometry = feature.properties, feature.geometry
        blocks.append(_literal_block("heading", props.label))
        context = [labels[f'geography_{facts["geometry_type"]}']]
        for key, value in (
            ("feature_type", props.feature_type),
            ("period", props.time_period),
            ("people", ", ".join(props.actors)),
            ("transport", labels[f"geography_{props.transport}"] if props.transport else None),
        ):
            if value:
                context.append(f"{labels[f'geography_{key}']}: {value}")
        blocks.append(_literal_block("paragraph", " · ".join(context)))
        if isinstance(geometry, GeographicPoint):
            longitude, latitude = geometry.coordinates
            blocks.append(_literal_block("paragraph", labels["geography_position"].format(
                longitude=precise_num(longitude, language, minimum_decimals=0),
                latitude=precise_num(latitude, language, minimum_decimals=0),
            )))
        distance = facts["route_length_km"]
        if distance is not None:
            distance_text = f"< {num(0.01, language, 2)}" if 0 < distance < 0.01 else num(distance, language, 2)
            blocks.append(_literal_block("paragraph", labels["geography_route_facts"].format(
                positions=facts["position_count"], segments=facts["segment_count"], distance=distance_text,
            )))
        if props.description:
            blocks.append(_literal_block("paragraph", props.description))
        if props.waypoint_labels:
            blocks.append(_literal_block("paragraph", " → ".join(props.waypoint_labels)))
    if summary["route_length_km"] is not None:
        blocks.append(_literal_block("note", labels["geography_method"]))
    return blocks


def compose_dossier_pdf(project: Path, ref: Reference) -> tuple[str, bytes] | None:
    """Render the saved body, authored geography and pinned quotations."""
    repository = Repository(project)
    snapshot = repository.snapshot(frozenset({"dossier", "passage", "extraction", "source", "source_version"}))
    dossier = snapshot.revisions.get((ref.id, ref.revision))
    if not isinstance(dossier, Dossier) or any(
        (operation, "dossier", ref.id) in snapshot.lifecycle for operation in ("withdraw", "purge")
    ):
        return None

    labels = workspace_labels_for(dossier.language)
    revision = labels["research_revision_number"].format(revision=dossier.revision)
    appendix = _geography_blocks(dossier, labels)
    if dossier.evidence_refs:
        appendix.append(_literal_block("heading", labels["research_citations"], 2))
        reader = EvidenceCitationReader(repository, snapshot)
        for evidence in dossier.evidence_refs:
            citation = reader.read(evidence)
            if citation.get("availability") != "available":
                appendix.append(_literal_block("paragraph", labels["research_evidence_unavailable"]))
                continue
            source_revision = labels["research_revision_number"].format(revision=citation["source_sequence"])
            title = f'{citation["source_title"]} · {source_revision}'
            quote = citation["verbatim"]
            appendix.extend((
                _literal_block("heading", title),
                _literal_block("quote", quote),
            ))

    return dossier.title, dossier_pdf(
        title=dossier.title, revision_label=revision, language=dossier.language,
        body=dossier_display_body(snapshot, dossier), appendix=appendix,
    )
