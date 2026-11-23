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
  3.10+. Discuss new required dependencies. The current runtime uses
  `pydantic`, `rich`, `orjson` and `tomli` on Python 3.10.
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

Use `make install-dev` to create the checkout's isolated `.venv` with dev tools.
The [installation guide](docs/INSTALLATION.md) covers prerequisites, Windows
setup and the separate optional environments for audio inference.

For the dashboard, follow the [service and rollout procedure](docs/INSTALLATION.md#running-the-server)
and [verify the selected listener](docs/INSTALLATION.md#refresh-a-checkout-or-a-packaged-service)
after loading a change.

### Select the checks for your change

| Change | Check |
| --- | --- |
| Source | Run the affected test first, then `make check` for pinned Ruff, `mypy --strict` and the full pytest suite with warnings as errors. |
| UI behavior | Use `make browser` for the fast group or `make browser-changed` to select suites from modified paths. Run `make browser-full` on the final source before a release affecting rendered output. See [browser prerequisites and coverage](tests/browser/README.md). |
| Documentation | Follow [generation and preview](#updating-documentation-and-pages), then run `make docs-check` for a standalone docs pass. When also running `make check`, add `make docs-generated-check` to cover the generators without repeating the Python docs tests. |
| GitHub workflows | Run `make workflow-check` with `actionlint` installed. Override `ACTIONLINT` to use an explicit executable. |
| Packaging | Run `make build` or add an isolated install smoke test with `.venv/bin/python scripts/check_release.py --build --smoke`. |
| Public release | Follow [release preparation](#preparing-a-release) for the local and remote gates. |

For focused Python checks without make, use
`PYTHONPATH=src .venv/bin/python -m pytest tests/test_NAME.py -W error -q -p no:asyncio`.
Run Ruff as `.venv/bin/ruff check src tests scripts` and mypy as
`.venv/bin/mypy --strict src`.

After a failure, pytest's `--ff -x` runs previous failures first and stops at the
next failure. Use `--lf` in a repair loop and run the selected gate again at the
end. `make test` reports the 15 slowest cases. Default Ruff, mypy and pytest
caches stay inside each checkout. Override `RUFF_CACHE`, `MYPY_CACHE` or
`PYTEST_CACHE` to use a different location.
Use the same pinned Ruff in the editor and optional commit hook; its native
[language server](https://docs.astral.sh/ruff/editors/) reports issues while
editing. Keep strict mypy as the shared type-checking authority rather than
introducing a second incompatible checker configuration. For edited JavaScript,
`node --check path/to/file.js` catches syntax errors before a browser run.
These checks complement focused behavior tests; they do not prove runtime behavior.

#### Reproduce a performance finding

Use the included public-domain texts and synthetic chapters for analysis
profiling. Run this command on both source revisions with the same inputs
and iteration count.

```sh
PYTHONPATH=src .venv/bin/python scripts/benchmark_pipeline.py --iterations 3 --json
```

Compare the stage medians and result digests. This process reports a single
peak resident memory figure for the run in MiB on macOS and Linux. Other
platforms still report timings and digests. The JSON uses `null` when memory
usage is unavailable. For a research workflow, profile the actual request
with a synthetic archive and report the record count, page or result limit,
and median. Prefer operation counts or output equivalence for regression
assertions where timing varies by host.

#### CI and test environments

Pull requests targeting `main` run the `tests` workflow on Linux with Python
3.10 and 3.12, Poppler and FFmpeg. Each job runs the source checks and a wheel
smoke test. The development extra includes NumPy for audio fixtures and
independent numerical tests. The `dependencies` workflow also runs on pull
requests touching dependency inputs and on its weekly schedule.

Dispatch `tests`, `browser` or `research-platforms` manually for targeted CI
evidence. Match the run's commit to the change. For filesystem, process lifecycle,
packaging and other native-tool changes, verify Windows and macOS locally or
through `research-platforms`. That workflow defaults to the pytest `portability` marker
(`python -m pytest tests -m portability -W error -q -p no:asyncio`), covering
archive/filesystem, service observation, installed-package notices and read-only
export seams, plus real start/restart/stop, simultaneous starts and the Windows
PowerShell wrapper. Select `scope=full` only when the full research/lifecycle suite is
needed on both systems. The ordinary local full suite still runs every test;
markers do not remove coverage from `make check`.

The shared `scripts/check_release.py` builds
the source archive and wheel in a fresh temporary directory, compares both
packages' Python modules, typing marker and UI assets against source filenames
and bytes, and checks exact version metadata. Only after validation does it
replace managed `dist/` artifacts and write `SHA256SUMS`. Unrelated files or
directories in `dist/` cause an error and are preserved. The release workflow
uses the same checker.
The source archive also includes and verifies shared Python test fixtures.

Native PDF tests need Poppler (`pdftotext` and `pdftoppm`) and report an explicit
skip if it is missing. Select them locally with `pytest -m native_pdf`.
FFmpeg exercises speech tempo processing and verifies the published media in
the Python suite. The browser suite uses checked-in synthetic clips.
Synthetic worker and Tesseract protocol tests need no model or installed OCR engine.
For optional hooks, install `pre-commit` separately and run
`pre-commit install`. See [`.pre-commit-config.yaml`](.pre-commit-config.yaml).

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

For shared interactions, cover entry, visible state, action scope, dismissal
and return to the same task by pointer and keyboard. Keep the destination
visible and the return control reachable after scrolling. Preserve manuscript
text and selection, exact research anchors and unsaved input according to the
view's contract. Exercise pending, unavailable, stale and failed states, and
verify disappearance and recovery when backend freshness changes.

Follow the [annotation semantics](docs/ARCHITECTURE.md#annotation-semantics-and-visual-identity)
for research associations, measured comparisons, counted spans, search and
author tasks. Check overlap, Analysis Off, selection, forced colors and both
themes. Verify that units and counts remain meaningful when changing their
presentation. Apply these checks in the native and read-only review views.
Use the [geometry checks](AGENT_PROFILE.md#prevent-ui-clipping-and-layout-collisions)
for clipping, focus destinations and toolbar widths.

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

To prepare a new release, bump the version, scaffold pending release notes (explicitly
marking publication date and verification results as pending) and synchronize
documentation with the same generators used by GitHub Pages:

```bash
make release-prepare VERSION=X.Y.Z
```

Review and complete the draft in `docs/releases/vX.Y.Z.md` and follow the
[generation procedure](#updating-documentation-and-pages) for changed UI or
public guides. The preparation target keeps the changelog date pending and
compares against the last published version. When the release date is known,
run `make release-prepare VERSION=X.Y.Z RELEASE_DATE=YYYY-MM-DD` to record it in
the changelog and citation. Both invocations update local files and preserve
reviewed release notes. Commit, push, tag and publication each use their own
operation.

1. **Verify the local candidate.** Run `make release-check RELEASE_TAG=vX.Y.Z`,
   `make workflow-check` and, for changes affecting rendered output,
   `make browser-full`. The release check validates the proposed tag string
   against the source version and requires release notes before running the
   source checks, generated documentation check and dependency audit. It then
   promotes the verified archives and `SHA256SUMS` to `dist/` after an isolated
   wheel smoke test covering package identity, CLI diagnostics, all three
   reading-website formats and a document PDF. To recheck existing archives, use
   `.venv/bin/python scripts/check_release.py --tag vX.Y.Z --smoke`.
2. **Qualify the candidate and push a matching tag.** Review the commit and
   run `make github-check RELEASE_TAG=vX.Y.Z`. Inspect the clean-worktree and
   authentication fields, review the reported GitHub/PyPI state and resolve
   any pending release-note placeholders. If an ambient token or askpass
   override prevents Git or `gh` from using authorized keyring credentials,
   clear it for the affected command with
   `env -u GH_TOKEN -u GITHUB_TOKEN -u GIT_ASKPASS -u SSH_ASKPASS`.
   Push the reviewed commit to `main` before an optional `make rc-gate`
   (`rc.yml`). It qualifies the commit at remote `main` without publishing.
   Confirm the run's SHA before creating the annotated `vX.Y.Z` tag. Compare
   the reviewed SHA with `git rev-parse 'vX.Y.Z^{commit}'` before pushing the
   tag, then verify the dereferenced remote tag and the release run's SHA.
3. **Follow tag publication.**
   The tag workflow (`release.yml`) first requires reusable full source (`tests.yml`
   across Python 3.10 and 3.12, including isolated wheel build + smoke),
   4-shard Chromium browser (`browser.yml`) and full native
   (`research-platforms.yml` with `scope: full` on `windows-latest` and `macos-latest`)
   checks on the exact tagged commit, along with the dependency gate. These
   run concurrently in both release and RC workflows. Publication waits for
   all of them to pass.
   The Python 3.12 source job stages its smoke-tested archives and a CycloneDX
   SBOM from that same install. The RC workflow validates the handoff against
   its checked-out source. A new tag publication retrieves the staged archive
   set from its own run and checks the contents and checksums against the tag.
   It attests the archives and their SBOM, attaches the archives to a draft release,
   verifies the draft manifest, digests and provenance via `scripts/release_channels.py verify-draft`,
   publishes the immutable GitHub Release and confirms it with `verify-github`. On a rerun
   of an already published tag, `scripts/release_channels.py recover` retrieves and
   verifies the immutable GitHub assets instead of rebuilding.
   After GitHub publication and a successful or intentionally skipped PyPI
   step, the release pipeline deploys Pages from that exact tag.
4. **Verify each channel and perform any authorized local rollout.**
   Run `make release-verify RELEASE_TAG=vX.Y.Z` from the exact tagged checkout
   to check the GitHub Release and attestations, PyPI archive bytes, live Pages
   and the version-specific Zenodo status. Use
   `RELEASE_VERIFY_ARGS=--skip-pypi` if PyPI publication was intentionally disabled.
   Follow the
   [local rollout procedure](docs/INSTALLATION.md#refresh-a-checkout-or-a-packaged-service)
   for the checkout or installed environment that owns the selected port.

To verify a historical release after a newer Pages deployment, pass
`RELEASE_VERIFY_ARGS=--skip-pages`. Add `--skip-pypi` to the same quoted value
when neither channel applies. From the current maintainer checkout, set
`RELEASE_VERIFY_ROOT=/path/to/tagged-checkout` to use these checks for an older
checkout. Set `RELEASE_VERIFY_DIR` to a separate download directory for each
tag when verifying multiple releases.

Verify a downloaded artifact with:

```bash
gh attestation verify dist/lixity-X.Y.Z-py3-none-any.whl -R mfahsold/lixity
```

Repository-level immutable releases are enabled, so published assets and tags
remain fixed. Prepare and review release notes before tagging. Corrected code or
artifacts belong in a new patch release, preserving the earlier checksums and
provenance.

If a tag-triggered run fails, check the workflow, the remote tag target, the
GitHub release and PyPI publication status before deciding how to recover.
Prefer a new patch release when corrections are needed; do not silently move a
public tag. An exception for a visible tag that has not been published as a
release or package requires explicit authorization and a record of its previous
and corrected targets. Never replace an already published release or artifact.

Every tagged release is distributed and archived automatically:

- the workflow uploads wheel and sdist to PyPI when the repository variable
  `PUBLISH_PYPI` is `true` (trusted publishing, environment `pypi`); initial
  tag runs reuse the verified artifact set from `publish`, while reruns and
  manual PyPI catch-up dispatches (`workflow_dispatch` with `tag`) use
  `scripts/release_channels.py` (`inspect`, `recover`, `stage-pypi`,
  `verify-pypi`) from the workflow commit to recover the immutable GitHub Release
  assets, verify `SHA256SUMS`, GitHub digests, source equivalence and GitHub
  attestations, reconcile existing PyPI filenames and SHA-256 digests, and upload
  only missing identical distributions without rebuilding or using `--skip-existing`;
- Zenodo archives each new release once the repository is enabled there, so
  released versions receive a DOI without a local step.

Zenodo processing is asynchronous and outside the Actions result. Check the
specific release independently with
`.venv/bin/python scripts/release_channels.py verify-zenodo --repo mfahsold/lixity --tag vX.Y.Z`.
Confirm the DOI before reporting archival complete. Investigate a
missing record in Zenodo's GitHub integration release/error view rather than
republishing an immutable tag. When both metadata files exist,
`.zenodo.json` takes precedence over `CITATION.cff`; maintain their product
description and conceptual citation consistently. See
[Zenodo's metadata guidance](https://help.zenodo.org/docs/github/describe-software/).

The GitHub Pages environment must permit release tags (`v*`). Manual release
dispatches promote an already published release to PyPI only. See the
[Pages channels](#publish-and-verify-pages) for exact-source verification.

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

The published guide and blog Markdown alternates are generated from HTML.
Maintain section IDs and quoted examples in the HTML source. `make docs-sync`
regenerates the Markdown and preserves those anchors and quotations.

Maintain installation, CLI/API and contributor references in English. Preserve
localized guides, metric explanations and public entry pages. Describe language
coverage according to the available translations and validation.

Public home pages are generated from `docs/templates/*.template` and complete
`docs/locales/*.json` dictionaries. Keep the seven localized entry pages
equivalent, with a static URL, self canonical and reciprocal `hreflang` links.
The optional language suggestion offers an explicit link and keeps direct URLs
stable. Link to English technical references explicitly. Page-path measurement
distinguishes entry pages without collecting manuscript data.

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

For participating search engines, `docs/indexnow-key.txt` is a public IndexNow
ownership proof, not an account credential. Pages stages it at
`https://mfahsold.github.io/lixity/indexnow-key.txt`; use that exact `keyLocation`
with host `mfahsold.github.io` so submissions stay within `/lixity/`. After an
authorized deployment, verify the public key file and submit added, changed or
removed public URLs to `https://api.indexnow.org/indexnow`. Do not submit local
preview URLs or repeatedly notify unchanged pages. An accepted request confirms
receipt, not crawling, indexing or ranking. See the
[IndexNow protocol](https://www.indexnow.org/documentation). Bing Webmaster Tools
requires its own verified access for performance and indexing diagnostics;
Google Search Console credentials do not grant Bing access.

#### Generate and preview

1. Run `make screenshots` and then `make examples` when UI assets or published
   guides change. The examples use the captured image dimensions. Regenerate
   videos with `make videos` when the reviewed walkthrough changes. Review the
   captures. The docs tests compare the bundled UI assets with source bytes.
2. Run `make docs-sync` to sync version pins and regenerate the public home
   pages, Markdown alternates, `llms-full.txt` and localized metric references.
3. Run the [documentation and browser checks](#select-the-checks-for-your-change).
   Inspect desktop and mobile layouts, titles, links and reviewed media.
4. Stage a local preview with
   `python3 scripts/stage_pages.py --output /tmp/lixity-pages-preview`, using a
   new directory. The staging rules select published content and explicitly
   copy the shared design-token and component assets. Add new public paths
   deliberately. Link to root documents such as README and CONTRIBUTING by
   absolute GitHub URL. The documentation tests validate links in the staged tree.

Screenshot selection is maintained once in `docs/screenshots/manifest.json`.
Normal capture, the generated catalog and Pages staging use that inventory;
adding an image alone does not publish it. Prepare the reusable lead/support
asset handoff with `scripts/make_screenshots.py --outreach-package NEW_DIRECTORY`.
It records the source revision, working-tree status, exact image hashes, captions,
alt text and destinations without sending or scheduling posts. Keep one current
editorial package in the separate outreach workspace; old publication records
remain history rather than additional active campaigns. See the
[screenshot catalog](docs/screenshots/README.md).

Check labels, screenshots, capability limits and release versus current-main
claims together in README, the relevant Pages guide and the demo. The
visual-consistency browser check covers palette, contrast, focus and enlarged
text spacing. Describe the measured results within the
[documented scope](docs/ARCHITECTURE.md#visual-consistency-and-evidence).

#### Publish and verify Pages

Review the staged public paths for private data, local reports and planning.
A push to `main` leaves the site at its previously deployed commit. After the
reviewed commit reaches remote `main`, use `make pages-deploy` for an authorized
documentation rollout. The production workflow also accepts a verified release
ref from the tag pipeline. It verifies generated documentation before staging.
Wait for the run on the intended commit, then check `source_sha` and
`workflow_run_url` in the live [deployment record](https://mfahsold.github.io/lixity/deployment.json)
and open the affected public routes. Run `make pages-verify` from that deployed
checkout to compare its exact SHA and representative public files with live
Pages. The check works for deployments from `main` and from release tags.

#### Maintain the Wiki and historical references

Keep `docs/wiki/` as the source of the navigation pages linking to maintained
manuals. `python scripts/sync_wiki.py` previews the changes. Use
`python scripts/sync_wiki.py --publish` only for an authorized Wiki update.
The script publishes to the Wiki repository's default branch. Pages publication
and a push to the product repository leave the Wiki unchanged.

Before archiving a document, audit its inbound links and the generators,
workflows and release references that use it. Update active references to the
canonical owner. Retain published URLs as short signposts when readers still
use them, and preserve tagged snapshots and Git history. Keep private project
files, research archives and backups outside the documentation cleanup.
See the [historical records and proposals](docs/README.md#historical-records-and-proposals)
for archived material and its scope.

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

Use the [verified backup and restore procedure](docs/PROJECT_BACKUP.md) for
project copies and the [manifest storage migration](docs/research/USAGE.md#migrate-manifest-storage)
for legacy plaintext research manifests. For storage changes, cover staging
interruption, post-marker cleanup retry, stale snapshots and unchanged evidence
links. Validate the migrated store, restore its portable backup and check the
affected analysis, citation, import and publication workflows before resuming
services. Identify the backup scope for manuscripts, Zotero data and app profiles.
Keep the pre-migration backup until recovery and the affected workflows have
been verified. Implement and test migrations before describing them as available.
Project migration, release publication and restart each require their own scope.

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
7. Run the [checks for the affected surfaces](#select-the-checks-for-your-change).

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
