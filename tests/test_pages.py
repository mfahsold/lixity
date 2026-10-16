"""Public Pages staging excludes local planning and private working material."""

import json
import tempfile
import unittest
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

from scripts.stage_pages import stage


class TestPagesStaging(unittest.TestCase):
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
                      "research/USAGE.md", "research/examples/synthetic-source.txt",
                      "screenshots/public.png", "sitemap.xml", ".nojekyll",
                      "examples/novel.html", "examples/novel-report.pdf")
            private = ("superpowers/plans/task.md", "archive/wave2-plan.md", "notes.md",
                       "GROWTH_REVIEW.md", "SECURITY_REVIEW.md",
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
            self.assertEqual(
                published,
                set(public) | {"assets/design-tokens.css", "assets/components.css", "sitemap-alt.xml"},
            )
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
        import re as _re

        docs = Path(__file__).resolve().parents[1] / "docs"
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "site"
            stage(docs, output)
            pages = sorted(output.rglob("*.html"))
            self.assertTrue(pages, "Staged pages expected")
            for page in pages:
                text = page.read_text(encoding="utf-8")
                relative = page.relative_to(output).as_posix()
                for pattern, label in (
                    (r'<meta name="description" content="[^"]+"/>', "description"),
                    (r'<link rel="canonical" href="https://[^"]+"/>', "canonical"),
                    (r'<meta property="og:title" content="[^"]+"/>', "og:title"),
                    (r'<meta property="og:description" content="[^"]+"/>', "og:description"),
                    (r'<meta property="og:url" content="https://[^"]+"/>', "og:url"),
                    (r'<meta property="og:image" content="https://[^"]+"/>', "og:image"),
                    (r'<meta name="twitter:card" content="summary_large_image"/>', "twitter:card"),
                    (r'<meta name="twitter:image" content="https://[^"]+"/>', "twitter:image"),
                ):
                    self.assertRegex(text, pattern, f"{relative}: {label}")
                blocks = _re.findall(
                    r'<script type="application/ld\+json">\s*(\{.*?\})\s*</script>', text, _re.DOTALL
                )
                self.assertTrue(blocks, f"{relative}: JSON-LD")
                types = [json.loads(block).get("@type") for block in blocks]
                # The site root presents the software; the blog index is a
                # collection and every guide or article page is an article.
                expected = {
                    "index.html": "SoftwareApplication",
                    "blog/index.html": "Blog",
                }.get(relative, "TechArticle")
                self.assertTrue(
                    any(
                        expected == item or (isinstance(item, list) and expected in item)
                        for item in types
                    ),
                    f"{relative}: JSON-LD {expected}",
                )
            sitemap_text = (output / "sitemap.xml").read_text(encoding="utf-8")
            self.assertNotRegex(sitemap_text, r"<lastmod>(?!\d{4}-\d{2}-\d{2})")
