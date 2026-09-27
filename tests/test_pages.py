"""Public Pages staging excludes local planning and private working material."""

import tempfile
import unittest
from pathlib import Path

from scripts.stage_pages import stage


class TestPagesStaging(unittest.TestCase):
    def test_only_product_paths_are_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            public = ("index.html", "USAGE.md", "guides/install.html", "assets/site.css",
                      "research/USAGE.md", "research/examples/synthetic-source.txt",
                      "screenshots/public.png", "sitemap.xml", ".nojekyll")
            private = ("superpowers/plans/task.md", "archive/wave2-plan.md", "notes.md",
                       ".planning/secret.md", "research/.scratch/session.md",
                       "screenshots/local.log", "private/source.txt")
            for name in public + private:
                path = docs / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic fixture")
            output = root / "site"
            stage(docs, output)
            published = {str(path.relative_to(output)).replace("\\", "/")
                         for path in output.rglob("*") if path.is_file()}
            self.assertEqual(published, set(public))
            with self.assertRaises(FileExistsError):
                stage(docs, output)

    def test_symlink_cannot_publish_external_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            docs.mkdir()
            source = root / "private.txt"
            source.write_text("synthetic private content", encoding="utf-8")
            try:
                (docs / "index.html").symlink_to(source)
            except (OSError, NotImplementedError):
                self.skipTest("Symlinks unavailable on this platform")
            with self.assertRaisesRegex(ValueError, "Symlink"):
                stage(docs, root / "site")
