# Changelog

All notable changes to Lixity are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
