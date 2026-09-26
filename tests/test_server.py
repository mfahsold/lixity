"""Tests for lixity.server – loopback development server and interactive dashboard."""

import http.client
import json
import os
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

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
        orig_ws = LixityServerHandler.workspace_root
        orig_ms = LixityServerHandler.source_input
        orig_title = LixityServerHandler.title
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
                upload_payload = json.dumps({
                    "title": "Das verlorene Artefakt",
                    "language": "de",
                    "path": str(proj_upload_dir),
                    "content": "# Das verlorene Artefakt\n\n## Erstes Kapitel\n\nDer Wind pfiff durch die alten Gassen der Stadt.",
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
                self.assertIn("Der Wind pfiff durch die alten Gassen der Stadt.", (proj_upload_dir / "manuscript.md").read_text(encoding="utf-8"))
        finally:
            LixityServerHandler.workspace_root = orig_ws
            LixityServerHandler.source_input = orig_ms
            LixityServerHandler.title = orig_title
            LixityServerHandler.refresh()

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

    def test_project_open_attaches_existing_research(self):
        from lixity.research import api as research_api
        orig_ws = LixityServerHandler.workspace_root
        orig_res = LixityServerHandler.research_dir
        try:
            with tempfile.TemporaryDirectory() as td:
                proj_dir = Path(td) / "existing-novel"
                proj_dir.mkdir()
                ms_path = proj_dir / "manuscript.md"
                ms_path.write_text("# Chapter 1\n\nSome text.", encoding="utf-8")
                research_api.init(proj_dir, title="Historical Research")

                status, body, _ = self.make_request(
                    "/api/project-open",
                    method="POST",
                    body=json.dumps({"path": str(ms_path)}),
                    headers={"Content-Type": "application/json"},
                )
                self.assertEqual(status, 200)
                res = json.loads(body)
                self.assertTrue(res["ok"])
                self.assertEqual(Path(res["workspace_root"]).resolve(), proj_dir.resolve())
                self.assertEqual(Path(str(LixityServerHandler.research_dir)).resolve(), proj_dir.resolve())
        finally:
            LixityServerHandler.workspace_root = orig_ws
            LixityServerHandler.research_dir = orig_res
            LixityServerHandler.refresh()

