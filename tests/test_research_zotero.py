"""Synthetic Zotero responses exercise the optional local read-only bridge."""

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from lixity.research import api, zotero
from lixity.research.repository import Repository, ResearchError


class TestZotero(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / "project"
        api.init(self.project, title="Synthetic research")
        self.file = self.root / "synthetic.txt"
        self.file.write_text("The reading room opened in 1924.", encoding="utf-8")
        self.parent = {"key": "ABCDEFGH", "version": 3, "data": {
            "itemType": "book", "title": "Synthetic history", "date": "1924",
            "creators": [{"firstName": "Mara", "lastName": "Example"}],
            "url": "https://example.org/history"}}
        self.attachment = {"key": "JKLMNPQR", "version": 2, "data": {
            "itemType": "attachment", "parentItem": "ABCDEFGH", "title": "Scan",
            "contentType": "text/plain", "linkMode": "linked_file"}}

    def response(self, path):
        if path.endswith("/file/view/url"):
            return self.file.as_uri().encode(), "test-instance"
        if path.endswith("/items/JKLMNPQR"):
            return json.dumps(self.attachment).encode(), "test-instance"
        if path.endswith("/items/ABCDEFGH"):
            return json.dumps(self.parent).encode(), "test-instance"
        if "/children?" in path:
            return json.dumps([self.attachment]).encode(), "test-instance"
        return json.dumps([self.parent]).encode(), "test-instance"

    def test_browse_is_read_only_and_paged(self):
        before = Repository(self.project).snapshot().digest
        with patch.object(zotero, "_request", side_effect=self.response) as request:
            result = zotero.browse(self.project, library="users/0", query="room & book", limit=1, start=4)
            self.assertIn("q=room+%26+book", request.call_args.args[0])
            self.assertIn("start=4", request.call_args.args[0])
            self.assertEqual(result["items"][0]["key"], "ABCDEFGH")
            detail = zotero.browse(self.project, library="users/0", item_key="ABCDEFGH")
            self.assertEqual(detail["attachments"][0]["key"], "JKLMNPQR")
        self.assertEqual(Repository(self.project).snapshot().digest, before)

    def test_import_preserves_provenance_citations_and_explicit_refresh(self):
        with patch.object(zotero, "_request", side_effect=self.response):
            result = zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR", allow_retention=True)
            source = api.get_source(self.project, result["source_id"])
            passage = source["passages"][0]["id"]
            self.assertEqual(source["context"]["origin_url"], "https://example.org/history")
            self.assertIn("test-instance", source["context"]["provenance_note"])
            self.assertIn("JKLMNPQR", source["context"]["provenance_note"])
            self.assertIn("Mara Example", source["context"]["provenance_note"])
            self.assertTrue(zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR",
                                         source_id=result["source_id"], allow_retention=True)["unchanged"])
            self.file.write_text("The reading room opened in 1925.", encoding="utf-8")
            zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR",
                          source_id=result["source_id"], allow_retention=True)
        self.assertIn("1924", api.cite(self.project, passage)["verbatim"])
        self.assertTrue(api.audit(self.project)["ok"])

    def test_retention_gate_and_dry_run(self):
        before = Repository(self.project).snapshot().digest
        with patch.object(zotero, "_request", side_effect=self.response) as request:
            with self.assertRaisesRegex(ResearchError, "retention"):
                zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR")
            request.assert_not_called()
            result = zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR",
                                   allow_retention=True, dry_run=True)
            self.assertTrue(result["dry_run"])
        self.assertEqual(Repository(self.project).snapshot().digest, before)

    def test_rejects_path_injection_and_unsupported_media(self):
        with patch.object(zotero, "_request", side_effect=self.response) as request:
            for library in ("../users/0", "users/0/items", "https://example.org", "groups/0"):
                with self.subTest(library=library), self.assertRaises(ResearchError):
                    zotero.browse(self.project, library=library)
            request.assert_not_called()
            self.attachment["data"]["contentType"] = "video/mp4"
            with self.assertRaisesRegex(ResearchError, "PDF or UTF-8"):
                zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR", allow_retention=True)
        self.assertEqual(api.audit(self.project)["records"], 1)

    def test_malformed_response_and_instance_change_do_not_write(self):
        before = Repository(self.project).snapshot().digest
        with patch.object(zotero, "_request", return_value=(b'{"error": true}', "instance")), self.assertRaises(ResearchError):
            zotero.browse(self.project, library="users/0")
        def changing(path):
            payload, instance = self.response(path)
            return payload, "other-instance" if path.endswith("/items/ABCDEFGH") else instance
        with patch.object(zotero, "_request", side_effect=changing), self.assertRaisesRegex(ResearchError, "instance"):
            zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR", allow_retention=True)
        self.assertEqual(Repository(self.project).snapshot().digest, before)

    def test_file_url_must_be_local_regular_file(self):
        for location in ("https://example.org/file.txt", "file://remote/share/file.txt", self.root.as_uri()):
            def response(path, location=location):
                return (location.encode(), "test-instance") if path.endswith("/file/view/url") else self.response(path)
            with self.subTest(location=location), patch.object(zotero, "_request", side_effect=response), self.assertRaises(ResearchError):
                zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR", allow_retention=True)
        self.assertEqual(api.audit(self.project)["records"], 1)

    def test_transport_is_loopback_get_only_and_rejects_redirects_and_large_responses(self):
        connection = MagicMock()
        response = connection.getresponse.return_value
        response.status = 200
        response.read.return_value = b"[]"
        response.getheader.return_value = "instance"
        with patch("http.client.HTTPConnection", return_value=connection) as factory:
            self.assertEqual(zotero._request("users/0/items/top"), (b"[]", "instance"))
            factory.assert_called_once_with("127.0.0.1", 23119, timeout=10)
            connection.request.assert_called_once_with("GET", "/api/users/0/items/top", headers={"Zotero-API-Version": "3"})
            for status in (302, 403, 404):
                response.status = status
                with self.subTest(status=status), self.assertRaises(ResearchError):
                    zotero._request("users/0/items/top")
            response.status = 200
            response.read.return_value = b"x" * (zotero.MAX_RESPONSE_BYTES + 1)
            with self.assertRaises(ResearchError):
                zotero._request("users/0/items/top")
        self.assertTrue(connection.close.called)

    def test_cli_capture_export_restore_and_refresh_mismatch(self):
        from lixity.cli import main
        output = io.StringIO()
        with patch.object(zotero, "_request", side_effect=self.response), contextlib.redirect_stdout(output):
            code = main(["research", "zotero-ingest", "--project", str(self.project), "--library", "users/0",
                         "--attachment-key", "JKLMNPQR", "--allow-retention"])
        self.assertEqual(code, 0)
        result = json.loads(output.getvalue())
        archive = self.root / "backup.tar.gz"
        api.export_archive(self.project, archive)
        restored = self.root / "restored"
        api.restore_archive(archive, restored)
        self.assertEqual(api.get_source(restored, result["source_id"])["context"],
                         api.get_source(self.project, result["source_id"])["context"])
        ordinary = api.ingest(self.project, self.file, allow_retention=True)
        with patch.object(zotero, "_request", side_effect=self.response), self.assertRaisesRegex(ResearchError, "match"):
            zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR",
                          source_id=ordinary["source_id"], allow_retention=True)

    def test_missing_instance_allows_capture_but_not_refresh(self):
        def response(path):
            return self.response(path)[0], None
        with patch.object(zotero, "_request", side_effect=response):
            result = zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR", allow_retention=True)
            with self.assertRaisesRegex(ResearchError, "server identity"):
                zotero.ingest(self.project, library="users/0", attachment_key="JKLMNPQR",
                              source_id=result["source_id"], allow_retention=True)

    def test_migration_export_is_additive_exact_and_refuses_overwrite(self):
        first = api.ingest(self.project, self.file, title="Title\nER  -\nTY  - BOOK", allow_retention=True)
        hidden = api.ingest(self.project, self.file, title="Withdrawn", allow_retention=True)
        api.withdraw(self.project, hidden['source_id'])
        before = Repository(self.project).snapshot().digest
        destination = self.root / 'migration'
        preview = zotero.export_library(self.project, destination, allow_retention=True, dry_run=True)
        self.assertEqual(preview['sources'], 1)
        self.assertFalse(destination.exists())
        result = zotero.export_library(self.project, destination, allow_retention=True)
        manifest = json.loads((destination/'migration.json').read_text())
        self.assertEqual(manifest['sources'][0]['source_id'], first['source_id'])
        self.assertEqual((destination/manifest['sources'][0]['file']).read_bytes(), self.file.read_bytes())
        self.assertEqual((destination/'library.ris').read_text().count('\nER  -\n'), 1)
        self.assertEqual(result['sources'], 1)
        self.assertEqual(Repository(self.project).snapshot().digest, before)
        with self.assertRaises(ResearchError):
            zotero.export_library(self.project, destination, allow_retention=True)

    def test_structured_identity_deduplicates_and_requires_explicit_changed_refresh(self):
        with patch.object(zotero, '_request', side_effect=self.response):
            first = zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR', allow_retention=True)
            again = zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR', allow_retention=True)
            self.assertEqual(first['source_id'], again['source_id'])
            self.assertTrue(again['unchanged'])
            source = api.get_source(self.project, first['source_id'])
            external = source['context']['external_reference']
            self.assertEqual(external['attachment_key'], 'JKLMNPQR')
            self.assertEqual(external['provider'], 'zotero')
            self.assertEqual(Repository(self.project).snapshot().manifest.schema_version, 'research-manifest-local/3')
            self.file.write_text('Changed source text.', encoding='utf-8')
            with self.assertRaisesRegex(ResearchError, 'source-id'):
                zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR', allow_retention=True)
            zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR',
                          source_id=first['source_id'], allow_retention=True)

    def test_migration_binding_requires_matching_tag_and_exact_bytes(self):
        existing = api.ingest(self.project, self.file, allow_retention=True, context={'tags': ['kept'], 'provenance_note':'Original source criticism'})
        self.parent['data']['tags'] = [{'tag': 'lixity-source:' + existing['source_id'][9:]}]
        with patch.object(zotero, '_request', side_effect=self.response):
            result = zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR',
                                  source_id=existing['source_id'], allow_retention=True)
        self.assertEqual(result['source_id'], existing['source_id'])
        self.assertEqual(api.get_source(self.project, existing['source_id'])['context']['tags'], ['kept'])
        self.assertEqual(api.get_source(self.project, existing['source_id'])['context']['provenance_note'], 'Original source criticism')
        self.assertTrue(api.audit(self.project)['ok'])

    def test_collection_filter_and_preview_identity_prevent_wrong_capture(self):
        with patch.object(zotero, '_request', side_effect=self.response) as request:
            zotero.browse(self.project, library='users/0', collection_key='STUVWXYZ', query='history')
            self.assertIn('collections/STUVWXYZ/items/top?', request.call_args.args[0])
            with self.assertRaisesRegex(ResearchError, 'instance'):
                zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR',
                              expected_server_id='different', allow_retention=True)
        self.assertEqual(api.audit(self.project)['records'], 1)

    def test_external_reference_requires_v3_and_old_encoding_is_unchanged(self):
        from lixity.research.models import SourceVersion
        from lixity.research.repository import encode
        local = api.ingest(self.project, self.file, allow_retention=True)
        old = Repository(self.project).snapshot().records[local['source_version_id']]
        self.assertNotIn(b'external_reference', encode(old))
        with patch.object(zotero, '_request', side_effect=self.response):
            result = zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR', allow_retention=True)
        record = Repository(self.project).snapshot().records[result['source_version_id']]
        with self.assertRaisesRegex(ValueError, 'External reference requires'):
            SourceVersion.model_validate({**record.model_dump(), 'schema_version':'research-local/2'})

    def test_concurrent_project_change_requires_retry_before_capture(self):
        changed = False
        def response(path):
            nonlocal changed
            if not changed:
                api.create_dossier(self.project, title='Concurrent edit', body='Synthetic edit')
                changed = True
            return self.response(path)
        with patch.object(zotero, '_request', side_effect=response), self.assertRaisesRegex(ResearchError, 'snapshot'):
            zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR', allow_retention=True)
        self.assertEqual(api.list_sources(self.project)['sources'], [])

    def test_personal_library_aliases_share_identity_and_groups_stay_distinct(self):
        with patch.object(zotero, '_request', side_effect=self.response):
            first = zotero.ingest(self.project, library='users/123', attachment_key='JKLMNPQR', allow_retention=True)
            again = zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR', allow_retention=True)
            self.assertEqual(first['source_id'], again['source_id'])
            self.assertTrue(again['unchanged'])
            group = zotero.ingest(self.project, library='groups/123', attachment_key='JKLMNPQR', allow_retention=True)
            self.assertNotEqual(group['source_id'], first['source_id'])
            self.assertEqual(len(api.list_sources(self.project)['sources']), 2)

    def test_historical_personal_alias_keeps_identity_without_rewriting_capture(self):
        context = {'external_reference': {'provider':'zotero', 'server_id':'test-instance',
            'library':'users/123', 'item_key':'ABCDEFGH', 'attachment_key':'JKLMNPQR',
            'item_version':3, 'attachment_version':2}, 'origin_url':'https://example.org/history',
            'provenance_note':'Original historical provenance'}
        first = api.ingest(self.project, self.file, context=context, allow_retention=True)
        with patch.object(zotero, '_request', side_effect=self.response):
            again = zotero.ingest(self.project, library='users/0', attachment_key='JKLMNPQR', allow_retention=True)
        self.assertEqual(first['source_id'], again['source_id'])
        self.assertTrue(again['unchanged'])
