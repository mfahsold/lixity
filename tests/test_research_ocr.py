"""Tests for self-hosted Baidu Unlimited-OCR extraction boundary and PDF ingestion."""

import contextlib
import io
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from lixity.research import api
from lixity.research.models import Activity, Extraction, Passage, SourceVersion
from lixity.research.ocr import (
    INTEGRATION_RECIPE_REVISION,
    MODEL_SNAPSHOT,
    PageImage,
    extract_pdf_document,
    extract_pdf_with_worker,
    get_ocr_diagnostics,
    get_pdf_page_count,
    probe_ocr_worker,
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

    @unittest.skipUnless(shutil.which("pdftoppm"), "requires Poppler pdftoppm")
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

    @unittest.skipUnless(shutil.which("pdftotext"), "requires Poppler pdftotext")
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

with open(sys.argv[1], encoding="utf-8") as stream:
    req = json.load(stream)
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

        # Use the current interpreter on every OS; Windows does not execute
        # Python shebangs. Rasterization has its own real Poppler integration test.
        run = subprocess.run
        def run_worker(args, **kwargs):
            return run([sys.executable, *args], **kwargs)

        with (
            patch("lixity.research.ocr.render_pdf_pages", return_value=[
                PageImage(page_number=1, image_bytes=b"synthetic", sha256="a" * 64),
            ]),
            patch("lixity.research.ocr.subprocess.run", side_effect=run_worker),
        ):
            res = extract_pdf_document(pdf_path, worker_cmd=str(worker_script))
        self.assertEqual(res.full_text, "Extracted OCR text line A.\n\nExtracted OCR text line B.")
        self.assertEqual(len(res.blocks), 2)
        self.assertEqual(res.blocks[0].confidence, 0.99)
        self.assertEqual(len(res.spans), 2)

    @unittest.skipUnless(shutil.which("pdftotext"), "requires Poppler pdftotext")
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

    @unittest.skipUnless(shutil.which("pdftotext"), "requires Poppler pdftotext")
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

    @unittest.skipUnless(shutil.which("pdftotext"), "requires Poppler pdftotext")
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

    def test_worker_rejects_incomplete_pages_without_silent_native_fallback(self):
        from lixity.research.ocr import extract_pdf_with_worker
        pages = [PageImage(page_number=i, image_bytes=b'fixture', sha256='a'*64) for i in (1,2)]
        response = subprocess.CompletedProcess([], 0, stdout=json.dumps({'blocks':[{'page_number':1,'text':'Only first page'}]}), stderr='')
        with patch('lixity.research.ocr.subprocess.run', return_value=response), self.assertRaisesRegex(ResearchError, 'page'):
            extract_pdf_with_worker(self.root/'synthetic.pdf', pages, worker_cmd='synthetic-worker')

    def test_worker_timeout_and_unknown_confidence(self):
        from lixity.research.ocr import extract_pdf_with_worker
        pages = [PageImage(page_number=1, image_bytes=b'fixture', sha256='a'*64)]
        response = subprocess.CompletedProcess([],0,stdout=json.dumps({'blocks':[{'page_number':1,'text':'Complete page'}]}),stderr='')
        with patch.dict(os.environ, {'LIXITY_OCR_TIMEOUT':'600'}), patch('lixity.research.ocr.subprocess.run',return_value=response) as run:
            _, blocks, _ = extract_pdf_with_worker(self.root/'synthetic.pdf',pages,worker_cmd='synthetic-worker')
            self.assertEqual(run.call_args.kwargs['timeout'],600)
            self.assertIsNone(blocks[0].confidence)

    def test_worker_orders_pages_stably_before_building_archived_text(self):
        from lixity.research.ocr import extract_pdf_with_worker
        pages = [PageImage(page_number=i, image_bytes=b'fixture', sha256='a'*64) for i in (1,2)]
        response = subprocess.CompletedProcess([], 0, stdout=json.dumps({'blocks':[
            {'page_number':2,'text':'Second page'}, {'page_number':1,'text':'First paragraph'},
            {'page_number':1,'text':'Next paragraph'}]}), stderr='')
        with patch('lixity.research.ocr.subprocess.run', return_value=response):
            text, blocks, _ = extract_pdf_with_worker(self.root/'synthetic.pdf', pages, worker_cmd='synthetic-worker')
        self.assertEqual(text, 'First paragraph\n\nNext paragraph\n\nSecond page')
        self.assertEqual([b.page_number for b in blocks], [1,1,2])

    def test_worker_invalid_timeout_and_failure_never_fall_back(self):
        from lixity.research.ocr import extract_pdf_with_worker, get_ocr_diagnostics
        pages = [PageImage(page_number=1, image_bytes=b'fixture', sha256='a'*64)]
        for value in ('zero','0','3601'):
            with self.subTest(value=value), patch.dict(os.environ, {'LIXITY_OCR_TIMEOUT':value}), patch('lixity.research.ocr.subprocess.run') as run:
                with self.assertRaisesRegex(ResearchError, 'LIXITY_OCR_TIMEOUT'):
                    extract_pdf_with_worker(self.root/'synthetic.pdf', pages, worker_cmd='synthetic-worker')
                run.assert_not_called()
                diag = get_ocr_diagnostics(worker_cmd=sys.executable)
                self.assertEqual(diag['status'], 'misconfigured_worker')
                self.assertTrue(any('LIXITY_OCR_TIMEOUT' in g for g in diag['guidance']))
        for failure in (subprocess.CompletedProcess([], 1, stdout='', stderr='Failure'), subprocess.TimeoutExpired('worker', 1)):
            kwargs = {'side_effect':failure} if isinstance(failure, Exception) else {'return_value':failure}
            with self.subTest(failure=str(failure)), patch('lixity.research.ocr.subprocess.run', **kwargs) as run:
                with self.assertRaises(ResearchError):
                    extract_pdf_with_worker(self.root/'synthetic.pdf', pages, worker_cmd='synthetic-worker')
                self.assertEqual(run.call_count, 1)

    def test_get_pdf_page_count(self) -> None:
        pdf_bytes = make_synthetic_pdf("Single page text.")
        pdf_path = self.root / "single.pdf"
        pdf_path.write_bytes(pdf_bytes)
        count = get_pdf_page_count(pdf_path)
        self.assertEqual(count, 1)

    def test_get_pdf_page_count_returns_none_when_undeterminable(self) -> None:
        """An unmeasurable page tree must report unknown, never guess 1.

        A guessed 1 makes the native extractor capture exactly one page of a
        multi-page document and still report success.
        """
        unreadable = self.root / "compressed-tree.pdf"
        unreadable.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n")
        with patch("lixity.research.ocr.shutil.which", return_value=None):
            self.assertIsNone(get_pdf_page_count(unreadable))

    def test_native_extraction_refuses_to_capture_partial_pdf(self) -> None:
        """Without a determinable page count the capture must fail, not truncate."""
        unreadable = self.root / "no-page-tree.pdf"
        unreadable.write_bytes(b"%PDF-1.4\n1 0 obj << /Type /Catalog >>\nendobj\ntrailer\n%%EOF\n")
        with (
            patch("lixity.research.ocr.render_pdf_pages", return_value=[]),
            patch("lixity.research.ocr.shutil.which", return_value="/usr/bin/pdftotext"),
            self.assertRaises(ResearchError) as raised,
        ):
            extract_pdf_with_worker(unreadable, [], allow_fallback=True)
        message = str(raised.exception)
        self.assertIn("Cannot determine the page count", message)
        self.assertIn("part of it", message)
        # The message has to say what to do, not only what went wrong.
        self.assertIn("Install Poppler", message)

    def test_probe_ocr_worker_success_and_failure(self) -> None:
        # 1. Non-executable worker
        fail_res = probe_ocr_worker("/nonexistent/worker")
        self.assertFalse(fail_res["ok"])
        self.assertIn("not executable", fail_res["error"])

        # 2. Mock worker responding to probe
        probe_worker = self.root / "probe_worker.py"
        probe_worker.write_text(
            f"""#!{sys.executable}
import sys, json
with open(sys.argv[1], encoding="utf-8") as stream:
    req = json.load(stream)
assert req.get("probe") is True
resp = {{
    "blocks": [{{"page_number": 1, "text": "Probe OK", "confidence": 1.0}}],
    "warnings": []
}}
print(json.dumps(resp))
""",
            encoding="utf-8",
        )
        probe_worker.chmod(0o755)

        run = subprocess.run
        def run_probe(args, **kwargs):
            return run([sys.executable, *args], **kwargs)

        with (
            patch("lixity.research.ocr.shutil.which", side_effect=lambda name: sys.executable if name == "pdftoppm" else None),
            patch("lixity.research.ocr.render_pdf_pages", return_value=[]),
            patch("lixity.research.ocr.subprocess.run", side_effect=run_probe),
        ):
            diag = get_ocr_diagnostics(worker_cmd=str(probe_worker), probe=True)
            self.assertEqual(diag["status"], "ready (probed)")
            self.assertTrue(diag["probe"]["ok"])
            self.assertEqual(diag["probe"]["blocks_count"], 1)

        for timeout in ("invalid", "0", "3601"):
            with (
                self.subTest(timeout=timeout),
                patch.dict(os.environ, {"LIXITY_OCR_TIMEOUT": timeout}),
                patch("lixity.research.ocr.shutil.which", side_effect=lambda name: sys.executable if name == "pdftoppm" else None),
                patch("lixity.research.ocr.render_pdf_pages", return_value=[]),
                patch("lixity.research.ocr.subprocess.run", side_effect=run_probe),
            ):
                diag = get_ocr_diagnostics(worker_cmd=str(probe_worker), probe=True)
                self.assertTrue(diag["probe"]["ok"])
                self.assertEqual(diag["status"], "misconfigured_worker")
                self.assertTrue(any("LIXITY_OCR_TIMEOUT" in hint for hint in diag["guidance"]))

        with (
            patch("lixity.research.ocr.shutil.which", return_value=None),
            patch("lixity.research.ocr.subprocess.run", side_effect=run_probe),
        ):
            diag = get_ocr_diagnostics(worker_cmd=str(probe_worker), probe=True)
            self.assertTrue(diag["probe"]["ok"])
            self.assertEqual(diag["status"], "partial")
            self.assertTrue(any("pdftoppm is missing" in hint for hint in diag["guidance"]))

    @unittest.skipUnless(shutil.which("pdftotext"), "requires Poppler pdftotext")
    def test_explicit_fallback_mode_when_worker_fails(self) -> None:
        pdf_bytes = make_synthetic_pdf("Archival document with native text layer.")
        pdf_path = self.root / "fallback_doc.pdf"
        pdf_path.write_bytes(pdf_bytes)

        # Worker that fails with exit code 1
        failing_worker = self.root / "failing_worker.py"
        failing_worker.write_text(
            f"""#!{sys.executable}
import sys
sys.stderr.write("GPU Out of Memory error\\n")
sys.exit(1)
""",
            encoding="utf-8",
        )
        failing_worker.chmod(0o755)

        run = subprocess.run
        def run_fail(args, **kwargs):
            if str(args[0]) == str(failing_worker):
                return run([sys.executable, *args], **kwargs)
            return run(args, **kwargs)

        # Without fallback -> ResearchError
        with (
            patch("lixity.research.ocr.subprocess.run", side_effect=run_fail),
            self.assertRaisesRegex(ResearchError, "OCR worker exited with code 1"),
        ):
            extract_pdf_document(pdf_path, worker_cmd=str(failing_worker), allow_fallback=False)

        # With fallback -> Falls back to native poppler pdftotext with warning
        with patch("lixity.research.ocr.subprocess.run", side_effect=run_fail):
            res = extract_pdf_document(pdf_path, worker_cmd=str(failing_worker), allow_fallback=True)
            self.assertIn("Archival document with native text layer.", res.full_text)
            self.assertTrue(any("fallback" in w.lower() for w in res.warnings))

        with (
            patch.dict(os.environ, {"LIXITY_OCR_WORKER": str(failing_worker)}),
            patch("lixity.research.ocr.subprocess.run", side_effect=run_fail),
        ):
            preview = api.ingest(self.project, pdf_path, allow_retention=True,
                                 allow_fallback=True, dry_run=True)
            self.assertEqual(preview["warnings"], res.warnings)
            self.assertEqual(len(api.list_sources(self.project)["sources"]), 0)
            captured = api.ingest(self.project, pdf_path, allow_retention=True, allow_fallback=True)
            self.assertEqual(captured["schema_version"], "research-ingest-local/1")
            self.assertEqual(captured["warnings"], res.warnings)
            reused = api.ingest(self.project, pdf_path, allow_retention=True,
                                source_id=captured["source_id"])
            self.assertTrue(reused["unchanged"])
            self.assertEqual(reused["warnings"], [])

            from lixity.cli import main
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                code = main(["research", "ingest", "--project", str(self.project),
                             "--file", str(pdf_path), "--allow-retention", "--fallback", "--dry-run"])
            self.assertEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())["warnings"], res.warnings)

            text_path = self.root / "native.txt"
            text_path.write_text("Synthetic source with no extraction warning.", encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
                code = main(["research", "ingest", "--project", str(self.project),
                             "--file", str(pdf_path), str(self.root / "missing.txt"), str(text_path),
                             "--allow-retention", "--fallback", "--dry-run"])
            self.assertEqual(code, 1)
            batch = json.loads(output.getvalue())
            self.assertEqual(batch["schema_version"], "research-batch-ingest-local/1")
            self.assertEqual((batch["succeeded"], batch["failed"]), (2, 1))
            self.assertEqual(batch["items"][0]["warnings"], res.warnings)
            self.assertFalse(batch["items"][1]["ok"])
            self.assertEqual(batch["items"][2]["warnings"], [])
        self.assertTrue(api.audit(self.project)["ok"])


if __name__ == "__main__":
    unittest.main()
