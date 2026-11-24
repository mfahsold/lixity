# Lixity documentation

Use this index to find the reference for your task. The app and its metric
guides are available in German, English, French, Spanish, Italian, Portuguese
and Dutch. The technical manuals are maintained in English.
[Language coverage](LOCALIZATION.md)

## Start here

| Starting point | Read or try |
| --- | --- |
| Try a passage before installing | [Browser exercise in German or English](sandbox/index.html) · [Read-only example project in English](demo/report.html) |
| Find the installer or check your version | [Installation and updates](INSTALLATION.md) |
| Open your first manuscript and inspect a finding | [First session](ONBOARDING.md) · [Illustrated tour](guides/first-look.html) |

## Find a task

| I want to… | Workflow | Detailed reference |
| --- | --- | --- |
| Write, compare versions and recover a draft | [Editing and recovery](WORKSPACE.md#write-a-manuscript) · [Compare versions](WORKSPACE.md#compare-versions-and-resolve-a-conflict) | [Editing contract](AGENTS.md#native-manuscript-editing) |
| Find counted text or compare chapters | [Analysis overview and reading marks](WORKSPACE.md#explore-language-in-the-browser) · [Read a difference in context](guides/interpretation.html) | [Metric reference](guides/metrics/en.html) · [Analysis commands](USAGE.md#linguistic-text-analysis) |
| Follow a quotation or review a character dossier | [Dossier beside the manuscript](WORKSPACE.md#read-a-dossier-beside-the-manuscript) · [Review a draft dossier](ONBOARDING.md#review-a-manuscript-dossier) | [Research manual](research/USAGE.md#find-a-task) |
| Retain material from Zotero or scanned PDFs | [First Zotero capture](ONBOARDING.md#first-zotero-capture) | [Zotero](research/USAGE.md#zotero-desktop-bridge) · [PDF extraction and OCR](research/USAGE.md#self-hosted-pdf-and-ocr-extraction) |
| Share a manuscript, dossier or reading website | [Manuscript PDF](WORKSPACE.md#download-a-manuscript-pdf) · [Dossier PDF](WORKSPACE.md#download-a-dossier-pdf) · [Reading website](WORKSPACE.md#export-a-reading-website) | [PDF layouts](USAGE.md#lixity-pdf) · [Dossier PDF contents](research/USAGE.md#download-a-dossier-as-pdf) · [Website scope](USAGE.md#lixity-export-site) |
| Record a voice, use the teleprompter or add chapter audio | [Audio manual](AUDIO.md) | [Optional workers and setup](INSTALLATION.md#optional-qwen-audio-worker) |
| Reopen a project or inspect generated outputs | [Project structure and outputs](WORKSPACE.md#inspect-project-structure) | [Build outputs](USAGE.md#lixity-build) · [Service and diagnostics](INSTALLATION.md#running-the-server) |
| Back up and restore | [Project backup](PROJECT_BACKUP.md) includes the selected project files and retained research | [Research archive recovery](research/USAGE.md#export-and-restoration) covers retained evidence |

<a id="which-document-owns-an-instruction"></a>

## Understand results and integrate Lixity

| Information | Maintained reference |
| --- | --- |
| Counting rules, limits and tested language coverage | [Methods](METHODS.md) · [Validation and limits](STABILITY.md) · [Language support](LOCALIZATION.md) |
| CLI, project settings and machine-readable responses | [Commands and configuration](USAGE.md) · [Automation contracts and MCP](AGENTS.md) · [Agent skill](https://github.com/mfahsold/lixity/blob/main/skills/lixity/SKILL.md) |
| Application layers, local storage and evidence revisions | [Architecture](ARCHITECTURE.md) · [Research data model](research/DATA_MODEL.md) |
| Development, checks and publication | [Contributor guide](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md) · [Desktop maintainers' guide](https://github.com/mfahsold/lixity/blob/main/desktop/README.md) |
| Product priorities and feedback criteria | [Product direction](PRODUCT.md) |
| Licensing and reporting issues | [Licensing](LICENSING.md) · [Security](https://github.com/mfahsold/lixity/blob/main/SECURITY.md) |

Use **Tools → System Status & Extensions** to identify your desktop build. For
the CLI and local browser app, use `lixity --version`. The [installation
manual](INSTALLATION.md#read-documentation-offline) explains offline help.
The [Wiki](https://github.com/mfahsold/lixity/wiki), [illustrated guides](https://mfahsold.github.io/lixity/#guides)
and [articles](blog/index.html) link to the maintained references.
`llms-full.txt` bundles those references for offline tools and is generated
from the canonical Markdown and HTML.
[Documentation workflow](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#updating-documentation-and-pages)

## Historical records and proposals

- [Published releases](https://github.com/mfahsold/lixity/releases) link to the code and packages for each tag. The [release-note sources](https://github.com/mfahsold/lixity/tree/main/docs/releases) preserve numbering and migration history. The [changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md) tracks current development.
- The [manuscript editing design archive](MANUSCRIPT_EDITING_RFC.md) leads to the original design and acceptance criteria. The [workspace manual](WORKSPACE.md#write-a-manuscript) describes current editing.
- The [Rust evaluation](RUST_EVALUATION_RFC.md) records performance measurements and proposed experiments. [Architecture](ARCHITECTURE.md) describes the layers in use.
- The [research documentation map](research/README.md) links to the scientific review, archive design and later proposals.
