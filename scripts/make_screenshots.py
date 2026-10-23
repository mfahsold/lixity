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
from urllib.parse import quote, urlencode

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
from lixity.ui.dashboard import render_analysis  # noqa: E402
from lixity.ui.manuscript_document import reader_blocks  # noqa: E402

CAPTURES: list[dict[str, str | int]] = []
WORK_DIR = BASE_DIR / ".artifacts" / "screenshots"
OUT_DIR = BASE_DIR / "docs" / "screenshots"
RESEARCH_DEMO_CONTEXT = "synthetic-research-example"
RESEARCH_DEMO_MANUSCRIPT_CONTEXT = "synthetic-harbour-manuscript"
DEMO_MANUSCRIPT = BASE_DIR / "samples/first-look.md"


def manuscript_title(text: str, fallback: str = "Manuscript") -> str:
    """Use the selected manuscript's title, independently of its language."""
    heading = re.search(r"(?m)^#\s+(.+?)\s*$", text)
    return heading[1] if heading else fallback

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
    # Full native widgets are the default. Explicit excerpts are bounded by
    # complete component selectors in the browser capture definitions.
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


def build_research_demo(root: Path, project: Path) -> Path:
    """Wrap the production website export of the reviewed synthetic project."""
    from build_examples import (
        SITE,
        _analytics_endpoint,
        _finalize,
        _head_metadata,
        _insert_notice,
        _replace_title,
        _site_navigation,
    )

    from lixity.pdf_export import PDF_LAYOUTS, compose_pdf
    from lixity.site_contracts import SiteManifest
    from lixity.site_export import prepare_site

    manuscript = project / "harbour-manuscript.md"
    manuscript_bytes = manuscript.read_bytes()
    if manuscript_bytes != DEMO_MANUSCRIPT.read_bytes():
        raise ValueError("The public demo must use the reviewed synthetic manuscript")
    text = manuscript_bytes.decode("utf-8")
    title = manuscript_title(text)
    public_manuscript = root / "docs/research/examples/harbour-manuscript.md"
    public_manuscript.parent.mkdir(parents=True, exist_ok=True)
    public_manuscript.write_bytes(manuscript_bytes)

    bundle = prepare_site(project, manuscript=manuscript, include_research=True, include_source_files=True)
    files = {name: content for name, content in bundle.files.items() if name not in ("index.html", "manifest.json")}
    document = bundle.files["index.html"].decode("utf-8")
    # The reviewed public wrapper has one additional, disclosed image endpoint.
    # Replace the private export policy rather than intersecting two policies.
    document = re.sub(r'<meta http-equiv="Content-Security-Policy"[^>]*>', "", document, count=1)
    page_title = "Lixity project demo — " + title
    document = _replace_title(document, page_title)
    head = _head_metadata(canonical=f"{SITE}/demo/report.html", title=page_title,
                          description="Does chapter 2's shorter rhythm fit its action? Read a passage, inspect the counted sentences and make your own judgment in this fictional, read-only project.",
                          language="en", preview_image=("screenshots/dashboard-dossier-image.png",
                              "Historical Hamburg map retained with source provenance in a research dossier"))
    policy = (
        '<style>'
        '#example-context { margin-block: 1rem; }'
        '.demo-quick-start { display: flex; align-items: center; justify-content: space-between; '
        'gap: var(--space-3); margin-block: var(--space-3); padding: var(--space-3); '
        'border-inline-start: 3px solid var(--accent); background: var(--surface); }'
        '.demo-quick-start-copy { min-width: 0; }'
        '.demo-quick-start h2 { margin: 0 0 var(--space-1); font-size: var(--text-body); }'
        '.demo-quick-start p { margin: 0; color: var(--fg-secondary); }'
        '.demo-quick-start-actions { display: flex; flex-wrap: wrap; gap: var(--space-2); flex-shrink: 0; }'
        '@media (max-width: 600px) { .demo-quick-start { align-items: stretch; flex-direction: column; '
        'gap: var(--space-2); padding: var(--space-2); } '
        '.demo-quick-start-actions { flex-wrap: wrap; gap: var(--space-1); } '
        '.demo-quick-start-actions > .ctl { width: auto; min-height: 2rem; padding: .25rem .45rem; '
        'font-size: var(--text-small); } }'
        '</style>'
    )
    counter = _analytics_endpoint(root)
    counter_source = f" {counter}" if counter else ""
    site_code = counter.removeprefix("https://").split(".", 1)[0] if counter else None
    head = head.replace('src="../assets/analytics.js"',
                        'src="../assets/analytics.js" data-site-code="' +
                        html.escape(json.dumps(site_code), quote=True) + '"', 1)
    restrictions = ('<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; '
                    'script-src \'self\' \'unsafe-inline\'; style-src \'unsafe-inline\'; '
                    f'img-src \'self\' data: blob:{counter_source}; '
                    'connect-src \'none\'; font-src data:; base-uri \'none\'; form-action \'none\'"/>')
    document = document.replace("</head>", restrictions + head + policy + "</head>", 1)
    pdf_links = [(f"warehouse-4-{layout}.pdf", label) for layout, label in (
        ("editor", "Editorial manuscript PDF"), ("book", "Reading manuscript PDF"),
        ("sheet", "Submission manuscript PDF"), ("report", "Analysis report PDF"),
        ("document", "Document PDF (A4)"))]
    about_paragraphs = [
        "Start in Research with Dossiers: Warehouse 4 case notes connects the customs log, an office discrepancy and exact manuscript quotations. "
        "The preliminary log and its correction disagree about where the crate was opened; claim versions preserve the earlier interpretation. "
        "Review identifies the two quotations still linked to an earlier claim version. Decisions records the author's fictional choices. "
        "These links are explicit associations, not automatic fact checks.",
        "Zotero normally owns bibliography, reading and source notes. Lixity retains selected evidence and authored records for manuscript work. "
        "This offline example has no live Zotero connection; local Zotero identities are omitted from the website. "
        "The retained passage, authored claim and manuscript quote are separate records.",
        "The customs log, weather notes, manuscript, people, Warehouse 4 incident and journeys are fictional demonstration records. "
        "The dated public-domain visuals provide setting references and do not verify events or conditions in 1923. "
        "Select a dossier image or diagram to enlarge and zoom it. Coordinates are approximate author-entered examples. "
        "Maps use the packaged coordinates and offline vectors without requesting background tiles. "
        "The coordinate sketch remains available. "
        "No route or line of sight is calculated.",
        "These short synthetic chapters and language-dependent heuristics support human review; "
        "they are not a benchmark, calibration corpus or writing-quality verdict.",
        f"Generated with Lixity {__version__}. This page cannot import, edit or save records.",
    ]
    notice = (
        '<details class="panel" id="example-context" aria-labelledby="example-heading">'
        '<summary id="example-heading">About this read-only demo</summary>'
        '<p>Read in Manuscript, then explore the same project in Research. '
        'This demo cannot import, edit or save. It uses the same read-only website export as a local project.</p>'
        '<div class="license-links"><a href="../guides/first-look.html">Follow the walkthrough</a>'
        '<a href="#demo-downloads">Download PDFs</a>'
        '<a href="../guides/installation.html">Install the local app</a></div>'
        + "".join("<p>" + paragraph + "</p>" for paragraph in about_paragraphs)
        + '</details>'
    )
    fallback = ('<noscript><style>.view-navigation,#project-controls,#view-pane-research,#view-pane-project,.reader-controls,.marker-row,#demo-quick-start {display:none !important;}'
                '#view-pane-analysis {display:block !important;}</style>'
                '<section class="panel"><p>Interactive research requires JavaScript. '
                'The complete manuscript analysis, PDF downloads and source credits remain available below. '
                '<a href="../guides/installation.html">Install the full local app</a>.</p></section></noscript>')
    document = _insert_notice(document, fallback)
    quick_start = (
        '<section class="panel demo-quick-start" id="demo-quick-start" aria-labelledby="demo-quick-start-title">'
        '<div class="demo-quick-start-copy"><h2 id="demo-quick-start-title">Why the short sentences?</h2>'
        '<details id="demo-task-guide"><summary>Try one reading check</summary>'
        '<p>Does its shorter rhythm fit the action? No score tells you whether to rewrite.</p>'
        '<ol><li>Choose <strong>Inspect chapter 2</strong>. Read “A board moved. Mara turned.”</li>'
        '<li>Use the paragraph’s <strong>… → Explore passage → Explain measurement</strong> to inspect the sentence counts. '
        'If marks are hidden, turn on <strong>Counted text</strong>.</li>'
        '<li>Compare the <a href="#ch-1" data-jump="#ch-1" data-layer="asl">opening chapter</a>. '
        'Short beats accompany moving the crate; longer sentences establish the harbour. '
        'You may keep that contrast, or reread it for an unintended choppy effect.</li></ol>'
        '<p>The result is a reason to read, not a correction. '
        '<a href="../guides/installation.html">Try the same question with your own manuscript</a>.</p>'
        '</details></div>'
        '<div class="demo-quick-start-actions">'
        '<a class="ctl primary" href="#ch-2" data-jump="#ch-2" data-layer="asl">Inspect chapter 2</a>'
        '<button class="ctl" type="button" data-switch-view="research">Explore research</button>'
        '</div></section>'
    )
    navigation_content = '<div id="workspace-navigation-content">'
    if document.count(navigation_content) != 1:
        raise ValueError("The demo must retain one native workspace navigation container")
    document = document.replace(navigation_content, quick_start + navigation_content, 1)
    credits = ['<section class="panel" id="research-source-credits"><h2>Image source credits</h2>']
    for item, _content in reviewed_visual_sources():
        credits.append(f'<h3>{html.escape(item["title"])}</h3><p>{html.escape(item["created_period"])}. '
                       f'{html.escape(item["credit"])}. {html.escape(item["rights"])}</p>'
                       f'<p>{html.escape(item["provenance_note"])}</p><p>'
                       f'<a href="{html.escape(item["source_url"], quote=True)}">Source catalogue</a> · '
                       f'<a href="{html.escape(item["origin_url"], quote=True)}">Wikimedia Commons record</a> · '
                       f'<a href="{html.escape(item["rights_url"], quote=True)}">Public-domain rights statement</a></p>')
    credits.append('<p><a href="../assets/research/sources.json">Reviewed image provenance manifest</a></p></section>')
    downloads = ('<section class="panel" id="demo-downloads"><h2>Download this project</h2>'
                 '<p>All PDFs use the same fictional manuscript shown in Analysis and linked in Research.</p>'
                 '<div class="license-links">' + " ".join(f'<a href="{href}" download>{label}</a>' for href, label in pdf_links) +
                 '<a href="../research/examples/harbour-manuscript.md">Synthetic manuscript source</a>'
                 '<a href="#demo-license">Distribution license</a></div></section>')
    license_text = html.escape((BASE_DIR / "LICENSE").read_text(encoding="utf-8"))
    appendix = ('<section class="panel" id="demo-license"><h2>Distribution license (AGPL-3.0)</h2>'
                '<p>This report and its synthetic manuscript are distributed under AGPL-3.0-or-later. '
                'The complete unchanged repository LICENSE follows; it is not part of the analyzed manuscript.</p>'
                '<details><summary>Read the complete LICENSE</summary><pre id="demo-license-text" '
                'style="white-space:pre-wrap;overflow-wrap:anywhere;font-size:var(--text-note)">' + license_text + '</pre></details></section>')
    document = document.replace("<footer>", notice + downloads + "".join(credits) + appendix + "<footer>", 1)
    document = _site_navigation(document, title, demo=True, breadcrumbs=False)
    destination = root / "docs/demo/report.html"
    destination.parent.mkdir(parents=True, exist_ok=True)
    files["report.html"] = _finalize(document).encode("utf-8")
    for layout in PDF_LAYOUTS:
        files[f"warehouse-4-{layout}.pdf"] = compose_pdf(
            text, manuscript="harbour-manuscript.md", layout=layout, language="en",
            title=title, author="Example Author", project_config={},
        )
    files["research.html"] = (
        '<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"/>'
        '<meta name="viewport" content="width=device-width, initial-scale=1"/>'
        '<title>Lixity project demo — research</title>'
        f'<link rel="canonical" href="{SITE}/demo/report.html"/>'
        '<meta http-equiv="refresh" content="0; url=report.html#research-manager"/>'
        '</head><body><p>Research is part of the same Warehouse 4 project. '
        '<a href="report.html#research-manager">Open the project research view</a>.</p></body></html>\n'
    ).encode()
    manifest = {**bundle.manifest, "entrypoint": "report.html",
                "disclosures": [*bundle.manifest["disclosures"],
                    "The public Pages wrapper adds reviewed navigation, PDF downloads, source credits and optional privacy-respecting analytics."],
                "capabilities": {**bundle.manifest["capabilities"], "automatic_external_requests": bool(counter)}, "files": {
        name: {"sha256": sha256(content).hexdigest(), "byte_length": len(content)}
        for name, content in sorted(files.items())
    }}
    SiteManifest.model_validate(manifest)
    files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    for name, content in files.items():
        target = destination.parent / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    # This response map belonged to the former demo-only transport.
    destination.with_name("research-data.json").unlink(missing_ok=True)
    return destination


def render_research_workspace(research_fixture: dict, **options) -> str:
    """Render analysis and research over exactly the archive's manuscript bytes."""
    from lixity.scenes import scene_report_for_display

    text = DEMO_MANUSCRIPT.read_bytes().decode("utf-8")
    config, resolved = resolve_document_config(text, "en", project_config={})
    thresholds = resolve_thresholds(project_config={})
    analysis = analyze_document(text, config, thresholds, include_evidence=True)
    review = research_fixture["/api/research/manuscript-review?project_token=" + RESEARCH_DEMO_MANUSCRIPT_CONTEXT]
    if review["current_source_sha256"] != sha256(text.encode("utf-8")).hexdigest():
        raise ValueError("The public demo analysis and research manuscript differ")
    return render_analysis(
        analysis, resolved, title=options.pop("title", manuscript_title(text)),
        reader_document=reader_blocks(text, config, analysis.paragraphs),
        flag_min_severity=thresholds.flag_min_severity,
        scenes=scene_report_for_display(text, config, None, premeasured_chapters=analysis.metrics.chapters),
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, ["Mara", "Ivo", "Hansen"], config),
        pacing=pacing_report(text, config).to_dict(),
        motifs=motif_report(text, None, config).to_dict(),
        showing=showing_report(text, config, metrics=analysis.metrics).to_dict(),
        manuscript_name=options.pop("manuscript_name", "harbour-manuscript.md"), current_language="en",
        controls=True, research_context_token=RESEARCH_DEMO_CONTEXT,
        manuscript_pdf_token=RESEARCH_DEMO_MANUSCRIPT_CONTEXT,
        manuscript_source_sha256=review["current_source_sha256"], **options,
    )


def build_publication_examples(root: Path, project: Path) -> dict[str, Path]:
    """Publish two reviewed synthetic profiles through the production exporter.

    The reader includes all six chapters; the standalone companion is capped at
    chapter three. No analytics or source-project mutation is added here.
    """
    from build_examples import SITE, _finalize, _head_metadata, _site_navigation

    from lixity.site_contracts import SiteManifest
    from lixity.site_export import prepare_site

    manuscript = project / "harbour-manuscript.md"
    if manuscript.read_bytes() != DEMO_MANUSCRIPT.read_bytes():
        raise ValueError("Public publications require the reviewed synthetic manuscript")
    outputs = {}
    for mode, cap in (("reader", None), ("companion", 3)):
        bundle = prepare_site(project, manuscript=manuscript, mode=mode,
            publication_profile="readers", max_chapter=cap, include_source_files=True)
        document = bundle.files["index.html"].decode("utf-8")
        title = "Warehouse 4 — " + ("read with context" if mode == "reader" else "a reader's companion")
        description = ("Read six fictional harbour chapters with context you reveal as you read." if mode == "reader" else
                       "Explore a fictional harbour's setting beside your book; this companion contains no novel text and stops at chapter three.")
        metadata = _head_metadata(canonical=f"{SITE}/demo/{mode}/index.html", title=title,
            description=description, language="en", analytics=False)
        document = document.replace("</head>", metadata + "</head>", 1)
        document = _site_navigation(document, title, demo=True, breadcrumbs=False, links=(
            ("../report.html", "Author workspace"), ("../reader/", "Read with context"),
            ("../companion/", "Companion only"), ("../../guides/first-look.html", "Short tour")))
        notice = ('<details class="panel"><summary>About this synthetic reading example</summary>'
            '<p>The people, records and incident are invented. Reveal context deliberately with the reading-progress control. '
            'All content included in a static file remains inspectable; chapter caps remove later material before export.</p>'
            '<p>The map and harbour view are public-domain setting references from circa 1900, not evidence of the fictional 1923 incident. '
            '<a href="../../assets/research/sources.json">Image credits and reviewed provenance</a>. '
            'The ordinary product export has the same reading interface and no visitor counter.</p></details>')
        document = document.replace("<footer>", notice + "<footer>", 1)
        files = {**bundle.files, "index.html": _finalize(document).encode("utf-8")}
        files.pop("manifest.json")
        manifest = {**bundle.manifest,
            "disclosures": [*bundle.manifest["disclosures"],
                "The reviewed public wrapper adds navigation, canonical metadata and visual credits; no analytics."],
            "files": {name: {"sha256": sha256(content).hexdigest(), "byte_length": len(content)}
                      for name, content in sorted(files.items())}}
        SiteManifest.model_validate(manifest)
        files["manifest.json"] = (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
        directory = root / "docs/demo" / mode
        directory.mkdir(parents=True, exist_ok=True)
        for name, content in files.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(content)
        outputs[mode] = directory / "index.html"
    return outputs


def build_research_fixture(work_dir: Path, *, language: str = "en",
                           nda_project_name: str = "") -> dict:
    """Create the disposable research example through the ordinary project API."""
    work_dir.mkdir(parents=True, exist_ok=True)
    research_proj = work_dir / "research-demo"
    if research_proj.exists():
        shutil.rmtree(research_proj)
    from lixity.research import api as research_api

    manuscript_bytes = DEMO_MANUSCRIPT.read_bytes()
    research_api.init(research_proj, title=manuscript_title(manuscript_bytes.decode("utf-8")), language="en")
    (research_proj / "lixity.toml").write_text(
        'author_name = "Example Author"\n\n[characters.Mara]\n\n[characters.Ivo]\n\n[characters.Hansen]\n',
        encoding="utf-8",
    )
    source_text = """## Section 1: Port Authority Log – October 1923

At ten ten on the evening of October 14, 1923, the night watchman reported two unidentified figures attempting to force the external lock at the eastern gate of Warehouse 4.
The autumn mist obscured the water beyond the quay lamps. The figures ran towards the basin when challenged. No customs seals on the inner warehouse doors were broken.

## Preliminary entry: dictated before the transfer

Officer Hansen opened the crate beside the gate and found forty bundles of untaxed tobacco. The abandoned crate was prepared for transfer to the customs station at dawn.

## Follow-up: station inspection, October 15

Correction to the preliminary entry: the crate was first opened at the customs station at six ten. The count of forty tobacco bundles belongs to that inspection, not to the quay. Hansen signed this amendment after checking the transfer sheet.

A loose base board shifted while the crate was moved away from the drain. One lid plank cracked. The damaged lid was bound to prevent spillage; opening was deferred until arrival at the station. Mara identified the blood on the lid as hers. A blue label fragment and the older board number seventeen were retained separately.

## Witness limits

The watchman saw the two figures leave towards the basin. Mara saw a launch light and heard its engine after the light disappeared. Neither witness saw a crate loaded aboard, identified passengers or recovered a tool. The proposed crowbar and launch connection remain unconfirmed.
"""
    customs_file = work_dir / "customs_log_1923.txt"
    customs_file.write_text(source_text, encoding="utf-8")
    customs_res = research_api.ingest(
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
        "Wet cobblestones reflect a lamp more clearly than a face. From the eastern gate, "
        "the lamp lights the lock and crate but leaves the water in darkness. An engine "
        "can remain audible after the launch light disappears. This does not establish a route or boarding.\n\n"
        "## Office notebook: two entries for cart seventeen\n\n"
        "Mara copied a dispatch at eight in the evening. The ledger also lists cart seventeen "
        "as returned at six forty that evening, without a receiving signature. The earlier "
        "entry is squeezed into the margin. Reused boards, a copied number or a later ledger "
        "entry could explain the discrepancy; the notebook does not identify a culprit.\n\n"
        "## Reference limits\n\n"
        "These invented notes support a fictional scene; they are not historical evidence. "
        "The circa-1900 map and 1890–1900 harbour view are setting references. They cannot "
        "establish the lamp position, weather, warehouse layout or journey on this invented night in 1923.\n",
        encoding="utf-8",
    )
    weather_res = research_api.ingest(
        research_proj,
        weather_file,
        title="Harbor Weather Notes (synthetic)",
        context={
            "genre": "Fictional setting and office notes",
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

    def retained_passage(source: dict, phrase: str) -> str:
        return next(passage["id"] for passage in source["passages"] if phrase in passage["verbatim"])

    customs_source = research_api.get_source(research_proj, customs_res["source_id"])
    weather_source = research_api.get_source(research_proj, weather_res["source_id"])
    passage_id = retained_passage(customs_source, "night watchman reported two unidentified figures")
    early_inspection = retained_passage(customs_source, "opened the crate beside the gate")
    corrected_inspection = retained_passage(customs_source, "crate was first opened at the customs station")
    damaged_lid = retained_passage(customs_source, "opening was deferred until arrival")
    witness_limits = retained_passage(customs_source, "Neither witness saw a crate loaded aboard")
    weather_passage = retained_passage(weather_source, "Mist covered the harbor")
    visibility_passage = retained_passage(weather_source, "An engine can remain audible")
    receipt_passage = retained_passage(weather_source, "ledger also lists cart seventeen")

    # Read-only browser responses below are serialized from this disposable,
    # API-created archive. The dashboard itself is the real controls UI.
    dossier_res = research_api.create_dossier(
        research_proj,
        title="Warehouse 4 case notes",
        body="Fictional case file for the six-chapter harbour story. Times and testimony belong to the invented case.\n\n"
        "## Timeline\n\n"
        "| Time | Working sequence | Status |\n| --- | --- | --- |\n"
        "| 14 October, 18:40 | Cart seventeen entered as returned | Receiving signature missing |\n"
        "| 20:00 | Mara copies the dispatch | Crate not seen by Mara |\n"
        "| 22:10 | Watchman calls for customs | Two figures leave towards the basin |\n"
        "| Before dawn | Cracked lid bound; crate transferred | Contents still unknown to Mara |\n"
        "| 15 October, 06:10 | Station inspection counts tobacco | Corrected log entry |\n\n"
        "## Accounts to compare\n\n"
        "The preliminary customs entry places the opening beside the gate. The signed follow-up "
        "moves it to the station. Preserve both passages: the correction changes the author’s "
        "working interpretation, not the retained earlier wording. The launch is heard, but boarding is not observed.\n\n"
        "## Open Questions\n\n"
        "- Who entered the return before Mara copied the dispatch?\n"
        "- Does seventeen identify this crate, a cart, or a reused board?\n"
        "- Why did Ivo reach for the label, and who told him to keep the gate clear?\n"
        "- Is the blank receiving line an omission or a deliberate removal?\n\n"
        "## Scene decisions\n\n"
        "Keep the crate closed on the quay. Let handling account for the blood and cracked plank. "
        "Introduce the number before the office scene; end with the missing signature rather than naming a culprit.\n\n"
        "## Evidence trail\n\nThese are explicit author associations, not automatic fact checks.\n\n"
        "```mermaid\nflowchart LR\n subgraph Retained evidence\n  P[Customs log passage]\n end\n"
        " P --> C[Authored claim]\n C --> Q[Manuscript quotation]\n C --> D[Author decision]\n```\n\n"
        "## Historical map\n\nCirca-1900 reference; not evidence of the invented 1923 incident.\n\n"
        "## Historical harbour view\n\n1890–1900 photochrom reference; not a photograph of the fictional event.",
        tags=["Warehouse", "Timeline"],
        evidence_ids=[passage_id, early_inspection, corrected_inspection, damaged_lid, receipt_passage],
        geography=json.loads((BASE_DIR / "docs/research/examples/harbour-geography.json").read_text(encoding="utf-8")),
    )
    weather_dossier = research_api.create_dossier(
        research_proj,
        title="Harbor setting notes",
        body="Fictional atmosphere and sightline notes. The weather and setting are fictional examples, not verified historical claims.\n\n"
        "## Weather\n\nMist closes the water view before it silences the launch. Rain has begun after the office closes; "
        "the covered cart seat can register as a small unexplained detail. Wet boots and a cold stove carry the night into the office scene.\n\n"
        "## Visibility and sound\n\n"
        "| Position | Available impression | Limit |\n| --- | --- | --- |\n"
        "| Quay lamp | Lock scratches, label, blood | Does not illuminate a face across the basin |\n"
        "| Eastern gate | Launch light, then engine | No witnessed boarding or cargo transfer |\n"
        "| Office desk | Paper edges, ink, ledger entries | Similar paper does not identify a sender |\n\n"
        "## Scene Planning\n\nUse the long harbour sentences before the short rescue beats. "
        "Keep Ivo’s movements visible without supplying his thoughts. Mara tries the label against her receipt; "
        "the edges do not fit. The later ledger discrepancy must therefore remain a question, not a solved identification.\n\n"
        "## Revision question\n\n"
        "Does chapter 2's shorter rhythm fit the action? Compare “A board moved. Mara turned.” with "
        "chapter 1's harbour description. Short sentences separate the physical actions; the longer opening "
        "lets Mara notice the quay before she has to act. This is an authored contrast, not a model's finding of good pace.\n\n"
        "A useful review can end with keeping those beats. If the passage feels mechanically chopped when read aloud, "
        "try joining an action to its consequence and compare the reading again. Neither shorter sentences nor "
        "matching the manuscript median is a goal. The measurement identifies what was counted; the author decides what works.\n\n"
        "## Reference boundaries\n\nThe historical map and harbour image establish their own dated visual context. "
        "The approximate walking and driving sketches are author-entered examples, not calculated routes or sightlines.\n\n"
        "## Next research questions\n\nWhich details of customs procedure need historical checking before a longer novel uses them? "
        "Could an actual warehouse layout support these movements? Leave both questions open in this fictional demonstration.\n\n"
        "## Reader introduction\n\nThe harbour in this story is an invented place within a real city's visual history. "
        "The quay, office and Warehouse 4 belong to the fiction. The old map and harbour view below offer a wider setting, "
        "rather than a plan of the characters' movements.\n\n"
        "## Reader weather\n\nLight reaches the lock more clearly than the water. Beyond the quay lamp, a sound may remain "
        "distinct after its source has disappeared into the mist. Keep that difference in mind as the witnesses describe the night.\n\n"
        "## Reader witness limits\n\nSeeing a light, hearing an engine and seeing someone board a boat are different observations. "
        "The three quay chapters leave gaps between them. The companion does not fill those gaps with an unseen journey.\n\n"
        "## Reader final clue\n\nA blank signature is an absence, not a name. The two ledger entries, reused board and torn paper "
        "leave several possible connections. The morning handover preserves the question instead of identifying a culprit.",
        tags=["Weather", "Setting"],
        evidence_ids=[weather_passage, visibility_passage, receipt_passage, witness_limits],
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
        statement="The watchman reports intact seals on the inner warehouse doors, despite scratches on the external lock.",
        confidence="hypothetical", time_period="1922–1924", place="Hamburg Free Port Zone",
        dossier_id=dossier_res["dossier_id"],
    )
    research_api.create_claim(
        research_proj,
        title="Harbour tour research notes",
        statement="A future research visit could check the fictional warehouse layout against dated plans and surviving buildings.",
        confidence="hypothetical", time_period="present day", place="Hamburg",
    )
    claim_res = research_api.create_claim(
        research_proj,
        title="Attempted warehouse entry",
        statement="The customs log describes an attempted entry at Warehouse 4 in October 1923.",
        confidence="evidenced", time_period="1923", place="Hamburg Free Port Zone",
        actors=["Night watchman", "Customs officers"], dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=claim_res["claim_id"], passage_id=passage_id,
        relation="supports", rationale="The initial fictional log reports the attempted entry; it does not identify the people.",
    )
    inspection = research_api.create_claim(
        research_proj, title="Where the crate was opened",
        statement="Hansen opened the crate on the quay before it was transferred to the customs station.",
        confidence="hypothetical", time_period="1923-10-14", place="Eastern quay",
        dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=inspection["claim_id"], passage_id=early_inspection,
        relation="supports", rationale="The preliminary entry places the inspection beside the gate.",
    )
    research_api.link_evidence(
        research_proj, claim_id=inspection["claim_id"], passage_id=corrected_inspection,
        relation="contradicts", rationale="The signed correction explicitly places the first opening at the station.",
    )
    research_api.revise_record(
        research_proj, "claim", inspection["claim_id"], expected_revision=1,
        changes={"statement": "The crate was first opened at the customs station after dawn; the preliminary quay inspection entry was corrected.",
                 "confidence": "evidenced", "time_period": "1923-10-15", "place": "Customs station"},
        change_kind="supersession", reason="Prefer the signed follow-up while preserving the earlier interpretation and its conflicting citations.",
    )
    research_api.link_evidence(
        research_proj, claim_id=inspection["claim_id"], passage_id=corrected_inspection,
        relation="supports", rationale="This citation is explicitly linked to the revised interpretation, not silently transferred from version 1.",
    )
    lid = research_api.create_claim(
        research_proj, title="The cracked lid delayed inspection",
        statement="The damaged lid was bound for transport, and opening was deferred until the station.",
        confidence="evidenced", time_period="1923-10-14 / 1923-10-15", place="Eastern quay",
        dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=lid["claim_id"], passage_id=damaged_lid, relation="supports",
        rationale="The follow-up records the cracked plank, binding and deferred opening in the fictional sequence.",
    )
    receipt = research_api.create_claim(
        research_proj, title="The missing receiving signature",
        statement="Cart seventeen appears as returned before the dispatch Mara copied; the missing signature leaves the connection unresolved.",
        confidence="hypothetical", time_period="1923-10-14", place="Warehouse office",
        actors=["Mara", "Foreman"], dossier_id=dossier_res["dossier_id"],
    )
    research_api.link_evidence(
        research_proj, claim_id=receipt["claim_id"], passage_id=receipt_passage, relation="contextualizes",
        rationale="The fictional working notebook keeps several explanations open; it does not identify a culprit.",
    )
    research_api.create_claim_relation(
        research_proj, lid["claim_id"], inspection["claim_id"], relation="causes",
        rationale="Author interpretation for the scene: securing the damaged lid moves the inspection to the station. This link does not verify causality.",
    )
    manuscript = research_proj / "harbour-manuscript.md"
    manuscript.write_bytes(manuscript_bytes)
    manuscript_hash = sha256(manuscript_bytes).hexdigest()
    for claim_id, revision, query in (
        (claim_res["claim_id"], 1, "Someone had tried the eastern gate of Warehouse 4."),
        (claim_res["claim_id"], 1, "Fresh scratches crossed the lock"),
        (lid["claim_id"], 1, "One plank cracked."),
        (inspection["claim_id"], 2, "The crate was first opened at the customs station at six ten."),
        (receipt["claim_id"], 1, "Cart seventeen: returned, six forty in the evening."),
    ):
        anchor = research_api.resolve_manuscript_anchor(research_proj, manuscript, query=query)
        research_api.link_manuscript_claim(
            research_proj, manuscript, claim_id, claim_revision=revision,
            selection={key: anchor[key] for key in ("start_line", "end_line", "paragraph_sha256", "start", "end", "quote")},
            expected_project_id=anchor["project_id"], expected_snapshot=anchor["snapshot"],
            expected_source_sha256=manuscript_hash, allow_retention=True,
            note="Explicit author association in a synthetic manuscript; not evidence that the fictional incident happened.",
        )
    research_api.revise_record(
        research_proj, "claim", claim_res["claim_id"], expected_revision=1,
        changes={"statement": "The customs log reports an attempted entry at Warehouse 4 in October 1923; the implement, people and launch connection remain unconfirmed."},
        change_kind="correction", reason="Distinguish the reported attempt from unobserved details; preserve both manuscript associations at their reviewed version 1.",
    )
    research_api.link_evidence(
        research_proj, claim_id=claim_res["claim_id"], passage_id=passage_id,
        relation="supports", rationale="The current wording describes the report, not independent verification of this invented incident.",
    )
    research_api.link_evidence(
        research_proj, claim_id=claim_res["claim_id"], passage_id=witness_limits,
        relation="qualifies", rationale="The witnesses do not establish a weapon, passengers or the launch connection.",
    )
    research_api.record_decision(
        research_proj, title="Keep the inspection at dawn",
        rationale="Use the signed station correction while preserving the contradictory preliminary entry in the research record.",
        claim_id=inspection["claim_id"], dossier_ids=[dossier_res["dossier_id"]],
        impact_on_plot="The crate stays closed through the quay scenes; the formal note reveals the tobacco after transfer.",
    )
    research_api.record_decision(
        research_proj, title="Move the discovery scene",
        rationale="Let Mara arrive before customs so her handling changes the physical evidence; this is an explicit fictional staging choice.",
        claim_id=claim_res["claim_id"], dossier_ids=[dossier_res["dossier_id"], weather_dossier["dossier_id"]],
        deviation_from_fact=True,
        impact_on_plot="The cut, cracked plank and label make her an involved witness rather than a distant observer.",
    )
    research_api.record_decision(
        research_proj, title="Leave the receiving signature blank",
        rationale="The two ledger entries and reused board support a question, not a solved identification.",
        claim_id=receipt["claim_id"], dossier_ids=[dossier_res["dossier_id"], weather_dossier["dossier_id"]],
        impact_on_plot="Mara stops the foreman closing the book; the unresolved receiving line ends the story.",
    )
    from lixity.config import prepare_project_settings

    current_case = research_api.get_dossier(research_proj, dossier_res["dossier_id"])
    prepare_project_settings(research_proj, {"site_publications": {"readers": {
        "title": "Warehouse 4 — a reader's companion",
        "introduction": "Keep this context beside the story. Choose the last chapter you have finished to reveal the notes prepared for that point.",
        "entries": [
            {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader introduction", "title": "The harbour around the story", "reveal_after_chapter": 0},
            {"dossier_id": dossier_res["dossier_id"], "revision": current_case["revision"], "section": "Historical map", "title": "A map from another time", "reveal_after_chapter": 0},
            {"dossier_id": dossier_res["dossier_id"], "revision": current_case["revision"], "section": "Historical harbour view", "title": "The harbour in colour", "reveal_after_chapter": 0},
            {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader weather", "title": "Light and sound", "reveal_after_chapter": 1},
            {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader witness limits", "title": "What a witness can tell", "reveal_after_chapter": 3},
            {"dossier_id": weather_dossier["dossier_id"], "revision": 1, "section": "Reader final clue", "title": "The receiving signature", "reveal_after_chapter": 6},
        ],
    }}}).commit()
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
        "project_name": nda_project_name or manuscript_title(manuscript_bytes.decode("utf-8")),
        "date": "2026-10-06", "place": "Example City",
    }
    research_fixture = {
        **image_resources,
        "/api/nda-draft": {
            "fields": nda_fields,
            "text": draft_document(research_proj, **nda_fields, language=language).text,
        },
        # Synthetic server-local paths demonstrate the chooser without exposing a user's home.
        "/api/project-paths": {
            "ok": True, "path": "/home/demo/warehouse-4", "parent": "/home/demo",
            "entries": [
                {"name": "research", "path": "/home/demo/warehouse-4/research", "kind": "directory"},
                {"name": "harbour-manuscript.md", "path": "/home/demo/warehouse-4/harbour-manuscript.md", "kind": "manuscript"},
            ],
            "truncated": False,
        },
        "/api/research/status": {
            "ok": True,
            "initialized": True,
            "project_root": "./warehouse-4",
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
        "/api/research/matrix?format=md": {
            "text": research_api.render_claim_matrix(research_api.claim_matrix_data(research_proj), format="md")},
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
    evidence_data = research_api.list_evidence_links(research_proj)
    relations_data = research_api.list_claim_relations(research_proj)
    for kind, records in (("dossier", dossiers_data["dossiers"]), ("claim", claims_data["claims"]),
                          ("decision", decisions_data["decisions"]), ("evidence_link", evidence_data["evidence_links"]),
                          ("claim_relation", [{"id": relation["relation_id"]} for relation in relations_data["relations"]])):
        for item in records:
            identifier = quote(item["id"], safe="")
            endpoint = "?kind=" + kind + "&id=" + identifier
            research_fixture["/api/research/record" + endpoint] = {"ok": True, **research_api.get_record(research_proj, kind, item["id"])}
            if kind in ("claim", "dossier"):
                context_query = urlencode({"project_token": RESEARCH_DEMO_MANUSCRIPT_CONTEXT,
                                           "id": item["id"], "kind": kind})
                research_fixture["/api/research/record?" + context_query] = research_fixture["/api/research/record" + endpoint]
            history = research_api.record_history(research_proj, kind, item["id"])
            research_fixture["/api/research/history" + endpoint] = {"ok": True, **history}
            for version in history["revisions"]:
                retained = {
                    "ok": True, **research_api.get_record(research_proj, kind, item["id"], revision=version["revision"])}
                research_fixture["/api/research/record" + endpoint + "&revision=" + str(version["revision"])] = retained
                if kind in ("claim", "dossier"):
                    query = urlencode({"project_token": RESEARCH_DEMO_MANUSCRIPT_CONTEXT,
                                       "id": item["id"], "kind": kind, "revision": version["revision"]})
                    research_fixture["/api/research/record?" + query] = retained
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
    # The native companion binds dossier reads to the selected manuscript.
    for url, value in list(research_fixture.items()):
        if url == "/api/research/dossiers" or url.startswith("/api/research/dossiers?id="):
            extra = "&" + url.partition("?")[2] if "?" in url else ""
            research_fixture["/api/research/dossiers?project_token=" + RESEARCH_DEMO_MANUSCRIPT_CONTEXT + extra] = value
    # Exact aliases preserve the native context-bound GET URLs without making
    # the public adapter strip arbitrary parameters or emulate a live server.
    research_fixture.update({
        url + ("&" if "?" in url else "?") + "research_token=" + RESEARCH_DEMO_CONTEXT: value
        for url, value in list(research_fixture.items())
        if url.startswith("/api/research/") and url not in image_resources
    })
    return research_fixture


def sync_embedded_image_sizes() -> int:
    """Update embedded and social/structured image sizes from their local PNG.

    The screenshots are regenerated independently of the pages that embed
    them; without this step a re-render silently leaves stale attributes
    behind. Returns the number of corrected image references.
    """
    from build_examples import SITE

    pattern = re.compile(r"<img\s+([^>]*?)/?>", re.DOTALL)
    meta_pattern = re.compile(r"<meta\s+([^>]*?)/?>", re.DOTALL)
    structured_pattern = re.compile(r'(<script\s+type="application/ld\+json"[^>]*>)(.*?)(</script>)', re.DOTALL)
    attributes = re.compile(r'(\w+)="([^"]*)"')
    docs = (BASE_DIR / "docs").resolve()
    sizes: dict[Path, tuple[int, int] | None] = {}

    def image_size(source: str, document: Path) -> tuple[int, int] | None:
        source = html.unescape(source)
        if source.startswith(SITE + "/"):
            image = docs / source.removeprefix(SITE + "/")
        elif not source or source.startswith(("http:", "https:", "data:", "blob:")):
            return None
        else:
            image = document.parent / source
        image = image.resolve()
        if not image.is_relative_to(docs):
            return None
        if image not in sizes:
            try:
                with image.open("rb") as content:
                    header = content.read(24)
            except OSError:
                header = b""
            sizes[image] = (struct.unpack(">II", header[16:24])
                            if len(header) == 24 and header[:8] == b"\x89PNG\r\n\x1a\n" else None)
        return sizes[image]

    corrected = 0
    for document in sorted(docs.glob("**/*.html")):
        markup = document.read_text(encoding="utf-8")
        changed = False
        for match in list(pattern.finditer(markup)):
            values = dict(attributes.findall(match.group(1)))
            source = values.get("src", "")
            dimensions = image_size(source, document)
            if dimensions is None:
                continue
            width, height = dimensions
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

        head, boundary, body = markup.partition("</head>")
        metadata = [dict(attributes.findall(match[1])) for match in meta_pattern.finditer(head)]
        dimensions_by_key = {}
        for prefix in ("og", "twitter"):
            source = next((item.get("content", "") for item in metadata
                           if item.get("property", item.get("name")) == prefix + ":image"), "")
            dimensions = image_size(source, document)
            if dimensions:
                dimensions_by_key.update({prefix + ":image:width": dimensions[0], prefix + ":image:height": dimensions[1]})

        def update_meta(match, dimensions_by_key=dimensions_by_key):
            nonlocal corrected, changed
            values = dict(attributes.findall(match[1]))
            size = dimensions_by_key.get(values.get("property", values.get("name")))
            if size is None or values.get("content") == str(size):
                return match[0]
            corrected += 1
            changed = True
            return re.sub(r'content="[^"]*"', f'content="{size}"', match[0], count=1)

        def update_structured(match, document=document):
            nonlocal corrected, changed
            value = json.loads(match[2])
            count = 0

            def update_image(node):
                nonlocal count
                if isinstance(node, list):
                    for child in node:
                        update_image(child)
                elif isinstance(node, dict):
                    kind = node.get("@type")
                    if kind == "ImageObject" or (isinstance(kind, list) and "ImageObject" in kind):
                        dimensions = image_size(node.get("url", ""), document)
                        if dimensions and (node.get("width"), node.get("height")) != dimensions:
                            node.update(width=dimensions[0], height=dimensions[1])
                            count += 1
                    for child in node.values():
                        update_image(child)

            update_image(value)
            if not count:
                return match[0]
            corrected += count
            changed = True
            raw = match[2]
            leading = raw[:len(raw) - len(raw.lstrip())]
            trailing = raw[len(raw.rstrip()):]
            encoded = json.dumps(value, ensure_ascii=False, indent=2 if "\n" in raw.strip() else None)
            return match[1] + leading + encoded + trailing + match[3]

        head = meta_pattern.sub(update_meta, head)
        head = structured_pattern.sub(update_structured, head)
        markup = head + boundary + body
        if changed:
            document.write_text(markup, encoding="utf-8")
    return corrected


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate README screenshots.")
    parser.add_argument("--manuscript", default="samples/first-look.md",
                        help="Analysis screenshot manuscript override; research captures keep the canonical Warehouse 4 project.")
    parser.add_argument("--only", nargs="+", help="Capture only these screenshot filenames.")
    parser.add_argument("--video", action="store_true", help="Record the short guided walkthroughs instead of stills.")
    args = parser.parse_args()
    CAPTURES.clear()

    manuscript = (BASE_DIR / args.manuscript).resolve()
    text = manuscript.read_text(encoding="utf-8")
    config, resolved = resolve_document_config(text, "auto", project_config={})
    is_en = resolved.key == "en"
    title = manuscript_title(text, manuscript.stem)

    thresholds = resolve_thresholds(project_config={})
    analysis = analyze_document(text, config, thresholds, include_evidence=True)
    metrics, fingerprint = analysis.metrics, analysis.fingerprint
    paragraphs, chapters = analysis.paragraphs, analysis.chapters

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Screenshots from {manuscript.relative_to(BASE_DIR)} ({resolved.key})")
    if manuscript != DEMO_MANUSCRIPT:
        print("Research workspace captures use the canonical Warehouse 4 manuscript independently of the analysis override.")

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
        f'<pre style="white-space:pre-wrap;overflow-wrap:anywhere">{passport}</pre>',
        OUT_DIR / "cli-style.png",
        1320,
        860,
    )

    # 3. Dashboard (light, top area) --------------------------------------
    status = [
        {"key": "exports", "state": "ok", "detail": "none generated" if is_en else "keine erzeugt"},
        {"key": "markers", "state": "ok", "detail": "no open markers" if is_en else "keine offenen"},
    ]
    char_names = ["Mara", "Ivo", "Hansen"] if manuscript == DEMO_MANUSCRIPT else []
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
        reader_document=reader_blocks(text, config, paragraphs),
        fingerprint=fingerprint,
        paragraph_evidence=analysis.evidence,
        status=status,
        dialogue=dialogue_report(text, config).to_dict(),
        characters=presence_report(text, char_names, config) if char_names else None,
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
    marker_reviews = (
        (0, "pruefen", "Check the gate observation against the retained log"),
        (5, "sachcheck", "Keep the invented journey separate from historical imagery"),
        (11, "todo", "Review the quay conversation's attribution"),
        (18, "achtung", "Distinguish the inspection note from its interpretation"),
        (27, "pruefen", "Confirm the dawn handover sequence"),
    )
    markers_spec = tuple(
        (paragraphs[min(index, len(paragraphs) - 1)].start_line, kind, note)
        for index, kind, note in marker_reviews
    ) if paragraphs else ()
    for line, kind, note in markers_spec:
        marked, _ = add_marker(marked, kind=kind, note=note, target_line=line)
    marked_analysis = analyze_document(marked, config, thresholds, include_evidence=True)
    marked_metrics = marked_analysis.metrics
    marked_paragraphs, marked_chapters = marked_analysis.paragraphs, marked_analysis.chapters
    from lixity.markers import list_markers

    marked_dashboard = render_dashboard(
        marked_chapters,
        marked_paragraphs,
        metrics=marked_metrics,
        reader_document=reader_blocks(marked, config, marked_paragraphs),
        fingerprint=marked_analysis.fingerprint,
        paragraph_evidence=marked_analysis.evidence,
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
        reader_document=reader_blocks(marked, config, marked_paragraphs),
        fingerprint=marked_analysis.fingerprint,
        paragraph_evidence=marked_analysis.evidence,
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
    _queue_capture(editorial_path, OUT_DIR / "dashboard-flags-dark.png", 1152, 501)
    _queue_capture(editorial_path, OUT_DIR / "dashboard-editorial.png", 1480, 760)

    # 7. Style layer (opening chapter with sentence-length emphasis) ------
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
    build_research_demo(BASE_DIR, research_proj)
    build_publication_examples(BASE_DIR, research_proj)
    _write_html("research-workspace-fixture.json", json.dumps(research_fixture, ensure_ascii=False))
    research_workspace = _write_html(
        "dashboard-research-workspace.html",
        render_research_workspace(
            research_fixture, enabled_actions=NATIVE_UI_ACTIONS,
            project_author="Example Author", author_setting_enabled=True,
            identity_check=manuscript_identity_check(
                DEMO_MANUSCRIPT.read_text(encoding="utf-8"),
                manuscript_title(DEMO_MANUSCRIPT.read_text(encoding="utf-8")), "Example Author"),
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
        f"$ lixity research search --project ./warehouse-4 --query \"warehouse customs\" --limit 1\n"
        f"{json.dumps(search_res, indent=2)}\n\n"
        f"$ lixity research cite --project ./warehouse-4 --passage {passage_id}\n"
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
        CAPTURES[:] = [
            {
                "source": str(research_workspace),
                "target": str(OUT_DIR / "dashboard-research-timeline.png"),
                "width": 1280, "height": 800, "video": True,
                "videoTarget": str(video_dir / "research-timeline.webm"),
            },
            {
                "source": str(dashboard_path),
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
