"""Composed PDF documents with embedded TrueType subsets.

Every page is placed explicitly, so the writer depends on no browser, no
external converter and no document model. Text is addressed through glyph ids
and Identity-H encoding, preserving covered Unicode codepoints rather than the
fixed WinAnsi repertoire used by the older draft renderer. Contextual shaping
and bidirectional layout are outside this writer's scope.

Line breaking measures real advance widths from the embedded font, so a measure
is filled with actual glyph metrics rather than an average-character guess.
"""

from __future__ import annotations

import hashlib
import math
import re
import zlib
from collections.abc import Mapping
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


@dataclass(frozen=True)
class PageFurniture:
    text: str
    role: str
    size: float
    literal: bool = False


@dataclass
class Page:
    width: float
    height: float
    lines: list[Line] = field(default_factory=list)
    rules: list[tuple[float, float, float, float, float]] = field(default_factory=list)
    decorated: bool = True
    bookmarks: list[tuple[str, float]] = field(default_factory=list)


def text_width(text: str, face: EmbeddedFont, size: float) -> float:
    return sum(face.advance(ord(character)) / 1000 * size for character in text)


@dataclass(frozen=True)
class _MeasuredText:
    """Text and cumulative glyph advances, shared by both line breakers."""

    text: str
    advances: list[float]

    def width(self, start: int, end: int) -> float:
        return self.advances[end] - self.advances[start]


def _measured(text: str, face: EmbeddedFont, size: float,
              advances: list[float] | None = None) -> _MeasuredText:
    widths = advances if advances is not None else [
        face.advance(ord(character)) / 1000 * size for character in text
    ]
    if len(widths) != len(text):
        raise PdfError("Glyph advances must cover the complete block text")
    cumulative = [0.0]
    for width in widths:
        cumulative.append(cumulative[-1] + width)
    return _MeasuredText(text, cumulative)


def _break_offsets(measured: _MeasuredText, measure: float, *, first_indent: float = 0.0,
                   columns: int | None = None,
                   preserve_whitespace: bool = False) -> list[tuple[int, int]]:
    """Greedy fallback and fixed-grid breaker, using the same glyph measurements."""
    result: list[tuple[int, int]] = []
    offset = 0
    for paragraph in measured.text.split("\n"):
        words = list(re.finditer(r"[^ ]+", paragraph))
        if preserve_whitespace and paragraph and not words:
            words = list(re.finditer(r".+", paragraph))
        if not words:
            result.append((offset, offset + len(paragraph) if preserve_whitespace else offset))
            offset += len(paragraph) + 1
            continue
        start = end = offset if preserve_whitespace else offset + words[0].start()
        for word in words:
            word_start, word_end = offset + word.start(), offset + word.end()
            available = measure - (first_indent if not result else 0.0)
            if end > start and (measured.width(start, word_end) > available
                                or (columns is not None and word_end - start > columns)):
                result.append((start, end))
                start = word_start
            end = word_end
            available = measure - (first_indent if not result else 0.0)
            while (measured.width(start, end) > available
                   or (columns is not None and end - start > columns)) and end - start > 1:
                cut = min(end - 1, start + (columns or end - start))
                while cut - start > 1 and measured.width(start, cut) > available:
                    cut -= 1
                result.append((start, cut))
                start = cut
                available = measure
        result.append((start, end))
        offset += len(paragraph) + 1
    return result


def break_lines(
    text: str,
    face: EmbeddedFont,
    size: float,
    measure: float,
    *,
    first_indent: float = 0.0,
    columns: int | None = None,
) -> list[str]:
    """Split text into lines that fit ``measure``; explicit newlines always break."""
    measured = _measured(text, face, size)
    return [text[start:end] for start, end in _break_offsets(
        measured, measure, first_indent=first_indent, columns=columns,
    )]


def _subset_or_fail(path: str, codepoints: set[int]) -> EmbeddedFont:
    try:
        return subset_font(path, codepoints)
    except FontError as error:
        raise PdfError(str(error)) from error
    except OSError as error:
        raise PdfError(f"Cannot read configured font: {error}") from error


@dataclass(frozen=True)
class FittedLine:
    """One composed line and its source range; slack is measured in points."""

    text: str
    slack: float
    start: int = 0
    end: int = 0


def fit_paragraph(
    text: str,
    face: EmbeddedFont,
    size: float,
    measure: float,
    *,
    first_indent: float = 0.0,
    allow_tightening: bool = True,
    advances: list[float] | None = None,
    columns: int | None = None,
    preserve_whitespace: bool = False,
) -> list[FittedLine]:
    """Choose a low-badness chain of word breaks with actual glyph advances.

    Optional per-character advances let inline font roles share the same
    breaker as ordinary prose. Oversized words and character grids use the
    common greedy fallback, preserving source ranges for styled fragments.
    """
    measured = _measured(text, face, size, advances)

    def fitted(start: int, end: int, indent: float = 0.0) -> FittedLine:
        return FittedLine(text[start:end], measure - indent - measured.width(start, end), start, end)

    if columns is not None or preserve_whitespace:
        return [fitted(start, end, first_indent if index == 0 else 0.0)
                for index, (start, end) in enumerate(_break_offsets(
                    measured, measure, first_indent=first_indent, columns=columns,
                    preserve_whitespace=preserve_whitespace,
                ))]
    lines: list[FittedLine] = []
    offset = 0
    for paragraph in text.split("\n"):
        words = [(offset + match.start(), offset + match.end())
                 for match in re.finditer(r"[^ ]+", paragraph)]
        indent = first_indent if not lines else 0.0
        if not words:
            lines.append(fitted(offset, offset, indent))
            offset += len(paragraph) + 1
            continue
        widths = [measured.width(start, end) for start, end in words]
        count = len(words)
        best = [float("inf")] * (count + 1)
        best[0] = 0.0
        choice = [0] * (count + 1)
        if not any(width > measure - indent for width in widths):
            for start in range(count):
                if best[start] == float("inf"):
                    continue
                available = measure - (indent if start == 0 else 0.0)
                for stop in range(start, count):
                    natural = measured.width(words[start][0], words[stop][1])
                    slack = available - natural
                    if slack < 0 and not allow_tightening:
                        break
                    final = stop + 1 == count
                    if final:
                        if slack < 0:
                            break
                        cost = 0.0
                    elif natural < available * 0.5:
                        continue
                    else:
                        spaces = sum(measured.width(words[i][1], words[i + 1][0])
                                     for i in range(start, stop))
                        ratio = slack / spaces if spaces else 0.0
                        if ratio < -0.34:
                            if stop > start:
                                break
                            continue
                        cost = ((abs(ratio) ** 3) * 100.0 + 5000.0 if ratio > 1.0 else
                                (abs(ratio) ** 3) * 100.0 + (slack**2) / 40.0 + 8.0)
                    if best[start] + cost < best[stop + 1]:
                        best[stop + 1] = best[start] + cost
                        choice[stop + 1] = start
        if best[count] == float("inf"):
            local_widths = [measured.width(i, i + 1) for i in range(offset, offset + len(paragraph))]
            local = _measured(paragraph, face, size, local_widths)
            lines.extend(fitted(offset + start, offset + end, indent if index == 0 else 0.0)
                         for index, (start, end) in enumerate(_break_offsets(
                             local, measure, first_indent=indent,
                         )))
        else:
            breaks: list[tuple[int, int]] = []
            position = count
            while position > 0:
                start = choice[position]
                breaks.append((start, position))
                position = start
            for start, stop in reversed(breaks):
                lines.append(fitted(words[start][0], words[stop - 1][1],
                                    indent if start == 0 else 0.0))
        offset += len(paragraph) + 1
    return lines


class FontSet:
    """Named faces subset once per document, after every character is known."""

    def __init__(self, paths: dict[str, str]) -> None:
        missing = [role for role, path in paths.items() if not path]
        if missing:
            raise PdfError(f"Missing font file for: {', '.join(sorted(missing))}")
        self.paths = dict(paths)
        self._codepoints: dict[str, set[int]] = {role: set() for role in paths}
        self._faces: dict[str, EmbeddedFont] = {}

    def collect(self, role: str, text: str) -> None:
        if role not in self.paths:
            raise PdfError(f"No font configured for the {role} role")
        codepoints = self._codepoints[role]
        before = len(codepoints)
        codepoints.update(ord(character) for character in text)
        if len(codepoints) != before:
            # Faces are built once from the collected characters. Text seen after
            # a build must widen the subset, otherwise its glyphs are missing.
            self._faces.pop(role, None)

    def build(self) -> dict[str, EmbeddedFont]:
        if not any(self._codepoints.values()):
            raise PdfError("The document contains no text to render")
        for role, path in self.paths.items():
            if self._codepoints[role] and role not in self._faces:
                self._faces[role] = _subset_or_fail(path, self._codepoints[role])
        return self._faces

    def face(self, role: str) -> EmbeddedFont:
        faces = self.build()
        if role not in faces:
            raise PdfError(f"No text collected for the {role} font")
        return faces[role]

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
    columns: int | None = None
    decorated: bool = True
    bookmark: str = ""
    runs: list[tuple[str, str]] | None = None
    inset: float = 0.0
    keep_with_next: bool = False
    min_split_lines: int = 1
    numbered: bool = False
    preserve_whitespace: bool = False


@dataclass
class Rule:
    """A horizontal hairline the flow consumes; used for covers and tables."""

    space_before: float = 0.0
    space_after: float = 0.0
    width: float = 0.6
    new_page: bool = False
    decorated: bool = True


@dataclass
class Table:
    """A grid placed as one flow item: rows stay whole and wrap inside columns.

    ``widths`` are the column content widths; ``gap`` is the space between
    columns. The first row is the header when ``header`` is set: it is drawn
    with ``heading_role``, gets a rule, and is repeated after a page break.
    """

    rows: list[list[str]]
    widths: list[float]
    gap: float = 10.0
    role: str = "text"
    heading_role: str = "heading"
    alignments: list[str] | None = None
    size: float = 10.0
    leading: float = 1.3
    header: bool = True
    repeat_header: bool = True
    row_rules: bool = False
    row_gap: float = 3.0
    space_before: float = 0.0
    space_after: float = 0.0
    new_page: bool = False
    decorated: bool = True


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
        metadata: Mapping[str, str] | None = None,
    ) -> None:
        self.fonts = fonts
        self.width, self.height = page_size
        self.left, self.right, self.top, self.bottom = margins
        # Mirrored margins are what a bound spread needs: the inside edge sits
        # on opposite sides of facing pages, so without this every second page
        # sits visibly off centre when the file is printed double-sided.
        self.mirror = mirror
        self.baseline = baseline
        self.metadata = dict(metadata or {})
        self.blocks: list[Block | Table | Rule] = []
        self.furniture: dict[str, list[PageFurniture]] = {}
        self.omit_first: set[str] = set()
        self.line_numbers: tuple[str, float, float] | None = None

    @property
    def measure(self) -> float:
        return self.width - self.left - self.right

    def _snap(self, cursor: float) -> float:
        """Round a baseline onto the baseline grid, when one is set."""
        if not self.baseline:
            return cursor
        return math.floor(cursor / self.baseline + 1e-9) * self.baseline

    def add(self, block: Block) -> None:
        if block.runs is not None:
            if "".join(text for text, _role in block.runs) != block.text:
                raise PdfError("Inline runs must cover the complete block text")
            for text, role in block.runs:
                if text:
                    self.fonts.collect(role, text)
        else:
            self.fonts.collect(block.role, block.text)
        self.blocks.append(block)

    def add_rule(
        self,
        *,
        space_before: float = 0.0,
        space_after: float = 0.0,
        width: float = 0.6,
        new_page: bool = False,
        decorated: bool = True,
    ) -> None:
        self.blocks.append(Rule(space_before, space_after, width, new_page, decorated))

    def add_table(self, table: Table) -> None:
        """Collect every cell before the faces are subset, then queue the grid."""
        for role in {table.role, table.heading_role}:
            for row in table.rows:
                for cell in row:
                    self.fonts.collect(role, cell)
        self.blocks.append(table)

    def page_furniture(
        self,
        text: str,
        *,
        role: str,
        size: float,
        position: str,
        omit_first: bool = False,
        literal: bool = False,
    ) -> None:
        """Register running heads or folios drawn on the rendered pages.

        ``{folio}`` and ``{pages}`` become physical page numbers and totals.
        ``literal`` keeps entered headers inert; ``omit_first`` omits furniture
        on the first page, while undecorated frontmatter omits it on every page.
        """
        numbered = not literal and ("{folio}" in text or "{pages}" in text)
        self.fonts.collect(role, text + ("0123456789" if numbered else ""))
        self.furniture[position] = [
            *self.furniture.get(position, []),
            PageFurniture(text, role, size, literal),
        ]
        if omit_first:
            self.omit_first.add(position)

    def _compose(self) -> list[Page]:
        faces = self.fonts.build()
        pages: list[Page] = []
        page = Page(self.width, self.height)
        cursor = self.height - self.top

        def new_page(decorated: bool) -> None:
            nonlocal page, cursor
            pages.append(page)
            page = Page(self.width, self.height, decorated=decorated)
            cursor = self.height - self.top

        def draw_table(table: Table) -> None:
            nonlocal cursor
            body_face = faces[table.role]
            head_face = faces[table.heading_role]
            step = table.size * table.leading
            aligns = list(table.alignments or ["left"] * len(table.widths))
            total = sum(table.widths) + table.gap * max(0, len(table.widths) - 1)

            def row_height(cells: list[str], face: EmbeddedFont) -> float:
                lines = 1
                for column, cell in enumerate(cells):
                    if column < len(table.widths):
                        lines = max(
                            lines, len(break_lines(cell, face, table.size, table.widths[column]))
                        )
                return lines * step

            def draw_row(cells: list[str], face: EmbeddedFont, role: str, *, header: bool) -> None:
                nonlocal cursor
                # Table lines are not snapped onto the body baseline grid: their
                # step is smaller than the grid, so snapping made rows collide.
                first = cursor - table.size
                origin = self._origin(len(pages))
                x = origin
                height = row_height(cells, face)
                for column, cell in enumerate(cells):
                    if column >= len(table.widths):
                        break
                    for index, drawn in enumerate(
                        break_lines(cell, face, table.size, table.widths[column])
                    ):
                        if not drawn:
                            continue
                        advance = text_width(drawn, face, table.size)
                        align = aligns[column] if column < len(aligns) else LEFT
                        if align == "right":
                            start = x + table.widths[column] - advance
                        elif align == "centre":
                            start = x + (table.widths[column] - advance) / 2
                        else:
                            start = x
                        page.lines.append(
                            Line(drawn, start, first - index * step, table.size, role)
                        )
                    x += table.widths[column] + table.gap
                if header:
                    rule_y = first - table.size * 0.30
                    page.rules.append((origin, rule_y, origin + total, rule_y, 0.6))
                elif table.row_rules:
                    rule_y = first - height + table.size * 0.55
                    page.rules.append((origin, rule_y, origin + total, rule_y, 0.4))
                cursor -= height

            header_row = table.rows[0] if table.header and table.rows else None
            body_rows = table.rows[1:] if header_row is not None else table.rows
            if header_row is not None:
                needed = row_height(header_row, head_face) + table.row_gap
                if cursor - needed < self.bottom:
                    new_page(table.decorated)
                draw_row(header_row, head_face, table.heading_role, header=True)
                cursor -= table.row_gap
            for index, row in enumerate(body_rows):
                gap = table.row_gap if index + 1 < len(body_rows) else 0.0
                if cursor - (row_height(row, body_face) + gap) < self.bottom:
                    new_page(table.decorated)
                    if header_row is not None and table.repeat_header:
                        draw_row(header_row, head_face, table.heading_role, header=True)
                        cursor -= table.row_gap
                draw_row(row, body_face, table.role, header=False)
                cursor -= gap

        def prepared(block: Block) -> tuple[list[FittedLine], EmbeddedFont, list[tuple[int, int, str]]]:
            runs = block.runs or [(block.text, block.role)]
            role = next((role for text, role in runs if text), block.role)
            face = faces.get(role) or next(iter(faces.values()))
            spans: list[tuple[int, int, str]] = []
            advances: list[float] = []
            offset = 0
            for text, role in runs:
                if not text:
                    continue
                spans.append((offset, offset + len(text), role))
                advances.extend(faces[role].advance(ord(character)) / 1000 * block.size
                                for character in text)
                offset += len(text)
            pieces = fit_paragraph(
                block.text, face, block.size, self.measure - block.inset * 2,
                first_indent=block.indent, allow_tightening=block.align == JUSTIFIED,
                advances=advances if block.runs is not None else None,
                columns=block.columns, preserve_whitespace=block.preserve_whitespace,
            )
            return pieces, face, spans

        def capacity(block: Block, face: EmbeddedFont, start: float) -> int:
            count = 0
            descent = face.metrics.descent * block.size / face.metrics.units_per_em
            while count < 10000:
                baseline = self._snap(start - block.size)
                if baseline + descent < self.bottom - 1e-6:
                    break
                count += 1
                start = baseline + block.size - block.size * block.leading
            return count

        for block_index, block in enumerate(self.blocks):
            if block.new_page and page.lines:
                new_page(block.decorated)
            if not page.lines:
                page.decorated = block.decorated
            if block.space_before and cursor < self.height - self.top:
                cursor -= block.space_before
            if isinstance(block, Table):
                draw_table(block)
                cursor -= block.space_after
                continue
            if isinstance(block, Rule):
                origin = self._origin(len(pages))
                page.rules.append((origin, cursor, origin + self.measure, cursor, block.width))
                cursor -= block.space_after
                continue
            pieces, face, spans = prepared(block)
            step = block.size * block.leading
            if block.keep_with_next and page.lines:
                # Reserve the whole heading chain and the first body fragment.
                # Stop once it fits, the page fills, or an explicit boundary
                # intervenes; a long manuscript does not widen this lookahead.
                after = cursor
                for following_index in range(block_index, len(self.blocks)):
                    following = self.blocks[following_index]
                    if not isinstance(following, Block) or (
                        following_index > block_index and following.new_page
                    ):
                        break
                    if following_index == block_index:
                        following_pieces, following_face = pieces, face
                    else:
                        after -= following.space_before
                        following_pieces, following_face, _ = prepared(following)
                    required = (len(following_pieces) if following.keep_with_next else
                                min(max(2, following.min_split_lines), len(following_pieces)))
                    if capacity(following, following_face, after) < required:
                        new_page(block.decorated)
                        break
                    if not following.keep_with_next:
                        break
                    for _piece in following_pieces:
                        after = (self._snap(after - following.size) + following.size
                                 - following.size * following.leading)
                    after -= following.space_after
            index = 0
            while index < len(pieces):
                available = capacity(block, face, cursor)
                remaining = len(pieces) - index
                minimum = min(block.min_split_lines, remaining)
                if available < minimum and page.lines:
                    new_page(block.decorated)
                    available = capacity(block, face, cursor)
                count = min(max(1, available), remaining)
                if 0 < remaining - count < block.min_split_lines:
                    adjusted = remaining - block.min_split_lines
                    if adjusted >= block.min_split_lines:
                        count = adjusted
                origin = self._origin(len(pages)) + block.inset
                for piece in pieces[index:index + count]:
                    baseline = self._snap(cursor - block.size)
                    start_x = origin + (block.indent if index == 0 else 0.0)
                    natural = self.measure - block.inset * 2 - piece.slack
                    if index == 0:
                        natural -= block.indent
                    if block.align == CENTRE and piece.text:
                        start_x = origin + (self.measure - block.inset * 2 - natural) / 2
                    extra = 0.0
                    if block.align == JUSTIFIED and piece.text and index < len(pieces) - 1:
                        gaps = 0.0
                        for start, stop, role in spans:
                            fragment = block.text[max(piece.start, start):min(piece.end, stop)]
                            gaps += fragment.count(" ") * text_width(" ", faces[role], block.size)
                        if gaps and abs(piece.slack / gaps) <= 0.34:
                            extra = piece.slack / piece.text.count(" ")
                    if block.numbered and self.line_numbers is not None and piece.text:
                        role, size, gutter = self.line_numbers
                        # One number per baseline, independent of inline fragments.
                        number = str(1 + sum(line.x < self._origin(len(pages))
                                             for line in page.lines))
                        x = self._origin(len(pages)) - gutter / 2 - text_width(number, faces[role], size)
                        page.lines.append(Line(number, x, baseline, size, role))
                    drawn = False
                    for start, stop, role in spans:
                        fragment = block.text[max(piece.start, start):min(piece.end, stop)]
                        if not fragment:
                            continue
                        line = Line(fragment, start_x, baseline, block.size, role, extra)
                        page.lines.append(line)
                        start_x += text_width(fragment, faces[role], block.size) + fragment.count(" ") * extra
                        drawn = True
                    if not drawn:
                        page.lines.append(Line("", start_x, baseline, block.size, block.role))
                    if index == 0 and block.bookmark:
                        page.bookmarks.append((block.bookmark, baseline + block.size))
                    cursor = baseline + block.size - step
                    index += 1
                if index < len(pieces):
                    new_page(block.decorated)
            cursor -= block.space_after
        pages.append(page)
        return [self._decorate(page, index, len(pages)) for index, page in enumerate(pages)]

    def _origin(self, page_number: int) -> float:
        """Return the left text edge, mirroring the margin on verso pages."""
        if self.mirror and page_number % 2:
            return self.right
        return self.left

    def _decorate(self, page: Page, index: int, total: int) -> Page:
        if not page.decorated:
            return page
        for position, entries in self.furniture.items():
            if index == 0 and position in self.omit_first:
                continue
            for entry in entries:
                text = (
                    entry.text
                    if entry.literal
                    else entry.text.replace("{folio}", str(index + 1)).replace(
                        "{pages}", str(total)
                    )
                )
                face = self.fonts.face(entry.role)
                if position == "footer-centre":
                    y = self.bottom / 2
                    x = (
                        self._origin(index)
                        + (self.measure - text_width(text, face, entry.size)) / 2
                    )
                elif position == "footer-right":
                    y = self.bottom / 2
                    x = self._origin(index) + self.measure - text_width(text, face, entry.size)
                elif position == "header-centre":
                    y = self.height - self.top / 2
                    x = (
                        self._origin(index)
                        + (self.measure - text_width(text, face, entry.size)) / 2
                    )
                else:
                    y = self.height - self.top / 2
                    x = self.left
                page.lines.append(Line(text, x, y, entry.size, entry.role))
        return page

    def render(self) -> bytes:
        pages = self._compose()
        for page in pages:
            for line in page.lines:
                missing = self.fonts.unmapped(line.role, line.text)
                if missing:
                    characters = ", ".join(
                        f"U+{ord(character):04X}" for character in sorted(missing)
                    )
                    raise PdfError(f"Font for {line.role} cannot draw: {characters}")
        return _write_pdf(pages, self.fonts.build(), metadata=self.metadata)


def _cid_map(face: EmbeddedFont) -> dict[int, int]:
    codepoints = sorted(cp for cp, glyph in face.glyph_ids.items() if glyph)
    if len(codepoints) > 0xFFFF:
        raise PdfError("A font has too many distinct Unicode characters for a PDF CID map")
    return {cp: index for index, cp in enumerate(codepoints, 1)}


def _to_unicode_cmap(face: EmbeddedFont, cids: Mapping[int, int] | None = None) -> str:
    """Map unique PDF character codes back to their original Unicode text."""
    entries = sorted((cid, cp) for cp, cid in (cids or _cid_map(face)).items())
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
        chr(byte) if 33 <= byte <= 126 and chr(byte) not in "()<>[]{}/%#" else f"#{byte:02X}"
        for byte in text.encode("utf-8")
    )


def _show(line: Line, face: EmbeddedFont, cids: Mapping[int, int] | None = None) -> str:
    """Return the text-showing operator for one line.

    Justified lines use a TJ array with an explicit adjustment at every word
    gap. The Tw operator is not usable here: PDF 32000 9.3.3 applies word
    spacing only to byte code 32 in simple fonts, so with Identity-H
    encoding it would silently do nothing and leave a ragged right edge.
    TJ adjustments are in thousandths of a text-space unit and a positive
    number moves left, so extra word space is a negative adjustment.
    """
    if not line.word_spacing:
        return f"<{_hex_glyphs(line.text, face, cids)}> Tj"
    adjustment = round(-line.word_spacing * 1000 / line.size)
    if adjustment == 0:
        return f"<{_hex_glyphs(line.text, face, cids)}> Tj"
    tokens = line.text.split(" ")
    array: list[str] = []
    for index, word in enumerate(tokens):
        # Each chunk keeps the space that follows it. Dropping the space glyph
        # and replacing it with the adjustment alone shortens the line by the
        # whole natural word spacing, which is roughly the error being fixed.
        chunk = word if index == len(tokens) - 1 else f"{word} "
        array.append(f"<{_hex_glyphs(chunk, face, cids)}>")
        if index < len(tokens) - 1:
            array.append(str(adjustment))
    return "[" + " ".join(array) + "] TJ"


def _hex_glyphs(text: str, face: EmbeddedFont, cids: Mapping[int, int] | None = None) -> str:
    mapping = cids if cids is not None else _cid_map(face)
    return "".join(f"{mapping.get(ord(character), 0):04X}" for character in text)


def _pdf_string(text: str) -> bytes:
    return b"<FEFF" + text.encode("utf-16-be").hex().upper().encode("ascii") + b">"


def _write_pdf(
    pages: list[Page], faces: dict[str, EmbeddedFont], *, metadata: Mapping[str, str] | None = None
) -> bytes:
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
    character_codes = {role: _cid_map(faces[role]) for role in roles}
    for role in roles:
        face = faces[role]
        cids = character_codes[role]
        prefix = "".join(chr(65 + byte % 26) for byte in hashlib.sha256(face.data).digest()[:6])
        font_name = _escape_name(prefix + "+" + face.metrics.postscript_name)
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
                f"<< /Type /FontDescriptor /FontName /{font_name} /Flags {face.metrics.flags} "
                f"/FontBBox [{bbox}] /ItalicAngle {face.metrics.italic_angle:.1f} "
                f"/Ascent {round(face.metrics.ascent * scale, 2)} "
                f"/Descent {round(face.metrics.descent * scale, 2)} "
                f"/CapHeight {round(face.metrics.cap_height * scale, 2)} "
                f"/StemV {face.metrics.stem_v} /FontFile2 {font_file} 0 R >>"
            ).encode("ascii")
        )
        widths = " ".join(
            f"{cids[codepoint]} [{round(face.advances.get(codepoint, 0) * scale)}]"
            for codepoint in sorted(cids)
        )
        glyph_map = add(
            stream(b"\0\0" + b"".join(face.glyph_ids[cp].to_bytes(2, "big") for cp in sorted(cids)))
        )
        descendant = add(
            (
                f"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /{font_name} "
                f"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
                f"/FontDescriptor {descriptor} 0 R /DW 1000 /W [{widths}] "
                f"/CIDToGIDMap {glyph_map} 0 R >>"
            ).encode("ascii")
        )
        # Without /ToUnicode a reader has no way back from a glyph id to the
        # character, so the exported text is neither searchable nor copyable.
        to_unicode = add(stream(_to_unicode_cmap(face, cids).encode("ascii")))
        resources[role] = add(
            (
                f"<< /Type /Font /Subtype /Type0 /BaseFont /{font_name} "
                f"/Encoding /Identity-H /DescendantFonts [{descendant} 0 R] "
                f"/ToUnicode {to_unicode} 0 R >>"
            ).encode("ascii")
        )

    page_objects: list[int] = []
    for page in pages:
        parts: list[str] = []
        for x1, y1, x2, y2, rule_width in page.rules:
            parts += [
                "q",
                "0.55 G",
                f"{rule_width:.2f} w",
                f"{x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S",
                "Q",
            ]
        for line in page.lines:
            parts += [
                "BT",
                f"/F{roles.index(line.role) + 1} {line.size:.2f} Tf",
                f"1 0 0 1 {line.x:.2f} {line.y:.2f} Tm",
                _show(line, faces[line.role], character_codes[line.role]),
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

    navigation = [
        (title, y, page_objects[index])
        for index, page in enumerate(pages)
        for title, y in page.bookmarks
    ]
    outline_entry = b""
    if navigation:
        outline_root = add(b"")
        outline_nodes = [add(b"") for _entry in navigation]
        for index, (title, y, destination) in enumerate(navigation):
            links = f" /Parent {outline_root} 0 R /Dest [{destination} 0 R /XYZ null {y:.2f} null]"
            if index:
                links += f" /Prev {outline_nodes[index - 1]} 0 R"
            if index + 1 < len(outline_nodes):
                links += f" /Next {outline_nodes[index + 1]} 0 R"
            objects[outline_nodes[index]] = (
                b"<< /Title " + _pdf_string(title) + links.encode("ascii") + b" >>"
            )
        objects[outline_root] = (
            f"<< /Type /Outlines /First {outline_nodes[0]} 0 R /Last {outline_nodes[-1]} 0 R "
            f"/Count {len(outline_nodes)} >>".encode("ascii")
        )
        outline_entry = f" /Outlines {outline_root} 0 R".encode("ascii")
    settings = metadata or {}
    language = b" /Lang " + _pdf_string(settings["language"]) if settings.get("language") else b""
    objects[catalog] = (
        f"<< /Type /Catalog /Pages {pages_obj} 0 R".encode("ascii")
        + language
        + outline_entry
        + b" >>"
    )
    objects[pages_obj] = (
        f"<< /Type /Pages /Kids [{' '.join(f'{n} 0 R' for n in page_objects)}] "
        f"/Count {len(page_objects)} >>"
    ).encode("ascii")

    info = (
        add(
            b"<< "
            + b" ".join(
                b"/" + key.encode("ascii") + b" " + _pdf_string(settings[value])
                for key, value in (("Title", "title"), ("Author", "author"))
                if settings.get(value)
            )
            + b" >>"
        )
        if any(settings.get(key) for key in ("title", "author"))
        else None
    )
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
    info_entry = f" /Info {info} 0 R" if info is not None else ""
    out += (
        f"trailer\n<< /Size {size} /Root {catalog} 0 R{info_entry} >>\n"
        f"startxref\n{xref_at}\n%%EOF\n"
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
    "Rule",
    "Table",
    "break_lines",
    "text_width",
]
