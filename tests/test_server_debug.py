"""Debug diagnostics share timestamps without changing response behavior."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from pathlib import Path

from lixity import log
from tests.support import LoopbackServer, make_handler


class TestServerDebug(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        log.configure(level="DEBUG", force=True)
        self.addCleanup(log.configure, level="INFO", force=True)
        self.handler = make_handler(
            self.temp_dir.name,
            debug=True,
            dashboard_html="<!DOCTYPE html><title>Synthetic debug fixture</title>",
        )
        self.loop = LoopbackServer(self.handler).start()
        self.addCleanup(self.loop.close)

    def request(self, method, path, body=None):
        response = self.loop.request(
            path,
            method=method,
            body=body,
            headers={"Content-Type": "application/json"},
        )
        return response.status

    def test_request_and_error_detail_have_valid_utc_timestamps(self):
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(self.request("GET", "/"), 200)
            self.assertEqual(self.request("POST", "/api/marker-add", "invalid JSON"), 400)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(any("HTTP 400" in line for line in lines))
        self.assertTrue(any("GET /" in line and "200" in line for line in lines))
        for line in lines:
            self.assertRegex(line, r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC DEBUG lixity\.server ")
            datetime.strptime(line[:23], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)

    def test_debug_output_keeps_context_tokens_out_of_logs(self):
        token = "synthetic-context-token-value"  # noqa: S105 - synthetic fixture value
        output = io.StringIO()
        with redirect_stderr(output):
            self.request("GET", f"/api/research/claims?research_token={token}")
        text = output.getvalue()
        self.assertNotIn(token, text)
        self.assertIn("/api/research/claims", text)

    def test_debug_does_not_log_private_project_path_in_error_response(self):
        private_path = str(Path(self.temp_dir.name) / "lixity-synthetic-private-project-name-24680")
        output = io.StringIO()
        with redirect_stderr(output):
            response = self.loop.request("/api/project-open", payload={"path": private_path})
        self.assertEqual(response.status, 404)
        self.assertIn(private_path, response.json["message"])
        self.assertNotIn(private_path, output.getvalue())
        self.assertIn("/api/project-open", output.getvalue())

    def test_debug_redacts_workspace_token_and_unrecognised_path(self):
        workspace_id = "1234567890abcdef1234567890abcdef"  # synthetic test value
        private_part = "SYNTHETIC-PRIVATE-PATH"
        output = io.StringIO()
        with redirect_stderr(output):
            self.loop.request(f"/w/{workspace_id}/api/speech?token=SECRET-QUERY")
            self.loop.request(f"/unrecognised/{private_part}")
        text = output.getvalue()
        self.assertNotIn(workspace_id, text)
        self.assertNotIn(private_part, text)
        self.assertNotIn("SECRET-QUERY", text)
        self.assertIn("/api/speech", text)

    def test_debug_does_not_log_raw_unrecognised_http_method(self):
        method = "SYNTHETIC_PRIVATE_METHOD"
        output = io.StringIO()
        with redirect_stderr(output):
            response = self.loop.request("/api/speech", method=method)
        self.assertEqual(response.status, 501)
        self.assertNotIn(method, output.getvalue())

    def test_disabled_debug_keeps_requests_and_error_detail_quiet(self):
        self.handler.debug = False
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(self.request("GET", "/"), 200)
            self.assertEqual(self.request("POST", "/api/marker-add", "invalid JSON"), 400)
        self.assertEqual(output.getvalue(), "")
