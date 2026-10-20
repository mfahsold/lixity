# Lixity

[![tests](https://github.com/mfahsold/lixity/actions/workflows/tests.yml/badge.svg)](https://github.com/mfahsold/lixity/actions)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![Downloads](https://img.shields.io/pypi/dm/lixity)](https://pypistats.org/packages/lixity)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

**Read before you revise.**

Lixity is a local manuscript analysis tool for authors, editors and researchers.
Read continuous chapters, inspect changes in sentence rhythm, vocabulary,
dialogue and tense, and keep research beside the text. Measurements help you
choose passages to review; they do not grade literary quality or rewrite prose.
The browser app, CLI and Python API share one analysis pipeline.

[Explore the demo](https://mfahsold.github.io/lixity/demo/report.html) ·
[Website and guides](https://mfahsold.github.io/lixity/) ·
[v0.7.2 release notes](https://mfahsold.github.io/lixity/releases/v0.7.2.md)

[![Lixity manuscript reader with chapter navigation and contextual tools](https://mfahsold.github.io/lixity/screenshots/dashboard-dark.png)](https://mfahsold.github.io/lixity/screenshots/dashboard-dark.png)

The demo opens *The Crate at Warehouse 4*: six invented English chapters and a
research archive with credited historical images. Explore the three native
workspace views without an account or upload. It is read-only: local actions
cannot import, edit or save. Follow the
[three-minute walkthrough](https://mfahsold.github.io/lixity/guides/first-look.html)
or browse [more views and image credits](https://mfahsold.github.io/lixity/screenshots/README.md).

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
English is the default; automatic detection is explicit. Built-in analysis runs
on your computer. Optional integrations have separate
[data boundaries](https://mfahsold.github.io/lixity/research/USAGE.md).

[Your first project](https://mfahsold.github.io/lixity/ONBOARDING.md) explains the
workflow. [Installation and updates](https://mfahsold.github.io/lixity/INSTALLATION.md)
covers launchers, pinned wheels, service management and removal. After upgrading,
run `lixity service restart --open` and reload the browser; installing a package
does not update an already running service.

## What you can do

- **Read and review.** Adjust the reading view, turn Analysis on or off, and open
  passage Values or work markers when needed. Compare chapters against your
  manuscript’s own patterns, then return to the text.
- **Connect research.** Keep a dossier alongside a passage. The experimental
  research workspace connects retained sources, authored claims and decisions
  to exact manuscript quotations. Zotero remains your collection tool;
  retaining evidence is an explicit action. An integrity check is not a fact check.
- **Export and automate.** Create editorial, reading, submission or analysis
  PDFs; use terminal reports and versioned JSON in your own workflows.
  `lixity --help` and `lixity about --json` describe the installed commands
  and capabilities.

English and German have the broadest analysis resources. French, Spanish,
Italian, Portuguese and Dutch offer localized interfaces with narrower heuristic
coverage. [Language support](https://mfahsold.github.io/lixity/LOCALIZATION.md) and
[interpretation](https://mfahsold.github.io/lixity/guides/interpretation.html)
explain coverage, short-sample limits and unavailable measurements.

## Documentation map

| Looking for | Start here |
| :--- | :--- |
| Daily checks, project defaults and CLI | [Usage and CLI reference](https://mfahsold.github.io/lixity/USAGE.md) · [Practical guides](https://mfahsold.github.io/lixity/#guides) |
| Research and Zotero | [Research workflows and compatibility](https://mfahsold.github.io/lixity/research/USAGE.md) · [Data model](https://mfahsold.github.io/lixity/research/DATA_MODEL.md) |
| Measurements and limits | [Methods](https://mfahsold.github.io/lixity/METHODS.md) · [Validation](https://mfahsold.github.io/lixity/STABILITY.md) |
| Integrations | [Python, CLI and HTTP contracts](https://mfahsold.github.io/lixity/AGENTS.md) · [Architecture](https://mfahsold.github.io/lixity/ARCHITECTURE.md) · [Agent index](https://mfahsold.github.io/lixity/llms.txt) |
| Contributing | [Contributor setup and checks](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md) · [Security](https://github.com/mfahsold/lixity/blob/main/SECURITY.md) |

In the repository, [`src/lixity/`](https://github.com/mfahsold/lixity/tree/main/src/lixity)
contains the shared engine, CLI and UI;
[`tests/`](https://github.com/mfahsold/lixity/tree/main/tests) verifies behavior;
[`docs/`](https://github.com/mfahsold/lixity/tree/main/docs) holds maintained product
documentation; and [`samples/`](https://github.com/mfahsold/lixity/tree/main/samples)
contains synthetic or public-domain examples. Book-specific adapters belong in
their own projects.

## Release, citation and license

The current release is **v0.7.2**, in the pre-1.0 development line. Historical
v3.0.1 and earlier tags remain available. Product and schema versions are
independent; [Release notes](https://mfahsold.github.io/lixity/releases/v0.7.2.md)
cover archive compatibility and upgrades. See the
[changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) for subsequent work.

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
