# Stability & known limitations

Research basis, known limitations and every documented trade-off in one
place — kept in the present tense, no session logs.

Severity: 🔴 high (can mislead users) · 🟠 medium (can break silently) ·
🟡 low (cosmetic or documented trade-off).

## 1. Research findings (state of the art)

### Development-version guarantees and limits

The `1.15.0.dev0` suite checks English defaults, language resource-key coverage,
readability-coefficient dispatch and locale formatting. These are software
contracts, not empirical validation of linguistic accuracy across seven
languages. No language-wide accuracy percentage is established by this suite.

The 3D chapter view is exploratory: its dimensions are corpus-specific, signs
can be arbitrary, and per-axis thresholds are not simultaneous confidence
regions. Pointer interaction is tested; complete keyboard navigation within
the canvas is not yet available. Textual dimension information remains visible.

Engine tests use synthetic/public samples. Project adapters and optional local
servers have separate trust boundaries and need their own tests; core test
success is not a security certification for an arbitrary adapter.

**Robust statistics & multiplicity control.**
- MAD with the 1.4826 consistency constant ($1/\Phi^{-1}(3/4)$, R/DescTools
  default) scales the median absolute deviation to normal-consistent σ;
  0.6745 is the dual factor used in `robust_z`. Lixity never treats sample
  SD as the house-style spread when MAD is available.
- Significance-adjusted $z^* = (x-\tilde x)/\sqrt{\sigma_{\mathrm{MAD}}^2+\mathrm{SE}^2}$
  shrinks short chapters (Poisson/binomial plug-in SEs) so a 120-word chapter
  cannot outrank an 8,000-word chapter on a pure robust z.
- Benjamini–Hochberg at $q=0.05$ is the default multiplicity control over
  chapter × feature cells; Benjamini–Yekutieli ($c=\sum 1/i$) is available via
  `fdr_method="by"` / `--fdr-method by` when dependence among features is
  unknown. Storey’s $\pi_0$ is optional literature, not required for a
  400-cell matrix. Expected false positives at $|z^*|\ge 2.5$
  are reported (`expected_false_positives`) so no deviation is called
  “significant” in isolation.
- Surviving FDR cells carry **Cliff’s $\delta$** (Romano bands: negligible /
  small / medium / large) and the implied Vargha–Delaney $\hat{A}_{12}$ so
  magnitude is never confused with significance alone.
- Baseline **exchangeability diagnostics** (runs test about the series
  median, lag-1 autocorrelation vs $1/\sqrt{n}$, `low_power` for $n<8$)
  flag series where the i.i.d. FDR model is optimistic — the passport’s
  `baseline_diagnostics` block reports them.
- Thresholds (`z_mild=2.5`, `z_strong=3.5`, `fdr_q=0.05`, `fdr_method="bh"`,
  `dim_score_threshold=2.5`, `flag_min_severity=2`) are injectable
  (CLI / API / control-server settings / `[tool.lixity]` project config) and
  echoed in every passport `meta` block — see [`METHODS.md`](METHODS.md) §3.

**Lexical diversity.**
- McCarthy & Jarvis (2010, *Behavior Research Methods* 42:381–392) recommend
  using **MTLD + vocd-D/HD-D + Maas together** – not a single index; each
  captures unique lexical information. The corpus report follows exactly this
  combination.
- Bestgen (2024/2025, *The Twofold Length Problem*): **all** LD indices are
  sensitive to very short texts; reliable measurement requires minimum text
  lengths (their analyses use a 60-word floor). Kyle et al. (2024) confirm:
  Root TTR and D are not length-reliable; **optimized MATTR and MTLD** are.
- MATTR and MTLD correlate only weakly (≈0.07 in one corpus) – they measure
  different things (local repetition vs. global variation); the UI shows
  both, side by side.

**Readability & stylistics.**
- Amstad (1978) recalibrates Flesch for German; Kandel-Moles, Szigriszt-Pazos,
  Franchina-Vacca, Martins and Douma supply the fr/es/it/pt/nl constants.
  Weiss & Meurers (2022) show that raw readability *formulas* miss
  linguistic dimensions that matter for comprehension — Lixity therefore
  names the formula variant (`flesch_variant`) and treats the score as a
  relative, language-local signal, never a cross-language quality ranking.
- Foregrounding theory (Mukařovský / standard stylistics): deviation from
  a text’s *own* norm is the literary signal. The self-calibrating house
  style is that norm — a cultural-science reading of “what is remarkable
  *here*” rather than “what is correct” against an external standard.

**Stylometry.**
- Burrows’ Delta remains the standard baseline; 2026 work generalises it to
  **Jensen–Shannon Delta** and Rank-Turbulence Delta and stresses
  *interpretability*. The chapter divergence is a Jensen–Shannon distance
  with interpretable driver words – in line with this direction, but not an
  authorship-attribution instrument (documented).
- Stylometry is best used as a "complementary, explainable diagnostic"
  (2026), not as a verdict – the self-calibrating, author-centred design
  matches this guidance.

**Structural diagnostics.**
- PELT (Killick et al. 2012) is the standard exact changepoint method;
  the BIC penalty $2\ln n$ is the default for Gaussian cost and keeps the
  segment count conservative. Changepoints mark *where* the house style
  shifts, not *why* — they must be read together with the driver words.
- Mann–Kendall (Mann 1945, Kendall 1975) is the non-parametric monotonic
  trend test of choice for ordered environmental / stylistic series; the
  tie-corrected normal approximation is appropriate for $n \ge 10$ and
  remains a heuristic below that (documented).
- Sn and Qn (Rousseeuw & Croux 1993) have 50 % breakdown and higher
  Gaussian efficiency than MAD; Lixity reports them *next to* MAD so the
  reader can see whether a band is robust to a single outlier chapter
  (Sn/Qn stable, MAD not) or genuinely tight.
- Hill’s $\hat\alpha$ estimates the power-law tail exponent; values
  $\alpha \lesssim 2$ flag a heavy-tailed feature (occasional extreme
  chapters) that a median/MAD band will under-represent.
- Early/late **Wasserstein + two-sample KS** (`distribution_shift`) answer
  whether the first half of the book differs distributionally from the
  second half; KS $p$ is asymptotic (fine for $n \ge 10$, heuristic below).
- **Dunning $G^2$** is the standard keyness measure for sub-corpus
  contrasts; Lixity’s early/late split is a *documented heuristic* (chapter
  count midpoint), not a fitted breakpoint — read it with PELT
  `changepoints` when the halves look arbitrary.
- **Goh–Barabási** (Goh et al. 2001) fits discrete power laws to the
  content-word co-occurrence degree sequence; the KS distance and
  asymptotic $p$ report fit quality, not “scale-free-ness” as a verdict.
- **Co-occurrence degrees** (window = 2 by default) are a structural signal
  over *content* words only; function/stop words are excluded so the graph
  reflects topical co-occurrence, not syntax.

**Track B / C (research & pedagogy, not shipped).** Textometry / Burrows’
Delta (and 2026 JS/Rank-Turbulence generalisations), OHCO/TEI interchange,
a deeper hermeneutic layer on flagged cells, and worked tutorial walks are
catalogued as future directions in [`METHODS.md`](METHODS.md) Track B/C —
they are not current product features and must not be cited as such.

**Accessibility / data visualisation (WCAG 2.2).**
- Colour must never be the only channel (SC 1.4.1, 1.3.3): the heatmap
  prints the numeric z* values, the band chart encodes band/median/outliers
  by position and shape, every chip reveals tense + value as text on click.
- Non-text contrast ≥ 3:1 (SC 1.4.11), text ≥ 4.5:1 (SC 1.4.3): palette kept
  (blue/orange diverging = colour-blind-safe canonical pair, grey midpoint).
- Target size ≥ 24×24 px (SC 2.5.8): paragraph chips are deliberately dense
  (18 px) – documented exception with keyboard access and click-to-read.
- Diverging scales only with a meaningful midpoint (the chapter mean).


## 2. Stability register

| # | Component | Instability | Evidence | Mitigation |
| :-- | :--- | :--- | :--- | :--- |
| 1 | Dashboard JS | no automated JS test; DOM hooks (ids/classes) are an implicit contract | renaming a class breaks interactions silently | 🟠 → **fixed**: UI-contract test asserts every hook used by `dashboard.js` exists in the rendered HTML |
| 2 | Label packs | missing translations fall back to English silently | untranslated UI goes unnoticed | 🟠 → **fixed**: completeness test over the 7 languages for a required key set |
| 3 | LD indices on short texts | literature shows unreliability below ~60 words | Bestgen 2024; Kyle et al. 2024 | 🔴 → **fixed**: MTLD ≥ 100 tokens, Maas ≥ 100, MATTR ≥ window (50); otherwise `null` + help texts updated |
| 4 | Style fingerprint with few chapters | median/MAD unstable for n < 5; dimensions need spread | baseline sigma = 0 for single chapters | 🟠 → **fixed** (v1.3.0): panels hidden when no measurable spread; **documented** minimum chapters |
| 5 | Heuristic syllable counting | ±5–10 % error, language-specific rules | no gold-standard corpus in-repo | 🟡 **documented**; used only as a relative signal, formula names shown |
| 6 | Tense patterns | curated alternations + productive `-te`/`-ed` have FP/FN on ambiguous forms | stoplists documented; `read` fix in v1.3.0 | 🟡 **documented**; dominance is a heuristic, not ground truth |
| 7 | Packaging | a wheel could miss `ui/assets/*` or `py.typed` | config exists, never verified in CI | 🟠 → **fixed**: CI job builds a wheel and asserts assets + typing marker are inside |
| 8 | Book hook / venv | fallback `python3` without lixity breaks the hook | `pyproject` pin + `.venv` | 🟡 **documented** in book `docs/ARCHITECTURE.md`; hook prefers `.venv/bin/python` |
| 9 | PDF/EPUB exports | depend on system Cairo/Pango; not unit-tested | tests deliberately renderer-free | 🟡 mitigated by the pre-push hook running `export_all.py` (smoke) |
| 10 | Dashboard size | ~2 MB HTML for 95k words, linear growth | per-paragraph payload | 🟡 **documented**; future option: JSON payload + client render |
| 11 | Cross-machine determinism | float last bits may differ across platforms/Python versions | `math.log` summation order | 🟡 **documented**: byte-identical on the same interpreter; in-process determinism is tested |
| 12 | NDA store | `nda/` is gitignored; only the off-site backup covers it | data loss if backup fails | 🟡 **documented**; backup includes `nda/`; hook warns when backup is skipped |
| 13 | Chip target size | 18 px strips below WCAG 2.5.8 (24 px) | deliberate density | 🟡 **documented** exception (keyboard + click-to-read + hover growth) |
| 14 | UI labels architecture | label packs merged at runtime (base → metric → help → group → layer → ui) | fallback chain is implicit | 🟠 → **fixed**: merge order documented in `docs/AGENTS.md` §3.3 + completeness test |
| 15 | Status strip | states derive from file presence/mtime – a restored or clock-skewed file can read "stale" although it is current | no content hash in the status path | 🟡 **documented**: state is advisory; undeterminable components render `unknown`, not a fake `ok` |
| 16 | Marker notes | notes live in an HTML-comment attribute: quotes/newlines must be escaped; very long notes bloat the comment line | `note="…"` in the marker line | 🟠 → **fixed**: escaping on write (round-trip test); **documented** guidance: one short sentence |
| 17 | Drill-down filters | `data-flags` / `data-only` preselect a view filter; users may wonder why rows are hidden | UI state only, data untouched | 🟡 **documented**; the active filter is visible and one click clears it |
| 18 | orjson serialisation | `orjson` rejects non-string dict keys by default – chapter keys are ints in `deviations` | `OPT_NON_STR_KEYS` required | 🟠 → **fixed**: one `_json()` helper used everywhere; round-trip test covers integer chapter keys |
| 19 | Busy states | server actions have latency; without feedback users click twice | action buttons | 🟡 **mitigated**: buttons disable + spinner while running; server-side idempotence remains the actual guard |
| 20 | Layer colour semantics | colour encodes the absolute value span (min–max per dimension), not deviation sign alone | narrow bands would wash out | 🟡 **documented** in the legend (min/max values) + `USAGE.md`; the ring (|z| ≥ 1.5) is the second, deviation-specific channel |
| 21 | Sentence segmentation | abbreviation-aware splitter; unknown abbreviations, decimals and ellipses are still heuristic | naive splitting inflated ASL on `Mr.`/`z.B.` texts | 🟠 → **fixed**: shared `lixity.sentences` splitter (abbreviation/number/initial guards, closing marks stay with their sentence); **documented** as a heuristic |
| 22 | Corpus vs. chapter metrics | two divergent sentence splitters and duplicated sentence statistics | chapter matrix was still on the naive regex | 🟠 → **fixed**: one splitter and one `SentenceStats` implementation for both levels |
| 23 | Syllable heuristics | German double vowels and English silent-e/-le were mis-counted | `Kaffee`=3, `table`=3 | 🟡 → **fixed** for these fixtures: double vowels count as one nucleus, syllabic-l rule de-duplicated; language-wide accuracy remains unestablished |
| 24 | LIX long-word threshold | per-language calibration (7/8 characters) deviated from the standard | Björnsson defines >6 characters | 🟠 → **fixed**: standard >6 characters for every language; LIX values rise accordingly (documented, breaking metric change) |
| 25 | Readability formulas | constants must match the named literature formulas | hand-computed tests added | 🟢 **verified**: Amstad, Flesch, Kandel-Moles, INFLESZ (62.35), Franchina-Vacca (0.6 per 100 words = 60.0), Martins, Douma |
| 26 | UI interaction contract | some click targets were not keyboard reachable; one drill-down was lost | band rows lacked `role`/`tabindex` and the layer mapping | 🟠 → **fixed**: unified `[role="button"]` contract, one JS selector, focus ring for all; band rows jump to `#feat-<field>` (heatmap column) with optional layer + deviations-only |
| 27 | Dialogue turns | "turn" = quoted segment; no speaker attribution, quotation patterns are curated per language | no reliable offline speaker ID | 🟡 **documented**: turn structure, not who speaks; patterns per language profile |
| 28 | Character presence | whole-word matching on caller-supplied names/aliases; no NER, no coreference | nickname not in the list is invisible | 🟡 **documented**: alias patterns supported (`Matthias|Matze`); appendix/front matter excluded so chapter numbers match the metrics |
| 29 | Chapter hook score | 0–3 heuristic (short closing sentence, terminal ?/!/…, closing dialogue) | deliberate calm endings score 0 | 🟡 **documented**: ranks and locates chapter endings, no quality verdict |
| 30 | Showing/telling balance | heuristic composite of telling vs. showing signals; robust z against the book's own medians | MAD can be zero for share features | 🟡 **documented**: MAD→SD fallback; not a quality verdict; underlying signals visible in the heatmap |
| 31 | Repetition analysis | n-grams (default 3) with ≥ 3 occurrences; content words depend on the curated stop-word lists | deliberate repetition is a device | 🟡 **documented**: signal, not a verdict; pure function-word phrases excluded; stop lists de/en extended |
| 32 | Type safety & warnings | untyped helpers and warning noise could hide defects | strict typing was off; `\w` in a docstring raised a SyntaxWarning | 🟠 → **fixed**: `mypy --strict` clean (0 errors) and enforced in CI; `python -W error` test run is clean |
| 33 | Marker controls in jumpable rows | a click on “+ kind”/“Resolve” inside a `row-link` also fired the row jump (marker buttons carry `data-line`, which the INTERACTIVE selector matched) | double action: note field opened *and* the page scrolled | 🟠 → **fixed**: `isMarkerControl()` guard in click *and* keydown handlers; contract test asserts the guard |
| 34 | Flagged list length | severity ≥ 2 rows grow linearly with manuscript size (100+ rows in a novel) | a flat list would push the dashboard top down | 🟡 **documented**: capped scroll area (sticky header, ~26 rem); severity-descending sort keeps the worst cases visible |
| 35 | Structural changepoints | PELT on short series ($n < 8$) can over-segment; BIC penalty is conservative but not a stationarity proof | $n \ge 3$ required; penalty $2\ln n$ | 🟡 **documented**: `segmented_features` is a signal to inspect, not a proof of regime change; read with `trends` and JSD drivers |
| 36 | Mann–Kendall $p$ | normal approximation degrades for very short series; ties affect $\tau$ | $n \ge 3$ required | 🟡 **documented**: `trending_features` uses $p < 0.05$ as a heuristic cut; treat $n < 10$ as provisional |
| 37 | Hill tail index | $\hat\alpha$ biased for small $k$; undefined for non-positive values | $n \ge 5$, $k = \lfloor\sqrt n\rfloor$ | 🟡 **documented**: `tail_index` is diagnostic only; low $\alpha$ = occasional extreme chapters, not a quality problem |
| 38 | Sn / Qn vs. MAD | different consistency constants ($1.1926$, $2.2219$); $O(n^2)$ | both reported side by side in `robust_scales` | 🟡 **documented**: Sn/Qn are cross-checks, not replacements for the MAD band; disagreement flags outlier sensitivity |
| 39 | Goh–Barabási fit | discrete power-law fit on short degree sequences is unreliable | $n \ge 5$ positive degrees, non-constant | 🟡 **documented**: needs ≥ 50 content tokens for the co-occurrence graph; KS $p$ is asymptotic, not exact for tiny samples |
| 40 | Parallel split paths | `dialogue` and `analyzer` once had divergent `split_chapters` implementations | chapter numbering could drift | 🟠 → **fixed**: single source in `markdown_parser.split_chapters` (re-export from `dialogue`); regression test asserts shared titles + sequential numbering |
| 41 | Threshold resolution | three call sites built `FingerprintThresholds` independently (CLI / API / dashboard) | a new key could be wired on one path only | 🟠 → **fixed**: one builder `config.resolve_thresholds` (kwargs > project config > default); unit tests cover each precedence level |
| 42 | `flag_min_severity` wiring | profile / dashboard / CLI each resolved the flags cut differently | raising the floor could leave stale counts in one surface | 🟠 → **fixed**: end-to-end plumbing (CLI `_thresholds_and_profile` → `ProfileThresholds` → `render_dashboard(flag_min_severity=…)`); contract tests for profile + dashboard select |
| 43 | Structural early/late split | `distribution_shift` / `keyness` use a chapter-count midpoint, not a fitted breakpoint | PELT may place the break elsewhere | 🟡 **documented**: heuristic halves; cross-read with `changepoints` and `trends` |
| 44 | Token-level structural only on text surfaces | `from_metrics` alone has no tokens, so `cooccurrence` / `keyness` appear only when built from source text | a metrics-only passport looks “incomplete” | 🟡 **documented** in METHODS §4c: merge via `lexical_structural_diagnostics`; metric-derived keys always present |
| 45 | `signal_counts` empty by default | language profiles ship `"signal_keywords": {}`; without `CorpusConfig.signal_keywords` the field is always `{}` | empty looks like “no signal words found” rather than “not configured” | 🟡 **documented** in USAGE/AGENTS: field is opt-in via config; not a measurement failure |
| 46 | Filter-verb count ≠ editorial lists | engine `de` filter regex is a curated lemma list (perception/filter verbs); broader editorial lists differ (≈94 vs 120 for German) | dossier tables use a different definition | 🟡 **documented**: never swap numbers without restating the definition; within-language only |
| 47 | Pacing without explicit dividers | no `---`/`* * *` breaks → `explicit_scene_breaks=0`, `scenes_are_chapters=true` (scenes ≡ chapters) | scene counts look like real pacing | 🟠 → **fixed** (v1.12.0): report field + CLI warning; USAGE/AGENTS: scene structure uninformative when flag is set |
| 48 | `characters` empty names | empty `--names` used to return `figures: []` silently | caller mistake looks like “no characters” | 🟠 → **fixed** (v1.12.0): CLI exit 1 (`err_no_names`); API `ValueError` (no NER — names come from the caller) |
| 49 | No external Delta stylometry | JSD / driver words are in-corpus chapter-vs-rest diagnostics | misread as authorship attribution | 🟡 **documented**: METHODS Track B (not implemented); STABILITY §1 stylometry note |
| 50 | Dialogue speaker attribution | turns = quotation segments; no speaker ID | “turn” misread as speaker turn | 🟡 **documented**: USAGE `dialogue` section; STABILITY row 27 (patterns per language) |
