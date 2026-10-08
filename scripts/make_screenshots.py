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
import base64
import html
import io
import json
import shutil
import struct
import subprocess
import sys
import zlib
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
from lixity.server.constants import NATIVE_UI_ACTIONS  # noqa: E402
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


def _synthetic_harbour_image() -> bytes:
    """Create a small invented setting diagram; no external image is needed."""
    width, height = 640, 240
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        for x in range(width):
            colour = (219, 232, 231) if y < 155 else (70, 120, 139)
            if 36 <= y < 126 and any(start <= x < start + 100 for start in (45, 190, 335, 480)):
                colour = (74, 95, 106)
            elif 144 <= y < 155 or (x % 145 < 12 and 155 <= y < 206):
                colour = (162, 180, 183)
            rows.extend(colour)

    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))

    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(bytes(rows))) + chunk(b"IEND", b""))


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
    from lixity.scenes import scene_report

    scenes = scene_report(text, config)
    scenes = scene_report(text, config, {
        "assignments": {item["id"]: "Sample register" for item in scenes["items"]},
        "groups": {"Sample register": {}},
    })
    dashboard = render_dashboard(
        chapters,
        paragraphs,
        metrics=metrics,
        fingerprint=fingerprint,
        status=status,
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, char_names, config),
        pacing=pacing_report(text, config).to_dict(),
        scenes=scenes,
        motifs=motif_report(text, None, config).to_dict(),
        showing=showing_report(text, config, metrics=metrics).to_dict(),
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        current_language=resolved.key,
        manuscript_name=manuscript.name,
        controls=True,
        enabled_actions=NATIVE_UI_ACTIONS,
        nda_project_name=title,
    )
    dashboard_path = _write_html("dashboard.html", dashboard)
    _queue_capture(dashboard_path, OUT_DIR / "dashboard-light.png", 1480, 945)
    for view in ("project-settings", "project-import", "nda", "scenes"):
        for suffix, width in (("", 1480), ("-mobile", 390)):
            _queue_capture(
                dashboard_path,
                OUT_DIR / f"dashboard-{view}{suffix}.png",
                width,
                1050,
            )

    # 4. Dashboard (dark) --------------------------------------------------
    _queue_capture(
        dashboard_path,
        OUT_DIR / "dashboard-dark.png",
        1480,
        945,
    )

    # 5. Dashboard sections ------------------------------------------------
    _queue_capture(
        dashboard_path,
        OUT_DIR / "dashboard-heatmap.png",
        1750,
        1000,
    )
    _queue_capture(
        dashboard_path,
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
        _write_html("dashboard-markers.html", marked_dashboard),
        OUT_DIR / "dashboard-markers.png",
        1440,
        380,
    )

    # 7. Style layer (draft chapter with the dialogue layer active) --------
    _queue_capture(
        dashboard_path,
        OUT_DIR / "dashboard-layer.png",
        1600,
        900,
    )

    # 8. Welcome Hero & Project Creation Modal (empty state) ---------------
    welcome_dashboard = render_dashboard(
        [], [], title="Lixity", controls=True, language_name=resolved.name,
        language_key=resolved.key, current_language=resolved.key,
        labels=resolved.labels, enabled_actions=NATIVE_UI_ACTIONS,
    )
    welcome_path = _write_html("dashboard-welcome.html", welcome_dashboard)
    _queue_capture(
        welcome_path,
        OUT_DIR / "dashboard-welcome.png",
        1440,
        930,
    )
    _queue_capture(
        welcome_path,
        OUT_DIR / "dashboard-project-modal.png",
        1440,
        720,
    )
    for suffix, width in (("", 1440), ("-mobile", 390)):
        _queue_capture(welcome_path, OUT_DIR / f"dashboard-project-open{suffix}.png", width, 1000)

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
        title="Port Authority Customs Log (synthetic)",
        context={
            "genre": "Official Customs Register",
            "created_period": "1923",
            "depicted_period": "October 1923",
            "place": "Hamburg Free Port Zone",
            "perspective": "Third-Person Administrative",
            "provenance_note": "Synthetic demonstration text; not an archival document or verified historical account.",
            "tags": ["Customs", "Warehouse 4"],
        },
        allow_retention=True,
    )
    weather_file = WORK_DIR / "harbor_weather_notes.txt"
    weather_file.write_text(
        "## Harbor Weather Notes\n\n"
        "Mist covered the harbor before sunrise. A light wind carried drizzle "
        "across the eastern pier, and the quay lamps remained lit.\n\n"
        "## Setting Observations\n\n"
        "The observer recorded wet cobblestones and distant bell signals. "
        "These invented notes support a fictional scene; they are not historical evidence.\n",
        encoding="utf-8",
    )
    weather_res = research_api.ingest(
        research_proj,
        weather_file,
        title="Harbor Weather Notes (synthetic)",
        context={
            "genre": "Fictional setting notes",
            "place": "Imaginary harbor",
            "provenance_note": "Synthetic demonstration text; not an archival document or verified historical account.",
            "tags": ["Weather", "Setting"],
        },
        allow_retention=True,
    )
    research_api.reindex(research_proj)
    research_html = research_api.source_dashboard(research_proj, ingest_res["source_id"])
    _queue_capture(
        _write_html("dashboard-research.html", research_html),
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
        body="## Timeline\n\nCompare the night watchman's account with the synthetic customs log.\n\n"
        "## Open Questions\n\nKeep source quotations separate from the author's fictional scene decisions.",
        tags=["Warehouse", "Timeline"],
        evidence_ids=[passage_id],
    )
    weather_passage = research_api.get_source(research_proj, weather_res["source_id"])["passages"][0]["id"]
    research_api.create_dossier(
        research_proj,
        title="Harbor setting notes",
        body="## Weather\n\nUse the synthetic notes to review the harbor scene's atmosphere.\n\n"
        "## Scene Planning\n\nThe weather and setting are fictional examples, not verified historical claims.",
        tags=["Weather", "Setting"],
        evidence_ids=[weather_passage],
    )
    visual_bytes = _synthetic_harbour_image()
    dossier_current = research_api.get_dossier(research_proj, dossier_res["dossier_id"])
    attached = research_api.attach_dossier_image(
        research_proj, dossier_res["dossier_id"], visual_bytes, filename="invented-harbour.png",
        expected_snapshot=dossier_current["snapshot"], expected_revision=dossier_current["revision"],
        allow_retention=True, alt="Four invented warehouses beside a quay and water",
        title="Synthetic harbour layout", section="Open Questions",
        caption="Invented setting sketch; not a map or historical evidence.",
        context={"provenance_note": "Generated from simple geometry for this UI example."},
    )
    visual_url = attached["images"][0]["url"]
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
    workspace_search = research_api.search(
        research_proj, "warehouse customs", scope="sources", ensure_fresh=True,
    )
    from lixity.nda import draft_document

    nda_fields = {
        "name": "Example Reader", "address": "Example street 1",
        "project_name": title, "date": "2026-10-06", "place": "Example City",
    }
    research_fixture = {
        visual_url: {"media_type": "image/png", "content_base64": base64.b64encode(visual_bytes).decode("ascii")},
        "/api/nda-draft": {
            "fields": nda_fields,
            "text": draft_document(**nda_fields, language=resolved.key).text,
        },
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
            "project_id": sources_data["project_id"],
            "project_title": sources_data["project_title"],
            "project_language": sources_data["project_language"],
            "sources": sources_data["sources"],
            "dossiers": dossiers_data["dossiers"],
            "claims": claims_data["claims"],
            "decisions": decisions_data["decisions"],
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
        "/api/research/review": {"ok": True, **research_api.editorial_review(research_proj)},
        "/api/research-search": {"ok": True, **workspace_search},
    }
    for source in sources_data["sources"]:
        research_fixture["/api/research/sources?id=" + quote(source["id"], safe="")] = {
            "ok": True, **research_api.get_source(research_proj, source["id"]),
        }
    for dossier in dossiers_data["dossiers"]:
        research_fixture["/api/research/dossiers?id=" + quote(dossier["id"], safe="")] = {
            "ok": True, **research_api.get_dossier(research_proj, dossier["id"]),
        }
    operations = []
    revision_previews = {}
    for dossier in dossiers_data["dossiers"]:
        record = research_api.get_record(research_proj, "dossier", dossier["id"])
        research_fixture["/api/research/record?kind=dossier&id=" + quote(dossier["id"], safe="")] = {"ok": True, **record}
        operation = {
            "kind": "dossier", "id": dossier["id"], "expected_revision": record["record"]["revision"],
            "changes": {"title": record["record"]["title"] + " — reviewed notes"},
            "change_kind": "correction", "reason": "Align these notes with the harbour scene.",
        }
        operations.append(operation)
        revision_previews[dossier["id"]] = {"ok": True, **research_api.prepare_record_revision(
            research_proj, "dossier", dossier["id"], base_revision=operation["expected_revision"],
            changes=operation["changes"],
        )}
    research_fixture["/api/research-record-prepare"] = revision_previews
    research_fixture["/api/research-revision-batch-prepare"] = {"ok": True, **research_api.prepare_record_revisions(research_proj, operations)}
    _write_html("research-workspace-fixture.json", json.dumps(research_fixture, ensure_ascii=False))
    research_workspace = _write_html(
        "dashboard-research-workspace.html",
        render_dashboard(
            [], [], title="Synthetic archival research", controls=True,
            labels=resolved.labels, language_name=resolved.name, language_key=resolved.key,
            current_language=resolved.key, enabled_actions=NATIVE_UI_ACTIONS,
        ),
    )
    for view in ("sources", "dossiers", "search", "claims", "decisions", "review", "change-set"):
        for suffix, width, height in (("", 1480, 1000), ("-mobile", 390, 1000)):
            _queue_capture(
                research_workspace,
                OUT_DIR / f"dashboard-research-{view}{suffix}.png",
                width,
                height,
            )
    for suffix, width in (("", 1480), ("-mobile", 390)):
        _queue_capture(research_workspace, OUT_DIR / f"dashboard-dossier-image{suffix}.png", width, 1000)

    cli_research_text = (
        f"$ lixity research search --project ./novel-research --query \"warehouse customs\" --limit 1\n"
        f"{json.dumps(search_res, indent=2)}\n\n"
        f"$ lixity research cite --project ./novel-research --passage {passage_id}\n"
        f"{json.dumps(cite_res, indent=2)}"
    )
    _terminal_shot(
        "lixity research search & cite",
        f'<pre style="white-space:pre-wrap;overflow-wrap:anywhere">{html.escape(cli_research_text)}</pre>',
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
        f"Done – {len(list(OUT_DIR.glob('*.png')))} screenshots in {OUT_DIR}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
