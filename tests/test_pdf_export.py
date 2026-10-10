"""Font subsetting, PDF composition and the three published layouts."""

from __future__ import annotations

import shutil
import unittest
import unittest.mock
from pathlib import Path

from lixity.pdf_document import Block, Document, FontSet, PdfError, break_lines
from lixity.pdf_font import FontError, subset_font
from lixity.pdf_layouts import (
    NORM_COLUMNS,
    NORM_LINES,
    FontChoice,
    FontUnavailable,
    book_pdf,
    manuscript_pdf,
    report_pdf,
    resolve_fonts,
)

FONTS = Path("/usr/share/fonts/truetype/dejavu")
SERIF = FONTS / "DejaVuSerif.ttf"
BOLD = FONTS / "DejaVuSerif-Bold.ttf"
MONO = FONTS / "DejaVuSansMono.ttf"

CHOSEN = FontChoice(serif=str(SERIF), serif_bold=str(BOLD), mono=str(MONO))
HAVE_FONTS = SERIF.is_file() and BOLD.is_file() and MONO.is_file()
needs_fonts = unittest.skipUnless(HAVE_FONTS, "requires the DejaVu font family")


class SubsetFontTest(unittest.TestCase):
    @needs_fonts
    def test_subset_keeps_only_requested_characters(self):
        subset = subset_font(SERIF, {ord("A"), ord("B"), ord(" ")})
        self.assertEqual(set(subset.glyph_ids), {ord("A"), ord("B"), ord(" ")})
        self.assertLess(len(subset.data), SERIF.stat().st_size)

    @needs_fonts
    def test_advances_are_reported_per_mille_of_the_em(self):
        subset = subset_font(SERIF, {ord("A"), ord(" ")})
        self.assertGreater(subset.advance(ord("A")), 0)
        self.assertGreater(subset.advance(ord(" ")), 0)
        self.assertEqual(subset.advance(0x4E2D), 0)

    @needs_fonts
    def test_unmapped_characters_are_absent(self):
        subset = subset_font(SERIF, {ord("A")})
        self.assertFalse(subset.has(ord("Z")))

    def test_missing_file_is_reported(self):
        with self.assertRaises(FileNotFoundError):
            subset_font(Path("/nonexistent/font.ttf"), {ord("A")})

    def test_truncated_file_is_reported(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            broken = Path(directory) / "broken.ttf"
            broken.write_bytes(SERIF.read_bytes()[:200] if HAVE_FONTS else b"\x00\x01\x00\x00")
            with self.assertRaises(FontError):
                subset_font(broken, {ord("A")})

    @needs_fonts
    def test_non_font_input_is_rejected(self):
        import tempfile

        with tempfile.TemporaryDirectory() as directory:
            junk = Path(directory) / "junk.ttf"
            junk.write_bytes(b"%PDF-1.4 this is not a font at all, not even close")
            with self.assertRaises(FontError):
                subset_font(junk, {ord("A")})

    @needs_fonts
    def test_empty_character_set_is_refused(self):
        with self.assertRaises(FontError):
            subset_font(SERIF, set())

    @needs_fonts
    def test_subset_reopens_as_a_font(self):
        import tempfile

        subset = subset_font(SERIF, {ord("A"), ord("B"), ord(" ")})
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "subset.ttf"
            path.write_bytes(subset.data)
            # A broken checksum or table length is silently tolerated by some
            # readers and fatal in others, so it must survive a re-read.
            again = subset_font(path, {ord("A"), ord("B"), ord(" ")})
            self.assertEqual(set(again.glyph_ids), {ord("A"), ord("B"), ord(" ")})


class FontResolutionTest(unittest.TestCase):
    def test_explicit_choices_win(self):
        roles = resolve_fonts({"text": str(SERIF), "heading": str(BOLD), "mono": str(MONO)})
        self.assertEqual(roles["text"], str(SERIF))

    def test_missing_configuration_names_the_setting(self):
        with self.assertRaises(FontUnavailable) as caught:
            resolve_fonts(
                {"text": "/nonexistent/serif.ttf", "heading": str(BOLD), "mono": str(MONO)}
            )
        self.assertIn("/nonexistent/serif.ttf", str(caught.exception))

    def test_absent_font_is_named_with_an_example(self):
        import os

        import lixity.pdf_layouts as layouts

        environment = dict(os.environ)
        for key in list(environment):
            if key.startswith("LIXITY_PDF_FONT_"):
                del environment[key]
        with (unittest.mock.patch.dict(os.environ, environment, clear=True),
              unittest.mock.patch.object(layouts, "_installed_fonts", dict),
              self.assertRaises(FontUnavailable) as caught):
            resolve_fonts({})
        message = str(caught.exception)
        self.assertIn("LIXITY_PDF_FONT_TEXT", message)
        self.assertIn(".ttf", message)


class LineBreakingTest(unittest.TestCase):
    @needs_fonts
    def test_lines_never_exceed_the_measure(self):
        fonts = FontSet({"text": str(SERIF)})
        text = "Ein Absatz mit vielen Wörtern, der über mehrere Zeilen umbrechen muss. " * 4
        fonts.collect("text", text)
        face = fonts.face("text")
        from lixity.pdf_document import text_width

        for line in break_lines(text, face, 11.0, 200.0):
            self.assertLessEqual(text_width(line, face, 11.0), 200.0)

    @needs_fonts
    def test_explicit_newlines_always_break(self):
        fonts = FontSet({"text": str(SERIF)})
        fonts.collect("text", "eins\nzwei")
        self.assertEqual(
            break_lines("eins\nzwei", fonts.face("text"), 11.0, 500.0), ["eins", "zwei"]
        )

    @needs_fonts
    def test_unknown_role_is_refused(self):
        fonts = FontSet({"text": str(SERIF)})
        with self.assertRaises(PdfError):
            fonts.collect("missing", "text")

    @needs_fonts
    def test_empty_document_is_refused(self):
        with self.assertRaises(PdfError):
            FontSet({"text": str(SERIF)}).build()

    def test_missing_font_path_is_refused(self):
        with self.assertRaises(PdfError):
            FontSet({"text": ""})


class ComposedDocumentTest(unittest.TestCase):
    @needs_fonts
    def test_pdf_is_structurally_complete(self):
        fonts = FontSet({"text": str(SERIF)})
        document = Document(fonts)
        document.add(Block("Hallo Welt", role="text", size=12))
        data = document.render()
        self.assertTrue(data.startswith(b"%PDF-1.4"))
        self.assertTrue(data.rstrip().endswith(b"%%EOF"))
        self.assertIn(b"/Type /Catalog", data)
        self.assertIn(b"startxref", data)

    @needs_fonts
    def test_compressed_font_declares_its_filter(self):
        fonts = FontSet({"text": str(SERIF)})
        document = Document(fonts)
        document.add(Block("Hallo", role="text", size=12))
        data = document.render()
        # A zlib stream without /Filter is handed to the font loader unchanged
        # and every reader rejects the embedded font.
        self.assertIn(b"/FontFile2", data)
        self.assertEqual(data.count(b"/Filter /FlateDecode"), 1)

    @needs_fonts
    def test_long_text_paginates(self):
        fonts = FontSet({"text": str(SERIF)})
        document = Document(fonts)
        document.add(Block("Ein Absatz. " * 400, role="text", size=11))
        self.assertGreater(len(document.render()), 0)
        pages = document._compose()
        self.assertGreater(len(pages), 1)

    @needs_fonts
    def test_text_collected_after_a_build_is_still_embedded(self):
        fonts = FontSet({"text": str(SERIF)})
        fonts.collect("text", "A")
        fonts.face("text")
        fonts.collect("text", "Ω")
        self.assertTrue(fonts.face("text").has(ord("Ω")))


class LayoutTest(unittest.TestCase):
    @needs_fonts
    def test_report_renders_unicode(self):
        data = report_pdf(
            title="Stilbericht",
            markdown="# Überblick\n\nÄÖÜ äöü ß «» … ½ № €",
            subtitle="Analyse",
            choice=CHOSEN,
        )
        self.assertTrue(data.startswith(b"%PDF-1.4"))
        self.assertIn(b"/ToUnicode", data)

    @needs_fonts
    def test_book_layout_paginates_chapters(self):
        chapters = [
            ("Kapitel 1", ["Ein Absatz. " * 200]),
            ("Kapitel 2", ["Noch ein Absatz. " * 200]),
        ]
        data = book_pdf(title="weglaufen", author="M. Fahsold", chapters=chapters, choice=CHOSEN)
        self.assertTrue(data.startswith(b"%PDF-1.4"))

    @needs_fonts
    def test_sheet_layout_keeps_the_thirty_by_sixty_grid(self):
        paragraph = ("Der Zug verlaesst Spoleto kurz nach Mitternacht. " * 12).strip()
        chapters = [("Kapitel 1", [paragraph]), ("Kapitel 2", [paragraph, paragraph])]
        data = manuscript_pdf(title="weglaufen", chapters=chapters, choice=CHOSEN)
        self.assertTrue(data.startswith(b"%PDF-1.4"))
        pages = _composed_pages(data)
        self.assertGreater(len(pages), 1)
        for page in pages:
            self.assertLessEqual(len(page), NORM_LINES)
            for drawn in page:
                self.assertLessEqual(_character_count(drawn), NORM_COLUMNS)

    @needs_fonts
    def test_sheet_strips_markdown_markers_from_the_grid(self):
        from lixity.pdf_layouts import _plain

        self.assertEqual(_plain("**Fett** und _kursiv_."), "Fett und kursiv.")

    @needs_fonts
    def test_sheet_draws_only_grid_characters(self):
        data = manuscript_pdf(
            title="weglaufen", chapters=[("Kapitel", ["Ein kurzer Absatz."])], choice=CHOSEN
        )
        drawn = [line for page in _composed_pages(data) for line in page]
        self.assertTrue(drawn)
        for hexed in drawn:
            self.assertLessEqual(_character_count(hexed), NORM_COLUMNS)


def _composed_pages(data: bytes) -> list[list[str]]:
    """Read back what was drawn on each page, without an external PDF tool.

    Content streams are written uncompressed, so the glyph hex strings can be
    decoded directly. Each glyph is one UTF-16 code unit, which is exactly the
    character count the submission grid is defined in.
    """
    import re

    objects = {
        int(match.group(1)): match.group(2)
        for match in re.finditer(rb"(\d+) 0 obj\n(.*?)\nendobj", data, re.S)
    }
    pages: list[list[str]] = []
    for body in objects.values():
        if not body.startswith(b"<< /Type /Page ") or b"/Contents" not in body:
            continue
        reference = int(re.search(rb"/Contents (\d+) 0 R", body).group(1))
        stream = re.search(rb"stream\n(.*?)\nendstream", objects[reference], re.S).group(1)
        drawn = [match.group(1) for match in re.finditer(rb"Tm\n<([0-9A-F]+)> Tj", stream)]
        pages.append(drawn)
    return pages


def _character_count(hexed: str) -> int:
    """One glyph is one UTF-16 code unit, so the hex length is the character count."""
    return len(hexed) // 4


class ToolchainAvailableTest(unittest.TestCase):
    def test_poppler_can_validate_generated_pdfs(self):
        pdfinfo = shutil.which("pdfinfo")
        pdftotext = shutil.which("pdftotext")
        if not (pdfinfo and pdftotext):
            self.skipTest("Poppler is optional tooling, not a Lixity dependency")


if __name__ == "__main__":
    unittest.main()
