# Lixity

[![tests](https://github.com/mfahsold/lixity/actions/workflows/tests.yml/badge.svg)](https://github.com/mfahsold/lixity/actions)
![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)
![License: LNCL-1.0](https://img.shields.io/badge/license-LNCL--1.0-orange)
![Dependencies](https://img.shields.io/badge/dependencies-pydantic%20%7C%20rich%20%7C%20orjson-brightgreen)

**Lixity** is an offline text-linguistics engine that measures *how a literary manuscript reads* – sentence rhythm, lexical diversity, tense continuity, register signals – and flags only the passages where a chapter departs from its own established voice.

Unlike grammar checkers or general NLP stacks, Lixity never measures against external norms. It derives a **self-calibrating style passport** from the manuscript itself (robust median/MAD house style), shrinks noisy observations from short chapters ($z^*$), and controls false discoveries across all chapter×feature cells (Benjamini-Hochberg FDR). The result is macro-editing evidence, not style dogma.

Built for fiction authors, literary editors and translators, digital humanities researchers, and autonomous AI agents that need deterministic, auditable text analytics. Pure Python, zero cloud calls, three dependencies (`pydantic`, `rich`, `orjson`), seven native language profiles.

The name represents the mathematical foundation of its analysis: **T**TR (Type-Token Ratio), **Y**ule's characteristic $K$, and **LIX** (Läsbarhetsindex).

![Lixity CLI analysis report](docs/screenshots/cli-analyze.png)

![Lixity interactive HTML dashboard](docs/screenshots/dashboard-light.png)

---

## Table of Contents

1. [Why Lixity?](#why-lixity)
2. [Target Personas & Workflows](#target-personas--workflows)
3. [Key Capabilities](#key-capabilities)
4. [What Lixity Measures](#what-lixity-measures)
5. [Installation](#installation)
6. [Quick Start & CLI Reference](#quick-start--cli-reference)
7. [The Self-Calibrating Style Passport](#the-self-calibrating-style-passport)
8. [Work Markers (Editor-Visible)](#work-markers-editor-visible)
9. [Python API for AI Agents](#python-api-for-ai-agents)
10. [Multilingual Support](#multilingual-support)
11. [Mathematical & Linguistic Principles](#mathematical--linguistic-principles)
12. [Frequently Asked Questions (FAQ)](#frequently-asked-questions-faq)
13. [License](#license)

---

## Why Lixity?

Most text analysis tools fall into one of two extremes: heavy general NLP libraries designed for tokenization and entity extraction, or consumer grammar checkers that enforce rigid corporate writing rules. Lixity is engineered specifically for **long-form literary prose**, where style is intentional, variety is essential, and the manuscript itself defines what is "normal."

| Dimension | Lixity | General NLP (spaCy / NLTK) | Traditional Stylometry (R `stylo`) | Consumer Writing Apps |
| :--- | :--- | :--- | :--- | :--- |
| **Primary Focus** | **Literary manuscripts & stylometry** | Tokenization, POS, NER | Authorship attribution | Spelling & grammar fixes |
| **Baseline Norm** | **Self-calibrating** (Manuscript median/MAD) | External web/news training corpora | External comparative corpus | Generic corporate/web prose |
| **Statistical Rigor** | **$z^*$ shrinkage** + Benjamini-Hochberg FDR | Raw frequencies without sample variance | Distance metrics (Delta, PCA) | Heuristic rule counters |
| **Lexical Diversity** | **HD-D** & **Yule's $K$** (length-invariant) | Naive TTR (biased by chapter length) | Most Frequent Words (MFW) | Basic vocabulary variety score |
| **Tense Dynamics** | **Paragraph-level** narrative present vs. past | Per-token POS tags (`VBD`/`VBP`) | Not analyzed | Isolated verb alerts |
| **Latent Dimensions** | **Cyclic Jacobi eigendecomposition** on Spearman $\rho$ | Requires external SciPy / scikit-learn | Factor analysis in R | Not available |
| **Editorial Flow** | **Non-destructive HTML work markers** + Agent API | Data science scripts only | R console / static plots | Proprietary cloud extensions |
| **Runtime Footprint** | **Zero C-extensions**, pure Python, offline | Heavy neural models (> 500 MB) | Full R runtime environment | Cloud-dependent, closed source |

---

## Target Personas & Workflows

### 1. Fiction Authors & Novelists
- **Macro-Editing & Pacing:** Analyze chapter rhythm via sentence-length distribution (staccato vs. norm vs. hypotactic cascades) and rhythm variability (CV).
- **Tense Drift Prevention:** Automatically detect unintentional slips between narrative present (*Präsens*) and epic past (*Präteritum*) within scenes.
- **Narrative Economy:** Track dialogue ratio, perception filter density (*saw, heard, felt*), and passive voice constructions.

### 2. Literary Editors & Translators
- **Objective Consistency Auditing:** Evaluate chapter-by-chapter deviations against the book's self-established voice rather than arbitrary external guidelines.
- **Translation Register Matching:** Compare lexical richness and syntactic rhythm between original source texts and foreign language translations.
- **Non-Destructive Work Markers:** Embed persistent editorial flags (`<!-- LIXITY-MARKER ... -->`) that render cleanly in Markdown editors (Obsidian, VS Code, Ulysses) but vanish completely in print and EPUB builds.

### 3. Digital Humanities Researchers & Stylometrists
- **Length-Robust Vocabulary Metrics:** Compute hypergeometric HD-D (McCarthy & Jarvis 2010), Yule's characteristic $K$, and Guiraud's $R$ across unequal chapter lengths without sample size distortion.
- **Unsupervised Latent Style Axes:** Discover intrinsic stylistic dimensions using cyclic Jacobi eigendecomposition on Spearman rank correlation matrices without external matrix libraries.
- **Reproducible Corpus Analysis:** Run fast, fully deterministic batch analyses with byte-for-byte reproducible JSON and markdown outputs.

### 4. AI Agent Engineers & Automated Publishing Pipelines
- **Strict Machine Contracts:** Integrate with language models via stable `schema_version: 2` JSON payloads, complete with metadata headers and POSIX exit codes.
- **Python Facade (`lixity.api`):** Deterministic programmatic access to analysis, tense profiling, passport generation, and marker manipulation.
- **Offline & CI-Ready:** Zero network calls, zero API keys, and zero heavyweight runtime dependencies.

---

## Key Capabilities

- **Completely Offline & Deterministic:** Identical manuscript input produces byte-for-byte identical metrics, JSON schemas, and HTML reports.
- **Self-Calibrating Norms:** No arbitrary external style dogmas or pre-defined genre registers. Lixity derives the reference house style directly from the manuscript's own median and MAD (Median Absolute Deviation).
- **Statistical Significance ($z^*$):** Every style feature includes documented standard error estimation (Poisson, binomial, Miller-Madow entropy correction). Outlier deviations are adjusted for sample noise ($z^* = \frac{x - \text{median}}{\sqrt{\sigma^2 + \text{SE}^2}}$), preventing small chapters from triggering false alarms.
- **Multiple-Testing Control:** Reports statistically expected false positives and the Benjamini-Hochberg False Discovery Rate (FDR, $q = 0.05$) set across all chapter×feature cells.
- **Unsupervised Style Dimensions:** Derives the manuscript's latent stylistic axes via Spearman rank correlation and cyclic Jacobi eigendecomposition (pure standard library, no NumPy/SciPy required).
- **Paragraph-Accurate Tense Profiling:** Tracks narrative present vs. epic past paragraph-by-paragraph with line anchors and severity friction markers.
- **Editor-Visible Work Markers:** Insert persistent, invisible HTML comments (`<!-- LIXITY-MARKER ... -->`) with deterministic content-hash IDs directly from the interactive dashboard or API.
- **Agent-Ready JSON & API:** Strict JSON schemas with metadata blocks (`tool`, `version`, `schema_version`, `language`), clean exit codes, and a stable facade in `lixity.api`.

---

## What Lixity Measures

### 1. Sentence Architecture & Rhythm
- **Average Sentence Length (ASL):** Arithmetic mean of words per sentence.
- **Sentence-Length Architecture:** Binned classification into **Staccato** ($\le 6$ words), **Paratactic** (7–15 words), **Norm** (16–25 words), and **Hypotactic / Cascade** ($> 25$ words).
- **Coefficient of Variation (CV):** Standard deviation divided by mean sentence length; quantifies rhythm variability vs. monotone pacing.
- **Punctuation Density:** Granular distribution of periods, commas, dashes (–/—), colons, semicolons, question marks, exclamation marks, and ellipses (…/...).

### 2. Lexical Diversity & Vocabulary Richness
- **Type-Token Ratio (TTR):** Distinct vocabulary types divided by total tokens.
- **Guiraud's Index ($R = V / \sqrt{N}$):** Length-stabilized vocabulary richness.
- **HD-D (McCarthy & Jarvis 2010):** Deterministic, hypergeometric implementation of vocd/D; robust against text length differences across chapters.
- **Yule's Characteristic $K$:** Length-independent measure of vocabulary concentration and repetition stability.

### 3. Readability & Accessibility
- **Flesch Reading Ease (German Amstad Adaptation):** Syllable- and sentence-calibrated readability score (0–100).
- **LIX (Läsbarhetsindex):** Scandinavian readability index combining sentence length and proportion of long words ($> 6$ characters).

### 4. Narrative Voice & Register Signals
- **Dialogue Share:** Proportion of direct speech enclosed in quotation marks.
- **Function-Word Share:** Grammatical structural words (articles, pronouns, prepositions, conjunctions, auxiliaries/modals).
- **Perception Filter Density:** Sensory filter verbs (*see, hear, feel, notice, think*) marking "telling" instead of "showing".
- **Modal Verb Density:** Signals of uncertainty, hesitation, or subjective filtering.
- **Passive Voice Markers:** Language-specific passive construction frequency per 1,000 words.
- **Nominal Style Density:** Noun derivations via nominalization suffixes per 1,000 words.
- **Adjective Density:** Descriptive attribute load per 1,000 words.
- **Sentence-Starter Entropy:** Shannon entropy ($H$) of initial sentence words with Miller-Madow bias correction.
- **First-Person Sentence Starts:** Proportion of sentences beginning with first-person singular pronouns (*ich / I / je / yo / io / eu / ik*).

### 5. Tense Dynamics
- **Dominance Detection:** Per-paragraph classification into Narrative Present (*Präsens*), Epic Past (*Präteritum/Imparfait*), Mixed, or Neutral.
- **Friction Severity (0–3):** Highlights unintentional tense switches or excessive blending within a single narrative scene.

---

## Installation

Requires **Python 3.10 or newer**.

```bash
# Install directly from GitHub
pip install git+https://github.com/mfahsold/lixity.git

# Or install in editable mode for local development
git clone https://github.com/mfahsold/lixity.git
cd lixity
pip install -e .
```

### Dependencies
Lixity deliberately keeps dependencies minimal:
- [`pydantic>=2.0.0`](https://pydantic.dev/) – Strict schema validation and data models
- [`rich>=13.0.0`](https://github.com/Textualize/rich) – Terminal tables, trees, and progress rendering
- [`orjson>=3.9.0`](https://github.com/ijl/orjson) – Fast, standards-compliant JSON serialization

---

## Quick Start & CLI Reference

### 1. Corpus Analysis
Generates a terminal report or machine-readable JSON of the manuscript's linguistic KPIs.

```bash
# Formatted Rich terminal report
lixity analyze manuscript.md

# Self-describing JSON with metadata block
lixity analyze manuscript.md --json

# Force a specific language profile (e.g. English)
lixity analyze manuscript.md --language en
```

### 2. Tense Profiling
Inspects tense continuity paragraph by paragraph with line anchors.

```bash
# Paragraph report with friction warnings
lixity profile manuscript.md

# Machine-readable JSON output
lixity profile manuscript.md --json
```

### 3. Self-Calibrating Style Passport
Derives the manuscript's reference house style, computes significance-adjusted deviations, and uncovers latent style dimensions.

```bash
# Text summary of house style, deviations, and dimensions
lixity style manuscript.md

# Schema v2 JSON (bands, z*, FDR, dimensions, units)
lixity style manuscript.md --json
```

![Lixity CLI style passport](docs/screenshots/cli-style.png)

### 4. Interactive Single-File HTML Dashboard
Generates a zero-dependency HTML dashboard with an interactive chapter map, diverging z-score heatmap, and work marker controls.

```bash
lixity dashboard manuscript.md -o exports/dashboard.html
```

![Lixity dashboard heatmap](docs/screenshots/dashboard-heatmap.png)
![Lixity style dimensions](docs/screenshots/dashboard-dimensions.png)

### 5. Introspection & Shell Completion

```bash
# Display registered languages, features, and heuristics
lixity about

# Generate shell completion script for Bash or Zsh
lixity completion bash >> ~/.bashrc
lixity completion zsh > "${fpath[1]}/_lixity"
```

---

## The Self-Calibrating Style Passport

Traditional stylometry often evaluates texts against external norms (e.g. newspaper German or academic English). Lixity takes a fundamentally different, text-intrinsic approach: **the manuscript itself establishes the norm**.

```
                           MANUSCRIPT CORPUS
                                  │
                  ┌───────────────┴───────────────┐
                  ▼                               ▼
       Robust House Style               Feature Correlation
      (Median / MAD Bands)               (Spearman Matrix)
                  │                               │
                  ▼                               ▼
        Estimation Uncertainty             Cyclic Jacobi
       (Poisson, Binomial SE)           Eigendecomposition
                  │                               │
                  ▼                               ▼
      Significance Adjustment              Self-Calibrated
    z* = (x - med) / √(σ² + SE²)           Style Dimensions
                  │                               │
                  ▼                               ▼
        Benjamini-Hochberg               Latent Narrative Axes
       FDR Control (q=0.05)              (e.g. Dialogue vs Action)
```

1. **Robust Centrality:** Evaluates 16 descriptive features per chapter using median and MAD (Median Absolute Deviation, scaled $\sigma \approx 1.4826 \times \text{MAD}$).
2. **Significance-Adjusted $z^*$:** A short 300-word chapter naturally has higher variance than a 5,000-word chapter. Lixity computes the standard error $\text{SE}$ for each feature and shrinks noisy deviations:
   $$z^* = \frac{x - \text{median}}{\sqrt{\sigma_{\text{MAD}}^2 + \text{SE}^2}}$$
3. **FDR Multiplicity Control:** With 25 chapters and 16 features (400 comparisons), $\sim 5$ deviations at $|z^*| \ge 2.5$ occur purely by chance. Lixity calculates the Benjamini-Hochberg FDR set ($q = 0.05$) to separate true stylistic shifts from random noise.
4. **Style Dimensions:** Computes the Spearman rank correlation matrix across features and solves for principal axes using cyclic Jacobi eigendecomposition (pure standard library). This reveals the author's own latent style dimensions (e.g. Staccato-Action vs. Reflective-Hypotaxis) without relying on preconceived external genre models.

---

## Work Markers (Editor-Visible)

Lixity bridges the gap between statistical analysis and editorial text editing through non-destructive **work markers**.

- **Format:** Formatted as standard HTML comment lines placed directly above the target paragraph:
  ```markdown
  <!-- LIXITY-MARKER id="m-7f8a1c9b" kind="pruefen" note="Tempuspruefung: unabsichtlicher Praesens-Sprung" created="2026-09-22T14:00:00Z" -->
  Er ging zum Fenster und sieht den Regen fallen.
  ```
- **Visible in Editors:** Authors and editors see markers directly inside VS Code, Obsidian, Neovim, or Ulysses.
- **Invisible in Exports:** Markdown renderers (Pandoc, CommonMark, Typst, LaTeX) treat HTML comments as invisible comments; they never appear in printed books or EPUBs.
- **Idempotent IDs:** Marker IDs are deterministic content hashes derived from anchor text and line position. Markers stay anchored when text above or below is edited.
- **Interactive Control:** Markers can be added or resolved directly from the Lixity dashboard when running the local UI server.

![Lixity work markers](docs/screenshots/dashboard-markers.png)

---

## Python API for AI Agents

Lixity provides a stable, deterministic Python facade designed for AI coding agents, editorial bots, and automated publication pipelines:

```python
from lixity import api

# 1. Corpus analysis (metadata + metrics)
metrics_result = api.analyze(text, language="auto")
kpis = metrics_result["metrics"]
print(f"ASL: {kpis['asl']:.2f}, LIX: {kpis['lix']:.1f}")

# 2. Paragraph-level tense profiling
profiles = api.profile(text, language="de")
flagged_paragraphs = [p for p in profiles["paragraphs"] if p["severity"] >= 2]

# 3. Self-calibrating style passport
passport = api.fingerprint(text, language="de")
for dim in passport["dimensions"]:
    print(f"Dimension {dim['index']}: {dim['variance']*100:.0f}% variance")

# 4. Single-file interactive HTML dashboard
html_content = api.dashboard(text, language="de", title="My Manuscript")

# 5. Work markers manipulation
new_text, marker = api.add_marker(
    text, kind="pruefen", note="Verify tense shift", line=142
)
updated_text, success = api.resolve_marker(new_text, marker["id"])

# 6. Tool introspection
about_info = api.about()
print("Supported languages:", about_info["languages"])
```

Full contracts, JSON schema specifications, and agent interpretation heuristics are documented in [`docs/AGENTS.md`](docs/AGENTS.md).

---

## Multilingual Support

Lixity natively supports **7 languages** plus an extensible `generic` fallback:

| Code | Language | Function Words | Tense Detection | Readability | Style Suffixes |
| :---: | :--- | :---: | :---: | :---: | :---: |
| `de` | German (*Deutsch*) | Full | Full (Präsens/Präteritum) | Flesch (Amstad) + LIX | Full |
| `en` | English | Full | Full (Present/Past) | Flesch + LIX | Full |
| `fr` | French (*Français*) | Full | Full (Présent/Imparfait/Passé) | LIX | Full |
| `es` | Spanish (*Español*) | Full | Full (Presente/Pasado) | LIX | Full |
| `it` | Italian (*Italiano*) | Full | Full (Presente/Passato) | LIX | Full |
| `pt` | Portuguese (*Português*) | Full | Full (Presente/Pretérito) | LIX | Full |
| `nl` | Dutch (*Nederlands*) | Full | Full (O.T.T. / O.V.T.) | LIX | Full |
| `generic` | Generic Fallback | Universal | Minimal | LIX | Heuristic |

The language can be explicitly set or automatically detected (`--language auto`) via function-word distribution vectors. Adding a new language requires only a single `LanguageProfile` definition without modifying any algorithmic code.

---

## Mathematical & Linguistic Principles

Lixity implements peer-reviewed algorithms and mathematically sound formulations:

- **HD-D Lexical Diversity:** Implements the McCarthy & Jarvis (2010) closed-form hypergeometric formulation of vocd, drawing random sample sizes of $N=42$ words to compute the probability of encountering each type.
- **Yule's Characteristic $K$:**
  $$K = 10^4 \times \frac{\sum_{m} m^2 V_m - N}{N^2}$$
  where $V_m$ is the number of types occurring exactly $m$ times.
- **Miller-Madow Entropy Correction:** Corrects the finite-sample undershoot in naive Shannon entropy calculations for sentence-starter distributions:
  $$H_{\text{corrected}} = -\sum p_i \ln p_i + \frac{k - 1}{2N}$$
- **Cyclic Jacobi Eigendecomposition:** Solves the symmetric eigenvalue problem $A v = \lambda v$ through iterative plane rotations, guaranteeing orthogonal eigenvectors and real eigenvalues without external BLAS/LAPACK bindings.

---

## Frequently Asked Questions (FAQ)

<details>
<summary><b>Why does Lixity avoid external genre averages?</b></summary>
A literary manuscript has its own distinct aesthetic. Measuring a noir crime novel or an experimental prose piece against the "average German newspaper article" or "general prose corpus" produces meaningless critique. Lixity discovers what is normal <i>for your book</i> and flags only chapters that stray from your self-established style.
</details>

<details>
<summary><b>How does significance adjustment prevent false alarms?</b></summary>
In short chapters (e.g. a brief transitional scene of 250 words), a few extra commas or short sentences cause extreme percentage swings. By incorporating standard errors directly into $z^* = \frac{x - \text{median}}{\sqrt{\sigma^2 + \text{SE}^2}}$, Lixity automatically shrinks noisy observations toward zero. A small chapter must deviate dramatically to be flagged.
</details>

<details>
<summary><b>Will Lixity work with non-fiction or academic papers?</b></summary>
Yes. While developed with literary manuscripts in mind, Lixity's rhythm, lexical richness, readability, and style passport features apply equally well to essays, dissertations, memoirs, and technical documentation.
</details>

<details>
<summary><b>Can I run Lixity in CI/CD pipelines?</b></summary>
Yes. Lixity returns clean, standardized POSIX exit codes (0 = clean, 1 = error/invalid input, 2 = linting/style warnings if configured) and emits JSON with deterministic key ordering.
</details>

---

## License

**Lixity Non-Commercial License 1.0 (LNCL-1.0)**

Free for research, educational purposes, personal writing, and non-commercial open science projects. Commercial exploitation or integration into proprietary SaaS products requires a written commercial license from the author.

Contact: **Matthias Fahsold** ([mfahsold@googlemail.com](mailto:mfahsold@googlemail.com))