# Lixity – Usage & Reference

Complete command-line and library reference for Lixity. If you are new to the
project, start with the [README](../README.md); this document goes into detail.

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

## Installation

Use the [installation guide](INSTALLATION.md) for Windows/macOS/Linux,
updates, removal, pipx, Python API environments and troubleshooting.
Lixity is source-available under LNCL-1.0 for non-commercial use, not on PyPI.
With Git and uv installed, the recommended CLI setup is:

```bash
uv tool install --python 3.12 "git+https://github.com/mfahsold/lixity.git@main"
lixity --version
lixity about
```

`main` is the unreleased 1.15.0.dev0 checkout. Choose `@v1.14.0` instead for
the older published release, or a full commit hash for reproducibility.
`uv tool upgrade lixity` updates within the chosen source/ref. Reopen your
terminal after `uv tool update-shell` if the command is not found.
The engine supports Python 3.10+; TOML project configuration needs 3.11+.

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

All commands read a Markdown manuscript and write to stdout, except `dashboard`,
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
| I want a reproducible artifact set | `lixity build` | `exports/`, archive rotation, `nda/` |
| What can the engine do? | `lixity about --json` | languages, features, thresholds, commands |

## Development dashboard workflow

The `1.15.0.dev0` checkout adds the shared pipeline and the 3D style-space
interaction. These features are not promised for the older `v1.14.0` tag.

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
point to navigate to the underlying chapter. Rotation is opt-in and pauses
when the tab is hidden. Dimension cards show positive and negative loadings.

The box represents independent per-axis cutoffs, not a confidence ellipsoid.
An outlying point means “inspect this chapter,” not “this writing is bad.”
The canvas is pointer-operated; textual scores/loadings remain available, but
full keyboard navigation of individual canvas points is not implemented.

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
| `clean_words`, `clean_chars` | prose only (appendix removed) |
| `tokens`, `vocab_types` | token count (N) and distinct types (V) |
| `ttr`, `guiraud_r`, `yules_k` | lexical diversity measures |
| `total_sentences`, `asl`, `median_sl`, `std_sl` | sentence metrics |
| `sentence_dist` | counts and shares of the four sentence classes |
| `asw` | average syllables per word |
| `flesch_de`, `flesch_variant`, `lix` | language-calibrated readability indices |
| `mtld`, `mattr`, `maas_a2` | length-invariant lexical diversity (`null` when too short) |
| `dialog_words`, `dialog_ratio` | quoted speech |
| `total_paragraphs`, `avg_paragraph_len`, `single_line_paragraphs` | paragraph economy |
| `punctuation`, `signal_counts`, `filter_count` | punctuation (language-neutral keys), signal words, perception filters |
| `chapters` | per-chapter metrics (words, sentences, ASL, TTR, dialogue, motifs, dominance) |

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

- **Positive balance:** the chapter shows more than this manuscript usually
  does. **Negative balance:** it tells more.
- Fallback (documented): when the median absolute deviation is zero (the
  majority of chapters share the median — common for share features such as
  dialogue), the standard deviation is used so the signal is not lost.
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

Prints the **style reference** – the self-calibrated house style of the
manuscript. Defaults: \|z\*\| ≥ 2.5 notable, ≥ 3.5 strong, FDR q = 0.05 (BH);
override with `--z-mild`, `--z-strong`, `--fdr-q`, `--fdr-method`,
`--dim-threshold`, `--flag-min-severity` (same flags on `dashboard`
and `build`). Active values are always reported in the passport `meta`
(`z_mild`, `z_strong`, `fdr_q`, `fdr_method`, `dim_score_threshold`) and in
the dashboard legend / settings – re-read them, never assume the defaults.
Lixity measures 16 descriptive, register-neutral features per
chapter (ASL, staccato, hypotaxis, sentence CV, dialogue, function words,
perception filters, modals, passive, nominalisations, adjectives, long words,
starter entropy, first-person starts, Guiraud R, HD-D) and derives their
robust centre (median) and spread (MAD) from the corpus itself. Deviations
are **significance-adjusted** against each chapter's estimation noise
(`z* = (x − median) / √(σ² + SE²)`, documented standard errors per feature),
reported with the statistically expected number of false positives and an
**FDR set** (BH or BY, q = 0.05). Confirmed cells carry Cliff's δ effect
sizes; the passport also reports baseline exchangeability diagnostics
(runs test, lag-1 ACF). Additionally, the style reference derives
the manuscript's own abstract **style dimensions** (Spearman correlation of
the features, Jacobi eigendecomposition) with loadings and per-chapter
scores, plus redundant feature pairs (|ρ| ≥ 0.8). Structural
diagnostics ride along in `structural_diagnostics`: PELT changepoints, Mann–Kendall
trends, Sn/Qn scales, Hill tail index, early/late Wasserstein–KS
`distribution_shift` / `shifted_features`, and — because `style` builds from
source text — token-level `cooccurrence` (mean degree + Goh–Barabási
fitness) and `keyness` (Dunning G² for the first half of chapters vs the
second; omitted for single-chapter texts). Whether a deviation is
intended (register scene) or drift is for the author to decide, never the
engine. The style reference doubles as a constraint block for authoring and editing
(human or assisting LLM).

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
  lower the faster) with its hook score,
- a **motifs & repetition** panel (when data is supplied or computed by the
  CLI): motif presence and the most repeated phrases with their chapters,
- a **narrative distance** panel (when data is supplied or computed by the
  CLI): tell/show mean z and the per-chapter balance bars (positive = showing),
- the **style heatmap**: chapter × feature matrix of significance-adjusted
  z* values with a diverging colour scale (blue = below, orange = above the
  house mean), plus the expected-false-positive/FDR footnote; cells jump to
  the chapter and activate the matching style layer,
- the **style reference** panel (median, ±2σ band, outlier count per
  feature): **each band row is clickable** and jumps to that feature's
  column in the style heatmap (`#feat-<field>`), activating the matching
  style layer and preselecting “deviations only” when outliers exist; the
  red **outlier count** opens the strongest outlier chapter directly,
- the **style dimensions** panel (self-calibrated principal axes with
  loadings and flagged chapters),
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
  (`Enter` saves, `Esc` cancels) so the reason travels with the marker.

```bash
lixity dashboard manuscript.md -o ui.html
```

### `lixity build`

Idempotent workspace build. Put a manuscript into a folder and run `lixity
build` (or `lixity build path/to/manuscript.md`): lixity discovers the
manuscript, creates the subfolders `exports/` (with `exports/archive/`) and
`nda/`, and publishes all analysis artifacts:

- `exports/<slug>_metrics.json` – full corpus metrics (schema_version 2 meta),
- `exports/<slug>_profile.json` – paragraph-accurate tense profiles,
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
2. **Style corridor** – `lixity build samples/effi-briest.md` publishes the
   manuscript's own median ± 2σ band per feature
   (`samples/exports/effi-briest_style.json`).
3. **Draft** – `samples/effi-briest-folge/effi-briest-folge.md`: the first
   chapter of a sequel about Annie, Effi's daughter.
4. **Verification** – `lixity analyze samples/effi-briest-folge/effi-briest-folge.md`
   measures the draft against that corridor.

| Feature | Fontane (median) | Corridor (±2σ) | Draft |
| :--- | ---: | ---: | ---: |
| ASL | 15.57 | 10.45 – 20.70 | 15.21 |
| Staccato share | 31.53 % | 19.78 – 43.27 | 28.35 % |
| Hypotaxis share | 19.13 % | 5.71 – 32.56 | 15.75 % |
| Sentence-length CV | 0.87 | 0.71 – 1.04 | 0.83 |
| Dialogue share | 58.44 % | 26.78 – 90.10 | 43.84 % |
| Function-word share | 44.98 % | 42.41 – 47.56 | 47.64 % |
| Perception filters | 0.86 | −0.34 – 2.07 | 0.00 |
| Modals / passive (per 1,000) | 11.37 / 4.50 | 6.41 – 16.34 / 2.11 – 6.88 | 10.85 / 2.58 |
| Nominalisations (per 1,000) | 14.94 | 8.63 – 21.25 | 18.09 |
| Adjectives (per 1,000) | 21.18 | 14.41 – 27.95 | 17.05 |
| Long words | 20.28 % | 15.52 – 25.04 | 17.09 % |
| Starter entropy | 5.52 bit | 4.87 – 6.18 | 5.36 |
| First-person starts | 6.57 % | 1.53 – 11.61 | 4.72 % |
| Guiraud R | 18.11 | 14.61 – 21.62 | 14.91 |
| HD-D | 0.9924 | 0.9900 – 0.9948 | 0.9898 |

**14 of 16 features** land inside the corridor; the two at its edge are the
function-word share (+0.08 pp) and HD-D (−0.0002). Three features (dialogue
share, function-word share, long words) exist per chapter only — for the
single-chapter draft they are measured on that chapter. The loop is always the
same: `build` → write → `analyze` → compare → revise – no external style
dogma, only the author's own distribution.

## Work markers (editor-visible)

The dashboard (local control server) can set **work markers** directly into
the manuscript: invisible HTML comment lines with stable IDs
(`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed above the target
paragraph. They appear in the text editor, never render in any export, move
with the paragraph when editing, and are idempotent (deterministic
content-hash IDs). Kinds: `pruefen`, `sachcheck`, `todo`, `achtung`. In the
dashboard, clicking a kind opens an inline note field: type the reason,
`Enter` commits (the marker is written with `note="…"`), `Esc` cancels.
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

| Metric | Definition | Rule of thumb |
| :--- | :--- | :--- |
| **ASL** | average sentence length in words | 8–11.5 = short, paratactic; higher = more complex |
| **Median / σ** | middle sentence length and spread | a low median with high σ means short base plus bursts |
| **TTR** | type-token ratio V/N | 0.17–0.22 for novel-length prose; falls as texts grow |
| **Guiraud R** | V / √N | length-stabilised lexical spread; comparable across texts |
| **Yule's K** | vocabulary repetition measure | 50–70 = stable narrator idiom; higher = more repetitive |
| **ASW** | average syllables per word | feeds Flesch; ~1.7 is everyday German |
| **MTLD** | mean segment length until TTR < 0.72 (forward/backward averaged) | ≥ 60 = rich; length-invariant |
| **MATTR** | moving-average TTR over a 50-token window | ≥ 0.70 = rich; the most length-stable index |
| **Maas a²** | (log N − log V) / (log N)² | lower = richer vocabulary |
| **Flesch** | language-calibrated Flesch family (Amstad for German) | 65–80 = easy; higher is easier |
| **LIX** | ASL + share of long words (Björnsson: more than six characters, all languages) | < 40 = accessible, > 50 = demanding |
| **Dialogue ratio** | share of words inside quoted speech | 5–15 % typical for narrative prose |
| **Function words** | share of articles, pronouns, prepositions, conjunctions, particles, auxiliaries, modals | high share = grammatical glue, implicit style |
| **Perception filters** | verbs of perception/sensation ("sah", "hörte", "fühlte") | few = showing, many = telling |
| **Sentence classes** | staccato ≤ 6, medium 7–15, long 16–25, complex > 25 words | describes the rhythm architecture |
| **Tense severity** | 0 = neutral, 1 = watch, 2 = conspicuous, 3 = strong friction | flags switches and mixtures for review |

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

## Known limitations & stability

What the numbers can and cannot do — the full register (research basis,
evidence, every trade-off) lives in [`docs/STABILITY.md`](STABILITY.md):

- **Short texts:** length-invariant lexical-diversity indices need minimum
  sizes (MTLD/Maas a² ≥ 100 tokens, HD-D ≥ 175, MATTR ≥ window 50);
  below that Lixity returns `null` and the dashboard shows `–`.
- **Heuristics:** syllables (±5–10 %), suffix-based densities and tense
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
- **Self-calibration needs several chapters** with measurable spread; a
  single chapter hides the heatmap instead of showing noise.
- **Determinism** is byte-identical on the same interpreter; across Python
  versions the last floating-point bits may differ.
- **Dashboard size** grows with paragraph count (~2 MB for 95k words) by
  design — self-contained and offline.
- **Accessibility:** colour is never the only channel (values printed, band
  chart by shape); dense paragraph strips are a documented WCAG 2.5.8
  exception with keyboard access and click-to-read.

## Library

### High-Level API Facade (`lixity.api`)

For automation, AI agents, and straightforward scripting, use the deterministic facade:

```python
from lixity import api

# 1. Analyze corpus KPIs
res = api.analyze(text, language="auto")
kpis = res["metrics"]
print(f"ASL: {kpis['asl']:.2f}, LIX: {kpis['lix']:.1f}")

# 2. Self-calibrated style reference (bands, z*, FDR, dimensions)
reference = api.fingerprint(text, language="de")

# 2b. Structure modules (dialogue, characters, pacing, motifs, showing)
turns = api.dialogue(text, language="de")
cast = api.characters(text, ["Anna", "Ralf"], language="de")
pace = api.pacing(text, language="de")
motifs = api.motifs(text, {"Wut": r"\b(Wut|wütend\w*)\b"}, language="de")
distance = api.showing(text, language="de")

# 3. Paragraph-level tense & style profiling
profiles = api.profile(text, language="de")

# 4. Generate standalone HTML dashboard
html = api.dashboard(text, language="de", title="My Manuscript")

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
contains threshold settings only; language, title and corpus options remain
explicit arguments. See [architecture](ARCHITECTURE.md).

CLI commands with an explicit manuscript path load project settings relative to
that manuscript, not the shell's working directory. Without an explicit path,
workspace discovery starts in the current directory. The configured `title`
is used by both `dashboard` and `build`; artifact filenames still follow the
manuscript filename. An explicit `--language` overrides the project language.

| Field | Default | Purpose |
| :--- | :--- | :--- |
| `language` | `de` | Language profile key (`auto` when set by the CLI). |
| `chapter_regex` | `(?m)^##\s+` | Chapter boundary detection. |
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
demonstration status strip). CI runs lint and tests on Python 3.10 and 3.12
plus a wheel packaging job. Contribution workflow:
[`CONTRIBUTING.md`](../CONTRIBUTING.md).

## License

Lixity Non-Commercial License 1.0 (LNCL-1.0) – see [`LICENSE`](../LICENSE).
Commercial licensing on request: mfahsold@googlemail.com.
