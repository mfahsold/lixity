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
)

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


def report_pdf(
    *,
    title: str,
    markdown: str,
    subtitle: str = "",
    choice: FontChoice | None = None,
    author: str = "",
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """Render the analysis report as a paginated A4 document.

    A report is read on screen and skimmed, so it uses a sans face, symmetric
    margins and a wider measure than a book. The foot stays larger than the
    head so the block does not read as sinking.
    """
    fonts = _report_fontset(choice)
    document = Document(fonts, page_size=A4, margins=(62, 62, 56, 78),
                        metadata={"title": title, "author": author, **(metadata or {})})
    sections = _paragraphs(markdown)
    sample = " ".join(line for _, lines in sections for line in lines)[:3000]
    size = fit_size(fonts, "text", document.measure, REPORT_CPL, sample)
    leading = round(size * 1.5, 2)
    document.baseline = leading
    document.add(Block(title, role="heading", size=19, leading=1.25, space_after=4))
    if subtitle:
        document.add(Block(subtitle, role="text", size=size, align=CENTRE, space_after=leading))
    for heading, entries in sections:
        if heading:
            document.add(
                Block(heading, role="heading", size=13, leading=1.3, space_before=leading,
                      space_after=leading / 2)
            )
        for entry in entries:
            document.add(
                Block(entry, role="text", size=size, leading=leading / size, align=JUSTIFIED,
                      space_after=leading / 2)
            )
    _running_header(document, title, author, role="text", size=8)
    document.page_furniture("{folio}/{pages}", role="text", size=8.5, position="footer-centre")
    return document.render()


def book_pdf(
    *,
    title: str,
    author: str = "",
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
    _running_header(document, title, author, role="text", size=8)
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
    metadata: Mapping[str, str] | None = None,
) -> bytes:
    """Render a submission sheet: exactly 30 lines of at most 60 characters."""
    from .pdf_document import text_width

    fonts = _fontset(choice, ("mono",))
    sections = _book_sections(chapters, body)
    # Every character is collected before the face is built: the measure needs
    # real advance widths, and a face measured before the rest of the text is
    # known would report zero for characters it has not seen yet.
    fonts.collect("mono", title)
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
    _running_header(document, title, author, role="mono", size=8, columns=NORM_COLUMNS)
    document.page_furniture("{folio}/{pages}", role="mono", size=8, position="footer-centre")
    return document.render()


def _running_header(document: Document, title: str, author: str, *, role: str,
                    size: float, columns: int | None = None) -> None:
    """Bound literal title/author text to one line outside the body block."""
    from .pdf_document import text_width

    text = " · ".join(" ".join(value.split()) for value in (title, author) if value.strip())
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
