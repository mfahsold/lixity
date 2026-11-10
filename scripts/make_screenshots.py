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
import tempfile
from hashlib import sha256
from pathlib import Path
from urllib.parse import quote, urlencode

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR / "src"))
sys.path.insert(0, str(BASE_DIR))

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
from scripts.example_project import DEMO_MANUSCRIPT, manuscript_title  # noqa: E402
from scripts.example_publications import build_publication_examples, build_research_demo  # noqa: E402
from scripts.stage_pages import screenshot_manifest  # noqa: E402

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
    # Full native widgets are the default. Explicit excerpts are bounded by
    # complete component selectors in the browser capture definitions.
    final_target = target
    if target.suffix == ".webp":
        target = WORK_DIR / "webp-captures" / target.with_suffix(".png").name
        target.parent.mkdir(parents=True, exist_ok=True)
    CAPTURES.append({
        "source": str(source), "target": str(target), "finalTarget": str(final_target), "width": width, "height": height,
        "maxHeight": max_height,
    })


def _reviewed_capture_name(capture: dict[str, str | int]) -> str:
    return Path(str(capture.get("finalTarget", capture["target"]))).name


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


def build_research_fixture(work_dir: Path, *, language: str = "en",
                           nda_project_name: str = "") -> dict:
    """Adapt an ordinary disposable example project for screenshot HTTP reads."""
    work_dir.mkdir(parents=True, exist_ok=True)
    research_proj = work_dir / "research-demo"
    if research_proj.exists():
        shutil.rmtree(research_proj)
    from lixity.research import api as research_api
    from scripts.example_project import create_example_project

    created = create_example_project(research_proj)
    manuscript = research_proj / "harbour-manuscript.md"
    manuscript_bytes = manuscript.read_bytes()
    image_resources = created["image_resources"]
    claim_res = {"claim_id": created["primary_claim_id"]}
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
            "ok": True, **research_api.review_manuscript_links(research_proj, manuscript, include_context=True)},
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
    from scripts.example_publications import SITE

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


def sync_screenshot_catalog() -> None:
    """Render the public image table from the shared catalog, without a second list."""
    images = screenshot_manifest(BASE_DIR / "docs")
    path = OUT_DIR / "README.md"
    text = path.read_text(encoding="utf-8")
    start, end = "<!-- catalog:start -->", "<!-- catalog:end -->"
    before, rest = text.split(start, 1)
    _old, after = rest.split(end, 1)
    rows = ["| Task | View | Role and scope |", "| --- | --- | --- |"]
    rows.extend(f"| {item['question']} | [{item['file']}]({item['file']}) | {item['role']}: {item['caption']} |"
                for item in images)
    path.write_text(before + start + "\n\n" + "\n".join(rows) + "\n\n" + end + after, encoding="utf-8")


def build_outreach_package(source: Path, output: Path) -> None:
    """Prepare one unpublished asset handoff; never touch accounts or the send queue."""
    if output.exists() or output.is_symlink():
        raise FileExistsError(output)
    images = [item for item in screenshot_manifest(source) if item["role"] in {"lead", "support"}]
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required to identify the package source revision")
    commit = subprocess.check_output([git, "rev-parse", "HEAD"], cwd=BASE_DIR, text=True).strip()  # noqa: S603 -- resolved Git, fixed arguments
    dirty = bool(subprocess.check_output([git, "status", "--porcelain", "--untracked-files=normal"],  # noqa: S603 -- fixed read-only arguments
                                         cwd=BASE_DIR, text=True).strip())
    manifest = {"schema_version": "lixity-outreach-assets/1", "state": "draft-unpublished",
                "source_commit": commit, "source_dirty": dirty, "source_version": __version__,
                "images": []}
    lines = ["# Lixity outreach package", "", "Prepared assets only. No account, queue or publication changes.",
             "Source commit: " + commit + (" (working tree has changes)." if dirty else "."), "",
             "Choose one reader question and one matching image per post. Do not send every alternative.", ""]
    with tempfile.TemporaryDirectory(prefix=".lixity-outreach-", dir=output.parent) as temporary:
        prepared = Path(temporary) / "package"
        (prepared / "images").mkdir(parents=True)
        for item in images:
            content = (source / "screenshots" / item["file"]).read_bytes()
            (prepared / "images" / item["file"]).write_bytes(content)
            manifest["images"].append({**item, "sha256": sha256(content).hexdigest(), "byte_length": len(content)})
            lines.extend(["## " + item["question"], "", "Image: images/" + item["file"],
                          "Alt: " + item["alt"], "Caption: " + item["caption"],
                          "Destination: https://mfahsold.github.io/lixity/" + item["destination"], ""])
        (prepared / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (prepared / "README.md").write_text("\n".join(lines), encoding="utf-8")
        prepared.rename(output)


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate README screenshots.")
    parser.add_argument("--manuscript", default="samples/first-look.md",
                        help="Analysis screenshot manuscript override; research captures keep the canonical Warehouse 4 project.")
    parser.add_argument("--only", nargs="+", help="Capture only these screenshot filenames.")
    parser.add_argument("--video", action="store_true", help="Record the short guided walkthroughs instead of stills.")
    parser.add_argument("--outreach-package", type=Path, help="Build one unpublished asset package in a new directory, without recapturing.")
    args = parser.parse_args()
    if args.outreach_package:
        if args.only or args.video or args.manuscript != "samples/first-look.md":
            parser.error("Package preparation cannot be combined with capture options")
        build_outreach_package(BASE_DIR / "docs", args.outreach_package)
        return 0
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

    # Dashboard reading and analysis views.
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
    for name in ("dashboard-reader-focus.png", "dashboard-measurement-focus.png"):
        _queue_capture(dashboard_path, OUT_DIR / name, 760, 820)
    _queue_capture(dashboard_path, OUT_DIR / "dashboard-mobile.png", 390, 1028)
    for view in ("project-settings", "project-import"):
        _queue_capture(dashboard_path, OUT_DIR / f"dashboard-{view}.png", 1480, 1050)
    _queue_capture(dashboard_path, OUT_DIR / "dashboard-dark.png", 1480, 945)
    _queue_capture(dashboard_path, OUT_DIR / "dashboard-heatmap.png", 1750, 1000)

    # Editorial still and walkthrough share one marked manuscript.
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
    _queue_capture(editorial_path, OUT_DIR / "dashboard-editorial.png", 1480, 760)

    research_fixture = build_research_fixture(WORK_DIR, language=resolved.key, nda_project_name=title)
    research_proj = WORK_DIR / "research-demo"
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
    for view in ("dossiers", "search", "claims", "timeline", "decisions", "review"):
        _queue_capture(research_workspace, OUT_DIR / f"dashboard-research-{view}.png", 1480, 1000)
    for visual in ("image", "photo", "geography", "diagram", "image-zoom"):
        suffix = "webp" if visual in ("photo", "image-zoom") else "png"
        _queue_capture(research_workspace, OUT_DIR / f"dashboard-dossier-{visual}.{suffix}", 1480, 1000)
    _queue_capture(research_workspace, OUT_DIR / "dashboard-dossier-image-mobile.webp", 390, 1000)

    if args.video:
        video_dir = WORK_DIR / "videos"
        video_dir.mkdir(parents=True, exist_ok=True)
        CAPTURES[:] = [
            {
                "source": str(research_workspace),
                "target": str(OUT_DIR / "dashboard-light.png"),
                "width": 1440, "height": 900, "video": True,
                "videoTarget": str(video_dir / "product-tour.webm"),
            },
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
        if args.only:
            CAPTURES[:] = [capture for capture in CAPTURES
                          if Path(str(capture["videoTarget"])).stem in args.only]
            if not CAPTURES:
                parser.error("No matching video capture")
    else:
        approved = {item["file"] for item in screenshot_manifest(BASE_DIR / "docs")}
        available = {_reviewed_capture_name(capture) for capture in CAPTURES}
        if approved - available:
            parser.error("Reviewed images lack capture definitions: " + ", ".join(sorted(approved - available)))
        CAPTURES[:] = [capture for capture in CAPTURES if _reviewed_capture_name(capture) in approved]
    if args.only and not args.video:
        requested = set(args.only)
        available = {_reviewed_capture_name(capture) for capture in CAPTURES}
        missing = requested - available
        if missing:
            parser.error("Unknown screenshot filenames: " + ", ".join(sorted(missing)))
        CAPTURES[:] = [capture for capture in CAPTURES
                       if _reviewed_capture_name(capture) in requested]

    manifest = WORK_DIR / "captures.json"
    manifest.write_text(json.dumps(CAPTURES), encoding="utf-8")
    node = shutil.which("node")
    if node is None:
        raise SystemExit("Node.js is required for Playwright screenshot capture.")
    subprocess.run(  # noqa: S603
        [node, str(BASE_DIR / "scripts/capture_screenshots.cjs"), str(manifest)], check=True,
        timeout=420,
    )
    for capture in CAPTURES:
        target = Path(str(capture.get("finalTarget", capture["target"])))
        if target.suffix == ".webp":
            ffmpeg = shutil.which("ffmpeg")
            if ffmpeg is None:
                raise SystemExit("FFmpeg is required to encode reviewed WebP screenshots.")
            subprocess.run(  # noqa: S603 - paths are generated by the capture definitions
                [ffmpeg, "-v", "error", "-y", "-i", str(capture["target"]),
                 "-c:v", "libwebp", "-quality", "95", str(target)], check=True)

    # Social previews use the final capture dimensions. Build the publication
    # and its checksums together, rather than mutating a checksummed HTML member.
    build_research_demo(BASE_DIR, research_proj)
    build_publication_examples(BASE_DIR, research_proj)
    sync_screenshot_catalog()
    corrected = sync_embedded_image_sizes()
    print(
        f"Done – {len(list(OUT_DIR.glob('*.png')))} screenshots in {OUT_DIR}"
        + (f"; {corrected} embedded image size(s) synced" if corrected else "")
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
