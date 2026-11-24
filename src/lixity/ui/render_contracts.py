"""Typed inputs for the shared renderer, independent of transport and storage."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Literal

from ..dossier_draft_settings import AUTOMATIC_LOCATION_NAMES
from ..markers import Marker
from ..models import CorpusConfig, CorpusMetrics
from ..style_fingerprint import ParagraphLayerData, StyleFingerprint
from ..style_profile import ChapterProfile, ParagraphProfile
from .manuscript_document import ReaderBlock


@dataclass(frozen=True)
class AnalysisIdentity:
    """Backend-owned analysis scope, never inferred from document context/text."""

    scope: Literal["manuscript_internal", "source_internal"] = "manuscript_internal"
    context_status: Literal["not_applicable", "user_supplied_unverified"] = "not_applicable"
    source_id: str = ""
    source_version_id: str = ""

    def __post_init__(self) -> None:
        if self.scope == "source_internal":
            if (
                not self.source_id
                or not self.source_version_id
                or self.context_status != "user_supplied_unverified"
            ):
                raise ValueError(
                    "Source analysis requires pinned provenance and explicit context status"
                )
        elif (
            self.scope != "manuscript_internal"
            or self.context_status != "not_applicable"
            or self.source_id
            or self.source_version_id
        ):
            raise ValueError("Invalid manuscript analysis identity")


@dataclass(frozen=True)
class DashboardContent:
    """Optional prepared reports and reading data; no rendering capabilities."""

    markers: Sequence[Marker] | None = None
    artifacts: Sequence[Mapping[str, Any]] | None = None
    status: Sequence[Mapping[str, Any]] | None = None
    dialogue: Mapping[str, Any] | None = None
    characters: Mapping[str, Any] | None = None
    pacing: Mapping[str, Any] | None = None
    motifs: Mapping[str, Any] | None = None
    showing: Mapping[str, Any] | None = None
    scenes: Mapping[str, Any] | None = None
    document_context: Mapping[str, Any] | None = None
    reader_document: Sequence[ReaderBlock] | None = None
    identity: AnalysisIdentity = field(default_factory=AnalysisIdentity)


@dataclass(frozen=True)
class DashboardOptions:
    """Presentation and host capabilities; no analysis or report payloads."""

    title: str = "Manuscript"
    labels: Mapping[str, str] | None = None
    language_name: str = ""
    language_key: str = "en"
    tense_available: bool = True
    engine_name: str = "Lixity"
    flag_min_severity: int | None = None
    controls: bool = False
    read_only: bool = False
    api_base: str = "/api"
    manuscript_name: str = ""
    current_language: str | None = None
    language_options: Sequence[Any] | None = None
    enabled_actions: Sequence[str] | None = None
    debug: bool = False
    nda_project_name: str = ""
    project_author: str = ""
    identity_check: Mapping[str, Any] | None = None
    author_setting_enabled: bool = False
    manuscript_pdf_token: str = ""
    scene_intents_token: str = ""
    research_context_token: str = ""
    external_diagram_library: bool = False
    publication: Mapping[str, Any] | None = None
    publication_error: str = ""
    project_token: str = ""
    manuscript_source_sha256: str = ""
    register_settings: Mapping[str, Any] | None = None
    site_publications: Mapping[str, Any] | None = None
    site_publication_context_token: str = ""
    location_names: object = AUTOMATIC_LOCATION_NAMES
    dossier_drafts: object = None
    corpus_config: CorpusConfig | None = None
    project_overview_enabled: bool = False
    project_create_base: str = ""


@dataclass(frozen=True)
class DashboardRenderInput:
    """Complete prepared core measurements plus optional rendered content."""

    chapters: Sequence[ChapterProfile]
    paragraphs: Sequence[ParagraphProfile]
    paragraph_layers: ParagraphLayerData
    metrics: CorpusMetrics | None = None
    fingerprint: StyleFingerprint | None = None
    paragraph_evidence: Mapping[int, Mapping[str, Any]] | None = None
    content: DashboardContent = field(default_factory=DashboardContent)
    paragraph_available_layers: frozenset[str] | None = None
