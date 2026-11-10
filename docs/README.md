# Lixity documentation

Lixity connects close reading, traceable research and linguistic text analysis in
one local manuscript workspace. Compare chapters, inspect the counted text behind
a measurement, follow a quotation to retained evidence and prepare a reading copy
with the background you choose to share.
The browser app, CLI and Python API provide different ways into the same platform;
they do not promise identical commands or independently implemented analysis.

Integrated manuscript writing is **unreleased**: the development checkout adds
undo, local autosave and explicit conflict recovery. Read the
[editing workflow and current limits](WORKSPACE.md#write-a-manuscript-unreleased)
before using it. The public demo and exported websites remain read-only.

Technical documentation is maintained in **English only**. The app interface
supports German, English, French, Spanish, Italian, Portuguese and Dutch;
[language coverage](LOCALIZATION.md) explains differences in analysis support.
For a product introduction before reading the manuals, visit the
[Lixity website](https://mfahsold.github.io/lixity/) or try the
[read-only English example](demo/report.html).

Choose a task below. The manuals describe the current source tree; sections
marked **unreleased** can differ from an installed package even when the version
number matches. Use `lixity --version` and `lixity COMMAND --help` to check your
installation. The [installation guide](INSTALLATION.md#cli-current-release) links
the release notes for its documented baseline;
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
| Write and recover manuscript prose (unreleased) | [Editing workflow](WORKSPACE.md#write-a-manuscript-unreleased) | [Editing architecture and remaining work](MANUSCRIPT_EDITING_RFC.md) |
| Read a passage and understand a highlighted value | [Read and explore](ONBOARDING.md#read-and-explore) | [Choose an analysis command](USAGE.md#which-command-for-which-question) |
| Compare chapters and change analysis settings | [Workspace manual](WORKSPACE.md) | [Configuration](USAGE.md#configuration-corpusconfig) |
| Follow a quotation into retained evidence | [Research beside the manuscript](WORKSPACE.md#read-a-dossier-beside-the-manuscript) | [Research tasks](research/USAGE.md#find-a-task) |
| Import sources from Zotero or scanned PDFs | [First Zotero capture](ONBOARDING.md#first-zotero-capture) | [Zotero](research/USAGE.md#zotero-desktop-bridge) · [PDF/OCR setup](research/USAGE.md#self-hosted-pdf-and-ocr-extraction) |
| Make a PDF or a reading website | [Choose the exported content](WORKSPACE.md#export-a-reading-website) | [PDF command](USAGE.md#lixity-pdf) · [CLI reference](USAGE.md#command-reference) |
| Record an author's voice or use the teleprompter | [Audio manual](AUDIO.md) | [Audio worker installation](INSTALLATION.md#optional-qwen-audio-worker) |
| Add chapter audio to a reading copy | [Audio generation and exchange](AUDIO.md) | [Reading website options](WORKSPACE.md#export-a-reading-website) |
| Stop, restart or repair the app | [Service management](INSTALLATION.md#running-the-server) | [Troubleshooting](INSTALLATION.md#troubleshooting) · [`doctor`](USAGE.md#lixity-doctor) |
| Back up a saved project inventory (unreleased) | [Project backup](PROJECT_BACKUP.md) | [CLI backup and restore](USAGE.md#verified-project-backup-unreleased) |
| Back up retained research and restore it | [Archive lifecycle](research/USAGE.md#storage-lifecycle-and-recovery) | [Export and restoration](research/USAGE.md#export-and-restoration) |

For the product's capability boundaries and proposed next priorities, see
[Product direction](PRODUCT.md). Priorities are recommendations, not release promises.

An analysis report, a curated reading website and a research backup are different
outputs. A reading copy does not replace a project backup. Research backups do not
include the manuscript or external linked attachments. The unreleased project
backup combines explicitly selected files with retained research.
The public demo is read-only. Recording, saving and generating new audio/PDFs
require the local application and, where applicable, separately installed tools.

## Understand results and integrate Lixity

- [Interpretation guide](guides/interpretation.html): how to read a difference before deciding whether it matters.
- [Methods](METHODS.md), [validation and limits](STABILITY.md) and [language support](LOCALIZATION.md): formulas, tested coverage and explicit unknowns. Measurements are not literary-quality scores.
- [Automation contracts](AGENTS.md): discovery, CLI/JSON, Python and HTTP interfaces. Repository agent instructions live separately in [AGENTS.md](https://github.com/mfahsold/lixity/blob/main/AGENTS.md).
- [Architecture](ARCHITECTURE.md) and [research documentation map](research/README.md): implementation boundaries, storage and clearly marked proposals.
- [Manuscript editing RFC](MANUSCRIPT_EDITING_RFC.md): CodeMirror 6, source fidelity, autosave and recovery; distinguishes the unreleased first implementation from future work.
- [Contributor guide](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md): development, checks and release workflow.
- [Licensing](LICENSING.md) and [security](https://github.com/mfahsold/lixity/blob/main/SECURITY.md): usage terms and reporting issues.

## Which document owns an instruction?

Installation owns environments, optional tools and service lifecycle. Onboarding
is one short session. The workspace, CLI, audio and research manuals own their
respective operating instructions; illustrated guides and [articles](blog/index.html)
provide examples and link back to those manuals. The [wiki](https://github.com/mfahsold/lixity/tree/main/docs/wiki)
is a short route into the same documentation, not a second command reference.
Historical release notes and research RFCs are not descriptions of every current
feature. An RFC being linked does not make its proposals available commands.

For offline reading, retain a matching checkout and start with this file.
`llms-full.txt` is a generated text bundle of the operating references, not a
separate manual to edit. [Offline documentation](INSTALLATION.md#read-documentation-offline)
explains the installed help and bundle. Maintainers edit the canonical Markdown
or HTML page and regenerate mirrors with `make docs-sync`; see the
[documentation workflow](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#updating-documentation-and-pages).
