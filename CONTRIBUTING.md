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
| Agent operating rules that `AGENTS.md` delegates to | `AGENT_PROFILE.md` | Commit only durable rules; a session log belongs in `.planning/` |
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
make docs-check           # version pins, changelog, staged-site link integrity
```

To exercise the dashboard locally, `make serve` starts a background instance
through `scripts/lixity-start.sh` (PID file, `status`/`restart`/`stop`), and
`make stop` shuts it down. Override the port with `make serve LIXITY_PORT=9000`.
Windows uses `scripts/lixity-start.ps1` with the same lifecycle. See
[running the server](docs/INSTALLATION.md#running-the-server) for the
systemd/launchd/Task Scheduler equivalents.

Without make:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -W error -q -p no:asyncio
RUFF_CACHE_DIR=/tmp/ruff_cache .venv/bin/ruff check src tests scripts
.venv/bin/mypy --strict src
```

CI (`.github/workflows/tests.yml`) runs the same checks on Python 3.10–3.13,
research checks on macOS and Windows, browser checks, and wheel packaging.
Native PDF integration tests need Poppler (`pdftotext` and `pdftoppm`); CI installs
it on Linux and macOS. Locally, follow [the PDF setup](docs/INSTALLATION.md).
Tests requiring an unavailable Poppler executable report an explicit skip;
the synthetic worker subprocess test runs on every platform without a model.
Optional local hooks:
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
   entries. `tests/test_pages.py` checks that staged HTML canonicals match the
   sitemap. Regenerate public screenshots after visual changes, review them,
   and update their HTML dimensions; label unreleased appearances explicitly. Keep `llms.txt` factual; it is not a search visibility guarantee.
5. Preview publication with `python3 scripts/stage_pages.py --output /tmp/lixity-pages-preview`
   using a new output directory. Pages uploads this selected tree, not all of
   `docs/`. New public paths must be added deliberately to the staging rules.

   Two invariants matter for links, because staging flattens `docs/<name>` to
   `/<name>`:

   - **Nothing outside `docs/` is published.** Repository-root documents are
     written for browsing inside the checkout, where `docs/` is a real
     subdirectory, so flattening them onto the site root would break every
     `docs/...` link they contain. Reference `README.md`, `CONTRIBUTING.md`,
     `SECURITY.md`, `LICENSE` and `CHANGELOG.md` by absolute repository URL
     (`https://github.com/mfahsold/lixity/blob/main/<name>`) — correct both in
     the checkout and on Pages. A `../NAME` link resolves locally and 404s
     publicly.
   - `tests/test_documentation.py` stages the docs and validates every relative
     link and heading anchor against the **staged tree**. The pre-existing
     checkout-only link test cannot see this class of breakage, which is why
     the staged-tree test exists. Run `make docs-check` before concluding a
     documentation change is link-safe.
6. Review staged paths and content. Exclude `.planning/`, local reports, private
   source bytes and machine-specific settings. After an authorized push, verify
   CI and the public deployment; do not infer success from a local build alone.

For UI work, run `node tests/browser/visual-consistency.cjs` as described in
[the browser guide](tests/browser/README.md). It protects common palette roles,
action and heatmap contrast, focus and enlarged text-spacing behavior; it is not
a full accessibility audit. Ground new design claims in
[the documented evidence](docs/ARCHITECTURE.md#visual-consistency-and-evidence),
not an assumed universal font, hue or performance gain.

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
5. A behaviour that degrades instead of failing must announce itself. If a
   fallback guess can change a result the user relies on, return unknown and
   report it — undeterminable is not absent. Distinguish "could not read",
   "could not parse" and "not present" in the message.
6. A deprecated parameter keeps working but warns, states the version it will
   be removed in, and gets a test that pins both the warning and the silence of
   the current call path. The suite runs under `-W error`, so a warning that
   fires during normal use fails the build.
7. All tests, mypy and ruff must pass.

## Reporting bugs

Open an issue with:

- Lixity version (`lixity --version`)
- Python version and OS
- Minimal Markdown snippet that reproduces the problem
- Command line used

Security issues: private mail to **mfahsold@googlemail.com** (see
[`SECURITY.md`](SECURITY.md)).
