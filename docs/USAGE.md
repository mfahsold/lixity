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
| Where does the tense slip? | `lixity profile` | per paragraph: dominant tense, mix, switch, severity 0–3 |
| Is this chapter still *this book's* style? | `lixity style` | median/MAD bands, z\*, FDR set, style dimensions |
| How is the dialogue structured? | `lixity dialogue` | turns, turn lengths, turns per 1,000 words, dialogue paragraphs |
| Who appears where — and when not? | `lixity characters` | mentions, chapters present, span, longest gap |
| Where are the scenes and hooks? | `lixity pacing` | scenes, scene length, ASL curve, hook score 0–3 |
| What repeats itself? | `lixity motifs` | motif presence, top content words, repeated n-grams |
| Which chapters *tell* instead of *show*? | `lixity showing` | tell/show z, balance per chapter (self-calibrating) |
| I want to see and click all of it | `lixity dashboard` | single-file HTML, all panels, offline |
| I want a foreground server for development or integration | `lixity serve` | loopback HTTP server, live settings, manuscript upload, research panel |
| I want to start or manage the installed app | `lixity service` | managed start, stop, restart and status without a source checkout |
| I want to manage and cite research sources | `lixity research` | immutable archives, citations, dossiers, manuscript grounding |
| I want a printable report or reading copy | `lixity pdf` | A4 report, A5 book layout, 30×60 sheet |
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

<a id="download-a-manuscript-pdf-since-v240"></a>

### Download a manuscript PDF

Open **Project actions → PDF export**, choose a layout, then
**Download PDF**. Since v0.7.0, **A4 editorial copy** is the initial choice;
**A5 reading copy**, **A4 manuscript sheets** and **A4 analysis report** are also available.
Changing the layout alone does not generate a file. The download uses the same
composer and project metadata as [`lixity pdf`](#lixity-pdf), returning bytes
directly without creating server export files. Reload after switching projects
or externally changing root configuration; stale export context is rejected.
JavaScript and a compatible native server are required.

<a id="start-a-review-since-v230"></a>

### Start a review

In the interactive workspace, the **Analysis** switch has a visible
On/Off state while the manuscript remains continuous. Showing diagnostics keeps
the prose width and navigation choice; it does not open a context tool. An
analyzed paragraph's **Values** opens the **Passage values** inspector independently
of the Analysis On/Off choice. **Analysis overview** opens chapter comparisons and other dense views;
**Back to passage** restores the earlier analysis choice and document context.

**Start your review → Open passage** opens the first paragraph meeting the
selected tense threshold, otherwise the opening paragraph, clearing filters and
focusing the passage. **Explore chapters** opens available chapter comparisons;
**Open sentence rhythm** appears when measurable. Other passage/chapter links
navigate to the corresponding prose. These are review locations, not rankings
or instructions to revise.

**On current main (Unreleased):** the overview keeps these review routes,
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

**On current main (Unreleased):** the workspace switcher comes before project
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

A saved association's **Open claim** shows the recorded claim revision. Its
dossier reference opens the recorded dossier version; choose newer history
explicitly when needed. Claim and dossier views can open their saved manuscript
associations in Review. Only an exactly resolved current passage offers a direct
jump; moved, changed, ambiguous and unavailable anchors retain their review state.

**On current main (Unreleased):** choose a paragraph's **… → Saved research**,
its saved-association count or a marked saved quotation to read its context
beside the manuscript. The context shows up to five exact saved associations,
with their total, pinned claim and dossier versions and author-assigned confidence.
Associated decisions are labelled **current dossier context**; they do not
reconstruct the historical state of the saved quotation. Each title opens its
displayed version in the existing record viewer. **Review** remains a separate
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

**On current main (Unreleased):** leaving an open dossier for its saved
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

Choose a chapter in the reader toolbar. **Reading settings** groups **A−**/**A+**
for text size (16–28 nominal pixels), narrow/standard/wide text and
compact/standard/relaxed line spacing. Appearance and the desktop split are local
browser preferences; display changes do not edit the source.

**On current main (Unreleased):** **Reading settings → Keyboard shortcuts**
lists the passage menu, search and close keys. Hovering or focusing key controls
also gives a short explanation; Escape dismisses a tooltip. Essential actions
remain labeled and work without hovering. In manuscript search, `Enter` selects
the next match, `Shift+Enter` selects the previous match and Escape clears the
query. These keys apply in the search field, not throughout the application.
Passage jumps wait for their scrolling area to settle before a brief destination
cue; reduced-motion preferences keep navigation immediate.

Each analyzed paragraph has an **…** button. It opens the same contextual tools as a
right-click on the prose or `Shift+F10`/the context-menu key while the paragraph
or its button has focus. Arrow keys move through the menu; `Home`/`End` reach its
first/last action. Escape closes it and restores focus. Actions depend on the
available capabilities: **Values**, work markers, **Link selection to claim**
for a valid selection, and the companion dossier. A selection within one paragraph
also offers a compact toolbar. Marker notes and claim associations still require
their existing explicit save and retention steps.
Use Shift+right-click to open the browser's native context menu instead.

**Values** opens **Passage values** with the selected paragraph's chapter, source
lines, tense and style measurements in the closable context area. Opening or
closing it leaves the global Analysis choice unchanged; turning Analysis Off
keeps the inspector available. In v0.7.2, **Saved manuscript associations** opens
the quote review for that paragraph. On current main, this entry and **Saved
research** open the passage's saved context alongside; its **Review** action opens
the dedicated quote review. Switch between passage values, saved research and
the saved dossier explicitly; closing the tool does not turn all
analysis off. On desktop, tools occupy adjacent space. On mobile, an explicit
paragraph-to-tool action reveals the stacked tool heading; closing it or pressing
Escape returns to the requesting passage and its paragraph control.
**Focus reading** temporarily hides surrounding navigation and
tools; its visible exit or Escape restores the workspace. Opening a tool exits
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

On current main, empty source and dossier collections omit their unused filter.
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

**On current main (Unreleased):** the chapter matrix shows `0` when a style
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

The matrix color scale stays fixed at z* = −2.5 to +2.5. A **●** marks an
FDR-selected cell; color alone is not a significance decision. Cell details
include raw values, z*, standardized effect and Cliff's δ. The style reference
shows the manuscript median ± 2 robust standard deviations, with sample counts.
Its cutoff-hit counts differ from FDR decisions; the bands are neither
confidence intervals nor external editorial targets. Paragraph style layers
show measured values and flag unusual values relative to the chapter.

**On current main (Unreleased):** with **Analysis On**, select one metric in
**Deviations**. A transparent background and up/down arrow on a notable paragraph
refer to that chapter's median/MAD, not literary quality. The paragraph button
explains its raw value, unit, source lines and local z; choose **Values** for the
measurements. **Next deviation** opens the paragraph, and **Clear metric** removes
only this metric. Analysis Off hides the paint and related hints while retaining
your choice. Native text selection, search and saved research marks remain separate.

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

### `lixity profile`

Locate paragraph-level tense mixtures, switches and style densities with
source line anchors:

```bash
lixity profile manuscript.md > profile.json
```

This command emits JSON. Language-neutral `dominant` values (`present`, `past`,
`mixed`, `neutral`) become localized labels in reports. Tense classification
counts curated verb forms: `mixed` requires at least two markers per tense and
at least 25% minority share. `switch` compares consecutive dominant tenses;
severity 0–3 prioritizes review. See the [classification contract](AGENTS.md)
for the truth table and direct-library threshold controls.

Densities are counts per 1,000 words, not percentages; short paragraphs can have
large values from few matches. Nominalization suffix cues exclude curated
function words unless a project regex override is supplied. They remain
heuristics rather than a grammatical parse.

**On current main (Unreleased):** inspect the same selected paragraph metric
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
separate from rows shown. Configured manuscript omission follows the existing
[project resolver](#default-manuscript). Without `--layer`, profile retains its
existing JSON v2 output, including when `--json` is omitted.

With `--layer --json`, the opt-in envelope is `paragraph-layer/1`; unavailable
comparisons have `z: null` and `notable: null`, while measured zero remains zero.
Densities remain word-pattern counts per 1,000 words, not exact token spans or a
grammatical interpretation. See [the contract](AGENTS.md#311-opt-in-paragraph-layers).

### `lixity dialogue`

Inspect quoted-speech segments, their lengths and chapter distribution:

```bash
lixity dialogue manuscript.md
```

A turn is a quotation segment, without speaker attribution. A dialogue paragraph
has at least half its words inside detected quotations. `--json` returns these
summary and per-chapter measurements for automation.

**On current main (Unreleased):** the browser dialogue chart retains every
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

**On current main (Unreleased):** the pacing panel labels average sentence length
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

**On current main (Unreleased):** the scene comparison table stays visible in a
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

Telling signals are perception filters, modals, passive constructions and
nominalizations per 1,000 words; showing signals are dialogue and staccato
percentages. Robust chapter z-scores yield `balance = show_z − tell_z`.
A positive balance means more showing signals than usual for this manuscript;
it does not establish a better scene. Zero MAD falls back to standard deviation.

Comparison needs at least three chapters with differing signals. Otherwise the
app shows `–` and explains the missing support while retaining raw measurements.
For compatibility, JSON component z-scores fall back to zero with too few
chapters; identical balances yield empty `most_telling`/`most_showing` ranks.
Empty ranks mean no distinguishable ordering, not identical artistic effect.

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
```

| Layout | Page | Purpose |
| :--- | :--- | :--- |
| `editor` (since v0.7.0) | A4 | Editorial reading with line numbers and room for comments |
| `report` | A4 | Analysis report with cover page and repeated table headers |
| `book` | A5 | Continuous reading with serif text, mirrored margins and chapter openings |
| `sheet` | A4 | Submission grid, at most 30 lines per page and 60 characters per line |

Output defaults beside the manuscript; `-o` selects another path. Unchanged input,
settings and fonts produce identical output. The manuscript is not modified.
The [native download form](#download-a-manuscript-pdf) uses the same composer
without writing a CLI output path.

Title selection prefers an explicit override, the selected project's title,
supported manuscript title metadata/heading, then the filename. Fenced code is
not a title candidate. `--author` overrides project `author_name`; an explicitly
empty value clears the byline. PDF metadata includes title/author when present
and the resolved language. A5 has chapter bookmarks and body-page title/author
headers; title/imprint pages omit decorations but count toward physical folios.
A4 headers and current/total page footers sit outside the prose/grid area.
The optional `draft_notice` project setting (or `--draft-notice` override) adds
a running-header notice in every layout; an empty override clears it. See
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
Inline emphasis uses font styles; notes are collected as endnotes. Embedded
LaTeX text formatting is a bounded subset, never executed as TeX. Unsupported
TeX constructs report an error rather than silently changing the manuscript.
Compare the same six-chapter *The Crate at Warehouse 4* manuscript as an
[editorial copy](demo/warehouse-4-editor.pdf),
[reading copy](demo/warehouse-4-book.pdf),
[submission grid](demo/warehouse-4-sheet.pdf) or
[analysis report](demo/warehouse-4-report.pdf).

The composer wraps paragraphs and overlong words but does not hyphenate, place
images, typeset mathematics, create page-numbered tables of contents or alternate
recto/verso running heads. Image references remain labelled text. See
[Architecture](ARCHITECTURE.md) for the shared composition boundary.

These fixed-layout PDFs are for editing, analysis, reading and submission. There is no
EPUB export, bleed/crop marks, print color management, printer preflight or
PDF/UA/PDF/X certification. Searchable text, metadata and bookmarks alone do
not establish accessibility or production compliance.

### `lixity service`

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

For automation, `lixity service status --json` returns
`lixity-service-local/1`: `schema_version`, `ok`, `state`, `message`, plus
`url`, `pid`, `backend`, `installed_version`, `running_version` and `log` when
the manager initializes (unavailable values may be null). States are `running`,
`starting`, `stopped`, `busy` and `unknown`. Exit 0 means `ok: true`; exit 1
means false. Status succeeds only for a ready owned instance; stopped status
exits 1, while stopping an already stopped instance succeeds. Stop preserves
saved launch settings and logs.

**On current main (Unreleased):** status does not create or repair storage or
acquire the lifecycle writer lock. Missing private folders are a normal stopped
state. Unsafe, unreadable or changing records report uncertainty; status does not
change runtime locations to work around a permission error. Lifecycle commands
prepare their private storage when explicitly requested.

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
| **MTLD** | mean segment length until TTR < 0.72 (forward/backward averaged) | larger values mean longer diverse segments; requires ≥ 100 tokens |
| **MATTR** | moving-average TTR over a 50-token window | describes local repetition; compare the same window and tokenization |
| **Maas a²** | (log₁₀ N − log₁₀ V) / (log₁₀ N)² | requires ≥ 100 tokens; lower means more types at the same N, not better prose |
| **Flesch** | language-calibrated Flesch family (Amstad for German) | formula output is not clipped to 0–100; not reader comprehension |
| **LIX** | ASL + share of long words (Björnsson: more than six characters, all languages) | a surface-structure estimate, not a universal difficulty or quality threshold |
| **Dialogue ratio** | share of configured word tokens inside detected quotations | quotation and token regexes affect counts; no speaker attribution |
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

For a review, follow a heatmap cell or paragraph strip to the passage, then
compare the measurement with the chapter's purpose. See
[dashboard navigation](#dashboard-workflow) rather than treating a highlighted
value as an editing instruction.

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
Current-main `--project` and configured-omission modes instead use strict settings
from the selected root; see [default manuscript](#default-manuscript).
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

**On current main (Unreleased):** all manuscript analysis/export commands accept
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

### Chapter register settings

In the native workspace, **Project → Settings → Chapter registers** edits named
registers, optional feature bounds and chapter assignments. **Apply** validates,
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
Lixity's supported exports remain A5 book, A4 sheet and A4 report PDFs. They
provide fixed-layout reading copies, not EPUB or certified PDF/UA/PDF/X files;
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
