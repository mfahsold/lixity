"""Local, opt-in OCR contracts using synthetic pages and a fake Tesseract CLI."""

import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from pydantic import ValidationError

from lixity.research import api
from lixity.research.models import Activity
from lixity.research.ocr import (
    PageImage,
    extract_pdf_document,
    extract_pdf_with_worker,
    get_ocr_diagnostics,
)
from lixity.research.repository import Repository, ResearchError


class TesseractOCRTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.pdf = self.root / "synthetic.pdf"
        self.pdf.write_bytes(b"%PDF synthetic test")
        self.tool = self.root / "tesseract"
        self.tool.write_text(
            "import sys\n"
            "if '--list-langs' in sys.argv:\n"
            " print('List of available languages (2):\\neng\\ndeu')\n"
            "else:\n"
            " data = sys.stdin.buffer.read()\n"
            " if data == b'failure':\n"
            "  sys.stderr.write('Synthetic engine failure'); sys.exit(1)\n"
            " if data != b'blank': print('Der Berg ist hoch.' if data == b'first' else 'The valley is quiet.')\n"
            " if data == b'first': sys.stderr.write('Synthetic recognition warning')\n",
            encoding="utf-8",
        )
        self.tool.chmod(0o755)
        original_which = shutil.which
        self.which = patch("lixity.research.ocr.shutil.which", side_effect=lambda name:
                           str(self.tool) if name == "tesseract" else original_which(name))
        original_run = subprocess.run
        self.run = patch("lixity.research.ocr.subprocess.run", side_effect=lambda args, **kwargs:
                         original_run([sys.executable, *args], **kwargs) if args[0] == str(self.tool)
                         else original_run(args, **kwargs))
        self.env = patch.dict(os.environ, {"LIXITY_OCR_BACKEND": "tesseract",
                                          "LIXITY_OCR_LANGUAGES": "deu+eng"})
        for patcher in (self.env, self.which, self.run):
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_opt_in_multilingual_pages_spans_and_runtime_warnings(self):
        pages = [PageImage(1, b"first", "first-hash"), PageImage(2, b"blank", "blank-hash"),
                 PageImage(3, b"last", "last-hash")]
        with patch("lixity.research.ocr.render_pdf_pages", return_value=pages):
            result = extract_pdf_document(self.pdf)
        self.assertEqual(result.full_text, "Der Berg ist hoch.\n\nThe valley is quiet.")
        self.assertEqual([block.page_number for block in result.blocks], [1, 3])
        self.assertEqual([result.full_text[start:end] for start, end in result.spans],
                         ["Der Berg ist hoch.", "The valley is quiet."])
        self.assertEqual(result.implementation_id, "tesseract-cli/1")
        self.assertIsNone(result.model_snapshot)
        self.assertTrue(any("Synthetic recognition warning" in warning for warning in result.warnings))
        self.assertTrue(any("page 2" in warning for warning in result.warnings))

    def test_status_installed_and_missing_language_data(self):
        diag = get_ocr_diagnostics()
        self.assertEqual(diag["backend"], "tesseract")
        self.assertEqual(diag["requested_languages"], ["deu", "eng"])
        self.assertEqual(diag["available_languages"], ["eng", "deu"])
        self.assertEqual(diag["missing_languages"], [])
        self.assertIsNone(diag["model_snapshot"])
        with patch.dict(os.environ, {"LIXITY_OCR_LANGUAGES": "deu+ita"}):
            diag = get_ocr_diagnostics()
            self.assertEqual(diag["status"], "misconfigured_backend")
            self.assertEqual(diag["missing_languages"], ["ita"])
            with self.assertRaisesRegex(ResearchError, "ita"):
                extract_pdf_with_worker(self.pdf, [PageImage(1, b"first", "hash")])

    def test_engine_failure_never_retains_partial_text(self):
        pages = [PageImage(1, b"first", "hash"), PageImage(2, b"failure", "other")]
        with self.assertRaisesRegex(ResearchError, "Synthetic engine failure"):
            extract_pdf_with_worker(self.pdf, pages)

    def test_timeout_is_bounded_and_reported(self):
        def timed_out(args, **kwargs):
            if "--list-langs" in args:
                return subprocess.CompletedProcess(args, 0, stdout="eng\ndeu\n", stderr="")
            self.assertGreater(kwargs["timeout"], 0)
            self.assertLessEqual(kwargs["timeout"], 7)
            raise subprocess.TimeoutExpired(args, kwargs["timeout"])
        with (patch.dict(os.environ, {"LIXITY_OCR_TIMEOUT": "7"}),
              patch("lixity.research.ocr.subprocess.run", side_effect=timed_out),
              self.assertRaisesRegex(ResearchError, "timed out")):
            extract_pdf_with_worker(self.pdf, [PageImage(1, b"first", "hash")])

    def test_invalid_settings_are_actionable(self):
        for setting, value in (("LIXITY_OCR_BACKEND", "unknown"),
                               ("LIXITY_OCR_LANGUAGES", "deu --psm 0"),
                               ("LIXITY_OCR_TIMEOUT", "0")):
            with self.subTest(setting=setting), patch.dict(os.environ, {setting: value}):
                diag = get_ocr_diagnostics()
                self.assertEqual(diag["status"], "misconfigured_backend")
                self.assertTrue(any(setting in hint for hint in diag["guidance"]))
                with self.assertRaisesRegex(ResearchError, setting):
                    extract_pdf_with_worker(self.pdf, [PageImage(1, b"first", "hash")])

    def test_native_default_does_not_discover_or_run_tesseract(self):
        with patch.dict(os.environ, {"LIXITY_OCR_BACKEND": "", "LIXITY_OCR_WORKER": ""}), \
                patch("lixity.research.ocr.subprocess.run") as run:
            diag = get_ocr_diagnostics()
        self.assertEqual(diag["backend"], "native")
        run.assert_not_called()

    def test_failed_startup_probe_does_not_report_ready(self):
        with patch("lixity.research.ocr._extract_tesseract", side_effect=ResearchError("Synthetic startup failure")):
            diag = get_ocr_diagnostics(probe=True)
        self.assertEqual(diag["status"], "misconfigured_backend")
        self.assertFalse(diag["probe"]["ok"])
        self.assertTrue(any("Synthetic startup failure" in hint for hint in diag["guidance"]))

    def test_missing_executable_and_rasterizer_are_distinct(self):
        with patch("lixity.research.ocr.shutil.which", return_value=None):
            diag = get_ocr_diagnostics()
        self.assertEqual(diag["status"], "misconfigured_backend")
        self.assertFalse(diag["tesseract_available"])
        self.assertEqual(diag["requested_languages"], ["deu", "eng"])
        self.assertEqual(diag["available_languages"], [])
        self.assertEqual(diag["missing_languages"], [])
        self.assertTrue(any("PATH" in hint for hint in diag["guidance"]))
        with patch("lixity.research.ocr.shutil.which", side_effect=lambda name:
                   str(self.tool) if name == "tesseract" else None):
            diag = get_ocr_diagnostics()
        self.assertEqual(diag["status"], "partial")
        self.assertTrue(any("pdftoppm" in hint for hint in diag["guidance"]))

    def test_invalid_languages_are_reported_before_missing_executable(self):
        with (patch("lixity.research.ocr.shutil.which", return_value=None),
              patch.dict(os.environ, {"LIXITY_OCR_LANGUAGES": "deu --psm 0"}),
              patch("lixity.research.ocr.subprocess.run") as run):
            diag = get_ocr_diagnostics()
            self.assertEqual(diag["status"], "misconfigured_backend")
            self.assertEqual(diag["requested_languages"], [])
            self.assertEqual(diag["available_languages"], [])
            self.assertEqual(diag["missing_languages"], [])
            self.assertTrue(any("LIXITY_OCR_LANGUAGES" in hint for hint in diag["guidance"]))
            with self.assertRaisesRegex(ResearchError, "LIXITY_OCR_LANGUAGES"):
                extract_pdf_with_worker(self.pdf, [PageImage(1, b"first", "hash")])
            run.assert_not_called()

    def test_explicit_worker_argument_preserves_existing_override(self):
        response = subprocess.CompletedProcess([], 0,
            stdout='{"blocks":[{"page_number":1,"text":"Synthetic worker output"}]}', stderr="")
        with patch("lixity.research.ocr.subprocess.run", return_value=response) as run:
            text, _, _ = extract_pdf_with_worker(self.pdf, [PageImage(1, b"first", "hash")], worker_cmd="custom-worker")
        self.assertEqual(text, "Synthetic worker output")
        self.assertEqual(run.call_args.args[0][0], "custom-worker")

    def test_mixed_pdf_native_fallback_announces_unreadable_page(self):
        pages = [PageImage(1, b"failure", "hash"), PageImage(2, b"blank", "other")]
        original_run = subprocess.run
        def mixed(args, **kwargs):
            if "pdftotext" in str(args[0]):
                return subprocess.CompletedProcess(args, 0,
                    stdout=b"Synthetic native page" if args[2] == "1" else b"", stderr=b"")
            return original_run([sys.executable, *args], **kwargs)
        with patch("lixity.research.ocr.subprocess.run", side_effect=mixed), \
                patch("lixity.research.ocr.shutil.which", side_effect=lambda name:
                      str(self.tool) if name == "tesseract" else "/synthetic/pdftotext"):
            text, _, warnings = extract_pdf_with_worker(self.pdf, pages, allow_fallback=True)
            with patch("lixity.research.ocr.render_pdf_pages", return_value=pages):
                result = extract_pdf_document(self.pdf, allow_fallback=True)
        self.assertEqual(text, "Synthetic native page")
        self.assertTrue(any("fallback" in warning for warning in warnings))
        self.assertTrue(any("page 2" in warning for warning in warnings))
        self.assertEqual(result.implementation_id, "poppler-native/1")
        self.assertIsNone(result.model_snapshot)

    def test_runtime_probe_uses_only_synthetic_input(self):
        diag = get_ocr_diagnostics(probe=True)
        self.assertTrue(diag["probe"]["ok"])
        self.assertEqual(diag["status"], "ready (probed)" if diag["pdftoppm_available"] else "partial")

    def test_ingest_records_actual_backend_and_retains_revision_on_refresh(self):
        project = self.root / "archive"
        api.init(project, title="Synthetic OCR archive")
        with patch("lixity.research.ocr.render_pdf_pages", return_value=[PageImage(1, b"first", "hash")]):
            captured = api.ingest(project, self.pdf, allow_retention=True)
        activities = [record for record in Repository(project).snapshot().records.values() if isinstance(record, Activity)]
        self.assertEqual([(item.schema_version, item.implementation) for item in activities],
                         [("research-local/4", "tesseract-cli/1")])
        self.assertEqual(Repository(project).snapshot().manifest.schema_version, "research-manifest-local/4")
        with self.assertRaises(ValidationError):
            Activity.model_validate({**activities[0].model_dump(), "schema_version": "research-local/1"})
        with self.assertRaises(ValidationError):
            Activity.model_validate({**activities[0].model_dump(), "implementation": "baidu-unlimited-ocr/1"})
        with patch("lixity.research.api.extract_pdf_document") as extraction:
            refreshed = api.ingest(project, self.pdf, source_id=captured["source_id"], allow_retention=True)
        self.assertTrue(refreshed["unchanged"])
        extraction.assert_not_called()
        self.assertTrue(api.audit(project)["ok"])

    def test_empty_or_failed_capture_leaves_archive_unchanged(self):
        project = self.root / "archive"
        api.init(project, title="Synthetic OCR archive")
        before = Repository(project).snapshot().digest
        for image in [b"blank", b"failure"]:
            with self.subTest(image=image), patch("lixity.research.ocr.render_pdf_pages",
                return_value=[PageImage(1, image, "hash")]), self.assertRaises(ResearchError):
                api.ingest(project, self.pdf, allow_retention=True)
            self.assertEqual(Repository(project).snapshot().digest, before)
            self.assertEqual(api.list_sources(project)["sources"], [])


if __name__ == "__main__":
    unittest.main()
