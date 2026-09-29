"""Integration tests for project-isolated NDA management in lixity.server (Issue #12)."""

import http.client
import json
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from pathlib import Path

from lixity.nda import ProjectNdaProvider
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
        self.assertTrue((self.proj_nda / "nda" / "nda_1.pdf").is_file())

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


if __name__ == "__main__":
    unittest.main()
