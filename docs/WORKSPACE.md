# Lixity browser workspace manual

Use this manual while reading and reviewing a manuscript in the local app.
Start with [Onboarding](ONBOARDING.md) to create, import or open a project;
[Installation](INSTALLATION.md) owns application setup and service updates.
The [CLI reference](USAGE.md), [audio manual](AUDIO.md) and
[research manual](research/USAGE.md) provide the corresponding specialist workflows.

Labels below use the English interface. The same routes are localized, with
German coverage prioritized. The workflows below are available in 0.8.0.
Later changes marked **unreleased** require a development checkout.

| Your next task | Start here |
| --- | --- |
| Read with one analysis question | [Connected first session](#a-connected-first-session), then [Reading paragraphs](#reading-paragraphs) |
| Understand a marked word or value | [Counted text and paragraph comparison](#counted-text-and-paragraph-comparison), then [Explore a passage](#explore-a-passage) |
| Find text or review tense observations | [Search](#searching-the-manuscript), [Start a review](#start-a-review), [Save review decisions](#save-review-decisions) |
| Compare chapters or style dimensions | [Style area](#style-area), [Settings and interpretation](#settings-and-interpretation), [Style-space navigation](#style-space-navigation) |
| Read evidence beside the text | [Dossier alongside](#read-a-dossier-beside-the-manuscript), [Claim associations](#link-a-manuscript-quote-to-a-claim) |
| Leave an explicit note in the manuscript | [Work markers](#work-markers-editor-visible) |
| Inspect files and project settings | [Project structure](#inspect-project-structure), [Saved project settings](#saved-project-settings) |
| Record or listen | [Audio manual](AUDIO.md#author-voice-recording-and-listening) |
| Prepare a recipient's copy | [PDF](#download-a-manuscript-pdf), [Reading website](#export-a-reading-website), [Preflight](#check-a-reading-website-before-exporting) |
| Recover an unavailable source or missing control | [Source freshness](#source-availability-and-saved-analysis), [Troubleshooting](#troubleshooting) |

## Before you begin

Start the installed local app with `lixity service start --open`. It normally opens
`http://127.0.0.1:8765/`; use **Open Project** for an existing folder or follow
the import preview to create a copy at an explicit destination. Import confirmation
writes the new project; opening reconnects an existing one. The manuscript stays
in its project folder and is edited in your text editor.

| Surface | Available work |
| --- | --- |
| Local app | Read, inspect measurements, open projects, apply settings and explicitly save supported manuscript/research actions |
| `lixity dashboard` HTML | Offline manuscript and analysis snapshot; no project settings or manuscript/research writes |
| Review website | Fixed manuscript/analysis copy with the explicitly included research; no live project writes |
| Reader or companion website | Curated recipient view; no import, recalculation or local project editing |

The live app separates **Manuscript**, **Research** and **Project**. Open projects
have separate view URLs under the same app address; those URLs expire on restart.
Reopen the project from the home address rather than reusing an expired view.

## Dashboard workflow

In the local app, read in **Manuscript** and use **Analysis overview** for
comparisons. The sections below describe both navigation and the explicit
actions that need a running server. For a separate offline analysis snapshot:

```bash
lixity dashboard manuscript.md --language en -o dashboard.html
```

Open the file in a browser for offline analysis navigation. It embeds manuscript
text and measurements, so treat it as manuscript material when sharing. Project
settings, manuscript writes and research actions require a compatible local
server; start the installed workspace with `lixity service start --open`.

The live workspace separates **Manuscript**, **Research** and **Project**. Use
[Onboarding](ONBOARDING.md#open-or-import) for create/import/open: a file preview
writes nothing until confirmation; opening reconnects an existing project.
For research, use Zotero for ordinary source work and Lixity for retained evidence,
authored records and manuscript associations; the [research guide](research/USAGE.md)
defines that boundary and the optional local-import workflow.

### A connected first session

1. Open or import a manuscript, confirm its language and read a chapter with analysis
   off. The import preview writes nothing until you confirm the destination.
2. Turn analysis on for one question. Use **Counted text** to inspect the original
   words or sentences; **Paragraph comparison** independently compares the paragraph
   with its chapter. Return to the unmarked passage before deciding what to change.
3. Open a linked dossier beside the manuscript. Follow its retained source passages,
   claims and decisions; distinguish an exact earlier link from the current record.
4. For spoken review, open **Listen and direct** from the manuscript toolbar. The
   [audio manual](AUDIO.md) covers plans, recording, profiles and synthesis. Plan
   export is available without a speech service; recording and synthesis are separate actions.
5. Choose a review workspace, curated reader/companion or PDF for the intended recipient.
   Check the prepared export and test the resulting copy without the local service.

The [demo workspace](demo/report.html), [reader copy](demo/reader/index.html) and
[standalone companion](demo/companion/index.html) show different projections of one
fictional project. They are fixed exports; they cannot import, record or save to your project.

<a id="reading-paragraphs-since-v230"></a>

## Reading paragraphs

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

### Counted text and paragraph comparison

The first explicit **Analysis On** selects **Sentence length**
unless you have already saved a metric choice.
Use the directly visible **Measure**
selector while Analysis is on. **Counted text** and **Paragraph comparison** are
independent switches: keep either, both or neither. **In 0.8.0:** counted text starts off
for each measure, and its choice is remembered separately per measure; paragraph
comparison starts on and remains a shared choice. An older saved global counted-text
choice is assigned to the last selected measure, if one was selected. If it was
set to None or no valid measure was saved, all measures start with counted text off.
Other reader preferences are retained. For sentence length, every recognized sentence with words is counted,
so enabling counted text can underline almost the whole manuscript; this does not
mean that those sentences are unusually long or require editing. With counted text enabled,
violet underlines identify counted words, patterns, quoted speech or sentences.
Hover a mark for its explanation; a short stationary tap opens it on touch
screens. Escape closes it. Analysis Off and **None** hide both kinds of indicator;
unchecking either switch hides only its own marks and key. The selected metric and
the switch preferences persist in the browser, including deliberate **None** and
disabled switches. Turning Analysis on again preserves those choices.

While a measurement overlay is active, separate tense-pattern badges are hidden
in the text. Tense findings remain available in the analysis overview and passage
inspector, subject to the configured severity threshold.

### Explore a passage

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
The **Emphasize deviations in chapter strips** control dims other paragraph chips
in those strips; it does not remove manuscript paragraphs.

Saved research has a separate visual identity:
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

### Reading settings and first-analysis help

Choose a chapter in the reader toolbar. **Reading settings** groups **A−**/**A+**
for text size (16–28 nominal pixels), narrow/standard/wide text and
compact/standard/relaxed line spacing. Appearance and the desktop split are local
browser preferences; display changes do not edit the source.

The analysis overview's section links sit in its existing
header and wrap instead of hiding later sections beyond a horizontal scroll.
They jump within the overview; the underlined link indicates the current
section, not a completed review step. **Back to passage** remains the return to
the manuscript. On short viewports the header scrolls with the content to leave
room for the measurements.

**? → Help with your first analysis** is a voluntary
panel in the reader toolbar. It explains the current Analysis Off /
no selected measure / selected measure state and a read–count–compare workflow.
It does not enable diagnostics, reset preferences, create a task or change
measurements. It is hidden in Focus reading and the overview; returning to
the manuscript restores it. The overview's opening-passage action now visibly
explains its existing tense-flag/opening-paragraph selection, not a quality rank.
CLI `profile --help` gives the same source-lines → counted-text workflow;
default outputs and JSON contracts are unchanged.

### Save review decisions

**Review decisions:** the overview's flagged list contains tense
heuristics, not all chapter or paragraph metrics. **Why here?** reports actual
configured present/past marker counts and mixed/switch criteria. **Read passage**
is primary; a diagnostic no longer directly proposes a To-do. Author work markers
remain available from the manuscript's paragraph menu.
The passage list switches from columns to the same compact records when its
available pane becomes too narrow. Reading and decision controls remain visible
beside the sidebar as well as on smaller screens.

The native host advertises `analysis-review` to permit project-local decisions.
From a flagged passage, **Explore passage** offers **Open review decision** to
return directly to its matching review entry. Filters that would hide the entry
are cleared. The passage identity must still match; opening it does not save.
Chapter, stage and decision filters limit the visible list; **Read next visible
passage** follows that selection without saving anything. Choose **Deliberately
kept**, **Changed by me** or **Review later**, then save explicitly. Completed
counts include only current kept/changed decisions, not deferred or stale ones.
Previously saved decisions for the current manuscript path that no longer match a
current observation are counted as unmatched and retained, including when no flags
remain. Decisions under another path, including a manuscript's former name, remain
in the state file but are not included in this count. Decisions are not silently
attached to another passage; their individual contents are not yet exposed here.
No automatic manuscript change, task, source capture or research decision occurs.

For the CLI workflow, exact identity guards, storage limits and backup scope,
see [`lixity analysis-review`](USAGE.md#lixity-analysis-review). Text or analysis
changes can make earlier decisions stale or unmatched; they are retained rather
than silently attached to another passage. Reading exports do not include these
decisions or allow saves.

### Keyboard, touch and focus reading

**Reading settings → Keyboard shortcuts**
lists the passage menu, search and close keys. Hovering or focusing key controls
also gives a short explanation; Escape dismisses a tooltip. Mouse hints wait
briefly for deliberate hovering, then switch faster between neighboring tools.
They appear beside the hovered control near the pointer;
keyboard and touch hints keep room for adjacent toolbar actions. They show the control name, its explanation and any declared
shortcut. Moving away or starting an action cancels a pending hint. Keyboard
focus and explicit touch explanations do not wait for mouse dwell. An open hint
stays available while its trigger retains focus or the pointer remains over
the trigger or hint; Escape dismisses it. Essential actions
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

### Source structure and coverage

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
The [book PDF](USAGE.md#lixity-pdf) keeps its established presentation and stricter TeX
rules. Profile-only embedding callers retain their analysis-projection fallback.
Plain reports retain their report presentation, and the no-JavaScript fallback
keeps source text readable. Complete paragraph data remains embedded; deferred
interaction does not make the self-contained file smaller.

The manuscript is a document reader: dragging selects text and resizing text
changes its layout. Images use the shared zoom viewer, maps use Leaflet pan/zoom,
and style-space retains its own rotation and zoom controls.

## Searching the manuscript

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

<a id="start-a-review-since-v230"></a>

## Start a review

In the interactive workspace, the **Analysis** switch has a visible
On/Off state while the manuscript remains continuous. Showing diagnostics keeps
the prose width and navigation choice; it does not open a context tool. An
analyzed paragraph's **Values** opens the **Passage values** inspector independently
of the Analysis On/Off choice. **Analysis overview** opens chapter comparisons and other dense views;
**Back to passage** restores the earlier analysis choice and document context.

**Available in 0.8.0:** the reading controls group chapter, text settings and focus
together. The analysis measure explains what its marks and paragraph comparison
show; comparison arrows sit with that switch. **Analysis help → Inspect the
count** examines a visible manuscript passage. Overview navigation includes
quoted text, names, pacing and signal groups in document order.

A tense review card names its actual trigger:
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

The overview keeps these review routes,
section navigation and flagged passages visible. Expand **Manuscript
measurements** for the grouped scope, rhythm, language, vocabulary and style
values; use the same summary to collapse them. Its open state survives switching
between the overview and manuscript. Standalone reports start with these values
expanded, including without JavaScript.

The flagged-passages heading shows the list count. Use **Read passage** to
inspect its context; author work markers remain explicit paragraph actions.
Long flag and scene lists use bounded
scrolling regions: focus the region and use arrow or page-scrolling keys, or use
wheel/touch. Wide chapter, character and scene comparisons retain the row identity
while scrolling sideways. Section-navigation arrow keys keep offscreen labels
reachable; keyboard passage/chapter drills focus the revealed text. **Back to
passage** retains its earlier passage position, analysis choice and context tool.

<a id="style-area-since-v230"></a>

## Style area

Tabs group the heatmap, style reference, dimensions and structural diagnostics.
`ArrowLeft`/`ArrowRight` moves between tabs; `Home`/`End` selects the first/last.
Links to `#heatmap`, `#bands`, `#dimensions`, `#structural` and `#feat-<field>`
select the relevant tab. All available panels remain readable without JavaScript.
**Available in 0.8.0:** static reports keep native chapter links and the dimension-score
table; interactive filters and the 3D plot are unavailable without scripting.

Keep the three comparison scopes separate:

| View | Measurement / reference | What it does not establish |
| --- | --- | --- |
| Paragraph comparison | One paragraph's raw value against that chapter's median/MAD | A chapter-level z* or a writing fault |
| Chapter fingerprint | One chapter feature against the manuscript reference, with noise-adjusted z* | A cross-metric ranking or an external writing target |
| Style dimensions | Chapter coordinates and axis loadings in standardized midrank space | Paragraph evidence, chapter z*, causal contributions or quality |

The [methods](METHODS.md) define these quantities; the
[interpretation guide](guides/interpretation.html) explains their limits.

Selecting a heatmap cell or a style-reference
cutoff-hit count opens **Chapter measurements** before navigating. It explains
the selected metric, its unit and chapter sample, alongside all 16 canonical
chapter values, manuscript medians, reference sample counts and z* values.
Switching metrics keeps the same chapter and does not change manuscript marks.
Each metric has its own unit and reference. `–` remains unavailable, never zero.
**Read chapter** uses the existing manuscript navigation and selects only an
applicable paragraph layer; chapter-only metrics clear the prior layer rather
than substituting word marks. Closing or Escape returns focus to the trigger.

The chapter matrix shows `0` when a style
comparison is available and no feature crosses its cutoff; `–` means that the
comparison is unavailable. **What is counted** explains the existing coverage:
chapter values use profiled body paragraphs and lists, while corpus/style
comparisons also include blockquotes. Their values can therefore differ;
the underlying coverage and scores have not changed.

## Settings and interpretation

In **Project → Settings → Analysis**, expand **Adjust highlights** to inspect controls
and explanations. **Apply** submits changes; restoring defaults only changes
the form. Invalid numbers and a strong cutoff below the noticeable cutoff fail
validation. [Configuration](USAGE.md#configuration-corpusconfig) explains persistent
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

## Style-space navigation

In **Style dimensions**, drag to rotate, use the wheel or labeled buttons to
zoom/rotate, and select chapter points or **Chapter scores** links to read a
chapter. Toggle the trajectory or cutoff box and reset the camera as needed.
Rotation is opt-in and pauses in a hidden tab. Cards show positive/negative
loadings; the table gives the same measured chapter scores and flags.

Every loading, including chapter-only metrics,
opens the same **Chapter measurements** view for the selected chapter.
The originating axis and loading coefficient remain distinct from the chapter's
measurement and z*. Selecting another metric removes that axis-origin caption;
it does not recompute scores, infer chapter contributions or establish causality.

The chapter selector keeps the chosen chapter's
scores beside the plot. Choose a flat axis pair in **View** when points overlap;
return to 3D to rotate the same data. The line follows chapter order, including
gaps where a chapter has no measured position. **Reset** restores the view,
without changing chapter scores or analysis settings.

**Available in 0.8.0:** the count beside the plot shows how many measured chapters
reach an axis cutoff. **Next chapter at cutoff** cycles through those chapters
in manuscript order. The cutoff uses unrounded scores and is a prompt for
contextual review, not a quality ranking or an FDR selection.

In the signal-group comparison, the centered bars show the signed difference
between the standardized groups, scaled to the largest absolute chapter value.
The method disclosure explains the underlying signals and their limits.

The box represents independent axis cutoffs, not a confidence ellipsoid.
Canvas points are pointer-operated; native controls and chapter-score links
provide keyboard/touch navigation and remain usable without JavaScript.
These provisions do not establish complete accessibility conformance.


<a id="read-a-dossier-beside-the-manuscript-since-v240"></a>

## Read a dossier beside the manuscript

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

The workspace switcher comes before project
details, so a long title does not push Manuscript, Research and Project out of
reach. **Project actions** keeps New, Open, guidance and available PDF exports
together; version and license information follow those controls.

In the **Research** workspace, dossier cards offer a structured, scannable overview
with clean metadata pills (evidence links, revision numbers), a two-line preview
clamp, and direct section links. When a dossier contains more than 4 sections, an
accessible disclosure (`+N more…`) displays the remaining section links in a
scrollable container, keeping extensive editorial reports compact and readable.

<a id="link-a-manuscript-quote-to-a-claim-v030"></a>

## Link a manuscript quote to a claim

Use **Link selection to claim** (`Alt+L`) on text in one analyzed paragraph.
The selection toolbar and paragraph context menu reach the same action. Review
the claim and quote, then permit retention before saving. Preview writes nothing;
saved links pin exact claim/paragraph versions and need review after changes.
See [retention, anchoring and compatibility](research/USAGE.md#associate-a-manuscript-quote-with-a-claim).

A recorded association retains the exact claim and dossier versions used for it.
Claim and dossier views can open their manuscript
associations in Review. Only an exactly resolved current passage offers a direct
jump; moved, changed, ambiguous and unavailable anchors retain their review state.

Choose **Explore passage → Research for this
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

Leaving an open dossier for its saved
associations or a global research collection offers **Back to dossier**. It
restores that saved version, tab, scroll position and requesting control without
reloading the dossier or discarding drafts. An earlier manuscript return remains
available after returning to the dossier. On narrow screens the return stays
above the current content. Closing or replacing the originating dossier, or
changing project context, removes an invalid return rather than guessing.

## Work markers (editor-visible)

The dashboard (local control server) can set **work markers** directly into
the manuscript: invisible HTML comment lines with stable IDs
(`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed above the target
paragraph. The comments stay out of manuscript prose and PDF text, but exported
HTML dashboards include the marker list and notes. Review those before sharing
a dashboard. Markers move with the paragraph when editing and are idempotent (deterministic
content-hash IDs). Kinds: `pruefen`, `sachcheck`, `todo`, `achtung`. In the
dashboard, clicking a kind opens an inline note field. Type the reason and
choose **Save marker** or press Enter to commit (the marker is written with `note="…"`);
**Cancel** or Escape discards the note. Failed saves show an error and retain
your text; pending requests disable repeated submission.
Open the paragraph's **…** menu and choose a marker kind; this targets the exact
source line. Programmatic access: `api.markers(text)`,
`api.add_marker(text, kind, note, line)`, `api.resolve_marker(text,
marker_id)`.

Failed marker saves report an error and preserve the manuscript bytes and
permissions. The interface retains the draft for correction; HTTP details are
in the [automation contract](AGENTS.md).

## Inspect project structure

Open **Project** to see the selected manuscript, matching research workspace and
existing outputs. **Outputs** groups eligible files directly under `exports/`;
**Check again** repeats the read-only metadata inspection without rebuilding
analysis. **Project → Settings → Audio and services** groups recording, profiles,
microphone settings and service/queue controls in 0.8.0.

**Available** means filesystem metadata is accessible, not that an output is
fresh or the archive is valid. Existing outputs state **Source and generation
history unknown**. Missing optional folders are normal; ambiguous sources,
unsafe links, invalid settings and incomplete scans have explicit findings.
Nothing in this view creates, moves, deletes or repairs files.

See [`lixity project`](USAGE.md#lixity-project) for the same inspection without
a running service, its bounded scanning limits and exit codes. Use
[`lixity build`](USAGE.md#lixity-build) to deliberately regenerate reports and
[research audit](research/USAGE.md#export-and-restoration) for retained archive integrity.

## Saved project settings

Use **Project → Settings** for metadata, publication profiles, audio/services and
project-specific configuration. **Apply** commits the submitted settings; restoring
defaults changes the form until you apply it. Title, author and publication/register
settings persist in the selected root. Analysis language and thresholds remain
session choices unless **Save analysis defaults for this project** is selected.

See the [configuration reference](USAGE.md#configuration-corpusconfig) for the
complete persistence rules, root-local TOML examples and configuration discovery.
If another writer changes the project or configuration, reload before applying;
a conflict or invalid value keeps the draft and previous saved state.

<a id="download-a-manuscript-pdf-since-v240"></a>

## Download a manuscript PDF

Open **Project actions → PDF export**, choose a layout, then
**Download PDF**. Since v0.7.0, **A4 editorial copy** is the initial choice;
**A5 reading copy**, **A4 manuscript sheets** and **A4 analysis report** are also available.
Since v0.7.4, **A4 document** adds a neutral copy for exposés and everyday text.
Changing the layout alone does not generate a file. The download uses the same
composer and project metadata as [`lixity pdf`](USAGE.md#lixity-pdf), returning bytes
directly without creating server export files. Reload after switching projects
or externally changing root configuration; stale export context is rejected.
JavaScript and a compatible native server are required.

## Export a reading website

Since v0.7.4, **Project actions → Reading website** downloads a fixed project
copy as ZIP. Unzip it and open `index.html`, or serve the folder on static
hosting. The recipient needs no Lixity installation or running service.
Later project changes require a new export.

| Format | Included content | Intended use |
| --- | --- | --- |
| Review workspace | Manuscript and analysis; optionally internal research and history | Author/editor review |
| Manuscript + selected background | Reading text, curated notes, optional analysis and opted-in chapter audio | Read the story with selected context and listening material |
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
On first opening for a project, research and source-file inclusion are unchecked.
The dialog retains choices within that project; changing the format, publication
profile or saved profile clears source-file inclusion. Leave research unchecked
for a manuscript/analysis copy, or choose a reader format and publication profile
for selected companion notes.

**Since v0.7.7:** a manuscript-and-background reader copy can optionally include
analysis. Select chapter figures and/or language measurements, or the complete
analysis. The default is no analysis. In the CLI, repeat `--analysis chapters`
and `--analysis language` for the two summaries; `--analysis full` (or `all`)
selects the complete analysis instead. These choices require `--mode reader`.
They produce a separate `analysis.html` linked from the reading copy. Summaries
contain figures and chapter titles, not paragraphs; the full analysis contains
the exported manuscript text and evidence. Neither includes work-marker notes.

Analysis is recomputed from only the chapters physically included by the export
cap, using the chosen language's default rules and default thresholds. It can
therefore differ from the project's analysis. Reading progress does not hide
the resulting figures or full-analysis evidence; use a chapter cap when later
content must be omitted from the delivered files. Opt-in analysis copies use
manifest schema `lixity-read-only-site/2`; existing exports retain version 1.
`--include-research` adds authored dossiers, claims, decisions, their accessible
revision history, cited excerpts, manuscript associations, timelines and map
geometry. This can include internal notes and superseded wording; review the
copy before sharing it. In review mode, original source files and complete
extracted source text require `--include-source-files` together with
`--include-research`. Local retention permission does not establish permission
to redistribute a source.

<a id="include-existing-chapter-recordings-unreleased"></a>

### Include existing chapter recordings

For a **reader** copy, select **Include chapter audio** in the export dialog or add
`--include-audio` to the CLI command:

```bash
lixity export-site --project . -o listening-copy --mode reader \
  --publication-profile readers --include-audio
```

This copies completed chapter recordings; it does not synthesize speech during
export. Use the [audio manual](AUDIO.md) to record, render and review them first. Successful native chapter renders retain project-local audio artifacts.
Explicitly imported chapter WAVs can also be included. Only artifacts bound to the
exact current manuscript and inside the export chapter cap qualify. A changed
manuscript does not silently reuse an older recording.

To retain an existing recording, obtain the SHA-256 of the current manuscript's
exact file bytes, replace `CURRENT_MANUSCRIPT_SHA256` below, and choose its chapter:

```bash
lixity audio-import --project . --audio chapter-1.wav --chapter 1 \
  --source-sha256 CURRENT_MANUSCRIPT_SHA256 --manuscript manuscript.md
```

`--manuscript` is optional when the project resolves one manuscript. The explicit hash
guards against binding the recording after the source changes; it does not prove
that the audio speaks those words. Supported imports are mono/stereo 16-bit PCM
WAV at 8–192 kHz. No implicit format conversion, trimming or transcription runs.

Each included chapter has the shared audio player and a WAV download. Partial
coverage is allowed and shown: a chapter without a matching recording stays text
only. If no current recording qualifies, the requested audio export fails clearly
instead of producing a misleading silent copy. Export without this option remains
available. Review and companion formats do not accept `--include-audio`.

The delivered files contain chapter/title, WAV hash and size, duration and whether
the recording was generated or imported. They contain no voice-reference bytes,
reference transcripts, speech-profile IDs or service endpoints. An imported WAV's chapter
binding is not transcript verification or forced alignment. Audio does not start
automatically and the recipient needs no synthesis service.
When opened directly from local files, playback keeps the normal controls but
reports the frequency spectrum as unavailable because of browser origin limits.
Serving the folder over local HTTP enables spectrum display; no speech service is needed.

Audio-inclusive exports use `lixity-read-only-site/3` and
`lixity-reader-publication/2`; analysis-only and ordinary exports retain their
existing schema versions. **Check export** accounts for the chosen files before
writing or downloading the copy. Review recording rights and listen to the output
before redistribution.

### Curate a reader publication

In **Project → Settings → Reading website profiles**, create a named publication
profile. Choose
an existing dossier, either its full body or a unique section, and the chapter
after which it may appear. Chapter 0 means before the first chapter. A blank
revision uses the current dossier when exporting; an explicit revision keeps
that version. Each export records the actual resolved version.

Export choices use only profiles saved with
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

PDF/video attachments use the same source-file choice and
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

### Sharing limits and automation

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

### Check a reading website before exporting
Prepare and inspect the actual package without
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
mode), or selected publication entries after the chapter cap. `html_bytes` is
the entry page; when reader analysis is included, `analysis_html_bytes` and
`total_html_bytes` report the additional page and both HTML pages together.
Available retained
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

Export data, revision-count and bundle limits stop the check
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

## Source availability and saved analysis

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

## Troubleshooting

| What you see | Next action |
| --- | --- |
| A control for saving, importing or recording is missing | Confirm that this is the local app, not a static demo/report/website, and that the selected project supports the action. |
| An old project-view URL no longer opens | Reopen the project from the app home after a server restart. |
| Saved analysis with a freshness notice | Restore the manuscript or correct the source/settings, then use **Retry refresh**; see [source availability](#source-availability-and-saved-analysis). |
| Text or measurements disappear after filtering | Clear manuscript search and check paragraph, chapter and review filters. [Search](#searching-the-manuscript) and [analysis controls](#settings-and-interpretation) have different reset scopes. |
| An exact counted span is unavailable | Read the stated mapping limit. A numerical value can remain available without verified text evidence; it is not permission to guess the span. |
| A save is rejected after editing the source elsewhere | Reload current observations/context and review again before saving. The app does not silently move a saved quotation or decision to new prose. |
| A research record or source is missing | Use the [research manual](research/USAGE.md); opening a dossier does not itself create passage associations or retain source bytes. |
| Microphone, voice profile or synthesis problem | Follow [audio troubleshooting](AUDIO.md#troubleshooting-and-limits). Recording, retained references and generated speech have separate prerequisites. |
| A website check fails or the copy is too large | Read the [preflight diagnostic](#check-a-reading-website-before-exporting) and select a smaller explicit publication scope. |

For installation/version mismatches and debug logging, use
[CLI troubleshooting](USAGE.md#troubleshooting).
