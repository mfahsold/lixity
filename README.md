# <img src="https://mfahsold.github.io/lixity/assets/brand/icon-192.png" width="64" height="64" alt=""> Lixity

[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)](https://github.com/mfahsold/lixity/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)

Lixity is an open-source manuscript workspace for writers, editors and
researchers. When a sentence is marked, open the words that were counted and
read them in context. Revise the draft, keep the sources that shaped it close
by, and share the reading copy you choose. Built-in analysis runs offline.

[Download Lixity for desktop](https://mfahsold.github.io/lixity/guides/installation.html#desktop) ·
[Visit the product website](https://mfahsold.github.io/lixity/)

<a id="start-here"></a>

## Install and start

1. Choose a desktop download for a
   [Mac with Apple silicon or an Intel processor](https://mfahsold.github.io/lixity/guides/installation.html#macos),
   [Windows 64-bit PC](https://mfahsold.github.io/lixity/guides/installation.html#windows)
   or [Linux 64-bit PC](https://mfahsold.github.io/lixity/guides/installation.html#linux).
   The current desktop test archives require GitHub sign-in. Windows and Linux
   builds target x86-64.
2. Extract the archive, [check the installer in your browser](https://mfahsold.github.io/lixity/guides/installation.html#installer-check)
   and follow the setup steps for your computer. The desktop app includes the analysis runtime.
3. Open Lixity. Choose **Try the example offline**
   for an editable sample, **Open a project folder** for work already in a
   project, or **Import a manuscript** to bring in a Word, Markdown or text file.
   [First session](https://github.com/mfahsold/lixity/blob/main/docs/ONBOARDING.md)

Try the [browser exercise](https://mfahsold.github.io/lixity/sandbox/index.html)
or follow a finding in the [read-only demo](https://mfahsold.github.io/lixity/demo/report.html)
before installing. The published
[local browser app and CLI](https://mfahsold.github.io/lixity/guides/installation.html#install)
are available through PyPI. [Installation and updates](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md)

<a id="choose-what-leaves-the-project"></a>

## Work with a draft

- **Read and revise.** Follow a measurement to its passage, compare chapters
  or saved versions, and revisit earlier drafts.
  [Writing and recovery](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#write-a-manuscript)
- **Keep research by the text.** Link passages to dossiers, notes and exact
  source quotations. Revisit the retained source version behind a citation.
  [Research and dossiers](https://github.com/mfahsold/lixity/blob/main/docs/research/USAGE.md)
- **Read it aloud.** Rehearse in the teleprompter and keep delivery notes with
  the passage. Review a recording before deciding whether to retain it.
  [Audio and passage direction](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md)
- **Share a reading copy.** Export a manuscript or dossier PDF, or prepare a
  reading website with the chapters and background you choose.
  [Reading website export](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#export-a-reading-website)

The interface is available in German, English, French, Spanish, Italian,
Portuguese and Dutch. Measurement coverage depends on the language.
[Language coverage](https://github.com/mfahsold/lixity/blob/main/docs/LOCALIZATION.md) ·
[Methods](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md) ·
[Manuals by task](https://github.com/mfahsold/lixity/blob/main/docs/README.md)

## Use the analysis engine

Use the CLI for repeatable file analysis. English is the default. Choose
`--language auto` to opt into detection. The same engine supports the Python
and local HTTP APIs and the read-only MCP server.
[Commands and configuration](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md) ·
[Automation contracts](https://github.com/mfahsold/lixity/blob/main/docs/AGENTS.md) ·
[Agent skill](https://github.com/mfahsold/lixity/blob/main/skills/lixity/SKILL.md)

## How the project is built

The Python engine serves the CLI, local browser app and Rust/Tauri desktop
host. The desktop host provides the native window, platform controls and
bundled runtime. Project files and retained research stay in project storage.
Optional connected services have their own data requirements.
[Architecture](https://github.com/mfahsold/lixity/blob/main/docs/ARCHITECTURE.md) ·
[Project backup](https://github.com/mfahsold/lixity/blob/main/docs/PROJECT_BACKUP.md) ·
[Product direction](https://github.com/mfahsold/lixity/blob/main/docs/PRODUCT.md)

## Contribute and verify

Report the installed build, operating system and steps to reproduce the problem
with synthetic or public-domain text. Use the
[documentation map](https://github.com/mfahsold/lixity/blob/main/docs/README.md#maintain-the-documentation)
to find the source of a guide or example before editing it.

```sh
make install-dev
make check
```

[Report an issue](https://github.com/mfahsold/lixity/issues/new/choose) ·
[Contributor guide](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md) ·
[Security policy](https://github.com/mfahsold/lixity/blob/main/SECURITY.md)

## Release, citation and license

> **Version line:** The documentation source version is **v0.9.3**, in the pre-1.0 **0.x** line.
> Historical 1.x and 3.x tags predate the numbering reset.

The published package comes from the verified tag. The demo and test builds
identify the source that produced them.
[Latest GitHub release](https://github.com/mfahsold/lixity/releases/latest) ·
[v0.9.3 release notes](https://github.com/mfahsold/lixity/blob/main/docs/releases/v0.9.3.md) ·
[Changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md)

Lixity is licensed under **AGPL-3.0-or-later**. You can write and sell your
books with it, including through self-publishing. The first project funding is
intended for public desktop installers and the Android and iOS / iPadOS ports.
A separate commercial license is available for closed-source integrations.
[Licensing guide](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md) ·
[Support Lixity](https://mfahsold.github.io/lixity/guides/support.html) ·
[Legal notice and contact](https://mfahsold.github.io/lixity/#impressum)

Cite the software using [Zenodo](https://doi.org/10.5281/zenodo.23390297) or
[CITATION.cff](https://github.com/mfahsold/lixity/blob/main/CITATION.cff).
[Software paper draft](https://github.com/mfahsold/lixity/blob/main/paper/paper.md)
