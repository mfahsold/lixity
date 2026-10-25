# Lixity

[![Checks: local-first](https://img.shields.io/badge/checks-local--first-blue)](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

**Find the passages worth a second look.**

Lixity is a local research and revision workbench for authors and editors using
Markdown or plain-text manuscripts. Why does a chapter sound different? Is that
repetition deliberate? Which source supports a detail?
Choose one question, inspect what was counted and read the passage before deciding
what to keep or change. Saved research links lead separately to dossiers, source
passages and author decisions. Lixity does not grade or rewrite your prose.

[Open the example manuscript](https://mfahsold.github.io/lixity/demo/report.html) ·
[Take the short tour](https://mfahsold.github.io/lixity/guides/first-look.html) ·
[Install Lixity](https://mfahsold.github.io/lixity/guides/installation.html)

[Einstieg auf Deutsch](https://mfahsold.github.io/lixity/guides/first-look-de.html)

<a href="https://mfahsold.github.io/lixity/screenshots/dashboard-reader-focus.png"><img src="https://mfahsold.github.io/lixity/screenshots/dashboard-reader-focus.png" width="560" alt="Warehouse 4 reader excerpt with chapter navigation, reading settings and Analysis Off"/></a>

Start with the passage. This current-main excerpt shows the native reader with
analysis off; [open the complete workspace view](https://mfahsold.github.io/lixity/screenshots/dashboard-light.png).

The read-only example follows a suspicious harbour delivery through six invented
English chapters, linked case notes and credited research images. It needs no
account or upload and cannot import, edit or save.
Try one question first: **does chapter 2's shorter rhythm fit its action?**
The demo's **Inspect chapter 2** action opens the actual manuscript with the
shared sentence-length controls, not a separate presentation.

**One question, one dossier, back to the scene.** A preliminary log puts a crate's
opening on the quay; its correction moves it to the customs station. The fictional
demo keeps both source passages beside an explicit author decision: leave the
crate closed until dawn. [Follow the research decision in German](https://mfahsold.github.io/lixity/guides/first-look-de.html#recherche)
or [take the English walkthrough](https://mfahsold.github.io/lixity/guides/first-look.html#decision).

## From a passage to the context behind it

| When you want to… | Lixity helps you… |
| :--- | :--- |
| Understand a change in rhythm or voice | Compare chapters against your own manuscript's patterns, then inspect the counted text. |
| Decide whether a repetition needs attention | Locate nearby phrase echoes, read their context and keep or revise them yourself. |
| Revisit the research behind a line | Follow explicitly linked claims and dossiers to retained source passages, images and author decisions. |
| Resume reading without losing context | Keep a dossier alongside the manuscript or return from a research entry to the original passage. |
| Prepare a copy for someone else | Choose a PDF, a review workspace, or a reading website with selected notes; check its scope and try it on the reader’s device. |

Source evidence, authored claims and creative decisions stay distinct.
Links can preserve exact earlier revisions; a newer record does not silently
replace the version used. A retained source is not a guarantee of factual truth.

<a id="start-here"></a>

## Install and start

Install [uv](https://docs.astral.sh/uv/), then run on Windows, macOS or Linux:

```bash
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Open a new terminal:

```bash
lixity --version
lixity service start --open
```

Choose **Open Project** or **Analyze a manuscript**, then confirm the language.
Manuscript input supports `.md`, `.markdown` and `.txt`; convert Word/DOCX or
Scrivener documents before import. Retaining a PDF as research is a separate action.
English is the default; automatic detection is explicit. Built-in analysis works
offline on your computer and does not grade or rewrite prose. Optional
integrations have separate
[data boundaries](https://mfahsold.github.io/lixity/research/USAGE.md).

[Your first project](https://mfahsold.github.io/lixity/ONBOARDING.md) explains the
workflow. [Installation and updates](https://mfahsold.github.io/lixity/INSTALLATION.md)
covers launchers, pinned wheels, service management and removal. After upgrading,
run `lixity service restart --open` and reload the browser; installing a package
does not update an already running service.

## What you can do

- **Manuscript & Analysis.** Open paragraph values and work markers, or compare
  chapters against the manuscript's own patterns and review local phrase echoes.
  Analysis can be turned on and off.
- **Research & Dossiers.** Link retained sources, authored claims and decisions
  to exact manuscript quotations. Keep source images, maps and dated claims with
  the dossier beside a passage; Zotero remains your collection tool. Retention is explicit,
  and archive integrity does not establish factual truth.
- **Project & exports.** Manage project metadata and create editorial, reading,
  submission or analysis PDFs, terminal reports and versioned JSON. Export a
  review website, a novel with curated companion material, or a standalone
  companion. Reveal notes after a confirmed chapter, or omit later material
  entirely for an excerpt.
  NDA generation creates a draft without
  recording consent or signatures; dossier Markdown edits require explicit preview
  and apply. See [export and project limits](https://mfahsold.github.io/lixity/USAGE.md).

The browser app, CLI and Python API share one analysis pipeline;
`lixity --help` and `lixity about --json` describe installed capabilities.

Try the same fictional project as a
[novel with companion notes](https://mfahsold.github.io/lixity/demo/reader/index.html)
or a [standalone companion](https://mfahsold.github.io/lixity/demo/companion/index.html).
These curated reading copies are different from the analysis/research workspace:
they contain selected material, not the full archive.

<details>
<summary>Analysis controls, revision-aware research and project inspection</summary>

Turn **Analysis** on beside the text and choose the visible metric. Switch
**Counted text** and **Paragraph comparison** independently. Violet underlines identify
counted spans; blue/orange value-and-arrow markers compare notable paragraphs
with their chapter. Both preferences persist in the browser. Hover, touch and the
paragraph menu explain the concrete text; the CLI exposes the same evidence with
`lixity profile manuscript.md --layer asl --evidence`.

**Current main (unreleased):** matrix cells and style-space loadings share
chapter measurements: meaning, units, manuscript reference and the other
metrics of the same chapter. Reading the text is an explicit next action;
chapter-only measurements do not invent word-level highlights.

Current-main `export-site --preflight` and the native **Check export** action
measure the prepared package before writing/downloading, including media not
packaged and missing attribution fields. Reading website exports are beta and
can be large; the check does not promise a package size or mobile performance. Existing research projects require the
[explicit manifest-storage migration](https://mfahsold.github.io/lixity/research/USAGE.md#migrate-manifest-storage)
before using the current compressed layout.

Current main also shares versioned image, PDF and MP4/WebM attachments across
dossiers and reading copies, with explicit retention and source-file export
choices. [Media workflow and compatibility](https://mfahsold.github.io/lixity/research/USAGE.md#retain-a-pdf-or-video-in-a-dossier).

A passage's research associations open its claims and dossier beside the
manuscript, with a return to the passage. Current entries and exact linked earlier
versions remain distinct. Dossier editing offers `--body-only` section drafts and
`--compact` update receipts. Current-main `--preamble` targets the opening text,
`research media-context` corrects retained-media attribution without copying bytes,
and `dossier-images --missing-provenance` finds absent attribution fields; see the
[section-editing workflow](https://mfahsold.github.io/lixity/research/USAGE.md#work-on-one-dossier-section).
The native **Project overview** and `lixity project --project PATH` also separate
sources, existing outputs and read-only structure findings. They neither move
files nor establish that an output matches the current manuscript; see
[project inspection](https://mfahsold.github.io/lixity/USAGE.md#inspect-project-structure).

CLI workflows can reuse the project's configured manuscript;
[default manuscript guidance](https://mfahsold.github.io/lixity/USAGE.md#default-manuscript)
explains explicit project selection and settings scope.

</details>

English and German have the broadest analysis resources. French, Spanish,
Italian, Portuguese and Dutch offer localized interfaces with narrower heuristic
coverage. [Language support](https://mfahsold.github.io/lixity/LOCALIZATION.md) and
[interpretation](https://mfahsold.github.io/lixity/guides/interpretation.html)
explain coverage, short-sample limits and unavailable measurements.

## Documentation map

[Additional screenshots and image credits](https://mfahsold.github.io/lixity/screenshots/README.md).

| Looking for | Start here |
| :--- | :--- |
| Everyday use | [Usage and CLI reference](https://mfahsold.github.io/lixity/USAGE.md) · [Interpret results](https://mfahsold.github.io/lixity/guides/interpretation.html) |
| Research | [Workflows and compatibility](https://mfahsold.github.io/lixity/research/USAGE.md) · [Data model](https://mfahsold.github.io/lixity/research/DATA_MODEL.md) |
| Measurements | [Methods](https://mfahsold.github.io/lixity/METHODS.md) · [Checks and limits](https://mfahsold.github.io/lixity/STABILITY.md#core-validation-status) |
| Integrations | [API contracts](https://mfahsold.github.io/lixity/AGENTS.md) · [Architecture](https://mfahsold.github.io/lixity/ARCHITECTURE.md) · [Agent index](https://mfahsold.github.io/lixity/llms.txt) |
| Contributing | [Contributor setup and checks](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md) · [Security](https://github.com/mfahsold/lixity/blob/main/SECURITY.md) |

In the repository, [`src/lixity/`](https://github.com/mfahsold/lixity/tree/main/src/lixity)
contains the shared engine, CLI and UI;
[`tests/`](https://github.com/mfahsold/lixity/tree/main/tests) verifies behavior;
[`docs/`](https://github.com/mfahsold/lixity/tree/main/docs) holds maintained product
documentation; and [`samples/`](https://github.com/mfahsold/lixity/tree/main/samples)
contains synthetic or public-domain examples. Book-specific adapters belong in
their own projects.

## Release, citation and license

> **Version line:** The current release is **v0.7.6**, in the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the numbering reset; use the current
> release rather than the numerically largest tag. Product, JSON response and
> archive schema versions are independent.

[Release notes](https://mfahsold.github.io/lixity/releases/v0.7.6.md)
cover archive compatibility and upgrades. See the
[changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) for subsequent work.
The repository's generated demo follows the interface documented here, including
unreleased changes, with a fictional project and read-only research. Importing
and saving require the local app. A push to `main` alone does not deploy Pages
or update a running local installation; see
[update and deployment boundaries](https://mfahsold.github.io/lixity/INSTALLATION.md).

Cite [Lixity on Zenodo](https://doi.org/10.5281/zenodo.23390297), with metadata in
[`CITATION.cff`](https://github.com/mfahsold/lixity/blob/main/CITATION.cff).
The [software paper draft](https://github.com/mfahsold/lixity/blob/main/paper/paper.md)
describes its research context.

**AGPL-3.0-or-later.** Use Lixity for private or commercial writing, research and
teaching, including self-publishing your book. A separate written commercial
license is available for integrations that cannot meet the AGPL.
[Licensing guide](https://mfahsold.github.io/lixity/LICENSING.md) ·
[Full terms](https://github.com/mfahsold/lixity/blob/main/LICENSE) ·
[Legal notice and contact](https://mfahsold.github.io/lixity/#impressum).
