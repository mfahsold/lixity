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
from urllib.parse import quote

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
    extra_style = "\n.page { max-width: 1720px !important; }\n" if marker == "heatmap" else ""
    for match in re.finditer(r'<section class="panel"[^>]*>.*?</section>', dashboard, re.DOTALL):
        if f'id="{marker}"' in match.group(0).split(">", 1)[0]:
            return (
                "<!DOCTYPE html>"
                f'<html lang="{lang}"><head><meta charset="utf-8"/><style>{style}{extra_style}</style></head>'
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
        1320,
        840,
    )

    # 2. CLI: style passport ----------------------------------------------
    passport = html.escape(fingerprint.passport_text(labels=resolved.labels, language_key=resolved.key))
    _terminal_shot(
        f"lixity style {args.manuscript}",
        f"<pre>{passport}</pre>",
        OUT_DIR / "cli-style.png",
        1320,
        860,
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
    _queue_capture(dashboard_path, OUT_DIR / "dashboard-light.png", 1480, 945)

    # 4. Dashboard (dark) --------------------------------------------------
    _queue_capture(
        _write_html("dashboard-dark.html", _force_dark(dashboard)),
        OUT_DIR / "dashboard-dark.png",
        1480,
        945,
    )

    # 5. Dashboard sections ------------------------------------------------
    _queue_capture(
        _write_html(
            "section-heatmap.html", _extract_section(_force_light(dashboard), "heatmap")
        ),
        OUT_DIR / "dashboard-heatmap.png",
        1750,
        1000,
    )
    _queue_capture(
        _write_html(
            "section-dimensions.html", _extract_section(_force_light(dashboard), "dimensions")
        ),
        OUT_DIR / "dashboard-dimensions.png",
        1600,
        580,
    )

    # 6. Work markers (temporary copy with representative editorial markers)
    marked = text
    markers_spec = (
        (
            (7, "pruefen", "Verify dialogue tense continuity"),
            (61, "sachcheck", "Fact-check: Netherfield ball timeline"),
            (85, "todo", "Tighten chapter closing cadence"),
            (120, "achtung", "Check Darcy introduction register & tone"),
            (180, "pruefen", "Confirm dialogue attribution consistency"),
        )
        if is_en
        else (
            (7, "pruefen", "Tempuswechsel im Dialog prüfen"),
            (61, "sachcheck", "Chronologie: Effis Sterbejahr"),
            (85, "todo", "Kapitelende kürzen?"),
            (120, "achtung", "Registerwechsel bei Crampas prüfen"),
            (180, "pruefen", "Sprecherzuordnung im Dialog konsistent"),
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
        1440,
        380,
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

    # 8. Welcome Hero & Project Creation Modal (empty state) ---------------
    welcome_dashboard = render_dashboard([], [], title="Lixity", controls=True, language_name=resolved.name, language_key=resolved.key, labels=resolved.labels)
    _queue_capture(
        _write_html("dashboard-welcome.html", _force_light(welcome_dashboard)),
        OUT_DIR / "dashboard-welcome.png",
        1440,
        600,
    )
    _queue_capture(
        _write_html("dashboard-project-modal.html", _force_light(welcome_dashboard)),
        OUT_DIR / "dashboard-project-modal.png",
        1440,
        720,
    )
    open_project_dashboard = _write_html("dashboard-project-open.html", _force_light(welcome_dashboard))
    for suffix, width in (("", 1440), ("-mobile", 390)):
        _queue_capture(open_project_dashboard, OUT_DIR / f"dashboard-project-open{suffix}.png", width, 1000)

    # 9. Research Source Dashboard & CLI Citation (Research Pilot) ---------
    research_proj = WORK_DIR / "research-demo"
    if research_proj.exists():
        shutil.rmtree(research_proj)
    from lixity.research import api as research_api

    research_api.init(research_proj, title="Synthetic archival research example", language="en")
    source_text = """## Section 1: Port Authority Log – October 1923

On the cold evening of October 14, 1923, customs officers on the night shift observed suspicious movements near Warehouse 4 in the Free Port zone.
The autumn mist hung heavy over the Elbe river, obscuring the watercraft anchored along the quay.
Two unidentified figures were seen attempting to force the secondary padlock on the eastern warehouse gate.

When challenged by the night watchman, both individuals abandoned a wooden crate and fled along the cobblestone embankment toward Sandtorhafen.
Officer Hansen inspected the abandoned crate and found forty bundles of untaxed Virginian tobacco leaves.
The evidence was impounded and transferred to the central customs station at dawn.

## Section 2: Witness Statement and Follow-up

The night watchman reported that a small motor launch with muffled exhaust had been idling near the southern pier shortly before the incident.
Inspection of the lock revealed fresh tool abrasions consistent with a heavy steel crowbar.
No customs seals on the adjacent bonded storehouses had been broken during the encounter.
"""
    customs_file = WORK_DIR / "customs_log_1923.txt"
    customs_file.write_text(source_text, encoding="utf-8")
    ingest_res = research_api.ingest(
        research_proj,
        customs_file,
        context={
            "genre": "Official Customs Register",
            "created_period": "1923",
            "depicted_period": "October 1923",
            "place": "Hamburg Free Port Zone",
            "perspective": "Third-Person Administrative",
            "provenance_note": "Synthetic demonstration text; not an archival document or verified historical account.",
        },
        allow_retention=True,
    )
    research_api.reindex(research_proj)
    research_html = research_api.source_dashboard(research_proj, ingest_res["source_id"])
    _queue_capture(
        _write_html("dashboard-research.html", _force_light(research_html)),
        OUT_DIR / "dashboard-research.png",
        1480,
        960,
    )

    search_res = research_api.search(research_proj, "warehouse customs", limit=1)
    matches = search_res["hits"]
    if not matches:
        raise RuntimeError("Synthetic research source must produce a real passage citation")
    passage_id = matches[0]["passage_id"]
    cite_res = research_api.cite(research_proj, passage_id)

    # Read-only browser responses below are serialized from this disposable,
    # API-created archive. The dashboard itself is the real controls UI.
    dossier_res = research_api.create_dossier(
        research_proj,
        title="Warehouse 4 case notes",
        body="Synthetic case note: compare the night watchman's account with the customs log.",
        evidence_ids=[passage_id],
    )
    claim_res = research_api.create_claim(
        research_proj,
        title="Attempted warehouse entry",
        statement="The customs log describes an attempted entry at Warehouse 4 in October 1923.",
        confidence="evidenced",
        time_period="October 1923",
        place="Hamburg Free Port Zone",
        actors=["Night watchman", "Customs officers"],
        dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj,
        claim_id=claim_res["claim_id"],
        passage_id=passage_id,
        relation="supports",
        rationale="The synthetic log describes the attempted entry.",
    )
    research_api.record_decision(
        research_proj,
        title="Keep the inspection at dawn",
        rationale="The synthetic source places the transfer at dawn; preserve that sequence.",
        claim_id=claim_res["claim_id"],
        impact_on_plot="The crate reaches the customs station in the following scene.",
    )
    research_api.record_decision(
        research_proj,
        title="Move the discovery scene",
        rationale="Bring the discovery forward to make the fictional chapter flow clearer.",
        claim_id=claim_res["claim_id"],
        deviation_from_fact=True,
        impact_on_plot="The protagonist arrives before the night watchman calls for help.",
    )
    sources_data = research_api.list_sources(research_proj)
    dossiers_data = research_api.list_dossiers(research_proj)
    claims_data = research_api.list_claims(research_proj)
    decisions_data = research_api.list_decisions(research_proj)
    research_fixture = {
        # Synthetic server-local paths demonstrate the chooser without exposing a user's home.
        "/api/project-paths": {
            "ok": True, "path": "/home/demo/my-novel", "parent": "/home/demo",
            "entries": [
                {"name": "research", "path": "/home/demo/my-novel/research", "kind": "directory"},
                {"name": "manuscript.md", "path": "/home/demo/my-novel/manuscript.md", "kind": "manuscript"},
            ],
            "truncated": False,
        },
        "/api/research/status": {
            "ok": True,
            "initialized": True,
            "project_root": "./research-demo",
            "sources_count": len(sources_data["sources"]),
            "dossiers_count": len(dossiers_data["dossiers"]),
            "claims_count": len(claims_data["claims"]),
            "decisions_count": len(decisions_data["decisions"]),
        },
        "/api/research/sources": {"ok": True, **sources_data},
        "/api/research/dossiers": {"ok": True, **dossiers_data},
        "/api/research/claims": {"ok": True, **claims_data},
        "/api/research/claims?claim_id=" + quote(claim_res["claim_id"], safe=""): {
            "ok": True,
            **research_api.list_evidence_links(research_proj, claim_id=claim_res["claim_id"]),
        },
        "/api/research/decisions": {"ok": True, **decisions_data},
    }
    _write_html("research-workspace-fixture.json", json.dumps(research_fixture, ensure_ascii=False))
    research_workspace = _write_html(
        "dashboard-research-workspace.html",
        _force_light(render_dashboard(
            [], [], title="Synthetic archival research", controls=True,
            labels=resolved.labels, language_name=resolved.name, language_key=resolved.key,
        )),
    )
    for view in ("claims", "decisions"):
        for suffix, width, height in (("", 1480, 1000), ("-mobile", 390, 1000)):
            _queue_capture(
                research_workspace,
                OUT_DIR / f"dashboard-research-{view}{suffix}.png",
                width,
                height,
            )

    cli_research_text = (
        f"$ lixity research search --project ./novel-research --query \"warehouse customs\" --limit 1\n"
        f"{json.dumps(search_res, indent=2)}\n\n"
        f"$ lixity research cite --project ./novel-research --passage {passage_id}\n"
        f"{json.dumps(cite_res, indent=2)}"
    )
    _terminal_shot(
        "lixity research search & cite",
        f"<pre>{html.escape(cli_research_text)}</pre>",
        OUT_DIR / "cli-research.png",
        1320,
        780,
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
