"""Strict contracts for the local source-to-citation pilot, not the entire RFC."""

from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    TypeAdapter,
    field_validator,
    model_serializer,
    model_validator,
)

Identifier = Annotated[str, Field(pattern=r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Language = Literal["en", "de", "fr", "es", "it", "pt", "nl", "generic"]
Kind = Literal[
    "project",
    "source",
    "source_version",
    "activity",
    "extraction",
    "passage",
    "tombstone",
    "dossier",
    "claim",
    "evidence_link",
    "decision",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Reference(StrictModel):
    id: Identifier
    revision: Annotated[int, Field(ge=1)] = 1


class Blob(StrictModel):
    sha256: Digest
    byte_length: Annotated[int, Field(ge=0, le=50 * 1024 * 1024)]
    media_type: Literal["text/plain", "application/pdf", "image/png", "image/jpeg"] = "text/plain"


class Record(StrictModel):
    schema_version: Literal["research-local/1"] = "research-local/1"
    id: Identifier
    revision: Annotated[int, Field(ge=1, le=1)] = 1
    project_id: Identifier
    created_at: Annotated[str, Field(pattern=r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{6}Z$")]
    created_by: Annotated[str, Field(min_length=1, max_length=200)]

    @field_validator("created_at")
    @classmethod
    def valid_timestamp(cls, value: str) -> str:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")
        return value


class RevisionChange(StrictModel):
    """Explicit author intent attached to a replacement authored revision."""

    change_kind: Literal["correction", "supersession"]
    reason: Annotated[str, Field(min_length=1, max_length=2000)]
    previous_revision: Annotated[int, Field(ge=1)]

    @field_validator("reason")
    @classmethod
    def nonblank_reason(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("A revision reason must not be blank")
        return value


class AuthoredRecord(Record):
    # Frozen authored records intentionally extend the otherwise fixed v1 envelope.
    schema_version: Literal["research-local/1", "research-local/2"] = "research-local/1"  # type: ignore[assignment]
    revision: Annotated[int, Field(ge=1)] = 1
    change: RevisionChange | None = None

    @model_validator(mode="after")
    def valid_revision(self) -> "AuthoredRecord":
        if self.revision == 1:
            if self.schema_version != "research-local/1" or self.change is not None:
                raise ValueError("Initial authored records retain the revision-1 contract")
        elif (self.schema_version != "research-local/2" or self.change is None
              or self.change.previous_revision != self.revision - 1):
            raise ValueError("Authored revisions require version 2 and their immediate predecessor")
        return self


class Project(Record):
    kind: Literal["project"] = "project"
    title: Annotated[str, Field(min_length=1, max_length=500)]
    language: Language = "en"


class Source(Record):
    kind: Literal["source"] = "source"
    title: Annotated[str, Field(min_length=1, max_length=500)]
    language: Language


ContextLabel = Annotated[str, Field(min_length=1, max_length=500)]


class ExternalReference(StrictModel):
    """Versioned local Zotero identity; independent of mutable prose metadata."""

    provider: Literal["zotero"] = "zotero"
    server_id: Annotated[str, Field(min_length=1, max_length=200)]
    library: Annotated[str, Field(pattern=r"^(users/(0|[1-9][0-9]*)|groups/[1-9][0-9]*)$")]
    item_key: Annotated[str, Field(pattern=r"^[A-Z0-9]{8}$")]
    attachment_key: Annotated[str, Field(pattern=r"^[A-Z0-9]{8}$")]
    item_version: Annotated[int, Field(ge=0)]
    attachment_version: Annotated[int, Field(ge=0)]


class SourceContext(StrictModel):
    """User-supplied source criticism, not verified facts or inferred identities."""

    genre: ContextLabel | None = None
    created_period: ContextLabel | None = None
    depicted_period: ContextLabel | None = None
    place: ContextLabel | None = None
    perspective: ContextLabel | None = None
    original_language: ContextLabel | None = None
    is_translation: bool | None = None
    provenance_note: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    origin_url: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list)
    external_reference: ExternalReference | None = None

    @field_validator("origin_url")
    @classmethod
    def valid_origin_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        invalid = "Origin URL must be an absolute HTTP(S) URL without credentials or whitespace"
        if any(char.isspace() or ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError(invalid)
        try:
            parsed = urlsplit(value)
            port = parsed.port
            if (parsed.scheme not in ("http", "https") or not parsed.hostname
                    or parsed.username is not None or parsed.password is not None
                    or "\\" in value or (port is not None and not 1 <= port <= 65535)):
                raise ValueError(invalid)
        except ValueError:
            raise ValueError(invalid) from None
        return value

    @model_serializer(mode="wrap")
    def serialize_context(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        result: dict[str, Any] = handler(self)
        if self.origin_url is None:
            result.pop("origin_url", None)
        if self.external_reference is None:
            result.pop("external_reference", None)
        return result


class SourceVersion(Record):
    schema_version: Literal["research-local/1", "research-local/2", "research-local/3"] = "research-local/1"  # type: ignore[assignment]
    kind: Literal["source_version"] = "source_version"
    source_ref: Reference
    sequence: Annotated[int, Field(ge=1)]
    blob: Blob
    retention_confirmed: Literal[True]
    redistribution: Literal["unknown"] = "unknown"
    context: SourceContext = Field(default_factory=SourceContext)

    @model_validator(mode="after")
    def valid_provenance_version(self) -> "SourceVersion":
        if self.context.external_reference is not None and self.schema_version != "research-local/3":
            raise ValueError("External reference requires source version schema research-local/3")
        if self.context.origin_url is not None and self.schema_version == "research-local/1":
            raise ValueError("Origin URL requires source version schema research-local/2")
        return self


class Activity(Record):
    kind: Literal["activity"] = "activity"
    source_version_ref: Reference
    operation: Literal["extract_utf8", "extract_ocr"] = "extract_utf8"
    implementation: Literal["utf8-paragraphs/1", "baidu-unlimited-ocr/1"] = "utf8-paragraphs/1"
    status: Literal["succeeded", "failed"] = "succeeded"


class Extraction(Record):
    kind: Literal["extraction"] = "extraction"
    source_version_ref: Reference
    activity_ref: Reference
    text_blob: Blob
    encoding: Literal["UTF-8"] = "UTF-8"
    normalization: Literal["none"] = "none"
    offset_unit: Literal["unicode_codepoint"] = "unicode_codepoint"


class Passage(Record):
    kind: Literal["passage"] = "passage"
    extraction_ref: Reference
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    verbatim: Annotated[str, Field(min_length=1, max_length=2 * 1024 * 1024)]
    language: Language
    verification: Literal["unreviewed"] = "unreviewed"

    @model_validator(mode="after")
    def valid_span(self) -> "Passage":
        if self.end - self.start != len(self.verbatim):
            raise ValueError("Passage offsets must match the quote length")
        return self


class Dossier(AuthoredRecord):
    kind: Literal["dossier"] = "dossier"
    title: Annotated[str, Field(min_length=1, max_length=500)]
    language: Language = "en"
    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list)
    body: Annotated[str, Field(min_length=1, max_length=2 * 1024 * 1024)]
    evidence_refs: list[Reference] = Field(default_factory=list)


class ClaimScope(StrictModel):
    time_period: ContextLabel | None = None
    place: ContextLabel | None = None
    actors: list[Annotated[str, Field(min_length=1, max_length=100)]] = Field(default_factory=list)


class Claim(AuthoredRecord):
    kind: Literal["claim"] = "claim"
    title: Annotated[str, Field(min_length=1, max_length=500)]
    statement: Annotated[str, Field(min_length=1, max_length=10000)]
    confidence: Literal["hypothetical", "evidenced", "disputed"] = "hypothetical"
    scope: ClaimScope = Field(default_factory=ClaimScope)
    dossier_ref: Reference | None = None
    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list)


EvidenceRelation = Literal["supports", "contradicts", "qualifies", "contextualizes"]


class EvidenceLink(AuthoredRecord):
    kind: Literal["evidence_link"] = "evidence_link"
    claim_ref: Reference
    passage_ref: Reference
    relation: EvidenceRelation = "supports"
    rationale: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    reviewer: Annotated[str, Field(min_length=1, max_length=200)] = "author"


class Decision(AuthoredRecord):
    kind: Literal["decision"] = "decision"
    title: Annotated[str, Field(min_length=1, max_length=500)]
    rationale: Annotated[str, Field(min_length=1, max_length=10000)]
    claim_ref: Reference | None = None
    deviation_from_fact: bool = False
    impact_on_plot: Annotated[str, Field(min_length=1, max_length=2000)] | None = None


class Tombstone(Record):
    kind: Literal["tombstone"] = "tombstone"
    target_ref: Reference
    target_kind: Literal[
        "source",
        "source_version",
        "activity",
        "extraction",
        "passage",
        "dossier",
        "claim",
        "evidence_link",
        "decision",
    ]
    operation: Literal["withdraw", "purge"]
    reason: Annotated[str, Field(min_length=1, max_length=500)]


Entity = Annotated[
    Project
    | Source
    | SourceVersion
    | Activity
    | Extraction
    | Passage
    | Tombstone
    | Dossier
    | Claim
    | EvidenceLink
    | Decision,
    Field(discriminator="kind"),
]
ENTITY: TypeAdapter[Entity] = TypeAdapter(Entity)


class Entry(StrictModel):
    kind: Kind
    ref: Reference
    sha256: Digest


class Manifest(StrictModel):
    schema_version: Literal["research-manifest-local/1", "research-manifest-local/2", "research-manifest-local/3"] = "research-manifest-local/1"
    project_id: Identifier
    generation: Annotated[int, Field(ge=1)]
    parent: Digest | None
    entries: Annotated[list[Entry], Field(min_length=1, max_length=25000)]


class Head(StrictModel):
    schema_version: Literal["research-head-local/1"] = "research-head-local/1"
    sha256: Digest


def reference(record: Record) -> Reference:
    return Reference(id=record.id, revision=record.revision)
