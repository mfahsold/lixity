"""Explicit publication data shared by project settings and PDF composition.

These fields store author-entered data. Validation checks syntax and bounds,
not legal completeness, ownership, ISBN assignment or publication readiness.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator, model_validator

from .workspace_labels import WORKSPACE_LABELS


@dataclass(frozen=True)
class PublicationField:
    key: str
    kind: str
    max_chars: int


PUBLICATION_FIELDS = (
    PublicationField("publisher_name", "text", 500),
    PublicationField("publisher_address", "multiline", 2000),
    PublicationField("printer_name", "text", 500),
    PublicationField("printer_address", "multiline", 2000),
    PublicationField("edition", "text", 200),
    PublicationField("year", "text", 4),
    PublicationField("isbn_print", "text", 32),
    PublicationField("isbn_digital", "text", 32),
    PublicationField("rights_notice", "multiline", 3000),
    PublicationField("credits", "multiline", 3000),
    PublicationField("extra_info", "multiline", 4000),
)
_FIELDS = {field.key: field for field in PUBLICATION_FIELDS}


def validate_metadata_text(value: object, label: str, maximum: int, *, multiline: bool = False) -> str:
    """Validate literal project text without rewriting spelling or inner spaces."""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label} must contain valid Unicode characters") from exc
    if multiline:
        value = value.replace("\r\n", "\n")
    if any((ord(char) < 32 and not (char == "\n" and multiline))
           or 127 <= ord(char) <= 159 or char in "\u2028\u2029" for char in value):
        message = "contains unsupported control characters" if multiline else "must not contain controls or line separators"
        raise ValueError(f"{label} {message}")
    value = value.strip()
    if len(value) > maximum:
        raise ValueError(f"{label} must be at most {maximum} characters")
    return value


def _isbn_digits(value: str) -> str:
    return value.replace("-", "").replace(" ", "").upper()


def _valid_isbn(value: str) -> bool:
    digits = _isbn_digits(value)
    if re.fullmatch(r"[0-9]{9}[0-9X]", digits):
        return sum((10 - index) * (10 if char == "X" else int(char))
                   for index, char in enumerate(digits)) % 11 == 0
    if re.fullmatch(r"97[89][0-9]{10}", digits):
        return sum(int(char) * (1 if index % 2 == 0 else 3)
                   for index, char in enumerate(digits)) % 10 == 0
    return False


def _canonical_isbn(value: str) -> str:
    """Compare the ISBN-13 identity, including equivalent old ISBN-10 forms."""
    digits = _isbn_digits(value)
    if len(digits) == 10:
        prefix = "978" + digits[:9]
        check = -sum(int(char) * (1 if index % 2 == 0 else 3)
                     for index, char in enumerate(prefix)) % 10
        return prefix + str(check)
    return digits


class PublicationSettings(BaseModel):
    """One bounded, optional imprint configuration for an explicit project.

    Text must be valid Unicode without unsupported control characters or line
    separators. Strings are stripped before length checks; multiline fields
    allow newlines and normalize CRLF to LF. Nonempty years require four digits
    from 0001 to 9999. Nonempty ISBNs require valid ISBN-10/ISBN-13 checksums;
    print and digital identifiers must differ even when ISBN-10 and ISBN-13
    spellings refer to the same edition. These custom checks are not all
    encoded in JSON Schema. Validation does not establish legal completeness,
    ownership, ISBN assignment or publication readiness.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    enabled: bool = False
    publisher_name: str = ""
    publisher_address: str = ""
    printer_name: str = ""
    printer_address: str = ""
    edition: str = ""
    year: str = ""
    isbn_print: str = ""
    isbn_digital: str = ""
    rights_notice: str = ""
    credits: str = ""
    extra_info: str = ""

    @field_validator(*_FIELDS, mode="before")
    @classmethod
    def bounded_text(cls, value: object, info: ValidationInfo) -> str:
        field = _FIELDS[str(info.field_name)]
        value = validate_metadata_text(value, field.key, field.max_chars, multiline=field.kind == "multiline")
        if field.key == "year" and value and (not re.fullmatch(r"[0-9]{4}", value) or value == "0000"):
            raise ValueError("Publication year must be a four-digit year from 0001 to 9999")
        if field.key.startswith("isbn_") and value and not _valid_isbn(value):
            raise ValueError(f"{field.key} must be a valid ISBN-10 or ISBN-13")
        return value

    @model_validator(mode="after")
    def distinct_format_identifiers(self) -> PublicationSettings:
        if self.isbn_print and self.isbn_digital and _canonical_isbn(self.isbn_print) == _canonical_isbn(self.isbn_digital):
            raise ValueError("Print and digital editions require distinct ISBNs")
        return self


def publication_configuration_schema() -> dict[str, Any]:
    """Describe model defaults and the text policy used by its validators."""
    schema = PublicationSettings.model_json_schema()
    for key, field in _FIELDS.items():
        schema["properties"][key]["x-lixity-text"] = {
            "kind": field.kind, "max_chars": field.max_chars, "length_after": "strip",
        }
    schema["$comment"] = (
        "x-lixity-text describes component validation, not JSON Schema keywords. "
        "Text bounds apply after stripping whitespace; multiline text also normalizes CRLF. "
        "Use PublicationSettings for full input validation."
    )
    return schema


def load_publication(settings: Mapping[str, Any]) -> PublicationSettings:
    """Validate supplied project data; never discover or inherit another root."""
    return PublicationSettings.model_validate(settings.get("publication", {}))


def publication_imprint(
    settings: PublicationSettings, labels: Mapping[str, str],
) -> tuple[str, list[str]] | None:
    """Return only entered imprint paragraphs, without inferred legal claims."""
    if not settings.enabled:
        return None

    def translated(key: str) -> str:
        return labels.get(key, WORKSPACE_LABELS["en"].get(key, key))

    paragraphs = []
    for role in ("publisher", "printer"):
        name, address = getattr(settings, role + "_name"), getattr(settings, role + "_address")
        lines = ([translated("publication_" + role + "_name") + ": " + name] if name else [])
        if address:
            lines.append(address)
        if lines:
            paragraphs.append("\n".join(lines))
    for key in ("edition", "year", "isbn_print", "isbn_digital"):
        value = getattr(settings, key)
        if value:
            paragraphs.append(translated("publication_" + key) + ": " + value)
    if settings.rights_notice:
        paragraphs.append(settings.rights_notice)
    if settings.credits:
        paragraphs.append(translated("publication_credits") + ":\n" + settings.credits)
    if settings.extra_info:
        paragraphs.append(settings.extra_info)
    return (translated("publication_imprint_title"), paragraphs) if paragraphs else None
