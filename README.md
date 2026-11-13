# Lixity

[![Checks: local-first](https://img.shields.io/badge/checks-local--first-blue)](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
[![Mastodon](https://img.shields.io/badge/Mastodon-@lixity-6364ff?logo=mastodon&logoColor=white)](https://mastodon.social/@lixity)
[![Bluesky](https://img.shields.io/badge/Bluesky-@lixity.bsky.social-0285ff?logo=bluesky&logoColor=white)](https://bsky.app/profile/lixity.bsky.social)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

> **A private, local workspace for novelists, editors, and scholars.**
> Inspect chapter rhythms, verify scene research, and share standalone reading copies — 100% offline, privacy-first, and deterministic.
>
> 🚀 **[Interactive Demo](https://mfahsold.github.io/lixity/demo/report.html)** · ✍️ **[Browser Sandbox](https://mfahsold.github.io/lixity/sandbox/index.html)** · 📖 **[Read Demo Novel](https://mfahsold.github.io/lixity/demo/reader/index.html)** · ⚡ **[Install Guide](https://mfahsold.github.io/lixity/guides/installation.html)** · 📚 **[First-Look Tour](https://mfahsold.github.io/lixity/guides/first-look.html)**

**Read closely. Trace the evidence. Understand your text.**

Lixity is a private, local manuscript studio for novelists, dramatists, editors,
and linguistic researchers. It brings the craft of writing and the discipline of
text analysis into a single, beautifully restrained environment: sense where a
chapter's rhythm accelerates or falters, inspect the exact counted words behind
every metric, and trace scene details back to retained primary sources. Keep
dossiers, author decisions, and prose organically connected, then choose
precisely what to share in a standalone reading edition. The browser app, CLI,
and Python API share one deterministic analysis engine.

- **Every finding connects to prose:** chapter comparisons, outlier flags, and
  cadence explanations never live in isolated charts—they bring you directly back
  to the sentence in context, where you make the artistic call.
- **Research retains living memory:** primary sources, historical claims, and
  authorial decisions have distinct roles; evidence links preserve the exact
  revisions behind them even as sources or interpretations evolve.
- **Your work stays on your machine:** analysis runs 100% offline and deterministic.
  Zero telemetry, no forced cloud accounts, and no AI rewriting your prose.
  Sharing is always an intentional, explicitly curated export.

**Writing joins the workspace (unreleased).** The development checkout adds an
integrated, distraction-free manuscript editor with multi-level undo, local
autosave, conflict detection and recovery, search/replace, and a fluid single-row
writing bar with auto-hiding chrome. Switching between writing and reading
re-analyzes the saved revision while preserving your undo stack and editing
buffer intact. Research links remain reviewable across text revisions; saved
evidence is never silently rewritten. The public demo remains read-only.
See [editing scope and limits](https://mfahsold.github.io/lixity/WORKSPACE.md#write-a-manuscript-unreleased).

Lixity provides localized workspaces across seven languages ([Deutsch](https://mfahsold.github.io/lixity/index-de.html) ·
[English](https://mfahsold.github.io/lixity/) · [Français](https://mfahsold.github.io/lixity/index-fr.html) ·
[Español](https://mfahsold.github.io/lixity/index-es.html) · [Italiano](https://mfahsold.github.io/lixity/index-it.html) ·
[Português](https://mfahsold.github.io/lixity/index-pt.html) · [Nederlands](https://mfahsold.github.io/lixity/index-nl.html)),
while technical developer contracts remain in English. German and English offer the deepest heuristic resources;
see [language coverage and limits](https://mfahsold.github.io/lixity/LOCALIZATION.md).

**Explore patterns. Return to the text. Make your own interpretation.**
Measurements illuminate differences; they do not grade literary quality or tell
you how to write. Built-in analysis works offline. The engine accepts Markdown
or plain text. The app can also preview and convert a Word/DOCX file when
importing a copy; export Scrivener projects to a supported format first.

[Explore the demo workspace](https://mfahsold.github.io/lixity/demo/report.html) ·
[Read the example novel](https://mfahsold.github.io/lixity/demo/reader/index.html) ·
[English tour](https://mfahsold.github.io/lixity/guides/first-look.html) ·
[Einstieg auf Deutsch](https://mfahsold.github.io/lixity/guides/first-look-de.html) ·
[Install](https://mfahsold.github.io/lixity/guides/installation.html)

**Start without installing:** open the demo, inspect one marked passage, then
return to the scene and decide whether you would keep it.

The public demo follows six invented English harbour chapters and their linked
case notes. It needs no account or manuscript upload. It is a fixed, read-only
copy: importing, recording, changing settings and saving require the local app.
The demo and these docs follow current development; features labelled
**unreleased** may differ from your installed package.

For linguistic work, follow the [browser workflow](https://mfahsold.github.io/lixity/WORKSPACE.md#explore-language-in-the-browser)
or the [reproducible CLI workflow](https://mfahsold.github.io/lixity/USAGE.md#linguistic-text-analysis),
then read the [formulas](https://mfahsold.github.io/lixity/METHODS.md) and [interpretation limits](https://mfahsold.github.io/lixity/STABILITY.md).

## What can you do with Lixity?

The project is your creative anchor: manuscript prose, historical research, and
authorial settings stay together while you move naturally between composing,
close reading, investigation, and sharing. These are interwoven creative modes,
not rigid steps:

- **Compose & Refine**: Write in a clean typography canvas with local autosave,
  tactile review markers, and an auto-scrolling teleprompter for spoken auditions.
- **Listen to Cadence & Melody**: Compare sentence lengths, sticky-sentence
  glue-word density, dialogue balance, tag/adverbial-tag density, and voice
  separation (spoken dialogue vs. narrative prose), scene entry/exit hooks,
  intra-scene pacing dynamics and plateaus, declared POV chapter gaps, sensory
  perception (showing vs. telling), tense consistency, and optional
  non-prescriptive genre reference corridors across chapters. Every metric is
  grounded in transparent counts against chapter medians. In the reader,
  **Direct Speech Mode** (`D`) dims narrative prose to audition spoken dialogue
  alone, and inline evidence filter chips highlight **sticky sentences**,
  **dialogue tags**, and **same-paragraph word echoes** directly in the prose.
- **Anchor Scene Research**: Open dossiers alongside the manuscript (`Dossier daneben`).
  Connect facts, character motives, and scene geography directly to paragraphs.
- **Collaborate with AI on Your Terms (MCP)**: Run `lixity mcp` to connect Claude Desktop,
  Cursor, Antigravity, or local coding agents directly to 12 read-only analytical tools
  (including `lixity_scenes` and `lixity_corridors`) and 3 structured editorial prompts.
  Keep your manuscript strictly local with zero telemetry.
- **Curate Standalone Editions**: Generate beautiful print PDFs or self-contained,
  offline companion websites for beta readers and editors without exposing
  private working notes.

| Your task | Work in Lixity | What stays under your control |
| :--- | :--- | :--- |
| Read and revise a chapter | Continuous prose, search, work markers and passage tools | Analysis marks can be switched off; nothing rewrites the manuscript for you. |
| Back up a saved project (unreleased) | [Verified backup and restore](https://mfahsold.github.io/lixity/PROJECT_BACKUP.md) | Explicit file inventory, retained research and checksums; unsaved drafts are excluded. |
| Edit manuscript prose (unreleased) | Native CodeMirror editor with undo, local autosave and recovery | Conflicting external edits stop autosave; recovery is reviewed before applying. [Scope and limits](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#write-a-manuscript-unreleased). |
| Audit pacing, dialogue, and showing with AI | `lixity mcp` stdio server with 10 tools and 3 structured prompts | Deterministic, read-only analysis; no manuscript bytes or telemetry ever leave your machine. |
| Understand a change in voice or rhythm | Compare chapters, inspect counted words and sentences, open a measurement explanation | A statistical difference is a prompt for review, not an error or target score. |
| Investigate language use | Explore sentence lengths, lexical diversity and readability; export JSON with explicit analysis settings | Results describe the supplied text, not a representative population or proof of authorship. |
| Explain a scene detail | Link a quotation to a claim, its source passages, a dossier and an author decision | Evidence, assertions and creative decisions remain separate; exact linked versions are retained. |
| Hear a passage | Prepare direction, pronunciation rules and pauses; review a short recording or synthesis preview | Speech planning needs no worker. Recording needs permission; synthesis uses the explicitly selected service. |
| Share a reading copy | Choose manuscript, curated companion notes, analysis or a printable PDF | Preview the contents before export; a fixed copy does not expose your live project. |

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

<a id="start-here"></a>

## Share one revision experience

What did you want to check? Did the explanation help? What got in the way?
[Send a short description](mailto:mfahsold@googlemail.com?subject=Lixity%20feedback)
or [report a reproducible issue](https://github.com/mfahsold/lixity/issues).
You do not need to share manuscript text to give useful feedback.

## Install and start

Install [uv](https://docs.astral.sh/uv/), then run on Windows, macOS or Linux:

```bash
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

In a new terminal:

```bash
lixity --version
lixity service start --open
```

Choose **Open Project** or **Analyze a manuscript**, then confirm the language.
The engine reads `.md`, `.markdown` and `.txt`; the app can also preview and
convert a `.docx` file when importing a copy. Retaining a PDF as research is a
separate action. English is the default analysis language;
automatic detection is an explicit choice.

[Your first project](https://mfahsold.github.io/lixity/ONBOARDING.md) covers
opening, importing and settings. The
[installation guide](https://mfahsold.github.io/lixity/INSTALLATION.md) covers
updates, local launchers and removal. After upgrading, run
`lixity service restart --open` and reload the browser: installation alone does
not update a running service. `lixity doctor` identifies the installed package
and owned service.

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
[Language coverage](https://mfahsold.github.io/lixity/LOCALIZATION.md) ·
[Grammatical tense setup](https://mfahsold.github.io/lixity/USAGE.md#grammatical-tense).

### Keep research connected and versioned

A dossier gathers authored notes, retained source passages, claims, decisions,
images and maps. Passage associations return to their manuscript context. A linked
earlier version remains distinct from the current entry. Configured terms and
props locate declared wording and connect it to dossiers; they do not infer
characters or automatically verify continuity.

Research is scoped to an explicit project. Retaining a source and redistributing
it are separate choices. Original PDFs, images and videos have their own import
and export controls. Existing archives require a reviewed migration before
adopting a newer storage format.
[Research workflows](https://mfahsold.github.io/lixity/research/USAGE.md) ·
[Data model](https://mfahsold.github.io/lixity/research/DATA_MODEL.md).

### Record, direct and listen

**Available in 0.8.0:** open **Project → Settings → Audio and services**
for author recordings, voice profiles, microphone settings, services and the audio
queue. **Listen & direct** is also available from the manuscript toolbar. The
four audio tabs separate recording, profile/service setup, passage direction and
hardware levels. A shared player provides elapsed/total time, seeking, volume
and a measured frequency spectrum.

Record a short author reference or import a WAV, review the actual words and
confirm the transcript before saving. Browser microphone permission belongs to
the current local address; changing hardware gain cannot grant it. Permission,
recording and failure states appear beside the recording button.
[Recording and troubleshooting](https://mfahsold.github.io/lixity/AUDIO.md#author-voice-recording-and-listening).

The manuscript **Teleprompter** (`P`) combines adjustable scrolling with the
canonical spoken text, direction cues, pauses and explicit IPA annotations.
Record a take, edit its transcript, download its WAV plus JSON metadata, or hand
it to the author-voice studio for review. A reading script is not an exact
transcript. The scrolling rate is approximate; it does not track live speech.
[Teleprompter and take exchange](https://mfahsold.github.io/lixity/AUDIO.md#manuscript-teleprompter-direction-cues-phonetics-and-synchronized-dossier-images).

Speech planning and synthesis are separate actions. Export a passage, chapter or
manuscript as JSON or SSML without a running speech worker. JSON retains the
supported authored controls; SSML reports portability limits. Optional local
Qwen, Coqui/OpenVoice and IMS-Toucan setups have different voice, language and
direction capabilities. IMS-Toucan's optional German/English path supports
separate IPA overrides and structured passage-level duration/prosody controls;
it does not interpret free acting prompts. Existing F5 profiles remain readable,
but the bundled F5 runtime is unavailable.
[Choose and set up a speech engine](https://mfahsold.github.io/lixity/INSTALLATION.md#ims-toucan-author-voice-and-phonetic-direction).

An explicitly configured external speech provider receives selected text only
when rendering is requested. Audio plans may include provider URLs, model names
and credential-variable names, so review them before sharing. Audio inspection
can measure a local recording; comparison with planned words requires a supplied,
timestamped transcript. Lixity does not perform speech recognition. Listen to a
short preview before committing to a long render.
[Audio workflow and limits](https://mfahsold.github.io/lixity/AUDIO.md#audio-export-and-external-providers-unreleased).

### Choose what leaves the project

| Copy | Contents and purpose |
| :--- | :--- |
| [Review workspace](https://mfahsold.github.io/lixity/demo/report.html) | Manuscript and analysis, optionally internal research and history; for author/editor review. |
| [Novel with companion notes](https://mfahsold.github.io/lixity/demo/reader/index.html) | Manuscript with explicitly selected dossier notes, plus optional analysis of the exported chapters. |
| [Standalone companion](https://mfahsold.github.io/lixity/demo/companion/index.html) | Selected background material for someone reading the novel elsewhere. |
| PDF | Neutral/editorial manuscript, analysis report, A5 book or submission sheet. |

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
[Include chapter audio](https://mfahsold.github.io/lixity/WORKSPACE.md#include-existing-chapter-recordings-unreleased).
Existing recordings enter through the explicit
`audio-import --project ROOT --audio WAV --chapter N --source-sha256 HASH`
command, with optional `--manuscript manuscript.md`. That binding records your selection;
it does not verify the spoken text or align the recording automatically.

Use **Check export** to inspect the prepared package, omitted media and missing
attribution before downloading. Original source files need an explicit inclusion
choice and redistribution rights. Website exports are beta; test the copy on the
recipient's device. The local **Project overview** inspects sources and existing
outputs without rebuilding analysis; filenames alone do not establish freshness.
[Export workflow](https://mfahsold.github.io/lixity/WORKSPACE.md#export-a-reading-website) ·
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
workflows aligned. [Choose a command](https://mfahsold.github.io/lixity/USAGE.md#which-command-for-which-question)
or start with the [API contracts](https://mfahsold.github.io/lixity/AGENTS.md).

## Documentation map

[Find a task in the complete documentation map](https://mfahsold.github.io/lixity/README.md).

[Additional screenshots and image credits](https://mfahsold.github.io/lixity/screenshots/README.md).

| Looking for | Start here |
| :--- | :--- |
| First session | [Install and start](https://mfahsold.github.io/lixity/INSTALLATION.md) · [Walkthrough](https://mfahsold.github.io/lixity/ONBOARDING.md) |
| Everyday use | [Workspace manual](https://mfahsold.github.io/lixity/WORKSPACE.md) · [CLI and configuration reference](https://mfahsold.github.io/lixity/USAGE.md) |
| Audio and teleprompter | [Recording, direction, generation and exchange](https://mfahsold.github.io/lixity/AUDIO.md) |
| Interpret results | [Reading measurements](https://mfahsold.github.io/lixity/guides/interpretation.html) |
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

> **Version line:** The documentation source version is **v0.8.0**, in the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the numbering reset; use the current
> release rather than the numerically largest tag. Product, JSON response and
> archive schema versions are independent.

[Release notes](https://mfahsold.github.io/lixity/releases/v0.8.0.md)
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
