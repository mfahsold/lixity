# Stability & known limitations

Use this page to judge what a result can support. Formula details live in
[METHODS.md](METHODS.md); machine-readable thresholds and availability policies
come from `lixity about --json`. This page keeps interpretation and integration
limits that a passing check cannot resolve. Statistical signals support human
review, not a prose grade.

## 1. Research findings (state of the art)

### Release verification and limits

The maintained suite checks English defaults, language resource-key coverage,
readability-coefficient dispatch and locale formatting. These are software
contracts, not empirical validation of linguistic accuracy across seven
languages. No language-wide accuracy percentage is established by this suite.

The 3D chapter view is exploratory: its dimensions are corpus-specific, signs
are fixed by convention, and per-axis thresholds are not simultaneous confidence
regions. Native rotation/zoom buttons and a chapter-score table provide keyboard and touch access to the displayed scores,
flag status and chapter navigation. Individual canvas points remain pointer-operated.
These targeted checks do not establish full assistive-technology coverage.

Engine tests use synthetic/public samples. Project adapters and optional local
servers have separate trust boundaries and need their own tests; core test
success is not a security certification for an arbitrary adapter.

### Manual manuscript association limits

Manually selected quotes require explicit retention and exact source/paragraph/claim
pins. Anchor review detects structural changes, not semantic contradictions or
factual support. Moved or ambiguous quotes require review; claim pins change only
through an explicit revision. Zero saved links do not prove a claim is unused.
The source recheck is optimistic and does not lock manuscript editors. Backups
include retained private quotes; this workflow creates no full manuscript blob.
See [retention and compatibility](research/USAGE.md#associate-a-manuscript-quote-with-a-claim).

### Research and external-library limits

Zotero owns bibliography and reading; Lixity retains selected evidence and authored
records. Their backup requirements are separate. An integrity audit verifies
retained bytes, references and citations; it cannot verify historical truth,
chronology or the completeness of an external library. Native integration checks
are bounded synthetic tests, not certification of every platform or collection.

Source analysis uses its own `source_internal` reference and unverified supplied
context. Retaining a historical source does not make it a manuscript style norm;
lexical overlap does not establish factual support or appropriate context.
Search does not resolve contradictory prose or accept a hypothesis for the author.

PNG/JPEG images retain exact source versions and stay outside text analysis.
Header validation and browser preview do not establish complete codec validity or
historical authenticity. Geographic coordinates and routes are authored data;
rendering a map does not verify a journey or sightline. An unavailable image
never silently resolves to a different version.

RIS migration is additive; verify attachment identities, retained citations and
restoration before retiring a workflow. Automatic background/cloud synchronization,
audio/video transcription, image OCR and visual AI are not implemented. PDF
extraction or an external OCR worker does not establish recognition accuracy.
Current media, provider and schema boundaries live in [Research usage](research/USAGE.md).

### Robust comparisons and statistical claims

Median/MAD and the noise-adjusted $z^*$ describe contrast within the supplied
manuscript. A normal-consistency multiplier does not make arbitrary chapter
features normally distributed. Missing SE means no estimated measurement error;
zero event counts or constant samples do not establish certainty.

BH/BY are established selection procedures **given valid null probabilities**
and their dependence conditions. Lixity's normal-tail probabilities use a
baseline estimated from the same chapters; their calibration is not established.
BY, runs/lag diagnostics and the `low_power` flag do not repair that gap.
`fdr_flagged` means selected under the implemented model, and
`expected_false_positives` is a standard-normal reference expectation, not an
observed error count. Cliff's delta describes ordinal contrast, not quality.
Definitions and active thresholds: [METHODS §§1–4](METHODS.md#1-robust-house-style-baseline).

Style axes now use PCA of standardized tied midranks on one common complete
chapter set. Covariance, explained variance and scores share that rank space;
missing measurements are not imputed. At least three complete chapters and
three varying baseline-usable features are required, with constant columns
dropped on that set. Incomplete chapters have no dimension scores. Complete-case selection and small samples still limit interpretation. Score flags are
descriptive and do not validate prose quality or simultaneous confidence.
See [METHODS §5](METHODS.md#5-exploratory-style-dimensions).

### Lexical diversity

Length, local vocabulary and estimator parameters affect different indices.
[Bestgen (2024)](https://doi.org/10.1111/lang.12630) studies English learner essays
and monologues; 60 tokens is one truncation condition, not a universal floor.
Its main experiment uses a 50-token draw/window parameter, so it does not
directly calibrate Lixity's 42-token HD-D.
[Kyle et al. (2024)](https://doi.org/10.1017/S0272263123000402) assesses optimized
oral-task variants, not Lixity's defaults on German novels. Neither establishes
genre-wide reliability for the local 100-token policy. Guiraud remains sensitive
to length; fixed-window MATTR and fixed-draw HD-D still depend on their parameters
and the supplied vocabulary distribution.

HD-D is exact expected TTR for a fixed draw. Exact computation removes Monte Carlo
error, not population uncertainty. MTLD variants also differ in direction
averaging, threshold and trailing-factor rules. Compare measurements only after
aligning formulas, parameters and segmentation; regenerate historical reports
when those contracts changed. See [formula and guard details](METHODS.md#6-lexical-diversity-indices).

### Linguistic proxies and literary interpretation

Analysis shares a bounded Markdown prose projection. Link labels contribute;
destinations, images, code, comments and excluded document regions do not.
Paragraph profiles preserve displayed text and source anchors separately from
counting. The configured token rules and narrower paragraph scope do not imply
complete CommonMark support or linguistic token accuracy. See
[analysis scope](METHODS.md) for the unit and denominator of each measurement.

Passive, tense, adjective, nominalization and modality fields count lexical
markers or suffixes. For example, German `werden` also marks future tense or
becoming; English `been` also appears in active perfect constructions. These
counts do not identify syntactic voice or distinguish epistemic uncertainty
from obligation. Sentence segmentation and syllables are also heuristic;
utterance abbreviations (`no.`, `co.`) split sentences and tokenless
fragments do not count as sentences.
Suffix cues over-include on purpose-ambiguous words: English nominal `-th`
counts *month/health/truth*, German adjective `-ig`/`-al` count
*König/Saal*, German nominal `-ik`/`-ur` count *Musik/Natur*. Modal lexicons
have unequal morphology coverage (German and Dutch include preterite forms,
the other profiles only present), so `modal_density` is not comparable across
languages.

Readability coefficient tests verify the declared formulas, not their original
calibration or reader comprehension. Amstad's original coefficient page and
calibration protocol have not been verified here. Scores may fall outside 0–100
and are not comparable across language formulas. [German PALME research
(2026)](https://aclanthology.org/2026.bea-1.6/) separates controlled detector tests
from graded-reader evaluation; its results do not validate Lixity's regex cues.

Showing/telling is a composite of those visible signals. Empty rankings and
zero fallback scores do not establish equal artistic effect. Without explicit
dividers, pacing scenes are chapter placeholders. Short sentences, perception
verbs and vocabulary contrast do not establish immersion, tension or a reason
to rewrite. Scene/register targets are explicit author preferences, never
hardcoded genre norms. [Underwood's expert discussion](https://tedunderwood.com/2024/01/05/can-language-models-predict-the-next-twist-in-a-story/)
illustrates why surface predictability and narrative experience differ.

Dialogue turns are quotation segments without speaker attribution. Character
mentions depend on supplied names or literal project aliases; declared viewpoint
chapters are separate metadata, not inferred first-person presence. There is no
NER or coreference. Hook and repetition scores also locate surface patterns;
deliberate calm endings and repeated motifs can be appropriate author choices.

### Structural diagnostics

These diagnostics preserve their declared numerical definitions; an exact
implementation does not validate the underlying model:

- `pelt_changepoints` uses exact unpruned dynamic programming: $O(n^2)$
  time and $O(n)$ storage. The retained singleton/zero-variance guard violates
  the PELT pruning premise, so no pruning or linear-time claim is made.
  Anchored variance updates reduce cancellation; exact optimization of this
  guarded objective does not validate its Gaussian model or a narrative break.
  [Killick et al., Theorem 3.1](https://arxiv.org/abs/1101.1438v3).
- Sn uses the original low outer/high inner medians and factor 1.1926. Qn
  preserves its pairwise-distance rank with modern factor 2.21914; neither
  applies finite-sample correction. Normal-consistency factors, finite bias
  corrections and robustness remain distinct. [Original paper](https://wis.kuleuven.be/stat/robust/papers/publications-1993/rousseeuwcroux-alternativestomedianad-jasa-1993.pdf),
  [maintained reference](https://cran.r-project.org/web/packages/robustbase/robustbase.pdf).
- Early/late Wasserstein integrates the exact empirical-CDF difference;
  merged CDFs also give KS $D$, with $D=0$ returning $p=1$ and stable survival
  evaluation. The same asymptotic probability model remains: ties, short
  samples, serial dependence and fitted distributions are not calibrated by
  this numerical correction. Mann–Kendall `tau` remains tau-a, with a
  tie-corrected approximate normal probability for $S$, not tau-b.
- The graph exponent follows the approximate discrete estimator in
  [Clauset–Shalizi–Newman Eq. 3.7](https://arxiv.org/abs/0706.1062v2).
  The current continuous fitted CDF and ordinary KS probability do not implement
  its refitted goodness-of-fit procedure. Graph degrees are dependent too;
  neither a fit distance nor a small sample certifies a scale-free graph.

Early/late splits are chapter-count midpoints, not learned narrative boundaries.
Signed Dunning keyness ranks token contrast; it has no multiplicity adjustment.
Chapter-to-rest JSD is raw divergence in nats, not its square-root distance or
an external Delta authorship test. Inspect driver words in context. Formula
details and unchanged field contracts: [METHODS §4c](METHODS.md#4c-structural-diagnostics-structural_diagnostics).

**Accessibility / data visualisation (WCAG 2.2).**
- Colour must never be the only channel (SC 1.4.1, 1.3.3): the heatmap
  prints the numeric z* values, the band chart encodes band/median/outliers
  by position and shape, every chip reveals tense + value as text on click.
- Contrast targets are 3:1 for relevant non-text UI and 4.5:1 for normal text.
  Lixity chooses heatmap text from each cell’s luminance and
  tests the full blue/orange scale. This does not certify every canvas mark or
  every color-vision condition; numeric labels remain essential.
- WCAG 2.5.8 has a 24×24 CSS-pixel minimum with defined exceptions. Paragraph
  chips and dimension controls use at least 24×24,
  increasing to 44×44 for coarse pointers. Pressed chips retain their target
  size, and long strips scroll horizontally. These checks do not establish
  conformance for the entire interface or every canvas mark.
- Diverging scales have a meaningful midpoint: zero deviation from the
  within-manuscript reference (median in the robust style calculation).
- See [visual design rationale](ARCHITECTURE.md#visual-consistency-and-evidence)
  for evidence, typography choices and the limits of automated UI checks.

## 2. Stability register

The current cross-cutting limits below replace the completed-bug checklist.
Historical fixes and release-specific evidence remain in [CHANGELOG](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md),
[release notes](https://github.com/mfahsold/lixity/tree/main/docs/releases) and the
[archived register and verification snapshot](https://github.com/mfahsold/lixity/blob/123b198db2b3d276b4bba71664e4e6b989377247/docs/STABILITY.md#2-stability-register).

| Surface | Remaining boundary | Maintained reference |
| :--- | :--- | :--- |
| Numerical reproducibility | Floating-point last bits can differ across interpreters/platforms. | [Methods](METHODS.md) |
| Large dashboards | Bundled assets and full offline text increase document size; opening paragraph details lazily does not remove the retained text payload. | [Architecture](ARCHITECTURE.md) |
| Workspace status | File-derived status is advisory; timestamps and restored files can be misleading. Unknown is not success. | [Workspace interfaces](AGENTS.md) |
| Optional project adapters | Core checks do not verify a project's launcher, export tools or local runtime. | [Installation](INSTALLATION.md) |
| Publication formats | Font coverage and layout limits remain; no EPUB, PDF/UA or PDF/X certification is claimed. | [PDF export](USAGE.md#download-a-manuscript-pdf) |
| Agreement drafts | Built-in PDF fonts do not cover every script; download text for external rendering and retain reviewed documents in project storage. | [Project interface](AGENTS.md) |

Empty optional signal fields, unavailable small-sample metrics and missing
rankings must be interpreted using their configuration/availability metadata.
They are not evidence of no signal or equal literary effect.
