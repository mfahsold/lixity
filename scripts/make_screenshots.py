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
import struct
import subprocess
import sys
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))

from rich.console import Console  # noqa: E402

from lixity import ReportFormatter, __version__  # noqa: E402
from lixity.characters import presence_report  # noqa: E402
from lixity.config import resolve_thresholds  # noqa: E402
from lixity.dialogue import dialogue_report  # noqa: E402
from lixity.markers import add_marker  # noqa: E402
from lixity.motifs import motif_report  # noqa: E402
from lixity.pacing import pacing_report  # noqa: E402
from lixity.pipeline import analyze_document, resolve_document_config  # noqa: E402
from lixity.project_identity import manuscript_identity_check  # noqa: E402
from lixity.server.constants import NATIVE_UI_ACTIONS  # noqa: E402
from lixity.showing import showing_report  # noqa: E402
from lixity.ui import render_dashboard  # noqa: E402

CAPTURES: list[dict[str, str | int]] = []
WORK_DIR = BASE_DIR / ".artifacts" / "screenshots"
OUT_DIR = BASE_DIR / "docs" / "screenshots"
RESEARCH_DEMO_CONTEXT = "synthetic-research-example"
RESEARCH_DEMO_MANUSCRIPT_CONTEXT = "synthetic-harbour-manuscript"

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


def _queue_capture(source: Path, target: Path, width: int, height: int,
                   max_height: int | None = None) -> None:
    #: Element captures taller than a real screen are clamped so published
    #: images stay lifelike; dialogs bypass the clamp to show complete content.
    if max_height is None:
        max_height = 1100 if width >= 800 else 1250
    CAPTURES.append({
        "source": str(source), "target": str(target), "width": width, "height": height,
        "maxHeight": max_height,
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


def reviewed_visual_sources(asset_dir: Path | None = None) -> list[tuple[dict, bytes]]:
    """Fail closed unless the two reviewed visual references match their manifest."""
    from lixity.research.images import validate_image

    asset_dir = asset_dir or BASE_DIR / "docs/assets/research"
    manifest = json.loads((asset_dir / "sources.json").read_text(encoding="utf-8"))
    expected = {"hamburg-free-port-1900.jpg", "hamburg-harbour-1890-1900.jpg"}
    if {item["filename"] for item in manifest["sources"]} != expected or len(manifest["sources"]) != 2:
        raise ValueError("The reviewed research visual manifest must identify the two approved JPEGs")
    sources = []
    for item in manifest["sources"]:
        content = (asset_dir / item["filename"]).read_bytes()
        if sha256(content).hexdigest() != item["sha256"]:
            raise ValueError(f"Image differs from its reviewed SHA-256: {item['filename']}")
        image = validate_image(content, filename=item["filename"])
        if (image["width"], image["height"]) != (item["width"], item["height"]):
            raise ValueError(f"Image differs from its reviewed dimensions: {item['filename']}")
        sources.append((item, content))
    return sources


_PUBLIC_READ_ADAPTER = r"""(function () {
  "use strict";
  var nativeFetch = window.fetch.bind(window);
  var base = new URL(document.baseURI);
  var images = new Set([
    new URL("../assets/research/hamburg-free-port-1900.jpg", base).href,
    new URL("../assets/research/hamburg-harbour-1890-1900.jpg", base).href
  ]);
  var records = nativeFetch(new URL("research-data.json", base)).then(function (response) {
    if (!response.ok) throw new Error("Read-only example data is unavailable");
    return response.json();
  });
  window.fetch = async function (input, options) {
    var request = typeof input === "string" || input instanceof URL ? null : input;
    var url = new URL(request ? request.url : input, base);
    var method = String(options && options.method || request && request.method || "GET").toUpperCase();
    if (method !== "GET" || url.origin !== base.origin) throw new Error("Read-only example permits local fixture reads only");
    if (images.has(url.href)) return nativeFetch(url);
    var fixture = await records, key = url.pathname + url.search;
    if (!Object.prototype.hasOwnProperty.call(fixture, key)) throw new Error("Read-only example has no fixture for this request");
    return new Response(JSON.stringify(fixture[key]), {status: 200, headers: {"Content-Type": "application/json"}});
  };
})();"""


def build_research_demo(root: Path, research_fixture: dict) -> Path:
    """Publish the real dashboard with a bounded, GET-only local fixture adapter."""
    from build_examples import SITE, _head_metadata, _insert_notice, _notice

    resources = {url: "../" + value["asset_path"].removeprefix("docs/")
                 for url, value in research_fixture.items() if "asset_path" in value}

    def public_value(value):
        if isinstance(value, str):
            return resources.get(value, value)
        if isinstance(value, dict):
            return {key: public_value(item) for key, item in value.items()}
        if isinstance(value, list):
            return [public_value(item) for item in value]
        return value

    fixture = {url: public_value(value) for url, value in research_fixture.items()
               if url.startswith("/api/research/") and url not in resources}
    document = render_research_workspace(research_fixture, title="Hamburg harbour research example",
                                         enabled_actions=["manuscript-pdf", "research-manuscript-link"])
    document = re.sub(r"<title>[^<]*</title>", "<title>Lixity research example — Hamburg harbour</title>", document, count=1)
    head = _head_metadata(canonical=f"{SITE}/demo/research.html", title="Lixity research example — Hamburg harbour",
                          description="Follow retained source evidence through an authored claim to a saved synthetic manuscript quote, with credited historical imagery.",
                          language="en", preview_image=("screenshots/dashboard-dossier-image.png",
                              "Historical Hamburg map retained with source provenance in a research dossier"))
    allowed = ("[data-rtab]:not([data-rtab=search]):not([data-rtab=grounding]), "
               "[data-claim-view], #r-open-timeline, #r-review-refresh, [data-filter-tag], "
               "[data-load-evidence], [data-research-history], [data-research-revision], #research-revision-history-tab, "
               "[data-close-modal], [data-dossier-enlarge], #modal-dossier-image-enlarge button, "
               "[data-geo-select], [data-geo-map], [data-geo-fit], .leaflet-control-zoom a, [data-diagram-enlarge], "
               "[data-source-view], [data-source-toggle]")
    hidden = ("#project-controls, .view-navigation, #view-pane-analysis, #view-pane-project, #welcome-hero, "
              "#research-setup-guide, #research-init-box, #r-local-import, #zotero-box, #research-revision-batch-review, "
              "[data-rtab=search], [data-rtab=grounding], #rtab-search, #rtab-grounding, #rtab-dossiers > .ctl-group, "
              "#rtab-claims-list > .ctl-group:not(.research-timeline-entry):not(.research-relation-section), "
              "#r-relation-form, #rtab-decisions > .ctl-group")
    policy = f"""<style>
{hidden} {{ display: none !important; }}
button:not(:is({allowed})) {{ display: none !important; }}
input[type=file], a[href^="zotero:"], a[href^="/api/"] {{ display: none !important; }}
#example-context {{ margin-block: 1rem; }}
</style>
<script id="research-demo-adapter">{_PUBLIC_READ_ADAPTER}</script>
<script id="research-demo-controls">
document.addEventListener("DOMContentLoaded", function () {{
  var allowed = {json.dumps(allowed)};
  var imageResources = {json.dumps(resources)};
  var restoreImages = window.LixityDossierImages.restoreMarkdown;
  window.LixityDossierImages.restoreMarkdown = function (rendered, prepared) {{
    var template = document.createElement("template");
    template.innerHTML = restoreImages(rendered, prepared);
    template.content.querySelectorAll("img").forEach(function (image) {{
      var resource = imageResources[image.getAttribute("src")];
      if (!resource) throw new Error("Read-only example image is absent from the reviewed fixture");
      image.setAttribute("src", resource);
    }});
    return template.innerHTML;
  }};
  function disableWrites() {{
    document.querySelectorAll("button, input[type=file], textarea").forEach(function (control) {{
      if (!control.matches(allowed) && !control.disabled) control.disabled = true;
    }});
  }}
  document.addEventListener("click", function (event) {{
    var control = event.target.closest("button, a[href^='zotero:']");
    if (control && !control.matches(allowed)) {{ event.preventDefault(); event.stopImmediatePropagation(); }}
  }}, true);
  document.addEventListener("submit", function (event) {{ event.preventDefault(); event.stopImmediatePropagation(); }}, true);
  disableWrites();
  new MutationObserver(disableWrites).observe(document.body, {{childList: true, subtree: true}});
  switchActiveView("research");
  document.getElementById("research-hint").textContent = "Read-only public example: open a dossier, inspect its linked claim and retained evidence, then find the saved manuscript quote in Review.";
}});
</script>
"""
    restrictions = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
                    'script-src \'unsafe-inline\'; style-src \'unsafe-inline\'; '
                    'img-src \'self\' data: blob: https://tile.openstreetmap.org; '
                    'connect-src \'self\'; font-src data:; base-uri \'none\'; form-action \'none\'"/>')
    document = document.replace("</head>", restrictions + head + policy + "</head>", 1)
    notice = _notice(f"Lixity {__version__} · read-only research example · Current main (unreleased)", [
        "Start with Dossiers: Warehouse 4 case notes links to an authored claim and one saved manuscript quote. "
        "Claims exposes the retained supporting passage; Review shows the exact saved quote and its claim-version pin. "
        "Decisions records the author's fictional choices. These links are explicit associations, not automatic fact checks.",
        "Zotero normally owns bibliography, reading and source notes. Lixity retains selected evidence and authored records for manuscript work. "
        "This offline example has no live Zotero connection: its customs-log capture contains explicitly synthetic Zotero identity metadata, "
        "and source-return actions are disabled. The retained passage, authored claim and manuscript quote are separate records.",
        "The customs log, weather notes, manuscript, people, Warehouse 4 incident and journeys are fictional demonstration records. "
        "The dated public-domain visuals provide setting references and do not verify events or conditions in 1923. "
        "Select a dossier image or diagram to enlarge and zoom it. Coordinates are approximate author-entered examples. "
        "Interactive maps start with offline vectors; OpenStreetMap tiles load only when explicitly enabled and reveal the visible area to that provider. "
        "No route or line of sight is calculated.",
        f"Generated with Lixity {__version__}. This page cannot import, edit or save records.",
    ], [("../guides/research-pdf.html", "Research walkthrough"), ("../research/examples/harbour-manuscript.md", "Synthetic manuscript"),
        ("../index.html", "Lixity home"), ("#research-source-credits", "Image source credits")])
    fallback = ('<noscript><style>#research-manager {display:none !important;}</style>'
                '<section class="panel"><p>This interactive read-only example requires JavaScript. '
                'Source credits remain available below.</p></section></noscript>')
    document = _insert_notice(document, notice + fallback)
    credits = ['<section class="panel" id="research-source-credits"><h2>Image source credits</h2>']
    for item, _content in reviewed_visual_sources():
        credits.append(f'<h3>{html.escape(item["title"])}</h3><p>{html.escape(item["created_period"])}. '
                       f'{html.escape(item["credit"])}. {html.escape(item["rights"])}</p>'
                       f'<p>{html.escape(item["provenance_note"])}</p><p>'
                       f'<a href="{html.escape(item["source_url"], quote=True)}">Source catalogue</a> · '
                       f'<a href="{html.escape(item["origin_url"], quote=True)}">Wikimedia Commons record</a> · '
                       f'<a href="{html.escape(item["rights_url"], quote=True)}">Public-domain rights statement</a></p>')
    credits.append('<p><a href="../assets/research/sources.json">Reviewed image provenance manifest</a></p></section>')
    document = document.replace("<footer>", "".join(credits) + "<footer>", 1)
    destination = root / "docs/demo/research.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
    destination.with_name("research-data.json").write_text(json.dumps(fixture, ensure_ascii=False), encoding="utf-8")
    return destination


def render_research_workspace(research_fixture: dict, **options) -> str:
    """Reuse the native read-only quote review with fixed offline fixture context."""
    review = research_fixture["/api/research/manuscript-review?project_token=" + RESEARCH_DEMO_MANUSCRIPT_CONTEXT]
    return render_dashboard(
        [], [], controls=True, research_context_token=RESEARCH_DEMO_CONTEXT,
        manuscript_pdf_token=RESEARCH_DEMO_MANUSCRIPT_CONTEXT,
        manuscript_source_sha256=review["current_source_sha256"], **options,
    )


def build_research_fixture(work_dir: Path, *, language: str = "en",
                           nda_project_name: str = "Synthetic archival research") -> dict:
    """Create the disposable research example through the ordinary project API."""
    work_dir.mkdir(parents=True, exist_ok=True)
    research_proj = work_dir / "research-demo"
    if research_proj.exists():
        shutil.rmtree(research_proj)
    from lixity.research import api as research_api

    research_api.init(research_proj, title="Synthetic archival research example", language="en")
    (research_proj / "lixity.toml").write_text('author_name = "Example Author"\n', encoding="utf-8")
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
    customs_file = work_dir / "customs_log_1923.txt"
    customs_file.write_text(source_text, encoding="utf-8")
    research_api.ingest(
        research_proj,
        customs_file,
        title="Port Authority Customs Log (synthetic)",
        context={
            "genre": "Official Customs Register",
            "created_period": "1923",
            "depicted_period": "October 1923",
            "place": "Hamburg Free Port Zone",
            "perspective": "Third-Person Administrative",
            "provenance_note": "Synthetic demonstration text and Zotero identity metadata; not an archival document or verified historical account. "
                               "No live Zotero connection was used. The retained bytes remain available independently of Zotero.",
            "external_reference": {"provider": "zotero", "server_id": "synthetic-offline-example", "library": "users/0",
                                   "item_key": "DEMOLOG1", "attachment_key": "DEMOTXT1", "item_version": 1, "attachment_version": 1},
            "tags": ["Customs", "Warehouse 4"],
        },
        allow_retention=True,
    )
    weather_file = work_dir / "harbor_weather_notes.txt"
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
    search_res = research_api.search(research_proj, "warehouse customs", limit=1)
    matches = search_res["hits"]
    if not matches:
        raise RuntimeError("Synthetic research source must produce a real passage citation")
    passage_id = matches[0]["passage_id"]

    # Read-only browser responses below are serialized from this disposable,
    # API-created archive. The dashboard itself is the real controls UI.
    dossier_res = research_api.create_dossier(
        research_proj,
        title="Warehouse 4 case notes",
        body="## Timeline\n\nCompare the night watchman's account with the synthetic customs log.\n\n"
        "## Open Questions\n\nKeep source quotations separate from the author's fictional scene decisions.\n\n"
        "## Evidence trail\n\nThese are explicit author associations, not automatic fact checks.\n\n"
        "```mermaid\nflowchart LR\n subgraph Retained evidence\n  P[Customs log passage]\n end\n"
        " P --> C[Authored claim]\n C --> Q[Saved manuscript quote]\n C --> D[Author decision]\n```\n\n"
        "## Historical map\n\nCirca-1900 reference; not evidence of the invented 1923 incident.\n\n"
        "## Historical harbour view\n\n1890–1900 photochrom reference; not a photograph of the fictional event.",
        tags=["Warehouse", "Timeline"],
        evidence_ids=[passage_id],
        geography=json.loads((BASE_DIR / "docs/research/examples/harbour-geography.json").read_text(encoding="utf-8")),
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
    image_resources = {}
    for item, visual_bytes in reviewed_visual_sources():
        dossier_current = research_api.get_dossier(research_proj, dossier_res["dossier_id"])
        caption_title = item["title"]
        if item["created_period"].casefold() not in caption_title.casefold():
            caption_title += f" ({item['created_period']})"
        credit = item["creator"] or "Library of Congress, Photochrom Print Collection"
        attached = research_api.attach_dossier_image(
            research_proj, dossier_res["dossier_id"], visual_bytes, filename=item["filename"],
            expected_snapshot=dossier_current["snapshot"], expected_revision=dossier_current["revision"],
            allow_retention=True, alt=item["alt"], title=item["title"],
            section="Historical map" if item["id"] == "hamburg-free-port-1900" else "Historical harbour view",
            caption=f"{caption_title}. {credit}. Public domain.",
            context={"genre": item["genre"], "created_period": item["created_period"], "place": item["place"],
                     "origin_url": item["origin_url"], "tags": ["Historical visual reference"],
                     "provenance_note": f"{item['provenance_note']}\nCredit: {item['credit']}\n"
                                        f"Rights: {item['rights']}\nCatalogue: {item['source_url']}"},
        )
        captured_id = attached["capture"]["source_id"]
        image = next(image for image in attached["images"] if image["source_id"] == captured_id)
        image_resources[image["url"]] = {"media_type": "image/jpeg", "asset_path": "docs/assets/research/" + item["filename"]}
    research_api.create_claim(
        research_proj,
        title="Reformed customs seal",
        statement="The night watchman reports an unharmed seal on the bonded warehouses.",
        confidence="hypothetical",
        time_period="1922–1924",
        place="Hamburg Free Port Zone",
        dossier_id=dossier_res["dossier_id"],
    )
    research_api.create_claim(
        research_proj,
        title="Harbour tour research notes",
        statement="Modern field notes describe the former free port as a museum quarter.",
        confidence="hypothetical",
        time_period="present day",
        place="Hamburg",
    )
    claim_res = research_api.create_claim(
        research_proj,
        title="Attempted warehouse entry",
        statement="The customs log describes an attempted entry at Warehouse 4 in October 1923.",
        confidence="evidenced",
        time_period="1923",
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
    manuscript = research_proj / "harbour-manuscript.md"
    manuscript.write_bytes((BASE_DIR / "docs/research/examples/harbour-manuscript.md").read_bytes())
    anchor = research_api.resolve_manuscript_anchor(
        research_proj, manuscript, query="Someone had tried the eastern gate of Warehouse 4.",
    )
    research_api.link_manuscript_claim(
        research_proj, manuscript, claim_res["claim_id"], claim_revision=1,
        selection={key: anchor[key] for key in ("start_line", "end_line", "paragraph_sha256", "start", "end", "quote")},
        expected_project_id=anchor["project_id"], expected_snapshot=anchor["snapshot"],
        expected_source_sha256=sha256(manuscript.read_bytes()).hexdigest(), allow_retention=True,
        note="Explicit author association in a synthetic manuscript; not evidence that the fictional incident happened.",
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
        "project_name": nda_project_name, "date": "2026-10-06", "place": "Example City",
    }
    research_fixture = {
        **image_resources,
        "/api/nda-draft": {
            "fields": nda_fields,
            "text": draft_document(research_proj, **nda_fields, language=language).text,
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
        "/api/research/manuscript-links": {"ok": True, **research_api.list_manuscript_links(research_proj)},
        "/api/research/manuscript-review?project_token=" + RESEARCH_DEMO_MANUSCRIPT_CONTEXT: {
            "ok": True, **research_api.review_manuscript_links(research_proj, manuscript)},
        "/api/research/timeline": {"ok": True, **research_api.timeline(research_proj)},
        "/api/research/claim-relations?include_retracted=false": {
            "ok": True, **research_api.list_claim_relations(research_proj)},
        "/api/research/claim-relations?include_retracted=true": {
            "ok": True, **research_api.list_claim_relations(research_proj, include_retracted=True)},
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
        research_fixture["/api/research/claims?dossier_id=" + quote(dossier["id"], safe="")] = {
            "ok": True, **research_api.list_claims(research_proj, dossier_id=dossier["id"]),
        }
    for kind, records in (("dossier", dossiers_data["dossiers"]), ("claim", claims_data["claims"]),
                          ("decision", decisions_data["decisions"])):
        for item in records:
            identifier = quote(item["id"], safe="")
            endpoint = "?kind=" + kind + "&id=" + identifier
            research_fixture["/api/research/record" + endpoint] = {"ok": True, **research_api.get_record(research_proj, kind, item["id"])}
            history = research_api.record_history(research_proj, kind, item["id"])
            research_fixture["/api/research/history" + endpoint] = {"ok": True, **history}
            for version in history["revisions"]:
                research_fixture["/api/research/record" + endpoint + "&revision=" + str(version["revision"])] = {
                    "ok": True, **research_api.get_record(research_proj, kind, item["id"], revision=version["revision"])}
            if kind == "claim":
                research_fixture["/api/research/claims?claim_id=" + identifier] = {
                    "ok": True, **research_api.list_evidence_links(research_proj, claim_id=item["id"])}
            if kind == "decision":
                research_fixture["/api/research/decision-impact?id=" + identifier] = {
                    "ok": True, **research_api.decision_impact(research_proj, item["id"])}
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
    # Exact aliases preserve the native context-bound GET URLs without making
    # the public adapter strip arbitrary parameters or emulate a live server.
    research_fixture.update({
        url + ("&" if "?" in url else "?") + "research_token=" + RESEARCH_DEMO_CONTEXT: value
        for url, value in list(research_fixture.items())
        if url.startswith("/api/research/") and url not in image_resources
    })
    return research_fixture


def sync_embedded_image_sizes() -> int:
    """Update width/height of docs images to their real PNG size.

    The screenshots are regenerated independently of the pages that embed
    them; without this step a re-render silently leaves stale attributes
    behind. Returns the number of corrected <img> tags.
    """
    pattern = re.compile(r"<img\s+([^>]*?)/?>", re.DOTALL)
    attributes = re.compile(r'(\w+)="([^"]*)"')
    corrected = 0
    for document in sorted((BASE_DIR / "docs").glob("**/*.html")):
        markup = document.read_text(encoding="utf-8")
        changed = False
        for match in list(pattern.finditer(markup)):
            values = dict(attributes.findall(match.group(1)))
            source = values.get("src", "")
            if not source or source.startswith(("http:", "https:", "data:")):
                continue
            image = (document.parent / source).resolve()
            try:
                header = image.read_bytes()[:24]
            except OSError:
                continue
            if header[:8] != b"\x89PNG\r\n\x1a\n":
                continue
            width, height = struct.unpack(">II", header[16:24])
            if values.get("width") == str(width) and values.get("height") == str(height):
                continue
            tag = match.group(0)
            new_tag = re.sub(r'width="[^"]*"', f'width="{width}"', tag, count=1)
            new_tag = re.sub(r'height="[^"]*"', f'height="{height}"', new_tag, count=1)
            if 'width="' not in tag:
                new_tag = new_tag.replace("<img", f'<img width="{width}"', 1)
            if 'height="' not in tag:
                new_tag = new_tag.replace("<img", f'<img height="{height}"', 1)
            markup = markup.replace(tag, new_tag, 1)
            changed = True
            corrected += 1
        if changed:
            document.write_text(markup, encoding="utf-8")
    return corrected


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate README screenshots.")
    parser.add_argument("--manuscript", default="samples/pride-and-prejudice.md")
    parser.add_argument("--only", nargs="+", help="Capture only these screenshot filenames.")
    parser.add_argument("--video", action="store_true", help="Record the short guided walkthroughs instead of stills.")
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

    WORK_DIR.mkdir(parents=True, exist_ok=True)
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
    status = [
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
        project_author="Example Author",
        author_setting_enabled=True,
        project_token="a" * 64,
        identity_check=manuscript_identity_check(text, title, "Example Author"),
    )
    dashboard_path = _write_html("dashboard.html", dashboard)
    _queue_capture(dashboard_path, OUT_DIR / "dashboard-light.png", 1480, 945)
    for name, width, height in (
        ("dashboard-mobile.png", 390, 1028),
        ("dashboard-dimensions-mobile.png", 390, 1028),
        ("dashboard-dimensions-dark.png", 1600, 1050),
        ("dashboard-reference.png", 1600, 1050),
        ("dashboard-settings.png", 1600, 1050),
    ):
        _queue_capture(dashboard_path, OUT_DIR / name, width, height)
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

    # 4b. Dark surface variants for the marketing shots. The staged site leads
    # with the dark surface; light variants stay available in the captions.
    for name, width, height in (
        ("dashboard-mobile-dark.png", 390, 1028),
        ("dashboard-heatmap-dark.png", 1750, 1000),
        ("dashboard-dimensions-dark.png", 1600, 1050),
        ("dashboard-flags-dark.png", 1152, 501),
        ("dashboard-research-timeline-dark.png", 1110, 1036),
        ("dashboard-research-claims-dark.png", 1152, 1101),
        ("dashboard-research-dossiers-dark.png", 1152, 1101),
        ("dashboard-project-settings-dark.png", 1152, 1005),
        ("dashboard-dossier-image-dark.png", 1082, 481),
        ("dashboard-dossier-photo-dark.png", 1480, 1000),
        ("dashboard-dossier-geography-dark.png", 1480, 1000),
        ("dashboard-scenes-dark.png", 1152, 1101),
    ):
        _queue_capture(dashboard_path, OUT_DIR / name, width, height)

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

    # 6b. Editorial loop: the same marked manuscript with the native controls,
    # so flags, paragraph values and the inline marker note appear together.
    editorial_dashboard = render_dashboard(
        marked_chapters,
        marked_paragraphs,
        metrics=marked_metrics,
        fingerprint=marked_analysis.fingerprint,
        title=title,
        labels=resolved.labels,
        language_name=resolved.name,
        language_key=resolved.key,
        markers=list_markers(marked),
        controls=True,
        enabled_actions=NATIVE_UI_ACTIONS,
    )
    editorial_path = _write_html("dashboard-editorial.html", editorial_dashboard)
    _queue_capture(editorial_path, OUT_DIR / "dashboard-flags.png", 1480, 560)
    _queue_capture(editorial_path, OUT_DIR / "dashboard-editorial.png", 1480, 760)

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
    research_fixture = build_research_fixture(WORK_DIR, language=resolved.key, nda_project_name=title)
    from lixity.research import api as research_api
    research_proj = WORK_DIR / "research-demo"
    search_res = research_api.search(research_proj, "warehouse customs", limit=1)
    passage_id = search_res["hits"][0]["passage_id"]
    cite_res = research_api.cite(research_proj, passage_id)
    research_html = research_api.source_dashboard(research_proj, search_res["hits"][0]["source_id"])
    _queue_capture(_write_html("dashboard-research.html", research_html), OUT_DIR / "dashboard-research.png", 1480, 960)
    build_research_demo(BASE_DIR, research_fixture)
    _write_html("research-workspace-fixture.json", json.dumps(research_fixture, ensure_ascii=False))
    research_workspace = _write_html(
        "dashboard-research-workspace.html",
        render_research_workspace(
            research_fixture, title="Synthetic archival research",
            labels=resolved.labels, language_name=resolved.name, language_key=resolved.key,
            current_language=resolved.key, enabled_actions=NATIVE_UI_ACTIONS,
            project_author="Example Author", author_setting_enabled=True,
            identity_check=manuscript_identity_check(None, "Synthetic archival research", "Example Author"),
        ),
    )
    for view in ("sources", "dossiers", "search", "claims", "timeline", "decisions", "review", "change-set"):
        for suffix, width, height in (("", 1480, 1000), ("-mobile", 390, 1000)):
            _queue_capture(
                research_workspace,
                OUT_DIR / f"dashboard-research-{view}{suffix}.png",
                width,
                height,
            )
    for suffix, width in (("", 1480), ("-mobile", 390)):
        for visual in ("image", "photo", "geography", "diagram", "image-zoom"):
            _queue_capture(research_workspace, OUT_DIR / f"dashboard-dossier-{visual}{suffix}.png", width, 1000)

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

    if args.video:
        video_dir = WORK_DIR / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        demo_report = BASE_DIR / "docs" / "demo" / "report.html"
        CAPTURES[:] = [
            {
                "source": str(research_workspace),
                "target": str(OUT_DIR / "dashboard-research-timeline.png"),
                "width": 1280, "height": 800, "video": True,
                "videoTarget": str(video_dir / "research-timeline.webm"),
            },
            {
                "source": str(demo_report),
                "target": str(OUT_DIR / "dashboard-light.png"),
                "width": 1280, "height": 800, "video": True,
                "videoTarget": str(video_dir / "analysis-review.webm"),
            },
            {
                "source": str(editorial_path),
                "target": str(OUT_DIR / "dashboard-editorial.png"),
                "width": 1280, "height": 800, "video": True,
                "videoTarget": str(video_dir / "editorial-loop.webm"),
            },
        ]
    elif args.only:
        requested = set(args.only)
        available = {Path(str(capture["target"])).name for capture in CAPTURES}
        missing = requested - available
        if missing:
            parser.error("Unknown screenshot filenames: " + ", ".join(sorted(missing)))
        CAPTURES[:] = [capture for capture in CAPTURES
                       if Path(str(capture["target"])).name in requested]

    manifest = WORK_DIR / "captures.json"
    manifest.write_text(json.dumps(CAPTURES), encoding="utf-8")
    node = shutil.which("node")
    if node is None:
        raise SystemExit("Node.js is required for Playwright screenshot capture.")
    subprocess.run(  # noqa: S603
        [node, str(BASE_DIR / "scripts/capture_screenshots.cjs"), str(manifest)], check=True,
        timeout=180,
    )

    corrected = sync_embedded_image_sizes()
    print(
        f"Done – {len(list(OUT_DIR.glob('*.png')))} screenshots in {OUT_DIR}"
        + (f"; {corrected} embedded image size(s) synced" if corrected else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
