"""Regression checks for public documentation rendering."""

import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# scripts/ holds the documentation maintenance entrypoint. Set up once here
# rather than inside a single test: doing it in a test body made the import work
# only for whichever tests happened to run after it, so a test ordered earlier
# failed on ModuleNotFoundError.
sys.path.insert(0, str(ROOT / "scripts"))


class TestDocumentation(unittest.TestCase):
    def test_public_demo_boundary_excludes_unapproved_helper_files(self):
        """Publishing the demo must not publish its entire working directory."""
        import tempfile

        from stage_pages import DOCS_ROOT_FILES, PUBLIC_TREES, stage

        self.assertEqual({name for name in DOCS_ROOT_FILES if name.startswith("demo/")}, {"demo/report.html"})
        self.assertNotIn("demo", PUBLIC_TREES)

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "docs"
            (source / "demo").mkdir(parents=True)
            (source / "guides").mkdir()
            report = "<html><body>Synthetic read-only report.</body></html>"
            (source / "demo" / "report.html").write_text(report, encoding="utf-8")
            (source / "guides" / "first-look.html").write_text("Synthetic guide.", encoding="utf-8")
            for name in ("unapproved.html", "source.md", "output.json", "archive.zip"):
                (source / "demo" / name).write_text("Synthetic unapproved helper.", encoding="utf-8")
            (source / "demo" / "helpers").mkdir()
            (source / "demo" / "helpers" / "input.html").write_text("Unapproved nested helper.", encoding="utf-8")
            output = Path(directory) / "site"
            stage(source, output)
            self.assertEqual((output / "demo" / "report.html").read_text(encoding="utf-8"), report)
            self.assertTrue((output / "guides" / "first-look.html").is_file())
            self.assertEqual({path.name for path in (output / "demo").iterdir()}, {"report.html"})

    def test_first_look_journey_and_relative_assets_exist_in_published_output(self):
        """The guide/report journey must survive Pages' explicit staging boundary."""
        import tempfile
        from urllib.parse import urlsplit

        from stage_pages import stage

        class Links(HTMLParser):
            def __init__(self):
                super().__init__()
                self.targets = []

            def handle_starttag(self, tag, attrs):
                attributes = dict(attrs)
                for key in ("href", "src"):
                    if attributes.get(key):
                        self.targets.append(attributes[key])

        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            stage(ROOT / "docs", output)
            pages = (output / "index.html", output / "guides" / "first-look.html", output / "demo" / "report.html")
            resolved = {}
            for page in pages:
                self.assertTrue(page.is_file(), f"Missing staged journey page: {page.relative_to(output)}")
                parser = Links()
                parser.feed(page.read_text(encoding="utf-8"))
                local = set()
                for target in parser.targets:
                    url = urlsplit(target)
                    if url.scheme or url.netloc or not url.path:
                        continue
                    path = (page.parent / url.path).resolve()
                    self.assertTrue(path.is_relative_to(output), f"Public link escapes staged output: {target}")
                    self.assertTrue(path.exists(), f"Broken staged journey link: {page.relative_to(output)} -> {target}")
                    local.add(path)
                resolved[page] = local
            self.assertIn(pages[1], resolved[pages[0]])
            self.assertIn(pages[2], resolved[pages[1]])

    def test_synthetic_demo_distributes_complete_license_as_an_appendix(self):
        """A standalone generated report retains the unchanged distribution terms."""
        from html import unescape

        report = (ROOT / "docs" / "demo" / "report.html").read_text(encoding="utf-8")
        appendix = re.search(r'<pre\b[^>]*\bid="demo-license-text"[^>]*>(.*?)</pre>', report, re.DOTALL)
        self.assertIsNotNone(appendix)
        self.assertEqual(unescape(appendix[1]), (ROOT / "LICENSE").read_text(encoding="utf-8"))
        self.assertNotIn("Lixity Non-Commercial License", report.split('<main id="chapters">')[1].split("</main>")[0])

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

    def test_next_release_syncs_current_note_links_and_preserves_history(self):
        import tempfile
        from unittest.mock import patch

        from sync_docs import check_or_sync_files, find_version_drift, get_version

        current = get_version()
        major, minor, _ = current.split(".")
        next_version = f"{major}.{int(minor) + 1}.0"
        originals = {
            "README.md": (ROOT / "README.md").read_text(encoding="utf-8"),
            "docs/index.html": (ROOT / "docs/index.html").read_text(encoding="utf-8"),
            "docs/INSTALLATION.md": (ROOT / "docs/INSTALLATION.md").read_text(encoding="utf-8"),
            "docs/guides/installation.html": (ROOT / "docs/guides/installation.html").read_text(encoding="utf-8"),
        }
        historical = {
            "README.md": "\nSince v1.16.0: [HD-D release](docs/releases/v1.16.0.md).\n",
            "docs/index.html": '\n<p>Since v1.16.0: <a href="releases/v1.16.0.md">HD-D release</a>.</p>\n',
            "docs/INSTALLATION.md": "\nSince v1.16.0: [HD-D release](releases/v1.16.0.md).\n",
            "docs/guides/installation.html": '\n<p>Since v1.16.0: <a href="../releases/v1.16.0.md">release history</a>.</p>\n',
        }
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            for name, text in originals.items():
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_text(text + historical[name], encoding="utf-8")
            with patch("sync_docs.ROOT", root):
                self.assertCountEqual(check_or_sync_files(next_version, check_only=True), originals)
                for name, text in originals.items():
                    self.assertEqual((root / name).read_text(encoding="utf-8"), text + historical[name])

                check_or_sync_files(next_version)
                self.assertEqual(find_version_drift(next_version), [])
                for name in originals:
                    content = (root / name).read_text(encoding="utf-8")
                    self.assertIn(f"releases/v{next_version}.md", content)
                    self.assertNotIn(f"releases/v{current}.md", content)
                    self.assertIn(historical[name], content)
                    # Keep the label current but make only its target stale.
                    (root / name).write_text(
                        content.replace(f"releases/v{next_version}.md", f"releases/v{current}.md", 1),
                        encoding="utf-8",
                    )
                findings = find_version_drift(next_version)
                self.assertEqual(len(findings), 4)
                self.assertTrue(all("current release-note target" in finding for finding in findings))

    def test_citation_release_metadata_syncs_without_changing_authorship(self):
        import tempfile
        from unittest.mock import patch

        from sync_docs import check_or_sync_files, find_version_drift

        citation = 'cff-version: 1.2.0\nversion: "0.1.0"\ndate-released: "2000-01-01"\nauthors: []\n'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            path = root / "CITATION.cff"
            path.write_text(citation, encoding="utf-8")
            (root / "CHANGELOG.md").write_text("## [2.3.4] - 2026-10-05\n", encoding="utf-8")
            with patch("sync_docs.ROOT", root):
                self.assertEqual(check_or_sync_files("2.3.4", check_only=True), ["CITATION.cff"])
                self.assertEqual(path.read_text(encoding="utf-8"), citation)
                self.assertTrue(any("CITATION.cff" in finding for finding in find_version_drift("2.3.4")))
                check_or_sync_files("2.3.4")
                self.assertEqual(path.read_text(encoding="utf-8"), citation.replace(
                    'version: "0.1.0"', 'version: "2.3.4"').replace("2000-01-01", "2026-10-05"))
                self.assertEqual(check_or_sync_files("2.3.4", check_only=True), [])
                self.assertEqual(find_version_drift("2.3.4"), [])

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
