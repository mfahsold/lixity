"""The three composed PDF documents Lixity can publish.

Each layout exists because a different reader needs different geometry:

* the report answers "what did the analysis find" and follows the measured
  report the CLI already writes;
* the book layout is for reading a manuscript continuously, so it uses a serif
  measure, indented paragraphs, chapter openings and running heads;
* the 30 by 60 sheet is a submission format: fixed character grid, fixed line
  count, page breaks only where the format demands them.

Fonts are located on the host rather than shipped, because a bundled typeface
would impose a licence on every generated file. A missing font is reported with
the paths that were searched instead of silently falling back to a face that
cannot draw the manuscript's script.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from .pdf_document import (
    A4,
    A5,
    CENTRE,
    GRID,
    JUSTIFIED,
    Block,
    Document,
    FontSet,
    PdfError,
    Table,
    text_width,
)
from .pdf_font import EmbeddedFont

NORM_LINES = 30
NORM_COLUMNS = 60

#: Target characters per line. Print research treats 45-75 as the band and
#: 55-70 as the working range; justified text below ~40 develops rivers.
BOOK_CPL = 64
REPORT_CPL = 78


class FontUnavailable(PdfError):
    """Raised when no usable font file could be located on this host."""


# A reading face first: EB Garamond and Linux Libertine are set for book work,
# Liberation Serif carries Times metrics, and DejaVu Serif is the last resort
# because it is wide and reads more like a screen face than a printed page.
_SERIF = (
    "EBGaramond12-Regular.ttf",
    "Garamond12.ttf",
    "LinuxLibertine-Regular.ttf",
    "CharisSIL-Regular.ttf",
    "GentiumPlus-Regular.ttf",
    "LiberationSerif-Regular.ttf",
    "DejaVuSerif.ttf",
    "NotoSerif-Regular.ttf",
    "FreeSerif.ttf",
    "Tinos-Regular.ttf",
)
_SERIF_BOLD = (
    "EBGaramond12-Bold.ttf",
    "LinuxLibertine-Bold.ttf",
    "CharisSIL-Bold.ttf",
    "LiberationSerif-Bold.ttf",
    "DejaVuSerif-Bold.ttf",
    "NotoSerif-Bold.ttf",
    "FreeSerifBold.ttf",
    "Tinos-Bold.ttf",
)
_SANS = (
    # DejaVu Sans includes the mathematical symbols emitted by analysis reports.
    "DejaVuSans.ttf",
    "NotoSans-Regular.ttf",
    "LiberationSans-Regular.ttf",
    "Arimo-Regular.ttf",
    "FreeSans.ttf",
)
_SANS_BOLD = (
    "DejaVuSans-Bold.ttf",
    "NotoSans-Bold.ttf",
    "LiberationSans-Bold.ttf",
    "Arimo-Bold.ttf",
    "FreeSansBold.ttf",
)
_MONO = (
    "DejaVuSansMono.ttf",
    "NotoSansMono-Regular.ttf",
    "LiberationMono-Regular.ttf",
    "FreeMono.ttf",
    "UbuntuMono-R.ttf",
    "Cousine-Regular.ttf",
)

_ROLE_FONTS = {
    "text": _SERIF,
    "heading": _SERIF_BOLD,
    "mono": _MONO,
    "sans": _SANS,
    "sans_bold": _SANS_BOLD,
}

_SEARCH_ROOTS = (
    "/usr/share/fonts",
    "/usr/local/share/fonts",
    "/usr/share/fonts/truetype",
    "/Library/Fonts",
    "/System/Library/Fonts",
    "C:/Windows/Fonts",
)


@dataclass(frozen=True)
class FontChoice:
    """PDF font roles, resolved from explicit choices, role settings or host fonts."""

    serif: str | None = None
    serif_bold: str | None = None
    mono: str | None = None
    sans: str | None = None
    sans_bold: str | None = None

    def roles(self, required: tuple[str, ...] | None = None) -> dict[str, str]:
        return resolve_fonts({
            "text": self.serif, "heading": self.serif_bold, "mono": self.mono,
            "sans": self.sans, "sans_bold": self.sans_bold,
        }, required=required)


def _installed_fonts() -> dict[str, str]:
    """Index the host's TrueType files by file name.

    Fonts are installed in per-family subdirectories whose layout differs per
    distribution, so the tree is walked once instead of guessing paths.
    """
    import os

    index: dict[str, str] = {}
    for root in _SEARCH_ROOTS:
        if not Path(root).is_dir():
            continue
        for base, _, files in os.walk(root):
            for name in files:
                if name.lower().endswith((".ttf", ".ttc")) and name not in index:
                    index[name] = str(Path(base) / name)
    return index


def resolve_fonts(roles: dict[str, str | None], *,
                  required: tuple[str, ...] | None = None) -> dict[str, str]:
    """Find one readable file per role, preferring explicit configuration."""
    import os

    requested = {role: roles.get(role) for role in (required or tuple(_ROLE_FONTS))}
    wanted = {role: _ROLE_FONTS[role] for role in requested}
    found: dict[str, str] = {}
    environment = {role: os.environ.get(f"LIXITY_PDF_FONT_{role.upper()}") for role in requested}
    index = _installed_fonts() if any(not path for path in requested.values()) else {}
    for role, names in wanted.items():
        configured = requested[role] or environment[role]
        if configured:
            if Path(configured).is_file():
                found[role] = configured
                continue
            raise FontUnavailable(f"Configured font for {role} does not exist: {configured}")
        for name in names:
            if name in index:
                found[role] = index[name]
                break
        else:
            raise FontUnavailable(
                f"No usable {role} font found. Set LIXITY_PDF_FONT_{role.upper()} "
                f"to a TrueType file, for example one of: {', '.join(names)}"
            )
    return found


#: Representative prose, not filler: the average character advance of a face is
#: only meaningful on text like the text the document will actually carry.
_PROBE = (
    "Die Mühe lohnt sich findet die Nachtigall. Sie findet ihren Gesang ganz wunderbar, "
    "und am Ende sitzt sie still auf einem Ast und wartet darauf, dass jemand zuhört. "
    "Manchmal sitze ich nachts an der Bar, wenn die Straßen leer werden und der Nebel "
    "heraufzieht, und schaue den Leuten zu, wie sie sich langsam wieder verlieren. "
    "Was bleibt, ist ein Maß, das man nicht berechnen kann, sondern nur auswählen."
)


def fit_size(fonts: FontSet, role: str, measure: float, target: int,
             sample: str = _PROBE) -> float:
    """Choose a type size whose lines hold about ``target`` characters.

    Print research puts comfortable book measures at roughly 55-70 characters
    and warns that justified text below about 40 produces rivers. The number
    depends on the face, so the size is derived from a real paragraph rather
    than assumed: measure the achieved characters per line at a reference size
    and scale. Characters per line fall as the type grows, so the correction
    multiplies by achieved/target, not the other way round.
    """
    from .pdf_document import break_lines, text_width

    probe = sample.strip() or _PROBE
    fonts.collect(role, probe)
    face = fonts.face(role)
    size = 10.0
    for _ in range(4):
        lines = [line for line in break_lines(probe, face, size, measure) if line.strip()]
        achieved = sum(len(line) for line in lines) / len(lines) if lines else target
        if achieved <= 0:
            break
        size *= (achieved / target) ** 0.85
        size = min(max(size, 7.0), 22.0)
    del text_width
    return round(size, 1)


def _fontset(choice: FontChoice | None, required: tuple[str, ...]) -> FontSet:
    return FontSet((choice or FontChoice()).roles(required))


def _report_fontset(choice: FontChoice | None) -> FontSet:
    """A report is read on screen, so it uses a sans face rather than a book face."""
    resolved = (choice or FontChoice()).roles(("sans", "sans_bold"))
    return FontSet({"text": resolved["sans"], "heading": resolved["sans_bold"]})


def _markdown_line(raw: str) -> str | None:
    """Turn one Markdown line into plain text, or ``None`` to drop it.

    The analysis report is a Markdown table, and printing its pipes, bold
    markers and back ticks into a PDF makes the document unreadable. A table
    row becomes a readable ``label: value`` run; the rule row is dropped.
    """
    line = raw.strip()
    if not line:
        return ""
    if set(line) <= set("|-: "):
        return None
    if line.startswith("|"):
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        cells = [cell for cell in cells if cell]
        if not cells:
            return None
        line = "  ·  ".join(cells)
    elif line.startswith(("- ", "* ")):
        line = "– " + line[2:].strip()
    elif line.startswith("#"):
        line = line.lstrip("#").strip()
    return _plain(line)


def _paragraphs(markdown: str) -> list[tuple[str, list[str]]]:
    """Split a markdown body into (heading, lines) sections."""
    sections: list[tuple[str, list[str]]] = []
    heading = ""
    body: list[str] = []
    for raw in markdown.splitlines():
        line = raw.rstrip()
        if line.startswith("#"):
            if heading or body:
                sections.append((heading, body))
            heading = _plain(line.lstrip("#").strip())
            body = []
        elif line.strip():
            rendered = _markdown_line(line)
            if rendered:
                body.append(rendered)
    if heading or body:
        sections.append((heading, body))
    return sections


@dataclass(frozen=True)
class _TableData:
    """One pipe table from the report Markdown, markers already stripped."""

    header: list[str]
    rows: list[list[str]]


def _table_data(raw_rows: list[str]) -> _TableData | None:
    """Parse Markdown pipe rows; the alignment rule row is dropped."""
    rows: list[list[str]] = []
    for raw in raw_rows:
        if set(raw) <= set("|-: "):
            continue
        cells = [_plain(cell.strip()) for cell in raw.strip("|").split("|")]
        if any(cells):
            rows.append(cells)
    if len(rows) < 2:
        return None
    width = max(len(row) for row in rows)
    return _TableData(rows[0], [row + [""] * (width - len(row)) for row in rows[1:]])


def _report_sections(markdown: str) -> list[tuple[str, list[str | _TableData]]]:
    """Split the report into (heading, items); tables stay tabular.

    The report was previously flattened into ``label · value`` runs, which
    wrapped like prose and made every figure unreadable. Tables now travel as
    grids and are placed as grids.
    """
    sections: list[tuple[str, list[str | _TableData]]] = []
    heading = ""
    items: list[str | _TableData] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].rstrip()
        if not line.strip():
            index += 1
            continue
        if re.fullmatch(r"(?:-{3,}|\*{3,}|_{3,})", line.strip()):
            # The report Markdown separates sections with thematic breaks;
            # they structure the source, not the printed page.
            index += 1
            continue
        if line.startswith("#"):
            if heading or items:
                sections.append((heading, items))
            heading = _plain(line.lstrip("#").strip())
            items = []
            index += 1
            continue
        if line.lstrip().startswith("|"):
            raw_rows: list[str] = []
            while index < len(lines) and lines[index].lstrip().startswith("|"):
                raw_rows.append(lines[index].strip())
                index += 1
            table = _table_data(raw_rows)
            if table is not None:
                items.append(table)
            continue
        paragraph: list[str] = []
        while (index < len(lines) and lines[index].strip()
               and not lines[index].startswith("#")
               and not lines[index].lstrip().startswith("|")):
            raw = lines[index].strip()
            paragraph.append(("– " + raw[2:].strip()) if raw.startswith(("- ", "* ")) else _plain(raw))
            index += 1
        if paragraph:
            items.append(" ".join(paragraph))
    if heading or items:
        sections.append((heading, items))
    return sections


#: A cell whose body values are numbers and units reads as a measured column.
_NUMERIC_CELL = re.compile(r"^[0-9][0-9 .,%:/( )\u2013\u2014-]*$")


def _column_alignments(rows: list[list[str]]) -> list[str]:
    """Right-align columns whose body values are all numeric."""
    alignments: list[str] = []
    for column in range(len(rows[0])):
        values = [row[column] for row in rows[1:] if row[column]]
        alignments.append("right" if values and all(_NUMERIC_CELL.match(value) for value in values) else "left")
    return alignments


def _column_widths(header: list[str], rows: list[list[str]], text_face: EmbeddedFont,
                   heading_face: EmbeddedFont, size: float, measure: float,
                   gap: float) -> tuple[list[float], float]:
    """Fit column widths so no word is broken and long cells wrap.

    A naive proportional fit squeezes narrow numeric columns until their
    headings break mid-word ("Wört/er"). Every column therefore keeps a floor
    of its longest word plus a little air; the remaining space is shared
    proportionally to how much each column could still grow.
    """
    columns = len(header)
    naturals: list[float] = []
    floors: list[float] = []
    for column in range(columns):
        natural = text_width(header[column], heading_face, size)
        floor = max((text_width(word, heading_face, size) for word in header[column].split()),
                    default=0.0)
        for row in rows:
            cell = row[column]
            natural = max(natural, text_width(cell, text_face, size))
            for word in cell.split() or [""]:
                floor = max(floor, text_width(word, text_face, size))
        floors.append(floor + size * 0.6)
        naturals.append(natural)
    available = measure - gap * (columns - 1)
    if available <= 0:
        return floors, size
    if sum(floors) > available:
        # Prefer a slightly smaller table over broken words: a proportional
        # squeeze closes every column by a character and breaks every heading.
        # 0.78 keeps the type legible while the widest columns give way.
        factor = max(0.78, available / sum(floors))
        size = round(size * factor, 2)
        floors = [width * factor for width in floors]
        naturals = [width * factor for width in naturals]
    caps = [max(natural, floor) for natural, floor in zip(naturals, floors, strict=False)]
    widths = list(floors)
    excess = sum(widths) - available
    for _ in range(4):
        if excess <= 1e-6:
            break
        for index in sorted(range(columns), key=lambda column: widths[column], reverse=True):
            if excess <= 1e-6:
                break
            take = min(excess, widths[index] * 0.2)
            widths[index] -= take
            excess -= take
    if excess > 1e-6:
        scale = available / sum(widths)
        widths = [width * scale for width in widths]
    leftover = available - sum(widths)
    if leftover > 1e-6:
        growth = [max(0.0, cap - width) for cap, width in zip(caps, widths, strict=False)]
        total = sum(growth)
        if total > 0:
            widths = [min(cap, width + leftover * grow / total)
                      for cap, width, grow in zip(caps, widths, growth, strict=False)]
        else:
            widths = [width + leftover / columns for width in widths]
    return widths, size


#: Table type is a step below the body so tables read as reference material.
_REPORT_TABLE_SCALE = 0.92
_REPORT_TABLE_GAP = 12.0


def report_pdf(
    *,
    title: str,
    markdown: str,
    subtitle: str = "",
    choice: FontChoice | None = None,
    author: str = "",
    draft_notice: str = "",
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """Render the analysis report: a cover page, section headings and tables.

    A report is read on screen and skimmed, so it uses a sans face and a wider
    measure than a book. Figures live in aligned tables instead of flowing
    prose, the header row repeats after a page break and rows stay whole.
    """
    fonts = _report_fontset(choice)
    document = Document(fonts, page_size=A4, margins=(62, 62, 56, 78),
                        metadata={"title": title, "author": author, **(metadata or {})})
    sections = _report_sections(markdown)
    sample = " ".join(
        " ".join(item.header + [cell for row in item.rows for cell in row])
        if isinstance(item, _TableData) else item
        for _heading, items in sections for item in items
    )[:3000]
    size = fit_size(fonts, "text", document.measure, REPORT_CPL, sample or title)
    leading = round(size * 1.5, 2)
    document.baseline = leading

    # Cover: a bare letterhead keeps the first page calm; content starts on
    # page two and the running furniture never touches the cover.
    document.add(Block(title, role="heading", size=22, leading=1.2, space_after=leading * 0.2,
                       decorated=False))
    if author:
        document.add(Block(author, role="text", size=11.5, leading=1.3, space_after=2, decorated=False))
    if subtitle:
        document.add(Block(subtitle, role="text", size=11, leading=1.3, space_after=2, decorated=False))
    document.add_rule(space_before=leading * 0.5, space_after=0.0, decorated=False)

    # Collect every character first: table widths are measured against the
    # finished faces, not against a subset that still changes per block.
    document.fonts.collect("text", sample or title)
    for heading, items in sections:
        if heading:
            document.fonts.collect("heading", heading)
        for item in items:
            if isinstance(item, _TableData):
                for cell in item.header:
                    document.fonts.collect("heading", cell)
                for row in item.rows:
                    for cell in row:
                        document.fonts.collect("text", cell)
            else:
                document.fonts.collect("text", item)
    body_face = document.fonts.face("text")
    heading_face = document.fonts.face("heading")
    table_size = round(size * _REPORT_TABLE_SCALE, 1)
    first = True
    for heading, items in sections:
        if heading:
            document.add(Block(heading, role="heading", size=13.5, leading=1.3,
                               new_page=first, decorated=True,
                               space_before=0.0 if first else leading * 1.8,
                               space_after=leading * 0.7, bookmark=heading))
            first = False
        for item in items:
            if isinstance(item, _TableData):
                table_rows = [item.header, *item.rows]
                widths, drawn_size = _column_widths(item.header, item.rows, body_face,
                                                    heading_face, table_size,
                                                    document.measure, _REPORT_TABLE_GAP)
                document.add_table(Table(
                    rows=table_rows, widths=widths, gap=_REPORT_TABLE_GAP,
                    alignments=_column_alignments(table_rows),
                    size=drawn_size, leading=1.32, header=True, repeat_header=True,
                    row_rules=len(item.rows) >= 8, row_gap=drawn_size * 0.34,
                    space_before=leading * 0.25, space_after=leading * 1.0,
                    new_page=first, decorated=True,
                ))
            else:
                document.add(Block(item, role="text", size=size, leading=leading / size,
                                   align=JUSTIFIED, space_after=leading * 0.5,
                                   new_page=first, decorated=True))
            first = False
    _running_header(document, title, author, role="text", size=8, draft_notice=draft_notice)
    document.page_furniture("{folio}/{pages}", role="text", size=8.5, position="footer-centre")
    return document.render()


def book_pdf(
    *,
    title: str,
    author: str = "",
    draft_notice: str = "",
    chapters: list[tuple[str, list[str]]] | None = None,
    body: str = "",
    choice: FontChoice | None = None,
    metadata: Mapping[str, str] | None = None,
    front_matter: tuple[str, list[str]] | None = None,
) -> bytes:
    """Render a manuscript for continuous reading: serif measure, chapter openings."""
    fonts = _fontset(choice, ("text", "heading"))
    # Margins follow the classical hierarchy rather than four equal gaps: the
    # foot is larger than the head, because a vertically centred block reads as
    # sinking off the page, and the inside edge is the smaller of the two sides.
    left, right, top, bottom = 46.0, 52.0, 54.0, 74.0
    document = Document(
        fonts, page_size=A5, margins=(left, right, top, bottom), mirror=True,
        metadata={"title": title, "author": author, **(metadata or {})},
    )
    sections = _book_sections(chapters, body)
    sample = " ".join(" ".join(paragraphs) for _, paragraphs in sections)[:2000]
    size = fit_size(fonts, "text", document.measure, BOOK_CPL, sample)
    leading = round(size * 1.45, 2)
    document.baseline = leading
    # The cover block sits on the optical third of the page; a title at the top
    # edge reads as a letterhead, not as a book.
    spacer = round((A5[1] - top - bottom) * 0.26, 1)
    document.add(Block("", role="text", size=size, leading=spacer / size, decorated=False))
    document.add(
        Block(title, role="heading", size=17, leading=1.3, align=CENTRE, space_after=8,
              decorated=False)
    )
    if author:
        document.add(
            Block(author, role="text", size=11, leading=1.3, align=CENTRE, space_after=4,
                  decorated=False)
        )
    if front_matter is not None:
        heading, paragraphs = front_matter
        document.add(Block(heading, role="heading", size=13.5, new_page=True,
                           space_after=leading, decorated=False))
        for paragraph in paragraphs:
            document.add(Block(paragraph, role="text", size=size,
                               leading=leading / size, space_after=leading / 2,
                               decorated=False))
    first_body = True
    for heading, paragraphs in sections:
        if heading:
            document.add(
                Block(
                    heading,
                    role="heading",
                    size=13.5,
                    leading=1.4,
                    align=CENTRE,
                    new_page=True,
                    space_after=leading * 2,
                    bookmark=heading,
                )
            )
        for index, paragraph in enumerate(paragraphs):
            document.add(
                Block(
                    paragraph,
                    role="text",
                    size=size,
                    leading=leading / size,
                    align=JUSTIFIED,
                    # The first paragraph after a chapter opening is set flush,
                    # as a book does; every later one carries a first-line indent.
                    indent=0 if index == 0 else size * 1.4,
                    new_page=first_body and not heading,
                )
            )
            first_body = False
    _running_header(document, title, author, role="text", size=8, draft_notice=draft_notice)
    document.page_furniture("{folio}", role="text", size=9, position="footer-centre",
                           omit_first=True)
    return document.render()


def _book_sections(
    chapters: list[tuple[str, list[str]]] | None, body: str
) -> list[tuple[str, list[str]]]:
    if chapters is not None:
        return chapters
    return [(heading, lines) for heading, lines in _paragraphs(body) if lines or heading]


_MARKDOWN_INLINE = re.compile(r"(\*\*|__|\*|_|`)")


def _plain(text: str) -> str:
    """Strip only inline emphasis markers from a PDF heading line.

    Intentionally narrower than ``markdown_parser.strip_inline_markup``:
    headings keep footnote anchors and comments as literal layout text.
    """
    return _MARKDOWN_INLINE.sub("", text).strip()


def manuscript_pdf(
    *,
    title: str,
    chapters: list[tuple[str, list[str]]] | None = None,
    body: str = "",
    choice: FontChoice | None = None,
    author: str = "",
    draft_notice: str = "",
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """Render a submission sheet: exactly 30 lines of at most 60 characters."""
    from .pdf_document import text_width

    fonts = _fontset(choice, ("mono",))
    sections = _book_sections(chapters, body)
    # Every character is collected before the face is built: the measure needs
    # real advance widths, and a face measured before the rest of the text is
    # known would report zero for characters it has not seen yet.
    fonts.collect("mono", title + " " + draft_notice)
    for heading, paragraphs in sections:
        fonts.collect("mono", heading)
        for paragraph in paragraphs:
            fonts.collect("mono", paragraph)
    probe = "0" * NORM_COLUMNS
    fonts.collect("mono", probe)
    mono = fonts.face("mono")

    # The grid is a character count, so the measure follows the font's own
    # advance for NORM_COLUMNS glyphs rather than an assumed page width.
    measure = text_width(probe, mono, 12.0)
    side = max(24.0, (A4[0] - measure) / 2)
    top = bottom = 54.0
    size = 12.0
    # Space NORM_LINES lines evenly over the text block so the sheet holds
    # exactly 30 lines. Pagination then falls out of the page geometry instead
    # of a counter that can drift away from what actually fits.
    leading = (A4[1] - top - bottom) / NORM_LINES
    document = Document(fonts, margins=(side, side, top, bottom),
                        metadata={"title": title, "author": author, **(metadata or {})})
    document.add(Block(title, role="mono", size=size, align=CENTRE,
                       leading=leading / size, space_after=leading, columns=NORM_COLUMNS))

    # Each paragraph is handed to the document unbroken. Breaking it here and
    # letting the layout break it again put the 60-character limit exactly on
    # the boundary, where the two measurements disagreed and a word fell to
    # the next line for no reason.
    for heading, paragraphs in sections:
        if heading:
            document.add(Block(heading, role="mono", size=size, leading=leading / size,
                               align=GRID, columns=NORM_COLUMNS))
            document.add(Block("", role="mono", size=size, leading=leading / size, align=GRID))
        for paragraph in paragraphs:
            document.add(Block(paragraph, role="mono", size=size, leading=leading / size,
                               align=GRID, columns=NORM_COLUMNS))
            document.add(Block("", role="mono", size=size, leading=leading / size, align=GRID))
    _running_header(document, title, author, role="mono", size=8, columns=NORM_COLUMNS,
                    draft_notice=draft_notice)
    document.page_furniture("{folio}/{pages}", role="mono", size=8, position="footer-centre")
    return document.render()


def _running_header(document: Document, title: str, author: str, *, role: str,
                    size: float, columns: int | None = None, draft_notice: str = "") -> None:
    """Bound literal title/author/draft-notice text to one line outside the body block."""
    from .pdf_document import text_width

    text = " · ".join(
        " ".join(value.split()) for value in (title, author, draft_notice) if value.strip()
    )
    document.fonts.collect(role, text + "...")
    face = document.fonts.face(role)
    shortened = text
    while (text_width(shortened, face, size) > document.measure
           or (columns is not None and len(shortened) > columns)):
        text = text[:-1]
        shortened = text.rstrip() + "..."
        if not text:
            break
    document.page_furniture(shortened, role=role, size=size, position="header-centre", literal=True)


__all__ = [
    "NORM_COLUMNS",
    "NORM_LINES",
    "FontChoice",
    "FontUnavailable",
    "book_pdf",
    "manuscript_pdf",
    "report_pdf",
    "resolve_fonts",
]
