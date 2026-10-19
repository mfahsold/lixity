"""Public Pages staging excludes local planning and private working material."""

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
                      "demo/report.html", "demo/research.html", "demo/research-data.json",
                      "demo/warehouse-4-editor.pdf", "demo/warehouse-4-book.pdf",
                      "demo/warehouse-4-sheet.pdf", "demo/warehouse-4-report.pdf",
                      "research/USAGE.md", "research/examples/synthetic-source.txt",
                      "screenshots/public.png", "sitemap.xml", ".nojekyll",
                      "examples/novel.html", "examples/novel-report.pdf")
            private = ("superpowers/plans/task.md", "archive/wave2-plan.md", "notes.md",
                       "GROWTH_REVIEW.md", "SECURITY_REVIEW.md",
                       ".planning/secret.md", "research/.scratch/session.md",
                       "screenshots/local.log", "private/source.txt")
            private += ("blog/session-notes.md",)
            private += ("assets/research/unreviewed.jpg", "demo/local-source.json",)
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
