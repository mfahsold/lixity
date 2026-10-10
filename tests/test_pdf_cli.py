"""The ``lixity pdf`` command and the binary artifact writer it relies on."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from lixity.cli import main
from lixity.io import FileUtils
from lixity.pdf_layouts import NORM_COLUMNS, NORM_LINES
from tests.test_pdf_export import _character_count, _composed_pages

FONTS = Path("/usr/share/fonts/truetype/dejavu")
SERIF = str(FONTS / "DejaVuSerif.ttf")
BOLD = str(FONTS / "DejaVuSerif-Bold.ttf")
MONO = str(FONTS / "DejaVuSansMono.ttf")
HAVE_FONTS = all(Path(path).is_file() for path in (SERIF, BOLD, MONO))

MANUSCRIPT = (
    "# Weglaufen\n\n"
    "Ein erster Absatz mit ÄÖÜ, einem Gedanken und einem Fragezeichen?\n\n"
    "Zweiter Absatz mit etwas mehr Text, damit der Umbruch arbeiten muss.\n\n"
    "## Kapitel 2\n\n"
    "Noch ein Absatz.\n"
)


def _fonts() -> list[str]:
    return ["--serif-font", SERIF, "--bold-font", BOLD, "--mono-font", MONO]


class BinaryWriteTest(unittest.TestCase):
    def test_bytes_are_written_and_left_alone_on_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifact.bin"
            self.assertTrue(FileUtils.atomic_write_bytes_if_changed(str(target), b"\x00\x01\x02"))
            self.assertEqual(target.read_bytes(), b"\x00\x01\x02")
            self.assertFalse(FileUtils.atomic_write_bytes_if_changed(str(target), b"\x00\x01\x02"))
            self.assertTrue(FileUtils.atomic_write_bytes_if_changed(str(target), b"\x03"))

    def test_binary_content_survives_a_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "nested" / "artifact.bin"
            payload = bytes(range(256))
            FileUtils.atomic_write_bytes_if_changed(str(target), payload)
            self.assertEqual(target.read_bytes(), payload)

    def test_unreadable_target_is_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "artifact.bin"
            target.write_bytes(b"stale")
            self.assertTrue(FileUtils.atomic_write_bytes_if_changed(str(target), b"fresh"))


@unittest.skipUnless(HAVE_FONTS, "requires the DejaVu font family")
class PdfCommandTest(unittest.TestCase):
    def _workspace(self) -> tuple[tempfile.TemporaryDirectory, Path]:
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        manuscript = Path(directory.name) / "manuscript.md"
        manuscript.write_text(MANUSCRIPT, encoding="utf-8")
        return directory, manuscript

    def test_each_layout_writes_a_pdf(self):
        for layout in ("report", "book", "sheet"):
            with self.subTest(layout=layout):
                directory, manuscript = self._workspace()
                command = [
                    "pdf",
                    str(manuscript),
                    "--language",
                    "de",
                    "--layout",
                    layout,
                    *_fonts(),
                ]
                self.assertEqual(main(command), 0)
                produced = Path(directory.name) / f"manuscript-{layout}.pdf"
                self.assertTrue(produced.is_file())
                self.assertTrue(produced.read_bytes().startswith(b"%PDF-1.4"))

    def test_repeat_run_is_idempotent(self):
        directory, manuscript = self._workspace()
        command = ["pdf", str(manuscript), "--language", "de", "--layout", "book", *_fonts()]
        produced = Path(directory.name) / "manuscript-book.pdf"
        self.assertEqual(main(command), 0)
        stamp = produced.stat().st_mtime_ns
        self.assertEqual(main(command), 0)
        self.assertEqual(produced.stat().st_mtime_ns, stamp)

    def test_explicit_output_path_is_honoured(self):
        directory, manuscript = self._workspace()
        target = Path(directory.name) / "out" / "reader.pdf"
        command = [
            "pdf",
            str(manuscript),
            "--language",
            "de",
            "--layout",
            "book",
            "-o",
            str(target),
            *_fonts(),
        ]
        self.assertEqual(main(command), 0)
        self.assertTrue(target.is_file())

    def test_sheet_layout_keeps_the_grid(self):
        directory, manuscript = self._workspace()
        command = ["pdf", str(manuscript), "--language", "de", "--layout", "sheet", *_fonts()]
        self.assertEqual(main(command), 0)
        data = (Path(directory.name) / "manuscript-sheet.pdf").read_bytes()
        for page in _composed_pages(data):
            self.assertLessEqual(len(page), NORM_LINES)
            for drawn in page:
                self.assertLessEqual(_character_count(drawn), NORM_COLUMNS)

    def test_book_layout_carries_the_author_line(self):
        directory, manuscript = self._workspace()
        command = [
            "pdf",
            str(manuscript),
            "--language",
            "de",
            "--layout",
            "book",
            "--author",
            "Testautorin",
            *_fonts(),
        ]
        self.assertEqual(main(command), 0)
        self.assertTrue((Path(directory.name) / "manuscript-book.pdf").is_file())

    def test_missing_manuscript_is_reported(self):
        self.assertEqual(main(["pdf", "/nonexistent/manuscript.md", "--layout", "report"]), 1)

    def test_unknown_font_file_fails_without_writing(self):
        directory, manuscript = self._workspace()
        command = [
            "pdf",
            str(manuscript),
            "--language",
            "de",
            "--layout",
            "book",
            "--serif-font",
            str(Path(directory.name) / "absent.ttf"),
        ]
        self.assertEqual(main(command), 1)
        self.assertFalse((Path(directory.name) / "manuscript-book.pdf").exists())

    def test_command_accepts_help(self):
        with self.assertRaises(SystemExit) as caught:
            main(["pdf", "--help"])
        self.assertEqual(caught.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
