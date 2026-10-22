# Lixity

[![Checks: local-first](https://img.shields.io/badge/checks-local--first-blue)](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![Downloads](https://img.shields.io/pypi/dm/lixity)](https://pypistats.org/packages/lixity)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

Lixity is a local workbench for authors. Explore language patterns and keep
sources, claims and notes beside your manuscript. Try an invented example in
your browser before installing the app for your own writing.

> **Version line:** The current release is **v0.7.5**, in the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the numbering reset; use the current
> release rather than the numerically largest tag. Product, JSON response and
> archive schema versions are independent.

[Open the example manuscript](https://mfahsold.github.io/lixity/demo/report.html) ·
[Take the short tour](https://mfahsold.github.io/lixity/guides/first-look.html) ·
[Install Lixity](https://mfahsold.github.io/lixity/guides/installation.html)

<a href="https://mfahsold.github.io/lixity/screenshots/dashboard-dark.png"><img src="https://mfahsold.github.io/lixity/screenshots/dashboard-dark.png" width="560" alt="Lixity manuscript reader with continuous prose, chapter navigation and contextual tools"/></a>

The read-only example follows a suspicious harbour delivery through six invented
English chapters, linked case notes and credited research images. It needs no
account or upload and cannot import, edit or save.
[More views and image credits](https://mfahsold.github.io/lixity/screenshots/README.md).

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

Turn **Analysis** on beside the text and choose the visible metric. Switch
**Counted text** and **Paragraph comparison** independently. Violet underlines identify
counted spans; blue/orange value-and-arrow markers compare notable paragraphs
with their chapter. Both preferences persist in the browser. Hover, touch and the
paragraph menu explain the concrete text; the CLI exposes the same evidence with
`lixity profile manuscript.md --layer asl --evidence`.

A passage's research associations open its claims and dossier beside the
manuscript, with a return to the passage. Current entries and exact linked earlier
versions remain distinct. Dossier editing offers `--body-only` section drafts and
`--compact` update receipts; see the
[section-editing workflow](https://mfahsold.github.io/lixity/research/USAGE.md#work-on-one-dossier-section).
The native **Project overview** and `lixity project --project PATH` also separate
sources, existing outputs and read-only structure findings. They neither move
files nor establish that an output matches the current manuscript; see
[project inspection](https://mfahsold.github.io/lixity/USAGE.md#inspect-project-structure).

CLI workflows can reuse the project's configured manuscript;
[default manuscript guidance](https://mfahsold.github.io/lixity/USAGE.md#default-manuscript)
explains explicit project selection and settings scope.

English and German have the broadest analysis resources. French, Spanish,
Italian, Portuguese and Dutch offer localized interfaces with narrower heuristic
coverage. [Language support](https://mfahsold.github.io/lixity/LOCALIZATION.md) and
[interpretation](https://mfahsold.github.io/lixity/guides/interpretation.html)
explain coverage, short-sample limits and unavailable measurements.

## Documentation map

| Looking for | Start here |
| :--- | :--- |
| Everyday use | [Usage and CLI reference](https://mfahsold.github.io/lixity/USAGE.md) · [Interpret results](https://mfahsold.github.io/lixity/guides/interpretation.html) |
| Research | [Workflows and compatibility](https://mfahsold.github.io/lixity/research/USAGE.md) · [Data model](https://mfahsold.github.io/lixity/research/DATA_MODEL.md) |
| Measurements | [Methods](https://mfahsold.github.io/lixity/METHODS.md) · [Validation](https://mfahsold.github.io/lixity/STABILITY.md) |
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

[Release notes](https://mfahsold.github.io/lixity/releases/v0.7.5.md)
cover archive compatibility and upgrades. See the
[changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) for subsequent work.
The repository's generated demo follows the interface documented here, including
unreleased changes, with a fictional project and read-only research. Importing
and saving require the local app.

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
