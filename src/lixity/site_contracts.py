"""Publication contracts, separate from accepted project/research records.

Scope choices are per-export disclosure, not stored permissions or recipient
roles. CLI, Python and native downloads validate the same strict options.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .site_publications import ProfileKey

SITE_SCHEMA = "lixity-read-only-site/1"
DATA_SCHEMA = "lixity-read-only-site-data/1"
MAX_SITE_BYTES = 200 * 1024 * 1024
MAX_SITE_DATA_BYTES = 64 * 1024 * 1024
# Review copies budget authored archive versions; source passages are byte-bounded.
MAX_SITE_REVISIONS = 10_000
MAX_SITE_RESPONSES = 50_000
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
SiteMode = Literal["review", "reader", "companion"]
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

    @model_validator(mode="after")
    def source_scope(self) -> SiteExportOptions:
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


class SiteManifest(_SiteModel):
    """Inventory for the publication projection; it is not a restore manifest."""

    schema_version: Literal["lixity-read-only-site/1"]
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

    @model_validator(mode="after")
    def consistent_scope(self) -> SiteManifest:
        scope = SiteExportOptions(include_research=self.research.included,
                                  include_source_files=self.capabilities.source_files,
                                  mode=self.mode,
                                  publication_profile=(self.publication or {}).get("profile"))
        if (self.capabilities.research != scope.include_research
                or (self.research.snapshot is not None) != scope.include_research
                or (not scope.include_research and self.research.revision_count != 0)
                or self.entrypoint not in self.files):
            raise ValueError("Website manifest scope and inventory disagree")
        if self.mode != "review" and (self.capabilities.analysis or self.analysis is not None):
            raise ValueError("Reader publications must not contain analysis payloads")
        return self


class SiteData(_SiteModel):
    """Prepared native responses and explicit static-only media mappings."""

    schema_version: Literal["lixity-read-only-site-data/1"]
    responses: dict[str, Any]
    resources: dict[str, str]
    publication: dict[str, Any] | None = None
