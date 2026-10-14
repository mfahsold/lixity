"""Strict contracts for the local source-to-citation pilot, not the entire RFC."""

from datetime import datetime
from pathlib import PurePosixPath
from typing import Annotated, Any, ClassVar, Literal, get_args
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

from .limits import MAX_PDF_BYTES, MAX_SOURCE_BYTES, MAX_SOURCE_CONTEXT_CHARS

Identifier = Annotated[str, Field(pattern=r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Language = Literal["en", "de", "fr", "es", "it", "pt", "nl", "generic"]
ClaimConfidence = Literal["hypothetical", "evidenced", "disputed"]
# Runtime views of the strict literals; get_args keeps both in sync.
LANGUAGES: tuple[Language, ...] = get_args(Language)
CLAIM_CONFIDENCES: tuple[ClaimConfidence, ...] = get_args(ClaimConfidence)
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
    "claim_relation",
    "manuscript_claim_link",
    "evidence_link",
    "decision",
    "decision_acknowledgement",
]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Reference(StrictModel):
    id: Identifier
    revision: Annotated[int, Field(ge=1)] = 1


class Blob(StrictModel):
    sha256: Digest
    byte_length: Annotated[int, Field(ge=0, le=MAX_PDF_BYTES)]
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
    initial_schema_version: ClassVar[str] = "research-local/1"
    revision_schema_version: ClassVar[str] = "research-local/2"

    @model_validator(mode="after")
    def valid_revision(self) -> "AuthoredRecord":
        if self.revision == 1:
            if self.schema_version != self.initial_schema_version or self.change is not None:
                raise ValueError("Initial authored records retain the revision-1 contract")
        elif (self.schema_version != self.revision_schema_version or self.change is None
              or self.change.previous_revision != self.revision - 1):
            version = self.revision_schema_version.rsplit("/", 1)[1]
            raise ValueError(f"Authored revisions require version {version} and their immediate predecessor")
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
    provenance_note: Annotated[str, Field(min_length=1, max_length=MAX_SOURCE_CONTEXT_CHARS)] | None = None
    origin_url: Annotated[str, Field(min_length=1, max_length=MAX_SOURCE_CONTEXT_CHARS)] | None = None
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
    schema_version: Literal["research-local/1", "research-local/4"] = "research-local/1"  # type: ignore[assignment]
    kind: Literal["activity"] = "activity"
    source_version_ref: Reference
    operation: Literal["extract_utf8", "extract_ocr"] = "extract_utf8"
    implementation: Literal["utf8-paragraphs/1", "baidu-unlimited-ocr/1", "tesseract-cli/1", "poppler-native/1"] = "utf8-paragraphs/1"
    status: Literal["succeeded", "failed"] = "succeeded"

    @model_validator(mode="after")
    def compatible_implementation(self) -> "Activity":
        local_ocr = self.implementation in {"tesseract-cli/1", "poppler-native/1"}
        if local_ocr and (self.schema_version != "research-local/4" or self.operation != "extract_ocr"):
            raise ValueError("Local OCR implementations require a research-local/4 extract_ocr activity")
        if not local_ocr and self.schema_version != "research-local/1":
            raise ValueError("Legacy implementations use research-local/1 activities")
        return self


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
    verbatim: Annotated[str, Field(min_length=1, max_length=MAX_SOURCE_BYTES)]
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
    confidence: ClaimConfidence = "hypothetical"
    scope: ClaimScope = Field(default_factory=ClaimScope)
    dossier_ref: Reference | None = None
    tags: list[Annotated[str, Field(min_length=1, max_length=50)]] = Field(default_factory=list)


class ClaimRelation(AuthoredRecord):
    """An author's causal assertion between exact claim revisions, never proof."""

    schema_version: Literal["research-local/6"] = "research-local/6"  # type: ignore[assignment]
    initial_schema_version: ClassVar[str] = "research-local/6"
    revision_schema_version: ClassVar[str] = "research-local/6"
    kind: Literal["claim_relation"] = "claim_relation"
    from_claim_ref: Reference
    to_claim_ref: Reference
    relation: Literal["causes"] = "causes"
    state: Literal["active", "retracted"] = "active"
    rationale: Annotated[str, Field(min_length=1, max_length=2000)] | None = None

    @model_validator(mode="after")
    def distinct_claims(self) -> "ClaimRelation":
        if self.from_claim_ref.id == self.to_claim_ref.id:
            raise ValueError("A causal relation must connect two distinct claims")
        return self


class ManuscriptAnchor(StrictModel):
    """Reviewed quote in displayed paragraph text; the manuscript is not imported."""

    selector_version: Literal["paragraph-profile-text/1"] = "paragraph-profile-text/1"
    source_path: Annotated[str, Field(min_length=1, max_length=2000)]
    source_sha256: Digest
    paragraph_sha256: Digest
    start_line: Annotated[int, Field(ge=1)]
    end_line: Annotated[int, Field(ge=1)]
    start: Annotated[int, Field(ge=0)]
    end: Annotated[int, Field(gt=0)]
    quote: Annotated[str, Field(min_length=1, max_length=10000)]
    offset_unit: Literal["unicode_codepoint"] = "unicode_codepoint"
    retention_confirmed: Literal[True]

    @field_validator("retention_confirmed", mode="before")
    @classmethod
    def explicit_retention(cls, value: Any) -> Any:
        if value is not True:
            raise ValueError("Retention confirmation must be the boolean true")
        return value

    @model_validator(mode="after")
    def valid_selector(self) -> "ManuscriptAnchor":
        path = PurePosixPath(self.source_path)
        if (not path.parts or path.is_absolute() or ".." in path.parts or "\\" in self.source_path
                or path.as_posix() != self.source_path or any(ord(c) < 32 for c in self.source_path)):
            raise ValueError("Manuscript path must be normalized and project-relative")
        if self.end_line < self.start_line or self.end - self.start != len(self.quote) or not self.quote.strip():
            raise ValueError("Manuscript selector must contain a nonblank exact quote and valid span")
        return self


class ManuscriptClaimLink(AuthoredRecord):
    """An explicit author association, distinct from retained source evidence."""

    schema_version: Literal["research-local/7"] = "research-local/7"  # type: ignore[assignment]
    initial_schema_version: ClassVar[str] = "research-local/7"
    revision_schema_version: ClassVar[str] = "research-local/7"
    kind: Literal["manuscript_claim_link"] = "manuscript_claim_link"
    claim_ref: Reference
    anchor: ManuscriptAnchor
    state: Literal["active", "retracted"] = "active"
    note: Annotated[str, Field(min_length=1, max_length=2000)] | None = None


def normalize_claim_relation(value: str) -> Literal["causes"]:
    """Accept the results_in input alias without introducing another stored type."""
    if isinstance(value, str) and value.strip().lower() in ("causes", "results_in"):
        return "causes"
    raise ValueError("Claim relation must be causes or results_in")


EvidenceRelation = Literal["supports", "contradicts", "qualifies", "contextualizes"]
EVIDENCE_RELATIONS: tuple[EvidenceRelation, ...] = get_args(EvidenceRelation)


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
    dossier_refs: list[Reference] = Field(default_factory=list)


class DecisionAcknowledgement(Record):
    """An author's statement about exact reviewed revisions, never semantic verification."""

    schema_version: Literal["research-local/5"] = "research-local/5"  # type: ignore[assignment]
    kind: Literal["decision_acknowledgement"] = "decision_acknowledgement"
    decision_ref: Reference
    dossier_ref: Reference
    status: Literal["applied", "review_needed"]
    note: Annotated[str, Field(min_length=1, max_length=2000)] | None = None
    supersedes_ref: Reference | None = None


class Tombstone(Record):
    schema_version: Literal["research-local/1", "research-local/2"] = "research-local/1"  # type: ignore[assignment]
    kind: Literal["tombstone"] = "tombstone"
    target_ref: Reference
    source_ref: Reference | None = None
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

    @model_validator(mode="after")
    def valid_source_ownership(self) -> "Tombstone":
        if self.source_ref is not None:
            if self.operation != "purge" or self.target_kind != "source_version" or self.schema_version != "research-local/2":
                raise ValueError("Source ownership requires a version-2 source-version purge tombstone")
        elif self.schema_version != "research-local/1":
            raise ValueError("Version-2 purge tombstones require explicit source ownership")
        return self

    @model_serializer(mode="wrap")
    def serialize_tombstone(self, handler: SerializerFunctionWrapHandler) -> dict[str, Any]:
        fields: dict[str, Any] = handler(self)
        if self.source_ref is None:
            fields.pop("source_ref", None)
        return fields


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
    | ClaimRelation
    | ManuscriptClaimLink
    | EvidenceLink
    | Decision
    | DecisionAcknowledgement,
    Field(discriminator="kind"),
]
ENTITY: TypeAdapter[Entity] = TypeAdapter(Entity)


class Entry(StrictModel):
    kind: Kind
    ref: Reference
    sha256: Digest


class Manifest(StrictModel):
    schema_version: Literal["research-manifest-local/1", "research-manifest-local/2", "research-manifest-local/3", "research-manifest-local/4", "research-manifest-local/5", "research-manifest-local/6", "research-manifest-local/7"] = "research-manifest-local/1"
    project_id: Identifier
    generation: Annotated[int, Field(ge=1)]
    parent: Digest | None
    entries: Annotated[list[Entry], Field(min_length=1, max_length=25000)]


class Head(StrictModel):
    schema_version: Literal["research-head-local/1"] = "research-head-local/1"
    sha256: Digest


def reference(record: Record) -> Reference:
    return Reference(id=record.id, revision=record.revision)
