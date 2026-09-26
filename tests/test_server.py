"""Tests for lixity.server – loopback development server and interactive dashboard."""

import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.parse import quote

from lixity.server import (
    LixityServerHandler,
    build_server_dashboard,
    run_server,
    sanitize_filename,
)


class TestLixityServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.exports_dir = os.path.join(cls.temp_dir.name, "exports")
        os.makedirs(cls.exports_dir, exist_ok=True)
        LixityServerHandler.source_input = None
        LixityServerHandler.workspace_root = cls.temp_dir.name
        LixityServerHandler.exports_dir = cls.exports_dir
        LixityServerHandler.language = "en"
        LixityServerHandler.title = "Test Dashboard"
        LixityServerHandler.title_custom = False
        LixityServerHandler.refresh()

        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), LixityServerHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.port = cls.server.server_port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)
        cls.temp_dir.cleanup()

    def make_request(
        self,
        path: str = "/",
        method: str = "GET",
        body: str | bytes | None = None,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, bytes, dict[str, str]]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        req_headers = {"Host": f"127.0.0.1:{self.port}"}
        if headers:
            req_headers.update(headers)
        try:
            conn.request(method, path, body=body, headers=req_headers)
            resp = conn.getresponse()
            resp_body = resp.read()
            resp_headers = {k.lower(): v for k, v in resp.getheaders()}
            return resp.status, resp_body, resp_headers
        finally:
            conn.close()

    def test_sanitize_filename(self):
        self.assertEqual(sanitize_filename("normal.md"), "normal.md")
        self.assertEqual(sanitize_filename("../../../etc/passwd.md"), "passwd.md")
        self.assertEqual(sanitize_filename("bad;file|name.md"), "manuscript.md")
        self.assertEqual(sanitize_filename(""), "manuscript.md")
        self.assertEqual(sanitize_filename(None), "manuscript.md")

    def test_build_server_dashboard_empty(self):
        html, info = build_server_dashboard(None, language="en", title="Empty Project")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("Empty Project", html)
        self.assertIn('id="btn-modal-open-project"', html)
        self.assertIn('id="settings-form"', html)
        self.assertIn('id="research-manager"', html)
        self.assertIn('data-action="analyze"', html)
        self.assertIn('data-action="rebuild"', html)
        for absent in ('id="ms-file"', 'id="nda-manager"', 'data-action="export"',
                       'data-action="sync"', 'data-action="audit"', 'data-action="prune"',
                       'data-action="gdrive"'):
            self.assertNotIn(absent, html)
        self.assertEqual(info["chapters"], 0)
        self.assertEqual(info["paragraphs"], 0)
        self.assertTrue(info["is_empty"])

    def test_build_server_dashboard_with_file(self):
        with tempfile.TemporaryDirectory() as td:
            ms = Path(td) / "book.md"
            ms.write_text("## Chapter 1\n\nIt was a dark and stormy night.\n", encoding="utf-8")
            html, info = build_server_dashboard(str(ms), language="en")
            self.assertIn("<!DOCTYPE html>", html)
            self.assertEqual(info["chapters"], 1)
            self.assertEqual(info["paragraphs"], 1)
            self.assertFalse(info["is_empty"])

    def test_get_dashboard_ok(self):
        status, body, headers = self.make_request("/")
        self.assertEqual(status, 200)
        self.assertIn(b"<!DOCTYPE html>", body)
        self.assertIn(b'id="research-manager"', body)
        self.assertTrue(headers.get("content-type", "").startswith("text/html"))
        self.assertEqual(headers.get("x-frame-options"), "DENY")
        self.assertEqual(headers.get("x-content-type-options"), "nosniff")

    def test_project_paths_lists_one_level_and_preserves_project_state(self):
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in ("workspace_root", "source_input", "research_dir", "language", "title", "dashboard_html")
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Zulu").mkdir()
            (root / "alpha.md").mkdir()
            (root / ".hidden").mkdir()
            (root / "Notes.TXT").write_text("Synthetic note.\n", encoding="utf-8")
            (root / "a & 'note'.md").write_text("Synthetic note.\n", encoding="utf-8")
            (root / "other.pdf").write_bytes(b"%PDF synthetic")
            (root / ".private.md").write_text("Hidden.\n", encoding="utf-8")
            (root / "Zulu" / "nested.md").write_text("Nested.\n", encoding="utf-8")
            if os.name == "posix":
                os.mkdir(os.fsencode(root) + b"/bad-\xff.md")
            with patch("lixity.server.Path.home", return_value=root):
                status, body, _ = self.make_request("/api/project-paths")
            self.assertEqual(status, 200, body)
            result = json.loads(body)
            self.assertEqual(result["path"], str(root))
            self.assertEqual(result["parent"], str(root.parent))
            self.assertEqual(result["entries"], [
                {"name": "alpha.md", "path": str(root / "alpha.md"), "kind": "directory"},
                {"name": "Zulu", "path": str(root / "Zulu"), "kind": "directory"},
                {"name": "a & 'note'.md", "path": str(root / "a & 'note'.md"), "kind": "manuscript"},
                {"name": "Notes.TXT", "path": str(root / "Notes.TXT"), "kind": "manuscript"},
            ])
            self.assertFalse(result["truncated"])
            status, body, _ = self.make_request(f"/api/project-paths?path={quote(str(root / 'Notes.TXT'), safe='')}")
            self.assertEqual(status, 200, body)
            self.assertEqual(json.loads(body)["path"], str(root))
            empty = root / "Zulu"
            status, body, _ = self.make_request(f"/api/project-paths?path={quote(str(empty), safe='')}")
            self.assertEqual(status, 200, body)
            self.assertEqual(json.loads(body)["entries"], [{
                "name": "nested.md", "path": str(empty / "nested.md"), "kind": "manuscript",
            }])
            self.assertEqual(
                {name: getattr(LixityServerHandler, name) for name in original_state}, original_state,
            )

    def test_project_paths_errors_origin_and_bounded_listing(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "item.pdf").write_text("Not a manuscript.\n", encoding="utf-8")
            for i in range(201):
                (root / f"folder-{i:03d}").mkdir()
            path = f"/api/project-paths?path={quote(str(root), safe='')}"
            status, body, _ = self.make_request(path)
            self.assertEqual(status, 200, body)
            result = json.loads(body)
            self.assertEqual(len(result["entries"]), 200)
            self.assertTrue(result["truncated"])
            self.assertEqual(result["entries"][0]["name"], "folder-000")
            self.assertEqual(result["entries"][-1]["name"], "folder-199")
            (root / "empty").mkdir()
            status, body, _ = self.make_request(
                f"/api/project-paths?path={quote(str(root / 'empty'), safe='')}"
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(json.loads(body)["entries"], [])
            for target, expected in ((root / "missing", 404), (root / "item.pdf", 400)):
                status, body, _ = self.make_request(f"/api/project-paths?path={quote(str(target), safe='')}")
                self.assertEqual(status, expected, body)
                self.assertFalse(json.loads(body)["ok"])
            with patch("lixity.server.os.scandir", side_effect=PermissionError("denied")):
                status, body, _ = self.make_request(path)
            self.assertEqual(status, 403, body)
            self.assertFalse(json.loads(body)["ok"])
            for headers in ({"Origin": "http://evil.example"}, {"Host": "evil.example"}):
                status, body, _ = self.make_request(path, headers=headers)
                self.assertEqual(status, 403, body)
                self.assertFalse(json.loads(body)["ok"])
    def test_untrusted_host_forbidden(self):
        status, body, _ = self.make_request("/", headers={"Host": "evil.example.com"})
        self.assertEqual(status, 403)
        self.assertIn(b"Untrusted Host forbidden", body)

    def test_cross_origin_post_forbidden(self):
        status, body, _ = self.make_request(
            "/api/rebuild",
            method="POST",
            body="{}",
            headers={
                "Origin": "http://evil.example.com",
                "Content-Type": "application/json",
            },
        )
        self.assertEqual(status, 403)
        self.assertIn(b"Cross-origin request forbidden", body)

    def test_post_invalid_content_type(self):
        status, _, _ = self.make_request(
            "/api/rebuild",
            method="POST",
            body="{}",
            headers={"Content-Type": "text/plain"},
        )
        self.assertEqual(status, 415)

    def test_post_payload_too_large(self):
        status, _, _ = self.make_request(
            "/api/rebuild",
            method="POST",
            body="{}",
            headers={
                "Content-Type": "application/json",
                "Content-Length": str(10 * 1024 * 1024),
            },
        )
        self.assertEqual(status, 413)

    def test_post_rebuild_success(self):
        status, body, _ = self.make_request(
            "/api/rebuild",
            method="POST",
            body="{}",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        self.assertIn(b'"ok": true', body)

    def test_post_settings_validation(self):
        # Invalid: z_strong < z_mild
        status, _, _ = self.make_request(
            "/api/settings",
            method="POST",
            body='{"z_mild": 4.0, "z_strong": 2.0}',
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 400)

        # Valid settings
        status, body, _ = self.make_request(
            "/api/settings",
            method="POST",
            body='{"z_mild": 2.0, "z_strong": 3.0, "fdr_q": 0.1, "language": "en"}',
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        self.assertIn(b'"ok": true', body)

    def test_settings_preserve_threshold_fields_not_exposed_in_ui(self):
        from lixity.style_fingerprint import FingerprintThresholds

        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in ("language", "title", "title_custom", "thresholds", "dashboard_html", "dashboard_info")
        }
        try:
            LixityServerHandler.thresholds = FingerprintThresholds(fdr_method="by", min_chapters=5)
            status, body, _ = self.make_request(
                "/api/settings", method="POST",
                body=json.dumps({"language": "fr"}),
                headers={"Content-Type": "application/json"},
            )
            self.assertEqual(status, 200, body)
            self.assertEqual(LixityServerHandler.thresholds.fdr_method, "by")
            self.assertEqual(LixityServerHandler.thresholds.min_chapters, 5)
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_research_compare_uses_current_analysis_language(self):
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in ("research_dir", "source_input", "language")
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                project = Path(td)
                (project / "research").mkdir()
                manuscript = project / "manuscript.md"
                manuscript.write_text("## Kapitel\n\nEin synthetischer Absatz.\n", encoding="utf-8")
                LixityServerHandler.research_dir = str(project)
                LixityServerHandler.source_input = str(manuscript)
                LixityServerHandler.language = "de"
                with patch("lixity.server.research_api.compare_source", return_value={"summary": {}}) as compare:
                    status, body, _ = self.make_request(
                        "/api/research-compare", method="POST",
                        body=json.dumps({"source_id": "synthetic-source"}),
                        headers={"Content-Type": "application/json"},
                    )
                self.assertEqual(status, 200, body)
                compare.assert_called_once_with(
                    project, "synthetic-source", str(manuscript), language="de",
                )
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_post_load_and_markers(self):
        sample_text = "## Act 1\n\nFirst line of the story.\nSecond line.\n"
        payload = json.dumps({"name": "loaded_novel.md", "content": sample_text})

        # Load manuscript
        status, body, _ = self.make_request(
            "/api/load",
            method="POST",
            body=payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        self.assertIn(b'"ok": true', body)
        self.assertEqual(LixityServerHandler.dashboard_info["chapters"], 1)

        # Add marker
        marker_payload = json.dumps({"kind": "pruefen", "line": 2, "note": "Check fact"})
        status, body, _ = self.make_request(
            "/api/marker-add",
            method="POST",
            body=marker_payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        self.assertIn(b'"ok": true', body)

        with open(LixityServerHandler.source_input, encoding="utf-8") as f:
            marked_text = f.read()
        self.assertIn("<!-- LIXITY-MARKER", marked_text)
        self.assertIn('kind="pruefen"', marked_text)

        # Resolve marker
        resolve_payload = json.dumps({"id": "39937c60"})
        status, body, _ = self.make_request(
            "/api/marker-resolve",
            method="POST",
            body=resolve_payload,
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(status, 200)
        self.assertIn(b'"ok": true', body)

    def test_load_rejects_existing_saved_copy_without_switching_project(self):
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in ("workspace_root", "source_input", "exports_dir", "research_dir", "language", "title", "title_custom", "thresholds", "dashboard_html", "dashboard_info")
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                exports = Path(td) / "exports"
                saved = exports / "manuscripts" / "draft.md"
                saved.parent.mkdir(parents=True)
                original_bytes = b"## Original\n\nKeep these words.\n"
                saved.write_bytes(original_bytes)
                LixityServerHandler.workspace_root = td
                LixityServerHandler.exports_dir = str(exports)
                before_source = LixityServerHandler.source_input
                before_html = LixityServerHandler.dashboard_html
                status, body, _ = self.make_request(
                    "/api/load", method="POST",
                    body=json.dumps({"name": "draft.md", "content": "## Replacement\n\nNew words."}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 409, body)
                self.assertFalse(json.loads(body)["ok"])
                self.assertEqual(saved.read_bytes(), original_bytes)
                self.assertEqual(LixityServerHandler.source_input, before_source)
                self.assertEqual(LixityServerHandler.dashboard_html, before_html)
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_standalone_unsupported_actions_fail_without_refresh_or_artifacts(self):
        original_html = LixityServerHandler.dashboard_html
        original_source = LixityServerHandler.source_input
        before_artifacts = sorted(Path(self.exports_dir).glob("*"))
        with patch.object(LixityServerHandler, "refresh", side_effect=AssertionError("unexpected refresh")):
            for action in ("export", "sync", "audit", "prune", "gdrive"):
                with self.subTest(action=action):
                    status, body, _ = self.make_request(
                        f"/api/{action}", method="POST", body="{}",
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(status, 501, body)
                    self.assertFalse(json.loads(body)["ok"])
        self.assertEqual(LixityServerHandler.dashboard_html, original_html)
        self.assertEqual(LixityServerHandler.source_input, original_source)
        self.assertEqual(sorted(Path(self.exports_dir).glob("*")), before_artifacts)

    def test_analysis_and_rebuild_actions_refresh_successfully(self):
        for action in ("analyze", "rebuild"):
            with self.subTest(action=action):
                status, body, _ = self.make_request(
                    f"/api/{action}", method="POST", body="{}",
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200, body)
                data = json.loads(body)
                self.assertTrue(data["ok"])
                self.assertTrue(data["reload"])

    def test_artifact_serving_and_traversal_protection(self):
        test_pdf = Path(self.exports_dir) / "novel.pdf"
        test_pdf.write_bytes(b"%PDF-1.4 sample content")

        # Valid artifact fetch
        status, body, headers = self.make_request("/artifact/novel.pdf")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"%PDF-1.4 sample content")
        self.assertEqual(headers.get("content-type"), "application/pdf")

        # Directory traversal attempt
        status, _, _ = self.make_request("/artifact/../../etc/passwd")
        self.assertEqual(status, 404)

    def test_run_server_validation(self):
        with self.assertRaises(ValueError):
            run_server(host="192.168.1.100")

    def test_research_endpoints_workflow(self):
        with tempfile.TemporaryDirectory() as rdir:
            orig_rdir = LixityServerHandler.research_dir
            orig_ms = LixityServerHandler.source_input
            try:
                LixityServerHandler.research_dir = rdir
                ms_path = Path(rdir) / "ms.md"
                ms_path.write_text("## Chapter 1\n\nThe archives in Prague were quiet.", encoding="utf-8")
                LixityServerHandler.source_input = str(ms_path)

                # 1. Status before init
                status, body, _ = self.make_request("/api/research/status")
                self.assertEqual(status, 200)
                data = json.loads(body)
                self.assertFalse(data["initialized"])

                # 2. Init
                init_payload = json.dumps({"title": "Test Archive", "language": "en"})
                status, body, _ = self.make_request(
                    "/api/research-init",
                    method="POST",
                    body=init_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                data = json.loads(body)
                self.assertTrue(data["ok"])

                # 3. Ingest without retention fails
                bad_ingest = json.dumps({"content": "A historic letter from 1924.", "title": "Letter"})
                status, body, _ = self.make_request(
                    "/api/research-ingest",
                    method="POST",
                    body=bad_ingest,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 400)

                # 4. Ingest with retention succeeds
                ok_ingest = json.dumps({
                    "content": "The archives in Prague were established in 1924.\n\nThey contain letters.",
                    "title": "Prague Records",
                    "allow_retention": True,
                    "tags": ["history", "prague"],
                })
                status, body, _ = self.make_request(
                    "/api/research-ingest",
                    method="POST",
                    body=ok_ingest,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                src_res = json.loads(body)
                self.assertTrue(src_res["ok"])
                source_id = src_res["source_id"]

                # 5. List sources
                status, body, _ = self.make_request("/api/research/sources")
                self.assertEqual(status, 200)
                sources_data = json.loads(body)
                self.assertEqual(len(sources_data["sources"]), 1)
                self.assertEqual(sources_data["sources"][0]["tags"], ["history", "prague"])

                # 6. Search
                search_payload = json.dumps({"query": "Prague"})
                status, body, _ = self.make_request(
                    "/api/research-search",
                    method="POST",
                    body=search_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                search_res = json.loads(body)
                self.assertTrue(len(search_res["hits"]) >= 1)
                passage_id = search_res["hits"][0]["passage_id"]

                # 7. Create Dossier
                dossier_payload = json.dumps({
                    "title": "Prague Investigation",
                    "body": "Evidence confirms the establishment in 1924.",
                    "tags": ["summary"],
                    "evidence_ids": [passage_id],
                })
                status, body, _ = self.make_request(
                    "/api/research-dossier",
                    method="POST",
                    body=dossier_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                dos_res = json.loads(body)
                self.assertTrue(dos_res["ok"])

                # 8. List Dossiers
                status, body, _ = self.make_request("/api/research/dossiers")
                self.assertEqual(status, 200)
                dos_data = json.loads(body)
                self.assertEqual(len(dos_data["dossiers"]), 1)
                self.assertEqual(dos_data["dossiers"][0]["evidence_count"], 1)

                # 9. Compare source against manuscript
                cmp_payload = json.dumps({"source_id": source_id})
                status, body, _ = self.make_request(
                    "/api/research-compare",
                    method="POST",
                    body=cmp_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                cmp_res = json.loads(body)
                self.assertTrue(cmp_res["ok"])
                self.assertIn("jaccard_similarity", cmp_res["summary"])

                # 10. Create Claim
                claim_payload = json.dumps({
                    "title": "Establishment in 1924",
                    "statement": "The archives in Prague were established in 1924.",
                    "confidence": "evidenced",
                    "time_period": "1924",
                    "place": "Prague",
                    "actors": ["Archivist"],
                    "tags": ["founding"],
                })
                status, body, _ = self.make_request(
                    "/api/research-claim-add",
                    method="POST",
                    body=claim_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                cl_res = json.loads(body)
                self.assertTrue(cl_res["ok"])
                claim_id = cl_res["claim_id"]

                # 11. Link Evidence
                link_payload = json.dumps({
                    "claim_id": claim_id,
                    "passage_id": passage_id,
                    "relation": "supports",
                    "rationale": "Directly corroborates the year.",
                })
                status, body, _ = self.make_request(
                    "/api/research-evidence-link",
                    method="POST",
                    body=link_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                lk_res = json.loads(body)
                self.assertTrue(lk_res["ok"])

                # 12. List Claims & Evidence Links
                status, body, _ = self.make_request("/api/research/claims")
                self.assertEqual(status, 200)
                claims_data = json.loads(body)
                self.assertEqual(len(claims_data["claims"]), 1)

                status, body, _ = self.make_request(f"/api/research/claims?claim_id={claim_id}")
                self.assertEqual(status, 200)
                links_data = json.loads(body)
                self.assertEqual(len(links_data["evidence_links"]), 1)
                self.assertEqual(links_data["evidence_links"][0]["relation"], "supports")

                # 13. Record Decision
                dec_payload = json.dumps({
                    "title": "Set archive founding in 1910 for plot tension",
                    "rationale": "Allows characters to explore older secret records.",
                    "claim_id": claim_id,
                    "deviation_from_fact": True,
                    "impact_on_plot": "Adds pre-war tension to chapter 2.",
                })
                status, body, _ = self.make_request(
                    "/api/research-decision-add",
                    method="POST",
                    body=dec_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                dec_res = json.loads(body)
                self.assertTrue(dec_res["ok"])

                # 14. List Decisions
                status, body, _ = self.make_request("/api/research/decisions")
                self.assertEqual(status, 200)
                dec_data = json.loads(body)
                self.assertEqual(len(dec_data["decisions"]), 1)
                self.assertTrue(dec_data["decisions"][0]["deviation_from_fact"])

                # 15. Status after init & ingests & claims & decisions
                status, body, _ = self.make_request("/api/research/status")
                self.assertEqual(status, 200)
                st_data = json.loads(body)
                self.assertTrue(st_data["initialized"])
                self.assertEqual(st_data["sources_count"], 1)
                self.assertEqual(st_data["dossiers_count"], 1)
                self.assertEqual(st_data["claims_count"], 1)
                self.assertEqual(st_data["decisions_count"], 1)
            finally:
                LixityServerHandler.research_dir = orig_rdir
                LixityServerHandler.source_input = orig_ms

    def test_project_create_and_open_workflow(self):
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in (
                "workspace_root", "source_input", "exports_dir", "research_dir",
                "language", "title", "title_custom", "thresholds", "dashboard_html", "dashboard_info",
            )
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                # 1. Create minimal project
                proj_dir = Path(td) / "my-novel"
                create_payload = json.dumps({
                    "title": "Die Chroniken von Nebelwald",
                    "language": "de",
                    "path": str(proj_dir),
                    "template": "three_act",
                    "init_research": True,
                })
                status, body, _ = self.make_request(
                    "/api/project-create",
                    method="POST",
                    body=create_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                res = json.loads(body)
                self.assertTrue(res["ok"])
                self.assertTrue(proj_dir.is_dir())
                self.assertTrue((proj_dir / "manuscript.md").is_file())
                self.assertTrue((proj_dir / "lixity.toml").is_file())
                self.assertTrue((proj_dir / "research").is_dir())

                ms_text = (proj_dir / "manuscript.md").read_text(encoding="utf-8")
                self.assertIn("Erster Akt: Aufbruch", ms_text)
                self.assertIn("Zweiter Akt: Konfrontation", ms_text)
                self.assertIn("Dritter Akt: Rückkehr", ms_text)

                self.assertEqual(LixityServerHandler.workspace_root, str(proj_dir))
                self.assertEqual(LixityServerHandler.source_input, str(proj_dir / "manuscript.md"))

                # 2. Open project by path
                open_payload = json.dumps({"path": str(proj_dir)})
                status, body, _ = self.make_request(
                    "/api/project-open",
                    method="POST",
                    body=open_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                open_res = json.loads(body)
                self.assertTrue(open_res["ok"])
                self.assertEqual(open_res["workspace_root"], str(proj_dir))

                # 3. Open manuscript file explicitly
                open_file_payload = json.dumps({"path": str(proj_dir / "manuscript.md")})
                status, body, _ = self.make_request(
                    "/api/project-open",
                    method="POST",
                    body=open_file_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                open_file_res = json.loads(body)
                self.assertTrue(open_file_res["ok"])

                # 4. Error on non-existent path
                err_payload = json.dumps({"path": str(proj_dir / "non-existent")})
                status, body, _ = self.make_request(
                    "/api/project-open",
                    method="POST",
                    body=err_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 404)

                # 5. Create project with custom imported manuscript content
                proj_upload_dir = Path(td) / "uploaded-novel"
                imported_text = "    An indented opening.\r\n\r\n## Erstes Kapitel\r\n\r\nDer Wind pfiff durch die alten Gassen der Stadt.  "
                upload_payload = json.dumps({
                    "title": "Das verlorene Artefakt",
                    "language": "de",
                    "path": str(proj_upload_dir),
                    "content": imported_text,
                    "init_research": False,
                })
                status, body, _ = self.make_request(
                    "/api/project-create",
                    method="POST",
                    body=upload_payload,
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                upload_res = json.loads(body)
                self.assertTrue(upload_res["ok"])
                self.assertTrue((proj_upload_dir / "manuscript.md").is_file())
                self.assertEqual((proj_upload_dir / "manuscript.md").read_bytes(), imported_text.encode("utf-8"))
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_dashboard_welcome_hero_and_modals(self):
        # When no manuscript/chapters loaded, welcome hero and modals must be rendered
        html, info = build_server_dashboard(None, language="de", title="Lixity Empty")
        self.assertEqual(info["chapters"], 0)
        self.assertIn('id="welcome-hero"', html)
        self.assertIn('id="modal-project-create"', html)
        self.assertIn('id="modal-project-open"', html)
        self.assertIn('id="hero-btn-new-project"', html)
        self.assertIn('id="hero-btn-open-project"', html)
        self.assertIn('id="open-proj-path"', html)
        self.assertIn('id="link-switch-to-import"', html)
        self.assertIn('id="tab-btn-import"', html)
        self.assertIn('template-card', html)

        # Research tabs and controls
        self.assertIn('data-rtab="claims"', html)
        self.assertIn('data-rtab="decisions"', html)
        self.assertIn('id="r-claim-create-btn"', html)
        self.assertIn('id="r-decision-create-btn"', html)
        self.assertIn('id="r-link-evidence-btn"', html)

    def test_project_templates_use_the_selected_language_and_reloadable_settings(self):
        from lixity.config import load_project_config

        chapter_titles = {
            "en": "Chapter 1", "de": "Kapitel 1", "fr": "Chapitre 1",
            "es": "Capítulo 1", "it": "Capitolo 1", "pt": "Capítulo 1", "nl": "Hoofdstuk 1",
        }
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in ("workspace_root", "source_input", "exports_dir", "research_dir",
                         "language", "title", "title_custom", "thresholds", "dashboard_html", "dashboard_info")
        }
        try:
            with tempfile.TemporaryDirectory() as directory:
                for language, heading in chapter_titles.items():
                    with self.subTest(language=language):
                        project = Path(directory) / language
                        title = 'A "quoted" title \\ with a newline\nSecond line'
                        status, body, _ = self.make_request(
                            "/api/project-create", method="POST",
                            body=json.dumps({"title": title, "path": str(project), "language": language}),
                            headers={"Content-Type": "application/json"},
                        )
                        self.assertEqual(status, 200, body)
                        manuscript = project / "manuscript.md"
                        self.assertIn(f"## {heading}\n", manuscript.read_text(encoding="utf-8"))
                        settings = load_project_config(manuscript)
                        self.assertEqual(settings.get("language"), language)
                        self.assertEqual(settings.get("title"), title)

                existing = Path(directory) / "en"
                original_bytes = (existing / "manuscript.md").read_bytes()
                status, _, _ = self.make_request(
                    "/api/project-create", method="POST",
                    body=json.dumps({"title": "Import", "path": str(existing), "content": "Replacement"}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 409)
                self.assertEqual((existing / "manuscript.md").read_bytes(), original_bytes)
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_project_open_attaches_existing_research(self):
        from lixity.research import api as research_api
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in (
                "workspace_root", "source_input", "exports_dir", "research_dir",
                "language", "title", "title_custom", "thresholds", "dashboard_html", "dashboard_info",
            )
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                proj_dir = Path(td) / "existing-novel"
                proj_dir.mkdir()
                ms_path = proj_dir / "manuscript.md"
                ms_path.write_bytes(b"")
                source_path = Path(td) / "archive-note.txt"
                source_bytes = b"The reading room opened in 1924.\n\nThe inventory stayed on site.\n"
                source_path.write_bytes(source_bytes)
                research_api.init(proj_dir, title="Historical Research")
                source = research_api.ingest(
                    proj_dir, source_path, title="Archive Note", allow_retention=True,
                )
                passage_id = research_api.get_source(proj_dir, source["source_id"])["passages"][0]["id"]
                dossier = research_api.create_dossier(
                    proj_dir, "Reading Room File", "The opening date is recorded.",
                    evidence_ids=[passage_id],
                )
                claim = research_api.create_claim(
                    proj_dir, title="Opening date", statement="The room opened in 1924.",
                    confidence="evidenced", dossier_id=dossier["dossier_id"],
                )
                research_api.link_evidence(
                    proj_dir, claim_id=claim["claim_id"], passage_id=passage_id,
                )
                decision = research_api.record_decision(
                    proj_dir, title="Move opening date", rationale="Plot timing",
                    claim_id=claim["claim_id"], deviation_from_fact=True,
                )
                research_files = {
                    path.relative_to(proj_dir / "research"): path.read_bytes()
                    for path in (proj_dir / "research").rglob("*") if path.is_file()
                }

                for open_path in (proj_dir, ms_path):
                    with self.subTest(open_path=open_path):
                        status, body, _ = self.make_request(
                            "/api/project-open",
                            method="POST",
                            body=json.dumps({"path": str(open_path)}),
                            headers={"Content-Type": "application/json"},
                        )
                        self.assertEqual(status, 200)
                        opened = json.loads(body)
                        self.assertTrue(opened["ok"])
                        self.assertEqual(Path(opened["workspace_root"]).resolve(), proj_dir.resolve())
                        self.assertEqual(Path(opened["manuscript"]).resolve(), ms_path.resolve())
                        self.assertEqual(Path(LixityServerHandler.research_dir).resolve(), proj_dir.resolve())
                        self.assertTrue(LixityServerHandler.dashboard_info["is_empty"])

                        status, body, _ = self.make_request("/api/research/status")
                        self.assertEqual(status, 200)
                        research_status = json.loads(body)
                        self.assertTrue(research_status["initialized"])
                        self.assertEqual(research_status["project_title"], "Historical Research")
                        self.assertEqual(
                            tuple(research_status[key] for key in (
                                "sources_count", "dossiers_count", "claims_count", "decisions_count",
                            )),
                            (1, 1, 1, 1),
                        )

                        status, body, _ = self.make_request(
                            f"/api/research/sources?id={quote(source['source_id'], safe='')}"
                        )
                        self.assertEqual(status, 200)
                        source_data = json.loads(body)
                        self.assertEqual(source_data["id"], source["source_id"])
                        self.assertEqual(source_data["passages"][0]["verbatim"],
                                         "The reading room opened in 1924.")

                        status, body, _ = self.make_request(
                            f"/api/research/dossiers?id={quote(dossier['dossier_id'], safe='')}"
                        )
                        self.assertEqual(status, 200)
                        dossier_data = json.loads(body)
                        self.assertEqual(dossier_data["body"], "The opening date is recorded.")
                        self.assertEqual(dossier_data["citations"][0]["passage_id"], passage_id)

                        status, body, _ = self.make_request("/api/research/claims")
                        self.assertEqual(status, 200)
                        claim_data = json.loads(body)["claims"][0]
                        self.assertEqual(claim_data["id"], claim["claim_id"])
                        self.assertEqual(claim_data["statement"], "The room opened in 1924.")
                        self.assertEqual(claim_data["dossier_id"], dossier["dossier_id"])

                        status, body, _ = self.make_request(
                            f"/api/research/claims?claim_id={claim['claim_id']}"
                        )
                        self.assertEqual(status, 200)
                        evidence_link = json.loads(body)["evidence_links"][0]
                        self.assertEqual(evidence_link["passage_id"], passage_id)
                        self.assertEqual(evidence_link["citation"]["verbatim"],
                                         "The reading room opened in 1924.")

                        status, body, _ = self.make_request("/api/research/decisions")
                        self.assertEqual(status, 200)
                        decision_data = json.loads(body)["decisions"][0]
                        self.assertEqual(decision_data["id"], decision["decision_id"])
                        self.assertEqual(decision_data["claim_id"], claim["claim_id"])
                        self.assertTrue(decision_data["deviation_from_fact"])

                        self.assertEqual(ms_path.read_bytes(), b"")
                        self.assertEqual(source_path.read_bytes(), source_bytes)
                        self.assertEqual(
                            {
                                path.relative_to(proj_dir / "research"): path.read_bytes()
                                for path in (proj_dir / "research").rglob("*") if path.is_file()
                            },
                            research_files,
                        )
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_project_open_loads_target_settings_after_project_create(self):
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in (
                "workspace_root", "source_input", "exports_dir", "research_dir",
                "language", "title", "title_custom", "thresholds", "dashboard_html",
                "dashboard_info", "project_open_overrides",
            )
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                first = Path(td) / "first"
                status, body, _ = self.make_request(
                    "/api/project-create", method="POST",
                    body=json.dumps({"path": str(first), "title": "First title", "language": "de"}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200, body)
                status, body, _ = self.make_request(
                    "/api/settings", method="POST",
                    body=json.dumps({"title": "Edited first title"}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200, body)
                self.assertTrue(LixityServerHandler.title_custom)
                status, body, _ = self.make_request(
                    "/api/project-open", method="POST",
                    body=json.dumps({"path": str(first)}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200, body)
                self.assertEqual(LixityServerHandler.title, "Edited first title")
                second = Path(td) / "second"
                second.mkdir()
                manuscript = second / "manuscript.md"
                manuscript.write_text("## Chapter One\n\nA synthetic paragraph.\n", encoding="utf-8")
                (second / "lixity.toml").write_text(
                    'title = "Second title"\nlanguage = "fr"\nfdr_q = 0.12\n',
                    encoding="utf-8",
                )
                for path in (second, manuscript):
                    with self.subTest(path=path):
                        status, body, _ = self.make_request(
                            "/api/project-open", method="POST",
                            body=json.dumps({"path": str(path)}),
                            headers={"Content-Type": "application/json"},
                        )
                        self.assertEqual(status, 200, body)
                        self.assertEqual(LixityServerHandler.language, "fr")
                        self.assertEqual(LixityServerHandler.title, "Second title")
                        self.assertEqual(LixityServerHandler.thresholds.fdr_q, 0.12)
                        self.assertEqual(LixityServerHandler.dashboard_info["language_key"], "fr")
                        self.assertIn("Second title", LixityServerHandler.dashboard_html)

                LixityServerHandler.project_open_overrides = {
                    "language": "en", "title": "Session title", "fdr_q": 0.03,
                }
                status, body, _ = self.make_request(
                    "/api/project-open", method="POST",
                    body=json.dumps({"path": str(second)}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200, body)
                self.assertEqual(LixityServerHandler.language, "en")
                self.assertEqual(LixityServerHandler.title, "Session title")
                self.assertEqual(LixityServerHandler.thresholds.fdr_q, 0.03)
                self.assertIn("Session title", LixityServerHandler.dashboard_html)
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_project_open_invalid_targets_keep_current_project(self):
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in (
                "workspace_root", "source_input", "exports_dir", "research_dir",
                "language", "title", "title_custom", "thresholds", "dashboard_html",
                "dashboard_info", "project_open_overrides",
            )
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                project = Path(td) / "current"
                status, body, _ = self.make_request(
                    "/api/project-create", method="POST",
                    body=json.dumps({"path": str(project), "title": "Current title", "language": "en"}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200, body)
                before = {
                    name: getattr(LixityServerHandler, name)
                    for name in original_state
                }
                unsupported = Path(td) / "image.pdf"
                unsupported.write_bytes(b"%PDF synthetic")
                invalid = Path(td) / "invalid.md"
                invalid.write_bytes(b"\xff\xfe")
                folder = Path(td) / "invalid-folder"
                folder.mkdir()
                (folder / "manuscript.md").write_bytes(b"\xff\xfe")
                for path in (unsupported, invalid, folder):
                    with self.subTest(path=path):
                        status, body, _ = self.make_request(
                            "/api/project-open", method="POST",
                            body=json.dumps({"path": str(path)}),
                            headers={"Content-Type": "application/json"},
                        )
                        self.assertEqual(status, 400, body)
                        self.assertFalse(json.loads(body)["ok"])
                        self.assertEqual(
                            {name: getattr(LixityServerHandler, name) for name in before},
                            before,
                        )
                unreadable = Path(td) / "unreadable.md"
                unreadable.write_text("Synthetic manuscript.\n", encoding="utf-8")
                read_text = Path.read_text

                def fail_target_read(path, *args, **kwargs):
                    if path == unreadable:
                        raise PermissionError("Synthetic unreadable manuscript")
                    return read_text(path, *args, **kwargs)

                with patch.object(Path, "read_text", fail_target_read):
                    status, body, _ = self.make_request(
                        "/api/project-open", method="POST",
                        body=json.dumps({"path": str(unreadable)}),
                        headers={"Content-Type": "application/json"},
                    )
                self.assertEqual(status, 400, body)
                self.assertIn("Synthetic unreadable manuscript", json.loads(body)["message"])
                self.assertEqual(
                    {name: getattr(LixityServerHandler, name) for name in before}, before,
                )
                status, body, _ = self.make_request("/")
                self.assertEqual(status, 200)
                self.assertIn(b"Current title", body)
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_direct_run_server_title_stays_explicit_when_opening_another_project(self):
        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in (
                "workspace_root", "source_input", "exports_dir", "research_dir",
                "language", "title", "title_custom", "thresholds", "dashboard_html",
                "dashboard_info", "project_open_overrides",
            )
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                first = Path(td) / "first"
                second = Path(td) / "second"
                for project, title in ((first, "First title"), (second, "Second title")):
                    project.mkdir()
                    (project / "manuscript.md").write_text("## Chapter\n\nSynthetic text.\n", encoding="utf-8")
                    (project / "lixity.toml").write_text(f'title = "{title}"\n', encoding="utf-8")
                with (
                    patch("lixity.server.ThreadingHTTPServer", side_effect=RuntimeError("stop before bind")),
                    self.assertRaisesRegex(RuntimeError, "stop before bind"),
                ):
                    run_server(target_path=str(first), title="Direct override")
                self.assertEqual(LixityServerHandler.project_open_overrides, {"title": "Direct override"})
                status, body, _ = self.make_request(
                    "/api/project-open", method="POST",
                    body=json.dumps({"path": str(second)}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200, body)
                self.assertEqual(LixityServerHandler.title, "Direct override")
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_project_open_research_only_folder_without_manuscript(self):
        from lixity.research import api as research_api

        original_state = {
            name: getattr(LixityServerHandler, name)
            for name in (
                "workspace_root", "source_input", "exports_dir", "research_dir",
                "language", "title", "title_custom", "thresholds", "dashboard_html", "dashboard_info",
            )
        }
        try:
            with tempfile.TemporaryDirectory() as td:
                project = Path(td) / "research-only"
                project.mkdir()
                source_path = Path(td) / "public-note.txt"
                source_bytes = b"The reading room opened in 1924.\n"
                source_path.write_bytes(source_bytes)
                research_api.init(project, title="Reading Room Archive")
                source = research_api.ingest(
                    project, source_path, title="Opening Note", allow_retention=True,
                )
                passage_id = research_api.get_source(project, source["source_id"])["passages"][0]["id"]
                dossier = research_api.create_dossier(
                    project, "Opening File", "The opening year is recorded.",
                    evidence_ids=[passage_id],
                )
                before_files = {
                    path.relative_to(project): path.read_bytes()
                    for path in project.rglob("*") if path.is_file()
                }

                status, body, _ = self.make_request(
                    "/api/project-open",
                    method="POST",
                    body=json.dumps({"path": str(project)}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                opened = json.loads(body)
                self.assertTrue(opened["ok"])
                self.assertEqual(opened["workspace_root"], str(project))
                self.assertIsNone(opened["manuscript"])
                self.assertIsNone(LixityServerHandler.source_input)
                self.assertEqual(LixityServerHandler.research_dir, str(project))
                self.assertTrue(LixityServerHandler.dashboard_info["is_empty"])

                status, body, _ = self.make_request("/api/research/status")
                self.assertEqual(status, 200)
                archive = json.loads(body)
                self.assertTrue(archive["initialized"])
                self.assertEqual(archive["project_title"], "Reading Room Archive")
                self.assertEqual(archive["sources_count"], 1)
                self.assertEqual(archive["dossiers_count"], 1)

                status, body, _ = self.make_request(
                    f"/api/research/sources?id={source['source_id']}"
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["passages"][0]["verbatim"],
                                 "The reading room opened in 1924.")
                status, body, _ = self.make_request(
                    f"/api/research/dossiers?id={dossier['dossier_id']}"
                )
                self.assertEqual(status, 200)
                self.assertEqual(json.loads(body)["citations"][0]["passage_id"], passage_id)

                self.assertEqual(source_path.read_bytes(), source_bytes)
                self.assertFalse((project / "manuscript.md").exists())
                self.assertEqual(
                    {path.relative_to(project): path.read_bytes()
                     for path in project.rglob("*") if path.is_file()},
                    before_files,
                )
        finally:
            for name, value in original_state.items():
                setattr(LixityServerHandler, name, value)

    def test_project_open_research_fallback_preserves_discovery_errors(self):
        from lixity.research import api as research_api

        with tempfile.TemporaryDirectory() as td:
            ambiguous_folder = Path(td) / "ambiguous"
            ambiguous_folder.mkdir()
            research_api.init(ambiguous_folder, title="Archive")
            (ambiguous_folder / "one.md").write_text("# One\n", encoding="utf-8")
            (ambiguous_folder / "two.md").write_text("# Two\n", encoding="utf-8")

            ordinary_folder = Path(td) / "ordinary"
            ordinary_folder.mkdir()
            incomplete_folder = Path(td) / "incomplete"
            (incomplete_folder / "research").mkdir(parents=True)
            for path, message in (
                (ordinary_folder, "No manuscript found"),
                (ambiguous_folder, "Multiple manuscripts"),
                (incomplete_folder, "Research store is missing or incomplete"),
            ):
                with self.subTest(path=path):
                    status, body, _ = self.make_request(
                        "/api/project-open",
                        method="POST",
                        body=json.dumps({"path": str(path)}),
                        headers={"Content-Type": "application/json"},
                    )
                    self.assertEqual(status, 400)
                    self.assertIn(message, json.loads(body)["message"])
