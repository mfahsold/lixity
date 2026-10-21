# Lixity

[![tests](https://github.com/mfahsold/lixity/actions/workflows/tests.yml/badge.svg)](https://github.com/mfahsold/lixity/actions)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![Downloads](https://img.shields.io/pypi/dm/lixity)](https://pypistats.org/packages/lixity)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

Lixity is a local workbench for reading manuscripts, comparing language patterns
and connecting research to passages. It runs on your computer and offers a
browser app, CLI and Python API. Measurements support your review; Lixity does
not grade or rewrite prose.

[Explore the demo](https://mfahsold.github.io/lixity/demo/report.html) ·
[Install Lixity](https://mfahsold.github.io/lixity/guides/installation.html) ·
[Documentation](https://mfahsold.github.io/lixity/#guides)

<a href="https://mfahsold.github.io/lixity/screenshots/dashboard-dark.png"><img src="https://mfahsold.github.io/lixity/screenshots/dashboard-dark.png" width="640" alt="Lixity manuscript reader with continuous prose, chapter navigation and contextual tools"/></a>

The read-only demo opens *The Crate at Warehouse 4*, with six invented English
chapters and credited research images, without an account or upload. Follow the
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

- **Review passages.** Open paragraph values and work markers, or compare chapters
  against the manuscript's own patterns. Analysis can be turned on and off.
- **Connect research.** The experimental workspace links retained sources,
  authored claims and decisions to exact manuscript quotations. Keep a dossier
  alongside a passage; Zotero remains your collection tool. Retention is explicit,
  and archive integrity does not establish factual truth.
- **Export and automate.** Create editorial, reading, submission or analysis PDFs,
  terminal reports and versioned JSON. `lixity --help` and `lixity about --json`
  describe the installed commands and capabilities.

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

The current release is **v0.7.2**, in the pre-1.0 development line. Historical
v3.0.1 and earlier tags remain available. Product and schema versions are
independent; [Release notes](https://mfahsold.github.io/lixity/releases/v0.7.2.md)
cover archive compatibility and upgrades. See the
[changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) for subsequent work.
The public demo follows current main and can show changes beyond the release.

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
