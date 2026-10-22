"""The native PDF layouts share one document engine and manuscript block flow.

Each layout exists because a different reader needs different geometry:

* the report answers "what did the analysis find" and follows the measured
  report the CLI already writes;
* the editorial copy leaves correction space and numbers manuscript lines;
* the neutral A4 document retains authored text without adding a title page,
  running heads, line numbers or analysis;
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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path

from .manuscript_document import (
    ManuscriptBlock,
    ManuscriptSections,
    inline_runs,
    manuscript_sections,
)
from .pdf_document import (
    A4,
    A5,
    CENTRE,
    GRID,
    JUSTIFIED,
    LEFT,
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
_SERIF_ITALIC = (
    "EBGaramond12-Italic.ttf", "LinuxLibertine-Italic.ttf", "CharisSIL-Italic.ttf",
    "GentiumPlus-Italic.ttf", "LiberationSerif-Italic.ttf", "DejaVuSerif-Italic.ttf",
    "NotoSerif-Italic.ttf", "FreeSerifItalic.ttf", "Tinos-Italic.ttf",
)
_SERIF_BOLD_ITALIC = (
    "EBGaramond12-BoldItalic.ttf", "LinuxLibertine-BoldItalic.ttf", "CharisSIL-BoldItalic.ttf",
    "LiberationSerif-BoldItalic.ttf", "DejaVuSerif-BoldItalic.ttf",
    "NotoSerif-BoldItalic.ttf", "FreeSerifBoldItalic.ttf", "Tinos-BoldItalic.ttf",
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
    "italic": _SERIF_ITALIC,
    "bold_italic": _SERIF_BOLD_ITALIC,
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
    serif_italic: str | None = None
    serif_bold_italic: str | None = None

    def roles(self, required: tuple[str, ...] | None = None) -> dict[str, str]:
        return resolve_fonts({
            "text": self.serif, "heading": self.serif_bold, "mono": self.mono,
            "sans": self.sans, "sans_bold": self.sans_bold,
            "italic": self.serif_italic, "bold_italic": self.serif_bold_italic,
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

    requested = {role: roles.get(role) for role in
                 (required or ("text", "heading", "mono", "sans", "sans_bold"))}
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
    """Estimate a stable type size from a representative glyph-width sample.

    The character target is a layout heuristic, not a measurement of the
    manuscript. A fixed probe keeps short chapters and long books at the same
    size and avoids counting an incomplete final line as a full measure.
    """
    probe = sample.strip() or _PROBE
    fonts.collect(role, probe)
    average = text_width(probe, fonts.face(role), 1.0) / len(probe)
    return round(min(max(measure / (target * average), 9.0), 22.0), 1)


def _fontset(choice: FontChoice | None, required: tuple[str, ...]) -> FontSet:
    return FontSet((choice or FontChoice()).roles(required))


def _report_fontset(choice: FontChoice | None) -> FontSet:
    """A report is read on screen, so it uses a sans face rather than a book face."""
    resolved = (choice or FontChoice()).roles(("sans", "sans_bold"))
    return FontSet({"text": resolved["sans"], "heading": resolved["sans_bold"]})


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
    size = fit_size(fonts, "text", document.measure, REPORT_CPL)
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


@dataclass(frozen=True)
class _ManuscriptStyle:
    """Geometry-dependent choices for the shared manuscript block flow."""

    mode: str
    size: float
    leading: float
    paragraph_gap: float = 0.0


def _manuscript_runs(block: ManuscriptBlock, *, sheet: bool = False) -> list[tuple[str, str]]:
    if block.kind in {"scene_break", "code"}:
        return [(block.text.expandtabs(4) if block.kind == "code" else block.text,
                 "mono" if sheet or block.kind == "code" else "text")]
    base = "heading" if block.kind == "heading" else "text"
    roles = {"plain": base, "emphasis": "bold_italic" if base == "heading" else "italic",
             "strong": "heading", "strong_emphasis": "bold_italic", "code": "mono"}
    return [(run.text, "mono" if sheet else roles[run.style]) for run in inline_runs(block.text)]


def _manuscript_fonts(choice: FontChoice | None, sections: ManuscriptSections,
                      *, sheet: bool = False) -> FontSet:
    required = {"mono"} if sheet else {"text", "heading"}
    for heading, blocks in sections:
        if heading:
            required.update(role for text, role in _manuscript_runs(
                ManuscriptBlock("heading", heading), sheet=sheet) if text)
        for block in blocks:
            required.update(role for text, role in _manuscript_runs(block, sheet=sheet) if text)
    return _fontset(choice, tuple(sorted(required)))


def _render_manuscript(document: Document, sections: ManuscriptSections,
                       style: _ManuscriptStyle, *, start_on_page: bool = False) -> None:
    """Place semantic manuscript blocks through one flow for all reading formats."""
    sheet = style.mode == "sheet"
    body_role = "mono" if sheet else "text"
    new_page = start_on_page
    for chapter_index, (heading, blocks) in enumerate(sections):
        first_paragraph = True
        if heading:
            heading_runs = _manuscript_runs(ManuscriptBlock("heading", heading), sheet=sheet)
            visible_heading = "".join(text for text, _role in heading_runs)
            heading_size = style.size if sheet else (17.0 if style.mode == "editor" else 13.5)
            if style.mode == "document":
                heading_size = 16.0
            document.add(Block(
                visible_heading, role="mono" if sheet else "heading", size=heading_size,
                leading=style.leading / heading_size,
                align=GRID if sheet else (CENTRE if style.mode == "book" else LEFT),
                columns=NORM_COLUMNS if sheet else None,
                new_page=new_page or (style.mode == "book") or
                         (style.mode == "editor" and chapter_index > 0),
                space_after=style.leading * (2 if style.mode == "book" else 1),
                bookmark=visible_heading, keep_with_next=True, runs=heading_runs,
            ))
            new_page = False
        for semantic in blocks:
            if semantic.kind == "page_break":
                new_page = True
                first_paragraph = True
                continue
            runs = _manuscript_runs(semantic, sheet=sheet)
            text = "".join(part for part, _role in runs)
            size = style.size
            inset = 0.0
            align = GRID if sheet else (JUSTIFIED if style.mode == "book" else LEFT)
            before = 0.0
            after = style.leading if sheet else style.paragraph_gap
            role = body_role
            keep = False
            if semantic.kind == "heading":
                role = "mono" if sheet else "heading"
                size = style.size if sheet else (13.0 if style.mode == "editor" else max(11.0, style.size * 1.12))
                if style.mode == "document":
                    size = max(style.size, 20.0 - semantic.level * 2.0)
                align = GRID if sheet else LEFT
                before = 0.0 if sheet else style.leading
                after = style.leading * (1.0 if sheet else 0.5)
                keep = True
                first_paragraph = True
            elif semantic.kind == "scene_break":
                align = CENTRE
                before = 0.0 if sheet else style.leading * 0.4
                after = style.leading * (1.0 if sheet else 0.7)
                first_paragraph = True
            elif semantic.kind in {"quote", "list_item", "code", "note"}:
                align = GRID if sheet else LEFT
                inset = style.size * (1.5 if semantic.kind == "quote" else 0.75)
                if semantic.kind == "code":
                    role = "mono"
                if semantic.kind == "note" and not sheet:
                    size = max(8.5, style.size * 0.82)
                if not sheet:
                    before = style.leading * 0.25
                    after = max(after, style.leading * 0.4)
                first_paragraph = True
            indent = (style.size * 1.4 if style.mode == "book" and
                      semantic.kind == "paragraph" and not first_paragraph else 0.0)
            document.add(Block(
                text, role=role, size=size, leading=style.leading / size,
                align=align, indent=indent, inset=inset, space_before=before,
                space_after=after, new_page=new_page, columns=NORM_COLUMNS if sheet else None,
                runs=runs, keep_with_next=keep, min_split_lines=1 if sheet else 2,
                numbered=style.mode == "editor", preserve_whitespace=semantic.kind == "code",
            ))
            new_page = False
            if semantic.kind == "paragraph":
                first_paragraph = False


def book_pdf(
    *,
    title: str,
    author: str = "",
    draft_notice: str = "",
    chapters: Sequence[tuple[str, Sequence[str | ManuscriptBlock]]] | None = None,
    body: str = "",
    choice: FontChoice | None = None,
    metadata: Mapping[str, str] | None = None,
    front_matter: tuple[str, list[str]] | None = None,
) -> bytes:
    """Render a manuscript for continuous reading, retaining semantic structure."""
    sections = _book_sections(chapters, body)
    fonts = _manuscript_fonts(choice, sections)
    left, right, top, bottom = 46.0, 52.0, 54.0, 74.0
    document = Document(
        fonts, page_size=A5, margins=(left, right, top, bottom), mirror=True,
        metadata={"title": title, "author": author, **(metadata or {})},
    )
    size = fit_size(fonts, "text", document.measure, BOOK_CPL)
    leading = round(size * 1.45, 2)
    document.baseline = leading
    spacer = round((A5[1] - top - bottom) * 0.26, 1)
    document.add(Block("", role="text", size=size, leading=spacer / size, decorated=False))
    document.add(Block(title, role="heading", size=17, leading=1.3, align=CENTRE,
                       space_after=8, decorated=False))
    if author:
        document.add(Block(author, role="text", size=11, leading=1.3, align=CENTRE,
                           space_after=4, decorated=False))
    if front_matter is not None:
        heading, paragraphs = front_matter
        document.add(Block(heading, role="heading", size=13.5, new_page=True,
                           space_after=leading, decorated=False, keep_with_next=True))
        for paragraph in paragraphs:
            document.add(Block(paragraph, role="text", size=size,
                               leading=leading / size, space_after=leading / 2,
                               decorated=False, min_split_lines=2))
    _render_manuscript(document, sections, _ManuscriptStyle("book", size, leading),
                       start_on_page=True)
    _running_header(document, title, author, role="text", size=8, draft_notice=draft_notice)
    document.page_furniture("{folio}", role="text", size=9, position="footer-centre",
                           omit_first=True)
    return document.render()


def editor_pdf(
    *,
    title: str,
    author: str = "",
    draft_notice: str = "",
    chapters: Sequence[tuple[str, Sequence[str | ManuscriptBlock]]] | None = None,
    body: str = "",
    choice: FontChoice | None = None,
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """Render an A4 editorial copy with correction margins and numbered lines."""
    from .layout import BookLayoutConfig

    layout = BookLayoutConfig.from_preset("lektorat")
    sections = _book_sections(chapters, body)
    fonts = _manuscript_fonts(choice, sections)
    document = Document(
        fonts, page_size=A4,
        margins=(layout.margin_left, layout.margin_right, layout.margin_top, layout.margin_bottom),
        metadata={"title": title, "author": author, **(metadata or {})},
    )
    size = layout.font_size_body
    leading = size * 1.5
    document.baseline = leading
    document.fonts.collect("text", "0123456789")
    document.line_numbers = ("text", layout.line_number_font_size, layout.line_number_gutter)
    document.add(Block(title, role="heading", size=layout.font_size_h1, leading=1.2,
                       space_after=12, keep_with_next=True))
    if author:
        document.add(Block(author, size=layout.title_sub_size, leading=1.3, space_after=6,
                           keep_with_next=True))
    document.add_rule(space_before=6, space_after=leading)
    _render_manuscript(document, sections,
                       _ManuscriptStyle("editor", size, leading, layout.para_spacing))
    _running_header(document, title, author, role="text", size=8, draft_notice=draft_notice)
    document.page_furniture("{folio}/{pages}", role="text", size=9,
                           position="footer-centre")
    return document.render()


def document_pdf(
    *,
    title: str,
    author: str = "",
    chapters: Sequence[tuple[str, Sequence[str | ManuscriptBlock]]] | None = None,
    body: str = "",
    choice: FontChoice | None = None,
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """Render neutral A4 text; title and author are metadata, not added prose."""
    sections = _book_sections(chapters, body, include_title=True)
    document = Document(
        _manuscript_fonts(choice, sections), page_size=A4,
        margins=(72.0, 72.0, 72.0, 72.0),
        metadata={"title": title, "author": author, **(metadata or {})},
    )
    document.baseline = 16.2
    _render_manuscript(document, sections, _ManuscriptStyle("document", 12.0, 16.2, 8.1))
    return document.render()


def _book_sections(
    chapters: Sequence[tuple[str, Sequence[str | ManuscriptBlock]]] | None, body: str,
    *, include_title: bool = False,
) -> ManuscriptSections:
    if chapters is not None:
        return [(heading, [ManuscriptBlock("paragraph", block) if isinstance(block, str) else block
                           for block in blocks]) for heading, blocks in chapters]
    from .models import CorpusConfig

    return manuscript_sections(body, CorpusConfig(), include_title=include_title)


_MARKDOWN_INLINE = re.compile(r"(\*\*|__|\*|_|`)")


def _plain(text: str) -> str:
    """Strip only inline emphasis markers from analysis report text.

    Intentionally narrower than ``markdown_parser.strip_inline_markup``:
    headings keep footnote anchors and comments as literal layout text.
    """
    return _MARKDOWN_INLINE.sub("", text).strip()


def manuscript_pdf(
    *,
    title: str,
    chapters: Sequence[tuple[str, Sequence[str | ManuscriptBlock]]] | None = None,
    body: str = "",
    choice: FontChoice | None = None,
    author: str = "",
    draft_notice: str = "",
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """Render a submission sheet: exactly 30 lines of at most 60 characters."""
    sections = _book_sections(chapters, body)
    fonts = _manuscript_fonts(choice, sections, sheet=True)
    probe = "0" * NORM_COLUMNS
    fonts.collect("mono", probe)
    measure = text_width(probe, fonts.face("mono"), 12.0)
    side = max(24.0, (A4[0] - measure) / 2)
    top = bottom = 54.0
    size = 12.0
    leading = (A4[1] - top - bottom) / NORM_LINES
    document = Document(fonts, margins=(side, side, top, bottom),
                        metadata={"title": title, "author": author, **(metadata or {})})
    document.add(Block(title, role="mono", size=size, align=CENTRE,
                       leading=leading / size, space_after=leading, columns=NORM_COLUMNS))
    _render_manuscript(document, sections, _ManuscriptStyle("sheet", size, leading))
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
    "document_pdf",
    "editor_pdf",
    "manuscript_pdf",
    "report_pdf",
    "resolve_fonts",
]
