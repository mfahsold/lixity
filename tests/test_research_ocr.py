"""Tests for self-hosted Baidu Unlimited-OCR extraction boundary and PDF ingestion."""

import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from lixity.research import api
from lixity.research.models import Activity, Extraction, Passage, SourceVersion
from lixity.research.ocr import (
    INTEGRATION_RECIPE_REVISION,
    MODEL_SNAPSHOT,
    extract_pdf_document,
    render_pdf_pages,
)
from lixity.research.repository import Repository, ResearchError


def make_synthetic_pdf(text: str) -> bytes:
    """Generate a minimal valid PDF-1.4 containing text in a standard Type1 font."""
    stream_bytes = f"BT /F1 12 Tf 72 712 Td ({text}) Tj ET".encode("latin1")
    stream_obj = f"<< /Length {len(stream_bytes)} >>\nstream\n".encode("latin1") + stream_bytes + b"\nendstream"
    objs = [
        b"",
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
        stream_obj,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    pdf = [b"%PDF-1.4\n"]
    offsets = [0]
    for i in range(1, len(objs)):
        offsets.append(sum(len(x) for x in pdf))
        pdf.append(f"{i} 0 obj\n".encode("latin1") + objs[i] + b"\nendobj\n")
    xref_offset = sum(len(x) for x in pdf)
    pdf.append(f"xref\n0 {len(objs)}\n0000000000 65535 f \n".encode("latin1"))
    pdf.extend(f"{off:010d} 00000 n \n".encode("latin1") for off in offsets[1:])
    pdf.append(f"trailer\n<< /Size {len(objs)} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF\n".encode("latin1"))
    return b"".join(pdf)


class ResearchOCRTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.project = self.root / "project"
        api.init(self.project, title="OCR Pilot Project")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_render_pdf_pages(self) -> None:
        pdf_bytes = make_synthetic_pdf("Historical record of the 1924 expedition.")
        pdf_path = self.root / "sample.pdf"
        pdf_path.write_bytes(pdf_bytes)

        pages = render_pdf_pages(pdf_path)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_number, 1)
        self.assertEqual(pages[0].media_type, "image/png")
        self.assertGreater(len(pages[0].image_bytes), 0)
        self.assertEqual(len(pages[0].sha256), 64)

    def test_extract_pdf_document_local_text_layer(self) -> None:
        content = "Archival field note paragraph one.\n\nArchival field note paragraph two."
        pdf_bytes = make_synthetic_pdf(content)
        pdf_path = self.root / "two_para.pdf"
        pdf_path.write_bytes(pdf_bytes)

        res = extract_pdf_document(pdf_path)
        self.assertIn("Archival field note", res.full_text)
        self.assertGreaterEqual(len(res.spans), 1)
        for start, end in res.spans:
            span_text = res.full_text[start:end]
            self.assertTrue(len(span_text) > 0)
        self.assertEqual(res.model_snapshot, MODEL_SNAPSHOT)
        self.assertEqual(res.recipe_revision, INTEGRATION_RECIPE_REVISION)

    def test_extract_pdf_document_with_mock_worker(self) -> None:
        # Create a mock worker script
        worker_script = self.root / "mock_worker.py"
        worker_script.write_text(
            f"""#!{sys.executable}
import sys, json

req = json.load(open(sys.argv[1]))
assert req["model_snapshot"] == "{MODEL_SNAPSHOT}"
assert req["recipe_revision"] == "{INTEGRATION_RECIPE_REVISION}"
assert len(req["pages"]) == 1

resp = {{
    "blocks": [
        {{"page_number": 1, "text": "Extracted OCR text line A.", "box": [10.0, 20.0, 100.0, 40.0], "confidence": 0.99}},
        {{"page_number": 1, "text": "Extracted OCR text line B.", "box": [10.0, 50.0, 100.0, 70.0], "confidence": 0.98}}
    ],
    "warnings": []
}}
print(json.dumps(resp))
""",
            encoding="utf-8",
        )
        worker_script.chmod(0o755)

        pdf_bytes = make_synthetic_pdf("Dummy text")
        pdf_path = self.root / "worker_test.pdf"
        pdf_path.write_bytes(pdf_bytes)

        res = extract_pdf_document(pdf_path, worker_cmd=str(worker_script))
        self.assertEqual(res.full_text, "Extracted OCR text line A.\n\nExtracted OCR text line B.")
        self.assertEqual(len(res.blocks), 2)
        self.assertEqual(res.blocks[0].confidence, 0.99)
        self.assertEqual(len(res.spans), 2)

    def test_pdf_ingest_lifecycle_audit_cite_and_search(self) -> None:
        pdf_bytes = make_synthetic_pdf("Botanical observations in the alpine meadow.")
        pdf_path = self.root / "botany.pdf"
        pdf_path.write_bytes(pdf_bytes)

        # 1. Retention permission check
        with self.assertRaisesRegex(ResearchError, "retention"):
            api.ingest(self.project, pdf_path, allow_retention=False)

        # 2. Ingest PDF
        ingested = api.ingest(
            self.project,
            pdf_path,
            allow_retention=True,
            title="Botanical Observations",
            context={"genre": "field-notebook", "tags": ["botany", "alps"]},
        )
        self.assertFalse(ingested["unchanged"])
        self.assertGreaterEqual(ingested["passages"], 1)

        # 3. Verify record graph and blobs
        repo = Repository(self.project)
        snapshot = repo.snapshot()
        version = next(r for r in snapshot.records.values() if isinstance(r, SourceVersion))
        self.assertEqual(version.blob.media_type, "application/pdf")
        self.assertEqual(version.blob.byte_length, len(pdf_bytes))

        activity = next(r for r in snapshot.records.values() if isinstance(r, Activity))
        self.assertEqual(activity.operation, "extract_ocr")
        self.assertEqual(activity.implementation, "baidu-unlimited-ocr/1")
        self.assertEqual(activity.status, "succeeded")

        extraction = next(r for r in snapshot.records.values() if isinstance(r, Extraction))
        self.assertEqual(extraction.text_blob.media_type, "text/plain")
        self.assertNotEqual(extraction.text_blob.sha256, version.blob.sha256)

        # 4. Audit validates both PDF and text blobs
        audit_res = api.audit(self.project)
        self.assertTrue(audit_res["ok"])
        self.assertEqual(audit_res["errors"], [])

        # 5. Citation verification
        passage = next(r for r in snapshot.records.values() if isinstance(r, Passage))
        citation = api.cite(self.project, passage.id)
        self.assertEqual(citation["verbatim"], passage.verbatim)
        self.assertIn("Botanical", citation["verbatim"])

        # 6. Lexical search across PDF extractions
        api.reindex(self.project)
        search_res = api.search(self.project, "Botanical")
        self.assertEqual(len(search_res["hits"]), 1)
        self.assertEqual(search_res["hits"][0]["passage_id"], passage.id)

        # 7. Unchanged re-ingest
        reingest = api.ingest(self.project, pdf_path, allow_retention=True, source_id=ingested["source_id"])
        self.assertTrue(reingest["unchanged"])

    def test_pdf_archive_export_and_restore_roundtrip(self) -> None:
        pdf_bytes = make_synthetic_pdf("Geological survey data 1926.")
        pdf_path = self.root / "geology.pdf"
        pdf_path.write_bytes(pdf_bytes)

        ingested = api.ingest(self.project, pdf_path, allow_retention=True)
        archive_path = self.root / "archive.tar.gz"
        api.export_archive(self.project, archive_path)

        restored_project = self.root / "restored"
        api.restore_archive(archive_path, restored_project)

        # Verify restored integrity
        audit_res = api.audit(restored_project)
        self.assertTrue(audit_res["ok"])

        # Verify source and citations intact in restored archive
        src = api.get_source(restored_project, ingested["source_id"])
        self.assertEqual(len(src["passages"]), 1)
        cited = api.cite(restored_project, src["passages"][0]["id"])
        self.assertIn("Geological survey", cited["verbatim"])

    def test_nonexistent_and_invalid_pdf_handling(self) -> None:
        missing_pdf = self.root / "missing.pdf"
        with self.assertRaisesRegex(ResearchError, "local PDF file"):
            api.ingest(self.project, missing_pdf, allow_retention=True)

        empty_pdf = self.root / "empty.pdf"
        empty_pdf.write_bytes(b"")
        with self.assertRaisesRegex(ResearchError, "nonempty and at most 50 MiB"):
            api.ingest(self.project, empty_pdf, allow_retention=True)

    def test_ocr_diagnostics_and_cli_status(self) -> None:
        import json
        from io import StringIO
        from unittest.mock import patch

        from lixity.cli import main
        from lixity.research.ocr import get_ocr_diagnostics

        diag = get_ocr_diagnostics()
        self.assertIn("status", diag)
        self.assertIn("pdftoppm_available", diag)
        self.assertIn("pdftotext_available", diag)
        self.assertIn("model_snapshot", diag)
        self.assertIn("recipe_revision", diag)
        self.assertIn("guidance", diag)

        # Test CLI invocation
        buf = StringIO()
        with patch("sys.stdout", buf):
            code = main(["research", "ocr-status"])
        self.assertEqual(code, 0)
        cli_out = json.loads(buf.getvalue())
        self.assertEqual(cli_out["model_snapshot"], MODEL_SNAPSHOT)
        self.assertEqual(cli_out["recipe_revision"], INTEGRATION_RECIPE_REVISION)

        # Test misconfigured worker diagnosis
        bad_diag = get_ocr_diagnostics(worker_cmd="/nonexistent/path/to/worker")
        self.assertEqual(bad_diag["status"], "misconfigured_worker")
        self.assertTrue(any("not found or is not executable" in g for g in bad_diag["guidance"]))

    def test_ingest_progress_callback(self) -> None:
        pdf_bytes = make_synthetic_pdf("Progress callback test document text.")
        pdf_path = self.root / "progress.pdf"
        pdf_path.write_bytes(pdf_bytes)

        events: list[tuple[str, str]] = []

        def callback(stage: str, msg: str) -> None:
            events.append((stage, msg))

        res = api.ingest(self.project, pdf_path, allow_retention=True, progress_callback=callback)
        self.assertIn("source_id", res)
        stages = [e[0] for e in events]
        self.assertIn("read", stages)
        self.assertIn("ocr", stages)
        self.assertIn("passages", stages)
        self.assertIn("commit", stages)
        self.assertIn("complete", stages)


if __name__ == "__main__":
    unittest.main()
