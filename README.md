# Lixity

**Lixity** is a dependency-light, multilingual text-analysis engine for literary
manuscripts: quantitative text linguistics, stylometry, readability indices,
paragraph-accurate tense profiles and a **self-calibrating style passport** –
as a colour-coded terminal report, machine-readable JSON, a Python API for AI
agents, or a single-file HTML dashboard. Offline, deterministic, seven languages.

The name is an acronym of its mathematical core: **T**TR (Type-Token Ratio),
**Y**ule's characteristic K and **LIX** (Lasbarhetsindex).

![Lixity CLI report](docs/screenshots/cli-analyze.png)

## What Lixity measures

- **Sentence rhythm** – sentence-length architecture from staccato fragments
  (<= 6 words) to complex hypotaxes (> 25 words), ASL, median, standard
  deviation and the coefficient of variation, plus punctuation density.
- **Lexical diversity** – TTR, Guiraud R and **HD-D** (McCarthy & Jarvis 2010)
  as length-robust measures, Yule's K for vocabulary stability.
- **Readability** – Flesch Reading Ease (German Amstad adaptation) and LIX.
- **Register signals** – dialogue share, function-word ratio, perception
  filters (show, don't tell), modal verbs, passive markers, nominalisation and
  adjective density, sentence-starter entropy and first-person start rate.
- **Tense profiles** – present/past dominance per paragraph with line anchors,
  switch/mix detection and severity flags.
- **Style passport** – the manuscript's *own* house style, self-calibrated via
  robust statistics (median/MAD). Sixteen descriptive features, significance-
  adjusted deviations (z* with measurement uncertainty), Benjamini-Hochberg
  FDR control, and self-calibrated **style dimensions** (Spearman correlation
  + Jacobi eigendecomposition) – no pre-defined registers, only the author's
  own axes.
- **Work markers** – set editor-visible markers from the dashboard
  (`<!-- LIXITY-MARKER ... -->` inline comments with stable IDs) that never
  render in exports and move with the paragraph when editing.

## Install

```bash
pip install git+https://github.com/mfahsold/lixity.git
```

Requires Python 3.10+; dependencies: pydantic, rich, orjson.

## Usage

```bash
lixity analyze manuscript.md              # corpus metrics (Rich report)
lixity analyze manuscript.md --json       # self-describing JSON (meta + metrics)
lixity profile manuscript.md              # tense/style profiles per paragraph
lixity style manuscript.md                # self-calibrated style passport
lixity style manuscript.md --json         # passport JSON (bands, deviations, FDR, dimensions)
lixity dashboard manuscript.md -o ui.html # single-file HTML dashboard
lixity about                              # languages, features, heuristics
lixity completion bash                    # shell completion (bash/zsh)
```

### Python API (stable facade for AI agents and automation)

```python
from lixity import api

metrics = api.analyze(text, language="auto")          # -> {"meta", "metrics"}
profiles = api.profile(text, language="de")           # -> {"meta", "chapters", "paragraphs"}
passport = api.fingerprint(text, language="de")       # -> passport dict (schema v2)
html = api.dashboard(text, language="de", title="...") # -> self-contained HTML
info = api.about()                                    # -> languages, features, heuristics
new_text, marker = api.add_marker(text, "pruefen", "Tempus prüfen", line=47)
```

All calls are deterministic – identical input yields identical output.
Full contracts: [docs/AGENTS.md](docs/AGENTS.md) and
[docs/USAGE.md](docs/USAGE.md).

## Languages

`de`, `en`, `fr`, `es`, `it`, `pt`, `nl` plus a `generic` fallback; `auto`
detects the language via function words. New languages are registered as one
data entry (`LanguageProfile`) – no code changes.

## License

**Lixity Non-Commercial License 1.0 (LNCL-1.0)** – free for research, teaching
and clearly non-commercial projects. Commercial use only with a written
license on request: **mfahsold@googlemail.com**. Source-available, explicitly
not an OSI open-source license.