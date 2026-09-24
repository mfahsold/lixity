# Mathematical methods

Formal description of every estimator Lixity uses — definitions, defaults
and injectability. Research context and known limitations live in
[`STABILITY.md`](STABILITY.md); command flags live in [`USAGE.md`](USAGE.md).

Severity of thresholds: defaults are documented heuristics, not universal
laws. They are injectable (CLI / API / UI settings) and reported back in
every `meta` block.

## 1. Robust house-style baseline

### Language and presentation boundary

Language selection changes tokenization, linguistic feature extraction and
the readability model. It does not translate or alter the definitions of
median/MAD, FDR correction or eigendecomposition. JSON numbers remain numeric;
locale-specific decimal separators are applied only when rendering reports.
See [LOCALIZATION.md](LOCALIZATION.md) for supported profiles and limitations.

The 3D dashboard displays up to three derived dimension scores. A point is
flagged when a completed dimension score reaches the configured absolute
cutoff on any displayed axis. All feature contributions must be summed before
testing that cutoff: intermediate partial sums are not dimension scores.
The visual boundary is therefore a box of per-axis cutoffs, not a sphere or
a joint confidence region. Camera rotation and zoom do not change scores.

Per feature $f$ over $n$ measurable chapters with values $x_1,\dots,x_n$:

| Quantity | Definition | Notes |
| :--- | :--- | :--- |
| Centre | $\tilde{x} = \operatorname{median}(x_i)$ | robust to single outliers |
| Spread | $\mathrm{MAD} = \operatorname{median}(\lvert x_i - \tilde{x}\rvert)$ | 0 for $n < 2$ |
| Sigma | $\sigma = 1.4826 \cdot \mathrm{MAD}$ | 1.4826 = $1/\Phi^{-1}(0.75)$ (DescTools/R default) |

A feature is **measurable** only when $n \ge$ `FingerprintThresholds.min_chapters`
(default 2) and $\sigma > 0$; otherwise its baseline is zeroed and it stays out
of the fingerprint.

## 2. Significance-adjusted deviation $z^*$

Plain robust z:

$$z_{\text{raw}} = 0.6745 \cdot \frac{x - \tilde{x}}{\mathrm{MAD}}
\quad (0.6745 = 1/1.4826)$$

Lixity scores the style reference with the **noise-aware** form:

$$z^* = \frac{x - \tilde{x}}{\sqrt{\sigma_{\mathrm{MAD}}^2 + \mathrm{SE}^2}}$$

Standard errors per feature (plug-in estimators, fixed constants, see
`style_se` in the analyze schema):

| Feature family | Estimator |
| :--- | :--- |
| Count densities (per 1 000 words) | Poisson: $\mathrm{SE} = \sqrt{\hat{\lambda}/W \cdot 1000^2}$ |
| Shares (%) | binomial: $\mathrm{SE} = \sqrt{p(1-p)/N}$ |
| ASL, CV, entropy, HD-D, … | sample-based (variance / delta method) |

Short chapters get a large $\mathrm{SE}$, so their $z^*$ shrinks and cannot
manufacture false alarms.

## 3. Thresholds (`FingerprintThresholds`)

| Key | Default | Meaning |
| :--- | :--- | :--- |
| `z_mild` | 2.5 | notable deviation: enters `deviations`, drives expected FP count |
| `z_strong` | 3.5 | strong deviation (reported, not a second cut on `deviations`) |
| `fdr_q` | 0.05 | target FDR for `fdr_flagged` |
| `fdr_method` | `bh` | `bh` = Benjamini–Hochberg; `by` = Benjamini–Yekutieli (arbitrary dependence) |
| `min_chapters` | 2 | below this, no baseline for a feature |
| `dim_score_threshold` | 2.5 | \|dimension score\| from here: chapter flagged on that axis |
| `flag_min_severity` | 2 | paragraph severity floor for the flags panel (1–3) |

- A cell counts **in band** iff |z\*| < `z_mild`.
- `expected_false_positives` = m · P(|Z| ≥ z_mild) with
  m = measured cells and P the two-sided normal tail (`erfc`). At the
  default 2.5 this is ≈ 1.24 % of $m$.
- Injectability: CLI `--z-mild/--z-strong/--fdr-q/--fdr-method/--dim-threshold/--flag-min-severity`
  on `style`, `dashboard`, `build`; API kwargs of the same names; the
  control-server settings form persists `z_mild`, `z_strong`, `fdr_q`,
  `flag_min_severity`, `dim_score_threshold`. Project defaults may live in
  `[tool.lixity]` / `lixity.toml` / `~/.config/lixity.toml`
  (CLI flag > UI session > project config > user config > code default).
- Every passport reports the **active** values under `meta.*` — never
  re-hardcode the defaults.

## 4. Multiple testing (Benjamini–Hochberg / Benjamini–Yekutieli)

Input: one $p$-value per measured cell, $p = P(\lvert Z \rvert \ge \lvert z^* \rvert)$
(two-sided normal tail). Sort ascending, find the largest $k$ with
$p_{(k)} \le (k/m) \cdot q \cdot c$, reject $p_{(1)},\dots,p_{(k)}$.
Deterministic tie-break by $(\text{chapter}, \text{feature})$. The rejected
set is `fdr_flagged` — prefer it over raw `deviations` for strong claims.

- **BH** ($c = 1$): controls FDR under independence / PRDS.
- **BY** ($c = \sum_{i=1}^{m} 1/i$, the harmonic factor): valid under
  arbitrary dependence; more conservative — use when feature dependence is
  unknown or adversarial (`fdr_method = "by"`).

## 4a. Effect sizes (magnitude, not just significance)

For every FDR-confirmed cell the passport carries Cliff's $\delta$ and the
implied Vargha–Delaney $\hat{A}_{12} = (\delta + 1)/2$, labelled with
Romano et al.'s bands:

| $\lvert\delta\rvert$ | Label |
| :--- | :--- |
| < 0.147 | negligible |
| < 0.33 | small |
| < 0.474 | medium |
| ≥ 0.474 | large |

Sign: positive = chapter above house-style median. Effect sizes answer
"how different", not only "different at q".

## 4b. Exchangeability diagnostics (baseline quality)

On the ordered per-feature series $x_1,\dots,x_n$ (chapters in order):

- **Runs test** about the series median: $z = (R - \mu_R)/\sigma_R$;
  $\lvert z\rvert \ge 1.96$ puts the feature on `runs_flagged` (temporal
  structure the i.i.d. FDR model ignores).
- **Lag-1 autocorrelation** $\rho_1$; critical band $\approx 1/\sqrt{n}$.
  `mean_lag1_rho` and `acf_critical` are reported; `exchangeable` is
  false when runs flag or mean $\rho_1$ exceeds the critical value.
- `low_power` is true for $n < 8$ chapters — treat every downstream
  significance claim as provisional.

## 4c. Structural diagnostics (`structural_diagnostics`)

Pure-stdlib structural and distributional diagnostics over the ordered
per-feature series (chapters in order) plus token-level lexical diagnostics
when the passport is built from source text (`api.fingerprint`, `lixity style`,
`lixity build`, `lixity dashboard`). They answer *where* and *how*
the house style shifts — orthogonal to the per-cell z\*/FDR layer.

| Key | Estimator | Guard / notes |
| :--- | :--- | :--- |
| `changepoints` | **PELT** (pruned exact linear time) with Gaussian cost $n\ln\sigma^2$ and BIC penalty $2\ln n$ | $n < 3$ or constant series → `[]`; values are 0-based indices of the first element after each break |
| `trends` | **Mann–Kendall** monotonic trend: $\tau$, $S$, two-sided normal $p$ (tie-corrected variance, continuity correction) | $n < 3$ → `None`; constant → $(0,0,1)$ |
| `robust_scales` | **Sn** (Rousseeuw & Croux 1993, consistency $c_n = 1.1926$) and **Qn** (same paper, $d_n = 2.2219$), alongside $1.4826\cdot\mathrm{MAD}$ | $n < 2$ → $0$; Sn/Qn have 50 % breakdown (vs. MAD's 50 % with lower Gaussian efficiency) |
| `tail_index` | **Hill** estimator $\hat\alpha = \bigl[\tfrac1k\sum\ln\frac{x_{(n-i+1)}}{x_{(n-k)}}\bigr]^{-1}$ over the $k$ largest values | $n \ge 5$, $k=\lfloor\sqrt n\rfloor$ (or user $k\ge 2$); non-positive threshold → `None` |
| `distribution_shift` | **Wasserstein-1D** $W_1$ (L¹ integral of quantile functions) and **two-sample KS** ($D$, asymptotic $p$) of the first half of chapters vs the second half, per feature | both halves $\ge 2$ (so $n \ge 4$); empty half → omitted |
| `trending_features` | feature names with Mann–Kendall $p < 0.05$ | summary list |
| `segmented_features` | feature names with at least one PELT changepoint | summary list |
| `shifted_features` | feature names with early/late KS $p < 0.05$ | summary list |
| `cooccurrence` *(token-level)* | undirected content-word graph (sliding window, default 2) with mean degree and **Goh–Barabási** degree-sequence fitness $\hat\alpha = 1 + n/\sum\ln(k_i/(k_{\min}-0.5))$ + KS fit | needs ≥ 50 content tokens; fit omitted when degenerate / $n<5$ / constant |
| `keyness` *(token-level)* | **Dunning $G^2$** (log-likelihood ratio) of first-half chapters vs second half, content words only; signed so positive = over in the early half | both halves ≥ 20 content tokens; single-chapter texts omit `keyness` |

Token-level blocks (`cooccurrence`, `keyness`) are computed by
`lexical_structural_diagnostics(text, config)` and merged into
`structural_diagnostics` on the text-bearing surfaces (`api.fingerprint`,
CLI `style` / `build` / `dashboard`). `StyleFingerprint.from_metrics`
alone still yields the metric-derived keys only.

The passport `meta` block reports `schema_version: 4`, `min_chapters` and
`flag_min_severity` alongside the z\*/FDR thresholds; `passport_text` adds a
“Structural diagnostics” line when any feature has a changepoint, significant
trend or early/late distribution shift.

### Track B / research extensions (not implemented)

Documented research directions, **not** current product features:

- **Textometry / Burrows’ Delta** (and 2026 generalisations to Jensen–
  Shannon / Rank-Turbulence Delta): authorship-attribution baselines.
  Lixity’s chapter↔rest JSD with driver words is *inspired by* this line
  but deliberately **not** an attribution instrument (see STABILITY §1).
  There is **no external Delta stylometry** against a reference corpus;
  a future Delta panel would rank chapters against such a corpus — out of
  scope while the product stays manuscript-intrinsic. Structure-module
  caveats (empty `signal_counts`, filter-list definitions, pacing without
  dividers, no NER/speaker attribution) are registered in STABILITY §2
  and summarised in AGENTS §3.5.
- **OHCO / TEI**: the hierarchical ordered corpus of hypotheses (OHCO) and
  TEI XML are the scholarly interchange standards. Lixity’s input contract
  is UTF-8 Markdown with `## ` chapter headings (configurable
  `chapter_regex` / `appendix_marker`); a TEI→Markdown ingest path would be
  the natural bridge, not a second analysis core.
- **Hermeneutic loop / Foregrounding (Mukařovský)**: deviation from a
  text’s *own* norm is the literary signal — already the design principle
  of the self-calibrating house style. A deeper hermeneutic layer (quotes,
  interpretive commentary tied to flagged cells) is UI/agent territory, not
  a new estimator.

### Track C / pedagogy (not implemented)

- Worked examples that walk one chapter from KPI → heatmap → paragraph →
  marker, suitable as a tutorial on the project page.
- Glossary of every passport key for non-statisticians (beyond `llms.txt`).
- Exportable “method card” (estimator + citation + guard) per metric for
  peer review / replication packages.

## 5. Latent style dimensions

1. Spearman rank correlation $\rho$ over chapter values of usable features
   (ties → average ranks; zero-variance pairs → 0).
2. Cyclic Jacobi eigendecomposition on the symmetric matrix
   (standard library only; eigenvalues sorted descending; sign fixed by
   the largest-absolute loading).
3. Dimension score threshold: |score| ≥ `dim_score_threshold` (default 2.5) marks `flagged` chapters on that axis.
4. Redundancy: pairs with |ρ| ≥ `REDUNDANCY_RHO` (0.8).

## 6. Lexical diversity indices

| Index | Definition sketch | Guard |
| :--- | :--- | :--- |
| Guiraud $R$ | $\mathrm{TTR} \sqrt{N}$ | length-dependent; prefer with HD-D |
| HD-D | hypergeometric expected TTR of 35-token draws | McCarthy & Jarvis; 42 fixed samples |
| MTLD | mean factor length until TTR hits 0.72 | $\ge 100$ tokens else `null` |
| MATTR | mean TTR over sliding 50-token windows | window length |
| Maas $a^2$ | $a^2 = (\ln N - H)/\ln^2 N$ | $\ge 100$ tokens |
| Yule $K$ | $10^4 \cdot (\sum m^2 V_m - N)/N^2$ | length-dependent by design |

McCarthy & Jarvis (2010): report MTLD + HD-D + Maas **together**, not a
single index. See [`STABILITY.md`](STABILITY.md) §1 for length caveats.

## 7. Readability (language-calibrated)

Seven published formulas, selected by profile; constants are fixed and
covered by hand-computed tests:

| Lang | Formula (name) | ASL / word-share terms |
| :---: | :--- | :--- |
| de | Amstad / Flesch-De | $180 - 20\cdot\mathrm{ASL} - 58.5\cdot\%S$ |
| en | Flesch | $206.835 - 1.015\cdot\mathrm{ASL} - 84.6\cdot\%S$ |
| fr | Kandel-Moles | $207.0 - 1.015\cdot\mathrm{ASL} - 73.6\cdot\%S$ |
| es | Szigriszt-Pazos | $206.835 - 20\cdot\mathrm{ASL} - 62.35\cdot\%S$ |
| it | Franchina-Vacca | $217.0 - 1.3\cdot\mathrm{ASL} - 60.0\cdot\%S$ |
| pt | Martins | $248.835 - 1.015\cdot\mathrm{ASL} - 84.6\cdot\%S$ |
| nl | Douma | $207.0 - 0.93\cdot\mathrm{ASL} - 77.0\cdot\%S$ |

$S$ = syllables per 100 words (heuristic syllable counter). **LIX** uses the
standard Björnsson cut: words with **more than six characters**, for every
language: $\mathrm{LIX} = \mathrm{ASL} + 100 \cdot \frac{\text{long words}}{\text{tokens}}$.

## 8. Jensen–Shannon divergence (chapter ↔ rest)

$JSD(P \| Q) = \tfrac12 D_{\mathrm{KL}}(P \| M) + \tfrac12 D_{\mathrm{KL}}(Q \| M)$
with $M = \tfrac12(P+Q)$ (base-2, so $\in [0,1]$). Driver words are ranked by
their contribution (using terms of the form $\tfrac12\sum_x p_m(x)\log\frac{p_m(x)}{q(x)}$)
— interpretable, not a black-box embedding.

## 9. Paragraph layers (within-chapter colouring)

Each chapter is its own reference: robust $z$ of the paragraph value against
that chapter’s paragraph median/MAD ($n \ge 3$ measurable paragraphs, else
skipped). Layer fill uses the absolute value span (min–max per dimension);
the ring marks $\lvert z \rvert \ge 1.5$ (unusual **for this chapter**).

## 10. Determinism contract

- No wall-clock in the analysis path; fixed HD-D sample seed.
- Float operations in fixed order on the same interpreter → byte-identical
  HTML/JSON (platform last-bit differences are documented in STABILITY).
- `python -W error` test run + `mypy --strict` + ruff gate every change.

## Where to plug new thresholds

| Surface | Hook |
| :--- | :--- |
| CLI | `--z-mild`, `--z-strong`, `--fdr-q`, `--fdr-method`, `--dim-threshold`, `--flag-min-severity` (see USAGE) |
| API | `api.fingerprint(..., z_mild=…, fdr_q=…, fdr_method=…, …)` |
| Control UI | Settings group → POST `/api/settings` → `ui_server.UIHandler` |
| Embedders | `build_dashboard_html(..., z_mild=…, z_strong=…, fdr_q=…, flag_min_severity=…, dim_score_threshold=…)` |
| Config file | `[tool.lixity]` in `pyproject.toml`, or `lixity.toml` / `~/.config/lixity.toml` |
| Tests | `FingerprintThresholds(...)` + passport `meta` |

Resolution order per key: CLI/API flag → UI session → project config →
user config → code default (`src/lixity/config.py`).
