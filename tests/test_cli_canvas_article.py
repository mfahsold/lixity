"""CLI integration tests for JSON Canvas and Defuddle article extraction."""

import json
import subprocess
import sys
from pathlib import Path


def test_cli_canvas_narrative(tmp_path: Path):
    manuscript = tmp_path / "novel.md"
    manuscript.write_text("# Chapter 1\n\nFirst scene arrival.\n\n# Chapter 2\n\nSecond scene action.\n", encoding="utf-8")
    out_canvas = tmp_path / "story.canvas"

    cmd = [
        sys.executable, "-m", "lixity", "canvas", str(manuscript),
        "-o", str(out_canvas),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
    assert res.returncode == 0
    assert out_canvas.is_file()

    canvas_data = json.loads(out_canvas.read_text(encoding="utf-8"))
    assert "nodes" in canvas_data
    assert "edges" in canvas_data
    assert len(canvas_data["nodes"]) >= 2


def test_cli_extract_article(tmp_path: Path):
    html_file = tmp_path / "article.html"
    html_file.write_text("""<!DOCTYPE html>
<html>
<head><title>Harbour Report 1900</title><meta name="author" content="Historian A"></head>
<body>
<nav>Menu</nav>
<main><h1>Harbour Report</h1><p>Detailed analysis of docks.</p></main>
</body></html>""", encoding="utf-8")
    out_md = tmp_path / "article.md"

    cmd = [
        sys.executable, "-m", "lixity", "research", "extract-article", str(html_file),
        "--url", "https://example.org/harbour",
        "-o", str(out_md),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, check=True)  # noqa: S603
    assert res.returncode == 0
    assert out_md.is_file()

    md_content = out_md.read_text(encoding="utf-8")
    assert "Harbour Report 1900" in md_content
    assert "Historian A" in md_content
    assert "Detailed analysis of docks." in md_content
    assert "extractor: lixity-defuddle/1" in md_content
    assert "Menu" not in md_content
