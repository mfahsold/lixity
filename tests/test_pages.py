"""Public Pages staging excludes local planning and private working material."""

import hashlib
import json
import struct
import tempfile
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime, timezone
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from scripts.stage_pages import stage

SITE = "https://mfahsold.github.io/lixity/"


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
            self.assertIn("nicht als klassischer Desktop-Installer", german)
            self.assertTrue((output / "guides/first-look-de.html.md").is_file())

    def test_compact_demo_navigation_keeps_orientation_without_repeating_the_title(self):
        from scripts.build_examples import _site_navigation

        document = (
            '<html><head></head><body id="top" class="lixity-workspace">'
            '<div class="page"><h1>Fictional manuscript</h1></div></body></html>'
        )
        compact = _site_navigation(document, "Fictional manuscript", demo=True, breadcrumbs=False)
        self.assertNotIn('<nav class="site-breadcrumbs"', compact)
        self.assertIn('<a href="../">About Lixity</a>', compact)
        self.assertIn('Read-only demo · Fictional manuscript', compact)
        self.assertNotIn('href="../demo/report.html"', compact)
        self.assertIn('<h1>Fictional manuscript</h1>', compact)
        ordinary = _site_navigation(document, "Fictional manuscript", demo=True)
        self.assertNotIn('<nav class="site-breadcrumbs"', ordinary)

    def test_public_navigation_preserves_workspace_and_report_classes(self):
        from scripts.build_examples import _insert_notice, _site_navigation

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
        from scripts.build_examples import _replace_title

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
        class Canonicals(HTMLParser):
            def handle_starttag(self, tag, attrs):
                values = dict(attrs)
                if tag == "link" and values.get("rel") == "canonical":
                    canonical_urls.append(values["href"])

        docs = Path(__file__).resolve().parents[1] / "docs"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            stage(docs, output)
            canonical_urls = []
            for page in output.rglob("*.html"):
                if page.relative_to(output).as_posix() == "demo/research.html":
                    continue  # The tested compatibility redirect shares the report's canonical.
                Canonicals().feed(page.read_text(encoding="utf-8"))
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
            public = ("index.html", "USAGE.md", "guides/install.html", "assets/site.css",
                      "blog/article.html", "blog/article.html.md",
                      "assets/research/hamburg-free-port-1900.jpg",
                      "assets/research/hamburg-harbour-1890-1900.jpg", "assets/research/sources.json",
                      "demo/report.html", "demo/research.html",
                      "demo/warehouse-4-editor.pdf", "demo/warehouse-4-book.pdf",
                      "demo/warehouse-4-sheet.pdf", "demo/warehouse-4-report.pdf",
                      "demo/warehouse-4-document.pdf",
                      "research/USAGE.md", "research/examples/synthetic-source.txt",
                      "screenshots/public.png", "sitemap.xml", ".nojekyll",
                      "examples/novel.html", "examples/novel-report.pdf")
            private = ("superpowers/plans/task.md", "archive/wave2-plan.md", "notes.md",
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
        docs = Path(__file__).resolve().parents[1] / "docs"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            stage(docs, output)
            pages = sorted(output.rglob("*.html"))
            self.assertTrue(pages, "Staged pages expected")
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
        from scripts.build_examples import _head_metadata

        head = _head_metadata(canonical=SITE + "demo/report.html", title="Synthetic demo",
                              description="Synthetic public example", language="en")
        self.assertIn('<script defer src="../assets/analytics.js"></script>', head)
        local = api.dashboard("## Sample\n\nA synthetic reader opens a door.")
        self.assertNotIn("analytics.js", local)
        self.assertNotIn("goatcounter", local)

    def test_demo_counter_policy_uses_validated_public_configuration(self):
        from scripts.build_examples import _analytics_endpoint

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
