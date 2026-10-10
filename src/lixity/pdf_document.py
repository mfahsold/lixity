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
GRID = "grid"


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


@dataclass(frozen=True)
class FittedLine:
    """One composed line: its text and the slack the margin has to absorb."""

    text: str
    slack: float


def fit_paragraph(text: str, face: EmbeddedFont, size: float, measure: float) -> list[FittedLine]:
    """Break a paragraph into lines, minimising the total badness of the page.

    A greedy first-fit break fills each line to the brim and is the reason a
    justified page without hyphenation develops rivers and loose lines: it
    optimises the present line at the expense of the next one. This is Knuth's
    approach reduced to its essentials - for every pair of break points the
    adjustment ratio is scored, and the cheapest chain through them wins.
    """
    lines: list[FittedLine] = []
    for paragraph in text.split("\n"):
        words = paragraph.split(" ")
        if not any(words):
            lines.append(FittedLine("", 0.0))
            continue
        widths = [text_width(word, face, size) for word in words]
        space = text_width(" ", face, size)
        count = len(words)
        best = [float("inf")] * (count + 1)
        best[0] = 0.0
        choice: list[int] = [0] * (count + 1)
        for start in range(count):
            if best[start] == float("inf"):
                continue
            natural = 0.0
            spaces = 0
            for stop in range(start, count):
                natural += widths[stop] + (space if stop > start else 0.0)
                spaces = stop - start
                slack = measure - natural
                final = stop + 1 == count
                # The last line of a paragraph may end anywhere, so it is scored
                # on nothing. Charging it for leftover space is what made a
                # two-word heading break into two lines.
                if final:
                    cost = 0.0
                elif natural < measure * 0.5:
                    # A line less than half full reads as a break, not as text.
                    # Adding the next word is the only way to improve it, and
                    # the paragraph's last line is exempt above.
                    continue
                else:
                    ratio = slack / (space * spaces) if spaces and space else 0.0
                    # A line may tighten by at most a third of an em per word
                    # gap. Past that it only gets worse, so the search stops.
                    if ratio < -0.34:
                        if stop > start:
                            break
                        continue
                    # A line that is merely too loose is expensive, not
                    # forbidden: adding the next word may close it up. Ending
                    # the search here is what left one word on every line.
                    if ratio > 1.0:
                        cost = (abs(ratio) ** 3) * 100.0 + 5000.0
                    else:
                        cost = (abs(ratio) ** 3) * 100.0 + (slack ** 2) / 40.0 + 8.0
                if best[start] + cost < best[stop + 1]:
                    best[stop + 1] = best[start] + cost
                    choice[stop + 1] = start
        if best[count] == float("inf"):
            # No acceptable chain: fall back to the greedy break rather than
            # emitting nothing, so the text is never silently dropped.
            lines.extend(_greedy(words, widths, space, size, measure))
            continue
        breaks: list[tuple[int, int]] = []
        position = count
        while position > 0:
            start = choice[position]
            breaks.append((start, position))
            position = start
        breaks.reverse()
        for start, stop in breaks:
            natural = sum(widths[start:stop]) + space * max(0, stop - start - 1)
            lines.append(FittedLine(" ".join(words[start:stop]), measure - natural))
    return lines


def _greedy(
    words: list[str], widths: list[float], space: float, size: float, measure: float
) -> list[FittedLine]:
    lines: list[FittedLine] = []
    current: list[int] = []
    natural = 0.0
    for index, width in enumerate(widths):
        candidate = natural + width + (space if current else 0.0)
        if current and candidate > measure:
            lines.append(FittedLine(" ".join(words[i] for i in current), measure - natural))
            current, natural = [index], width
        else:
            current.append(index)
            natural = candidate
    if current:
        lines.append(FittedLine(" ".join(words[i] for i in current), measure - natural))
    return lines


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
        mirror: bool = False,
        baseline: float | None = None,
    ) -> None:
        self.fonts = fonts
        self.width, self.height = page_size
        self.left, self.right, self.top, self.bottom = margins
        # Mirrored margins are what a bound spread needs: the inside edge sits
        # on opposite sides of facing pages, so without this every second page
        # sits visibly off centre when the file is printed double-sided.
        self.mirror = mirror
        self.baseline = baseline
        self.blocks: list[Block] = []
        self.furniture: dict[str, list[Line]] = {}
        self.omit_first: set[str] = set()

    @property
    def measure(self) -> float:
        return self.width - self.left - self.right

    def _snap(self, cursor: float) -> float:
        """Round a baseline onto the baseline grid, when one is set."""
        if not self.baseline:
            return cursor
        return round(cursor / self.baseline) * self.baseline

    def add(self, block: Block) -> None:
        self.fonts.collect(block.role, block.text)
        self.blocks.append(block)

    def page_furniture(self, text: str, *, role: str, size: float, position: str,
                       omit_first: bool = False) -> None:
        """Register running heads or folios drawn on the rendered pages.

        ``{folio}`` in the text becomes the page number. A title page carries no
        folio in a printed book, so ``omit_first`` leaves the first page bare.
        """
        self.fonts.collect(role, text)
        self.furniture[position] = [
            *self.furniture.get(position, []),
            Line(text, 0.0, 0.0, size, role),
        ]
        if omit_first:
            self.omit_first.add(position)

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
                cursor -= self._snap(block.space_before)
            face = faces[block.role]
            step = block.size * block.leading
            # A submission sheet is a fixed character grid, not prose: it is
            # broken at the measure and never spaced out, because the column
            # count is the contract rather than a typographic preference.
            if block.align == GRID:
                pieces = [FittedLine(piece, 0.0) for piece in break_lines(
                    block.text, face, block.size, self.measure - block.indent)]
            else:
                pieces = fit_paragraph(
                    block.text, face, block.size, self.measure - block.indent
                )
            origin = self._origin(len(pages))
            for index, piece in enumerate(pieces):
                if cursor - step < self.bottom - 1e-6:
                    new_page()
                    origin = self._origin(len(pages))
                # Baselines sit on the grid, and the left edge follows the page
                # number once mirrored margins are on.
                baseline = self._snap(cursor - block.size)
                line = Line(piece.text, origin + block.indent, baseline, block.size,
                            block.role)
                # The last line of a paragraph is not justified: stretching it
                # to the margin is the classic give-away of amateur typesetting.
                if block.align == JUSTIFIED and piece.text and index < len(pieces) - 1:
                    line = self._justify(line, face, block.size, piece.slack)
                elif block.align == CENTRE and piece.text:
                    line = Line(
                        piece.text,
                        origin
                        + (self.measure - text_width(piece.text, face, block.size)) / 2,
                        baseline,
                        block.size,
                        block.role,
                    )
                page.lines.append(line)
                cursor -= step
            cursor -= self._snap(block.space_after)
        pages.append(page)
        return [self._decorate(page, index, len(pages)) for index, page in enumerate(pages)]

    def _origin(self, page_number: int) -> float:
        """Return the left text edge, mirroring the margin on verso pages."""
        if self.mirror and page_number % 2:
            return self.right
        return self.left

    def _justify(
        self, line: Line, face: EmbeddedFont, size: float, slack: float
    ) -> Line:
        """Spread the line's slack over its word gaps.

        The breaker has already chosen the breaks, so the slack is known and
        only the gaps have to absorb it. A negative spacing tightens the line,
        which is why lines no longer all fall short.
        """
        spaces = line.text.count(" ")
        if not spaces:
            return line
        space = text_width(" ", face, size)
        if space <= 0:
            return line
        extra = slack / (spaces * space)
        if abs(extra) > 0.34:
            # Beyond a third of an em in either direction the word spaces stop
            # reading as spaces. The line stays ragged rather than opening a
            # gap or crushing the words together.
            return line
        return Line(line.text, line.x, line.y, line.size, line.role, word_spacing=extra * space)

    def _decorate(self, page: Page, index: int, total: int) -> Page:
        for position, entries in self.furniture.items():
            if index == 0 and position in self.omit_first:
                continue
            for entry in entries:
                text = entry.text.replace("{folio}", str(index + 1))
                face = self.fonts.face(entry.role)
                if position == "footer-centre":
                    y = self.bottom / 2
                    x = self._origin(index) + (self.measure - text_width(text, face, entry.size)) / 2
                elif position == "footer-right":
                    y = self.bottom / 2
                    x = self._origin(index) + self.measure - text_width(text, face, entry.size)
                else:
                    y = self.height - self.top / 2
                    x = self.left
                page.lines.append(Line(text, x, y, entry.size, entry.role))
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


def _show(line: Line, face: EmbeddedFont) -> str:
    """Return the text-showing operator for one line.

    Justified lines use a TJ array with an explicit adjustment at every word
    gap. The Tw operator is not usable here: PDF 32000 9.3.3 applies word
    spacing only to byte code 32 in simple fonts, so with Identity-H
    encoding it would silently do nothing and leave a ragged right edge.
    TJ adjustments are in thousandths of a text-space unit and a positive
    number moves left, so extra word space is a negative adjustment.
    """
    if not line.word_spacing:
        return f"<{_hex_glyphs(line.text, face)}> Tj"
    adjustment = round(-line.word_spacing * 1000 / line.size)
    if adjustment >= 0:
        return f"<{_hex_glyphs(line.text, face)}> Tj"
    tokens = line.text.split(" ")
    array: list[str] = []
    for index, word in enumerate(tokens):
        # Each chunk keeps the space that follows it. Dropping the space glyph
        # and replacing it with the adjustment alone shortens the line by the
        # whole natural word spacing, which is roughly the error being fixed.
        chunk = word if index == len(tokens) - 1 else f"{word} "
        array.append(f"<{_hex_glyphs(chunk, face)}>")
        if index < len(tokens) - 1:
            array.append(str(adjustment))
    return "[" + " ".join(array) + "] TJ"


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
                _show(line, faces[line.role]),
                "ET",
            ]
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
    "GRID",
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
