# Lixity

[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
[![License: AGPL-3.0-or-later](https://img.shields.io/badge/license-AGPL--3.0--or--later-blue)](https://github.com/mfahsold/lixity/blob/main/LICENSE)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)

Lixity is an open-source workspace for writing and revising manuscripts on your
own computer. When a sentence runs long or a phrase repeats, go straight to the
passage and read it in context. Keep the notes and sources behind a scene close
by, and choose what to share when the draft is ready.

[Download Lixity for desktop](https://mfahsold.github.io/lixity/guides/installation.html#desktop) ·
[Edit a paragraph in the browser exercise](https://mfahsold.github.io/lixity/sandbox/index.html) ·
[Follow a finding in the read-only demo](https://mfahsold.github.io/lixity/demo/report.html) ·
[Visit the product website](https://mfahsold.github.io/lixity/)

<a id="choose-what-leaves-the-project"></a>

## Work with a draft

- **Read and revise.** Compare chapters and saved versions, open the words or
  sentences behind a measurement, and decide what to change in the draft.
  [First session](https://github.com/mfahsold/lixity/blob/main/docs/ONBOARDING.md)
- **Keep research by the text.** Review a character's appearances in context.
  Link manuscript passages to your dossiers, notes and exact source quotations.
  [Research and dossiers](https://github.com/mfahsold/lixity/blob/main/docs/research/USAGE.md)
- **Read it aloud.** Rehearse in the teleprompter and keep delivery notes with
  the passage. Review a recording before deciding whether to retain it.
  [Audio and passage direction](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md)
- **Share a reading copy.** Export a manuscript or dossier PDF, or prepare a
  reading website with the chapters and background you choose.
  [Reading website export](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#export-a-reading-website)

Built-in analysis runs offline. The interface is available in German, English,
French, Spanish, Italian, Portuguese and Dutch. Measurement coverage depends
on the language. [Language coverage](https://github.com/mfahsold/lixity/blob/main/docs/LOCALIZATION.md) ·
[Methods](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md)

<a id="start-here"></a>

## Install and start

Choose your operating system and processor, then follow the download and setup
steps. The desktop app includes its analysis runtime. Open Lixity from your
applications menu and choose **Try the example offline** for a first session.
[Desktop downloads](https://mfahsold.github.io/lixity/guides/installation.html#desktop) ·
[macOS](https://mfahsold.github.io/lixity/guides/installation.html#macos)
· [Windows x64](https://mfahsold.github.io/lixity/guides/installation.html#windows)
· [Linux x64](https://mfahsold.github.io/lixity/guides/installation.html#linux)

For desktop test builds, sign in to GitHub and check the installer in your
browser or use the included SHA-256 checksum list.
[Check an installer](https://mfahsold.github.io/lixity/guides/installation.html#installer-check)

For a system without a compatible desktop build, use the published package for
the [local browser app and CLI](https://mfahsold.github.io/lixity/guides/installation.html#install).
[Installation and updates](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md)

## Use the analysis engine

Run the CLI directly on a file. English is the default. Use `--language auto`
to opt into language detection.

```sh
lixity analyze manuscript.md --language en
lixity profile manuscript.md --language en --layer asl --evidence
```

Project settings live in the project folder. The same engine supports the
Python and local HTTP APIs and the read-only MCP server.
[Commands and configuration](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md) ·
[Automation contracts](https://github.com/mfahsold/lixity/blob/main/docs/AGENTS.md) ·
[Agent skill](https://github.com/mfahsold/lixity/blob/main/skills/lixity/SKILL.md)

## Project structure and data boundaries

Python owns the shared engine and project data operations. Browser components
display the results and handle reading and editing interactions. Rust/Tauri
provides the desktop window, native controls and bundled runtime. Project files
and retained research stay in project storage. Optional connected services have
their own data requirements.
[Architecture](https://github.com/mfahsold/lixity/blob/main/docs/ARCHITECTURE.md) ·
[Project backup](https://github.com/mfahsold/lixity/blob/main/docs/PROJECT_BACKUP.md) ·
[Manuals by task](https://github.com/mfahsold/lixity/blob/main/docs/README.md)

## Contribute and verify

Use synthetic or public-domain text when reproducing a problem. Include the
installed build, operating system and steps to reproduce it. Contributors can
use the [documentation map](https://github.com/mfahsold/lixity/blob/main/docs/README.md#maintain-the-documentation)
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
> Historical 1.x and 3.x tags predate the numbering reset. Use the release
> identified as current on GitHub.

The published package comes from the verified tag. The read-only demo and
desktop test builds can show changes from the development checkout.
[Latest GitHub release](https://github.com/mfahsold/lixity/releases/latest) ·
[v0.9.3 release notes](https://github.com/mfahsold/lixity/blob/main/docs/releases/v0.9.3.md) ·
[Changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md)

Lixity is licensed under **AGPL-3.0-or-later**. You can write and sell your
books with it, including through self-publishing. A separate commercial license
is available for closed-source integrations.
[Licensing guide](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md) ·
[Legal notice and contact](https://mfahsold.github.io/lixity/#impressum)

Cite the software using [Zenodo](https://doi.org/10.5281/zenodo.23390297) or
[CITATION.cff](https://github.com/mfahsold/lixity/blob/main/CITATION.cff).
[Software paper draft](https://github.com/mfahsold/lixity/blob/main/paper/paper.md)
