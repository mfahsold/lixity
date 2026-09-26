# Changelog

All notable changes to Lixity are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.16.0] – 2026-09-26

### Added

- Standalone local `lixity serve` with project creation, explicit manuscript import,
  existing-project opening, live settings and marker controls. Host/Origin checks,
  loopback binding and request limits protect the local HTTP boundary.
- A file and folder browser in Open Project selects existing server-local paths
  without changing the workspace until Open is confirmed. The persistent
  workspace bar keeps New Project, Open Project and Show guidance available in
  loaded projects; guidance can be reopened after dismissal.
- Localized explanations for project and research controls. Shared tooltips work
  by keyboard and touch, stay visible inside dialogs, and preserve related help.
- Experimental explicit-project research workspace: retained UTF-8 sources,
  versioned source context, SQLite/FTS5 search, exact passage citations, dossiers,
  claims, evidence links and author decisions through CLI, Python and HTTP APIs.
  Retention requires permission; source text is evidence, not an accepted claim.
- Integrated research tabs with full source/context and dossier views, passage
  selection for claims/dossiers, claim-to-dossier association, author decisions,
  visible archive root and counts, and distinct empty/uninitialized/unavailable states.
- Research withdrawal, purge preview and integrity audit. Purged passages leave
  content-free reference tombstones so historical evidence chains remain readable
  without retaining their deleted quotes.
- Cross-corpus lexical and stylistic comparison using the shared analysis pipeline.
  Vocabulary overlap is a navigation aid, not proof of factual support.
- All seven language profiles cover project workflows, research controls, templates
  and status labels. English and German remain the most developed linguistic cores.
- Additive `median_sl_exact` JSON metric; text reports display the conventional
  midpoint median for an even number of sentences. The legacy integer `median_sl`
  remains available with its original upper-middle semantics.
- Real-server browser regression for file/folder opening, import/error recovery,
  research creation and source lifecycle, with desktop and seven-locale mobile checks.

### Fixed

- Correct HD-D to hypergeometric expected TTR for a 42-token draw instead of
  the mislabeled windowed Simpson calculation. The minimum is now 100 tokens;
  legacy sampling arguments have no effect, and no population SE is reported.
  Recompute older analyses and dependent style baselines before comparison.
- “Open project” no longer routes file selection or drops silently into new-project
  import. Existing file/folder paths preserve their original research archive,
  including empty manuscripts and initialized research folders without manuscripts.
- Project opening reloads target settings; unsuccessful opening preserves the
  current workspace. Dialog errors remain visible beside editable inputs.
- Imported content preserves submitted whitespace and line endings and cannot
  overwrite an existing manuscript. Generated project settings use valid TOML
  and preserve quoted titles and the selected language.
- Standalone controls show only implemented actions; Run analyses/Rebuild refresh,
  while unsupported export/sync/audit/prune/Drive requests return HTTP 501
  without pretending to produce artifacts. Legacy `/api/load` returns HTTP 409
  rather than replacing a saved copy with the same filename.
- Source, claim and dossier selections survive background list refreshes. A decision
  with no recorded deviation is shown neutrally, without implying factual validation.
- Correct chapter-to-rest JSD probability mass; unequal chapter lengths no longer
  produce negative divergence for identical lexical distributions.
- Use all four cells of the term/non-term contingency table for Dunning G².
  Research comparison uses analyzed prose consistently and reports cross-language
  comparability limits; shared vocabulary does not establish factual support.
- Verify retained source bytes before exposing source-detail quotes, matching the
  integrity checks already used for citations.
- Align token/syllable/readability/dialogue counts with sentence metrics by excluding
  Markdown headings consistently from prose measurements.
- Project TOML works on Python 3.10 through a conditional `tomli` dependency;
  Python 3.11+ continues to use the standard library.
- Rebuilding the research catalogue flushes a writable file descriptor on
  Windows before atomic publication. Browser checks honor an external Python
  environment in CI as well as the local development environment.
- Correct the documented Benjamini–Yekutieli harmonic factor and Maas logarithm
  base to match the existing implementations; no numerical change for these fixes.

### Changed

- English is the default across CLI, API and local server; automatic language
  detection requires an explicit choice and import preserves that choice.
- English onboarding, installation, architecture and methods documentation now
  separates implemented research workflows from planned provider integrations.
- Analysis/style JSON schema versions remain 2/4. Corrected numeric outputs require
  recomputing older analyses before longitudinal comparison. Research stays an
  experimental family of `*-local/1` contracts.
- Refreshed public/synthetic screenshots and project presentation; no private
  manuscripts or real research records are included.

## [1.15.0] – 2026-09-24

### Added

- Explanatory settings form with visible labels, expandable thresholds,
  restore-without-saving and client/server validation in the local adapter.
- FDR-specific matrix markers and chapter filtering, fixed-scale legend,
  Cliff's δ details, and visible reference medians/sample counts.
- Classic serif typography for the project title only; system UI sans elsewhere.
- Shared `lixity.pipeline` orchestration for CLI, API and project adapters,
  with one corpus analysis per complete result and explicit threshold mappings.
- Interactive 3D chapter trajectories with zoom, rotation, localized tooltips,
  per-axis threshold boxes, chapter navigation and responsive feature loadings.
- Browser regression checks and localization contracts for all seven profiles.
- Architecture and localization guides with explicit engine/adapter boundaries.
- Shared project header with engine version and localized non-commercial-use notice.
- Thirteen refreshed public-sample screenshots, including full dimension panels,
  real expanded paragraph context, mobile views and dark-mode diagnostics.

### Changed

- Installation guidance now has one canonical guide for CLI/API/development,
  Windows, updates and first-run verification. `make install` uses `.venv`
  rather than global Python; both installation targets check dependencies.

- Promoted the reviewed `1.15.0.dev0` work to release `1.15.0`.
- CLI/API/core analysis defaults to English. Use `--language de` for German
  or `--language auto` for detection; CLI project language settings are honored.
- Documentation and comments use English; localized resources remain multilingual.
- Canvas animation runs only when rotation is enabled and the page is visible.

### Fixed

- NDA records render through text-safe DOM APIs instead of HTML interpolation;
  artifact links reject executable URL schemes. Added synthetic regressions.

- Public API `min_chapters` now reaches the style core rather than being
  silently ignored; the CLI exposes `--min-chapters`. API threshold mappings
  can explicitly disable current-directory configuration discovery.
- Repository guidance distinguishes analysis from authorized mutations;
  ignore rules cover local agent/browser state and the default HTML export.

- Shared panel and page spacing replaces overlapping margins; mobile charts use
  stacked labels and wide tables scroll instead of crushing their columns.
- Chapter matrix headers explain every column in all seven UI languages;
  shared tooltips now support keyboard focus, Escape and ARIA descriptions.

- Control groups share one spacing and separator rule; the duplicate legacy NDA
  entry form is removed in favor of the encrypted NDA manager.
- Settings display the analysis language unless the host explicitly selects auto.
- CLI configuration follows an explicitly selected manuscript's directory;
  dashboard and workspace builds honor the configured project title.

- Localized settings no longer write decimal commas into HTML number values.
- Matrix color legends reflect the actual color scale rather than the configured
  detection cutoff; reference rows respect the configured minimum sample size.
- Dimension scores are flagged only after all feature contributions are summed.
- Point hit testing matches the rendered projection after zoom/rotation.
- Chapter titles in canvas tooltips are text rather than executable HTML.
- English percentages retain their percent sign; tooltip numbers use their locale.
- Mobile dimension cards retain space for feature labels and avoid overflow.
- Long chapter paragraph strips scroll within their component on mobile.
- Screenshot selection uses exact panel IDs instead of incidental label matches.

## [1.14.0] – 2026-09-24

### Added

- **Substantive Documentation & Presentation Elevation:**
  - `README.md` and GitHub Pages (`docs/index.html`) thoroughly expanded, tightened, and refined in English, emphasizing self-calibrating macro-editing versus external normative style checkers.
  - Added an executive Mathematical Core summary table in `README.md` with clean, platform-independent Unicode notations (`x̃`, `Â₁₂`, `ρ₁`, `τ, S, p`, `G²`).
  - Added in-depth descriptions of the 5 core metric groups and their diagnostic value for macro-editing and developmental line editing.
  - Expanded FAQs in `README.md` and `docs/index.html` covering noise-aware significance shrinkage ($z^*$), non-destructive Markdown editor work markers (Pandoc / Typst / LaTeX pass-through), and pipeline integration.
  - Enhanced persona-workflow cards and comparison matrix on GitHub Pages.
- **English Schema & Model Descriptions:**
  - Translated all Pydantic model field descriptions in `src/lixity/models.py` (`CorpusConfig`, `SentenceDistribution`, `ChapterMetrics`, `CorpusMetrics`, `DossierStatus`, `CorpusAuditReport`) and internal error messages into English for clean API introspection.
- **UI Performance & Accessibility Enhancements:**
  - Throttled tooltip repositioning on scroll and resize via `requestAnimationFrame` tick scheduling to avoid layout thrashing and maintain 60/120 fps fluid scrolling.
  - Added Escape key dismissals to close open paragraph detail panels (`.ptext.open`) and active inline marker note input fields (`.marker-note`).
  - Extended CSS `scroll-margin-top: 4.5rem` to all panels and anchored sections (`.panel`, `section[id]`), preventing sticky toolbars from obscuring content headers upon link activation.
  - Added `user-select: none` to `.kpi-link` tiles to prevent accidental text selection during navigation clicks.
  - Standardized NDA table headers and fallback file upload status text to English in `dashboard.js`.

### Fixed

- **GitHub Markdown & KaTeX Math Rendering:**
  - Removed KaTeX delimiter-backtick collisions in `docs/METHODS.md` that previously caused red parse error boxes on GitHub.
  - Escaped mathematical asterisks (`z\*`) across documentation to eliminate accidental Markdown italics formatting.
  - Replaced unstable combining circumflex diacritics (`Hill &alpha;&#770;` / `Hill α̂`) that produced detached boxes across browser fonts with `Hill tail index`.
  - Normalized schema version indicators (`schema_version 4` for style references) across GitHub Pages and documentation.
- **Typographic, Editorial & Security Updates:**
  - Fixed duplicate word in `docs/USAGE.md` ("Structural structural diagnostics" → "Structural diagnostics").
  - Converted German decimal commas to standard English decimal points in the worked example in `docs/USAGE.md` (`15,57` → `15.57`, `+0,08 pp` → `+0.08 pp`, `−0,0002` → `−0.0002`).
  - Corrected English article and thousands formatting in `docs/STABILITY.md` ("a 8 000-word" → "an 8,000-word chapter", `chapter × feature`).
  - Added missing accent in `CITATION.cff` (`Goh-Barabási`).
  - Updated `SECURITY.md` supported release branch to `1.14.x`.
  - Completed all missing GitHub release comparison links at the bottom of `CHANGELOG.md` from v1.1.0 through v1.9.1.

## [1.13.0] – 2026-09-23

### Changed

- **Layout default leading ≈ 1.50×:** all three `BookLayoutConfig.from_preset`
  presets (`a4`, `taschenbuch`, `mobile`) now set `line_spacing=0.94`
  (Pango factor ≈ 18.0 / 13.2 / 12.8 pt baseline distance at 12 / 8.8 / 8.5 pt).
  Previously mobile and paperback used `0.88` (≈ 1.41×) and A4 used natural
  Pango metrics (≈ 1.33×); the tighter leading was reported as too cramped
  for continuous reading. Typographic defaults for reproducible exports —
  override per call via CLI `--line-spacing` or a custom config.

### Tests

- **`tests/test_layout.py`:** renderer-free assertions on preset
  `line_spacing`, body sizes, and the ≈ 1.50× target (no Cairo/Pango in pytest).

## [1.12.0] – 2026-09-23

### Added

- **Pacing degeneracy flag:** `PacingReport` / JSON gain
  `explicit_scene_breaks` and `scenes_are_chapters` (true when the text has
  no explicit `---`/`* * *` dividers, so scenes ≡ chapters). The CLI prints
  a warning in that case; scene counts are then structure placeholders, not
  pacing evidence.

### Changed

- **`characters` requires names:** empty `--names` / empty API name list
  now fail fast (CLI exit 1 `err_no_names`; `ValueError` via the API)
  instead of returning a silent `figures: []`. No NER — the caller
  supplies the names.

### Documentation

- **Boundary caveats** (USAGE §Known limitations, STABILITY register rows
  45–50, AGENTS §3.5 boundary note, METHODS Track B):
  heuristics measure the text, not ground truth; `signal_counts` is empty
  unless `CorpusConfig.signal_keywords` is set; German filter-verb counts
  (engine ≈ 94) intentionally differ from broader editorial lists (120);
  pacing without explicit dividers is flagged; no external Delta
  stylometry and no dialogue speaker attribution.

## [1.11.0] – 2026-09-23

### Added

- **Packaging & installability (SOTA):** dynamic version from
  `lixity._version.__version__` (single source for setuptools / `__version__` /
  `--version`), optional-dependencies `dev` extra (`pytest`, `mypy`, `ruff`,
  `build`), richer classifiers (`Environment :: Console`, Python 3.13,
  `Typing :: Typed`, OS Independent), project URLs for the GitHub Pages site
  and security policy.
- **`Makefile`** (`make help|install-dev|test|lint|typecheck|check|build|screenshots|clean`)
  and **`CONTRIBUTING.md`** (dev setup, PR checklist, bug reports).
- **`.github/dependabot.yml`** weekly updates for GitHub Actions.
- **Shell completion parity:** zsh script now covers all commands and the
  style-threshold flags (`--z-mild`…`--flag-min-severity`); bash completion
  gained `--fdr-method`, `--flag-min-severity`, `--dry-run`, `--names`,
  `--motif` and install-path hints; `lixity completion` accepts
  `bash|zsh|sh` as choices.
- **Top-level `--help` epilog** with examples, docs URL and `LIXITY_LANG`.
- **Structural diagnostics** on the style passport (`structural_diagnostics`,
  `schema_version: 4`): PELT changepoints, Mann–Kendall trends, Sn/Qn
  robust scales (alongside MAD), Hill tail index, and summary lists
  (`trending_features`, `segmented_features`); `passport_text` gains a
  “Structural diagnostics” line (en/de). Pure stdlib — no numpy/scipy.
- **Wired structural estimators** (previously standalone-only):
  - `distribution_shift` + `shifted_features`: Wasserstein-1D and
    two-sample KS comparing the first half of chapters against the second
    (both halves ≥ 2);
  - `lexical_structural_diagnostics(text, config)` merges token-level blocks
    into the passport on text-bearing surfaces (`api.fingerprint`,
    CLI `style` / `build` / `dashboard`): `cooccurrence` (content-word
    graph mean degree + Goh–Barabási fitness) and `keyness` (Dunning $G^2$
    early vs late halves). Guards: ≥ 50 content tokens for the graph,
    ≥ 20 per keyness half; single-chapter texts omit `keyness`.
- **`CITATION.cff`**, **`.pre-commit-config.yaml`** (ruff + trailing
  whitespace), **release workflow** (tag → wheel + GitHub Release), and
  **GitHub Pages deploy** (`docs/` on `main`).
- **Injectable statistical thresholds** (`z_mild`, `z_strong`, `fdr_q`,
  `fdr_method`, `dim_score_threshold`, `flag_min_severity`):
  stored on `StyleFingerprint.thresholds`, reported in every passport `meta`,
  and controllable from
  - CLI: `--z-mild`, `--z-strong`, `--fdr-q`, `--fdr-method {bh,by}`,
    `--dim-threshold`, `--flag-min-severity {1,2,3}` on `style`,
    `dashboard`, `build`;
  - API: `api.fingerprint(..., z_mild=…, fdr_q=…, fdr_method=…, …)`
    (same kwargs on `api.passport` / `api.dashboard`);
  - control UI: Settings fields for z\* mild/strong, FDR q, flags severity
    floor and dimension-score threshold, persisted on the embedded server;
  - config file: `[tool.lixity]` in `pyproject.toml`, or `lixity.toml` /
    `~/.config/lixity.toml` via `src/lixity/config.py`
    (CLI > UI session > project > user > code default).
- **Benjamini–Yekutieli FDR** (`fdr_method="by"`, harmonic factor \(c(m)\))
  alongside the default BH path (`fdr_rejects`).
- **Effect sizes on confirmed cells**: Cliff’s δ and Vargha–Delaney
  \(\hat{A}_{12}\) with Romano bands (`effect_label`), exposed as
  passport `effect_magnitudes`.
- **Baseline exchangeability diagnostics**: runs test about the series
  median, lag-1 autocorrelation vs \(1/\sqrt{n}\), `low_power` for
  \(n < 8\) — passport `baseline_diagnostics` + `passport_text` line.
- **`docs/METHODS.md`**: formal catalogue of every estimator (MAD/σ scaling,
  z\*, BH/BY-FDR, Cliff’s δ, runs/ACF, Jacobi dimensions, LD indices,
  readability constants, JSD, layer z, Structural PELT/MK/Sn/Qn/Hill and
  Wasserstein/KS/Dunning/Goh–Barabási — including their passport wiring —)
  with injectability table including the config file; Track B/C research
  and pedagogy backlog (Burrows’ Delta / OHCO-TEI / hermeneutics, tutorials).
- Contract tests for threshold round-trip and sensitivity settings markup
  (z mild/strong, FDR q, flags cut, dimension threshold).

### Changed

- **BREAKING (schema v3 → v4):** style-passport JSON container key renamed
  `wave2_diagnostics` → `structural_diagnostics`; passport text label
  `wave2` → `structural` (en: “Structural diagnostics”, de: “Strukturelle
  Diagnostik”); function `lexical_wave2_diagnostics` →
  `lexical_structural_diagnostics`. Sub-keys (`changepoints`, `trends`,
  `distribution_shift`, `cooccurrence`, `keyness`, …) are unchanged.
  Project-management codenames no longer appear in public contracts.
- **Centralised status codes** in new module `lixity.status`: `Status`
  (UI ok/warn/error/unknown), `Tense` (present/past/mixed/neutral),
  `Severity` (0–3 + `FLAG_MIN_SEVERITY`), `NdaStatus`, and
  `ContractKeys` / `STRUCTURAL_DIAGNOSTICS_KEY` / `SCHEMA_VERSION_*`.
  `style_profile.TENSE_*` / `FLAG_MIN_SEVERITY` now re-export from
  `status`; NDA status list is server-injected (`data-nda-statuses`)
  instead of hard-coded in `dashboard.js`.
- **Feature units localised for all seven UI languages** (en/de/fr/es/it/pt/nl)
  via `FEATURE_UNITS` (was: German override + English fallback only).
- **Install docs** (README, `docs/USAGE.md`, project page, `docs/llms.txt`):
  pipx / uv / pip / pinned-tag options; development via `make install-dev`.
- **`docs/USAGE.md` Development** section now documents `make check`
  (ruff + mypy --strict + pytest -W error) instead of the stale unittest count.
- **GH Pages** (`docs/index.html`): Structural FAQ and feature pills, style
  schema v4, BH/BY, injectable thresholds, structure-module cards, Methods /
  Contributing / Security footer links, installation matrix.
- **`.gitignore`** hardened: agent/tool workspaces (`.remember/`, `.claude/`,
  …), coverage formats, keystores / `.netrc` / swap files, stray
  `*_dashboard.html` / `*_metrics.json` style build artifacts outside
  `exports/`.
- **`SECURITY.md`**: supported-versions table, expanded threat model,
  consumer hardening checklist (pipx/uv, pinned tags, local-only dashboards).
- **Single chapter segmentation**: `split_chapters` moved from `dialogue`
  to `markdown_parser` (re-export kept); `analyzer` and all structure
  modules share one implementation, so chapter titles/numbers can no longer
  drift between reports.
- **Single threshold builder**: `config.resolve_thresholds` is the only
  place that builds `FingerprintThresholds` (kwargs > project config >
  code default); CLI `_thresholds_from_args` and API `_thresholds` both
  call it.
- **`flag_min_severity` end-to-end**: CLI `_thresholds_and_profile` feeds
  `ProfileThresholds` into `ParagraphProfiler` and passes the resolved cut
  to `render_dashboard`; `api.profile` / `api.dashboard` accept
  `flag_min_severity` explicitly.
- Passport `meta` now reports `min_chapters` and `flag_min_severity`
  alongside the z\*/FDR thresholds.
- **Style reference rows are fully clickable**: every `.band-row` jumps to
  that feature's heatmap column (`#feat-<field>`), activates the matching
  style layer when one exists, and preselects “deviations only” when the
  feature has outliers. The red **outlier count** is a nested control that
  opens the strongest outlier chapter (with layer + only-deviations).
- Heatmap column headers expose stable anchors (`id="feat-<field>"`).
- Heatmap legend and “deviations only” cut use `fingerprint.thresholds.z_mild`
  instead of a hardcoded 2.5.
- Research basis (STABILITY §1) extended: robust statistics / multiplicity
  control, readability literature (Amstad…Douma, Weiss & Meurers 2022),
  foregrounding/stylistics angle.
- README condensed with an explicit mathematical-core focus; links to
  METHODS.md.

### Fixed

- Dialogue and nominal style layers now bind correctly:
  `LAYER_FEATURES` uses fingerprint field names (`dialog_pct`,
  `nominalization_density`); `LAYER_PARAGRAPH_ATTR` maps them to the
  `ParagraphProfile` attributes (`dialogue_pct`, `nominal_density`) used by
  `layer_stats`. Previously the dialogue band had no layer and the nominal
  layer produced empty stats.
- Export-format `<select id="fmt">` exposes a short `aria-label` (export)
  instead of the full help sentence; the tooltip moved to `title`.
- USAGE metric table: LIX long-word threshold is **>6 characters in every
  language** (Björnsson), not per-language 6/7/8 (docs inconsistency with
  STABILITY #24 / METHODS §7).
- Book scripts `export_pdf.py` / `export_nda.py`: suppress third-party
  `PyGIDeprecationWarning` for `GLib.unix_signal_add_full` during Pango
  import (system PyGObject, not Lixity code).

## [1.10.0] – 2026-09-22

### Added

- **Flagged passages panel** (`#flags`) directly under the KPIs: every
  paragraph with severity ≥ 2 as a row (severity badge, chapter, line anchor,
  excerpt), sorted by severity then line. Clicking a row jumps straight to
  that paragraph — opens it, scrolls, flashes — with the “flagged only”
  filter preselected; a quick **+ To-do** button writes the work marker
  inline without leaving the list. The “flagged” KPI now targets this panel.
- `ParagraphProfile.is_flagged`, the `FLAG_MIN_SEVERITY` constant and
  `flagged_paragraphs()` (severity desc, line asc) replace the repeated
  `severity >= 2` checks; `classify_severity()` is a documented, tested
  pure function (0–3 truth table).

### Fixed

- **Marker clicks no longer scroll the page**: buttons inside jumpable rows
  (`data-marker-kind`, `data-marker-resolve`, note field) are excluded from
  jump activation in both the click and the keyboard handler.
- **Line jumps land on the paragraph, not just the chapter**: `jumpToLine`
  opens the target `.ptext` panel (via `data-target` or its
  `data-start`/`data-end` span) and activates its chip; chapter scroll remains
  the fallback (e.g. marker lines outside any paragraph span).

### Removed

- Dead aliases: `render_style_report`, `DEFAULT_TEXTE`, and the unused
  `ParagraphProfile.line_label` property (the localised `line_label()` in
  `ui.components` remains the single implementation).

## [1.9.1] – 2026-09-22

### Changed

- **Chapter names wherever they are available**: dialogue, pacing and
  showing rows show `Kap. N · Titel`, the deviation KPI names its chapter,
  the marker table gained a chapter column, and the character span shows the
  first chapter's title on hover.

### Fixed

- **Layout overflow hardened**: the chapter matrix and marker table scroll
  horizontally inside their panels (like the heatmap); long texts wrap or
  ellipsize (KPI labels, dimension loading chips, status details, chapter
  titles, repeated phrases, paragraph text); the pacing and showing lists are
  height-capped with a fade hint; the toolbar select is width-capped.

## [1.9.0] – 2026-09-22

### Added

- **`lixity dialogue`** (and `api.dialogue`): dialogue turn structure — turns
  (quoted segments), mean/median/longest turn, turns per 1,000 words and the
  dialogue paragraph share, per chapter and corpus. Heuristic via the language
  profile's dialogue pattern; no speaker attribution.
- **`lixity characters`** (and `api.characters`): character presence across
  chapters for curated names or alias patterns — mentions, chapters present,
  first/last chapter, longest gap, presence ratio. Appendix and front matter
  are excluded so chapter numbers match the metrics.
- **`lixity pacing`** (and `api.pacing`): scene structure via explicit
  dividers, tempo signals per scene/chapter (ASL, staccato, dialogue) and a
  documented 0–3 chapter hook score.
- **`lixity motifs`** (and `api.motifs`): motif presence (mentions, density,
  chapter span, longest gap) and generic repetition signals — most frequent
  content words and repeated n-grams with their chapter spread.
- Dashboard panels for dialogue structure, character presence, the pacing
  curve and motifs/repetition (clickable, keyboard reachable, seven
  languages).
- **`lixity showing`** (and `api.showing`): self-calibrating showing vs.
  telling balance per chapter (robust z of telling and showing signals
  against the book's own medians; documented MAD→SD fallback).
- **`lixity about --json`** now lists all commands with purpose, output type
  and schema version (agent discovery).
- Curated stop-word lists (de/en) extended with high-frequency adverbs,
  possessives and particles so repetition and driver-word analysis stays
  content-focused.
- **`mypy --strict` is enabled** (147 → 0 errors) and runs in CI; the code
  base is also free of runtime and syntax warnings (`python -W error`).

## [1.8.0] – 2026-09-22

### Changed (breaking, metric-affecting)

- **Sentence segmentation is abbreviation-aware** and shared by corpus and
  chapter metrics (`lixity.sentences`): abbreviations (`Mr.`, `z.B.`, `Dr.`),
  decimal numbers and initials no longer split sentences, closing quotation
  marks stay with the sentence they close. Sentence counts, ASL, CV, Flesch
  and LIX change accordingly (dialogue-heavy texts get more, shorter
  sentences; the chapter matrix was still on the naive regex before).
- **LIX uses the standard long-word threshold** (more than six characters)
  for every language; the previous per-language calibration (7/8 characters)
  deviated from Björnsson. LIX values rise accordingly.
- **Syllable heuristics improved:** German double vowels count as one nucleus
  (`Kaffee`, `Idee`), the English silent-e/-le rule no longer double-counts
  (`table`, `people`).
- **Spanish readability** uses the INFLESZ coefficient 62.35 (matches the
  named scale).

### Changed (structure)

- New core modules: `lixity/sentences.py` (segmentation), `lixity/syllables.py`
  (per-language rule tables as data), `lixity/diversity.py` (HD-D, MTLD,
  MATTR, Maas a², Yule's K). `analyzer.py` is orchestration and metric
  assembly (857 → ~540 lines).
- `SentenceStats` is the one sentence-architecture data structure for corpus
  and chapters; `share_se`/`count_se` are module-level plug-in estimators.
- `language.py`: one profile dataclass, resolved via `dataclasses.replace`
  (was two identical dataclasses with three field lists).
- **Unified UI interaction contract**: every content drill-down is a
  keyboard-reachable `[role="button"]`, driven by one JS selector; focus
  styling covers all targets (documented in `docs/AGENTS.md` §3.4).

### Fixed

- Style-reference band rows are clickable again (the layer mapping was lost
  in a refactor) – as documented since v1.5.0.
- `jacobi_eigh` docstring corrected (one eigenvector per list entry).
- New `tests/test_math_core.py` pins the mathematical core (hand-computed
  readability formulas, published Benjamini-Hochberg example, Jacobi
  properties, Spearman, z*/MAD helpers, lexical-diversity properties).

## [1.7.0] – 2026-09-22

### Changed (breaking)

- **Language-neutral tense values:** `dominance` (chapter metrics) and
  `dominant` (paragraph profiles) are now `present` / `past` / `mixed` /
  `neutral`; display labels come from the language packs. The JSON contract
  version is now **schema_version 2** for `analyze` and `profile`.
- **English is the engine default** for reports and CLI messages; German is
  available via `LIXITY_LANG=de` (Rich report, Markdown report, style
  reference text, build/dashboard messages). Other report languages fall
  back to English.
- **Project corridors are opt-in:** reference corridors and literary
  assessments are no longer engine defaults – projects supply them as
  `texts` (the book project passes its own German corridors). Without them
  the Rich report stays factual (metric + value).
- Report row labels and feature units are localised (`de` / `en` packs).

### Fixed

- Chapter detection: front matter preceded by editorial HTML comments no
  longer becomes chapter 1 (chapter numbering stays correct).
- A chapter without tense markers is classified `neutral` instead of `past`
  (one shared `dominance_from_hits` helper for chapters and paragraphs).
- Style reference: correct singular/plural chapter count; localised units.

### Added

- `LIXITY_LANG` environment variable (`en` default, `de` supported) for
  user-facing CLI messages.

## [1.6.1] – 2026-09-22

### Fixed

- **Markdown report:** punctuation rows now use their own texts. Previously
  the `colons` matcher also matched inside `semicolons`, so the semicolon row
  displayed the colon text.

### Changed

- `CorpusAuditReport` carries a generic `tracked_chapters` mapping instead of
  the book-specific `kap23_words` / `kap24_words` / `kap25_words` fields —
  project data belongs to the adapter, not the engine.
- Documentation tightened: leaner README (features and quick start instead of
  marketing comparisons and duplicated CLI reference), single stability
  register `docs/STABILITY.md` (replaces `docs/ITERATION-2.md` and
  `docs/ITERATION-3.md`), compact security policy, condensed "Known
  limitations" with a pointer to the register.

### Removed

- `lixity.visualizer` compatibility shim — import the renderer from
  `lixity.ui` (`from lixity.ui import render_dashboard`).
- Committed sample dashboard artifact (`samples/effi-briest-dashboard.html`,
  2.4 MB); it is reproducible from the sample manuscript.

## [1.6.0] – 2026-09-22

### Added

- **Component status strip**: one dot per component (manuscript, analysis,
  dossiers, exports, NDA, markers) with a one-word state, supplied by the
  embedding tool; undeterminable components render `unknown` instead of a
  fake `ok`.
- **Work-marker notes**: clicking a marker kind opens an inline note field —
  `Enter` saves the marker with `note="…"`, `Esc` cancels. Labels in all
  seven languages.
- **Drill-down filters**: KPI tiles, band rows, dimension loadings, matrix
  rows and heatmap cells now navigate *and* preselect the matching view
  ("flagged only" / "deviations only" plus the style layer).
- **Busy states**: action buttons disable and spin while a server action
  runs, so latency is visible and double-clicks are avoided.
- `docs/llms.txt`, `docs/robots.txt`, `docs/sitemap.xml` and
  `docs/STABILITY.md` (single stability register).
- `samples/README.md` documenting sample provenance and licensing
  (Project Gutenberg #5323, public domain).

### Changed

- **Style-layer colour semantics**: colour encodes the *absolute value span*
  (min–max per dimension) so narrow bands stay readable; the legend prints
  the concrete min/max values, and the ring (|z| ≥ 1.5) remains the
  deviation-specific channel.
- **One JSON serializer**: the whole CLI and all artifact writers serialise
  through a single `orjson` helper (`OPT_NON_STR_KEYS`, deterministic
  output) instead of mixed `json` calls.
- Dependencies updated and validated in both project environments
  (pydantic 2.13.5, rich 15.0.0, orjson 3.12.0); the declared floors are
  unchanged, so existing installations keep working.
- README, `docs/USAGE.md`, `docs/AGENTS.md` (§3.4 dashboard DOM hooks) and
  the project page now cover the new UI, licensing/attribution and
  agent-readable surfaces.

### Fixed

- Zero-value heatmap cells use the neutral surface colour (previously they
  punched dark holes into the light theme and vice versa).
- Marker notes are escaped on write, so quotes and line breaks cannot break
  the marker comment.

### Removed

- Legacy payload helpers (`layer_colors`) and the short layer labels
  (`layer_below_short` / `layer_above_short`); `layer_stats` is the single
  source for layer values and deviations.

## [1.5.0] – 2026-09-22

### Added

- **Everything relevant is clickable**: KPI tiles jump to their panel (or
  activate the matching style layer), style-reference band rows and dimension
  loading bars open the layer, chapter-matrix rows jump to the chapter and
  work-marker rows jump to the containing chapter — mouse and keyboard.
- **Style-layer v2**: deviations (|z| ≥ 1.5) are ring-marked and counted in
  the legend, "only deviations" dims the rest, and "next deviation" walks
  through the marked passages one by one (opens the paragraph and scrolls).
- **Plain-language tooltips** in all seven languages: short, concrete, with a
  reading direction ("higher = …") instead of formulas; the heatmap formula
  moved to the docs.
- `docs/STABILITY.md` stays the reference for the stability register.

### Changed

- **"Style passport" is now "Style reference"** (de: *Stilreferenz*,
  fr: *Référence de style*, es/it/pt/nl analogous) – clearer name for the
  self-calibrated style norm. The API (`fingerprint`/`passport`) and the
  JSON schema are unchanged.
- Style layer is framed as **"Deviations"** (the select lists the dimensions),
  with short scale words ("below · above") and guidance on demand.
- KPI labels balance their line breaks; chapter-matrix micro-bars render as a
  thin underline instead of a block behind the number.

### Fixed

- Style-layer payload carries the robust z value (used for marking, counting
  and navigation); the legend count uses correct singular/plural.

## [1.4.0] – 2026-09-22

### Added

- **Centralised UI package `lixity.ui`** – renderer (`dashboard.py`),
  reusable components (`components.py`) and assets (CSS/JS) in one place;
  `lixity.visualizer` remains as a compatibility shim.
- **"Show, don't tell" dashboard**: style-passport **band chart** (range,
  median tick, outlier dots; numbers on demand in the tooltip), dimension
  **loading bars**, KPI **proportion bars**, chapter-matrix micro-bars and a
  self-dismissing hint instead of permanent instructions.
- **UI contract tests** (`tests/test_ui_contract.py`): every DOM id the
  script uses exists in the render, every help key and core label key is
  translated in all seven languages, and the visual components are rendered.
- **CI packaging job** verifying that the wheel contains the UI assets and
  the `py.typed` marker.
- `docs/STABILITY.md` – research findings, critical assessment and the
  stability register (with severity, evidence, mitigation); "Known
  limitations" section in `docs/USAGE.md`.

### Changed

- **Micro-interactions**: hover/press feedback on chips and buttons, animated
  paragraph expand (grid-rows), heatmap row/column highlight, translucent
  sticky toolbar, tooltip fade; `prefers-reduced-motion` disables animation.
- **Lexical-diversity guards** per Bestgen (2024/2025): MTLD and Maas a²
  require ≥ 100 tokens, otherwise `null` (all LD indices are unreliable on
  very short texts).
- Label-pack merge order documented (`docs/AGENTS.md` §3.3).

### Fixed

- Chapter-matrix micro-bars are rendered (replaces the unused placeholder);
  dead CSS rules removed.

## [1.3.1] – 2026-09-22

### Added

- Dashboard control panel shows a **manuscript-format hint**
  (`Markdown (.md), UTF-8 · chapters as “## Title”`), localized in all seven
  languages.

### Changed

- `docs/USAGE.md`: clearer manuscript-format section plus a step-by-step
  operating flow for the dashboard (KPIs → heatmap → style layer → paragraph).

## [1.3.0] – 2026-09-22

### Added

- **Idempotent workspace build** (`lixity build [FILE] [--dry-run]`): discovers
  the manuscript in a folder (`<folder>.md`, `manuscript.md`/`manuskript.md`,
  or the only `.md` file), creates `exports/` (with `exports/archive/`) and
  `nda/`, and publishes `_metrics.json`, `_profile.json`, `_style.json`,
  `_style_passport.txt`, `_report.md` and `_dashboard.html`. Identical input
  causes **zero writes**; changed input creates one timestamped version,
  updates the stable name and rotates older versions into the archive
  (last 10 kept per family). New module `lixity.workspace`.
- **Language-calibrated readability**: Flesch-type formulas per profile
  (Amstad, Flesch, Kandel-Moles, Szigriszt-Pazos, Franchina-Vacca, Martins,
  Douma), per-language syllable heuristics and a `flesch_variant` field.
- **Length-invariant lexical diversity**: MTLD (McCarthy & Jarvis 2010),
  MATTR (Covington & McFall 2010) and Maas a² – in JSON, reports and dashboard.
- Productive tense patterns for German (weak preterite, Perfekt) and English
  (regular `-ed`), complementing the curated verb forms.
- **Locale-aware number rendering** (`lixity.format`): one source of truth for
  CLI reports, style passport and dashboard – comma decimals and spaced
  percentages for de/es/it/pt/nl, narrow-space grouping for French.
- Reproducible screenshots: `scripts/make_screenshots.py` renders CLI reports
  and dashboard sections with headless Chromium.
- Worked example in README/USAGE: Fontane's *Effi Briest* as reference corpus
  and a sequel draft measured against its style corridor (`samples/`).

### Changed

- **Style layer overlay, reworked**: selecting a layer now colours the whole
  paragraph strip (blue = below, orange = above the chapter mean; tense stays
  on the top edge), with a legend, per-layer guidance ("what to look for"),
  exact values in the tooltip, and the active colour on the expanded
  paragraph. Heatmap cells are clickable and jump to the chapter while
  activating the matching layer; zero cells render calm.
- LIX long-word thresholds are calibrated per language (> 6/7/8 letters).
- Dashboard KPI grid grouped into **Scope · Rhythm · Language · Vocabulary ·
  Style**; locale-aware numbers; keyboard focus outlines and
  Escape-to-close tooltips.
- **Performance**: JSD chapter divergence iterates only the chapter's own
  vocabulary (closed form for absent types, ~4× faster), MATTR runs in O(N)
  with an incremental type counter, syllable/comment regexes are precompiled
  and a duplicated sentence scan was removed – analysis of the 95k-word
  reference corpus drops from ~3.0 s to ~1.7 s.
- **Architecture**: dashboard CSS/JS moved to `lixity/assets/` (editable,
  lintable, shipped as package data); locale-aware number rendering
  centralised in `lixity.format`; language data typed (`TypedDict`,
  annotated registries); `py.typed` marker added; `mypy` configured and
  enforced in CI.
- `punctuation` uses language-neutral keys (`periods`, `commas`, …); display
  names are localized.
- Chapter dominance uses canonical values (Präsens/Präteritum/Gemischt).

### Fixed

- All pre-existing type errors resolved (`mypy` clean across 18 modules and
  the test suite).
- Jensen-Shannon chapter divergence is now bit-identical across processes
  (deterministic iteration) – reproducible artifacts.
- Dutch passive regex no longer matches plain copula sentences.
- French first-person starters handle elision (`J'aime`).
- English `read` is no longer counted in both present and past.

### Security

- `SECURITY.md` documents the threat model (offline, no shell, escaped
  output, no secrets on disk).
- `.gitignore` hardened for secrets and private stores (`*.enc`, `*.key`,
  `*.pem`, `.env*`, `secrets/`).
- Artifact writes are `fsync`ed before the atomic rename (durability).

## [1.2.0] – 2026-09-22

### Added

- **Measurement uncertainty**: every style feature carries a documented
  standard error (`ChapterMetrics.style_se`: Poisson for count densities,
  binomial for shares, plug-ins for ASL/CV/starter entropy via Miller-Madow,
  HD-D sample dispersion). Deviations are now **significance-adjusted**:
  `z* = (x − median) / √(σ² + SE²)` – noisy small chapters cannot produce
  false alarms.
- **Multiple-testing control**: the passport reports the statistically
  expected false positives at |z*| ≥ 2.5 and the **Benjamini-Hochberg FDR
  set** (q = 0.05) across all chapter×feature cells.
- **Self-calibrated style dimensions**: Spearman correlation matrix of the
  features, eigendecomposed via cyclic Jacobi rotations (pure stdlib) –
  the manuscript's own abstract style axes with loadings, variance share,
  per-chapter scores and flagged chapters (Biber-style, but no pre-defined
  registers). Redundant feature pairs (|ρ| ≥ 0.8) are reported.
- **Work markers** (`markers.py`): editor-visible, renderer-invisible
  `<!-- LIXITY-MARKER id="…" kind="…" note="…" -->` lines with deterministic
  content-hash IDs; add/list/resolve/update, idempotent, sanitised notes;
  set/resolve from the dashboard (local control server) or the Python API.
- **Agent interface**: stable `lixity.api` facade (`analyze`, `profile`,
  `fingerprint`/`passport`, `dashboard`, `markers`, `add_marker`,
  `resolve_marker`, `about`) with self-describing meta blocks, plus CLI
  `about`, `completion bash|zsh`, `--version` and defined exit codes.
- `docs/AGENTS.md`: machine-facing contracts (commands, JSON schemas,
  interpretation heuristics, Python API).
- New tests: significance adjustment, Benjamini-Hochberg, Jacobi
  eigendecomposition, Spearman, markers lifecycle, API facade, CLI surface.

### Changed

- `style --json` passport is now schema version 2 (meta block with
  expected false positives and FDR q; `dimensions`, `fdr_flagged`,
  `redundant_features`, feature units).
- Dashboard: style-dimensions panel, significance-adjusted heatmap cells
  with effect-size tooltips, false-positive/FDR footnote, work-marker panel
  and per-paragraph marker buttons (control mode).
- Language profiles: project-neutral signal keywords (empty defaults –
  leitmotifs belong to `CorpusConfig.signal_keywords` / `motif_regexes`).
- Release kit: `api.py`, `markers.py`, current CLI/CI/pyproject templates,
  richer `.gitignore`, SEO-optimised README and GitHub Pages
  (meta description, Open Graph, Twitter cards, JSON-LD).

## [1.1.0] – 2026-09-22

### Added

- **Self-calibrating style fingerprint** (`style_fingerprint.py`): register-neutral
  consistency analysis. For 16 descriptive features (ASL, staccato, hypotaxis,
  sentence CV, dialogue, function words, perception filters, modals, passive,
  nominalisations, adjectives, long words, starter entropy, first-person starts,
  Guiraud R, HD-D) the engine derives the manuscript's own house style
  (robust median/MAD) and flags chapters only by deviation from it (robust z).
- **Jensen-Shannon chapter divergence** with additive, interpretable driver
  words (leave-one-out, content-word filtered) per chapter.
- **HD-D** (McCarthy & Jarvis 2010) and per-chapter **Guiraud R** as
  length-robust lexical diversity measures (TTR stays for continuity).
- **`lixity style manuscript.md`**: style passport as text or JSON
  (`--json`) – self-calibrated feature bands usable as constraints for
  authoring/editing (human or assisting LLM).
- **Dashboard**: chapter × feature heatmap with diverging z-colour scale,
  style-passport panel (median, ±2σ band, outliers), consistency KPI,
  top-deviant KPI, drift column in the chapter matrix, and a style-layer
  overlay for the chapter strips (ASL/function/dialogue/filter/modal/
  nominal/passive, within-chapter normalised).
- Per-paragraph style densities (perception filters, modals, nominalisations,
  passive) in the paragraph detail line and chip tooltips.
- Style-pattern data per language (`STYLE_DATA`: first-person starters,
  passive markers, nominal/adjective suffixes) – empty for `generic`, so all
  metrics degrade gracefully without the profile.
- New tests (`tests/test_style_fingerprint.py`): robust statistics, HD-D
  determinism, JSD driver words, passport structure, heatmap/layer rendering.

### Changed

- `ChapterMetrics`/`CorpusMetrics` extended with the style features
  (all fields defaulted – existing payloads stay valid).
- `LanguageProfile`/`ResolvedLanguage` carry the new style patterns;
  `CorpusConfig` accepts optional overrides (`passive_regex`, `nominal_regex`,
  `adjective_regex`, `first_person_starters`).
- Dashboard KPI row extended (Guiraud R, HD-D, staccato, first-person starts,
  consistency, top deviant).

## [1.0.2] – 2026-09-22

### Fixed

- `lixity dashboard` crashed with `NameError: name 'os' is not defined`
  (`os` was imported only in the `__main__` branch).
- `lixity dashboard` now accepts the documented `-o` shorthand for `--output`.

### Added

- Screenshots (CLI report, dashboard light/dark) generated from the reference
  manuscript, embedded in the README and the project page.
- `docs/USAGE.md`: full command-line, library and configuration reference with
  a metric glossary and troubleshooting section.
- `CHANGELOG.md`.
- CI matrix testing Python 3.10 and 3.12 plus a pinned lint step.
- `[project.urls]` metadata for repository, docs, changelog and issues.

### Changed

- README and GitHub Pages rewritten for readability, with a quick start, a
  dashboard guide and a worked example.
- Requires Python 3.10 or newer (previously `>= 3.9`, which was EOL and
  inconsistent with the configured Ruff target `py310`).
- Modernised type annotations (`X | None`, builtin generics), sorted imports,
  precise exception handling in `FileUtils`; all 99 Ruff findings resolved and
  the rule set pinned in `pyproject.toml`.

## [1.0.1] – 2026-09-22

### Changed

- English code comments, documentation and generated CLI/site text.

## [1.0.0] – 2026-09-22

### Added

- Initial release: corpus metrics (ASL, TTR, Guiraud R, Yule's K, Flesch, LIX,
  dialogue and function-word ratios, punctuation densities, perception
  filters), paragraph-accurate tense profiles, single-file HTML dashboard,
  seven language profiles plus a neutral fallback, and idempotent publication
  helpers.

[Unreleased]: https://github.com/mfahsold/lixity/compare/v1.16.0...HEAD
[1.16.0]: https://github.com/mfahsold/lixity/compare/v1.15.0...v1.16.0
[1.15.0]: https://github.com/mfahsold/lixity/compare/v1.14.0...v1.15.0
[1.14.0]: https://github.com/mfahsold/lixity/compare/v1.13.0...v1.14.0
[1.13.0]: https://github.com/mfahsold/lixity/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/mfahsold/lixity/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/mfahsold/lixity/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/mfahsold/lixity/compare/v1.9.1...v1.10.0
[1.9.1]: https://github.com/mfahsold/lixity/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/mfahsold/lixity/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/mfahsold/lixity/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/mfahsold/lixity/compare/v1.6.1...v1.7.0
[1.6.1]: https://github.com/mfahsold/lixity/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/mfahsold/lixity/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/mfahsold/lixity/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/mfahsold/lixity/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/mfahsold/lixity/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/mfahsold/lixity/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/mfahsold/lixity/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/mfahsold/lixity/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/mfahsold/lixity/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/mfahsold/lixity/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/mfahsold/lixity/releases/tag/v1.0.0
