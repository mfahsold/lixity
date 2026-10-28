# Lixity – Usage & Reference

Use this guide to choose an analysis, read its results and configure a project.
For a first session, follow [Onboarding](ONBOARDING.md). The separate
[research guide](research/USAGE.md) owns retained sources, citations, dossiers,
Zotero, backups and OCR; [automation contracts](AGENTS.md) own JSON envelopes
and HTTP requests.

<!-- Legacy fragment IDs below preserve incoming links; current headings define version-neutral links. -->

- [Choose a command](#which-command-for-which-question)
- [Review a dashboard](#dashboard-workflow)
- [Command workflows](#command-reference)
- [Interpret results](#understanding-the-metrics)
- [Prepare a manuscript](#manuscript-format--how-to-operate-lixity)
- [Use the library](#library)
- [Configure a project](#configuration-corpusconfig)
- [Troubleshoot](#troubleshooting)

## Installation

The [installation guide](INSTALLATION.md) covers supported systems, isolated
CLI/Python environments, updates, removal and shell completion. Commands here
assume `lixity` is on your `PATH`. For a source checkout, use
[CONTRIBUTING.md](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md).

## Report language

Reports and CLI messages use English by default; `LIXITY_LANG=de` selects
German presentation. Other presentation languages fall back to English. This
is separate from the manuscript's analysis language: use `--language de`,
for example, or explicit `--language auto` for detection. Weak or ambiguous
evidence selects the generic profile. See [Localization](LOCALIZATION.md) for
coverage and project-supplied report text.

## Quick start

```bash
lixity analyze manuscript.md --language en
lixity dashboard manuscript.md --language en -o dashboard.html
```

`analyze` prints a terminal report; `dashboard` writes a browsable HTML file.
[Choose another command](#which-command-for-which-question) for focused analysis
or a different output.

## Which command for which question?

| Question | Command | Key numbers |
| :--- | :--- | :--- |
| How does the manuscript read overall? | `lixity analyze` | ASL, CV, TTR, HD-D, MTLD, Flesch, LIX, dialogue, registers |
| Where do heuristic tense markers change or mix? | `lixity profile` | per paragraph: dominant tense, mix, switch, severity 0–3 |
| How does each chapter differ from this manuscript's reference? | `lixity style` | median/MAD bands, z\*, FDR set, style dimensions |
| How is the dialogue structured? | `lixity dialogue` | turns, turn lengths, turns per 1,000 words, dialogue paragraphs |
| Who appears where — and when not? | `lixity characters` | mentions, chapters present, span, longest gap |
| Where do scene lengths and endings differ? | `lixity pacing` | scenes, scene length, ASL curve, ending-cue count 0–3 |
| What repeats itself? | `lixity motifs` | motif presence, top content words, repeated n-grams |
| How do word-pattern and quotation/short-sentence cues vary? | `lixity showing` | standardized signal groups and their difference; not a narrative classification |
| I want to browse the available analysis panels | `lixity dashboard` | self-contained HTML; research and writes require the local app |
| I want a foreground server for development or integration | `lixity serve` | loopback HTTP server, live settings, manuscript upload, research panel |
| I want to start or manage the installed app | `lixity service` | managed start, stop, restart and status without a source checkout |
| Which installation and service am I using? | `lixity doctor` | package versions, module/interpreter location, contracts and owned service status |
| Which files are sources or outputs, and are their locations usable? | `lixity project --project PATH` | read-only roles, existing outputs and bounded structure findings |
| I want to manage and cite research sources | `lixity research` | immutable archives, citations, dossiers, manuscript grounding |
| I want a printable document, report or reading copy | `lixity pdf` | neutral/editorial A4, A4 report, A5 book, 30×60 sheet |
| I want an experimental local listening copy | `lixity read-aloud` | project voice profiles, Qwen3-TTS 1.7B locally or on a configured Jetson; prototype setup and limits below |
| I want to share a browsable reading copy | `lixity export-site` | static website, optional research and original sources |
| I want a reproducible artifact set | `lixity build` | `exports/`, archive rotation |
| What can the engine do? | `lixity about --json` | languages, features, thresholds, commands |
| What does the installed tool expose? | `lixity schema` | capability metadata, equivalent to `about --json`; not an analysis-result JSON Schema |

## Dashboard workflow

```bash
lixity dashboard manuscript.md --language en -o dashboard.html
```

Open the file in a browser for offline analysis navigation. It embeds manuscript
text and measurements, so treat it as manuscript material when sharing. Project
settings, manuscript writes and research actions require a compatible local
server; start the installed workspace with `lixity service start --open`.

The live workspace separates research, analysis and project settings. Use
[Onboarding](ONBOARDING.md#open-or-import) for create/import/open: a file preview
writes nothing until confirmation; opening reconnects an existing project.
For research, use Zotero for ordinary source work and Lixity for retained evidence,
authored records and manuscript associations; the [research guide](research/USAGE.md)
defines that boundary and the optional local-import workflow.

### Inspect project structure

Open **Project** to inspect the selected
folder. **Sources** identifies the selected/configured manuscript and native
research folder; **Outputs** lists existing files directly under `exports/`
and the conventional `exports/archive/` location. Open the manuscript or matching
research workspace through its existing view, or open an eligible output.
**Check again** repeats the metadata inspection without rebuilding analysis.
There is no background scan of all projects.

The equivalent CLI works without a running service:

```bash
lixity project --project /path/to/book
lixity project /path/to/book --json
```

Without a selector, the CLI inspects the current directory only. It reads root
`pyproject.toml`/`lixity.toml`, never user or ancestor settings. Manuscript
selection reuses the configured relative path and existing workspace discovery;
the live overview also identifies disagreement with the currently selected file.
Missing optional research/output folders are normal. Ambiguous or unavailable
sources, invalid settings, unsafe links and source/configuration aliases produce
explicit findings. Exit 1 means an error finding or an unavailable inspection;
warnings and an unassigned manuscript alone do not fail the command.

**Available** means the filesystem metadata was accessible. It does not certify
research integrity, output contents or freshness. Existing outputs always show
**Source and generation history unknown**: filenames and modification times do
not prove which manuscript/configuration generated them. Run `research audit`
for archive integrity and `build` to produce analysis outputs deliberately.
Submission documents remain **Unassigned**; this view does not guess which
dossier is an exposé or invent a second folder convention.

Inspection reads no manuscript/output contents or research history. Configuration
reads stop at 1 MiB per file; discovery and output scans stop at 2,000 directory
entries and return at most 200 output files. Reaching a limit is reported as an
incomplete inspection, not a clean bill of health. Nested output folders are not
inventoried. The native view requires a current selected-project context; a changed
or oversized configuration can require reopening the view or CLI inspection.
Downloads recheck their file and project context when opened.

This feature creates, edits, moves and deletes no files. Git, backups, private
recipient records and unknown project files remain outside its remit. Static
reports and exported reading websites contain no local project inventory or
live structure controls.

<a id="download-a-manuscript-pdf-since-v240"></a>

### Download a manuscript PDF

Open **Project actions → PDF export**, choose a layout, then
**Download PDF**. Since v0.7.0, **A4 editorial copy** is the initial choice;
**A5 reading copy**, **A4 manuscript sheets** and **A4 analysis report** are also available.
Since v0.7.4, **A4 document** adds a neutral copy for exposés and everyday text.
Changing the layout alone does not generate a file. The download uses the same
composer and project metadata as [`lixity pdf`](#lixity-pdf), returning bytes
directly without creating server export files. Reload after switching projects
or externally changing root configuration; stale export context is rejected.
JavaScript and a compatible native server are required.

### Export a reading website

Since v0.7.4, **Project actions → Reading website** downloads a fixed project
copy as ZIP. Unzip it and open `index.html`, or serve the folder on static
hosting. The recipient needs no Lixity installation or running service.
Later project changes require a new export.

| Format | Included content | Intended use |
| --- | --- | --- |
| Review workspace | Manuscript and analysis; optionally internal research and history | Author/editor review |
| Manuscript + selected background | Reading text plus explicitly curated background notes | Read the story with chapter-dependent context |
| Selected background only | Curated notes without the novel or analysis | Background for someone reading elsewhere |

```bash
lixity export-site --project . -o manuscript-copy
lixity export-site --project . -o editorial-copy --include-research
lixity export-site --project . -o novel-copy --mode reader --publication-profile readers
lixity export-site --project . -o companion-copy --mode companion --publication-profile readers
lixity export-site --project . -o excerpt-copy --mode reader --publication-profile readers --max-chapter 4
```

The destination must be a **new directory**. Existing paths are never
overwritten. With no mode flag, the default is the review workspace. It includes
manuscript text, work-marker notes and analysis, including exact text marks.
The dialog starts with research and source-file inclusion unchecked each time.
Leave research unchecked for a manuscript/analysis copy, or choose a reader format
and publication profile for selected companion notes.
`--include-research` adds authored dossiers, claims, decisions, their accessible
revision history, cited excerpts, manuscript associations, timelines and map
geometry. This can include internal notes and superseded wording; review the
copy before sharing it. In review mode, original source files and complete
extracted source text require `--include-source-files` together with
`--include-research`. Local retention permission does not establish permission
to redistribute a source.

#### Curate a reader publication

In **Project → Settings → Reading website profiles**, create a named publication
profile. Choose
an existing dossier, either its full body or a unique section, and the chapter
after which it may appear. Chapter 0 means before the first chapter. A blank
revision uses the current dossier when exporting; an explicit revision keeps
that version. Each export records the actual resolved version.

**Since v0.7.6:** export choices use only profiles saved with
**Apply** in project settings. An empty selector explains that no saved profile
exists and links directly to profile creation. Unsaved edits and malformed
stored settings have distinct messages; they are not treated as selectable
profiles. A failed dossier catalogue can be retried without discarding the
profile draft. Select a saved profile before choosing its chapter cap or
downloading a publication.

The profile is a validated root-local `site_publications` project setting,
separate from PDF imprint settings and accepted Research records. Save this TOML
in the selected project's root `lixity.toml` (or prefix its tables with
`tool.lixity.` in that root's `pyproject.toml`). Profiles are not read from
`.lixity/config.json`.

```toml
[site_publications.readers]
title = "Notes beside the story"
introduction = "Choose the last chapter you have finished."

[[site_publications.readers.entries]]
dossier_id = "urn:uuid:11111111-1111-4111-8111-111111111111"
section = "Harbour"
title = "The harbour setting"
reveal_after_chapter = 2
include_citations = false
include_geography = false
```

Use a real dossier ID from your project. The entries form an explicit allowlist:
reader and companion exports include only selected dossier bodies or sections.
Leave internal dossiers out of that list. Citations and geography are off by
default. If selected, these are the **whole pinned dossier's** citations or map;
there is no inferred section-to-citation/map association. Review that content
before including it. Publication modes do not automatically include claims,
internal decisions, reverse links, revision history, source context notes or
complete extracted source text. `--include-research` is rejected for these
formats; choose the curated profile instead. Selected retained media needs the
separate source-file inclusion choice.

Current-main PDF/video attachments use the same source-file choice and
dossier/section scope as images. They remain unavailable placeholders when the
original files are omitted. See the [shared media workflow](research/USAGE.md#retain-a-pdf-or-video-in-a-dossier)
for file limits, version compatibility and public credit requirements.

Inspect the installed profile JSON Schema without opening a project:

```sh
lixity about --section configuration |
  python3 -c 'import json, sys; print(json.dumps(json.load(sys.stdin)["configuration"]["site_publications_schema"], indent=2))'
```

This JSON describes the TOML setting; it does not create a separate configuration
file. Profiles accept `title`, `introduction` and `entries`. Each entry accepts
`dossier_id`, `revision`, `section`, `reveal_after_chapter`, `title`,
`include_citations` and `include_geography`; unknown fields are rejected.
Theme settings, paths and exclusion lists are not profile fields. Choose the
destination with `-o`; `--mode`, `--max-chapter` and the research/source-file
inclusion flags belong to `export-site`. Profiles do not inherit from user or
ancestor settings.

Readers explicitly set the last chapter they have finished. Scrolling and
chapter navigation do not count as reading. Later notes have no visible titles
or preview snippets. Progress is browser-local; unavailable or invalid storage
starts at chapter 0. Previewing later notes is separate from saved progress.

Progressive reveal is **display guidance**, not encryption: a full reading
website contains its later notes in inspectable files. For a bounded edition,
`--max-chapter N` excludes later notes and their dependencies before the website
is serialized. In novel-and-companion mode it also removes later novel chapters.
A companion-only copy contains no novel prose, diagnostics or work-marker notes,
except quotations the author deliberately selected in the published dossier.
One-off research/source-file choices are not stored as future redistribution
permission or automatically saved export defaults.

#### Sharing limits and automation

Editing, project switching, import, analysis recalculation and research writes
are unavailable in the copy. Ordinary exports make no automatic analytics,
external font or map-tile requests. Dossier map geometry works offline; external
reference links require deliberate activation. `manifest.json` inventories scope,
source identity and files; `--json` prints it for automation. Exporting changes
neither the manuscript nor the research archive. The public website may add its
separately disclosed analytics wrapper; that is not part of ordinary exports.

A reading website is **not access control, encryption or a backup**. Anyone
with its files can read or copy the included content. Confidential hosting needs
its own access controls. Use [archive export and restoration](research/USAGE.md#export-and-restoration)
for restorable backups. Limits fail explicitly rather than silently dropping
material: 64 MiB each for manuscript input, archived record input and prepared
website data; 50,000 prepared research responses; and 200 MiB for the complete bundle.

Review exports with research limit
authored history to 10,000 revisions (dossiers, claims, decisions and their links).
Source and passage records do not consume that count; curated reader/companion exports do
not apply the history count. The manifest's `research.revision_count` still counts
all accepted record versions when research is included, so it may exceed 10,000.
The byte and response limits above still apply. For a history-limit error, export
without internal research or select a curated reader/companion profile.

<a id="start-a-review-since-v230"></a>

### Start a review

In the interactive workspace, the **Analysis** switch has a visible
On/Off state while the manuscript remains continuous. Showing diagnostics keeps
the prose width and navigation choice; it does not open a context tool. An
analyzed paragraph's **Values** opens the **Passage values** inspector independently
of the Analysis On/Off choice. **Analysis overview** opens chapter comparisons and other dense views;
**Back to passage** restores the earlier analysis choice and document context.

**Since v0.7.6:** a tense review card names its actual trigger:
present/past cues in one paragraph, a dominant-tense change from the previous
paragraph, or both. Original counted forms appear as buttons grouped by present
and past; activate one to locate it in the manuscript. Repeated forms keep
separate occurrences. The card starts with three cues per group; expand the
remaining cues, counts or heuristic help when needed. Other paragraph values
start collapsed. Missing or unverifiable mappings are stated explicitly. A
counted cue does not prove a grammatical error, and mixed cues alone do not
establish a switch from the previous paragraph.

**Start your review → Open passage** opens the first paragraph meeting the
selected tense threshold, otherwise the opening paragraph, clearing filters and
focusing the passage. **Explore chapters** opens available chapter comparisons;
**Open sentence rhythm** appears when measurable. Other passage/chapter links
navigate to the corresponding prose. These are review locations, not rankings
or instructions to revise.

**Since v0.7.3:** the overview keeps these review routes,
section navigation and flagged passages visible. Expand **Manuscript
measurements** for the grouped scope, rhythm, language, vocabulary and style
values; use the same summary to collapse them. Its open state survives switching
between the overview and manuscript. Standalone reports start with these values
expanded, including without JavaScript.

The flagged-passages heading shows the list count. **+ To-do** opens the existing
marker draft; saving remains explicit. Long flag and scene lists use bounded
scrolling regions: focus the region and use arrow or page-scrolling keys, or use
wheel/touch. Wide chapter, character and scene comparisons retain the row identity
while scrolling sideways. Section-navigation arrow keys keep offscreen labels
reachable; keyboard passage/chapter drills focus the revealed text. **Back to
passage** retains its earlier passage position, analysis choice and context tool.

<a id="read-a-dossier-beside-the-manuscript-since-v240"></a>

### Read a dossier beside the manuscript

Choose **Dossier alongside** to read a saved dossier while retaining manuscript
search and the current reading presentation. Analysis visibility remains a
separate choice: opening a dossier does not turn it off. Use the context area's
**Passage values** and **Dossier alongside** controls to switch the active tool; only
one tool occupies that area at a time. Opening it collapses desktop project
navigation; its toggle remains reachable, and closing restores the earlier manual
choice. Drag the divider to change the desktop widths, or focus it and use
`Left`/`Right` in five-point steps; `Home` and `End` select the 35% and 75%
manuscript-width limits. The split is a local browser preference. Narrow screens
stack the readers and hide the divider. When opened from a paragraph's tools,
the dossier heading scrolls into view on mobile; its close button or Escape
returns to that paragraph and its control. Close with the same toggle or the
dossier's close button; refresh explicitly for the latest revision. The
[research workflow](research/USAGE.md#reading-and-cli-workflows) owns
selection, evidence and retention semantics.

**Since v0.7.3:** the workspace switcher comes before project
details, so a long title does not push Manuscript, Research and Project out of
reach. **Project actions** keeps New, Open, guidance and available PDF exports
together; version and license information follow those controls.

<a id="link-a-manuscript-quote-to-a-claim-v030"></a>

### Link a manuscript quote to a claim

Use **Link selection to claim** (`Alt+L`) on text in one analyzed paragraph.
The selection toolbar and paragraph context menu reach the same action. Review
the claim and quote, then permit retention before saving. Preview writes nothing;
saved links pin exact claim/paragraph versions and need review after changes.
See [retention, anchoring and compatibility](research/USAGE.md#associate-a-manuscript-quote-with-a-claim).

A recorded association retains the exact claim and dossier versions used for it.
Claim and dossier views can open their manuscript
associations in Review. Only an exactly resolved current passage offers a direct
jump; moved, changed, ambiguous and unavailable anchors retain their review state.

**Since v0.7.4:** choose **Explore passage → Research for this
passage**, its association count or a marked quotation to read the linked
context beside the manuscript. The context shows up to five associations with
their total, grouping quotations of the same claim version. Titles open the
current entry; a separate **Linked version** button opens an earlier pinned
version. **Text associations** contains the exact quotations and assessment of
the linked claim version. **Decisions in current dossier** expands separately,
with further decisions available beyond the first five. These decisions do not
reconstruct the quotation's historical context. **Review** remains a separate
action for changed or unresolved anchors. An empty summary means no saved
associations for this passage, not that no relevant facts exist. Opening or
refreshing the summary reads existing records without saving or repinning them.

When following a connection from the manuscript, **Back to passage** returns to
the preserved origin while the project/source context still matches. The work
thread groups this action with the originating chapter and lines. **Viewed version:**
introduces the title and version of the claim or dossier you opened. Labels distinguish a pinned
version from a current or viewed version; browsing history does not repin a
record. Returning to the manuscript, or changing the project/source context,
clears the thread.
Cited source
quotations remain pinned retained passages; opening an ordinary source reader is
not a new historical-source navigation contract.

**Since v0.7.3:** leaving an open dossier for its saved
associations or a global research collection offers **Back to dossier**. It
restores that saved version, tab, scroll position and requesting control without
reloading the dossier or discarding drafts. An earlier manuscript return remains
available after returning to the dossier. On narrow screens the return stays
above the current content. Closing or replacing the originating dossier, or
changing project context, removes an invalid return rather than guessing.

<a id="reading-paragraphs-since-v230"></a>

### Reading paragraphs

Interactive workspaces start with continuous
manuscript text and **Analysis Off**. Toggle **Analysis** to reveal diagnostic
presentation in place. The switch, visible On/Off text and pressed state identify
the choice while its accessible name stays **Analysis**. Showing the layer alone
does not open a dock or collapse navigation. Its gutter marker sits outside text
flow, preserving the prose width and line wrapping. Opening or closing the
dossier is independent of that state. Use
**Analysis overview** for chapter matrices, sentence rhythm and other comparisons,
then **Back to passage** to restore the document context and prior analysis
display choice. Hiding analysis leaves the overview and restores the prior
passage tool. The inspector and dossier work with Analysis On or Off.

**Since v0.7.3:** the first explicit **Analysis On** selects **Sentence length**
unless you have already saved a metric choice.
Use the directly visible **Measure**
selector while Analysis is on. **Counted text** and **Paragraph comparison** are
independent switches: keep either, both or neither. With counted text enabled,
violet underlines identify counted words, patterns, quoted speech or sentences.
Hover a mark for its explanation; a short stationary tap opens it on touch
screens. Escape closes it. Analysis Off and **None** hide both kinds of indicator;
unchecking either switch hides only its own marks and key. The selected metric and
both switch preferences persist in the browser, including deliberate **None** and
disabled switches. Turning Analysis on again preserves those choices.

**Explore passage** opens chapter/source-line context and measurements in the
existing passage inspector without changing global Analysis. Its **Explain
measurement** action inspects counted text; **Research for this passage** reads
explicitly linked claims, sources and decisions. Switch between passage values,
linked research and the chosen dossier explicitly. On mobile, a paragraph-to-tool
action reveals the stacked tool heading; close or Escape returns to that passage
and its control. Desktop tools occupy adjacent space.

The visible keys distinguish violet **Counted text** underlines from
**Paragraph comparison**. Notable paragraphs have a raw-value marker with a
down/up arrow and a blue/orange edge for below/above the chapter median; the prose
background receives only a subtle edge wash. Click the marker to inspect the measurement. **Read these
marks** keeps the comparison method and counting guidance collapsed until opened.
A marked sentence's word count and its paragraph's average are different
quantities.

**Since v0.7.6:** saved research has a separate visual identity:
neutral dotted marks and a book-icon **Research · … associations** control. They
identify explicitly saved quotation links to claims, dossiers and decisions;
they are not measurement deviations or automatic fact checks. The count is
associations, not distinct sources or evidence strength. The control opens
research context by keyboard or pointer; an exact inline mark also opens it on
click when no text selection is active. Closing the context returns to the
passage. Research references remain visible with Analysis Off and coexist with
solid counted-text underlines and search backgrounds. There is currently no
separate global Research-mark visibility switch. The
[annotation design contract](ARCHITECTURE.md#annotation-semantics-and-visual-identity)
explains the ownership and color roles.

These routes share existing actions rather than creating separate records:

| Task | Passage route | Other access |
| --- | --- | --- |
| Explain counted text | **Explore passage → Explain measurement** | Hover or tap a marked word or sentence |
| Read explicitly linked research | **Explore passage → Research for this passage** | The paragraph's association count |
| Link a quotation to a claim | **Link selection to claim** in the paragraph menu | The selection toolbar or `Alt+L`, with a valid selection inside one paragraph |
| Add a work marker | The paragraph menu's marker actions | The compact selection toolbar offers **Check**; the overview lists saved work markers |
| Keep a chosen dossier beside the text | **Dossier alongside** in the paragraph menu | The reader toolbar and the dossier context control |

**Dossier alongside** displays the dossier you explicitly choose. **Research
for this passage** follows associations saved for the selected paragraph. Merely opening
a dossier beside the manuscript does not link it to that passage.

**Explore passage → Explain measurement** also works by keyboard or right-click,
including with Analysis Off or Focus reading. That explicit action enables
Analysis and chooses Sentence length if no metric is selected, while preserving
both display-switch preferences.

The measurement card puts the quotation and its count first, with paragraph
measurement and chapter comparison in a separate panel. Mapping limits stay
under **About this comparison**. A word count is not an editorial fault; a
perception-word match does not establish narrative distance. When exact
counting/display mapping cannot be verified, the value remains but its evidence
is explicitly unavailable. Browsers without native text highlighting retain
explicit inspection. Text, selection, saved quotations and search marks keep
their identities.

Choose a chapter in the reader toolbar. **Reading settings** groups **A−**/**A+**
for text size (16–28 nominal pixels), narrow/standard/wide text and
compact/standard/relaxed line spacing. Appearance and the desktop split are local
browser preferences; display changes do not edit the source.

**Since v0.7.6:** the analysis overview's section links sit in its existing
header and wrap instead of hiding later sections beyond a horizontal scroll.
They jump within the overview; the underlined link indicates the current
section, not a completed review step. **Back to passage** remains the return to
the manuscript. On short viewports the header scrolls with the content to leave
room for the measurements.

**Since v0.7.6:** **? → Help with your first analysis** is a voluntary
panel in the reader toolbar. It explains the current Analysis Off /
no selected measure / selected measure state and a read–count–compare workflow.
It does not enable diagnostics, reset preferences, create a task or change
measurements. It is hidden in Focus reading and the overview; returning to
the manuscript restores it. The overview's opening-passage action now visibly
explains its existing tense-flag/opening-paragraph selection, not a quality rank.
CLI `profile --help` gives the same source-lines → counted-text workflow;
default outputs and JSON contracts are unchanged.

**Current main review decisions:** the overview's flagged list contains tense
heuristics, not all chapter or paragraph metrics. **Why here?** reports actual
configured present/past marker counts and mixed/switch criteria. **Read passage**
is primary; a diagnostic no longer directly proposes a To-do. Author work markers
remain available from the manuscript's paragraph menu.
The passage list switches from columns to the same compact records when its
available pane becomes too narrow. Reading and decision controls remain visible
beside the sidebar as well as on smaller screens.

The native host advertises `analysis-review` to permit project-local decisions.
Chapter, stage and decision filters limit the visible list; **Read next visible
passage** follows that selection without saving anything. Choose **Deliberately
kept**, **Changed by me** or **Review later**, then save explicitly. Completed
counts include only current kept/changed decisions, not deferred or stale ones.
No automatic manuscript change, task, source capture or research decision occurs.

For the same observation/state model from the CLI:

```sh
lixity analysis-review --project ./novel --json
lixity analysis-review --project ./novel --observation ID --status kept \
  --expected-source-sha256 SOURCE --expected-analysis-sha256 ANALYSIS \
  --expected-review-sha256 REVIEW --json
```

Use exact identities from the current read. A stale tab/writer/settings/source
returns an error; read again before deciding. **Changed by me** is explicitly
self-reported. State lives in `.lixity/analysis-review.json` with schema
`lixity-analysis-review-state/1`, bounded to 10,000 decisions and 4 MiB.
Reads create no files. Writes reuse the project writer lock and atomic file
writer; no research archive is initialized. Back up this local project state
separately from the Research archive if those decisions matter.

The entire source digest and resolved configuration/threshold signature bind
a decision. Even an unrelated text edit makes an earlier matching decision
stale; edited/moved paragraphs can instead appear as new observations, while the
prior decision is retained but unmatched. This is a conservative review boundary,
not semantic change detection or a “since last session” diff. Reading exports
do not serialize decisions or allow saves. No review data is sent to analytics.

**Since v0.7.3:** **Reading settings → Keyboard shortcuts**
lists the passage menu, search and close keys. Hovering or focusing key controls
also gives a short explanation; Escape dismisses a tooltip. **Since v0.7.6:**
mouse hints wait briefly for deliberate hovering, then switch faster between
neighboring tools. They appear beside the hovered control near the pointer;
keyboard and touch hints keep room for adjacent toolbar actions. They show the control name, its explanation and any declared
shortcut. Moving away or starting an action cancels a pending hint. Keyboard
focus and explicit touch explanations do not wait for mouse dwell. Essential actions
remain labeled and work without hovering. In manuscript search, `Enter` selects
the next match, `Shift+Enter` selects the previous match and Escape clears the
query. These keys apply in the search field, not throughout the application.
Passage jumps wait for their scrolling area to settle before a brief destination
cue; reduced-motion preferences keep navigation immediate.

Each analyzed paragraph has an **…** button. It opens the same contextual tools as a
right-click on the prose or `Shift+F10`/the context-menu key while the paragraph
or its button has focus. Arrow keys move through the menu; `Home`/`End` reach its
first/last action. Escape closes it and restores focus. Actions depend on the
available capabilities: **Explore passage**, work markers, **Link selection to claim**
for a valid selection, and the companion dossier. A selection within one paragraph
also offers a compact toolbar. Marker notes and claim associations still require
their existing explicit save and retention steps.
Use Shift+right-click to open the browser's native context menu instead.

**Focus reading** temporarily hides surrounding navigation and
tools, counted-text underlines and paragraph comparison markers; its visible exit
or Escape restores the workspace and prior display choices. Opening a tool exits
focus coherently. Text-size, layout and companion changes retain the visible
source block's position where available. Menus close on scrolling or resizing;
switching workspace closes temporary menus and reading settings.

Optional brief feedback marks changed controls, newly visible content and passage
returns. Visibility, selection and focus changes take effect immediately. The
workspace respects reduced motion, including preference changes while it is open;
running feedback is cancelled and the return gutter remains useful without motion.

The source-backed reader retains supported headings, multi-paragraph quotations,
list content, literal code, scene/page dividers and note definitions in source
order. Preface, empty chapters and the configured analysis-excluded appendix
remain readable. Unprofiled blocks show a coverage note, without paragraph
measurements or claim-save actions. Documents without measurable prose can still
be read. The statistical analysis continues to use its existing coverage.

Analyzed paragraph text, line spans, hashes and quotation offsets remain exact.
One analysis paragraph can own several presentation list items, so those items
remain one text owner rather than duplicated passages. Links, inline code and
footnote markers inside those paragraphs are not normalized into a new rich-text
quote contract. Pipe tables remain literal text; embedded HTML and unsupported
TeX stay inert, and manuscript image URLs are not fetched automatically. This
bounded reader is not a general Markdown editor or full CommonMark/GFM renderer.
The [book PDF](#lixity-pdf) keeps its established presentation and stricter TeX
rules. Profile-only embedding callers retain their analysis-projection fallback.
Plain reports retain their report presentation, and the no-JavaScript fallback
keeps source text readable. Complete paragraph data remains embedded; deferred
interaction does not make the self-contained file smaller.

The manuscript is a document reader: dragging selects text and resizing text
changes its layout. Images use the shared zoom viewer, maps use Leaflet pan/zoom,
and style-space retains its own rotation and zoom controls.

### Searching the manuscript

Type a phrase in the manuscript search control to show matching text blocks and mark
hits. Arrows or `Enter`/`Shift+Enter` move between matches; `Escape` or
**Clear search** restores the manuscript. Search includes readable structural
blocks as well as analyzed paragraphs; the count is matching blocks out of
blocks searched. Search takes priority over **Flagged only**; clearing
it restores that filter.

Matching is a case-insensitive substring test: it does not stem, ignore
diacritics or cross paragraph boundaries. Text resembling markup remains text.
Research list filters only match loaded record metadata; use
**Research → Search** for retained source text.

Since v0.7.3, empty source and dossier collections omit their unused filter.
A filter that finds no matches stays available so you can change or clear it.

### Source availability and saved analysis

Reloading the local dashboard validates the selected
manuscript before serving cached measurements. Changed readable bytes trigger a
rebuild. If the file is missing, unreadable or a rebuild fails, a last successful
view remains usable with an **Analysis freshness** notice and **Retry refresh**.
That label identifies saved analysis; it does not claim the unavailable source
is current. Restore access or correct the source/settings, then retry. Recovery
clears the notice only after the required read or rebuild succeeds. An initial
missing source without a successful snapshot keeps the existing missing-file
presentation. This is request-time validation, not an automatic file/configuration
watcher; an unavailable source is not presented as a newly validated analysis.

<a id="style-area-since-v230"></a>

### Style area

Tabs group the heatmap, style reference, dimensions and structural diagnostics.
`ArrowLeft`/`ArrowRight` moves between tabs; `Home`/`End` selects the first/last.
Links to `#heatmap`, `#bands`, `#dimensions`, `#structural` and `#feat-<field>`
select the relevant tab. All available panels remain readable without JavaScript.

Keep the three comparison scopes separate:

| View | Measurement / reference | What it does not establish |
| --- | --- | --- |
| Paragraph comparison | One paragraph's raw value against that chapter's median/MAD | A chapter-level z* or a writing fault |
| Chapter fingerprint | One chapter feature against the manuscript reference, with noise-adjusted z* | A cross-metric ranking or an external writing target |
| Style dimensions | Chapter coordinates and axis loadings in standardized midrank space | Paragraph evidence, chapter z*, causal contributions or quality |

The [methods](METHODS.md) define these quantities; the
[interpretation guide](guides/interpretation.html) explains their limits.

**Since v0.7.6:** selecting a heatmap cell or a style-reference
cutoff-hit count opens **Chapter measurements** before navigating. It explains
the selected metric, its unit and chapter sample, alongside all 16 canonical
chapter values, manuscript medians, reference sample counts and z* values.
Switching metrics keeps the same chapter and does not change manuscript marks.
Each metric has its own unit and reference. `–` remains unavailable, never zero.
**Read chapter** uses the existing manuscript navigation and selects only an
applicable paragraph layer; chapter-only metrics clear the prior layer rather
than substituting word marks. Closing or Escape returns focus to the trigger.

**Since v0.7.3:** the chapter matrix shows `0` when a style
comparison is available and no feature crosses its cutoff; `–` means that the
comparison is unavailable. **What is counted** explains the existing coverage:
chapter values use profiled body paragraphs and lists, while corpus/style
comparisons also include blockquotes. Their values can therefore differ;
the underlying coverage and scores have not changed.

### Settings and interpretation

In **Project → Analysis**, expand **Adjust highlights** to inspect controls
and explanations. **Apply** submits changes; restoring defaults only changes
the form. Invalid numbers and a strong cutoff below the noticeable cutoff fail
validation. [Configuration](#configuration-corpusconfig) explains persistent
project metadata and session settings.

**Manuscript language (analysis)** selects the language profile for counting and
also sets the generated interface language. English is the default; `auto`
requests explicit function-word-based detection. This control is not an
independent interface-language preference, especially for mixed-language texts.

The matrix color scale stays fixed at z* = −2.5 to +2.5. A **●** marks an
FDR-selected cell; color alone is not a significance decision. Cell details
include raw values, z*, standardized effect and Cliff's δ. The style reference
shows the manuscript median ± 2 robust standard deviations, with sample counts.
Its cutoff-hit counts differ from FDR decisions; the bands are neither
confidence intervals nor external editorial targets. Paragraph style layers
show measured values and flag unusual values relative to the chapter.

With **Analysis On**, choose one metric
in the direct **Measure** selector. Blue/orange raw-value markers and down/up
arrows identify notable paragraph comparisons against that chapter's median/MAD;
the prose background stays clear. The marker opens the paragraph measurement
and its local comparison; **Values** retains the full paragraph measurements.
**Next deviation** opens the paragraph. **Clear metric** removes
the selected metric and its deviation filter, leaving the flagged-paragraph
filter unchanged. **Show all paragraphs** clears both paragraph filters and the
selected metric. These are different reset scopes, not separate analyses.
Analysis Off hides the marks and related keys while retaining your choices.
Native text selection, search and saved research marks remain separate.

The strip's colour and notable membership now use the same within-chapter
comparison. The scale is fixed at z = −2.5 … +2.5; paragraph notability uses
`abs(round(z, 2)) >= 1.5`. This is separate from chapter cutoffs and FDR.
At least three measurable paragraphs and nonzero MAD are required. The legend
reports comparable coverage and distinguishes no comparison from zero notable
paragraphs; raw paragraph values remain available in both cases.

In the **Style fingerprint** table, declared chapter registers and declared POV
can filter the visible rows. The choices combine with FDR-only. The visible
status states that the reference remains the full manuscript: no baseline,
score, global count, register target or style dimension is recalculated. Only
this table is filtered. **About this comparison** explains scope and register
exemptions; **Clear chapter filters** restores all rows. Name mentions are not
POV declarations. Following an exact hidden row anchor clears the display filters
before the existing jump. A separate within-voice reference is not implemented.

### Style-space navigation

In **Style dimensions**, drag to rotate, use the wheel or labeled buttons to
zoom/rotate, and select chapter points or **Chapter scores** links to read a
chapter. Toggle the trajectory or cutoff box and reset the camera as needed.
Rotation is opt-in and pauses in a hidden tab. Cards show positive/negative
loadings; the table gives the same measured chapter scores and flags.

**Since v0.7.6:** every loading, including chapter-only metrics,
opens the same **Chapter measurements** view for the selected chapter.
The originating axis and loading coefficient remain distinct from the chapter's
measurement and z*. Selecting another metric removes that axis-origin caption;
it does not recompute scores, infer chapter contributions or establish causality.

The chapter selector keeps the chosen chapter's
scores beside the plot. Choose a flat axis pair in **View** when points overlap;
return to 3D to rotate the same data. The line follows chapter order, including
gaps where a chapter has no measured position. **Reset** restores the view,
without changing chapter scores or analysis settings.

The box represents independent axis cutoffs, not a confidence ellipsoid.
Canvas points are pointer-operated; native controls and chapter-score links
provide keyboard/touch navigation and remain usable without JavaScript.
These provisions do not establish complete accessibility conformance.

## Command reference

### Common options

The installed CLI owns exact arguments, accepted values and defaults:

```bash
lixity --help
lixity style --help
```

Use `lixity COMMAND --help` for any command below. Explicit analysis options
override project settings. English is the default analysis language; automatic
detection requires `--language auto`. `lixity about --json` lists installed
commands, formats, feature identifiers, languages and thresholds. `lixity schema`
emits the same capability metadata, not a JSON Schema for every result.
[Automation contracts](AGENTS.md) describe versioned output envelopes and exit
codes; a running server advertises registered operations at `GET /api`.

**Since v0.7.6:** `analyze`, `profile`, `style`, `dialogue`, `pacing` and `showing`
accept `-o PATH` / `--output PATH` for their text or JSON report. Without it,
report data goes to stdout. With it, a successful result is written atomically
and stdout stays empty; diagnostics remain on stderr. A failed report/write
preserves an existing destination. The manuscript and its aliases cannot be
used as the report destination. PDF and dashboard keep their own file formats.

```bash
lixity analyze manuscript.md --language en --json -o analysis.json
lixity profile manuscript.md --language en --layer asl -o paragraph-review.txt
```

`dialogue`, `pacing`, `motifs` and `showing` use the same guarded manuscript
reader as `analyze`: invalid UTF-8 or a special file node returns processing
failure (exit 1), without waiting for a pipe writer or publishing a result.

### `lixity analyze`

Use the terminal report for corpus size, sentence rhythm, vocabulary,
readability, dialogue and chapter measurements:

```bash
lixity analyze manuscript.md --language en
```

Add `--json` for the versioned metrics envelope. Counts distinguish full input,
prose and regex tokens; `clean_words` retains its legacy whitespace count.
`median_sl` retains the integer upper median; `median_sl_exact` averages the
middle pair. Dialogue percentages divide quoted tokens by tokens under the
same configured `word_regex`, including chapter `dialog_pct`. Regenerate both
sides of a comparison with the same analysis version. See
[metric definitions](#understanding-the-metrics) and
[JSON contracts](AGENTS.md#3-json-contracts).

<a id="grammatical-german-tense"></a>

### Grammatical tense

Since v0.7.6, explicitly installed local syntax models can replace lexical
tense cues with contextual verb-group analysis in de/en/fr/es/it/pt/nl. This is optional: the default
installation retains lightweight, incomplete pattern counts. Installing a model
does not silently change existing projects. Languages without an explicitly selected model retain their existing
profiles. No model or manuscript data is downloaded/uploaded during analysis.

For the normal isolated application installation, install the extra and the
explicit model wheel in the same environment (network access is needed here):

```sh
uv tool install --force --python 3.12 "lixity[linguistics]==0.7.6" --with https://github.com/explosion/spacy-models/releases/download/de_core_news_md-3.8.0/de_core_news_md-3.8.0-py3-none-any.whl
```

For a Python project, use `python -m pip install "lixity[linguistics]==0.7.6"`
and install that model wheel into the same environment. The model is a separate
upstream artifact, not bundled in the Lixity wheel. Its published metadata lists
MIT licensing. Pin and review model versions independently; restart the app after
changing models. The core package still supports Python 3.10+; model/runtime wheel
availability is a separate platform prerequisite. Python 3.12 is the tested setup.

The initial CPU model choices were checked separately, not assumed equally
accurate. Models and their training data have separate licenses; none are
bundled in Lixity. Review the selected artifact's current terms before reuse:

| Analysis language | Initial tested model | Runtime | Published model terms |
| --- | --- | --- | --- |
| German | `de_core_news_md` 3.8.0 | spaCy | MIT |
| English | `en_core_web_md` 3.8.0 | spaCy | MIT |
| French | `stanza:fr_gsd`, resources 1.15.0, GSD nocharlm | Stanza CPU | Apache-2.0 model repository; GSD data CC BY-SA4.0 |
| Spanish | `es_core_news_md` 3.8.0 | spaCy | GPL-3.0 |
| Italian | `stanza:it_markit`, resources 1.15.0, MarkIT nocharlm | Stanza CPU | Apache-2.0 model repository; MarkIT data CC BY4.0 |
| Portuguese | `pt_core_news_md` 3.8.0 | spaCy | CC BY-SA4.0 |
| Dutch | `nl_core_news_md` 3.8.0 | spaCy | CC BY-SA4.0 |

Other supported-language spaCy pipelines can be explicitly selected; they need
a parser and POS/morphology annotations and their actual language must match.
The Italian spaCy models' CC BY-NC-SA terms are why the initial tested Italian
setup uses MarkIT instead. This records published terms, not blanket clearance
of every training source or voice model. See official
[spaCy model metadata](https://github.com/explosion/spacy-models/tree/master/meta)
and the [Stanza Italian](https://huggingface.co/stanfordnlp/stanza-it) and
[French](https://huggingface.co/stanfordnlp/stanza-fr) model repositories.

The Stanza profiles require `lixity[linguistics-stanza]` and a suitable CPU
PyTorch installation. Use the interpreter of the same environment that runs
Lixity; obtain resources explicitly during setup, never during analysis:

```python
import stanza
stanza.download("fr", package=None, processors={
    "tokenize": "gsd_nocharlm", "mwt": "gsd", "pos": "gsd_nocharlm",
    "lemma": "gsd_nocharlm", "depparse": "gsd_nocharlm",
})
stanza.download("it", package=None, processors={
    "tokenize": "markit_nocharlm", "mwt": "markit", "pos": "markit_nocharlm",
    "lemma": "markit_nocharlm", "depparse": "markit_nocharlm",
})
```

`STANZA_RESOURCES_DIR` can explicitly select the machine's resource directory;
use the same location during setup and app startup. The adapter selects only
these named processors, CPU mode and `download_method=None`; it does not select
a default/combined model if resources are missing. Set project `language="fr"`
with `tense_model="stanza:fr_gsd"`, or `it` with `stanza:it_markit`. For spaCy,
install the selected official 3.8.0 model wheel in the same environment, as in
the German example above. Pipeline failures are explicit; a single word whose
morphology is unknown is retained as an unresolved group instead of aborting
an otherwise annotated chapter.

Enable it explicitly at the project root, outside any TOML section:

```toml
language = "de"
tense_model = "de_core_news_md"
tense_scope = "narration"
```

Or select it for one invocation:

```sh
lixity profile draft.md --language de --tense-model de_core_news_md --tense-scope narration
lixity analyze draft.md --language de --tense-model de_core_news_md --json
```

`analyze`, `profile`, `analysis-review`, `style`, `dashboard`, `build`, `scenes` and foreground
`serve` accept these overrides. Saved project settings apply to CLI, native app,
Python pipeline and exports. `tense_scope = "all"` counts indicative verb groups
inside and outside recognized quotations; `narration` excludes recognized quoted
spans. This is quotation scope, not automatic narrator, thought or speaker
attribution. Scope is resolved over canonical chapter prose, including blockquote
context, before individual paragraphs are analyzed. Unmatched and unsupported
quotation formats can be missed; quotes do not continue across chapter boundaries.

A perfect construction such as `hat lange gesungen` counts once as past;
its auxiliary does not also count as present. Resolved present forms populate the present bucket; preterite, imperfect,
perfect, pluperfect and anterior perfect populate past. English and Dutch models
often omit Mood: those finite forms retain `mood="unmarked"` rather than being
relabeled indicative, but can contribute a resolved morphological tense. Future, conditional, modal,
subjunctive, imperative and nonfinite/unresolved groups do not populate them.
`ParagraphProfile.tense_analysis` and profile JSON preserve the detailed
`grammatical-tense/1` groups, exact component ranges, mood, voice, quotation scope,
selection and unresolved reasons. Component offsets address canonical counting
text; the existing evidence layer separately maps the enclosing cue span to
original displayed prose. It may contain intervening words. A coordinated
predicate can share an auxiliary with another predicate. The passage inspector
shows exclusions and unresolved groups, including paragraphs without a warning.

Explicit tense regex overrides cannot be combined with `tense_model`.
Missing models, annotation failures and paragraphs over 250,000 characters fail
explicitly; they never silently fall back to pattern counts. Parser model, model
version, spaCy version and composition policy are part of saved review identity.
Changing those settings invalidates prior review decisions rather than accepting
old decisions under a new measurement. Recompute reports after enabling a model.

The initial model comparison and known errors are documented in
[Stability](STABILITY.md#grammatical-tense). A grammatical form is not an
editorial error; historical present, recollections and dialogue need human review.

### `lixity profile`

Locate paragraph-level tense mixtures, switches and style densities with
source line anchors:

```bash
lixity profile manuscript.md > profile.json
```

This command emits JSON. Language-neutral `dominant` values (`present`, `past`,
`mixed`, `neutral`) become localized labels in reports. Without an explicit grammatical model, tense classification
counts curated verb forms: `mixed` requires at least two markers per tense and
at least 25% minority share. `switch` compares consecutive dominant tenses;
severity 0–3 prioritizes review. See the [classification contract](AGENTS.md)
for the truth table and direct-library threshold controls.

Densities are counts per 1,000 words, not percentages; short paragraphs can have
large values from few matches. Nominalization suffix cues exclude curated
function words unless a project regex override is supplied. They remain
heuristics rather than a grammatical parse.

**Since v0.7.3:** inspect the same selected paragraph metric
from the terminal, without printing manuscript prose:

```bash
lixity profile manuscript.md --layer asl
lixity profile --layer filter --only-notable
lixity profile --layer filter --only-notable --json
```

Choices are `asl`, `function`, `dialogue`, `filter`, `modal`, `nominal` and
`passive`. Human output lists source-file/line anchors, raw values/units and local
z. `--only-notable` filters output after computing all chapter references; it
requires `--layer`. The summary keeps full profiled/comparable/notable counts
separate from rows shown. On current main after v0.7.6, empty human selections
explain the actual chapter limits (too few measurable paragraphs, zero MAD or no
measurable values) and provide a shell-quoted full-evidence command. German
analysis reports also use German explanations; machine identifiers remain stable.
Configured manuscript omission follows the existing
[project resolver](#default-manuscript). Without `--layer`, profile retains its
existing JSON v2 output, including when `--json` is omitted.

With `--layer --json`, the opt-in envelope is `paragraph-layer/1`; unavailable
comparisons have `z: null` and `notable: null`, while measured zero remains zero.
Densities remain word-pattern counts per 1,000 words, not exact token spans or a
grammatical interpretation. See [the contract](AGENTS.md#311-opt-in-paragraph-layers).

Since v0.7.3, add `--evidence` to a selected layer for literal counted spans:

```sh
lixity profile --layer filter --evidence
lixity profile --layer asl --evidence --json
```

Human output includes bounded quoted examples and source lines. JSON uses the
separate opt-in `paragraph-layer-evidence/1` envelope with exact Unicode-codepoint
offsets and paragraph hashes; default profile and `paragraph-layer/1` outputs are
unchanged. `--only-notable` still filters after full chapter references. Mapping
status distinguishes available, partial and unavailable evidence; measured zero
remains zero. See [the evidence contract](AGENTS.md#311-opt-in-paragraph-layers).

### `lixity dialogue`

Inspect quoted-speech segments, their lengths and chapter distribution:

```bash
lixity dialogue manuscript.md
```

A turn is a quotation segment, without speaker attribution. A dialogue paragraph
has at least half its words inside detected quotations. `--json` returns these
summary and per-chapter measurements for automation.

**Since v0.7.3:** the browser dialogue chart retains every
measured chapter in manuscript order, including chapters with zero detected
turns. Long charts scroll within their bounded area rather than showing only
the chapters with the most dialogue.

### `lixity characters`

Count supplied names or alias patterns across chapters:

```bash
lixity characters manuscript.md --name "Alex|Alexander" --name Morgan --json
```

Matching is whole-word and case-insensitive, excludes appendix/front matter,
and reports mentions, mention-based chapter span and longest gap. A match does
not establish physical presence, speaker identity or viewpoint. v0.7.1
can use [project-local literal profiles](#character-profiles) when explicit names
are omitted. Explicit names replace configured selections, including an empty
selection; the standalone command rejects empty names rather than discovering entities.
The [structure-result contract](AGENTS.md#35-structure-modules-dialogue-characters-pacing-motifs-showing)
documents all dialogue, character, pacing, motif and showing result fields.

### `lixity pacing`

Inspect scene lengths, sentence-length curves and chapter-ending cues:

```bash
lixity pacing manuscript.md
```

Explicit Markdown dividers split scenes. With no dividers,
`explicit_scene_breaks=0` and `scenes_are_chapters=true`: scene counts are chapter
placeholders and give no independent pacing evidence. Tempo proxies are sentence
length, staccato share, dialogue share and scene length. The hook score (0–3)
adds one for each closing cue: at most eight words, terminal `?`/`!`/`…`, and
closing dialogue. It measures these cues, not suspense or reader response.

**Since v0.7.6:** text summaries identify the chapters with the shortest and
longest mean sentence length. The historical JSON keys `fastest_chapter` and
`slowest_chapter` retain their ASL-based meaning; they do not measure narrative
speed or reading time.

**Since v0.7.3:** the pacing panel labels average sentence length
as **ASL**, gives its words-per-sentence unit and explains that bars are scaled
to the largest chapter average. The **Hook** help describes the same 0–3
heuristic; it adds no new suspense or quality score.

In the browser's **Pacing & scenes** and **Showing/telling** panels, long chapter
charts scroll within their bounded area. Use the mouse wheel or touch, or focus
a chapter row and use the keyboard's scrolling keys. All rows remain readable
at the end; a short chart that already fits needs no inner scrolling.

### Scene registers and project targets

Without chapter headings, a draft is measured as one chapter and keeps all its
prose. A leading `# Title` supplies its title; scene dividers still split the draft.

Use `lixity scenes manuscript.md --language de` to inspect each scene separately;
add `--json` for the scene envelope (schema version 1). The dashboard
shows the same observations in **Scenes & style registers**. Chapters serve as
scenes when there are no explicit dividers.

**Since v0.7.3:** the scene comparison table stays visible in a
bounded scrolling region. Choose a scene's linked title to reveal its detailed
measurements inside **Scene measurements**. The catalogue and each scene use
native, reversible disclosures; close either summary when finished. These are
the same observations and project-defined comparisons, without a new analysis
or API format.

For everyday checks in a selected project:

```bash
lixity scenes --chapter 2
lixity scenes --scene 2:1 --json
lixity scenes --latest
lixity scenes --chapter 2 --latest
```

The optional file defaults to the current workspace's manuscript; configure it
explicitly as described [below](#default-manuscript). Chapter numbers and
`chapter:scene` IDs are the numbers printed by Lixity, not numbers embedded in
heading titles. `--latest` means the last **measurable scene in document order**,
not the most recently edited scene. It excludes plans. `--scene` and `--latest`
are mutually exclusive; a supplied `--chapter` must agree with `--scene`.
Unknown selections fail rather than return an empty success.

Filters reduce output after the entire manuscript is validated and measured.
They preserve scene IDs, measurements and full-manuscript register references;
they do not speed up analysis or hide invalid assignments elsewhere. Filtered
JSON adds `scenes.selection` with `chapter`, `scene`, `latest`, `selected_count`,
`total_count` and `reference_scope: "full_manuscript"`. Counts refer to measured
rows; when plans are configured, `selected_planned_count` and
`total_planned_count` describe those separately. Unfiltered JSON has no selection
object and retains its existing shape.

Register assignments and targets belong to your project. For example:

```toml
[scene_analysis.assignments]
"1:1" = "close narration"
"1:2" = "close narration"
"2:1" = "report"

[scene_analysis.groups."close narration".targets]
asl = [8, 15]
filter_density = { upper = 2 }

[scene_analysis.groups.report.targets]
modal_density = { lower = 3 }
```

Save this in the project's `lixity.toml` (or under `[tool.lixity.scene_analysis]`
in `pyproject.toml`). These numbers illustrate settings, not recommended prose.
Assignments use chapter:scene numbers; review them after inserting or removing
scenes. Invalid assignments are reported instead of silently moving a register.
Since v0.7.4, the error names measured scene and recognized divider counts for
each affected chapter, or states that the chapter is absent. Review missing
standalone dividers, removed/merged scenes and configuration; blank lines alone
do not separate scenes. Explicitly planned scenes remain separate from measurements.
Each group gets its own manuscript-only median and MAD, with at least two
available observations per feature. Unassigned scenes have no register baseline.
Research sources never enter these references.

To plan an unwritten scene without disabling stale-assignment checks, explicitly
list its assigned ID:

```toml
[scene_analysis]
planned = ["3:1"]

[scene_analysis.assignments]
"1:1" = "voice"
"3:1" = "voice"

[scene_analysis.groups.voice.targets]
asl = [8, 15]
```

`planned` must be a unique list of valid assignment IDs. Missing assignments not
listed there still fail. A plan has no analyzable text, measurements or baseline
membership. CLI output labels it separately; the analysis panel has an expandable
**Planned scenes** section. Once its text is measurable, the same ID appears as an
ordinary measured scene. Review positional IDs after inserting/removing scenes.
JSON adds `planned_items` only when a nonempty `planned` list is configured; its
rows contain `id`, `chapter`, `scene`, `group` and `state: "planned"`. It becomes
empty once all listed IDs are measurable. No plans are inferred from headings,
blank lines or missing assignments. A completely empty workspace still opens its
existing setup view; the CLI can inspect its plans without inventing measurements.

Targets use the fields reported by `lixity about --json`, such as `asl`,
`filter_density`, `modal_density`, `nominalization_density`, `passive_density`,
`sentence_cv` and `start_entropy`. `feat_*` names are translated display keys,
not API functions. HD-D uses **0–1**, not 28–48; staccato is **≤6 words** and
the long-sentence share is **>25 words**. Rhythm proxies do not measure musical BPM.

The report includes actual word/sentence counts, observations, approximate core
standard errors and descriptive target positions (below/within/above). HD-D is
unavailable below 100 tokens; CV needs at least two sentences. Zero plug-in
standard errors are withheld, and HD-D has no population error estimate.
These are not validated confidence intervals or a literary-quality score.
Existing analyze/profile (v2) and style (v4) envelopes remain unchanged.

### `lixity motifs`

Configured motifs use the root-local `[motif_regexes]` table. The compatible
legacy `[motifs]` spelling is also accepted. Since v0.7.4, distinct names from
both tables combine consistently in chapter measurements, the live dashboard,
the motif panel in `build` dashboards, CLI and Python reports. Other optional
`build` panels retain their existing scope. Identical duplicates deduplicate;
different patterns under the same name fail explicitly. Prefer one table for a new project.
`--motif NAME=REGEX` replaces configured motifs for that invocation. In Python,
an omitted mapping inherits configuration; an explicit `{}` suppresses curated
motifs while leaving generic repetition analysis available. An empty configured
regex counts no occurrences, consistently with other empty cue patterns.

Track a curated regular-expression motif alongside frequent content words and
repeated n-grams:

```bash
lixity motifs manuscript.md --motif 'door=\bdoor\w*\b' --json
```

The report counts and locates repetition across chapters; deliberate repetition
is not an error. Function/stop words are excluded from top-word counts. See
[local repetition echoes](#local-repetition-echoes) for nearby clusters and
phrase-overlap handling.

### `lixity showing`

Compare a heuristic chapter balance against this manuscript's own baseline:

```bash
lixity showing manuscript.md
```

The word-pattern group combines perception/thought, modal, passive and noun-ending
cues per 1,000 words. The second group combines quoted-word and short-sentence
shares. The equally weighted group means yield `balance = show_z − tell_z`:
positive means the second group is higher relative to this manuscript's baseline,
negative means the first is higher. This does not classify narrative distance,
showing/telling or scene quality. Zero MAD falls back to standard deviation.

Comparison needs at least three chapters with differing signals. Otherwise the
app shows `–` and explains the missing support while retaining raw measurements.
For compatibility, JSON component z-scores fall back to zero with too few
chapters; identical balances yield empty `most_telling`/`most_showing` ranks.
Empty ranks mean no distinguishable ordering, not identical artistic effect.

The native **Analysis overview → Signal-group comparison** panel
shows these chapter values and links back to the manuscript. Review-workspace
website copies include that analysis; curated reader/companion copies exclude
it. Bar length shows the magnitude of the balance; its signed number gives the
direction between the two groups relative to this manuscript. For concrete wording, enable manuscript **Analysis**
and choose a component such as **Perception filters**, **Modals**, **Noun endings** or
**Passive patterns**. **Counted text** marks the exact
lexical cues independently of **Paragraph comparison**. Inspect a marked span
to read its count and counting rule.

The composite is chapter-level; it is not a word-by-word showing/telling
classification. It does not distinguish abstract adjectives from sensory verbs.
A marked perception verb is a counted filter cue, not proof of telling or a
request to remove it. Interpret the chapter contrast together with the scene's
purpose and the [heuristic limits](STABILITY.md#linguistic-proxies-and-literary-interpretation).

### `lixity style`

Compare chapter features with the manuscript's own style baseline:

```bash
lixity style manuscript.md --json
```

Inspect active thresholds in the JSON `meta` or dashboard legend rather than
assuming defaults. `lixity style --help` lists available overrides.

The reference describes sentence patterns, vocabulary and heuristic markers
against this manuscript's own baseline. Raw deviations, nominal FDR selections
and exploratory dimensions answer different questions; none establishes literary
quality or a guaranteed false-discovery rate. [Methods](METHODS.md) owns the
mathematical definitions; [Stability](STABILITY.md) describes inference limits.

Select a chapter in the style space, inspect its
values and open its passage. The view and CLI explain their coverage, axes,
cutoffs and unavailable values in place; JSON exposes `dimension_diagnostics`.

Compare scenes within their intended register and read the passages. A
deliberate change of voice can explain a deviation; the style reference does
not prescribe a writing target or decide whether to edit.

### `lixity dashboard`

```bash
lixity dashboard manuscript.md -o dashboard.html
```

The output is one self-contained HTML file with manuscript text, measurements
and offline navigation; it needs no CDN or external requests. Identical input
and settings produce identical output. The panels cover sentence rhythm,
dialogue, curated character presence, scenes, motifs, narrative-distance cues,
chapter style, paragraph profiles and work markers as data permits. See the
[dashboard workflow](#dashboard-workflow) to move from measurements to passages.
A compatible server provides explicit project actions and marker saves.

### `lixity pdf`

Create a local reading copy without a browser or external converter:

```sh
lixity pdf manuscript.md --layout book --author "Example Writer" -o reading.pdf
# Since v0.7.0: an annotation copy with page and line numbers.
lixity pdf manuscript.md --layout editor -o editorial.pdf
# Since v0.7.4: neutral A4 text without generated title/header material.
lixity pdf expose.md --layout document -o expose.pdf
```

| Layout | Page | Purpose |
| :--- | :--- | :--- |
| `editor` (since v0.7.0) | A4 | Editorial reading with line numbers and room for comments |
| `document` (since v0.7.4) | A4 | Neutral text with authored headings; no added title page, headers, footers or line numbers |
| `report` | A4 | Analysis report with cover page and repeated table headers |
| `book` | A5 | Continuous reading with serif text, mirrored margins and chapter openings |
| `sheet` | A4 | Submission grid, at most 30 lines per page and 60 characters per line |

Output defaults in the selected workspace root; `-o` selects another path. Unchanged input,
settings and fonts produce identical output. The manuscript is not modified.
PDF and dashboard CLI exports reject the source path and its symbolic/hard-link
aliases, before writing and again immediately before atomic replacement.
The [native download form](#download-a-manuscript-pdf) uses the same composer
without writing a CLI output path.

Title selection prefers an explicit override, the selected project's title,
supported manuscript title metadata/heading, then the filename. Fenced code is
not a title candidate. `--author` overrides project `author_name`; an explicitly
empty value clears the byline. PDF metadata includes title/author when present
and the resolved language. A5 has chapter bookmarks and body-page title/author
headers; title/imprint pages omit decorations but count toward physical folios.
A4 editorial, sheet and report headers and page footers sit outside the prose/grid area.
The neutral `document` layout retains the authored first title and other headings;
configured title/author overrides affect metadata only. It adds no byline,
analysis, imprint, title page or running furniture.
The optional `draft_notice` project setting (or `--draft-notice` override) adds
a running-header notice in the other four layouts; `document` omits it.
An empty override clears the notice. See
[publication settings](#publication-settings) for optional A5 imprint text.

Fonts come from the host and can be pinned per role with CLI options listed by
`lixity pdf --help`, or `LIXITY_PDF_FONT_TEXT`, `_HEADING`, `_ITALIC`, `_BOLD_ITALIC`,
`_MONO`, `_SANS` and `_SANS_BOLD`. Only used glyphs are embedded, with searchable/copyable text maps.
Missing fonts, embedding restrictions or missing glyphs fail explicitly; a
glyph error identifies its font role and Unicode codepoint. Each role requires
a single-face TrueType outline font; collections and CFF outlines are
unsupported. There is no automatic mixed-script fallback, contextual shaping
or bidirectional layout. Font coverage alone does not establish correct
rendering for every script.

Since v0.7.0, manuscript structure is preserved independently of the analysis text:
prefaces, subheadings, scene breaks, lists, quotations and notes survive export.
Inline emphasis uses font styles; note definitions retain their text. Embedded
LaTeX text formatting is a bounded subset, never executed as TeX. Unsupported
TeX constructs report an error rather than silently changing the manuscript.
Compare the same six-chapter *The Crate at Warehouse 4* manuscript as an
[A4 document](demo/warehouse-4-document.pdf),
[editorial copy](demo/warehouse-4-editor.pdf),
[reading copy](demo/warehouse-4-book.pdf),
[submission grid](demo/warehouse-4-sheet.pdf) or
[analysis report](demo/warehouse-4-report.pdf).

The composer wraps paragraphs and overlong words but does not hyphenate, place
images, typeset mathematics, create page-numbered tables of contents or alternate
recto/verso running heads. Image references remain labelled text. See
[Architecture](ARCHITECTURE.md) for the shared composition boundary.

These fixed-layout PDFs are for everyday documents, editing, analysis, reading and submission.
There is no EPUB/DOCX export, custom trim size, bleed/crop marks, print color management, printer preflight or
PDF/UA/PDF/X certification. Searchable text, metadata and bookmarks alone do
not establish accessibility or production compliance.

### `lixity read-aloud`

**Development prototype:** create a listening copy using Qwen3-TTS 1.7B
CustomVoice. The CLI and native preview/chapter dialog share the same project
voice profiles, rendering controls and local/Jetson targets. The optional worker
and its model require separate setup. This is not a production audiobook pipeline.

```bash
lixity read-aloud manuscript.md --language en -o manuscript.wav
lixity read-aloud manuscript.md --language de --chapter 2 --voice Ryan -o chapter-2.wav
lixity read-aloud --project ./novel --language de -o reading-copy.wav
```

`--chapter` selects a one-based chapter number. Without an explicit file, the
command uses the selected project's configured manuscript or folder discovery.
Without saved audio settings, the default is one Qwen narrator using preset
`Ryan`, the project language and empty delivery instructions. English remains the
language default. `--voice` selects a Qwen preset, such as `Ryan` or `Aiden`.
The supported languages are `en`, `de`, `fr`, `es`, `it`, `pt`, `ru`, `zh`, `ja`
and `ko`: six of the seven analysis languages, with Dutch (`nl`) unsupported.
Choose a supported speech language explicitly for a Dutch project; there is no
automatic language or backend fallback. Preset language support does not certify
native pronunciation. Review the model license before distributing output.

**Since v0.7.6:** saved project audio profiles are shared by the CLI
and native **Audio & voices** dialog, reachable from Project settings and the
manuscript controls. Choose or create a profile, audition the selected passage,
then render a chapter. Draft previews do not save settings; **Save profiles**
persists the selected profile and its controls through the normal atomic project
settings path. Read-only exports do not offer synthesis or expose audio settings.

```bash
lixity read-aloud --project ./novel --profile narrator -o reading-copy.wav
lixity read-aloud --project ./novel --profile narrator --chapter 2 -o chapter-2.wav
```

Choose **Render on → This computer / Configured Jetson** in the dialog,
or pass `--speech-target local|jetson` to the CLI. This choice applies to that
render; it is not part of a saved voice profile. The default is local, and an
unavailable target fails explicitly without switching machines or models.
Jetson sends the selected synthesis text to your configured machine through SSH;
it does not use a hosted inference provider.

```bash
lixity read-aloud --project ./novel --profile narrator --speech-target jetson --chapter 2 -o chapter-2.wav
```

Machine setup is explicit: run the same Qwen worker on the Jetson with its
supported CUDA environment and complete local checkpoint. Keep that worker on
`127.0.0.1:8769` there, and forward laptop port `8770` over authenticated SSH:

```bash
ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 -L 127.0.0.1:8770:127.0.0.1:8769 USER@JETSON
```

Use your normal verified SSH host key and account. The local CPU worker continues
to use port `8769`; selecting Jetson uses only the fixed loopback forward `8770`.
The browser cannot supply a host address or arbitrary inference URL. Lixity does
not install or start the remote worker or SSH connection. GPU compatibility and
available shared memory must be checked on the actual device; 8 GB does not
guarantee that every input fits.

Long CPU renders can be retried without recomputing every completed segment.
Qwen chapter jobs in the native UI and CLI renders retain verified segments in
`$XDG_CACHE_HOME/lixity/speech/<project-hash>/` (default
`~/.cache/lixity/speech/<project-hash>/`), bounded to 2 GiB per project.
The manuscript folder need not be writable.
Repeating the render reuses only requests with the same synthesis text, named
model family, language, preset voice and delivery instructions. Changes to pauses
are applied when assembling the output; they do not require new speech. Progress
includes reused segments. The final WAV/MP3 still appears only after successful
completion, so cancellation or failure preserves an existing output.

The native **Reuse completed chapter segments** option is enabled by default;
uncheck it for a fresh interpretation. CLI users can request the same explicitly:

```bash
lixity read-aloud --project ./novel --profile narrator --chapter 2 --fresh-audio -o chapter-2.wav
```

`--no-audio-cache` renders without reading or retaining segments.
Previews are always fresh. The Python renderer
opts in with `cache_dir=...`, and accepts `fresh_audio=True` to recompute while
refreshing retained segments. Matching segments can be reused across execution
targets; request fresh audio when comparing CPU and GPU delivery.
Cache metadata stores request/audio hashes rather
than raw manuscript text, but the WAV files contain spoken project content and
must be treated as private. Missing, corrupt or evicted entries are recomputed.
The cache is not a saved job ledger: after restarting the app, start a new chapter
job to reuse its completed work. Temporary download expiration does not erase
these retained segments. Remove the derived folder to discard it. After replacing
local checkpoint files within the same named model family, request fresh audio
or clear the cache; the key does not fingerprint model weight bytes.

External FFmpeg conversion is limited to one hour per invocation.
A timeout fails the export, preserves an existing completed output and removes
temporary files. It does not restart a service or switch engines. This limits
the direct child process, not in-process inference or arbitrary grandchildren.

The selected saved profile is used when `--profile` is omitted. Explicit `--voice`,
`--language` and `--instructions` override that invocation without rewriting the
saved profile. Unsupported combinations fail before rendering. Precise speed
control and `--speed` are unavailable; profile `speed` must remain `1.0`. Delivery
instructions can request a pace, but do not guarantee an exact speaking rate.

A root `lixity.toml` can contain:

```toml
[audio]
schema_version = "lixity-audio-settings/1"
selected = "narrator"

[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3"
language = "de"
voice = "Ryan"
speed = 1.0
instructions = "Read calmly and clearly, without whispering."
paragraph_pause = 0.45
scene_pause = 1.2
```

Profiles are project-only; user and ancestor configurations cannot supply them.
They also accept a `pronunciations` table of literal term-to-spoken-form pairs.
These substitutions affect synthesis text only. A voice profile does not infer
character identities or turn words such as “quiet” into acting instructions.

**Current engine:** only `qwen3`, using the fixed
`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` checkpoint family and one of its nine presets.
Explicit style instructions, structural pauses and pronunciation settings are
shared by CLI and UI. Base voice cloning and VoiceDesign are not implemented.
Model capabilities determine the available controls; there is no automatic
backend fallback.

### Passage direction (current main; after 0.7.6)

The native Audio dialog can attach an author's direction to an exact passage or
selected range. Open Audio from the manuscript or Project settings, choose the
passage, and select text in the read-only **Spoken text** field for a smaller
range. With no selection, **Use selected text / whole passage** restores the
whole passage. Choose a saved voice profile or inherit the current narrator,
write local direction, and optionally set silence before/after in seconds.
The calm/tension/whisper choices are editable English prompt starting points,
not measured emotion controls. **Inspect preview plan** shows the actual spoken
text, effective preset, combined instructions and silence before calling a model.
Preview uses the draft; chapter generation requires **Save passage direction**.
Profile settings and passage direction have separate save actions.

Direction is retained in `.lixity/audio-directions.json`, separately from both
manuscript prose and `lixity.toml`. Each record binds the project-relative source,
its exact paragraph line/hash identity and a Unicode-code-point range in the
advertised spoken projection. Repeated wording at another location is a different
passage. Changed or moved paragraphs are preserved as stale records and require
explicit review/removal; they are never automatically reassigned. Overlapping
ranges and missing saved profiles fail before synthesis. The native dialog lists
stale records with explicit removal controls. Saved direction is private author
metadata and must be included in project backups when it should survive a move.

The shared planner first resolves ranges, then applies the selected profile's
literal pronunciation substitutions, then splits at direction and transport
boundaries. It never interprets bracketed manuscript text as acting instructions.
Longer pronunciation keys win; matching is case-sensitive, can match within a
word and is a single non-recursive replacement pass. A substitution spanning two
direction ranges does not match across their boundary.

A directed range uses its explicitly selected saved profile, otherwise the
invocation's current profile. Its local direction is appended to that profile's
instructions. CLI voice/language/instruction overrides affect the invocation's
default profile; explicitly referenced profiles keep their own settings. Newlines
in instructions become spaces. Silence after a range is inherited at paragraph
end or zero inside the paragraph unless supplied explicitly; supplied silence
replaces that boundary's default rather than adding a second pause. Pauses are
inserted as PCM silence by Lixity, not requested probabilistically from Qwen.

This data model takes separation of voice, pronunciation and pauses from SSML,
without claiming SSML compliance. Qwen receives ordinary `text`, `speaker`,
`language` and a separate `instruct`. Tone, emphasis and pace are model-interpreted;
there is no calibrated emotion intensity, exact speaking-rate/pitch control,
IPA phoneme input, guaranteed nonverbal effect or automatic character assignment.
Very short directed spans can sound disconnected. No cross-segment dramatic
memory or seamless multi-character performance is promised. Audio must be heard
and checked for word fidelity, pronunciation, voice continuity and delivery.

CLI observation and plan inspection need no running worker:

```bash
lixity audio-direction inspect --project ./novel
lixity read-aloud --project ./novel --chapter 1 --plan-only
lixity read-aloud --project ./novel --chapter 1 --no-direction --fresh-audio -o neutral.wav
```

`audio-direction inspect` returns paragraph anchors/spoken text, saved ranges,
stale flags, and the `source_sha256`, `settings_sha256`, `direction_sha256`
snapshots. Its JSON and plan output contain private prose and instructions.
To save, put one direction object in a private JSON file: `anchor` copied exactly
from inspection, optional code-point `start`/`end` (default whole paragraph),
optional `profile_id`, `instructions`, `pause_before`, and nullable `pause_after`.
`audio-direction save --project ./novel --input direction.json` additionally
requires `--expected-source`, `--expected-settings`, `--expected-direction` with
the three observed hashes. When changing a saved range’s bounds, pass its original
`--replace-id ID`; the original range is replaced under the same snapshot guards.
Removal uses `audio-direction remove --project ./novel
--id ID` with the same guards. Concurrent source/settings/direction changes reject
writes instead of overwriting another edit. Identical saves are idempotent.
`--no-direction` is an explicit neutral baseline for that invocation, not deletion.
Saved offsets use the marker-stripped spoken projection. `--keep-markers` is
rejected when retaining editorial markers would shift a directed passage; use
`--no-direction` for that deliberate alternative.
Cache reuse keys include the effective text/profile instructions; edited direction
cannot accidentally reuse audio synthesized with different instructions.

Piper has been removed. Existing saved Piper profiles fail with migration
guidance; a Qwen voice is not an exact replacement for their timbre or precise
speed. Preview explicit replacements before applying them:

```bash
lixity audio-migrate --project ./novel --replace narrator=Ryan
```

The command prints a JSON dry run and its `snapshot` token, without changing files.
Supply one `--replace PROFILE=VOICE` for every Piper profile; repeat the option for
multiple profiles. Optional `--instructions PROFILE=TEXT` chooses a new delivery
style explicitly; otherwise migrated instructions are empty. Review the choices,
then repeat them with the returned token and a new backup path outside the project:

```bash
lixity audio-migrate --project ./novel --replace narrator=Ryan \
  --apply --backup /backups/novel-audio-before-qwen.zip \
  --expected-snapshot REVIEWED_TOKEN
```

Migration preserves profile IDs, selected profile, names, languages, pauses and
pronunciation replacements. Speed becomes `1.0`; no timbre or exact pace equivalence
is assumed. The non-overwriting ZIP backup contains the original root configuration
files and a verification manifest, with private file permissions (`0600` on POSIX).
It contains no manuscript bytes. Keep it in private project storage: configuration
can contain private metadata and pronunciation text. Source/configuration changes
or changed replacement/style choices invalidate the reviewed snapshot. Apply verifies the backup before the atomic
settings update and never edits the manuscript. For recovery, preserve the current
configuration, then restore the original root configuration files from the backup;
do not replace manuscript or retained research files. Rendering restored Piper
settings requires a compatible prior application version.

Qwen runs in an optional isolated Python 3.12 environment with `qwen-tts` and a
hardware-appropriate PyTorch installation. Install the development checkout into
that environment (`python -m pip install -e /path/to/lixity`) and obtain the
complete local CustomVoice checkpoint, including its speech tokenizer, using the
[upstream setup instructions](https://github.com/QwenLM/Qwen3-TTS). Choose the CPU
build of PyTorch for CPU-only use. Neither opening Lixity nor starting the worker
downloads weights or sends manuscript text to an inference provider.

Start the worker explicitly from that environment:

```bash
python -m lixity.speech_qwen --model /path/to/CustomVoice --device cpu --threads 1
```

It binds only to `127.0.0.1:8769`, loads the local model once and serializes
synthesis. CPU operation supports full chapters; generation can be much slower than the
result's duration, so use a short preview to choose the voice. Match Torch threads
to the CPU budget assigned to the worker. A heavily throttled four-thread worker
can waste time contending within a one-core quota. Keep workstation CPU/memory
headroom through the operating system rather than silently reducing model size. GPU operation is
optional via `--device cuda`, with an explicit error when unavailable. The native
UI starts a background job and reports completed segments without keeping the
initial HTTP request open. Cancellation waits for an in-flight model segment to
return, then prevents publication. A slow segment is allowed up to one hour;
that limit is not an estimate of chapter duration.

Worker-only `--attention auto|eager|sdpa` selects the attention implementation.
The default `auto` uses eager attention on CPU and SDPA on CUDA. An operator can
compare an explicit override on the same checkpoint and workload; measure actual
synthesis, memory and output before selecting it. This flag does not establish a
performance improvement and cannot be set by browser input or a voice profile.

On a memory-constrained CUDA machine, an operator can explicitly keep the
talker on the GPU and run audio decoding on the CPU with the same checkpoint:

```bash
python -m lixity.speech_qwen --model /path/to/CustomVoice --device cuda --codec-device cpu --threads 4
```

The default `--codec-device model` keeps the decoder on the selected main device.
Worker-only `--codec-chunk-frames N` accepts 16–300 audio-code frames. The default
300 preserves the installed upstream decoder behavior. A smaller explicit value
uses that decoder's existing chunk algorithm with its 25-frame left context;
it can reduce per-chunk activation memory without changing model weights.
For example, test `--device cuda --codec-device model --codec-chunk-frames 32`
on the actual machine before adopting it. Unsupported decoder interfaces fail
explicitly. Chunking does not bound all model, KV-cache or output allocations,
and this option does not guarantee that a checkpoint fits in RAM.

CPU decoding uses float32 and trades GPU allocations for CPU work; this is an
explicit machine setting, not a voice profile or an automatic fallback. Shared
RAM remains finite. Suitable SSD-backed swap is a separate operating-system
decision; see [NVIDIA's Jetson memory guidance](https://www.jetson-ai-lab.com/tutorials/ram-optimization/).
Validate actual synthesis and memory headroom before scheduling long jobs.

Body paragraphs, quoted blocks and list prose use the shared Markdown text
projection. Link labels are read; destinations, images, code, footnote definitions
and YAML metadata are omitted. Long paragraphs use bounded sentence/word segments
without inserting paragraph pauses between fragments. Recognised editorial
markers are omitted unless `--keep-markers` is supplied. The manuscript is not
edited. Unknown chapters, unsupported voices and unsupported languages fail explicitly.

WAV output needs no FFmpeg; MP3 requires it before synthesis. Missing, malformed,
empty or mismatched PCM and failed conversion are errors. Streamed atomic output
preserves an existing file on failure. Native audio is a temporary download:
WAV output is capped at 200 MB during rendering, including inserted silence;
results are bound to the selected source/settings and selection generation, with
at most four retained jobs and a 30-minute retention window after completion.
Save the download when needed. Project/source changes invalidate old results;
returning to an earlier project cannot revive them. Model-generated omissions,
repetitions, pronunciation and expressive reading still need human review.
Successful encoding or an ASR transcript does not establish narration quality.

### `lixity service`

**Since v0.7.6:** one regular app instance supports independent
project views in multiple tabs. Project selection returns a scoped view URL
under the same origin instead of replacing every tab's selection. Use **App and
audio** to revisit open views, close an idle view or refresh worker/queue status.
The startup view stays available. At most 16 views are retained; their URLs
expire on server restart and return HTTP 410 instead of selecting another project.
Reopen the project from the home address after restarting. Additional ports are
for explicitly separate development instances, not ordinary project selection.
Launch overrides belong to the startup view; newly opened projects use their
own configuration instead of inheriting another book's analysis language or thresholds.

Audio jobs share one FIFO in that app: one render plus at most three waiting
jobs from other contexts. The dialog reports a waiting position. Cancellation
and stale-source checks apply before queued work starts; completed outputs retain
their own bounded retention window. **Ready** for a target means its expected
model answered the health probe, not merely that the tunnel port accepted TCP.
The existing external worker and SSH-forward lifecycle remains separate; status
does not install models, start a tunnel or establish that GPU acceleration works.

Start the installed workspace without keeping a terminal open:

```sh
lixity service start --open
```

Use `status`, `restart` and `stop` to manage the owned instance. Start defaults
to an empty workspace in an application-owned directory unless a project or
`LIXITY_DIR` is specified. `start` takes fresh launch settings; `restart` reuses
saved settings with explicit overrides, even after a stop. Neither restores a
later browser project choice. An already running instance is reported without
changing its settings. Restarting into a different project clears the prior
title unless explicitly replaced; plain restart keeps the saved title.

The controller manages its own instances. Stop foreground `lixity serve` with
Ctrl+C and OS-managed startup units through their manager. A busy port never
permits terminating an unrelated listener. Backend selection is per invocation;
repeat an explicit backend on restart. `LIXITY_*` environment values, including
OCR settings, are inherited on launch and are not saved as startup settings.
Use `lixity service --help` for lifecycle arguments, or
[installation and service setup](INSTALLATION.md#running-the-server).
For foreground `lixity serve PATH`, an invalid explicit path fails before startup.
A valid directory without a unique manuscript can open an empty workspace;
`lixity serve --no-project` intentionally starts without selecting a project.

**Changed in v0.7.4:** `lixity service status --json` uses the status-specific
`lixity-service-status/1` contract: `schema_version`, `ok`, `running`, `state`,
`port`, `url`, `pid`, `backend`, `installed_version`, `running_version` and
`message`. `ok` means the inspection succeeded: known `running`, `starting`,
`stopped` and unmanaged-port `busy` states exit 0. `running` means a ready owned
instance; it is false for the other known states. An unreadable, invalid or
changing state remains `unknown`, with `ok: false`, `running: null` and exit 1.
Unavailable metadata can be null; log paths, launch settings and raw errors are
omitted. Scripts parsing the older lifecycle envelope must update explicitly.

Human `service status` keeps its existing exit codes: a ready owned instance
exits 0; stopped, starting, busy and unknown states exit 1. JSON for `start`,
`restart` and `stop` remains `lixity-service-local/1` with its existing fields and
success semantics; stopping an already stopped instance succeeds. Stop preserves
saved launch settings and logs.

**Since v0.7.3:** status does not create or repair storage or
acquire the lifecycle writer lock. Missing private folders are a normal stopped
state. Unsafe, unreadable or changing records report uncertainty; status does not
change runtime locations to work around a permission error. Lifecycle commands
prepare their private storage when explicitly requested.

### `lixity doctor`

Inspect the installation and owned service without opening a manuscript project:

```sh
lixity doctor
lixity doctor --json --port 9000
```

Since v0.7.4, `doctor` compares the imported CLI version, installed distribution
metadata and a running service's reported version. It reports the module and
interpreter paths, supported JSON contract versions and the shared read-only
service observation. It does not install, repair, restart, create service storage
or read manuscript/project configuration. Version agreement does not establish
that an installation matches an unreleased source checkout.
Use this optional diagnostic when investigating installation/service issues;
ordinary writes and exports use their own validation and revision/context guards.

JSON uses `lixity-doctor/1` with `ok`, `installation`, `service`, `schemas` and
`issues` (each issue has `code` and `severity`). A consistent installation with a
stopped service is healthy and exits 0; reported mismatches or unavailable
metadata/status exit 1. The port uses `--port`, then `LIXITY_PORT`, then 8765.
An out-of-range numeric port or invalid `LIXITY_PORT` returns `ok: false` and
`error: {code: "invalid-service-port", message: ...}` under the same schema, with
exit 1. A non-integer explicit `--port` is a normal argument usage error (exit 2).

### `lixity build`

Create the reproducible artifact set for a project:

```bash
lixity build manuscript.md --dry-run
```

Remove `--dry-run` to write `exports/<slug>_metrics.json` (v2), `_profile.json`
(v2), `_style.json` (v4), `_style_passport.txt` (legacy filename), `_report.md`
and `_dashboard.html`. Identical content causes zero writes. Changed artifacts
get unique timestamped versions and atomically replace stable links or fallback
copies; the last 10 versions per artifact family remain in `exports/archive/`.
A failed replacement preserves the previous stable artifact and reports an error.

An explicit manuscript path wins. Otherwise discovery uses the selected root's
[configured manuscript](#default-manuscript), then tries `<folder>.md`,
then `manuscript.md`/`manuskript.md`, then a sole Markdown file (ignoring
README/AGENTS/LICENSE/NDA). `--dry-run` displays the plan without writing.

### `lixity about` and `lixity completion`

`lixity about --json` describes installed capabilities and thresholds;
`lixity schema` is its JSON metadata alias. Plain `about` gives a terminal summary.
**Since v0.6.0:** `--section languages|features|heuristics|commands|configuration`
returns one section plus version metadata as JSON. See [configuration discovery](#configuration-corpusconfig)
for scope and older-release alternatives. For Bash/Zsh setup, follow
[shell completion](INSTALLATION.md#optional-shell-completion).

<a id="research-search-scopes-since-v1190"></a>
<a id="research-search-scopes"></a>
<a id="claim-chronology-causal-interpretations-and-keyword-citations-since-v300"></a>
<a id="claim-chronology-causal-interpretations-and-keyword-citations"></a>
<a id="zotero-integration-since-v1190"></a>
<a id="zotero-integration"></a>
<a id="research-batch-workflow-and-index-ergonomics-since-v1200"></a>
<a id="research-workflows-and-index-ergonomics"></a>

### `lixity research`

Research is a separate, explicit-project workspace. Its
[usage guide](research/USAGE.md) owns retained source capture, authored records,
lexical search, chronology, citations, Zotero, OCR, backups and archive versions.
Use `lixity research COMMAND --help` for installed arguments/formats and `GET /api`
for a running server's operations. Confirm permission to retain source bytes
before ingesting. Retrieved passages are evidence to review, not accepted claims.

Useful entrypoints: [source/current-record search](research/USAGE.md#search-current-authored-records),
[chronology and causal interpretations](research/USAGE.md#claim-chronology-and-causeeffect-links),
[keyword citations](research/USAGE.md#choose-citations-by-keywords),
[Zotero capture and recovery](research/USAGE.md#zotero-desktop-bridge),
[author revisions and acknowledgements](research/USAGE.md#research-workflows).
Use the same supported application version for every archive writer; product
release numbers, archive versions and response schemas are independent.

<a id="worked-example-a-sequel-in-the-authors-style"></a>
## Literary case study

The [Fontane case study](blog/effi-briest-case-study.html) explores a reference
built from a public-domain novel. Its linked excerpt and complete-book report
have different chapter sets and can have different baselines. These are named
case-study artifacts; the [Warehouse 4 project](demo/report.html) is the product
walkthrough. Matching any reference distribution does not establish literary quality.

## Work markers (editor-visible)

The dashboard (local control server) can set **work markers** directly into
the manuscript: invisible HTML comment lines with stable IDs
(`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed above the target
paragraph. The comments stay out of manuscript prose and PDF text, but exported
HTML dashboards include the marker list and notes. Review those before sharing
a dashboard. Markers move with the paragraph when editing and are idempotent (deterministic
content-hash IDs). Kinds: `pruefen`, `sachcheck`, `todo`, `achtung`. In the
dashboard, clicking a kind opens an inline note field. Type the reason and
choose **Save** or press Enter to commit (the marker is written with `note="…"`);
**Cancel** or Escape discards the note. Failed saves show an error and retain
your text; pending requests disable repeated submission.
Markers can be set from the flagged-passages list (quick `+ To-do` per row)
or from an opened paragraph in the chapter map — both target the exact
source line. Programmatic access: `api.markers(text)`,
`api.add_marker(text, kind, note, line)`, `api.resolve_marker(text,
marker_id)`.

Failed marker saves report an error and preserve the manuscript bytes and
permissions. The interface retains the draft for correction; HTTP details are
in the [automation contract](AGENTS.md).

## Understanding the metrics

Compare scenes or narrative voices using comparable language, passage length,
chapter boundaries and discourse mode. Inspect the prose alongside the values:
a dialogue scene and an expository scene may deliberately differ. Neither
short sentences nor low perception-filter counts establish effective pacing,
immersion or a writing defect. There is no automatic narrator-voice assessment.

| Metric | Definition | Interpretation limits |
| :--- | :--- | :--- |
| **ASL** | average sentence length in words | describes length, not syntactic complexity or dramatic pace by itself |
| **Median / σ** | middle sentence length and spread | a low median with high σ means short base plus bursts |
| **TTR** | type-token ratio V/N | sensitive to length, topic and tokenization; no universal novel target |
| **Guiraud R** | V / √N | remains length-dependent; compare with sampling and corpus context |
| **Yule's K** | vocabulary repetition measure | repetition does not establish a stable narrator or a quality verdict |
| **ASW** | average syllables per word | a language-dependent heuristic input to readability formulas |
| **MTLD** | mean segment length until TTR ≤ 0.72 (forward/backward averaged) | larger values mean longer diverse segments; requires ≥ 100 tokens |
| **MATTR** | moving-average TTR over a 50-token window | describes local repetition; compare the same window and tokenization |
| **Maas a²** | (log₁₀ N − log₁₀ V) / (log₁₀ N)² | requires ≥ 100 tokens; lower means more types at the same N, not better prose |
| **Flesch** | language-calibrated Flesch family (Amstad for German) | formula output is not clipped to 0–100; not reader comprehension |
| **LIX** | ASL + share of long words (Björnsson: more than six characters, all languages) | a surface-structure estimate, not a universal difficulty or quality threshold |
| **Quoted words** | share of configured word tokens inside detected quotations | quotation and token regexes affect counts; neither speaker attribution nor dialogue classification |
| **Function words** | share of articles, pronouns, prepositions, conjunctions, particles, auxiliaries, modals | language-profile counts describe grammatical patterns, not artistic value |
| **Perception filters** | curated word-pattern matches (e.g. German "hörte", "roch", "fühlte") | lexical cues include environmental descriptions and idioms; they do not classify narrator mediation or narrative distance |
| **Sentence classes** | staccato ≤ 6, medium 7–15, long 16–25, very long > 25 words | length bins; the legacy `complex_*` keys do not establish syntactic nesting |
| **Tense severity** | 0 = neutral, 1 = watch, 2 = conspicuous, 3 = strong friction | flags switches and mixtures for review |

The 100-token minimum is a local short-text policy, not a reliability guarantee.
Maas is valid for a one-type text: 100 repetitions produce `maas_a2=0.5`.
Unavailable estimates are `null` in JSON and shown as `–` in the dashboard;
legacy zero values on empty input must not be interpreted as measured quality.

Use actual JSON fields when automating: corpus metrics have `asl`,
`dialog_ratio`, `filter_density` and `nominalization_density`; chapter metrics
use `asl`, `dialog_pct`, `filter_density` and `nominalization_density`.
The style passport stores these feature identifiers in `features[].feature`
and its deviation/FDR entries. Display keys such as `feat_asl` and `feat_dialog`
belong to localized labels, not callable API functions or result fields.

<a id="unavailable-consistency-and-empty-manuscripts-since-v1180"></a>

### Unavailable consistency and empty manuscripts

Dashboard/text reports show `–` without measurable chapter–feature cells.
Empty chapters contribute no measurements; one chapter or fewer than configured
`min_chapters` is insufficient for a baseline. Style JSON v4 reports
`measured_cells`: when zero, legacy `consistency: 1.0` is an unavailable sentinel,
not 100%. Otherwise consistency counts cells with `abs(z*) < z_mild`, not whole
chapters. See [interpretation](guides/interpretation.html) for short-text limits.

## Manuscript format & how to operate lixity

**Format (Markdown, UTF-8):**

- **Chapters** are level-2 headings: `## Title`. Everything before the first
  `##` is front matter and is not analysed when chapter headings exist. Without
  chapter headings, all prose is measured as one chapter. The boundary regex is
  configurable (`CorpusConfig.chapter_regex`).
- **Appendix** starts at `## Anmerkungen und Literaturverzeichnis`
  (`CorpusConfig.appendix_marker`); it is excluded from prose metrics.
- **Paragraphs** are separated by blank lines. Hard line breaks inside a
  paragraph are joined automatically – no manual reformatting needed.
- **Dialogue** in typographic quotes (`»…«`, `„…“`, `“…”`) feeds the dialogue
  ratio.
- **Work markers** are invisible HTML comments
  (`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed directly above the
  paragraph. HTML dashboards include their notes; prose/PDF text omits the
  comments. They move with the paragraph when editing. Other HTML comments are
  ignored by the analysis.
- Explicit project title/metadata can supply the title; filenames remain the
  artifact naming basis.

For review, use [chapter measurements](#style-area) or a paragraph's measurement
explanation, then read the passage against its intended purpose. A highlighted
value is not an editing instruction.

Line anchors in reports and dashboards refer to lines in the source file, so
findings stay navigable in the editor.
**Since v0.7.1:** shared counting excludes inline code, images and
Markdown link destinations while retaining visible link labels. This measurement
projection does not change displayed paragraph text, saved quote identities or
chapter numbering; a chapter without countable prose still retains its number.

## Known limitations & stability

[Methods](METHODS.md) documents estimator conventions;
[Stability](STABILITY.md) records evidence and inference limits.

- Minimum sizes (HD-D/MTLD/Maas ≥100 tokens; MATTR ≥50) are availability
  floors, not reliability guarantees. Short inputs can yield unstable values.
- Syllable, suffix and tense patterns are language-specific heuristics without
  established gold-standard error rates here; cross-language comparisons need
  separate justification. Curated filter-verb counts differ from broader
  editorial definitions.
- `signal_counts` is empty unless project `signal_keywords` supplies thematic
  patterns. Vocabulary/JSD contrasts are in-corpus diagnostics, without external
  Delta authorship attribution or automatic narrator-voice assessment.
- Research source analysis is `source_internal`; explicit source–manuscript
  comparisons remain separate. Retained sources never become the manuscript's
  baseline automatically. Period/place/genre labels are unverified context.
- Determinism is byte-identical on the same interpreter; Python versions may
  differ in the final floating-point bits. Offline dashboard size grows with
  embedded text/data even though paragraphs are rendered on demand.
- Numeric details and keyboard/touch controls complement color scales, but
  pointer-operated canvas points and automated checks do not establish full
  accessibility conformance.

<a id="ai-agent-interface"></a>

## Library

### High-Level API Facade (`lixity.api`)

Use the deterministic facade for scripting. This example selects English and
explicit code defaults instead of discovering unrelated project configuration:

```python
from pathlib import Path
from lixity import api

text = Path("manuscript.md").read_text(encoding="utf-8")
metrics = api.analyze(text, language="en")["metrics"]
reference = api.fingerprint(text, language="en", project_config={})
html = api.dashboard(text, language="en", title="Example", project_config={})
Path("dashboard.html").write_text(html, encoding="utf-8")
```

Each convenience call analyzes independently. To reuse one analysis across
several outputs or integrate multiple projects, use the
[shared pipeline and configuration guidance](ARCHITECTURE.md#configuration-and-multiple-projects).
[Automation contracts](AGENTS.md) describe facade inputs, envelopes and marker
operations; `api.about()` returns runtime capability metadata.

### Low-Level Classes

Use `CorpusAnalyzer`, `CorpusConfig`, `ParagraphProfiler` and renderers for direct
object-model control; the [architecture reference](ARCHITECTURE.md) explains
these boundaries. Low-level structure reports also default to English when no
configuration is supplied. Automatic language detection is explicit and needs a text sample:
`resolve_language(CorpusConfig(language="auto"), sample_text=text)`.
Without a sample, `auto` resolves to `generic`; the CLI supplies its manuscript
automatically. `FileUtils.atomic_write_if_changed(path, text)` provides atomic,
idempotent output writes.

## Configuration (`CorpusConfig`)

Legacy CLI commands with an explicit manuscript path load settings relative to
that manuscript; otherwise workspace discovery starts in the current directory.
The `--project` and configured-omission modes added in v0.7.3 instead use strict
settings from the selected root; see [default manuscript](#default-manuscript).
Project settings live in `lixity.toml` or `[tool.lixity]` in `pyproject.toml`.
An explicit CLI option overrides its project value. Configured title affects
dashboard/build presentation; artifact names still follow the manuscript name.

Use `--min-chapters` on style/dashboard/build or server startup, or
`api.fingerprint(..., min_chapters=4)`, to require more usable chapters before a
style baseline is available. The minimum is 2; fewer usable chapters mean
unavailable evidence, not a perfectly consistent style.

For API project isolation, pass `project_config={}` to `profile`, `fingerprint`,
`passport` or `dashboard` to avoid implicit threshold lookup. A supplied mapping
provides thresholds and known `CorpusConfig` fields; explicit options win.
Language and title remain explicit API arguments. See
[configuration precedence](ARCHITECTURE.md#configuration-and-multiple-projects).

In the native workspace, **Apply** persists title, `author_name`, publication
and chapter register settings in the selected project's `lixity.toml`; language
and detection thresholds keep session behavior by default. Author/publication identity
comes only from the explicit selected root, excluding user/ancestor defaults.
Empty author clears it. Failed validation or saves keep previous metadata and
the active view; failed submissions retain the draft. Reload after a project or
root-config change instead of submitting stale values. An optimistic conflict
guard rejects observed concurrent changes; it is not an external-editor lock.

**Since v0.6.0:** check **Save analysis defaults for this project**
before **Apply** to persist the posted language and detection thresholds in that
project's `lixity.toml`. It starts unchecked and requires the current selected
project context. Unposted settings stay unchanged; `auto` remains an explicit
saved choice. The same transaction saves metadata and defaults together or neither.

The identity check compares configured title/author with explicit manuscript
metadata: flat leading YAML strings or a leading Markdown title page with
`by`, `von`, `Author:` or `Autor:`. It normalizes Unicode/whitespace and reports
missing, unsupported and unavailable evidence separately from a mismatch. A
missing manuscript value means it was not automatically detected in these
formats, not that the project setting is empty. The optional comparison does
not infer authorship or edit the manuscript. A display byline does not
identify a publisher or printer.

An existing unreadable/malformed config emits a warning naming the file and
ignores those settings. This includes non-table `tool`/`tool.lixity` sections in
`pyproject.toml` and failed permission/I/O checks while locating a config. Missing
files and paths that cannot exist beneath a file are silent. Check `meta.language`
and active thresholds after a warning, or supply explicit options. Invalid stored
publication fields remain visible for correction while analysis stays available.

**Since v0.6.0:** discover configuration keys, defaults and
constraints with:

```bash
lixity schema --section configuration
```

The `configuration` object (`lixity-configuration/1`) reports accepted keys,
project-only keys, uninterpreted keys, native-settings persistence/session scope,
and component schemas for corpus, threshold and publication settings. v0.7.1
also exposes the owning character-profile schema. Defaults
are annotations, not active project/server values. Scene and NDA settings retain
their owning component's validation; this is not a
single complete project-file schema. Threshold comments also state finite-number
requirements and `z_mild <= z_strong`, validated by the backend.

Older releases provide `lixity about --json` and `lixity COMMAND --help`; Python
callers can inspect `CorpusConfig.model_json_schema()` for corpus fields. Optional
`None` linguistic patterns use the selected language profile's defaults.
`phrases` and `capabilities` are accepted but uninterpreted by the bundled engine.

### Default manuscript

In the selected project's root `lixity.toml`, set an optional relative path:

```toml
manuscript = "drafts/manuscript.md"
```

The equivalent is `manuscript` under `[tool.lixity]` in the root
`pyproject.toml`; root `lixity.toml` takes precedence. This is project data, never
inherited from user settings or an ancestor directory. Paths are relative to the
selected root, may contain spaces and must remain inside it, including symlinks.
Absolute paths and parent traversal are rejected. An explicit manuscript argument
wins. When selecting a configured default, an invalid/unreadable configuration
or missing/nonregular configured file fails selection instead of choosing another
manuscript. Explicit-file analysis retains its existing configuration warnings.

The published v0.7.2 release uses this setting for folder selection (Open
Project, service startup and `build`), omitted `scenes` input and read-only
Research manuscript review. Text-taking Python APIs do not discover files.

**Since v0.7.3:** all manuscript analysis/export commands accept
`--project PATH`: `analyze`, `profile`, `dialogue`, `pacing`, `showing`, `style`,
`motifs`, `characters`, `dashboard`, `pdf`, `scenes` and `build`. With no file,
these commands use the selected root's configured manuscript. Only `scenes` and
`build` retain their existing conventional-file discovery when no default is set.

```bash
lixity analyze --project ./novel
lixity scenes --project ./novel --latest
lixity research review-manuscript --project ./novel
```

New explicit-project/configured-omission analysis reads settings only from that
root, excluding user and ancestor defaults. Language, title and registers belong
to the same root even when its manuscript is nested. Explicit CLI options win.
With `--project`, relative files belong to that root and absolute files must
also remain inside it. Without this option, an explicit file retains legacy
path/configuration behavior. Conventional discovery by `scenes`/`build` without
`--project` also retains its existing settings merge. Commands do not select
another running server's project. Project build exports and default PDF output belong to the
selected workspace root.

Research `review-manuscript`, `find-anchor`, `link-manuscript`,
`unlink-manuscript`, `reconcile-manuscript` and `compare` can reuse the validated
Research project's root-local default. They do not guess from other Markdown
files. Existing positional/option forms, acceptance, retention and snapshot
requirements remain. Read-only review retains informative `missing`/`unreadable`
source states. See the [research reference](research/USAGE.md).

### Character profiles

**Since v0.7.1:** define literal aliases and optional author-declared
viewpoint chapters in the selected project's configuration:

```toml
[characters.Alex]
aliases = ["Alexander", "A. Rivers"]
pov_in_chapters = [1, 3]
```

The profile name is also matched. Aliases are literal text, unlike legacy `names`
and explicit `--name` regular-expression patterns. Explicit name selections win;
an existing `characters` table, even empty, replaces legacy `names`. Profiles come
only from the explicit project root, not user/ancestor defaults. The CLI and
dashboard share this resolver; Python accepts explicit `project_config`.

Declared viewpoint appears separately as `declared_pov_chapters`; it does not
increase mention counts or fill mention gaps. Chapter numbers must exist in the
current manuscript. No pronoun resolution, narrator inference or named-entity
recognition is performed. Use configuration discovery for accepted fields and bounds.

For an existing adapter that keeps its own figure list, move the reviewed names
into `[characters]` profiles, then omit explicit `--name`/`--names` selections
when calling `lixity characters --project ./novel`. Pass the same root-local
settings as `project_config` to Python APIs; an explicit adapter name list still
overrides the profiles. Review literal aliases rather than mechanically copying
regex syntax, and never use a pronoun such as `I` as an alias for a viewpoint.
Verify the resulting mentions and declared POV separately. This does not edit
the manuscript or infer character presence.

### Chapter register settings

In the native workspace, **Project → Settings → Chapter registers** edits named
registers, optional feature bounds and chapter assignments. Since v0.7.4,
feature choices and target rows show the shared units, including per-1,000-word
densities and HD-D's 0–1 scale. Scene groups remain configured separately in
`scene_analysis`; the style-table display filters do not change the whole-book
reference. **Apply** validates,
rebuilds and saves both tables together in the selected project's `lixity.toml`.
It requires the current project token and preserves newer browser drafts during
pending saves. Resetting detection thresholds does not reset registers.

```toml
[register_profiles.formal]
asl = [15, 35]
passive_density = { lower = 5 }

[chapter_registers]
"2" = "formal"
```

A range may be `[lower, upper]`, a scalar exact target, or a table with `lower`
and/or `upper`. Omit one table bound for an open interval (TOML has no `null`).
Empty profiles label intentional registers without targets. Names must be
nonempty single-line text of at most 100 characters; unknown profiles/features, invalid bounds
and unmatched chapter selectors fail explicitly. Numeric selectors match exactly
one chapter. Otherwise full titles take precedence, then the longest matching
partial title, with lexical order breaking equal-length ties. Number assignments
take precedence over title assignments.

The report lists each target's measured value and `below`, `within`, `above` or
`unavailable` position. The usual chapter measurement floors still apply.
Register assignment expresses author intent; it is not evidence of a stylistic
or factual defect. Scene registers remain separately configured through the
existing `scene_analysis` settings.

### Local repetition echoes

Since v0.7.4, human `lixity motifs FILE` output and the analysis overview also
show **Local phrase echoes**, including local count, chapter and inclusive
chapter-prose word bounds. These remain separate from whole-book repeated phrase
counts. The overview links to the chapter, not an invented exact line anchor.

`lixity motifs FILE --json` and `api.motifs` add `echoes` alongside repeated
phrases and content-word counts. Each echo contains `term`, `chapter`, `count`,
`first_word` and `last_word`. The detector retains the densest local cluster per
term/chapter (earliest tie); its default span is 300 words and its default minimum
is two occurrences. Word offsets are 1-based chapter-prose token positions,
including the final token of the last occurrence. Shifted n-grams are deduplicated
when their recorded occurrences overlap by at least two tokens in the same
repeated passage; independent phrases sharing words remain separate.

These are lexical review hints: punctuation is discarded during tokenization,
and deliberate repetition is not an error. `echo_window`, `echo_min_count` and
`top_echoes` are keyword arguments of `lixity.motifs.motif_report`; they are not
CLI flags or project configuration keys.

### Publication settings

In the native workspace, open **Project → Settings → A5 book PDF details**. The
disclosure is collapsed initially and disabled without an explicit project.
The inclusion checkbox controls the A5 `book` layout; sheets and analysis
reports omit the imprint. All text fields are optional and empty by default.
Only entered nonempty text is emitted: an enabled, entirely empty configuration
adds no blank imprint page. A single imprint section starts after the title
page; long addresses or credits can flow onto additional pages.

The same fields can be entered in the selected root's `lixity.toml`:

```toml
title = "Example manuscript"
author_name = "Example Writer"

[publication]
enabled = true
publisher_name = "Example Press"
publisher_address = "Example Street 1\nExample Town"
```

These example identities are synthetic. Enter confirmed information for your
own project; Lixity does not derive it from prose, a pen name or a project path.

**Since v0.6.0:** `configuration.publication_schema` in the
[installed configuration metadata](#configuration-corpusconfig) supplies keys,
defaults, text bounds and validation notes from the shared model/field registry.
Its extension annotations describe checks beyond ordinary JSON Schema.

Validation does not verify assigned ISBNs, addresses, rights ownership or legal
completeness. No copyright statement or Deutsche Nationalbibliothek catalog claim
is generated automatically.

#### Germany: print and digital publication

For printed works, imprint requirements depend on the applicable Bundesland.
For example, Bavaria and North Rhine-Westphalia require printer and publisher
names or registered business names and addresses; self-publishing identifies
the author or editor in the publisher role. Enter that identity explicitly,
independently of a display pen name. See [BayPrG Article 7](https://www.gesetze-bayern.de/Content/Document/BayPrG-7)
and [NRW Landespressegesetz § 8](https://recht.nrw.de/lrgv/gesetz/18052021-pressegesetz-fuer-das-land-nordrhein-westfalen-landespressegesetz-nrw/).

Digital provider/website duties are separate from a printed-book imprint.
[MStV § 18](https://www.gesetze-bayern.de/Content/Document/MStV-18) requires
provider name/address information for telemedia beyond purely personal or family
purposes. [DDG § 5](https://www.gesetze-im-internet.de/ddg/__5.html) adds contact
and applicable business disclosures for businesslike digital services normally
offered for payment. Check the actual provider and distribution channel; these
rules do not mean every ebook must contain every website-imprint field. Lixity's
entered publication data does not validate or publish a website imprint.

An ISBN is voluntary. When ISBNs are used, separately available formats such as
print, PDF and EPUB use distinct identifiers; a single digital field describes
only the selected digital edition. See the [German ISBN agency FAQ](https://german-isbn.de/faq/faq-isbn).
Copyright protection generally arises without registration or a notice; an
optional entered rights notice does not establish ownership. See [WIPO's copyright FAQ](https://www.wipo.int/en/web/copyright/faq-copyright).
Legal deposit of print and digital publications is a separate process; saving
metadata or generating a PDF performs no deposit. See [DNBG § 14](https://www.gesetze-im-internet.de/dnbg/__14.html).

The BFSG covers consumer e-book services provided after 28 June 2025. Scope and
exceptions matter, including the microenterprise exemption for services under
§ 3(3). See [BFSG § 1](https://www.gesetze-im-internet.de/bfsg/__1.html)
and [§ 3](https://www.gesetze-im-internet.de/bfsg/__3.html).
Lixity exports A4 document/editorial/sheet/report and A5 book PDFs. These
fixed layouts do not include EPUB, DOCX, custom trim sizes or certified PDF/UA/PDF/X files;
an imprint, searchable text or bookmarks do not establish BFSG compliance.

### Project NDA configuration (`[nda]`)

The [five-field generator](#nda-agreements) works without configuring a store.
Optional project settings select a document language or text model:

```toml
[nda]
# language = "de"                    # optional explicit language override
# template = "agreements/nda.txt"     # optional project-owned UTF-8 model
```

`language` takes precedence over the resolved server/project language, then
project configuration and English. Supported codes are `en`, `de`, `fr`, `es`,
`it`, `pt` and `nl`. `template` must be nonempty UTF-8 text inside the project,
at most 2 MiB; paths and symlinks escaping the project are rejected.

The literal placeholders are `{{recipient_name}}`, `{{recipient_address}}`,
`{{project_title}}`, `{{date}}`, `{{place}}` and optional `{{project_author}}`.
The project author comes from the project-wide `author_name` setting. Existing
five-field models remain supported. Unknown fields are rejected;
supplied values remain literal data. Generation and downloads are described
[below](#nda-agreements).

## NDA agreements

Under **Project**, enter the recipient's name, optional **Address**, **Project
name**, **Date** and **Place**. A real loaded project name can be prefilled;
an empty workspace leaves it blank. The date defaults to the browser's local
calendar day. Choose **Preview** to read the full friendly agreement, then
**Download PDF** or **Download text**. The address may span several lines.
The output is titled **Confidentiality agreement**. It offers the recipient a
signature line or a clear consent in text form, for example a reply to the email
that delivered the document; the sending project representative needs no separate
handwritten signature on this sent copy. Review the details together before
consenting; generating or downloading a file records no consent and no signature.
The representative's name is filled from **Author name** in project Settings.
The five NDA input fields remain unchanged. Without a configured author, the
download keeps a blank name line for manual completion.

The native generator uses the resolved project language or the optional
`nda.language` override. Seven localized text models are available. Preview
shows text literally, and the browser downloads a paginated PDF or editable
UTF-8 text. The request returns the document directly; generation creates no
server files or recipient registry. Details remain in the current form for a
retry and are not saved across reloads. JavaScript and a compatible live server
are required for the form; standalone analysis HTML has no NDA controls.

Native PDF text is limited to Windows-1252 Western Latin characters. If a name
or other value requires a broader repertoire, download UTF-8 text and render it
with your local document editor. Keep reviewed and signed copies in your own
project storage. Language selection does not choose a law or jurisdiction.

The wording is editable to fit the project. Language selection and filled fields
do not establish universal enforceability.
For trade-secret rules and disclosure exceptions, see
[§5 GeschGehG](https://www.gesetze-im-internet.de/geschgehg/__5.html) and
[Directive (EU) 2016/943](https://eur-lex.europa.eu/eli/dir/2016/943/oj/eng).
[WIPO's trade-secret overview](https://www.wipo.int/en/web/trade-secrets) provides
broader background. These references do not validate a particular agreement.

## Troubleshooting

| Symptom | Cause and fix |
| :--- | :--- |
| `FileNotFoundError` / `No such file` | Path or working directory is wrong; quote paths containing spaces. |
| All paragraphs are `Neutral`, no tense colours | The language profile does not match the text, or the text is too short. Force the language with `--language de` (or the correct code). |
| Metrics look wrong / appendix counted as prose | Check the `appendix_marker`; the default expects `## Anmerkungen und Literaturverzeichnis`. |
| Dashboard looks unchanged after editing | Expected when the prose did not change (idempotent writes). Check the file mtime, or compare with a fresh `-o` target. |
| `lixity: command not found` | The install did not land on `PATH`; use `.venv/bin/lixity` or reinstall the package. |

<a id="debug-logging-since-v1190"></a>

### Debug logging

Start with `lixity serve /absolute/path/to/project --debug` or `LIXITY_DEBUG=1`
(`true`/`yes` also work). This enables backend request logging and a browser
debug default. Browser-console `setLixityDebug(true)`/`false` saves an explicit
choice across reloads when local storage works; remove `lixity_debug` to restore
the server/window default. With blocked storage, the choice lasts for the page.
It does not change backend logging; restart with the intended server setting.

Warnings/errors still log. API diagnostics show method, URL, status and duration
without copying response bodies. Backend debug lines carry UTC timestamps;
browser diagnostics do not. Logs may contain source text or paths, so review
before sharing.

## Development

Use [CONTRIBUTING.md](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md)
for checkout setup, supported checks, browser suites and documentation generation.
`make help` lists the maintained entrypoints.

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) – see [`LICENSE`](https://github.com/mfahsold/lixity/blob/main/LICENSE).
Commercial licensing on request: mfahsold@googlemail.com.


### Check a reading website before exporting

**Since v0.7.6:** prepare and inspect the actual package without
writing an output directory:

```sh
lixity export-site --project ./novel --preflight --json
lixity export-site --project ./novel --mode reader --publication-profile readers --preflight
```

Do not supply `--output` with `--preflight`. The native **Reading website** dialog
has the same explicit **Check export** action. It neither downloads nor publishes;
changing the selection clears the displayed result. Preparation uses the same
scope, project guards and limits as export and can take comparable time/memory.
An invalid selection or an unreadable selected asset fails explicitly rather
than returning an invented size.

`lixity-site-preflight/1` measures actual `html_bytes`, `total_bytes`, `zip_bytes`,
`source_file_bytes` and `file_count` for the prepared candidate. Counts cover
exactly the exported dossier revisions (including earlier revisions in review
mode), or selected publication entries after the chapter cap. Available retained
media without copied source files is reported as `not_packaged`, separately from
unavailable pins. Ordinary Markdown image destinations are counted as unchecked;
no loose file or external URL is opened. Attribution checks only the presence of
`origin_url` and `provenance_note` in retained source metadata, not license validity
or whether a reader-visible credit appears in the exported page. External link auditing
and mobile rendering are not performed: `mobile_layout_check` is `not_run` and
`rights_check` is `not_performed`.

Warnings advise on HTML over 10 MiB or ZIP over 20 MiB; these are disclosed
practical thresholds, not performance guarantees. The result describes this
candidate, not a reserved later export. Curated reader/companion modes often
avoid exporting internal review history; choose the appropriate saved profile
and retained-file options deliberately. No automatic image recompression or
promise of a package under 20 MiB is introduced here.

**Since v0.7.6:** export data, revision-count and bundle limits stop the check
with exit code 1. With
`--json`, stdout still contains a parseable `lixity-site-preflight-error/1`
report identifying the limit, observed bytes/count, allowed amount and overflow.
Response-budget failures identify the route and affected record parameters, with
accepted bytes grouped by route; operational tokens and source prose are omitted.
This is the first limit crossing, not a full package-size estimate: `complete`
is false and no output is written. The 64 MiB data and 200 MiB bundle limits
remain in force. Suggestions follow the limiting category: prepared research
responses can exceed their budget without original source files. Omitting
`--include-source-files` is relevant to the separate bundle budget, not a general
repair for large record/history responses. Select a narrower publication scope
rather than deleting project records to make an export fit.
