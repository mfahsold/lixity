# Start using Lixity

[Documentation map](README.md) · [Install Lixity](INSTALLATION.md) · [Workspace manual](WORKSPACE.md)

Start by reading one passage. Choose a measurement, check what Lixity counted,
and decide whether the difference matters to the scene.
Practice in the read-only [Warehouse 4 demo](demo/report.html) with the
[illustrated walkthrough](guides/first-look.html), or open your own project below.

<a id="the-journey-at-a-glance"></a>
<a id="see-a-finished-example-first"></a>
## Choose your starting point

| Your starting point | Action |
| --- | --- |
| A folder where you already work | Choose **Project actions → Open Project** to reconnect its manuscript and research. |
| A file to copy into a new project | Choose **Analyze a manuscript** on the welcome screen, or **Project actions → New Project → Import manuscript**. |
| A blank manuscript | Choose **Project actions → New Project → Start new manuscript**. |
| A linguistic question about an existing text | Follow the [text-analysis workflow](USAGE.md#linguistic-text-analysis) to record scope, settings and reproducible outputs. |
| Sources without a manuscript | Open or initialize a [research project](research/USAGE.md#try-it). |

## Session checklist

1. Open or create the project and confirm its path and analysis language.
2. Read a paragraph in **Manuscript** and inspect one [measurement](#read-and-explore).
3. To revise the passage locally, choose **Write**. Check for **Saved locally**,
   then choose **Close writing** to return to the reader.
   [Writing and recovery](WORKSPACE.md#write-a-manuscript-unreleased)

## Start with a manuscript

In a Markdown manuscript, use `## Chapter title` headings and blank lines
between paragraphs. For an initial measurement from the terminal:

```sh
lixity analyze manuscript.md --language en
```

English is the default. For automatic language detection, choose
`--language auto`. Some measurements require a longer text.
[Language support](LOCALIZATION.md) · [Command reference](USAGE.md#which-command-for-which-question)

## Use the interactive workspace

```sh
lixity service start --open
```

Open the address reported by the service. The default is
`http://127.0.0.1:8765/`. Use **Project actions** to open or create a project.
This menu starts expanded in an empty workspace. It may be collapsed when a
manuscript is already open. [Start, reconnect or change ports](INSTALLATION.md#running-the-server)

### Open or import?

**Open Project** connects to the existing folder and its research archive.
Confirm the path to open it in the current tab. To keep two projects open,
open the service's root address in a new tab and choose **Open Project** there.
Tabs with the same `/w/…/` address share a view. Reopen projects from the service
root after restarting. [Service management](USAGE.md#lixity-service)

**Analyze a manuscript** opens a preview of one Markdown (`.md`, `.markdown`),
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

1. Read a paragraph in **Manuscript**. Turn on **Analysis**, open **Measure**,
   and choose **Sentence length**. **Analysis help (?)** explains the selected
   measure and can open the count for the passage in view.
2. Use **Counted text** to display the exact words or sentences where the
   measurement can show a source span. Open a mark directly or use the
   paragraph menu **… → Explore passage → Explain measurement**. The menu also
   works with **Analysis** off and turns analysis on when you choose **Explain
   measurement**.
3. Read **Why this is marked** and **What to check while reading**. For sentence
   length, “A board moved.” counts as three words. In **Sticky sentences**, the
   card highlights the contributing function words and shows the rule and the
   count. Ask whether the sentence's connections are clear when you read it
   within its paragraph. Use **How it’s measured** for the full method.

**Paragraph comparison** is a separate display. It compares a paragraph
measurement with that chapter when a comparison is available. A measured
zero means the rule found no matches. An unavailable comparison can reflect a
short sample. When a result has no verified source span, **What is counted**
shows the evidence card's coverage.
[Counted text and paragraph comparison](WORKSPACE.md#counted-text-and-paragraph-comparison)

Open **Analysis overview** to compare chapters or explore patterns.
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
To create an
association locally, select text in one paragraph, choose **Link selection to
claim**, review the claim and quote, and explicitly permit quote retention before
**Save association**. This saves the quote, not a full manuscript capture or source
evidence. The public demo lets you explore saved records without writing them.

<a id="use-zotero-for-sources-and-media-since-v1190"></a>
## Use Zotero for sources and media

### First Zotero capture

Enable Zotero's local API and download the needed attachments. **Since v0.7.1:**
choose **Research → Evidence captures → Capture from Zotero**,
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
audio. A PDF is a separate printable output; see [PDF layouts](USAGE.md#lixity-pdf).
Inspect the copy before sharing it. An export is not a complete project backup.

## Check your first session and return later

Check that the active project and analysis language match your manuscript.
Use [service management](INSTALLATION.md#running-the-server) to close, reopen or
update the local app. The project stays in its folder between sessions.

Back up manuscripts separately: research/Zotero backups exclude them and external
linked attachments. Use [implemented research usage](research/USAGE.md), not
[historical proposals](research/README.md), to determine available operations.
