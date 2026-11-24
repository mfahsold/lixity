# Lixity

[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)](https://github.com/mfahsold/lixity/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)

Lixity is an open-source manuscript workspace with a shared Python analysis
engine, CLI, local browser interface and Rust/Tauri desktop host. It links
measurements to manuscript passages, preserves the revisions behind research
citations, and exports the reading or review copy the author selects. Built-in
analysis runs offline.

[Product website](https://mfahsold.github.io/lixity/) ·
[Read-only demo](https://mfahsold.github.io/lixity/demo/report.html) ·
[Browser sandbox](https://mfahsold.github.io/lixity/sandbox/index.html) ·
[Manuals by task](https://github.com/mfahsold/lixity/blob/main/docs/README.md) ·
[Contributor guide](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md)

<a id="start-here"></a>

## Install and start

### Desktop test installers

The desktop app bundles the analysis engine and opens in its own window. If
you already have a test installer, follow the steps for your system. The app
supplies its own Python runtime.

| System | Test installer | Open Lixity |
| --- | --- | --- |
| macOS, Apple Silicon or Intel | `.dmg` | Drag **Lixity.app** to **Applications**, eject the disk image and open Lixity from **Applications**. |
| Windows x64 | `.exe` or `.msi` | Run the installer and open **Lixity** in the Start menu. |
| Linux x64, including Ubuntu | `.deb` or `.AppImage` | Install the `.deb` and open **Lixity** from the applications menu, or make the `.AppImage` executable and open it. |

GitHub Actions builds these installers as time-limited test downloads. Sign in
to GitHub and choose the artifact for your system from a successful run. The
desktop download page lists installers that have cleared the public release
checks.

[Get a test installer](https://github.com/mfahsold/lixity/blob/main/desktop/README.md#download-a-test-build) ·
[Desktop installation by operating system](https://mfahsold.github.io/lixity/guides/installation.html#desktop)

### Published browser app and CLI

Install [uv](https://docs.astral.sh/uv/getting-started/installation/) first.
The published package works on macOS, Windows and Linux. This command installs
Lixity in an isolated tool environment and lets uv supply Python 3.12. The
package supports Python 3.10 and later.

```bash
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Open a new terminal and start the local browser app.

```bash
lixity --version
lixity service start --open
```

The default address is `http://127.0.0.1:8765/`. Choose **Open Project** to
open an existing folder or **Analyze a manuscript** to preview importing a
Markdown, plain-text or Word file. One managed service can open several project
views. Use `lixity service status` to check its address and `lixity doctor` to
diagnose the installation.

For an installed CLI or browser app, run `uv tool upgrade lixity` and restart
the service using the update procedure. Desktop test builds use the desktop
update procedure.

[Installation and updates](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md) ·
[First session](https://github.com/mfahsold/lixity/blob/main/docs/ONBOARDING.md) ·
[Desktop build and verification](https://github.com/mfahsold/lixity/blob/main/desktop/README.md)

## Use the analysis engine

The CLI runs without a browser service. Start with an explicit text and
language. English is the default, and `--language auto` opts into detection.

```bash
lixity analyze manuscript.md --language en
lixity profile manuscript.md --language en --layer asl --evidence
lixity project --project ./novel
lixity about --json
```

Configure a project in its own `lixity.toml` or in `[tool.lixity]` in its
`pyproject.toml`. From the browser, open the same project folder to use its
settings. Automation clients can call the CLI or Python API, use the local
HTTP interface, or run the read-only MCP server. Product, JSON response and
archive schema versions evolve independently.

The interface is available in German, English, French, Spanish, Italian,
Portuguese and Dutch. Measurement coverage varies by language. Signals
point to passages and patterns for human review. The methods and validation
references explain what is measured and when a result is unavailable.

[CLI and configuration](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md#which-command-for-which-question) ·
[Python, HTTP and JSON contracts](https://github.com/mfahsold/lixity/blob/main/docs/AGENTS.md) ·
[MCP setup](https://github.com/mfahsold/lixity/blob/main/docs/AGENTS.md#model-context-protocol-mcp-server) ·
[Agent skill](https://github.com/mfahsold/lixity/blob/main/skills/lixity/SKILL.md)

[Language coverage](https://github.com/mfahsold/lixity/blob/main/docs/LOCALIZATION.md) ·
[Methods](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md) ·
[Validation and limits](https://github.com/mfahsold/lixity/blob/main/docs/STABILITY.md#core-validation-status)

## Project structure and data boundaries

| Area | Responsibility |
| --- | --- |
| [Python package](https://github.com/mfahsold/lixity/tree/main/src/lixity) | Language resources, shared analysis pipeline, CLI and API, loopback server, and project-scoped research and exports. |
| [Shared UI](https://github.com/mfahsold/lixity/tree/main/src/lixity/ui) | Python renders supplied results. Browser components handle presentation, navigation and interaction. The public demo uses the shared interface on a fixed example. |
| [Desktop host](https://github.com/mfahsold/lixity/tree/main/desktop) | Rust/Tauri windows, OS integration, bundled runtime supervision and authenticated local transport. |
| [Project files and research](https://github.com/mfahsold/lixity/blob/main/docs/research/DATA_MODEL.md) | The project owns its saved manuscript, configuration and retained research. Exact citations can refer to earlier research revisions. |
| [Documentation](https://github.com/mfahsold/lixity/blob/main/docs/README.md) and [GitHub Pages](https://mfahsold.github.io/lixity/) | Maintained technical references, public product presentation and reviewed examples. The contributor guide owns the build and publishing procedures. |
| [Tests](https://github.com/mfahsold/lixity/tree/main/tests) and [samples](https://github.com/mfahsold/lixity/tree/main/samples) | Verification across engine, contracts and workflows using synthetic or public-domain manuscripts. |

Manuscript analysis, editing and standard exports run locally without an
account. Optional integrations such as remote speech synthesis have their
own data paths. Website visit measurement applies to the public website.
Keep project-specific adapters, private manuscripts and retained research
outside the shared repository.

[Architecture and trust boundaries](https://github.com/mfahsold/lixity/blob/main/docs/ARCHITECTURE.md) ·
[Analysis ownership across Python, Rust and JavaScript](https://github.com/mfahsold/lixity/blob/main/docs/ARCHITECTURE.md#analysis-ownership-across-python-rust-and-javascript) ·
[Research workflows](https://github.com/mfahsold/lixity/blob/main/docs/research/USAGE.md) ·
[Website measurement notice](https://mfahsold.github.io/lixity/#website-measurement)

## Choose what leaves the project

Export a PDF or a fixed reading website with the selected manuscript,
chapters and background notes. Review the export scope and retained source
permissions before sharing. Use the project backup procedure to create a
restorable copy of the selected project files and archive.

[Manuscript PDF](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#download-a-manuscript-pdf) ·
[Dossier PDF](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#download-a-dossier-pdf) ·
[Reading website](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#export-a-reading-website) ·
[Backup and restore](https://github.com/mfahsold/lixity/blob/main/docs/PROJECT_BACKUP.md)

## Contribute and verify

Lixity is maintained by Matthias Fahsold. Use GitHub issues for reproducible
bugs and proposals, and pull requests for changes. For a bug report, identify
the installed build, the affected surface and the steps to reproduce it with
synthetic data. Report security issues privately through the security policy.

```bash
make install-dev
make check
```

Run these commands from a repository checkout. `make check` runs Ruff, strict
mypy and pytest with warnings as errors. The contributor guide gives the
additional checks for browser interactions, native desktop behavior and
generated documentation. It also owns the release and Pages procedures.

[Report an issue](https://github.com/mfahsold/lixity/issues/new/choose) ·
[Select checks](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#select-the-checks-for-your-change) ·
[Release process](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#preparing-a-release) ·
[Documentation and Pages](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#updating-documentation-and-pages) ·
[Security policy](https://github.com/mfahsold/lixity/blob/main/SECURITY.md)

## Release, citation and license

> **Version line:** The documentation source version is **v0.9.1**, in the pre-1.0 **0.x** line.
> Historical 1.x and 3.x tags predate the numbering reset. Use the release
> identified as current on GitHub.

The published package comes from the verified tag. The public demo is a
read-only snapshot from the development checkout and identifies the version
that generated it. Work in progress is recorded under **Unreleased**.

[Latest GitHub release](https://github.com/mfahsold/lixity/releases/latest) ·
[PyPI package](https://pypi.org/project/lixity/) ·
[v0.9.1 release notes](https://github.com/mfahsold/lixity/blob/main/docs/releases/v0.9.1.md) ·
[Changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md)

Cite [Lixity on Zenodo](https://doi.org/10.5281/zenodo.23390297), with metadata
in [CITATION.cff](https://github.com/mfahsold/lixity/blob/main/CITATION.cff).
The [software paper draft](https://github.com/mfahsold/lixity/blob/main/paper/paper.md)
describes the research context.

Lixity is licensed under **AGPL-3.0-or-later**. Authors can use it for private
and commercial writing, including self-publishing. A separate written
commercial license is available for integrations that cannot meet the AGPL.

[Licensing guide](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md) ·
[Full terms](https://github.com/mfahsold/lixity/blob/main/LICENSE) ·
[Legal notice and contact](https://mfahsold.github.io/lixity/#impressum)
