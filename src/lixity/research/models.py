"""Strict contracts for the local source-to-citation pilot, not the entire RFC."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, field_validator, model_validator

Identifier = Annotated[str, Field(pattern=r"^urn:uuid:[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Language = Literal["en", "de", "fr", "es", "it", "pt", "nl", "generic"]
Kind = Literal["project", "source", "source_version", "activity", "extraction", "passage", "tombstone"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class Reference(StrictModel):
    id: Identifier
    revision: Annotated[int, Field(ge=1)] = 1


class Blob(StrictModel):
    sha256: Digest
    byte_length: Annotated[int, Field(ge=0, le=2 * 1024 * 1024)]
    media_type: Literal["text/plain"] = "text/plain"


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


class Project(Record):
    kind: Literal["project"] = "project"
    title: Annotated[str, Field(min_length=1, max_length=500)]
    language: Language = "en"


class Source(Record):
    kind: Literal["source"] = "source"
    title: Annotated[str, Field(min_length=1, max_length=500)]
    language: Language


ContextLabel = Annotated[str, Field(min_length=1, max_length=500)]


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


class SourceVersion(Record):
    kind: Literal["source_version"] = "source_version"
    source_ref: Reference
    sequence: Annotated[int, Field(ge=1)]
    blob: Blob
    retention_confirmed: Literal[True]
    redistribution: Literal["unknown"] = "unknown"
    context: SourceContext = Field(default_factory=SourceContext)


class Activity(Record):
    kind: Literal["activity"] = "activity"
    source_version_ref: Reference
    operation: Literal["extract_utf8"] = "extract_utf8"
    implementation: Literal["utf8-paragraphs/1"] = "utf8-paragraphs/1"
    status: Literal["succeeded"] = "succeeded"


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


class Tombstone(Record):
    kind: Literal["tombstone"] = "tombstone"
    target_ref: Reference
    target_kind: Literal["source", "source_version", "activity", "extraction", "passage"]
    operation: Literal["withdraw", "purge"]
    reason: Annotated[str, Field(min_length=1, max_length=500)]


Entity = Annotated[Project | Source | SourceVersion | Activity | Extraction | Passage | Tombstone,
                   Field(discriminator="kind")]
ENTITY: TypeAdapter[Entity] = TypeAdapter(Entity)


class Entry(StrictModel):
    kind: Kind
    ref: Reference
    sha256: Digest


class Manifest(StrictModel):
    schema_version: Literal["research-manifest-local/1"] = "research-manifest-local/1"
    project_id: Identifier
    generation: Annotated[int, Field(ge=1)]
    parent: Digest | None
    entries: Annotated[list[Entry], Field(min_length=1, max_length=25000)]


class Head(StrictModel):
    schema_version: Literal["research-head-local/1"] = "research-head-local/1"
    sha256: Digest


def reference(record: Record) -> Reference:
    return Reference(id=record.id, revision=record.revision)
