# Mathematical methods

Definitions, defaults and implementation limits of Lixity's measurements.
Research context and known limitations live in
[`STABILITY.md`](STABILITY.md); command flags live in [`USAGE.md`](USAGE.md).

Review thresholds are configurable heuristics, not universal laws. Read their
active values from passport `meta`; formula constants and estimator conventions
are separate from author preferences.

The earlier 1.25 corrections changed measurements and derived results.
Passport schema 5 also changes the ordered-baseline diagnostics described below.
Regenerate chapter
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
are omitted; inline emphasis and footnote anchors are stripped. Sentence
boundaries never cross a blank line: each semantic block is split on its own,
and a block without terminal punctuation stays one fragment unit. This bounded
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

**Since v0.7.6:** the shared Markdown counting projection uses Unicode NFC for
token, vocabulary, cue and syllable measurements. Configured word/cue patterns
operate on that canonical counting text; their flags are unchanged. Document
boundary patterns and appendix markers still address the original source. Manuscript
bytes, displayed quotations, line anchors and source hashes are not normalized.
Literal evidence maps complete canonical clusters back to original codepoint
ranges; ambiguous inner-cluster cuts retain counts with unavailable mapping.
Legacy raw/clean character counts still describe original codepoints, not
grapheme clusters. This is canonical equivalence, not general linguistic word
segmentation; see [Unicode UAX #29](https://www.unicode.org/reports/tr29/).

The global UI word count uses the corpus token measurement, matching its sentence
and ASL values. Paragraph/chapter profile views remain narrower: pre-chapter
prose and blockquotes can contribute to corpus counts without paragraph profiles.
The two scope explanations are separate; a missing profile is not missing prose.

v0.7.2 corrects internal straight (`'`) and curly (`’`) apostrophes in the French,
Spanish, Italian, Portuguese and Dutch default word patterns. These orthographic
tokens follow the existing profile convention, not grammatical clitic analysis.
First-person starter matching recognizes both forms while preserving the exact
original starter for diversity and entropy. Recompute affected token counts,
derived measurements and first-person start rates before comparing older outputs.

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

### Perception/filter word cues

Density features (`filter_density`, modal, passive, nominalisation) are counts
over the whole prose scope including detected quotations: a perception verb in
direct speech contributes like one in the narrating voice. The reports do not
attribute speakers. Treat a high density together with the chapter's
`dialog_pct` — a value carried by dialogue is characterisation, not narration.
A narrative-only variant of these densities is a documented candidate for a
future schema, not part of the current contract.

Since v0.7.2 the German cue list includes the indicative present and simple-past
forms of **hören** and **riechen**, alongside the existing listed forms. Their
spellings follow Duden's [hören](https://www.duden.de/konjugation/hoeren) and
[riechen](https://www.duden.de/konjugation/riechen) tables. This is a bounded lexical
extension, not a lemmatizer or a test of narrative distance. For example, a room
that *riecht nach Farbe* contributes a match even without a perceiving narrator;
a somatic description without a listed verb can contribute none. Compounds,
all tenses, subjunctives and participles are not exhaustively covered; ambiguous
*gehört* is not added as a standalone cue. Project `filter_verbs_regex` replaces
the list, including an explicitly empty pattern. Zero means no listed matches,
not an ideal style. Regenerate German filter densities and dependent comparisons
before comparing reports across this change.

### Dimension cutoffs and robust baselines

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

The shared median sorts once and retains the ordinary midpoint arithmetic. If
two finite middle values overflow their floating sum, the midpoint uses the
standard library's exact-ratio mean instead. The shared mean applies the same
fallback only when a finite input sequence overflows its ordinary sum; this
also preserves cancellation residuals that could disappear if each observation
were scaled first. MAD reuses the shared median. Ordinary finite rounding,
signed-zero and empty-input conventions are unchanged; this is not a claim of
exact arithmetic throughout every downstream statistic.

A standardized chapter–feature comparison requires at least
`FingerprintThresholds.min_chapters` observations and a nonzero MAD. Schema 5
marks insufficient references and both constant and varying zero-MAD series
explicitly. It excludes those cells from z*, nominal FDR and consistency;
zero MAD does not establish that every observation is equal. Raw values and
separately calculated Cliff's delta remain available where supported. Ranked
dimensions and structural measurements can still use varying zero-MAD series.

Text passports show unavailable reference bands and their reason. JSON uses
`null` for the band when MAD is zero and for median, sigma and band when there
are too few observations. The legacy numeric consistency sentinel is qualified
by `measured_cells` and is not a measurement when that count is zero.

## 2. Noise-adjusted deviation (z*)

Plain robust z:

$$
z_{\text{raw}} = \frac{1}{1.4826} \cdot \frac{x - \tilde{x}}{\mathrm{MAD}}
\quad (0.6745 \approx 1/1.4826\text{; implemented as the exact inverse})
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
| ASL | observed-population plug-in: $\mathrm{SE} = \sigma_s/\sqrt{N_s}$, where $\sigma_s^2=\sum_i (l_i-\bar l)^2/N_s$ |
| Sentence-length CV | delta method: $\mathrm{SE} = \frac{\mathrm{CV}}{\sqrt{2N_s}}\sqrt{1+2\,\mathrm{CV}^2}$ |
| Start entropy | plug-in variance $(H_2 - H^2)/N$ with $H_2=\sum p\log_2^2 p$; negative values clamp to 0 |
| Guiraud R | relative-error approximation $\mathrm{SE} = 0.5\,R/\sqrt{N}$ over $N$ content tokens |

Larger standard errors reduce the magnitude of $z^*$, limiting noise-driven
flags. Exact HD-D has no independent window-sampling SE: its `style_se` entry
is omitted. The fingerprint's missing-SE fallback of zero denotes no estimated
measurement SE for this feature, **not** certainty about a larger population.
These plug-ins do not establish independence of words/sentences or calibrated
null probabilities for chapter features. Zero observed events can give zero
plug-in error without establishing population certainty.

The ASL plug-in uses the observed sentence population variance (divisor $N_s$),
not the conventional sample variance (divisor $N_s-1$). For sentence lengths
10, 10, 20, 30, 30, it returns 4.0 words; the conventional sample SEM is about
4.4721 words. An empty or one-sentence unit currently has zero plug-in error,
not evidence of certainty. The manuscript's sentences are not an IID sample;
neither estimator alone establishes a confidence interval for narrative style.
Changing the estimator or one-sentence availability policy is a separate model
decision, not a correction to the descriptive sentence-length SD/CV.

The $z^*$ denominator is evaluated with a scaled Euclidean norm (`math.hypot`)
to avoid overflow and underflow from squaring extreme finite spread/SE values.
Finite operands whose difference overflows are divided before subtraction;
overflowing finite spread/SE norms are evaluated in normalized units. Ordinary
finite arithmetic and cutoff-neighbor behavior retain their existing path.
This preserves the formula and zero-spread rule; it does not calibrate the
underlying normal-tail probabilities.

Since v0.7.2, the library's `StyleFingerprint.from_metrics` boundary rejects
non-finite numeric feature values and supplied standard errors that are
nonnumeric, boolean, negative or non-finite, naming the chapter and feature in a
`ValueError`. Validation precedes comparability floors. A `None` feature remains
unavailable; an absent or `None` standard error keeps the documented zero
fallback. Invalid measurements do not become measured zero deviations.

### Comparability floors

Local minimum sizes keep tiny samples out of comparisons. They are policies,
not reliability guarantees; below a floor the affected value is unavailable
(a dash in the dashboard, `null` in JSON) and is excluded from medians, MAD,
dimensions and FDR calculations.

| Floor | Value | Applies to |
| :--- | :--- | :--- |
| Words per chapter | `MIN_COMPARABLE_WORDS` = 100 (the `MIN_TOKENS_LD` diversity floor) | every per-chapter feature comparison in the style fingerprint: z*, effect sizes, FDR sets and the reference baseline; showing/telling z-scores, means and rankings. Chapters below it keep their word counts in the matrix but receive no comparison values. Scenes stay descriptive: they show measured values with standard errors, and HD-D remains unavailable below the same word count. |
| Sentences | `MIN_COMPARABLE_SENTENCES` = 5 | sentence-distribution features: staccato share, cascade share, sentence-length CV, start entropy and first-person starts; shares, variance and entropy from fewer sentences are bound to the sample size. The sentence-length mean (`asl`) stays measurable above the word floor. |
| Sentences for variation (scenes) | 2 | scene-table sentence CV; a single-sentence unit has no variation. |

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

**Since v0.5.0:** chapters explicitly assigned through
`chapter_registers` retain their measured values, z-scores and membership in
the manuscript baseline, but are excluded from `deviations` and the FDR input
family. Here $m$ is the number of eligible cells after that exclusion.
`measured_cells`, descriptive consistency and the nominal
`expected_false_positives` reference still count all measured cells. Author
`register_profiles` ranges produce separate `register_targets` comparisons;
they supply neither a sampling distribution nor statistical significance.
See [Chapter register settings](USAGE.md#chapter-register-settings).

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

<a id="4b-exchangeability-diagnostics-baseline-quality"></a>
## 4b. Exploratory chapter-order indicators

Schema 5 replaces schema 4's `exchangeable`, `mean_lag1_rho`, `acf_critical`
and global `low_power` fields. They could imply a positive result without any
measurements and opposite feature correlations could cancel. Each entry in
`baseline_diagnostics.features` instead records `observed_chapters` and
`missing_chapters`, plus `runs_z`, `lag1_rho` and `lag1_critical` as numbers or
null. A feature with no observations has no entry. A missing chapter makes its
order statistics unavailable: observations on either side are not treated as
adjacent. A constant series or fewer than three chapters has no lag statistic;
the runs statistic additionally requires at least eight chapters.

For a complete measured series, `lag1_flagged` uses the local descriptive
cutoff $|\rho_1| \ge 1/\sqrt{n}$, with that feature's own $n$;
`runs_flagged` uses $|z| \ge 1.96$. `measured_features` counts features with
at least one available statistic. These cutoffs are exploratory heuristics,
not validated tests for literary chapter series. For example, the conventional
normal approximation for the runs test has stronger sample requirements
([NIST](https://www.itl.nist.gov/div898/handbook/eda/section3/eda35d.htm)).
Neither a flag nor its absence establishes exchangeability, independence,
calibrated probabilities or an artistic judgment.

## 4c. Structural diagnostics (`structural_diagnostics`)

Pure-stdlib structural and distributional diagnostics over the ordered
per-feature series (chapters in order) plus token-level lexical diagnostics
when the passport is built from source text (`api.fingerprint`, `lixity style`,
`lixity build`, `lixity dashboard`). They add exploratory ordered-series and
lexical contrasts alongside the per-cell z\*/FDR layer; calculation and model
limits are listed below.

| Key | Estimator | Guard / notes |
| :--- | :--- | :--- |
| `changepoints` | exact unpruned dynamic programming for guarded cost $n\ln\sigma^2$ and penalty $2\ln n$ | singleton/zero-variance costs are zero; anchored centred moments; $O(n^2)$ time, $O(n)$ storage; a feature with missing chapters or $n<3$ is listed in `segmentation_unavailable`; complete series use 0-based indices of the first chapter after a break |
| `trends` | Mann–Kendall $S$ with tie-corrected normal $p$ and continuity correction; $\tau=S/\binom n2$ is tau-a | uses the available observations in chapter order; $n<3$ → unavailable; partial series are listed in `trend_incomplete`, with observed and missing chapter IDs in `baseline_diagnostics.features`; not tie-normalized tau-b |
| `robust_scales` | Sn: low outer median of high inner medians, including self-distances, ×1.1926; Qn: sorted pairwise distance at rank $\binom{\lfloor n/2\rfloor+1}{2}$, ×2.21914 | Gaussian asymptotic factors; no finite-sample correction; $n<2$ → 0 |
| `tail_index` | **Hill** estimator $\hat\alpha = \bigl[\tfrac1k\sum\ln\frac{x_{(n-i+1)}}{x_{(n-k)}}\bigr]^{-1}$ over the $k$ largest values | $n \ge 5$, $k=\lfloor\sqrt n\rfloor$ (or user $k\ge 2$); non-positive threshold → `None`; $k \ge n$ → `None` |
| `distribution_shift` | exact empirical-CDF Wasserstein $W_1$ and two-sample KS $D$; stable asymptotic KS $p$ | the chapter sequence is split before dropping unavailable values; both original halves need $\ge2$ observations or the feature is listed in `distribution_unavailable`; computed but partial comparisons appear in `distribution_incomplete`. Coverage is in `baseline_diagnostics.features`. $D=0$ → $p=1$; $p$ is not calibrated for tied/fitted distributions |
| `trending_features` | feature names with Mann–Kendall $p < 0.05$ | summary list |
| `segmented_features` | feature names with at least one guarded-objective changepoint | summary list |
| `shifted_features` | feature names with early/late KS $p < 0.05$ | summary list |
| `cooccurrence` *(token-level)* | content-word graph (window 2; single-character tokens excluded); approximate discrete exponent $\hat\alpha=1+n/\sum\ln(k_i/(k_{\min}-0.5))$ and fitted-CDF comparison | estimator follows Clauset–Shalizi–Newman Eq. 3.7; current truncated continuous CDF and ordinary KS $p$ do not establish discrete power-law goodness of fit; ≥50 content tokens, ≥5 positive nonconstant degrees |
| `keyness` *(token-level)* | **Dunning $G^2$** (log-likelihood ratio) of first-half chapters vs second half, content words only (single-character tokens excluded); signed so positive = over in the early half | both halves ≥ 20 content tokens; single-chapter texts omit `keyness` |

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

Since v0.7.6, near-null keyness uses exact integer table residuals and a centered
deviance series for small relative residuals, avoiding cancellation of a small
positive divergence into zero. Lag-1 sample autocorrelation uses anchored,
scaled centered moments and accurate summation to avoid avoidable overflow,
underflow and constant-sample roundoff. Constant samples remain unavailable.
These are numerical corrections to the existing estimators, not new statistical
calibrations; independent high-precision Decimal calculations cover their
extreme-scale and near-null regression cases.

The structural diagnostics retain their field names in schema 5. The structural summary
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
does not define the PCA matrix or its scoring population. The list is capped
at the ten strongest pairs.

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
not clipped to 0–100. Empty or fully unmeasurable input returns `0.0` as an
explicit unavailable sentinel, not a readability score. The coefficients above match `language_data.READABILITY`;
correct formula dispatch is not empirical validation on every manuscript. **LIX** uses the
standard Björnsson cut: words with **more than six characters**, for every
language: $\mathrm{LIX} = \mathrm{ASL} + 100 \cdot \frac{\text{long words}}{\text{tokens}}$.

The Spanish syllable estimate counts orthographic vowel nuclei: standalone
closed vowels (`i`, `u`) count, open/unstressed-closed combinations and distinct
closed-vowel pairs can share a nucleus, and marked hiatus remains separate.
Triphthongs use the closed/open/closed pattern. Standard silent `u` in
`que`/`qui`/`gue`/`gui` is omitted; pronounced `ü` is retained, and interposed
`h` does not itself block grouping. These bounded spelling rules follow the
RAE/ASALE explanations of [diphthongs](https://www.rae.es/dpd/diptongo),
[hiatus](https://www.rae.es/dpd/hiato) and [the letter u](https://www.rae.es/dpd/u).
They are an orthographic proxy, not phonetic transcription: regional hiatus,
foreign names and loans, and poetic synaeresis remain outside the estimate.
Regression examples do not establish language-wide accuracy or reader comprehension.

**Since v0.7.2:** the estimator corrects skipped closed-vowel nuclei in Spanish, for example
`vivir` from one estimated syllable to two and `dibujo` from one to three.
This changes Spanish ASW and its derived readability score without changing
the formula coefficients or JSON fields. Regenerate Spanish reports before
comparing results across this correction.

## 8. Jensen–Shannon divergence (chapter ↔ rest)

$JSD(P \| Q) = \tfrac12 D_{\mathrm{KL}}(P \| M) + \tfrac12 D_{\mathrm{KL}}(Q \| M)$
with $M = \tfrac12(P+Q)$. The implementation uses natural logarithms, so the
divergence is in $[0,\ln 2]$ nats. It is zero for identical distributions,
regardless of their token counts. This is the equal-weight form of
[Lin's Jensen–Shannon divergence (1991, §IV)](https://www.cise.ufl.edu/~anand/sp06/jensen-shannon.pdf).
Driver words present in the chapter are ranked by their positive additive
contribution, excluding function words and single-character tokens.
Types absent from the chapter contribute half their rest-corpus probability
times $\ln 2$; their total probability is calculated from the observed rest
distribution. No square root or base-2 rescaling is applied.

The interface names the observable **Word distribution (JSD)** and explains the
divergence. It does not label this number a mathematical distance: the
[Jensen–Shannon distance](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.distance.jensenshannon.html)
is its square root. Topics and proper names can change word distributions without
establishing a change of writing style.

**Since v0.7.2:** absent-type mass is computed from remaining
integer token counts, and contributions are accumulated with `math.fsum`.
Near equal probabilities, the same per-type contribution is evaluated as
$m[d\mathrm{atanh}(d)+\tfrac12\ln(1-d^2)]$, where
$m=(p+q)/2$ and $d=(p-q)/(p+q)$; the contrast is derived from count cross-products
before probabilities are rounded. This avoids cancellation of first-order
logarithmic terms. No fixed epsilon suppresses small genuine divergence.
Unchanged-rate words are omitted from the driver list; identical distributions
return zero and an empty list. The definition, natural-log units and JSON fields
are unchanged.

Version 1.16.0 corrects the absent-type probability calculation, which could
previously produce negative divergence. Recompute older metrics before comparing
chapter profiles across this release. With no chapter tokens or no remaining
corpus tokens, `0.0` and an empty driver list mean unavailable, rather than
measured agreement. JSD uses empirical token frequencies and ignores word order
and narrative context. Its values and driver rankings are descriptive; they
provide no calibrated probability, significance test, quality assessment,
attribution or historical-accuracy judgment.

## 9. Paragraph layers (within-chapter colouring)

Each chapter is its own reference: robust $z$ of the paragraph value against
that chapter’s paragraph median/MAD ($n \ge 3$ measurable paragraphs, else
skipped). Layer fill uses the absolute value span (min–max per dimension);
the ring marks $\lvert z \rvert \ge 1.5$ (unusual **for this chapter**).

The **Signal-group comparison** (command `showing`) standardizes each raw signal
against the manuscript's chapter median/MAD, then averages each group with equal
feature weights: four word-pattern cues versus quoted-word and short-sentence
shares. The displayed difference is second group minus first. Zero spread uses
the population standard deviation when available. The `tell_z`/`show_z` names are
machine identities, not evidence for a validated narrative-distance construct.
Fewer than three sufficiently long chapters leave component scores and means
unavailable. With sufficient chapters, a constant component has zero relative
variation. `most_telling` and `most_showing` are empty when balances are
unavailable or identical; chapter-order ties are not evidence of a ranking.
These signals describe relative patterns, not prose quality.

## 10. Determinism contract

- No wall-clock in the analysis path; HD-D is an exact frequency calculation.
- Float operations in fixed order on the same interpreter → byte-identical
  HTML/JSON (platform last-bit differences are documented in STABILITY).

## 11. Linguistic analysis (tense, dialogue, sentences, scenes)

### Optional grammatical analysis

The optional `tense_model` setting selects contextual POS/morphology/dependency
analysis with an explicitly installed local spaCy or explicitly profiled Stanza
pipeline. Language-specific composition covers de/en/fr/es/it/pt/nl. `grammatical_tense.py`
composes auxiliary-linked German verbal complexes using TIGER `oc`/`pd` or UD
`aux`/`aux:tense`/`aux:pass`/`cop` relations (English also `auxpass`), with
coordinated auxiliary inheritance and shared nonverbal predicate heads. French/Italian
reflexives and positive intransitive auxiliary licensing distinguish some perfect
forms from simple be-passives; unlicensed ambiguous forms remain limited. This is an
independent implementation informed by [IDS Grammis](https://grammis.ids-mannheim.de/progr%40mm/1695)
and [Dönicke (2020)](https://aclanthology.org/2020.tlt-1.1/), not a reproduction of
that paper's evaluated system. The published 92.6% score does not apply to Lixity.

Nested coordination follows the [UD conjunct chain](https://universaldependencies.org/u/dep/conj.html),
stopping at a finite component instead of borrowing across a separate finite
clause. A shared token validator rejects duplicate/missing indices, cycles and
source-span mismatches; expanded words may share their original token span.

The finite carrier's tense and mood are composed with participles, infinitives,
replacement infinitives and passive auxiliaries. Resolved simple present maps
to present; preterite, imperfect, perfect, pluperfect and anterior perfect map to
past. Absent English/Dutch Mood features remain `unmarked`, not indicative. Future and subjunctive
forms remain separate and do not enter the binary counts. Ambiguous unlicensed
`sein`/participle complexes remain unresolved. The existing curated `sein` inventory
provides positive licensing only, not a complete valency lexicon.

Each canonical prose paragraph is parsed consistently across corpus/profile calls;
quotation scope is resolved over chapter-bounded prose before counting. Exact
immutable parse results have a process-local LRU bounded to 256 entries and one
million input characters. Models are explicitly loaded and cached; changing a
model installation requires restart. The engine never sends text to a provider.
The grammatical record carries a versioned policy and runtime/model identity;
UI cue mapping still uses the existing NFC-to-original-source projection.

This resolves many suffix collisions without certifying grammatical accuracy.
See the [bounded evaluation and known errors](STABILITY.md#grammatical-tense).



These heuristics are transparent rules over curated resources, not a
grammatical parser. Their constants and guards live in the named modules.
Shared mathematical primitives (robust scale, significance z, normal tail,
ratio/share/density totalization, plug-in standard errors and published effect
bands) come from `lixity.math_core`; heuristics import them instead of
restating formulas.

| Heuristic | Rule | Limits |
| :--- | :--- | :--- |
| Sentence bins | ≤ 6 / 7–15 / 16–25 / > 25 words (`analyzer.py`, `pacing.py`) | Bins describe the supplied text; tokenless fragments distort ASL |
| Hook | Closing sentence ≤ `HOOK_SHORT_SENTENCE` (8) words, ending in `?`, `!` or `…`, or containing detected dialogue (`pacing.py`) | Each condition adds one point; this is not a validated suspense measure. Only the ellipsis character scores; `...` does not |
| Dialogue paragraph | ≥ 50 % of the paragraph's words inside dialogue spans (`dialogue.py`) | Quotation conventions differ per language |
| Tense mixed/switch | `mixed`: ≥ 2 present and ≥ 2 past markers and minority share ≥ 25 %; `switch`: the dominant tense changes between consecutive paragraphs (`style_profile.py`) | Lexical cues and language-specific patterns are incomplete and can be ambiguous; they are not grammatical parses. Since v0.7.7, an unknown German `-te/-ten/-test` ending alone is not a past cue; no productive present pattern |
| Sentence splitter | Language abbreviation tables, digit and initial guards; utterance `no.`/`co.` split; prose splits keep blank-line block boundaries (`split_prose_sentences`) | Tables are curated and incomplete; tokenless fragments are not sentences; an unterminated block stays one fragment unit with its token length |
| Severity | `classify_severity` truth table; defaults: 3 = switch + mixed + minority ≥ 3, 2 = (switch + minority ≥ 2) or (mixed + minority ≥ 3), 1 = either, 0 = neither | Only `flag_min_severity` reaches CLI/API/config; other `ProfileThresholds` fields need direct `ParagraphProfiler` construction |
| Dominance | Neutral with at most one marker; otherwise present when `present/(past+ε) > 1.5`, past when `< 0.67`, mixed within the band; ε = 0.001 (`style_profile.py`) | Ratio bands are conventions, not measured boundaries |
| Nominal/adjective suffixes | Curated suffix cues; default nominal cues exclude curated function words (`language_data.py`) | Over-include (e.g. `month/health/truth`, `König/Saal`, `Musik/Natur`); adjective cues have no equivalent function-word exclusion |
| Modal lexicons | Curated forms per language | Unequal morphology coverage; not cross-language comparable |

**Since v0.7.6:** nominal ending lists include selected plural forms in each
language, including `Entscheidungen`, `decisions`, `décisions`, `decisiones`,
`decisioni`, `decisões` and `beslissingen`. German `zur` belongs to the curated
function words and is excluded from default nominal matches. This corrects
number-dependent undercounting and a suffix collision; it does not distinguish
nouns from homographic verbs or establish nominal writing style. Explicit
`nominal_regex` overrides still replace the default rule. Recompute affected
densities and derived comparisons before comparing older reports.

The UI calls this measurement **Noun endings**, rather than claiming to measure
nominal style. Nominal style can express an action as a noun phrase ("the
examination" rather than "we examine"); a suffix counter cannot establish that
syntactic choice. Localized examples explain the distinction before the
counted-text and statistical comparison instructions. Counts and numeric keys
are unchanged by this presentation.

The analogous **Adjective endings** measurement counts selected suffix matches,
not grammatical adjective tokens or attributive syntax. Untagged word patterns
can both miss adjectives and match other word classes. Participle-shaped words
also need context: the [Universal Dependencies annotation guidance](https://universaldependencies.org/u/dep/aux-pass.html)
explicitly distinguishes passive auxiliaries from copular uses of participles.
The lightweight passive measurement therefore remains a cue count; a match does
not resolve whether an ambiguous participle is adjectival or verbal.

Configured cue patterns override the profile patterns for direct Python calls.
**Since v0.7.6:** `lixity.tense.TenseMatcher` owns tense counting for chapters,
scenes and paragraph profiles. With default patterns, a standalone productive
past candidate, or a pronoun-plus-finite candidate, is rejected when the finite
word is explicitly listed as present and not past in the curated inventory.
Auxiliary-plus-participle candidates are preserved, including participles that
also occur as finite forms (`haben erzählt`, `a écrit`). This corrects collisions such as
German `halten` and Dutch `Wij moeten`; it does not infer syntax from endings.
**Since v0.7.7:** German removes the unrestricted weak-past suffix rule used in
v0.7.6: `feuchten` and `kunstvollsten` no longer become past cues merely from
their endings. Selected forms of `üben` and `singen` have been added to the
lexicon, including `übt`; unknown regular past forms such as `flatterten` can
now be missed. Listed forms can still be ambiguous, as can auxiliary/participle
matches. This intentionally changes the counts and dependent results; regenerate
analyses before comparison and review old decisions against the new evidence.
In German, listed auxiliary/participle pairs additionally form one past cue;
their contained lexical matches are consumed, so three recognized perfect
constructions give three past cues and no present-auxiliary double count.
Productive lowercase `ge-…-t/-en` and `-iert` candidates can additionally resolve
with a form of `haben` at a bounded punctuation/end-of-text predicate-head edge.
Weak `ge-…-t` stems require at least two letters (`geübt`, `geölt`); strong
`ge-…-en` and `-iert` stems require at least three. A bounded inventory of
separable preverbs also admits forms such as `eingekauft`, `aufgeräumt` and
`abgeholt`. Curated finite forms and function words remain excluded. This covers `habe geschlafen/getroffen/gehabt`
without expanding the participle inventory. An immediately following `worden`
also licenses the passive perfect with `sein`, including `ist renoviert worden`.
An unlisted `sein` + participle without `worden` remains unresolved. This is
incomplete morphology: unlisted/combined preverbs and inseparable-prefix forms
such as `wiedergutgemacht` and `vorbereitet` remain outside the new productive rule.
No new `sein` licensing is inferred from a recognized prefix. Nominal/adjectival continuations
are not resolved merely because a word has a matching ending.
The German display label is therefore `Vergangenheit`, not the narrower
grammatical form `Präteritum`.
Up to three intervening words are allowed in a bounded word window. Punctuation, blank
lines, conjunctions and intervening listed finite verbs/auxiliaries stop the scan.
The rightmost listed candidate within that window owns the span, so a preceding
participial modifier does not create a second past cue (`geschlossen gehalten`).
Listed `sein … worden` passive-perfect patterns follow the same span ownership.
The auxiliary selection follows the distinction described by
[IDS grammis](https://grammis.ids-mannheim.de/fragen/86), which also documents
regional and object-dependent variants. Inventory absence is not proof of
incompatibility: unresolved pairs retain lexical ambiguity, including state,
regional and transitive readings. Unlisted compounds, longer gaps and other
languages are not a complete grammatical tense analysis. German nominal
capitalization rejects broad compound guesses such as `habe Bedenken`;
it is a cue guard, not part-of-speech tagging.

Explicitly overriding either tense pattern preserves
independent pattern counting, including empty patterns. The review-policy identity
changes with these semantics, so saved decisions require renewed review rather
than silently carrying over to a changed measurement.

Passive patterns retain auxiliary context while allowing shorter regular stems
and selected irregular forms (`rotas`, `rotte`, `lette`, `lues`, `lidas`) and
Spanish accented `leídas`. Irregulars need lexical coverage; lowering a stem
length alone would not recognize them (see the
[RAE participle reference](https://www.rae.es/gramática/morfología/verbos-irregulares-iv-pretéritos-fuertes-y-participios-irregulares)).
Morphology-specific limits keep French `est ici` and `est plus grand` outside
the expanded short accented-participle pattern. Italian `stato/stati` can be
intermediate auxiliaries before a lexical participle, not passive heads by
themselves. Negative examples such as `son vida`, `est si`, `are red` and
`sono stati a casa` constrain broadening.
German `sein + participle` state passive is not silently added to the event-
passive metric. A zero remains zero detected cues, not proof of active voice.

Cue patterns (including `dialogue_regex`) use the case-insensitive cue
contract from §2 across the analysis core and the `dialogue`/`pacing` reports.
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

## Method currency and recent literature

The lexical-diversity and readability choices follow the current methodological
literature and are re-checked when it changes:

- **Length dependence.** Bestgen's 2024 methodological review confirms that the
  classic length problem of lexical diversity is addressed by length-reducing
  indices, but that the reduction parameter itself becomes a source of
  variance. The review recommends HD-D for an overall score and MATTR/MTLD for
  local trajectories, with a fixed parameter for cross-text comparability.
  Lixity computes HD-D on a 42-token draw — the review's preferred value for
  comparability — reports MTLD and MATTR with fixed windows, and treats
  per-chapter values as short-text estimates. The same review shows that MATTR
  weights tokens by position, which is why Lixity reports it as a local measure
  and keeps HD-D as the corpus-level index.
- **Minimum text lengths.** Koizumi & In'nami (2012) and Zenker & Kyle (2020)
  quantify when lexical-diversity indices stabilise. Lixity states these limits
  in the interface and marks unavailable results instead of hiding them.
- **Measurement noise.** Kyle et al. (2024) evaluate reliability and validity of
  lexical-diversity indices against proficiency scores. Lixity follows the same
  principle with its standard-error approximations (`style_se`) and the
  noise-adjusted deviation `z*` rather than presenting a bare rank.

Adjacent tasks are deliberately out of scope. Authorship attribution and
LLM-generated-text detection are separate research fields with their own
benchmarks and models (Huang et al. 2024; Weerasinghe et al. 2025); their
results depend on the candidate set, the domain and the generator version.
Lixity describes the observable patterns of one manuscript. Every signal stays a
prompt for reading, never a verdict about authorship, quality or machine origin.

References:

- Bestgen, Y. (2024). *Measuring lexical diversity in texts: The twofold length
  problem.* *Language Learning* 74(3), 638–671. doi:10.1111/lang.12630
- Bestgen, Y. (2024). *Estimating lexical diversity using the moving average
  type-token ratio (MATTR): Pros and cons.* (Positional weighting of MATTR.)
- Covington, M. A., & McFall, J. D. (2010). Cutting the Gordian knot: The
  moving-average type-token ratio (MATTR). *Journal of Quantitative
  Linguistics* 17(2), 94–100. doi:10.1080/09296171003643098
- Huang, R., et al. (2024). *Authorship attribution in the era of LLMs:
  Problems, methodologies, and challenges.* arXiv:2408.08946.
- Koizumi, R., & In'nami, Y. (2012). Effects of text length on lexical
  diversity measures. *System* 40(4), 554–564. doi:10.1016/j.system.2012.10.012
- Kyle, K., Sung, H., Eguchi, M., & Zenker, F. (2024). Evaluating evidence for
  the reliability and validity of lexical diversity indices. *Studies in Second
  Language Acquisition* 46(1), 278–299. doi:10.1017/S0272263123000402
- McCarthy, P. M., & Jarvis, S. (2010). MTLD, vocd-D, and HD-D: A validation
  study. *Behavior Research Methods* 42(2), 381–392. doi:10.3758/BRM.42.2.381
- Weerasinghe, J., et al. (2025). Be sure to use the same writing style:
  Applying authorship verification on large-language-model-generated texts.
  *Applied Sciences* 15(5), 2467. doi:10.3390/app15052467
- Zenker, F., & Kyle, K. (2020). Investigating minimum text lengths for lexical
  diversity indices. *Assessing Writing* 47, 100505.
  doi:10.1016/j.asw.2020.100505
