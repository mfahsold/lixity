"""Tests for named dossier collections and explicit reading order."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from lixity.cli import main
from lixity.config import (
    prepare_project_settings,
    project_config_snapshot,
    read_explicit_project_config,
)
from lixity.research import api
from lixity.research.archive import export_archive, restore_archive
from lixity.research.repository import ResearchError
from lixity.site_export import prepare_site


class DossierCollectionsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="lixity-dossier-collections-")
        self.root = Path(self._tmp.name) / "project"
        self.root.mkdir(parents=True)
        api.init(self.root, title="Synthetic collections project", language="en")
        self.d1 = api.create_dossier(self.root, title="Chronology Notes", body="First body")["dossier_id"]
        self.d2 = api.create_dossier(self.root, title="Harbour Map", body="Second body")["dossier_id"]
        self.d3 = api.create_dossier(self.root, title="Character Sketch", body="Third body")["dossier_id"]

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_collections_preserve_pin_immutability_and_multi_membership(self) -> None:
        """Ordering and multi-collection membership never revise dossiers or invalidate pins."""
        claim = api.create_claim(
            self.root,
            title="Synthetic claim",
            statement="Harbour opened in 1924.",
            dossier_id=self.d2,
        )
        decision = api.record_decision(
            self.root,
            title="Synthetic decision",
            rationale="Keep the 1924 date.",
            claim_id=claim["claim_id"],
            dossier_ids=[self.d1, self.d2],
        )
        before_snapshot = api.list_claims(self.root)
        before_dossiers = {d["id"]: d["revision"] for d in api.list_dossiers(self.root)["dossiers"]}

        saved_one = api.save_dossier_collection(
            self.root,
            "arc-one",
            name="Opening Arc",
            dossier_ids=[self.d2, self.d1],
        )
        self.assertEqual([c["id"] for c in saved_one["collections"]], ["arc-one"])

        saved_two = api.save_dossier_collection(
            self.root,
            "reference",
            name="Reference Pack",
            dossier_ids=[self.d1, self.d2],
        )
        self.assertEqual([c["id"] for c in saved_two["collections"]], ["arc-one", "reference"])

        # Dossier revisions and archive snapshot must remain untouched.
        after_dossiers = {d["id"]: d["revision"] for d in api.list_dossiers(self.root)["dossiers"]}
        self.assertEqual(before_dossiers, after_dossiers)
        after_claims = api.list_claims(self.root)
        self.assertEqual(before_snapshot["claims"], after_claims["claims"])
        impact = api.decision_impact(self.root, decision["decision_id"])
        self.assertTrue(
            all(
                entry["pinned_revisions"] == [entry["current_revision"]]
                for entry in impact["dossiers"]
            )
        )

        # Both collections contain d1 and d2 in their own reading orders; d3 stays unassigned.
        arc_list = api.list_dossiers(self.root, collection="arc-one")
        self.assertEqual([d["id"] for d in arc_list["dossiers"]], [self.d2, self.d1])
        ref_list = api.list_dossiers(self.root, collection="reference")
        self.assertEqual([d["id"] for d in ref_list["dossiers"]], [self.d1, self.d2])
        unassigned = api.list_dossiers(self.root, collection="unassigned")
        self.assertEqual([d["id"] for d in unassigned["dossiers"]], [self.d3])

        # Multi-collection memberships are projected on each dossier in collection order.
        by_id = {d["id"]: d for d in api.list_dossiers(self.root)["dossiers"]}
        self.assertEqual(
            by_id[self.d2]["collections"],
            [
                {"id": "arc-one", "name": "Opening Arc", "position": 1},
                {"id": "reference", "name": "Reference Pack", "position": 2},
            ],
        )
        self.assertEqual(by_id[self.d3]["collections"], [])

    def test_withdrawn_and_missing_entries_are_reported_without_hiding_remaining(self) -> None:
        """Withdrawn or missing dossier IDs stay preserved in config and are reported explicitly."""
        missing_id = "urn:uuid:00000000-0000-4000-8000-000000000099"
        api.save_dossier_collection(
            self.root,
            "places",
            name="Key Places",
            dossier_ids=[self.d3, self.d2, missing_id, self.d1],
        )
        current = api.get_dossier(self.root, self.d2)
        api.withdraw(
            self.root,
            dossier_id=self.d2,
            expected_snapshot=current["snapshot"],
            expected_revision=current["revision"],
            reason="Withdrawn for synthetic test",
        )

        listing = api.list_dossiers(self.root, collection="places")
        self.assertEqual([d["id"] for d in listing["dossiers"]], [self.d3, self.d1])
        col = listing["collections"][0]
        self.assertEqual(
            [e["dossier_id"] for e in col["entries"] if e["status"] == "available"],
            [self.d3, self.d1],
        )
        self.assertEqual(
            [e["dossier_id"] for e in col["entries"] if e["status"] == "withdrawn"],
            [self.d2],
        )
        self.assertEqual(
            [e["dossier_id"] for e in col["entries"] if e["status"] == "missing"],
            [missing_id],
        )
        self.assertEqual(col["dossier_ids"], [self.d3, self.d2, missing_id, self.d1])

    def test_unknown_config_keys_and_concurrent_edit_protection(self) -> None:
        """Updating collections preserves unrelated TOML settings and enforces snapshot guards."""
        config_path = self.root / "lixity.toml"
        config_path.write_text(
            'language = "en"\ncustom_future_option = "preserved"\n',
            encoding="utf-8",
        )
        stale_snapshot = project_config_snapshot(config_path)
        api.save_dossier_collection(
            self.root,
            "cast",
            name="Main Cast",
            dossier_ids=[self.d3],
            expected_config_snapshot=stale_snapshot,
        )
        text = config_path.read_text(encoding="utf-8")
        self.assertIn('custom_future_option = "preserved"', text)

        with self.assertRaises(ResearchError):
            api.save_dossier_collection(
                self.root,
                "cast",
                name="Stale Cast",
                dossier_ids=[self.d1],
                expected_config_snapshot=stale_snapshot,
            )

        # Reordering collections updates the persisted order even when the keys are identical.
        api.set_dossier_collections(
            self.root,
            [
                {"id": "first", "name": "First", "dossier_ids": [self.d1]},
                {"id": "second", "name": "Second", "dossier_ids": [self.d2]},
            ],
        )
        api.set_dossier_collections(
            self.root,
            [
                {"id": "second", "name": "Second", "dossier_ids": [self.d2]},
                {"id": "first", "name": "First", "dossier_ids": [self.d1]},
            ],
        )
        self.assertEqual(
            [c["id"] for c in api.list_dossiers(self.root)["collections"]],
            ["second", "first"],
        )

    def test_validation_rejects_reserved_or_duplicate_collection_keys(self) -> None:
        for reserved in ("all", "unassigned", "InvalidKey"):
            with self.subTest(reserved=reserved), self.assertRaises(ResearchError):
                api.save_dossier_collection(self.root, reserved, name="Test", dossier_ids=[self.d1])
        with self.assertRaises(ResearchError):
            api.save_dossier_collection(
                self.root,
                "dup",
                name="Duplicate Dossiers",
                dossier_ids=[self.d1, self.d1],
            )
        with self.assertRaises(ValueError):
            prepare_project_settings(
                self.root,
                {"dossier_collections": {"bad": {"name": "", "dossier_ids": []}}},
            )

    def test_portable_archive_and_read_only_site_export_preserve_collections(self) -> None:
        """Portable archives and read-only site exports carry the same ordered collection projection."""
        api.save_dossier_collection(
            self.root,
            "reading-order",
            name="Reading Order",
            dossier_ids=[self.d3, self.d1],
        )
        bundle = Path(self._tmp.name) / "backup.tar.gz"
        exported = export_archive(self.root, bundle)
        self.assertEqual(exported["output_path"], str(bundle))

        restored_root = Path(self._tmp.name) / "restored"
        restore_archive(bundle, restored_root)
        self.assertTrue((restored_root / "lixity.toml").is_file())
        restored_listing = api.list_dossiers(restored_root, collection="reading-order")
        self.assertEqual([d["id"] for d in restored_listing["dossiers"]], [self.d3, self.d1])
        self.assertEqual(restored_listing["unassigned_dossier_ids"], [self.d2])

        (restored_root / "manuscript.md").write_text(
            "## Chapter 1\n\nSynthetic text for the portable export check.\n",
            encoding="utf-8",
        )
        bundle_site = prepare_site(
            restored_root,
            manuscript=restored_root / "manuscript.md",
            include_research=True,
        )
        html = bundle_site.files["index.html"].decode("utf-8")
        self.assertIn('"reading-order"', html)
        self.assertIn('"Reading Order"', html)

    def test_cli_save_list_and_delete_collection(self) -> None:
        """CLI flags manage and filter dossier collections in JSON and human output."""
        import io
        from contextlib import redirect_stdout

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([
                "research",
                "dossier",
                "--project",
                str(self.root),
                "--set-collection",
                "places",
                "--collection-name",
                "Places & Maps",
                "--dossiers",
                f"{self.d2},{self.d1}",
                "--format",
                "json",
            ])
        self.assertEqual(code, 0)
        payload = json.loads(buf.getvalue())
        self.assertEqual(payload["selected_collection"], "places")

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([
                "research",
                "dossier",
                "list",
                "--project",
                str(self.root),
                "--collection",
                "places",
                "--format",
                "json",
            ])
        self.assertEqual(code, 0)
        listed = json.loads(buf.getvalue())
        self.assertEqual([d["id"] for d in listed["dossiers"]], [self.d2, self.d1])

        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([
                "research",
                "dossier",
                "--project",
                str(self.root),
                "--delete-collection",
                "places",
                "--format",
                "json",
            ])
        self.assertEqual(code, 0)
        deleted = json.loads(buf.getvalue())
        self.assertEqual(deleted["collections"], [])
        self.assertEqual(read_explicit_project_config(self.root).get("dossier_collections"), {})


if __name__ == "__main__":
    unittest.main()
