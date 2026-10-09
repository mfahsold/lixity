"""Metadata refresh reuses verified PDF extraction and preserves citation history."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api
from lixity.research.models import Activity, Extraction, Head, Passage
from lixity.research.ocr import OCRBlock, OCRExtractionResult
from lixity.research.repository import Repository, ResearchError, digest, encode


class TestResearchMetadataRefresh(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        self.pdf = self.root / "source.pdf"
        self.pdf.write_bytes(b"%PDF-1.4 synthetic metadata fixture")
        api.init(self.project, title="Synthetic metadata regression")
        self.text = "Café in Zürich.\n\nThe reading room opened in 1924."
        self.external = {"provider": "zotero", "server_id": "synthetic-instance", "library": "users/0",
                         "item_key": "ABCDEFGH", "attachment_key": "JKLMNPQR",
                         "item_version": 1, "attachment_version": 1}
        result = self.extraction(self.text)
        with patch("lixity.research.api.extract_pdf_document", return_value=result):
            self.first = api.ingest(self.project, self.pdf, allow_retention=True,
                                    origin_url="https://example.org/original",
                                    context={"tags": ["original"], "external_reference": self.external})
        self.repository = Repository(self.project)
        self.initial = self.repository.snapshot()
        self.initial_extraction = next(record for record in self.initial.records.values() if isinstance(record, Extraction))
        self.initial_passages = sorted((record for record in self.initial.records.values() if isinstance(record, Passage)),
                                       key=lambda record: record.start)

    def extraction(self, text):
        paragraphs = text.split("\n\n")
        spans = []
        position = 0
        for paragraph in paragraphs:
            spans.append((position, position + len(paragraph)))
            position += len(paragraph) + 2
        return OCRExtractionResult(pages=[], full_text=text,
                                   blocks=[OCRBlock(page_number=1, text=text)], spans=spans,
                                   implementation_id="poppler-native/1")

    def refresh(self, **kwargs):
        return api.ingest(self.project, self.pdf, allow_retention=True,
                          source_id=self.first["source_id"], origin_url="https://example.org/revised", **kwargs)

    def retained_files(self):
        return {path.relative_to(self.project): path.read_bytes()
                for path in self.project.rglob("*") if path.is_file()}

    def assert_corruption_stops_refresh(self, message="Research object checksum mismatch"):
        before = self.retained_files()
        with patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("Corruption must not trigger OCR")), \
                self.assertRaisesRegex(ResearchError, message):
            self.refresh()
        self.assertEqual(self.retained_files(), before)

    def test_context_refresh_reuses_extraction_and_keeps_pinned_citations(self):
        original = self.initial_passages[1]
        dossier = api.create_dossier(self.project, title="Pinned note", body="Original authorial note.",
                                     evidence_ids=[original.id])
        before = self.repository.snapshot()
        with patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("Identical PDF must reuse extraction")):
            refreshed = self.refresh(context={"tags": ["revised"],
                                              "external_reference": {**self.external, "item_key": "QRSTUVWX", "item_version": 2}})
        self.assertFalse(refreshed["unchanged"])
        current = self.repository.snapshot()
        self.assertNotEqual(refreshed["source_version_id"], self.first["source_version_id"])
        for identifier, record in before.records.items():
            self.assertEqual(current.records[identifier], record)
        old = api.cite(self.project, original.id)
        self.assertEqual(old["source_version_id"], self.first["source_version_id"])
        self.assertEqual(old["context"]["origin_url"], "https://example.org/original")
        self.assertEqual(old["context"]["tags"], ["original"])
        self.assertEqual(old["context"]["external_reference"]["item_key"], "ABCDEFGH")
        self.assertEqual(old["verbatim"], "The reading room opened in 1924.")
        latest = api.get_source(self.project, self.first["source_id"])
        self.assertEqual(latest["context"]["origin_url"], "https://example.org/revised")
        self.assertEqual(latest["context"]["tags"], ["revised"])
        self.assertEqual(latest["context"]["external_reference"]["item_key"], "QRSTUVWX")
        self.assertEqual(latest["text"], self.text)
        self.assertTrue({passage["id"] for passage in latest["passages"]}.isdisjoint(
            record.id for record in self.initial_passages))
        extraction = next(record for record in current.records.values()
                          if isinstance(record, Extraction) and record.source_version_ref.id == refreshed["source_version_id"])
        self.assertEqual(extraction.text_blob, self.initial_extraction.text_blob)
        activity = current.get(extraction.activity_ref, Activity)
        self.assertEqual(activity.implementation, "poppler-native/1")
        pinned = api.get_record(self.project, "dossier", dossier["dossier_id"])
        self.assertEqual(pinned["record"]["revision"], 1)
        self.assertEqual(pinned["record"]["body"], "Original authorial note.")
        self.assertEqual(pinned["citations"][0]["passage_id"], original.id)
        self.assertEqual(pinned["source_updates"][0]["latest_version_id"], refreshed["source_version_id"])
        api.reindex(self.project)
        hits = api.search(self.project, "1924")["hits"]
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["source_version_id"], refreshed["source_version_id"])
        self.assertEqual(hits[0]["context"]["origin_url"], "https://example.org/revised")
        self.assertTrue(api.audit(self.project)["ok"])

    def test_repeated_context_refresh_is_a_noop(self):
        with patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("Identical PDF must reuse extraction")):
            refreshed = self.refresh()
            before = self.retained_files()
            repeated = self.refresh()
        self.assertTrue(repeated["unchanged"])
        self.assertEqual(repeated["source_version_id"], refreshed["source_version_id"])
        self.assertEqual(repeated["snapshot"], refreshed["snapshot"])
        self.assertEqual(self.retained_files(), before)

    def test_metadata_refresh_progress_reports_retained_verification_not_skipped_ocr(self):
        events = []
        with patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("Identical PDF must reuse extraction")):
            refreshed = self.refresh(progress_callback=lambda phase, message: events.append((phase, message)))
        self.assertFalse(refreshed["unchanged"])
        self.assertNotIn("ocr", [phase for phase, _ in events])
        self.assertFalse(any("rasteriz" in message.lower() for _, message in events))
        self.assertTrue(any(phase == "read" and "retained" in message.lower() for phase, message in events))
        self.assertEqual(events[-1][0], "complete")

    def test_changed_pdf_progress_reports_actual_extraction(self):
        self.pdf.write_bytes(b"%PDF-1.4 changed synthetic metadata fixture")
        events = []

        def extract(path, **kwargs):
            self.assertIn("ocr", [phase for phase, _ in events])
            self.assertFalse(any("retained" in message.lower() for _, message in events))
            return self.extraction(self.text)

        with patch("lixity.research.api.extract_pdf_document", side_effect=extract):
            refreshed = self.refresh(progress_callback=lambda phase, message: events.append((phase, message)))
        self.assertFalse(refreshed["unchanged"])
        self.assertEqual([phase for phase, _ in events].count("ocr"), 1)
        self.assertEqual(events[-1][0], "complete")

    def test_context_refresh_dry_run_does_not_publish(self):
        before = self.retained_files()
        with patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("Identical PDF must reuse extraction")):
            preview = self.refresh(dry_run=True)
        self.assertFalse(preview["unchanged"])
        self.assertTrue(preview["dry_run"])
        self.assertEqual(preview["snapshot"], self.initial.digest)
        self.assertEqual(self.retained_files(), before)

    def test_corrupt_original_blob_stops_refresh_without_reextraction(self):
        version = self.initial.records[self.first["source_version_id"]]
        (self.repository.data / "blobs" / version.blob.sha256).write_bytes(b"Corrupt retained PDF")
        self.assert_corruption_stops_refresh()

    def test_corrupt_text_blob_stops_refresh_without_reextraction(self):
        (self.repository.data / "blobs" / self.initial_extraction.text_blob.sha256).write_bytes(b"Corrupt retained text")
        self.assert_corruption_stops_refresh()

    def test_mismatched_retained_span_stops_refresh(self):
        passage = self.initial_passages[0]
        broken = passage.model_copy(update={"start": passage.start + 1, "end": passage.end + 1})
        entries = []
        for entry in self.initial.manifest.entries:
            if entry.ref.id == passage.id:
                content = encode(broken)
                self.repository.record_path(entry).write_bytes(content)
                entries.append(entry.model_copy(update={"sha256": digest(content)}))
            else:
                entries.append(entry)
        manifest = self.initial.manifest.model_copy(update={"entries": entries})
        manifest_bytes = encode(manifest)
        checksum = digest(manifest_bytes)
        (self.repository.data / "manifests" / f"{checksum}.json").write_bytes(manifest_bytes)
        (self.repository.data / "HEAD.json").write_bytes(encode(Head(sha256=checksum)))
        self.assert_corruption_stops_refresh("Retained PDF extraction does not match its passages")

    def test_changed_pdf_bytes_require_a_new_extraction(self):
        self.pdf.write_bytes(b"%PDF-1.4 changed synthetic metadata fixture")
        updated_text = "The reading room opened in 1925."
        with patch("lixity.research.api.extract_pdf_document", return_value=self.extraction(updated_text)):
            refreshed = self.refresh()
        self.assertFalse(refreshed["unchanged"])
        latest = api.get_source(self.project, self.first["source_id"])
        self.assertEqual(latest["text"], updated_text)
        self.assertNotEqual(latest["sha256"], self.initial.records[self.first["source_version_id"]].blob.sha256)
        self.assertEqual(api.cite(self.project, self.initial_passages[1].id)["verbatim"],
                         "The reading room opened in 1924.")
