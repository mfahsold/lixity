# AGENTS.md – Lixity interface for AI agents and automation

Guidance for AI agents (and other programs) that use Lixity as a tool:
which commands to call, how to interpret the JSON, and which heuristics
govern the numbers.

## 1. What Lixity does (one paragraph)

Lixity turns a Markdown manuscript into quantitative text linguistics:
sentence rhythm, lexical diversity, readability, dialogue share,
paragraph-accurate tense profiles, and a **self-calibrating style reference**.
It never judges style against external norms – it derives the manuscript's
own house style (robust median/MAD per feature) and flags only deviations
from that style, controlled for measurement noise and multiple testing.

## 2. Commands

| Command | Purpose | Output |
|---|---|---|
| `lixity analyze FILE --json` | corpus metrics + per-chapter style features | JSON (meta + metrics) |
| `lixity profile FILE` | paragraph-accurate tense/style profiles | JSON (meta + chapters + paragraphs) |
| `lixity dialogue FILE [--json]` | dialogue turn structure (turns, lengths, per chapter) | text / JSON |
| `lixity characters FILE --names A,B [--json]` | character presence per chapter | text / JSON |
| `lixity pacing FILE [--json]` | scenes, pacing signals, chapter hooks | text / JSON |
| `lixity motifs FILE --motif NAME=REGEX [--json]` | motif presence + repetition (words, n-grams) | text / JSON |
| `lixity showing FILE [--json]` | showing vs. telling balance per chapter | text / JSON |
| `lixity style FILE --json` | style reference (bands, deviations, dimensions, FDR) | JSON (schema v2) |
| `lixity dashboard FILE -o ui.html` | single-file HTML dashboard | file path |
| `lixity build [FILE] [--dry-run]` | idempotent workspace build into `exports/` | artifact list |
| `lixity about` | tool metadata: languages, features, heuristics | text / JSON |
| `lixity completion bash\|zsh` | shell completion script | script |

- `--language auto|de|en|fr|es|it|pt|nl|generic` – `auto` detects via function words.
- Exit codes: `0` success, `1` file/processing error, `2` usage error (argparse).
  Errors go to stderr as `[error] …` lines (`LIXITY_LANG=de` switches the
  user-facing messages to German); stdout carries only the payload.
- Report language: English by default, German via `LIXITY_LANG=de`.

## 3. JSON contracts

### 3.1 `analyze --json` (schema_version 2)

```json
{"meta": {"tool": "lixity", "version": "1.9.0", "schema_version": 2, "language": "de"},
 "metrics": {"raw_words": 55331, "asl": 9.63, "ttr": 0.1784, "guiraud_r": 41.11,
             "hd_d": 0.997, "mtld": 78.4, "mattr": 0.742, "maas_a2": 0.031,
             "flesch_de": 71.2, "flesch_variant": "Flesch Reading Ease (Amstad)",
             "staccato_pct": 38.5, "chapters": [ … ]}}
```

Tense values are **language-neutral**: `dominance` (chapters) and `dominant`
(paragraphs) are one of `present`, `past`, `mixed`, `neutral` – display labels
come from the UI label packs. `metrics.chapters[]` carries per chapter, among
these:

- `words`, `sentences`, `asl`, `dialog_pct`, `ttr`, `guiraud_r`, `hd_d`,
- style features: `staccato_pct`, `kaskade_pct`, `sentence_cv`,
  `start_entropy` (bits), `first_person_start_rate` (% of sentences),
  `function_word_pct`, `long_word_pct`,
  `filter_density`, `modal_density`, `passive_density`,
  `nominalization_density`, `adjective_density` (all per 1,000 words),
- `style_se`: standard error per feature (documented plug-in estimators:
  Poisson for count densities, binomial for shares, sample-based for
  ASL/CV/entropy/HD-D) – **use these for uncertainty-aware reasoning**,
- `jsd` (Jensen-Shannon distance of the chapter's word distribution to the
  rest of the corpus) and `jsd_top_words` (the most contributing content
  words – interpretable drivers of divergence).

Corpus-level notes:

- `mtld`, `mattr`, `maas_a2` are length-invariant lexical-diversity indices
  (`null` for texts too short to estimate them); `mattr` uses a 50-token
  window, `mtld` the standard TTR threshold of 0.72.
- `flesch_de` is the **language-calibrated** Flesch-type score of the active
  profile; `flesch_variant` names the formula used (Amstad, Flesch,
  Kandel-Moles, Szigriszt-Pazos, Franchina-Vacca, Martins, Douma).
- `punctuation` uses language-neutral keys (`periods`, `commas`, `dashes`,
  `colons`, `semicolons`, `questions`, `exclamations`, `ellipses`), so agents
  can parse them independent of the UI language.


### 3.2 `style --json` (style reference, schema_version 2)

```json
{"meta": {"schema_version": 2, "n_chapters": 25, "n_features": 16,
          "expected_false_positives": 5.0, "fdr_q": 0.05},
 "consistency": 0.98,
 "features": [{"feature": "asl", "unit": "…", "median": 9.79, "sigma": 1.8,
               "band": [6.2, 13.4], "chapters_measured": 25}, …],
 "deviations": {"20": {"dialog_pct": 5.1}, …},
 "fdr_flagged": {"20": ["dialog_pct"], …},
 "dimensions": [{"index": 1, "variance": 0.33, "loadings": {…},
                 "scores": {"1": -2.1, …}, "flagged": [1, 2, 3]}, …],
 "redundant_features": [{"a": "asl", "b": "staccato_pct", "rho": -0.93}]}
```

### 3.3 UI label packs (merge order)

The dashboard resolves labels from six packs, later packs override earlier
ones; a missing key falls back to English and then to the key itself:

1. `LABELS` – core UI terms (tense, severity, chapters, …)
2. `METRIC_LABELS` – metric names and control labels
3. `HELP_TEXTS` – tooltip texts (`help_*`)
4. `GROUP_LABELS` – KPI group captions
5. `LAYER_LABELS` – style-layer legend and guidance
6. `UI_LABELS` – cross-cutting hints (load hint, short scale words)

`tests/test_ui_contract.py` enforces that every key the renderer uses exists
in all seven languages.

### 3.4 Dashboard interaction contract (for embedding and UI automation)

The dashboard follows **one interaction model**: every content drill-down is a
keyboard-reachable `[role="button"]` element carrying a small, uniform data
vocabulary; every server control is a native `<button>`/`<select>`.

| Hook | Meaning |
|---|---|
| `data-jump="<anchor>"` | scroll to a panel/row and flash it |
| `data-layer="<key>"` | activate a style layer (paragraph colouring) |
| `data-only="1"` | additionally preselect "deviations only" |
| `data-flags="1"` | additionally preselect "flagged only" |
| `data-line="<n>"` | jump to the chapter containing that source line |
| `data-chapter="<n>"` | heatmap cell: open that chapter (with its layer) |
| `data-action="<name>"` + `data-payload="<form-id>"` | control-server action |
| `data-marker-kind="<kind>"` / `data-marker-resolve="<id>"` | set/resolve a work marker (inline note field) |
| `role="button" tabindex="0"` | every clickable non-native target (KPI tile, band row, loading bar, table row, heatmap cell) |
| `:focus-visible` | visible focus ring for all of the above (CSS covers `[role="button"]`) |

The script drives click **and** keyboard activation through one selector
(`INTERACTIVE = "[data-jump], [data-line], [role='button'], td.z[data-chapter]"`),
so a new drill-down only needs the attributes, not new JavaScript. Marker
writes go through the embedding server's action API
(`{"action": "marker-add", "kind": …, "line": …, "note": …}`); the library
itself never writes files.

### 3.5 Structure modules (`dialogue`, `characters`, `pacing`, `motifs`, `showing`)

All five return `{"meta": {...}, …}` with the same meta block; every field is
deterministic and documented in [`USAGE.md`](USAGE.md).

- `dialogue`: `turns` = quoted segments (language dialogue pattern; **no
  speaker attribution**), `avg_turn_words`, `median_turn_words`,
  `longest_turn_words`, `turns_per_1000`, `dialogue_paragraph_pct` (a
  paragraph counts as dialogue paragraph when ≥ 50 % of its words sit inside
  quotation marks), `chapters[]` with the same per chapter.
- `characters`: whole-word, case-insensitive matching of curated names or
  alias patterns (`{"Matthias|Matze": "Matthias"}`); `mentions`,
  `chapters_present`, `first_chapter`/`last_chapter`, `longest_gap` (chapters
  without mention), `presence_ratio`, `per_chapter`. Appendix and front matter
  are excluded, so chapter numbers match the metrics. **No NER** — the caller
  supplies the names.
- `pacing`: scene breaks are explicit dividers (`---`, `* * *`, `***`, `___`,
  `•••`); `scenes` per chapter = breaks + 1. `hook_score` (0–3, heuristic):
  +1 closing sentence ≤ 8 words, +1 terminal `?`/`!`/`…`, +1 closing in
  dialogue. `fastest_chapter`/`slowest_chapter` use the lowest/highest ASL.
- `motifs`: motif presence (regex patterns; `mentions`, `density_per_1000`,
  chapter span, `longest_gap`) plus generic repetition — `top_words` (content
  words; curated stop words excluded) and `repeated_phrases` (n-grams with
  ≥ 3 occurrences and their chapters). Repetition is a **signal**, not a
  verdict.
- `showing`: telling signals (filter/modal/passive/nominalisation densities)
  vs. showing signals (dialogue, staccato) as robust z against the book's own
  chapter medians; `balance = show_z − tell_z` (positive = showing).
  Documented fallback: if MAD = 0 (majority of chapters share the median), the
  standard deviation is used. Heuristic composite, **not** a quality verdict.

### 3.6 Task recipes (typical agent workflows)

| Task | Steps |
|---|---|
| First contact with a manuscript | `lixity about --json` → `lixity analyze FILE --json` → `lixity style FILE --json` |
| Editorial pass on tense | `lixity profile FILE` → paragraphs with `severity ≥ 2` and `switch = true` |
| "Why does chapter N feel different?" | `lixity style FILE --json` → `deviations["N"]` + `fdr_flagged["N"]`, then `jsd_top_words` from `analyze` |
| Dialogue overhaul | `lixity dialogue FILE --json` → chapters with low `turns`/`dialogue_pct` |
| Character continuity check | `lixity characters FILE --names "A,B,C" --json` → `longest_gap`, `presence_ratio` |
| Structural pacing review | `lixity pacing FILE --json` → `hook_score` and `fastest/slowest_chapter` |
| Repetition cleanup | `lixity motifs FILE --json` → `repeated_phrases`, `top_words` |
| Style drift in a new draft | `lixity build` (reference) → `lixity analyze draft.md --json` → compare against the corridor |
| Human-readable hand-off | `lixity dashboard FILE -o review.html --names "A,B"` |

## 4. Interpretation heuristics (documented, not black-box)

- **z*** = significance-adjusted deviation: `z* = (x − median) / √(σ² + SE²)`
  with σ = 1.4826·MAD. Small chapters have large SE – their deviations are
  shrunk, so they cannot produce false alarms.
- **Thresholds**: |z*| ≥ 2.5 noticeable, ≥ 3.5 strong. At 2.5, ~1.2 % of all
  chapter×feature cells exceed the threshold by chance; the style reference reports
  the expected count (`expected_false_positives`) – never report a deviation
  as "significant" without comparing it to this number.
- **FDR**: `fdr_flagged` is the Benjamini-Hochberg set (q = 0.05) – the cells
  that remain significant under multiplicity control. Prefer it over the raw
  `deviations` when making strong claims.
- **Dimensions**: principal components of the Spearman correlation matrix
  (Jacobi eigendecomposition, deterministic sign). They are the manuscript's
  own abstract style axes, not pre-defined registers. `flagged` chapters sit
  at |score| ≥ 2.5 on that axis. Loadings name the features that shape the
  axis; do not invent register names beyond the loadings.
- **Redundant features**: pairs with |Spearman ρ| ≥ 0.8 measure (almost) the
  same thing – do not double-count them when summarising deviations.
- **JSD driver words**: the words that most contribute to a chapter's
  divergence from the rest of the corpus – use them for concrete,
  quotable editing feedback.
- **Caveats**: per-chapter TTR is length-dependent (compare Guiraud R or
  HD-D instead); density features are heuristic counts (suffix/marker
  regexes per language profile) – comparable within one language only;
  chapters under ~200 words have noisy starter/entropy estimates (SE grows).

## 5. Python API (stable facade)

```python
from lixity import api

metrics = api.analyze(text, language="auto")          # -> {"meta", "metrics"}
profiles = api.profile(text, language="de")           # -> {"meta", "chapters", "paragraphs"}
reference = api.fingerprint(text, language="de")      # -> style reference (schema v2)
turns = api.dialogue(text, language="de")             # -> {"meta", "dialogue"}
cast = api.characters(text, ["Anna", "Ralf"], language="de")  # -> {"meta", "chapters", "figures"}
pace = api.pacing(text, language="de")                # -> {"meta", "pacing"}
motifs = api.motifs(text, {"Wut": r"\b(Wut|wütend\w*)\b"}, language="de")  # -> {"meta", "motifs", …}
distance = api.showing(text, language="de")           # -> {"meta", "showing"}
html = api.dashboard(text, language="de", title="…")  # -> self-contained HTML string
marker_list = api.markers(text)                       # -> list of active work markers
new_text, m = api.add_marker(text, kind="pruefen", note="Verify tense", line=42)
updated_text, ok = api.resolve_marker(new_text, m["id"])
info = api.about()                                    # languages, features, heuristics
```

All calls are deterministic (no timestamps, fixed HD-D seed) – identical
input yields identical output; safe for caching and idempotent tool calls.
Low-level classes remain available (`CorpusAnalyzer`, `ParagraphProfiler`,
`StyleFingerprint`, `CorpusConfig`) for callers that need the object models.

## 6. Constraints for editing workflows

- Input is UTF-8 Markdown; chapters are `## ` headings (configurable);
  the appendix starts at `## Anmerkungen und Literaturverzeichnis`
  (configurable via `CorpusConfig.appendix_marker`).
- HTML comments (`<!-- … -->`) are ignored by the analysis – use them for
  work markers that must never appear in rendered output.
- Never modify the manuscript when only reading metrics is required.
  Lixity itself is read-only for `analyze`/`profile`/`style`.
