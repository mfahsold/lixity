"""Font subsetting, PDF composition and the three published layouts."""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
import unittest
import unittest.mock
from pathlib import Path

import pytest

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
    def test_entirely_unsupported_character_set_is_reported(self):
        with self.assertRaises(FontError):
            subset_font(SERIF, {0x4E2D})

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
    def test_unsupported_visible_characters_fail_instead_of_drawing_missing_glyphs(self):
        fonts = FontSet({"text": str(SERIF)})
        document = Document(fonts)
        document.add(Block("Hallo 中"))
        with self.assertRaises(PdfError) as caught:
            document.render()
        self.assertIn("U+4E2D", str(caught.exception))
        self.assertIn("text", str(caught.exception))

    @needs_fonts
    def test_folios_embed_digits_absent_from_the_document_text(self):
        fonts = FontSet({"text": str(SERIF)})
        document = Document(fonts, page_size=(300, 180), margins=(20, 20, 20, 30))
        document.add(Block("Nur Buchstaben. " * 90))
        document.page_furniture("{folio}", role="text", size=9, position="footer-centre")
        pages = document._compose()
        self.assertGreater(len(pages), 1)
        for number, page in enumerate(pages, 1):
            self.assertEqual(page.lines[-1].text, str(number))
            self.assertFalse(fonts.unmapped("text", page.lines[-1].text))

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
    def test_report_sections_keep_tables_and_skip_thematic_breaks(self):
        from lixity.pdf_layouts import _report_sections, _TableData

        sections = _report_sections(
            "### 1.1 Kennzahlen\n\n| Metrik | Wert |\n| :--- | ---: |\n| **ASL** | 19,15 |\n"
            "\n---\n\n### 1.2 Rhythmus\n"
        )
        self.assertEqual([heading for heading, _items in sections], ["1.1 Kennzahlen", "1.2 Rhythmus"])
        table = sections[0][1][0]
        self.assertIsInstance(table, _TableData)
        self.assertEqual(table.header, ["Metrik", "Wert"])
        self.assertEqual(table.rows, [["ASL", "19,15"]])
        self.assertEqual(sections[1][1], [])

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
        data = book_pdf(title="Harbour Story", author="M. Fahsold", chapters=chapters, choice=CHOSEN)
        self.assertTrue(data.startswith(b"%PDF-1.4"))

    @needs_fonts
    def test_sheet_layout_keeps_the_thirty_by_sixty_grid(self):
        paragraph = ("Der Zug verlaesst Spoleto kurz nach Mitternacht. " * 12).strip()
        chapters = [("Kapitel 1", [paragraph]), ("Kapitel 2", [paragraph, paragraph])]
        data = manuscript_pdf(title="Harbour Story", chapters=chapters, choice=CHOSEN)
        self.assertTrue(data.startswith(b"%PDF-1.4"))
        pages = _composed_pages(data, body_only=True)
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
            title="Harbour Story", chapters=[("Kapitel", ["Ein kurzer Absatz."])], choice=CHOSEN
        )
        drawn = [line for page in _composed_pages(data, body_only=True) for line in page]
        self.assertTrue(drawn)
        for hexed in drawn:
            self.assertLessEqual(_character_count(hexed), NORM_COLUMNS)


def _composed_pages(data: bytes, *, body_only: bool = False) -> list[list[str]]:
    """Read back what was drawn on each page, without an external PDF tool.

    Content streams are written uncompressed, so the glyph hex strings can be
    decoded directly. Each PDF character code represents one source codepoint;
    the sheet's running furniture is outside its thirty-line body grid.
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
        matches = re.finditer(rb"1 0 0 1 [-.0-9]+ ([-.0-9]+) Tm\n<([0-9A-F]+)> Tj", stream)
        height = float(re.search(rb"/MediaBox \[0 0 [-.0-9]+ ([-.0-9]+)\]", body).group(1))
        drawn = [match.group(2) for match in matches
                 if not body_only or 54 <= float(match.group(1)) <= height - 54]
        pages.append(drawn)
    return pages


def _character_count(hexed: str) -> int:
    """Each four-digit PDF CID represents one source Unicode codepoint."""
    return len(hexed) // 4


@needs_fonts
class TypesettingTest(unittest.TestCase):
    def _lines(self, text, size=10.0, measure=300.0):
        from lixity.pdf_document import FontSet, fit_paragraph

        fonts = FontSet({"text": str(SERIF)})
        fonts.collect("text", text)
        return fit_paragraph(text, fonts.face("text"), size, measure)

    def test_no_line_falls_below_half_the_measure(self):
        text = ("Die Nachtigall übt und übt und übe lauthals im Wald. Die Mühe lohnt sich "
                "findet die Nachtigall. Sie findet ihren Gesang ganz wunderbar und singt "
                "bis tief in die Nacht hinein, während der Nebel über die Wiesen zieht. "
                "Am Ende sitzt sie still auf einem Ast und wartet darauf, dass jemand "
                "zuhört, was sie die ganze Zeit hindurch gesucht hat.")
        for line in self._lines(text):
            if line.text:
                self.assertGreaterEqual(line.slack + 300.0, 150.0)

    def test_last_line_is_free_of_any_length_penalty(self):
        # A heading must not be split: every word would be a line of its own.
        lines = self._lines("Kapitel 1", size=13.5, measure=300.0)
        self.assertEqual([line.text for line in lines], ["Kapitel 1"])

    def test_last_line_still_obeys_the_measure(self):
        lines = self._lines("Wiesen Wiesen", size=11.0, measure=70.0)
        self.assertEqual([line.text for line in lines], ["Wiesen", "Wiesen"])
        self.assertTrue(all(line.slack >= 0 for line in lines))

    def test_overlong_word_wraps_without_losing_characters(self):
        text = "Donaudampfschifffahrtsgesellschaftskapitän" * 4
        lines = self._lines(text, size=11.0, measure=200.0)
        self.assertGreater(len(lines), 1)
        self.assertEqual("".join(line.text for line in lines), text)
        self.assertTrue(all(line.slack >= 0 for line in lines))

    def test_pdf_writer_applies_negative_word_spacing(self):
        from lixity.pdf_document import Line, _show

        fonts = FontSet({"text": str(SERIF)})
        fonts.collect("text", "Wiesen Wiesen")
        operator = _show(
            Line("Wiesen Wiesen", 0, 0, 10, "text", word_spacing=-0.5),
            fonts.face("text"),
        )
        # PDF TJ adjustments use thousandths of the font size: +50 removes 0.5 pt.
        self.assertIn(" 50 ", operator)
        self.assertTrue(operator.endswith("] TJ"))

    def test_every_word_survives_the_break(self):
        text = ("Ich habe es noch nie geschafft ohne Druck ein Geschenk zu besorgen "
                "und laufe grundsätzlich am Vorabend los durch die volle Stadt.")
        expected = text.split(" ")
        joined = " ".join(line.text for line in self._lines(text))
        self.assertEqual(joined.split(" "), expected)

    def test_short_line_is_never_chosen_mid_paragraph(self):
        text = ("Die Pfändungsmitteilung landet nicht diskret in der Post sondern schlägt "
                "direkt in der Gehaltsabteilung der Questura auf und ich schiebe das "
                "Kuvert unter den Stapel alter Zeitungen.")
        lines = [line for line in self._lines(text) if line.text]
        self.assertTrue(all(len(line.text.split(" ")) > 1 for line in lines[:-1]))

    def test_grid_layout_never_exceeds_the_column_count(self):
        data = manuscript_pdf(
            title="Harbour Story",
            chapters=[("Kapitel", ["Ein kurzer Absatz fuer den Normbogen." * 4])],
            choice=CHOSEN,
        )
        for page in _composed_pages(data, body_only=True):
            for drawn in page:
                self.assertLessEqual(_character_count(drawn), NORM_COLUMNS)


@pytest.mark.native_pdf
@needs_fonts
class NativePdfTest(unittest.TestCase):
    @unittest.skipUnless(
        shutil.which("pdfinfo") and shutil.which("pdftotext") and shutil.which("pdffonts"),
        "requires Poppler pdfinfo, pdftotext and pdffonts",
    )
    def test_book_round_trips_unicode_long_words_and_page_numbers(self):
        pdfinfo = shutil.which("pdfinfo")
        pdftotext = shutil.which("pdftotext")
        pdffonts = shutil.which("pdffonts")
        if not (pdfinfo and pdftotext and pdffonts):
            self.skipTest("Poppler is optional tooling, not a Lixity dependency")
        paragraph = "ÄÖÜ äöü ß – „Grüße“ begleiten die Erzählung. " * 100
        compound = "Donaudampfschifffahrtsgesellschaftskapitän" * 4
        data = book_pdf(
            title="Erfundene Geschichten",
            chapters=[("Über den Fluss", [paragraph, compound])],
            choice=CHOSEN,
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reader.pdf"
            path.write_bytes(data)
            info = subprocess.run(  # noqa: S603 - resolved Poppler executable, synthetic local input
                [pdfinfo, str(path)], check=True, capture_output=True, text=True,
            )
            text = subprocess.run(  # noqa: S603 - resolved Poppler executable, synthetic local input
                [pdftotext, "-layout", str(path), "-"],
                check=True, capture_output=True, text=True,
            )
            fonts = subprocess.run(  # noqa: S603 - resolved Poppler executable, synthetic local input
                [pdffonts, str(path)], check=True, capture_output=True, text=True,
            )
        self.assertFalse(info.stderr or text.stderr or fonts.stderr)
        self.assertRegex(info.stdout, r"Page size:\s+419\.528 x 595\.276 pts")
        self.assertEqual(text.stdout.count("Grüße"), 100)
        self.assertRegex(fonts.stdout, r"CID TrueType\s+Identity-H\s+yes\s+\w+\s+yes")
        pages = text.stdout.split("\f")[:-1]
        self.assertGreater(len(pages), 1)
        body_pages = [pages[0]]
        for number, page in enumerate(pages[1:], 2):
            lines = page.strip().splitlines()
            self.assertEqual(lines[-1].strip(), str(number))
            self.assertEqual(lines[0].strip(), "Erfundene Geschichten")
            body_pages.append("\n".join(lines[1:-1]))
        self.assertIn(compound, "".join("\n".join(body_pages).split()))

    @unittest.skipUnless(shutil.which("pdftotext"), "requires Poppler pdftotext")
    def test_report_tables_align_repeat_and_never_leak_markup(self):
        pdftotext = shutil.which("pdftotext")
        if not pdftotext:
            self.skipTest("requires Poppler pdftotext")
        rows = [f"| Kennzahl {index:02d} | {index}.000 | Beschreibung {index} |"
                for index in range(1, 61)]
        markdown = (
            "### 1.1 Kennzahlen\n\n| Metrik | Wert | Interpretationsgrenze |\n"
            "| :--- | ---: | :--- |\n" + "\n".join(rows)
            + "\n\n---\n\n### 1.2 Rhythmus\n\n| Signal | Wert |\n| :--- | ---: |\n"
            "| Guiraud (V/√N) | 36,00 |\n"
        )
        data = report_pdf(title="Synthetischer Bericht", author="Synthetische Autorin",
                          markdown=markdown, choice=CHOSEN)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.pdf"
            path.write_bytes(data)
            result = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic local input
                [pdftotext, "-layout", str(path), "-"],
                check=True, capture_output=True, text=True,
            )
        self.assertFalse(result.stderr)
        pages = result.stdout.split("\f")[:-1]
        self.assertGreaterEqual(len(pages), 3)
        # Cover page: title and author only, no section and no table.
        self.assertIn("Synthetischer Bericht", pages[0])
        self.assertNotIn("Kennzahlen", pages[0])
        self.assertIn("1.1 Kennzahlen", pages[1])
        body = "\n".join(pages[1:])
        self.assertGreaterEqual(body.count("Metrik"), 2, "the header row repeats after a page break")
        self.assertIn("Interpretationsgrenze", body, "header words are never broken")
        self.assertNotIn("|", body)
        self.assertNotIn("\\sqrt", body)
        self.assertIn("V/√N", body)
        # A numeric column stays aligned: right-aligned values end on one edge.
        ends = []
        for marker in ("01", "02", "30"):
            line = next(line for line in body.splitlines() if f"Kennzahl {marker} " in line)
            token = next(word for word in line.split() if word.endswith(".000"))
            ends.append(line.index(token) + len(token))
        self.assertEqual(len(set(ends)), 1, "right-aligned values share one edge")
        # Rows stay whole: a label and its value never split across pages.
        page_of_last = next(page for page in pages if "Kennzahl 60 " in page)
        self.assertIn("60.000", page_of_last)
        self.assertIn("Beschreibung 60", page_of_last)

    @unittest.skipUnless(shutil.which("pdftotext"), "requires Poppler pdftotext")
    def test_default_report_fonts_preserve_generated_math_symbols(self):
        pdftotext = shutil.which("pdftotext")
        if not pdftotext:
            self.skipTest("requires Poppler pdftotext")
        data = report_pdf(title="Synthetic report", markdown="Standardized signal: √n ≤ 2.")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.pdf"
            path.write_bytes(data)
            result = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic local input
                [pdftotext, "-layout", str(path), "-"],
                check=True, capture_output=True, text=True,
            )
        self.assertFalse(result.stderr)
        self.assertIn("√n ≤ 2.", result.stdout)


if __name__ == "__main__":
    unittest.main()


@pytest.mark.native_pdf
@needs_fonts
@pytest.mark.parametrize("mode", ["book", "editor", "sheet"])
@pytest.mark.skipif(not shutil.which("pdftotext") or not shutil.which("pdffonts"),
                    reason="requires Poppler pdftotext and pdffonts")
def test_semantic_pdf_round_trip_keeps_rich_text_and_embeds_real_styles(tmp_path, mode):
    from lixity.manuscript_document import ManuscriptBlock
    from lixity.pdf_layouts import editor_pdf

    renderer = {"book": book_pdf, "editor": editor_pdf, "sheet": manuscript_pdf}[mode]
    italic = next((path for path in (FONTS / "DejaVuSerif-Italic.ttf",
                                    FONTS.parent / "liberation/LiberationSerif-Italic.ttf")
                   if path.is_file()), None)
    bold_italic = next((path for path in (FONTS / "DejaVuSerif-BoldItalic.ttf",
                                         FONTS.parent / "liberation/LiberationSerif-BoldItalic.ttf")
                        if path.is_file()), None)
    if italic is None or bold_italic is None:
        pytest.skip("requires real italic and bold italic TrueType fonts")
    choice = FontChoice(serif=str(SERIF), serif_bold=str(BOLD), mono=str(MONO),
                        serif_italic=str(italic), serif_bold_italic=str(bold_italic))
    path = tmp_path / f"synthetic-{mode}.pdf"
    path.write_bytes(renderer(title="Synthetic manuscript", choice=choice, chapters=[
        ("Chapter", [
            ManuscriptBlock("paragraph", "Café *emphasis* **strong** ***combined*** `inline` words."),
            ManuscriptBlock("heading", "Subheading"),
            ManuscriptBlock("quote", "Quoted synthetic words."),
            ManuscriptBlock("list_item", "- Listed synthetic words."),
            ManuscriptBlock("scene_break", "* * *"),
            ManuscriptBlock("code", "literal = **source**"),
            ManuscriptBlock("note", "[1] Synthetic endnote."),
        ]),
    ]))
    pdftotext, pdffonts = shutil.which("pdftotext"), shutil.which("pdffonts")
    assert pdftotext and pdffonts
    extracted = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic local PDF
        [pdftotext, "-layout", str(path), "-"], check=True, capture_output=True, text=True,
    )
    embedded = subprocess.run(  # noqa: S603 - resolved Poppler, synthetic local PDF
        [pdffonts, str(path)], check=True, capture_output=True, text=True,
    )
    assert not extracted.stderr and not embedded.stderr
    prose = " ".join(extracted.stdout.split())
    for expected in ("Café emphasis strong combined inline words.", "Subheading",
                     "Quoted synthetic words.", "- Listed synthetic words.",
                     "literal = **source**", "[1] Synthetic endnote."):
        assert expected in prose
    assert re.search(r"(?:^|\n)\s*(?:\d+\s+)?\*\s*\*\s*\*\s*(?:\n|$)", extracted.stdout)
    if mode == "sheet":
        assert "DejaVuSansMono" in embedded.stdout
        assert "DejaVuSerif" not in embedded.stdout
    else:
        assert "Serif-Italic" in embedded.stdout
        assert "Serif-BoldItalic" in embedded.stdout
        assert "DejaVuSerif-Bold" in embedded.stdout
        assert "DejaVuSansMono" in embedded.stdout


@needs_fonts
@pytest.mark.parametrize("style,field", [("*emphasis*", "serif_italic"),
                                         ("***combined***", "serif_bold_italic")])
def test_missing_inline_style_font_is_explicit_only_when_the_style_is_used(style, field):
    from lixity.manuscript_document import ManuscriptBlock

    choice = FontChoice(serif=str(SERIF), serif_bold=str(BOLD), **{field: "/missing/style.ttf"})
    assert book_pdf(title="Title", choice=choice,
                    chapters=[("Chapter", ["Plain manuscript prose."])]).startswith(b"%PDF")
    with pytest.raises(FontUnavailable, match=r"/missing/style\.ttf"):
        book_pdf(title="Title", choice=choice,
                 chapters=[("Chapter", [ManuscriptBlock("paragraph", style)])])
