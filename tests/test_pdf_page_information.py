"""Shared pagination, navigation and publication metadata stay readable."""

from __future__ import annotations

import re
import shutil
import struct
import subprocess

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


@pytest.mark.parametrize("function,kwargs", [
    (manuscript_pdf, {"chapters": [("Chapter", ["i" * 1000] * 6)]}),
    (report_pdf, {"markdown": "# Report\n\n" + "\n\n".join(["Synthetic prose. " * 100] * 5)}),
])
def test_sheet_report_headers_are_bounded_and_footer_contains_total(monkeypatch, function, kwargs):
    _, doc, pages = captured_layout(
        monkeypatch, function, title="A very long synthetic title " * 60,
        author="A very long synthetic author " * 30, choice=CHOSEN, **kwargs,
    )
    assert len(pages) > 1
    for index, page in enumerate(pages, 1):
        headers = [line for line in page.lines if line.y > page.height - doc.top]
        footers = [line for line in page.lines if line.y < doc.bottom]
        assert len(headers) == 1 and len(footers) == 1
        assert footers[0].text == f"{index}/{len(pages)}"
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
    assert pages[0].lines[-2].text == "Literal {folio}/{pages} · Author"
    assert pages[0].lines[-1].text == "1/1"


def test_left_aligned_text_does_not_rely_on_unapplied_justification():
    fonts = FontSet({"text": str(SERIF)})
    doc = Document(fonts, page_size=(142, 300), margins=(25, 25, 25, 25))
    doc.add(Block("Wiesen " * 11, size=12))
    for page in doc._compose():
        for line in page.lines:
            assert text_width(line.text, fonts.face("text"), line.size) <= doc.measure + 0.01
