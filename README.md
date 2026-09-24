# Lixity

[![tests](https://github.com/mfahsold/lixity/actions/workflows/tests.yml/badge.svg)](https://github.com/mfahsold/lixity/actions)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: LNCL-1.0](https://img.shields.io/badge/license-LNCL--1.0-orange)
![Dependencies](https://img.shields.io/badge/dependencies-pydantic%20%7C%20rich%20%7C%20orjson-brightgreen)

**Lixity** is an offline text-linguistics engine that quantitatively measures *how a literary manuscript reads* — sentence rhythm, length-invariant lexical diversity, narrative distance, tense continuity, and register signals — and precisely flags only those passages where a chapter departs from its own established voice.

Lixity never measures against arbitrary external corpora or generic newspaper prose. Instead, a **self-calibrating style reference** (robust median and MAD as house style) is derived directly from the manuscript itself. Observations from shorter chapters are stabilized via noise-aware significance shrinkage (z\*), while multiplicity across chapter × feature cells is strictly controlled using Benjamini–Hochberg or Benjamini–Yekutieli FDR. Confirmed departures carry standardized non-parametric effect sizes (Cliff’s δ) alongside exchangeability diagnostics (Runs test, Lag-1 ACF). The result is empirical evidence for macro-editing and developmental line editing — not rigid dogma.

Pure Python (3.10+), zero cloud calls, three runtime dependencies (`pydantic`, `rich`, `orjson`), seven native language profiles. Formal mathematical estimators are documented in [`docs/METHODS.md`](docs/METHODS.md); empirical stability boundaries in [`docs/STABILITY.md`](docs/STABILITY.md). The name reflects its mathematical roots: **T**TR, **Y**ule's characteristic K, and **LIX**.

<p align="center">
  <img src="docs/screenshots/dashboard-light.png" alt="Lixity Interactive Stylometry Dashboard" width="100%" />
</p>

## Mathematical Core

| Estimator / Method | Role in System |
| :--- | :--- |
| Robust baseline x̃, MAD, σ = 1.4826 · MAD | Manuscript-intrinsic house-style corridor per feature |
| Noise-aware z\* = (x − x̃) / √(σ² + SE²) | Shrinks sampling noise in short chapters via analytical SE |
| BH / BY FDR at q (default: 0.05) | Multiplicity-controlled `fdr_flagged` cells |
| Expected FP = m · P(\|Z\| ≥ z_mild) | Calibration against statistical over-interpretation |
| Cliff’s δ / Vargha–Delaney Â₁₂ | Standardized non-parametric effect size for confirmed cells |
| Runs test + Lag-1 ρ₁ | Exchangeability diagnostics (I.I.D. baseline assumption) |
| Spearman ρ + cyclic Jacobi EVD | Latent style dimensions and principal axes (pure stdlib) |
| PELT changepoints (BIC) | Locates structural regime shifts in the house style |
| Mann–Kendall τ, S, p | Detects monotonic feature drift across chapter progression |
| Sn / Qn (Rousseeuw & Croux) | Outlier-resistant alternative scale cross-checks to MAD |
| Hill tail index (α̂) | Diagnostics for heavy-tailed feature distributions |
| 1D Wasserstein + 2-sample KS | Distributional shift between early and late manuscript halves |
| Dunning G² + Co-occurrence fitness | Lexical keyness and Goh–Barabási network architecture |

Thresholds (`z_mild`, `z_strong`, `fdr_q`, `fdr_method`, `dim_score_threshold`, `flag_min_severity`) are fully configurable via CLI flags, API kwargs, UI settings, or `[tool.lixity]` project configuration (resolution order in [`docs/METHODS.md`](docs/METHODS.md)).

## Key Capabilities

- **Offline & Deterministic:** Identical input produces bit-identical metrics, JSON, and HTML reports.
- **Self-Calibrating Norms:** House style derived from the manuscript's own median and MAD bands.
- **Noise-Aware z\* + FDR (BH/BY):** Controlled false discovery rate with configurable severity cuts.
- **Effect Sizes & Diagnostics:** Cliff’s δ, Runs test, and lag-1 autocorrelation for every confirmed cell.
- **Structural Diagnostics:** PELT changepoints, Mann–Kendall trends, Sn/Qn scales, Hill tail index, Wasserstein–KS shift, Goh–Barabási co-occurrence graphs, and Dunning G² keyness.
- **Latent Style Dimensions:** Spearman rank correlation and cyclic Jacobi eigendecomposition (pure Python stdlib).
- **Paragraph-Accurate Tense Profiling:** Present, past, mixed, neutral with a 0–3 friction severity scale.
- **Narratological Structure Modules:** Dialogue turn structure, character presence, scene/pacing curves, motifs, and showing vs. telling balance.
- **Idempotent Workspace Build & Dashboard:** Fully self-contained, single-file interactive HTML dashboard with 7 language profiles.
- **AI Agent-Ready:** Strict JSON schemas (analyze/profile **v2**, style **v4**), stable `lixity.api` facade, [`docs/AGENTS.md`](docs/AGENTS.md).

## Visual Overview

| Departure Heatmap (Noise-Aware z* & FDR) | Paragraph Style Layer Overlay |
| :---: | :---: |
| <img src="docs/screenshots/dashboard-heatmap.png" alt="z* deviation heatmap" width="100%" /> | <img src="docs/screenshots/dashboard-layer.png" alt="Paragraph style overlay" width="100%" /> |
| *Significance-adjusted departures from house style* | *Sentence rhythm & syntactic density mapped in context* |

| Unsupervised Style Dimensions | Editor-Visible Work Markers |
| :---: | :---: |
| <img src="docs/screenshots/dashboard-dimensions.png" alt="Unsupervised style dimensions" width="100%" /> | <img src="docs/screenshots/dashboard-markers.png" alt="Editor work markers" width="100%" /> |
| *Spearman correlation & cyclic Jacobi EVD (pure stdlib)* | *Persistent content-hashed `<!-- LIXITY-MARKER -->` tags* |

| CLI Corpus Diagnostics | Self-Calibrating Style Reference |
| :---: | :---: |
| <img src="docs/screenshots/cli-analyze.png" alt="CLI analyze output" width="100%" /> | <img src="docs/screenshots/cli-style.png" alt="CLI style reference" width="100%" /> |
| *Rich terminal metrics and chapter overview* | *Median/MAD corridor, z* shrinkage, and effect sizes* |

<details>
<summary><b>View Dashboard in Dark Mode</b></summary>
<p align="center">
  <img src="docs/screenshots/dashboard-dark.png" alt="Lixity Dashboard Dark Mode" width="100%" />
</p>
</details>

## Installation

Requires Python **3.10+**. Lixity is source-available (LNCL-1.0), not on PyPI, and installed directly from GitHub:

```bash
# Recommended: Isolated tool environment (pipx or uv)
pipx install git+https://github.com/mfahsold/lixity.git
uv tool install git+https://github.com/mfahsold/lixity.git

# Regular pip (in active virtual environment)
pip install git+https://github.com/mfahsold/lixity.git

# Pinned release for reproducible pipelines
pip install "git+https://github.com/mfahsold/lixity.git@v1.14.0"
```

Development installation (editable, with test and typing tools):

```bash
git clone https://github.com/mfahsold/lixity.git && cd lixity
make install-dev        # venv + pip install -e ".[dev]"
make check              # ruff + mypy --strict + pytest -W error

# or without make
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
```

Shell completion (Bash / Zsh):

```bash
lixity completion bash > ~/.local/share/bash-completion/completions/lixity
lixity completion zsh  > "${fpath[1]}/_lixity"
```

## Quick Start

```bash
lixity analyze manuscript.md            # Rich terminal report (--json for machines)
lixity profile manuscript.md            # Tense continuity, paragraph by paragraph
lixity style manuscript.md              # Style reference (BH/BY, δ, diagnostics)
lixity dialogue manuscript.md           # Turn structure and speech ratio per chapter
lixity characters manuscript.md --names "Anna,Ralf" # Character presence
lixity pacing manuscript.md             # Scenes, tempo, and chapter hooks
lixity motifs manuscript.md --motif 'Wut=\b(Wut|wütend\w*)\b' # Motifs & repetition
lixity showing manuscript.md            # Showing vs. telling per chapter
lixity dashboard manuscript.md -o exports/dashboard.html # Interactive HTML dashboard
cd my-novel && lixity build             # Idempotent workspace: exports/ + archive
lixity about                            # Languages, heuristics, and metadata
```

Common sensitivity flags (for `style`, `dashboard`, and `build`):

```bash
lixity style manuscript.md --json \
  --z-mild 2.5 --z-strong 3.5 --fdr-q 0.05 --fdr-method bh \
  --dim-threshold 2.5 --flag-min-severity 2
```

Project-wide defaults: place the same keys under `[tool.lixity]` in
`pyproject.toml`, or in `lixity.toml` / `~/.config/lixity.toml`
(CLI flag > UI session > project config > user config > code defaults).

Test with the bundled public-domain samples:

```bash
lixity analyze samples/effi-briest.md          # German – Fontane, 36 chapters
lixity analyze samples/pride-and-prejudice.md  # English – Austen, 61 chapters
```

Reports and CLI messages appear in English by default; `LIXITY_LANG=de` switches them to German.

Full command reference, metric glossary, worked example, and troubleshooting:
[`docs/USAGE.md`](docs/USAGE.md). Agent-facing JSON contracts:
[`docs/AGENTS.md`](docs/AGENTS.md). Project website:
[mfahsold.github.io/lixity](https://mfahsold.github.io/lixity/).

## What Lixity Measures

Detailed formulas, mathematical derivations, and academic citations are documented in [`docs/METHODS.md`](docs/METHODS.md) and [`docs/USAGE.md`](docs/USAGE.md#understanding-the-metrics):

1. **Sentence Architecture & Rhythm** – Average sentence length (ASL), coefficient of variation (CV), and distribution across four syntactic length tiers (staccato ≤ 6 words, medium 7–15, long 16–25, complex hypotaxis > 25 words). Uncovers pacing ruptures, breathlessness, and rhythmic monotony.
2. **Length-Invariant Lexical Diversity** – Type-Token Ratio (TTR), Guiraud R, hypergeometric HD-D (McCarthy & Jarvis 2010), MTLD, moving-average MATTR, Maas a², and Yule's characteristic K. Guarded by strict token floors so short scenes and expansive chapters remain comparable without sample-size distortion.
3. **Language-Calibrated Readability** – Standard LIX (Björnsson, words > 6 characters for all languages) and language-specific calibrated Flesch variants: Amstad (de), classic Flesch (en), Kandel-Moles (fr), Szigriszt-Pazos (es), Franchina-Vacca (it), Martins (pt), and Douma (nl).
4. **Narrative Voice & Register** – Dialogue ratio, function-word density (the author's implicit grammatical fingerprint), perception filters ("telling" verbs like *saw*, *heard*, *felt*), modal hedging, passive voice, nominal style suffixes, sentence-starter Shannon entropy, and first-person openings.
5. **Tense Dynamics & Continuity** – Paragraph-accurate classification into dominant tense (present, past, mixed, neutral) with a 4-tier friction severity rating (0–3) to flag unintended slips between epic past and scenic present.

## Work Markers (Editor-Visible)

Work markers are standard HTML comment lines placed directly above the target paragraph:

```markdown
<!-- LIXITY-MARKER id="m-7f8a1c9b" kind="pruefen" note="Verify tense shift" created="…" -->
He walked to the window and watches the rain falling outside.
```

- Visible in VS Code, Obsidian, Neovim, Ulysses; **completely invisible in book exports**
  (Pandoc, Typst, and LaTeX treat HTML comments natively as comments).
- Deterministic content-hash IDs remain anchored even as surrounding text shifts during revision.
- Clicking a marker kind in the dashboard opens an inline note field directly in the document
  (`Enter` saves, `Esc` cancels).
- Programmatic access via `api.markers`, `api.add_marker`, and `api.resolve_marker`.

![Lixity work markers](docs/screenshots/dashboard-markers.png)

## Python API for AI Agents

```python
from lixity import api

metrics = api.analyze(text, language="auto")          # {"meta", "metrics"}
profiles = api.profile(text, language="en")           # {"meta", "chapters", "paragraphs"}
reference = api.fingerprint(text, language="en")      # Style reference (schema v4)
html = api.dashboard(text, language="en", title="My Novel")
new_text, marker = api.add_marker(text, kind="pruefen", note="Check tense", line=142)
updated_text = api.resolve_marker(new_text, marker["id"])
info = api.about()                                    # Languages, features, heuristics
```

Machine-readable surfaces:

| Need | Surface |
| :--- | :--- |
| Whole-corpus metrics | `lixity analyze FILE --json` (meta block, schema_version 2) |
| Paragraph profiles | `lixity profile FILE` (schema_version 2) |
| Style reference (bands, z\*, FDR, effect sizes, structural) | `lixity style FILE --json` (**schema_version 4**) |
| Reproducible artifact set | `lixity build [FILE] [--dry-run]` |
| Capability discovery | `lixity about --json` |
| Shell completion | `lixity completion bash\|zsh` |
| LLM-friendly summary | [`docs/llms.txt`](docs/llms.txt) |

Interface contracts, interpretation heuristics, and dashboard DOM hooks:
[`docs/AGENTS.md`](docs/AGENTS.md). Known limitations and stability boundaries:
[`docs/STABILITY.md`](docs/STABILITY.md).

## Supported Languages

| Code | Language | Tense Detection | Readability |
| :---: | :--- | :--- | :--- |
| `de` | German | Präsens / Präteritum | Flesch (Amstad) + LIX |
| `en` | English | Present / Past | Flesch + LIX |
| `fr` | French | Présent / Imparfait / Passé | Flesch (Kandel-Moles) + LIX |
| `es` | Spanish | Presente / Pasado | Flesch (Szigriszt-Pazos) + LIX |
| `it` | Italian | Presente / Passato | Flesch (Franchina-Vacca) + LIX |
| `pt` | Portuguese | Presente / Pretérito | Flesch (Martins) + LIX |
| `nl` | Dutch | O.T.T. / O.V.T. | Flesch (Douma) + LIX |
| `generic` | Fallback | Minimal | LIX |

`--language auto` detects the language automatically from function-word distributions. Adding a new language requires only a single `LanguageProfile` registration — no algorithm changes needed.

## Frequently Asked Questions (FAQ)

<details>
<summary><b>Why doesn't Lixity compare against an external reference corpus?</b></summary>
A literary manuscript creates its own aesthetic world and stylistic conventions. Comparing a gothic novel or experimental prose against "average contemporary journalism" or corporate corpora generates misplaced criticism and flattens authorial voice. Lixity determines what is normal <i>for this specific work</i>, establishing reference corridors from the manuscript's own median and MAD distributions.
</details>

<details>
<summary><b>How does noise-aware z* shrinkage prevent false alarms in short chapters?</b></summary>
Short scenes (e.g., 200 words) naturally exhibit high sampling variance; under naive statistics, they are almost invariably flagged as extreme outliers. Lixity calculates the analytical standard error (SE) for every feature and applies <b>noise-aware z\* significance shrinkage</b>: <code>z\* = (x − x̃) / √(σ² + SE²)</code>. The greater the estimation uncertainty of a short chapter, the more heavily its deviation is shrunk toward zero — reliably preventing sample-size false alarms.
</details>

<details>
<summary><b>How do work markers integrate into author workflows and book exports?</b></summary>
Work markers are inserted as standard HTML comments (<code>&lt;!-- LIXITY-MARKER id="..." kind="..." note="..." --&gt;</code>) directly above the target paragraph. They are fully visible and editable in plain-text editors (VS Code, Obsidian, Neovim, Ulysses), yet completely ignored by document compilers (Pandoc, Typst, LaTeX) when generating PDF, EPUB, or print output.
</details>

<details>
<summary><b>Is Lixity suitable for non-fiction, essays, and scholarly manuscripts?</b></summary>
Yes. Sentence rhythm architecture, lexical richness, readability indices, and self-calibrating consistency analysis apply equally well to essays, dissertations, memoirs, long-form journalism, and technical documentation.
</details>

<details>
<summary><b>Can Lixity run in automated CI/CD and publishing pipelines?</b></summary>
Yes. Lixity operates entirely offline, executes no network calls, runs on pure Python, produces bit-identical JSON and HTML outputs for identical inputs, and follows standard POSIX exit codes (0 = success, 1 = processing error, 2 = CLI usage error).
</details>

## Licensing, Commercial Inquiries & Location

Lixity is distributed under a dual-licensing model engineered for independent creative freedom, academic research, and commercial software integration:

- **Non-Commercial Edition (LNCL-1.0):** Free for independent novelists, creative writers, academic researchers, digital humanities scholars, and non-commercial open science projects. Full terms: [`LICENSE`](LICENSE); the license text must accompany every copy.
- **Commercial & Enterprise Licensing:** Required for commercial book publishing houses, literary agencies, writing software developers, and enterprise editorial platforms integrating Lixity into commercial products, SaaS platforms, or proprietary AI pipelines. Commercial licenses include commercial deployment rights, technical integration support, priority issue resolution, and bespoke language profile training.

### Inquiries & Support

| Attribute | Details |
| :--- | :--- |
| **Maintainer & Lead Architect** | **Matthias Fahsold** |
| **Location & Jurisdiction** | **Hamburg, Germany** (Central European Time, UTC+1 / UTC+2) |
| **Direct Contact** | [mfahsold@googlemail.com](mailto:mfahsold@googlemail.com?subject=Lixity%20Commercial%20Inquiry) |
| **Response Window** | Typically within 24–48 business hours (Mon–Fri) |
| **Security Advisories** | [`SECURITY.md`](SECURITY.md) |
| **Contributing Guide** | [`CONTRIBUTING.md`](CONTRIBUTING.md) |

Third-party components (all permissively licensed): [pydantic](https://github.com/pydantic/pydantic) (MIT), [rich](https://github.com/Textualize/rich) (MIT), [orjson](https://github.com/ijl/orjson) (MIT/Apache-2.0).

Sample corpus: `samples/` includes two **public-domain** works for testing and demonstration — Fontane's *Effi Briest* (German, [Project Gutenberg #5323](https://www.gutenberg.org/ebooks/5323)) and Austen's *Pride and Prejudice* (English, [#1342](https://www.gutenberg.org/ebooks/1342)) — each provided as an unmodified Project Gutenberg source file and as a clean Markdown conversion. These sample texts are **not** relicensed under the LNCL; the original sequel draft under `samples/effi-briest-folge/` is the author's own work. Provenance and license details: [`samples/README.md`](samples/README.md).

