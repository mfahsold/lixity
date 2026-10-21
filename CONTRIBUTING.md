# Contributing to Lixity

Lixity is **open source under the AGPL-3.0-or-later**; contributions are
accepted under the same license. A separate written commercial license exists
for closed-source integrations that cannot meet the AGPL.
See [licensing](docs/LICENSING.md).

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
make browser              # everyday local Playwright checks (browser-full: all)
make docs-check           # version pins, changelog, staged-site link integrity
```

For the dashboard, use `make run` in the foreground, or `make start` and
`make stop` for the managed background service. A custom port
is selected with `make start LIXITY_PORT=9000`. See
[server setup](docs/INSTALLATION.md#running-the-server) for Windows and login startup.

Without make:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -W error -q -p no:asyncio
RUFF_CACHE_DIR=/tmp/ruff_cache .venv/bin/ruff check src tests scripts
.venv/bin/mypy --strict src
```

Core CI (`.github/workflows/tests.yml`) is one `check` job on Python 3.12 for
every pull request, push to `main` and manual dispatch: Ruff, `mypy` and the
full suite with real Poppler PDF tests. Compatibility interpreters, browser
regression suites and Windows/macOS suites are local-first. Run `make check`
with each supported interpreter, `make browser` for rendered desktop/mobile
workflows, and dispatch the manual `browser` or `research-platforms` workflow
when a change needs an independent platform signal. Configure required status
checks from `check`. Pip downloads are cached, and newer pushes cancel
superseded runs.

Build artifacts with `make build`. The shared `scripts/check_release.py` builds
the source archive and wheel in a fresh temporary directory, compares both
packages' Python modules, typing marker and UI assets against source filenames
and bytes, and checks exact version metadata. Only after validation does it
replace managed `dist/` artifacts and write `SHA256SUMS`. Unrelated files or
directories in `dist/` cause an error and are preserved. CI uses the same checker.
The source archive also includes and verifies shared Python test fixtures.

Native PDF tests need Poppler (`pdftotext` and `pdftoppm`) and report an explicit
skip if it is missing. Select them locally with `pytest -m native_pdf`.
Synthetic worker and Tesseract protocol tests need no model or installed OCR engine.
Optional hooks are installed with `pre-commit install`; see
[`.pre-commit-config.yaml`](.pre-commit-config.yaml). Tags matching `v*` build
release packages; authorized documentation pushes to `main` deploy Pages.

### Test architecture

Keep numerical reference cases close to the primitive they verify, with expected
values derived independently of the implementation. Pipeline tests should check
composition: selected chapters, register exemptions, emitted diagnostics and
preserved contracts. Use enough varied chapters to exercise a diagnostic; an
assertion loop over an empty result does not verify its values.

Test settings markup directly for component contracts, HTTP handlers for saved
state and conflicts, and browsers for rendered interactions. Shared mechanics
belong in `tests/support.py`, `tests/research_support.py` or the browser support
directory; test modules should not import fixtures from one another. Cached
fixtures must be immutable or return fresh mutable state.

Render every supported locale at desktop and mobile widths when labels or
layout vary. Run language-independent interaction and failure scenarios once
per relevant viewport unless localization affects their behavior. Preserve
native HTTP workflows separately from intercepted browser scenarios.

For workbench changes, test composed transitions with the existing browser
runner rather than proving each isolated control independently:

| Journey | Required invariant |
| --- | --- |
| Manuscript → analysis toggle → values → dossier → overview → return | The document/profile nodes and passage remain the same; analysis visibility and dossier choice are distinct |
| Quotation → pinned claim/dossier → saved associations → passage | Version and source context remain explicit; unresolved anchors are reviewed rather than guessed |
| Menu/form → workspace switch → Escape | Only the active visible surface dismisses or receives return focus; permitted unsaved drafts survive ordinary view changes |
| Changed/unavailable source → retry → recovery | Saved analysis is labelled, cached source identity stays truthful, and successful validation removes the notice |

Use synthetic mixed-structure documents to cover source-order joins, repeated
text, custom chapters, code/notes and one profile spanning multiple list items.
Keep analytical scope, exact profile hashes/offsets, PDF adapter behavior and
versioned JSON contracts unchanged when changing presentation. For large-book
work, record generated size, reader-ready/reflow timing and native selection/find
behavior before considering virtualization; a short fixture or one unthrottled
sample is not a performance guarantee. See [browser coverage](tests/browser/README.md)
for the maintained suites and temporary artifacts.

Consolidate repeated setup and parameterize equivalent cases before removing
coverage. Remove a test only when retained assertions cover its failure mode
more precisely. For subtle regressions, verify that the assertion detects a
small representative fault in an isolated copy; never mutate the shared source
tree while other tests or agents are using it. Test counts and single-run
timings alone do not establish coverage or performance.

### Preparing a release

After updating the source version, changelog, release notes and documentation
pins (`make docs-sync`), run:

```bash
make release-check RELEASE_TAG=vX.Y.Z
```

This runs `make check` and `make docs-check`, builds fresh archives, requires an
exact tag/source/wheel/sdist version match, and installs the wheel in a temporary
isolated environment outside the checkout. It checks dependencies, CLI version
and `about --json` metadata. The output is the verified wheel, source archive and
`SHA256SUMS` in `dist/`. Recheck existing artifacts without rebuilding with
`.venv/bin/python scripts/check_release.py --tag vX.Y.Z --smoke`.

Code-only releases can skip the generated documentation surfaces. When the UI
or the published guides change, regenerate them first with `make docs-sync`,
`make examples` and `make screenshots` (and `make videos` for the walkthroughs).

Preparation does not commit, tag, push or publish. After reviewing the changes
and obtaining release authorization, run `make browser` for UI-affecting changes,
push the reviewed commit to `main` and its matching `vX.Y.Z` tag. The tag
workflow only builds, verifies and smoke-installs the artifacts from the tag,
attests them for `gh attestation verify`, attaches them to a draft release and
publishes that draft only when every asset is present. The full source and
documentation checks already ran locally through `make release-check` and in the
`check` job. Verify a downloaded artifact with:

```bash
gh attestation verify dist/lixity-X.Y.Z-py3-none-any.whl -R mfahsold/lixity
```

Repository-level immutable releases are enabled, so published assets and tags
cannot change afterwards. Prepare and review the release notes before tagging;
to correct an already published release, disable the setting with
`gh api --method DELETE repos/mfahsold/lixity/immutable-releases`, then enable
it again afterwards.

Every tagged release is distributed and archived automatically:

- the workflow uploads wheel and sdist to PyPI when the repository variable
  `PUBLISH_PYPI` is `true` (trusted publishing, environment `pypi`); if a run
  misses PyPI, dispatch the same workflow with the `tag` input to build and
  publish without touching the GitHub release;
- Zenodo archives each new release once the repository is enabled there, so
  released versions receive a DOI without a local step.

Documentation deployment remains the separate Pages workflow. A new release with
a lower version number requires explicit version selection by installations
already using a higher version; this workflow does not change package-manager
ordering.

### Public website measurement

Pages-only `docs/assets/analytics.js` uses GoatCounter's documented
[pixel endpoint](https://www.goatcounter.com/help/pixel). The public site code
lives in the explicitly staged `docs/assets/analytics.json`; `null` disables it.
Only the production HTTPS origin and `/lixity/` path are eligible. Respect browser
Do Not Track / Global Privacy Control. Send only public pathname, public title,
origin-only referrer and fixed CTA names; exclude URL query/hash, form inputs,
selection, manuscript/research data, local paths and persistent identifiers.
The local app and generated user exports must never acquire this adapter.

The shared site script loads it for normal Pages; public example metadata adds
it to the reviewed synthetic/public-domain examples. Do not add the provider's
ordinary auto-tracking snippet alongside it: that would double-count and include
its default data. A pixel request is transmission evidence, not proof of a
processed dashboard count. Verify pageviews and each named CTA after deployment
against the actual statistics. Existing visits cannot be backfilled. API read
credentials and outreach snapshots belong outside this repository; the site
code is public, an API token is not. See the
[visitor notice](https://mfahsold.github.io/lixity/#website-measurement).

### Updating documentation and Pages

Update the canonical reference, changelog, README and relevant guides together.
Preserve mathematical limits and JSON compatibility notes. Reuse the shared
Pages stylesheet and scripts; distinguish unreleased behavior from the current
release. Keep `llms.txt` factual.

Search and AI retrieval use the same maintained public evidence: descriptive
page titles, one canonical URL, readable HTML, accurate application/article
metadata, source links and real modification dates. Keep release information
consistent with PyPI, the demo and installation guidance. Do not invent ratings
or turn roadmap items into published capabilities. Google's
[AI search guidance](https://developers.google.com/search/docs/fundamentals/ai-optimization-guide)
does not require special AI markup; `llms.txt` serves documentation consumers,
not a promised Google ranking improvement. Crawlability and a sitemap do not
establish indexing, traffic or inclusion in generated answers. Inspect those
outcomes through authorized Search Console and analytics access, and report
unavailable measurements as unknown.

Run `make docs-check` (`make docs-sync` updates release pins) and relevant
[browser checks](tests/browser/README.md). Inspect desktop and mobile layouts,
titles, links and reviewed public screenshots; set their actual image dimensions.

Preview the published tree with
`python3 scripts/stage_pages.py --output /tmp/lixity-pages-preview`, using a new
directory. Only selected paths inside `docs/` are published. New public paths
must be added deliberately to the staging rules. The shared design-token and
component stylesheets are explicitly copied packaged assets. Root documents such as README
and CONTRIBUTING must be linked by their absolute GitHub URL: `../README.md`
works in a checkout but breaks on Pages. The documentation tests validate links
against the staged tree.

Review staged paths and content for private data, local reports and planning.
After an authorized push, verify CI and the public deployment.

The Pages push-path filter does not currently watch `src/lixity/ui/assets/components.css`.
After an authorized `main` push that changes only that shared stylesheet, deploy
it manually with `gh workflow run pages.yml --ref main`, then verify the deployment.

The visual-consistency browser check covers palette, contrast, focus and enlarged
text spacing; it is not a full accessibility audit. Ground design claims in
[documented evidence](docs/ARCHITECTURE.md#visual-consistency-and-evidence).

For shared interaction changes, define the user journey before choosing suites.
Cover entry, visible state, action scope, dismissal and return to the same task.
Exercise transitions between already working components: a correct inspector and
a correct research form can still interact incorrectly after a view change.
Use synthetic content to check that the requested destination is actually visible,
the reverse control remains reachable after scrolling, and Escape affects only
the active visible surface. Verify both pointer and keyboard routes.

Retain manuscript text/selection, exact research anchors and unsaved field values
where the flow promises them. Include pending, unavailable, stale and failed states
when their owners change; an empty result is not evidence of a successful read.
Backend freshness changes need disappearance/failure/recovery cases as well as
successful source edits. Keep assertions about user-visible behavior rather than
mirroring implementation classes or treating a larger test count as usability.

Publish the same verified workflow in README, the relevant Pages guide and the
generated demo. Check labels, screenshots, capability limits and release versus
current-main claims together; defer descriptions of a candidate UI until it exists.

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

## Support and governance

Lixity is maintained by its author, Matthias Fahsold. Bug reports and feature
requests run through GitHub issues; security reports follow
[`SECURITY.md`](SECURITY.md). Releases are tagged, recorded in the changelog and
distributed through PyPI, GitHub Releases and Zenodo. There is no foundation or
steering committee: changes arrive through pull requests under the repository
license, and public discussion happens in issues. The maintainer aims to respond
to reports within a couple of weeks; there is no paid support.
