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

Requires Python 3.10 or newer.

```bash
pip install git+https://github.com/mfahsold/lixity.git
```

Development install (editable, with the test suite):

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v
```

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

## Command reference

### Common options

| Option | Applies to | Description |
| :--- | :--- | :--- |
| `--language CODE` | all commands | `auto` (default), `de`, `en`, `fr`, `es`, `it`, `pt`, `nl`, `generic`. `auto` detects the language from function words and falls back to `generic` when the signal is weak or ambiguous. |
| `--json` | `analyze`, `profile`, `style` | Print machine-readable JSON instead of the Rich/text output. |
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

### `lixity style`

Prints the **style reference** – the self-calibrated house style of the
manuscript. Lixity measures 16 descriptive, register-neutral features per
chapter (ASL, staccato, hypotaxis, sentence CV, dialogue, function words,
perception filters, modals, passive, nominalisations, adjectives, long words,
starter entropy, first-person starts, Guiraud R, HD-D) and derives their
robust centre (median) and spread (MAD) from the corpus itself. Deviations
are **significance-adjusted** against each chapter's estimation noise
(`z* = (x − median) / √(σ² + SE²)`, documented standard errors per feature),
reported with the statistically expected number of false positives and a
**Benjamini-Hochberg FDR set** (q = 0.05). Additionally, the style reference derives
the manuscript's own abstract **style dimensions** (Spearman correlation of
the features, Jacobi eigendecomposition) with loadings and per-chapter
scores, plus redundant feature pairs (|ρ| ≥ 0.8). Whether a deviation is
intended (register scene) or drift is for the author to decide, never the
engine. The style reference doubles as a constraint block for authoring and editing
(human or assisting LLM).

```bash
lixity style manuscript.md          # text block
lixity style manuscript.md --json   # machine-readable (schema v2)
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
- the sentence-length architecture as bars,
- the **style heatmap**: chapter × feature matrix of significance-adjusted
  z* values with a diverging colour scale (blue = below, orange = above the
  house mean), plus the expected-false-positive/FDR footnote; cells jump to
  the chapter and activate the matching style layer,
- the **style reference** panel (median, ±2σ band, outlier count per
  feature): each band row is clickable and opens the corresponding chapter,
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

- `exports/<slug>_metrics.json` – full corpus metrics (schema v1),
- `exports/<slug>_profile.json` – paragraph-accurate tense profiles,
- `exports/<slug>_style.json` – self-calibrated style reference (schema v2),
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
lixity about            # tool metadata: languages, features, heuristics
lixity about --json     # same metadata as machine-readable JSON
lixity completion bash  # shell completion script (bash or zsh)
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
| ASL | 21,06 | 14,96 – 27,15 | 20,12 |
| Staccato share | 16,87 % | 4,03 – 29,71 | 16,67 % |
| Hypotaxis share | 29,41 % | 13,49 – 45,34 | 29,17 % |
| Sentence-length CV | 0,80 | 0,60 – 0,99 | 0,68 |
| Dialogue share | 58,31 % | 26,22 – 90,40 | 43,84 % |
| Function-word share | 44,91 % | 42,08 – 47,74 | 47,64 % |
| Perception filters | 0,85 | −0,39 – 2,09 | 0,00 |
| Modals / passive (per 1,000) | 11,32 / 4,47 | 6,40 – 16,24 / 1,81 – 7,12 | 10,85 / 2,58 |
| Nominalisations (per 1,000) | 14,77 | 8,34 – 21,20 | 18,09 |
| Adjectives (per 1,000) | 21,52 | 14,10 – 28,94 | 17,05 |
| Long words | 11,02 % | 8,53 – 13,51 | 8,62 % |
| Starter entropy | 5,30 bit | 4,57 – 6,02 | 5,16 |
| First-person starts | 7,55 % | 1,87 – 13,22 | 5,21 % |
| Guiraud R | 18,08 | 14,28 – 21,87 | 14,91 |
| HD-D | 0,9924 | 0,9900 – 0,9948 | 0,9898 |

**15 of 16 features** land inside the corridor; only HD-D misses it by a
hair (0,9898 vs. 0,9900). Three features (dialogue share, function-word
share, long words) exist per chapter only — for the single-chapter draft they
are measured on that chapter. The loop is always the same:
`build` → write → `analyze` → compare → revise – no external style dogma,
only the author's own distribution.

## Work markers (editor-visible)

The dashboard (local control server) can set **work markers** directly into
the manuscript: invisible HTML comment lines with stable IDs
(`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed above the target
paragraph. They appear in the text editor, never render in any export, move
with the paragraph when editing, and are idempotent (deterministic
content-hash IDs). Kinds: `pruefen`, `sachcheck`, `todo`, `achtung`. In the
dashboard, clicking a kind opens an inline note field: type the reason,
`Enter` commits (the marker is written with `note="…"`), `Esc` cancels.
Programmatic access: `api.markers(text)`, `api.add_marker(text, kind, note,
line)`, `api.resolve_marker(text, marker_id)`.

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
| **LIX** | ASL + share of long words (threshold per language: > 6/7/8 letters) | < 40 = accessible, > 50 = demanding |
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
  patterns are comparable *within* one language, not across languages.
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

```bash
.venv/bin/python -m unittest discover -s tests -v   # 126 tests, offline
.venv/bin/ruff check src tests                      # lint (rule set pinned in pyproject.toml)
```

Screenshots for README and project page are generated reproducibly from the
bundled public-domain sample with headless Chromium:
`python3 scripts/make_screenshots.py` (writes `docs/screenshots/`, including a
demonstration status strip). CI runs lint and tests on Python 3.10 and 3.12.

## License

Lixity Non-Commercial License 1.0 (LNCL-1.0) – see [`LICENSE`](../LICENSE).
Commercial licensing on request: mfahsold@googlemail.com.
