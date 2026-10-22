# Start using Lixity

Explore [*The Crate at Warehouse 4*](https://mfahsold.github.io/lixity/demo/report.html),
the shared demo project for manuscript analysis, research and PDF layouts.
The [illustrated first look](guides/first-look.html) follows that same project;
then use your own manuscript below. The demo is generated through the same
reading-website export as your own shareable copies. [Installation](INSTALLATION.md) covers setup, upgrades and
service management;
[interpretation](guides/interpretation.html) explains the measurements.

<a id="the-journey-at-a-glance"></a>
<a id="see-a-finished-example-first"></a>
## Choose your starting point

| Your starting point | Action |
| --- | --- |
| An existing manuscript/project folder | Start the app and choose **Open Project**. |
| A file to copy into a new project | Choose **Analyze a manuscript**, review the preview and confirm the destination. |
| A new manuscript | Choose **New Project → Start New Manuscript**. |
| Sources without a manuscript | Open or initialize a [research project](research/USAGE.md#try-it). |

## Start with a manuscript

Use UTF-8 Markdown with `## Chapter title` headings and blank lines between
paragraphs. For terminal analysis and saved exports:

```sh
lixity analyze manuscript.md --language en
lixity build manuscript.md --language en
```

Open `exports/manuscript_dashboard.html`. Choose the manuscript language explicitly;
English is the default, and `auto` requests detection. Short texts can leave
measurements unavailable. [Language support](LOCALIZATION.md) describes profile limits.

## Use the interactive workspace

```sh
lixity service start --open
```

The default address is `http://127.0.0.1:8765/`. The app's welcome guidance and
field explanations describe the next action. **Project actions** groups New/Open,
**Show guidance**, PDF export and **Reading website**. It starts expanded in an empty workspace and
collapsed when a manuscript is loaded; the three workspace destinations stay visible.

### Open or import?

**Open Project** reconnects the folder and research archive visible to the server.
Browsing or cancelling does not switch projects. **Analyze a manuscript** copies
a file into a separate project after preview; it does not reconnect the original
folder's archive. A research project may open without a manuscript. All tabs on
one server share its active project, so check the displayed path before saving.

If configuration or Research setup fails while creating/importing a project,
the app reports incomplete setup and keeps the previous project selected. Created
files remain at the destination named in the message. Correct or save
`lixity.toml`, repair the Research setup if needed, then use **Open Project** to
continue and initialize Research if it is still absent.

### Read and explore

Start in **Manuscript** and read a passage. Turn **Analysis**
On to show diagnostics in place; this does not open a tool or narrow the prose.
Choose a paragraph's **… → Explore passage** for measurement explanations or
research beside that passage. The **Passage values** inspector
works with Analysis On or Off. **Analysis overview**
opens chapter comparisons; **Back to passage** restores your place and prior
Analysis On/Off choice.
The opening candidate is not a quality ranking; read the text before
deciding whether a difference matters. Settings explain saved versus session-only
choices. A standalone analysis report is read-only. To share manuscript,
analysis and optional research together, choose **Project actions → Reading
website**. The ZIP copy opens in a browser without a running Lixity server;
project writes and new PDF generation require the local app. See
[reading websites](USAGE.md#export-a-reading-website) and [PDF layouts](USAGE.md#lixity-pdf).

### Choose a view

The project sidebar stays available while you
read on a wide screen. On mobile, use the same views above the workspace.
**Manuscript** is the starting point for your text; open a dossier
alongside it when you need context, and use **Research** to work on the source
archive. Analysis guides your attention; the manuscript remains the reference.

The [reader reference](USAGE.md#reading-paragraphs) explains display preferences,
keyboard controls, companion sizing and coverage. Changing a view writes nothing.

| What you want to do | Where to start |
| --- | --- |
| Read a difference in context | **Manuscript**: choose **… → Explore passage** for one paragraph; use **Analysis** independently for diagnostics. |
| Compare chapter positions | **Analysis overview → Style dimensions**: select a chapter or use a flat axis view to inspect overlaps. |
| Follow a source into an argument | **Research**: open a dossier, inspect its evidence and follow a saved manuscript quotation. |
| Change the manuscript or analysis setup | **Project**: check the active project and whether a setting is saved or session-only. |

Maps open with OpenStreetMap. Select a numbered
place or route to read its details; switch off the background for local vectors
or choose the sketch. The map background uses the network. Mermaid diagrams
render locally: scroll a wide diagram or enlarge it to inspect the whole view.
Tile requests send the viewed area and client IP to the provider and stop when
the map context is hidden.

## Work through review notes

Read a passage before adding a marker. **Save marker** explicitly writes a
Markdown comment; cancelling writes nothing. Dashboards include marker notes,
so review them before sharing. [Marker usage](USAGE.md#work-markers-editor-visible)
explains retention and exports. Analysis does not rewrite prose.

## Research workflow

The [research guide](research/USAGE.md) owns capture, exact citations, authored
records, manuscript associations and recovery. Retain only permitted source bytes.
Claims and author decisions remain interpretations; saving or finding a passage
does not verify it. Review changed anchors and linked revisions explicitly.

A paragraph's saved associations lead through **Open claim**
to the linked claim version, its linked dossier versions and cited source passages.
Close the record viewer, then use **Back to passage** to return to the requesting
manuscript text. The work thread keeps its originating lines and the viewed
record's title/version visible; pinned and current versions remain distinct.
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
PDF/text and PNG/JPEG captures are supported; audio/video remain in Zotero. Scans
need an OCR backend. The [Zotero reference](research/USAGE.md#zotero-desktop-bridge-since-v1190)
owns setup, refresh, migration and paired backup. Capture enables no background sync.

## Check your first session and return later

Check the project, language and a sample quotation against its source. Stop with
`lixity service stop`; return with `lixity service start --open` and open the project.
For an explicit startup project, use `lixity service start --open ./my-novel` while
stopped. Restart uses recorded launch settings, not a later browser selection;
[restart after upgrades](INSTALLATION.md#running-the-server) to load new code.

Back up manuscripts separately: research/Zotero backups exclude them and external
linked attachments. Use [implemented research usage](research/USAGE.md), not
[historical proposals](research/README.md), to determine available operations.
