"""Tests for Word (.docx) manuscript import and loss reporting."""

from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from lixity import manuscript_import
from lixity.manuscript_import import convert_docx, preview_docx


def _create_synthetic_docx_bytes() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
        doc_xml = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
        <w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
          <w:body>
            <w:p>
              <w:pPr><w:pStyle w:val="Title"/></w:pPr>
              <w:r><w:t>The Mariner's Gate</w:t></w:r>
            </w:p>
            <w:p>
              <w:pPr><w:pStyle w:val="Heading1"/></w:pPr>
              <w:r><w:t>Chapter 1: The Harbour</w:t></w:r>
            </w:p>
            <w:p>
              <w:r><w:t>The cold wind blew over the quay. </w:t></w:r>
              <w:r><w:rPr><w:b/></w:rPr><w:t>Mira stood</w:t></w:r>
              <w:r><w:t> by the lantern, watching </w:t></w:r>
              <w:r><w:rPr><w:i/></w:rPr><w:t>the grey water</w:t></w:r>
              <w:r><w:t>.</w:t></w:r>
            </w:p>
            <w:p>
              <w:r><w:t>* * *</w:t></w:r>
            </w:p>
            <w:p>
              <w:pPr><w:pStyle w:val="Quote"/></w:pPr>
              <w:r><w:t>A sailor never speaks of tomorrow.</w:t></w:r>
            </w:p>
            <w:tbl>
              <w:tr><w:tc><w:p><w:r><w:t>Cell 1</w:t></w:r></w:p></w:tc></w:tr>
            </w:tbl>
            <w:p>
              <w:r><w:drawing/></w:r>
              <w:r><w:t>The bell rang twice.</w:t></w:r>
            </w:p>
          </w:body>
        </w:document>"""
        zf.writestr("word/document.xml", doc_xml)
    return buf.getvalue()


class ManuscriptImportTests(unittest.TestCase):
    def test_preview_accepts_empty_document_and_exact_byte_budgets(self) -> None:
        xml = b'<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body/></w:document>'
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", xml)
        content = buffer.getvalue()
        with patch.multiple(manuscript_import, MAX_DOCX_SOURCE_BYTES=len(content),
                            MAX_DOCX_MEMBERS=1, MAX_DOCX_XML_BYTES=len(xml),
                            MAX_DOCX_OUTPUT_BYTES=0):
            self.assertEqual(preview_docx(content).markdown, "")

    def test_preview_accepts_compressible_text_within_byte_budgets(self) -> None:
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
               '<w:body><w:p><w:r><w:t>' + "a" * 10000 + '</w:t></w:r></w:p></w:body></w:document>')
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("word/document.xml", xml)
        with patch.object(manuscript_import, "MAX_DOCX_OUTPUT_BYTES", 10001):
            self.assertEqual(preview_docx(buffer.getvalue()).markdown, "a" * 10000 + "\n")

    def test_preview_rejects_source_that_grows_after_metadata_check(self) -> None:
        content = _create_synthetic_docx_bytes()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "growing.docx"
            source.write_bytes(content)
            original_fstat = os.fstat

            def grow_source(descriptor: int) -> os.stat_result:
                metadata = original_fstat(descriptor)
                with source.open("ab") as stream:
                    stream.write(b"more bytes")
                return metadata

            with patch.object(manuscript_import, "MAX_DOCX_SOURCE_BYTES", len(content)), patch(
                "lixity.manuscript_import.os.fstat", side_effect=grow_source,
            ), self.assertRaisesRegex(ValueError, "source.*safety ceiling"):
                preview_docx(source)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Named pipes require POSIX")
    def test_preview_rejects_fifo_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.docx"
            os.mkfifo(source)
            result = subprocess.run(  # noqa: S603 - Fixed interpreter and synthetic fixture path.
                [sys.executable, "-c", "from lixity.manuscript_import import preview_docx\n"
                 "import sys\ntry:\n preview_docx(sys.argv[1])\n"
                 "except ValueError as exc:\n print(exc)\nelse:\n sys.exit(1)\n", str(source)],
                capture_output=True, text=True, check=False, timeout=3,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("regular file", result.stdout)

    def test_preview_bounds_decompressed_read_before_xml_parse(self) -> None:
        original_read = zipfile.ZipExtFile.read
        requested: list[int] = []

        def read_xml(stream: zipfile.ZipExtFile, size: int = -1) -> bytes:
            requested.append(size)
            return original_read(stream, size)

        with patch.object(manuscript_import, "MAX_DOCX_XML_BYTES", 128), patch.object(
            zipfile.ZipExtFile, "read", read_xml,
        ), self.assertRaisesRegex(ValueError, "XML.*safety ceiling"):
            preview_docx(_create_synthetic_docx_bytes())
        self.assertEqual(requested, [129])

    def test_preview_rejects_source_byte_budget_for_bytes_and_paths(self) -> None:
        content = _create_synthetic_docx_bytes()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.docx"
            source.write_bytes(content)
            with patch.object(manuscript_import, "MAX_DOCX_SOURCE_BYTES", len(content) - 1,
                              create=True):
                for value in (content, source):
                    with self.subTest(path=isinstance(value, Path)), self.assertRaisesRegex(
                        ValueError, "source.*safety ceiling",
                    ):
                        preview_docx(value)

    def test_preview_rejects_nonregular_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory, self.assertRaisesRegex(ValueError, "regular file"):
            preview_docx(Path(directory))

    def test_preview_rejects_archive_member_budget(self) -> None:
        with patch.object(manuscript_import, "MAX_DOCX_MEMBERS", 1, create=True), self.assertRaisesRegex(
            ValueError, "member.*safety ceiling",
        ):
            preview_docx(_create_synthetic_docx_bytes())

    def test_preview_rejects_actual_document_xml_byte_budget(self) -> None:
        content = _create_synthetic_docx_bytes()
        with patch.object(manuscript_import, "MAX_DOCX_XML_BYTES", 128, create=True), self.assertRaisesRegex(
            ValueError, "XML.*safety ceiling",
        ):
            preview_docx(content)

    def test_preview_rejects_converted_utf8_byte_budget(self) -> None:
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as archive:
            archive.writestr("word/document.xml", '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>雪雪</w:t></w:r></w:p></w:body></w:document>')
        with patch.object(manuscript_import, "MAX_DOCX_OUTPUT_BYTES", 6, create=True), self.assertRaisesRegex(
            ValueError, "output.*safety ceiling",
        ):
            preview_docx(buf.getvalue())

    def test_convert_refuses_source_and_aliases_even_with_overwrite(self) -> None:
        content = _create_synthetic_docx_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.docx"
            source.write_bytes(content)
            aliases = [source]
            hardlink = root / "hardlink.md"
            hardlink.hardlink_to(source)
            aliases.append(hardlink)
            symlink = root / "symlink.md"
            symlink.symlink_to(source)
            aliases.append(symlink)
            for output in aliases:
                with self.subTest(output=output.name):
                    source.write_bytes(content)
                    with self.assertRaisesRegex(ValueError, "alias|manuscript"):
                        convert_docx(source, output, overwrite=True)
                    self.assertEqual(source.read_bytes(), content)

    def test_convert_rechecks_source_alias_before_atomic_replacement(self) -> None:
        content = _create_synthetic_docx_bytes()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source.docx"
            source.write_bytes(content)
            output = root / "output.md"
            original_fsync = os.fsync

            def change_output(descriptor: int) -> None:
                original_fsync(descriptor)
                output.hardlink_to(source)

            with patch("lixity.io.os.fsync", side_effect=change_output), self.assertRaisesRegex(
                ValueError, "alias|manuscript",
            ):
                convert_docx(source, output, overwrite=True)
            self.assertEqual(source.read_bytes(), content)
            self.assertEqual(output.read_bytes(), content)
            self.assertEqual(sorted(path.name for path in root.iterdir()),
                             ["output.md", "source.docx"])

    def test_convert_rechecks_overwrite_before_atomic_replacement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.docx"
            source.write_bytes(_create_synthetic_docx_bytes())
            output = Path(directory) / "output.md"
            original_fsync = os.fsync

            def create_output(descriptor: int) -> None:
                original_fsync(descriptor)
                output.write_text("existing content", encoding="utf-8")

            with patch("lixity.io.os.fsync", side_effect=create_output), self.assertRaises(FileExistsError):
                convert_docx(source, output)
            self.assertEqual(output.read_text(encoding="utf-8"), "existing content")

    def test_convert_preserves_source_and_destination_if_atomic_replace_fails(self) -> None:
        content = _create_synthetic_docx_bytes()
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.docx"
            source.write_bytes(content)
            output = Path(directory) / "output.md"
            output.write_text("previous manuscript", encoding="utf-8")
            with patch("lixity.io.os.replace", side_effect=OSError("synthetic failure")), self.assertRaisesRegex(
                OSError, "synthetic failure",
            ):
                convert_docx(source, output, overwrite=True)
            self.assertEqual(source.read_bytes(), content)
            self.assertEqual(output.read_text(encoding="utf-8"), "previous manuscript")

    def test_preview_docx_extracts_headings_formatting_and_loss_report(self) -> None:
        docx_bytes = _create_synthetic_docx_bytes()
        preview = preview_docx(docx_bytes, filename="story.docx")

        self.assertEqual(preview.source_filename, "story.docx")
        self.assertEqual(preview.source_format, "docx")
        self.assertTrue(len(preview.source_sha256) == 64)

        # Check Markdown content
        self.assertIn("# The Mariner's Gate", preview.markdown)
        self.assertIn("# Chapter 1: The Harbour", preview.markdown)
        self.assertIn("**Mira stood**", preview.markdown)
        self.assertIn("*the grey water*", preview.markdown)
        self.assertIn("* * *", preview.markdown)
        self.assertIn("> A sailor never speaks of tomorrow.", preview.markdown)
        self.assertIn("The bell rang twice.", preview.markdown)

        # Check detected headings
        self.assertEqual(len(preview.headings), 2)
        self.assertEqual(preview.headings[0].text, "The Mariner's Gate")
        self.assertEqual(preview.headings[0].level, 1)
        self.assertEqual(preview.headings[1].text, "Chapter 1: The Harbour")
        self.assertEqual(preview.headings[1].level, 1)

        # Check loss report contains table and drawing
        elements = [item.element for item in preview.loss_report]
        self.assertIn("table", elements)
        self.assertIn("drawing", elements)

        # JSON serialization
        d = preview.to_dict()
        self.assertEqual(d["schema_version"], "manuscript-import-preview-local/1")
        self.assertEqual(d["paragraph_count"], 6)
        self.assertGreater(d["word_count"], 20)

    def test_convert_docx_writes_markdown_file_and_protects_existing(self) -> None:
        docx_bytes = _create_synthetic_docx_bytes()
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            doc_file = tmp_path / "novel.docx"
            doc_file.write_bytes(docx_bytes)

            md_file = tmp_path / "novel.md"
            preview = convert_docx(doc_file, md_file)
            self.assertTrue(md_file.is_file())
            content = md_file.read_text(encoding="utf-8")
            self.assertEqual(content, preview.markdown)

            # Prevent accidental overwrite
            with self.assertRaises(FileExistsError):
                convert_docx(doc_file, md_file, overwrite=False)

            # Explicit overwrite succeeds
            preview2 = convert_docx(doc_file, md_file, overwrite=True)
            self.assertEqual(preview2.source_sha256, preview.source_sha256)

    def test_corrupted_inputs_raise_value_errors(self) -> None:
        with self.assertRaises(ValueError):
            preview_docx(b"not a zip file")

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("something_else.txt", "hello")
        with self.assertRaises(ValueError):
            preview_docx(buf.getvalue())


if __name__ == "__main__":
    unittest.main()
