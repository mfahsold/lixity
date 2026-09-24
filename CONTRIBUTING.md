# Contributing to Lixity

Thanks for helping improve Lixity. The project is **source-available under
LNCL-1.0** (free for research, education, personal writing and
non-commercial open science; commercial use needs a written license).

## Ground rules

- Write documentation, code comments and docstrings in English. Localized
  resources, quoted source material and linguistic test fixtures are exceptions.
- English is the default language. Automatic manuscript-language detection is
  explicit (`--language auto`); never silently use German as a default.
- Localization includes linguistic profiles, tokenization, sentence boundaries,
  syllables, tense/style patterns, readability models, scientific explanations
  and number formatting—not only translated interface labels.
- Keep language-independent mathematics and machine-readable identifiers stable.
  Language-specific coefficients need documented sources and numerical tests;
  heuristics must be labeled as such, not presented as validated measurements.
- Offline, deterministic, pure Python 3.10+ — no new hard dependencies
  without discussion (current: `pydantic`, `rich`, `orjson`).
- Statistical code stays stdlib-only (no numpy/scipy) so wheels stay tiny
  and installs stay predictable.
- Prefer small, reviewable PRs with tests.
- Never commit manuscripts, dashboards under `exports/`, or secrets —
  see [`.gitignore`](.gitignore) and [`SECURITY.md`](SECURITY.md).

## Development setup

Start with the [installation guide](docs/INSTALLATION.md) for prerequisites,
Windows commands and an isolated environment. `make install` and
`make install-dev` both create `.venv`, verify dependencies and print the
installed version; neither installs into global Python.

```bash
make install-dev          # or: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
make check                # ruff + mypy --strict + pytest -W error
```

Without make:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -W error -q -p no:asyncio
RUFF_CACHE_DIR=/tmp/ruff_cache .venv/bin/ruff check src tests scripts
.venv/bin/mypy --strict src
```

CI (`.github/workflows/tests.yml`) runs the same checks on Python 3.10–3.13
plus a wheel packaging job. Optional local hooks:
`pre-commit install` (trailing whitespace, YAML check, ruff `--fix` — see
[`.pre-commit-config.yaml`](.pre-commit-config.yaml)). Tags matching `v*`
build a wheel and open a GitHub Release (`.github/workflows/release.yml`);
pushes to `main` under `docs/` deploy GitHub Pages
(`.github/workflows/pages.yml` — enable Pages → Source: GitHub Actions in
repo settings once).

## Pull requests

1. Branch from `main`.
2. Keep public JSON contracts stable or bump `schema_version`
   (`docs/AGENTS.md`).
3. Update `CHANGELOG.md` under `[Unreleased]`.
4. New metrics: document formulas in `docs/METHODS.md` and caveats in
   `docs/STABILITY.md`.
5. All tests, mypy and ruff must pass.

## Reporting bugs

Open an issue with:

- Lixity version (`lixity --version`)
- Python version and OS
- Minimal Markdown snippet that reproduces the problem
- Command line used

Security issues: private mail to **mfahsold@googlemail.com** (see
[`SECURITY.md`](SECURITY.md)).
