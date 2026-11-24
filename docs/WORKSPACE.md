# Lixity browser workspace manual

Use this manual to read a manuscript, inspect language patterns, keep research
linked to passages and prepare copies for readers. These activities share one
local project. The native writing, reading and research workflows below are
available in the local app. The **Versions** menu and the text association
display control beside the editor describe the current development build.
Start with [Onboarding](ONBOARDING.md) to create, import or open a project;
use [Installation](INSTALLATION.md) for application setup and service updates.
The [CLI reference](USAGE.md), [audio manual](AUDIO.md) and
[research manual](research/USAGE.md) provide the corresponding specialist workflows.

Labels below use the English interface. The same routes are localized, with
German coverage prioritized. The installation guide covers setup for optional
workers and integrations.

| Your next task | Start here |
| --- | --- |
| Write, undo or recover a draft | [Write a manuscript](#write-a-manuscript) |
| Inspect one language pattern while reading | [Connected first session](#a-connected-first-session), then [Reading paragraphs](#reading-paragraphs) |
| Investigate rhythm, vocabulary or readability | [Explore language in the browser](#explore-language-in-the-browser) |
| Understand a marked word or value | [Counted text and paragraph comparison](#counted-text-and-paragraph-comparison), then [Explore a passage](#explore-a-passage) |
| Find text or review tense observations | [Search](#searching-the-manuscript), [Start a review](#start-a-review), [Save review decisions](#save-review-decisions) |
| Compare language patterns across chapters | [Style area](#style-area), [Settings and interpretation](#settings-and-interpretation), [Style-space navigation](#style-space-navigation) |
| Read evidence beside the text | [Dossier alongside](#read-a-dossier-beside-the-manuscript), [Claim associations](#link-a-manuscript-quote-to-a-claim) |
| Review and save character, scene or place notes | [Manuscript dossiers](#research-in-context), [Dossier proposal rules](research/USAGE.md#manuscript-driven-dossier-drafts) |
| Leave an explicit note in the manuscript | [Work markers](#work-markers-editor-visible) |
| Inspect files and project settings | [Project structure](#inspect-project-structure), [Saved project settings](#saved-project-settings) |
| Record or listen | [Audio manual](AUDIO.md#author-voice-recording-and-listening) |
| Prepare a recipient's copy | [Manuscript PDF](#download-a-manuscript-pdf), [Dossier PDF](#download-a-dossier-pdf), [Reading website](#export-a-reading-website), [Preflight](#check-a-reading-website-before-exporting) |
| Recover an unavailable source or missing control | [Source freshness](#source-availability-and-saved-analysis), [Troubleshooting](#troubleshooting) |

## Before you begin

Start the installed local app with `lixity service start --open`. It normally opens
`http://127.0.0.1:8765/`; use **Open Project** for an existing folder or follow
the import preview to create a copy at an explicit destination. Import confirmation
writes the new project; opening reconnects an existing one. The manuscript stays
in its project folder. Use your text editor or the native
[Write workflow](#write-a-manuscript).

The DOCX importer accepts at most 32 MiB of source bytes, 4,096 ZIP
entries, 32 MiB of streamed document XML and 16 MiB of converted UTF-8 text.
Larger inputs fail explicitly before publication. Conversion preserves the
original file, including when an output path aliases it; successful output is
published atomically. These import ceilings do not increase the separate local
manuscript editing limits.

<a id="write-a-manuscript-unreleased"></a>

## Write a manuscript

In the local app, **Write** opens CodeMirror in the manuscript workspace and
loads its bundled assets locally. It supports selected `.md`, `.markdown` and
`.txt` files inside the project, in UTF-8, up to 4 MiB of encoded source.
UTF-8 BOM and uniform LF/CRLF are preserved. Mixed endings, CR-only text, binary
content and unsupported encodings are rejected rather than silently converted.
Public exports remain read-only and do not contain the editor bundle.

Lixity starts saving to your project file after 800 ms without typing or after
up to four seconds of continuous typing. **Saved locally** appears when the server
acknowledges the save. Undo and redo work across autosaves. Open **Versions** to
compare versions or manage recovery copies. **Download draft** in the same menu
saves the current editor text as a separate Markdown file. For saved manuscript
and research files, see
[project backup and restore](PROJECT_BACKUP.md).

**Close writing** saves pending edits and returns to the reader. When the saved
file changes, Lixity reloads the reader and recalculates its analysis. A reload
resets undo history. Returning without a reload restores the previous analysis
display. A failed save or a conflicting edit keeps the editor open so you can
check the save status, recover your text or compare versions.

Open **Dossier alongside** to keep research beside the editor. Where text links
are available, use **Text associations** to show or hide them. Lixity remembers
this display preference in your browser. When reviewing a link in the reader,
inspect the candidate before accepting its association. Changes to manuscript
text leave accepted research links and past analysis decisions for you to review.

**Find / replace** opens the bundled CodeMirror search panel (also Ctrl/Cmd+F).
It supports case-sensitive, whole-word and regular-expression searches, individual
replacement and replace-all. Replacement edits the current buffer and follows
normal autosave. A replace-all is one undoable operation.

To edit a passage after reviewing an analysis finding, jump to the passage in
the reader and choose **Write**. The editor starts at the visible source block.

### Compare versions and resolve a conflict

When another tab or an external editor changes the file, Lixity rejects the
conflicting save, retains the submitted draft and pauses autosave. The text in
the editor stays available. With a network error or interrupted save, use
**Versions → Download draft** to keep a copy of the current buffer.

1. Open **Versions → Compare versions**. The dialog shows **Last acknowledged
   text**, **Current file** and **Draft to review**. The last acknowledged text
   is the editor's last confirmed revision. To compare a recovery copy, choose
   it in **Versions** before opening the comparison.
2. Check the two saved texts and edit **Draft to review**. **Use as draft**
   brings your candidate into the editor with autosave paused. Closing an edited
   comparison asks for confirmation before discarding its changes.
3. Choose **Save this draft** to apply the result. The save checks the exact
   file revision shown in the comparison. If the file changed again, open a
   fresh comparison before trying to save.

The three texts use the same effective analysis settings. With automatic
language detection, the current file supplies the language for all three.
Chapter differences appear when the comparison can match the chapters. A
dialogue share rising from 25% to 50% increases by 25 percentage points.
Unavailable measurements leave the text available for review. Timeline values
stay recorded under their original measurement rules. For a new comparison,
Lixity remeasures retained source text where it can and leaves a gap when it
cannot establish comparable values.

### Use recovery copies and project backups

Choose an entry in **Versions → Choose a recovery copy**. **Load as draft**
opens a retained copy for review with saving paused. If the editor already has
unsaved changes, **Load as draft** downloads that buffer and leaves the text
in the editor. To combine text from both drafts, use **Compare versions** with
the recovery copy selected.

Recovery lives in `.lixity/editing/recovery.sqlite3`, with up to 20 previous source
versions and eight unresolved drafts per document. Unresolved drafts are not
silently evicted; remove a reviewed copy explicitly to free a slot. This directory
contains manuscript text and must remain private and excluded from version control.
It is not included in public reading exports. Use [project backup and restore](PROJECT_BACKUP.md) for an explicit
verified inventory of saved manuscript, selected settings, research and attachments.
The editor recovery journal and unacknowledged drafts are excluded from that backup.
When the same save is retried after a process interruption, Lixity uses the
journal's verified base revision and retained source bytes to complete its
timeline. If the exact base cannot be recovered, the timeline keeps the gap.
Changes made before an autosave request reaches the server are not guaranteed
recoverable; failed/offline saves remain visibly unsaved. Browser-close warnings
are an additional safeguard, not reliable persistence. Atomic writes and retained
copies do not guarantee power-loss durability or prevent every race with an
uncooperative external editor.

| Surface | Available work |
| --- | --- |
| Local app | Read, inspect measurements, open projects, apply settings and explicitly save supported manuscript/research actions |
| `lixity dashboard` HTML | Offline manuscript and analysis snapshot; no project settings or manuscript/research writes |
| Review website | Fixed manuscript/analysis copy with the explicitly included research; no live project writes |
| Reader or companion website | Curated recipient view; no import, recalculation or local project editing |

The live app separates **Manuscript**, **Research** and **Project**. To work on
two projects at once, open the app's home address in a new browser tab and use
**Project actions → Open Project**. Each new project view has its own
`/w/…/` address. Duplicating a tab at that address shows the same view. One
instance can keep up to 16 views. After a restart, return to the home address
and reopen any additional projects you need.

## Explore language in the browser

Start with one question: do sentence lengths vary between chapters, or does a
passage use different vocabulary from its surroundings? Inspect the counts,
then read the passage to decide what the difference means in context.

1. Open the text and confirm its analysis language in **Project → Settings**.
   Website language preferences do not select a linguistic profile. Applying
   analysis settings rebuilds the dashboard; record the settings used for a comparison.
2. Open **Analysis overview**. In the unreleased native navigation, choose
   **Compare chapters** for the chapter matrix or style measurements, or
   **Explore patterns** for sentence rhythm. Choose a comparison within the
   supplied text rather than treating its internal reference as a population norm.
3. Return to a passage and open its measurement explanation. **Counted text**
   exposes the words or sentences behind the value; **Paragraph comparison**
   describes a separate comparison with the chapter. Read both in context.
4. Check the [formula](METHODS.md), [language coverage](LOCALIZATION.md) and
   [interpretation limits](STABILITY.md) before drawing a conclusion. An unknown
   measurement is not zero, and a statistical difference is not a literary fault.
5. For a reproducible record, follow the [CLI text-analysis workflow](USAGE.md#linguistic-text-analysis)
   to export JSON alongside the input provenance, version and explicit settings.
   Keep samples, segmentation and preprocessing comparable across runs.

The research archive can retain supporting evidence and authored observations.
It does not automatically merge retained sources into the manuscript's analysis.

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

**How it’s measured** opens the measurement reference in the interface
language from the overview, evidence card, chapter inspector or version
comparison. The reference gives the counting scope, defaults and examples.
The local app serves it offline. Exported reports link to the public reference.
Read the [English measurement reference](guides/metrics/en.html) to browse all
sections.

In the manuscript, **Measure** offers eight paragraph measurements with a
within-chapter comparison: sentence length, function words, quoted text,
perception and thought cues, sensory cues, passive patterns, modal forms and
nominal-style patterns. The function-word sentence filter, dialogue tags,
indirect-speech cues and repeated words show text evidence. The selected
metric's help links directly to its method. The reader separates a measured
zero, missing language rules and a measured count without exact text ranges.
Reports without paragraph evidence omit the four evidence-only options.

Lixity computes these choices and their text ranges from the current source and
project settings. The browser stores the selected metric as a display preference.
SQLite retains selected aggregate measurements for saved versions. In the
development build, the chapter matrix uses the same chapter measurements as
the version comparison. Look for the baseline date and changes below the word,
sentence-length or quoted-speech value. Deltas require a matched chapter and the
source revision shown in the reader. Tense review uses its own saved decisions
in `.lixity/analysis-review.json`. [Revision comparison](#compare-versions-and-resolve-a-conflict)

**Words in quotes and marked speech** shows the counted words in the selection
and their share of the paragraph. A quote can continue across paragraphs in the
same chapter and scene. The evidence card identifies the recognized marks and
reports uncertain boundaries. A project's `dialogue_regex` can declare other
quotation or reply markers. The editor labels a version delta with the
date of its actual baseline.

Use Zotero to manage your source library and Lixity to retain selected evidence,
record claims and decisions, and link them to manuscript passages. The
[research guide](research/USAGE.md) explains those roles and the optional local-import workflow.

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

### Navigation model and happy path

The workspace groups controls by how they affect your reading context. In the
manuscript toolbar, actions follow one left-to-right flow:
**Reading & Presentation** (`Chapter…`, `Aa Appearance`, `Focus`, `Teleprompter`,
`Listen and direct`), **Review & Companion Dock** (`Analysis Off/On`, `? Guide`,
`Analysis overview`, `Dossiers`), and **Writing** (`Write` / `Close writing`).

Across the application, controls use six distinct interaction patterns:

- **View tabs** (`Manuscript` / `Research` / `Project` in the left sidebar):
  switch the whole workspace context. Scroll position and draft state are
  preserved; nothing is saved or discarded by switching views.
- **Context dock panels** (`Paragraph details`, `Research for this passage`, and
  `Dossiers` in the right-hand split dock): open beside the manuscript on
  desktop (or stacked with a passage-return action on mobile) so you can inspect
  values, claims and notes without losing your place in the prose.
- **In-place disclosures** (`details`/`summary`, e.g. `Aa Appearance`, `? Guide`,
  `Paragraph measurements`, `Read these marks`, `Project actions`, research composers):
  expand where they are and close with `Escape` without leaving the current view.
- **Jumps and drill-downs** (review routes, section nav, `data-jump` KPI tiles,
  heatmap cells, 3D style-space chapter links, search hits, command palette,
  research and publication links): route through one shared scroll-anchor owner
  that switches to the target view or `document`/`overview` surface, reveals
  collapsed disclosures, cancels stale reader-restore timers, applies dynamic
  sticky-header clearance, preserves focus without unintended viewport jumps,
  and highlights the arrival target (including the owning passage for search
  hits) in a reduced-motion-safe style.
- **Dialogs** (project create/open, `Listen and direct` audio studio, `Teleprompter`,
  command palette `Ctrl+K` / `Ctrl+P`, version comparison,
  dossier image viewer): modal overlays. They require an explicit close (`Escape`
  or close button) and keep the underlying buffer, selection and undo history intact.
- **Surface switches** (`Analysis overview` and `Write` mode):
  replace continuous reading with the statistical overview panels or the
  manuscript editor. Leave the overview with `Back to passage` (restoring your
  exact paragraph and prior analysis layer) and leave writing with `Close writing`
  to save and return to the reader.

Happy path for an author or lector (no technical setup beyond the local app):

1. Read with **Analysis Off**. Use the chapter selector, text search (`Enter` /
   `Shift+Enter`) or **Back to passage** to stay oriented.
2. Turn **Analysis On** for exactly one question. Inspect **Counted text** or the
   **Paragraph comparison**, then return to the unmarked passage before deciding.
3. In **Analysis overview**, choose one task: **Review passages**
   (**Textstellen prüfen**), **Compare chapters** (**Kapitel vergleichen**) or
   **Explore patterns** (**Muster erkunden**). These unreleased native entrypoints
   replace the exhaustive section list. Pick a secondary view only when needed;
   the next-passage action remains available above the views.
4. Follow research beside the text via **Dossiers** or **Paragraph details →
   Research for this passage**. Distinguish the exact retained quotation from
   the current dossier record; a changed source never silently updates a saved link.
5. Leave a work marker (`+ Review`, `+ Fact check`, `+ To-do`, `+ Attention`) or
   a triage/dossier decision instead of editing prose to fit a number.
6. Share a bounded copy (PDF, review workspace, reader/companion) and test it
   without the local service.

Alternative and power-user paths that reach the same features (all legitimate, pick one per task):

| Goal | Happy path | Other ways that work |
| --- | --- | --- |
| Chapter comparison | `Analysis overview` → `Compare chapters` → `Chapter matrix` | Heatmap cell click, KPI tile click, command palette (`Ctrl+K` / `Ctrl+P`) |
| Sentence rhythm & dialogue | `Analysis overview` → `Explore patterns` → sentence lengths or quoted text; `Analysis On` → `Measure`, or `D` (**Direct Speech Mode**) | Measure layers (`Sentence length`, `Sticky sentences`, `Dialogue-tag density`, `Word echoes`, `Indirect speech`), command palette, KPI tile drill-down, outlier stepper `◀` / `▶` |
| Tense review | `Analysis overview` → `Review passages`, or paragraph review badge with `Analysis On` | Command palette `Highlight Grammatical Tense`, `#flags` triage table `Read passage`, `.chip` click in chapter strip |
| Feature-rank projection & scenes | `Compare chapters` → `Style` → projection, or `Explore patterns` → scenes | Command palette `Open Style Space Comparison` / `Open Scenes & Registers`, `Stil` tabs (`Heatmap` / `Bänder` / `Projektion der Merkmalsränge`), 3D canvas point click |
| Passage values & evidence | Paragraph `…` button → `Paragraph details` → `Explain measurement` | Click paragraph with `Analysis Off`, click paragraph comparison badge, keyboard `Shift+F10` / right-click context menu, `?` guide actions |
| Research & quotation linking | `Research for this passage` in inspector or `Dossiers` | Select prose text → floating selection toolbar (`Link quotation`), inspector backlink card `Historical Evidence / Dossier`, command palette `Open Research Search` / `Create New Research Dossier` / `Open Chronology & Timeline` |
| Spoken review & teleprompter | `Listen and direct` or `Teleprompter` in toolbar | Keyboard shortcut `P` in reader, select prose text → `Read selection`, inspector backlink card `Vocal Directions & Teleprompter`, command palette |
| Project settings & PDF export | `Project` tab → settings form; sidebar `Project actions` → `Manuscript PDF` | Command palette `Switch to Project Settings` / `Export Manuscript as PDF`, URL hash `#view-project` |
| Writing | `Write` in the manuscript toolbar, then `Close writing` in the editor toolbar | `Undo`, `Redo`, `Find / replace` (`Ctrl/Cmd+F`), `Versions` for comparison, download and recovery, and `Dossier alongside`. |

If a control opens a side panel, it stays beside your text. If it clicks a view tab,
the whole workspace switches. If it opens a dialog, close it explicitly with `Escape`.
Surface switches (`Analysis overview` and `Write`) always expose an explicit return
action in their toolbars (`Back to passage` / `Close writing`).

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
Use **Inspect passages** to choose what to inspect in the text. **Chapter &
manuscript** lists the reports currently available in the overview. Choose a
report and press **Open in overview**. When a passage measurement has a related
report, Lixity suggests it in this picker. **Back to passage** restores your
reading position and selected measurement.

**Analysis help** highlights the next step for the current state. Turn on
analysis, choose a measurement or inspect the measurement at the current
paragraph. **Paragraph details** remains available from the help and the
paragraph menu. Close the measurement card or paragraph details to return to
the visible help control when you started there.

In the overview, read the reason beside the first suggested passage. The
button identifies whether it opens a tense flag or the manuscript start.
Choose a question to reach its available reports and their measurement guides.

**Counted text** and **Paragraph comparison** are
independent switches. **Counted text** initially follows the selected measure's
inline-evidence availability and remembers your choice for each measure.
**Paragraph comparison** starts on and is a shared choice across measures.
For sentence length, every recognized sentence with words is counted,
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

**Paragraph details** opens chapter/source-line context and measurements in the
existing passage inspector without changing global Analysis. Its **Explain
measurement** action inspects counted text; **Research for this passage** reads
explicitly linked claims, sources and decisions. Switch between passage values,
linked research and the chosen dossier explicitly. On mobile, a paragraph-to-tool
action reveals the stacked tool heading; close or Escape returns to that passage
and its control. Desktop tools occupy adjacent space; the reader toolbar compacts
to the available width when the context panel is open.

The visible keys distinguish violet **Counted text** underlines from
**Paragraph comparison**. Notable paragraphs have a raw-value marker with a
down/up arrow and a blue/orange edge for below/above the chapter median; the prose
background receives only a subtle edge wash. Click the marker to see the paragraph
value and the typical measured value in that chapter in the same units. The
chapter matrix uses the manuscript as its reference. **Read these
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
solid counted-text underlines and search backgrounds. The companion's **Text
associations** control applies to the open dossier. The
[annotation design contract](ARCHITECTURE.md#annotation-semantics-and-visual-identity)
explains the ownership and color roles.

These routes share existing actions rather than creating separate records:

| Task | Passage route | Other access |
| --- | --- | --- |
| Explain counted text | **Paragraph details → Explain measurement** | Hover, click or tap a marked word or sentence |
| Read explicitly linked research | **Paragraph details → Research for this passage** | The paragraph's association count |
| Link a quotation to a claim | **Link selection to claim** in the paragraph menu | The selection toolbar or `Alt+L`, with a valid selection inside one paragraph |
| Add a work marker | The paragraph menu's marker actions | The compact selection toolbar offers **Check**; the overview lists saved work markers |
| Keep a chosen dossier beside the text | **Dossier alongside** in the paragraph menu | The reader toolbar and the dossier context control |

**Dossier alongside** displays the dossier you explicitly choose. **Research
for this passage** follows associations saved for the selected paragraph. Merely opening
a dossier beside the manuscript does not link it to that passage.

**Paragraph details → Explain measurement** also works by keyboard or right-click,
including with Analysis Off or Focus reading. That explicit action enables
Analysis and chooses Sentence length if no metric is selected, while preserving
both display-switch preferences.

The measurement card shows the selected quotation and count, the reason for
the mark and a reading question. Paragraph measurements and chapter comparison
have their own section. In **Sticky sentences**, a filled highlight identifies
each counted function word in the selected sentence. In the repeated-word
view, dashed underlines connect additional occurrences of the selected word.
Mapping limits appear under **What is counted**. A word count is not an editorial fault; a
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

**Unreleased native navigation:** the overview opens with **Manuscript
measurements**, manuscript status, the next passage and three task choices.
Selecting **Review passages**, **Compare
chapters** or **Explore patterns** reveals one existing analysis section.
Secondary choices switch sections within that task and retain your inputs.
Use **Sections** in the overview toolbar to reach the choices again
from a long table or chart. Opening the overview again starts at manuscript
measurements, with your previous choices still available inside each task.
Selecting **Manuscript measurements** opens its overview. Deep links reveal
their owning section before navigating, including nested style views.
**Back to passage** restores the manuscript position and analysis choice.
CLI standalone reports retain direct section navigation; without JavaScript their
complete text and tables remain readable.

With **Analysis On**, open **Analysis help (?)** in the reader toolbar. It
explains the selected measure and the steps from counted text to comparison.
Return from Focus reading or the overview to find it in the regular toolbar.
The overview's opening-passage action explains whether it selected a tense
finding or the opening paragraph.
CLI `profile --help` gives the same source-lines → counted-text workflow;
default outputs and JSON contracts are unchanged.

### Save review decisions

Open **Analysis overview → Review passages → Flagged passages** in the local
app. Expand a finding's explanation to see the configured present and past
marker counts and the criteria for a mix or a switch. Use **Show in manuscript**
to read the passage in context. Chapter, severity and decision filters narrow
the list, and **Review next finding** follows the visible findings.

From a flagged paragraph, **Paragraph details → Open review decision** returns to
the matching entry and clears any filters that hide it. Choose **Deliberately
kept**, **Changed by me** or **Review later**, then click **Save decision**.
Choosing a value alone leaves the previous decision in place. **Changed by me**
records your assessment. To edit the manuscript itself, use **Write** and save
the edit there.

Completed counts cover current kept and changed decisions. Deferred items stay
open. A change to the source or analysis settings can leave earlier decisions
stale or unmatched. Lixity retains them and counts unmatched decisions for the
current manuscript path. A renamed file has a different path. Previous decisions
for the old path remain in the project state. To resolve an out-of-date review,
refresh the analysis, reopen the finding and save a decision for the current
passage.

The [CLI review workflow](USAGE.md#lixity-analysis-review) explains the exact
identity checks, storage limits and backup scope. Reading exports omit saved
decisions. Author work markers are a separate action in the paragraph menu.

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
available capabilities: **Paragraph details**, work markers, **Link selection to claim**
for a valid selection, and the companion dossier. A selection within one paragraph
also offers a compact toolbar. Marker notes and claim associations still require
their existing explicit save and retention steps.
Use Shift+right-click to open the browser's native context menu instead.

**Focus reading** temporarily hides surrounding navigation and
tools, counted-text underlines and paragraph comparison markers; its visible exit
or Escape restores the workspace and prior display choices. Opening a tool exits
focus coherently. The compact toolbar keeps chapter selection bounded; dark-mode
surroundings become quieter without lowering manuscript contrast. Subtle color
transitions respect reduced motion. Text-size, layout and companion changes retain the visible
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

<a id="research-in-context-unreleased"></a>

## Research in context

The research workspace uses five content tabs: **Dossiers**, **Claims &
evidence**, **Timeline**, **Decisions** and **Sources**. **Search research** and
**Review links** open shared tools above the selected content. Closing a tool
returns to the originating control; switching tools does not save a record or
replace an unfinished evidence draft.

**Search research** searches retained source passages and current authored
records. Choose all records or a source/dossier/claim/decision scope. From a
claim, **Find evidence** uses the same search in the source scope and returns to
that claim's evidence draft. Search-result details expose technical relevance
information. An exact retained quotation and the latest full source are distinct
reading destinations; opening the latest source does not update an existing pin.

In **Sources**, select a retained text source and choose **Compare vocabulary
with manuscript**. The explicit comparison uses the current captured source and
the loaded manuscript; shared terms and chapter links precede optional numeric
details. Word occurrences do not establish factual agreement, influence or evidence
strength. Missing extracted text or manuscript makes comparison unavailable with
an explanation. This does not replace reading exact cited passages. The
[comparison reference](research/USAGE.md#cross-corpus-comparison-and-evidence-grounding)
describes language, counting and chapter-parsing limits.

**Review links** remains available for the whole project, including unassigned
decisions and unresolved manuscript associations. Contextual dossier/decision
entries open the same review component. Exact-version comparison, author
assessments, manuscript-link repair and configured term variants retain their
explicit review/save steps; they are not automatic corrections. **Terms &
variants** is also reachable from manuscript inspection.

To start a dossier from the text, open **Research → Dossiers → From
manuscript** and choose **Show suggestions**. Browse the available characters,
places and scenes, then select a suggestion to see why it appeared, the
relevant excerpt and the text that will be saved.
**Create dossier** confirms that preview. If the manuscript or settings change,
reload the suggestions and review the new draft. After saving, **Open saved
dossier** opens that record. **New dossier** in the Dossiers toolbar opens the form
on the same page and places the cursor in its title field. Choose the
**Character** template, then fill in the title and details before saving.
Place previews show chapters with matches and the first and last matching
passages. Automatic suggestions include the directional cue that qualified
the name. Use the place settings action to enter a list or turn suggestions
off.
Scene previews use the measured opening and closing sentences. A problem in
scene settings or the place list leaves the other suggestions available.

In a generated character dossier, choose **Preview manuscript analysis** to
review the count, chapters with matches and any excerpts included by your
report settings.
Choose **Save dossier version** to update the saved report alongside your
notes, or use **Edit dossier text** to review and change the combined text.
**Review character analysis** under **From manuscript** opens the same review
for the dossier you select.

Set the inference limits and the contents of saved character reports under
**Project → Analysis → Dossier suggestions and character reports**.
The character preview also opens those settings. Choose **Apply** to
save the project preferences. A compact draft shows the first passage for
review separately from the text it will save.

Open **Current passages in the manuscript** for the live counts and matching
paragraphs. Expand the chapter table for the full distribution, including
zero counts, or select a chapter to focus the reading. Read the highlighted
name in context to check who is meant. To include these passages in a PDF,
review and save the analysis first. [Counting rules and scope](research/USAGE.md#manuscript-driven-dossier-drafts) ·
[Dossier PDF](#download-a-dossier-pdf)

For an object or recurring expression, start with the **Object or term**
template. After saving the dossier, choose it in **Linked dossier** in
**Manage terms & props** and save the term.
**Configured term occurrences** then opens exact matches and their passages
from the current manuscript. [Configure terms and variants](research/USAGE.md#configured-terms-and-boundary-policies)

## Editing research text

Research text fields share one Markdown editor with localized formatting controls
and word/character counts. The formatting actions preserve the text selection;
`Ctrl`/`Cmd` + `B`, `I`, `K` and `H` apply bold, italic, links and headings.
`Tab` and `Shift+Tab` move between controls without changing the text. Pressing
`Enter` continues a list, including task checkboxes; an empty item ends the list.

In the research revision dialog, the action row remains outside the scrolling
fields. Saving still requires an explicit change type and reason. Formatting or
switching tabs does not save a revision automatically.

## Organizing dossier collections

In **Research → Dossiers**, open **Collections and reading order**. Give the
collection a name, choose dossiers by title, and use **Add dossier** to include
them. Move entries up or down to set the reading order; removing an entry only
removes its membership in this collection. Select an existing collection to edit
it, or choose **New collection** to start another one. Changes take effect only
after **Save collection**.

Technical references are read-only and collapsed by default. New collections get
an identifier when saved; existing identifiers remain unchanged. Missing or
withdrawn dossiers stay in the reading order with an unavailable notice until
explicitly removed. Saving a collection changes project configuration, without
creating dossier revisions or changing retained sources or evidence links.
Interface labels follow the selected language; authored dossier titles stay as
written.

## Searching the manuscript

In the analysis overview, choose **Back to passage** to return to the manuscript.
Type a phrase in the manuscript search field to show matches before jumping to
one. `Ctrl+F` (`Cmd+F` on macOS) focuses the field when it is visible. Use the
arrows or `Enter` and `Shift+Enter` to move between matches. `Escape` or **Clear
search** restores the manuscript and reapplies **Flagged only** if it was active.
The count shows matching blocks out of the blocks searched, including readable
structural blocks and analyzed paragraphs.

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

**Open passage** in the overview opens the first paragraph meeting the
selected tense threshold, otherwise the opening paragraph, clearing filters and
focusing the passage. Choose **Compare chapters** for chapter comparisons or
**Explore patterns** for sentence rhythm and other patterns in the unreleased
native navigation. Passage/chapter links navigate to the corresponding prose.
These are review locations, not rankings or instructions to revise.

The native overview keeps only the selected analysis section visible.
**Review passages** exposes flagged passages and work markers. Use **Compare
chapters** to ask where the writing changes, for example where sentences get
longer or more words appear in quotations or marked speech. The chapter table
gives average words per sentence and the percentage of words in those passages.
Under **Explore patterns**, the rhythm view puts chapter averages and the
sentence-length distribution together. Open the examples for a selected chapter
or length group to read actual sentences. The word-pattern view opens examples
for the selected pattern and indicates whether the match falls inside a quotation
or marked speech, outside it or across a boundary. It reports unclear boundaries
separately. The examples come from verifiable manuscript paragraphs.

Under **Motifs and repetition**, open a match or highlight related occurrences
together. The reading toolbar keeps previous and next actions within reach.
After opening a group of matches by keyboard, press Tab to reach the next
match. Closing the toolbar returns to the control that opened it for matches
and sentence examples. The native app also finds literal expressions and optional
patterns in the selected manuscript. A coverage note identifies counted hits
that could not be located or were outside the displayed limit.

Choose **Manuscript
measurements** to see the grouped scope, rhythm and language values immediately.
Expand the vocabulary and style disclosures for the additional measures.
Standalone reports open the main measurements by default, including without
JavaScript.

The flagged-passages heading shows the list count. Use **Read passage** to
inspect its context; author work markers remain explicit paragraph actions.
Long flag and scene lists use bounded
scrolling regions: focus the region and use arrow or page-scrolling keys, or use
wheel/touch. Wide chapter, character and scene comparisons retain the row identity
while scrolling sideways. Workflow choices wrap to remain reachable on narrow
screens; keyboard passage/chapter drills focus the revealed text. **Back to
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

**Unreleased chapter measurements.** Select a heatmap cell or a style-reference
cutoff-hit count to see what the selected metric measures, its unit and sample,
the chapter value and the manuscript's typical value (the median in the style
reference).
For example, if a chapter averages 8 words per sentence and the typical value is
12, its sentences are shorter on average. Read the chapter to decide how that
rhythm fits the scene. Expand **All measurements and comparisons** for all 16
chapter values, manuscript medians, reference sample counts and z* values.
Switching metrics keeps the same chapter and the current manuscript marks.
A dash means the value is unavailable.
**Read chapter** opens the chapter and selects the matching paragraph layer if
one is available. Chapter-only metrics clear the prior layer. Closing or
pressing Escape returns focus to the trigger.

The chapter matrix shows `0` when a style
comparison is available and no feature crosses its cutoff; `–` means that the
comparison is unavailable. **What is counted** explains the existing coverage:
chapter values use profiled body paragraphs and lists, while corpus/style
comparisons also include blockquotes. Their values can therefore differ;
the underlying coverage and scores have not changed.

## Settings and interpretation

In **Project → Settings → Analysis**, expand **Adjust highlights** to inspect controls
and explanations. **Apply** submits changes; restoring defaults only changes
the form. Choose a review profile to fill in the thresholds, then adjust any
field. The result of applying settings appears beside the button. If the project
or its settings changed elsewhere, copy any edits you want to keep before
reloading. [Configuration](USAGE.md#configuration-corpusconfig) explains
persistent project metadata and session settings.

In a writable project, expand **Sentence rhythm, dialogue and word-pattern
thresholds** to see how Lixity groups sentences and speech or selects the
function-word cue. Each field describes what changes and shows its default.
**Apply** saves edited values for the current project. The separate option to
save analysis defaults applies to the language and highlight settings above.
The local **How it’s measured** links show the limits used by the current
analysis. The public reference explains the defaults in a fresh installation.

**Manuscript language (analysis)** selects the language profile for counting and
also sets the generated interface language. English is the default.
**Detect automatically** (`auto` in configuration and CLI) estimates the profile
using function words. Check the result for short or multilingual texts.

The matrix color scale stays fixed at z* = −2.5 to +2.5. A **●** marks an
FDR-selected cell; color alone is not a significance decision. Cell details
include raw values, z*, standardized effect and Cliff's δ. The style reference
shows the manuscript median ± 2 robust standard deviations, with sample counts.
**Unreleased:** a shared legend distinguishes the ±2σ band, SE-adjusted
chapter cutoff, nominal FDR selection and chapter-local paragraph cutoff.
`consistency` counts measurable cells below the chapter deviation cutoff, not
inside the ±2σ band. A per-feature notice explains when only two distinct
comparable chapters make the configured deviation cutoff unreachable. This
retains calculated z* cells; absence of marks does not establish uniformity.
Normal-model tails and nominal FDR have no established error-rate calibration.

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

## Style changes and coverage

Open **Compare chapters → Style → Style over time** to review candidate
chapter boundaries, trends, and the first and second manuscript halves.
The cards state how many features were tested and how many were shortlisted.
The boundary search requires a complete chapter series per feature. Use its
chapter links to see where measurements are missing, including chapters below
the shared word floor. Trends use available observations in order. The two
halves retain their original chapter boundaries. [Methods and coverage](METHODS.md#4c-structural-diagnostics-structural_diagnostics)
explain the selection rules.

## Style-space navigation

In **Style map**, select a chapter above the plot or choose its point.
**Read chapter** opens the selected text. Drag to rotate, or use the labeled
rotation and zoom buttons. Use Shift with the mouse wheel to zoom. On touch
screens a vertical swipe scrolls the page. Toggle the trajectory or cutoff box
and reset the camera as needed.
Rotation is opt-in and pauses in a hidden tab. Cards show positive/negative
loadings; the table gives the same measured chapter scores and flags.

Every loading, including chapter-only metrics,
opens the same **Chapter measurements** view for the selected chapter.
The originating axis and loading coefficient remain distinct from the chapter's
measurement and z*. Selecting another metric removes that axis-origin caption;
it does not recompute scores, infer chapter contributions or establish causality.

The chapter selector keeps the chosen chapter's scores with the plot. Choose a
flat axis pair in **View** when points overlap. A cutoff ring can reflect an axis
outside that pair. Return to 3D to rotate the same data. The line follows chapter order, including
gaps where a chapter has no measured position. **Reset** restores the view,
without changing chapter scores or analysis settings.

**Unreleased:** this view is labelled a feature-rank projection. The regularization
notice shows ridge lambda and the complete-chapter/feature counts. Reported
variance shares refer to the regularized matrix's eigenvalues, not necessarily
empirical score variance. They do not establish literary registers. Mahalanobis
distances use the same rank coordinates as the covariance; recompute distances
from earlier mixed-space builds before comparing them.

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
one tool occupies that area at a time. Project navigation keeps its chosen width
when tools or views change. Only its toggle collapses it; toggling preserves the
current reading passage. Drag the divider to change the desktop widths, or focus
it and use
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

The full manuscript-association list lives in **Research → Review**, outside the
reading surface. Passage controls still open the related saved records and offer
a return to the manuscript; expanding review never inserts a list above the prose.

A recorded association retains the exact claim and dossier versions used for it.
Claim and dossier views can open their manuscript
associations in Review. Only an exactly resolved current passage offers a direct
jump; moved, changed, ambiguous and unavailable anchors retain their review state.

Choose **Paragraph details → Research for this
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
thread groups this action with the originating chapter and lines. On desktop,
the passage return is hidden while its origin is visible and reappears when you
leave it. The mobile return bar stays in place to avoid moving the prose.
**Viewed version:**
introduces the title and version of the claim or dossier you opened. Labels distinguish a pinned
version from a current or viewed version; browsing history does not repin a
record. Using the return action, or changing the project/source context,
clears the corresponding journey; simply viewing its origin does not discard it.
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

Reading appearance is different: font size, line spacing and reading width apply
immediately and are remembered in this browser when local storage is available.
They do not change project files. Project settings currently require **Apply**;
typing into that form does not save it automatically. Applying settings rebuilds
the dashboard and can reload the view. Exporting a file or saving a research
revision remains a separate, explicit action.

See the [configuration reference](USAGE.md#configuration-corpusconfig) for the
complete persistence rules, root-local TOML examples and configuration discovery.
If another writer changes the project or configuration, reload before applying;
a conflict or invalid value keeps the draft and previous saved state.

<a id="download-a-manuscript-pdf-since-v240"></a>

## Download a manuscript PDF

Open **Project actions → PDF export**, choose a layout and select **Download
PDF**. The browser initially selects **A4 editorial copy** with line numbers
and room for comments. Choose **A5 reading copy** for continuous reading,
**A4 manuscript sheets** for a submission grid, **A4 analysis report** for
measurements, or **A4 document** for neutral text such as a synopsis.

The browser returns a download. Use [`lixity pdf`](USAGE.md#lixity-pdf) to write
a chosen file from the terminal. Both paths use the shared composer and
project metadata. If the browser reports a stale export context, reload the
project view and select the layout again.

## Download a dossier PDF

In **Research → Dossiers**, open a dossier and choose **Download PDF**. The
same action is available beside the manuscript and when viewing a saved
version. Check the version beside the button. The A4 document includes saved
notes and tables, place and route descriptions, and pinned source quotations.
Use your PDF reader's bookmarks to move between sections of a long dossier.

To include current manuscript passages, review and save the analysis, then
download the new version. Repeated copies of the same generated report appear
once in the PDF. Use the attachment controls to open original media. See the
[research manual](research/USAGE.md#download-a-dossier-as-pdf) for what each
copy contains.

## Export a reading website

Open **Project actions → Reading website** and choose the format that fits
your recipient.

| Format | Included content | Intended use |
| --- | --- | --- |
| Review copy | Manuscript and analysis, with optional internal research and history | Author/editor review |
| Manuscript + selected background | Reading text, curated notes, optional analysis and opted-in chapter audio | Read the story with selected context and listening material |
| Selected background only | Curated notes without the novel or analysis | Background for someone reading elsewhere |

1. Choose **Review copy** for the manuscript, work-marker notes and
   analysis. Enable research only when the recipient should see the included
   records, earlier versions and cited excerpts. For either curated format,
   choose a [saved publication profile](#curate-a-reader-publication).
2. Set the chapter cap and any optional analysis, recording or source-file
   choices that apply to the selected format. Review and companion formats
   have different scopes. The dialog clears source-file inclusion when you
   change the format or profile.
3. Select [**Check export**](#check-a-reading-website-before-exporting) to
   inspect the chosen scope. Select **Download ZIP**, unpack the copy and
   open `index.html` to review what the recipient will receive.

The website is a fixed copy. The recipient can open the unpacked copy locally
or from static hosting. Export a new copy after project changes. For terminal
commands and fresh output directories, see [`lixity export-site`](USAGE.md#lixity-export-site).

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

Use [Retain or import chapter audio](AUDIO.md#retain-or-import-chapter-audio-unreleased)
for the supported WAV format and the browser or CLI steps. The import associates
the recording with the selected chapter and manuscript revision.

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
its own access controls. For saved manuscripts, selected settings and attachments
alongside retained research, use [project backup and restore](PROJECT_BACKUP.md)
in 0.8.1. [Research archive export and restoration](research/USAGE.md#export-and-restoration)
covers the research store, not the manuscript or editor drafts.
Limits fail explicitly rather than silently dropping
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

**Check export** prepares the selected package and reports its sizes, entries
and packaged media. It can take comparable time and memory to a download.
Changing the selection clears the result. Check again after changing which
chapters, notes or files to include.

Use the result to confirm the chapter cap, included notes and source files.
Media without copied source files appears separately from unavailable media.
The check reports known attribution fields. Review the unpacked copy on the
target screen and verify permission to share its contents and files.

If the report identifies a data or history limit, narrow the publication
scope. A curated profile can omit internal review history. If the bundle is too
large, review the copied source files and recordings. These choices affect the
export. The original project remains available for another export.

[Terminal preflight and export](USAGE.md#lixity-export-site) ·
[Preflight response contract](AGENTS.md#website-export-preflight)

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

## Workspace motion

Workspace entrances use short, finite opacity animations through the shared
`LixityMotion` controller. They leave passage geometry unchanged, replace an
interrupted entrance instead of stacking effects, and cancel immediately when
reduced motion is requested. Hidden pages and reduced-motion view changes skip
viewport animation scans. No permanent `will-change` layers or per-frame
JavaScript layout loops are used. The document reserves scrollbar space to avoid
width changes between short and long views.

This follows the [browser animation performance guidance](https://web.dev/articles/animations-guide):
prefer compositable properties and avoid speculative layer promotion. Actual
GPU composition depends on the browser and hardware; this is not an FPS guarantee.
