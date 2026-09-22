#!/usr/bin/env python3
"""
scripts/make_screenshots.py
===========================
Regenerates the README/GitHub-Pages screenshots reproducibly.

Requires Chromium (headless) and the repository's own sample manuscript.

Usage:
    python3 scripts/make_screenshots.py
    python3 scripts/make_screenshots.py --manuscript samples/effi-briest.md
"""

import argparse
import html
import io
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from rich.console import Console  # noqa: E402

from lixity import CorpusAnalyzer, CorpusConfig, ReportFormatter  # noqa: E402
from lixity.characters import presence_report  # noqa: E402
from lixity.dialogue import dialogue_report  # noqa: E402
from lixity.language import resolve_language  # noqa: E402
from lixity.markdown_parser import parse_markdown_blocks  # noqa: E402
from lixity.markers import add_marker  # noqa: E402
from lixity.style_fingerprint import StyleFingerprint  # noqa: E402
from lixity.style_profile import ParagraphProfiler  # noqa: E402
from lixity.ui import render_dashboard  # noqa: E402

CHROME = (
    shutil.which("chromium")
    or shutil.which("chromium-browser")
    or shutil.which("google-chrome")
    or shutil.which("chrome")
)
WORK_DIR = BASE_DIR / ".screenshots"
OUT_DIR = BASE_DIR / "docs" / "screenshots"

WINDOW_CHROME = """<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; padding: 28px; background: #0b0d10; font-family: {font}; }}
  .win {{ max-width: 1240px; margin: 0 auto; border-radius: 10px; overflow: hidden;
          box-shadow: 0 18px 48px rgba(0,0,0,.55); background: #16181d; }}
  .bar {{ display: flex; align-items: center; gap: 8px; padding: 11px 16px; background: #21242b; }}
  .dot {{ width: 12px; height: 12px; border-radius: 50%; }}
  .red {{ background: #ff5f57; }} .yellow {{ background: #febc2e; }} .green {{ background: #28c840; }}
  .title {{ flex: 1; text-align: center; color: #b9bec7; font-size: 13px; letter-spacing: .01em; }}
  .body {{ padding: 18px 22px 24px; }}
  pre {{ margin: 0; font-family: "SF Mono", "JetBrains Mono", Menlo, Consolas, monospace;
         font-size: 13.5px; line-height: 1.42; color: #e6e6e6; white-space: pre; }}
</style></head><body>
  <div class="win">
    <div class="bar"><span class="dot red"></span><span class="dot yellow"></span>
      <span class="dot green"></span><span class="title">{title}</span></div>
    <div class="body">{content}</div>
  </div>
</body></html>
"""


def _run_chrome(source: Path, target: Path, width: int, height: int) -> None:
    if CHROME is None:
        raise SystemExit("Chromium not found – cannot render screenshots.")
    cmd = [
        CHROME,
        "--headless=new",
        "--disable-gpu",
        "--hide-scrollbars",
        f"--window-size={width},{height}",
        "--virtual-time-budget=2500",
        f"--screenshot={target}",
        source.as_uri(),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=120)  # noqa: S603
    print(f"  {target.relative_to(BASE_DIR)} ({width}x{height})")


def _write_html(name: str, document: str) -> Path:
    path = WORK_DIR / name
    path.write_text(document, encoding="utf-8")
    return path


def _terminal_shot(title: str, content_html: str, target: Path, width: int, height: int) -> None:
    document = WINDOW_CHROME.format(
        font="system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
        title=html.escape(title),
        content=content_html,
    )
    _run_chrome(_write_html(target.stem + ".html", document), target, width, height)


def _extract_section(dashboard: str, marker: str) -> str:
    style_match = re.search(r"<style>(.*?)</style>", dashboard, re.DOTALL)
    lang_match = re.search(r'<html lang="([^"]*)"', dashboard)
    if style_match is None or lang_match is None:
        raise SystemExit("Dashboard markup incomplete – cannot extract section.")
    style = style_match.group(1)
    lang = lang_match.group(1)
    for match in re.finditer(r'<section class="panel"[^>]*>.*?</section>', dashboard, re.DOTALL):
        if marker in match.group(0):
            return (
                "<!DOCTYPE html>"
                f'<html lang="{lang}"><head><meta charset="utf-8"/><style>{style}</style></head>'
                f'<body><div class="page">{match.group(0)}</div></body></html>'
            )
    raise SystemExit(f"Section not found: {marker}")


def _force_dark(dashboard: str) -> str:
    return dashboard.replace("@media (prefers-color-scheme: dark) {", "@media all {")


def _force_light(dashboard: str) -> str:
    return dashboard.replace("@media (prefers-color-scheme: dark) {", "@media not all {")


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate README screenshots.")
    parser.add_argument("--manuscript", default="samples/effi-briest.md")
    args = parser.parse_args()

    manuscript = (BASE_DIR / args.manuscript).resolve()
    text = manuscript.read_text(encoding="utf-8")
    config = CorpusConfig(language="auto")
    resolved = resolve_language(config, sample_text=text)
    config = CorpusConfig(language=resolved.key)
    title = manuscript.stem

    metrics = CorpusAnalyzer(config).analyze_text(text)
    paragraphs, chapters = ParagraphProfiler(config).profile_blocks(parse_markdown_blocks(text))
    fingerprint = StyleFingerprint.from_metrics(metrics)

    WORK_DIR.mkdir(exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Screenshots from {manuscript.relative_to(BASE_DIR)} ({resolved.key})")

    # 1. CLI: rich corpus report -----------------------------------------
    console = Console(
        record=True,
        width=112,
        force_terminal=True,
        color_system="truecolor",
        file=io.StringIO(),
    )
    ReportFormatter.print_rich_report(metrics, console=console, texts=resolved.labels)
    _terminal_shot(
        f"lixity analyze {args.manuscript}",
        console.export_html(inline_styles=True),
        OUT_DIR / "cli-analyze.png",
        1560,
        1030,
    )

    # 2. CLI: style passport ----------------------------------------------
    passport = html.escape(fingerprint.passport_text(labels=resolved.labels))
    _terminal_shot(
        f"lixity style {args.manuscript}",
        f"<pre>{passport}</pre>",
        OUT_DIR / "cli-style.png",
        1560,
        1030,
    )

    # 3. Dashboard (light, top area) --------------------------------------
    status = [
        {"key": "manuscript", "state": "ok", "detail": f"{title}.md"},
        {
            "key": "analysis",
            "state": "ok",
            "detail": f"{len(chapters)} Kapitel · {len(paragraphs)} Absätze",
        },
        {"key": "dossiers", "state": "ok", "detail": "aktuell"},
        {"key": "exports", "state": "warn", "detail": "keine erzeugt"},
        {"key": "nda", "state": "unknown", "detail": "kein Speicher"},
        {"key": "markers", "state": "ok", "detail": "keine offenen"},
    ]
    dashboard = render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        status=status,
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, ["Effi", "Innstetten", "Crampas", "Briest"], config),
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
    )
    dashboard_path = _write_html("dashboard.html", _force_light(dashboard))
    _run_chrome(dashboard_path, OUT_DIR / "dashboard-light.png", 1600, 2100)

    # 4. Dashboard (dark) --------------------------------------------------
    _run_chrome(
        _write_html("dashboard-dark.html", _force_dark(dashboard)),
        OUT_DIR / "dashboard-dark.png",
        1600,
        2100,
    )

    # 5. Dashboard sections ------------------------------------------------
    _run_chrome(
        _write_html(
            "section-heatmap.html", _extract_section(_force_light(dashboard), "heatmap-wrap")
        ),
        OUT_DIR / "dashboard-heatmap.png",
        1600,
        1500,
    )
    _run_chrome(
        _write_html(
            "section-dimensions.html", _extract_section(_force_light(dashboard), "dim-card")
        ),
        OUT_DIR / "dashboard-dimensions.png",
        1600,
        560,
    )

    # 6. Work markers (temporary copy with three editorial markers) --------
    marked = text
    for line, kind, note in (
        (7, "pruefen", "Tempuswechsel im Dialog prüfen"),
        (61, "sachcheck", "Chronologie: Effis Sterbejahr"),
        (85, "todo", "Kapitelende kürzen?"),
    ):
        marked, _ = add_marker(marked, kind=kind, note=note, target_line=line)
    marked_metrics = CorpusAnalyzer(config).analyze_text(marked)
    marked_paragraphs, marked_chapters = ParagraphProfiler(config).profile_blocks(
        parse_markdown_blocks(marked)
    )
    from lixity.markers import list_markers

    marked_dashboard = render_dashboard(
        marked_chapters,
        marked_paragraphs,
        metrics=marked_metrics,
        fingerprint=StyleFingerprint.from_metrics(marked_metrics),
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        markers=list_markers(marked),
    )
    _run_chrome(
        _write_html(
            "section-markers.html", _extract_section(_force_light(marked_dashboard), "marker")
        ),
        OUT_DIR / "dashboard-markers.png",
        1600,
        330,
    )

    # 7. Style layer (draft chapter with the dialogue layer active) --------
    layer_manuscript = BASE_DIR / "samples" / "effi-briest-folge" / "effi-briest-folge.md"
    if layer_manuscript.is_file():
        layer_text = layer_manuscript.read_text(encoding="utf-8")
        layer_resolved = resolve_language(CorpusConfig(language="auto"), sample_text=layer_text)
        layer_config = CorpusConfig(language=layer_resolved.key)
        layer_metrics = CorpusAnalyzer(layer_config).analyze_text(layer_text)
        layer_paragraphs, layer_chapters = ParagraphProfiler(layer_config).profile_blocks(
            parse_markdown_blocks(layer_text)
        )
        layer_dashboard = render_dashboard(
            layer_chapters,
            layer_paragraphs,
            metrics=layer_metrics,
            fingerprint=StyleFingerprint.from_metrics(layer_metrics),
            title="Annie – Erstes Kapitel",
            labels=layer_resolved.labels,
            language_name=layer_resolved.name,
            language_key=layer_resolved.key,
        ).replace('<option value="dialogue"', '<option value="dialogue" selected', 1)
        _run_chrome(
            _write_html("dashboard-layer.html", _force_light(layer_dashboard)),
            OUT_DIR / "dashboard-layer.png",
            1600,
            1500,
        )

    print(
        f"Done – {len(list(OUT_DIR.glob('*.png')))} screenshots in {OUT_DIR.relative_to(BASE_DIR)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
