"""Composed PDF documents with embedded TrueType subsets.

Every page is placed explicitly, so the writer depends on no browser, no
external converter and no document model. Text is addressed through glyph ids
and Identity-H encoding: that is what makes arbitrary Unicode scripts work with
a font subset instead of the fixed WinAnsi repertoire the older draft renderer
is limited to.

Line breaking measures real advance widths from the embedded font, so a measure
is filled with actual glyph metrics rather than an average-character guess.
"""

from __future__ import annotations

import zlib
from dataclasses import dataclass, field

from .pdf_font import EmbeddedFont, FontError, subset_font

A4 = (595.276, 841.890)
A5 = (419.528, 595.276)

LEFT = "left"
CENTRE = "centre"
JUSTIFIED = "justified"


class PdfError(Exception):
    """Raised when a document cannot be composed or rendered."""


@dataclass(frozen=True)
class Line:
    """One placed line. ``y`` is the baseline in PDF user space."""

    text: str
    x: float
    y: float
    size: float
    role: str
    word_spacing: float = 0.0


@dataclass
class Page:
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)


def text_width(text: str, face: EmbeddedFont, size: float) -> float:
    return sum(face.advance(ord(character)) / 1000 * size for character in text)


def break_lines(text: str, face: EmbeddedFont, size: float, measure: float) -> list[str]:
    """Split text into lines that fit ``measure``; explicit newlines always break."""
    result: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph:
            result.append("")
            continue
        current = ""
        for word in paragraph.split(" "):
            candidate = f"{current} {word}" if current else word
            if not current or text_width(candidate, face, size) <= measure:
                current = candidate
            else:
                result.append(current)
                current = word
            while text_width(current, face, size) > measure and len(current) > 1:
                cut = len(current) - 1
                while cut > 1 and text_width(current[:cut], face, size) > measure:
                    cut -= 1
                result.append(current[:cut])
                current = current[cut:]
        result.append(current)
    return result


def _subset_or_fail(path: str, codepoints: set[int]) -> EmbeddedFont:
    try:
        return subset_font(path, codepoints)
    except FontError as error:
        raise PdfError(str(error)) from error


class FontSet:
    """Named faces subset once per document, after every character is known."""

    def __init__(self, paths: dict[str, str]) -> None:
        missing = [role for role, path in paths.items() if not path]
        if missing:
            raise PdfError(f"Missing font file for: {', '.join(sorted(missing))}")
        self.paths = dict(paths)
        self._codepoints: set[int] = set()
        self._faces: dict[str, EmbeddedFont] = {}

    def collect(self, role: str, text: str) -> None:
        if role not in self.paths:
            raise PdfError(f"No font configured for the {role} role")
        before = len(self._codepoints)
        self._codepoints.update(ord(character) for character in text)
        if self._faces and len(self._codepoints) != before:
            # Faces are built once from the collected characters. Text seen after
            # a build must widen the subset, otherwise its glyphs are missing.
            self._faces = {}

    def build(self) -> dict[str, EmbeddedFont]:
        if self._faces:
            return self._faces
        if not self._codepoints:
            raise PdfError("The document contains no text to render")
        for role, path in self.paths.items():
            self._faces[role] = _subset_or_fail(path, self._codepoints)
        return self._faces

    def face(self, role: str) -> EmbeddedFont:
        return self.build()[role]

    def unmapped(self, role: str, text: str) -> set[str]:
        """Return visible characters the face cannot draw, for an honest error."""
        face = self.face(role)
        return {
            character
            for character in text
            if character not in "\n\r\t"
            and not character.isspace()
            and not face.has(ord(character))
        }


@dataclass
class Block:
    """A request to place text; the document decides where it lands."""

    text: str
    role: str = "text"
    size: float = 11.0
    leading: float = 1.35
    align: str = LEFT
    indent: float = 0.0
    space_before: float = 0.0
    space_after: float = 0.0
    new_page: bool = False


class Document:
    """A paginated text document rendered into one self-contained PDF file."""

    def __init__(
        self,
        fonts: FontSet,
        *,
        page_size: tuple[float, float] = A4,
        margins: tuple[float, float, float, float] = (56.0, 56.0, 56.0, 64.0),
    ) -> None:
        self.fonts = fonts
        self.width, self.height = page_size
        self.left, self.right, self.top, self.bottom = margins
        self.blocks: list[Block] = []
        self.furniture: dict[str, list[Line]] = {}
        self._measure = self.width - self.left - self.right

    @property
    def measure(self) -> float:
        return self._measure

    def add(self, block: Block) -> None:
        self.fonts.collect(block.role, block.text)
        self.blocks.append(block)

    def page_furniture(self, text: str, *, role: str, size: float, position: str) -> None:
        """Register running heads or folios drawn on every rendered page."""
        self.fonts.collect(role, text)
        self.furniture[position] = [
            *self.furniture.get(position, []),
            Line(text, 0.0, 0.0, size, role),
        ]

    def _compose(self) -> list[Page]:
        faces = self.fonts.build()
        pages: list[Page] = []
        page = Page(self.width, self.height)
        cursor = self.height - self.top

        def new_page() -> None:
            nonlocal page, cursor
            pages.append(page)
            page = Page(self.width, self.height)
            cursor = self.height - self.top

        for block in self.blocks:
            if block.new_page and page.lines:
                new_page()
            if block.space_before and cursor < self.height - self.top:
                cursor -= block.space_before
            face = faces[block.role]
            step = block.size * block.leading
            for piece in break_lines(block.text, face, block.size, self._measure - block.indent):
                if cursor - step < self.bottom - 1e-6:
                    new_page()
                baseline = cursor - block.size
                line = Line(piece, self.left + block.indent, baseline, block.size, block.role)
                if block.align == JUSTIFIED and piece:
                    line = self._justify(line, face, block.size)
                elif block.align == CENTRE and piece:
                    line = Line(
                        piece,
                        self.left + (self._measure - text_width(piece, face, block.size)) / 2,
                        baseline,
                        block.size,
                        block.role,
                    )
                page.lines.append(line)
                cursor -= step
            cursor -= block.space_after
        pages.append(page)
        return [self._decorate(page, index, len(pages)) for index, page in enumerate(pages)]

    def _justify(self, line: Line, face: EmbeddedFont, size: float) -> Line:
        """Spread the slack over the spaces so the line reaches the right margin."""
        spaces = line.text.count(" ")
        if not spaces:
            return line
        slack = self.left + self._measure - (line.x + text_width(line.text, face, size))
        if slack <= 0:
            return line
        return Line(line.text, line.x, line.y, line.size, line.role, word_spacing=slack / spaces)

    def _decorate(self, page: Page, index: int, total: int) -> Page:
        for position, entries in self.furniture.items():
            for entry in entries:
                face = self.fonts.face(entry.role)
                if position == "footer-centre":
                    y = self.bottom / 2
                    x = self.left + (self._measure - text_width(entry.text, face, entry.size)) / 2
                elif position == "footer-right":
                    y = self.bottom / 2
                    x = self.left + self._measure - text_width(entry.text, face, entry.size)
                else:
                    y = self.height - self.top / 2
                    x = self.left
                page.lines.append(Line(entry.text, x, y, entry.size, entry.role))
        return page

    def render(self) -> bytes:
        return _write_pdf(self._compose(), self.fonts.build())


def _to_unicode_cmap(face: EmbeddedFont) -> str:
    """Map each embedded glyph id back to the character it stands for."""
    entries = sorted((glyph, codepoint) for codepoint, glyph in face.glyph_ids.items() if glyph)
    chunks = [
        "/CIDInit /ProcSet findresource begin",
        "12 dict begin",
        "begincmap",
        "/CIDSystemInfo << /Registry (Adobe) /Ordering (UCS) /Supplement 0 >> def",
        "/CMapName /Adobe-Identity-UCS def",
        "/CMapType 2 def",
        "1 begincodespacerange",
        "<0000> <FFFF>",
        "endcodespacerange",
    ]
    for start in range(0, len(entries), 100):
        block = entries[start : start + 100]
        chunks.append(f"{len(block)} beginbfchar")
        for glyph, codepoint in block:
            target = "".join(f"{unit:04X}" for unit in _utf16_units(codepoint))
            chunks.append(f"<{glyph:04X}> <{target}>")
        chunks.append("endbfchar")
    chunks += ["endcmap", "CMapName currentdict /CMap defineresource pop", "end", "end"]
    return "\n".join(chunks)


def _utf16_units(codepoint: int) -> list[int]:
    if codepoint <= 0xFFFF:
        return [codepoint]
    offset = codepoint - 0x10000
    return [0xD800 + (offset >> 10), 0xDC00 + (offset & 0x3FF)]


def _escape_name(text: str) -> str:
    return "".join(
        character if 33 <= ord(character) <= 126 and character not in "()<>[]{}/%" else "#"
        for character in text
    )


def _hex_glyphs(text: str, face: EmbeddedFont) -> str:
    return "".join(f"{face.glyph_ids.get(ord(character), 0):04X}" for character in text)


def _write_pdf(pages: list[Page], faces: dict[str, EmbeddedFont]) -> bytes:
    roles = sorted({line.role for page in pages for line in page.lines})
    objects: dict[int, bytes] = {}

    def add(body: bytes) -> int:
        objects[len(objects) + 1] = body
        return len(objects)

    def stream(body: bytes, extra: bytes = b"", *, flate: bool = False) -> bytes:
        # A compressed stream must declare its filter: without /Filter /FlateDecode
        # the reader hands the still-compressed bytes to the font loader and the
        # embedded font is rejected as invalid.
        filter_entry = b" /Filter /FlateDecode" if flate else b""
        return (
            b"<< /Length "
            + str(len(body)).encode("ascii")
            + extra
            + filter_entry
            + b" >>\nstream\n"
            + body
            + b"\nendstream"
        )

    catalog, pages_obj = add(b""), add(b"")
    resources: dict[str, int] = {}
    for role in roles:
        face = faces[role]
        scale = 1000 / face.metrics.units_per_em
        font_file = add(
            stream(
                zlib.compress(face.data, 9),
                b" /Length1 " + str(len(face.data)).encode("ascii"),
                flate=True,
            )
        )
        bbox = " ".join(str(round(value * scale, 2)) for value in face.metrics.bbox)
        descriptor = add(
            (
                f"<< /Type /FontDescriptor /FontName /{_escape_name(role)} /Flags {face.metrics.flags} "
                f"/FontBBox [{bbox}] /ItalicAngle {face.metrics.italic_angle:.1f} "
                f"/Ascent {round(face.metrics.ascent * scale, 2)} "
                f"/Descent {round(face.metrics.descent * scale, 2)} "
                f"/CapHeight {round(face.metrics.cap_height * scale, 2)} "
                f"/StemV {face.metrics.stem_v} /FontFile2 {font_file} 0 R >>"
            ).encode("ascii")
        )
        widths = " ".join(
            f"{face.glyph_ids[codepoint]} [{round(face.advances.get(codepoint, 0) * scale)}]"
            for codepoint in sorted(face.glyph_ids)
        )
        descendant = add(
            (
                f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{_escape_name(role)} "
                f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                f"/FontDescriptor {descriptor} 0 R /DW 1000 /W [{widths}] "
                f"/CIDToGIDMap /Identity >>"
            ).encode("ascii")
        )
        # Without /ToUnicode a reader has no way back from a glyph id to the
        # character, so the exported text is neither searchable nor copyable.
        to_unicode = add(stream(_to_unicode_cmap(face).encode("ascii")))
        resources[role] = add(
            (
                f"<< /Type /Font /Subtype /Type0 /BaseFont /{_escape_name(role)} "
                f"/Encoding /Identity-H /DescendantFonts [{descendant} 0 R] "
                f"/ToUnicode {to_unicode} 0 R >>"
            ).encode("ascii")
        )

    page_objects: list[int] = []
    for page in pages:
        parts: list[str] = []
        for line in page.lines:
            parts += [
                "BT",
                f"/F{roles.index(line.role) + 1} {line.size:.2f} Tf",
                f"1 0 0 1 {line.x:.2f} {line.y:.2f} Tm",
            ]
            if line.word_spacing:
                parts.append(f"{line.word_spacing:.4f} Tw")
            parts.append(f"<{_hex_glyphs(line.text, faces[line.role])}> Tj")
            parts.append("ET")
        content_object = add(stream("\n".join(parts).encode("ascii")))
        fonts = " ".join(f"/F{index + 1} {resources[role]} 0 R" for index, role in enumerate(roles))
        page_objects.append(
            add(
                (
                    f"<< /Type /Page /Parent {pages_obj} 0 R /MediaBox [0 0 "
                    f"{page.width:.3f} {page.height:.3f}] /Resources << /Font << {fonts} >> >> "
                    f"/Contents {content_object} 0 R >>"
                ).encode("ascii")
            )
        )

    objects[catalog] = f"<< /Type /Catalog /Pages {pages_obj} 0 R >>".encode("ascii")
    objects[pages_obj] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{n} 0 R' for n in page_objects)}] "
        f"/Count {len(page_objects)} >>"
    ).encode("ascii")

    out = bytearray(b"%PDF-1.4\n% Lixity composed document\n")
    offsets: dict[int, int] = {}
    for number in sorted(objects):
        offsets[number] = len(out)
        out += f"{number} 0 obj\n".encode("ascii") + objects[number] + b"\nendobj\n"
    xref_at = len(out)
    size = max(objects) + 1
    out += f"xref\n0 {size}\n".encode("ascii") + b"0000000000 65535 f \n"
    for number in range(1, size):
        out += f"{offsets[number]:010d} 00000 n \n".encode("ascii")
    out += (
        f"trailer\n<< /Size {size} /Root {catalog} 0 R >>\nstartxref\n{xref_at}\n%%EOF\n"
    ).encode("ascii")
    return bytes(out)


__all__ = [
    "A4",
    "A5",
    "CENTRE",
    "JUSTIFIED",
    "LEFT",
    "Block",
    "Document",
    "FontSet",
    "Line",
    "Page",
    "PdfError",
    "break_lines",
    "text_width",
]
