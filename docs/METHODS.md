# Mathematical methods

Definitions, defaults and implementation limits of Lixity's measurements.
Research context and known limitations live in
[`STABILITY.md`](STABILITY.md); command flags live in [`USAGE.md`](USAGE.md).

Review thresholds are configurable heuristics, not universal laws. Read their
active values from passport `meta`; formula constants and estimator conventions
are separate from author preferences.

The 1.25 corrections below retain the JSON field names and passport
schema 4, but change measurements and derived results. Regenerate chapter
metrics, style passports and reports before comparing outputs from before the
prose-scope, MTLD, robust-scale, segmentation, distribution and dimension
corrections. A source update alone does not refresh stored outputs.

## 1. Robust house-style baseline

The reference population is the supplied manuscript's measurable chapters.
Retained research sources, including travel accounts and monographs, are not
added to that population. Source analysis uses the same engine on one archived
source version and labels its interpretation `source_internal`; an explicit
source–manuscript comparison produces a separate report, not a new baseline.

### Language and presentation boundary

Language selection changes tokenization, linguistic feature extraction and
the readability model. It does not translate or alter the definitions of
median/MAD, FDR correction or eigendecomposition. JSON numbers remain numeric;
locale-specific decimal separators are applied only when rendering reports.
See [LOCALIZATION.md](LOCALIZATION.md) for supported profiles and limitations.

Token, syllable, dialogue and sentence measures share the supported prose scope:
body paragraphs, list items and blockquote paragraphs with `>` delimiters
removed. YAML front matter, code, headings, comments and footnote definitions
are omitted; inline emphasis and footnote anchors are stripped. This bounded
Markdown policy is not a complete CommonMark parser. Visible prose beneath a
leading document title (`# …`) before the first chapter contributes to global
metrics but not chapter-only reports.
Paragraph profiles intentionally cover body paragraphs and list items only,
retaining their source line anchors; they omit blockquotes.

Configured `word_regex` flags are respected across analysis surfaces; cue
patterns retain their separate case-insensitive contract. English and German
default word patterns include Unicode accented letters. LF and CRLF share
semantic paragraph boundaries. Short-paragraph counting uses paragraph
whitespace words and the inclusive configured threshold, including eight-word
paragraphs. Legacy whitespace counts remain distinct from regex token counts.

Chapter labels remain available for navigation; changing a title does not
change its prose readability. For even sentence counts, `median_sl_exact`
averages the two middle lengths. The older integer `median_sl` retains its upper
middle value for JSON compatibility; reports use the exact median.

Corpus `dialog_words` and chapter dialogue counts use the configured
`word_regex`, as do their denominators (`tokens` and chapter `words`). Thus
`dialog_ratio` and chapter `dialog_pct` count the same token unit inside and
outside detected quotations. The legacy whitespace count `clean_words` is
unchanged and is not the dialogue-ratio denominator. Recompute older dialogue
reports and dependent style results before comparing across this correction.

The 3D dashboard displays up to three derived dimension scores. A point is
flagged when a completed dimension score reaches the configured absolute
cutoff on any displayed axis. All feature contributions must be summed before
testing that cutoff: intermediate partial sums are not dimension scores.
The visual boundary is therefore a box of per-axis cutoffs, not a sphere or
a joint confidence region. Camera rotation and zoom do not change scores.

Per feature $f$ over $n$ measurable chapters with values $x_1,\dots,x_n$:

| Quantity | Definition | Notes |
| :--- | :--- | :--- |
| Centre | $\tilde{x} = \mathrm{median}(x_i)$ | robust to single outliers |
| Spread | $\mathrm{MAD} = \mathrm{median}(\lvert x_i - \tilde{x}\rvert)$ | 0 for $n < 2$ |
| Sigma | $\sigma = 1.4826 \cdot \mathrm{MAD}$ | rounded normal-consistency factor $1/\Phi^{-1}(0.75)$; not a finite-sample correction |

A chapter–feature cell is **measurable** when the feature has at least
`FingerprintThresholds.min_chapters` observations (default 2). Below this floor,
the baseline is zeroed and no cells are scored. Constant features can still
produce measured zero deviations; derived dimensions and spread-based
diagnostics require positive $\sigma$. Availability and informative variation
are different conditions.

## 2. Noise-adjusted deviation (z*)

Plain robust z:

$$
z_{\text{raw}} = 0.6745 \cdot \frac{x - \tilde{x}}{\mathrm{MAD}}
\quad (0.6745 \approx 1/1.4826)
$$

Lixity combines the descriptive manuscript spread with an estimated measurement
error:

$$
z^* = \frac{x - \tilde{x}}{\sqrt{\sigma_{\mathrm{MAD}}^2 + \mathrm{SE}^2}}
$$

Standard errors per feature (plug-in estimators, fixed constants, see
`style_se` in the analyze schema):

| Feature family | Estimator |
| :--- | :--- |
| Count densities (per 1 000 words) | Poisson plug-in: $\mathrm{SE} = 1000\sqrt{k}/W$, for observed count $k$ and $W$ tokens |
| Shares (%) | binomial plug-in: $\mathrm{SE} = 100\sqrt{p(1-p)/N}$ percentage points, with $p$ on 0–1 |
| ASL, CV, entropy, … | sample-based (variance / delta method) |

Larger standard errors reduce the magnitude of $z^*$, limiting noise-driven
flags. Exact HD-D has no independent window-sampling SE: its `style_se` entry
is omitted. The fingerprint's missing-SE fallback of zero denotes no estimated
measurement SE for this feature, **not** certainty about a larger population.
These plug-ins do not establish independence of words/sentences or calibrated
null probabilities for chapter features. Zero observed events can give zero
plug-in error without establishing population certainty.

## 3. Thresholds (`FingerprintThresholds`)

| Key | Default | Meaning |
| :--- | :--- | :--- |
| `z_mild` | 2.5 | notable deviation: enters `deviations`, drives expected FP count |
| `z_strong` | 3.5 | strong deviation (reported, not a second cut on `deviations`) |
| `fdr_q` | 0.05 | nominal selection level; prose FDR is not established |
| `fdr_method` | `bh` | BH or BY step-up rule; both require valid input null probabilities |
| `min_chapters` | 2 | below this, no baseline for a feature |
| `dim_score_threshold` | 2.5 | \|dimension score\| from here: chapter flagged on that axis |
| `flag_min_severity` | 2 | paragraph severity floor for the flags panel (1–3) |

- A cell counts **in band** iff |z\*| < `z_mild`.
- `expected_false_positives` = m · P(|Z| ≥ z_mild) with
  m = measured cells and P the two-sided normal tail (`erfc`). At the
  default 2.5 this is ≈ 1.24 % of $m$ under a standard-normal null. It is
  a model reference, not a measured count of false findings in the manuscript.
- Injectability: CLI `--z-mild/--z-strong/--fdr-q/--fdr-method/--dim-threshold/--flag-min-severity`
  on `style`, `dashboard`, `build`; API kwargs of the same names; the
  control-server settings form applies `z_mild`, `z_strong`, `fdr_q`,
  `flag_min_severity`, `dim_score_threshold` to the current server session.
  It preserves the existing `fdr_method`; configure that through the CLI,
  Python API or project configuration. Project defaults may live in
  `[tool.lixity]` / `lixity.toml` / `~/.config/lixity.toml`
  (CLI flag > UI session > project config > user config > code default).
- Every passport reports the **active** values under `meta.*` — never
  re-hardcode the defaults.

## 4. Multiple testing (Benjamini–Hochberg / Benjamini–Yekutieli)

Input: one $p$-value per measured cell, $p = P(\lvert Z \rvert \ge \lvert z^* \rvert)$
(two-sided normal tail). Sort ascending, find the largest $k$ with
$p_{(k)} \le (k/m) \cdot q / c$, reject $p_{(1)},\dots,p_{(k)}$.
Deterministic tie-break by $(\text{chapter}, \text{feature})$. The rejected
set is `fdr_flagged`. This records selection under the implemented model,
not confirmed errors or validated statistical significance in prose.

- **BH** ($c = 1$): controls FDR for valid null probabilities under
  independence or the specified positive-dependence conditions.
- **BY** ($c = \sum_{i=1}^{m} 1/i$): accommodates arbitrary dependence
  between valid null probabilities. It does not repair invalid probabilities.

Lixity estimates its median/MAD from the same chapters it scores and then
applies a normal tail to the custom $z^*$. That calibration has not been
established. Runs/lag diagnostics and switching to BY do not establish it.

## 4a. Effect sizes (magnitude, not just significance)

For every FDR-selected cell, passport `effect_magnitudes` carries a band label
derived from Cliff's $\delta$, using Romano et al.'s bands. The implied
Vargha–Delaney $\hat{A}_{12} = (\delta + 1)/2$ restates the same contrast;
neither numerical value is emitted in that field:

| $\lvert\delta\rvert$ | Label |
| :--- | :--- |
| < 0.147 | negligible |
| < 0.33 | small |
| < 0.474 | medium |
| ≥ 0.474 | large |

Sign: positive = the chapter exceeds more other chapters than it falls below;
ties contribute zero. The bands describe ordinal contrast, not literary merit.

## 4b. Exchangeability diagnostics (baseline quality)

On the ordered per-feature series $x_1,\dots,x_n$ (chapters in order):

- **Runs test** about the series median: $z = (R - \mu_R)/\sigma_R$;
  $\lvert z\rvert \ge 1.96$ puts the feature on `runs_flagged` (temporal
  structure the i.i.d. FDR model ignores).
- **Lag-1 autocorrelation** $\rho_1$; critical band $\approx 1/\sqrt{n}$.
  `mean_lag1_rho` and `acf_critical` are reported; `exchangeable` is
  false when runs flag or $|\mathrm{mean}(\rho_1)|$ reaches or exceeds the
  critical value.
- `low_power` is true for $n < 8$ chapters. Neither this flag nor an
  `exchangeable` result establishes calibrated probabilities.

## 4c. Structural diagnostics (`structural_diagnostics`)

Pure-stdlib structural and distributional diagnostics over the ordered
per-feature series (chapters in order) plus token-level lexical diagnostics
when the passport is built from source text (`api.fingerprint`, `lixity style`,
`lixity build`, `lixity dashboard`). They add exploratory ordered-series and
lexical contrasts alongside the per-cell z\*/FDR layer; calculation and model
limits are listed below.

| Key | Estimator | Guard / notes |
| :--- | :--- | :--- |
| `changepoints` | exact unpruned dynamic programming for guarded cost $n\ln\sigma^2$ and penalty $2\ln n$ | singleton/zero-variance costs are zero; anchored centred moments; $O(n^2)$ time, $O(n)$ storage; $n<3$ or constant → `[]`; 0-based indices of the first observation after a break |
| `trends` | Mann–Kendall $S$ with tie-corrected normal $p$ and continuity correction; $\tau=S/\binom n2$ is tau-a | $n<3$ → `None`; constant → $(0,0,1)$; not tie-normalized tau-b |
| `robust_scales` | Sn: low outer median of high inner medians, including self-distances, ×1.1926; Qn: sorted pairwise distance at rank $\binom{\lfloor n/2\rfloor+1}{2}$, ×2.21914 | Gaussian asymptotic factors; no finite-sample correction; $n<2$ → 0 |
| `tail_index` | **Hill** estimator $\hat\alpha = \bigl[\tfrac1k\sum\ln\frac{x_{(n-i+1)}}{x_{(n-k)}}\bigr]^{-1}$ over the $k$ largest values | $n \ge 5$, $k=\lfloor\sqrt n\rfloor$ (or user $k\ge 2$); non-positive threshold → `None` |
| `distribution_shift` | exact empirical-CDF Wasserstein $W_1$ and two-sample KS $D$; stable asymptotic KS $p$ | sort plus linear CDF merge, including ties and unequal sizes; $D=0$ → $p=1$; both halves need $\ge2$ observations; $p$ is not calibrated for tied/fitted distributions |
| `trending_features` | feature names with Mann–Kendall $p < 0.05$ | summary list |
| `segmented_features` | feature names with at least one guarded-objective changepoint | summary list |
| `shifted_features` | feature names with early/late KS $p < 0.05$ | summary list |
| `cooccurrence` *(token-level)* | content-word graph (window 2); approximate discrete exponent $\hat\alpha=1+n/\sum\ln(k_i/(k_{\min}-0.5))$ and fitted-CDF comparison | estimator follows Clauset–Shalizi–Newman Eq. 3.7; current truncated continuous CDF and ordinary KS $p$ do not establish discrete power-law goodness of fit; ≥50 content tokens, ≥5 positive nonconstant degrees |
| `keyness` *(token-level)* | **Dunning $G^2$** (log-likelihood ratio) of first-half chapters vs second half, content words only; signed so positive = over in the early half | both halves ≥ 20 content tokens; single-chapter texts omit `keyness` |

The legacy Python name `pelt_changepoints` is retained, but the implementation
does not prune or claim linear time. Its guarded singleton/constant cost does
not satisfy the PELT pruning premise in
[Killick et al., Theorem 3.1](https://arxiv.org/abs/1101.1438v3). Considering
every predecessor corrects optimization of this declared objective; the guard
is still a modelling choice, not a nondegenerate Gaussian likelihood. Anchoring
before centred variance updates limits cancellation from large offsets without
recovering precision already lost in input floats.

Sn's low/high medians follow the
[original definition](https://wis.kuleuven.be/stat/robust/papers/publications-1993/rousseeuwcroux-alternativestomedianad-jasa-1993.pdf).
Qn uses the modern rounded Gaussian factor 2.21914 instead of historical
2.2219, preserving its order-statistic rank. These normalizations remain
separate from finite-sample bias correction; neither estimator applies it.

Wasserstein distance integrates $|F_{\mathrm{early}}-F_{\mathrm{late}}|$ over
the distinct empirical-CDF knots. KS $D$ is the maximum CDF difference on the
same merged support. Stable evaluation of the asymptotic survival function
corrects the identical-distribution boundary and small-argument cancellation;
it does not turn the approximate $p$ into an exact, fitted-null or tied-data
calibration. Short samples and serially dependent chapters need care.

Token-level blocks (`cooccurrence`, `keyness`) are computed by
`lexical_structural_diagnostics(text, config)` and merged into
`structural_diagnostics` on the text-bearing surfaces (`api.fingerprint`,
CLI `style` / `build` / `dashboard`). `StyleFingerprint.from_metrics`
alone still yields the metric-derived keys only.

Keyness uses the full term/non-term × corpus A/B contingency table. Expected
counts are row-total × column-total / grand-total, and
$G^2 = 2\sum O\ln(O/E)$, with zero observed cells contributing zero. Lixity adds
a direction sign for over-representation in A. This follows the binomial
likelihood-ratio formulation in [Dunning (1993), §5.3](https://aclanthology.org/J93-1003.pdf).
Version 1.16.0 includes the non-term cells previously omitted from this calculation;
recompute older keyness values before comparison. A signed ranking is not a
multiple-testing-adjusted significance claim.

The passport retains schema 4 and these field names. The structural summary
uses the implemented thresholds; it does not certify a narrative boundary,
trend or fitted distribution. See [STABILITY.md](STABILITY.md#structural-diagnostics)
for the model assumptions and current calculation limits.

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
- **OHCO / TEI**: OHCO means [Ordered Hierarchy of Content Objects](https://experts.illinois.edu/en/publications/what-is-text-really/),
  a document-model thesis; TEI supplies scholarly text-encoding guidelines. Lixity’s input contract
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

## 5. Exploratory style dimensions

The dimensions are PCA of standardized tied midranks on one common complete
chapter set. Covariance, loadings, explained variance and scores use that same
rank space:

1. Start with baseline-usable features and select chapters measured on every
   candidate feature. At least three complete chapters are required.
2. Give tied values their average rank within this set. Centre each rank column
   and divide by its sample standard deviation ($n-1$ denominator). Drop
   columns constant on this set; at least three varying features must remain.
3. Form $C=X^\mathsf{T}X/(n-1)$ and use cyclic Jacobi eigendecomposition
   (standard library only). Eigenvalues are sorted descending; the
   largest-absolute loading fixes each axis sign.
4. Project the same standardized ranks: $s_k=Xv_k$. Only the common complete
   chapters receive `scores`; missing measurements are not imputed. The
   reported `variance` is $\lambda_k/p$ for $p$ unit-variance columns, the
   explained fraction in this rank space.
5. A completed, unrounded score with |score| ≥ `dim_score_threshold` (default
   2.5) puts a chapter in `flagged` on that axis. Scores are stored rounded to
   two decimals; the cutoff remains descriptive, not a calibrated probability.

Fewer than three complete chapters or varying features yields no dimensions.
Incomplete chapters remain available in the other measured-feature views but
do not receive dimension scores. The complete-case subset can be small or
unrepresentative, and ranks depend on the supplied manuscript. Explained
variance does not mean literary importance or a simultaneous confidence region.

The separate redundancy list still compares each pair's available chapters:
|Spearman $\rho$| ≥ `REDUNDANCY_RHO` (0.8). Pairwise availability in that list
does not define the PCA matrix or its scoring population.

## 6. Lexical diversity indices

| Index | Definition sketch | Guard |
| :--- | :--- | :--- |
| Guiraud $R$ | $\mathrm{TTR} \sqrt{N}$ | length-dependent; prefer with HD-D |
| HD-D | hypergeometric expected TTR of one 42-token draw without replacement from whole-text type frequencies | $\ge 100$ tokens else `null` |
| MTLD | arithmetic mean $\tfrac12(N/F_{\mathrm{forward}}+N/F_{\mathrm{reverse}})$; factor completes at TTR ≤0.72; trailing weight $(1-\mathrm{TTR})/(1-0.72)$ | $\ge100$ tokens; zero factors/all-unique input → `null`; no minimum run length |
| MATTR | mean TTR over sliding 50-token windows | window length |
| Maas $a^2$ | $a^2 = (\log_{10} N - \log_{10} V)/(\log_{10} N)^2$ | $\ge 100$ tokens; base 10 as in the implementation |
| Yule $K$ | $10^4 \cdot (\sum m^2 V_m - N)/N^2$ | length-dependent by design |

MTLD now averages directional $N/F$ scores arithmetically, following the
original-style `mtldo` aggregation in the
[author-lab TAALED reference](https://github.com/LCR-ADS-Lab/TAALED/blob/f3c39692b01efa84e39e4de69f8ac109ac1c4bcd/taaled/ld.py).
The previous combination averaged factors first, yielding the harmonic mean
of directional scores. Lixity retains its inclusive threshold, fractional
remainder, no minimum run length and local availability policies. TAALED's
segmentation conventions differ, so complete tool equivalence is not claimed.
The original McCarthy–Jarvis full paper was unavailable for this review; the
author-lab source supports the narrower aggregation claim. See
[STABILITY.md](STABILITY.md#lexical-diversity) for comparison limits.

The 100-token floor is a local short-text policy, not a universal reliability
threshold. Maas is defined for a one-type text: $N=100$, $V=1$ gives $a^2=0.5$.
Only a nonpositive type count or an input below the token floor is unavailable;
repetition alone is not a missing measurement. Guiraud $R=V/\sqrt{N}$ remains
length-dependent and does not make arbitrary texts directly comparable.

For $N$ tokens, type counts $f_t$, and draw size $d=42$, the implemented
expectation is

$$
\mathrm{HD\text{-}D} = \frac{1}{d}\sum_t
\left(1-\frac{\binom{N-f_t}{d}}{\binom{N}{d}}\right),
$$

where $\binom{N-f_t}{d}=0$ if fewer than $d$ non-$t$ tokens remain. The
frequency histogram makes the result independent of token order. The public
`seed` and `min_samples` arguments remain accepted legacy no-ops that emit a
`DeprecationWarning` when explicitly supplied. Ordinary calls omit them and
remain warning-free. The second value of `hd_d_stats` is `0.0` because this
exact expectation has no Monte Carlo sampling error; it does not estimate
uncertainty about a population of possible texts.

Before version 1.16.0, the `hd_d` key held mean Gini–Simpson diversity over
sampled, contiguous 35-token windows, with a window-based plug-in SE. Those
numbers are **not comparable** with corrected HD-D even though the JSON key is
unchanged. Reanalyze the original manuscript and regenerate chapter metrics,
style baselines, reports, and passports before comparing or publishing results
across that boundary. The new 100-token floor also makes values available for
100–174-token inputs that previously returned `null` by default.

## 7. Language-specific readability

Seven named formula variants, selected by profile; the implemented coefficients
are fixed and covered by hand-computed tests:

| Lang | Formula (name) | Implemented formula |
| :---: | :--- | :--- |
| de | Amstad / Flesch-De | $180 - 1.0\cdot\mathrm{ASL} - 58.5\cdot\mathrm{ASW}$ |
| en | Flesch | $206.835 - 1.015\cdot\mathrm{ASL} - 84.6\cdot\mathrm{ASW}$ |
| fr | Kandel-Moles | $207.0 - 1.015\cdot\mathrm{ASL} - 73.6\cdot\mathrm{ASW}$ |
| es | Szigriszt-Pazos | $206.835 - 1.0\cdot\mathrm{ASL} - 62.35\cdot\mathrm{ASW}$ |
| it | Franchina-Vacca | $217.0 - 1.3\cdot\mathrm{ASL} - 60.0\cdot\mathrm{ASW}$ |
| pt | Martins | $248.835 - 1.015\cdot\mathrm{ASL} - 84.6\cdot\mathrm{ASW}$ |
| nl | Douma | $207.0 - 0.93\cdot\mathrm{ASL} - 77.0\cdot\mathrm{ASW}$ |

$\mathrm{ASL}$ = words per sentence; $\mathrm{ASW}$ = syllables per word
(heuristic syllable counter), not syllables per 100 words. These scores are
not clipped to 0–100. The coefficients above match `language_data.READABILITY`;
correct formula dispatch is not empirical validation on every manuscript. **LIX** uses the
standard Björnsson cut: words with **more than six characters**, for every
language: $\mathrm{LIX} = \mathrm{ASL} + 100 \cdot \frac{\text{long words}}{\text{tokens}}$.

## 8. Jensen–Shannon divergence (chapter ↔ rest)

$JSD(P \| Q) = \tfrac12 D_{\mathrm{KL}}(P \| M) + \tfrac12 D_{\mathrm{KL}}(Q \| M)$
with $M = \tfrac12(P+Q)$. The implementation uses natural logarithms, so the
divergence is in $[0,\ln 2]$ nats. It is zero for identical distributions,
regardless of their token counts. Driver words present in the chapter are ranked
by their additive contribution to this expression, excluding function words.
Types absent from the chapter contribute half their rest-corpus probability
times $\ln 2$; their total probability is calculated from the observed rest
distribution. No square root or base-2 rescaling is applied.

Version 1.16.0 corrects the absent-type probability calculation, which could
previously produce negative divergence. Recompute older metrics before comparing
chapter profiles across this release. JSD describes lexical difference, not
quality, attribution, or historical accuracy.

## 9. Paragraph layers (within-chapter colouring)

Each chapter is its own reference: robust $z$ of the paragraph value against
that chapter’s paragraph median/MAD ($n \ge 3$ measurable paragraphs, else
skipped). Layer fill uses the absolute value span (min–max per dimension);
the ring marks $\lvert z \rvert \ge 1.5$ (unusual **for this chapter**).

The separate showing/telling composite standardizes each raw signal against
the manuscript's chapter median/MAD, then averages the telling and showing
groups. If MAD is zero, it uses population standard deviation when available.
Fewer than three chapters or zero spread produce zero component scores.
`most_telling` and `most_showing` are empty when all balances are identical,
including this insufficient-data fallback; chapter-order ties are not evidence
of a ranking. These signals describe relative patterns, not prose quality.

## 10. Determinism contract

- No wall-clock in the analysis path; HD-D is an exact frequency calculation.
- Float operations in fixed order on the same interpreter → byte-identical
  HTML/JSON (platform last-bit differences are documented in STABILITY).
- `python -W error` test run + `mypy --strict` + ruff gate every change.

## Where to plug new thresholds

| Surface | Hook |
| :--- | :--- |
| CLI | `--z-mild`, `--z-strong`, `--fdr-q`, `--fdr-method`, `--dim-threshold`, `--flag-min-severity` (see USAGE) |
| API | `api.fingerprint(..., z_mild=…, fdr_q=…, fdr_method=…, …)` |
| Control UI | Settings group → POST `/api/settings` → `lixity.server.LixityServerHandler` |
| Embedders | `build_dashboard_html(..., z_mild=…, z_strong=…, fdr_q=…, flag_min_severity=…, dim_score_threshold=…)` |
| Config file | `[tool.lixity]` in `pyproject.toml`, or `lixity.toml` / `~/.config/lixity.toml` |
| Tests | `FingerprintThresholds(...)` + passport `meta` |

Resolution order per key: CLI/API flag → UI session → project config →
user config → code default (`src/lixity/config.py`).
