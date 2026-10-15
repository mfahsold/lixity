"""Debug diagnostics share timestamps without changing response behavior."""

import io
import tempfile
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone

from tests.support import LoopbackServer, make_handler


class TestServerDebug(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.handler = make_handler(
            self.temp_dir.name, debug=True,
            dashboard_html="<!DOCTYPE html><title>Synthetic debug fixture</title>",
        )
        self.loop = LoopbackServer(self.handler).start()
        self.addCleanup(self.loop.close)

    def request(self, method, path, body=None):
        response = self.loop.request(
            path, method=method, body=body, headers={"Content-Type": "application/json"},
        )
        return response.status

    def test_request_and_error_detail_have_valid_utc_timestamps(self):
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(self.request("GET", "/"), 200)
            self.assertEqual(self.request("POST", "/api/marker-add", "invalid JSON"), 400)
        lines = output.getvalue().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(any("HTTP 400" in line and "Invalid JSON body" in line for line in lines))
        self.assertTrue(any('"GET / HTTP/1.1" 200' in line for line in lines))
        for line in lines:
            self.assertRegex(line, r"^\[\d{4}-\d\d-\d\d \d\d:\d\d:\d\d UTC\] \[server:debug\] ")
            datetime.strptime(line[1:24], "%Y-%m-%d %H:%M:%S UTC").replace(tzinfo=timezone.utc)

    def test_debug_output_keeps_context_tokens_out_of_logs(self):
        token = "synthetic-context-token-value"  # noqa: S105 - synthetic fixture value
        output = io.StringIO()
        with redirect_stderr(output):
            self.request("GET", f"/api/research/claims?research_token={token}")
        text = output.getvalue()
        self.assertNotIn(token, text)
        self.assertIn("/api/research/claims", text)

    def test_disabled_debug_keeps_requests_and_error_detail_quiet(self):
        self.handler.debug = False
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(self.request("GET", "/"), 200)
            self.assertEqual(self.request("POST", "/api/marker-add", "invalid JSON"), 400)
        self.assertEqual(output.getvalue(), "")
