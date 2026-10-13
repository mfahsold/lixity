"""The guide Markdown alternates stay generated from their HTML sources."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "docs" / "guides"
sys.path.insert(0, str(ROOT / "scripts"))

from build_guide_markdown import guide_markdown  # noqa: E402


def test_guide_markdown_alternates_match_their_pages() -> None:
    pages = sorted(GUIDES.glob("*.html"))
    assert pages, "guide pages"
    for page in pages:
        target = page.with_suffix(page.suffix + ".md")
        assert target.is_file(), f"missing Markdown alternate for {page.name}"
        assert target.read_text(encoding="utf-8") == guide_markdown(page), (
            f"{target.name} is outdated; run 'python scripts/build_guide_markdown.py'"
        )


def test_every_guide_links_its_markdown_alternate() -> None:
    for page in sorted(GUIDES.glob("*.html")):
        text = page.read_text(encoding="utf-8")
        match = re.search(r'rel="alternate" type="text/markdown" href="([^"]+)"', text)
        assert match, f"{page.name} does not link a Markdown alternate"
        assert match.group(1) == page.name + ".md"
        assert (GUIDES / match.group(1)).is_file()
