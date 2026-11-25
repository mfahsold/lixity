"""Public Pages staging excludes local planning and private working material."""

import hashlib
import html
import json
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import textwrap
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from desktop.scripts.verify_desktop_artifacts import DesktopArtifact, public_installer_inventory
from scripts import desktop_downloads
from scripts.stage_pages import stage

SITE = "https://mfahsold.github.io/lixity/"
BASH = shutil.which("bash")
GIT = shutil.which("git")


class TestDesktopDownloads(unittest.TestCase):
    def test_catalog_uses_only_verified_public_asset_bytes(self):
        tag = "v0.10.0"
        base = desktop_downloads.RELEASES
        artifacts = []
        for name, (target, kind) in public_installer_inventory(tag).items():
            artifacts.append(DesktopArtifact(target, kind, name, 2048, hashlib.sha256(name.encode()).hexdigest()))
        checksums = "".join(f"{asset.sha256}  {asset.filename}\n" for asset in artifacts).encode("ascii")

        def published_asset(name, size, digest):
            return {"name": name, "size": size, "digest": f"sha256:{digest}", "state": "uploaded",
                    "browser_download_url": f"{base}/download/{tag}/{name}"}

        checksum_asset = published_asset(desktop_downloads.CHECKSUMS, len(checksums),
                                         hashlib.sha256(checksums).hexdigest())
        qualification = b"qualification receipt fixture"
        receipt_asset = published_asset(desktop_downloads.QUALIFICATION_FILE, len(qualification),
                                        hashlib.sha256(qualification).hexdigest())
        release = {"tag_name": tag, "html_url": f"{base}/tag/{tag}", "draft": False, "prerelease": False,
                   "immutable": True,
                   "published_at": "2026-01-01T00:00:00Z", "assets": [
                       *(published_asset(asset.filename, asset.size, asset.sha256) for asset in artifacts),
                       checksum_asset, receipt_asset,
                   ]}
        catalog = desktop_downloads.record_catalog(release, artifacts, checksums, qualification)
        rendered = desktop_downloads.render(catalog)
        for asset in artifacts:
            self.assertIn(f'href="{base}/download/{tag}/{asset.filename}"', rendered)
        self.assertIn(f'href="{base}/download/{tag}/{desktop_downloads.CHECKSUMS}"', rendered)
        self.assertNotIn(desktop_downloads.TEST_BUILDS, rendered)
        catalog_with_old_installer = {**catalog, "installers": [
            {**entry, "filename": entry["filename"].replace("0.10.0", "0.9.1")}
            for entry in catalog["installers"]
        ]}
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate desktop installer"):
            desktop_downloads.validate_catalog(catalog_with_old_installer)
        without_one_msi = [asset for asset in artifacts if not asset.filename.endswith("de-DE.msi")]
        self.assertEqual(len(without_one_msi), len(artifacts) - 1)
        with self.assertRaisesRegex(ValueError, "qualified installer variants"):
            desktop_downloads.record_catalog(release, without_one_msi, checksums, qualification)
        swapped_architecture = {**catalog, "installers": [
            {**entry, "target": "x86_64-apple-darwin"}
            if entry["target"] == "aarch64-apple-darwin" else entry for entry in catalog["installers"]
        ]}
        with self.assertRaisesRegex(ValueError, "Invalid or duplicate desktop installer"):
            desktop_downloads.validate_catalog(swapped_architecture)
        with self.assertRaisesRegex(ValueError, "duplicate public release asset"):
            duplicate = {**release, "assets": [*release["assets"], checksum_asset]}
            desktop_downloads.record_catalog(duplicate, artifacts, checksums, qualification)
        with self.assertRaisesRegex(ValueError, "public stable"):
            desktop_downloads.record_catalog({**release, "prerelease": True}, artifacts, checksums, qualification)
        with self.assertRaisesRegex(ValueError, "published checksum list"):
            desktop_downloads.record_catalog(release, artifacts, checksums + checksums, qualification)
        with self.assertRaisesRegex(ValueError, "Public release asset differs .*desktop-qualification"):
            desktop_downloads.record_catalog(release, artifacts, checksums, b"replaced qualification")
        checksum_asset["digest"] = "sha256:" + "0" * 64
        with self.assertRaisesRegex(ValueError, "Public release asset differs"):
            desktop_downloads.record_catalog(release, artifacts, checksums, qualification)

    def test_empty_catalog_and_platform_anchors_are_rendered_without_native_downloads(self):
        catalog = {"schema_version": desktop_downloads.SCHEMA, "tag": None, "installers": []}
        rendered = desktop_downloads.render(catalog)
        self.assertIn('href="#install"', rendered)
        self.assertIn(f'href="{desktop_downloads.TEST_BUILDS}"', rendered)
        self.assertNotIn("/download/", rendered)
        guide = (desktop_downloads.ROOT / desktop_downloads.GUIDE).read_text(encoding="utf-8")
        for anchor in ("macos", "windows", "linux"):
            self.assertIn(f'href="#{anchor}"', guide)
            self.assertIn(f'id="{anchor}"', guide)

    def test_only_the_validated_desktop_catalog_is_published(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "docs"
            source.mkdir()
            path = source / desktop_downloads.CATALOG.name
            expected = (desktop_downloads.ROOT / desktop_downloads.CATALOG).read_bytes()
            path.write_bytes(expected)
            (source / "desktop-downloads-local.json").write_bytes(expected)
            output = Path(directory) / "public"
            stage(source, output)
            self.assertEqual((output / path.name).read_bytes(), expected)
            self.assertFalse((output / "desktop-downloads-local.json").exists())

            path.write_text('{"schema_version": "unknown"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid desktop download catalog"):
                stage(source, Path(directory) / "invalid")


def pages_workflow_script(name):
    """Extract one reviewed literal shell step for a local workflow boundary test."""
    source = (Path(__file__).resolve().parents[1] / ".github/workflows/pages.yml").read_text()
    step = source.split(f"      - name: {name}\n", 1)[1].split("      - ", 1)[0]
    script = step.split("        run: ", 1)[1]
    return textwrap.dedent(script[2:]) if script.startswith("|\n") else script.splitlines()[0]


@unittest.skipUnless(BASH and GIT, "Workflow boundary requires the Pages runner's bash and git")
class TestPagesWorkflow(unittest.TestCase):
    @unittest.skipUnless(shutil.which("make"), "Pages documentation gate requires make")
    def test_stale_metric_reference_fails_the_standalone_generated_documentation_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            checkout = Path(__file__).resolve().parents[1]
            for relative in ("Makefile", "scripts/sync_docs.py", "scripts/check_release.py", "src/lixity/_version.py"):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(checkout / relative, target)
            builders = ("build_blog_feed", "build_public_site", "build_llms_full",
                    "build_guide_markdown", "build_metric_reference")
            for name in builders:
                stale = ["docs/guides/metrics/de.html"] if name == "build_metric_reference" else []
                (root / "scripts" / f"{name}.py").write_text(
                    "def build(*, check_only, root):\n"
                    "    assert check_only\n"
                    f"    (root / '{name}.checked').touch()\n"
                    f"    return {stale!r}\n",
                    encoding="utf-8",
                )
            result = subprocess.run(  # noqa: S603 - reviewed workflow step, disposable generators
                [BASH, "-e", "-c", pages_workflow_script("Verify generated documentation")],
                cwd=root, capture_output=True, text=True, check=False, timeout=10,
                env={**os.environ, "PATH": os.pathsep.join((str(Path(sys.executable).parent), os.environ.get("PATH", "")))},
            )
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("docs/guides/metrics/de.html", result.stderr)
            for name in builders:
                self.assertTrue((root / f"{name}.checked").exists(), name)

    def test_public_deployment_metadata_records_actual_checkout_head(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for command in ([GIT, "init", "-q"],
                            [GIT, "-c", "user.name=Synthetic CI", "-c", "user.email=ci@example.test",
                             "commit", "--allow-empty", "-qm", "Synthetic Pages source"]):
                subprocess.run(command, cwd=root, check=True, capture_output=True)  # noqa: S603
            expected = subprocess.check_output([GIT, "rev-parse", "HEAD"],  # noqa: S603
                                               cwd=root, text=True).strip()
            (root / "lixity-pages").mkdir()
            summary = root / "summary.md"
            outputs = root / "outputs"
            run_url = "https://github.com/example/synthetic/actions/runs/123"
            result = subprocess.run(  # noqa: S603 - reviewed workflow step, synthetic repository
                [BASH, "-e", "-c", pages_workflow_script("Record exact public deployment source")],
                cwd=root, capture_output=True, text=True, check=False, timeout=10,
                env={**os.environ, "RUNNER_TEMP": directory, "GITHUB_STEP_SUMMARY": str(summary),
                     "SOURCE_RUN_URL": run_url, "GITHUB_SHA": "0" * 40,
                     "GITHUB_OUTPUT": str(outputs), "GITHUB_RUN_ATTEMPT": "2"},
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            metadata = json.loads((root / "lixity-pages/deployment.json").read_text())
            self.assertEqual(metadata, {"schema_version": 1, "source_sha": expected,
                                        "workflow_run_url": run_url})
            self.assertIn(expected, summary.read_text())
            self.assertNotIn(directory, json.dumps(metadata))
            self.assertEqual(outputs.read_text(), "artifact_name=github-pages-2\n")

    def test_production_deployment_preserves_an_active_run_and_uses_an_immutable_default(self):
        source = (Path(__file__).resolve().parents[1] / ".github/workflows/pages.yml").read_text()
        concurrency = re.search(r"(?ms)^concurrency:\n(.*?)(?=^jobs:)", source)
        self.assertIsNotNone(concurrency)
        self.assertIn("cancel-in-progress: false", concurrency.group(1))
        self.assertIn("ref: ${{ inputs.source_ref || github.sha }}", source)
        self.assertIn("if: inputs.release_tag != ''", source)
        self.assertIn("if: inputs.release_tag == '' || steps.guard.outputs.allow == 'true'", source)

    @unittest.skipUnless(shutil.which("jq"), "Workflow boundary requires the Pages runner's jq")
    def test_release_deployment_guard_keeps_newer_pages_and_allows_pending_release(self):
        live, proposed = "a" * 40, "b" * 40
        metadata = json.dumps({"schema_version": 1, "source_sha": live})
        cases = (
            ("superseded tag", {"TEST_LATEST": "v0.9.3"}, 0, False, ["latest"]),
            ("deployed release ancestor", {}, 0, True, ["latest", "metadata", "compare"]),
            ("same-source retry", {"TEST_METADATA": metadata.replace(live, proposed)},
             0, True, ["latest", "metadata"]),
            ("same latest tag behind deployed main", {"TEST_RELATIONSHIP": "behind"},
             0, False, ["latest", "metadata", "compare"]),
            ("divergent deployed source", {"TEST_RELATIONSHIP": "diverged"},
             0, False, ["latest", "metadata", "compare"]),
            ("first deployment", {"TEST_META_STATUS": "404", "TEST_ROOT_STATUS": "404"},
             0, True, ["latest", "metadata", "root"]),
            ("existing site missing metadata", {"TEST_META_STATUS": "404"},
             1, False, ["latest", "metadata", "root"]),
            ("invalid metadata", {"TEST_METADATA": "{}"}, 1, False, ["latest", "metadata"]),
            ("unavailable metadata", {"TEST_META_STATUS": "503"}, 1, False, ["latest", "metadata"]),
            ("unverified ancestry", {"TEST_MERGE_BASE": proposed}, 1, False, ["latest", "metadata", "compare"]),
        )
        script = pages_workflow_script("Protect newer Pages deployments from release retries")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            gh = root / "gh"
            gh.write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                case "$2" in
                  repos/example/synthetic/releases/latest)
                    echo latest >> "$TEST_REQUESTS"
                    printf '{"tag_name":"%s"}\\n' "$TEST_LATEST" ;;
                  "repos/example/synthetic/compare/$TEST_LIVE...$RELEASE_SHA?per_page=1")
                    echo compare >> "$TEST_REQUESTS"
                    printf '{"status":"%s","merge_base_commit":{"sha":"%s"}}\\n' \\
                      "$TEST_RELATIONSHIP" "$TEST_MERGE_BASE" ;;
                  *) exit 9 ;;
                esac
                """), encoding="utf-8", newline="\n")
            curl = root / "curl"
            curl.write_text(textwrap.dedent("""\
                #!/usr/bin/env bash
                [[ -z "${GH_TOKEN:-}${GITHUB_TOKEN:-}" ]] || exit 8
                while (($#)); do
                  case "$1" in
                    --output) destination="$2"; shift ;;
                    https://*) url="$1" ;;
                  esac
                  shift
                done
                case "$url" in
                  https://example.test/site/deployment.json\\?run=100-2)
                    echo metadata >> "$TEST_REQUESTS"
                    printf '%s' "$TEST_METADATA" > "$destination"
                    printf '%s' "$TEST_META_STATUS" ;;
                  https://example.test/site/\\?run=100-2)
                    echo root >> "$TEST_REQUESTS"
                    printf '%s' "$TEST_ROOT_STATUS" ;;
                  *) exit 9 ;;
                esac
                """), encoding="utf-8", newline="\n")
            gh.chmod(0o700)
            curl.chmod(0o700)
            outputs, summary, requests = (root / name for name in ("outputs", "summary", "requests"))
            env = {**os.environ, "PATH": os.pathsep.join((directory, os.environ.get("PATH", ""))),
                   "RUNNER_TEMP": directory, "GITHUB_OUTPUT": str(outputs), "GITHUB_STEP_SUMMARY": str(summary),
                   "GITHUB_REPOSITORY": "example/synthetic", "GITHUB_RUN_ID": "100", "GITHUB_RUN_ATTEMPT": "2",
                   "GH_TOKEN": "synthetic-gh-token", "GITHUB_TOKEN": "synthetic-github-token",
                   "RELEASE_TAG": "v0.9.2", "RELEASE_SHA": proposed,
                   "PAGES_BASE_URL": "https://example.test/site/", "TEST_REQUESTS": str(requests),
                   "TEST_LATEST": "v0.9.2", "TEST_LIVE": live, "TEST_METADATA": metadata,
                   "TEST_META_STATUS": "200", "TEST_ROOT_STATUS": "200", "TEST_RELATIONSHIP": "ahead",
                   "TEST_MERGE_BASE": live}
            for name, overrides, code, allow, expected_requests in cases:
                with self.subTest(name=name):
                    outputs.unlink(missing_ok=True)
                    summary.unlink(missing_ok=True)
                    requests.unlink(missing_ok=True)
                    result = subprocess.run(  # noqa: S603 - reviewed workflow step, synthetic API responses
                        [BASH, "-e", "-o", "pipefail", "-c", script], cwd=root, timeout=10,
                        env={**env, **overrides}, text=True, capture_output=True, check=False,
                    )
                    self.assertEqual(result.returncode == 0, code == 0, result.stdout + result.stderr)
                    self.assertEqual(requests.read_text().splitlines(), expected_requests)
                    if allow:
                        self.assertEqual(outputs.read_text(), "allow=true\n")
                    else:
                        self.assertFalse(outputs.exists())
                        if code == 0:
                            self.assertIn("Pages deployment skipped", summary.read_text())


class PageHead(HTMLParser):
    """Inspect actual head declarations, excluding text in dashboard examples."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_head = False
        self.in_json = False
        self.links = []
        self.meta = {}
        self.structured = []
        self.json_parts = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "head":
            self.in_head = True
        if not self.in_head:
            return
        if tag == "link":
            self.links.append(values)
        elif tag == "meta":
            key = values.get("property") or values.get("name") or values.get("http-equiv")
            if key:
                self.meta.setdefault(key, []).append(values.get("content", ""))
        elif tag == "script" and values.get("type") == "application/ld+json":
            self.in_json = True
            self.json_parts = []

    def handle_data(self, data):
        if self.in_json:
            self.json_parts.append(data)

    def handle_endtag(self, tag):
        if tag == "script" and self.in_json:
            self.structured.append(json.loads("".join(self.json_parts)))
            self.in_json = False
        elif tag == "head":
            self.in_head = False


class TestPagesStaging(unittest.TestCase):
    def test_german_entry_is_published_linked_and_honest_about_demo_language(self):
        docs = Path(__file__).resolve().parents[1] / "docs"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            stage(docs, output)
            german = (output / "guides/first-look-de.html").read_text(encoding="utf-8")
            english = (output / "guides/first-look.html").read_text(encoding="utf-8")
            home = (output / "index.html").read_text(encoding="utf-8")
            self.assertIn('<html lang="de"', german)
            self.assertIn('href="guides/first-look-de.html" lang="de" hreflang="de"', home)
            self.assertIn('hreflang="de" href="' + SITE + 'guides/first-look-de.html"', english)
            self.assertIn('hreflang="en" href="' + SITE + 'guides/first-look.html"', german)
            self.assertIn("erfundenes englisches Hafenmanuskript", german)
            self.assertIn("<code>lixity service start --open</code>", german)
            self.assertIn('href="installation.html#restart"', german)
            self.assertTrue((output / "guides/first-look-de.html.md").is_file())

    def test_demo_uses_the_native_rail_for_guidance(self):
        docs = Path(__file__).resolve().parents[1] / "docs"
        document = (docs / "demo/report.html").read_text(encoding="utf-8")
        rail = document.split('<div class="workspace-shell">', 1)[1].split('<!--dashboard-freshness-->', 1)[0]
        self.assertIn('id="demo-quick-start"><summary>Try the draft examples</summary>', rail)
        self.assertIn('class="site-read-only-notice"', rail)
        self.assertIn('<a href="../">About Lixity</a>', document)
        self.assertNotIn('<nav class="site-return"', document)
        self.assertNotIn('<a class="site-back-top"', document)

    def test_public_navigation_preserves_workspace_and_report_classes(self):
        from scripts.example_publications import _insert_notice, _site_navigation

        for mode in ("lixity-workspace", "lixity-report"):
            with self.subTest(mode=mode):
                content = (
                    '<div class="workspace-shell"><header>Example</header>'
                    '<div id="workspace-navigation-content">'
                    '<nav class="view-navigation"></nav>'
                    '<details id="project-actions"><summary>Project actions</summary>'
                    '<nav id="project-controls"><div><button>Open</button></div></nav>'
                    '</details></div></div><!--dashboard-freshness-->'
                ) if mode == "lixity-workspace" else '<header>Example</header>'
                page = _site_navigation(
                    f'<html><head></head><body id="top" class="{mode}">'
                    '<div class="page">' + content + '<main>Manuscript</main></div></body></html>',
                    "Example",
                )
                body = page.split("<body", 1)[1].split(">", 1)[0]
                self.assertEqual(body.count('class="'), 1)
                self.assertIn(f'class="{mode} site-page"', body)
                self.assertIn('tabindex="-1"', body)
                page = _insert_notice(page, '<section id="demo-notice">About</section>')
                if mode == "lixity-workspace":
                    self.assertLess(page.index('class="site-return"'), page.index('class="workspace-shell"'))
                    self.assertIn('</details></div></div><section id="demo-notice">', page)
                    self.assertIn('</section><!--dashboard-freshness--><main>', page)
                else:
                    self.assertIn('</header><section id="demo-notice">About</section><main>', page)

    def test_report_title_replacement_ignores_embedded_svg_script_literals(self):
        from scripts.example_publications import _replace_title

        report = '<html><head><title>Original</title></head><body><script>var svg = "<title>Feature</title>";</script></body></html>'
        self.assertEqual(_replace_title(report, "Research & maps"), report.replace(
            "<title>Original</title>", "<title>Research &amp; maps</title>",
        ))

    def test_legacy_research_page_redirects_to_the_single_workspace(self):
        docs = Path(__file__).resolve().parents[1] / "docs"
        document = (docs / "demo/research.html").read_text(encoding="utf-8")
        head = PageHead()
        head.feed(document)
        self.assertEqual([link["href"] for link in head.links if link.get("rel") == "canonical"],
                         [SITE + "demo/report.html"])
        self.assertRegex(head.meta.get("refresh", [""])[0], r"(?i)^0;\s*url=report\.html#research-manager$")
        self.assertIn('href="report.html#research-manager"', document)
        self.assertNotIn('id="research-manager"', document)
        self.assertLess(len(document.encode("utf-8")), 8_000, "The old URL is a compatibility page, not a second workspace")

    def test_sitemap_covers_published_html_canonicals(self):
        docs = Path(__file__).resolve().parents[1] / "docs"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            stage(docs, output)
            canonical_urls = []
            for page in output.rglob("*.html"):
                if page.relative_to(output).as_posix() == "demo/research.html":
                    continue  # The tested compatibility redirect shares the report's canonical.
                head = PageHead()
                head.feed(page.read_text(encoding="utf-8"))
                directives = {rule.strip().lower() for policy in head.meta.get("robots", []) for rule in policy.split(",")}
                if "noindex" not in directives:
                    canonical_urls.extend(link["href"] for link in head.links if link.get("rel") == "canonical")
            # This XML is maintained repository content, never an imported document.
            listed = [node.text for node in ET.parse(output / "sitemap.xml")  # noqa: S314
                      .findall("{*}url/{*}loc")]
            self.assertEqual(len(listed), len(set(listed)))
            self.assertCountEqual(listed, canonical_urls)
            tree = ET.parse(output / "sitemap.xml")  # noqa: S314
            sitemap_text = (output / "sitemap.xml").read_text(encoding="utf-8")
            self.assertIn("sitemap-image/1.1", sitemap_text)
            self.assertIn("sitemap-video/1.1", sitemap_text)
            image_ns = "{http://www.google.com/schemas/sitemap-image/1.1}"
            video_ns = "{http://www.google.com/schemas/sitemap-video/1.1}"
            prefix = "https://mfahsold.github.io/lixity/"
            media = [node.text for node in tree.getroot().findall(f".//{image_ns}image/{image_ns}loc")]
            media += [node.text for node in tree.getroot().findall(f".//{video_ns}video/{video_ns}content_loc")]
            media += [node.text for node in tree.getroot().findall(f".//{video_ns}video/{video_ns}thumbnail_loc")]
            self.assertTrue(media, "sitemap media entries")
            for url in media:
                self.assertTrue(url.startswith(prefix), url)
                self.assertTrue((output / url[len(prefix):]).is_file(), url)
            self.assertEqual(
                (output / "sitemap.xml").read_bytes(), (output / "sitemap-alt.xml").read_bytes(),
                "The fallback sitemap must stay identical to the submitted one",
            )

    def test_only_product_paths_are_published(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            public = ("index.html", "index-de.html", "USAGE.md", "guides/install.html", "assets/site.css",
                      "blog/article.html", "blog/article.html.md",
                      "assets/research/hamburg-free-port-1900.jpg",
                      "assets/research/hamburg-harbour-1890-1900.jpg", "assets/research/sources.json",
                      "demo/report.html", "demo/research.html",
                      "demo/warehouse-4-editor.pdf", "demo/warehouse-4-book.pdf",
                      "demo/warehouse-4-sheet.pdf", "demo/warehouse-4-report.pdf",
                      "demo/warehouse-4-document.pdf", "demo/warehouse-4-dossier.pdf",
                      "research/USAGE.md", "research/examples/synthetic-source.txt",
                      "screenshots/public.png", "sitemap.xml", ".nojekyll",
                      "examples/novel.html", "examples/novel-report.pdf")
            private = ("index-draft.html", "superpowers/plans/task.md", "archive/wave2-plan.md", "notes.md",
                       "GROWTH_REVIEW.md", "SECURITY_REVIEW.md",
                       ".planning/secret.md", "research/.scratch/session.md",
                       "screenshots/local.log", "private/source.txt")
            private += ("blog/session-notes.md",)
            private += ("assets/research/unreviewed.jpg", "demo/local-source.json", "demo/research-data.json")
            private += ("demo/unapproved.html", "demo/source.md", "demo/output.json",
                        "demo/archive.zip", "demo/helpers/input.html", "demo/private.pdf",
                        "demo/warehouse-4-draft.pdf")
            for name in public + private:
                path = docs / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"synthetic fixture")
            (docs / "screenshots/manifest.json").write_text(json.dumps({
                "schema_version": "lixity-screenshot-catalog/1",
                "images": [{"file": "public.png", "role": "reference", "question": "How?",
                            "alt": "Synthetic", "caption": "Synthetic example.",
                            "destination": "guides/install.html"}],
            }))
            public += ("screenshots/manifest.json",)
            output = root / "site"
            count = stage(docs, output)
            published = {str(path.relative_to(output)).replace("\\", "/")
                         for path in output.rglob("*") if path.is_file()}
            self.assertEqual(
                published,
                set(public) | {"assets/design-tokens.css", "assets/components.css", "sitemap-alt.xml"},
            )
            self.assertEqual(count, len(published))
            with self.assertRaises(FileExistsError):
                stage(docs, output)

    def test_screenshot_manifest_excludes_unreviewed_images(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            shots = docs / "screenshots"
            shots.mkdir(parents=True)
            (shots / "selected.png").write_bytes(b"reviewed synthetic image")
            (shots / "unused.png").write_bytes(b"unreviewed synthetic image")
            (shots / "manifest.json").write_text(json.dumps({
                "schema_version": "lixity-screenshot-catalog/1",
                "images": [{"file": "selected.png", "role": "lead", "question": "What was counted?",
                            "alt": "Synthetic count", "caption": "Inspect the count.",
                            "destination": "guides/first-look.html"}],
            }))
            stage(docs, root / "site")
            self.assertTrue((root / "site/screenshots/selected.png").exists())
            self.assertFalse((root / "site/screenshots/unused.png").exists())
            self.assertTrue((root / "site/screenshots/manifest.json").exists())

    def test_outreach_package_contains_reviewed_media_and_integrity_metadata(self):
        from scripts.make_screenshots import build_outreach_package
        from scripts.make_videos import SOCIAL_CLIPS
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shots = root / "docs/screenshots"
            shots.mkdir(parents=True)
            videos = root / "docs/videos"
            videos.mkdir()
            for name, _, _, _ in SOCIAL_CLIPS:
                (videos / name).write_bytes(name.encode())
            (videos / "unreviewed.mp4").write_bytes(b"not a social clip")
            entries = []
            for name, role in (("lead.png", "lead"), ("reference.png", "reference")):
                (shots / name).write_bytes(name.encode())
                entries.append({"file": name, "role": role, "question": "What was counted?",
                                "alt": "Synthetic count", "caption": "Inspect the count.",
                                "destination": "guides/first-look.html"})
            (shots / "manifest.json").write_text(json.dumps({
                "schema_version": "lixity-screenshot-catalog/1", "images": entries,
            }))
            (shots / "private-note.txt").write_text("Not a publication input")
            output = root / "package"
            build_outreach_package(root / "docs", output)
            self.assertTrue((output / "images/lead.png").is_file())
            self.assertFalse((output / "images/reference.png").exists())
            self.assertFalse((output / "private-note.txt").exists())
            data = json.loads((output / "manifest.json").read_text())
            self.assertEqual(data["state"], "draft-unpublished")
            self.assertEqual(data["images"][0]["sha256"], hashlib.sha256(b"lead.png").hexdigest())
            self.assertEqual({item["file"] for item in data["clips"]}, {name for name, _, _, _ in SOCIAL_CLIPS})
            for item in data["clips"]:
                clip = output / "videos" / item["file"]
                self.assertEqual(item["sha256"], hashlib.sha256(clip.read_bytes()).hexdigest())
            self.assertFalse((output / "videos/unreviewed.mp4").exists())
            stage(root / "docs", root / "site")
            self.assertTrue((root / "site/videos" / SOCIAL_CLIPS[0][0]).is_file())
            self.assertFalse((root / "site/videos/unreviewed.mp4").exists())
            self.assertIn("What was counted?", (output / "README.md").read_text())
            with self.assertRaises(FileExistsError):
                build_outreach_package(root / "docs", output)

    def test_demo_publishes_only_verified_production_bundle_members(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            docs = root / "docs"
            members = {"report.html": b"<html>Reviewed demo</html>",
                       "assets/sources/" + "a" * 64 + ".jpg": b"reviewed source image",
                       "licenses/Lixity-LICENSE": b"reviewed license"}
            for name, content in members.items():
                target = docs / "demo" / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(content)
            excluded = docs / "demo/assets/sources" / ("b" * 64 + ".jpg")
            excluded.write_bytes(b"unlisted local image")
            (docs / "demo/warehouse-4-book.pdf").write_bytes(b"stale unlisted PDF")
            manifest = {"schema_version": "lixity-read-only-site/1", "entrypoint": "report.html", "files": {
                name: {"sha256": hashlib.sha256(content).hexdigest(), "byte_length": len(content)}
                for name, content in members.items()}}
            (docs / "demo/manifest.json").write_text(json.dumps(manifest))
            output = root / "published"
            stage(docs, output)
            published = {path.relative_to(output / "demo").as_posix()
                         for path in (output / "demo").rglob("*") if path.is_file()}
            self.assertEqual(published, {*members, "manifest.json"})
            excluded.rename(excluded.with_suffix(".png"))
            (docs / "demo" / next(name for name in members if name.endswith(".jpg"))).write_bytes(b"changed")
            with self.assertRaisesRegex(ValueError, "checksum|changed"):
                stage(docs, root / "changed")

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

    def test_published_html_head_contract(self):
        from lixity.status import LANGUAGE_CODES
        from lixity.ui.metric_reference import (
            METRIC_REFERENCE_ENTRIES,
            METRIC_REFERENCE_SECTIONS,
            metric_reference_document,
        )

        docs = Path(__file__).resolve().parents[1] / "docs"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            stage(docs, output)
            pages = sorted(output.rglob("*.html"))
            self.assertTrue(pages, "Staged pages expected")
            references = {f"guides/metrics/{code}.html": code for code in LANGUAGE_CODES if code != "generic"}
            self.assertLessEqual(references.keys(), {page.relative_to(output).as_posix() for page in pages})
            for reference, language in references.items():
                homepage = "index.html" if language == "en" else f"index-{language}.html"
                self.assertIn(f'href="{reference}"', (output / homepage).read_text(encoding="utf-8"))
            sitemap = {node.find("{*}loc").text: node.find("{*}lastmod").text
                       for node in ET.parse(output / "sitemap.xml").getroot()}  # noqa: S314
            for page in pages:
                relative = page.relative_to(output).as_posix()
                if relative == "demo/research.html":
                    self.assertNotIn(SITE + relative, sitemap)
                    continue  # Its canonical/refresh/fallback link have a dedicated contract above.
                head = PageHead()
                head.feed(page.read_text(encoding="utf-8"))
                canonical = SITE + ("" if relative == "index.html" else relative)
                self.assertEqual([item["href"] for item in head.links if item.get("rel") == "canonical"], [canonical])
                if relative in references:
                    language = references[relative]
                    rendered = metric_reference_document(language)
                    self.assertEqual(page.read_bytes(), rendered.encode("utf-8"))
                    self.assertIn(f'<html lang="{language}">', rendered)
                    self.assertNotIn(canonical, sitemap)
                    self.assertEqual(head.meta["robots"], ["noindex,follow"])
                    self.assertNotRegex(rendered, r"\{\w+\}|<script\b")
                    ids = re.findall(r'\bid="([^"]+)"', rendered)
                    self.assertEqual(len(ids), len(set(ids)))
                    self.assertLessEqual(METRIC_REFERENCE_ENTRIES | METRIC_REFERENCE_SECTIONS, set(ids))
                    self.assertEqual(set(re.findall(r'\bhref="#([^"]+)"', rendered)), METRIC_REFERENCE_SECTIONS)
                    continue  # The app's linked reference is a utility document, shared with Pages.
                for key in ("description", "og:title", "og:description", "og:url", "twitter:title",
                            "twitter:description", "twitter:card"):
                    self.assertEqual(len(head.meta.get(key, [])), 1, f"{relative}: one {key}")
                    self.assertTrue(head.meta[key][0].strip(), f"{relative}: nonempty {key}")
                self.assertEqual(head.meta["og:url"], [canonical])
                image_keys = ("og:image", "og:image:width", "og:image:height", "og:image:alt",
                              "twitter:image", "twitter:image:alt")
                image = None
                if "og:image" in head.meta:
                    for key in image_keys:
                        self.assertEqual(len(head.meta.get(key, [])), 1, f"{relative}: one {key}")
                        self.assertTrue(head.meta[key][0].strip(), f"{relative}: nonempty {key}")
                    self.assertEqual(head.meta["twitter:card"], ["summary_large_image"])
                    image = head.meta["og:image"][0]
                    self.assertTrue(image.startswith(SITE), f"{relative}: hosted preview image")
                    self.assertEqual(head.meta["twitter:image"], [image])
                    image_bytes = (output / image.removeprefix(SITE)).read_bytes()
                    self.assertEqual(image_bytes[:8], b"\x89PNG\r\n\x1a\n")
                    self.assertEqual(
                        (int(head.meta["og:image:width"][0]), int(head.meta["og:image:height"][0])),
                        struct.unpack(">II", image_bytes[16:24]), f"{relative}: preview dimensions",
                    )
                else:
                    self.assertEqual(head.meta["twitter:card"], ["summary"])
                    for key in image_keys:
                        self.assertNotIn(key, head.meta, f"{relative}: no orphaned image metadata")
                expected = {
                    "index.html": "SoftwareApplication",
                    "blog/index.html": "Blog",
                }.get(relative, "TechArticle")
                if relative.startswith("index-") and relative.endswith(".html"):
                    expected = "SoftwareApplication"
                entities = [item for item in head.structured
                            if expected in ([item.get("@type")] if isinstance(item.get("@type"), str) else item.get("@type", []))]
                self.assertEqual(len(entities), 1, f"{relative}: one primary {expected}")
                entity = entities[0]
                self.assertEqual(entity["@context"], "https://schema.org")
                self.assertEqual(entity["url"], canonical)
                self.assertTrue(entity.get("headline") or entity.get("name"))
                if expected == "TechArticle":
                    self.assertEqual(entity["mainEntityOfPage"], canonical)
                    if image:
                        self.assertEqual(entity["image"]["url"], image)
                        self.assertEqual((entity["image"]["width"], entity["image"]["height"]),
                                         struct.unpack(">II", image_bytes[16:24]))
                    else:
                        self.assertNotIn("image", entity)
                modified = entity.get("dateModified")
                if modified:
                    self.assertEqual(sitemap[canonical], modified)
                    self.assertLessEqual(date.fromisoformat(modified), datetime.now(timezone.utc).date())
                if entity.get("datePublished"):
                    self.assertLessEqual(date.fromisoformat(entity["datePublished"]), date.fromisoformat(modified))
                self.assertLessEqual(date.fromisoformat(sitemap[canonical]), datetime.now(timezone.utc).date())
                if relative.startswith(("guides/", "blog/")):
                    alternates = [link["href"] for link in head.links
                                  if link.get("rel") == "alternate" and link.get("type") == "text/markdown"]
                    self.assertEqual(alternates, [page.name + ".md"])
                    self.assertTrue((page.parent / alternates[0]).is_file())
                    self.assertEqual(urljoin(canonical, alternates[0]), canonical + ".md")


class TestPublicAnalyticsBoundary(unittest.TestCase):
    def test_pages_publishes_reviewed_config_without_other_json_assets(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "docs"
            assets = source / "assets"
            assets.mkdir(parents=True)
            content = '{"site_code": "synthetic-site"}\n'
            (assets / "analytics.json").write_text(content, encoding="utf-8")
            (assets / "unreviewed.json").write_text('{"synthetic": true}', encoding="utf-8")
            output = Path(directory) / "public"
            stage(source, output)
            self.assertEqual((output / "assets" / "analytics.json").read_text(encoding="utf-8"), content)
            self.assertFalse((output / "assets" / "unreviewed.json").exists())

    def test_public_example_head_loads_analytics_without_instrumenting_exports(self):
        from lixity import api
        from scripts.example_publications import _head_metadata

        head = _head_metadata(canonical=SITE + "demo/report.html", title="Synthetic demo",
                              description="Synthetic public example", language="en")
        self.assertIn('<script defer src="../assets/analytics.js"></script>', head)
        local = api.dashboard("## Sample\n\nA synthetic reader opens a door.")
        self.assertNotIn("analytics.js", local)
        self.assertNotIn("goatcounter", local)

    def test_demo_counter_policy_uses_validated_public_configuration(self):
        from scripts.example_publications import _analytics_endpoint

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            assets = root / "docs" / "assets"
            assets.mkdir(parents=True)
            config = assets / "analytics.json"
            self.assertIsNone(_analytics_endpoint(root))
            config.write_text('{"site_code": "mfahsold"}', encoding="utf-8")
            self.assertEqual(_analytics_endpoint(root), "https://mfahsold.goatcounter.com/count")
            config.write_text('{"site_code": null}', encoding="utf-8")
            self.assertIsNone(_analytics_endpoint(root))
            for value in (False, 42, "../other", "x;script-src *", "UPPER", "", "-start", "end-"):
                with self.subTest(value=value):
                    config.write_text(json.dumps({"site_code": value}), encoding="utf-8")
                    with self.assertRaises(ValueError):
                        _analytics_endpoint(root)


class TestPublicLanguages(unittest.TestCase):
    def test_home_image_dimensions_follow_regenerated_screenshots_in_every_language(self):
        from unittest.mock import patch

        from scripts.build_public_site import LANGUAGES, ROOT, render_pages

        class Images(HTMLParser):
            def __init__(self):
                super().__init__()
                self.dimensions = {}

            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "img" and values.get("src", "").startswith("screenshots/"):
                    self.dimensions[values["src"]] = (int(values["width"]), int(values["height"]))

        expected = {
            "dashboard-reader-focus.png": (191, 109),
            "dashboard-heatmap.png": (173, 83),
            "dashboard-research-dossiers.png": (157, 211),
            "dashboard-editorial.png": (223, 71),
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for relative in ("docs/templates/home.html.template", "docs/templates/home-footer.html.template",
                             "docs/videos/product-tour-timing.json",
                             *(f"docs/locales/{language}.json" for language in LANGUAGES)):
                target = root / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((ROOT / relative).read_bytes())
            version = root / "src/lixity/_version.py"
            version.parent.mkdir(parents=True)
            version.write_text('__version__ = "0.0.0"\n', encoding="utf-8")
            shots = root / "docs/screenshots"
            shots.mkdir()
            # This generator reads PNG headers; decoding is covered by browser checks.
            for name, dimensions in {"dashboard-light.png": (311, 127), **expected}.items():
                (shots / name).write_bytes(b"\x89PNG\r\n\x1a\n" + bytes(8) + struct.pack(">II", *dimensions))
            with patch("scripts.build_public_site.ROOT", root):
                pages = render_pages()
        self.assertEqual(len(pages), 7)
        for name, text in pages.items():
            with self.subTest(page=name):
                images = Images()
                images.feed(text)
                self.assertEqual(images.dimensions, {"screenshots/" + key: value for key, value in expected.items()})
                head = PageHead()
                head.feed(text)
                self.assertEqual(head.meta["og:image:width"], ["311"])
                self.assertEqual(head.meta["og:image:height"], ["127"])

    def test_home_tour_has_localized_transcript_and_explicit_playback(self):
        from scripts.build_public_site import LANGUAGES, ROOT, page_path, render_pages

        timing = json.loads((ROOT / "docs/videos/product-tour-timing.json").read_text())

        pages = render_pages()
        for language in LANGUAGES:
            with self.subTest(language=language):
                content = json.loads((ROOT / f"docs/locales/{language}.json").read_text())
                text = pages[page_path(language)]
                self.assertIn('src="videos/product-tour.mp4"', text)
                self.assertIn('preload="none"', text)
                self.assertIn('muted playsinline controls', text)
                self.assertNotIn(' autoplay', text)
                self.assertIn('id="tour-transcript"', text)
                for media in ("videos/social-hook-9x16.mp4", "videos/social-hook-16x9.mp4",
                              "screenshots/dashboard-measurement-focus.png"):
                    self.assertIn(f'href="{media}" hreflang="en" download', text)
                for scene in timing["scenes"]:
                    self.assertIn(html.escape(content['tour_' + scene['id']], quote=True), text)
                self.assertIn('href="demo/warehouse-4-dossier.pdf"', text)

    def test_analysis_links_open_the_passage_guide_and_localized_methods(self):
        from scripts.build_public_site import LANGUAGES, ROOT, page_path, render_pages

        pages = render_pages()
        for language in LANGUAGES:
            with self.subTest(language=language):
                guide_lang, guide_path, fragment = (
                    ("de", "guides/first-look-de.html", "beleg") if language == "de"
                    else ("en", "guides/first-look.html", "passage")
                )
                content = json.loads((ROOT / f"docs/locales/{language}.json").read_text(encoding="utf-8"))
                rendered = pages[page_path(language)]
                self.assertIn(
                    f'href="{guide_path}#{fragment}" hreflang="{guide_lang}">'
                    f'{html.escape(content["passage_guide_link"], quote=True)}</a>', rendered,
                )
                self.assertIn(f'href="guides/metrics/{language}.html" hreflang="{language}"', rendered)
                self.assertIn(f'id="{fragment}"', (ROOT / "docs" / guide_path).read_text(encoding="utf-8"))

    def test_generated_languages_are_complete_and_reciprocal(self):
        from scripts.build_public_site import (
            LANGUAGES,
            OG_LOCALES,
            ROOT,
            page_path,
            page_url,
            render_pages,
        )

        pages = render_pages()
        for language in LANGUAGES:
            with self.subTest(language=language):
                text = pages[page_path(language)]
                self.assertEqual((ROOT / 'docs' / page_path(language)).read_text(encoding='utf-8'), text)
                self.assertIn(f'<html lang="{language}"', text)
                head = PageHead()
                head.feed(text)
                alternates = {item['hreflang']: item['href'] for item in head.links
                              if 'hreflang' in item}
                self.assertEqual(alternates, {**{code: page_url(code) for code in LANGUAGES},
                                              'x-default': SITE})
                self.assertEqual(head.meta["og:locale"], [OG_LOCALES[language]])
                self.assertCountEqual(head.meta["og:locale:alternate"],
                                      [locale for code, locale in OG_LOCALES.items() if code != language])
                self.assertEqual(head.meta["robots"], ["max-image-preview:large"])
                self.assertIn(f'href="{page_url(language)}"', text)
                self.assertIn('href="demo/report.html" hreflang="en"', text)
                sandbox_language = "de" if language == "de" else "en"
                self.assertIn(f'href="sandbox/index.html?lang={sandbox_language}" hreflang="{sandbox_language}"', text)
                content = json.loads((ROOT / f"docs/locales/{language}.json").read_text(encoding="utf-8"))
                for key in ("read_alt", "linguistics_alt", "research_alt", "share_alt"):
                    self.assertIn(f'alt="{html.escape(content[key], quote=True)}"', text)
                self.assertIn('href="guides/installation.html"', text)

    def test_missing_translation_fails_instead_of_falling_back(self):
        from unittest.mock import patch

        from scripts.build_public_site import render_pages

        original = json.loads

        def missing_key(value):
            content = original(value)
            if content.get('language') == 'Sprache':
                del content['intro']
            return content

        with (patch('scripts.build_public_site.json.loads', side_effect=missing_key),
              self.assertRaisesRegex(ValueError, 'Incomplete public translation: de')):
            render_pages()
