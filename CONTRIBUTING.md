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
make docs-check           # standalone generated-doc and staged-site checks
```

For the dashboard, use `make run` in the foreground, or `make start` and
`make stop` for the managed background service. A custom port
is selected with `make start LIXITY_PORT=9000`. See
[server setup](docs/INSTALLATION.md#running-the-server) for Windows and login startup.

Without make:

```bash
PYTHONPATH=src .venv/bin/python -m pytest -W error -q --durations=15 -p no:asyncio
.venv/bin/ruff check src tests scripts
.venv/bin/mypy --strict src
```

`make check` is the canonical everyday source check; it includes documentation
Python tests in the full suite. Use `make browser` for UI changes and
`make browser-full` before a release that changes rendered behavior. Browser
selection and native desktop/mobile coverage are documented in
[the browser entrypoint](tests/browser/README.md).

During development, run the affected test module first. After a failure, pytest's
`--ff -x` runs previous failures first and stops at the next failure; `--lf` is
useful for a repair loop but does not establish a complete pass. Keep the full
release gate. `make test` reports the slowest 15 cases so runtime changes have
evidence. Default Ruff, mypy and pytest caches stay inside each checkout;
override `RUFF_CACHE`, `MYPY_CACHE` or `PYTEST_CACHE` only deliberately.
Use the same pinned Ruff in the editor and optional commit hook; its native
[language server](https://docs.astral.sh/ruff/editors/) reports issues while
editing. Keep strict mypy as the shared type-checking authority rather than
introducing a second incompatible checker configuration. For edited JavaScript,
`node --check path/to/file.js` catches syntax errors before a browser run.
These checks complement focused behavior tests; they do not prove runtime behavior.

GitHub's `tests`, `browser` and `research-platforms` workflows are manual
fallbacks; pushes and pull requests do not automatically repeat these heavy
suites. The `tests` workflow preserves Ruff, strict `mypy` and the full Python
suite with Poppler on Linux/Python 3.12. Run relevant supported interpreters
locally. Filesystem, process-lifecycle, packaging and native-tool changes also
need Windows/macOS evidence, either on those systems or from a deliberately
dispatched `research-platforms` run. A Linux pass does not establish equivalent
Windows/macOS behavior.
The platform workflow defaults to the central pytest `portability` marker
(`python -m pytest tests -m portability -W error -q -p no:asyncio`), covering
archive/filesystem, service observation, installed-package notices and read-only
export seams, plus real start/restart/stop, simultaneous starts and the Windows
PowerShell wrapper. Select `scope=full` only when the full research/lifecycle suite is
needed on both systems. The ordinary local full suite still runs every test;
markers do not remove coverage from `make check`.

When workflow files change, run `make workflow-check` with actionlint installed,
or `make workflow-check ACTIONLINT=/path/to/actionlint`. This explicitly validates
all `.github/workflows/*.yml` files and fails if the tool is unavailable; it is
not a required Python dependency or part of the default source/release targets.

Build artifacts with `make build`. The shared `scripts/check_release.py` builds
the source archive and wheel in a fresh temporary directory, compares both
packages' Python modules, typing marker and UI assets against source filenames
and bytes, and checks exact version metadata. Only after validation does it
replace managed `dist/` artifacts and write `SHA256SUMS`. Unrelated files or
directories in `dist/` cause an error and are preserved. The release workflow
uses the same checker.
The source archive also includes and verifies shared Python test fixtures.

Native PDF tests need Poppler (`pdftotext` and `pdftoppm`) and report an explicit
skip if it is missing. Select them locally with `pytest -m native_pdf`.
Synthetic worker and Tesseract protocol tests need no model or installed OCR engine.
For optional hooks, install `pre-commit` separately, then run
`pre-commit install`; see
[`.pre-commit-config.yaml`](.pre-commit-config.yaml). Tags matching `v*` build
release packages; after GitHub publication and a successful or intentionally
skipped PyPI step, the release pipeline deploys Pages from the same tag.
Main pushes do not publish unreleased documentation automatically;
manual Pages dispatch remains available for a deliberate preview.

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

### Investigating performance

Measure the operation authors actually wait for: a fresh public API read, a
complete analysis, or a native browser interaction. Separate fresh `Repository`
instances from repeated reads on one instance, and label a warm filesystem cache
as warm. Record synthetic input size/shape, Python version, source revision,
wall time, CPU time and several individual runs; compare their medians on the
same machine without other test workers. Fixture construction, profiling and
memory instrumentation belong outside timed runs. Check both tiny records and
large payloads: reducing small-read allocations must not double image/PDF memory.
A small test or a faster
inner loop does not establish an equivalent end-to-end improvement.

Use [cProfile](https://docs.python.org/3/library/profile.html) for call attribution,
then measure again without it: its instrumentation is not a benchmark. Inspect
allocations separately with [tracemalloc](https://docs.python.org/3/library/tracemalloc.html).
Keep profiles and measurements in ignored `.artifacts/`; never add a real book
archive to tests. The existing operation-count regressions cover revision path
checks, complete archive scans for citation batches, selected-history traversal,
anchor lookups without linguistic analysis and chapter effect comparisons.
Prefer these deterministic cost checks over machine-dependent time limits.

Faster reads must preserve bounded I/O, checksums, strict schemas, source quote
verification and project isolation. Test missing/changed files, symlinked path
components, withdrawals/purges, pinned versions and a subsequent fresh read.
A timestamp or file-size signature is not a checksum. A shared `Snapshot` cache
would also change nested mutable-model ownership and external-tamper detection;
do not extend its lifetime as a shortcut. Profile remaining work before adding
threads, dependencies, a database service or a native extension.

### Preparing a release

After updating the source version, changelog, release notes and documentation
pins (`make docs-sync`), run:

```bash
make release-check RELEASE_TAG=vX.Y.Z
```

This first rejects a missing or source-mismatched tag or absent/empty release notes, before heavy checks even
under `make -j`. It then runs `make check` once, `make docs-generated-check` and the dependency audit,
then builds fresh archives, requires an exact tag/source/wheel/sdist version match,
and installs the wheel in a temporary
isolated environment outside the checkout. It checks dependencies, CLI/distribution
identity, diagnostics, all three reading-website formats and a neutral document PDF.
The output is the verified wheel, source archive and
`SHA256SUMS` in `dist/`. Full pytest already covers Pages/documentation tests;
`docs-generated-check` adds check-only version-pin, bundle and guide-alternative
validation without running those tests twice. `make docs-check` remains the
complete standalone documentation check. Recheck existing artifacts without rebuilding with
`.venv/bin/python scripts/check_release.py --tag vX.Y.Z --smoke`.

Code-only releases can skip media regeneration. When the UI
or the published guides change, regenerate them first with `make docs-sync`,
`make examples` and `make screenshots` (and `make videos` for the walkthroughs).
The documentation tests compare every bundled UI asset in all three public
reports with the packaged source. A stale demo is a failing check, even if its
version string still matches. Before rollout, verify the installed distribution
and running service separately; rebuilding public pages does not update either.

Preparation does not commit, tag, push or publish. After reviewing the changes
and obtaining release authorization, complete `make browser-full` for UI-affecting releases,
push the reviewed commit to `main` and its matching `vX.Y.Z` tag. The tag
workflow only builds, verifies and smoke-installs the artifacts from the tag,
attests them for `gh attestation verify`, attaches them to a draft release and
publishes that draft only when every asset is present. The full source and
documentation checks must already have passed locally through `make release-check`;
the tag workflow does not rerun the heavy source/browser suites. Release build,
smoke installation and attestation remain automatic; after GitHub publication
and a successful or intentionally skipped PyPI step, the release pipeline
deploys Pages from that exact tag.
Verify a downloaded artifact with:

```bash
gh attestation verify dist/lixity-X.Y.Z-py3-none-any.whl -R mfahsold/lixity
```

Repository-level immutable releases are enabled, so published assets and tags
remain fixed. Prepare and review release notes before tagging. Corrected code or
artifacts belong in a new patch release, preserving the earlier checksums and
provenance.

Every tagged release is distributed and archived automatically:

- the workflow uploads wheel and sdist to PyPI when the repository variable
  `PUBLISH_PYPI` is `true` (trusted publishing, environment `pypi`); if a run
  misses PyPI, dispatch the same workflow with the `tag` input to build and
  publish without touching the GitHub release;
- Zenodo archives each new release once the repository is enabled there, so
  released versions receive a DOI without a local step.

Zenodo processing is asynchronous and outside the Actions result. Verify the
specific version's public record and DOI before reporting archival complete;
a successful GitHub/PyPI/Pages run alone does not establish it. Investigate a
missing record in Zenodo's GitHub integration release/error view rather than
republishing an immutable tag. When both metadata files exist,
`.zenodo.json` takes precedence over `CITATION.cff`; maintain their product
description and conceptual citation consistently. See
[Zenodo's metadata guidance](https://help.zenodo.org/docs/github/describe-software/).

Documentation deployment uses the separate reusable Pages workflow, called for
the published release tag after those publication steps. A PyPI catch-up dispatch
also pins Pages to its selected existing tag. The `github-pages` environment must
permit version tags (`v*`); existing branch policies remain separate. A manual
Pages dispatch can deliberately preview an explicitly selected, permitted ref.
A new release with
a lower version number requires explicit version selection by installations
already using a higher version; this workflow does not change package-manager
ordering.

### Release communication

Use the verified release notes as the source for communication. Update an
existing canonical article when the workflow changed; keep short patch pointers
proportionate to their reader impact. Preserve established article identities
and canonical URLs instead of creating a competing copy for every patch.
For examples of distinct patch and feature communication, see
[NumPy's release guidance](https://numpy.org/doc/stable/dev/releasing.html).

The release workflow publishes packages and documentation; it sends no social
posts. Keep account credentials, exact drafts, approval/send state and metric
snapshots in the separate outreach workspace. Preview the final composed text
and platform-specific limits before an explicitly authorized send. A draft or a
successful dry run is not publication. Read the destination back after sending,
record its identity and source version, and inspect an uncertain result before
retrying. Keep delivery, article views, repository activity and website traffic
as separate observations; unavailable statistics remain unknown.

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

Screenshot selection is maintained once in `docs/screenshots/manifest.json`.
Normal capture, the generated catalog and Pages staging use that inventory;
adding an image alone does not publish it. Prepare the reusable lead/support
asset handoff with `scripts/make_screenshots.py --outreach-package NEW_DIRECTORY`.
It records the source revision, working-tree status, exact image hashes, captions,
alt text and destinations without sending or scheduling posts. Keep one current
editorial package in the separate outreach workspace; old publication records
remain history rather than additional active campaigns. See the
[screenshot catalog](docs/screenshots/README.md).

Review staged paths and content for private data, local reports and planning.
After an authorized tagged release or manual Pages preview, verify the public
deployment and any explicitly dispatched test workflows. Ordinary pushes do not
start the heavy test suites or deploy Pages.

Shared component changes also affect staged Pages and embedded examples. Review
them through the same local browser checks, then publish the release tag or use
`gh workflow run pages.yml --ref main` for an authorized preview.

The visual-consistency browser check covers palette, contrast, focus and enlarged
text spacing; it is not a full accessibility audit. Ground design claims in
[documented evidence](docs/ARCHITECTURE.md#visual-consistency-and-evidence).

Follow the [annotation semantics](docs/ARCHITECTURE.md#annotation-semantics-and-visual-identity)
when changing manuscript presentation. Keep research association patterns,
measured comparisons, counted spans, search and author tasks distinguishable
without color. Exercise overlap, Analysis Off, keyboard context/return, selection,
forced colors and both themes at desktop/mobile widths. Counts must retain their
meaning (associations versus distinct sources; paragraph versus chapter values).
Display changes use current owners and do not introduce record writes or source
rewrites. Native/read-only review views share these semantics; curated publication
scope remains separate.

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

## Release migrations and the current product path

Maintain one current product and UI path. Existing projects move forward at
releases through explicit, reviewed migrations when conversion is needed; do not
add legacy UI modes or parallel compatibility branches for an older presentation.
A presentation-only change does not require rewriting project data. Discuss
concrete unresolved data or workflow conflicts before implementing a migration.

For changes that require conversion, document the affected versions, exact scope,
implemented procedure, validation and recovery in the release notes and relevant
usage guide. Test on a synthetic project and a restored copy before applying to
the original. Preserve retained source bytes, immutable revisions, provenance and
evidence links. Do not relabel schema versions, rewrite accepted history or delete
old records merely to make a project open in the new UI. Version intentional
public JSON contract changes explicitly.

The current research backup workflow is `lixity research export --project
PROJECT --output BACKUP`, followed by `lixity research restore --from BACKUP --to
NEW_PROJECT`, `lixity research audit --project NEW_PROJECT` and `lixity research
reindex --project NEW_PROJECT`. Restore requires a new or empty destination.
These commands back up and validate the research archive; they are not a general
release migration command. **Current main** implements the specific plaintext-to-gzip
manifest conversion as `lixity research migrate-storage --project PATH --backup
PATH [--expected-snapshot HASH]`. Normal application reads require the current
storage marker; run this explicit migration for an older plaintext store. The
command preserves canonical hashes, HEAD, immutable revisions and source bytes.
It verifies a non-overwriting portable backup and a restored copy before the
writer-locked conversion; changed HEAD aborts the conversion. Test this path on
synthetic data and a restored copy, including staging interruption, post-marker
cleanup retry, rejected stale snapshots and unchanged evidence links. Validate
the migrated store with audit, restore its portable backup and check affected
analysis, citation, import and publication workflows before resuming services.
Compression retains full snapshots and the bounded 100,000-entry limit; it is
not a delta-storage migration. Manuscripts, Zotero data and application profiles need
their own backup scope; see [export and restoration](docs/research/USAGE.md#export-and-restoration)
and [paired Zotero backup](docs/research/USAGE.md#paired-zoteroresearch-backup-and-restore).
Keep the pre-migration backup until recovery and the affected workflows have
been verified. A required migration is release work to implement and validate,
not an automatic capability to promise before it exists. Source edits alone do
not authorize migration of a user's project, a release or a service restart.

## Pull requests

1. Branch from `main`.
2. Keep public JSON contracts stable or bump `schema_version`
   (`docs/AGENTS.md`).
3. Update `CHANGELOG.md` under `[Unreleased]`.
4. New metrics: document formulas in `docs/METHODS.md` and caveats in
   `docs/STABILITY.md`.
5. Report degraded behavior. If a measurement cannot be determined, return
   unknown rather than guessing. Distinguish unreadable, invalid and absent data.
6. Replace obsolete interfaces through an explicit release transition rather than
   adding compatibility branches by default. Document the replacement and any
   required project migration; test the current path and migration behavior.
   If a transition warning is deliberately retained, state its removal version
   and test that ordinary current usage remains warning-free under `-W error`.
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
