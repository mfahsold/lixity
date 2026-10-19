# Start using Lixity

Try the [synthetic report](https://mfahsold.github.io/lixity/demo/report.html)
or [illustrated first look](guides/first-look.html), then use your own manuscript
below. [Installation](INSTALLATION.md) owns setup, upgrades and service management;
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
field explanations describe the next action; **Show guidance** reopens it.

### Open or import?

**Open Project** reconnects the folder and research archive visible to the server.
Browsing or cancelling does not switch projects. **Analyze a manuscript** copies
a file into a separate project after preview; it does not reconnect the original
folder's archive. A research project may open without a manuscript. All tabs on
one server share its active project, so check the displayed path before saving.

### Read and explore

Start with **Open passage** or **Explore chapters**, then expand a paragraph's
**Values**. The opening candidate is not a quality ranking; read the text before
deciding whether a difference matters. Settings explain saved versus session-only
choices. Standalone HTML is read-only; project writes and manuscript PDF downloads
require the native server. See [PDF layouts](USAGE.md#lixity-pdf).

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

<a id="use-zotero-for-sources-and-media-since-v1190"></a>
## Use Zotero for sources and media

### First Zotero capture

Enable Zotero's local API and download the needed attachments. **Current main
(unreleased):** choose **Research → Evidence captures → Capture from Zotero**,
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
