# Lixity

[![tests](https://github.com/mfahsold/lixity/actions/workflows/tests.yml/badge.svg)](https://github.com/mfahsold/lixity/actions)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: LNCL-1.0](https://img.shields.io/badge/license-LNCL--1.0-orange)
![Dependencies](https://img.shields.io/badge/dependencies-pydantic%20%7C%20rich%20%7C%20orjson-brightgreen)

**Lixity** is an offline text-linguistics engine that measures *how a literary
manuscript reads* — and flags only the passages where a chapter departs from
the manuscript's own established voice.

It never measures against external norms. A **self-calibrating style
reference** (robust median / MAD house style) is derived from the manuscript
itself; noisy short-chapter observations are shrunk ($z^*$), false discoveries
are controlled across all chapter×feature cells (Benjamini–Hochberg or
Benjamini–Yekutieli FDR), and surviving cells carry effect sizes (Cliff's
$\delta$) plus exchangeability diagnostics (runs test, lag-1 ACF). The result
is macro-editing evidence, not style dogma.

Pure Python (3.10+), zero cloud calls, three dependencies (`pydantic`,
`rich`, `orjson`), seven native language profiles. Formal methods live in
[`docs/METHODS.md`](docs/METHODS.md); stability caveats in
[`docs/STABILITY.md`](docs/STABILITY.md). The name stands for the
mathematical foundation: **T**TR, **Y**ule's characteristic $K$, and **LIX**.

![Lixity interactive HTML dashboard](docs/screenshots/dashboard-light.png)

![Lixity CLI analysis report](docs/screenshots/cli-analyze.png)

## Mathematical core

| Estimator | Role |
| :--- | :--- |
| Robust baseline $\tilde{x},\ \mathrm{MAD},\ \sigma = 1.4826\cdot\mathrm{MAD}$ | house-style band per feature |
| Noise-aware $z^* = (x-\tilde{x})/\sqrt{\sigma^2+\mathrm{SE}^2}$ | shrinks short-chapter noise |
| BH / BY FDR at $q$ (default 0.05) | multiplicity-controlled `fdr_flagged` |
| Expected FP $= m\cdot P(\lvert Z\rvert\ge z_{\mathrm{mild}})$ | calibration against over-reading |
| Cliff's $\delta$ / Vargha–Delaney $\hat{A}_{12}$ | magnitude of confirmed cells |
| Runs test + lag-1 $\rho_1$ | exchangeability of the baseline |
| Spearman $\rho$ + cyclic Jacobi EVD | latent style dimensions |
| PELT changepoints (BIC) | where the house style shifts (structural) |
| Mann–Kendall $\tau, S, p$ | monotonic style drift (structural) |
| Sn / Qn (Rousseeuw & Croux) | outlier-resistant scale cross-check |
| Hill $\hat\alpha$ | heavy-tailed feature diagnostic |
| Wasserstein-1D + two-sample KS | early/late chapter-half shift (structural) |
| Dunning $G^2$ + co-occurrence fitness | early/late keyness, Goh–Barabási on content-word graph (structural) |

Thresholds (`z_mild`, `z_strong`, `fdr_q`, `fdr_method`, `dim_score_threshold`,
`flag_min_severity`) are injectable via CLI, API kwargs, UI settings, or
`[tool.lixity]` project config — resolution order documented in
[`docs/METHODS.md`](docs/METHODS.md).

## Key capabilities

- **Offline & deterministic:** identical input → byte-identical metrics, JSON, HTML.
- **Self-calibrating norms:** house style from the manuscript’s own median/MAD.
- **Noise-aware $z^*$ + FDR (BH/BY)** with injectable thresholds.
- **Effect sizes & diagnostics** on every confirmed cell (Cliff’s δ, runs, ACF).
- **Structural diagnostics:** PELT changepoints, Mann–Kendall trends, Sn/Qn scales, Hill tail index, early/late Wasserstein–KS shift, content-word co-occurrence (Goh–Barabási) and Dunning keyness.
- **Latent style dimensions:** Spearman ρ + cyclic Jacobi (stdlib only).
- **Paragraph tense profiling:** present/past/mixed/neutral, severity 0–3.
- **Structure modules:** dialogue, characters, pacing, motifs, showing/telling.
- **Idempotent build & single-file dashboard** with seven language profiles.
- **Agent-ready:** strict JSON schemas (analyze/profile **v2**, style **v3**),
  stable `lixity.api`, [`docs/AGENTS.md`](docs/AGENTS.md).

## Installation

Requires Python **3.10+**. Lixity is source-available (LNCL-1.0), not on
PyPI — install from GitHub:

```bash
# recommended: isolated tool environment (pipx or uv)
pipx install git+https://github.com/mfahsold/lixity.git
uv tool install git+https://github.com/mfahsold/lixity.git

# plain pip (user or venv)
pip install git+https://github.com/mfahsold/lixity.git

# pin a release for reproducible pipelines
pip install "git+https://github.com/mfahsold/lixity.git@v1.11.0"
```

Development install (editable, with lint/type/test tooling):

```bash
git clone https://github.com/mfahsold/lixity.git && cd lixity
make install-dev        # venv + pip install -e ".[dev]"
make check              # ruff + mypy --strict + pytest -W error

# or without make
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Shell completion after install:

```bash
lixity completion bash > ~/.local/share/bash-completion/completions/lixity
lixity completion zsh  > "${fpath[1]}/_lixity"
```

## Quick start

```bash
lixity analyze manuscript.md            # Rich terminal report (--json for machines)
lixity profile manuscript.md            # tense continuity, paragraph by paragraph
lixity style manuscript.md              # style reference (BH/BY, δ, diagnostics)
lixity dialogue manuscript.md           # turn structure
lixity characters manuscript.md --names "Anna,Ralf"
lixity pacing manuscript.md             # scenes, pacing, hooks
lixity motifs manuscript.md --motif 'Wut=\b(Wut|wütend\w*)\b'
lixity showing manuscript.md            # showing/telling per chapter
lixity dashboard manuscript.md -o exports/dashboard.html
cd my-novel && lixity build             # idempotent workspace: exports/ + archive
lixity about                            # languages, features, heuristics
```

Common sensitivity flags (on `style` / `dashboard` / `build`):

```bash
lixity style manuscript.md --json \
  --z-mild 2.5 --z-strong 3.5 --fdr-q 0.05 --fdr-method bh \
  --dim-threshold 2.5 --flag-min-severity 2
```

Project defaults: put the same keys under `[tool.lixity]` in
`pyproject.toml`, or in `lixity.toml` / `~/.config/lixity.toml`
(CLI > UI session > project > user > defaults).


Try it on the bundled public-domain samples:

```bash
lixity analyze samples/effi-briest.md          # German – Fontane, 36 chapters
lixity analyze samples/pride-and-prejudice.md  # English – Austen, 61 chapters
```

Reports and CLI messages are English by default; `LIXITY_LANG=de` switches them to German.

Full command reference, metric glossary, worked example and troubleshooting:
[`docs/USAGE.md`](docs/USAGE.md). Agent-facing JSON contracts:
[`docs/AGENTS.md`](docs/AGENTS.md). Site overview:
[mfahsold.github.io/lixity](https://mfahsold.github.io/lixity/).

![Lixity style layer overlay](docs/screenshots/dashboard-layer.png)

## What Lixity measures

Five groups, formulas and caveats in [`docs/USAGE.md`](docs/USAGE.md#understanding-the-metrics)
and [`docs/METHODS.md`](docs/METHODS.md):

1. **Sentence architecture & rhythm** – ASL, staccato/parataxis/hypotaxis, CV, punctuation.
2. **Lexical diversity** – TTR, Guiraud $R$, HD-D, MTLD, MATTR, Maas $a^2$, Yule $K$ (length-guarded).
3. **Readability** – language-calibrated Flesch family + LIX (Björnsson >6 characters).
4. **Narrative voice & register** – dialogue, function words, perception filters, modals,
   passive, nominalisations, adjectives, starter entropy, first-person starts.
5. **Tense dynamics** – per-paragraph dominance and friction severity 0–3.

## Work markers (editor-visible)

Markers are HTML comment lines placed directly above the target paragraph:

```markdown
<!-- LIXITY-MARKER id="m-7f8a1c9b" kind="pruefen" note="Tempusprüfung" created="…" -->
Er ging zum Fenster und sieht den Regen fallen.
```

- Visible in VS Code, Obsidian, Neovim, Ulysses; **invisible in every export**
  (Pandoc, Typst, LaTeX treat HTML comments as comments).
- Deterministic content-hash IDs stay anchored when surrounding text changes.
- Clicking a marker kind in the control dashboard opens an inline note field
  (`Enter` saves, `Esc` cancels).
- Programmatic access: `api.markers`, `api.add_marker`, `api.resolve_marker`.

![Lixity work markers](docs/screenshots/dashboard-markers.png)

## Python API for AI agents

```python
from lixity import api

metrics = api.analyze(text, language="auto")          # {"meta", "metrics"}
profiles = api.profile(text, language="de")           # {"meta", "chapters", "paragraphs"}
reference = api.fingerprint(text, language="de")      # style reference (schema v4)
html = api.dashboard(text, language="de", title="My Manuscript")
new_text, marker = api.add_marker(text, kind="pruefen", note="Verify tense", line=142)
updated_text, ok = api.resolve_marker(new_text, marker["id"])
info = api.about()                                    # languages, features, heuristics
```

Machine-readable surfaces:

| Need | Surface |
| :--- | :--- |
| Corpus metrics | `lixity analyze FILE --json` (meta block, schema_version 2) |
| Paragraph profiles | `lixity profile FILE` (schema_version 2) |
| Style reference (bands, z\*, FDR, effect sizes, structural) | `lixity style FILE --json` (**schema_version 4**) |
| Reproducible artifact set | `lixity build [FILE] [--dry-run]` |
| Capability discovery | `lixity about --json` |
| Shell completion | `lixity completion bash\|zsh` |
| LLM-friendly site summary | [`docs/llms.txt`](docs/llms.txt) |

Contracts, interpretation heuristics and dashboard DOM hooks:
[`docs/AGENTS.md`](docs/AGENTS.md). Known limitations:
[`docs/STABILITY.md`](docs/STABILITY.md).

## Languages

| Code | Language | Tense detection | Readability |
| :---: | :--- | :--- | :--- |
| `de` | German | Präsens / Präteritum | Flesch (Amstad) + LIX |
| `en` | English | Present / Past | Flesch + LIX |
| `fr` | French | Présent / Imparfait / Passé | Flesch (Kandel-Moles) + LIX |
| `es` | Spanish | Presente / Pasado | Flesch (Szigriszt-Pazos) + LIX |
| `it` | Italian | Presente / Passato | Flesch (Franchina-Vacca) + LIX |
| `pt` | Portuguese | Presente / Pretérito | Flesch (Martins) + LIX |
| `nl` | Dutch | O.T.T. / O.V.T. | Flesch (Douma) + LIX |
| `generic` | Fallback | minimal | LIX |

`--language auto` detects via function-word distribution. Adding a language is
one `LanguageProfile` entry – no algorithmic change.

## Implementation principles

Estimator catalogue (HD-D samples, Yule $K$, Miller–Madow, cyclic Jacobi,
BH/BY, Cliff’s δ): [`docs/METHODS.md`](docs/METHODS.md).

## FAQ

<details>
<summary><b>Why not compare against an external corpus?</b></summary>
A literary manuscript has its own aesthetic. Measuring it against "average
newspaper German" produces meaningless critique; Lixity discovers what is
normal <i>for this book</i>.
</details>

<details>
<summary><b>Does it work for non-fiction?</b></summary>
Yes – rhythm, lexical richness, readability and the style reference apply to
essays, dissertations, memoirs and documentation as well.
</details>

<details>
<summary><b>Can it run in CI pipelines?</b></summary>
Yes: offline, deterministic, POSIX exit codes (0 / 1 / 2), byte-identical JSON
for identical input.
</details>

## License & attribution

**Lixity Non-Commercial License 1.0 (LNCL-1.0)** – *source-available, not open
source*: free for research, education, personal writing and clearly
non-commercial open science. Commercial use requires a written license
(mfahsold@googlemail.com). Full terms: [`LICENSE`](LICENSE); the license text
must be kept with every copy. Security reports: [`SECURITY.md`](SECURITY.md).
Contributing: [`CONTRIBUTING.md`](CONTRIBUTING.md).

Third-party components (all permissive): [pydantic](https://github.com/pydantic/pydantic)
(MIT), [rich](https://github.com/Textualize/rich) (MIT),
[orjson](https://github.com/ijl/orjson) (MIT/Apache-2.0).

Sample corpus: `samples/` ships two **public-domain** works for testing and
demos — Fontane's *Effi Briest* (German, [Project Gutenberg #5323](https://www.gutenberg.org/ebooks/5323))
and Austen's *Pride and Prejudice* (English, [#1342](https://www.gutenberg.org/ebooks/1342)) —
each as an unmodified Project Gutenberg source file plus a Markdown
conversion. They are **not** relicensed by the LNCL; the original sequel
draft in `samples/effi-briest-folge/` is the author's own work. Provenance and
license details: [`samples/README.md`](samples/README.md).

Contact: **Matthias Fahsold** ([mfahsold@googlemail.com](mailto:mfahsold@googlemail.com))
