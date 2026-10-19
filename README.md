# Lixity

[![tests](https://github.com/mfahsold/lixity/actions/workflows/tests.yml/badge.svg)](https://github.com/mfahsold/lixity/actions)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![Downloads](https://img.shields.io/pypi/dm/lixity)](https://pypistats.org/packages/lixity)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

**Read the patterns in your writing. Keep the evidence behind your decisions.**

Lixity helps authors, editors and researchers see how a manuscript changes from
chapter to chapter. It measures sentence lengths, word use, dialogue and tense,
with chapter comparisons and paragraph views for reading the measured text.
Its research workspace keeps source quotations and writing decisions connected. Your literary judgment guides
what you keep or revise.

![Lixity dashboard — chapter comparison, sentence rhythm and passage drill-down](docs/screenshots/dashboard-dark.png)

Matthias Fahsold developed Lixity as an architect and developer at ROST Services
GmbH and used it while writing his own debut novel.

[Try the example](https://mfahsold.github.io/lixity/demo/report.html) ·
[Three-minute first look](https://mfahsold.github.io/lixity/guides/first-look.html) ·
[Install](#install-and-start) · [What you can do](#what-you-can-do) ·
[Practical guides](https://mfahsold.github.io/lixity/#guides) ·
[v0.5.0 release notes](docs/releases/v0.5.0.md)

The example is a read-only report made from invented text. It needs no
installation or manuscript upload. Documentation is English; you can read the
results in German, English, French, Spanish, Italian, Portuguese or Dutch.

## Try it in 30 seconds

Open the [synthetic report](https://mfahsold.github.io/lixity/demo/report.html)
(invented text), [Effi Briest](https://mfahsold.github.io/lixity/examples/effi-briest.html)
or [Pride and Prejudice](https://mfahsold.github.io/lixity/examples/pride-and-prejudice.html).
Explore a chapter comparison, then open a paragraph to read its measurements.
No install, account or upload is needed. The
[three-minute first look](https://mfahsold.github.io/lixity/guides/first-look.html)
explains the results without requiring statistics background.

<a id="start-here"></a>
Built-in analysis runs on your computer. Optional external OCR workers have
separate [data boundaries](docs/research/OCR_INTEGRATION.md).

## Install and start

Install [uv](https://docs.astral.sh/uv/), then run on Windows, macOS or Linux:

```bash
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Open a new terminal, verify `lixity --version`, then start the local workspace
with `lixity service start --open`. Choose **Open Project** or **Analyze a
manuscript**; the [first-project guide](docs/ONBOARDING.md) explains both.
For later visits, use the packaged `lixity-start.sh` / `lixity-start.ps1` launcher
or the same service command.

The [installation guide](docs/INSTALLATION.md) covers platform setup, pinned
release wheels with `SHA256SUMS`, service status and logs, updates and removal.
After an upgrade, restart the workspace to load the installed version.

## What you can do

### Understand your writing

See how sentence lengths, vocabulary, dialogue and tense vary throughout your
manuscript. Open the passages behind a result before deciding whether to revise.
Short or empty texts cannot support every comparison; unavailable results are
shown explicitly.

<a href="docs/screenshots/dashboard-light.png"><img src="docs/screenshots/dashboard-light.png" alt="Manuscript overview showing sentence rhythm, vocabulary and dialogue measures" width="900" /></a>

[Read the language signals](https://mfahsold.github.io/lixity/guides/interpretation.html) ·
[Mobile view](docs/screenshots/dashboard-mobile.png) ·
[Dark theme](docs/screenshots/dashboard-dark.png)

<img src="docs/videos/analysis-review.gif" alt="Walkthrough: select a chapter cell, expand a paragraph's Values and switch to the style dimensions" width="900" />

### Compare chapters in context

The chapter map uses your manuscript's chapters as its reference. For example,
a chapter with longer sentences than usual may reflect a new voice or a formal
report. Select a coloured cell to inspect that chapter. The style axes bring
together related measurements, helping you see which chapters share patterns
and which features distinguish them.

<a href="docs/screenshots/dashboard-heatmap.png"><img src="docs/screenshots/dashboard-heatmap.png" alt="Chapter comparison map showing differences from the manuscript's own style" width="900" /></a>

[Understand chapter comparisons](https://mfahsold.github.io/lixity/guides/interpretation.html#consistency) ·
[Style dimensions](docs/screenshots/dashboard-dimensions.png) ·
[Reference bands](docs/screenshots/dashboard-reference.png)

Assign scenes to registers—such as dialogue, action or a formal report—so you
can compare scenes with a similar purpose. Each group has its own middle values
(medians); you can also set optional targets. Small samples may leave
measurements unavailable. [Scene example](docs/screenshots/dashboard-scenes.png) ·
[Setup and limits](docs/USAGE.md#scene-registers-and-project-targets).

### Print what the analysis found

Export an A5 reading copy, A4 analysis report or A4 submission sheet from
**PDF export** in the project controls, or use `lixity pdf`. The composer uses
your project's title, author and optional publication details. Empty fields
supply no inferred information.

See the complete [Effi Briest report](https://mfahsold.github.io/lixity/examples/effi-briest-report.pdf)
or [Pride and Prejudice report](https://mfahsold.github.io/lixity/examples/pride-and-prejudice-report.pdf).
[PDF layouts and font limits](docs/USAGE.md#lixity-pdf) ·
[Publication settings](docs/USAGE.md#publication-settings).

### Keep review notes beside the text

Start from the flagged passages list, open a paragraph and read its measured
values, source lines and tense labels. A note can be written directly on the
passage; work markers keep it next to the relevant text in Markdown. Their
visibility in a book export depends on the editor or converter you use.

<img src="docs/videos/editorial-loop.gif" alt="Walkthrough: review flagged passages, open a paragraph, read its values and write a marker note on the passage" width="900" />

<a href="docs/screenshots/dashboard-markers.png"><img src="docs/screenshots/dashboard-markers.png" alt="Review markers linked to passages, with statuses and an editable note" width="900" /></a>

[Work-marker instructions](docs/USAGE.md#work-markers-editor-visible) ·
[Flagged passages](docs/screenshots/dashboard-flags.png) ·
[Note on a passage](docs/screenshots/dashboard-editorial.png) ·
[Paragraph view](docs/screenshots/dashboard-layer.png)

### Connect sources, claims and decisions

The experimental research workspace keeps selected sources, quotations and notes
in a separate local archive. A dossier gathers notes on a topic; a claim records
an assertion you can link to source passages; a decision explains what you chose
for the book. Filter by title or tag, or search the saved text. A saved quotation
records what a source says; its accuracy still needs review.

<a href="docs/screenshots/dashboard-dossier-image.png"><img src="docs/screenshots/dashboard-dossier-image.png" alt="Local visual reference inside a dossier section, with a description and an explicit synthetic-source caption" width="900" /></a>

Import authorized local files or selected Zotero Desktop attachments.
Scans can use local Tesseract or a configured OCR worker; inspect extraction
warnings and quotations. Evidence links pin source paragraphs, while manuscript
quote associations connect reviewed prose to exact claim revisions.

**Review** identifies older linked versions and changed manuscript anchors for
your assessment. Related revisions can be previewed and saved together;
conflicts preserve your draft. Nothing is repinned silently. Add local images
as visual references, or use **Timeline** to organize claims with explicit
calendar periods. These links and views record your interpretation; they do
not establish factual truth. [Research workflows and limits](docs/research/USAGE.md).

<img src="docs/videos/research-timeline.gif" alt="Walkthrough: the claims timeline places dated claims on a shared axis and jumps from a bar to its claim card" width="900" />

[Research guide](https://mfahsold.github.io/lixity/guides/research-pdf.html) ·
[Search and citations](docs/screenshots/dashboard-research-search.png) ·
[Sources](docs/screenshots/dashboard-research-sources.png) ·
[Claims](docs/screenshots/dashboard-research-claims.png) ·
[Decisions](docs/screenshots/dashboard-research-decisions.png) ·
[Decision review](docs/screenshots/dashboard-research-review.png) ·
[Related revision preview](docs/screenshots/dashboard-research-change-set.png)

### Choose a project and its settings

Preview a manuscript before importing it, select its analysis language and
adjust which differences you want to examine. Project settings also hold the
author name, publication details and optional confidentiality-agreement controls.

<a href="docs/screenshots/dashboard-project-settings.png"><img src="docs/screenshots/dashboard-project-settings.png" alt="Project settings with manuscript selection, analysis preferences and the five-field NDA generator" width="900" /></a>

[Project workflow](docs/USAGE.md#dashboard-workflow) ·
[Import preview](docs/screenshots/dashboard-project-import.png) ·
[Mobile settings](docs/screenshots/dashboard-project-settings-mobile.png)

### Read a report in the terminal

Use `lixity analyze manuscript.md --language de` for a readable report, or add
`--json` for software integration. Chapter, paragraph, dialogue, pacing and
research commands are covered in the [command reference](docs/USAGE.md).

<a href="docs/screenshots/cli-analyze.png"><img src="docs/screenshots/cli-analyze.png" alt="Terminal report with sentence lengths, readability and vocabulary measures" width="900" /></a>

These screenshots use public-domain literature or synthetic project records.
[More views and capture details](docs/screenshots/README.md).

## How to read the results

Each measurement answers a specific question about the text:

| Measurement | What it helps you notice |
| :--- | :--- |
| Sentence length and variation | Whether sentences stay similar in length or alternate between short and long. Suspense also depends on what happens in them. |
| Vocabulary diversity | How much words repeat. Compare passages of similar length, language and purpose. |
| Dialogue share | How much text falls inside recognized quotation marks. A high value may be expected in a conversation scene. |
| Chapter differences and consistency | How closely measurable chapters follow the book's observed patterns. A deliberate change in voice can lower consistency. |

Chapter comparisons use the manuscript's middle values and typical spread
(median and MAD), with an adjustment for estimated sampling noise. Colours mark
the direction of a difference, not its literary value. Optional statistical
checks mark a selection for review; they cannot certify that a passage needs
editing. An unavailable value can mean there is too little text or too few
comparable chapters to calculate it.

The mathematical core includes several vocabulary measures (HD-D, MTLD, MATTR,
Guiraud R, Maas a² and Yule's K). They answer related questions using different
models and sample sizes. Readability and grammatical-pattern indicators have
language-specific limits. Formulas, citations and worked examples live in
[Methods](docs/METHODS.md). The
[interpretation guide](https://mfahsold.github.io/lixity/guides/interpretation.html)
explains how to read results; [stability and validation limits](docs/STABILITY.md)
describe what has and has not been established.

## Supported languages

German (`de`) and English (`en`) have the most extensive linguistic resources
and language-specific fixtures. French (`fr`), Spanish (`es`), Italian (`it`),
Portuguese (`pt`) and Dutch (`nl`) also have localized interfaces and analysis
resources, with narrower heuristic coverage and validation.

Choose the manuscript language explicitly. `LIXITY_LANG=de` selects German
terminal messages independently of `--language de`, which selects German
analysis. Documentation is English; source quotations retain their original
language. Mathematical identifiers and numeric JSON values are language-neutral.
[Language support and limits](docs/LOCALIZATION.md).

## Documentation map

- [Practical guides](https://mfahsold.github.io/lixity/#guides) — installation,
  interpretation, research and comparisons with other tools.
- [First project](docs/ONBOARDING.md) · [Installation and updates](docs/INSTALLATION.md).
- [CLI workflows](docs/USAGE.md) — use `lixity --help` and
  `lixity COMMAND --help` for the installed commands and options.
- [Automation contracts](docs/AGENTS.md) · [Research workflows](docs/research/USAGE.md).
- [Methods](docs/METHODS.md) · [Stability](docs/STABILITY.md) ·
  [Architecture](docs/ARCHITECTURE.md) · [Localization](docs/LOCALIZATION.md).
- [Agent index](docs/llms.txt) · [Full documentation bundle](docs/llms-full.txt).

## Current release

The current release is **v0.5.0**, continuing the pre-1.0 development line;
historical v3.0.1 and earlier notes and tags remain available. Public JSON and
research storage schema versions are independent; this release reads
research archives through v7.
When upgrading from the historical numbering, install the pinned release wheel
explicitly; PyPI upgrades continue normally afterwards.
[Release notes](docs/releases/v0.5.0.md) describe compatibility and known limits;
the [changelog](CHANGELOG.md) records subsequent work on `main`.

## Python API and automation

```python
from lixity import api

html = api.dashboard(text, language="de", project_config={})
```

CLI, Python and dashboard analysis share one pipeline. Analysis/profile JSON uses
schema **v2**; style JSON uses **v4**. Integrations should pass explicit project
settings when working with several projects.

Choose `api.analyze` for numeric results or `api.fingerprint` for a style
reference. Each convenience call performs its own analysis; integrations needing
several outputs can [reuse the shared analysis result](docs/ARCHITECTURE.md#configuration-and-multiple-projects).

[Interface contracts](docs/AGENTS.md) · [Architecture](docs/ARCHITECTURE.md) ·
[Research commands](docs/research/USAGE.md) · [Automation summary](docs/llms.txt)

## Research

The methods and the tool's placement among stylometry and corpus tools are
described in the software paper draft under [`paper/`](paper/paper.md),
prepared for the [Journal of Open Source Software](https://joss.theoj.org/).
Released versions are archived on Zenodo: cite the concept DOI
[`10.5281/zenodo.23390297`](https://doi.org/10.5281/zenodo.23390297) (see [`CITATION.cff`](CITATION.cff));
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

[Licensing guide](docs/LICENSING.md) · [Full AGPL text](LICENSE) ·
[Former LNCL-1.0 text](LICENSE-LNCL-1.0) ·
[Commercial enquiries](mailto:mfahsold@googlemail.com?subject=Lixity%20Commercial%20Inquiry)

Maintainer: Matthias Fahsold, Hamburg, Germany. Project operator:
ROST Services GmbH, Rümpel, Germany. [Legal notice](https://mfahsold.github.io/lixity/#impressum).

[Contributing](CONTRIBUTING.md) · [Report a security concern](SECURITY.md) ·
[Sample-text provenance](samples/README.md)
