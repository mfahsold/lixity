# AGENTS.md – Lixity interface for AI agents and automation

Guidance for AI agents (and other programs) that use Lixity as a tool:
which commands to call, how to interpret the JSON, and which heuristics
govern the numbers.

## 1. What Lixity does (one paragraph)

Lixity turns a Markdown manuscript into quantitative text linguistics:
sentence rhythm, lexical diversity, readability, dialogue share,
paragraph-accurate tense profiles, and a **self-calibrating style passport**.
It never judges style against external norms – it derives the manuscript's
own house style (robust median/MAD per feature) and flags only deviations
from that style, controlled for measurement noise and multiple testing.

## 2. Commands

| Command | Purpose | Output |
|---|---|---|
| `lixity analyze FILE --json` | corpus metrics + per-chapter style features | JSON (meta + metrics) |
| `lixity profile FILE` | paragraph-accurate tense/style profiles | JSON (meta + chapters + paragraphs) |
| `lixity style FILE --json` | style passport (bands, deviations, dimensions, FDR) | JSON (passport, schema v2) |
| `lixity dashboard FILE -o ui.html` | single-file HTML dashboard | file path |
| `lixity about` | tool metadata: languages, features, heuristics | text / JSON |
| `lixity completion bash\|zsh` | shell completion script | script |

- `--language auto|de|en|fr|es|it|pt|nl|generic` – `auto` detects via function words.
- Exit codes: `0` success, `1` file/processing error, `2` usage error (argparse).
  Errors go to stderr as `[Fehler] …` lines; stdout carries only the payload.

## 3. JSON contracts

### 3.1 `analyze --json` (schema_version 1)

```json
{"meta": {"tool": "lixity", "version": "1.1.0", "schema_version": 1, "language": "de"},
 "metrics": {"raw_words": 55331, "asl": 9.63, "ttr": 0.1784, "guiraud_r": 41.11,
             "hd_d": 0.997, "staccato_pct": 38.5, "chapters": [ … ]}}
```

`metrics.chapters[]` carries per chapter, among others:

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

### 3.2 `style --json` (passport, schema_version 2)

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

## 4. Interpretation heuristics (documented, not black-box)

- **z*** = significance-adjusted deviation: `z* = (x − median) / √(σ² + SE²)`
  with σ = 1.4826·MAD. Small chapters have large SE – their deviations are
  shrunk, so they cannot produce false alarms.
- **Thresholds**: |z*| ≥ 2.5 noticeable, ≥ 3.5 strong. At 2.5, ~1.2 % of all
  chapter×feature cells exceed the threshold by chance; the passport reports
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
passport = api.fingerprint(text, language="de")       # -> passport dict (schema v2)
html = api.dashboard(text, language="de", title="…")  # -> self-contained HTML string
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
