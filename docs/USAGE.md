# Lixity – Usage & Reference

Complete command-line and library reference for Lixity. If you are new to the
project, start with the [README](../README.md); this document goes into detail.

**Contents**

1. [Installation](#installation)
2. [Quick start](#quick-start)
3. [Command reference](#command-reference)
4. [Understanding the metrics](#understanding-the-metrics)
5. [Markdown conventions](#markdown-conventions)
6. [Library](#library)
7. [Configuration (`CorpusConfig`)](#configuration-corpusconfig)
8. [Reproducing the screenshots](#reproducing-the-screenshots)
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

## Quick start

```bash
lixity analyze   manuscript.md               # terminal report
lixity analyze   manuscript.md --json        # machine-readable metrics
lixity profile   manuscript.md               # tense profiles per paragraph
lixity style     manuscript.md               # self-calibrated style passport
lixity dashboard manuscript.md -o ui.html    # HTML dashboard
```

All commands read a Markdown manuscript and write to stdout, except `dashboard`,
which writes a single HTML file.

## Command reference

### Common options

| Option | Applies to | Description |
| :--- | :--- | :--- |
| `--language CODE` | all commands | `auto` (default), `de`, `en`, `fr`, `es`, `it`, `pt`, `nl`, `generic`. `auto` detects the language from function words and falls back to `generic` when the signal is weak or ambiguous. |
| `--json` | `analyze`, `profile` | Print machine-readable JSON instead of the Rich/text output. |
| `-o`, `--output PATH` | `dashboard` | Target HTML file (default: `lixity-dashboard.html`). |

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
| `flesch_de`, `lix` | readability indices |
| `dialog_words`, `dialog_ratio` | quoted speech |
| `total_paragraphs`, `avg_paragraph_len`, `single_line_paragraphs` | paragraph economy |
| `punctuation`, `signal_counts`, `filter_count` | punctuation, signal words, perception filters |
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
  `passive_density` per 1,000 words).

Tense classification is a transparent heuristic, not a black box: curated
high-frequency verb forms are counted per paragraph. A minority tense share of
≥ 25 % marks a paragraph as `mixed`; a change of the dominant tense between
consecutive paragraphs is a `switch`. Severity levels `0`–`3` (from
`unauffällig` to `starke Friktion`) prioritise what is worth a second look; the
thresholds are injectable via `ProfileThresholds`.

```bash
lixity profile manuscript.md > profile.json
```

### `lixity style`

Prints the **style passport** – the self-calibrated house style of the
manuscript. Lixity measures 16 descriptive, register-neutral features per
chapter (ASL, staccato, hypotaxis, sentence CV, dialogue, function words,
perception filters, modals, passive, nominalisations, adjectives, long words,
starter entropy, first-person starts, Guiraud R, HD-D) and derives their
robust centre (median) and spread (MAD) from the corpus itself. Deviations
are **significance-adjusted** against each chapter's estimation noise
(`z* = (x − median) / √(σ² + SE²)`, documented standard errors per feature),
reported with the statistically expected number of false positives and a
**Benjamini-Hochberg FDR set** (q = 0.05). Additionally, the passport derives
the manuscript's own abstract **style dimensions** (Spearman correlation of
the features, Jacobi eigendecomposition) with loadings and per-chapter
scores, plus redundant feature pairs (|ρ| ≥ 0.8). Whether a deviation is
intended (register scene) or drift is for the author to decide, never the
engine. The passport doubles as a constraint block for authoring and editing
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

- corpus KPIs (words, chapters, paragraphs, sentences, ASL, TTR, Yule's K,
  Flesch, LIX, dialogue, Guiraud R, HD-D, staccato, first-person starts,
  function words, flagged paragraphs),
- the sentence-length architecture as bars,
- the **style heatmap**: chapter × feature matrix of significance-adjusted
  z* values with a diverging colour scale (blue = below, orange = above the
  house mean), plus the expected-false-positive/FDR footnote,
- the **style passport** panel (median, ±2σ band, outlier count per feature),
- the **style dimensions** panel (self-calibrated principal axes with
  loadings and flagged chapters),
- a chapter map with a colour-coded paragraph strip (present / past / mixed /
  neutral) and severity markers, plus an optional **style layer** overlay
  (bottom edge colour per paragraph, within-chapter normalised),
- clickable paragraphs revealing text, line anchor and per-paragraph stats,
- the chapter comparison matrix with a deviation column.

```bash
lixity dashboard manuscript.md -o ui.html
```

### `lixity about` and `lixity completion`

```bash
lixity about            # tool metadata: languages, features, heuristics
lixity completion bash  # shell completion script (bash or zsh)
```

## Work markers (editor-visible)

The dashboard (local control server) can set **work markers** directly into
the manuscript: invisible HTML comment lines with stable IDs
(`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed above the target
paragraph. They appear in the text editor, never render in any export, move
with the paragraph when editing, and are idempotent (deterministic
content-hash IDs). Kinds: `pruefen`, `sachcheck`, `todo`, `achtung`.
Programmatic access: `api.markers(text)`, `api.add_marker(text, kind, note,
line)`, `api.resolve_marker(text, marker_id)`.

## AI agent interface

Stable, deterministic facade for agents and automation – see
[`docs/AGENTS.md`](AGENTS.md) for the full machine-facing contracts
(JSON schemas with meta blocks, exit codes, interpretation heuristics):

```python
from lixity import api

metrics = api.analyze(text, language="auto")
passport = api.fingerprint(text, language="de")
html = api.dashboard(text, language="de", title="…")
info = api.about()
```

## Understanding the metrics

| Metric | Definition | Rule of thumb |
| :--- | :--- | :--- |
| **ASL** | average sentence length in words | 8–11.5 = short, paratactic; higher = more complex |
| **Median / σ** | middle sentence length and spread | a low median with high σ means short base plus bursts |
| **TTR** | type-token ratio V/N | 0.17–0.22 for novel-length prose; falls as texts grow |
| **Guiraud R** | V / √N | length-stabilised lexical spread; comparable across texts |
| **Yule's K** | vocabulary repetition measure | 50–70 = stable narrator idiom; higher = more repetitive |
| **ASW** | average syllables per word | feeds Flesch; ~1.7 is everyday German |
| **Flesch (DE)** | Flesch Reading Ease, Amstad adaptation | 65–80 = easy; higher is easier |
| **LIX** | ASL + share of words longer than 6 characters | < 40 = accessible, > 50 = demanding |
| **Dialogue ratio** | share of words inside quoted speech | 5–15 % typical for narrative prose |
| **Function words** | share of articles, pronouns, prepositions, conjunctions, particles, auxiliaries, modals | high share = grammatical glue, implicit style |
| **Perception filters** | verbs of perception/sensation ("sah", "hörte", "fühlte") | few = showing, many = telling |
| **Sentence classes** | staccato ≤ 6, medium 7–15, long 16–25, complex > 25 words | describes the rhythm architecture |
| **Tense severity** | 0 = neutral, 1 = watch, 2 = conspicuous, 3 = strong friction | flags switches and mixtures for review |

## Markdown conventions

- Chapters are level-2 headings: `## Title` (configurable via
  `CorpusConfig.chapter_regex`).
- The appendix starts at `## Anmerkungen und Literaturverzeichnis`
  (configurable via `CorpusConfig.appendix_marker`); it is excluded from prose
  metrics and profiling.
- HTML comments (`<!-- ... -->`) are ignored, which makes them a safe place for
  editorial notes.
- Line anchors in reports and dashboards refer to lines in the source file, so
  findings stay navigable in the editor.

## Library

Metrics:

```python
from lixity import CorpusConfig, CorpusAnalyzer, ReportFormatter
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
from lixity.visualizer import render_dashboard

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

## Reproducing the screenshots

The screenshots in the README and on the project page were generated from the
reference manuscript »Eigentlich werde ich nie wütend« (55k words, German):

```bash
lixity analyze   "Eigentlich werde ich nie wütend.md"
lixity profile   "Eigentlich werde ich nie wütend.md" > profile.json
lixity dashboard "Eigentlich werde ich nie wütend.md" -o ui.html
```

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
.venv/bin/python -m unittest discover -s tests -v   # 43 tests, offline
.venv/bin/ruff check src tests                      # lint (rule set pinned in pyproject.toml)
```

CI runs lint and tests on Python 3.10 and 3.12.

## License

Lixity Non-Commercial License 1.0 (LNCL-1.0) – see [`LICENSE`](../LICENSE).
Commercial licensing on request: mfahsold@googlemail.com.
