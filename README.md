# Lixity

[![tests](https://github.com/mfahsold/lixity/actions/workflows/tests.yml/badge.svg)](https://github.com/mfahsold/lixity/actions)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: LNCL-1.0](https://img.shields.io/badge/license-LNCL--1.0-orange)
![Dependencies](https://img.shields.io/badge/dependencies-pydantic%20%7C%20rich%20%7C%20orjson-brightgreen)

**Explore sentence rhythm, vocabulary and tense across your manuscript.**
Lixity turns Markdown into an offline, interactive dashboard. Compare chapters
against the manuscript's own style, then inspect the passages behind each signal.

Python 3.10+ · Seven language profiles · No cloud calls.

**Free only for non-commercial projects.** Using Lixity for a book intended
for sale—including self-publishing—requires a separate written commercial
license. [Examples and terms](docs/LICENSING.md).

![Lixity manuscript dashboard](docs/screenshots/dashboard-light.png)

```bash
lixity build manuscript.md --language en
```

Open `exports/manuscript_dashboard.html`.
[Install Lixity](#installation) · [Usage](docs/USAGE.md) · [Methods](docs/METHODS.md)

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

| 3D Stylistic Space & Style Dimensions | Editor-Visible Work Markers |
| :---: | :---: |
| <img src="docs/screenshots/dashboard-dimensions.png" alt="3D stylistic space and latent style dimensions" width="100%" /> | <img src="docs/screenshots/dashboard-markers.png" alt="Editor work markers" width="100%" /> |
| *Interactive 3D narrative trajectory & cyclic Jacobi EVD* | *Persistent content-hashed `<!-- LIXITY-MARKER -->` tags* |

| CLI Corpus Diagnostics | Self-Calibrating Style Reference |
| :---: | :---: |
| <img src="docs/screenshots/cli-analyze.png" alt="CLI analyze output" width="100%" /> | <img src="docs/screenshots/cli-style.png" alt="CLI style reference" width="100%" /> |
| Terminal metrics and chapter overview | Median/MAD corridor, `z*` shrinkage and effect sizes |

<details>
<summary><b>View Dashboard in Dark Mode</b></summary>
<p align="center">
  <img src="docs/screenshots/dashboard-dark.png" alt="Lixity Dashboard Dark Mode" width="100%" />
</p>
</details>

### Settings and scientific context

![Settings with visible labels, explanations and restore-without-saving](docs/screenshots/dashboard-settings.png)

Choose project settings and detection thresholds. **●** marks FDR-selected
matrix cells; reference bands show medians and sample counts, not quality targets.

![Style reference bands with medians and chapter sample counts](docs/screenshots/dashboard-reference.png)

### Mobile views

| Project overview | Complete style-dimension panel |
| :---: | :---: |
| <img src="docs/screenshots/dashboard-mobile.png" alt="Mobile project header with version, non-commercial license and corpus overview" width="300" /> | <img src="docs/screenshots/dashboard-dimensions-mobile.png" alt="Mobile 3D chapter view with all three dimension cards and readable feature labels" width="300" /> |

Screenshots use the public-domain *Pride and Prejudice* sample; marker notes
are illustrative and never written back to the source. Open an image for full
resolution. [Screenshot provenance and regeneration](docs/screenshots/README.md).

## Installation

Install from GitHub into an isolated CLI environment. Requires Git and
[uv](https://docs.astral.sh/uv/getting-started/installation/); uv can supply
Python 3.12. Source-available under LNCL-1.0, **non-commercial use only**, not PyPI.

```bash
uv tool install --python 3.12 "git+https://github.com/mfahsold/lixity.git@v1.15.0"
lixity --version
lixity about
```

This installs **v1.15.0**, including the new UI, shared pipeline and security
fixes. The tag stays pinned: upgrading to a future release requires selecting
its tag explicitly. Use `@main` only for development builds, or a reviewed
full commit hash for reproducible deployments.

**[Full installation guide](docs/INSTALLATION.md):** Windows/macOS/Linux,
pipx alternative, Python API environments, PATH repair, upgrades and removal.
Python 3.10+ supports the engine; TOML project settings require 3.11+.

For engine development:

```bash
git clone https://github.com/mfahsold/lixity.git && cd lixity
make install-dev        # venv + pip install -e ".[dev]"
make check              # ruff + mypy --strict + pytest -W error

```

`make install` creates a local `.venv` without dev tools; both installation
targets verify dependencies and version, without changing global Python.

## Quick Start

Start with a UTF-8 Markdown manuscript using `## Chapter title` headings:

```bash
lixity build manuscript.md --language en
```

Open `exports/manuscript_dashboard.html`. Use `--language de` for German or
explicit `--language auto` for detection. No account, API key or upload is needed.
Settings/NDA actions require a project adapter, not just the standalone HTML.

Other commands:

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

Use `--min-chapters 4` with `style`, `dashboard` or `build` to require at least
four usable chapters for a style baseline (default: 2). API callers can pass
`min_chapters=4, project_config={}` to `fingerprint`/`passport` or `dashboard`
to avoid implicit threshold lookup. Language remains an explicit argument.

Test with the bundled public-domain samples:

```bash
lixity analyze samples/effi-briest.md --language de  # German – Fontane, 36 chapters
lixity analyze samples/pride-and-prejudice.md  # English – Austen, 61 chapters
```

Reports and CLI messages appear in English by default; `LIXITY_LANG=de` switches them to German.

Full command reference, metric glossary, worked example, and troubleshooting:
[`docs/USAGE.md`](docs/USAGE.md). Agent-facing JSON contracts:
[`docs/AGENTS.md`](docs/AGENTS.md). Project website:
[mfahsold.github.io/lixity](https://mfahsold.github.io/lixity/).

## What's new in v1.15.0

**v1.15.0** includes the UI, architecture and security improvements below.
Read the [release notes and migration checklist](docs/releases/v1.15.0.md)
before updating an existing project, especially its language defaults.

- **Explore style in 3D:** rotate and zoom chapter trajectories, toggle the
  trajectory and threshold box, and select a point to reach its chapter.
  Mobile layouts preserve feature labels; rotation stops when disabled or
  the tab is hidden. The picture is a projection, not a writing-quality score.
- **One analysis path:** CLI, API and project adapters share metrics,
  paragraph profiling and fingerprint assembly instead of maintaining copies.
- **Clear project boundaries:** explicit threshold mappings support several
  projects in one process without changing the working directory.
- **English by default:** select a manuscript language explicitly or request
  `--language auto`. Localization covers linguistic profiles, readability
  coefficients, labels, help text and number presentation.

The engine produces offline analysis and HTML. Publication workflows, local
control servers and encrypted NDA storage belong to project adapters; they
are not a bundled hosted service or a universal feature of every installation.

## Architecture and project adapters

CLI commands and the Python API share `lixity.pipeline`: language resolution,
paragraph profiling and fingerprint construction have one implementation.
`analyze_document` computes corpus metrics once and returns a typed
`DocumentAnalysis`; renderers only consume results. UI panels reuse central
components and bundled assets, without a frontend build or CDN.

Project adapters own file access, publication exports and local services—not
copies of analysis algorithms. For multiple projects in one process, pass an
explicit configuration instead of changing the working directory:

```python
from lixity.config import load_project_config, resolve_thresholds
from lixity.pipeline import analyze_document, resolve_document_config

settings = load_project_config("/path/to/project")
thresholds = resolve_thresholds(project_config=settings)
config, language = resolve_document_config(text, settings.get("language", "en"))
result = analyze_document(text, config, thresholds)
```

An empty `project_config={}` isolates thresholds from user/project files;
explicit threshold arguments override the supplied mapping. The pipeline itself
does not read files, discover projects or maintain global session state.

Adapters using the shared pipeline require Lixity 1.15.0 or newer.
See [architecture and integration boundaries](docs/ARCHITECTURE.md) for the
configuration contract and [language support](docs/LOCALIZATION.md) for its
scope, guarantees and limitations.

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

English is the default for CLI/API analysis and the core configuration.
`--language auto` explicitly enables function-word-based detection; weak or
ambiguous evidence uses the generic profile rather than guessing a language.
New languages require linguistic resources, localized labels, documented
readability behavior and regression fixtures—not just a translated menu.

Language-specific heuristics are not equally accurate for every genre or
dialect. Numerical dispatch and resource-coverage tests are not proof of
empirical linguistic accuracy. See [localization](docs/LOCALIZATION.md) and
[scientific limitations](docs/STABILITY.md).

## Frequently Asked Questions (FAQ)

<details>
<summary><b>Why doesn't Lixity compare against an external reference corpus?</b></summary>

It compares chapters with the manuscript's own median and spread, not an
external writing ideal. A deviation is a prompt to read, not a quality verdict.

</details>

<details>
<summary><b>How are short chapters handled?</b></summary>

`z* = (x − median) / √(σ² + SE²)`. Greater sampling uncertainty reduces the
score. This limits noise-driven flags; it does not eliminate false positives.

</details>

<details>
<summary><b>How do work markers integrate into author workflows and book exports?</b></summary>

Markers are HTML comments above a paragraph. They remain editable in Markdown;
export visibility depends on your converter. Check the generated book.

</details>

<details>
<summary><b>Is Lixity suitable for non-fiction, essays, and scholarly manuscripts?</b></summary>

Yes, but interpret genre-dependent heuristics cautiously. See
[limitations](docs/STABILITY.md).

</details>

<details>
<summary><b>Can Lixity run in automated CI/CD and publishing pipelines?</b></summary>

Yes. Use JSON output and exit codes: `0` success, `1` processing error,
`2` usage error. Pin the version, language and settings for reproducibility.

</details>

## License

Lixity is **source-available, not Open Source**. LNCL-1.0 permits only
non-commercial use. The project's purpose matters—not whether you are an
individual, independent author or organization.

| Project | Required license |
| :--- | :--- |
| Private writing with no commercial purpose | Included LNCL-1.0 |
| Book intended for sale, including self-publishing, ebooks and print-on-demand | Separate written commercial license |
| Paid editing, client work or commercial software integration | Separate written commercial license |

Obtain permission **before using Lixity for the commercial project**, not only
after the first sale. If plans change, contact the maintainer before commercial
use or sale. [Licensing guide](docs/LICENSING.md) · [Full terms](LICENSE).

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
