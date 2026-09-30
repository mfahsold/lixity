"""Integration tests for project-isolated NDA management in lixity.server (Issue #12)."""

import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from lixity.nda import ProjectNdaProvider, get_project_nda_provider
from lixity.server import LixityServerHandler
from lixity.status import NdaStatus


class TestServerNdaIntegration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp_dir.name)

        # Project 1: Plain project without NDA
        cls.proj_no_nda = cls.root / "proj_no_nda"
        cls.proj_no_nda.mkdir(parents=True)
        (cls.proj_no_nda / "manuscript.md").write_text(
            "# Plain Novel\n\n## Chapter 1\nSome text.", encoding="utf-8"
        )

        # Project 2: Project with NDA capability
        cls.proj_nda = cls.root / "proj_nda"
        cls.proj_nda.mkdir(parents=True)
        (cls.proj_nda / "manuscript.md").write_text(
            "# Book With NDA\n\n## Chapter 1\nSecret text.", encoding="utf-8"
        )
        (cls.proj_nda / "nda").mkdir(parents=True)
        (cls.proj_nda / "lixity.toml").write_text(
            'title = "Book With NDA"\n[nda]\nenabled = true\n', encoding="utf-8"
        )

        # Start server with proj_no_nda
        LixityServerHandler.source_input = str(cls.proj_no_nda / "manuscript.md")
        LixityServerHandler.workspace_root = str(cls.proj_no_nda)
        LixityServerHandler.exports_dir = str(cls.proj_no_nda / "exports")
        LixityServerHandler.research_dir = None
        LixityServerHandler.language = "en"
        LixityServerHandler.title = "Plain Novel"
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

    def make_post(self, path: str, payload: dict) -> tuple[int, dict]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {
            "Host": f"127.0.0.1:{self.port}",
            "Content-Type": "application/json",
            "Origin": f"http://127.0.0.1:{self.port}",
        }
        body = json.dumps(payload).encode("utf-8")
        conn.request("POST", path, body=body, headers=headers)
        res = conn.getresponse()
        raw = res.read()
        conn.close()
        data = json.loads(raw.decode("utf-8")) if raw else {}
        return res.status, data

    def make_get(self, path: str = "/") -> tuple[int, str]:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        headers = {"Host": f"127.0.0.1:{self.port}"}
        conn.request("GET", path, headers=headers)
        res = conn.getresponse()
        raw = res.read()
        conn.close()
        return res.status, raw.decode("utf-8")

    def test_nda_disabled_when_project_has_no_nda(self):
        # Open project without NDA
        status, data = self.make_post("/api/project-open", {"path": str(self.proj_no_nda)})
        self.assertEqual(status, 200)
        self.assertTrue(data.get("ok"))

        # Verify HTML has no nda-manager
        status_get, html = self.make_get("/")
        self.assertEqual(status_get, 200)
        self.assertNotIn('id="nda-manager"', html)

        # API calls return 404
        status_api, err = self.make_post("/api/nda-list", {})
        self.assertEqual(status_api, 404)
        self.assertFalse(err.get("ok"))
        self.assertIn("not enabled", err.get("message", ""))

    def test_nda_enabled_when_opening_supported_project_and_crud(self):
        # Open project with NDA support
        status, data = self.make_post("/api/project-open", {"path": str(self.proj_nda)})
        self.assertEqual(status, 200)
        self.assertTrue(data.get("ok"))

        # Verify HTML contains nda-manager
        status_get, html = self.make_get("/")
        self.assertEqual(status_get, 200)
        self.assertIn('id="nda-manager"', html)

        # 1. List initially empty
        status_api, list_data = self.make_post("/api/nda-list", {})
        self.assertEqual(status_api, 200)
        self.assertTrue(list_data.get("ok"))
        self.assertEqual(list_data.get("records"), [])

        # 2. Add recipient
        status_add, add_data = self.make_post(
            "/api/nda-add",
            {
                "name": "Jane BetaReader",
                "contact": "jane@example.org",
                "notes": "Chapter 1-3 review",
            },
        )
        self.assertEqual(status_add, 200)
        self.assertTrue(add_data.get("ok"))
        rec_id = add_data.get("id")
        self.assertEqual(rec_id, "1")

        # 3. List contains record
        status_api, list_data2 = self.make_post("/api/nda-list", {})
        self.assertEqual(status_api, 200)
        self.assertEqual(len(list_data2["records"]), 1)
        self.assertEqual(list_data2["records"][0]["name"], "Jane BetaReader")
        self.assertEqual(list_data2["records"][0]["status"], NdaStatus.DRAFT.value)

        # 4. Update status
        status_up, up_data = self.make_post(
            "/api/nda-update",
            {
                "id": rec_id,
                "status": NdaStatus.SENT.value,
            },
        )
        self.assertEqual(status_up, 200)
        self.assertTrue(up_data.get("ok"))
        self.assertEqual(up_data["record"]["status"], NdaStatus.SENT.value)

        # Invalid status rejected
        status_inv, _inv_data = self.make_post(
            "/api/nda-update",
            {
                "id": rec_id,
                "status": "invalid_status",
            },
        )
        self.assertEqual(status_inv, 400)

        # 5. Export PDF
        status_exp, exp_data = self.make_post("/api/nda-export", {"id": rec_id})
        self.assertEqual(status_exp, 200)
        self.assertTrue(exp_data.get("ok"))
        pdf = self.proj_nda / "nda" / "nda_1.pdf"
        self.assertTrue(pdf.is_file())
        self.assert_valid_pdf(pdf.read_bytes())

        # 6. Delete record
        status_del, del_data = self.make_post("/api/nda-delete", {"id": rec_id})
        self.assertEqual(status_del, 200)
        self.assertTrue(del_data.get("ok"))

        status_api, list_data3 = self.make_post("/api/nda-list", {})
        self.assertEqual(list_data3["records"], [])

    def test_project_switching_isolates_nda_data(self):
        # Create Project 3 with distinct NDA records
        proj3 = self.root / "proj_nda_3"
        proj3.mkdir(parents=True)
        (proj3 / "manuscript.md").write_text("# Proj 3\n\n## Ch 1\nText", encoding="utf-8")
        (proj3 / "nda").mkdir(parents=True)
        (proj3 / "lixity.toml").write_text(
            'title = "Proj 3"\n[nda]\nenabled = true\n', encoding="utf-8"
        )

        # Open Project 3 and add a record
        self.make_post("/api/project-open", {"path": str(proj3)})
        self.make_post("/api/nda-add", {"name": "Project 3 Recipient"})

        _status_p3, data_p3 = self.make_post("/api/nda-list", {})
        self.assertEqual(len(data_p3["records"]), 1)
        self.assertEqual(data_p3["records"][0]["name"], "Project 3 Recipient")

        # Switch to Project 1 (No NDA) -> Disabled
        self.make_post("/api/project-open", {"path": str(self.proj_no_nda)})
        status_p1, _ = self.make_post("/api/nda-list", {})
        self.assertEqual(status_p1, 404)

        # Switch back to Project 3 -> Record preserved
        self.make_post("/api/project-open", {"path": str(proj3)})
        _status_p3_again, data_p3_again = self.make_post("/api/nda-list", {})
        self.assertEqual(len(data_p3_again["records"]), 1)
        self.assertEqual(data_p3_again["records"][0]["name"], "Project 3 Recipient")

    def test_encrypted_passphrase_flow(self):
        proj_enc = self.root / "proj_enc"
        proj_enc.mkdir(parents=True)
        provider = ProjectNdaProvider(proj_enc)
        provider.add_record("Secret Recipient", "secret@test.org")
        # Lock with passphrase
        self.assertTrue(provider.unlock("secret123"))
        self.assertTrue(provider.enc_file.is_file())

        # New provider instance simulates fresh open of encrypted store
        fresh_provider = ProjectNdaProvider(proj_enc)
        self.assertTrue(fresh_provider.is_locked())
        with self.assertRaises(PermissionError):
            fresh_provider.list_records()

        # Unlock with wrong passphrase fails
        self.assertFalse(fresh_provider.unlock("wrong_pass"))
        self.assertTrue(fresh_provider.is_locked())

        # Unlock with correct passphrase succeeds
        self.assertTrue(fresh_provider.unlock("secret123"))
        self.assertFalse(fresh_provider.is_locked())
        records = fresh_provider.list_records()
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["name"], "Secret Recipient")


    @staticmethod
    def assert_valid_pdf(data: bytes) -> None:
        """A PDF is only usable if its cross-reference table is actually correct.

        A hardcoded xref looks plausible but breaks as soon as the byte length of
        the preceding content changes, which is what a recipient-specific header
        does on every single export.
        """
        assert data.startswith(b"%PDF-1.4"), "missing PDF header"
        assert data.rstrip().endswith(b"%%EOF"), "missing EOF marker"

        declared_start = int(data[data.rindex(b"startxref\n") + 10:].split()[0])
        xref_at = data.rindex(b"\nxref\n") + 1
        assert declared_start == xref_at, (
            f"startxref {declared_start} does not point at the xref table at {xref_at}"
        )

        # "xref\n<first> <count>\n" followed by <count> fixed-width 20-byte entries.
        start = xref_at + len(b"xref\n")
        first_token = data[start:].split(b"\n", 1)[0]
        first, _, count_token = first_token.partition(b" ")
        first, count = int(first), int(count_token)
        table = start + len(first_token) + 1
        for index in range(first + 1, first + count):
            entry = data[table + 20 * index: table + 20 * index + 20]
            assert len(entry) == 20, "truncated xref entry"
            offset = int(entry[:10])
            assert data[offset:].startswith(f"{index} 0 obj".encode()), (
                f"xref entry {index} points at byte {offset}, "
                f"which holds {data[offset:offset + 12]!r}"
            )

        # Every page object must declare its font, otherwise viewers show a blank
        # page and text extraction fails with "Unknown font tag".
        assert b"/Font << /F1" in data, "no font resource declared"


class ProjectAdapterFallbackTest(unittest.TestCase):
    """A broken project-owned extension must announce itself, not fail silently."""

    def test_broken_nda_provider_warns_and_falls_back(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            (project / "nda").mkdir(parents=True)
            (project / "nda_provider.py").write_text(
                "raise RuntimeError('adapter is broken')\n", encoding="utf-8"
            )
            with self.assertWarns(UserWarning) as caught:
                provider = get_project_nda_provider(project)
            self.assertIsInstance(provider, ProjectNdaProvider)
            message = str(caught.warning)
            self.assertIn("nda_provider.py", message)
            self.assertIn("not active", message)

    def test_working_nda_provider_does_not_warn(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            project = Path(td) / "proj"
            (project / "nda").mkdir(parents=True)
            (project / "nda_provider.py").write_text(
                "from lixity.nda import ProjectNdaProvider\n"
                "class Provider(ProjectNdaProvider):\n    pass\n",
                encoding="utf-8",
            )
            import warnings as _warnings

            with _warnings.catch_warnings(record=True) as caught:
                _warnings.simplefilter("always")
                provider = get_project_nda_provider(project)
            self.assertEqual([w for w in caught if "nda_provider.py" in str(w.message)], [])
            self.assertTrue(provider.is_available())


if __name__ == "__main__":
    unittest.main()
