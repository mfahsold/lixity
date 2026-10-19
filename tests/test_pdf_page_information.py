"""Shared pagination, navigation and publication metadata stay readable."""

from __future__ import annotations

import re
import shutil
import struct
import subprocess
from itertools import pairwise

import pytest

from lixity.pdf_document import Block, Document, FontSet, text_width
from lixity.pdf_font import _parse_cmap
from lixity.pdf_layouts import FontChoice, book_pdf, manuscript_pdf, report_pdf
from tests.test_pdf_export import CHOSEN, HAVE_FONTS, MONO, SERIF
from tests.test_pdf_integrity import fixture_font, tables

pytestmark = pytest.mark.skipif(not HAVE_FONTS, reason="requires the DejaVu font family")


def captured_layout(monkeypatch, function, **kwargs):
    from lixity import pdf_layouts

    captured = []

    class CaptureDocument(Document):
        def __init__(self, *args, **options):
            super().__init__(*args, **options)
            captured.append(self)

    monkeypatch.setattr(pdf_layouts, "Document", CaptureDocument)
    data = function(**kwargs)
    return data, captured[0], captured[0]._compose()


def test_mixed_heading_body_sizes_never_reuse_a_baseline():
    fonts = FontSet({"text": str(SERIF)})
    doc = Document(fonts, baseline=17.25)
    doc.add(Block("Title", size=19, leading=1.25, space_after=4))
    for _ in range(3):
        doc.add(Block("Corpus metrics", size=13, leading=1.3,
                      space_before=17.25, space_after=8.625))
        doc.add(Block("Following body text", size=11.5, leading=1.5))
    for page in doc._compose():
        for previous, following in zip(page.lines, page.lines[1:], strict=False):
            assert previous.y - following.y >= 11.5


def test_book_indent_affects_only_first_line_and_continuations_fit():
    fonts = FontSet({"text": str(SERIF)})
    doc = Document(fonts, page_size=(250, 180), margins=(25, 25, 25, 25))
    text = "Synthetic paragraphs have ordinary words and preserve readable margins. " * 20
    doc.add(Block(text, size=12, indent=18))
    pages = doc._compose()
    lines = [line for page in pages for line in page.lines]
    assert len(pages) > 1
    assert lines[0].x == 43
    assert all(line.x == 25 for line in lines[1:])
    face = fonts.face("text")
    for line in lines:
        assert line.x + text_width(line.text, face, line.size) <= 225 + 0.01
    assert " ".join(line.text for line in lines).split() == text.split()


def test_sheet_enforces_character_count_even_with_proportional_override(monkeypatch):
    _, _, pages = captured_layout(
        monkeypatch, manuscript_pdf, title="i" * 170,
        chapters=[("Grid", ["i" * 150, "W" * 150])],
        choice=FontChoice(mono=str(SERIF)),
    )
    for page in pages:
        body = [line for line in page.lines if 54 <= line.y <= page.height - 54]
        assert len(body) <= 30
        assert all(len(line.text) <= 60 for line in body)


def test_book_frontmatter_has_no_furniture_and_chapters_keep_physical_folios(monkeypatch):
    paragraphs = ["Synthetic paragraph, café Grüße. " * 50]
    _, _, pages = captured_layout(
        monkeypatch, book_pdf, title="Synthetic title", author="Synthetic Author",
        chapters=[("First chapter", paragraphs), ("Second chapter", paragraphs)],
        front_matter=("Imprint", ["Entered publisher\nEntered address", "Credits " * 300]),
        metadata={"title": "Synthetic title", "author": "Synthetic Author", "language": "de"},
        choice=CHOSEN,
    )
    chapter_page = next(i for i, page in enumerate(pages)
                        if any(line.text == "First chapter" for line in page.lines))
    assert chapter_page >= 2
    for page in pages[:chapter_page]:
        assert all(74 <= line.y <= page.height - 54 for line in page.lines)
    for index, page in enumerate(pages[chapter_page:], chapter_page + 1):
        assert page.lines[-1].text == str(index)
        assert any("Synthetic title" in line.text for line in page.lines if line.y > page.height - 54)


@pytest.mark.parametrize("function,kwargs,bare_cover", [
    (manuscript_pdf, {"chapters": [("Chapter", ["i" * 1000] * 6)]}, False),
    (report_pdf, {"markdown": "# Report\n\n" + "\n\n".join(["Synthetic prose. " * 100] * 5)}, True),
])
def test_sheet_report_headers_are_bounded_and_footer_contains_total(monkeypatch, function, kwargs,
                                                                    bare_cover):
    _, doc, pages = captured_layout(
        monkeypatch, function,
        title="A very long synthetic report title used for truncation checks " * 2,
        author="A very long synthetic author " * 3, choice=CHOSEN, **kwargs,
    )
    assert len(pages) > 1
    offset = 0
    if bare_cover:
        # The report cover is deliberately free of running furniture.
        assert not [line for line in pages[0].lines
                    if line.y > pages[0].height - doc.top or line.y < doc.bottom]
        pages = pages[1:]
        offset = 1
    for index, page in enumerate(pages, offset + 1):
        headers = [line for line in page.lines if line.y > page.height - doc.top]
        footers = [line for line in page.lines if line.y < doc.bottom]
        assert len(headers) == 1 and len(footers) == 1
        assert footers[0].text == f"{index}/{len(pages) + offset}"
        assert headers[0].text.endswith("...")
        for line in headers + footers:
            assert line.x >= doc.left
            assert line.x + text_width(line.text, doc.fonts.face(line.role), line.size) <= page.width - doc.right + 0.1


@pytest.mark.native_pdf
@pytest.mark.skipif(not shutil.which("pdftotext"), reason="requires Poppler pdftotext")
def test_unicode_aliases_keep_source_text_with_distinct_pdf_character_codes(tmp_path):
    original = tables(SERIF.read_bytes())
    cmap = _parse_cmap(original[b"cmap"])
    gid = cmap[ord("a")]
    # Valid format 12: two Unicode characters share the same outline.
    body = struct.pack(">III", ord("a"), ord("a"), gid) + struct.pack(">III", ord("b"), ord("b"), gid)
    subtable = struct.pack(">HHIII", 12, 0, 40, 0, 2) + body
    data = struct.pack(">HHHHI", 0, 1, 3, 10, 12) + subtable
    font = tmp_path / "shared-outline.ttf"
    font.write_bytes(fixture_font(SERIF, {b"cmap": data}))
    doc = Document(FontSet({"text": str(font)}))
    doc.add(Block("abba", size=20))
    pdf = tmp_path / "aliases.pdf"
    pdf.write_bytes(doc.render())
    executable = shutil.which("pdftotext")
    assert executable
    output = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic PDF
        [executable, str(pdf), "-"], capture_output=True, text=True, check=True,
    )
    assert not output.stderr
    assert output.stdout.strip() == "abba"


@pytest.mark.native_pdf
@pytest.mark.skipif(not shutil.which("pdfinfo") or not shutil.which("pdftotext"),
                    reason="requires Poppler pdfinfo and pdftotext")
def test_info_language_and_chapter_navigation_preserve_unicode_metadata(tmp_path):
    title, author = "ÄÖÜ, Café — a synthetic title", "Synthetic Grüße"
    data = book_pdf(title=title, author=author, choice=CHOSEN,
                    metadata={"title": title, "author": author, "language": "de"},
                    front_matter=("Imprint", ["Only entered synthetic information."]),
                    chapters=[("Überblick", ["First synthetic chapter."]),
                              ("Second chapter", ["Second synthetic chapter."])])
    path = tmp_path / "metadata.pdf"
    path.write_bytes(data)
    executable = shutil.which("pdfinfo")
    assert executable
    info = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic PDF
        [executable, str(path)], check=True, capture_output=True, text=True,
    )
    assert not info.stderr
    assert re.search(r"^Title:\s+" + re.escape(title), info.stdout, re.M)
    assert re.search(r"^Author:\s+" + re.escape(author), info.stdout, re.M)
    assert b"/Lang <FEFF00640065>" in data
    assert b"/Outlines" in data
    for heading in ("Überblick", "Second chapter"):
        encoded = b"<FEFF" + heading.encode("utf-16-be").hex().upper().encode() + b">"
        assert b"/Title " + encoded in data
    assert len(re.findall(rb"/Dest \[\d+ 0 R /XYZ", data)) == 2


def test_fontset_subsets_only_each_roles_drawn_characters():
    fonts = FontSet({"text": str(SERIF), "mono": str(MONO)})
    fonts.collect("text", "A")
    fonts.collect("mono", "B")
    assert fonts.face("text").has(ord("A"))
    assert not fonts.face("text").has(ord("B"))


def test_entered_header_placeholder_text_remains_literal(monkeypatch):
    _, _, pages = captured_layout(
        monkeypatch, report_pdf, title="Literal {folio}/{pages}", author="Author",
        markdown="Synthetic prose.", choice=CHOSEN,
    )
    # The cover stays bare; the body page carries the literal header and folio.
    assert not [line for line in pages[0].lines if line.y < 40]
    assert pages[1].lines[-2].text == "Literal {folio}/{pages} · Author"
    assert pages[1].lines[-1].text == "2/2"


def test_left_aligned_text_does_not_rely_on_unapplied_justification():
    fonts = FontSet({"text": str(SERIF)})
    doc = Document(fonts, page_size=(142, 300), margins=(25, 25, 25, 25))
    doc.add(Block("Wiesen " * 11, size=12))
    for page in doc._compose():
        for line in page.lines:
            assert text_width(line.text, fonts.face("text"), line.size) <= doc.measure + 0.01


@pytest.mark.skipif(not HAVE_FONTS, reason="requires DejaVu fonts")
def test_draft_notice_joins_running_header_in_every_layout(monkeypatch):
    _, _, report_pages = captured_layout(
        monkeypatch, report_pdf, title="Synthetic Report", author="Author",
        draft_notice="Confidential draft", markdown="Synthetic prose.", choice=CHOSEN,
    )
    assert report_pages[1].lines[-2].text == "Synthetic Report · Author · Confidential draft"

    _, _, book_pages = captured_layout(
        monkeypatch, book_pdf, title="Synthetic Book", author="Author",
        draft_notice="Confidential draft",
        chapters=[("One", ["Paragraph."]), ("Two", ["Another."])], choice=CHOSEN,
    )
    assert any(line.text == "Synthetic Book · Author · Confidential draft" for line in book_pages[1].lines)

    _, _, sheet_pages = captured_layout(
        monkeypatch, manuscript_pdf, title="Sheet", author="Author",
        draft_notice="Draft", chapters=[("One", ["Paragraph."])], choice=CHOSEN,
    )
    assert any(line.text == "Sheet · Author · Draft" for line in sheet_pages[0].lines)



@pytest.mark.parametrize("renderer,content_argument", [(book_pdf, "chapters"), (report_pdf, "markdown")])
def test_body_type_size_is_independent_of_manuscript_length(monkeypatch, renderer, content_argument):
    sizes = []
    for prose in ("Synthetic prose.", "Synthetic prose with ordinary readable words. " * 120):
        content = [("Chapter", [prose])] if content_argument == "chapters" else "# Section\n\n" + prose
        _, _, pages = captured_layout(monkeypatch, renderer, title="Title", choice=CHOSEN,
                                      **{content_argument: content})
        sizes.append(next(line.size for page in pages for line in page.lines
                          if line.text.startswith("Synthetic prose")))
    assert sizes[0] == sizes[1]
    assert sizes[0] >= 9.0


def test_editor_copy_has_annotation_margin_line_numbers_and_readable_leading(monkeypatch):
    from lixity import pdf_layouts

    _, doc, pages = captured_layout(
        monkeypatch, pdf_layouts.editor_pdf, title="Synthetic editor copy", choice=CHOSEN,
        chapters=[("Chapter", ["Readable manuscript paragraph for correction. " * 90])],
    )
    assert doc.width == pytest.approx(595.276)
    assert doc.height == pytest.approx(841.89)
    assert doc.right >= 96
    body = [line for page in pages for line in page.lines if line.text.startswith("Readable")]
    assert body and all(line.size == 12 for line in body)
    for page in pages:
        numbers = [line for line in page.lines if line.x < doc.left]
        if not page.decorated:
            assert not numbers
            continue
        assert numbers
        assert [int(line.text) for line in numbers] == list(range(1, len(numbers) + 1))
        for number in numbers:
            assert number.x + text_width(number.text, doc.fonts.face(number.role), number.size) < doc.left
        body_lines = [line for line in page.lines if doc.left <= line.x
                      and doc.bottom <= line.y <= doc.height - doc.top]
        assert all(line.word_spacing == 0 for line in body_lines)
        assert all(line.x + text_width(line.text, doc.fonts.face(line.role), line.size)
                   <= page.width - 96 + 0.01 for line in body_lines)
        assert all(number.x >= 0 for number in numbers)
        baselines = sorted({line.y for line in body_lines}, reverse=True)
        assert all(a - b >= 17.9 for a, b in pairwise(baselines))


def test_heading_stays_with_following_text_and_paragraphs_avoid_single_line_fragments():
    fonts = FontSet({"text": str(SERIF)})
    doc = Document(fonts, page_size=(250, 180), margins=(25, 25, 25, 25))
    doc.add(Block("Opening\n" * 5, size=12, leading=1.5))
    doc.add(Block("Subheading", size=14, keep_with_next=True))
    doc.add(Block("Following body paragraph. " * 10, size=12, leading=1.5, min_split_lines=2))
    pages = doc._compose()
    heading_page = next(page for page in pages if any(line.text == "Subheading" for line in page.lines))
    assert any(line.text.startswith("Following") for line in heading_page.lines)
    for page in pages:
        following = [line for line in page.lines if line.text and line.text != "Subheading"
                     and line.text != "Opening"]
        if following:
            assert len(following) >= 2


def test_inline_faces_use_actual_widths_and_preserve_words():
    from lixity.pdf_document import JUSTIFIED
    from tests.test_pdf_export import BOLD

    fonts = FontSet({"text": str(SERIF), "heading": str(BOLD)})
    doc = Document(fonts, page_size=(190, 230), margins=(25, 25, 25, 25))
    runs = [("Ordinary ", "text"), ("WWWWWW bold words ", "heading"),
            ("and ordinary prose repeated. " * 10, "text")]
    text = "".join(part for part, _ in runs)
    doc.add(Block(text, size=12, align=JUSTIFIED, runs=runs, min_split_lines=2))
    assert doc.render().startswith(b"%PDF")
    pages = doc._compose()
    words = []
    for page in pages:
        rows = {}
        for line in page.lines:
            rows.setdefault(line.y, []).append(line)
        for segments in rows.values():
            segments.sort(key=lambda line: line.x)
            words.extend("".join(line.text for line in segments).split())
            for line in segments:
                width = text_width(line.text, fonts.face(line.role), line.size)
                width += line.text.count(" ") * line.word_spacing
                assert line.x + width <= 165.01
    assert words == text.split()
    assert any(line.role == "heading" and "WWWW" in line.text for page in pages for line in page.lines)


@pytest.mark.parametrize("mode", ["book", "editor", "sheet"])
def test_semantic_manuscript_blocks_keep_structure_styles_and_explicit_breaks(monkeypatch, mode):
    from lixity import pdf_layouts
    from lixity.manuscript_document import ManuscriptBlock

    renderer = {"book": book_pdf, "editor": pdf_layouts.editor_pdf, "sheet": manuscript_pdf}[mode]
    chapters = [("Chapter", [
        ManuscriptBlock("paragraph", "Plain *emphasized* **strong** ***both*** and `code` words."),
        ManuscriptBlock("heading", "Subheading", level=3),
        ManuscriptBlock("paragraph", "Following paragraph."),
        ManuscriptBlock("quote", "Quoted words."),
        ManuscriptBlock("list_item", "- First listed item."),
        ManuscriptBlock("scene_break", "* * *"),
        ManuscriptBlock("code", "value = **literal**"),
        ManuscriptBlock("note", "[1] Endnote words."),
        ManuscriptBlock("page_break"),
        ManuscriptBlock("paragraph", "After explicit break."),
    ])]
    _, doc, pages = captured_layout(monkeypatch, renderer, title="Title", choice=CHOSEN,
                                    chapters=chapters)
    lines = [line for page in pages for line in page.lines]
    for word in ("emphasized", "strong", "both", "code", "Quoted words.",
                 "- First listed item.", "* * *", "value = **literal**", "[1] Endnote words."):
        assert any(word in line.text for line in lines)
    subhead_page = next(page for page in pages if any(line.text == "Subheading" for line in page.lines))
    assert any(line.text == "Following paragraph." for line in subhead_page.lines)
    before = next(i for i, page in enumerate(pages)
                  if any("Endnote words." in line.text for line in page.lines))
    after = next(i for i, page in enumerate(pages)
                 if any(line.text == "After explicit break." for line in page.lines))
    assert after > before
    if mode == "sheet":
        assert set(doc.fonts.paths) == {"mono"}
        for page in pages:
            body = [line for line in page.lines if doc.bottom <= line.y <= doc.height - doc.top]
            assert len(body) <= 30
            assert all(len(line.text) <= 60 for line in body)
    else:
        assert any(line.text == "emphasized" and line.role == "italic" for line in lines)
        assert any(line.text == "strong" and line.role == "heading" for line in lines)
        assert any(line.text == "both" and line.role == "bold_italic" for line in lines)
        assert any(line.text == "code" and line.role == "mono" for line in lines)
        assert any(line.text == "Quoted words." and line.x > doc.left for line in lines)


def test_unneeded_inline_font_roles_are_not_resolved(monkeypatch):
    from lixity import pdf_layouts

    monkeypatch.setenv("LIXITY_PDF_FONT_ITALIC", "/missing/italic.ttf")
    monkeypatch.setenv("LIXITY_PDF_FONT_BOLD_ITALIC", "/missing/bold-italic.ttf")
    monkeypatch.setenv("LIXITY_PDF_FONT_MONO", "/missing/mono.ttf")
    for renderer in (book_pdf, pdf_layouts.editor_pdf):
        assert renderer(title="Title", chapters=[("Chapter", ["Plain readable prose."])],
                        choice=FontChoice(serif=str(SERIF), serif_bold=str(SERIF))).startswith(b"%PDF")


@pytest.mark.parametrize("mode", ["book", "editor", "sheet"])
def test_chapter_labels_render_visible_inline_text_without_source_markers(monkeypatch, mode):
    from lixity import pdf_layouts

    renderer = {"book": book_pdf, "editor": pdf_layouts.editor_pdf, "sheet": manuscript_pdf}[mode]
    data, _, pages = captured_layout(
        monkeypatch, renderer, title="Title", choice=CHOSEN,
        chapters=[(r"**Night** and \textit{water}", ["Readable synthetic body."])],
    )
    visible = "".join(line.text for page in pages for line in page.lines)
    assert "Night and water" in visible
    assert "**" not in visible and r"\textit" not in visible
    if mode != "sheet":
        assert b"/Title <FEFF004E006900670068007400200061006E0064002000770061007400650072>" in data


def test_literal_code_blocks_preserve_indentation_and_explicit_lines(monkeypatch):
    from lixity.manuscript_document import ManuscriptBlock
    from lixity.pdf_layouts import editor_pdf

    _, _, pages = captured_layout(
        monkeypatch, editor_pdf, title="Title", choice=CHOSEN,
        chapters=[("Chapter", [ManuscriptBlock("code", "if ready:\n    nested = **literal**\n\tsecond = 2")])],
    )
    code = [line.text for page in pages for line in page.lines if line.role == "mono"]
    assert code == ["if ready:", "    nested = **literal**", "    second = 2"]


def test_sheet_character_limit_also_bounds_literal_whitespace_only_code(monkeypatch):
    from lixity.manuscript_document import ManuscriptBlock

    _, doc, pages = captured_layout(
        monkeypatch, manuscript_pdf, title="Title", choice=CHOSEN,
        chapters=[("Chapter", [ManuscriptBlock("code", " " * 140 + "\n    literal")])],
    )
    body = [line for page in pages for line in page.lines
            if doc.bottom <= line.y <= doc.height - doc.top]
    assert all(len(line.text) <= 60 for line in body)


def test_consecutive_headings_move_together_with_following_body():
    fonts = FontSet({"text": str(SERIF)})
    doc = Document(fonts, page_size=(200, 200), margins=(20, 20, 20, 20))
    for _ in range(5):
        doc.add(Block("Filler", size=12, leading=1.5))
    for heading in ("First heading", "Second heading"):
        doc.add(Block(heading, size=12, leading=1.5, space_after=4, keep_with_next=True))
    doc.add(Block("Following body with ordinary words " * 3,
                  size=12, leading=1.5, min_split_lines=2))
    pages = doc._compose()
    assert [line.text for line in pages[0].lines] == ["Filler"] * 5
    assert [line.text for line in pages[1].lines[:2]] == ["First heading", "Second heading"]
    assert pages[1].lines[2].text.startswith("Following body")
    assert len(pages[1].lines[2:]) >= 2
