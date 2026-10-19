# Start using Lixity

Lixity measures patterns in a manuscript for your own review. Start with the
[read-only synthetic report](https://mfahsold.github.io/lixity/demo/report.html)
or the [illustrated first look](guides/first-look.html), then follow the path
below for your own text. Installation and upgrades belong to the
[installation guide](INSTALLATION.md).

<a id="the-journey-at-a-glance"></a>
<a id="see-a-finished-example-first"></a>
## Choose your starting point

| Your starting point | Action |
| --- | --- |
| An existing manuscript/project folder | Start the local app and choose **Open Project**. |
| A file to copy into a new project | Choose **Analyze a manuscript**, review the import preview and confirm the destination. |
| A new manuscript | Choose **New Project → Start New Manuscript**. |
| Sources without a manuscript | Open or initialize a [research project](research/USAGE.md#try-it). |

The [Fontane](https://mfahsold.github.io/lixity/examples/effi-briest.html) and
[Austen](https://mfahsold.github.io/lixity/examples/pride-and-prejudice.html)
examples show opening chapters in HTML and complete novels in linked PDF reports.
Public examples are read-only and need no manuscript upload.

## Start with a manuscript

Use UTF-8 Markdown with `## Chapter title` headings and blank lines between
paragraphs. For a terminal report and saved analysis exports:

```sh
lixity analyze manuscript.md --language en
lixity build manuscript.md --language en
```

Open `exports/manuscript_dashboard.html`. Use each command's `--help` for
options. Select the manuscript's language explicitly; English is the default,
and `auto` requests heuristic detection. [Language support](LOCALIZATION.md)
explains unequal coverage across profiles. Short texts can leave measurements
unavailable; a highlight is a reading prompt, not a quality verdict.

## Use the interactive workspace

```sh
lixity service start --open
```

The local workspace opens at `http://127.0.0.1:8765/`. Choose among
**Manuscript & Analysis**, **Research & Dossiers** and **Project & Settings**.
Welcome guidance and field explanations describe the next action in the app.
Use **Show guidance** to reopen hidden welcome guidance.

### Open or import?

**Open Project** reconnects an existing folder and its archive. The file chooser
browses the computer running Lixity; browsing or cancelling does not switch
projects. **Analyze a manuscript** imports a selected or dropped file into a
separate project after you review its preview, language and destination. It does
not reconnect the original folder's research archive.

A research-only project can open without a manuscript. All tabs on one server
share its active project, so check the displayed path before saving.

### Read and explore

Start with **Open passage** or **Explore chapters**. The first opens a tense-flag
candidate in source order, or the opening paragraph when none qualifies; it is
not a quality ranking. Chapter comparisons describe whole chapters. Open a
paragraph and expand **Values** for its separate measurements and source lines.
The [interpretation guide](guides/interpretation.html) explains their limits.

Settings explain which changes last for the server session and which are saved
in the project. **Apply** rebuilds the analysis. Saved HTML is an offline report;
project writes and manuscript PDF downloads require the native local server.
For output layouts and optional publication details, see the
[PDF reference](USAGE.md#lixity-pdf). The optional
[NDA generator](USAGE.md#nda-agreements) is a separate authored document action.

## Work through review notes

Read a passage before adding a marker. **Save marker** explicitly writes a
Markdown comment above that paragraph; cancelling writes nothing. The analysis
does not rewrite prose or resolve your notes. Exported dashboards include notes,
so review them before sharing. See [work markers](USAGE.md#work-markers-editor-visible)
for marker syntax and export behavior.

## Research workflow

The experimental research workspace keeps retained sources and authored records
separate from analysis. Import only sources you may retain; that permission does
not grant redistribution rights or verify a claim. The
[research workflow guide](research/USAGE.md) covers capture, exact citations,
dossiers, claims, decisions, manuscript associations and recovery.

Search and preview before saving an evidence link or manuscript association.
Only source passages are citations; authored claims and causal relations remain
interpretations. A changed anchor or reviewed revision requires an explicit
review, never silent acceptance. The app shows retention and compatibility
notices before the corresponding save.

<a id="use-zotero-for-sources-and-media-since-v1190"></a>
## Use Zotero for sources and media

### First Zotero capture

Enable Zotero's local API, download the needed attachments, then choose the
library, collection and attachment in **Research → Sources → Zotero**. Preview
and permit retention before saving. Lixity captures selected PDF/text attachments;
images, audio and video remain in Zotero. Scans need a configured OCR backend.
The [Zotero reference](research/USAGE.md#zotero-desktop-bridge-since-v1190)
owns prerequisites, refresh, migration and paired backups. Capture does not
turn on automatic synchronization.

## Check your first session and return later

Check the displayed project, language and a sample quotation against the source.
Stop with `lixity service stop`; return with `lixity service start --open`, then
open your project. To choose the startup project explicitly while the service
is stopped, use `lixity service start --open ./my-novel`.

Restart uses recorded launch settings, not a later browser project selection.
After upgrades or OCR environment changes, restart the intended instance; a
browser reload does not load updated code. See
[service lifecycle](INSTALLATION.md#running-the-server).

Back up manuscripts separately from the research archive. Research/Zotero
backups exclude manuscripts and external linked attachments. Use the
[implemented research reference](research/USAGE.md), not the
[proposal](research/README.md), to determine available operations.
