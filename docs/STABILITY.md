# Stability & known limitations

Use this page to judge what a result can support. Formula details live in
[METHODS.md](METHODS.md); the register below tracks current calculation and
interface limits. Statistical signals support a human review, not a prose grade.

Severity: 🔴 high (can mislead users) · 🟠 medium (can break silently) ·
🟡 low (cosmetic or documented trade-off).

## 1. Research findings (state of the art)

### Release verification and limits

The 2.1.0 regression comparison used the checked-in public-domain *Effi Briest*
(36 chapters) and *Pride and Prejudice* (61 chapters). Metrics, paragraph profiles
and style-passport values matched 2.0.0 under explicit default settings after
excluding the software-version label. This verifies preservation on these inputs,
not empirical calibration, literary quality or agreement with an external study.

The maintained suite checks English defaults, language resource-key coverage,
readability-coefficient dispatch and locale formatting. These are software
contracts, not empirical validation of linguistic accuracy across seven
languages. No language-wide accuracy percentage is established by this suite.

The 3D chapter view is exploratory: its dimensions are corpus-specific, signs
are fixed by convention, and per-axis thresholds are not simultaneous confidence
regions. **Since 2.0.0:** native rotation/zoom buttons and
a chapter-score table provide keyboard and touch access to the displayed scores,
flag status and chapter navigation. Individual canvas points remain pointer-operated.
These targeted checks do not establish full assistive-technology coverage.

Engine tests use synthetic/public samples. Project adapters and optional local
servers have separate trust boundaries and need their own tests; core test
success is not a security certification for an arbitrary adapter.

### Research and external-library limits

Zotero can lead the source/media catalogue; Lixity retains immutable evidence
and authored records. These stores have complementary responsibilities and
separate backup requirements. Lixity's integrity audit checks retained bytes,
references and citations, not factual truth, chronology or the completeness of
an external library. Test fixtures and a successful audit do not establish that
an entire private collection has been validated.

Research retention does not change the manuscript's style reference. Each
source analysis is `source_internal`, with user-supplied context explicitly
unverified. Historical travel accounts and monographs remain evidence selected
for review, not an automatic stylistic norm. Source–manuscript comparison is an
explicit, separate lexical/register report; shared words do not prove that a
passage supports a claim or that its historical context is appropriate.

Synthetic native Zotero 10.0.3 tests on Linux ARM64 cover text/PDF imports and
bridge text capture, refresh and search. This is a bounded integration check,
not a general platform certification or a test of a user's complete collection.
Automatic background/cloud synchronization and audio/video transcription are
not implemented. PDF extraction and a configured OCR worker do not establish
recognition accuracy; review text against scans when exact quotations matter.

Local PNG/JPEG dossier images retain exact original versions and share archive
backup/audit and withdrawal/purge handling. They are excluded from text analysis.
Container/header validation and a successful browser preview do not establish
complete codec validity or historical authenticity. Remote downloads, image OCR
and visual AI are not implemented. An unavailable or unprovable reference stays
unavailable rather than resolving to a newer or unrelated image.

RIS migration is additive. Preserve the original evidence archive and verify
attachment identities, bytes, retained citations and restoration before retiring
a prior workflow. Structured external references require `research-local/3` and
`research-manifest-local/3`; older applications reject these snapshots. Current
readers also accept v1/v2. Search across current authored records does not resolve
contradictory prose or promote a hypothesis to an accepted author decision.
See [Research usage](research/USAGE.md) for operational limits.

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
dropped on that set. Incomplete chapters have no dimension scores. This
corrects the previous mixed raw/rank scoring population, but complete-case
selection and small samples still limit interpretation. Score flags are
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

HD-D is exact expected TTR for a 42-token draw on 0–1. Before v1.16.0 the same
key held a sampled-window Gini–Simpson measure: regenerate older measurements
before comparison. Exact computation removes Monte Carlo error, not population
uncertainty. The 1.25 MTLD correction averages forward/reverse $N/F$
scores arithmetically. It preserves Lixity's inclusive threshold, trailing
factor and availability rules; different external variants still need explicit
parameter and segmentation alignment. Formula and guard details:
[METHODS §6](METHODS.md#6-lexical-diversity-indices).

### Linguistic proxies and literary interpretation

Analysis now shares the supported body/list/blockquote prose scope, stripping
quote delimiters and inline emphasis while omitting YAML front matter, code,
headings, comments and footnote definitions. Paragraph profiles intentionally
retain their narrower body/list scope and source line anchors. Configured word
regex flags are respected, English/German default tokens include accented
Unicode letters, LF/CRLF paragraph boundaries agree, and the short-paragraph
threshold is inclusive. Legacy whitespace counts are a separate unit. This
bounded Markdown policy and language-rule coverage do not establish complete
CommonMark support or linguistic token accuracy.

Passive, tense, adjective, nominalization and modality fields count lexical
markers or suffixes. For example, German `werden` also marks future tense or
becoming; English `been` also appears in active perfect constructions. These
counts do not identify syntactic voice or distinguish epistemic uncertainty
from obligation. Sentence segmentation and syllables are also heuristic.

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

### Structural diagnostics

The 1.25 corrections retain structural field names, but require
regenerating stored metrics/passports before numerical comparisons. Remaining
model limits are separate from the corrected calculations:

- `pelt_changepoints` now uses exact unpruned dynamic programming: $O(n^2)$
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
- WCAG 2.5.8 has a 24×24 CSS-pixel minimum with defined exceptions. On current
  main for 2.0.0, paragraph chips and dimension controls use at least 24×24,
  increasing to 44×44 for coarse pointers. Pressed chips retain their target
  size, and long strips scroll horizontally. These checks do not establish
  conformance for the entire interface or every canvas mark.
- Diverging scales have a meaningful midpoint: zero deviation from the
  within-manuscript reference (median in the robust style calculation).
- See [visual design rationale](ARCHITECTURE.md#visual-consistency-and-evidence)
  for evidence, typography choices and the limits of automated UI checks.


## 2. Stability register

| # | Component | Instability | Evidence | Mitigation |
| :-- | :--- | :--- | :--- | :--- |
| 1 | Dashboard JS | no automated JS test; DOM hooks (ids/classes) are an implicit contract | renaming a class breaks interactions silently | 🟠 → **fixed**: UI-contract test asserts every hook used by `dashboard.js` exists in the rendered HTML |
| 2 | Label packs | missing translations fall back to English silently | untranslated UI goes unnoticed | 🟠 → **fixed**: completeness test over the 7 languages for a required key set |
| 3 | LD indices on short texts | local guards do not establish reliability | length and parameter sensitivity depend on corpus and estimator | 🟡 **mitigated**: HD-D/MTLD/Maas ≥100 tokens; MATTR requires a full window; `null` is availability, not a validated reliability boundary |
| 4 | Style fingerprint with few chapters | minimum observations do not establish calibration; missingness can shrink the complete-case set | single chapters have no comparative baseline | 🟡 **mitigated**: dimensions require ≥3 complete chapters and ≥3 varying usable features in one rank space; incomplete scores are omitted; availability is not reliability |
| 5 | Heuristic syllable counting | language-specific rules; no validated aggregate error rate | no gold-standard corpus in-repo | 🟡 **documented**; used only as a relative signal, formula names shown |
| 6 | Tense patterns | curated alternations + productive `-te`/`-ed` have FP/FN on ambiguous forms | stoplists documented; `read` fix in v1.3.0 | 🟡 **documented**; dominance is a heuristic, not ground truth |
| 7 | Packaging | a wheel could miss `ui/assets/*` or `py.typed` | config exists, never verified in CI | 🟠 → **fixed**: CI job builds a wheel and asserts assets + typing marker are inside |
| 8 | Project Python environments | an external launcher may select an environment without Lixity | core tests do not verify a project's launcher or installation | 🟡 **documented**: verify the interpreter and package version in the project's environment; project hooks belong to that project |
| 9 | Publication PDF/EPUB adapters | optional project renderers have their own runtime dependencies | core analysis tests do not verify an adapter's publication output | 🟡 **documented**: run synthetic export checks in the adapter's environment; native NDA PDF tests cover only the built-in NDA renderer |
| 10 | Dashboard size | ~2 MB HTML for 95k words, linear growth | per-paragraph payload | 🟡 **documented**; future option: JSON payload + client render |
| 11 | Cross-machine determinism | float last bits may differ across platforms/Python versions | `math.log` summation order | 🟡 **documented**: byte-identical on the same interpreter; in-process determinism is tested |
| 12 | NDA draft rendering and downloads | the native PDF cannot represent every Unicode script; downloaded agreements need user retention | generation returns bytes without server files or a recipient registry | 🟡 **documented**: download UTF-8 text for broader local rendering; keep reviewed/signed documents in project-owned storage |
| 13 | Chip target size | targets must remain reachable in dense strips and pressed states | Chromium checks cover target geometry, keyboard/touch activation and horizontal scrolling | 🟡 **mitigated** since 2.0.0: 24×24 minimums, 44×44 for coarse pointers; targeted tests do not certify complete accessibility conformance |
| 14 | UI labels architecture | label packs merged at runtime (base → metric → help → group → layer → ui) | fallback chain is implicit | 🟠 → **fixed**: merge order documented in `docs/AGENTS.md` §3.3 + completeness test |
| 15 | Status strip | states derive from file presence/mtime – a restored or clock-skewed file can read "stale" although it is current | no content hash in the status path | 🟡 **documented**: state is advisory; undeterminable components render `unknown`, not a fake `ok` |
| 16 | Marker notes | notes live in an HTML-comment attribute: quotes/newlines must be escaped; very long notes bloat the comment line | `note="…"` in the marker line | 🟠 → **fixed**: escaping on write (round-trip test); **documented** guidance: one short sentence |
| 17 | Drill-down filters | `data-flags` / `data-only` preselect a view filter; users may wonder why rows are hidden | UI state only, data untouched | 🟡 **documented**; the active filter is visible and one click clears it |
| 18 | orjson serialisation | `orjson` rejects non-string dict keys by default – chapter keys are ints in `deviations` | `OPT_NON_STR_KEYS` required | 🟠 → **fixed**: one `_json()` helper used everywhere; round-trip test covers integer chapter keys |
| 19 | Busy states | server actions have latency; without feedback users click twice | action buttons | 🟡 **mitigated**: buttons disable + spinner while running; server-side idempotence remains the actual guard |
| 20 | Layer colour semantics | colour encodes the absolute value span (min–max per dimension), not deviation sign alone | narrow bands would wash out | 🟡 **documented** in the legend (min/max values) + `USAGE.md`; the ring (\|z\| ≥ 1.5) is the second, deviation-specific channel |
| 21 | Sentence segmentation | abbreviation-aware splitter; unknown abbreviations, decimals and ellipses are still heuristic | naive splitting inflated ASL on `Mr.`/`z.B.` texts | 🟠 → **fixed**: shared `lixity.sentences` splitter (abbreviation/number/initial guards, closing marks stay with their sentence); **documented** as a heuristic |
| 22 | Corpus vs. chapter metrics | two divergent sentence splitters and duplicated sentence statistics | chapter matrix was still on the naive regex | 🟠 → **fixed**: one splitter and one `SentenceStats` implementation for both levels |
| 23 | Syllable heuristics | German double vowels and English silent-e/-le were mis-counted | `Kaffee`=3, `table`=3 | 🟡 → **fixed** for these fixtures: double vowels count as one nucleus, syllabic-l rule de-duplicated; language-wide accuracy remains unestablished |
| 24 | LIX long-word threshold | per-language calibration (7/8 characters) deviated from the standard | Björnsson defines >6 characters | 🟠 → **fixed**: standard >6 characters for every language; LIX values rise accordingly (documented, breaking metric change) |
| 25 | Readability formulas | coefficient dispatch and empirical validation are different | hand-computed tests cover declared constants | 🟡 **documented**: formula dispatch is tested; original Amstad calibration and language-wide syllable accuracy remain unverified |
| 26 | UI interaction contract | some click targets were not keyboard reachable; one drill-down was lost | band rows lacked `role`/`tabindex` and the layer mapping | 🟠 → **fixed**: unified `[role="button"]` contract, one JS selector, focus ring for all; band rows jump to `#feat-<field>` (heatmap column) with optional layer + deviations-only |
| 27 | Dialogue turns | "turn" = quoted segment; no speaker attribution, quotation patterns are curated per language | no reliable offline speaker ID | 🟡 **documented**: turn structure, not who speaks; patterns per language profile |
| 28 | Character presence | whole-word matching on caller-supplied names/aliases; no NER, no coreference | nickname not in the list is invisible | 🟡 **documented**: alias patterns supported (`Matthias\|Matze`); appendix/front matter excluded so chapter numbers match the metrics |
| 29 | Chapter hook score | 0–3 heuristic (short closing sentence, terminal ?/!/…, closing dialogue) | deliberate calm endings score 0 | 🟡 **documented**: ranks and locates chapter endings, no quality verdict |
| 30 | Showing/telling balance | heuristic composite of telling vs. showing signals; robust z against the book's own medians | MAD can be zero for share features | 🟡 **documented**: MAD→SD fallback; not a quality verdict; underlying signals visible in the heatmap |
| 31 | Repetition analysis | n-grams (default 3) with ≥ 3 occurrences; content words depend on the curated stop-word lists | deliberate repetition is a device | 🟡 **documented**: signal, not a verdict; pure function-word phrases excluded; stop lists de/en extended |
| 32 | Type safety & warnings | untyped helpers and warning noise could hide defects | strict typing was off; `\w` in a docstring raised a SyntaxWarning | 🟠 → **fixed**: `mypy --strict` clean (0 errors) and enforced in CI; `python -W error` test run is clean |
| 33 | Marker controls in jumpable rows | a click on “+ kind”/“Resolve” inside a `row-link` also fired the row jump (marker buttons carry `data-line`, which the INTERACTIVE selector matched) | double action: note field opened *and* the page scrolled | 🟠 → **fixed**: `isMarkerControl()` guard in click *and* keydown handlers; contract test asserts the guard |
| 34 | Flagged list length | severity ≥ 2 rows grow linearly with manuscript size (100+ rows in a novel) | a flat list would push the dashboard top down | 🟡 **documented**: capped scroll area (sticky header, ~26 rem); severity-descending sort keeps the worst cases visible |
| 35 | Structural changepoints | guarded singleton/constant cost remains a modelling choice; short series can over-segment | former pruning could miss the declared minimum | 🟡 **documented**: 1.25 correction uses exact unpruned $O(n^2)$ time/$O(n)$ storage; cuts are review signals, not validated narrative boundaries |
| 36 | Mann–Kendall | tau-a is not tie-normalized tau-b; normal approximation needs assumptions | ties and serial dependence affect interpretation | 🟡 **documented**: tau-a naming is corrected; S and approximate p remain separate outputs; `trending_features` is model-dependent |
| 37 | Hill tail index | $\hat\alpha$ biased for small $k$; undefined for non-positive values | $n \ge 5$, $k = \lfloor\sqrt n\rfloor$ | 🟡 **documented**: `tail_index` is diagnostic only; low $\alpha$ = occasional extreme chapters, not a quality problem |
| 38 | Sn / Qn | asymptotic scaling does not remove finite-sample bias; pairwise work grows with chapter count | no finite-sample correction is applied | 🟡 **documented**: 1.25 correction uses original Sn low/high medians ×1.1926 and the same Qn rank ×2.21914; descriptive cross-checks alongside MAD |
| 39 | Degree-sequence fit | approximate discrete exponent is combined with a different continuous CDF and ordinary fitted KS p | estimator attribution and goodness-of-fit assumptions differ | 🟠 **open**: label as exploratory; no calibrated fit probability or scale-free claim |
| 40 | Parallel split paths | `dialogue` and `analyzer` once had divergent `split_chapters` implementations | chapter numbering could drift | 🟠 → **fixed**: single source in `markdown_parser.split_chapters` (re-export from `dialogue`); regression test asserts shared titles + sequential numbering |
| 41 | Threshold resolution | three call sites built `FingerprintThresholds` independently (CLI / API / dashboard) | a new key could be wired on one path only | 🟠 → **fixed**: one builder `config.resolve_thresholds` (kwargs > project config > default); unit tests cover each precedence level |
| 42 | `flag_min_severity` wiring | profile / dashboard / CLI each resolved the flags cut differently | raising the floor could leave stale counts in one surface | 🟠 → **fixed**: end-to-end plumbing (CLI `_thresholds_and_profile` → `ProfileThresholds` → `render_dashboard(flag_min_severity=…)`); contract tests for profile + dashboard select |
| 43 | Structural early/late split | `distribution_shift` / `keyness` use a chapter-count midpoint, not a fitted breakpoint | changepoint optimization may place a break elsewhere | 🟡 **documented**: heuristic halves; cross-read with `changepoints` and `trends` |
| 44 | Token-level structural only on text surfaces | `from_metrics` alone has no tokens, so `cooccurrence` / `keyness` appear only when built from source text | a metrics-only passport looks “incomplete” | 🟡 **documented** in METHODS §4c: merge via `lexical_structural_diagnostics`; metric-derived keys always present |
| 45 | `signal_counts` empty by default | language profiles ship `"signal_keywords": {}`; without `CorpusConfig.signal_keywords` the field is always `{}` | empty looks like “no signal words found” rather than “not configured” | 🟡 **documented** in USAGE/AGENTS: field is opt-in via config; not a measurement failure |
| 46 | Filter-verb count ≠ editorial lists | engine `de` filter regex is a curated lemma list (perception/filter verbs); broader editorial lists differ (≈94 vs 120 for German) | dossier tables use a different definition | 🟡 **documented**: never swap numbers without restating the definition; within-language only |
| 47 | Pacing without explicit dividers | no `---`/`* * *` breaks → `explicit_scene_breaks=0`, `scenes_are_chapters=true` (scenes ≡ chapters) | scene counts look like real pacing | 🟠 → **fixed** (v1.12.0): report field + CLI warning; USAGE/AGENTS: scene structure uninformative when flag is set |
| 48 | `characters` empty names | empty `--names` used to return `figures: []` silently | caller mistake looks like “no characters” | 🟠 → **fixed** (v1.12.0): CLI exit 1 (`err_no_names`); API `ValueError` (no NER — names come from the caller) |
| 49 | No external Delta stylometry | JSD / driver words are in-corpus chapter-vs-rest diagnostics | misread as authorship attribution | 🟡 **documented**: METHODS Track B (not implemented); STABILITY §1 stylometry note |
| 50 | Dialogue speaker attribution | turns = quotation segments; no speaker ID | “turn” misread as speaker turn | 🟡 **documented**: USAGE `dialogue` section; STABILITY row 27 (patterns per language) |
| 51 | Research retention & citations | Pilot retains original UTF-8/PDF bytes and pins exact unicode codepoint offsets; SQLite/FTS5 provides rebuildable lexical search; withdrawn sources mark citations `withdrawn`; purged sources fail closed | citations do not imply factual truth; retention requires explicit permission | 🟡 **documented**: USAGE/AGENTS; research pilot is opt-in, explicit-project only; no ambient manuscript I/O |
| 52 | PDF page-count detection | a page tree in a compressed object stream is not greppable, so a raw-scan fallback cannot measure the document | `get_pdf_page_count()` returned `1` when it could measure neither `pdfinfo` nor a raw scan, so a 3-page PDF measured as 1 | 🔴 → **fixed** (v1.22.0): the count is `int \| None`, and the native extractor refuses with an actionable error instead of retaining part of a document; undeterminable is never defaulted |
| 53 | Project configuration files | a malformed TOML file is indistinguishable from an absent one unless the loader says so | one unclosed quote reverted language and thresholds to defaults and still exited `0`; `analyze --json` reported `"language": "en"` against a configured `de` | 🔴 → **fixed** (v1.22.0): a present-but-unreadable or unparseable file emits a `UserWarning` naming the path and the consequence; absent stays silent, and the suite runs under `-W error` so a valid config must stay quiet |
| 54 | Project NDA text models | an invalid path or unknown field cannot produce the requested agreement | templates are explicit project-owned UTF-8 input with five literal fields | 🟡 **mitigated** since 2.0.0: outside paths, missing/empty templates and unknown fields are rejected; values remain data |
| 55 | Native server request layer | one 1655-line module with two dispatch ladders made the route/handler mapping hard to review | `do_GET`/`do_POST` were 73/125-line `if` chains; adding a route meant editing a shared ladder | 🟡 **mitigated** (v1.22.0): split into a package with per-area route tables and focused request-validation helpers; behaviour verified against a live instance across 21 routes and guard conditions |
