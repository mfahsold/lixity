"""Portable research stores evidence independently of manuscript analysis."""

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from lixity.research import api
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
        self.ingest()
        api.reindex(self.project)
        passage = api.search(self.project, "1924")["hits"][0]["passage_id"]
        blob = next((self.project / "research" / "blobs").rglob("*"))
        blob.write_bytes(b"tampered")
        with self.assertRaises(ResearchError):
            api.cite(self.project, passage)
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


