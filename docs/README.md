# Lixity documentation

Lixity connects close reading, traceable research and linguistic text analysis in
one local manuscript workspace. Compare chapters, inspect the counted text behind
a measurement, follow a quotation to retained evidence and prepare a reading copy
with the background you choose to share.
The browser app, CLI and Python API share the analysis engine. The browser app
also supports [writing and recovery](WORKSPACE.md#write-a-manuscript).
The public demo and exported reading websites are fixed, read-only copies.

The app and its measurement reference support German, English, French, Spanish,
Italian, Portuguese and Dutch. The technical manuals are maintained in English.
[Language coverage](LOCALIZATION.md) explains differences in analysis support.
For a product introduction before reading the manuals, visit the
[Lixity website](https://mfahsold.github.io/lixity/) or try the
[read-only English example](demo/report.html) to compare two chapters.
The [browser sandbox](sandbox/index.html) lets you try the same questions
with a short passage in German or English.

Choose a task below. In a desktop test build, **Tools → System Status &
Extensions** shows the build and runtime details. For the published browser
app and CLI, use `lixity --version` and `lixity COMMAND --help`. The
[installation guide](INSTALLATION.md) covers both routes, and
[the changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) records work in progress.

## Start here

| Starting point | Read or try |
| --- | --- |
| See what Lixity does before installing | [Illustrated tour](guides/first-look.html) · [Read-only demo](demo/report.html) |
| Install, update or start the app | [Installation and service management](INSTALLATION.md) |
| Complete a first session with your manuscript | [First-session walkthrough](ONBOARDING.md) |
| Explore sentence rhythm, vocabulary or readability | [Browser workflow](WORKSPACE.md#explore-language-in-the-browser) · [Reproducible CLI analysis](USAGE.md#linguistic-text-analysis) · [Methods](METHODS.md) · [Limits](STABILITY.md) |
| Find an everyday browser action | [Workspace manual](WORKSPACE.md) |
| Run a command or configure a project | [CLI and configuration reference](USAGE.md) |
| Record, direct, generate, import or export audio | [Audio and teleprompter manual](AUDIO.md) |
| Retain sources, write dossiers or recover an archive | [Research manual](research/USAGE.md) |

## Find a task

| I want to… | Browser workflow | CLI or detailed reference |
| --- | --- | --- |
| Open an existing project or import a copy | [Open or import?](ONBOARDING.md#open-or-import) | [Project commands](USAGE.md) |
| Write, compare versions and recover manuscript prose | [Editing workflow](WORKSPACE.md#write-a-manuscript) · [Compare versions](WORKSPACE.md#compare-versions-and-resolve-a-conflict) | [Native editing contract](AGENTS.md#native-manuscript-editing) |
| Read a passage and understand a highlighted value | [Read and explore](ONBOARDING.md#read-and-explore) | [Measurement reference](guides/metrics/en.html) · [Choose an analysis command](USAGE.md#which-command-for-which-question) |
| Compare chapters and change analysis settings | [Workspace manual](WORKSPACE.md) | [Configuration](USAGE.md#configuration-corpusconfig) |
| Follow a quotation into retained evidence | [Research beside the manuscript](WORKSPACE.md#read-a-dossier-beside-the-manuscript) | [Research tasks](research/USAGE.md#find-a-task) |
| Draft a character dossier and review matching passages | [Review a manuscript dossier](ONBOARDING.md#review-a-manuscript-dossier) | [Manuscript-driven dossier drafts](research/USAGE.md#manuscript-driven-dossier-drafts) |
| Import sources from Zotero or scanned PDFs | [First Zotero capture](ONBOARDING.md#first-zotero-capture) | [Zotero](research/USAGE.md#zotero-desktop-bridge) · [PDF/OCR setup](research/USAGE.md#self-hosted-pdf-and-ocr-extraction) |
| Make one PDF for editing, reading or submission | [Download a manuscript PDF](WORKSPACE.md#download-a-manuscript-pdf) | [PDF layouts and command](USAGE.md#lixity-pdf) |
| Download one saved dossier version | [Download a dossier PDF](WORKSPACE.md#download-a-dossier-pdf) | [Dossier PDF contents](research/USAGE.md#download-a-dossier-as-pdf) |
| Share a read-only website or selected background notes | [Choose the recipient's copy](WORKSPACE.md#export-a-reading-website) | [Check and export the same scope](USAGE.md#lixity-export-site) |
| Generate project-local analysis artifacts | [Project outputs](WORKSPACE.md#inspect-project-structure) | [Preview or run a build](USAGE.md#lixity-build) |
| Record an author's voice or use the teleprompter | [Audio manual](AUDIO.md) | [Audio worker installation](INSTALLATION.md#optional-qwen-audio-worker) |
| Add chapter audio to a reading copy | [Audio generation and exchange](AUDIO.md) | [Reading website options](WORKSPACE.md#export-a-reading-website) |
| Reopen projects or check which local app is running | [Service management](INSTALLATION.md#running-the-server) | [Troubleshooting](INSTALLATION.md#troubleshooting) · [`doctor`](USAGE.md#lixity-doctor) |
| Back up a saved project inventory | [Project backup](PROJECT_BACKUP.md) | [CLI backup and restore](USAGE.md#verified-project-backup-unreleased) |
| Back up retained research and restore it | [Archive lifecycle](research/USAGE.md#storage-lifecycle-and-recovery) | [Export and restoration](research/USAGE.md#export-and-restoration) |

For the product's capability boundaries and proposed next priorities, see
[Product direction](PRODUCT.md). Priorities are recommendations, not release promises.

An analysis report, a curated reading website and a research backup are different
outputs. A reading copy does not replace a project backup. Research backups do not
include the manuscript or external linked attachments. The project
backup combines explicitly selected files with retained research.
The public demo is read-only. Recording, saving and generating new audio/PDFs
require the local application and, where applicable, separately installed tools.

## Understand results and integrate Lixity

- [Interpretation guide](guides/interpretation.html): how to read a difference before deciding whether it matters.
- [Methods](METHODS.md), [validation and limits](STABILITY.md) and [language support](LOCALIZATION.md): formulas, tested coverage and explicit unknowns. Measurements are not literary-quality scores.
- [Automation contracts](AGENTS.md): discovery, CLI/JSON, Python and HTTP interfaces. Repository agent instructions live separately in [AGENTS.md](https://github.com/mfahsold/lixity/blob/main/AGENTS.md).
- [Architecture](ARCHITECTURE.md) and [research data model](research/DATA_MODEL.md): implementation boundaries, state ownership and storage.
- [Lixity agent skill](https://github.com/mfahsold/lixity/blob/main/skills/lixity/SKILL.md) routes AI-assisted workflows to the maintained contracts. The source archive also includes the skill.
- [Contributor guide](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md): development, checks and release workflow.
- [Licensing](LICENSING.md) and [security](https://github.com/mfahsold/lixity/blob/main/SECURITY.md): usage terms and reporting issues.

## Which document owns an instruction?

| Information | Maintained reference |
| --- | --- |
| Published packages, prerequisites, update and service control | [Installation](INSTALLATION.md) |
| First session or an everyday browser task | [Onboarding](ONBOARDING.md) and [Workspace](WORKSPACE.md) |
| Commands, project configuration and machine responses | [CLI reference](USAGE.md) and [Automation contracts](AGENTS.md) |
| Domain tasks and data recovery | [Audio](AUDIO.md), [Research](research/USAGE.md) and [Project backup](PROJECT_BACKUP.md) |
| Counting rules, limits and validation | [Methods](METHODS.md), [Stability](STABILITY.md) and [Language support](LOCALIZATION.md) |
| Changes to source, checks and publication | [Contributor guide](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md) |

The [Wiki](https://github.com/mfahsold/lixity/wiki), illustrated guides and
[articles](blog/index.html) lead to these references. Rendered manuals are
available in the [GitHub repository](https://github.com/mfahsold/lixity/blob/main/docs/README.md).
Pages also serves the plain Markdown for downloads and automation.

For offline reading, retain a matching checkout and start with this file.
`llms-full.txt` is a generated text bundle of the operating references, not a
separate manual to edit. [Offline documentation](INSTALLATION.md#read-documentation-offline)
explains the installed help and bundle. Maintainers edit the canonical Markdown
or HTML page and regenerate mirrors with `make docs-sync`; see the
[documentation workflow](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#updating-documentation-and-pages).

## Historical records and proposals

- [Published releases](https://github.com/mfahsold/lixity/releases) link to the code and packages for each tag. The [release-note sources](https://github.com/mfahsold/lixity/tree/main/docs/releases) preserve earlier numbering and migration history. The top of the [changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) shows unreleased changes.
- [Manuscript editing RFC](MANUSCRIPT_EDITING_RFC.md) records the original design, acceptance criteria and deferred work. The [workspace manual](WORKSPACE.md#write-a-manuscript) and installed API describe current behavior.
- [Rust evaluation RFC](RUST_EVALUATION_RFC.md) preserves the performance hypothesis and experiment results. [Architecture](ARCHITECTURE.md) describes the implementation in use.
- The [research documentation map](research/README.md) links to the scientific review, original archive design and later proposals. [Research usage](research/USAGE.md) owns supported operations.
