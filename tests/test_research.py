"""Portable research stores evidence independently of manuscript analysis."""

import argparse
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api, cli
from lixity.research.models import Decision, Dossier
from lixity.research.repository import Repository, ResearchError


class TestResearch(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "project"
        self.source = self.root / "source.txt"
        self.source.write_bytes("Café in Zürich.\r\n\r\nThe reading room opened in 1924.\r\n".encode())
        api.init(self.project, title="Research", language="en")

    def ingest(self, **kwargs):
        return api.ingest(self.project, self.source, allow_retention=True, **kwargs)

    def test_ingest_cite_and_search(self):
        result = self.ingest()
        self.assertEqual(result["passages"], 2)
        api.reindex(self.project)
        search = api.search(self.project, "reading room")
        self.assertEqual(len(search["hits"]), 1)
        citation = api.cite(self.project, search["hits"][0]["passage_id"])
        self.assertEqual(citation["verbatim"], "The reading room opened in 1924.")
        self.assertEqual(citation["source_title"], "source.txt")
        self.assertEqual(citation["verification"], "unreviewed")
        self.assertTrue(api.audit(self.project)["ok"])

    def test_origin_url_capture_refresh_and_citation(self):
        first = self.ingest(origin_url="https://example.org/archive?a=1&b=2#page")
        api.reindex(self.project)
        passage = api.search(self.project, "1924")["hits"][0]["passage_id"]
        snapshot = Repository(self.project).snapshot()
        self.assertEqual(snapshot.manifest.schema_version, "research-manifest-local/2")
        version = snapshot.records[first["source_version_id"]]
        self.assertEqual(version.schema_version, "research-local/2")
        self.assertTrue(self.ingest(source_id=first["source_id"])["unchanged"])
        refreshed = self.ingest(source_id=first["source_id"], origin_url="https://example.org/revised")
        self.assertFalse(refreshed["unchanged"])
        self.assertEqual(api.cite(self.project, passage)["context"]["origin_url"],
                         "https://example.org/archive?a=1&b=2#page")
        self.assertEqual(api.get_source(self.project, first["source_id"])["context"]["origin_url"],
                         "https://example.org/revised")
        self.assertTrue(api.audit(self.project)["ok"])

    def test_origin_url_rejects_invalid_input_without_writing(self):
        before = Repository(self.project).snapshot().digest
        for url in ("javascript:alert(1)", "file:///tmp/source", "https://", "not a URL",
                    "https://user:password@example.org/", "https://example.org/\n", 123,
                    "https://example.org/a b", "https://example.org:bad/"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                self.ingest(origin_url=url)
            self.assertEqual(Repository(self.project).snapshot().digest, before)

    def test_no_origin_url_keeps_version_one_encoding(self):
        from lixity.research.repository import encode
        result = self.ingest()
        snapshot = Repository(self.project).snapshot()
        self.assertEqual(snapshot.manifest.schema_version, "research-manifest-local/1")
        self.assertNotIn(b"origin_url", encode(snapshot.records[result["source_version_id"]]))

    def test_origin_url_requires_versioned_record_and_manifest(self):
        from dataclasses import replace

        from lixity.research.models import Manifest, SourceVersion

        result = self.ingest(origin_url="https://example.org/source")
        repository = Repository(self.project)
        snapshot = repository.snapshot()
        version = snapshot.records[result["source_version_id"]]
        with self.assertRaisesRegex(ValueError, "Origin URL requires"):
            SourceVersion.model_validate({**version.model_dump(), "schema_version": "research-local/1"})
        v1_manifest = Manifest.model_validate({**snapshot.manifest.model_dump(),
                                              "schema_version": "research-manifest-local/1"})
        with self.assertRaisesRegex(ResearchError, "manifest version 2"):
            repository.validate(replace(snapshot, manifest=v1_manifest))

    def test_origin_url_can_be_cleared_without_rewriting_citations(self):
        first = self.ingest(origin_url="https://example.org/source", context={"tags": ["note"]})
        detail = api.get_source(self.project, first["source_id"])
        passage = detail["passages"][0]["id"]
        self.ingest(source_id=first["source_id"], context={"tags": ["note"], "origin_url": None})
        latest = api.get_source(self.project, first["source_id"])
        self.assertNotIn("origin_url", latest["context"])
        self.assertEqual(latest["context"]["tags"], ["note"])
        self.assertEqual(api.cite(self.project, passage)["context"]["origin_url"], "https://example.org/source")

    def test_invalid_provenance_is_rejected_before_pdf_extraction(self):
        pdf = self.root / "synthetic.pdf"
        pdf.write_bytes(b"%PDF-1.4 synthetic invalid-input fixture")
        before = Repository(self.project).snapshot().digest
        with (
            patch("lixity.research.api.extract_pdf_document", side_effect=AssertionError("must not extract")),
            self.assertRaises(ValueError),
        ):
            api.ingest(self.project, pdf, allow_retention=True, origin_url="javascript:invalid")
        self.assertEqual(Repository(self.project).snapshot().digest, before)

    def test_cli_origin_url_reaches_source_context(self):
        from lixity.cli import main

        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = main(["research", "ingest", "--project", str(self.project),
                         "--file", str(self.source), "--allow-retention",
                         "--origin-url", "https://example.org/cli-source"])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        self.assertEqual(api.get_source(self.project, result["source_id"])["context"]["origin_url"],
                         "https://example.org/cli-source")

    def test_refresh_keeps_old_citations_and_excludes_old_search_hits(self):
        first = self.ingest()
        api.reindex(self.project)
        passage = api.search(self.project, "1924")["hits"][0]["passage_id"]
        self.source.write_text("The reading room opened in 1925.", encoding="utf-8")
        self.ingest(source_id=first["source_id"])
        with self.assertRaisesRegex(ResearchError, "reindex"):
            api.search(self.project, "1925")
        api.reindex(self.project)
        self.assertEqual(api.search(self.project, "1924")["hits"], [])
        self.assertEqual(len(api.search(self.project, "1925")["hits"]), 1)
        self.assertIn("1924", api.cite(self.project, passage)["verbatim"])

    def test_no_write_dry_run_and_retention_gate(self):
        before = sorted(str(path.relative_to(self.project)) for path in self.project.rglob("*"))
        with self.assertRaisesRegex(ResearchError, "retention"):
            api.ingest(self.project, self.source)
        result = self.ingest(dry_run=True)
        self.assertTrue(result["dry_run"])
        self.assertEqual(before, sorted(str(path.relative_to(self.project)) for path in self.project.rglob("*")))
        self.assertEqual(api.audit(self.project)["records"], 1)

    def test_idempotent_refresh_and_no_implicit_cross_source_deduplication(self):
        first = self.ingest()
        second = self.ingest(source_id=first["source_id"])
        self.assertTrue(second["unchanged"])
        self.assertEqual(first["snapshot"], second["snapshot"])
        separate = self.ingest()
        self.assertNotEqual(first["source_id"], separate["source_id"])

    def test_foreign_project_source_is_rejected(self):
        foreign = self.root / "other"
        api.init(foreign, title="Other")
        result = self.ingest()
        with self.assertRaises(ResearchError):
            api.ingest(foreign, self.source, source_id=result["source_id"], allow_retention=True)

    def test_failed_publication_preserves_head(self):
        before = Repository(self.project).snapshot().digest
        with patch("lixity.research.repository.replace_head", side_effect=OSError("interrupted")), self.assertRaises(OSError):
            self.ingest()
        self.assertEqual(Repository(self.project).snapshot().digest, before)
        self.assertEqual(api.audit(self.project)["records"], 1)
        self.ingest()
        self.assertTrue(api.audit(self.project)["ok"])

    def test_tampered_source_fails_citation_and_audit(self):
        source = self.ingest()
        self.assertEqual(
            api.get_source(self.project, source["source_id"])["passages"][1]["verbatim"],
            "The reading room opened in 1924.",
        )
        api.reindex(self.project)
        passage = api.search(self.project, "1924")["hits"][0]["passage_id"]
        blob = next((self.project / "research" / "blobs").rglob("*"))
        blob.write_bytes(b"tampered")
        with self.assertRaises(ResearchError):
            api.cite(self.project, passage)
        with self.assertRaises(ResearchError):
            api.get_source(self.project, source["source_id"])
        self.assertFalse(api.audit(self.project)["ok"])

    def test_catalogue_is_rebuildable_and_literal_query_is_safe(self):
        self.ingest()
        api.reindex(self.project)
        self.assertEqual(api.search(self.project, '" OR NOT () *')["hits"], [])
        catalogue = self.project / ".lixity" / "research" / "catalogue.sqlite3"
        catalogue.unlink()
        with self.assertRaises(ResearchError):
            api.search(self.project, "Café")
        api.reindex(self.project)
        self.assertEqual(len(api.search(self.project, "Café")["hits"]), 1)

    def test_scoped_search_cli_and_old_cache_rebuild(self):
        import sqlite3

        from lixity.cli import main

        self.ingest()
        dossier = api.create_dossier(self.project, "Synthetic inspector", "Plays the violin.")
        api.reindex(self.project)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(["research", "search", "--project", str(self.project),
                         "--query", "inspector", "--scope", "dossiers"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(output.getvalue())["hits"][0]["record_id"], dossier["dossier_id"])
        path = self.project / ".lixity/research/catalogue.sqlite3"
        with contextlib.closing(sqlite3.connect(path)) as connection, connection:
            connection.execute("DROP TABLE documents")
        self.assertEqual(len(api.search(self.project, "1924")["hits"]), 1)
        with self.assertRaisesRegex(ResearchError, "reindex"):
            api.search(self.project, "inspector", scope="all")
        api.reindex(self.project)
        self.assertEqual(len(api.search(self.project, "inspector", scope="all")["hits"]), 1)

    def test_combined_search_excludes_withdrawn_sources_and_checks_citation_bytes(self):
        source = self.ingest()
        api.reindex(self.project)
        self.assertEqual(len(api.search(self.project, "1924", scope="all")["hits"]), 1)
        api.withdraw(self.project, source["source_id"], reason="Synthetic withdrawal")
        api.reindex(self.project)
        self.assertEqual(api.search(self.project, "1924", scope="all")["hits"], [])
        self.ingest()
        api.reindex(self.project)
        blob = next((self.project / "research/blobs").rglob("*"))
        blob.write_bytes(b"tampered")
        with self.assertRaises(ResearchError):
            api.search(self.project, "1924", scope="all")

    def test_invalid_text_and_size_are_rejected(self):
        for content in (b"", b"\xff", b"binary\x00text", b" " * 20):
            self.source.write_bytes(content)
            with self.subTest(content=content), self.assertRaises(ResearchError):
                self.ingest()

    def test_cli_json_and_explicit_project(self):
        from lixity.cli import main

        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = main(["research", "audit", "--project", str(self.project)])
        self.assertEqual(code, 0)
        self.assertTrue(json.loads(stdout.getvalue())["ok"])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as error:
            main(["research", "audit"])
        self.assertEqual(error.exception.code, 2)

    def test_lock_contention_and_stale_expected_head(self):
        repository = Repository(self.project)
        previous = repository.snapshot()
        with repository.locked(), self.assertRaisesRegex(ResearchError, "busy"):
            self.ingest()
        self.ingest()
        with self.assertRaisesRegex(ResearchError, "changed"):
            repository.commit([], {}, previous)

    def test_restore_works_without_catalogue_or_working_directory(self):
        self.ingest()
        restored = self.root / "restored"
        shutil.copytree(self.project / "research", restored / "research")
        api.reindex(restored)
        self.assertEqual(len(api.search(restored, "1924")["hits"]), 1)
        self.assertTrue(api.audit(restored)["ok"])

    def test_tampered_record_and_head_are_rejected(self):
        repository = Repository(self.project)
        entry = repository.snapshot().manifest.entries[0]
        record = repository.record_path(entry)
        original = record.read_bytes()
        record.write_bytes(original + b" ")
        self.assertFalse(api.audit(self.project)["ok"])
        record.write_bytes(original)
        head = self.project / "research" / "HEAD.json"
        head.write_text('{"sha256":"../../escape"}', encoding="utf-8")
        with self.assertRaises(ResearchError):
            api.cite(self.project, entry.ref.id)

    def test_symlinked_internal_directories_are_rejected(self):
        target = self.root / "outside"
        target.mkdir()
        link = self.project / "research" / "blobs"
        try:
            link.symlink_to(target, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")
        with self.assertRaisesRegex(ResearchError, "Symlinks"):
            self.ingest()
        self.assertEqual(list(target.iterdir()), [])

    def test_schema_and_records_reject_unknown_fields_and_invalid_references(self):
        from pydantic import ValidationError

        from lixity.research.models import ENTITY, Passage

        repository = Repository(self.project)
        values = repository.snapshot().project.model_dump()
        for changes in ({"unexpected": True}, {"schema_version": "research-local/99"},
                        {"id": "../../outside"}, {"revision": True}, {"created_at": "2026-99-99T99:99:99.000000Z"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                ENTITY.validate_python({**values, **changes})
        self.ingest()
        passage = next(record for record in repository.snapshot().records.values() if isinstance(record, Passage))
        with self.assertRaises(ValidationError):
            ENTITY.validate_python({**passage.model_dump(), "end": passage.end + 1})
        self.assertEqual(api.schema()["$schema"], "https://json-schema.org/draft/2020-12/schema")

    def test_source_size_limit_and_query_bounds(self):
        self.source.write_bytes(b"a" * (api.MAX_SOURCE_BYTES + 1))
        with self.assertRaises(ResearchError):
            self.ingest()
        for query, limit in (("", 20), ("word", 0), ("word", True), ("a" * 1001, 1)):
            with self.subTest(query=query[:20], limit=limit), self.assertRaises(ResearchError):
                api.search(self.project, query, limit=limit)

    def test_corrupted_index_cannot_resurface_old_versions(self):
        import sqlite3

        first = self.ingest()
        api.reindex(self.project)
        old = api.search(self.project, "1924")["hits"][0]["passage_id"]
        self.source.write_text("Updated text.", encoding="utf-8")
        self.ingest(source_id=first["source_id"])
        api.reindex(self.project)
        with contextlib.closing(sqlite3.connect(self.project / ".lixity/research/catalogue.sqlite3")) as connection, connection:
            connection.execute("INSERT INTO passages VALUES (?, ?)", (old, "1924"))
        with self.assertRaisesRegex(ResearchError, "reindex"):
            api.search(self.project, "1924")

    def test_existing_project_is_never_reinitialized(self):
        before = Repository(self.project).snapshot().digest
        with self.assertRaises(ResearchError):
            api.init(self.project, title="Replacement")
        self.assertEqual(before, Repository(self.project).snapshot().digest)

    def test_cli_errors_do_not_echo_private_source_content(self):
        from lixity.cli import main

        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["research", "ingest", "--project", str(self.project), "--file", str(self.source)])
        self.assertEqual(code, 1)
        self.assertEqual(stdout.getvalue(), "")
        self.assertNotIn("1924", stderr.getvalue())

    def test_cli_discovery_and_core_import_isolation(self):
        import subprocess
        import sys

        from lixity import api as analysis_api
        from lixity.cli import main

        self.assertIn("research", [command["name"] for command in analysis_api.about()["commands"]])
        for shell in ("bash", "zsh"):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(["completion", shell]), 0)
            self.assertIn("research", output.getvalue())
            self.assertIn("--allow-retention", output.getvalue())
        result = subprocess.run([sys.executable, "-c", "import sys; import lixity.pipeline; print(any(name.startswith('lixity.research') for name in sys.modules))"], capture_output=True, text=True, check=True)
        self.assertEqual(result.stdout.strip(), "False")

    def test_sources_listing_and_dossier_management(self):
        ingested = self.ingest(context={"genre": "chronicle", "tags": ["dolomites", "history"]})
        sources = api.list_sources(self.project)
        self.assertEqual(len(sources["sources"]), 1)
        src = sources["sources"][0]
        self.assertEqual(src["id"], ingested["source_id"])
        self.assertEqual(src["tags"], ["dolomites", "history"])
        self.assertEqual(src["context"]["genre"], "chronicle")
        self.assertEqual(src["passages"], 2)

        details = api.get_source(self.project, ingested["source_id"])
        self.assertEqual(details["id"], ingested["source_id"])
        self.assertEqual(len(details["passages"]), 2)
        passage_id = details["passages"][0]["id"]

        # Create dossier referencing this passage
        dossier = api.create_dossier(
            self.project,
            "Alpine Historical Overview",
            "# Overview\n\nThe expedition was documented in detail.",
            tags=["overview", "mountains"],
            evidence_ids=[passage_id],
        )
        self.assertEqual(dossier["schema_version"], "research-dossier-local/1")
        dossiers = api.list_dossiers(self.project)
        self.assertEqual(len(dossiers["dossiers"]), 1)
        self.assertEqual(dossiers["dossiers"][0]["title"], "Alpine Historical Overview")
        self.assertEqual(dossiers["dossiers"][0]["tags"], ["overview", "mountains"])

        # Inspect dossier
        loaded = api.get_dossier(self.project, dossier["dossier_id"])
        self.assertEqual(loaded["title"], "Alpine Historical Overview")
        self.assertEqual(len(loaded["citations"]), 1)
        self.assertEqual(loaded["citations"][0]["passage_id"], passage_id)
        self.assertEqual(loaded["citations"][0]["verbatim"], "Café in Zürich.")

    def test_claims_evidence_links_and_decisions(self):
        ingested = self.ingest(context={"genre": "field-report"})
        details = api.get_source(self.project, ingested["source_id"])
        passage_id = details["passages"][0]["id"]

        # 1. Create a claim
        claim = api.create_claim(
            self.project,
            title="Café Treffpunkt 1912",
            statement="Das Café diente im Herbst 1912 als geheimer Treffpunkt.",
            confidence="evidenced",
            time_period="Herbst 1912",
            place="Zürich",
            actors=["Julian", "Elena"],
            tags=["geheimtreffen", "zuerich"],
        )
        self.assertEqual(claim["schema_version"], "research-claim-local/1")
        self.assertEqual(claim["title"], "Café Treffpunkt 1912")
        self.assertEqual(claim["confidence"], "evidenced")

        claims = api.list_claims(self.project)
        self.assertEqual(len(claims["claims"]), 1)
        c = claims["claims"][0]
        self.assertEqual(c["id"], claim["claim_id"])
        self.assertEqual(c["scope"]["place"], "Zürich")
        self.assertEqual(c["scope"]["actors"], ["Julian", "Elena"])

        # 2. Link evidence to claim
        link = api.link_evidence(
            self.project,
            claim_id=claim["claim_id"],
            passage_id=passage_id,
            relation="supports",
            rationale="Passage belegt Treffen im Café in Zürich.",
            reviewer="Dr. Historicus",
        )
        self.assertEqual(link["schema_version"], "research-evidence-link-local/1")
        self.assertEqual(link["relation"], "supports")

        links = api.list_evidence_links(self.project, claim_id=claim["claim_id"])
        self.assertEqual(len(links["evidence_links"]), 1)
        l_item = links["evidence_links"][0]
        self.assertEqual(l_item["id"], link["evidence_link_id"])
        self.assertEqual(l_item["relation"], "supports")
        self.assertEqual(l_item["citation"]["verbatim"], "Café in Zürich.")

        # 3. Record literary decision
        decision = api.record_decision(
            self.project,
            title="Verschiebung des Datums auf 1914",
            rationale="Für dramaturgischen Spannungsaufbau vor Kriegsausbruch.",
            claim_id=claim["claim_id"],
            deviation_from_fact=True,
            impact_on_plot="Erhöht die Bedrohungslage im zweiten Akt.",
        )
        self.assertEqual(decision["schema_version"], "research-decision-local/1")
        self.assertTrue(decision["deviation_from_fact"])

        decisions = api.list_decisions(self.project)
        self.assertEqual(len(decisions["decisions"]), 1)
        d_item = decisions["decisions"][0]
        self.assertEqual(d_item["id"], decision["decision_id"])
        self.assertEqual(d_item["claim_id"], claim["claim_id"])
        self.assertTrue(d_item["deviation_from_fact"])

        # 4. Error handling: link to non-existent claim or passage raises error
        with self.assertRaises(api.ResearchError):
            api.link_evidence(
                self.project,
                claim_id="urn:uuid:00000000-0000-4000-8000-000000000000",
                passage_id=passage_id,
            )

    def test_identical_pdf_metadata_refresh_reuses_verified_extraction(self):
        from lixity.research.ocr import OCRBlock, OCRExtractionResult
        pdf = self.root / 'scan.pdf'
        pdf.write_bytes(b'%PDF-1.4 synthetic extraction fixture')
        text = 'The reading room opened in 1924.'
        extracted = OCRExtractionResult(full_text=text, blocks=[OCRBlock(page_number=1, text=text)],
                                        spans=[(0,len(text))], pages=[])
        with patch('lixity.research.api.extract_pdf_document', return_value=extracted):
            first = api.ingest(self.project, pdf, allow_retention=True)
        with patch('lixity.research.api.extract_pdf_document', side_effect=AssertionError('unchanged bytes must reuse')):
            result = api.ingest(self.project, pdf, source_id=first['source_id'],
                                allow_retention=True, origin_url='https://example.org/metadata')
        self.assertFalse(result['unchanged'])
        self.assertTrue(api.audit(self.project)['ok'])

    def test_search_auto_refresh_and_strict_mode(self):
        self.ingest()
        api.reindex(self.project)
        self.assertEqual(len(api.search(self.project, "1924")["hits"]), 1)

        # Ingest a second file causing index to become stale
        second = self.root / "second.txt"
        second.write_text("UniqueKeyword123 appeared in the archive.", encoding="utf-8")
        api.ingest(self.project, second, allow_retention=True)

        # Strict mode (default in api.search) raises ResearchError
        with self.assertRaisesRegex(ResearchError, "reindex"):
            api.search(self.project, "UniqueKeyword123", ensure_fresh=False)

        # ensure_fresh=True automatically refreshes and finds the new hit
        res = api.search(self.project, "UniqueKeyword123", ensure_fresh=True)
        self.assertEqual(len(res["hits"]), 1)
        self.assertTrue(any("refreshed" in w for w in res.get("warnings", [])))

        # Query with 0 hits in sources includes hint to try --scope all
        no_hit_res = api.search(self.project, "NonExistentWordXYZ", ensure_fresh=True)
        self.assertEqual(no_hit_res["hits"], [])
        self.assertTrue(any("--scope all" in w for w in no_hit_res.get("warnings", [])))

    def test_dossier_bounded_reads_and_section_update(self):
        body = (
            "# Main Title\n\n"
            "Introductory text.\n\n"
            "## Background\n\n"
            "This is historical background.\n\n"
            "## Timeline\n\n"
            "1924: First opening.\n"
        )
        dossier = api.create_dossier(self.project, "Test Dossier", body)
        did = dossier["dossier_id"]

        # Summary view
        summary = api.get_dossier(self.project, did, summary=True)
        self.assertEqual(summary["sections"], ["Main Title", "Background", "Timeline"])
        self.assertIn("Introductory text", summary["excerpt"])
        self.assertFalse(summary["review_needed"])

        # Section-bounded read
        sec = api.get_dossier(self.project, did, section="Timeline")
        self.assertEqual(sec["section"], "Timeline")
        self.assertEqual(sec["content"], "1924: First opening.")

        # Full get_dossier includes sections and section_map
        full = api.get_dossier(self.project, did)
        self.assertEqual(full["sections"], ["Main Title", "Background", "Timeline"])
        self.assertIn("Background", full["section_map"])
        self.assertEqual(full["section_map"]["Timeline"], "1924: First opening.")

        # list_dossiers includes sections list
        dlist = api.list_dossiers(self.project)
        self.assertEqual(dlist["dossiers"][0]["sections"], ["Main Title", "Background", "Timeline"])

        # Non-existent section raises ResearchError
        with self.assertRaisesRegex(ResearchError, "Section 'Unknown' not found"):
            api.get_dossier(self.project, did, section="Unknown")

        # Section update helper
        updated_body = api.update_section(body, "Timeline", "1914: Altered opening date.")
        self.assertIn("1914: Altered opening date.", updated_body)
        self.assertNotIn("1924: First opening.", updated_body)
        self.assertIn("This is historical background.", updated_body)

        # Preamble extraction and heading-less dossier extraction
        preamble_body = "Opening preamble notes.\n\n## Timeline\n1924: Event."
        sections_preamble = api.extract_sections(preamble_body)
        self.assertIn("Overview", sections_preamble)
        self.assertEqual(sections_preamble["Overview"], "Opening preamble notes.")
        self.assertEqual(sections_preamble["Timeline"], "1924: Event.")

        headingless = "Single paragraph without any markdown headings."
        sections_plain = api.extract_sections(headingless)
        self.assertEqual(sections_plain.get("Overview"), headingless)

    def test_decision_dossier_linking_and_review_needed_tracking(self):
        dossier = api.create_dossier(self.project, "Charter Dossier", "## Facts\nFounded in 1924.")
        did = dossier["dossier_id"]

        # Record a decision linked to this dossier
        dec = api.record_decision(
            self.project,
            title="Alter charter date",
            rationale="Dramaturgic necessity",
            dossier_ids=[did],
            deviation_from_fact=True,
        )
        dec_id = dec["decision_id"]
        self.assertEqual(dec["dossier_ids"], [did])

        # Inspect dossier - decision was created after dossier -> flagged
        d_info = api.get_dossier(self.project, did)
        self.assertTrue(d_info["review_needed"])
        self.assertEqual(len(d_info["decision_reviews"]), 1)
        self.assertEqual(d_info["decision_reviews"][0]["decision_id"], dec_id)
        self.assertTrue(api.list_dossiers(self.project)["dossiers"][0]["review_needed"])

        # Revise dossier to incorporate the decision
        repo = Repository(self.project)
        snap = repo.snapshot()
        d_record = snap.latest(did, Dossier)
        revised_dossier = api.revise_record(
            self.project, "dossier", did,
            changes={"body": "## Facts\nFounded in 1914 per artistic decision."},
            expected_snapshot=snap.digest,
            expected_revision=d_record.revision,
            change_kind="correction",
            reason="Adopted altered date",
        )
        self.assertEqual(revised_dossier["record"]["revision"], 2)

        # Now dossier is revised after decision -> review is no longer needed
        d_info_after = api.get_dossier(self.project, did)
        self.assertFalse(d_info_after["review_needed"])
        self.assertEqual(d_info_after["decision_reviews"][0]["status"], "current")
        self.assertFalse(api.list_dossiers(self.project)["dossiers"][0]["review_needed"])

        # Now revise the decision again -> triggers review_needed again
        snap2 = repo.snapshot()
        dec_record = snap2.latest(dec_id, Decision)
        api.revise_record(
            self.project, "decision", dec_id,
            changes={"rationale": "Updated rationale for 1912."},
            expected_snapshot=snap2.digest,
            expected_revision=dec_record.revision,
            change_kind="correction",
            reason="Change plot date again",
        )
        d_info_redec = api.get_dossier(self.project, did)
        self.assertTrue(d_info_redec["review_needed"])
        self.assertEqual(d_info_redec["decision_reviews"][0]["status"], "review_needed")

        # Revise dossier a second time to adopt the new decision revision
        snap3 = repo.snapshot()
        d_record2 = snap3.latest(did, Dossier)
        api.revise_record(
            self.project, "dossier", did,
            changes={"body": "## Facts\nFounded in 1912 per second artistic decision."},
            expected_snapshot=snap3.digest,
            expected_revision=d_record2.revision,
            change_kind="correction",
            reason="Adopted second altered date",
        )
        d_info_redec_cleared = api.get_dossier(self.project, did)
        self.assertFalse(d_info_redec_cleared["review_needed"])
        self.assertEqual(d_info_redec_cleared["decision_reviews"][0]["status"], "current")

    def test_claim_matrix_json_md_csv(self):
        # 1. Empty matrix
        empty_json = api.claim_matrix(self.project, format="json")
        self.assertEqual(empty_json["summary"]["total_claims"], 0)
        self.assertEqual(empty_json["claims"], [])

        empty_md = api.claim_matrix(self.project, format="md")
        self.assertIn("# Research Claim-Evidence Matrix: Research", empty_md)
        self.assertIn("*(no claims recorded)*", empty_md)

        empty_csv = api.claim_matrix(self.project, format="csv")
        self.assertIn("claim_id,title,confidence", empty_csv)

        # 2. Add source, claim, evidence link, and decision
        ingested = self.ingest()
        details = api.get_source(self.project, ingested["source_id"])
        pid = details["passages"][0]["id"]

        claim = api.create_claim(
            self.project,
            title="Meeting 1912",
            statement="Secret meeting took place in Zurich.",
            confidence="evidenced",
            place="Zürich",
        )
        cid = claim["claim_id"]

        api.link_evidence(
            self.project,
            claim_id=cid,
            passage_id=pid,
            relation="supports",
            rationale="Witness account",
        )

        api.record_decision(
            self.project,
            title="Shift to 1914",
            rationale="Better narrative pacing",
            claim_id=cid,
            deviation_from_fact=True,
        )

        # 3. Verify JSON output
        matrix = api.claim_matrix(self.project, format="json")
        self.assertEqual(matrix["schema_version"], "research-claim-matrix-local/1")
        self.assertEqual(matrix["summary"]["total_claims"], 1)
        self.assertEqual(matrix["summary"]["supported_claims"], 1)
        self.assertEqual(matrix["summary"]["deviation_claims"], 1)
        self.assertEqual(matrix["summary"]["total_evidence_links"], 1)
        self.assertEqual(matrix["summary"]["total_decisions"], 1)
        c_entry = matrix["claims"][0]
        self.assertEqual(c_entry["claim_id"], cid)
        self.assertEqual(c_entry["status"], "supported")
        self.assertTrue(c_entry["has_deviation"])
        self.assertEqual(len(c_entry["evidence"]), 1)
        self.assertEqual(len(c_entry["decisions"]), 1)

        # 4. Verify Markdown output
        matrix_md = api.claim_matrix(self.project, format="md")
        self.assertIn("Meeting 1912", matrix_md)
        self.assertIn("[DEVIATION]", matrix_md)
        self.assertIn("+1 / -0", matrix_md)

        # 5. Verify CSV output
        matrix_csv = api.claim_matrix(self.project, format="csv")
        self.assertIn("Meeting 1912", matrix_csv)
        self.assertIn("Shift to 1914", matrix_csv)
        self.assertIn("yes", matrix_csv)

    def test_cli_matrix_dispatch(self):
        parser = argparse.ArgumentParser()
        cli.configure(parser)

        # 1. Test matrix md stdout
        args_md = parser.parse_args(["matrix", "--project", str(self.project), "--format", "md"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.run(args_md)
        self.assertEqual(code, 0)
        self.assertIn("# Research Claim-Evidence Matrix", buf.getvalue())

        # 2. Test matrix csv output file
        out_file = self.root / "matrix.csv"
        args_csv = parser.parse_args(["matrix", "--project", str(self.project), "--format", "csv", "--output", str(out_file)])
        code = cli.run(args_csv)
        self.assertEqual(code, 0)
        self.assertTrue(out_file.is_file())
        self.assertIn("claim_id,title", out_file.read_text(encoding="utf-8"))

    def test_cli_ocr_status_probe(self):
        parser = argparse.ArgumentParser()
        cli.configure(parser)

        args = parser.parse_args(["ocr-status", "--probe"])
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = cli.run(args)
        self.assertEqual(code, 0)
        data = json.loads(buf.getvalue())
        self.assertIn("probe", data)
        self.assertIn("status", data)

