"""Unit tests for offline article extraction (Defuddle style) in research intake."""

from lixity.research.article_extract import extract_article

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <title>Speicherstadt Architecture in 1900</title>
    <meta name="author" content="E. Meyer">
    <meta property="article:published_time" content="2026-03-15T10:00:00Z">
    <meta property="og:site_name" content="Hamburg Archives">
    <meta name="description" content="A comprehensive review of the neo-gothic brick warehouse complex.">
    <link rel="canonical" href="https://example.org/speicherstadt">
</head>
<body>
    <header class="site-header">
        <nav><a href="/">Home</a><a href="/about">About</a></nav>
    </header>
    <aside class="sidebar ad-widget">
        <p>Advertisement</p>
    </aside>
    <main>
        <h1>Speicherstadt Architecture in 1900</h1>
        <p class="byline">By E. Meyer</p>
        <p>The <strong>Speicherstadt</strong> was built between 1883 and 1927 as a free zone.
        It features <em>distinctive</em> red-brick architecture.</p>

        <h2>Key Districts</h2>
        <ul>
            <li>Block A to D: Early phases</li>
            <li>Block E to G: Canal bridges</li>
        </ul>

        <blockquote>
            The warehouses allowed duty-free storage of goods like coffee and tea.
        </blockquote>

        <h2>Specifications</h2>
        <table>
            <tr><th>Block</th><th>Completed</th></tr>
            <tr><td>Block A</td><td>1888</td></tr>
            <tr><td>Block B</td><td>1892</td></tr>
        </table>

        <pre><code class="language-text">Warehouse elevation: 5 stories above water level.</code></pre>
    </main>
    <footer class="footer">
        <p>&copy; 2026 Hamburg Archives. All rights reserved.</p>
    </footer>
    <script>console.log("analytics tracking");</script>
</body>
</html>
"""


def test_article_metadata_extraction():
    doc = extract_article(SAMPLE_HTML, origin_url="https://example.org/speicherstadt")
    assert doc.title == "Speicherstadt Architecture in 1900"
    assert doc.byline == "E. Meyer"
    assert doc.published_time == "2026-03-15T10:00:00Z"
    assert doc.site_name == "Hamburg Archives"
    assert doc.canonical_url == "https://example.org/speicherstadt"
    assert doc.word_count > 30


def test_article_content_clean_markdown():
    doc = extract_article(SAMPLE_HTML)
    md = doc.markdown
    # Structural elements present
    assert "# Speicherstadt Architecture in 1900" in md
    assert "**Speicherstadt**" in md
    assert "*distinctive*" in md
    assert "## Key Districts" in md
    assert "- Block A to D: Early phases" in md
    assert "> The warehouses allowed duty-free storage" in md
    assert "| Block | Completed |" in md
    assert "| Block A | 1888 |" in md
    assert "```\nWarehouse elevation: 5 stories above water level.\n```" in md

    # Noise elements stripped
    assert "Advertisement" not in md
    assert "analytics tracking" not in md
    assert "All rights reserved" not in md


def test_to_research_markdown_header():
    doc = extract_article(SAMPLE_HTML, origin_url="https://example.org/speicherstadt")
    output = doc.to_research_markdown()
    assert "<!-- lixity-research-article/1" in output
    assert "title: Speicherstadt Architecture in 1900" in output
    assert "author: E. Meyer" in output
    assert "extractor: lixity-defuddle/1" in output
    assert "origin_url: https://example.org/speicherstadt" in output
