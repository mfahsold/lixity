"""Debug diagnostics share timestamps without changing response behavior."""

import http.client
import io
import threading
import unittest
from contextlib import redirect_stderr
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer

from lixity.server import LixityServerHandler


class TestServerDebug(unittest.TestCase):
    def setUp(self):
        class DebugHandler(LixityServerHandler):
            debug = True
            dashboard_html = "<!DOCTYPE html><title>Synthetic debug fixture</title>"

        self.handler = DebugHandler
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), DebugHandler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method, path, body=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            connection.request(method, path, body=body, headers={"Content-Type": "application/json"})
            response = connection.getresponse()
            response.read()
            return response.status
        finally:
            connection.close()

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

    def test_disabled_debug_keeps_requests_and_error_detail_quiet(self):
        self.handler.debug = False
        output = io.StringIO()
        with redirect_stderr(output):
            self.assertEqual(self.request("GET", "/"), 200)
            self.assertEqual(self.request("POST", "/api/marker-add", "invalid JSON"), 400)
        self.assertEqual(output.getvalue(), "")
