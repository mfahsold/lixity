"""Minimal project-language NDA drafts; no recipient registry or agreement storage."""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass
from datetime import date as CalendarDate
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import load_project_config
from .nda_templates import NDA_DOCUMENT_LABELS, NDA_TEMPLATES


@dataclass(frozen=True)
class NdaDraft:
    """A local editable draft, not evidence of consent or signature."""

    title: str
    text: str
    language: str

    def pdf(self) -> bytes:
        return _minimal_pdf(self.title, self.text.splitlines())


def _field(name: str, value: Any, *, maximum: int = 500, multiline: bool = False) -> str:
    if not isinstance(value, str):
        raise ValueError(f"NDA {name} must be text")
    clean = value.strip()
    controls = any(
        (ord(char) < 32 or 127 <= ord(char) <= 159)
        and not (multiline and char in "\r\n") for char in clean
    )
    if len(clean) > maximum or controls or (not multiline and any(c in clean for c in "\r\n\u2028\u2029")):
        raise ValueError(f"NDA {name} is too long or contains unsupported line/control characters")
    return clean


def draft_document(
    project_root: str | Path | None = None, *, name: str, address: str = "",
    project_name: str | None = None, date: str | None = None, place: str = "",
    language: str | None = None,
) -> NdaDraft:
    """Render five requested fields without writing files or tracking people."""
    root = Path(project_root).resolve() if project_root is not None else None
    config = load_project_config(root) if root is not None else {}
    settings = config.get("nda")
    if settings is not None and not isinstance(settings, dict):
        raise ValueError("NDA settings must be a table with document language or template options")
    settings = settings or {}
    chosen = settings.get("language", language or config.get("language", "en"))
    if not isinstance(chosen, str) or chosen not in NDA_TEMPLATES:
        raise ValueError("Choose a supported explicit NDA language for automatic/generic analysis")
    recipient = _field("name", name)
    project = _field("project name", project_name if project_name is not None else
                     str(config.get("title") or (root.name if root else "")))
    location = _field("place", place)
    if not recipient or not project or not location:
        raise ValueError("NDA name, project name and place are required")
    date_text = _field("date", date if date is not None else datetime.now(timezone.utc).date().isoformat())
    try:
        if CalendarDate.fromisoformat(date_text).isoformat() != date_text:
            raise ValueError("Noncanonical date")
    except ValueError:
        raise ValueError("NDA date must be a valid YYYY-MM-DD calendar date") from None
    values = {
        "recipient_name": recipient,
        "recipient_address": _field("address", address, maximum=2000, multiline=True),
        "project_title": project,
        "date": date_text,
        "place": location,
    }
    template = settings.get("template")
    if template is None:
        text = NDA_TEMPLATES[chosen]
    else:
        if root is None or not isinstance(template, str) or not template.strip():
            raise ValueError("NDA template must name a project-owned UTF-8 text file")
        path = (root / template).resolve()
        if not path.is_relative_to(root):
            raise ValueError("NDA template must remain inside the project")
        with path.open("rb") as stream:
            raw = stream.read(2 * 1024 * 1024 + 1)
        if len(raw) > 2 * 1024 * 1024:
            raise ValueError("NDA template exceeds 2 MiB")
        text = raw.decode("utf-8")
    if not text.strip() or "\0" in text:
        raise ValueError("NDA template must contain nonempty UTF-8 text without NUL bytes")

    def substitute(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        if key not in values:
            raise ValueError(f"Unknown NDA template field: {key}")
        return values[key]

    return NdaDraft(NDA_DOCUMENT_LABELS[chosen]["title"],
                    re.sub(r"\{\{([^{}]*)\}\}", substitute, text), chosen)


def _pdf_escape(text: str) -> str:
    """Escape a string for use inside a PDF literal string object."""
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


def _minimal_pdf(title: str, lines: list[str]) -> bytes:
    """Build a paginated A4 PDF, preserving supported text without truncation.

    Object offsets and the ``startxref`` value are computed from the assembled
    bytes. A hardcoded cross-reference table silently breaks as soon as the
    content length changes.
    """
    wrapped = [part for line in lines for part in (
        textwrap.wrap(line, width=75, replace_whitespace=False, drop_whitespace=True) or [""]
    )]
    pages = [wrapped[start:start + 44] for start in range(0, len(wrapped), 44)] or [[]]
    # Courier has a fixed 600-unit glyph width: 75 characters at 10.5pt fit
    # the 483pt body width. WinAnsi covers the seven supported Latin locales.
    font_number = 3 + 2 * len(pages)
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (f"<< /Type /Pages /Kids [{' '.join(f'{3 + 2 * n} 0 R' for n in range(len(pages)))}] "
         f"/Count {len(pages)} >>").encode("ascii"),
    ]
    for index, page in enumerate(pages):
        heading = textwrap.wrap(title, width=67) or [""]
        content_ops = ["BT", "/F1 12 Tf", "56 792 Td"]
        for part in heading:
            content_ops += [f"({_pdf_escape(part)}) Tj", "0 -15 Td"]
        content_ops += ["0 -12 Td", "/F1 10.5 Tf"]
        for line in page:
            content_ops += [f"({_pdf_escape(line)}) Tj", "0 -15 Td"]
        content_ops += ["ET", "BT", "/F1 9 Tf", "56 30 Td", f"({index + 1} / {len(pages)}) Tj", "ET"]
        try:
            stream = "\n".join(content_ops).encode("cp1252")
        except UnicodeEncodeError as exc:
            raise ValueError("Native NDA PDF cannot encode this character; download the UTF-8 text instead") from exc
        objects.extend([
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
             f"/Resources << /Font << /F1 {font_number} 0 R >> >> "
             f"/Contents {4 + 2 * index} 0 R >>").encode("ascii"),
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
        ])
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>")

    out = bytearray(b"%PDF-1.4\n% Lixity project document\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode("ascii") + body + b"\nendobj\n"

    xref_at = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    out += b"0000000000 65535 f \n"
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)
