#!/usr/bin/env python3
"""
scripts/make_screenshots.py
===========================
Regenerates the README/GitHub-Pages screenshots reproducibly.

Requires Node.js, Playwright with Chromium, and the public sample manuscript.
Set PLAYWRIGHT_MODULE when Playwright is installed outside the repository.

Usage:
    python3 scripts/make_screenshots.py
    python3 scripts/make_screenshots.py --manuscript samples/effi-briest.md
"""

import argparse
import html
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from rich.console import Console  # noqa: E402

from lixity import ReportFormatter  # noqa: E402
from lixity.characters import presence_report  # noqa: E402
from lixity.config import resolve_thresholds  # noqa: E402
from lixity.dialogue import dialogue_report  # noqa: E402
from lixity.markers import add_marker  # noqa: E402
from lixity.motifs import motif_report  # noqa: E402
from lixity.pacing import pacing_report  # noqa: E402
from lixity.pipeline import analyze_document, resolve_document_config  # noqa: E402
from lixity.showing import showing_report  # noqa: E402
from lixity.ui import render_dashboard  # noqa: E402

CAPTURES: list[dict[str, str | int]] = []
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


def _queue_capture(source: Path, target: Path, width: int, height: int) -> None:
    CAPTURES.append({
        "source": str(source), "target": str(target), "width": width, "height": height,
    })


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
    _queue_capture(_write_html(target.stem + ".html", document), target, width, height)


def _extract_section(dashboard: str, marker: str) -> str:
    style_match = re.search(r"<style>(.*?)</style>", dashboard, re.DOTALL)
    script_match = re.search(r"<script>(.*?)</script>", dashboard, re.DOTALL)
    lang_match = re.search(r'<html lang="([^"]*)"', dashboard)
    if style_match is None or lang_match is None:
        raise SystemExit("Dashboard markup incomplete – cannot extract section.")
    style = style_match.group(1)
    script = script_match.group(1) if script_match else ""
    lang = lang_match.group(1)
    for match in re.finditer(r'<section class="panel"[^>]*>.*?</section>', dashboard, re.DOTALL):
        if f'id="{marker}"' in match.group(0).split(">", 1)[0]:
            return (
                "<!DOCTYPE html>"
                f'<html lang="{lang}"><head><meta charset="utf-8"/><style>{style}</style></head>'
                f'<body><div class="page">{match.group(0)}</div><script>{script}</script></body></html>'
            )
    raise SystemExit(f"Section not found: {marker}")


def _force_dark(dashboard: str) -> str:
    return dashboard.replace("@media (prefers-color-scheme: dark) {", "@media all {")


def _force_light(dashboard: str) -> str:
    return dashboard.replace("@media (prefers-color-scheme: dark) {", "@media not all {")


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate README screenshots.")
    parser.add_argument("--manuscript", default="samples/pride-and-prejudice.md")
    args = parser.parse_args()
    CAPTURES.clear()

    manuscript = (BASE_DIR / args.manuscript).resolve()
    text = manuscript.read_text(encoding="utf-8")
    config, resolved = resolve_document_config(text, "auto")
    is_en = resolved.key == "en"
    title = "Pride and Prejudice" if is_en else manuscript.stem

    thresholds = resolve_thresholds(project_config={})
    analysis = analyze_document(text, config, thresholds)
    metrics, fingerprint = analysis.metrics, analysis.fingerprint
    paragraphs, chapters = analysis.paragraphs, analysis.chapters

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
    ReportFormatter.print_rich_report(metrics, console=console, texts=resolved.labels, language_key=resolved.key)
    _terminal_shot(
        f"lixity analyze {args.manuscript}",
        console.export_html(inline_styles=True),
        OUT_DIR / "cli-analyze.png",
        1560,
        920,
    )

    # 2. CLI: style passport ----------------------------------------------
    passport = html.escape(fingerprint.passport_text(labels=resolved.labels, language_key=resolved.key))
    _terminal_shot(
        f"lixity style {args.manuscript}",
        f"<pre>{passport}</pre>",
        OUT_DIR / "cli-style.png",
        1560,
        920,
    )

    # 3. Dashboard (light, top area) --------------------------------------
    chap_noun = "Chapters" if is_en else "Kapitel"
    para_noun = "Paragraphs" if is_en else "Absätze"
    status = [
        {"key": "manuscript", "state": "ok", "detail": f"{title}.md"},
        {
            "key": "analysis",
            "state": "ok",
            "detail": f"{len(chapters)} {chap_noun} · {len(paragraphs)} {para_noun}",
        },
        {"key": "exports", "state": "warn", "detail": "none generated" if is_en else "keine erzeugt"},
        {"key": "markers", "state": "ok", "detail": "no open markers" if is_en else "keine offenen"},
    ]
    char_names = ["Elizabeth", "Darcy", "Jane", "Bingley"] if is_en else ["Effi", "Innstetten", "Crampas", "Briest"]
    dashboard = render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        status=status,
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, char_names, config),
        pacing=pacing_report(text, config).to_dict(),
        motifs=motif_report(text, None, config).to_dict(),
        showing=showing_report(text, config, metrics=metrics).to_dict(),
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
    )
    dashboard_path = _write_html("dashboard.html", _force_light(dashboard))
    _write_html("dashboard-settings.html", _force_light(render_dashboard(
        chapters, paragraphs, metrics=metrics, fingerprint=fingerprint,
        title=title, labels=resolved.labels, language_name=resolved.name,
        language_key=resolved.key, current_language=resolved.key, controls=True,
    )))
    _queue_capture(dashboard_path, OUT_DIR / "dashboard-light.png", 1600, 1050)

    # 4. Dashboard (dark) --------------------------------------------------
    _queue_capture(
        _write_html("dashboard-dark.html", _force_dark(dashboard)),
        OUT_DIR / "dashboard-dark.png",
        1600,
        1050,
    )

    # 5. Dashboard sections ------------------------------------------------
    _queue_capture(
        _write_html(
            "section-heatmap.html", _extract_section(_force_light(dashboard), "heatmap")
        ),
        OUT_DIR / "dashboard-heatmap.png",
        1600,
        950,
    )
    _queue_capture(
        _write_html(
            "section-dimensions.html", _extract_section(_force_light(dashboard), "dimensions")
        ),
        OUT_DIR / "dashboard-dimensions.png",
        1600,
        580,
    )

    # 6. Work markers (temporary copy with three editorial markers) --------
    marked = text
    markers_spec = (
        (
            (7, "pruefen", "Verify dialogue tense continuity"),
            (61, "sachcheck", "Fact-check: Netherfield ball timeline"),
            (85, "todo", "Tighten chapter closing cadence"),
        )
        if is_en
        else (
            (7, "pruefen", "Tempuswechsel im Dialog prüfen"),
            (61, "sachcheck", "Chronologie: Effis Sterbejahr"),
            (85, "todo", "Kapitelende kürzen?"),
        )
    )
    for line, kind, note in markers_spec:
        marked, _ = add_marker(marked, kind=kind, note=note, target_line=line)
    marked_analysis = analyze_document(marked, config, thresholds)
    marked_metrics = marked_analysis.metrics
    marked_paragraphs, marked_chapters = marked_analysis.paragraphs, marked_analysis.chapters
    from lixity.markers import list_markers

    marked_dashboard = render_dashboard(
        marked_chapters,
        marked_paragraphs,
        metrics=marked_metrics,
        fingerprint=marked_analysis.fingerprint,
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        markers=list_markers(marked),
    )
    _queue_capture(
        _write_html(
            "section-markers.html", _extract_section(_force_light(marked_dashboard), "markers")
        ),
        OUT_DIR / "dashboard-markers.png",
        1600,
        340,
    )

    # 7. Style layer (draft chapter with the dialogue layer active) --------
    layer_dashboard = render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
    ).replace('<option value="dialogue"', '<option value="dialogue" selected', 1)
    _queue_capture(
        _write_html("dashboard-layer.html", _force_light(layer_dashboard)),
        OUT_DIR / "dashboard-layer.png",
        1600,
        900,
    )

    manifest = WORK_DIR / "captures.json"
    manifest.write_text(json.dumps(CAPTURES), encoding="utf-8")
    node = shutil.which("node")
    if node is None:
        raise SystemExit("Node.js is required for Playwright screenshot capture.")
    subprocess.run(  # noqa: S603
        [node, str(BASE_DIR / "scripts/capture_screenshots.cjs"), str(manifest)], check=True,
        timeout=180,
    )

    print(
        f"Done – {len(list(OUT_DIR.glob('*.png')))} screenshots in {OUT_DIR.relative_to(BASE_DIR)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
