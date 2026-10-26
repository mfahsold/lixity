"""Tests for Word (.docx) manuscript import and loss reporting."""

from __future__ import annotations

import io
import tempfile
import unittest
import zipfile
from pathlib import Path

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
