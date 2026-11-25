#!/usr/bin/env python3
"""Regenerate the published read-only example reports.

Five reading examples are published on the documentation site:

* ``demo/report.html`` - one synthetic six-chapter analysis/research project;
* ``demo/reader/index.html`` - its curated manuscript/context reading website;
* ``demo/companion/index.html`` - a standalone companion capped at chapter three;
* ``examples/effi-briest.html`` - the opening chapters of a public-domain novel;
* ``examples/pride-and-prejudice.html`` - the opening chapters of a public-domain novel.

The project also includes five manuscript/analysis PDF layouts, a saved
character dossier PDF and a bounded static research fixture. Its former
research URL is a compatibility redirect.
The two classic works also ship as complete analysis reports
(``examples/<slug>-report.pdf``). The Effi Briest excerpt additionally demonstrates
the shared editorial, reading and submission PDF layouts. Every HTML page carries canonical and social
metadata plus an explicit provenance notice. The script uses approved sample
inputs and enforces the size limits for each HTML output.
"""

from __future__ import annotations

import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

from lixity.api import dashboard
from lixity.pdf_export import compose_pdf

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.check_release import source_version  # noqa: E402
from scripts.example_publications import (  # noqa: E402
    DEMO_DOSSIER_PDF,
    LICENSE_URL,
    SITE,
    _finalize,
    _head_metadata,
    _insert_notice,
    _notice,
    _replace_title,
    _require,
    _site_navigation,
    build_publication_examples,
    build_research_demo,
)

# Each generated HTML page must fit its reviewed budget, including its inline
# application assets. The richer Warehouse 4 exports have their own limits.
MAX_PAGE_BYTES = 1_950_000
DEMO_PAGE_BUDGETS: dict[str, int] = {
    "docs/demo/report.html": 7_500_000,
    "docs/demo/reader/index.html": 1_750_000,
    "docs/demo/companion/index.html": 1_750_000,
}


def check_demo_budgets(root: Path) -> None:
    """Ensure the generated public demo artifacts stay within their size budgets."""
    for relative, budget in DEMO_PAGE_BUDGETS.items():
        page = root / relative
        size = page.stat().st_size
        if size > budget:
            raise SystemExit(
                f"{page} ({size:,} bytes) exceeds the published demo size budget ({budget:,} bytes)"
            )


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


def build_demo(root: Path) -> Path:
    """Build the one public project through the shared native workspace builder."""
    from tempfile import TemporaryDirectory

    with TemporaryDirectory(prefix="lixity-public-demo-") as directory:
        from lixity.research.dossier_pdf import compose_dossier_pdf
        from lixity.research.models import Reference
        from scripts.example_project import create_example_project, save_example_character_dossier

        project = Path(directory).resolve() / "research-demo"
        example = create_example_project(project)
        identifier, revision = save_example_character_dossier(project, example["character_evidence_id"])
        result = compose_dossier_pdf(project, Reference(id=identifier, revision=revision))
        if result is None:
            raise ValueError("The public character dossier revision must be available")
        demo = build_research_demo(root, project, dossier_pdf=result[1])
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
    version = source_version(root)
    notice = _notice(
        f"Public-domain example: {example.title}",
        [
            (
                f"<strong>Development checkout, base version {version}.</strong> The dashboard shows "
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


def _task_build_demo(root: Path) -> list[tuple[Path, str]]:
    demo = build_demo(root)
    check_demo_budgets(root)
    items: list[tuple[Path, str]] = [
        (demo, f"{demo.stat().st_size:,} bytes"),
        (root / "LICENSE", ""),
    ]
    dossier = demo.with_name(DEMO_DOSSIER_PDF)
    items.append((dossier, f"{dossier.stat().st_size:,} bytes"))
    for mode in ("reader", "companion"):
        page = root / f"docs/demo/{mode}/index.html"
        items.append((page, f"{page.stat().st_size:,} bytes"))
    return items


def _task_build_classic(root: Path, example: ClassicExample) -> list[tuple[Path, str]]:
    page, pdf = build_classic(root, example)
    return [
        (page, f"{page.stat().st_size:,} bytes"),
        (pdf, f"{pdf.stat().st_size:,} bytes"),
    ]


def _task_build_layout(
    root: Path, text: str, example: ClassicExample, layout: str
) -> list[tuple[Path, str]]:
    target = root / f"docs/examples/{example.slug}-{layout}.pdf"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(
        compose_pdf(
            text,
            manuscript=example.source,
            layout=layout,
            language=example.language,
            title=example.title,
            author=example.author,
            project_config={},
        )
    )
    return [(target, f"{target.stat().st_size:,} bytes")]


def main() -> int:
    example = EXAMPLES[0]
    text = excerpt((ROOT / example.source).read_text(encoding="utf-8"), example.chapters)
    first_chapter = re.search(r"(?m)^##\s+", text)
    _require(first_chapter is not None, "the manuscript PDF example needs a chapter opening")
    # This curated excerpt starts at chapter one; entered title/author supply its cover.
    text = text[first_chapter.start():] if first_chapter is not None else text

    workers = min(6, max(1, os.cpu_count() or 2))
    with ProcessPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_task_build_demo, ROOT),
            *(pool.submit(_task_build_classic, ROOT, item) for item in EXAMPLES),
            *(pool.submit(_task_build_layout, ROOT, text, example, layout) for layout in ("editor", "book", "sheet")),
        ]
        outputs: list[tuple[Path, str]] = []
        for future in futures:
            outputs.extend(future.result())
    for path, size in outputs:
        if size:
            print(f"{path.relative_to(ROOT)}: {size}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
