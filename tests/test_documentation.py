"""Regression checks for public documentation rendering."""

import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# scripts/ holds the documentation maintenance entrypoint. Set up once here
# rather than inside a single test: doing it in a test body made the import work
# only for whichever tests happened to run after it, so a test ordered earlier
# failed on ModuleNotFoundError.
sys.path.insert(0, str(ROOT / "scripts"))


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
        from sync_docs import check_or_sync_files, get_version

        version = get_version()
        drift = check_or_sync_files(version, check_only=True)
        self.assertEqual(
            drift, [],
            f"Documentation version drift detected for v{version}. Run 'python scripts/sync_docs.py' to update."
        )

    def test_current_version_claims_match_single_source_of_truth(self):
        """Currency claims must name the current release.

        check_or_sync_files only reports whether its own pinned-string list has
        anything left to rewrite, so it is silent about any version claim in
        wording it does not enumerate. That blind spot is how the published
        site came to advertise v1.20.0 while both the CLI check and the test
        suite reported success. find_version_drift is the invariant that
        covers the rest.
        """
        from sync_docs import find_version_drift, get_version

        self.assertEqual(find_version_drift(get_version()), [])

    def test_version_drift_check_reports_findings_when_claims_are_stale(self):
        """Prove the invariant detects stale claims instead of always passing.

        Runs the same scan with a deliberately wrong Single-Source-of-Truth
        version. Every current-version claim in the tree then disagrees and
        must be reported, which is the condition the old check could not see.
        """
        from sync_docs import find_version_drift, get_version

        current = get_version()
        findings = find_version_drift("0.0.1-not-a-version")
        self.assertTrue(
            findings,
            "find_version_drift reported nothing against a wrong SSOT version, "
            "so it cannot be relied on to catch stale claims",
        )
        # Findings must be actionable: file, line, and the expected version.
        for finding in findings:
            self.assertRegex(finding, r"\S+:\d+: .*v0\.0\.1-not-a-version")
        # Against the real version the same scan is clean.
        self.assertEqual(find_version_drift(current), [])

    def test_changelog_matches_current_version(self):
        from lixity import __version__
        changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn(f"## [{__version__}]", changelog)
        self.assertIn(f"[{__version__}]: https://github.com/mfahsold/lixity/compare/", changelog)

    def test_release_notes_exist_for_current_version(self):
        from lixity import __version__
        release_notes = ROOT / "docs" / "releases" / f"v{__version__}.md"
        self.assertTrue(release_notes.is_file(), f"Missing release notes file: {release_notes}")

    def test_published_tree_has_no_broken_links(self):
        """The staged Pages output must resolve every relative link it ships.

        Staging flattens ``docs/<name>`` to ``/<name>``, so a link that is
        correct when browsing the checkout can still break on the site. This
        validates the staged tree rather than the repository, which is what a
        reader actually receives.
        """
        import sys
        import tempfile

        sys.path.insert(0, str(ROOT / "scripts"))
        from stage_pages import stage

        with tempfile.TemporaryDirectory() as td:
            output = Path(td) / "site"
            stage(ROOT / "docs", output)

            def anchors(md: Path) -> set[str]:
                found = set()
                for line in md.read_text(encoding="utf-8").splitlines():
                    if line.startswith("#"):
                        slug = re.sub(r"[^\w\s-]", "", line.lstrip("#").strip().lower())
                        found.add(re.sub(r"\s+", "-", slug))
                return found

            broken: list[str] = []
            for md in output.rglob("*.md"):
                for m in re.finditer(
                    r"\]\((?!https?://|mailto:)([^)#]+)(?:#([^)]*))?\)",
                    md.read_text(encoding="utf-8"),
                ):
                    target, anchor = m.group(1), m.group(2)
                    resolved = (md.parent / target).resolve()
                    where = f"{md.relative_to(output)} -> {target}"
                    if not resolved.exists():
                        broken.append(where)
                    elif anchor and anchor not in anchors(resolved):
                        broken.append(f"{where}#{anchor}")
            self.assertEqual(broken, [], f"Broken links in the published site: {broken}")

    def test_repository_root_documents_are_linked_by_absolute_url(self):
        """Nothing outside docs/ is published, so cross-references must be absolute."""
        root_docs = {"README.md", "CONTRIBUTING.md", "SECURITY.md", "LICENSE", "CHANGELOG.md"}
        offenders: list[str] = []
        for md in (ROOT / "docs").rglob("*.md"):
            for m in re.finditer(r"\]\((?!https?://|mailto:|#)([^)]+)\)", md.read_text(encoding="utf-8")):
                target = m.group(1).split("#")[0]
                if target.startswith("../") and target[3:] in root_docs:
                    offenders.append(f"{md.relative_to(ROOT)} -> {target}")
        self.assertEqual(
            offenders, [],
            "These targets are not published; link them by absolute repository URL: "
            f"{offenders}",
        )

    def test_stability_register_rows_keep_their_column_count(self):
        r"""An unescaped ``|`` inside a cell splits it and breaks the rendered row.

        The register is a fixed five-column table, so a row whose pipe count
        differs from the header renders with the wrong columns. Escaped pipes
        (``\|``) are literal and must not count.
        """
        import re

        lines = (ROOT / "docs" / "STABILITY.md").read_text(encoding="utf-8").splitlines()
        header = next(i for i, line in enumerate(lines) if line.startswith("| # |"))
        expected = lines[header].replace("\\|", "").count("|")
        broken = [
            (n, line.count("|") - expected)
            for n, line in enumerate(lines, start=1)
            if re.match(r"^\| *\d+ *\|", line)
            and line.replace("\\|", "").count("|") != expected
        ]
        self.assertEqual(broken, [], f"Stability rows with a broken column count: {broken}")

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
