# Lixity – Usage & Reference

For the experimental research workspace, including Zotero capture, current-record
search, citations, backups and OCR, see [Research usage](research/USAGE.md). For interactive project workflows, see
[Onboarding](ONBOARDING.md).

Complete command-line and library reference for Lixity. If you are new to the
project, start with the [README](https://github.com/mfahsold/lixity/blob/main/README.md); this document goes into detail.

**Contents**

1. [Installation](#installation)
2. [Quick start](#quick-start)
3. [Command reference](#command-reference)
4. [Understanding the metrics](#understanding-the-metrics)
5. [Manuscript format & operation](#manuscript-format--how-to-operate-lixity)
6. [Known limitations & stability](#known-limitations--stability)
7. [Library](#library)
8. [Configuration (`CorpusConfig`)](#configuration-corpusconfig)
9. [Troubleshooting](#troubleshooting)
10. [Development](#development)
11. [License](#license)
12. [Unavailable consistency and empty manuscripts](#unavailable-consistency-and-empty-manuscripts-since-v1180)
13. [Debug logging](#debug-logging-since-v1190)
14. [Research search scopes](#research-search-scopes-since-v1190)
15. [Zotero integration](#zotero-integration-since-v1190)
16. [NDA agreements](#nda-agreements)
17. [Research batch workflow and index ergonomics](#research-batch-workflow-and-index-ergonomics-since-v1200)

## Installation

Use the [installation guide](INSTALLATION.md) for Windows/macOS/Linux,
updates, removal, pipx, Python API environments and troubleshooting.
Lixity is source-available under LNCL-1.0 for non-commercial use, not on PyPI.
Using it for a book intended for sale requires a separate written commercial
license, including self-publishing. See [licensing examples](LICENSING.md).
With Git and uv installed, the recommended CLI setup is:

```bash
uv tool install --python 3.12 "git+https://github.com/mfahsold/lixity.git@v2.3.0"
lixity --version
lixity about
```

`v2.3.0` is the release pin. Choose `@main` only to follow development,
or a reviewed full commit hash for reproducibility.
`uv tool upgrade lixity` updates within the chosen source/ref. Reopen your
terminal after `uv tool update-shell` if the command is not found.
The engine and TOML project configuration support Python 3.10+.

Development install (editable, isolated, with the test suite):

```bash
git clone https://github.com/mfahsold/lixity.git && cd lixity
make install-dev          # or: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
make check                # ruff + mypy --strict + pytest -W error
```

See [shell completion](INSTALLATION.md#optional-shell-completion) for safe
Bash/Zsh setup and user-writable destinations.

## Report language

Reports and CLI messages are **English by default**; set `LIXITY_LANG=de` for
German (the Rich report, the Markdown report, the style-reference text and the
build/dashboard messages follow it). Metric labels and feature units are
localised for `de` and `en`; other languages fall back to English. Project
texts (reference corridors, assessments) are supplied by the calling project
via the `texts` parameter and override single keys.

## Quick start

```bash
lixity analyze   manuscript.md               # terminal report
lixity analyze   manuscript.md --json        # machine-readable metrics
lixity profile   manuscript.md               # tense profiles per paragraph
lixity style     manuscript.md               # self-calibrated style reference
lixity dashboard manuscript.md -o ui.html    # HTML dashboard
```

The commands in this quick start read a Markdown manuscript and write to stdout, except `dashboard`,
which writes a single HTML file.

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
| I want an interactive live server | `lixity serve` | loopback HTTP server, live settings, manuscript upload, research panel |
| I want to manage and cite research sources | `lixity research` | immutable archives, citations, dossiers, manuscript grounding |
| I want a printable report or reading copy | `lixity pdf` | A4 report, A5 book layout, 30×60 sheet |
| I want a reproducible artifact set | `lixity build` | `exports/`, archive rotation |
| What can the engine do? | `lixity about --json` | languages, features, thresholds, commands |

## Dashboard workflow

The current release uses the shared analysis pipeline for CLI, HTML exports and
the local server. A generated dashboard supports analysis navigation offline;
project and research actions require the local server.

**Since v1.23.0:** The server dashboard has three views:
**Research & Dossiers**, **Manuscript & Analysis**, and **Project & Settings**.
New Project, Open Project and optional guidance remain accessible in every view.

Under Project & Settings, choose or drop a Markdown/plain-text manuscript to see
its filename. Selection alone sends no request. In the native server,
Selecting or dropping a file opens the existing **Import Manuscript** preview with that
selection. Confirming the dialog creates a separate project; use **Open Project**
to reconnect an existing folder and its research archive. Embedding hosts that
advertise the load capability instead show **Analyze manuscript now →**, retaining
their existing load action and payload.

Source and dossier list filters match case-insensitive substrings in loaded
titles, tags and IDs; dossiers also match excerpts and section names. Typing
does not request the server or search source text. Use Research → Search for
full-text archive search. Filters keep loaded details and leave association
dropdowns complete, including records hidden from the list. The NDA generator is shown only when the live host advertises `nda-draft`;
its five-field form has explicit preview and download actions.

```bash
lixity dashboard manuscript.md --language en -o dashboard.html
lixity dashboard roman.md --language de -o roman.html
lixity dashboard unknown-language.md --language auto -o detected.html
```

Open the generated file in a browser; no server is needed for analysis views.

### Settings and interpretation

In a compatible local project server, settings show language and project title
first. Expand **Detection thresholds** for labeled numeric controls and their
explanations. Changes apply only after **Apply**; restoring defaults changes
the form but does not save it. Invalid numbers and a strong-deviation cutoff
below the noticeable cutoff are rejected before submission.

The style matrix keeps its color scale fixed at z* = −2.5 to +2.5, independently
of your detection threshold. A **●** identifies a cell selected by the engine's
FDR correction. The optional filter shows only chapters with those results.
Color alone is not a significance decision or an assessment of writing quality.
Cell details include the raw value, z*, standardized effect and Cliff's δ.

The style reference shows the manuscript median ± 2 robust standard deviations,
with per-feature medians and sample counts. This is neither a confidence
interval nor an external editorial target. Its counts denote deviation-cutoff
hits; they are not interchangeable with the matrix's FDR decisions.

Only the project title uses a classic serif font stack. Controls, tables,
body text and all other headings use the existing modern system sans-serif.
No font files are fetched from a third-party server.

### Style-space navigation

In **Style dimensions**, drag to rotate, use the wheel to zoom, toggle the
trajectory or threshold box, and reset the camera as needed. Select a chapter
point to navigate to the underlying chapter. Automatic rotation is opt-in and
pauses when the tab is hidden. Dimension cards show positive and negative loadings.

**Since 2.0.0:** labeled rotation and zoom buttons support
keyboard and touch input. The **Chapter scores** table shows the same measured
chapters, their actual dimension scores and flag status. Its native chapter links
also work with JavaScript disabled. Focus the scrolling table region to reach
columns that extend beyond a small screen. Paragraph chips and dimension controls
have at least 24×24 CSS-pixel targets, increasing to 44×44 for coarse pointers;
long paragraph strips retain their proportional widths and scroll horizontally.

The box represents independent per-axis cutoffs, not a confidence ellipsoid.
An outlying point means “inspect this chapter,” not “this writing is bad.”
Individual canvas points remain pointer-operated. Use the native controls and
chapter-score links for equivalent keyboard/touch navigation; these provisions
do not establish complete accessibility conformance.

Publication, marker-mutation and NDA controls require a compatible project
server; a standalone HTML export does not provide those services itself.
See [architecture](ARCHITECTURE.md) for adapter responsibilities and
[localization](LOCALIZATION.md) for analysis versus presentation language.

## Command reference

### Common options

| Option | Applies to | Description |
| :--- | :--- | :--- |
| `--language CODE` | analysis commands | `en` (default), `de`, `fr`, `es`, `it`, `pt`, `nl`, `generic`, `auto`. Explicit flags override project language settings. `auto` detects the language from function words and falls back to `generic` when the signal is weak or ambiguous. |
| `--json` | `analyze`, `profile`, `style` | Print machine-readable JSON instead of the Rich/text output. |
| `--z-mild FLOAT` | `style`, `dashboard`, `build` | Notable \|z\*\| threshold (default `2.5`). Lower = more sensitive. Active values are reported in the passport `meta` and in the dashboard legend. |
| `--z-strong FLOAT` | `style`, `dashboard`, `build` | Strong \|z\*\| threshold (default `3.5`). |
| `--fdr-q FLOAT` | `style`, `dashboard`, `build` | False-discovery rate for `fdr_flagged` (default `0.05`). |
| `--fdr-method {bh,by}` | `style`, `dashboard`, `build` | BH = Benjamini–Hochberg (default); BY = Benjamini–Yekutieli (arbitrary dependence). |
| `--dim-threshold FLOAT` | `style`, `dashboard`, `build` | \|dimension score\| from which a chapter is flagged on that axis (default `2.5`). |
| `--flag-min-severity {1,2,3}` | `style`, `dashboard`, `build` | Minimum paragraph severity for the flags panel (default `2`). |
| `-o`, `--output PATH` | `dashboard` | Target HTML file (default: `lixity-dashboard.html`). |
| `--dry-run` | `build` | Show planned artifacts without writing anything. |
| `--version` | top-level | Print engine version and exit. |

### `lixity analyze`

Prints a colour-coded Rich report: corpus size, core metrics with reference
corridors and plain-language assessments, the sentence-length architecture and
punctuation densities.

```bash
lixity analyze manuscript.md
lixity analyze manuscript.md --json | jq '.asl, .ttr, .yules_k, .lix'
lixity analyze manuscript.md --language en
```

The JSON payload is the full `CorpusMetrics` schema:

| Field | Meaning |
| :--- | :--- |
| `raw_words`, `raw_chars` | full text including appendix |
| `clean_words`, `clean_chars` | prose only (appendix removed); `clean_words` retains its whitespace count |
| `tokens`, `vocab_types` | token count (N) and distinct types (V) |
| `ttr`, `guiraud_r`, `yules_k` | lexical diversity measures |
| `total_sentences`, `asl`, `median_sl_exact`, `std_sl` | prose sentence metrics; exact median averages the middle pair |
| `median_sl` | legacy integer upper median, preserved for compatibility |
| `sentence_dist` | counts and shares of the four sentence classes |
| `asw` | average syllables per word |
| `flesch_de`, `flesch_variant`, `lix` | language-calibrated readability indices |
| `mtld`, `mattr`, `maas_a2` | less length-sensitive lexical diversity (`null` when too short) |
| `dialog_words`, `dialog_ratio` | quoted word tokens and their percentage of `tokens`, using the same configured `word_regex` |
| `total_paragraphs`, `avg_paragraph_len`, `single_line_paragraphs` | paragraph economy |
| `punctuation`, `signal_counts`, `filter_count` | punctuation (language-neutral keys), signal words, perception filters |
| `chapters` | per-chapter metrics (words, sentences, ASL, TTR, dialogue, motifs, dominance) |

Chapter `dialog_pct` likewise divides quoted tokens by chapter `words`.
The corrected dialogue calculation can change older ratios and dependent style
results; regenerate both sides of a comparison with the same analysis version.
The JSON keys and legacy `clean_words` count remain unchanged.

### `lixity profile`

Emits paragraph-level tense and style profiles as JSON:

- `language` – resolved language key,
- `chapters[]` – `num`, `title`, `start_line`, `end_line`, `words`,
  `paragraphs`, `present_hits`, `past_hits`, `dominant`, `flagged`, `asl`,
  `dialog_pct`, `function_word_pct`,
- `paragraphs[]` – the same fields per paragraph plus `severity`, `mixed`,
  `switch`, `minority_ratio`, line anchors (`start_line`/`end_line`) and style
  densities (`filter_density`, `modal_density`, `nominal_density`,
  `passive_density` per 1,000 words). `dominant` is language-neutral:
  `present`, `past`, `mixed` or `neutral`; the dashboard and reports map these
  values to the display labels of the active language (Präsens, Present, …).

A density is a count scaled to 1,000 words, not a percentage. A few matches in
a very short paragraph can therefore produce a large value. The default
nominalization heuristic excludes the language's curated function words;
explicit project regex overrides retain their match-count semantics. These
suffix cues are not a full grammatical analysis. Rebuild older reports before
comparing their nominal-style results with 2.3.0.

Tense classification is a transparent heuristic, not a black box: curated
high-frequency verb forms are counted per paragraph. A minority tense share of
≥ 25 % marks a paragraph as `mixed`; a change of the dominant tense between
consecutive paragraphs is a `switch`. Severity levels `0`–`3` (from
*unremarkable* to *strong friction*) prioritise what is worth a second look;
the thresholds are injectable via `ProfileThresholds`.

```bash
lixity profile manuscript.md > profile.json
```

### `lixity dialogue`

Dialogue and interaction structure: how often speech starts (turns), how long
turns are and how dialogue is distributed. Heuristic: quoted speech via the
language profile's dialogue pattern; no speaker attribution.

```bash
lixity dialogue manuscript.md          # Rich tables (summary + per chapter)
lixity dialogue manuscript.md --json   # meta + dialogue report
```

JSON fields: `turns`, `turn_words`, `dialogue_words`, `dialogue_pct`,
`avg_turn_words`, `median_turn_words`, `longest_turn_words`, `turns_per_1000`,
`dialogue_paragraph_pct`, `chapters[]` (per chapter: `turns`, `dialogue_pct`,
`avg_turn_words`, `longest_turn_words`, `dialogue_paragraphs`, `paragraphs`).
A paragraph counts as dialogue paragraph when at least 50 % of its words sit
inside quotation marks.

### `lixity characters`

Character presence across chapters for curated names or alias patterns
(`Matthias|Matze`). Whole-word, case-insensitive matching; appendix and front
matter are excluded (chapter numbers match the metrics). **No NER** — the
caller supplies the names; empty `--names` is an error (CLI exit 1,
`ValueError` via the API).

```bash
lixity characters manuscript.md --names "Anna,Ralf"
lixity characters manuscript.md --name "Matthias|Matze" --name Anna --json
```

JSON fields: `chapters` (total), `figures[]` with `mentions`,
`chapters_present`, `first_chapter`, `last_chapter`, `longest_gap`,
`presence_ratio` and `per_chapter`.

### `lixity pacing`

Scene structure, pacing signals and chapter hooks. Scene breaks are explicit
Markdown dividers (`---`, `* * *`, `***`, `___`, `•••`); scenes per chapter =
breaks + 1. When the text has **no** explicit dividers, `explicit_scene_breaks`
is 0 and `scenes_are_chapters` is true — each chapter is one scene, so scene
structure is uninformative (the CLI prints a warning; do not read
`scenes`/`avg_scene_words` as pacing evidence in that case). Per scene and
chapter the report gives the observable tempo proxies (ASL, staccato share,
dialogue share, scene length). The **hook score** (0–3, documented heuristic)
adds one point each for a closing sentence of at most eight words, a terminal
`?`/`!`/`…`, and a closing in dialogue.

```bash
lixity pacing manuscript.md          # Rich tables (summary + per chapter)
lixity pacing manuscript.md --json   # meta + pacing report
```

JSON fields: `chapters`, `scenes`, `explicit_scene_breaks`,
`scenes_are_chapters`, `avg_scene_words`, `avg_chapter_scenes`,
`hook_score_mean`, `fastest_chapter`, `slowest_chapter` and `chapter_list[]`
with `scenes`, `asl`, `dialogue_pct`, `staccato_pct`,
`closing_sentence_words`, `closing_terminal`, `closing_is_dialogue`,
`hook_score` and the per-scene `scene_list[]`.

### Scene registers and project targets

Without chapter headings, a draft is measured as one chapter and keeps all its
prose. A leading `# Title` supplies its title; scene dividers still split the draft.

Use `lixity scenes manuscript.md --language de` to inspect each scene separately;
add `--json` for the complete scene envelope (schema version 1). The dashboard
shows the same observations in **Scenes & style registers**. Chapters serve as
scenes when there are no explicit dividers.

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

Motif tracking and repetition analysis. Motifs are curated regular
expressions (`--motif NAME=REGEX`, repeatable); repetition is generic: the
most frequent content words (function and stop words excluded) and repeated
n-grams (default 3-grams, at least three occurrences) with their chapter
spread. Repetition is a signal for macro editing — deliberate repetition is a
stylistic device, so the report counts and locates, it does not judge.

```bash
lixity motifs manuscript.md --motif 'Wut=\b(Wut|wütend\w*)\b'
lixity motifs manuscript.md --phrases 4 --json
```

JSON fields: `chapters`, `motifs[]` (`mentions`, `density_per_1000`,
`chapters_present`, `first_chapter`, `last_chapter`, `longest_gap`,
`per_chapter`), `top_words[]` and `repeated_phrases[]` (`phrase`, `count`,
`chapters`).

### `lixity showing`

Showing vs. telling balance — a **heuristic, self-calibrating** composite.
Telling signals (per 1,000 words): perception filters, modals, passive
constructions, nominalisations. Showing signals (shares in %): dialogue,
staccato sentences. For each chapter the report computes robust z-scores
(median/MAD, scaled) for the mean of each group against the manuscript's own
chapter medians, and the balance `show_z − tell_z`.

The comparison needs at least three chapters with differing signals. With too
few chapters or no measurable contrast, the app explains the missing support
instead of drawing empty score tiles. Individual measurements remain in the
chapter matrix; this restriction is not a software failure.

- **Positive balance:** the chapter shows more than this manuscript usually
  does. **Negative balance:** it tells more.
- Fallback (documented): when the median absolute deviation is zero (the
  majority of chapters share the median — common for share features such as
  dialogue), the standard deviation is used so the signal is not lost.
- With fewer than three chapters, component z-scores fall back to zero. When
  all chapter balances are identical, `most_telling` and `most_showing` are
  empty lists, including this insufficient-data case. Empty ranks mean no
  distinguishable ordering, not identical artistic effect.
- The dashboard shows comparison values as `–` with an explanation when there
  are fewer than three chapters or no nonzero comparative signals. Raw JSON
  fallback scores remain numeric for compatibility.
- Deliberate telling is a stylistic device — the report ranks and locates,
  it does not judge. The underlying signals are also visible per chapter in
  the dashboard's style heatmap and layer.

```bash
lixity showing manuscript.md          # summary + per-chapter table
lixity showing manuscript.md --json   # meta + showing report
```

JSON fields: `chapters`, `tell_z_mean`, `show_z_mean`, `balance_mean`,
`most_telling`, `most_showing` and `chapter_list[]` with `tell_z`, `show_z`,
`balance` and the raw signals.

### `lixity style`

Prints the **style reference** – descriptive comparisons against the
manuscript's own baseline. Defaults: \|z\*\| ≥ 2.5 notable, ≥ 3.5 strong,
nominal FDR q = 0.05 (BH);
override with `--z-mild`, `--z-strong`, `--fdr-q`, `--fdr-method`,
`--dim-threshold`, `--flag-min-severity` (same flags on `dashboard`
and `build`). Active values are always reported in the passport `meta`
(`z_mild`, `z_strong`, `fdr_q`, `fdr_method`, `dim_score_threshold`) and in
the dashboard legend / settings – re-read them, never assume the defaults.
The 16 chapter features cover sentence length and variation, short sentences
(≤6 words), long sentences (>25 words), quotation share, lexical patterns,
sentence starts and vocabulary diversity. Marker counts for passive, modality
and nominal style are heuristics, not a grammatical parse. Chapter medians
and MAD define the baseline; approximate standard errors reduce some noise in
`z* = (x − median) / √(σ² + SE²)`.

Raw deviations and the **FDR-selected set** (BH or BY) are separate outputs.
Their normal-tail probabilities are not calibrated for the same-sample
baseline: nominal q does not guarantee manuscript false-discovery control.
Cliff's δ adds an ordinal contrast; runs tests and lag-1 correlation expose
some baseline dependence. Exploratory dimensions, redundant feature pairs
and `structural_diagnostics` provide further pointers for review. Dimension
scores and variance share standardized ranks on complete measured chapters;
the plot shows its coverage. Segmentation, estimator conventions and remaining
inference limits are documented in [Methods](METHODS.md) and [Stability](STABILITY.md).

Compare scenes within their intended register and read the passages. A
deliberate change of voice can explain a deviation; the style reference does
not prescribe a writing target or decide whether to edit.

```bash
lixity style manuscript.md          # text block
lixity style manuscript.md --json   # machine-readable (schema v4)
lixity style manuscript.md --json --z-mild 1.5 --fdr-q 0.1 --fdr-method by
```

### `lixity dashboard`

Writes one self-contained HTML file — no CDN, no framework, no external
requests. The output is deterministic: regenerating an unchanged manuscript
produces an identical file, which makes it safe for version control.

The dashboard contains:

- a **status strip** at the top (when the embedding tool provides one, e.g.
  the manuscript workspace UI): one dot per component (manuscript, analysis,
  dossiers, exports, NDA, markers) with a one-word state, so the reader sees
  at a glance what is current and what is stale,
- corpus KPIs (words, chapters, paragraphs, sentences, ASL, TTR, Yule's K,
  Flesch, LIX, dialogue, Guiraud R, HD-D, MTLD, MATTR, Maas a², staccato,
  first-person starts, function words, flagged paragraphs) — **every KPI tile
  is clickable** and jumps to the panel that shows it, preselecting the
  matching filter where one exists (flags / deviations),
- a **flagged passages** panel (`#flags`, directly under the KPIs): one row
  per paragraph with severity ≥ 2, sorted by severity then line — severity
  badge, chapter, line anchor and a short excerpt. Clicking a row **jumps
  straight to that paragraph** (opens it, scrolls, flashes) with the
  “flagged only” filter preselected; each row also has a quick **+ To-do**
  button that writes the work marker inline (note field, `Enter` saves)
  without leaving the list. This is the start of the editorial loop:
  overview → passage → marker,
- the sentence-length architecture as bars,
- a **dialogue structure** panel (when dialogue data is supplied or computed by
  the CLI): turns, dialogue share, average turn length, turns per 1,000 words
  and the chapters with the most speech,
- a **character presence** panel (when names are supplied): mentions, chapters
  present, chapter span, longest gap and a presence bar per figure,
- a **pacing curve** (when pacing data is supplied or computed by the CLI):
  scenes, average scene length, hook mean and one bar per chapter (ASL, the
  sentence-length proxy) with its hook score. When `scenes_are_chapters` is
  true, the panel identifies scene counts as chapter placeholders,
- a **motifs & repetition** panel (when data is supplied or computed by the
  CLI): motif presence and the most repeated phrases with their chapters,
- a **narrative distance** panel (when data is supplied or computed by the
  CLI): tell/show mean z and the per-chapter balance bars (positive = showing),
- the **style heatmap**: chapter × feature matrix of noise-adjusted
  z* values with a diverging colour scale (blue = below, orange = above the
  manuscript median), plus the expected-false-positive/FDR footnote; cells jump to
  the chapter and activate the matching style layer,
- the **style reference** panel (median, ±2σ band, outlier count per
  feature): **each band row is clickable** and jumps to that feature's
  column in the style heatmap (`#feat-<field>`), activating the matching
  style layer and preselecting “deviations only” when outliers exist; the
  red **outlier count** opens the strongest outlier chapter directly,
- the **style dimensions** panel (exploratory rank-space axes with
  loadings, flagged chapters and complete-measurement coverage),
- a chapter map with a colour-coded paragraph strip (present / past / mixed /
  neutral) and severity markers, plus a **style layer** overlay: choosing a
  dimension (ASL, dialogue, function words, perception filters, modals,
  nominalisations, passive) colours every paragraph by its deviation from the
  chapter mean (blue = below, orange = above), with a legend, per-layer
  guidance on what to look for, and the exact value in the tooltip; layer
  colour encodes the absolute value span (min–max per dimension), while a
  ring marks paragraphs that are *unusual for this chapter* (|z| ≥ 1.5) —
  so the layer never hides low values in a narrow band,
- clickable paragraphs revealing text, line anchor and per-paragraph stats
  (highlighted in the active layer colour),
- the chapter comparison matrix with a deviation column; matrix rows and
  marker rows navigate to their passage,
- the **work markers** panel: setting a marker opens an inline note field
  with Save/Cancel (`Enter` saves, `Esc` cancels) so the reason travels with the marker.

```bash
lixity dashboard manuscript.md -o ui.html
```

### `lixity pdf`

Composes a PDF document directly, without a browser, converter or runtime font
package. No new dependency is involved, and nothing is uploaded.

```sh
lixity pdf manuscript.md --layout report            # A4 analysis report
lixity pdf manuscript.md --layout book --author "Name"   # A5 reading layout
lixity pdf manuscript.md --layout sheet             # 30 lines x 60 characters
lixity pdf manuscript.md --layout book -o reading.pdf
```

| Layout | Page | Purpose |
| :--- | :--- | :--- |
| `report` | A4 | The measured analysis report, set in a sans face for screen reading |
| `book` | A5 | Continuous reading: serif measure, mirrored margins, chapter openings, folios |
| `sheet` | A4 | Submission grid: at most 30 lines per page, at most 60 characters per line |

**Typography.** The layouts follow what print research and practice actually
agree on, and where they disagree the guide says so:

- **Measure.** Lines are fitted to roughly 64 characters (`book`) and 78
  (`report`) by choosing the type size from the real text, not the font alone.
  Readable print measures are usually quoted as 45–75 characters; the often
  cited "66 is ideal" is a craftsman's convention rather than a measured
  result, so the size is fitted per document instead of assumed.
- **Line breaking.** Paragraphs are broken by a shortest-cost search over all
  break points, not greedily line by line. Greedy breaking is what produces
  rivers and one-word lines in justified text. There is no hyphenation, so the
  last resort is a ragged edge instead of an unbreakable line.
- **Justification.** Slack is spread over the word gaps, tightening as well as
  stretching, and a line falls back to ragged rather than opening a gap beyond
  a third of an em. The last line of a paragraph is never justified.
- **Margins.** The foot is larger than the head, so the block does not read as
  sinking off the page. The book mirrors its margins for double-sided printing;
  the report uses symmetric margins for single-sided reading.
- **Vertical grid.** Book and report baselines sit on a grid set by the body
  leading, so headings and paragraph spacing land on the same rhythm.
- **Grid sheet.** The submission sheet is a fixed character grid: it is broken
  at the column count and never spaced out, because the count is the contract.
- **Markdown.** Markdown emphasis, code and table syntax are rendered away, so
  a report reads as a document rather than as its source.

Output is written beside the manuscript unless `-o` names another path, and is
deterministic: an unchanged manuscript produces an identical file.

**Characters and fonts.** Text is addressed by glyph id, so any script the
chosen font covers renders — including marks outside Basic Latin. Fonts are
looked up on the host and can be pinned per role with `--serif-font`,
`--bold-font`, `--mono-font`, `--sans-font`, `--sans-bold-font` or
`LIXITY_PDF_FONT_TEXT` / `_HEADING` / `_MONO` / `_SANS` / `_SANS_BOLD`. The
book prefers a face set for reading — EB Garamond, Linux Libertine, Charis SIL,
Gentium — and falls back through Times-metric faces to DejaVu Serif; the report
uses a sans face. Only glyphs actually used are
embedded, so a German manuscript stays a small file. A font whose licence
forbids embedding is refused rather than producing blank pages; an unavailable
font is reported with the file names searched. Exported text carries a
`ToUnicode` map, so it can be searched, selected and copied in a reader.

**Limits.** This is a text and layout renderer. It does not hyphenate, place
images, build tables of contents with page numbers, mirror a running head
between recto and verso, or typeset mathematics. Line breaking minimises badness
without Knuth–Plass hyphenation, so a narrow measure occasionally leaves a
loose line. Text a font cannot draw is reported rather than replaced by a
substitute character. These documents are generated from a Markdown manuscript; the
manuscript itself is never modified.

### `lixity build`

Idempotent workspace build. Put a manuscript into a folder and run `lixity
build` (or `lixity build path/to/manuscript.md`): lixity discovers the
manuscript, creates the subfolders `exports/` (with `exports/archive/`) and
publishes all analysis artifacts:

- `exports/<slug>_metrics.json` – full corpus metrics (schema_version 2 meta),
- `exports/<slug>_profile.json` – paragraph-level heuristic tense profiles with line anchors,
- `exports/<slug>_style.json` – self-calibrated style reference (schema v4),
- `exports/<slug>_style_passport.txt` – human-readable style reference (legacy file name),
- `exports/<slug>_report.md` – Markdown dossier report,
- `exports/<slug>_dashboard.html` – single-file HTML dashboard.

**Idempotency:** identical input causes zero writes; changed input creates
exactly one timestamped version, updates the stable file name (symlink with
file-copy fallback) and rotates older versions into `exports/archive/`
(last 10 kept per artifact family). `--dry-run` prints the plan without
touching any file.

**Manuscript discovery:** `<folder>.md`, then `manuscript.md`/`manuskript.md`,
otherwise the only Markdown file in the folder (README/AGENTS/LICENSE/NDA are
ignored); an explicit path always wins.

```bash
cd my-novel && lixity build          # discovers my-novel.md
lixity build manuscript.md --dry-run
```

### `lixity about` and `lixity completion`

```bash
lixity about                 # languages, features, heuristics
lixity about --json          # machine-readable capability discovery
lixity completion bash       # bash completion script
lixity completion zsh        # zsh completion script
```

Install completion (user-level):

```bash
lixity completion bash > ~/.local/share/bash-completion/completions/lixity
lixity completion zsh  > "${fpath[1]}/_lixity"
```

## Worked example: a sequel in the author's style

The repository ships a complete, reproducible example in `samples/`:

1. **Reference corpus** – Theodor Fontane, *Effi Briest* (Project Gutenberg
   #5323, public domain), converted to Markdown: `samples/effi-briest.md`
   (36 chapters, ~95,000 words).
2. **Style corridor** – `lixity build samples/effi-briest.md --language de` publishes the
   manuscript's own median ± 2σ band per feature
   (`samples/exports/effi-briest_style.json`).
3. **Draft** – `samples/effi-briest-folge/effi-briest-folge.md`: the first
   chapter of a sequel about Annie, Effi's daughter.
4. **Draft metrics** – Analyze the draft with the same language profile, then
   compare its chapter features with the reference passport. `analyze` does not
   automatically load a separate reference passport or decide what to revise.

```sh
lixity style samples/effi-briest.md --language de --json > /tmp/effi-reference.json
lixity analyze samples/effi-briest-folge/effi-briest-folge.md --language de --json > /tmp/effi-draft.json
```

Use newly generated values for both texts. Version 1.16.0 corrects HD-D and
other numerical calculations, so older corridors and draft values are not a
comparison baseline. Read changes in context: a departure can reflect dialogue,
topic or a deliberate narrative choice, and matching the reference distribution
is not evidence of literary quality.

## Work markers (editor-visible)

The dashboard (local control server) can set **work markers** directly into
the manuscript: invisible HTML comment lines with stable IDs
(`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed above the target
paragraph. They appear in the text editor, never render in any export, move
with the paragraph when editing, and are idempotent (deterministic
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

## AI agent interface

Stable, deterministic facade for agents and automation – the full
machine-facing contracts (JSON schemas with meta blocks, exit codes,
interpretation heuristics) live in [`docs/AGENTS.md`](AGENTS.md); the API
facade is described below under [Library](#library).

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
| **Perception filters** | verbs of perception/sensation ("sah", "hörte", "fühlte") | curated pattern counts; narrative distance still requires reading in context |
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

## Manuscript format & how to operate lixity

**Format (Markdown, UTF-8):**

- **Chapters** are level-2 headings: `## Title`. Everything before the first
  `##` is front matter and is not analysed. Both are configurable
  (`CorpusConfig.chapter_regex`).
- **Appendix** starts at `## Anmerkungen und Literaturverzeichnis`
  (`CorpusConfig.appendix_marker`); it is excluded from prose metrics.
- **Paragraphs** are separated by blank lines. Hard line breaks inside a
  paragraph are joined automatically – no manual reformatting needed.
- **Dialogue** in typographic quotes (`»…«`, `„…“`, `“…”`) feeds the dialogue
  ratio.
- **Work markers** are invisible HTML comments
  (`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed directly above the
  paragraph. They never appear in exports and move with the paragraph when
  editing. Other HTML comments are ignored by the analysis.
- Keep the file name stable: the dashboard derives its title from it.

**Operating flow (dashboard):**

1. `lixity dashboard manuscript.md -o exports/dashboard.html` (or `lixity build`
   for the full artifact set), open the file in a browser.
2. Read the KPI groups (Scope · Rhythm · Language · Vocabulary · Style), then
   the heatmap: click a cell to jump to the chapter and activate the matching
   style layer.
3. Use the style layer (toolbar) to see *where* a dimension deviates: blue =
   below, orange = above the chapter mean; the legend explains what to look
   for, the tooltip gives the exact value.
4. Click a paragraph strip to read the passage with line anchor, tense and
   stats; with the control server, markers can be set right there.

Line anchors in reports and dashboards refer to lines in the source file, so
findings stay navigable in the editor.

For example, to review an ASL difference in a synthetic **Report** chapter,
read its value and the manuscript reference, follow its chapter link, and open
a paragraph strip to inspect the source lines. Compare the longer sentences
with the chapter's purpose. Keep deliberate variation or record a review note;
after an author makes an edit, rebuild and inspect the passage again. A flagged
measurement supplies a review location, not a reason to rewrite automatically.

## Known limitations & stability

What the numbers can and cannot do — the full register (research basis,
evidence, every trade-off) lives in [`docs/STABILITY.md`](STABILITY.md):

- **Short texts:** less length-sensitive lexical-diversity indices need minimum
  sizes (HD-D/MTLD/Maas a² ≥ 100 tokens, MATTR ≥ window 50);
  below that Lixity returns `null` and the dashboard shows `–`. These guards
  do not establish reliability above the floor or assess prose quality.
- **Heuristics:** syllables (error rate not established by a gold-standard corpus here), suffix-based densities and tense
  patterns are comparable *within* one language, not across languages;
  heuristics measure what is in the text, they are not ground truth.
- **`signal_counts`:** empty (`{}`) unless the caller supplies
  `CorpusConfig.signal_keywords` — language profiles default to no thematic
  signal words. `filter_count` uses the language filter-verb regex (a curated
  lemma list), which intentionally differs from broader editorial definitions
  (e.g. German perception verbs: engine ≈ 94 vs a 120-verb dossier list);
  do not swap the two numbers without restating the definition.
- **Pacing without dividers:** no explicit `---`/`* * *` breaks means
  `explicit_scene_breaks=0` and `scenes_are_chapters=true` (scenes ≡
  chapters); scene counts are then structure placeholders, not pacing.
- **`characters` / `dialogue`:** no NER and no speaker attribution — names
  and alias patterns come from the caller; dialogue turns are quotation
  segments, not speaker turns.
- **No external Delta stylometry:** divergence metrics (JSD driver words)
  are in-corpus diagnostics for *this* manuscript, not authorship
  attribution against an external reference corpus.
- **Research reference scope:** retained sources never become the manuscript's
  baseline automatically. Source analysis is `source_internal`; explicit
  source–manuscript comparison returns separate vocabulary/register contrasts.
  Historical genre, period and place labels remain unverified context, not
  stylistic norms or factual proof.
- **Self-calibration needs several chapters** with measurable spread; a
  single chapter hides the heatmap instead of showing noise.
- **Determinism** is byte-identical on the same interpreter; across Python
  versions the last floating-point bits may differ.
- **Dashboard size** grows with paragraph count (~2 MB for 95k words) by
  design — self-contained and offline.
- **Accessibility:** numeric labels and text details complement analytical colour
  scales. Since 2.0.0, chapter-score links and native rotation/zoom
  controls provide keyboard/touch equivalents to point navigation. Paragraph
  chips and dimension controls use 24×24 targets, or 44×44 on coarse pointers.
  Individual canvas points remain pointer-operated; automated checks do not
  establish full accessibility conformance.

## Library

### High-Level API Facade (`lixity.api`)

Choose the outputs your integration needs. Each convenience call performs its
own analysis; [the shared pipeline](ARCHITECTURE.md#configuration-and-multiple-projects)
can reuse one result for several outputs. Pass explicit project settings when
working with multiple projects; `{}` selects code defaults for thresholds.

For automation, AI agents, and straightforward scripting, use the deterministic facade:

```python
from pathlib import Path

from lixity import api

text = Path("manuscript.md").read_text(encoding="utf-8")

# 1. Analyze corpus KPIs
res = api.analyze(text, language="auto")
kpis = res["metrics"]
print(f"ASL: {kpis['asl']:.2f}, LIX: {kpis['lix']:.1f}")

# 2. Self-calibrated style reference (bands, z*, FDR, dimensions)
reference = api.fingerprint(text, language="de", project_config={})

# 2b. Structure modules (dialogue, characters, pacing, motifs, showing)
turns = api.dialogue(text, language="de")
cast = api.characters(text, ["Anna", "Ralf"], language="de")
pace = api.pacing(text, language="de")
motifs = api.motifs(text, {"Wut": r"\b(Wut|wütend\w*)\b"}, language="de")
distance = api.showing(text, language="de")

# 3. Paragraph-level tense & style profiling
profiles = api.profile(text, language="de", project_config={})

# 4. Generate standalone HTML dashboard
html = api.dashboard(text, language="de", title="My Manuscript", project_config={})

# 5. Work markers (editor-visible HTML comments)
markers = api.markers(text)
new_text, marker = api.add_marker(text, kind="pruefen", note="Tense check", line=42)
updated_text, ok = api.resolve_marker(new_text, marker["id"])
```

### Low-Level Classes

For fine-grained control, custom configuration, or direct object-model access:

```python
from lixity import CorpusAnalyzer, CorpusConfig, ReportFormatter
from lixity.language import resolve_language

text = open("manuscript.md", encoding="utf-8").read()
resolved = resolve_language(CorpusConfig(language="auto"), sample_text=text)
config = CorpusConfig(language=resolved.key)

analyzer = CorpusAnalyzer(config)
metrics = analyzer.analyze_text(text)

print(metrics.asl, metrics.ttr, metrics.yules_k, metrics.lix)
print(ReportFormatter.format_markdown_report(metrics))
```

> `language="auto"` resolves to `generic` without a text sample (the CLI passes
> the manuscript automatically). Use `resolve_language(config,
> sample_text=text)` in the library to get real detection.

Profiling and dashboard rendering:

```python
from lixity import CorpusConfig
from lixity.language import resolve_language
from lixity.markdown_parser import parse_markdown_blocks
from lixity.style_profile import ParagraphProfiler
from lixity.ui import render_dashboard

text = open("manuscript.md", encoding="utf-8").read()
resolved = resolve_language(CorpusConfig(language="auto"), sample_text=text)
config = CorpusConfig(language=resolved.key)

blocks = parse_markdown_blocks(text)
paragraphs, chapters = ParagraphProfiler(config).profile_blocks(blocks)

html = render_dashboard(
    chapters,
    paragraphs,
    metrics=CorpusAnalyzer(config).analyze_text(text),
    title="manuscript.md",
    labels=resolved.labels,
    language_name=resolved.name,
)
```

Idempotent file writes (atomic, only writes when the content changed):

```python
from lixity import FileUtils

FileUtils.atomic_write_if_changed("ui.html", html)  # False if unchanged
```

## Configuration (`CorpusConfig`)

The style core's minimum calibration size is exposed through
`lixity style manuscript.md --min-chapters 4 --json` (also `dashboard` and
`build`) and `api.fingerprint(..., min_chapters=4)`. Values must be integers
of at least 2. Fewer usable chapters produce unavailable baselines rather
than evidence of a consistent style.

For API project isolation, pass `project_config={}` to `profile`, `fingerprint`,
`passport` or `dashboard` to avoid implicit threshold lookup. A supplied mapping
supplies thresholds and known `CorpusConfig` settings; explicit options override
the mapping. Language and title remain explicit API arguments. Project files accept those same corpus
fields, without a separate list of supported analysis patterns. See [architecture](ARCHITECTURE.md).

CLI commands with an explicit manuscript path load project settings relative to
that manuscript, not the shell's working directory. Without an explicit path,
workspace discovery starts in the current directory. The configured `title`
is used by both `dashboard` and `build`; artifact filenames still follow the
manuscript filename. An explicit `--language` overrides the project language.

Open **Project → Settings → Author name** in the live workspace. Apply saves
only `author_name` in that project's `lixity.toml`, so it survives a restart.
Language, title overrides and analysis thresholds keep their existing session
behavior. An empty author name clears it; no personal name is built into Lixity.
The field is unavailable until a manuscript or research project is open. Author
identity comes only from that project's root configuration, never user defaults
or a parent folder.

The nearby identity check compares the displayed project title and configured
author with explicit manuscript metadata. Supported forms are flat leading YAML
strings (`title` and `author`) or a leading Markdown title page with a `by`, `von`,
`Author:` or `Autor:` line. Missing or unsupported metadata is reported separately
from a mismatch; a missing or unreadable manuscript makes the check unavailable.
Formatting comparisons normalize Unicode and whitespace; they
do not guess authorship from prose or change the manuscript.

A `lixity.toml`, `pyproject.toml` or `~/.config/lixity.toml` that exists but
cannot be read or parsed emits a `UserWarning` naming the file, and its settings
are ignored in favour of code defaults. No config file at all is silent. The
distinction matters: a malformed file previously reverted the run to default
language and thresholds while still exiting `0`, so the JSON looked authoritative
and matched nothing the project had asked for. After any such warning, verify
`meta.language` in the JSON and check applied thresholds in the server dashboard
or pass explicit CLI flags to ensure your intended parameters applied.

| Field | Default | Purpose |
| :--- | :--- | :--- |
| `language` | `en` | Language profile key; automatic detection requires explicit `auto`. |
| `chapter_regex` | `(?m)^##\s+` | Chapter boundary detection. Matches individual heading lines, supporting marker prefixes or complete headings without consuming following prose. |
| `appendix_marker` | `## Anmerkungen und Literaturverzeichnis` | Start of the non-prose appendix. |
| `min_paragraph_length_for_oneliner` | `25` | Word threshold for one-liner classification. |
| `motif_regexes` | `{}` | Project motifs as label → regex, counted per chapter. |
| `signal_keywords` | `None` | Thematic signal words (label → regex); `None` = language profile. |
| `filter_verbs_regex` | `None` | Perception filters ("telling" indicators). |
| `praesens_regex` / `praeteritum_regex` | `None` | Tense markers. |
| `dialogue_regex` | `None` | Quoted speech detection. |
| `word_regex` | `None` | Tokenisation. |

All `None` patterns fall back to the curated defaults of the selected language
profile in `lixity.language_data` — adding a language is a data-layer entry,
not a code change.

### Project NDA configuration (`[nda]`)

The five-field generator works without configuring a store. Optional project
settings in **2.0.0** select a document language or text model:

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

## Troubleshooting

| Symptom | Cause and fix |
| :--- | :--- |
| `FileNotFoundError` / `No such file` | Path or working directory is wrong; quote paths containing spaces. |
| All paragraphs are `Neutral`, no tense colours | The language profile does not match the text, or the text is too short. Force the language with `--language de` (or the correct code). |
| Metrics look wrong / appendix counted as prose | Check the `appendix_marker`; the default expects `## Anmerkungen und Literaturverzeichnis`. |
| Dashboard looks unchanged after editing | Expected when the prose did not change (idempotent writes). Check the file mtime, or compare with a fresh `-o` target. |
| `lixity: command not found` | The install did not land on `PATH`; use `.venv/bin/lixity` or reinstall the package. |

## Development

One entry point (Makefile):

```bash
make help        # list targets
make install-dev # .venv + pip install -e ".[dev]"
make check       # ruff + mypy --strict + pytest -W error
make build       # sdist + wheel into dist/
make screenshots # regenerate docs/screenshots (headless Chromium)
```

Without make:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -W error -q -p no:asyncio
RUFF_CACHE_DIR=/tmp/ruff_cache .venv/bin/ruff check src tests scripts
.venv/bin/mypy --strict src
```

Screenshots for README and project page are generated reproducibly from the
bundled public-domain sample with headless Chromium:
`python3 scripts/make_screenshots.py` (writes `docs/screenshots/`, including a
demonstration status strip). CI runs the core tests on Python 3.10–3.13, research checks on macOS and Windows,
browser checks, lint/type checks and wheel packaging checks. Contribution workflow:
[`CONTRIBUTING.md`](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md).

## License

Lixity Non-Commercial License 1.0 (LNCL-1.0) – see [`LICENSE`](https://github.com/mfahsold/lixity/blob/main/LICENSE).
Commercial licensing on request: mfahsold@googlemail.com.

## Unavailable consistency and empty manuscripts (since v1.18.0)

The dashboard and text style report show “–” when there are no measurable
chapter–feature cells. Empty chapters do not contribute measurements. A single
chapter or a manuscript below the configured `min_chapters` can also be
unavailable even when it contains words. Increasing that minimum deliberately
requires more evidence before a ratio is shown.

Style JSON v4 adds `measured_cells`. If it is zero, the legacy numeric
`consistency: 1.0` is an unavailable-value sentinel retained for compatibility;
do not present it as 100%. When measured, consistency counts cells with
`abs(z*) < z_mild`, not whole chapters. A high result is not a quality verdict.
The [interpretation guide](https://mfahsold.github.io/lixity/guides/interpretation.html)
explains a practical review loop and short-text limits.

## Debug logging (since v1.19.0)

Start the local server with `lixity serve /absolute/path/to/project --debug`,
or set `LIXITY_DEBUG=1` in its environment (`true` and `yes` also enable it).
This enables backend request logging and emits a debug meta tag in the dashboard.
In the browser console, `setLixityDebug(true)` enables verbose API and runtime
diagnostics. **Since 2.0.0:** it saves an explicit `1`,
while `setLixityDebug(false)` saves `0`. These browser preferences take priority
over `window.LIXITY_DEBUG` and the server's debug meta tag, so either choice
survives reload when local storage is available. Remove `lixity_debug` from local
storage to return to the window/server default. With blocked storage, the choice
applies to the active page and reload uses those defaults again.

The browser preference does not change backend logging. Start or restart the
server with the intended CLI/environment setting. Browser warnings and errors
continue to log; API diagnostics include method, URL, status and elapsed milliseconds.
Since 2.3.0, they do not copy response contents into the console. In 2.0.0,
backend requests and error details share
one UTC writer and the prefix `[YYYY-MM-DD HH:MM:SS UTC] [server:debug]`.
Browser API diagnostics have no explicit wall-clock timestamp. Logs may contain
source content or paths; review them before sharing.

## Research search scopes (since v1.19.0)

`lixity research search --project ./novel --query "inspector" --scope all`
searches source passages and current dossiers, claims and decisions together.
Use `--scope dossiers`, `claims` or `decisions` to narrow the results; omitted
scope retains the source-only CLI contract. Run `research reindex --project
./novel` after changes. The dashboard's Search tab defaults to all record types.
See the [research reference](research/USAGE.md#search-current-authored-records-since-v1190)
for response versions and the distinction between authored records and citations.

## Zotero integration (since v1.19.0)

Zotero can be the leading catalogue for literature, images, audio and video.
Lixity captures selected PDF/text evidence and maintains dossiers, claims and
author decisions. It remains usable without Zotero.

In the server dashboard, open Research → Sources, select an explicit Zotero
library and collection, browse items and inspect attachments. Confirm retention
before capturing a supported file. Existing linked sources offer explicit refresh
and an Open in Zotero link. Refresh preserves previous citations; it does not
rewrite authored conclusions. Media files remain in Zotero without automatic
transcription or visual analysis.

The CLI offers `research zotero`, `zotero-ingest`, `zotero-export`,
`zotero-backup` and `zotero-restore`. Export is additive: review and import the
RIS bundle in Zotero, verify original attachment bytes and bind existing source
identities before considering any retirement of an older workflow. The paired
backup requires Zotero to be closed and does not include manuscripts, profiles
or files linked outside its data directory.

See the [Zotero bridge reference](research/USAGE.md#zotero-desktop-bridge-since-v1190)
for setup, pagination, dry runs, v3 compatibility, identity matching and recovery.
There is no automatic migration, bidirectional synchronization or archive deletion.

## NDA agreements

Under **Project & Settings**, enter the recipient's name, optional **Address**, **Project
name**, **Date** and **Place**. A real loaded project name can be prefilled;
an empty workspace leaves it blank. The date defaults to the browser's local
calendar day. Choose **Preview** to read the full friendly agreement, then
**Download PDF** or **Download text**. The address may span several lines.
The output is titled **Confidentiality agreement**, with signature lines for the
recipient and the project representative. Review the details together before
signing; generating or downloading a file does not record either person's consent.
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

## Research workflows and index ergonomics

The [research reference](research/USAGE.md) owns the implemented commands and
their versioned contracts: selected file capture, resumable imports, dossier
sections, author revisions, explicit acknowledgements, Zotero capture and backup.
It also explains lexical source comparisons and their limits. Use the same
supported application version for all archive writers.

For a terminal report, choose `--format text` or `--format md` where supported.
For automation, choose `--json` or `--format json`; `lixity about --json` lists
command-specific formats. HTTP endpoints can be discovered at `GET /api` before
opening a project. Research search refreshes a stale index by default; `--strict`
rejects stale indexes instead. Progress describes real phases on stderr.

**Mark as applied** records an author's review of one decision and dossier at
exact saved versions. Later changes ask for another review. This does not edit
prose, clear unrelated warnings or verify literary consistency. The first such
event upgrades the archive manifest to version 5; older writers reject it.
