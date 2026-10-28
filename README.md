# Lixity

[![Checks: local-first](https://img.shields.io/badge/checks-local--first-blue)](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

**Find the passages worth a second look.**

Lixity brings **close reading, manuscript analysis and documented research** into
one local workspace for authors, editors and manuscript reviewers. Find changes
in rhythm or voice, inspect what a signal counted, and follow the sources and
creative decisions behind a scene detail. The manuscript stays at the centre.

**The reference is your own book. The editorial decision stays yours.**
Lixity helps explain where a draft changes; it does not grade literary quality
or automatically rewrite prose. Built-in analysis runs on your computer.
Manuscript input is Markdown or plain text; Word/DOCX and Scrivener need conversion.

[Open the example manuscript](https://mfahsold.github.io/lixity/demo/report.html) ·
[Take the short tour](https://mfahsold.github.io/lixity/guides/first-look.html) ·
[Install Lixity](https://mfahsold.github.io/lixity/guides/installation.html)

[Einstieg auf Deutsch](https://mfahsold.github.io/lixity/guides/first-look-de.html)

## What changes in a revision session?

| The question | The useful next step |
| :--- | :--- |
| Why does this chapter feel different? | Compare its rhythm, vocabulary and dialogue with the manuscript's own patterns, then read the counted text. |
| Is this repetition doing useful work? | Locate nearby phrase echoes and inspect the surrounding passage before keeping or changing them. |
| Why is this detail in the scene? | Follow a linked quotation to its dossier, retained source passages and explicit author decision. Exact earlier versions remain available. |
| How can an editorial observation be explained? | Keep the manuscript in view while moving between the measurement explanation and linked research; prepare an editorial PDF or a fixed review copy for the discussion. |
| What belongs in a reader's copy? | Choose a manuscript with selected companion notes, a standalone companion, a review workspace or a PDF, and check what the copy includes. |

**Since v0.7.6:** one local app address now retains independent
project views in multiple tabs. **App and audio** shows open views, actual
local/Jetson model readiness and a shared bounded audio queue. View URLs expire
when the app restarts; reopen projects from the app home.

**Since v0.7.6:** tense review cards show the original counted forms
and their exact manuscript locations before optional counts and heuristic help.
These cues explain a mark; they do not establish an author error.

Source evidence, authored claims and creative decisions stay distinct. A saved
source records the evidence used; it does not guarantee that a claim is true.
Reading copies are fixed exports, not a live co-editing service.

<a href="https://mfahsold.github.io/lixity/screenshots/dashboard-measurement-focus.png"><img src="https://mfahsold.github.io/lixity/screenshots/dashboard-measurement-focus.png" width="560" alt="Sentence-length explanation: A board moved has three words; its paragraph averages 4.4 words per sentence, with a separate chapter comparison"/></a>

**Why does chapter 2 feel faster?** With analysis on, inspect one sentence and
its paragraph's rhythm, then read the scene before deciding whether to revise.
This current-main capture shows the actual explanation, not a writing target.
[See the reading view](https://mfahsold.github.io/lixity/screenshots/dashboard-reader-focus.png).

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

## One project, from draft to reading copy

Read continuous prose with analysis available on demand. Keep a dossier beside
the passage, follow a source or an earlier linked version, then return to the
text. For an editor, that gives a concrete starting point for an observation;
for an author, it keeps the question and its supporting material together.

**Since v0.7.6:** configured terms and props add another route into the
manuscript. Declare a name, object or alternative term, inspect its occurrences
and chapter scopes, and connect it to a dossier. Dossier manuscript evidence
brings its linked quotations together; ordered collections organise related
notes. These are declared lexical checks and explicit links, not automatic
continuity checking or character understanding. See
[terms and props](https://mfahsold.github.io/lixity/research/USAGE.md#configured-terms-props-and-boundary-policies)
and the [release notes](https://mfahsold.github.io/lixity/releases/v0.7.7.md).

Optional grammatical tense analysis covers all seven interface languages using
explicitly installed local syntax models and shared language-specific verb-group rules. It distinguishes perfect, passive,
subjunctive and future constructions and can exclude recognized quotations.
Parser errors remain possible; lightweight pattern counts stay available without
model dependencies. See [grammatical tense setup](https://mfahsold.github.io/lixity/USAGE.md#grammatical-tense).

The browser app, CLI and Python API share one analysis pipeline;
`lixity --help` and `lixity about --json` describe installed capabilities.

Try the same fictional project as a
[novel with companion notes](https://mfahsold.github.io/lixity/demo/reader/index.html)
or a [standalone companion](https://mfahsold.github.io/lixity/demo/companion/index.html).
These curated reading copies are different from the analysis/research workspace:
they contain selected material, not the full archive.
Since v0.7.7, reading copies can optionally include selected chapter or language measurements,
or a fuller analysis of the exported chapters, in a reader copy. Its figures use
standard settings and may differ from project-specific analysis; later chapters
and internal work markers remain outside that copy.

<details>
<summary>Analysis controls, revision-aware research and other project tools</summary>

**Version scope:** these controls are included in v0.7.6. Verify the installed
package separately from the running app with `lixity doctor`; the public demo is a
read-only example, not your local installation.

Turn **Analysis** on beside the text and choose the visible metric. Switch
**Counted text** and **Paragraph comparison** independently. Violet underlines identify
counted spans; blue/orange value-and-arrow markers compare notable paragraphs
with their chapter. Both preferences persist in the browser. Hover, touch and the
paragraph menu explain the concrete text; the CLI exposes the same evidence with
`lixity profile manuscript.md --layer asl --evidence`.

**Since v0.7.6:** matrix cells and style-space loadings share
chapter measurements: meaning, units, manuscript reference and the other
metrics of the same chapter. Reading the text is an explicit next action;
chapter-only measurements do not invent word-level highlights.

`export-site --preflight` and the native **Check export** action
measure the prepared package before writing/downloading, including media not
packaged and missing attribution fields. Reading website exports are beta and
can be large; the check does not promise a package size or mobile performance. Existing research projects require the
[explicit manifest-storage migration](https://mfahsold.github.io/lixity/research/USAGE.md#migrate-manifest-storage)
before using the current compressed layout.

Lixity also shares versioned image, PDF and MP4/WebM attachments across
dossiers and reading copies, with explicit retention and source-file export
choices. [Media workflow and compatibility](https://mfahsold.github.io/lixity/research/USAGE.md#retain-a-pdf-or-video-in-a-dossier).

A passage's research associations open its claims and dossier beside the
manuscript, with a return to the passage. Current entries and exact linked earlier
versions remain distinct. Dossier editing offers `--body-only` section drafts and
`--compact` update receipts. `--preamble` targets the opening text,
`research media-context` corrects retained-media attribution without copying bytes,
and `dossier-images --missing-provenance` finds absent attribution fields; see the
[section-editing workflow](https://mfahsold.github.io/lixity/research/USAGE.md#work-on-one-dossier-section).
The native **Project overview** and `lixity project --project PATH` also separate
sources, existing outputs and read-only structure findings. They neither move
files nor establish that an output matches the current manuscript; see
[project inspection](https://mfahsold.github.io/lixity/USAGE.md#inspect-project-structure).

The audio workflow shares saved project voice profiles between
`lixity read-aloud` and the native interface. Version 0.7.7 separates project voice
profiles and chapter output from manuscript passage direction and preview. It adds
separately saved passage direction, source-bound text ranges, explicit silence and
a shared inspectable CLI/UI speech plan. Optional Qwen3-TTS 1.7B
CustomVoice provides preset voices and explicit style instructions through a
local worker or a configured Jetson over SSH. Version 0.7.7 also supports the
separately installed Qwen 1.7B VoiceDesign checkpoint for described voices;
voice consistency across segments is not guaranteed. It also supports
explicit project-local reference voices using the separately installed Base model;
its reference and transcript need a project backup, and Base does not interpret
free-form delivery instructions. Assign voice profiles to passages deliberately.
Piper is removed; existing profiles
require an explicit backed-up `audio-migrate` replacement. Select the
execution target per render in the CLI or dialog. CPU generation can be slow;
completed Qwen segments can be reused when retrying long renders. Audio remains
a prototype requiring listening review. Version 0.7.7 adds an optional FFmpeg
post-synthesis tempo factor; it is not native model rate control. See the
[read-aloud scope](https://mfahsold.github.io/lixity/USAGE.md#lixity-read-aloud)
before relying on an export. NDA generation produces a draft, not consent or
signatures. Dossier Markdown edits require explicit preview and apply.

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

> **Version line:** The documentation source version is **v0.7.7**, in the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the numbering reset; use the current
> release rather than the numerically largest tag. Product, JSON response and
> archive schema versions are independent.

[Release notes](https://mfahsold.github.io/lixity/releases/v0.7.7.md)
cover archive compatibility and upgrades. See the
[changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) for subsequent work.
The repository's generated demo follows the interface documented here, using a fictional project and read-only research. Importing
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
