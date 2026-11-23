# Lixity

[![Checks: local-first](https://img.shields.io/badge/checks-local--first-blue)](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
[![Mastodon](https://img.shields.io/badge/Mastodon-@lixity-6364ff?logo=mastodon&logoColor=white)](https://mastodon.social/@lixity)
[![Bluesky](https://img.shields.io/badge/Bluesky-@lixity.bsky.social-0285ff?logo=bluesky&logoColor=white)](https://bsky.app/profile/lixity.bsky.social)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

> **A local workspace for authors, editors, and researchers.**
> Find a passage worth revisiting, keep the research for a scene at hand, and share the revision you choose. Built-in analysis runs offline.
>
> 🚀 **[Interactive Demo](https://mfahsold.github.io/lixity/demo/report.html)** · ✍️ **[Browser Sandbox](https://mfahsold.github.io/lixity/sandbox/index.html)** · 📖 **[Read Demo Novel](https://mfahsold.github.io/lixity/demo/reader/index.html)** · ⚡ **[Install Guide](https://mfahsold.github.io/lixity/guides/installation.html)** · 📚 **[First-Look Tour](https://mfahsold.github.io/lixity/guides/first-look.html)**

**Read closely. Follow the evidence. Decide what to revise.**

Lixity keeps your manuscript, its measurements and your research in one local
workspace. Read a measured passage in context, revise it, and compare what
changed. Keep the sources and decisions behind the scene together. When a copy
is ready to share, choose a PDF or a self-contained reading website.

- **Return from signal to prose:** open the relevant chapter and inspect
  counted words and sentences where evidence is available. Signals support
  the author's review and revision decisions.
- **Keep research traceable:** sources, claims, and author decisions stay
  distinct and retain the exact linked versions across edits.
- **Local-first by default:** analysis, editing (native editor with undo,
  autosave, and recovery), and exports run offline without accounts or
  telemetry. Supports `.md`, `.txt`, and `.docx` import.

**Try without installing.** Shorten a sentence or trace a repeated word in the
[Browser Sandbox](https://mfahsold.github.io/lixity/sandbox/index.html).
In the read-only [Demo Workspace](https://mfahsold.github.io/lixity/demo/report.html),
look for repeated wording or a possible tense shift in the fictional Warehouse 4
draft. Open the highlighted passage and decide whether it needs attention. The
demo identifies the development version that generated the snapshot.
Tours: [English](https://mfahsold.github.io/lixity/guides/first-look.html) ·
[Deutsch](https://mfahsold.github.io/lixity/guides/first-look-de.html) ·
[Methods & limits](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md) ·
[Stability](https://github.com/mfahsold/lixity/blob/main/docs/STABILITY.md).

**Seven interface languages:**
[Deutsch](https://mfahsold.github.io/lixity/index-de.html) ·
[English](https://mfahsold.github.io/lixity/) ·
[Français](https://mfahsold.github.io/lixity/index-fr.html) ·
[Español](https://mfahsold.github.io/lixity/index-es.html) ·
[Italiano](https://mfahsold.github.io/lixity/index-it.html) ·
[Português](https://mfahsold.github.io/lixity/index-pt.html) ·
[Nederlands](https://mfahsold.github.io/lixity/index-nl.html)
([language coverage](https://github.com/mfahsold/lixity/blob/main/docs/LOCALIZATION.md)).

<a id="start-here"></a>

## Install and start

Install [uv](https://docs.astral.sh/uv/) and run these commands on Windows,
macOS or Linux.

```bash
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Open a new terminal, check the installed package and start the local workspace.

```bash
lixity --version
lixity service start --open
```

The default address is `http://127.0.0.1:8765/`. Choose **Open Project** to
continue in an existing folder. Choose **Analyze a manuscript** to preview
importing a file into a new project. The preview accepts Markdown, plain text and
one Word (.docx) file. Choose the manuscript language in the preview.
Automatic detection is available in analysis settings or with `--language auto`.

To work on another project, open the service's root address in a new tab and
choose **Project actions → Open Project**. Lixity opens a separate view for the
chosen folder. Tabs with the same `/w/…/` URL share that view.

`lixity service status` reports the running address. For updates and restarts,
use the [installation guide](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#updates-and-removal).
The install command uses the package published on [PyPI](https://pypi.org/project/lixity/).
The demo follows the development checkout.

[Open your first project](https://github.com/mfahsold/lixity/blob/main/docs/ONBOARDING.md) ·
[Start with a project path or use a custom port](https://mfahsold.github.io/lixity/guides/installation.html#existing-project) ·
[Update or remove Lixity](https://mfahsold.github.io/lixity/guides/installation.html#updates)

## What can you do with Lixity?

| Your task | Start here |
| :--- | :--- |
| Read, revise or recover a draft | [Writing tools and recovery](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#write-a-manuscript) |
| Understand a change in rhythm or voice | [Explore language patterns](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#explore-language-in-the-browser) |
| Trace the sources behind a scene | [Read a dossier beside the manuscript](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#read-a-dossier-beside-the-manuscript) |
| Record, rehearse or listen | [Audio and teleprompter](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md) |
| Share selected chapters or notes | [Reading copies and PDFs](#choose-what-leaves-the-project) |
| Restore a saved project | [Verified backup and restore](https://github.com/mfahsold/lixity/blob/main/docs/PROJECT_BACKUP.md) |

<a href="https://mfahsold.github.io/lixity/screenshots/dashboard-measurement-focus.png"><img src="https://mfahsold.github.io/lixity/screenshots/dashboard-measurement-focus.png" width="560" alt="Sentence-length explanation: A board moved has three words; the paragraph comparison is shown separately"/></a>

**Try one question: does chapter 2's shorter rhythm fit the action?** In the
[demo workspace](https://mfahsold.github.io/lixity/demo/report.html), choose
**Inspect chapter 2**, explain a paragraph's measurement, then return to the
scene. **Counted text** shows the words or sentences behind a measurement;
**Paragraph comparison** is a separate comparison with that chapter.
[See the reading view](https://mfahsold.github.io/lixity/screenshots/dashboard-reader-focus.png).

For the research route, open **Research → Dossiers → Warehouse 4 case notes**.
A preliminary log puts the crate's opening on the quay; its correction moves it
to the customs station. Follow the two source passages and the explicit decision
to keep the crate closed until dawn. Lixity preserves the connection; it does not
resolve the contradiction or establish the truth of a saved claim.
[Follow the decision](https://mfahsold.github.io/lixity/guides/first-look.html#decision).

## Share one revision experience

What did you want to check? Did the explanation help? What got in the way?
[Send a short description](mailto:mfahsold@googlemail.com?subject=Lixity%20feedback)
or [report a reproducible issue](https://github.com/mfahsold/lixity/issues).
You do not need to share manuscript text to give useful feedback.

## One project, from draft to reading copy

### Read, inspect and return to the scene

Keep the manuscript in view while opening counted-text explanations or a dossier
alongside it. Tense cues show the original forms and manuscript locations before
heuristic interpretation. Chapter tables and the 3D style space compare measured
patterns; neither predicts literary quality. Flat projections and exact values
help inspect overlaps in the 3D view.

English and German have the broadest analysis resources. French, Spanish,
Italian, Portuguese and Dutch have localized interfaces with narrower heuristic
coverage. Optional local syntax models add grammatical tense analysis with
language-specific verb-group rules; parser errors remain possible.
[Interpretation](https://mfahsold.github.io/lixity/guides/interpretation.html) ·
[Metric reference](https://mfahsold.github.io/lixity/guides/metrics/en.html) ·
[Language coverage](https://github.com/mfahsold/lixity/blob/main/docs/LOCALIZATION.md) ·
[Grammatical tense setup](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md#grammatical-tense).

### Keep research connected and versioned

A dossier gathers authored notes, retained source passages, claims, decisions,
images and maps. Passage associations return to their manuscript context. A linked
earlier version remains distinct from the current entry. In the development
checkout, manuscript suggestions show why a character, place or scene was
proposed. Follow a highlighted match back to the manuscript, or save a
reviewed report alongside your notes. Configure place names and link exact
terms or props to a dossier. Use the saved version for a PDF.

Research is scoped to an explicit project. Retaining a source and redistributing
it are separate choices. Original PDFs, images and videos have their own import
and export controls. Existing archives require a reviewed migration before
adopting a newer storage format.
[Research workflows](https://github.com/mfahsold/lixity/blob/main/docs/research/USAGE.md) ·
[Data model](https://github.com/mfahsold/lixity/blob/main/docs/research/DATA_MODEL.md).

### Record, direct and listen

Use **Listen & direct** or the **Teleprompter** from the manuscript toolbar.
Record a take and review its transcript, or export a JSON or SSML speech plan
without a worker. To hear synthesized prose, choose a configured speech engine.
An external provider receives the selected text when you request its synthesis.
[Recording and audio workflows](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md) ·
[Worker setup](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#optional-qwen-audio-worker).

### Choose what leaves the project

| Copy | Contents and purpose |
| :--- | :--- |
| [Review workspace](https://mfahsold.github.io/lixity/demo/report.html) | Manuscript and analysis, optionally internal research and history; for author/editor review. |
| [Novel with companion notes](https://mfahsold.github.io/lixity/demo/reader/index.html) | Manuscript with explicitly selected dossier notes, plus optional analysis of the exported chapters. |
| [Standalone companion](https://mfahsold.github.io/lixity/demo/companion/index.html) | Selected background material for someone reading the novel elsewhere. |
| [Manuscript PDF](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#download-a-manuscript-pdf) | Neutral or editorial manuscript, analysis report, A5 book or submission sheet. |
| [Dossier PDF](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#download-a-dossier-pdf) | A saved dossier version with its notes, tables and pinned quotations in the development checkout. |

Reading websites are fixed exports, not live co-editing or project backups.
A publication profile selects dossier bodies or sections and chapter reveal
points. Reading progress is a convenience, not access control: use an export
chapter cap to omit later content from the files. Optional reader analysis is
recomputed on that exported text with default settings and can differ from the
project analysis. Work-marker notes are omitted from curated reader copies.

**Available in 0.8.0:** reader exports can also include existing chapter recordings with
`--include-audio`. Only audio matching the current manuscript and chapter cap is
copied; missing chapters remain visibly text-only. Export does not run synthesis.
The reader gets a player and WAV download, without your private voice references,
speech-profile settings or service endpoints.
[Include chapter audio](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#include-existing-chapter-recordings-unreleased).
Existing recordings enter through the explicit
`audio-import --project ROOT --audio WAV --chapter N --source-sha256 HASH`
command, with optional `--manuscript manuscript.md`. That binding records your selection;
it does not verify the spoken text or align the recording automatically.

Use **Check export** to inspect the prepared package, omitted media and missing
attribution before downloading. Original source files need an explicit inclusion
choice and redistribution rights. Website exports are beta; test the copy on the
recipient's device. The local **Project overview** inspects sources and existing
outputs without rebuilding analysis; filenames alone do not establish freshness.
[Export workflow](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#export-a-reading-website) ·
[PDF options](https://mfahsold.github.io/lixity/guides/research-pdf.html#manuscript-export).

### Use the same engine from scripts

```bash
lixity analyze manuscript.md --language en
lixity profile manuscript.md --layer asl --evidence
lixity project --project ./novel
lixity about --json
```

Start with `lixity --help`; `lixity COMMAND --help` explains each command
without running it. Help in 0.8.0 groups tasks and links the corresponding manual.
The CLI works without a running browser service. Root-local project settings,
explicit language selection and the shared pipeline keep browser and automation
workflows aligned. [Choose a command](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md#which-command-for-which-question)
or start with the [API contracts](https://github.com/mfahsold/lixity/blob/main/docs/AGENTS.md).
For a connected AI client, the [read-only MCP setup](https://github.com/mfahsold/lixity/blob/main/docs/AGENTS.md#model-context-protocol-mcp-server)
describes tool discovery and how to evaluate the client's handling of text.
The [Lixity skill](https://github.com/mfahsold/lixity/blob/main/skills/lixity/SKILL.md)
guides manuscript review, local research and service diagnosis.

## Documentation map

[Find a task in the documentation map](https://github.com/mfahsold/lixity/blob/main/docs/README.md) ·
[Wiki](https://github.com/mfahsold/lixity/wiki).

[Additional screenshots and image credits](https://github.com/mfahsold/lixity/blob/main/docs/screenshots/README.md).

| Looking for | Start here |
| :--- | :--- |
| First session | [Install and start](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md) · [Walkthrough](https://github.com/mfahsold/lixity/blob/main/docs/ONBOARDING.md) |
| Everyday use | [Workspace manual](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md) · [CLI and configuration reference](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md) |
| Audio and teleprompter | [Recording, direction, generation and exchange](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md) |
| Interpret results | [Reading measurements](https://mfahsold.github.io/lixity/guides/interpretation.html) |
| Research | [Workflows and compatibility](https://github.com/mfahsold/lixity/blob/main/docs/research/USAGE.md) · [Data model](https://github.com/mfahsold/lixity/blob/main/docs/research/DATA_MODEL.md) |
| Measurements | [Methods](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md) · [Checks and limits](https://github.com/mfahsold/lixity/blob/main/docs/STABILITY.md#core-validation-status) |
| Integrations | [API contracts](https://github.com/mfahsold/lixity/blob/main/docs/AGENTS.md) · [Architecture](https://github.com/mfahsold/lixity/blob/main/docs/ARCHITECTURE.md) · [Agent index](https://mfahsold.github.io/lixity/llms.txt) |
| Contributing | [Contributor setup and checks](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md) · [Security](https://github.com/mfahsold/lixity/blob/main/SECURITY.md) |

In the repository, [`src/lixity/`](https://github.com/mfahsold/lixity/tree/main/src/lixity)
contains the shared engine, CLI and UI;
[`tests/`](https://github.com/mfahsold/lixity/tree/main/tests) verifies behavior;
[`docs/`](https://github.com/mfahsold/lixity/tree/main/docs) holds maintained product
documentation; and [`samples/`](https://github.com/mfahsold/lixity/tree/main/samples)
contains synthetic or public-domain examples. Book-specific adapters belong in
their own projects.

## Release, citation and license

> **Version line:** The documentation source version is **v0.9.1**, in the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the numbering reset; use the current
> release rather than the numerically largest tag. Product, JSON response and
> archive schema versions are independent.

Use the [latest published release](https://github.com/mfahsold/lixity/releases/latest)
for published packages and their upgrade notes. The source
[release notes](https://github.com/mfahsold/lixity/blob/main/docs/releases/v0.9.1.md) describe
the version prepared in this repository. See the
[changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) for work
in progress. For local updates and website availability, see the
[installation guide](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md).

Cite [Lixity on Zenodo](https://doi.org/10.5281/zenodo.23390297), with metadata in
[`CITATION.cff`](https://github.com/mfahsold/lixity/blob/main/CITATION.cff).
The [software paper draft](https://github.com/mfahsold/lixity/blob/main/paper/paper.md)
describes its research context.

**AGPL-3.0-or-later.** Use Lixity for private or commercial writing, research and
teaching, including self-publishing your book. A separate written commercial
license is available for integrations that cannot meet the AGPL.
[Licensing guide](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md) ·
[Full terms](https://github.com/mfahsold/lixity/blob/main/LICENSE) ·
[Legal notice and contact](https://mfahsold.github.io/lixity/#impressum).
