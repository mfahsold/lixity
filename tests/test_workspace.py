"""
tests/test_workspace.py
=======================
Workspace discovery, layout creation and idempotent artifact publishing:
a manuscript in a folder yields ``exports/`` (with ``archive/``) and ``nda/``,
and repeated builds cause zero writes while changed content rotates versions.
"""

import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, os.path.join(BASE_DIR, "src"))

from lixity.cli import main as cli_main  # noqa: E402
from lixity.publishing import prune_archive  # noqa: E402
from lixity.workspace import discover, slugify  # noqa: E402


def _run_cli(argv):
    with contextlib.redirect_stdout(io.StringIO()):
        return cli_main(argv)


class TestSlugify(unittest.TestCase):
    def test_transliteration_and_cleanup(self):
        self.assertEqual(
            slugify("Eigentlich werde ich nie wütend"), "Eigentlich_werde_ich_nie_wuetend"
        )
        self.assertEqual(slugify("Effi-Briest"), "Effi-Briest")
        self.assertEqual(slugify("  "), "manuskript")


class TestDiscovery(unittest.TestCase):
    def test_explicit_file_sets_root_to_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "buch.md"
            path.write_text("# Buch\n", encoding="utf-8")
            workspace = discover(explicit=str(path))
            self.assertEqual(workspace.root, tmp)
            self.assertEqual(workspace.slug, "buch")

    def test_foldername_convention(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "Mein Roman"
            folder.mkdir()
            (folder / "Mein Roman.md").write_text("# X\n", encoding="utf-8")
            (folder / "README.md").write_text("ignored", encoding="utf-8")
            workspace = discover(root=str(folder))
            self.assertEqual(os.path.basename(workspace.manuscript), "Mein Roman.md")

    def test_single_markdown_fallback_and_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "a.md").write_text("A", encoding="utf-8")
            self.assertEqual(discover(root=tmp).slug, "a")
            (Path(tmp) / "b.md").write_text("B", encoding="utf-8")
            with self.assertRaises(ValueError):
                discover(root=tmp)

    def test_missing_manuscript_raises(self):
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(FileNotFoundError):
            discover(root=tmp)


class TestPublishIdempotency(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = self._tmp.name
        (Path(self.root) / "roman.md").write_text("## Kapitel 1\n\nText.\n", encoding="utf-8")
        self.ws = discover(root=self.root)

    def tearDown(self):
        self._tmp.cleanup()

    def _versions(self, stem):
        return sorted(p.name for p in Path(self.ws.exports_dir).glob(f"{stem}_*"))

    def test_layout_created_once(self):
        created = self.ws.ensure_layout()
        self.assertEqual(len(created), 3)
        self.assertTrue(os.path.isdir(self.ws.exports_dir))
        self.assertTrue(os.path.isdir(self.ws.archive_dir))
        self.assertTrue(os.path.isdir(self.ws.nda_dir))
        self.assertEqual(self.ws.ensure_layout(), [])

    def test_publish_is_idempotent(self):
        self.assertTrue(self.ws.publish("roman_report.md", "Inhalt A\n"))
        self.assertFalse(self.ws.publish("roman_report.md", "Inhalt A\n"))
        self.assertEqual(len(self._versions("roman_report")), 1)
        stable = Path(self.ws.artifact_path("roman_report.md"))
        self.assertEqual(stable.read_text(encoding="utf-8"), "Inhalt A\n")

    def test_change_archives_previous_version(self):
        self.ws.ensure_layout()
        older = Path(self.ws.exports_dir) / "roman_report_2026-01-01_10-00.md"
        older.write_text("alt\n", encoding="utf-8")
        self.assertTrue(self.ws.publish("roman_report.md", "B\n"))
        self.assertFalse(older.exists())
        self.assertTrue((Path(self.ws.archive_dir) / older.name).exists())
        stable = Path(self.ws.artifact_path("roman_report.md"))
        self.assertEqual(stable.read_text(encoding="utf-8"), "B\n")

    def test_prune_archive_keeps_last_ten(self):
        archive = Path(self.ws.archive_dir)
        archive.mkdir(parents=True, exist_ok=True)
        for i in range(12):
            (archive / f"roman_report_2026-01-{i + 1:02d}_10-00.md").write_text(
                str(i), encoding="utf-8"
            )
        self.assertEqual(prune_archive(str(archive), keep_last=10), 2)
        self.assertEqual(len(list(archive.glob("*.md"))), 10)


class TestBuildCommand(unittest.TestCase):
    def _manuscript(self, tmp):
        path = Path(tmp) / "roman.md"
        path.write_text(
            "## Kapitel 1\n\nIch trinke Kaffee. Der Regen fällt leise.\n\n"
            "## Kapitel 2\n\nEr ging zum Fenster und sah hinaus.\n",
            encoding="utf-8",
        )
        return path

    def test_build_publishes_artifacts_idempotently(self):
        with tempfile.TemporaryDirectory() as tmp:
            manuscript = self._manuscript(tmp)
            self.assertEqual(_run_cli(["build", str(manuscript)]), 0)
            exports = Path(tmp) / "exports"
            for suffix in (
                "_metrics.json",
                "_profile.json",
                "_style.json",
                "_style_passport.txt",
                "_report.md",
                "_dashboard.html",
            ):
                self.assertTrue((exports / f"roman{suffix}").exists(), suffix)
            self.assertTrue((Path(tmp) / "nda").is_dir())

            before = sorted(p.name for p in exports.glob("roman_*"))
            self.assertEqual(_run_cli(["build", str(manuscript)]), 0)
            self.assertEqual(sorted(p.name for p in exports.glob("roman_*")), before)

    def test_build_dry_run_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            manuscript = self._manuscript(tmp)
            self.assertEqual(_run_cli(["build", str(manuscript), "--dry-run"]), 0)
            self.assertFalse((Path(tmp) / "exports").exists())
            self.assertFalse((Path(tmp) / "nda").exists())


if __name__ == "__main__":
    unittest.main()
