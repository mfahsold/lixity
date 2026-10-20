"""Guide and blog Markdown alternates stay generated from their HTML sources."""

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GUIDES = ROOT / "docs" / "guides"
BLOG = ROOT / "docs" / "blog"
sys.path.insert(0, str(ROOT / "scripts"))

from build_guide_markdown import guide_markdown  # noqa: E402


def test_markdown_alternates_match_their_pages() -> None:
    pages = sorted([*GUIDES.glob("*.html"), *BLOG.glob("*.html")])
    assert pages, "guide and blog pages"
    for page in pages:
        target = page.with_suffix(page.suffix + ".md")
        assert target.is_file(), f"missing Markdown alternate for {page.name}"
        assert target.read_text(encoding="utf-8") == guide_markdown(page), (
            f"{target.name} is outdated; run 'python scripts/build_guide_markdown.py'"
        )


def test_every_page_links_its_markdown_alternate() -> None:
    for page in sorted([*GUIDES.glob("*.html"), *BLOG.glob("*.html")]):
        text = page.read_text(encoding="utf-8")
        match = re.search(r'rel="alternate" type="text/markdown" href="([^"]+)"', text)
        assert match, f"{page.name} does not link a Markdown alternate"
        assert match.group(1) == page.name + ".md"
        assert (page.parent / match.group(1)).is_file()


def test_article_markdown_preserves_table_sections_and_figure_images(tmp_path) -> None:
    page = tmp_path / "article.html"
    page.write_text('''<main><h1>Public example</h1>
<table><thead><tr><th>Tool</th><th>Evidence</th></tr></thead>
<tbody><tr><td>Local analysis</td><td>Chapter comparison</td></tr></tbody></table>
<figure><a href="full.png"><img src="preview.png" alt="Synthetic chapter map"/></a>
<figcaption>Review the source passage.</figcaption></figure></main>''', encoding="utf-8")
    rendered = guide_markdown(page)
    assert "| Tool | Evidence |\n| --- | --- |\n| Local analysis | Chapter comparison |" in rendered
    assert "![Synthetic chapter map](preview.png)" in rendered
    assert "Review the source passage." in rendered


def test_details_markdown_preserves_paragraphs_and_code_blocks(tmp_path) -> None:
    page = tmp_path / "details.html"
    page.write_text('''<main><details>
<summary>Verify <em>release</em> files</summary>
<p>Check <code>SHA256SUMS</code>, then read the <a href="checks.html">guide</a>
and <strong>verify</strong> the download.</p>
<pre><code>echo "verify"
  sha256sum --check SHA256SUMS</code></pre>
<div><p>Grouped <code>instructions</code> stay together.</p>
<details><summary>More checks</summary><p>Run the <strong>extra</strong> check.</p>
<pre><code>echo "extra"</code></pre></details></div>
</details></main>''', encoding="utf-8")

    assert guide_markdown(page) == '''**Verify *release* files**

Check `SHA256SUMS`, then read the [guide](checks.html) and **verify** the download.

```
echo "verify"
  sha256sum --check SHA256SUMS
```

Grouped `instructions` stay together.

**More checks**

Run the **extra** check.

```
echo "extra"
```
'''
