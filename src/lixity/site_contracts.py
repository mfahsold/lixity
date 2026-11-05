"""Publication contracts, separate from accepted project/research records.

Scope choices are per-export disclosure, not stored permissions or recipient
roles. CLI, Python and native downloads validate the same strict options.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    model_serializer,
    model_validator,
)

from .site_publications import ProfileKey

SITE_SCHEMA = "lixity-read-only-site/1"
SITE_ANALYSIS_SCHEMA = "lixity-read-only-site/2"
SITE_AUDIO_SCHEMA = "lixity-read-only-site/3"
DATA_SCHEMA = "lixity-read-only-site-data/1"
MAX_SITE_BYTES = 200 * 1024 * 1024
MAX_SITE_DATA_BYTES = 64 * 1024 * 1024
# Review copies budget authored archive versions; source passages are byte-bounded.
MAX_SITE_REVISIONS = 10_000
MAX_SITE_RESPONSES = 50_000
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SiteMode = Literal["review", "reader", "companion"]
AnalysisSection = Literal["chapters", "language", "full"]
SITE_MODES = get_args(SiteMode)


class _SiteModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class SiteExportOptions(_SiteModel):
    """Explicit disclosure choices; callers must not infer redistribution rights."""

    include_research: bool = False
    include_source_files: bool = False
    mode: SiteMode = "review"
    publication_profile: ProfileKey | None = None
    max_chapter: Annotated[int, Field(ge=0)] | None = None
    analysis_sections: Annotated[list[AnalysisSection], Field(max_length=3)] = Field(default_factory=list)
    include_audio: bool = False

    @model_serializer(mode="wrap")
    def serialize_options(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        """Keep the v1 default representation unchanged while exposing opt-ins."""
        data: dict[str, Any] = handler(self)
        if not self.analysis_sections:
            data.pop("analysis_sections", None)
        if not self.include_audio:
            data.pop("include_audio", None)
        return data

    @model_validator(mode="after")
    def source_scope(self) -> SiteExportOptions:
        if len(set(self.analysis_sections)) != len(self.analysis_sections):
            raise ValueError("Analysis sections must not be repeated")
        if "full" in self.analysis_sections and len(self.analysis_sections) != 1:
            raise ValueError("Full analysis cannot be combined with individual analysis sections")
        if self.mode != "reader" and self.analysis_sections:
            raise ValueError("Selected analysis is available only in reader mode")
        if self.mode != "reader" and self.include_audio:
            raise ValueError("Chapter audio is available only in reader mode")
        if self.mode == "review":
            if self.publication_profile is not None or self.max_chapter is not None:
                raise ValueError("Publication profile and chapter cap require reader or companion mode")
            if self.include_source_files and not self.include_research:
                raise ValueError("--include-source-files requires --include-research in review mode")
        else:
            if self.publication_profile is None:
                raise ValueError("Reader and companion modes require --publication-profile")
            if self.include_research:
                raise ValueError("--include-research exposes internal archive data and is only available in review mode")
        return self


class SiteExportRequest(SiteExportOptions):
    """Native request binds those choices to the selected manuscript metadata."""

    project_token: Digest
    include_research: bool = Field(...)
    include_source_files: bool = Field(...)

    def export_options(self) -> SiteExportOptions:
        return SiteExportOptions.model_validate(self.model_dump(exclude={"project_token"}))


class SiteExportReport(_SiteModel):
    """Content-free browser receipt, correlated with one native ZIP response."""

    export_id: Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")] | None = None
    stage: Literal["response_read", "zip_check", "download_start", "download_started",
                   "profiles_invalid", "profiles_empty", "profiles_unsaved", "profiles_available",
                   "catalogue_failed"]
    error_name: Literal["AbortError", "NetworkError", "TypeError", "Error", "Other"] | None = None
    profile_count: Annotated[int, Field(ge=0, le=50)] | None = None
    http_status: Annotated[int, Field(ge=0, le=599)] | None = None


class SiteFile(_SiteModel):
    sha256: Digest
    byte_length: Annotated[int, Field(ge=0)]


class SiteProject(_SiteModel):
    title: str
    language: str
    id: str | None = None


class SiteManuscript(_SiteModel):
    name: str | None = None
    source_sha256: Digest


class SiteAnalysis(_SiteModel):
    language: str
    thresholds: dict[str, Any]


class SiteResearch(_SiteModel):
    included: bool
    snapshot: Digest | None
    revision_count: Annotated[int, Field(ge=0)]


class SiteCapabilities(_SiteModel):
    read_only: Literal[True]
    analysis: bool
    research: bool
    source_files: bool
    automatic_external_requests: bool


class SiteAudioTrack(_SiteModel):
    """Public chapter playback metadata; never a worker or voice-reference binding."""

    chapter: Annotated[int, Field(ge=1)]
    title: str
    file: Annotated[str, Field(pattern=r"^assets/audio/[0-9a-f]{64}\.wav$")]
    sha256: Digest
    byte_length: Annotated[int, Field(gt=44)]
    duration_seconds: Annotated[float, Field(gt=0, allow_inf_nan=False)]
    origin: Literal["generated", "imported"]


class SiteAudio(_SiteModel):
    schema_version: Literal["lixity-reader-audio/1"]
    source_sha256: Digest
    tracks: Annotated[list[SiteAudioTrack], Field(min_length=1, max_length=1000)]


class SiteManifest(_SiteModel):
    """Inventory for the publication projection; it is not a restore manifest."""

    schema_version: Literal["lixity-read-only-site/1", "lixity-read-only-site/2", "lixity-read-only-site/3"]
    product_version: str
    created_at: str
    entrypoint: str
    project: SiteProject
    manuscript: SiteManuscript
    analysis: SiteAnalysis | None = None
    research: SiteResearch
    capabilities: SiteCapabilities
    disclosures: list[str]
    files: dict[str, SiteFile]
    mode: SiteMode = "review"
    publication: dict[str, Any] | None = None
    audio: SiteAudio | None = None

    @model_validator(mode="after")
    def consistent_scope(self) -> SiteManifest:
        scope = SiteExportOptions(include_research=self.research.included,
                                  include_source_files=self.capabilities.source_files,
                                  mode=self.mode,
                                  publication_profile=(self.publication or {}).get("profile"),
                                  analysis_sections=(self.publication or {}).get("analysis_sections", []),
                                  include_audio=self.audio is not None)
        if (self.capabilities.research != scope.include_research
                or (self.research.snapshot is not None) != scope.include_research
                or (not scope.include_research and self.research.revision_count != 0)
                or self.entrypoint not in self.files):
            raise ValueError("Website manifest scope and inventory disagree")
        if self.schema_version == SITE_SCHEMA and self.mode != "review" and (
                scope.analysis_sections or self.capabilities.analysis or self.analysis is not None):
            raise ValueError("Version 1 reader publications must not contain analysis payloads")
        if self.schema_version == SITE_ANALYSIS_SCHEMA and (
                self.mode != "reader" or not scope.analysis_sections or not self.capabilities.analysis
                or self.analysis is None or "analysis.html" not in self.files):
            raise ValueError("Version 2 requires explicitly selected reader analysis")
        if (self.audio is not None) != (self.schema_version == SITE_AUDIO_SCHEMA):
            raise ValueError("Version 3 requires explicitly selected reader audio")
        audio_files = {name for name in self.files if name.startswith("assets/audio/")}
        if audio_files != ({track.file for track in self.audio.tracks} if self.audio else set()):
            raise ValueError("Audio files must exactly match the disclosed chapter tracks")
        if self.audio is not None:
            cap = (self.publication or {}).get("max_chapter")
            if (type(cap) is not int or self.audio.source_sha256 != self.manuscript.source_sha256
                    or len({track.chapter for track in self.audio.tracks}) != len(self.audio.tracks)
                    or self.capabilities.analysis != bool(scope.analysis_sections)
                    or (self.analysis is not None) != bool(scope.analysis_sections)
                    or (scope.analysis_sections and "analysis.html" not in self.files)):
                raise ValueError("Reader audio, chapter scope and analysis inventory disagree")
            for track in self.audio.tracks:
                stored = self.files.get(track.file)
                if (track.chapter > cap or stored is None or stored.sha256 != track.sha256
                        or stored.byte_length != track.byte_length
                        or track.file != f"assets/audio/{track.sha256}.wav"):
                    raise ValueError("Reader audio exceeds its chapter cap or file inventory")
        return self


class SiteData(_SiteModel):
    """Prepared native responses and explicit static-only media mappings."""

    schema_version: Literal["lixity-read-only-site-data/1"]
    responses: dict[str, Any]
    resources: dict[str, str]
    publication: dict[str, Any] | None = None
