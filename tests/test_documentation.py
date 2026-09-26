"""Regression checks for public documentation rendering."""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TestDocumentation(unittest.TestCase):
    def test_math_avoids_macros_rejected_by_github(self):
        for path in (ROOT / "docs").glob("*.md"):
            with self.subTest(path=path.name):
                self.assertNotIn(r"\operatorname", path.read_text(encoding="utf-8"))

    def test_readme_has_no_markdown_escapes_in_raw_html(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for block in re.findall(r"<details>.*?</details>", readme, re.DOTALL):
            self.assertNotIn(r"\*", block)

    def test_public_entrypoints_explain_book_sales(self):
        for name in ("README.md", "docs/index.html", "docs/llms.txt"):
            with self.subTest(path=name):
                content = (ROOT / name).read_text(encoding="utf-8").lower()
                self.assertIn("self-publishing", content)
                self.assertIn("commercial license", content)

    def test_documentation_version_consistency(self):
        import sys
        sys.path.insert(0, str(ROOT / "scripts"))
        from sync_docs import check_or_sync_files, get_version

        version = get_version()
        drift = check_or_sync_files(version, check_only=True)
        self.assertEqual(
            drift, [],
            f"Documentation version drift detected for v{version}. Run 'python scripts/sync_docs.py' to update."
        )

    def test_changelog_matches_current_version(self):
        from lixity import __version__
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## [{__version__}]", changelog)
        self.assertIn(f"[{__version__}]: https://github.com/mfahsold/lixity/compare/", changelog)

    def test_release_notes_exist_for_current_version(self):
        from lixity import __version__
        release_notes = ROOT / "docs" / "releases" / f"v{__version__}.md"
        self.assertTrue(release_notes.is_file(), f"Missing release notes file: {release_notes}")

    def test_markdown_relative_links_resolve(self):
        broken: list[tuple[str, str]] = []
        for md_file in list(ROOT.glob("*.md")) + list((ROOT / "docs").rglob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            for m in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", text):
                target = m.group(2).strip()
                if target.startswith(("http://", "https://", "mailto:", "#")):
                    continue
                path_part = target.split("#")[0]
                if not path_part:
                    continue
                resolved = (md_file.parent / path_part).resolve()
                if not resolved.exists():
                    broken.append((str(md_file.relative_to(ROOT)), target))
        self.assertEqual(broken, [], f"Broken relative markdown links found: {broken}")
