# Scientific review of Lixity's analysis and research pilot (September 2026)

This is a source-grounded review of the implemented `src/lixity` engine and
experimental research API, not an accuracy certification or an implementation
plan. The comparison is between code, [METHODS](../METHODS.md),
[STABILITY](../STABILITY.md), [LOCALIZATION](../LOCALIZATION.md), and the
primary works listed below. Synthetic probes contain no manuscript or archive
material. The HD-D correction below was approved and implemented before
release; the other proposals remain for discussion.

## Corrected before release: HD-D identity

The earlier `hd_d_stats` computed mean Gini–Simpson diversity of sampled,
contiguous 35-token windows, although McCarthy and Jarvis's HD-D is the
hypergeometric expected TTR of a 42-token draw from whole-text type
frequencies [S7]. The approved correction now computes that exact expectation
under the existing `hd_d` key. Its 100-token floor replaces the former default
175-token threshold. `seed` and `min_samples` remain accepted as legacy no-op
arguments. Exact computation has no Monte Carlo error; `hd_d_stats` retains a
`0.0` computational-SE return value, while chapter `style_se` omits HD-D rather
than representing population certainty. See [METHODS](../METHODS.md) §6 for the
formula and compatibility boundary.

The mismatch was demonstrable without a reference corpus. For two synthetic
200-token sequences with the same counts (100 `a`, 100 `b`), one grouped and
one alternating, the **old** `hd_d_stats(seed=42)` returned respectively
`0.0504201681` and `0.5142857143`. Corrected 42-token hypergeometric expected
TTR is identical for both:

```text
2 × [1 − C(100, 42) / C(200, 42)] / 42 = 0.0476190476
```

The old and corrected numbers cannot be compared under the unchanged JSON key.
Recompute original manuscripts through chapter metrics, baselines, reports,
and passports before cross-version analysis. Synthetic frequency fixtures,
order invariance, short-input and rare-type numerical tests cover the new
calculation; they do not establish empirical length invariance or inferential
calibration.

## Findings requiring a decision

| Priority | Finding and evidence | Consequence | Decision to discuss |
| --- | --- | --- | --- |
| **P1: interpretation of FDR** | `StyleFingerprint.from_metrics` estimates each feature's median/MAD from the same manuscript chapters it tests, forms approximate normal-tail p-values from a custom `z*`, then applies BH/BY. BH/BY are valid multiplicity procedures **given valid null p-values** under their dependence conditions [S2, S3]; those conditions are not established by unit tests or the runs/lag diagnostics. | `fdr_flagged` is a useful ranking of deviations, but the nominal `q` cannot currently be advertised as an empirically established false-discovery rate for prose. `expected_false_positives = m·P(|Z|≥z_mild)` is a model-based expectation, not a count of actual chance findings. | Preserve the field names for compatibility but prefer “FDR-selected under the stated model” in help and reports. Before a stronger statistical claim, evaluate calibration with realistic same-author chapter corpora and dependency/short-sample simulations. |
| **P1: rank/raw axis mismatch** | `_derive_dimensions` obtains eigenvectors and its `variance` fraction from a Spearman **rank-correlation** matrix, then projects chapter **raw robust-z** feature values onto those vectors. [S6] explains that PCA loadings and scores belong to one specified input space. | The displayed coordinates are exploratory composites, but the displayed `variance` is not demonstrably the variance share of those plotted coordinates. The fixed 2.5 axis cutoff is not a simultaneous confidence region. | Decide whether to project consistently in rank space, instead derive axes from the raw standardized feature matrix, or relabel the current coordinate/variance relation. Test each with tied, skewed and missing-feature synthetic chapters before any migration. |
| **P1: help text overstates evidence** | Current seven-language help calls Guiraud independent of length; describes Flesch as confined to 0–100; calls FDR-selected cells “most reliable”; treats expected false positives as actual chance findings; and equates perception verbs/short sentences with telling or fast pace. The code does not clip Flesch; Guiraud is length-sensitive; lexical signals do not settle narrative effect [S8–S11, S14]. | These claims may make heuristic patterns look like calibrated judgments. The welcome/matrix guidance already says color is deviation, not quality, but the specific tooltips can contradict it. | Revise localized help together, separating what is counted from what a reader might infer. Keep factual/source review and author decisions visibly distinct from lexical overlap. |

Two narrower documentation errors were corrected in `METHODS.md` during this
review without changing engine behavior. Its Benjamini–Yekutieli step-up
threshold now divides `q` by the harmonic factor, as the code and [S3] do;
the earlier prose multiplied by that factor. Its Maas $a^2$ expression now
specifies base-10 logarithms, matching `diversity.maas_a2`; the previous
natural-log notation gave different numbers because the denominator is squared
[S8].

## Evidence by domain

| Implemented surface | Scientific support | Assumptions and demonstrated limits |
| --- | --- | --- |
| Median/MAD baseline, $1.4826$ scale factor; supplementary $S_n$/$Q_n$ | Robust scale estimation is established [S1]. Median/MAD resists isolated outliers; $S_n$ and $Q_n$ are alternatives. | A normal-consistency factor does not make arbitrary chapter features normal. `sn_estimator` and `qn_estimator` use asymptotic factors without finite-sample correction, so small-chapter-set values should be treated as descriptors, not calibrated scales [S1]. |
| BH/BY selection of approximate normal-tail p-values | BH controls FDR under its stated conditions; BY uses a harmonic adjustment for wider dependence classes [S2, S3]. | The procedures do not validate Lixity's input p-values. Chapters share the estimated baseline and narrative order, and the repository has no external null corpus or empirical calibration. `low_power`, runs and autocorrelation diagnostics are useful warnings, not a proof of exchangeability. |
| Chapter-to-rest Jensen–Shannon divergence and signed keyness $G^2$ | JSD is finite and bounded for distributions [S4]; full term/nonterm likelihood-ratio keyness is grounded in corpus statistics [S5]. | The recent four-cell $G^2$ and missing-type JSD corrections match their formulas. JSD measures a token-distribution difference, and keyness identifies overrepresented terms; neither establishes historical truth, relevance or authorial quality. Keyness lists have no multiple-testing adjustment. |
| Spearman axes and 3D manuscript style view | Data-derived axes are useful exploratory reduction; their orientation and variance depend on preprocessing and input data [S6]. | Lixity's rank-derived loadings/raw-z score mismatch above needs a choice. Its per-axis threshold is a visual heuristic, not a confidence region or universal quality scale. |
| TTR, Guiraud, MTLD, MATTR, Maas, Yule and corrected HD-D | Lexical-diversity indices measure different facets; McCarthy and Jarvis recommend several indices together [S7]. Bestgen documents two distinct length problems [S8]. | TTR and Guiraud are length-sensitive. A fixed 50-token MATTR window reduces one length effect but does not erase genre, topic, tokenization or window-composition effects. Exact HD-D removes the old estimator identity error, but a token cutoff is not empirical validation of length invariance or genre portability. |
| Sentence segmentation, syllable rules and seven named readability formulas | Flesch originally modeled reading ease with sentence and syllable measures in an English setting [S9]. Language identification performance depends on text length and sample conditions [S10]. | Lixity's en/de resources are deeper than fr/es/it/pt/nl; all seven have deterministic rules, not equal demonstrated accuracy. Literary dialogue, fragments, period spelling, names, code-switching and ambiguous abbreviations can alter denominators. Scores can fall outside 0–100 and are not comparable across formulas or proof of comprehensibility. |
| Local source retention, citation offsets, context labels, claims, evidence links and decisions | TEI records the source from which a digital text derives [S11]; PROV distinguishes entities, activities and agents for provenance [S12]; historical practice separates evidence from interpretation and invites alternative readings [S13]. | The archive pins local bytes and exact passages and the author records relations. A hash verifies bytes, not whether a source accurately depicts an event. User-supplied period/perspective/language metadata remains unverified; a support link records an interpretation, not a verified entailment. |
| Chapter/pacing/tense/perception signals and lexical source comparison | Narratology analyzes order, duration, frequency, mood and voice as interpretive relations [S14]. Digital literary evidence can complement close reading rather than replace it [S15]. | Counts of short sentences, tense markers, perception verbs and shared words do not by themselves establish pace, focalization, “showing,” contextual equivalence, aesthetic merit or factual support. Cross-language lexical overlap is especially non-comparable; the current comparison flags language mismatch but still returns numeric scores for inspection. |

## Proposed sequence for discussion, not implementation

1. **Tighten current explanation without claiming calibration.** Replace the
   overconfident help in all seven UI languages, use “selected under the model”
   rather than “confirmed/reliable,” and show formula/scope/short-input limits
   near results. This can precede estimator redesign.
2. **Validate the measurement layer on bounded public or synthetic corpora.**
   Record sentence/token/syllable agreement by language and genre, starting
   with English and German. Include historical spellings, dialogue, code-mixed
   passages and short fragments; publish denominators and error categories.
   Do not infer equal accuracy from localization-key coverage.
3. **Study style-axis and flag calibration separately.** Use controlled
   same-author and shifted-style chapter sets to test null p-value behavior,
   dependence, false discoveries, rank/raw axis consistency, and sensitivity
   to chapter count and length. Do not tune thresholds to one book.
4. **Keep source criticism human-led.** If provenance interchange or richer
   context becomes useful, map explicit author-supplied fields to TEI/PROV
   concepts only after a clear use case. Distinguish archival integrity,
   quotation availability, source perspective, claim confidence and narrative
   decisions in both API and UI.

## Primary sources

- **[S1]** Peter J. Rousseeuw and Christophe Croux (1993),
  [“Alternatives to the Median Absolute Deviation”](https://wis.kuleuven.be/stat/robust/papers/publications-1993/rousseeuwcroux-alternativestomedianad-jasa-1993.pdf),
  *Journal of the American Statistical Association* 88:1273–1283.
- **[S2]** Yoav Benjamini and Yosef Hochberg (1995),
  [“Controlling the False Discovery Rate: A Practical and Powerful Approach to Multiple Testing”](https://rss.onlinelibrary.wiley.com/doi/10.1111/j.2517-6161.1995.tb02031.x),
  *Journal of the Royal Statistical Society B* 57:289–300.
- **[S3]** Yoav Benjamini and Daniel Yekutieli (2001),
  [“The Control of the False Discovery Rate in Multiple Testing under Dependency”](https://doi.org/10.1214/aos/1013699998),
  *Annals of Statistics* 29:1165–1188.
- **[S4]** Jianhua Lin (1991),
  [“Divergence Measures Based on the Shannon Entropy”](https://ieeexplore.ieee.org/document/61115/),
  *IEEE Transactions on Information Theory* 37:145–151.
- **[S5]** Ted Dunning (1993),
  [“Accurate Methods for the Statistics of Surprise and Coincidence”](https://aclanthology.org/J93-1003/),
  *Computational Linguistics* 19:61–74.
- **[S6]** Ian T. Jolliffe and Jorge Cadima (2016),
  [“Principal Component Analysis: A Review and Recent Developments”](https://doi.org/10.1098/rsta.2015.0202),
  *Philosophical Transactions of the Royal Society A* 374:20150202.
- **[S7]** Philip M. McCarthy and Scott Jarvis (2010),
  [“MTLD, vocd-D, and HD-D: A Validation Study of Sophisticated Approaches to Lexical Diversity Assessment”](https://link.springer.com/article/10.3758/BRM.42.2.381),
  *Behavior Research Methods* 42:381–392.
- **[S8]** Yves Bestgen (2024),
  [“Measuring Lexical Diversity in Texts: The Twofold Length Problem”](https://onlinelibrary.wiley.com/doi/10.1111/lang.12630),
  *Language Learning* 74:638–671.
- **[S9]** Rudolf Flesch (1948),
  [“A New Readability Yardstick”](https://doi.org/10.1037/h0057532),
  *Journal of Applied Psychology* 32:221–233.
- **[S10]** Timothy Baldwin and Marco Lui (2010),
  [“Language Identification: The Long and the Short of the Matter”](https://aclanthology.org/N10-1027/),
  *NAACL HLT*, pp. 229–237.
- **[S11]** Text Encoding Initiative Consortium (current P5),
  [“The TEI Header”](https://www.tei-c.org/Vault/P5/current/doc/tei-p5-doc/en/html/HD.html),
  especially `sourceDesc`.
- **[S12]** W3C Provenance Working Group (2013),
  [“PROV-DM: The PROV Data Model”](https://www.w3.org/TR/prov-dm/),
  W3C Recommendation.
- **[S13]** American Historical Association (amended 2023),
  [“Statement on Standards of Professional Conduct”](https://www.historians.org/resource/statement-on-standards-of-professional-conduct/).
- **[S14]** Gérard Genette (English translation 1980),
  [*Narrative Discourse: An Essay in Method*](https://utpdistribution.com/9780801410994/narrative-discourse/),
  Cornell University Press.
- **[S15]** Ted Underwood (2019),
  [*Distant Horizons: Digital Evidence and Literary Change*](https://press.uchicago.edu/ucp/books/book/chicago/D/bo35853783.html),
  University of Chicago Press.
