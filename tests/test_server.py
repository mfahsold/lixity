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
