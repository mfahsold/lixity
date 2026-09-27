# Contributing to Lixity

Thanks for helping improve Lixity. The project is **source-available under
LNCL-1.0**, for projects with no commercial purpose. Books intended for sale,
including self-publishing, require a separate written commercial license.
See [licensing examples](docs/LICENSING.md).

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

## Where work belongs

| Material | Location | Commit / publish |
| --- | --- | --- |
| Engine behavior and shared UI | `src/lixity/` | Commit with relevant checks |
| Regression coverage and reusable tooling | `tests/`, `scripts/` | Commit when it protects or operates the product |
| Installation, usage, methods, interfaces and supported architecture | `docs/` and README | Maintain as product documentation; label proposals and unreleased behavior |
| Repository-wide agent rules | `AGENTS.md` | Commit concise, durable guidance |
| Task plans, session notes, temporary implementation decisions | `.planning/` | Local only, ignored; old tracked plans are preserved locally under `.planning/legacy/` |
| Browser screenshots, traces and diagnostic scratch output | `.artifacts/` or `/tmp` | Local only; reviewed public examples are a separate deliberate addition |
| Manuscripts, retained research bytes, backups and credentials | Separate project storage | Never include in engine commits or public artifacts |

Keep `docs/AGENTS.md` focused on using Lixity's automation interface, rather than
instructions for developing this repository. The research RFC remains durable
product architecture, explicitly marked as a proposal; an agent's task checklist
does not belong there. Do not duplicate these rules in tool-specific instruction
trees without a concrete integration need.

Ignore rules affect untracked files only. Review tracked and staged paths before
each commit; avoid blanket staging and forced additions. When removing an old
plan from public sources, preserve a local copy first. Removing a file from the
current tree does not remove it from Git history; do not rewrite history as part
of routine documentation cleanup.

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

### Updating documentation and Pages

1. Change the canonical command/API reference with the behavior; explain limits
   and intentional schema compatibility changes.
2. Update the README entrypoints, changelog and relevant HTML guides in
   `docs/guides/`. Reuse `docs/assets/site.css`; keep main-only features distinct
   from the current tagged release.
3. Run `make docs-check` (or `make docs-sync` to update release references), then
   the affected browser checks from `tests/browser/README.md`.
4. Check page titles, descriptions, canonical URLs, internal links and sitemap
   entries. Keep `llms.txt` factual; it is not a search visibility guarantee.
5. Preview publication with `python3 scripts/stage_pages.py --output /tmp/lixity-pages-preview`
   using a new output directory. Pages uploads this selected tree, not all of
   `docs/`. New public paths must be added deliberately to the staging rules.
6. Review staged paths and content. Exclude `.planning/`, local reports, private
   source bytes and machine-specific settings. After an authorized push, verify
   CI and the public deployment; do not infer success from a local build alone.

Search visibility work should prioritize useful HTML answers and accurate
product boundaries. Cite primary guidance for changing SEO/GEO practices and
separate recommendations from measured traffic or citation results.

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
