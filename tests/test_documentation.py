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
    def test_published_reports_bundle_the_current_packaged_interface(self):
        """Demo/classic UI must not silently drift from the release's native UI."""
        from lixity.ui.dashboard import _CSS_FILES, _JS_FILES

        assets = ROOT / "src/lixity/ui/assets"
        for relative in ("demo/report.html", "examples/effi-briest.html", "examples/pride-and-prejudice.html"):
            report = (ROOT / "docs" / relative).read_text(encoding="utf-8")
            for name in (*_CSS_FILES, *_JS_FILES):
                with self.subTest(report=relative, asset=name):
                    self.assertEqual(report.count((assets / name).read_text(encoding="utf-8").strip()), 1,
                                     "Regenerate public reports with 'make examples' before publishing UI changes")

    def test_public_demo_can_read_exact_passage_research_versions(self):
        """The read-only adapter must serve native context-bound pinned reads."""
        import json
        from urllib.parse import urlencode

        document = (ROOT / "docs/demo/report.html").read_text(encoding="utf-8")
        data = re.search(r'<script[^>]*id="lixity-site-data"[^>]*>(.*?)</script>', document, re.DOTALL)
        self.assertIsNotNone(data, "The public demo must use the production website transport")
        fixture = json.loads(data[1])["responses"]
        project_token = re.search(r'data-manuscript-project-token="([^"]+)"', document)[1]
        research_token = re.search(r'data-research-token="([^"]+)"', document)[1]
        reports = [value for value in fixture.values()
                   if value.get("schema_version") == "research-manuscript-review-local/1"]
        self.assertTrue(reports)

        def record(kind, identifier, revision, snapshot):
            query = urlencode(sorted({"project_token": project_token,
                               "id": identifier, "kind": kind, "revision": revision,
                               "research_token": research_token}.items()))
            key = "/api/research/record?" + query
            self.assertTrue(key in fixture, f"Native passage-context request has no prepared response: {key}")
            result = fixture[key]
            self.assertEqual(result["snapshot"], snapshot)
            self.assertEqual((result["record"]["id"], result["record"]["revision"]),
                             (identifier, revision))
            return result["record"]

        for report in reports:
            self.assertTrue(report["links"])
            for link in report["links"]:
                claim = record("claim", link["claim_id"], link["claim_revision"], report["snapshot"])
                if claim.get("dossier_ref"):
                    ref = claim["dossier_ref"]
                    record("dossier", ref["id"], ref["revision"], report["snapshot"])

    def test_packaged_readme_links_and_images_work_outside_the_repository(self):
        """PyPI renders the same README without a checkout-relative URL base."""
        import tempfile
        from urllib.parse import urlsplit

        from stage_pages import stage

        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        targets = re.findall(r"\]\(([^)]+)\)", readme)
        targets += re.findall(r'''\b(?:href|src)=["']([^"']+)["']''', readme)
        relative = [target for target in targets if not target.startswith("#") and not urlsplit(target).scheme]
        self.assertEqual(relative, [], "README targets must work on PyPI as well as GitHub")
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            stage(ROOT / "docs", output)
            for target in targets:
                url = urlsplit(target)
                if url.netloc == "mfahsold.github.io" and url.path.startswith("/lixity/"):
                    path = output / url.path.removeprefix("/lixity/")
                    self.assertTrue(path.exists(), f"README target is not published: {target}")
                elif target.startswith("https://github.com/mfahsold/lixity/blob/main/"):
                    path = ROOT / url.path.removeprefix("/mfahsold/lixity/blob/main/")
                    self.assertTrue(path.exists(), f"README repository target is missing: {target}")

    def test_absolute_readme_release_links_sync_and_report_target_drift(self):
        import tempfile
        from unittest.mock import patch

        from sync_docs import check_or_sync_files, find_version_drift

        prefix = "https://mfahsold.github.io/lixity/releases/"
        text = (
            f"[v0.7.1 release notes]({prefix}v0.7.1.md)\n"
            f"[Release notes]({prefix}v0.7.1.md)\n"
            f"Since v0.6.0: [historical note]({prefix}v0.6.0.md)\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "README.md"
            path.write_text(text, encoding="utf-8")
            with patch("sync_docs.ROOT", root):
                self.assertEqual(check_or_sync_files("0.7.2", check_only=True), ["README.md"])
                check_or_sync_files("0.7.2")
                actual = path.read_text(encoding="utf-8")
                self.assertEqual(actual, text.replace("v0.7.1", "v0.7.2"))
                self.assertEqual(find_version_drift("0.7.2"), [])
                path.write_text(actual.replace(f"{prefix}v0.7.2.md", f"{prefix}v0.7.1.md", 1))
                findings = find_version_drift("0.7.2")
                self.assertEqual(len(findings), 1)
                self.assertIn("current release-note target", findings[0])

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
            for layout in ("editor", "book", "sheet", "report", "document"):
                pdf = output / "demo" / f"warehouse-4-{layout}.pdf"
                self.assertIn(pdf, resolved[pages[2]], "All PDF examples belong to the same demo project")
                self.assertTrue(pdf.read_bytes().startswith(b"%PDF-"), f"Invalid staged PDF: {pdf.name}")

    def test_synthetic_demo_distributes_complete_license_as_an_appendix(self):
        """A standalone generated report retains the unchanged distribution terms."""
        from html import unescape

        report = (ROOT / "docs" / "demo" / "report.html").read_text(encoding="utf-8")
        appendix = re.search(r'<pre\b[^>]*\bid="demo-license-text"[^>]*>(.*?)</pre>', report, re.DOTALL)
        self.assertIsNotNone(appendix)
        self.assertEqual(unescape(appendix[1]), (ROOT / "LICENSE").read_text(encoding="utf-8"))
        manuscript = re.search(r'<main\b[^>]*\bid="chapters"[^>]*>(.*?)</main>', report, re.DOTALL)
        self.assertIsNotNone(manuscript)
        self.assertNotIn("GNU AFFERO GENERAL PUBLIC LICENSE", manuscript[1])

    def test_math_avoids_macros_rejected_by_github(self):
        for path in (ROOT / "docs").glob("*.md"):
            with self.subTest(path=path.name):
                self.assertNotIn(r"\operatorname", path.read_text(encoding="utf-8"))

    def test_readme_has_no_markdown_escapes_in_raw_html(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for block in re.findall(r"<details>.*?</details>", readme, re.DOTALL):
            self.assertNotIn(r"\*", block)

    def test_llms_full_bundle_matches_its_sources(self):
        """The agent bundle is generated; edit the sources and rerun the builder."""
        from build_llms_full import build_bundle

        actual = (ROOT / "docs" / "llms-full.txt").read_text(encoding="utf-8")
        self.assertEqual(actual, build_bundle(), "Run 'python scripts/build_llms_full.py'")

    def test_public_entrypoints_explain_book_sales(self):
        for name in ("README.md", "docs/index.html", "docs/llms.txt"):
            with self.subTest(path=name):
                content = " ".join((ROOT / name).read_text(encoding="utf-8").lower().split())
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

    def test_html_current_install_statement_is_checked_and_synced(self):
        import tempfile
        from unittest.mock import patch

        from sync_docs import check_or_sync_files, find_version_drift

        statement = '<p>This installs the current release, <strong>v1.2.3</strong>, from PyPI.</p>'
        history = '<p>Since v1.2.3: historical behavior.</p>'
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            guide = root / "docs/guides/installation.html"
            guide.parent.mkdir(parents=True)
            guide.write_text(statement + history, encoding="utf-8")
            with patch("sync_docs.ROOT", root):
                findings = find_version_drift("2.3.4")
                self.assertEqual(len(findings), 1)
                self.assertIn("current HTML install statement", findings[0])
                self.assertEqual(check_or_sync_files("2.3.4", check_only=True),
                                 ["docs/guides/installation.html"])
                self.assertEqual(guide.read_text(encoding="utf-8"), statement + history)
                check_or_sync_files("2.3.4")
                self.assertEqual(guide.read_text(encoding="utf-8"),
                                 statement.replace("v1.2.3", "v2.3.4") + history)
                self.assertEqual(find_version_drift("2.3.4"), [])

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
            "docs/llms.txt": (ROOT / "docs/llms.txt").read_text(encoding="utf-8"),
            "docs/guides/installation.html": (ROOT / "docs/guides/installation.html").read_text(encoding="utf-8"),
        }
        historical = {
            "README.md": "\nSince v1.16.0: [HD-D release](docs/releases/v1.16.0.md).\n",
            "docs/index.html": '\n<p>Since v1.16.0: <a href="releases/v1.16.0.md">HD-D release</a>.</p>\n',
            "docs/INSTALLATION.md": "\nSince v1.16.0: [HD-D release](releases/v1.16.0.md).\n",
            "docs/llms.txt": "\nSince v1.16.0: [HD-D release](https://mfahsold.github.io/lixity/releases/v1.16.0.md).\n",
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
                self.assertEqual(len(findings), len(originals))
                self.assertTrue(all("current release-note target" in finding for finding in findings))

    def test_zenodo_metadata_matches_citation_and_license(self):
        """The Zenodo deposit describes the same work as CITATION.cff."""
        import json

        metadata = json.loads(
            (Path(__file__).resolve().parents[1] / ".zenodo.json").read_text(encoding="utf-8")
        )
        self.assertEqual(metadata["upload_type"], "software")
        self.assertEqual(metadata["license"], "AGPL-3.0-or-later")
        self.assertEqual(metadata["access_right"], "open")
        self.assertEqual([creator["name"] for creator in metadata["creators"]],
                         ["Fahsold, Matthias"])
        self.assertTrue(metadata["title"].startswith("Lixity"))
        self.assertTrue(any(item["scheme"] == "url" for item in metadata["related_identifiers"]))

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

    def test_wheel_install_pin_checks_and_syncs_both_tag_and_artifact_version(self):
        import tempfile
        from unittest.mock import patch

        from sync_docs import check_or_sync_files, find_version_drift

        old = "https://github.com/mfahsold/lixity/releases/download/v1.2.3/lixity-9.8.7-py3-none-any.whl"
        new = "https://github.com/mfahsold/lixity/releases/download/v2.3.4/lixity-2.3.4-py3-none-any.whl"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            readme = root / "README.md"
            readme.write_text("Install with uv: " + old + "\n")
            with patch("sync_docs.ROOT", root):
                self.assertEqual(check_or_sync_files("2.3.4", check_only=True), ["README.md"])
                self.assertIn(old, readme.read_text())
                self.assertEqual(len(find_version_drift("2.3.4")), 2)
                check_or_sync_files("2.3.4")
                self.assertEqual(readme.read_text(), "Install with uv: " + new + "\n")
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

            def anchors(target: Path) -> set[str]:
                text = target.read_text(encoding="utf-8")
                found = set(re.findall(r'''\bid=["']([^"']+)["']''', text))
                if target.suffix == ".html":
                    return found
                for line in text.splitlines():
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
                    if resolved.is_dir():
                        resolved = resolved / "index.html"
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
