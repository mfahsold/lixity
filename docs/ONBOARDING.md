# Start using Lixity

Lixity helps you explore sentence rhythm, vocabulary and style patterns in a
Markdown manuscript on your computer. These signals point to passages worth
reviewing; they do not measure literary quality or prescribe edits.

Install Lixity using the [installation guide](INSTALLATION.md). Commercial use,
including a book intended for sale or self-publishing, requires a separate
written license; see [Licensing](LICENSING.md).

## Choose your starting point

| What you want to do | Start here |
| --- | --- |
| Explore a manuscript | Build a dashboard using the commands below. |
| Return to an existing project | Choose **Open Project** or run `lixity serve /path/to/project`. |
| Start a project | Run `lixity serve --no-project` and choose **New Project**. |
| Keep research sources | Open an initialized research project, or initialize one as shown below. |
| Capture sources from Zotero | Follow the [Zotero setup](research/USAGE.md#zotero-desktop-bridge-since-v1190), then select attachments in the dashboard. |

## Start with a manuscript

Save your manuscript as a UTF-8 Markdown file. Use `## Chapter title` headings
and blank lines between paragraphs. From its folder, run:

```sh
lixity analyze manuscript.md --language en
lixity build manuscript.md --language en
```

Open `exports/manuscript_dashboard.html` in your browser. `analyze` gives a
terminal report; `build` saves the dashboard and other analysis reports in
`exports/`. The original manuscript stays in its project folder.

Choose the language of your manuscript: use `--language de` for German or
`--language en` for English. English is the default. Explicit
`--language auto` requests detection; weak or ambiguous evidence uses the
generic profile. German and English currently have the most extensive
linguistic resources and tests; other supported profiles have more limited
coverage. See [language support and limitations](LOCALIZATION.md).

Start with a longer passage and several chapters when possible. Some results
are unavailable for short texts or chapters without measurable variation. Read
the [interpretation guide](guides/interpretation.html) before treating a
highlight as a reason to revise.

## Use the interactive workspace

```sh
lixity serve --no-project --port 8765
# Or open an existing project:
lixity serve ./my-novel --port 8765
```

Open `http://127.0.0.1:8765/`. The workspace has three views:
**Research & Dossiers**, **Manuscript & Analysis**, and **Project & Settings**.
Since v2.3.0, the welcome guidance follows three steps: choose or open a
manuscript, confirm its language in the import preview, then read a passage behind
a signal. **Analyze a manuscript** opens the existing import dialog; analysis
starts after you confirm the preview. **Research and further analysis** expands
optional guidance. An empty manuscript view offers the same import action.
**New Project**, **Open Project** and optional welcome guidance remain available
in every view. Hide the guidance when you no longer need it; **Show guidance**
reopens it. The browser remembers this preference when local storage is available.

### Open or import?

**Open Project** reconnects an existing folder and its research archive. Enter
a folder or manuscript path, or use **Browse files and folders**. The chooser
shows files on the computer running Lixity. **Home** and **Parent folder** help
you navigate; choose a manuscript or **Select this folder**, then **Open**.
Browsing or cancelling does not switch projects.

**New Project → Import Manuscript** creates a separate project from a selected
or dropped `.md`, `.markdown` or `.txt` file. It does not reopen the original
folder or its research. Selecting a file opens its preview directly; you confirm the new
project in the import dialog. **Start New Manuscript** creates a project from a
template. The Research Novel template also initializes a research archive.

An initialized research-only folder can be opened without a manuscript. Its
sources and notes remain available; manuscript analysis and comparison need a
loaded manuscript. All browser tabs connected to one server share its active
project, so check the displayed path when switching.

### Read and explore

**Since v2.4.0:** the native workspace adds a manuscript PDF form
at the top of **Manuscript & Analysis**, before **Start your review**. Select
**A5 reading copy** (the default), **A4 manuscript sheets** or **A4 analysis report**,
then select **Download PDF**. It generates a PDF from the currently selected
manuscript and returns it through your browser; it creates no server export files
and changes neither the manuscript nor the research archive. The form needs
JavaScript and a compatible live native server; standalone HTML reports do not
provide the download action.
The [`lixity pdf`](USAGE.md#lixity-pdf) terminal command remains available.

The **Start your review** panel appears before the measurements. **Open passage**
opens the first paragraph in source order that meets the selected tense-flag
threshold, or the opening paragraph when none does. It clears manuscript search
and paragraph filters so the text is visible, and moves keyboard focus to the
opened paragraph. This is a place to begin reading, not a quality ranking.

**Explore chapters** opens the style comparison when it is available; otherwise
it opens the chapter map with an explanation of the comparison's limits.
**Open sentence rhythm** is offered when measurements are available. Read the
passage before drawing conclusions from either view. Paragraph text appears
first; expand **Values** for source lines and measurements.

The manuscript view provides chapter and paragraph navigation, style signals
and analysis controls. Dotted-underlined terms have explanations: hover, use
keyboard focus, or tap. Press Escape or tap again to dismiss them. Statistical
settings also show their explanations beside the fields.

A saved HTML dashboard is a read-only analysis export. The local server adds
project and research actions using the same analysis engine. It is not a full
manuscript editor. The NDA generator downloads a friendly confidentiality agreement
using the recipient's name,
optional address, project, date and place; see the
[NDA reference](USAGE.md#nda-agreements).
Set **Author name** in the loaded project's Settings to prefill the project
representative in the agreement. Apply stores that name in the project. The
read-only manuscript identity check shows matching, missing or different metadata;
it does not edit prose or establish who wrote the text.
Book-specific publication and delivery integrations belong to project adapters;
the shared manuscript PDF layouts are described in the [PDF reference](USAGE.md#lixity-pdf).

## Research workflow

The research workspace is experimental. It keeps sources, quotations and authored
notes separate from manuscript analysis. Import a source only when you are
allowed to retain its original bytes. Retention does not grant redistribution
rights or verify a historical claim.

To initialize a new research archive and retain an authorized text source:

```sh
lixity research init --project ./my-novel --title "Novel research" --language en
lixity research ingest --project ./my-novel --file ./source.txt \
  --allow-retention --title "Library note"
lixity research search --project ./my-novel --query "reading room"
```

Research commands stay project-scoped. Since v2.4.0, the CLI also
accepts the validated initialized current directory for existing-archive commands;
it searches no parent folders or last-opened projects. Use `--project` when
working from elsewhere; it remains authoritative. See [CLI selection and the
link shortcut](research/USAGE.md#reading-and-cli-workflows-since-v240).
Search updates a stale search index
automatically unless `--strict` is requested. CLI search defaults to source
passages; `--scope all` also searches current dossiers, claims and decisions.
The dashboard searches all these record types by default. Only source passages
can be cited as evidence.

In the dashboard, select a source or dossier to read its details and citations.
Source and dossier filters narrow the loaded lists; **Search** looks through
retained text. A source-passage search result offers **Use for claim** and
**Use for dossier** actions.

**Since v2.4.0:** select text inside one source paragraph to prepare
a claim evidence-link draft. Read the selected quote and complete paragraph
context in the preview, choose the claim and evidence relation, then save
explicitly. The citation retains the whole source paragraph; selecting a
sentence does not create a sentence-level citation. Cross-paragraph or ambiguous
selections are unavailable; whole-passage actions remain in the Passages view.

Open **Dossier alongside** in **Manuscript & Analysis** and choose a dossier,
or use the matching action on a dossier card. Opening the optional view alone
does not choose a dossier. It is read-only, and closing it preserves manuscript
search and open paragraphs. Other analysis panels are temporarily hidden in this
focused reading view and return when you close it. Refresh explicitly for the latest saved dossier
revision; the selection lasts for the current page. The dossier appears above
the manuscript on narrow screens. Evidence status labels express your own
assessment; they do not certify historical facts.

For a visual reference, open a dossier and choose **Add image**. Select an
authorized local PNG/JPEG, add a short description, preview it and confirm
retention before saving. Original bytes and the dossier version are saved together.
Image sources have no searchable text or linguistic scores. Optional captions and
source notes help you remember what the picture can—and cannot—support.

Use **Add claim** or **Add decision** from that dossier to keep the topic selected
in the existing form. **Edit section** limits a revision to one unique heading;
you still review conflicts and explain the change before saving.

The records have different purposes:

- A **source** is retained evidence; its passages support exact quotations.
- A **dossier** collects notes, sections and cited passages on a topic.
- A **claim** records an assertion or hypothesis and an author-selected confidence
  label. Evidence links describe whether a passage supports, contradicts,
  qualifies or provides context for it.
- A **decision** records an author's choice and rationale. A linked dossier is
  marked for review when subsequent decisions are recorded.

These links support review, not automated proof. An unmarked deviation from fact
does not certify accuracy. If a source is purged, affected citations in retained
authored records show as unavailable rather than revealing deleted text.
See [Research usage](research/USAGE.md) for batch import, claim and decision
commands, backups and archive limits.

## Use Zotero for sources and media (since v1.19.0)

Zotero can remain your catalogue for books, PDFs and other media. Lixity captures
selected PDF/text attachments so that a later change in Zotero does not silently
change an earlier quotation. Images, audio and video stay in Zotero; Lixity does
not transcribe them. Scanned PDFs need local Tesseract or a configured OCR worker.

### First Zotero capture

Install Zotero on the computer running Lixity, enable its local API and download
the attachments you need. In **Research → Sources → Zotero**, choose the intended
library and collection, inspect an item, select an attachment and confirm
retention. Review its details and check a quotation against the original.

Before using an existing archive with a newer capture format, back it up and keep
all archive readers and writers on a compatible version. Follow the
[Zotero setup, migration and backup reference](research/USAGE.md#zotero-desktop-bridge-since-v1190)
for dry-run previews, explicit refresh and export. Capturing sources does not
enable automatic synchronization.

## Check your first session and return later

Before relying on a workspace, check its displayed project path, manuscript
language and a sample quotation against the source. For Zotero captures, also
check the original-item link and metadata. A successful search does not verify
a claim.

Stop a foreground server with Ctrl+C. To return, run
`lixity serve /path/to/project` and open the existing project. After updating
Lixity or changing OCR settings, restart the server; a browser reload alone does
not load updated code. See [server setup and restart](INSTALLATION.md#running-the-server).

Back up the manuscript separately from the research archive. Paired
research/Zotero backups exclude manuscripts and external linked attachments.
The [research command reference](research/USAGE.md) describes implemented
behavior; the [research RFC](research/README.md) also contains future proposals.
