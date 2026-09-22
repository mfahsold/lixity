# Changelog

All notable changes to Lixity are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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

[1.0.2]: https://github.com/mfahsold/lixity/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/mfahsold/lixity/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/mfahsold/lixity/releases/tag/v1.0.0
