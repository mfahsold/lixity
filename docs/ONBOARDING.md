# Start using Lixity

[Documentation map](README.md) · [Install Lixity](INSTALLATION.md) · [Workspace manual](WORKSPACE.md)

Start with one question about a passage. Open the words or sentence behind a
measurement, read the surrounding prose, and decide whether to keep reading
or revise the passage.

Before installing, [edit a short sample in the browser exercise](sandbox/index.html)
or [follow one finding in the read-only Warehouse 4 demo](guides/first-look.html#passage).
Use the [download guide](guides/installation.html#desktop) to check your system's
desktop options and find the published local browser installation. The desktop
app includes the local engine and opens from your application launcher.

<a id="the-journey-at-a-glance"></a>
<a id="see-a-finished-example-first"></a>
## Choose your starting point

| Your starting point | Action |
| --- | --- |
| A folder where you already work | Choose **Open a project folder**, select the folder containing your manuscript, and confirm in the form. From an open workspace, use **Project actions → Open Project**. |
| A file to copy into a new project | Choose **Import a manuscript** on the welcome screen, or **Project actions → New Project → Import manuscript**. Lixity previews a Word, Markdown, or plain-text file before copying it. |
| A new manuscript | Choose **Start writing**, enter a title and manuscript language, and create the project. From an open workspace, use **Project actions → New Project → Start new manuscript**. |
| An example to explore first | In the desktop app, choose **Try the example offline** to preview the bundled English manuscript. Check the destination and choose **Import and analyze manuscript** to create an editable copy. The browser workspace links to the [read-only Warehouse 4 demo](demo/report.html). |

In the desktop app, new and imported manuscripts use a new folder under
`~/Lixity` by default. Check the proposed folder in the form. You can enter
a different folder before creating the project. The published browser app can
show the welcome actions as **Open Project** and **Analyze a manuscript**.

## Session checklist

1. Open or create the project and confirm its folder and manuscript language.
2. Read a paragraph in **Manuscript**. Follow one counted sentence to its
   explanation and press Escape to return to the passage.
   [Read and explore](#read-and-explore)
3. When you want to revise it, choose **Write**. Check for **Saved locally**,
   then choose **Close writing** to return to the manuscript.
   [Writing and recovery](WORKSPACE.md#write-a-manuscript)

Starting with an empty manuscript? Write a paragraph first. Later, follow a
[research link](#research-workflow) beside the text or [choose a reading copy](#record-or-share-a-reading).
For a library of sources without a manuscript, start with a [research project](research/USAGE.md#try-it).

## Start with a manuscript

In a Markdown manuscript, use `## Chapter title` headings and blank lines
between paragraphs. For an initial measurement from the terminal:

```sh
lixity analyze manuscript.md --language en
```

English is the default. For automatic language detection, choose
`--language auto`. Start a short-text review with counts, sentence lengths or quoted passages.
A style comparison needs enough measurable chapters and features to build a
reference from your own text. An unavailable comparison gives you no basis
to judge the prose. For a first style comparison, use a multi-chapter example
such as [Effi Briest](examples/effi-briest.html) or
[Pride and Prejudice](examples/pride-and-prejudice.html).
[Language support](LOCALIZATION.md) · [Command reference](USAGE.md#which-command-for-which-question)

## Use the interactive workspace

Open the installed desktop app from your applications menu. If you installed
through the CLI, start the browser workspace with this command.

```sh
lixity service start --open
```

For the browser app, open the address reported by the service. The default is
`http://127.0.0.1:8765/`. Use **Project actions** to open or create a project.
This menu starts expanded in an empty workspace. It may be collapsed when a
manuscript is already open. [Start, reconnect or change ports](INSTALLATION.md#running-the-server)

### Open or import?

**Open Project** connects to the existing folder and its research archive.
Use **File → New Window** in the desktop app or open the browser service's
root address in a new tab to keep a second project open. Browser tabs with
the same `/w/…/` address share a view. Reopen a browser project from the
service root after restarting. [Service management](USAGE.md#lixity-service)

**Import a manuscript** opens a preview of one Markdown (`.md`, `.markdown`),
plain-text (`.txt`), or Word (`.docx`) file. The preview estimates words and
chapters. Check the destination and choose the analysis language before
confirming. Confirmation creates a new local project with a manuscript copy and
its own settings.

If configuration or Research setup fails while creating/importing a project,
the app reports incomplete setup and keeps the previous project selected. Created
files remain at the destination named in the message. Correct or save
`lixity.toml`, repair the Research setup if needed, then use **Open Project** to
continue and initialize Research if it is still absent.

### Read and explore

The labels below follow the current source and the demo. The published package
can show older labels. [Check your installed version](INSTALLATION.md#cli-current-release)

1. Read a paragraph in **Manuscript**. Turn on **Analysis** and choose
   **Sentence length** under **Inspect passages**. **Analysis help (?)** explains
   the measurement.
2. Choose **Text matches** to open a counted sentence. Use the arrows in the
   card to continue through the matches in your current reading scope. To
   mark them throughout the visible prose, open **Reading marks** and choose
   **Underline counted passages**. To inspect the paragraph you are already
   reading, use **… → Paragraph details → Explain this passage**.
3. Read **Why this is marked** and **What to check while reading**. For sentence
   length, “A board moved.” counts as three words. In **Sticky sentences**, the
   card highlights the contributing function words and shows the rule and the
   count. Ask whether the sentence's connections are clear when you read it
   within its paragraph. Use **How it’s measured** for the full method.

**Mark differing paragraphs** compares a paragraph's measurement with its
chapter. The comparison needs enough eligible paragraphs and enough variation.
When the comparison scale is unavailable, **Matches in this chapter** opens
the counted passages that can still be located. For a word pattern, a measured
zero means the rule counted no matches.
[Counted text and paragraph comparison](WORKSPACE.md#counted-text-and-paragraph-comparison)

Once you have explained a marked passage in your own words, open **Analysis
overview** to compare chapters or explore patterns.
**Open passage** suggests the first tense-pattern flag in manuscript order, or
the opening paragraph when no flag meets the threshold. The suggestion explains
its selection. **Back to passage** restores your reading position and prior
analysis display. [Interpret the measurements](guides/interpretation.html)

### Choose a view

On a wide screen, choose a view in the project sidebar. On mobile, the same
views sit above the workspace. Start in **Manuscript** to read your text, open a
dossier alongside it for context, or use **Research** to work with sources and
saved records. Analysis points to differences you can inspect; it does not
decide whether a passage needs revision.

The book button labelled **Research** opens the saved associations for that
paragraph. Its dotted references stay visible with **Analysis** off.
[Read the mark key](guides/interpretation.html#analysis-marks)

The [reader reference](WORKSPACE.md#reading-paragraphs) explains display preferences,
keyboard controls, companion sizing and coverage. Changing a view writes nothing.

| What you want to do | Where to start |
| --- | --- |
| Compare chapter positions | **Analysis overview → Compare chapters → Style → Feature-rank projection**. Select a chapter or use a flat axis view to inspect overlaps. |
| Follow a source into an argument | **Research**: open a dossier, inspect its evidence and follow a saved manuscript quotation. |
| Change the manuscript or analysis setup | **Project**: check the active project and whether a setting is saved or session-only. |

[Dossier media and maps](research/USAGE.md#keep-places-and-journeys-in-a-dossier)
have their own controls. Map tiles use the network; local vectors and sketches
work without the tile background.

## Work through review notes

Open **Analysis overview → Review passages → Flagged passages** to inspect
heuristic tense patterns. The highest flag level is called **strong difference**.
Filter by chapter or stage, inspect **Why here?**, and choose **Read passage**
or **Read next visible passage**. Marker counts, mixed-tense classification and
switch-from-prior-paragraph explain this list; sentence-length baselines do not.

The native app can save **Deliberately kept**, **Changed by me** or **Review later**
as explicit decisions in the selected project. Choosing an option alone saves
nothing; **Save decision** is required. “Changed by me” is the author's
assessment, not verified editing. Deferred entries remain open. The state is
separate from manuscript markers and research decisions; after text or analysis
changes, an earlier matching decision is marked stale rather than silently
counted as complete. Use the status filter to revisit unreviewed, stale or
deferred entries. A failed state read is unavailable, never “everything unreviewed.”
Reading exports permit inspection/filtering but do not include this private state.

Read a passage before adding a marker. **Save marker** explicitly writes a
Markdown comment; cancelling writes nothing. Dashboards include marker notes,
so review them before sharing. [Marker usage](USAGE.md#work-markers-editor-visible)
explains retention and exports. Analysis does not rewrite prose.

## Research workflow

The [research guide](research/USAGE.md) owns capture, exact citations, authored
records, manuscript associations and recovery. Retain only permitted source bytes.
Claims and author decisions remain interpretations; saving or finding a passage
does not verify it. Review changed anchors and linked revisions explicitly.

A paragraph's saved associations show each record by title. Open the title for
the current entry; where a saved link points to an older revision, use the
separate **Linked version N** action to inspect that exact earlier record. The
viewer leads to linked dossiers and cited source passages. Close it, then use
**Back to passage** to return to the requesting text. See the
[association workflow](WORKSPACE.md#link-a-manuscript-quote-to-a-claim) for the
pinned/current distinction.
To create an association locally, select text in one paragraph, choose **Link
selection to claim**, review the claim and quote, and explicitly permit quote
retention before **Save association**. The association stores the selected
quotation and its manuscript location with the selected claim version. The
public demo lets you explore saved records without writing them.

### Review a manuscript dossier

In the current development checkout, open **Research → Dossiers → From
manuscript → Show suggestions**. Choose a character, scene or place proposal and
read the preview before saving. For a generated character dossier, **Character
in the manuscript** shows the chapter distribution and matching passages in the
currently selected manuscript. A chapter can feature a character without
naming them.

Use **Preview addition** to review a supplement while keeping your earlier
notes. **Save dossier version** adds a new archived revision. To take that
revision to a reading session, reopen it and choose **Download PDF**. The PDF
keeps the saved text and its pinned source quotations. [Dossier proposals and
character reading](research/USAGE.md#manuscript-driven-dossier-drafts) ·
[Dossier PDF contents](research/USAGE.md#download-a-dossier-as-pdf)

<a id="use-zotero-for-sources-and-media-since-v1190"></a>
## Use Zotero for sources and media

### First Zotero capture

Enable Zotero's local API and download the needed attachments. Choose
**Research → Evidence captures → Capture from Zotero**,
then preview a library, collection and attachment before permitting retention.
The Zotero bridge captures PDF/text and PNG/JPEG; it does not capture audio or
video. Lixity separately supports [local PDF/video dossier attachments](research/USAGE.md#retain-a-pdf-or-video-in-a-dossier).
Scanned text needs an OCR backend. The [Zotero reference](research/USAGE.md#zotero-desktop-bridge-since-v1190)
owns setup, refresh, migration and paired backup. Capture enables no background sync.

## Record or share a reading

For a short recording, the teleprompter, an author's voice or generated narration,
follow the [audio manual](AUDIO.md). Recording permission, voice-reference
eligibility and speech-worker readiness are different checks. Start with a short
preview before generating a chapter; choosing a model does not start its worker.

Choose **Project actions → Reading website** to share a review workspace, curated
novel or companion. The [workspace export instructions](WORKSPACE.md#export-a-reading-website)
explain chapter limits, included research, optional analysis and saved chapter
audio. Use [manuscript PDF layouts](USAGE.md#lixity-pdf) for a printable reading
copy, or [download a dossier PDF](WORKSPACE.md#download-a-dossier-pdf) for a
saved research record. Review the chosen contents before sharing. Use a
[project backup](PROJECT_BACKUP.md) to retain the selected project files and
archive for later restoration.

## Check your first session and return later

Check that the active project and analysis language match your manuscript.
The project stays in its folder between sessions. Open Lixity from your system's
application launcher, or run the same executable AppImage on Linux. Choose the
project from **Recent projects** in the welcome window or **File → Recent
Projects**. If you moved it, choose **Open Project** and select its new location.
To close, reopen or update the browser app, use
[service management](INSTALLATION.md#running-the-server).

Choose a [project backup](PROJECT_BACKUP.md) to copy saved manuscripts and
retained research together. For a research-only archive or a Zotero library,
start with [research backup and recovery](research/USAGE.md#storage-lifecycle-and-recovery).
Include linked attachments or other files separately when your backup scope requires them.
