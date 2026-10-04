# Contributing to Lixity

Lixity is **source-available under LNCL-1.0**, for projects with no commercial
purpose. Books intended for sale, including self-publishing, require a separate
written commercial license.
See [licensing examples](docs/LICENSING.md).

## Ground rules

- Write documentation, code comments and docstrings in English. Localized
  resources, quoted source material and linguistic test fixtures are exceptions.
- English is the default language. Automatic manuscript-language detection is
  explicit (`--language auto`); never silently use German as a default.
- Localization includes linguistic profiles and scientific explanations, not
  just labels. Prioritize German, then English, then the other supported languages;
  see the [language contract](docs/LOCALIZATION.md). This does not change the
  default analysis language or establish equal accuracy.
- Keep language-independent mathematics and machine-readable identifiers stable.
  Language-specific coefficients need documented sources and numerical tests;
  heuristics must be labeled as such, not presented as validated measurements.
- Keep the analysis engine offline, deterministic and compatible with Python
  3.10+. Discuss new required dependencies (current: `pydantic`, `rich`, `orjson`).
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
| Task plans, session notes, temporary implementation decisions | `.planning/` | Local only, ignored |
| Browser screenshots, traces and diagnostic scratch output | `.artifacts/` or `/tmp` | Local only; reviewed public examples are a separate deliberate addition |
| Manuscripts, retained research bytes, backups and credentials | Separate project storage | Never include in engine commits or public artifacts |

`AGENTS.md` governs repository work; `AGENT_PROFILE.md` contains delegated
operating rules. `docs/AGENTS.md` describes the shipped automation interface.
Keep proposals clearly marked and task checklists out of product documentation.

Review staged paths and their complete diff before each commit. Ignore rules do
not remove tracked files. Preserve local planning before removing it from the
public tree; routine cleanup does not include rewriting Git history.

## Development setup

Use the [installation guide](docs/INSTALLATION.md) for prerequisites and Windows
commands. The make targets create an isolated `.venv`; they do not alter global Python.

```bash
make install-dev          # or: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
make check                # ruff + mypy --strict + pytest -W error
make docs-check           # version pins, changelog, staged-site link integrity
```

For the dashboard, run `lixity serve --no-project` in the foreground, or use
`make serve` and `make stop` for the optional background launcher. A custom port
is selected with `make serve LIXITY_PORT=9000`. See
[server setup](docs/INSTALLATION.md#running-the-server) for Windows and login startup.

Without make:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -W error -q -p no:asyncio
RUFF_CACHE_DIR=/tmp/ruff_cache .venv/bin/ruff check src tests scripts
.venv/bin/mypy --strict src
```

CI (`.github/workflows/tests.yml`) runs the same checks on Python 3.10–3.13,
research checks on macOS and Windows, browser checks, and wheel packaging.
Native PDF tests need Poppler (`pdftotext` and `pdftoppm`) and report an explicit
skip if it is missing. The synthetic worker test needs no model.
Optional hooks are installed with `pre-commit install`; see
[`.pre-commit-config.yaml`](.pre-commit-config.yaml). Tags matching `v*` build
release packages; authorized documentation pushes to `main` deploy Pages.

### Updating documentation and Pages

Update the canonical reference, changelog, README and relevant guides together.
Preserve mathematical limits and JSON compatibility notes. Reuse the shared
Pages stylesheet and scripts; distinguish unreleased behavior from the current
release. Keep `llms.txt` factual.

Run `make docs-check` (`make docs-sync` updates release pins) and relevant
[browser checks](tests/browser/README.md). Inspect desktop and mobile layouts,
titles, links and reviewed public screenshots; set their actual image dimensions.

Preview the published tree with
`python3 scripts/stage_pages.py --output /tmp/lixity-pages-preview`, using a new
directory. Only selected paths inside `docs/` are published. New public paths
must be added deliberately to the staging rules. Root documents such as README
and CONTRIBUTING must be linked by their absolute GitHub URL: `../README.md`
works in a checkout but breaks on Pages. The documentation tests validate links
against the staged tree.

Review staged paths and content for private data, local reports and planning.
After an authorized push, verify CI and the public deployment.

The visual-consistency browser check covers palette, contrast, focus and enlarged
text spacing; it is not a full accessibility audit. Ground design claims in
[documented evidence](docs/ARCHITECTURE.md#visual-consistency-and-evidence).

## Pull requests

1. Branch from `main`.
2. Keep public JSON contracts stable or bump `schema_version`
   (`docs/AGENTS.md`).
3. Update `CHANGELOG.md` under `[Unreleased]`.
4. New metrics: document formulas in `docs/METHODS.md` and caveats in
   `docs/STABILITY.md`.
5. Report degraded behavior. If a measurement cannot be determined, return
   unknown rather than guessing. Distinguish unreadable, invalid and absent data.
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
