#!/usr/bin/env python3
"""Regenerate the published read-only example reports.

Five reading examples are published on the documentation site:

* ``demo/report.html`` - one synthetic six-chapter analysis/research project;
* ``demo/reader/index.html`` - its curated manuscript/context reading website;
* ``demo/companion/index.html`` - a standalone companion capped at chapter three;
* ``examples/effi-briest.html`` - the opening chapters of a public-domain novel;
* ``examples/pride-and-prejudice.html`` - the opening chapters of a public-domain novel.

The project also includes five manuscript/analysis PDF layouts and a bounded
static research fixture. Its former research URL is a compatibility redirect.
The two classic works also ship as complete analysis reports
(``examples/<slug>-report.pdf``). The Effi Briest excerpt additionally demonstrates
the shared editorial, reading and submission PDF layouts. Every HTML page carries canonical and social
metadata plus an explicit provenance notice; private manuscripts and local
project configuration never enter these files. The script fails when an
example grows beyond a size the site should ship.
"""

from __future__ import annotations

import html
import json
import re
import struct
import sys
from dataclasses import dataclass
from pathlib import Path

from lixity import __version__
from lixity.api import dashboard
from lixity.pdf_export import compose_pdf

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://mfahsold.github.io/lixity"
OG_IMAGE_ALT = "Lixity continuous manuscript reader with chapter navigation and contextual tools"
LICENSE_URL = "https://github.com/mfahsold/lixity/blob/main/LICENSE"

#: A published example stays a quick page load; past this size the excerpt is
#: cut further instead of shipping a multi-megabyte HTML document. The shared
#: chapter inspection, media, export, review, literal-code handling, research
#: identity, terminology, localized diagnostics, contextual hints, association
#: review, dossier collections and terms review add a bounded 112 kB allowance.
MAX_PAGE_BYTES = 1_612_000


@dataclass(frozen=True)
class ClassicExample:
    """One public-domain work that is published as an excerpt and a full report."""

    slug: str
    source: str
    language: str
    title: str
    author: str
    chapters: int
    gutenberg: str
    description: str


EXAMPLES = (
    ClassicExample(
        slug="effi-briest",
        source="samples/effi-briest.md",
        language="de",
        title="Effi Briest",
        author="Theodor Fontane",
        chapters=3,
        gutenberg="https://www.gutenberg.org/ebooks/5323",
        description=(
            "A read-only Lixity analysis of the opening chapters of Theodor Fontane's "
            "Effi Briest: sentence rhythm, vocabulary, tense flags and dialogue measures, "
            "computed offline without an account."
        ),
    ),
    ClassicExample(
        slug="pride-and-prejudice",
        source="samples/pride-and-prejudice.md",
        language="en",
        title="Pride and Prejudice",
        author="Jane Austen",
        chapters=3,
        gutenberg="https://www.gutenberg.org/ebooks/1342",
        description=(
            "A read-only Lixity analysis of the opening chapters of Jane Austen's "
            "Pride and Prejudice: sentence rhythm, vocabulary, tense flags and dialogue "
            "measures, computed offline without an account."
        ),
    ),
)


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
        '<span class="demo-context">Read-only demo · Fictional manuscript</span>'
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


def build_demo(root: Path) -> Path:
    """Build the one public project through the shared native workspace builder."""
    from tempfile import TemporaryDirectory

    from make_screenshots import (
        build_publication_examples,
        build_research_demo,
        build_research_fixture,
    )

    with TemporaryDirectory(prefix="lixity-public-demo-") as directory:
        build_research_fixture(Path(directory))
        project = Path(directory) / "research-demo"
        demo = build_research_demo(root, project)
        build_publication_examples(root, project)
        return demo


def excerpt(text: str, chapters: int) -> str:
    """Keep the front matter and the first chapters of a public-domain work."""
    parts = re.split(r"(?m)^(?=## )", text)
    return "".join(parts[: chapters + 1]).rstrip() + "\n"


def build_classic(root: Path, example: ClassicExample) -> tuple[Path, Path]:
    text = (root / example.source).read_text(encoding="utf-8")
    canonical = f"{SITE}/examples/{example.slug}.html"
    report = dashboard(
        excerpt(text, example.chapters),
        language=example.language,
        project_config={},
        title=example.title,
    )
    report = _replace_title(report, f"Lixity example report — {example.title}")
    _require(report.count("</head>") == 1, "the dashboard must carry exactly one head")
    head = _head_metadata(
        canonical=canonical,
        title=f"Lixity example report — {example.title}",
        description=example.description,
        language=example.language,
        about=(example.title, example.author),
    )
    report = report.replace("</head>", head + "</head>", 1)
    notice = _notice(
        f"Public-domain example: {example.title}",
        [
            (
                f"<strong>Generated with Lixity {__version__}.</strong> The dashboard shows "
                f"the first {example.chapters} chapters of {example.title} "
                f"({example.author}); the complete work is available as a "
                f'<a href="{example.slug}-report.pdf">PDF analysis report</a>.'
            ),
            (
                "The opening chapters are reproduced from a public-domain Project Gutenberg "
                "edition. The report uses the real chapter, paragraph and style interactions "
                "of the renderer, without server functions; it accepts no uploads and saves "
                "no edits."
            ),
            (
                "Short excerpts and language-dependent heuristics support human review. This "
                "example is not a benchmark, a calibration corpus or a literary quality "
                "verdict."
            ),
        ],
        [
            (example.gutenberg, "Source: Project Gutenberg"),
            (f"{example.slug}-report.pdf", "Complete PDF report"),
            ("../guides/first-look.html", "Three-minute walkthrough"),
            (LICENSE_URL, "AGPL-3.0-or-later"),
        ],
    )
    report = _insert_notice(report, notice)
    report = _site_navigation(report, example.title)
    page = root / f"docs/examples/{example.slug}.html"
    page.parent.mkdir(parents=True, exist_ok=True)
    page.write_text(_finalize(report), encoding="utf-8")
    if page.stat().st_size > MAX_PAGE_BYTES:
        raise SystemExit(f"{page} exceeds the published example size budget")
    pdf = compose_pdf(
        text,
        manuscript=example.source,
        layout="report",
        language=example.language,
        title=example.title,
        author=example.author,
        project_config={},
    )
    target = root / f"docs/examples/{example.slug}-report.pdf"
    target.write_bytes(pdf)
    return page, target


def main() -> int:
    demo = build_demo(ROOT)
    outputs: list[tuple[Path, str]] = [
        (demo, f"{demo.stat().st_size:,} bytes"),
        (ROOT / "LICENSE", ""),
    ]
    for mode in ("reader", "companion"):
        page = ROOT / f"docs/demo/{mode}/index.html"
        outputs.append((page, f"{page.stat().st_size:,} bytes"))
    for example in EXAMPLES:
        page, pdf = build_classic(ROOT, example)
        outputs.append((page, f"{page.stat().st_size:,} bytes"))
        outputs.append((pdf, f"{pdf.stat().st_size:,} bytes"))
    example = EXAMPLES[0]
    text = excerpt((ROOT / example.source).read_text(encoding="utf-8"), example.chapters)
    first_chapter = re.search(r"(?m)^##\s+", text)
    _require(first_chapter is not None, "the manuscript PDF example needs a chapter opening")
    # This curated excerpt starts at chapter one; entered title/author supply its cover.
    text = text[first_chapter.start():] if first_chapter is not None else text
    for layout in ("editor", "book", "sheet"):
        target = ROOT / f"docs/examples/{example.slug}-{layout}.pdf"
        target.write_bytes(compose_pdf(
            text, manuscript=example.source, layout=layout, language=example.language,
            title=example.title, author=example.author, project_config={},
        ))
        outputs.append((target, f"{target.stat().st_size:,} bytes"))
    for path, size in outputs:
        if size:
            print(f"{path.relative_to(ROOT)}: {size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
