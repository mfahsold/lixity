# Lixity

[![tests](https://github.com/mfahsold/lixity/actions/workflows/tests.yml/badge.svg)](https://github.com/mfahsold/lixity/actions)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![Downloads](https://img.shields.io/pypi/dm/lixity)](https://pypistats.org/packages/lixity)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

**See where your manuscript changes. Read before you revise.**

Lixity is a local manuscript analysis tool for authors, editors and researchers.
Read chapters as a continuous document, then inspect sentence rhythm, vocabulary,
dialogue and tense where a passage makes you curious. Keep research beside the
text and ask whether a change serves the scene before deciding what to revise.

![Lixity continuous manuscript reader with chapter navigation and contextual tools](https://mfahsold.github.io/lixity/screenshots/dashboard-dark.png)

[Explore the demo project](https://mfahsold.github.io/lixity/demo/report.html) ·
[Three-minute first look](https://mfahsold.github.io/lixity/guides/first-look.html) ·
[Install](#install-and-start) · [What you can do](#what-you-can-do) ·
[v0.7.2 release notes](https://mfahsold.github.io/lixity/releases/v0.7.2.md)

## Try it in 30 seconds

Open [*The Crate at Warehouse 4*](https://mfahsold.github.io/lixity/demo/report.html):
one read-only project with six invented English chapters. Read the opening setting
and chapter 2's action, open **Values** for passage measurements or **Analysis
overview** for chapter comparisons, then return to the passage. Switch to **Research**
to follow the same story through a dossier, retained sources, a claim and its
saved manuscript quote. Keep a dossier alongside the manuscript, download the
claim-evidence matrix or choose one of four prepared PDF layouts. The three
native workspace views stay visible; actions marked **Local app** are disabled
previews with an [installation link](https://mfahsold.github.io/lixity/guides/installation.html).
The demo cannot import, edit or save. No install, account or upload is needed.
It demonstrates the v0.7.2 reading workflow using invented text and reviewed
historical images.

<a id="start-here"></a>
Built-in analysis runs on your computer. Optional external OCR workers have
separate [data boundaries](https://mfahsold.github.io/lixity/research/OCR_INTEGRATION.md).

## Install and start

Install [uv](https://docs.astral.sh/uv/), then run on Windows, macOS or Linux:

```bash
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Open a new terminal, verify `lixity --version`, then run
`lixity service start --open`. Choose **Open Project** or **Analyze a manuscript**.
The [first-project guide](https://mfahsold.github.io/lixity/ONBOARDING.md) explains the workflow;
[installation and updates](https://mfahsold.github.io/lixity/INSTALLATION.md) covers launchers, pinned wheels,
service management and removal. After upgrading, use `lixity service restart --open`
to reuse recorded launch settings, then reload the browser. Installing a package
does not update an already running service.

## What you can do

| Workflow | Result and next step |
| :--- | :--- |
| Read a manuscript | Continuous chapters, adjustable text size, width and spacing, plus a reversible focus view. [Reader controls](https://mfahsold.github.io/lixity/USAGE.md#reading-paragraphs). |
| Compare chapters | Sentence rhythm, vocabulary, dialogue and tense against the manuscript's own reference. [Read the signals](https://mfahsold.github.io/lixity/guides/interpretation.html). |
| Review passages | Open a paragraph's context tools for measurements, work markers and exact quote associations. [Review workflow](https://mfahsold.github.io/lixity/USAGE.md#start-a-review). |
| Compare intentional registers | Group scenes by purpose and set optional author targets. [Scene registers](https://mfahsold.github.io/lixity/USAGE.md#scene-registers-and-project-targets). |
| Export a manuscript | A4 editorial copy with line numbers and comment margins, A5 reading copy, submission sheet or analysis report. [PDF layouts and limits](https://mfahsold.github.io/lixity/USAGE.md#lixity-pdf). |
| Connect research | Retained sources, authored claims and decisions, dossiers, places, journeys and exact manuscript quotations. [Research guide](https://mfahsold.github.io/lixity/guides/research-pdf.html). |
| Work in a terminal or agent | Readable reports, versioned JSON and installed capability discovery. [CLI workflows](https://mfahsold.github.io/lixity/USAGE.md) · [Automation contracts](https://mfahsold.github.io/lixity/AGENTS.md). |

[More screenshots and short walkthroughs](https://mfahsold.github.io/lixity/screenshots/README.md) show desktop
and mobile views, paragraph notes, settings and the research timeline.

### Research with Zotero

Use Zotero for collecting sources, reading and general research notes. Lixity's
experimental workspace retains selected evidence and connects it to authored
claims, decisions and manuscript quotes. A dossier gathers a topic or scene;
images and structured geography can accompany it. Changing a Zotero attachment
does not change an already retained quotation. An integrity check is not a fact check.

<a href="https://mfahsold.github.io/lixity/screenshots/dashboard-dossier-image.png"><img src="https://mfahsold.github.io/lixity/screenshots/dashboard-dossier-image.png" alt="Historical Hamburg map in a fictional scene dossier, with source provenance" width="900" /></a>

[Open Research in the demo project](https://mfahsold.github.io/lixity/demo/report.html#research-manager) ·
[Workflows and compatibility](https://mfahsold.github.io/lixity/research/USAGE.md) ·
[Places and journeys](https://mfahsold.github.io/lixity/screenshots/dashboard-dossier-geography.png)

**Since v0.7.1:** edit an exported dossier in Markdown, review its
changes against the archive and apply the prepared revision explicitly. Images
and diagrams share a zoom viewer. [Literal character aliases and declared viewpoint chapters](https://mfahsold.github.io/lixity/USAGE.md#character-profiles)
keep name counts separate from author-declared perspective.

Visible maps use OpenStreetMap by default and send
the viewed area and client IP to the tile provider; choose local vectors or the
sketch for offline maps. [Research data boundaries](https://mfahsold.github.io/lixity/research/USAGE.md#keep-places-and-journeys-in-a-dossier).

## How to read the results

Measurements describe patterns, not literary quality. A deliberate change of
voice may differ from the book's baseline. Read the passage before revising;
short samples and missing measurements can leave comparisons unavailable.
[Interpretation](https://mfahsold.github.io/lixity/guides/interpretation.html),
[methods](https://mfahsold.github.io/lixity/METHODS.md) and [validation limits](https://mfahsold.github.io/lixity/STABILITY.md) explain the
models and what their results can support.

Read the workflows: [Intentional registers](https://mfahsold.github.io/lixity/blog/intentional-registers.html) ·
[Local word echoes](https://mfahsold.github.io/lixity/blog/local-word-echoes.html).

## Supported languages

English and German have the broadest analysis resources. French, Spanish,
Italian, Portuguese and Dutch also have localized interfaces and narrower
heuristic coverage. Choose the manuscript language explicitly; documentation
and terminal presentation are separate. [Language settings and limits](https://mfahsold.github.io/lixity/LOCALIZATION.md).

## Documentation map

- [Practical guides](https://mfahsold.github.io/lixity/#guides) — installation,
  interpretation, research and comparisons with other tools.
- [First project](https://mfahsold.github.io/lixity/ONBOARDING.md) · [Installation and updates](https://mfahsold.github.io/lixity/INSTALLATION.md).
- [CLI workflows](https://mfahsold.github.io/lixity/USAGE.md) — use `lixity --help` and
  `lixity COMMAND --help` for the installed commands and options.
- [Automation contracts](https://mfahsold.github.io/lixity/AGENTS.md) · [Research workflows](https://mfahsold.github.io/lixity/research/USAGE.md).
- [Methods](https://mfahsold.github.io/lixity/METHODS.md) · [Stability](https://mfahsold.github.io/lixity/STABILITY.md) ·
  [Architecture](https://mfahsold.github.io/lixity/ARCHITECTURE.md) · [Localization](https://mfahsold.github.io/lixity/LOCALIZATION.md).
- [Agent index](https://mfahsold.github.io/lixity/llms.txt) · [Full documentation bundle](https://mfahsold.github.io/lixity/llms-full.txt).

## Current release

The current release is **v0.7.2**, continuing the pre-1.0 development line;
historical v3.0.1 and earlier tags remain available. Product and schema versions
are independent. This release reads research archives through v8; geographic
saves opt into v8, which older readers cannot open. See [Release notes](https://mfahsold.github.io/lixity/releases/v0.7.2.md)
for compatibility and upgrading from historical numbering, and the
[changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) for subsequent work on `main`.

## Python API and automation

```python
from lixity import api

html = api.dashboard(text, language="de", project_config={})
```

CLI, Python and dashboard analysis share one pipeline. Pass explicit project
settings for multi-project integrations and inspect `lixity about --json` for
installed capabilities. [Interface contracts](https://mfahsold.github.io/lixity/AGENTS.md) define result schemas;
[architecture](https://mfahsold.github.io/lixity/ARCHITECTURE.md#configuration-and-multiple-projects) explains
reusing one analysis result for several outputs.

## Research

Matthias Fahsold developed Lixity as an architect and developer at ROST Services
GmbH and used it while writing his own debut novel. The methods and the tool's
placement among stylometry and corpus tools are
described in the software paper draft under [`paper/`](https://github.com/mfahsold/lixity/blob/main/paper/paper.md),
prepared for the [Journal of Open Source Software](https://joss.theoj.org/).
Released versions are archived on Zenodo: cite the concept DOI
[`10.5281/zenodo.23390297`](https://doi.org/10.5281/zenodo.23390297) (see [`CITATION.cff`](https://github.com/mfahsold/lixity/blob/main/CITATION.cff));
every release also receives its own version DOI.

## License

Lixity is **open source under the AGPL-3.0-or-later**. Use it freely for
private and commercial writing, research and teaching — including
self-publishing your book; no extra permission is needed. If you distribute
Lixity or a modified version, the AGPL requires that recipients receive the
corresponding source under the same license.

A separate written **commercial license** is available for integrations that
cannot meet the AGPL, for example embedding Lixity in a closed-source product
or running a modified version as a network service without releasing its
source.

[Licensing guide](https://mfahsold.github.io/lixity/LICENSING.md) · [Full AGPL text](https://github.com/mfahsold/lixity/blob/main/LICENSE) ·
[Former LNCL-1.0 text](https://github.com/mfahsold/lixity/blob/main/LICENSE-LNCL-1.0) ·
[Commercial enquiries](mailto:mfahsold@googlemail.com?subject=Lixity%20Commercial%20Inquiry)

Maintainer: Matthias Fahsold, Hamburg, Germany. Project operator:
ROST Services GmbH, Rümpel, Germany. [Legal notice](https://mfahsold.github.io/lixity/#impressum).

[Contributing](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md) · [Report a security concern](https://github.com/mfahsold/lixity/blob/main/SECURITY.md) ·
[Sample-text provenance](https://github.com/mfahsold/lixity/blob/main/samples/README.md)
