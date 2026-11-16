"""Non-destructive manuscript importer and converter for Word (.docx) documents.

Converts Word (.docx) documents into clean, structurally valid Markdown manuscripts
suitable for Lixity analysis and research workflows. Emits an explicit preview and
loss report detailing any non-text or unsupported elements (such as embedded drawings,
complex tables, or track changes). Original source files are never modified or replaced.
"""

from __future__ import annotations

import hashlib
import io
import os
import re
import stat
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .io import FileUtils

SCHEMA_VERSION = "manuscript-import-preview-local/1"

# Independent ceilings bound source reads, ZIP inventory, decompression and output.
# Highly compressible prose remains valid; no compression-ratio heuristic is used.
MAX_DOCX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_DOCX_MEMBERS = 4096
MAX_DOCX_XML_BYTES = 32 * 1024 * 1024
MAX_DOCX_OUTPUT_BYTES = 16 * 1024 * 1024

_W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_NS = {"w": _W_NS}
_VAL_ATTR = f"{{{_W_NS}}}val"

_HEADING_STYLES: dict[str, int] = {
    "title": 1,
    "heading1": 1,
    "heading 1": 1,
    "überschrift 1": 1,
    "ueberschrift 1": 1,
    "heading2": 2,
    "heading 2": 2,
    "überschrift 2": 2,
    "ueberschrift 2": 2,
    "subtitle": 2,
    "heading3": 3,
    "heading 3": 3,
    "überschrift 3": 3,
    "ueberschrift 3": 3,
    "heading4": 4,
    "heading 4": 4,
    "heading5": 5,
    "heading 5": 5,
    "heading6": 6,
    "heading 6": 6,
}

_SCENE_BREAK_PATTERNS = re.compile(r"^\s*(?:\*\s*\*\s*\*|-{3,}|_{3,}|#\s*#\s*#|⁂)\s*$")


@dataclass(frozen=True)
class ImportHeading:
    """Detected chapter or section heading in the converted document."""

    level: int
    text: str
    line: int


@dataclass(frozen=True)
class ImportLossItem:
    """A skipped, simplified or converted non-prose element from the source."""

    element: str
    location: str
    detail: str


@dataclass
class ImportPreview:
    """Structured result of inspecting and converting a manuscript document."""

    source_filename: str
    source_format: str
    source_sha256: str
    markdown: str
    headings: list[ImportHeading] = field(default_factory=list)
    paragraph_count: int = 0
    word_count: int = 0
    loss_report: list[ImportLossItem] = field(default_factory=list)
    schema_version: str = SCHEMA_VERSION

    def to_dict(self) -> dict[str, Any]:
        """Return JSON-serializable dictionary."""
        return {
            "schema_version": self.schema_version,
            "source_filename": self.source_filename,
            "source_format": self.source_format,
            "source_sha256": self.source_sha256,
            "markdown": self.markdown,
            "headings": [asdict(h) for h in self.headings],
            "paragraph_count": self.paragraph_count,
            "word_count": self.word_count,
            "loss_report": [asdict(item) for item in self.loss_report],
        }


def _is_truthy_val(element: ET.Element | None) -> bool:
    if element is None:
        return False
    val = element.get(_VAL_ATTR)
    if val is None:
        return True
    return val.lower() not in ("0", "false", "none", "off")


def _extract_run_markdown(run: ET.Element) -> str:
    """Extract text from a <w:r> element with inline Markdown formatting."""
    t_el = run.find("w:t", _NS)
    if t_el is None or not t_el.text:
        # Check for break elements
        if run.find("w:br", _NS) is not None:
            return "\n"
        return ""

    raw_text = t_el.text
    r_pr = run.find("w:rPr", _NS)
    if r_pr is None:
        return raw_text

    is_bold = _is_truthy_val(r_pr.find("w:b", _NS))
    is_italic = _is_truthy_val(r_pr.find("w:i", _NS))
    is_strike = _is_truthy_val(r_pr.find("w:strike", _NS))

    # Strip whitespace for delimiter wrapping, preserving leading/trailing spaces
    leading_space = " " if raw_text.startswith(" ") else ""
    trailing_space = " " if raw_text.endswith(" ") and len(raw_text) > 1 else ""
    core_text = raw_text.strip()
    if not core_text:
        return raw_text

    formatted = core_text
    if is_bold and is_italic:
        formatted = f"***{formatted}***"
    elif is_bold:
        formatted = f"**{formatted}**"
    elif is_italic:
        formatted = f"*{formatted}*"
    if is_strike:
        formatted = f"~~{formatted}~~"

    return f"{leading_space}{formatted}{trailing_space}"


def preview_docx(
    source: str | Path | bytes,
    *,
    filename: str = "manuscript.docx",
) -> ImportPreview:
    """Inspect and convert a Word (.docx) document into Markdown with a loss report.

    Args:
        source: File path (str/Path) or raw byte content of a valid .docx file.
        filename: Optional display name for the document when passing bytes.

    Returns:
        An ImportPreview containing the generated Markdown, detected chapter headings,
        structural metrics, and any warnings for unsupported/omitted elements.

    Raises:
        ValueError: Input is not a regular file/valid DOCX, or exceeds the
            32 MiB source, 4096 ZIP entries, 32 MiB document XML or 16 MiB
            converted UTF-8 output safety ceilings.
    """
    if isinstance(source, (str, Path)):
        source_path = Path(source)
        filename = source_path.name
        expected = source_path.stat()
        if not stat.S_ISREG(expected.st_mode):
            raise ValueError("Word document source must be a regular file")
        opened = os.open(
            source_path, os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_BINARY", 0),
        )
        descriptor: int | None = opened
        try:
            actual = os.fstat(opened)
            if (not stat.S_ISREG(actual.st_mode)
                    or (actual.st_dev, actual.st_ino) != (expected.st_dev, expected.st_ino)):
                raise ValueError("Word document source changed or is not a regular file")
            if actual.st_size > MAX_DOCX_SOURCE_BYTES:
                raise ValueError("Word document source exceeds byte safety ceiling")
            stream = os.fdopen(opened, "rb")
            descriptor = None
            with stream:
                source_bytes = stream.read(MAX_DOCX_SOURCE_BYTES + 1)
        finally:
            if descriptor is not None:
                os.close(descriptor)
    else:
        source_bytes = source

    if len(source_bytes) > MAX_DOCX_SOURCE_BYTES:
        raise ValueError("Word document source exceeds byte safety ceiling")

    source_hash = hashlib.sha256(source_bytes).hexdigest()

    try:
        with zipfile.ZipFile(io.BytesIO(source_bytes)) as zf:
            if len(zf.infolist()) > MAX_DOCX_MEMBERS:
                raise ValueError("Word document ZIP member count exceeds safety ceiling")
            if "word/document.xml" not in zf.namelist():
                raise ValueError("Document does not contain 'word/document.xml'; not a valid .docx file")
            # Bound actual decompressed bytes, independently of ZIP size metadata.
            with zf.open("word/document.xml") as xml_stream:
                document_xml = xml_stream.read(MAX_DOCX_XML_BYTES + 1)
            if len(document_xml) > MAX_DOCX_XML_BYTES:
                raise ValueError("Word document XML exceeds byte safety ceiling")
    except (zipfile.BadZipFile, OSError) as exc:
        raise ValueError(f"Invalid or corrupted Word document (.docx): {exc}") from exc
    try:
        root = ET.fromstring(document_xml)  # noqa: S314
    except ET.ParseError as exc:
        raise ValueError(f"Malformed XML in 'word/document.xml': {exc}") from exc

    body = root.find("w:body", _NS)
    if body is None:
        return ImportPreview(
            source_filename=filename,
            source_format="docx",
            source_sha256=source_hash,
            markdown="",
        )

    paragraphs_out: list[str] = []
    headings: list[ImportHeading] = []
    loss_report: list[ImportLossItem] = []
    line_number = 1
    total_words = 0
    p_index = 0
    output_bytes = 0

    for child in body:
        tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag

        if tag == "tbl":
            # Table element
            loss_report.append(
                ImportLossItem(
                    element="table",
                    location=f"Block {p_index + 1}",
                    detail="Table structure omitted from narrative manuscript text.",
                )
            )
            continue

        if tag != "p":
            continue

        p_index += 1
        p_el = child

        # Check for non-prose elements inside paragraph
        if p_el.find(".//w:drawing", _NS) is not None or p_el.find(".//w:pict", _NS) is not None:
            loss_report.append(
                ImportLossItem(
                    element="drawing",
                    location=f"Paragraph {p_index}",
                    detail="Embedded drawing or image omitted; images can be attached to research dossiers.",
                )
            )

        if p_el.find(".//w:footnoteReference", _NS) is not None:
            loss_report.append(
                ImportLossItem(
                    element="footnote",
                    location=f"Paragraph {p_index}",
                    detail="Footnote reference omitted from primary manuscript text.",
                )
            )

        # Determine paragraph style (heading / quote / normal)
        style_val = ""
        p_pr = p_el.find("w:pPr", _NS)
        if p_pr is not None:
            p_style = p_pr.find("w:pStyle", _NS)
            if p_style is not None:
                style_val = p_style.get(_VAL_ATTR, "").strip().lower()

        # Assemble run text
        run_texts = [_extract_run_markdown(r_el) for r_el in p_el.findall("w:r", _NS)]

        paragraph_text = "".join(run_texts).strip()
        if not paragraph_text:
            continue

        # Count words (simple whitespace split)
        words = len(paragraph_text.split())
        total_words += words

        # Determine if this is a heading
        heading_level = _HEADING_STYLES.get(style_val, 0)
        if heading_level > 0:
            prefix = "#" * heading_level + " "
            clean_heading = re.sub(r"^[#\s]+", "", paragraph_text)
            md_line = f"{prefix}{clean_heading}"
            headings.append(
                ImportHeading(
                    level=heading_level,
                    text=clean_heading,
                    line=line_number,
                )
            )
        elif _SCENE_BREAK_PATTERNS.match(paragraph_text):
            md_line = "* * *"
        elif style_val in ("quote", "blockquote", "zitat"):
            md_line = f"> {paragraph_text}"
        else:
            md_line = paragraph_text

        # Account for UTF-8 and paragraph separators before retaining output.
        output_bytes += len(md_line.encode("utf-8")) + (2 if paragraphs_out else 1)
        if output_bytes > MAX_DOCX_OUTPUT_BYTES:
            raise ValueError("Word document converted output exceeds byte safety ceiling")
        paragraphs_out.append(md_line)
        # 1 line for content + 1 blank line
        line_number += 2

    final_markdown = "\n\n".join(paragraphs_out) + ("\n" if paragraphs_out else "")

    return ImportPreview(
        source_filename=filename,
        source_format="docx",
        source_sha256=source_hash,
        markdown=final_markdown,
        headings=headings,
        paragraph_count=len(paragraphs_out),
        word_count=total_words,
        loss_report=loss_report,
    )


def convert_docx(
    source_path: str | Path,
    output_path: str | Path | None = None,
    *,
    overwrite: bool = False,
) -> ImportPreview:
    """Convert a Word document to a clean Markdown manuscript file.

    Args:
        source_path: Path to the input .docx file.
        output_path: Optional destination path for the .md file (defaults to same stem).
        overwrite: When False (default), prevents overwriting existing files.

    Returns:
        The ImportPreview describing the conversion.
    """
    src = Path(source_path).expanduser().resolve()
    if not src.is_file():
        raise FileNotFoundError(f"Source file not found: {src}")

    if output_path is None:
        out = src.with_suffix(".md")
    else:
        out = Path(output_path).expanduser().resolve()

    def check_output() -> None:
        FileUtils.require_distinct_output(str(src), str(out))
        if out.exists() and not overwrite:
            raise FileExistsError(
                f"Destination file already exists: {out}. Use overwrite=True or choose a different name."
            )

    check_output()
    preview = preview_docx(src)
    check_output()
    FileUtils.atomic_write_if_changed(str(out), preview.markdown, before_replace=check_output)
    return preview
