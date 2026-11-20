# Lixity

[![Checks: local-first](https://img.shields.io/badge/checks-local--first-blue)](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup)
[![PyPI](https://img.shields.io/pypi/v/lixity)](https://pypi.org/project/lixity/)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.23390297.svg)](https://doi.org/10.5281/zenodo.23390297)
[![Mastodon](https://img.shields.io/badge/Mastodon-@lixity-6364ff?logo=mastodon&logoColor=white)](https://mastodon.social/@lixity)
[![Bluesky](https://img.shields.io/badge/Bluesky-@lixity.bsky.social-0285ff?logo=bluesky&logoColor=white)](https://bsky.app/profile/lixity.bsky.social)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: AGPL-3.0](https://img.shields.io/badge/license-AGPL--3.0-blue)

> **A local workspace for authors, editors, and researchers.**
> Compare chapter rhythms, trace scene research to its sources, and choose what to share in a reading copy. Built-in analysis runs offline.
>
> 🚀 **[Interactive Demo](https://mfahsold.github.io/lixity/demo/report.html)** · ✍️ **[Browser Sandbox](https://mfahsold.github.io/lixity/sandbox/index.html)** · 📖 **[Read Demo Novel](https://mfahsold.github.io/lixity/demo/reader/index.html)** · ⚡ **[Install Guide](https://mfahsold.github.io/lixity/guides/installation.html)** · 📚 **[First-Look Tour](https://mfahsold.github.io/lixity/guides/first-look.html)**

**Read closely. Follow the evidence. Decide what to revise.**

Lixity keeps manuscript prose, stylometric signals, and scene research in one
offline workspace. Compare chapter rhythms, inspect dialogue and repeated words
in context, trace scene details to versioned sources and author decisions, and
export clean PDFs or self-contained reading websites.

- **Return from signal to prose:** jump from any chapter outlier or marked
  passage straight to the counted words and sentences. Signals support human
  review; they never grade literary quality or rewrite prose.
- **Keep research traceable:** sources, claims, and author decisions stay
  distinct and retain the exact linked versions across edits.
- **Local-first by default:** analysis, editing (native editor with undo,
  autosave, and recovery), and exports run offline without accounts or
  telemetry. Supports `.md`, `.txt`, and `.docx` import.

**Try without installing.** Shorten a sentence or trace a repeated word in the
[Browser Sandbox](https://mfahsold.github.io/lixity/sandbox/index.html).
In the read-only [Demo Workspace](https://mfahsold.github.io/lixity/demo/report.html),
compare average sentence lengths in two fictional harbour chapters, then open
the corresponding passages. The demo shows a fixed project snapshot and
identifies the development version that generated it.
Tours: [English](https://mfahsold.github.io/lixity/guides/first-look.html) ·
[Deutsch](https://mfahsold.github.io/lixity/guides/first-look-de.html) ·
[Methods & limits](https://mfahsold.github.io/lixity/METHODS.md) ·
[Stability](https://mfahsold.github.io/lixity/STABILITY.md).

**Seven interface languages:**
[Deutsch](https://mfahsold.github.io/lixity/index-de.html) ·
[English](https://mfahsold.github.io/lixity/) ·
[Français](https://mfahsold.github.io/lixity/index-fr.html) ·
[Español](https://mfahsold.github.io/lixity/index-es.html) ·
[Italiano](https://mfahsold.github.io/lixity/index-it.html) ·
[Português](https://mfahsold.github.io/lixity/index-pt.html) ·
[Nederlands](https://mfahsold.github.io/lixity/index-nl.html)
([language coverage](https://mfahsold.github.io/lixity/LOCALIZATION.md)).

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
one Word (.docx) file. Confirm the analysis language before reading the results.
English is the default. Choose automatic detection to analyze in the detected language.

To work on another project, open the same address in a second tab and choose
**Project actions → Open Project**. Each tab keeps its own project view.

To return to a running workspace, use the address shown by `lixity service status`.
After updating the installation, run `lixity service restart --open` on the
same port and reload the browser. `lixity doctor` reports the CLI and service
versions. The package installed from PyPI follows the
[latest published release](https://github.com/mfahsold/lixity/releases/latest).
The demo and source documentation follow development.

[Open your first project](https://mfahsold.github.io/lixity/ONBOARDING.md) ·
[Start with a project path or use a custom port](https://mfahsold.github.io/lixity/guides/installation.html#existing-project) ·
[Update or remove Lixity](https://mfahsold.github.io/lixity/guides/installation.html#updates)

## What can you do with Lixity?

Keep manuscript prose, research, and project settings together as you move
between reading, comparison, research, and sharing:

- **Read and review passages:** read continuous prose, search, and place work
  markers. The native manuscript editor supports writing, local autosave and
  reviewed recovery. Use the teleprompter to rehearse a passage aloud, or create
  a local listening preview with Qwen, Coqui, IMS-Toucan, ZONOS3 or an explicit
  provider. ZONOS3 on Apple Silicon can reuse a private project voice reference;
  its tempo is conditioned inside the model, not reprocessed with FFmpeg.
- **Compare prose patterns:** explore sentence lengths, length-invariant
  lexical diversity (`MATTR`, `MTLD`, exact `HD-D`), dialogue balance,
  repeated words, and skew-aware robust style baselines (median/MAD with
  `Sn`/`Qn` fallback, split-MAD, medcouple, and regularized Mahalanobis
  distances), plus heuristic signals for scene pacing, sensory language,
  tense, and character voices. Compare chapters or drafts (`lixity diff`),
  triage passages with live-count filter pills, inline decision toggles, and
  auto-refreshing review, and return to the relevant prose. Optional genre
  reference ranges are descriptive, not targets. In the reader, **Direct Speech
  Mode** (`D`) dims narration to focus on dialogue; evidence filters highlight
  **sticky sentences**, **dialogue tags**, **same-paragraph word echoes**, and
  **indirect speech**. Try a classic in the
  [Browser Sandbox](https://mfahsold.github.io/lixity/sandbox/index.html?preset=pride-prejudice).
  **Unreleased:** the reference view explains its separate thresholds and warns
  when two comparable chapters cannot reach the configured deviation cutoff.
  Rank projections expose regularization; nominal FDR is exploratory selection,
  with no established error-rate calibration. See the
  [methods](https://mfahsold.github.io/lixity/METHODS.md#decision-legend-and-small-chapter-sets-unreleased).
- **Follow scene research:** open a dossier beside the manuscript and connect
  paragraphs to claims, source passages, weighted tag clouds, character notes,
  or scene geography.
- **Connect an AI client (MCP):** run `lixity mcp` for read-only analysis,
  research inspection and guided editorial prompts. Use `tools/list` to see
  what's available in your installation. Lixity returns results over local
  stdio. The connected client controls where it processes them.
- **Share selected material:** export a printable PDF or a self-contained,
  offline reading website for beta readers and editors. Choose which manuscript,
  companion notes, and analysis to include before exporting.

| Your task | Work in Lixity | What stays under your control |
| :--- | :--- | :--- |
| Read and revise a chapter | Continuous prose, search, work markers and passage tools | Analysis marks can be switched off; nothing rewrites the manuscript for you. |
| Back up a saved project | [Verified backup and restore](https://mfahsold.github.io/lixity/PROJECT_BACKUP.md) | Explicit file inventory, retained research and checksums; unsaved drafts are excluded. |
| Edit manuscript prose | Native CodeMirror editor with undo, local autosave and recovery | Conflicting external edits stop autosave; recovery is reviewed before applying. [Scope and limits](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#write-a-manuscript-unreleased). |
| Audit pacing, dialogue, and showing with AI | `lixity mcp` stdio server with read-only tools and structured prompts | Lixity's analysis runs offline; review the connected AI client's data handling before supplying manuscript text. |
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

> **Version line:** The documentation source version is **v0.9.0**, in the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the numbering reset; use the current
> release rather than the numerically largest tag. Product, JSON response and
> archive schema versions are independent.

[Release notes](https://mfahsold.github.io/lixity/releases/v0.9.0.md)
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
