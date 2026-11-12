"""Reviewed Pages wrappers around ordinary project exports.

Project creation and screenshot HTTP fixtures belong to separate modules. Only
reviewed synthetic manuscript bytes may enter these public project examples.
"""
from __future__ import annotations

import html
import json
import re
import struct
from hashlib import sha256
from pathlib import Path

from lixity import __version__
from scripts.example_project import DEMO_MANUSCRIPT, manuscript_title, reviewed_visual_sources

ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = ROOT
SITE = "https://mfahsold.github.io/lixity"
OG_IMAGE_ALT = "Lixity continuous manuscript reader with chapter navigation and contextual tools"
LICENSE_URL = "https://github.com/mfahsold/lixity/blob/main/LICENSE"


def _finalize(report: str) -> str:
    return "\n".join(line.rstrip() for line in report.splitlines()) + "\n"


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(message)


def _analytics_endpoint(root: Path) -> str | None:
    """Derive the demo's narrow image policy from its reviewed public config."""
    try:
        config = json.loads((root / "docs/assets/analytics.json").read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    if not isinstance(config, dict) or "site_code" not in config:
        raise ValueError("Public analytics configuration must declare site_code")
    code = config["site_code"]
    if code is None:
        return None
    if not isinstance(code, str) or not re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", code):
        raise ValueError("Public analytics site_code must be a hosted GoatCounter subdomain")
    return f"https://{code}.goatcounter.com/count"


def _head_metadata(
    *,
    canonical: str,
    title: str,
    description: str,
    language: str,
    about: tuple[str, str] | None = None,
    preview_image: tuple[str, str] | None = None,
    analytics: bool = True,
) -> str:
    escaped = html.escape(description, quote=True)
    escaped_title = html.escape(title, quote=True)
    image_path, image_alt = preview_image or ("screenshots/dashboard-light.png", OG_IMAGE_ALT)
    image_url = f"{SITE}/{image_path}"
    image_header = (ROOT / "docs" / image_path).read_bytes()[:24]
    _require(image_header[:8] == b"\x89PNG\r\n\x1a\n", "the preview image must be a PNG")
    width, height = struct.unpack(">II", image_header[16:24])
    structured: dict[str, object] = {
        "@context": "https://schema.org",
        "@type": "TechArticle",
        "headline": title,
        "description": description,
        "url": canonical,
        "mainEntityOfPage": canonical,
        "image": {"@type": "ImageObject", "url": image_url, "width": width, "height": height,
                  "caption": image_alt},
        "inLanguage": language,
        "author": {
            "@type": "Person",
            "name": "Matthias Fahsold",
            "url": "https://github.com/mfahsold",
        },
        "isPartOf": {"@type": "WebSite", "name": "Lixity", "url": f"{SITE}/"},
        "license": LICENSE_URL,
    }
    if about is not None:
        structured["about"] = {
            "@type": "Book",
            "name": about[0],
            "author": {"@type": "Person", "name": about[1]},
        }
    return (
        f'<link rel="canonical" href="{canonical}"/>\n'
        + ('<script defer src="../assets/analytics.js"></script>\n' if analytics else '')
        + f'<meta name="description" content="{escaped}"/>\n'
        '<meta property="og:type" content="article"/>\n'
        '<meta property="og:site_name" content="Lixity"/>\n'
        f'<meta property="og:title" content="{escaped_title}"/>\n'
        f'<meta property="og:description" content="{escaped}"/>\n'
        f'<meta property="og:url" content="{canonical}"/>\n'
        f'<meta property="og:image" content="{image_url}"/>\n'
        f'<meta property="og:image:width" content="{width}"/>\n'
        f'<meta property="og:image:height" content="{height}"/>\n'
        f'<meta property="og:image:alt" content="{html.escape(image_alt, quote=True)}"/>\n'
        '<meta name="twitter:card" content="summary_large_image"/>\n'
        f'<meta name="twitter:title" content="{escaped_title}"/>\n'
        f'<meta name="twitter:description" content="{escaped}"/>\n'
        f'<meta name="twitter:image" content="{image_url}"/>\n'
        f'<meta name="twitter:image:alt" content="{html.escape(image_alt, quote=True)}"/>\n'
        '<script type="application/ld+json">\n'
        + json.dumps(structured, ensure_ascii=False)
        + "\n</script>\n"
    )


def _replace_title(report: str, title: str) -> str:
    head = report.partition("</head>")[0]
    match = re.search(r"<title>[^<]*</title>", head)
    _require(match is not None, "the dashboard must carry one title element")
    _require(head.count("<title>") == 1, "the dashboard head must carry exactly one title")
    return report.replace(match.group(0), f"<title>{html.escape(title)}</title>", 1)


def _insert_notice(report: str, notice: str) -> str:
    _require(report.count("</header>") == 1, "the dashboard must carry exactly one header")
    # Public explanation belongs to the document, outside the native project rail.
    shell = '<div class="workspace-shell">'
    if shell in report:
        # The renderer emits this boundary after the complete shell and status
        # strip. Its position does not depend on nested action disclosures.
        boundary = "<!--dashboard-freshness-->"
        _require(report.count(shell) == report.count(boundary) == 1,
                 "the workspace must carry one shell and one content boundary")
        content_start = report.index(boundary)
        _require(content_start > report.index(shell), "workspace content must follow the shell")
        return report[:content_start] + notice + report[content_start:]
    return report.replace("</header>", "</header>" + notice, 1)


def _notice(heading: str, paragraphs: list[str], links: list[tuple[str, str]]) -> str:
    body = "\n".join(f"<p>{text}</p>" for text in paragraphs)
    anchors = "\n".join(f'<a href="{href}">{label}</a>' for href, label in links)
    return f"""
<section class="panel" id="example-context" aria-labelledby="example-heading">
<h2 id="example-heading">{heading}</h2>
{body}
<div class="license-links">{anchors}</div>
</section>
"""


def _site_navigation(
    report: str, title: str, *, demo: bool = False, breadcrumbs: bool = True,
    links: tuple[tuple[str, str], ...] | None = None,
) -> str:
    """Keep public examples connected without adding external report assets."""
    stylesheet = (ROOT / "docs/assets/site.css").read_text(encoding="utf-8")
    start, end = "/* Public navigation start */", "/* Public navigation end */"
    _require(stylesheet.count(start) == stylesheet.count(end) == 1,
             "the shared public navigation stylesheet must have one bounded block")
    styles = stylesheet.partition(start)[2].partition(end)[0]
    navigation = (
        '<nav class="site-return" aria-label="Lixity navigation">'
        '<a href="../">About Lixity</a>'
        '<span class="demo-context">Read-only demo · Fictional manuscript · '
        '<a href="../guides/installation.html">Install local app</a></span>'
        '</nav>'
    ) if demo else (
        '<nav class="site-return" aria-label="Lixity navigation">'
        '<a href="../">Home</a><a href="../#guides">Guides</a>'
        '<a href="../blog/index.html">Articles</a>'
        '<a href="../demo/report.html">Demo</a>'
        '</nav>'
    )
    if links is not None:
        navigation = '<nav class="site-return" aria-label="Lixity navigation">' + ''.join(
            f'<a href="{html.escape(href, quote=True)}">{html.escape(label)}</a>' for href, label in links) + '</nav>'
    if breadcrumbs and not demo:
        navigation += (
            '<nav class="site-breadcrumbs" aria-label="Breadcrumb"><ol>'
            '<li><a href="../">Home</a></li>' +
            f'<li><span aria-current="page">{html.escape(title)}</span></li></ol></nav>'
        )
    if not re.search(r'<body\b[^>]*\bid="top"', report):
        report = re.sub(r'<body(?=\s|>)', '<body id="top"', report, count=1)
    _require(report.count('<body id="top"') == 1, "the report must have one top target")
    report = report.replace('<body id="top"', '<body id="top" tabindex="-1"', 1)
    report, class_count = re.subn(
        r'(<body\b[^>]*\bclass=")([^"]*)"',
        lambda match: match[1] + match[2] + ' site-page"', report, count=1,
    )
    _require(class_count == 1, "the report must retain its native body class")
    page = re.search(r'<div class="page"(?: id="[^"]*")?>', report)
    _require(page is not None, "the report must have one page container")
    if page is not None:
        report = report[:page.end()] + navigation + report[page.end():]
    report = report.replace('</head>', '<style>' + styles + '</style></head>', 1)
    return report.replace('</body>', '<a class="site-back-top" href="#top">Back to top ↑</a></body>', 1)


def build_research_demo(root: Path, project: Path) -> Path:
    """Wrap the production website export of the reviewed synthetic project."""
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
    document = document.replace("</head>", restrictions + head + "</head>", 1)
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
        f"Generated from the development checkout (base version {__version__}). This page cannot import, edit or save records.",
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
        '<section class="panel" id="demo-quick-start" aria-labelledby="demo-quick-start-title">'
        '<h2 id="demo-quick-start-title">Why the short sentences?</h2>'
        '<p class="ctl-note">Development preview · Read a passage or explore its research.</p>'
        '<div class="row">'
        '<a class="ctl primary" href="#ch-2" data-jump="#ch-2" data-layer="asl">Inspect chapter 2</a>'
        '<button class="ctl" type="button" data-switch-view="research">Explore research</button>'
        '</div>'
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
        '</details></section>'
    )
    # Keep the example prompt inside the real Manuscript view so the existing
    # workspace navigation hides it in Research and restores its disclosure state.
    document, count = re.subn(r'(<div\b[^>]*\bid="view-pane-analysis"[^>]*>)',
                              lambda match: match.group(1) + quick_start, document)
    if count != 1:
        raise ValueError("The demo must retain one native Manuscript view")
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


def build_publication_examples(root: Path, project: Path) -> dict[str, Path]:
    """Publish two reviewed synthetic profiles through the production exporter.

    The reader includes all six chapters; the standalone companion is capped at
    chapter three. The reviewed audio is imported into the disposable project
    before export. Neither reading website includes analytics.
    """
    from lixity.site_contracts import SiteManifest
    from lixity.site_export import prepare_site
    from lixity.speech_artifacts import retain_chapter_audio

    manuscript = project / "harbour-manuscript.md"
    if manuscript.read_bytes() != DEMO_MANUSCRIPT.read_bytes():
        raise ValueError("Public publications require the reviewed synthetic manuscript")
    audio_source = BASE_DIR / "docs/assets/audio/warehouse-4-chapter-1.wav"
    audio = audio_source.read_bytes()
    provenance = json.loads(audio_source.with_suffix(".json").read_text(encoding="utf-8"))
    if (provenance.get("schema_version") != "lixity-demo-audio/1" or provenance.get("chapter") != 1
            or provenance.get("source_sha256") != sha256(manuscript.read_bytes()).hexdigest()
            or provenance.get("audio_sha256") != sha256(audio).hexdigest()
            or provenance.get("generator", {}).get("name") != "eSpeak NG"):
        raise ValueError("Regenerate and review the synthetic chapter audio before building publications")
    # This is an explicit external recording import into the disposable demo
    # project. It never uses private author references or a running worker.
    retain_chapter_audio(project, audio, source_sha256=provenance["source_sha256"],
                         chapter=1, origin="imported")
    outputs = {}
    for mode, cap in (("reader", None), ("companion", 3)):
        bundle = prepare_site(project, manuscript=manuscript, mode=mode,
            publication_profile="readers", max_chapter=cap, include_source_files=True,
            analysis_sections=["chapters"] if mode == "reader" else [], include_audio=mode == "reader")
        document = bundle.files["index.html"].decode("utf-8")
        title = "Warehouse 4 — " + ("read with context" if mode == "reader" else "a reader's companion")
        description = ("Read six fictional harbour chapters with context you reveal as you read." if mode == "reader" else
                       "Explore a fictional harbour's setting beside your book; this companion contains no novel text and stops at chapter three.")
        metadata = _head_metadata(canonical=f"{SITE}/demo/{mode}/index.html", title=title,
            description=description, language="en", analytics=False)
        document = document.replace("</head>", metadata + "</head>", 1)
        document = _site_navigation(document, title, demo=True, breadcrumbs=False, links=(
            ("../report.html", "Author workspace"), ("../reader/", "Read with context"),
            ("../companion/", "Companion only"), ("../../guides/first-look.html", "Short tour"),
            ("../../guides/installation.html", "Install app")))
        notice = ('<details class="panel"><summary>About this synthetic reading example</summary>'
            '<p>The people, records and incident are invented. Reveal context deliberately with the reading-progress control. '
            'All content included in a static file remains inspectable; chapter caps remove later material before export.</p>'
            + ('<p>Choose <strong>Analysis</strong> above the reading view for a chapter overview, then '
               '<strong>Back to reading copy</strong> to return. This example includes all six chapters; '
               'the analysis is not hidden by reading progress.</p>'
               '<p><strong>Chapter audio</strong> contains the complete first chapter, synthesized with the generic '
               'eSpeak NG English voice and imported through the ordinary chapter-audio path. Press Play to listen '
               'or download the WAV. This demonstrates the export workflow, not neural voice quality; no human '
               'voice reference is used and the other five chapters have no audio.</p>' if mode == "reader" else '') +
            '<p>The map and harbour view are public-domain setting references from circa 1900, not evidence of the fictional 1923 incident. '
            '<a href="../../assets/research/sources.json">Image credits and reviewed provenance</a>. '
            'The ordinary product export has the same reading interface and no visitor counter. '
            'To export your own manuscript with private offline reading websites, '
            '<a href="../../guides/installation.html">install the local Lixity workspace</a>.</p></details>')
        document = document.replace("<footer>", notice + "<footer>", 1)
        files = {**bundle.files, "index.html": _finalize(document).encode("utf-8")}
        if mode == "reader":
            analysis = files["analysis.html"].decode("utf-8")
            analysis_metadata = _head_metadata(
                canonical=f"{SITE}/demo/reader/analysis.html",
                title="Warehouse 4 — chapter analysis",
                description="Explore selected chapter measurements for the synthetic Warehouse 4 reading copy.",
                language="en", analytics=False)
            analysis = analysis.replace("</head>", analysis_metadata + "</head>", 1)
            files["analysis.html"] = _finalize(analysis).encode("utf-8")
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
