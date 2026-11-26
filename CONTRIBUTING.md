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
| Desktop host, runtime bundle and installers | `desktop/` | Commit host and packaging changes with the [app checks](desktop/README.md#local-build-and-verification) |
| Regression coverage and reusable tooling | `tests/`, `scripts/` | Commit when it protects or operates the product |
| Installation, usage, methods, interfaces and supported architecture | `docs/` | Keep the [technical manual index](docs/README.md) current and label proposals and unreleased behavior |
| OSS project entry and contributor procedures | `README.md`, `CONTRIBUTING.md` | Maintain the repository entry and link to the guides that own command details |
| Public site and examples | `docs/templates/`, `docs/locales/` and approved Pages paths | Edit canonical sources and follow [generation and preview](#generate-and-preview) |
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
| Shared UI behavior | Use `make browser` for the fast group or `make browser-changed` to select suites from modified paths. Run `make browser-full` on the final source before a release affecting rendered output. See [browser prerequisites and coverage](tests/browser/README.md). |
| Native desktop behavior | Follow the [desktop maintainer guide](desktop/README.md#rust-and-native-webview-checks) for locked Cargo tests, Clippy, bundled runtime checks and the macOS WebView smoke test. |
| Documentation | Follow [generation and preview](#generate-and-preview), then run `make docs-check` for a standalone docs pass. When also running `make check`, add `make docs-generated-check` to cover the generators without repeating the Python docs tests. |
| GitHub workflows | Run `make workflow-check` with `actionlint` installed. Override `ACTIONLINT` to use an explicit executable. |
| Packaging | Run `make build` or add an isolated install smoke test with `.venv/bin/python scripts/check_release.py --build --smoke`. |
| Public release | Follow [release preparation](#preparing-a-release) for the local and remote gates. |

Use both UI rows when a change crosses the desktop bridge. Browser tests
exercise the shared interface in Chromium. The native smoke exercises the
bridge and navigation through WKWebView on macOS. For changes to OS menus,
dialogs or input methods, use a synthetic project in the app on the affected
platform.

For a focused Python check, use
`make test PYTEST_ARGS='-n 0 tests/test_NAME.py'`.
Run Ruff as `.venv/bin/ruff check src tests scripts` and mypy as
`.venv/bin/mypy --strict src`.

After a failure, pytest's `--ff -x` runs previous failures first and stops at the
next failure. Use `--lf` in a repair loop and run the selected gate again at the
end. `make test` reports the 15 slowest cases. For pytest 9, the default
output shows failed subtests. To display passing subtests, include
`-o verbosity_subtests=1` in `PYTEST_ARGS`. Default Ruff, mypy and pytest
caches stay inside each checkout. Override `RUFF_CACHE`, `MYPY_CACHE` or
`PYTEST_CACHE` to use a different location.
`make clean-caches` removes the default checkout caches and coverage output.
Custom cache overrides have a separate lifecycle. `make clean` also removes
the checkout's `build/`, `dist/` and Python package metadata.
Use the same pinned Ruff in the editor and optional commit hook; its native
[language server](https://docs.astral.sh/ruff/editors/) reports issues while
editing. Keep strict mypy as the shared type-checking authority rather than
introducing a second incompatible checker configuration. For edited JavaScript,
`node --check path/to/file.js` catches syntax errors before a browser run.
These checks complement focused behavior tests; they do not prove runtime behavior.

Clean up disposable checkouts with `git worktree remove <path>` after checking
their status, including ignored build output. Preserve uncommitted changes and
release evidence before removing a checkout. Keep one reusable native build
cache when several temporary worktrees share it. For a direct check of the
installed desktop's bundled Python, use `-I -B` to protect the app signature
from new bytecode files.

#### Trace runtime warnings

Record the emitting command or browser action, runtime version, and first
relevant source frame. For an installed service, compare the installed and
running versions with `lixity doctor` and use the log for the affected port.
Keep captures with project context in ignored local storage.
[Service diagnostics](docs/INSTALLATION.md#logs)

| Where the warning appears | How to reproduce it |
| --- | --- |
| Python CLI or server | Add `-W default::DeprecationWarning -W default::FutureWarning` before `-m lixity` in the affected invocation. Repeat the focused test with `-W error`, then use `make check` on the supported interpreter. |
| Isolated package build | Run `PYTHONWARNINGS=error .venv/bin/python scripts/check_release.py --build --smoke` to include the build backend and the installed-wheel entry points. |
| Node tool | Prefix the affected command with `NODE_OPTIONS=--trace-deprecation`. Install editor build dependencies from their lockfile with `(cd scripts/editor && npm ci)`, then check the bundle with `npm run --prefix scripts/editor check`. |
| Browser | Use the repository's Playwright pin and repeat the actual interaction. Capture console warnings and page errors, plus the affected browser and viewport. `scripts/run_browser_suites.py --only SUITE --diagnostics DIR` retains bounded synthetic evidence. |
| GitHub Actions | Match the job to the exact commit and action pin. Trace a bundled dependency warning to the action release and check the upstream fix before changing a pin. Use `make workflow-check` for YAML validation. |

Keep intentional API deprecations covered by their compatibility tests and
move maintained callers to the successor API. Treat rejected inputs,
interrupted transfers and unhandled failures according to their diagnostic
meaning. Verify that a quieter normal path still exposes the operational
failure a maintainer needs to investigate. For a warning in an upstream action,
record its owner and tracking link until a qualified replacement is available.

The pinned Pages deployment action can emit Node `DEP0040` from its bundled
dependencies during a successful deployment. Check the job conclusion and
the deployed source SHA. [Upstream tracking issue](https://github.com/actions/deploy-pages/issues/434)

Portable review HTML opened from `file://` can emit the `ScriptProcessorNode`
deprecation during its local recording workflow. Native browser recording
loads the packaged `AudioWorklet` from the loopback service. Exercise both
entry points for recording changes. [Browser coverage](tests/browser/README.md)

#### Reproduce a performance finding

Use the included public-domain texts and synthetic chapters for analysis
profiling. Run this command on both source revisions with the same inputs
and iteration count.

```sh
PYTHONPATH=src .venv/bin/python scripts/benchmark_pipeline.py --iterations 3 --json
```

Compare stage medians and result digests. The command reports peak resident
memory for the run in MiB on macOS and Linux. The JSON uses `null` when memory
usage is unavailable. For workload design, archive benchmarks and regression
assertions, follow [Investigating performance](#investigating-performance).

#### CI and test environments

Pull requests targeting `main` run the `tests` workflow on Linux with Python
3.10 and 3.12, Poppler and FFmpeg. Both interpreter jobs run the full suite
through `make test` and smoke-install the wheel. The Python 3.12 job also runs
the shared Ruff and mypy checks configured for the supported Python 3.10 target.
The development extra includes NumPy for audio fixtures and
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
same machine without other test workers. For an archive request, record the
record count and the page or result limit. Fixture construction, profiling and
memory instrumentation belong outside timed runs. Check both tiny records and
large payloads, including image and PDF memory. Measure the complete workflow
again after optimizing an inner loop.

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

Use Python 3.10 or newer for release tooling. In a fresh worktree, run
`make install-dev` with a supported `PYTHON`, or select an existing environment
with `VENV=/path/to/environment` when running the release commands.

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
reviewed release notes. The software paper cites the exact archive and sample
tag used for its case study. That evidence is maintained with the paper.
Commit, push, tag and publication each use their own operation.

1. **Verify the local candidate.** Run `make release-check RELEASE_TAG=vX.Y.Z`,
   `make workflow-check` and, for changes affecting rendered output,
   `make browser-full`. The release check validates the proposed tag string
   against the source version and requires release notes before running the
   source checks, generated documentation check and dependency audit. It then
   promotes the verified archives and `SHA256SUMS` to `dist/` after an isolated
   wheel smoke test covering package identity, CLI diagnostics, all three
   reading-website formats and a document PDF. When keeping earlier artifacts,
   set `RELEASE_DIST=.artifacts/release-X.Y.Z/dist` to build in a dedicated
   output directory. To recheck existing archives, use
   `.venv/bin/python scripts/check_release.py --tag vX.Y.Z --smoke` with
   `--dist` when they are outside the default directory.
2. **Qualify the candidate and push a matching tag.** Review the commit and
   run `make github-check RELEASE_TAG=vX.Y.Z`. Inspect the clean-worktree and
   authentication fields, review the reported GitHub/PyPI state and resolve
   any pending release-note placeholders. If an ambient token or askpass
   override prevents Git or `gh` from using authorized keyring credentials,
   clear it for the affected command with
   `env -u GH_TOKEN -u GITHUB_TOKEN -u GIT_ASKPASS -u SSH_ASKPASS`.
   Push the reviewed commit to `main`, then run the candidate workflow and
   verify its result from the reviewed checkout:

   ```bash
   make rc-gate RELEASE_TAG=vX.Y.Z
   # Wait for the dispatched run to finish on GitHub Actions.
   make rc-verify RELEASE_TAG=vX.Y.Z
   ```

   `rc-gate` sends the full local commit SHA to GitHub. The workflow stops at
   preflight if the dispatch resolves to a different commit. `rc-verify` reports
   the successful run, retained artifact ID and SHA-256 digest for that commit.
   If a check fails, diagnose it before creating the annotated `vX.Y.Z` tag.
   Qualify each corrected commit again. If the build artifact is missing or has
   expired, rerun the original workflow in full or dispatch qualification again
   while the reviewed commit is at the tip of `main`. Compare the reviewed SHA
   with `git rev-parse 'vX.Y.Z^{commit}'` before pushing the tag, then verify the
   dereferenced remote tag and the release run's SHA.
3. **Follow tag publication.**
   The candidate workflow (`rc.yml`) checks the release notes, then runs the
   reusable full source checks (`tests.yml`
   across Python 3.10 and 3.12, including isolated wheel build + smoke),
   four Chromium shards (`browser.yml`), full native tests
   (`research-platforms.yml` on `windows-latest` and `macos-latest`) and the
   dependency gate concurrently.
   The Python 3.12 source job stages its smoke-tested archives and a CycloneDX
   SBOM from that same install. After every gate passes, the candidate workflow
   verifies the handoff against its checkout and attests the archives on `main`.
   The tag workflow (`release.yml`) checks release notes, tag identity, the
   candidate run and any selected signed desktop bundle. It downloads the
   candidate by run and artifact ID and repeats the same checks for source
   contents, checksums, and the SBOM's source commit and archive hashes. It
   then verifies the hosted build attestations and reuses the exact archives
   for the release. It adds tag-bound
   attestations for the archives and their SBOM, attaches the archives to a draft,
   verifies the draft manifest, digests and provenance with `verify-draft`,
   publishes the immutable GitHub Release and confirms it with `verify-github`.
   For an already published tag, `scripts/release_channels.py recover` retrieves
   and verifies the immutable GitHub assets independently of candidate retention.
   After GitHub publication and a successful or intentionally skipped PyPI
   step, the release pipeline considers Pages from that exact tag. The
   serialized Pages job checks whether the tag is still the latest published
   release and whether its commit can advance the live deployment. A rerun
   skips deployment when the live site already includes newer or diverged work.
   Set the repository variable `PAGES_DEFERRED_RELEASE_TAG` to the exact tag
   before pushing it when the website must stay at its measured revision.
   The matching tag still publishes to GitHub and PyPI. Verify those channels
   with `RELEASE_VERIFY_ARGS=--skip-pages`, then use the separately reviewed
   Pages deployment when the measurement window closes. Remove the variable
   after that deployment has been verified.
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

The tag workflow always verifies the Python package. To include desktop
installers for an upcoming tag, qualify a single desktop workflow run from
the exact release commit on `main`. Set `DESKTOP_RELEASE_TAG`,
`DESKTOP_RELEASE_RUN_ID` and `DESKTOP_RELEASE_QUALIFICATION` before pushing
the tag. The first variable selects the tag, the second identifies the
completed run, and the third contains its reviewed qualification JSON.
The signed run produces `lixity-desktop-release-bundle`. Unsigned runs produce
`lixity-desktop-test-bundle`. The preflight checks the completed signed run and
its exact source SHA. The workflow verifies the hosted desktop build attestations and
uploads the qualified files to the same draft as the Python package. It
verifies the draft and the immutable release against those bytes. PyPI receives
the wheel and sdist from the separate Python directory. Already published tags
recover their immutable files even after the desktop handoff configuration changes
or the original build artifact expires.
[Desktop qualification and catalog procedure](desktop/README.md#public-desktop-downloads)

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
The check matches the requested version and repository in the public record,
including records whose citation metadata links to the repository root.
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
Only the two production website bases, `https://mfahsold.github.io/lixity/` and
`https://lixity.de/`, are eligible. Respect browser Do Not Track / Global Privacy
Control. Send only the visited public pathname, public title,
origin-only referrer and fixed CTA names; exclude URL query/hash, form inputs,
selection, manuscript/research data, local paths and persistent identifiers.
The local app and generated user exports must never acquire this adapter.

CTA counts measure link activation. Pageviews include direct visits. Playback
completion and installation require separate evidence. Find event names and
destination rules in the [public adapter](docs/assets/analytics.js). Check
existing Search Console and GoatCounter read access before adding tools.

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
4. Serve the staged preview under the production path prefix `/lixity/` on a
   loopback-only address. Open `http://127.0.0.1:8000/lixity/` while the server
   is running. The staging rules select published content and copy the shared
   design-token and component assets. Add public paths deliberately and use
   absolute GitHub URLs for repository-root documents. The documentation tests
   validate links in the staged tree.

   ```sh
   pages_preview_dir="$(mktemp -d "${TMPDIR:-/tmp}/lixity-pages.XXXXXX")"
   python3 scripts/stage_pages.py --output "$pages_preview_dir/lixity" &&
     python3 -m http.server 8000 --bind 127.0.0.1 --directory "$pages_preview_dir"
   ```

Screenshot selection is maintained once in `docs/screenshots/manifest.json`.
Normal capture, the generated catalog and Pages staging use that inventory;
adding an image alone does not publish it. Prepare the reusable lead/support
asset handoff with `scripts/make_screenshots.py --outreach-package NEW_DIRECTORY`.
It records the source revision, working-tree status, exact media hashes, captions,
text alternatives and destinations without sending or scheduling posts. Keep one current
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
checkout to compare the exact SHA and public files with live Pages. The byte
comparison covers the localized home pages and guides, crawl files, measurement
assets, shared styles, demo, sandbox and reviewed video files. The check works
for deployments from `main` and from release tags.

#### Move Pages to the verified custom domain

The Pages workflow uses the base URL reported by GitHub. The staging script
supports the existing project address and the custom domain at its root.
Preview the custom-domain output in a fresh directory before switching DNS.

```sh
pages_preview_dir="$(mktemp -d "${TMPDIR:-/tmp}/lixity-domain.XXXXXX")"
python3 scripts/stage_pages.py --base-url https://lixity.de/ --output "$pages_preview_dir/site"
```

Verify domain ownership in the repository owner's account settings. During the
coordinated switch, save `lixity.de` as the project's Pages custom domain, then
replace the apex web records at the DNS provider and point `www` to
`mfahsold.github.io`. Keep the ownership TXT and existing mail records. Recheck
DNS, wait for the Pages certificate and enable HTTPS before announcing the new
address. Follow the [GitHub custom-domain procedure](https://docs.github.com/en/pages/configuring-a-custom-domain-for-your-github-pages-site/managing-a-custom-domain-for-your-github-pages-site).

Deploy from the intended commit and run
`make pages-verify PAGES_BASE_URL=https://lixity.de/`. Try legacy deep links,
the `www` redirect, the feed and the desktop download catalog. Existing desktop
test builds that reject redirects need a new installer for in-app update checks.
Verify the new property in Search Console, submit its sitemap and record the
switch time in the measurement history.

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
7. When a change crosses Python, Rust or JavaScript, name the owner of the
   decision in the review description. Point to the existing call sites that
   consume its result and to the checks for the payload they receive. A port
   needs parity evidence and a plan for removing the superseded path.
   [Analysis ownership](docs/ARCHITECTURE.md#analysis-ownership-across-python-rust-and-javascript)
8. Run the [checks for the affected surfaces](#select-the-checks-for-your-change).

## Reporting bugs

For a [bug report](https://github.com/mfahsold/lixity/issues/new/choose), include
the operating system, install method, expected result and exact steps. Attach
a minimal synthetic example when the issue depends on a project. Identify the
surface and version that actually showed the problem.

| Where it happened | Include |
| --- | --- |
| CLI | `lixity --version`, Python version and the command with private paths replaced |
| Local browser app | Browser and version, running Lixity version and URL path without project IDs or query data. Check the running version with `lixity doctor`. [Service diagnostics](docs/INSTALLATION.md#logs) |
| Desktop app | Version from **About Lixity**, installer or test-build identity and relevant lines from the desktop log. [Desktop logs](docs/INSTALLATION.md#find-the-desktop-logs) |
| Public website, demo or sandbox | Public URL, browser and version, and the deployment source when available. [Deployment record](https://mfahsold.github.io/lixity/deployment.json) |

Review logs, diagnostics and screenshots for manuscript excerpts, account
details, local paths and secrets before sharing. Report security issues
privately. [Security policy](SECURITY.md)

## Support and governance

Lixity is maintained by its author, Matthias Fahsold. Bug reports and feature
requests run through GitHub issues; security reports follow
[`SECURITY.md`](SECURITY.md). Releases are tagged, recorded in the changelog and
distributed through PyPI, GitHub Releases and Zenodo. There is no foundation or
steering committee: changes arrive through pull requests under the repository
license, and public discussion happens in issues. The maintainer aims to respond
to reports within a couple of weeks; there is no paid support.
