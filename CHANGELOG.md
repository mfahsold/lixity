# Changelog

All notable changes to Lixity are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Update the vendored CodeMirror editor dependency `@codemirror/view` from
  `6.44.0` to `6.44.1` (rebuilding `codemirror-editor.js` and its license
  inventory) and apply semver-compatible patch updates in `desktop/Cargo.lock`
  (`sha2` `0.11.2`, `zerocopy` / `zerocopy-derive` `0.8.66`).
- Link home pages directly to desktop downloads and offer a one-click browser
  exercise on every localized home page. Explain the GitHub sign-in
  requirement beside test archives and document a terminal-only setup.
- Give CLI users next steps for a folder passed as a manuscript or multiple
  manuscripts passed to `characters`. Localize the remaining German dialogue
  report labels, show a project example in top-level help, and explain where
  to start reading a style comparison and why a short input can lack one.

- Tighten the narrow-viewport workspace entry so the first manuscript paragraph
  sits higher on 320 px screens: fold the project support link inline into the
  compact metadata row below 1100 px while keeping the sidebar button on wide
  desktops and the footer licensing link everywhere.
- Reduce first-click installation friction before signed desktop installers are
  published: keep the published login-free local browser app instructions open
  on the installation guide, add an opt-in `publish_preview_release` workflow
  input on `desktop-release.yml` to publish unsigned/ad-hoc desktop preview
  installers as a public GitHub prerelease without a GitHub account or 30-day
  expiry, and support `preview_release_tag` in `docs/desktop-test-build.json`.
- Use `https://lixity.de/` in the application, package metadata, funding and
  citation links. The earlier GitHub Pages address redirects to the same path
  on the new domain. The Pages build rewrites site links for the selected base.
- Keep the local ZONOS3 speech worker warm between segments and release it
  after 300 seconds of inactivity, instead of reloading the model per segment.
  New voice profiles prefer ZONOS3 when it is ready. The default preset voice
  is always sent to the worker; reference cloning continues to use the saved
  reference audio.
- Remove the obsolete single-book export, sync, audit, prune and gdrive
  controls from unconfigured workspaces. Hosts that explicitly provide these
  capabilities can still render their controls. The standalone server keeps
  answering these actions with HTTP 501.

- Lead the product site and setup guides with platform downloads. Check the
  desktop installer locally in the browser and keep terminal setup available
  as a fallback.
- Show plain-language computer names and package formats on the download page.
  Use the Lixity mark on the download page, in the workspace and in the offline
  Mac setup guide. Use platform and chip names on new hosted archives and
  versioned local Mac disk images.
- Find the installed Lixity executable through uv when creating a Linux menu
  entry outside the tool's executable search path.
- Give Mara a decision about what she signs in the Warehouse 4 demo. Add a
  dispatch receipt, an office ledger, a captioned witness statement and two
  authored journeys. The reader plays two chapter recordings and reveals
  selected research as readers progress.
- Introduce the workspace and its writing, analysis and research tools on all
  seven product pages. Group the Warehouse 4 editorial examples below the
  product overview and simplify the German first-look guide. Link the analysis
  feature directly to a chapter comparison with counted sentences.
- Store each prepared research response once in a static review export while
  preserving its exact token-bound routes.
- Keep map numbers from blocking nearby features at narrow widths. Keep every
  feature selectable in the list when the map has room for fewer numbers.
- Keep the writing toolbar visible during pauses and scrolling. Open editing
  and formatting actions from the text or the toolbar, with keyboard access
  and selection restoration.
- Explain the first funding priorities in a dedicated section on all seven
  product homepages. Keep the support link in the app welcome screen and project
  navigation. The support page shows the funding status and company contact.
- Prepare GitHub Pages staging and verification for `lixity.de`, including the
  site links, sitemap and feed. Let new desktop builds follow the exact
  download catalog redirect during the domain change.

### Fixed

- Exclude reserved private directories and credential files from local Pages
  staging, including inside approved public subtrees.
- Keep the home navigation, language picker and blog index within the page at
  narrow widths and enlarged text sizes. Let homepage titles wrap naturally.
- Keep delayed editor requests from taking over a newer workspace or focus
  choice. Preserve the cursor across an unchanged return to Write and complete
  pending saves before leaving. Include draft edits in the comparison dialog
  in the desktop close guard.
- Keep unsaved voice profile edits open when applying a reviewed audio settings
  upgrade. Bind the upgrade review to the manuscript open in the app.
- Show the selected speech worker's availability and setup link beside the
  rendering controls.

## [0.9.3] - 2026-11-25

### Added

- Add an optional Linux WebKitGTK check for first launch and an exact offline
  sample import, and a native macOS benchmark for counted evidence and its return.
- Add optional local SoundCraft trimming in Author's Voice. Keep the original
  take available for review and require confirmation of the excerpt transcript.
- Correlate audio requests, jobs and worker events with a server-generated
  diagnostic ID. Preserve typed fields and include redacted response records in
  browser test diagnostics.

### Changed

- Qualify the exact release commit with the hosted source, browser, native and
  dependency checks before tagging. Promote the attested candidate packages by
  run and artifact ID. Verify published releases independently of build retention.
- Check Chromium and the accessibility tools before running browser suites.
  Bound setup and test time, report each step's outcome and rebalance the four
  shards using v0.9.2 timings.
- Verify the candidate SBOM's source commit, version and package digests through
  the same validation before qualification and publication.
- Retry a failed installer upload once on the runner with the verified files.
- Keep the book's voice defaults in project settings. Edit direction and run
  chapter audio work beside the manuscript. Reset render overrides on reopening,
  and give plan export and recording comparison independent text scopes.
- Allow up to 60 seconds for author-voice takes and saved references. Show the
  available recording time and support manual stop. Save a per-project capture
  limit for desktop, browser and timed CLI recording. Share the accepted
  reference duration across storage, worker transport and SoundCraft.
- Explain what writing, comparing, saving and exporting will change in the
  workspace. Clarify analysis, recording and project help in all seven locales.
- Group voice models by the way they produce a voice. Show fixed profile,
  language and voice values directly. Keep the recording limit with Author's
  voice and place worker diagnostics in a disclosure within Voice profiles.
- Add explicit discard for audio takes and pending chapter file selections.
  Allow deletion of the reviewed chapter recording and staged removal of the
  last voice profile in current audio settings.
- Allow deletion of unused saved voice references. Add draft discard and
  reviewed withdrawal to the dossier editor while retaining archive history.
- Read only the selected manuscript measurements during revision comparison.
  Keep routine recovery reads read-only and preserve existing project journals.
- Verify research search results against the matching archive snapshot, then
  release the index connection before preparing citations and previews.
- Update supported dependency floors, browser tooling, CodeMirror and the native
  WebView binding. Reuse the desktop loopback client and bound its control replies.
- Capture revision comparison inputs before remeasurement so readers and saves
  can proceed during the comparison. Bound retained recovery content before
  loading it from SQLite.
- Reuse neighboring paragraph tokens in scene cohesion windows and validated
  record bytes while preparing research manifests.
- Build and verify the desktop wheel and bundled interpreter in one CI action
  using pinned uv and Python. Update the Rust advisory scanner and verify that
  bundled interpreter paths resolve inside the runtime.

### Fixed

- Reject PyTorch versions affected by CVE-2025-32434 before IMS-Toucan loads
  checkpoints. Withdraw the corresponding optional worker setup recipe.
- Order initial recovery schema setup across manuscripts in the same project.
  Reject newer recovery schemas and redirected database or journal files.
- Declare the ALSA runtime required by the Linux DEB. Verify the installed Rust
  host and bundled Python session on clean Ubuntu before uploading installers.
- Keep delayed version and draft requests within the current writing session.
  Explain recovery choices with unsaved changes and confirm before replacing
  different unsaved text from a comparison.
- Align the installation guide with the published package and desktop test builds.
- List native desktop microphones for Author's Voice and level checks. Show a
  single input by name, label the system default, and refresh connected devices.
- Explain microphone check results and show pending, confirmed and rejected
  gain changes beside the control using a read-back from the selected mixer.
- Keep Linux capture tied to the chosen input, offer gain only for a verified
  mixer, and report digital silence consistently in native and CLI checks.
- Keep the Markdown link shortcut in the editor. Show the available focus,
  search and palette shortcuts in their controls and use platform key labels.
- Move the native manuscript import shortcut to `Cmd/Ctrl+Shift+I` so the
  writing editor receives its italics shortcut.
- Keep short Qwen Base auditions usable with a saved voice reference. Show
  existing teleprompter shortcuts on their controls.
- Edit passage direction beside the manuscript or directly below its paragraph
  on a narrow screen. Open the same editor from the paragraph action menu.

## [0.9.2] - 2026-11-24

### Added

- Compare quoted-word share and mean sentence length in manuscript order.
  Scene details show counted quote-block lengths and text measurements for
  both halves with separate evidence labels.
- Try a different story sequence with author-written scene intent cards.
  The local rehearsal saves only on request and marks cards for review
  after edits to the inspected text.

- Add authenticated desktop-host loopback mode (`--_desktop-mode`, ephemeral
  `port=0`, stdin bootstrap secret, single-use `/_desktop/handshake` cookie
  exchange, host-only `/_desktop/nonce`, parent-process watchdog and
  `/api/desktop/environment` diagnostics) alongside progressive
  `window.lixityDesktop` hooks in the browser UI.
- Add the cross-platform Rust/Tauri v2 desktop host workspace (`desktop/`) with
  isolated `python-build-standalone` 3.12 runtime bundling, stripped-environment
  smoke verification, instant frameless cold-start splash window, port-independent
  display preferences (theme and zoom), 7-language native OS menus with View zoom
  and dynamic recent projects synchronized with the Welcome Hub, external link
  interception, saved-export Reveal toasts, drag-and-drop opening, window geometry
  persistence, Linux Wayland+NVIDIA WebKitGTK DMABUF guard, interactive and timed
  `cpal`+`hound` cross-platform audio capture/calibration, native installer
  packaging (signed-before-DMG macOS `.app`/`.dmg`/Homebrew, Windows NSIS/WiX/WinGet,
  Linux `.deb`/`.rpm`/`.AppImage`/Flatpak/AppStream), top-level artifact container
  verification, and three-OS CI and release workflows.
- Record teleprompter takes through the Rust microphone in the desktop app.
  The interface shows the native 30-second recording limit. The desktop host
  binds active recordings to the window that started them.
- Add a local macOS app build and verification command and a synthetic smoke
  test for Rust IPC and external links in the system WebView.
- Verify the bundled runtime inside the read-only mounted macOS disk image in
  local development builds and both desktop installer workflows.
- Include an English offline installation guide in the macOS disk image.
  Label ad hoc images as test builds and write a companion checksum file for
  locally built DMGs.
- Add English offline setup guides beside the verified Windows and Linux test
  installers in GitHub Actions artifacts.
- Offer an offline manuscript example on the desktop welcome screen. Preview
  the bundled text before creating an editable local project.
- Document the desktop download, installation and first-launch steps together.
  Generate public download links from verified GitHub Release assets.
- Lead with desktop installation across the website and documentation. While
  the public installer catalog is empty, label test builds and link to the
  published browser app and CLI. Require installer filenames to match the
  verified release version.
- Add opt-in Developer ID notarization on macOS and Azure Artifact Signing on Windows. Gate desktop
  publication on exact installer bytes, hosted build attestations and a
  per-installer qualification receipt. Verify the combined GitHub draft while
  keeping PyPI's distribution set independent.
- Report missing GitHub signing settings by name before starting a desktop
  release build. Report unavailable configuration listings as unknown.
- Explain how to update the desktop and CLI installations through their
  original installation channels.
- Support verified local replacement of an installed macOS test build from
  a clean checkout, with a retained rollback copy.

### Fixed

- Check release notes and signed desktop build identity before the full CI
  matrix. Verify all seven installer variants, including both Windows MSI
  languages, before qualification or catalog updates. Generate the catalog from
  the attested immutable release and stage PyPI uploads atomically.
- Verify the version-specific Zenodo DOI when the record links to the GitHub
  repository root.
- Skip automatic Pages deployments when a release rerun would replace a newer
  site or a deployment from a different source history.
- Keep subprocess tests on the selected checkout when they change their
  working directory to a temporary project.
- Keep help within the width of narrow dialogs with classic scrollbars. Allow
  its readable vertical placement beside short dialogs.

- Use one native recent-project list for the desktop welcome window and system
  menu. Keep each menu action bound to the displayed project.
- Open counted text matches directly from the reader and chapter comparison
  gaps. Keep the result count and navigation in the current reading scope.
- Preserve unknown paragraph values in CLI output for unsupported language
  profiles and explain why comparable paragraphs are missing.
- Explain why a chapter lacks paragraph comparisons while keeping measured
  values and passage navigation available. Keep the deviation arrows scoped
  to reachable paragraphs across the manuscript.
- In the manuscript, keep the current measurement and passage review at hand.
  Put marking and filter choices in one disclosure. Keep empty-search feedback
  and Clear reachable at large text sizes.
- Load the writing session's revision measurements on request from **Versions**.
  Opening the editor or autosaving with that panel closed makes no report request.
- Keep the draft during an author-intent conflict and display the currently saved
  order when a second window changes it. Inspect a newly selected scene without
  losing the card draft.
- Skip geography discovery in map-free reading views, including during scroll
  and unrelated DOM changes. Release map resources on removal.
- Resolve an explicit `auto` against the direct analyzer's input when no sample
  was provided. Reject a nonfinite comparison scale and avoid overflow in the
  medcouple skewness kernel. Withhold Flesch Reading Ease when no syllables can
  be estimated for the analyzed tokens (such as non-Latin scripts under `generic`)
  while keeping LIX available.
- Reuse unchanged chapter projections during manuscript editor saves and read
  tombstone lifecycle indexes directly during research catalogue searches.
- Explain the exploratory selection limits in the comparison report and name
  the separate BH setting used by trend and manuscript-half summaries. Correct
  the documented guarded segment objective and the two sentence-length bin roles.
- Align the v0.9.1 release labels for standardized-midrank Mahalanobis distances
  across `AGENTS.md`, `METHODS.md`, and `STABILITY.md`, clarify editorial preset
  calibration wording in `USAGE.md`, and document `voice_separation` cutoffs,
  `showing` group weights, `first_person_start_rate` denominators, `--preset`
  threshold injection, and `GENRE_CORRIDORS` bounds.
- Exclude retracted manuscript claim links (`state: "retracted"`) from anchored
  claims in `research_gaps()` (`research-gaps-local/1`) so claims with no
  remaining active link are reported under `unanchored_claims`.
- Report `features.asl` and plateau `mean_asl` as `null` (`"unavailable"` in
  target comparisons and `—` in UI/CLI) for word-bearing scene units with zero
  counted sentences in `scene_report()`, without changing the `analyze` schema-2
  numeric sentinels on `CorpusMetrics` or `ChapterMetrics`.
- Suppress non-comparable cross-language lexical overlap, Dunning $G^2$ keyness,
  register delta, and chapter grounding density numbers in
  `compare_source_to_manuscript()` (`null` / `[]`, rendered as `–` in Markdown).
- Stabilize direct statistical calculations at extreme scales. Retain small
  Jeffreys tails and valid scaled ratios, and reject invalid structural samples.
  Verify robust estimates, rhythm, rank trends and lexical diversity against
  independent exact and high-precision reference calculations.
- Retry normal eject of the verified macOS disk image when a system process
  briefly holds it open.

### Changed

- Bump cross-corpus source–manuscript comparison payloads to
  `schema_version: "research-comparison-local/2"`: cross-language comparisons
  preserve per-side token/vocabulary counts and per-side register values while
  returning `null` / `[]` for cross-corpus similarity, shared/exclusive terms,
  keyness lists, register deltas, and chapter grounding densities. Historical
  `research-comparison-local/1` payloads remain valid in saved artifacts; re-run
  comparisons to obtain `/2` outputs.

- Keep analysis controls visible when scrolling or pausing in the manuscript
  and analysis overview.
- Show quoted text directly in the reader with a word count on inspection.
  Keep the share in chapter and manuscript reports.
- Describe the OSS architecture and contributor workflows in the repository
  README. Show the author workflow, the interactive sandbox and the read-only
  example distinctly on the localized product pages.
- Use one close-control and status-banner treatment for shared workspace
  panels. Announce only changed status messages.
- Package reviewed screenshots and both short share clips together. Distinguish
  sandbox and clip links in the public site's aggregate action counts.
- Link each product page to a worked analysis example and its localized metric
  reference. Verify the deployed crawl files, measurement assets, demo and
  reviewed media against the staged site.
- Synchronize tab selection and panel accessibility in source comparison and
  style analysis. Share keyboard navigation across research and Audio Studio.
- Put the next action and its reason together in analysis help, the overview,
  passage evidence and dossier suggestions. Use shared guidance styling,
  localized action labels and keyboard focus return.
- Give the manuscript a single analysis-overview entry and distinct actions for
  counted passages, differing paragraphs and tense findings in all seven languages.
  Use the same reachable passages for the deviation count and arrow buttons.
  Offer to clear empty filters while keeping the measurement selected.
- Keep explanations and main actions visible in passage cards and measurement
  dialogs on narrow screens. Restore the reading position and focus after an
  analysis visit. Save reader preferences across desktop port changes and keep
  saved story rehearsal cards accessible when scene measurements are unavailable.
- Exclude capitalized German nominal uses after selected article contractions
  such as “beim Lesen” from default present-tense cues.
- Use the engine's quoted-word counts, sticky-sentence selection and echo groups
  in the reader. Forward the native project selector unchanged to the shared
  workspace resolver.
- Skip repeated toolbar, analysis highlight and dossier outline updates during
  steady scrolling. Fit the manuscript companion on viewport scroll and avoid
  refreshing dossier maps on pages without maps.
- Refine shared links, action and field boundaries, surface elevation, table
  headings and dialog contrast in both themes.
- Save and delete dossier collections through the shared research form before
  locking the other controls during the request.
- Route desktop diagnostics and exports through one authenticated Rust transport.
  Keep the OS-selected filename in the native save result and show the folder
  action in the same dialog that started the export.
- Guide the first workspace in all seven interface languages with distinct
  actions for opening a project folder, importing a file and starting a draft.
  Show the desktop project destination before saving and remember newly created
  projects. Use a folder under `~/Lixity` for automatic desktop destinations,
  independent of the directory from which the desktop app was launched.
- Keep the desktop window responsive while checking audio jobs before the last
  workspace closes. Preserve the confirmation for unsaved work and explain
  when the engine's audio status is unavailable.
- Save desktop settings, recent projects and window geometry through shared
  atomic persistence and serialize concurrent updates from workspace windows.
- Use the supported `diskutil image` commands for macOS disk image packaging
  when directory input is available.
- Bound Rust desktop startup and clean up the engine process when its readiness
  check fails. On Linux, tie the engine lifetime to the host process, so the
  engine can keep serving after the startup thread exits.
- Explain desktop startup failures in all seven interface languages and offer
  to open the log folder. Use verified installer manifests to generate Homebrew,
  WinGet and checksum files from the bundled assets.
- Connect the macOS title bar to the workspace theme, show the active project in
  the native window title, and provide native window, fullscreen and Help menus.
- Align shared toolbar buttons, give touch icon actions larger hit targets and
  keep button geometry and keyboard focus stable while an action runs.
- Offer a desktop update only for a newer published version. Show the installed
  version and desktop availability using the verified installer catalog. Explain
  missing platform builds and connectivity failures in the interface language.
- Reject incomplete or duplicate installer metadata before showing a desktop
  update.
- Show the source commit in System Status for local macOS update builds.
- Reuse quotation counts for matching paragraph evidence and chapters that
  form one scene.
- Open external links from the desktop window through the Rust host and grant
  the loopback workspace explicit access to the registered native commands.
- Link to the full AGPL text and readable commercial licensing instructions.
  Apply the same self-publishing guidance in all seven interface languages.
- Route links that open a new tab through the desktop host's URL policy so
  both license links reach the system browser.
- Process native microphone input in one path across host-supported PCM
  formats and avoid copying each input block or the finished take.
- Open the analysis overview at measured manuscript values, with a direct
  route back to the analysis sections from tables and charts. Keep the toolbar
  compact on narrow screens and explain unavailable style comparisons.
- Pause the 3D style plot while hidden and redraw it at the correct size when
  its analysis section is shown again.
- Retain native desktop requests to open manuscripts and projects while the
  local engine starts or the workspace changes.
- Stream desktop manuscript PDFs, saved dossier PDFs and website ZIPs into
  the selected file and report completion after the transfer succeeds.
- Keep manuscript measurements reachable in the analysis overview on narrow
  screens and reveal a flagged passage's review list before moving focus.
- Use the same analysis overview from the reader, command palette and desktop
  menu. Apply desktop zoom in the native webview and restore the saved theme
  across local desktop sessions.
- Keep signed desktop runtime resources intact after startup and use the same
  locked Rust dependencies for the host checks and installer builds.
- Open the configured manuscript when selecting a project's `lixity.toml`.
- Keep the dossier section list reachable when the reading pane resizes during
  a smooth return from the end of a document.
- Keep ordinary buffered-response cancellations in debug logging and preserve
  warnings for interrupted server errors, streamed transfers and website ZIPs.
- Use one AudioWorklet for native microphone and teleprompter recording while
  retaining local WAV capture in portable review copies.
- Detect floating-point WAV files consistently when auditing or normalizing
  audio on Python 3.15 and earlier supported interpreters.
- Install browser CI dependencies in an isolated Python environment and
  extract release artifacts after the download action verifies their checksums.

## [0.9.1] - 2026-11-23

The first published release with the changes listed under 0.9.0.

### Fixed

- Number the stops in dossier PDF routes so standard text fonts can render
  their order on macOS.

## [0.9.0] - 2026-11-23

The tagged candidate stopped before publication at the hosted macOS PDF check.

### Added

- Configure ten limits for sentence rhythm, dialogue and function-word cues in
  an optional project settings panel. Each control explains what it measures
  and shows its default in the interface language.
- Download the displayed saved dossier version as an A4 PDF from its detail
  view, history, or manuscript side panel. The PDF includes section bookmarks,
  saved notes and tables, descriptions of places and routes, and pinned source
  quotations. The action identifies the saved version before downloading.
- Open a manuscript overview, chapter distribution and complete matching prose
  paragraphs from generated character dossiers, including existing dossiers.
  The reading view includes up to two neighboring sentences on either side
  where available and highlights the names in the matching passage.

### Changed

- Load live paragraph evidence in chapter batches. Keep manuscript-wide
  result navigation and preserve self-contained offline reports.
- Reuse chapter and scene prose projections across the supplementary reports
  in one analysis. Archive searches process validated revision paths with less
  allocation and continue checking each record's digest.

- Combine sentence lengths and pacing in one view. Open verified rhythm and
  word-pattern examples in the manuscript and identify their quotation context.
- Open and highlight verified occurrences of recurring phrases and motifs.
  Find author-supplied expressions in the local app.
- Use one shared passage navigation bar, with stable keyboard focus and
  consistent insets, disclosure markers and dialog controls across the workspace.
- Label the actual sentence-length ranges in the distribution and pacing
  views. Older reports show when their boundaries are unavailable.
- Use a single set of filters for tense review and one explicit save action
  for each review decision.
- Show why a passage was marked and a concrete reading question in each
  manuscript measurement card. For sticky sentences, show the configured
  thresholds and highlight the exact function words in the selected sentence.
  Lead the dialogue and pacing panels with the measurements writers need to
  start reading.
- Explain manuscript analysis in terms of questions writers can answer. The
  overview and pattern panels suggest where to look in the text, chapter tables
  spell out units, and a chapter measurement opens with the observed value and
  its manuscript reference. The full comparison table is available on demand.
- Share disclosure controls across Analysis, Project and Research, use the
  configured sentence-length ranges in analysis reports, and log browser search
  timings only in debug mode.
- Guide the public demo through a comparison of its first two chapters. The
  browser sandbox starts with a passage and explains each count in context.
- Harden file I/O, HTTP boundaries, SSRF protections, recovery database, and
  service lifecycle: add `FileUtils.read_bounded_regular_bytes` (`O_NONBLOCK` /
  `O_NOFOLLOW` + `fstat` checks) and reuse it in `speech_transcription` and
  `research/zotero`; enforce `Content-Security-Policy: sandbox; default-src 'none'`
  on HTML export previews in `_serve_artifact`; unify `_require_same_origin()`
  (`Sec-Fetch-Site`) across `/api/*` and `/artifact/*`; map
  `ResearchConflictError -> 409` in `ResponseMixin._research_error`; stream
  `Range` media responses, validate base64 strictly, and enforce project-root
  containment on `POST /api/research-ingest`; enable `daemon_threads` and
  accept-time timeouts in `_LoopbackHTTPServer`; reject link-local
  `169.254.0.0/16` and validate resolved endpoint IPs in `speech_providers`;
  enable `PRAGMA trusted_schema=OFF` and `PRAGMA journal_mode=WAL` with cached
  schema setup and connection reuse in `manuscript_editing`; keep `log_fd` open
  via `os.fdopen`, write `"port"` in `ManagedServe.ready()`, and warn on
  running/package version mismatch in `service`.
- Consolidate backend configuration, strict JSON, and subprocess helpers: share
  `load_strict_json()` in `config.py` across `audio_audit` and
  `research/dossier_edit`, align `read_explicit_project_config` on nonsymlink
  `project_config_snapshot`, derive `THRESHOLD_PRESETS["balanced"]` and
  `FEATURES` English units from `status.THRESHOLD_DEFAULTS` and
  `FEATURE_UNITS["en"]`, extract `_run_audio_tool` (`speech_record`) and
  `validate_worker_compute` / `set_offline_hf_env` (`speech_lifecycle`), pass
  `env=_ocr_tool_env()` on external OCR worker calls, and remove redundant
  recursive snapshot/DB opens in `research/catalogue.search`.
- Consolidate UI security, seven-language localization, shared helpers, and
  design tokens: fix `escapeHtml` attribute escaping, function-based
  `dossier-images.js` replacement, protocol-relative link rejection, and
  scoped `MutationObserver` throttling in `dossier-geography.js`; add 151
  missing locale keys across all seven `src/lixity/locales/*.json` catalogs
  and replace inline EN/DE fallbacks across command palette, editor,
  teleprompter, research lists/tools/filters, and reader backlinks; extract
  `modal_shell()`, `artifacts_panel()`, `help_badge()`, `script_json()`,
  `attr_json()`, and `FAVICON_DATA_URI` in `components.py`, `LixityLabels` /
  shared modal/download/fetch helpers in `component-layer.js`, and normalize CSS
  token references.
- Fix release packaging parity and cross-platform browser harnesses: include
  `src/lixity/locales/*.json` in `MANIFEST.in` and `check_release.package_files()`,
  wire full docs/public-site sync into `prepare_release.py`, share
  `check_release.source_version()` across doc generators, add demo artifact byte
  budgets in `build_examples.py`, add `ControlOrMeta+` and portable `<select>`
  navigation across Playwright suites plus `.pane-ribbon` browser coverage, and
  parameterize/cache `tests/dashboard_fixtures.full_dashboard`.
- Harmonize workspace action ribbons across Manuscript, Research, and Project:
  centralize Lucide icon rendering (`ui_icon()` parsing `assets/icons.js`,
  eliminating duplicate inline SVGs across Python/JS views), shorten localized
  Research/Project jump pill labels (`research_nav_*`, `project_nav_*`) with
  icons, collapse ribbon labels cleanly to icon-only (`LixityRibbonDensity`)
  instead of showing horizontal scrollbars when horizontal space is tight,
  wire `data-help`/`title` tooltips across ribbon pills, Research tools, and
  Project settings/audio/NDA controls (`tooltips.js`, `speech.js`,
  `settings.py`), eliminate the top-left flash/jump in `tooltips.js` and
  floating reader overlays via `LixityComponents.measureOverlay()` and
  `placeClampedOverlay()`, centralize shared toolbar/chrome selectors and
  `data-ribbon-section` attributes (`component-layer.js`,
  `research-navigation.css`), replace hardcoded EN/DE fallback strings in
  `speech.js` with full seven-locale entries, extract `_PROJECT_RIBBON_SPEC`
  in `dashboard.py`, add the sticky auto-hiding `.pane-ribbon` jump bar with top
  button and dynamic `scroll-margin-top` to the Project view, and align
  `#manuscript-reader-controls` and `.toolbar` onto the same translucent
  surface and `LixityChrome` auto-hide pipeline.
- Centralize subprocess environment allowlisting in `lixity.io.sanitized_subprocess_env`
  and apply it across FFmpeg (`speech.py`, `audio_audit.py`), ZONOS3 workers
  (`speech_providers.py`), ALSA/PipeWire audio capture tools (`speech_record.py`,
  adding explicit control timeouts), and Poppler/Tesseract native OCR calls
  (`research/ocr.py`), alongside `0o700` temp directories, symlink output guards,
  and shared `no_redirect_opener()` usage in `speech_worker.py`.
- Share canonical `LANGUAGE_CODES`, `LANGUAGE_CHOICES`, and `THRESHOLD_DEFAULTS`
  in `lixity.status` and defer heavy analysis imports in `lixity.service`, cutting
  `import lixity.service` startup time and heap usage substantially while keeping
  `service`, `doctor`, and CLI parser contracts unchanged.
- Fix `research.manuscript.resolve_project_manuscript_path` and
  `site_export.prepare_site` on hosts with symlinked parent directories (such as
  macOS `/var` -> `/private/var`) so legitimate project manuscripts and
  contained internal aliases resolve cleanly while escaping symlinks remain
  rejected, and allow `research.manuscript.reconcile_manuscript_links` candidate
  rows to supply `new_quote`, `line`, and `reason` so revised (`changed`) quotes
  reconcile in a single batch commit.
- Move the seven-language workspace label catalog out of the 14.8k-line Python
  module into packaged JSON files (`src/lixity/locales/*.json`) loaded lazily
  per locale with `orjson` (`workspace_labels_for`), adopt PEP 562 lazy exports
  in `lixity.__init__`, extract `cli_texts.py` and `cli_completions.py` from
  `cli.py`, and build only the invoked subcommand parser on CLI startup.
- Harden isolated audio subprocesses: strip ambient environment secrets and
  enforce `HF_HUB_OFFLINE=1` / `TRANSFORMERS_OFFLINE=1` for the ZONOS3 worker,
  restrict `speech_mlx_zonos.py` to its pinned model, bounded stdin, allowlisted
  generation arguments and non-symlink paths, and sanitize FFmpeg subprocess
  environments. Group speech engine capabilities into `recommended`, `advanced`
  and `retired` tiers while keeping existing saved profiles intact.
- Resolve user-installed font directories (`~/.local/share/fonts`,
  `~/Library/Fonts`, `~/AppData/Local/Microsoft/Windows/Fonts`) and fall back to
  standard macOS/Windows TrueType system faces strictly after open-license book
  fonts so PDF export works out of the box across platforms while preferring
  open-license typography when available.
- Consolidate speech reference checks (`profile_uses_reference`), control
  support lookup, direction conflict validation, no-redirect HTTP openers, and
  segment dispatch across the speech pipeline; bind ZONOS3 `reference_id` and
  model `speed` in the segment cache key so cloned voices and tempo changes
  never collide in cache.
- Prefer `.venv/bin/python` when present for `Makefile` browser, docs and
  release helper targets so macOS hosts with older system Python stay compatible.
- Keep long research views navigable with sticky in-panel section jumps,
  compact review disclosures and paginated dossier lists. Dossier cards retain
  details and actions while limiting long excerpts, tags and section previews.
- Add an explicit `mlx-audio` speech profile for Apple Silicon and a bounded
  `audio-transcribe` command. Local ZONOS3-Mini TTS runs in an isolated worker
  across the configured Lixity languages with built-in voices or an explicit,
  hash-bound project reference, reports runtime/cache readiness in `audio-status`
  without exposing paths, rejects unsupported free-text passage direction while
  preserving pronunciation rules and pauses, and applies speed as a model
  condition rather than FFmpeg postprocessing. Speech recognition uses Parakeet
  TDT v3. MLX-Audio remains optional and outside Lixity's core dependencies.
- Run source, browser and platform release checks concurrently. Use four
  pytest workers on Linux CI, and balance full browser shards with measured
  suite timings while keeping the publication checks on the tagged commit.
- Pass the verified Python 3.12 build to publication within the same CI run.
  Recheck archive contents and checksums against the tag and attest the SBOM
  alongside the existing build provenance.
- Run hosted browser checks in a digest-pinned Playwright image. Use small
  synthetic media fixtures for playback coverage without installing FFmpeg
  on each browser runner.
- Track editor npm updates, verify the checked-in editor bundle against its
  lockfile, and audit Python, editor and separately vendored dependencies.
  Generate a CycloneDX inventory from the verified release and its smoke install.
- Update the vendored Mermaid Tiny diagrams to 12.3.0, including the upstream
  DOMPurify 3.4.17 update. Retain the classic bundle and offline rendering.
- Show Flesch and LIX together with the counts used by their formulas in
  Measurements. Verify the rank projection eigensolver against a separate
  numerical implementation in development tests.

- Load native Qwen, Coqui/OpenVoice and Toucan models only for synthesis, using
  one shared spawned-process lifecycle. Release the child after a configurable
  idle interval (default 300 seconds after completion), protect active jobs and
  retain the lightweight HTTP worker. Health/status distinguishes configured
  models, residency and active work without loading weights.
- Consolidate native worker startup/serving/shutdown policy, validate local
  Qwen assets before serving, and recover model processes after load/render
  failures. Explicit library loaders and existing transport adapters remain.

- Organize the native analysis overview into passage review, chapter comparison
  and pattern exploration, revealing one existing section at a time while
  retaining deep links, input state and complete no-script reports.
- Display archived-source analysis scope, unverified context and pinned
  provenance in HTML as well as JSON. Prepare paragraph-layer cells once in
  `DocumentAnalysis`; render them through typed content/options contracts.
  Adapter callers of `render_analysis` must move optional reports into
  `DashboardContent` and presentation settings into `DashboardOptions`.
- Retain current render bundles in a bounded cache and disclose missing or
  invalid projection cutoffs instead of substituting a browser default.

- Correct regularized Mahalanobis distances to use the same standardized midrank
  coordinates as their covariance, including the production path with populated
  z* cells. Earlier mixed-space distances must be recomputed.
- Add versioned `meta.interpretation` diagnostics and a shared UI/text threshold
  legend for descriptive bands, deviations, nominal FDR and paragraph layers.
  Explain per-feature two-chapter cutoff limits without hiding computed scores
  or claiming that larger sample minima establish calibration.
- Present style axes as exploratory feature-rank projections, surface ridge
  regularization and clarify that reported eigenvalue shares describe the
  regularized matrix. Existing schema-5 fields and thresholds remain intact.

- Keep passage research compact with nested claim cards and a smaller linked-version action. The desktop return control stays hidden while its origin passage is visible and becomes available after leaving it; the mobile return bar keeps its place to avoid shifting the prose. Reader tools compact when an open context panel reduces their available width.
- Dismiss contextual help when activating a native disclosure, so its hint does not intercept the next Escape intended to close the opened settings.
- **Statistical & changepoint core (`math_core.py`, `diversity.py`, `pacing.py`, `analyzer.py`, `style_fingerprint.py`)**:
  - Added Jeffreys continuity-adjusted standard errors (`binomial_se_percent`, `poisson_se_per_mille`), sample-SD `asl` SE, `split_mad()`, `medcouple()`, `adjusted_boxplot_fences()`, `mad_finite_sample_factor()`, and `huber_location()`.
  - Fixed `yules_k` finite-sample denominator (`n * (n - 1)`), added `DEFAULT_MTLD_MIN_FACTOR_LEN = 5` minimum-run guard in `mtld`, and added Goh-Barabási finite-sample `burstiness()` to `pacing.py` (`compute_rhythm_profile`).
  - Standardized `pelt_changepoints` for scale/translation invariance with mBIC-inspired default penalty (`3 * ln(n)`), added `sn_estimator`/`qn_estimator` fallback for `zero_mad_varying` series, enforced `MIN_PARAGRAPH_LAYER_WORDS = 5` on per-1000-word rate layers in `layer_stats`, clamped non-negative `StyleFingerprint.passport` lower bounds, added Hamed-Rao (1998) autocorrelation correction in `mann_kendall` + BH FDR in `_derive_structural_diagnostics`, and added ridge shrinkage PCA + regularized Mahalanobis distances (`top_deviants(..., metric="mahalanobis")`).
- **Linguistic & narratological core (`syllables.py`, `sentences.py`, `tense.py`, `verb_grammar.py`, `dialogue.py`, `scenes.py`, `characters.py`, `language_data.py`)**:
  - Improved syllable accuracy in `count_it()` (rising `[iu]`+vowel diphthongs, silent `qu`/`gu`), `count_de()` (`DE_CLEAN` empty guard, `qu->k`), `count_fr()` (`-ment` / `souvent` / `-éC+ent` exceptions), and `count_en()` (`-Cle(d|s)`).
  - Protected spaced abbreviations (`z. B.`, `d. h.`, `u. a.`, `o. ä.`, `p. ex.`, `d. w. z.`), accented initials, ellipses, and post-quote dialogue tags in `sentences.py`.
  - Extended `_german_perfect_spans()` across 12-token clauses and subordinate backward scans, added `_english_perfect_spans()` (`have/has/had + VBN`), and separated Konjunktiv I/II (`subjunctive_i`/`subjunctive_ii`) and `würde + Inf` (`conditional`) in `verb_grammar.py`.
  - Clamped `find_dialogue_tag_spans()` at sentence terminators/quotes, added line-initial dialogue dashes (`^[—–]`) for `fr`/`es`/`it`/`pt`, tightened German indirect-speech Konjunktiv II rules, excluded French `-ment` nouns, guarded German capitalized nouns in unconfigured `scenes.py` character cues, and added optional `case_sensitive` matching in `characters.py`.
- **UI scaling, dropdown replacements, CSS & Skill parity (`ui/`, `research/`, `skills/lixity/SKILL.md`)**:
  - Extracted `research/dossiers.py` and `research/matrix.py` from `research/api.py`; updated `skills/lixity/SKILL.md` to document all 16 MCP tools and valid CLI commands (`analysis-review`), backed by `tests/test_mcp.py`.
  - Added O(1) `.ptext` index and chapter `<details>` grouping for term occurrences (`manuscript-links.js`), collapsed dossier claim lists (`research-content.js`), list windowing (`40`), weighted tag clouds, confidence/status pills, and searchable pickers (`research-lists.js`, `research_panel.py`).
  - Added live-count filter pills and inline decision toggles in Triage, Heatmap scope, Dimensions projection, and Settings (`dashboard.py`, `heatmap.py`, `dimensions.py`, `settings.py`, `dashboard.js`); segmented Reader width/spacing toggles and dynamic Command Palette hydration (`manuscript_reader.py`, `manuscript-reader.js`, `command-palette.js`); fixed `#modal-research-revision-batch` footer placement (`modals.py`), CSS duplicate/touch-target rules (`dashboard.css`, `speech-player.css`), Speech modal i18n/nesting (`speech.js`), and grouped Publication chapter pickers (`publication.py`).
- **Per-document write lock & compact dossier sections (`manuscript_editing.py`, `routes_editing.py`, `routes_markers.py`, `research-cards.js`)**: Replaced coarse global `SOURCE_WRITE_LOCK` contention with `document_lock(source)` keyed by resolved manuscript path (preserving `SOURCE_WRITE_LOCK` export for compatibility), and reduced inline `DossierSections` preview limit in dossier cards from 4 to 2.
- **Normalized editorial review & UI disclosure (`research/editorial.py`, `research/presentation.py`, `research-review.js`, `manuscript-links.js`)**: `editorial_review_data()` now deduplicates affected dossier outlines into top-level `dossier_outlines` with `sections_count` per candidate; `research-review.js` collapses section outlines behind a disclosure toggle and `manuscript-links.js` groups large manuscript link lists (>12 links) by chapter `<details>` while keeping chapters needing attention open.
- **Inverted 3-gram & hash quote lookup (`research/manuscript.py`)**: `derive_manuscript_review()` now indexes paragraph SHA-256 hashes in O(1) (`by_hash`) and uses a character 3-gram inverted index (`_ParagraphQuoteIndex`) for exact quote fallback resolution.
- Preserve unchanged manuscript paragraphs while searching, and keep dossier
  suggestion controls in place when switching between drafts. The local app
  loads the diagram renderer on first use. Character dossiers reuse speaker
  attribution without calculating relationship pairs for the unused dialogue panel.
- Edit chapter-specific term variants in separate rows with their own chapter
  numbers and notes. Dossier review loads occurrences for the selected dossier
  using the open project's settings, including for manuscripts in subfolders.
- Share native test selection and browser fixtures between local and CI checks.
  Regenerate screenshots before examples so each public artifact has one writer.
- Group dossier actions with the version note and align the section headings.
  Keep the outline below the research toolbar, and space PDF excerpt labels
  closer to their passages while retaining the body type size.
- Share heading, prose and metadata roles across the workspace, reading
  exports and Pages. Apply semantic notice colors and modal shadows through
  the selected theme, including system mode.
- Reuse native select controls in project, dossier and export flows. Scale
  guide text with browser font preferences and let tour captions wrap below
  narrow players.
- Give analysis settings a single control per choice, explain the editorial
  presets in plain language, and show localized save feedback beside Apply.
  Language choices and threshold values come from the shared engine settings.
- Explain project path failures in the interface language and keep the folder
  chooser on the last loaded folder. Show where the Word import preview omits
  a table, image or footnote.
- Use the selected project's configuration for language and thresholds when
  opening a project, including when it sits inside another project folder.
- Localize generated dossier titles and distinguish suggestions, previews and
  saves. Show singular and plural project research counts in all seven locales.
- Open matching character evidence in the manuscript when the paragraph and
  source revision match the displayed reader. Keep excerpts readable when no
  jump is available.
- Show the chapter matrix's dated revision deltas next to their measurements.
  The matrix and the editor's comparison use the same chapter counts and
  display conventions. Tense review loads independently.
- Localize homepage image descriptions and send authors to the matching
  German or English sandbox. Label English demo links on localized Pages.
- Preview the complete manuscript dossier draft before saving and confirm
  its source, settings and content. Keep the scene register and each scene
  separately selectable. Use actual prose matches for place suggestions
  and identify configured places and inferred candidates.
- Preview and refresh the saved analysis directly from a generated character
  dossier. Group name counts, chapters with matches and full passages with
  highlighted names and surrounding context. Open live counts and passages
  separately. Show the first and last place match, and bring explicitly linked
  object or term matches into their dossiers.
- Explain why each manuscript dossier is proposed and show the qualifying
  passage for inferred places. Edit the place list from the workspace. Tune
  inferred candidate limits, character passage context and saved report
  length in the project workspace. Compact drafts retain a checkable first
  passage in the preview.
- Link a configured term to a dossier in the manuscript's term editor.
  Prepare contextual excerpts only for the requested page of figure evidence.
  Skip Unicode fallback scans when an NFC paragraph cannot contain a match.
- Use the same installed discovery sections in the CLI and MCP. Accept a
  positional manuscript or explicit project default in research comparison
  and report manuscript selectors in machine-readable command help.
- Use the selected manuscript’s project settings throughout dossier review
  and creation. Keep other proposals available when scene or place settings
  need attention. Share Markdown excerpts and chapter tables between generators.
- Share chapter-delta response fields between editor comparisons, revision
  history and standalone text comparisons. Read the paragraph comparison
  marker position from the prepared dashboard data.
- Reuse the bounded file reader for serving project exports and reuse validated
  export options when preparing a native reading website.
- Align the first-session, writing, recovery and publication guides with the
  current workspace. Document export choices in the workspace guide, CLI
  commands in the usage reference and preflight payloads in the API contracts.
- Document the checkout and packaged service paths separately. Add `make doctor`
  for the checkout's configured port, and include the Lixity skill in the
  source archive with the test that checks it.
- Explain same-port project views in the service help and setup guides. Show
  the running app version in service status and doctor output, and expose
  explicit-port service status through read-only MCP discovery.
- Give the writing surface its own editing controls and a Versions disclosure
  for comparison, recovery and download. Add a display preference for text
  associations in the companion dossier.
- Put the chapter picker and projection controls above the style plot. Fit
  point help within the canvas area and allow page scrolling over the plot.
- Open the public demo in the native manuscript layout, with guided draft
  examples and the read-only notice in the workspace navigation.
- Give the fictional Warehouse 4 draft verifiable examples of a tense slip,
  repeated phrasing, reported speech and wordiness. Add guided passage links
  and parallel English and German practice drafts in the browser sandbox.
- Add localized measurement references from the analysis overview, chapter
  inspector, passage evidence and version comparison. Explain counting filters
  and let writers decide how a passage reads in context.
- Use one manuscript metric selector for the app and reports. Explain each
  selection in seven languages and link to its exact method.
- Share the chapter and metric select control and define reader appearance
  choices in one place. Reuse the same function-word rule and quotation context
  across evidence, pacing, phrase search and version comparisons.
- Link each public homepage to its metric reference. Check generated guides
  with the same documentation gate in local builds, release preparation and
  GitHub Pages.
- Reuse the legacy word-count preparation in analysis and version history.
  Use one reader control path for metric selection and clearing, and share the
  export's page preparation between the reading and analysis pages.

### Fixed

- Keep teleprompter playback moving smoothly at slow reading speeds and high
  screen refresh rates by retaining fractional scroll distance between frames.
- Keep the next and previous examples reachable by keyboard, and restore focus
  to the control that opened the passage navigation. Localize invalid search
  pattern errors.
- Improve dark-mode quotation context contrast and wrap word-pattern actions
  at small widths and larger font sizes.
- Keep project navigation inside the viewport during resizing and make its
  destinations reachable with larger text. Use the shared control text size
  for the measurement selector and touch targets for passage navigation.
- Label changes in dialogue share and sticky-sentence share in percentage points.
- Update the teleprompter's dossier context when the last paragraph is reached.
- Verify file stability on Windows without comparing incompatible change times
  reported for paths and open file descriptors.
- Match the browser CI host to the Noble container and check Python TLS before
  installing dependencies.
- Measure all three texts in the local version comparison under one effective
  project configuration. Pair chapter deltas only when chapter identity can
  be established.
- Use the same availability decision for navigation and the rendered Motifs
  and Scenes panels. Explain an empty result when those analyses completed.
- Group occurrences of the selected repeated word in the reader.
- Keep the Research source navigation within the viewport immediately after
  resizing to a narrow screen.
- Defer manuscript autosave until text composition finishes.
- Keep percentage labels and inclusive dialogue-share and function-word
  comparisons stable when converting between percentages and ratios.
- Standardize finite chapter series before squaring their deviations so very
  large and very small values remain comparable in changepoint analysis.
- Reject unsupported language selectors and coerced paragraph flag levels in
  text-analysis MCP tools.
- Reject dossier PDF downloads when a retained extraction has inconsistent
  source-version provenance.
- Keep linked term and quote jumps on the verified line range when identical
  paragraphs appear in different chapters. Reuse prepared term variants and
  compute cross-profile overlap flags for returned matches.
- Clear old dossier revision, section and record-wide options when retargeting
  a reader export. Explain tempo in the audio editor according to the engine
  and show the current engine default.
- Keep pending releases undated and link to the working comparison until a
  maintainer records the release date.
- Keep PyPI catch-up dispatches independent of Pages deployments. Verify live
  Pages and Zenodo independently, and allow release verification to omit
  intentionally skipped PyPI publication or a superseded Pages deployment.
  The Linux application launcher opens the URL selected by the managed service.
- Show repeated copies of the same generated character analysis once in the
  dossier reader and PDF. Refresh unedited generated text in place and keep
  authored changes and saved versions.
- Verify manuscript jumps from configured term matches against the current
  source digest. Save term edits with the active project settings token and
  preserve their dossier and claim links.
- Accept decimal commas in dossier coordinate entry when a space separates
  longitude and latitude.
- Complete the manuscript timeline when an interrupted save is retried. Recover
  the starting measurement from the journal's verified revision and retained
  bytes, and commit the available measurements with the save receipt.
- Preserve section links and manuscript quotations in published Markdown guides.
- Refresh the open editorial review after saving a dossier image and request the
  report once when opening the whole-project review.
- Accept only the stdio launch syntax for `lixity mcp` and describe tool
  arguments through discovery. Build the MCP outlier matrix from measured
  chapter-feature scores and accept finite cutoffs above the default range.
  Use built-in text-analysis defaults independently of the subprocess directory
  and local user settings.
- Keep loaded dossier suggestions when switching categories or selecting a
  suggestion, including when loading before the research view finishes
  identifying its project. Offer the existing character template when there
  is no new character suggestion.
- Move focus to the title when opening the dossier form from the toolbar.
  Bring the form into view when expanding its heading in a short window.
- Hide reader analysis chrome during writing and keep reader shortcuts from
  activating hidden controls.
- Distinguish unavailable style-change calculations from tested comparisons
  with an empty shortlist. Show the exact missing chapters and word floor.
- Show manuscript measurements on first opening the analysis overview and
  keep overview links from interrupting the reader during startup.
- Show paragraph comparison measurements once in the tooltip, with the
  action in the heading.
- Share aligned text, arrow spacing and native selection across the chapter and
  analysis pickers, project settings and dynamically generated settings fields.
- Show the effective dialogue and chapter-closing thresholds. Label empty
  tense review results, show the reason for the suggested passage and offer
  sentence examples when they are available.
- Keep flagged manuscript passages visible when navigating to them on a
  narrow screen.
- Omit speech tags inside unresolved quotes consistently from dialogue
  reports and passage evidence. Keep authored heading-like text in capped
  exports and restrict the teleprompter shortcut to the manuscript reader.
- Recognize paired typographic quotation marks in the browser sandbox and keep
  function-word highlights visible across quotations and speech cues.
- Distinguish missing language rules, zero matches and unavailable text ranges
  in manuscript analysis. Apply revision deltas to the matching source and
  report missing chapter measurements as unavailable in version history.
- Preserve evidence display preferences across metric changes and reloads.
- Compare word-pattern groups only when the language profile supplies the
  component rules. Describe a passage's comparison against its chapter median.
- Keep sticky-sentence links when counted text and displayed text use
  canonically equivalent Unicode forms.
- Use the measured sentence lengths for paragraph averages, including with
  boundary-sensitive custom word patterns. Bind revision deltas and review
  results to the same project settings. Keep late responses from replacing
  the editor's current revision measurements.
- Keep cue hits consistent between corpus measurements and paragraph evidence
  when a project changes the word tokenizer or an unrelated cue pattern.
- Share quotation boundaries across the analysis, reader and retained-version
  measurements. Recognize supported typography across paragraphs and count
  each quoted word from its own analysis scope once. Use the actual baseline
  date in the editor's version summary and show share changes in percentage
  points for the manuscript as well as for chapters.
- Preserve an opening prose passage before the first chapter heading and
  ignore appendix markers shown inside comments and fenced code examples.

## [0.8.2] - 2026-11-16

### Changed

- **Research snapshot reuse (`research/api.py`)**: `research_gaps()` now reuses a single verified `Repository.snapshot()` across `_claim_matrix_data()`, `_editorial_review_data()`, and `_timeline_data()` instead of reloading the archive three times.
- **Manuscript save lock & single-pass metrics (`manuscript_editing.py`)**: `ManuscriptStore.save()` releases `SOURCE_WRITE_LOCK` while computing missing revision snapshots and inserts them with `INSERT OR IGNORE`; `analyze_manuscript_snapshot()` computes required metrics in a single pass.
- **Unknown semantics (`manuscript_editing.py`)**: `indirect_speech_per_1000` now guards on `indirect_speech_available` (returning `None` when unavailable), and unpopulated `flags_count` returns `None` instead of `0` with a nullable SQLite schema migration.
- **Chapter diagnostics scaling (`style_fingerprint.py`, `scripts/benchmark_pipeline.py`)**: Replaced O(n²) `mann_kendall` pair scans and `qn_estimator` distance materialization with O(n log n) Fenwick-tree inversion counting and O(n log n)/O(n)-space selection, added a constant-series fast path to `pelt_changepoints`, and added a synthetic varying-chapter benchmark fixture.

## [0.8.1] - 2026-11-16

### Added

- **Manuscript-Driven Dossier Drafts (`manuscript_drafts.py`, `research/api.py`, `research/cli.py`, `routes_research.py`, `mcp.py`, `research_panel.py`, `research-workspace.js`)**:
  - `lixity research dossier-drafts` and `GET /api/research/manuscript-dossier-drafts` extract deterministic, read-only character and scene dossier drafts (`manuscript-dossier-drafts/1`) from manuscript presence/POV gaps, character voice profiles, and scene metrics.
  - `lixity research dossier-from-manuscript` and `POST /api/research-dossier-from-manuscript` explicitly create a saved dossier from a selected draft (`--draft-id` / `draft_id`, or `--kind` fallback).
  - Read-only MCP tool `lixity_manuscript_dossier_drafts` exposes the same deterministic draft extraction for `text` (`language`, `kind`: `all|character|scene`).
  - Research -> Dossiers adds **Draft dossier from manuscript** (`#r-manuscript-dossier-btn`) to inspect and save manuscript-derived drafts.

### Fixed

- Accept GitHub's `untagged-<hex>` draft asset URLs during `verify-draft`
  before release publication binds `download/<tag>/` URLs, while keeping
  published asset URL checks strict.
- Honor `PYTHON_BIN` before falling back to `.venv/bin/python` across all browser
  suites (`editor-features.cjs`, `editor-navigation.cjs`, `manuscript-editor.cjs`,
  `home-tour.cjs`), verified with `tests/browser/support/python-entrypoints.test.cjs`.
- Keep logging importable on Python 3.10 by restricting generic handler types
  to static type checking.
- Preserve the zero-MAD population-deviation fallback at extreme finite scales
  on Python 3.10 without changing its formula. Run the complete source CI gate
  on Python 3.10 and 3.12; inject configuration metadata errors at the portable
  `Path.stat` boundary.

- Resolve platform-specific temporary directory aliases before building example
  projects, preserve the reviewed demo manuscript bytes across Git checkouts,
  and bind Windows loopback listeners exclusively to prevent a second server
  from reusing an active app port.

- Keep initial Research list reads bound to the accepted project context so a
  late startup response cannot strand collection editing or erase a new draft.

- Encode custom Markdown callout titles and wikilink destinations for their HTML
  attribute context so quoted input remains inert in native and exported readers.
- Bound DOCX source bytes, ZIP entry count, streamed document XML and converted
  output; reject original-file aliases and publish conversions atomically.
- Reject undeclared files and noncanonical inventory paths when restoring a
  research archive, before migration or publication.

- Synchronize the homepage tour, localized captions and duration labels with one
  48-second timeline. Pace pointer movement, show one verifiable action per shot,
  and keep captions readable without competing camera or typing effects.
- Publish speech job terminal states after temporary source cleanup, including
  cancellation or shutdown while cleanup is in progress.
- Bind manuscript revision deltas and the editor pulse to current source bytes
  after reverts or external edits, preserving immutable historical measurements.
  Resolve explicitly selected retained revisions outside the timeline window;
  do not infer a baseline for an older reused or unrecorded current snapshot.
- Honor live reduced-motion changes in the homepage video tour without polling
  its media query in animation frames; explicit playback remains available.
- Derive homepage screenshot dimensions from the generated images so a later
  documentation sync preserves their current aspect ratios.

### Changed

- Harden the release and CI pipeline (`Makefile`, `scripts/check_release.py`,
  `scripts/prepare_release.py`, `scripts/release_channels.py`,
  `scripts/run_browser_suites.py`, `.github/workflows/*.yml`): require full
  source (`Python 3.10` and `3.12`), Chromium browser and Windows/macOS native
  gates before release publication; verify `SHA256SUMS` read-only and stage
  fresh build/smoke artifacts before promoting into `dist/`; mark prepared
  release notes as pending verification; recover immutable GitHub release
  assets and reconcile existing PyPI digests without rebuilding or
  `--skip-existing`; add `doctor`, `verify-pages`, `verify-release` and
  `--check-zenodo` subcommands/options plus `make github-check`, `make rc-gate`
  and `make release-verify` (with modern `gh` binary discovery and
  askpass/keyring sanitization); add pre-tag release-candidate qualification
  (`rc.yml`), 4-shard Chromium browser CI (`--shard INDEX/TOTAL` in
  `run_browser_suites.py` and `browser.yml`), and isolated wheel build + smoke
  on both Python `3.10` and `3.12` in `tests.yml`; retain bounded failure-only
  browser CI diagnostics and summaries (`--diagnostics`, `--summary`); check
  all four site/doc generators and record `deployment.json` provenance on
  Pages; and pin workflow actions to explicit commit SHAs.
- Clarify central product and onboarding copy across seven public languages:
  distinguish development availability, built-in offline analysis, optional
  integrations, retained source provenance and heuristic text evidence.

- Keep five Research content tabs and move search/link review into shared tools
  with explicit return controls. Compare vocabulary from the selected source,
  with current-source provenance and terms/chapter links before optional numeric
  details; retain exact quotations, draft evidence and whole-project link review.
  Rename Source copies to Sources and clarify metadata-filter and lexical limits
  in all seven interface languages.

- Organize dossier collections by title: add dossiers from a chooser, reorder or
  remove selected entries, and name new collections without typing technical
  identifiers. Read-only references remain available in a collapsed section;
  unavailable members remain in the saved order until explicitly removed.
  Localize the controls and dossier metadata help in all seven interface languages.
- **Direct Research Timeline Tab (`research_panel.py`, `research-workspace.js`, `command-palette.js`)**: Promoted Timeline to a top-level Research tab (`#research-tab-timeline`) alongside Dossiers, Claims, and Decisions.
- **Brand Icon Suite & GitHub Pages Pipeline (`docs/assets/brand/`, `docs/favicon.ico`, `docs/manifest.webmanifest`, `docs/assets/home.css`, `scripts/build_brand_assets.py`, `.github/workflows/pages.yml`)**: Refined the multi-profile/multi-format brand icon suite (`make brand-assets`), tightened GitHub Pages vertical spacing (`docs/assets/home.css`), and added the `build_public_site.py --check` pre-deploy gate to `pages.yml`.

### Added

- **Manuscript Editor Formatting Bar (`manuscript-editor.js`, `scripts/editor/editor.js`)**: `H2`, `B`, `I`, and `—` formatting controls and `Ctrl+B`/`Ctrl+I` shortcuts.
- **Expanded Browser Sandbox (`docs/sandbox/index.html`)**: Sentence-by-sentence SVG rhythm sparkline, narration vs. dialogue voice contrast, rough-draft preset, clickable word-echo chips, highlight layer toggles, local `.txt`/`.md` drag-and-drop import, and Markdown summary copy.
- **Parallel Test Execution & Matrix Consolidation (`pyproject.toml`, `Makefile`, `scripts/run_browser_suites.py`, `scripts/browser_tools.cjs`)**: `pytest-xdist` (`-n auto`), `fast-check`, `pages-deploy`, longest-first browser suite scheduling, and fast representative browser matrix (`browserLocales` / `fullMatrix`, with `LIXITY_BROWSER_FULL=1` for `make browser-full`).
- **Navigation & Scroll-Anchor Documentation (`docs/WORKSPACE.md`, `tests/browser/README.md`)**: Documented the unified cross-view jump/scroll-anchor contract and the fast vs. full browser matrix.

### Fixed

- **Analysis Layer Legend (`dashboard.js`)**: Hide the paragraph-comparison unavailable notice when an inline-evidence layer (`sticky`, `dialogue_tag`, `indirect_speech`, `echo`) is active.
- **Sticky Scroll Margin & Capture (`interactions.js`, `manuscript-reader.js`)**: Count `bounds.bottom` in `setPassageScrollMargin` only when a sticky bar is already stuck (`bounds.top <= barTop + 1`), and align `capture()` threshold (`boundary + 10`) so jump targets are reliably captured.
- **Product Tour Video Pacing (`scripts/capture_screenshots.cjs`, `scripts/make_videos.py`)**: Replaced rapid 2-second cuts with 6 calm, readable 8-second scenes (48s total) and gentle transitions.

### Additional changes included in 0.8.1

- Add dramaturgical & structural analysis heuristics (`pacing.py`, `dialogue.py`,
  `scenes.py`, `characters.py`, `corridors.py`):
  - Sentence-level Sticky Sentences (`sticky_sentences`, `sticky_sentence_pct`,
    `mean_glue_pct`, `sticky_items`, `CorpusConfig.sticky_glue_pct=45.0`,
    `sticky_min_words=8`) and per-language Dialogue Tag density (`dialogue_tags`,
    `dialogue_tag_pct`, `dialogue_tags_per_1000`, `dialogue_tag_available`).
  - Scene Entry/Exit Hook classification (`classify_scene_hook`: `dialogue`,
    `question`, `reflection`, `action`, `unknown`; `hook_distribution`,
    `exit_hook_score`) and declared POV chapter-absence gaps (`pov_gaps`,
    `pov_longest_gap`, `pov_leading_gap`, `pov_trailing_gap`, `pov_share`,
    `pov_summary`, `pov_chapters_map`).
  - Optional non-prescriptive Genre Reference Corridors (`crime_thriller`,
    `literary`, `romance`, `speculative`) exposed via `lixity pacing --genre`,
    `api.pacing(..., genre=...)`, `api.corridors(...)`, and read-only MCP
    (`lixity_pacing` `genre` arg, plus `lixity_scenes` and `lixity_corridors`).
  - Direct Speech Mode (`Nur Dialoge` / `Dialogue only`, shortcut `D`) in the
    manuscript reader (`manuscript-reader.js`, `manuscript-reader.css`,
    7-language labels in `language_data.py`), plus organic surfacing of Scene
    Hooks, POV gaps, Sticky Sentences, Dialogue Tags, and Genre Corridors in
    `narration.py`.
- Add deep prose & inline evidence analytics (`paragraph_evidence.py`,
  `dialogue.py`, `scenes.py`, `narration.py`, `manuscript_reader.py`):
  - Paragraph inline evidence layers (`evidence[idx]["layers"]`) for `sticky`
    (sentence spans with `words >= sticky_min_words` and `glue_pct >= sticky_glue_pct`),
    `dialogue_tag` (speech-attribution verbs adjacent to dialogue quotes), and
    `echo` (non-function content words `len >= 4` repeated `>= 2` times in the
    same paragraph), wired into reader `CSS.highlights` filter chips
    (`#reader-inline-evidence-layers`) with 7-language labels in `language_data.py`.
  - Deep dialogue analytics in `dialogue.py`: `voice_separation` (spoken
    dialogue vs. narrative prose ASL, `asl_delta`, `?!` density,
    `cosine_similarity`, `separation_label`) and `adverbial_tags` /
    `adverbial_tag_pct` / `adverbial_tag_available`, surfaced in CLI,
    `lixity_dialogue` MCP, and `render_dialogue_panel`.
  - Deep scene dynamics in `scenes.py`: intra-scene `asl_shift`,
    `dialogue_shift`, `scene_dynamic` (`accelerating`, `decelerating`,
    `dialogue_surge`, `steady`, `insufficient_length`), `filter_per_1000`,
    `sensory_per_1000`, and corpus-level `pacing_plateaus` (`low_exit_hooks`,
    `flat_pacing`), surfaced in CLI, `lixity_scenes` MCP, and
    `render_scenes_panel`.
- Add 4 computational-narratology heuristics (`scenes.py`, `dialogue.py`,
  `characters.py`, `pacing.py`, `paragraph_evidence.py`, `narration.py`):
  - **Implicit scene breaks (`scenes.py`):** `scene_report()["implicit_breaks"]`
    lists `[{chapter, scene, paragraph_index, cue_type, snippet}]` for
    adjacent-paragraph `time`, `place`, and `character` transition cues inside
    explicit scenes.
  - **Character voice separation (`dialogue.py`, `characters.py`):**
    `character_voice_profiles()` / `presence_report()["character_voices"]`
    compares per-character attributed dialogue (`min_turns: 3`, `asl`,
    `question_excl_rate`, `function_word_share`, and `narrator_*_delta`) against
    narrative prose.
  - **Rhythm profile & sentence-length entropy (`pacing.py`):**
    `rhythm_profile` on `PacingReport` and `ChapterPacing` exposes `asl_cv`,
    `asl_iqr`, `length_entropy` (Shannon bits), `normalized_entropy`, and
    `bucket_shares` (`short`, `medium`, `long`).
  - **Indirect speech detection (`paragraph_evidence.py`, `dialogue.py`):**
    new `indirect_speech` inline evidence layer (`layers["indirect_speech"]`,
    `kind: "pattern"`) plus `indirect_speech`, `indirect_speech_per_1000`, and
    `indirect_speech_available` on `DialogueReport` / `DialogueChapter` (7
    languages + German *Konjunktiv I*).
- Add Phase 2 structural & revision analytics (`scenes.py`, `dialogue.py`,
  `characters.py`, `manuscript_editing.py`, `cli.py`, `mcp.py`,
  `docs/sandbox/index.html`):
  - **Lexical cohesion drops (`scenes.py`):** `implicit_breaks` now computes
    `cohesion_similarity` (Jaccard overlap of lowercase content tokens `>= 3`
    chars across adjacent 2-paragraph windows inside scenes) and emits
    `cue_type: "cohesion_drop"` (or `+`-joined combinations such as
    `"time+cohesion_drop"`) when both windows have `>= 10` content words and
    `cohesion_similarity <= 0.05`.
  - **Character interaction matrix (`dialogue.py`, `characters.py`):**
    `character_voice_profiles()` and `presence_report()` now expose
    `character_interactions` (`pairs: [{a, b, turn_exchanges, co_chapters}]`,
    `turn_dominance: [{name, turns, words, word_share, turn_share}]`).
  - **Enriched revision diff (`manuscript_editing.py`, `cli.py`, `mcp.py`):**
    `analyze_snapshot()`, `timeline()`, `delta()` (`lixity-timeline/1`), and
    `compare_texts()` (`lixity-diff/1`) include `length_entropy`, `sticky_pct`,
    and `indirect_speech_per_1000`, exposed via `lixity diff` and the read-only
    `revision_diff` MCP tool (13 tools total).
  - **Browser Sandbox upgrade (`docs/sandbox/index.html`):** 1-click classic
    presets (*Effi Briest* Kap. 7 & *Pride & Prejudice* Dialogue Contrast) with
    `?preset=` deep-link support, live `asl_cv` / `length_entropy`, and
    `indirect_speech` highlighting.
- Add local SQLite manuscript revision time-series (`manuscript_revisions` in
  `recovery.sqlite3`), deterministic `timeline()` / `delta()` APIs
  (`/api/manuscript-timeline`, `/api/manuscript-delta`), Writing-mode Session
  Pulse with sparkline popover, subtle edited-line gutter markers, comparison
  column summaries, and live chapter-delta badges in the heatmap matrix.
- Add a 100% client-side passage sandbox (`docs/sandbox/index.html`) for trying
  sentence rhythm, dialogue share, and local word echoes without installation,
  plus a per-user Linux XDG desktop launcher (`scripts/install-desktop-linux.sh`).
- Add a minimal read-only MCP server (`python -m lixity.mcp`, stdlib-only
  stdio transport, no writes) exposing `about`, `analyze` and `profile`
  over `tools/list` / `tools/call`. Documented in `docs/AGENTS.md`.
- Automated release preparation tooling via `scripts/prepare_release.py` and
  `make release-prepare VERSION=vX.Y.Z`, drafting release notes, updating
  `_version.py`, and running documentation synchronization in one verified step.

### Changed

- Harmonize UI visual hierarchy and resolve container border fatigue: introduce
  a unified 3-tier dark surface palette (`#0c1017` base canvas, `#121822` surface,
  `#1a2230` raised controls) paired with translucent `rgba(255, 255, 255, 0.08)`
  hairlines. Modernize context dock tabs into a seamless Segmented Pill Control
  (`Textstelle | Dossier daneben | Recherche`), flatten nested boxes within
  passage research, and eliminate awkward corner seams between sticky controls
  and the search toolbar.
- Refocus public site metadata and search engine snippets on offline manuscript
  analysis and evidence research across all 7 supported languages, adhering to
  optimal SERP length limits (≤60 char titles, ≤155 char descriptions) and adding
  Mastodon and Bluesky `rel="me"` federation links.
- Precompile motif and signal regular expressions in `CorpusAnalyzer`, directly
  reuse lowercased word token streams in `ParagraphMatcher._fast_cues`, and fast-path
  paragraph separation in German tense matching while strictly preserving transitive
  motion verb semantics.

- Streamline reader and writing toolbars into single-row desktop layouts with
  semantic grouping, and introduce central distraction-free auto-hide chrome
  (`window.LixityChrome`) fading sticky header bars on downward scroll or after
  3.5s of reading/writing inactivity, with zero layout shift (`CLS = 0`) and
  instant reveal on upward scroll, top-edge hover, keyboard focus (`:focus-within`)
  or shortcut keys (`Escape`, `Alt`, `F6`, `Ctrl/Cmd`).
- Fast-path paragraph and search DOM rendering in `interactions.js` and
  `dashboard.js`, skipping redundant `getSelection()` and `DocumentFragment`
  allocations on initial load and search clearing, precompiling search regular
  expressions, caching chip elements and isolating outlier DOM writes. Replace
  linear paragraph traversals with `O(log N)` binary-search geometry capture in
  `manuscript-reader.js` and throttle broad `document.body` mutation records.
- Group manuscript reader controls into a left-to-right reading, review/companion
  and authoring flow with an explicit `Close writing` return action, keep desktop
  search and paragraph filters on one shared toolbar row, offset the sticky
  overview outline below the reader toolbar, and align Command Palette (`Ctrl+K`
  / `Ctrl+P`) and inspector backlink routes with the active workspace views,
  metrics, disclosures and panels. Document the interaction taxonomy, author/lector
  happy path and alternative click paths in `docs/WORKSPACE.md`.

- Memoize per-token verb/descriptive and lexical cue classification (`filter`,
  `sensory`, `nominal`, `adjective`) across `CorpusAnalyzer`, `ParagraphMatcher`
  and `TenseMatcher`, fuse sentence-span and NFC-normalization passes in
  paragraph evidence, and evaluate curated finite tense inventories over a
  single tokenized word stream. Analysis, profile, evidence and fingerprint
  outputs remain bit-identical while book-scale `analyze` and `profile` run
  3x–4x faster (~150k–165k words/s).
- Use `sqlite3.Row`, `PRAGMA busy_timeout`, `ON CONFLICT` upserts, window
  functions (`ROW_NUMBER() OVER`) and batch `executemany` in the manuscript
  recovery store and FTS5 research catalogue, and render command-palette results
  and Markdown editor toolbars declaratively through the vendored Preact + `htm`
  component layer (`LixityComponents`).

- Keep project navigation stable across dossier and view changes, preserve the
  reading passage when toggling it, and reserve scrollbar width between views.
  Central workspace entrances remain finite and geometry-preserving, and skip
  hidden-page/reduced-motion scans. Tall paragraph jumps keep their beginning
  below sticky mobile controls instead of hiding it beneath the toolbar.
- Reduce redundant toolbar browser combinations from 126 to 66 while retaining
  every locale, both themes and all DE/EN breakpoints (`--exhaustive` is available).
  Browser runs now summarize their slowest suites to guide further optimization.
- Keep the native reading toolbar on one desktop row after adding Write. Compact
  optional labels according to available toolbar width, retain accessible names
  and test all seven fully localized interfaces in both themes.

- Preserve existing export history when an archive move fails: replace files
  atomically without deleting the previous target first. Cross-filesystem archive
  moves fail explicitly. Remove repeated workspace guidance and distinguish
  measured editor smoke timings from outstanding performance acceptance work.
  Clarify project versus research-only backup scope and link development installs
  to the shared checkout verification steps.

- Extend unreleased writing with localized search/replace, manual conflict and
  recovery comparison, guarded nested research drafts and revision-validated
  literal reader selections. Preserve undo across reading and writing.
- Add unreleased `project-backup` and `project-restore`: explicit saved-file
  inventories, retained research, checksums and validated no-replace restoration.
  Exclude unselected settings, editor recovery journals and unsaved browser drafts.

- Make product descriptions more concrete across the README and seven public
  languages: passage-level explanations, retained evidence and selected reading
  exports. Document capability boundaries and proposed product priorities.

- Align product introductions, README and platform documentation around one local
  manuscript workspace for writing, reading, research, analysis and sharing.
  Keep the editor's unreleased status explicit across all seven public languages.

- Add native-only CodeMirror 6 manuscript editing with undo/redo, conditional
  autosave, explicit conflict states and local recovery copies. Preserve UTF-8
  BOM and uniform line endings; keep editor assets out of read-only exports.
  Revision-bound reading sessions preserve editor undo and expose the existing
  research-link review without changing retained evidence or silently re-anchoring.

- Replace the public homepage screenshot with a quiet light/dark product tour,
  directed zooms and focus annotations, localized captions and a text transcript.
  Respect reduced motion, explicit pauses and offscreen playback; offer AV1 with
  an H.264 fallback and a compressed poster.
  Refine the tour with video-synchronized typing captions and compact target
  markings instead of clipped panel outlines.
  Align homepage typography with manuscript headings and shared UI controls,
  reduce the hero footprint, and unify discovery into a tour-to-demo path.

- Separate synthetic example-project creation from screenshot HTTP fixtures.
  Provide a non-overwriting project generator with explicit manuscript/language
  configuration; public examples use that same ordinary project and exporter.
  Keep reviewed Pages publication wrappers independent of screenshot adapters
  and share their metadata/navigation with the public-domain examples.

### Documentation

- Document the proposed CodeMirror 6 manuscript editor against current source
  boundaries and primary research, including source fidelity, conflict handling,
  recovery, accessibility and revision-bound analysis acceptance criteria.

- Connect the product and documentation entrypoints to a browser workflow for
  linguistic text analysis. Distinguish automatically remembered reading
  preferences from explicitly applied project settings and saved research revisions.

### Fixed

- Keep flagged-passage review records passive: only the read action navigates.
  Remove inherited whole-row hover fills and jump tooltips from decision controls.

- Keep manuscript search available while scrolling; typing updates matches without
  jumping or leaving the overview. Explicit navigation targets the highlighted text
  and uses the latest query even before its debounce completes.
- Align analysis entry actions and give search controls the available row width.
  Share quieter Markdown editor focus, larger formatting targets and visible form
  actions; preserve native Tab navigation and checkbox-list continuation.

- Keep manuscript associations in the central Research review instead of a
  duplicate list above the prose. Soften reading-surface edges without blurring
  text, and align nested dossier actions on the same row.

- Keep the reading toolbar compact and bound chapter selection width in focus
  mode. Dark focus surroundings are quieter without dimming manuscript text.
- Track the paragraph containing the teleprompter reading position, synchronize
  its chapter selector and avoid smooth-scroll interference during playback.
  Use smaller initial text and restrained highlighting for long paragraphs.

### Documentation

- Consolidate legacy German wiki manuals into links to the English references;
  retain their URLs and localized product introductions. Clarify current package
  availability versus Linux-first packaging and future Rust evaluation, and add
  concrete exploratory linguistic workflows.

- Present manuscript revision and exploratory linguistic text analysis consistently
  across seven product introductions, README, manuals and automation summary.
  Add a reproducible CLI workflow and clarify interpretation and language limits.
- Add an optional browser-language suggestion to public introductions, with a
  saved explicit choice and accessible native language links. Preserve direct
  URLs and English technical documentation; tolerate unavailable local storage.
- Replace stale unreleased annotations for functionality included in 0.8.0
  across the operating manuals, preserving existing section links.
- Correct the public claim of independent app/interface language: the native
  dashboard follows its analysis profile; CLI report presentation is separate.

## [0.8.0] - 2026-11-10

### Fixed

- Handle Linux process exit between opening and reading `/proc/<pid>/stat`
  during managed stop/restart. Confirm that the process is absent before
  treating it as stopped; unreadable live processes remain explicitly unknown.

- Render passage-context icons as SVG instead of stringified DOM elements.
- Keep regenerated GIF previews within their existing size budget at five frames
  per second; full-quality MP4 walkthroughs retain their existing encoding.

### Documentation

- Replace the long English homepage with seven equivalent static product entries,
  native language navigation, reciprocal search metadata and shared generation checks.
  Introduce an ultramarine product presentation and keep technical manuals in English.
  Keep German entry-page return navigation in German and align the public mark
  with the shared action color. Use language-aware heading hyphenation on narrow
  article and guide layouts; keep long comparison-table labels within their columns.

- Align the README, documentation map and public landing page on seven interface
  languages, English-only technical documentation and the read-only English demo.
  Add short multilingual product introductions and clarify the scope of offline
  analysis independently of optional services.

- Complete reciprocal, self-referencing English/German language alternatives for
  the first-look guides and the literary research article; clarify the German
  entry page title for manuscript revision.
- Stage a public IndexNow ownership file for `/lixity/` and document post-deployment
  URL notification. This does not submit URLs or establish indexing.

### Changed

- Align the metric selector with the shared reader control typography and the
  exported reading surface with its adjacent context panel.
- Improve tense badge text contrast in both themes without changing chart colors.
- Share a stronger blue identity, clearer navigation and a distinct manuscript
  document surface across the local workspace and public Pages.
- Omit the dormant publication-settings editor from classic read-only report
  bundles, saving about 19 KB without changing chapters or the example size limit.
- Keep the sensory summary on the same spacing rhythm as other analysis content;
  prevent long mobile pacing summaries from squeezing their actual bars to zero width.


### Added
- **Pacing & Micro-Dynamics (`lixity.pacing`)**: Rolling sentence length analysis (`compute_rolling_asl`) with adaptive window size, sentence length coefficient of variation (`sentence_cv`), 12-point chapter condensed timelines (`pacing_curve`), and 8-level Unicode sparklines (`pacing_sparkline`) surfaced across CLI and Dashboard UI.
- **POS-Stratified Lexical Diversity (`lixity.diversity`, `lixity.analyzer`)**: Stratified moving-average type-token ratio (`stratified_mattr`) separating action vocabulary MATTR (`verb_mattr`) and descriptive vocabulary MATTR (`desc_mattr`) across chapter and corpus levels, surfacing lexical depth profiles in the Narration UI.
- **Multilingual Sensory Immersion Profiling (`lixity.showing`, `lixity.language_data`)**: 4-modality sensory perception cues (auditory, visual, haptic/thermal, olfactory/gustatory) compiled for all 7 supported languages (`de`, `en`, `fr`, `es`, `it`, `pt`, `nl`), measuring sensory cue density (`sensory_density`) and immersion ratio (`immersion_ratio`), exposed in CLI and Dashboard Narration views.


## [0.7.9] - 2026-11-05

### Documentation

- Rework installed CLI help into task groups, command examples and canonical
  manual links; clarify project defaults, output formats, service lifecycle,
  audio capture and writes, retention guards and action-specific options.
  Share command-help presentation while retaining argument grammar and aliases.

- Consolidate the operating documentation into linked workspace, CLI, audio and
  research manuals, with a task-oriented documentation map and an explicit first-session checklist.
  Preserve existing section links, centralize optional worker setup in Installation,
  and include the new manuals in Pages and the generated offline reference bundle.
- Correct outdated wiki shortcuts, analysis claims and research-storage instructions;
  route illustrated guides and wiki pages to the maintained manuals.


### Added
- Tokenized LaTeX math renderer and Obsidian-compatible Callout engine for research
  dossiers and evidence cards, supporting math environments (`matrix`, `cases`, `aligned`),
  balanced fractions/roots, greek characters, wikilinks `[[Target|Label]]`, text highlights `==...==`,
  strikethrough `~~...~~`, and collapsible callouts (`> [!NOTE]-`).
- Lightweight markdown editor component (`LixityMarkdownEditor`) integrated into the dossier
  revision workflow with formatting toolbar, keyboard shortcuts (Ctrl+B/I/K/H, Tab),
  smart list continuation, auto-closing bracket pairs, and real-time word/character count.
- Curated inline Lucide SVG icon library (`window.LixityIcons`) providing consistent icons
  across callouts, UI controls, navigation, and editor actions.
- Full JSON Canvas 1.0 (`https://jsoncanvas.org/spec/1.0/`) support: narrative scene storyboard
  export (`lixity canvas`), research dossier/claim/decision canvas export (`lixity research canvas`),
  and JSON canvas import into research candidate entities.
- Offline HTML article extractor (`lixity research extract-article`) parsing web articles into
  clean structured Markdown with metadata and research frontmatter, inspired by Defuddle.
- Obsidian-inspired Command Palette (`window.LixityCommandPalette`, accessible via `Ctrl+P`,
  `Cmd+P` or `Ctrl+K`) with live filtering across analysis metrics, research search, audio
  studio, export tasks and themes.
- Reader Context Sidebar with Backlinks automatically surfacing associated research dossiers,
  anchored historical evidence, claims and vocal direction cues when inspecting a manuscript passage.
- Dedicated Focus Mode keyboard toggle (`F`) providing serene, distraction-free reading with
  calm typography and optional inline metric reveals.
- Refined form and status design following Obsidian Minimal Theme aesthetics: quiet typography,
  standardized field spacing, live pulsing status dots for background synthesis and service states.
- Reader-only `--include-audio` exports verified existing chapter recordings with
  the shared player and WAV downloads. Matching uses the exact manuscript and
  export chapter cap; partial coverage is visible and empty selection fails.
  Static copies contain no voice references, profiles or service endpoints.
- Explicit `audio-import` binds a PCM chapter WAV to a supplied manuscript hash
  without claiming transcript verification or automatic alignment. Successful
  native chapter renders retain their completed audio for later reader export.
- Conditional `lixity-read-only-site/3`, `lixity-reader-publication/2` and
  `lixity-reader-audio/1` contracts for opted-in audio; default exports keep their
  existing schemas and never invoke synthesis.
- Portable author takes with explicit WAV/transcript metadata exchange and guarded
  Studio handoff; draft reading scripts remain distinct from confirmed transcripts.
- Teleprompter pronunciation and direction presentation reuses the canonical
  speech timeline, including all current range controls and safe IPA annotations.
- Optional offline IMS-Toucan worker for author references, German/English IPA
  overrides and structured profile/passage prosody; separate inference environment.
- Reviewed, backed-up audio settings `/5` upgrade and conditional direction,
  plan and timeline `/2` contracts for phonetic/prosody data. Existing profiles
  retain their engine and voice; unsupported controls fail explicitly.
- Capability-driven model controls and separate IPA/prosody editing in the shared
  audio dialog, without exposing internal reference identities.
- Central native model/endpoint/reference registry and shared worker transport;
  native status routing and reference-aware cache keys are corrected.
- Recording saves report activation separately and never silently switch engines.
- Recording status beside the start button and privacy-preserving browser-console
  diagnostics for failed microphone requests and audio initialization.
- A compact shared audio player with elapsed/total time, seeking, volume, mute
  and a measured frequency spectrum for playback and author-voice recording.
- Control-specific help throughout the native audio dialog.
- Comprehensive UI harmonization, design token adherence, and accessibility polish:
  - Standardized CSS tokens across speech player controls, modal forms, and teleprompter elements using semantic variables (`--surface-raised`, `--line-strong`, `--accent`, `--on-action`) instead of orphaned custom tokens.
  - Added responsive off-canvas drawer layout (`@media (max-width: 960px)`) and quick toggle button (`🏛 Dossiers`, shortcut `D`) in the Teleprompter view, preserving full reading runway width on smaller displays and mobile devices.
  - Integrated client-side PCM WAV capture with explicit take preview and WAV/JSON download from the teleprompter.
  - Hardened managed service startup in containerized environments by gracefully falling back when `XDG_RUNTIME_DIR` is not writable.
- Manuscript Teleprompter with vocal direction, phonetics, and synchronized dossier images:
  - Added dedicated Teleprompter mode in the manuscript reader view (`#reader-teleprompter`, keyboard shortcut `P`), featuring variable WPM auto-scroll (60–240 WPM), horizontal eye-level reading ribbon, and dynamic typography controls (`A−`/`A+`).
  - Automatically renders vocal direction cues (`audio-direction` instructions and pauses) as visual prompt banners inline above directed passages.
  - Displays pronunciation guidance using semantic HTML `<ruby>` annotations. Spelling substitutions and explicit IPA overrides are separate controls.
  - Synchronizes contextual historical images and dossier evidence in a split-screen sidebar using direct paragraph claim links, entity heuristics, and chapter atmosphere matching as the speaker scrolls through the text.
  - Includes integrated one-click hardware audio recording with live session timer and microphone gain controls.
- Integrated microphone settings and hardware level management in CLI and UI:
  - Added `lixity audio-microphone` (and subcommands `status`, `set`, `devices`, `calibrate`) to inspect hardware capture devices, display active ALSA gain, dB levels, and hardware limits, and directly set mixer gain.
  - Added dedicated Microphone & Level controls in the browser UI with live device selector, gain slider/numeric input, immediate gain apply, and interactive 8-second burst calibration with verdict badges and one-click recommended gain adoption.
  - Added `/api/audio-microphone` backend endpoints (GET status, POST actions `set_gain` and `calibrate`) and embedded microphone state in `/api/speech`.
- Phonetically balanced voice calibration texts and dual reference acquisition:
  - Added `lixity audio-reference calibration-text` providing standard international phonetic reference texts (IPA standard "Der Nordwind und die Sonne" / "The North Wind and the Sun" and compact pangrams) covering the complete phonemic and prosodic space.
  - Option A (Direct Recording with Teleprompter): `lixity audio-reference record --project PATH --calibration-text` displays the calibration text live in the terminal as a teleprompter, counts down 2 seconds, and automatically bounds and stores verified reference audio.
  - Option B (Synthetic Reference Generation): `lixity audio-reference generate --project PATH [--voice-description "..."]` synthesizes a reference sample from the phonetically balanced calibration text using VoiceDesign and registers it as an immutable project reference.
- Microphone calibration and direct recording (`audio-calibrate`, `audio-reference record`):
  - Added `lixity audio-calibrate` for automated microphone gain calibration and dynamic range analysis using pure stdlib arithmetic and ALSA/amixer hardware controls.
  - Implemented the 4-second prep / 8-second burst evaluation loop (3× POPP, 2× claps, 1× speech) with automated verdicts (`CALIBRIERT FÜR AUFNAHMEN!`, `ZU HEISS`, `MEHR LUFT ALS NÖTIG`) and recommended gain adjustments.
  - Added `lixity audio-reference record` to capture voice references directly from hardware via OSS capture tools (`arecord`, `pw-record`, `ffmpeg`), automatically normalizing to 24 kHz mono 16-bit PCM WAV and storing content-addressed reference records.
- Enhanced OSS media playback across UI and Research:
  - Added dedicated speech player controls with quick-access playback speed toggles (`0.8×`, `1.0×`, `1.25×`, `1.5×`) and ±5-second scrub buttons in the browser listening interface.
  - Added native HTML5 audio player rendering for research dossier evidence attachments (`audio/*`) alongside existing video playback.
- Retained F5-TTS project and transport contracts:
  - Existing `f5-tts` profiles, references, plans and cache entries remain readable.
    An explicitly operated compatible HTTP worker can still use port 8771.
  - Removed the nonfunctional bundled inference loader; it now fails with actionable
    guidance before importing models or downloading files. New-profile selection hides
    this unavailable path without converting existing voices.
- Single-narrator listening core and delivery reference modeling:
  - Enforced single-narrator integrity in `read-aloud` and `audio-direction`: passage directions shape delivery, pauses, and pacing, but cannot switch to an entirely different voice or cast foreign speakers.
  - Added `same_narrator` validation in `speech_direction.py`: reference engines (`qwen3-base`, `coqui-reference`, `f5-tts`) permit switching between distinct attitude and delivery references of the same speaker without triggering multi-voice casting conflicts.
  - Added localized `speech_narrator_conflict` error across all seven supported languages when a direction attempts to cast a different narrator.
- `audio-import-transcript` CLI command and ASR bridge:
  - Added `lixity audio-import-transcript` to convert external speech recognizer outputs (OpenAI Whisper JSON segments/words, faster-whisper, or raw timestamped word arrays) into valid, SHA-256 bound `lixity-audio-transcript/1` objects.
  - Automatically handles tokenization by language profile, sub-token proportional timing allocation, and non-overlapping monotonic timestamp sanitization for seamless `audio-verify` intake.
- Direct `-o` / `--output` atomic file writes in `audio-export-plan`:
  - `lixity audio-export-plan` and `read-aloud --ssml / --timeline` now respect `-o` / `--output` to directly and atomically write timeline JSON or W3C SSML to target files instead of routing solely to standard output.
- Explicit scene titles and project-configured titles in `scenes` JSON exports:
  - Each item in `scenes.items` and `scenes.planned_items` now includes an explicit `scene_title` field alongside `chapter_title`.
  - Automatically derives scene titles from leading Markdown headings (`##`, `###`), explicit `scene_analysis.titles` table definitions in project configuration, or clean fallbacks (`Chapter · Scene`).
- Universal `-o` / `--output` file export support across all analysis commands:
  - `lixity scenes`, `lixity motifs`, and `lixity characters` now accept optional `-o` / `--output` flags to atomically write reports or JSON directly to target files, harmonizing them with `pacing`, `dialogue`, `analyze`, and `style`.
- Batch reconciliation for manuscript research links:
  - Added `--accept-all-moved` to `lixity research reconcile-manuscript` to batch-accept all uniquely resolved, relocated, or adjusted link anchors in one single atomic transaction when manuscript source hashes update after prose edits.
- Rich LaTeX math and formatting rendering engine in dossiers and markdown prose:
  - Offline, zero-dependency LaTeX parser converting math expressions (`$...$` and `$$...$$`) into clean, accessible mathematical typography. Supports fractions (`\frac`, `\dfrac`), square roots (`\sqrt`), sub- and superscripts (`^`, `_`), Greek letters (both lowercase and uppercase), mathematical operators (`\sum`, `\prod`, `\int`, `\times`, `\cdot`, `\approx`, `\le`, `\ge`, `\ne`, `\in`, `\infty`, `\partial`), mathematical functions (`\ln`, `\log`, `\sin`, `\cos`, `\exp`, `\det`), matrix and alignment environments (`\begin{aligned}`, `\begin{matrix}`), blackboard bold (`\mathbb{R}`, `\mathbb{N}`), and variable italics.
  - Full support for LaTeX prose styling: `\textbf{...}`, `\textit{...}`, `\emph{...}`, `\underline{...}`, `\texttt{...}`, `\sout{...}`, `\textsc{...}` alongside standard CommonMark markers.
  - GitHub-style alert callout boxes (`[!NOTE]`, `[!TIP]`, `[!IMPORTANT]`, `[!WARNING]`, `[!CAUTION]`) with distinct semantic accents, SVG icons, dark-mode tints, and localized titles (`Hinweis`, `Tipp`, `Wichtig`, `Warnung`, `Achtung`).
  - Tab-separated values (TSV) and pipe table auto-detection rendering formatted, responsive tables with sticky headers.
  - Responsive companion reader styles in `.workspace-reader-panel` preventing horizontal overflow while preserving mathematical expressions and tables during side-by-side manuscript reading.
- Central social presence cross-linking and discovery:
  - Added official Mastodon (`@lixity@mastodon.social`) and Bluesky (`@lixity.bsky.social`) profiles to `pyproject.toml` (`[project.urls]`) for PyPI presentation and `README.md` community badges.
  - Connected Schema.org JSON-LD `sameAs` entity metadata across `SoftwareApplication` and `WebSite` in `docs/index.html` linking Mastodon, Bluesky, GitHub, and DEV.to.
  - Interlinked social resource navigation in `docs/blog/index.html` and markdown alternates.
- Interactive Research Grounding ("Abgleich") dashboard:
  - Replaced the previous plain text comparison output with a clean, structured KPI card grid showing Jaccard similarity index, Szymkiewicz-Simpson overlap coefficient, unique shared lexeme types, and filtered content word counts.
  - Interactive segmented vocabulary explorer for shared terms, Dunning G² keyness terms, and exclusive source terms. Term chips feature detailed frequency tooltips and click-to-search integration that immediately reveals occurrences in the manuscript.
  - Interactive, sortable per-chapter evidence grounding table featuring sticky headers, sortable columns (chapter, words, tokens, density), proportional micro progress bars for grounding density (‰), chapter top terms, and one-click jump-to-chapter navigation in the reader view.
  - Collapsible style and register contrast breakdown comparing Average Sentence Length (ASL), Dialogue Ratio, Guiraud R, and Yule's K between source and manuscript.
  - Shifted static statistical disclaimer walls into contextual tooltips with localized descriptions across all seven supported languages.
- Universal table consolidation & interactive sorting:
  - Consolidated `.table-wrap` components across all views with sticky headers (`position: sticky`), accessible sortable headers (`th.sortable`, `aria-sort`, Enter/Space keyboard activation), proportional visual bar cells (`.table-bar-cell`), tabular numeric alignment (`.num-right`), and hover row highlights.
- Global tooltip and keyboard shortcut coverage across research surfaces:
  - Added localized tooltips, titles, and keyboard shortcuts (`Enter`, `Escape`) to all research filter inputs, search fields, grounding selectors, and refresh controls across German, English, French, Spanish, Italian, Portuguese, and Dutch.
- Global keyboard shortcut recognition and formatting in the central tooltip engine:
  interactive controls declaring `aria-keyshortcuts` or parenthesized shortcut
  conventions now render crisp `<kbd>` key badges in the tooltip header across
  desktop and touch viewports. Shortcut triggers without extra `data-help`
  gracefully display their accessible name alongside formatted keys without
  duplicate copy stutter.
- Wired explicit `aria-keyshortcuts` and localized tooltips across core interactive
  surfaces: manuscript text search (`Enter` next, `Shift+Enter` previous, `Escape`
  clear), modal close and cancel dialogs (`Escape`), manuscript inspector close,
  workspace split divider (`←`/`→`/`Home`/`End`), claim link action (`Alt+L`),
  and reader focus toggle (`Escape`).
- Central consolidation of repetitive patterns and hardcoded values across the engine:
  - Unified Markdown HTML comment stripping through `COMMENT_STRIP_RE` and
    `strip_html_comments` across `markdown_parser`, `analyzer`, and `scenes`.
  - Canonicalized character and register name/alias length bounds
    (`MAX_CHARACTER_NAME_CHARS`, `MAX_CHARACTER_ALIAS_CHARS`, `MAX_REGISTER_NAME_CHARS`)
    across `characters`, `registers`, and `scenes`.
  - Harmonized structural defaults between `models.py` (`CorpusConfig`),
    `sentences.py`, `dialogue.py`, and `pacing.py` (`SHORT_SENTENCE_MAX`,
    `MEDIUM_SENTENCE_MAX`, `LONG_SENTENCE_MAX`, `DEFAULT_SHORT_TURN_MAX_WORDS`,
    `DEFAULT_LONG_TURN_MIN_WORDS`, `DEFAULT_DIALOGUE_PARAGRAPH_SHARE`,
    `DEFAULT_HOOK_SHORT_SENTENCE`, `DEFAULT_MONOTONY_MIN_RUN`).
  - Standardized module defaults for lexical diversity (`DEFAULT_MTLD_THRESHOLD`,
    `DEFAULT_MATTR_WINDOW`) in `diversity.py` and repetition analysis in `motifs.py`.
  - Dynamically resolved UI settings preset choices from `FingerprintThresholds.presets`.
- Streamlined research record cards across dossiers, sources, claims, and decisions:
  dossier section headings over four entries collapse into a compact expandable
  disclosure (`+N more…`), excerpts clamp cleanly to two lines without title
  stutter, claim scope badges and monospace record IDs provide scannable hierarchy,
  and cards feature distinct borders and subtle elevation to replace unformatted text
  walls with a structured workspace catalogue.
- Interactive public demo expansion: configured dossier collections (`Warehouse Case Files`,
  `Atmosphere & Geography`) and register target profiles (`harbour_investigation`, `quay_action`)
  in the live demo project to showcase collection filtering and chapter register target corridors.
- Editorial threshold presets (`balanced`, `developmental`, `line_editing`,
  `conservative_by`) accessible via `--preset` on analysis commands (`analyze`,
  `profile`, `style`, `dashboard`, `pdf`, `build`) and through the native Settings
  dialog (`#set-threshold-preset`), tailoring deviation cutoffs (`z_mild`,
  `z_strong`, `fdr_q`, `fdr_method`) to macro-editing (developmental), line
  polishing, or conservative exploratory review.
- Chapter register starter templates (`dialogue_scene`, `action_scene`,
  `reflective_narration`, `epistolary`, `technical_record`) accessible through the
  Settings register editor (`#register-template-select`), pre-populating target
  corridors for dialogue share, ASL, TTR, and nominal density.
- Configurable structural and cadence thresholds in `CorpusConfig` / `[tool.lixity]`
  (`short_sentence_max`, `medium_sentence_max`, `long_sentence_max`,
  `short_turn_max_words`, `long_turn_min_words`, `dialogue_paragraph_share`,
  `hook_short_sentence`, `monotony_min_run`), reducing hardcoded limits and
  allowing fine-tuning per project or genre.
- Dialogue cadence and voice-contrast measurements in `dialogue_report`, CLI
  `dialogue`, and the Quoted passages overview panel: short quoted spans
  (`1–12` words, `short_turns`, `short_turn_pct`), long monologue spans
  (`>= 80` words, `long_turns`), and sentence-length contrast between recognized
  quoted spans and unquoted narration (`dialogue_asl`, `narration_asl`,
  `asl_contrast`, reported as `null`/`–` when either side is absent).
- Paragraph-local flow and cohesion signals in `pacing_report`, CLI `pacing`,
  and the Pacing & scenes overview panel: consecutive repeated sentence-start
  runs within paragraphs (`>= 3` sentences starting with the same word,
  `repeated_start_runs`) and adjacent-sentence content-word overlap
  (`adjacent_sentence_pairs`, `sentence_overlap_pct`).
- `audio-export-plan` and scoped browser JSON/SSML downloads share the manuscript
  direction planner. `lixity-audio-timeline/1` retains source/substitution
  provenance, voice choices, delivery and pauses; SSML reports unsupported
  portable controls and does not invent speech timestamps.
- Explicit OpenAI-compatible HTTP speech providers with model/voice bindings,
  optional credential environment-variable names and declared instruction
  support. Settings schema `/4` uses the reviewed backup migration; existing
  native profiles, references and cache keys retain their behavior. Bounded WAV
  responses share normalization, tempo, pauses, caching and atomic publication.
- Local `audio-inspect` and `audio-verify` for chapter WAV/FLAC/MP3 signal
  observations and optional plan comparison using an audio-hash-bound timed
  transcript (`lixity-audio-audit/1`). No speech recognition runs; missing text
  or pause evidence remains unknown.
- `audio-reference inspect` and a `quality` object in `audio-reference create`
  report level, noise floor, clipping and spectral bandwidth of a voice
  reference (`lixity-audio-reference-quality/1`), with uncalibrated heuristic
  notes for band-limited, gated, clipped or noisy recordings; formulas in
  `docs/METHODS.md`, limits in `docs/STABILITY.md`.
- Experimental local German Coqui Thorsten VITS audio and optional OpenVoice V2
  reference-voice conversion, reusing project references and speech planning;
  saved profiles require audio schema `/3` and a reviewed backed-up migration.
- An explicit per-render control in the audio dialog to ignore passage direction
  for a preview or chapter without modifying saved direction.
- Privacy-preserving audio diagnostics for job lifecycle and render segments,
  including independent diagnostic IDs and PCM timeline positions.
- Optional project-wide pronunciation rules in audio settings schema `/2`, with
  per-profile overrides and opt-in whole-word/case-insensitive matching; `/1`
  remains unchanged and version 0.7.7 cannot read `/2`.
- `audio-direction add` resolves chapter and source line to a guarded passage
  direction without manually supplying snapshot hashes.

### Changed
- README, the public landing page and English/German tours now connect manuscript
  reading, research, analysis, spoken review and deliberate export choices.
  Audio setup and calibration descriptions distinguish measured checks from
  unverified transcripts, automatic alignment and acoustic-quality claims.
- Author-voice references are saved only through the studio's reviewed transcript
  workflow. Teleprompter takes keep their WAV download and studio entry point.
- The native audio dialog assigns recording and reference management, voice
  profiles and service configuration, direction and output, and microphone
  hardware controls to four separate tabs instead of repeating sections.
- Restructured Project Settings & Overview: Reorganized project settings into elevated, distinct cards sorted by editorial workflow priority. Deduplicated audio actions by consolidating configuration into the primary workflow panel and cleanly collapsing large output file inventories into compact disclosures.
- Sidebar Tooltip Ergonomics: Fixed sidebar tooltips (`.workspace-shell`) position smoothly to the right of the trigger button, preventing overlap with vertically stacked navigation tabs and eliminating pointer interception seams.
- Screenshot Framing: Expanded `dashboard-reader-focus.png` capture frame to display complete paragraphs with balanced margins, eliminating cropped text in documentation and website walkthroughs.
- Analysis overview sections, KPI groups, and work markers are ordered by
  editorial workflow relevance: flagged passages and open work markers first,
  followed by pacing and scenes, dialogue and sentence craft, character
  mentions and local phrase echoes, and corpus style comparison and the chapter
  matrix.
- Analysis navigation links and the return and audio controls offer localized
  contextual help on hover or keyboard focus, reusing the shared tooltip.
- Project creation rejects invalid or automatic language values with HTTP 400
  before writing files instead of silently selecting English. An omitted
  language still inherits a concrete server language; an automatic session
  requires an explicit concrete choice.
- The mean number of ending cues is labeled per chapter ending, its actual
  denominator, in the dashboard and CLI.
- Style-dimension cards explain the raw axis cutoff relative to each axis's
  sample standard deviation; scores, flags and the passport contract are
  unchanged, and numerically degenerate axes are reported as unknown.
- With the default Spanish tense patterns, an adjacent detected present `haber`
  and regular past participle contributes one past cue instead of also counting
  the auxiliary as present. Existing Spanish review decisions are invalidated
  when their analysis context changes; custom tense patterns are unaffected.
- Quote-paragraph shares now use the same chapter-wide recognized quotation
  spans as quote-word counts, including quotations that cross paragraph breaks;
  overlapping spans count once within each paragraph. Configured patterns with
  multiple capture groups use their first group consistently across analysis
  instead of failing during quote-word counting.
- The local source importer preserves new drafts during pending operations,
  rejects an ambiguous file plus pasted text, and remains available alongside
  Zotero sources. It uses shared form labels and inline status feedback.
- Project creation requires an explicit supported language when the configured
  choice cannot be preserved. Import-preview counts are labeled estimates;
  runtime audio job locations stay unknown when the API cannot determine them.
- Static reports offer native chapter links and avoid advertising unavailable
  JavaScript controls. FDR selection and register exemptions are included in
  heatmap accessible names; scene errors retain their technical detail behind
  a localized explanation. Overlapping name patterns are disclosed.
- The style space counts chapters reaching an axis cutoff and can cycle through
  those points without ranking literary quality. Name-mention columns provide
  contextual definitions, and the signal-group method is available on demand;
  signed signal-group differences use a centered blue–orange scale.
  Shared tooltips remain visible while their trigger has focus or is hovered.
  Touch-opened evidence cards wait for the originating click before appearing;
  mobile dock focus restoration respects newer focus choices.
- The analysis overview links directly to the 3D style space when chapter
  scores are available. A legend distinguishes the axis cutoff from the
  selected chapter, even when both apply; loading directions show explicit
  signs. Incomplete dimensions identify display-only zero coordinates.
- The app and audio dialog groups speech services, queue and open projects,
  distinguishes a successful status refresh from worker readiness, and uses
  the shared dialog footer spacing. The demo's reading guide stays with the
  manuscript view, and documentation screenshots end at complete task boundaries.
- Workspace guidance and metric tooltips are shorter in all seven languages,
  while preserving counting definitions and heuristic limits. Reading and
  analysis controls are grouped by task; the overview now links to quoted text,
  names, pacing and signal groups. Research capture precedes the source catalogue,
  setup follows the working views, and claims use one list/timeline switch.
  Threshold reset stays with its controls; audio export and synthesis have
  separate groups, with audio actions outside the project settings form.
- Analysis labels describe the observed share of feature comparisons within the
  threshold, replacing the unsupported "stylistic cohesion" claim. Tense review
  guidance explains lexical patterns, auxiliary/infinitive ambiguity and the
  effects of quotations and retrospection in all seven interface languages.
  Those presentation changes do not alter the underlying calculations.
- Coqui/OpenVoice guidance states that the converter mainly changes timbre,
  inherits the reference's bandwidth limit and that the 1.2 playback default is
  not tuned for Thorsten.
- Installation guidance explains same-version checkout/tool drift, verified local
  wheel replacement, preservation of optional dependencies and scoped cleanup.
- Audio guidance now follows the selected engine, distinguishing Coqui's local
  runtime and direction limits from Qwen-specific behavior.
- Native audio previews now include all planned segments of the first anchored
  paragraph, enforce the same 6,000-character preview limit as selected passages,
  and fail explicitly when no paragraph or list item can be selected. The
  bounded context excerpt identifies the selected original passage; `truncated`
  is false when that passage is fully rendered, even if its display excerpt is
  abbreviated. Chapter rendering is unchanged.
- Documented the local recording, excerpt, transcript and short preview workflow
  for an explicit Base reference voice.
- CLI, audio dialogs and guidance clarify VoiceDesign continuity, the role of
  passage direction and the trade-offs of reference-based voices.
- CLI audio progress includes a rough remaining-time estimate after two segments.
- Counted-text visibility is remembered per analysis measure; the chapter-strip
  emphasis control and comparison counts use descriptive, neutral labels.
- Tense-pattern badges no longer overlap an active metric overlay; the passage
  inspector and chapter counts follow the configured tense severity threshold.
- The audio dialog distinguishes opening chapter output from starting its render
  and keeps progress and error messages visible while scrolling.

### Fixed
- Keep authored HTML inert inside dossier inline, display and matrix formulas;
  preserve literal angle brackets and matrix cell boundaries while formatting TeX.
- Direct-file reader playback keeps the native audio path instead of entering a
  Web Audio graph that Chromium can silence for local-file origins. The player
  reports spectrum unavailable; hosted copies retain measured frequency display.
- Teleprompter imagery now resolves canonical anchored dossier revision pins and
  retained image versions through shared helpers, with bounded detail caching,
  stale-context guards and explicitly labelled title/tag suggestions.
- Chapter profile quotation and function-word shares aggregate integer counts
  before rounding, avoiding drift from already-rounded paragraph percentages.
- Invalid configured cue expressions and signal/motif patterns fail validation
  before analysis instead of raising a late regex traceback or replacing output.
- Reject custom word patterns with multiple capturing groups at configuration
  validation, preventing tuple-valued tokens from crashing analysis; existing
  whole-match, single-capture and explicit-flag behavior is preserved.
- Retired the unusable experimental bundled F5 inference loader with an explicit
  runtime error; retained profiles, references, export/cache data and HTTP transport.
- Teleprompter literal manuscript markup is rendered as text, and planned cues
  include pause-only and structured directions instead of only the first instruction.
- Static reports and curated publications omit inactive teleprompter assets,
  keeping the published examples within their existing page-size budget.
- The global function-word overview now uses the corpus token share, including
  blockquotes and prose before the first chapter. Older metric payloads without
  that aggregate display an unavailable value instead of a paragraph average.
- Showing-cue comparisons reuse the shared stable standardization and mean
  primitives, keeping finite zero-MAD fallback scores at large numeric scales.
  Chapter-deviation rankings also reuse the stable mean, avoiding intermediate
  sum overflow when the final mean remains finite.
- Shared form fields, headings, disclosure spacing and dialog bounds now align
  across Project, Research and audio, including narrow screens. Services and the
  audio queue join voice and microphone configuration under Project settings.
- Author recordings and research references use names, excerpts and explicit
  unavailable labels instead of opaque identifiers; stored IDs and revision pins
  remain unchanged. Export limit feedback shows localized measurements.
- Browser test launchers mute desktop audio while preserving playback checks.
- Help popups in blurred native dialogs use the correct coordinates and remain
  readable within the dialog in Firefox and Chromium.
- Audio tabs start at the top of their section, preserve feedback when reselected,
  and enable recording only after the project's settings and reading text load.
- Opening the reader without a fragment no longer looks up an empty element ID.
- Native manuscript pages permit same-origin microphone capture after browser
  approval; the HTTP permissions policy no longer blocks author-voice recording.
  Other pages and exported HTML keep microphone access disabled.
- Author-voice recording reports denied browser microphone access with recovery
  guidance, guards pending requests and stops capture when leaving its surface.
  Takes use the required 24 kHz mono WAV format, enforce the reference duration
  limit, allow transcript corrections and reload the updated project after saving.
- Teleprompter context reads run only on explicit opening, with current project
  and source identifiers; page load no longer sends invalid audio/research requests.
- Local HTTP listeners reject a second live listener on the same port. Address
  reuse still permits restart after close; port sharing is no longer enabled.
- `lixity research find-anchor` and manuscript commands report helpful guidance instead of confusing mutually exclusive errors when positional `PATH` and `--manuscript` are both provided or project defaults apply.
- Unified project settings layout and eliminated inconsistent spacing:
  - Standardized `#controls` with a clean 1.5rem (`var(--space-5)`) vertical rhythm across the Project panel.
  - Flattened nested NDA draft panel into a cohesive card, eliminating double-margin and double-border collisions.
  - Harmonized `.settings-section` fieldsets and `.settings-advanced` disclosure accordions into consistent enclosed cards with subtle hover feedback and clean spacing.
  - Aligned `.setting-field` labels, full-width controls, and hints (`.ctl-note`) with consistent 1.45 line-height and muted tone.
  - Added dedicated top-border breathing room (`padding-top: 1rem`) above form actions (`.settings-actions`) so the save button is distinct from settings fields.
- `read-aloud --ssml` and `--timeline` imply export-only behavior, preventing
  accidental synthesis. Exports do not require retained native reference audio
  or worker readiness; unsupported synthesis controls still fail explicitly.
- The project import dialog rejects unsupported files and multiple-file drops
  with guidance in all seven languages. Rejected selections clear the previous
  preview and invalidate pending reads so an earlier manuscript cannot be
  imported accidentally. Guidance appears beside the file picker, and the same
  file can be selected again after a failed attempt.
- Research search submits with Enter and preserves literal source text when
  highlighting matches, including ampersands and HTML-like text. Result metadata
  uses a readable foreground color in light and dark themes.
- Audio plan previews keep the SSML export action outside the numbered segment
  list so assistive technology receives a valid list structure.
- Coqui worker no longer warns about the expected discard of the phonetic tie
  bar, non-syllabic mark and typographic quotation marks; other discarded
  characters are reported by code point only.
- CLI messages for `--reference-id`, missing references and delivery
  instructions named only Qwen Base although `coqui-reference` uses the same
  controls.
- Reloading a workspace notices external project configuration changes and
  refreshes its context token without overwriting a concurrent change.
- Qwen Base reports incompatible passage text direction with an actionable,
  localized message; ignoring direction remains an explicit per-render choice.

## [0.7.7] - 2026-10-28

### Added
- Reference-based Qwen3-TTS 1.7B Base voices: explicit private project-local
  WAV/transcript references, guarded CLI and browser profiles, reference-bound
  segment caching and explicit per-passage voice selection. Base rejects delivery
  instructions it cannot interpret; it does not infer character speakers.
- Post-synthesis FFmpeg tempo factors for Qwen audio, preserving explicit pauses
  and unmodified cached model segments. New default profiles use 1.2; existing
  saved or formerly omitted values retain their previous meaning.
- Opt-in corpus evaluation of German quotation cues against the separately
  obtained REDEWIEDERGABE corpus and French syllables against Lexique; neither
  corpus is bundled or a representative contemporary literary benchmark.
- The UD token-feature checker reports aligned finite-verb true/false positives,
  false negatives and coverage separately, including false positives on gold
  nonverbs; previous tense-feature denominators remain unchanged.
- Optional local PhonItalia 1.10 benchmark reports aggregate Italian syllable
  agreement and the source digest without bundling or downloading the lexicon.
- Reader websites can explicitly include selected chapter or language
  measurements, or a fuller analysis of capped chapters. Opt-in exports use
  `lixity-read-only-site/2`; the synthetic reader demo shows chapter measurements.
- CLI audio status, fresh paragraph previews by source line and opt-in segment
  progress; long renders reject changed source, settings and active direction.
- Experimental Qwen3-TTS 1.7B VoiceDesign profiles with an explicit voice description, separate model identity and a shared CLI/native audio path. The matching offline worker must be started explicitly.
- Model-independent project-local passage direction with exact paragraph/range
  anchors, saved voice selection, free-form delivery, explicit PCM pauses,
  stale/overlap guards and idempotent atomic saves. CLI `audio-direction`,
  `read-aloud --plan-only` and the seven-language native Audio dialog share one
  planner for previews and chapter renders; Qwen retains its existing full model.

### Changed
- Dossier edit files accept LF and CRLF control headers without changing the
  saved body, including on Windows.
- Passage review links back to its exact saved decision; unmatched decisions
  for the current manuscript are reported and retained in UI and CLI.
- The normal-model threshold expectation is labeled as a model reference,
  not an empirically established count of false findings.
- Tagged releases run reusable full source and browser checks on the same
  commit before publication. Local and cross-platform checks remain separate.
- Style JSON schema 5 replaces the misleading exchangeability verdict and
  averaged lag with nullable, per-feature order indicators and chapter coverage.
  Missing chapters are not treated as adjacent; segmentation reports missing
  data and distribution comparisons preserve the original chapter midpoint.
  Zero-MAD references no longer create artificial standardized scores or enter
  consistency and FDR; available ordinal contrasts are retained separately.
  Flags remain exploratory.
- Showing comparisons with fewer than three sufficiently long chapters now
  report unavailable component scores and means instead of artificial zeros;
  their raw chapter measurements remain available.
- Research source analysis counts only available standardized comparisons in
  its baseline coverage; zero-MAD features are excluded.
- The default German tense heuristic no longer guesses past tense from arbitrary
  `-te/-ten/-test` endings, avoiding adjective false positives; selected cues
  such as `übt` are added. Unlisted regular past forms may now be missed and
  other ambiguities remain. Recompute comparisons; retained observations with
  saved decisions become stale, while disappeared observations are unmatched.
  Existing review storage is preserved.
- Reading website export retains choices within the current project context,
  clears source-file consent when the profile changes and rejects stale downloads.
- Pronunciation replacements can be filtered and edited individually, with
  explicit save/discard protection for project audio drafts. Speech control
  semantics and Qwen adapter capability declarations share one implementation.
- German paragraph-layer reports localize their explanations. Empty selections
  explain actual chapter comparison limits and show a shell-quoted command for
  full evidence; versioned JSON contracts and measurements remain unchanged.
- Audio extraction retains full-source line identities and configured chapter
  boundaries. Direction is resolved before pronunciation replacement and input
  segmentation; multiline delivery instructions normalize to single-line text.

## [0.7.6] - 2026-10-27

### Added
- Explicit Qwen attention and bounded codec-chunk controls, inference-mode
  execution and non-sensitive resolved worker runtime diagnostics for measured
  CPU/CUDA tuning of the same full 1.7B checkpoint.
- Explicit offline grammatical tense analysis in seven languages with installed
  spaCy models or explicit French/Italian Stanza CPU profiles,
  central verb-group composition, chapter-bounded quotation scope, exact evidence,
  model/version review identities and explicit unresolved forms. Scientific
  verification tools distinguish UD token-feature checks from verb-group tests. CLI, native UI,
  scenes and exports share the same implementation; no model download or fallback.
- One-origin native project views with independent tab contexts, scoped API and
  artifact routes, explicit expired-view handling and a bounded shared audio FIFO.
- Native app/audio operational overview with actual local/Jetson model health
  probes, open views and content-free queue states.
- Passage-specific tense review with exact counted cue ranges from the shared
  backend, keyboard-accessible cue navigation and explicit unavailable mappings.
  Mixed/switch triggers precede collapsed counts, help and other paragraph values.
- Explicit worker-only CPU decoder placement for CUDA Qwen inference, retaining
  the same 1.7B checkpoint and portable voice profiles without automatic fallback.
- Per-render local/Jetson Qwen selection in the CLI and native audio dialog,
  using fixed loopback endpoints and an operator-configured SSH forward without
  embedding machine addresses in portable project voice profiles.
- Shared bounded Qwen segment reuse for retrying long CPU renders in the CLI and
  native chapter dialog, with explicit fresh-render controls. Completed segments
  survive failed/cancelled runs; previews remain fresh and final output stays atomic.
- Project-only audio profiles shared by CLI and the native Audio & voices dialog,
  with explicit narrator presets, supported delivery controls, pauses and literal
  pronunciation settings. Draft previews, saved-profile selection and cancellable
  chapter jobs use one validated backend path; read-only snapshots cannot render.
- Optional offline Qwen3-TTS 1.7B CustomVoice worker with explicit CPU/CUDA modes,
  bounded local transport and no automatic model download or backend fallback.
- Single-commit publication batching in `reconcile-manuscript` (parsing manuscript
  paragraphs once and committing all accepted link updates in one transaction) and
  extended `revise-batch` support for source-verified `manuscript_claim_link`
  anchor updates and `decision_acknowledgement` operations.
- Named dossier collections with explicit reading order (`[dossier_collections]`),
  supporting multi-collection membership, unassigned/unavailable visibility,
  portable archive round-trips, read-only website exports, CLI (`dossier --collection`,
  `--set-collection`, `--delete-collection`) and native UI/companion filtering
  without revising dossier records or invalidating pins.
- Configured manuscript terms and props (`[terms]` and `lixity research terms`),
  deriving read-only source-bound candidate occurrences for preferred forms,
  aliases and chapter-scoped alternatives with explicit overlap, out-of-scope and
  Unicode normalization/casefold ambiguity flags and guarded reader navigation.
- `--quote` aliases for manuscript anchor lookup and explicit quote replacement.
- Active manuscript-link duplicate protection across library, CLI and native UI,
  preserving distinct occurrences and reporting the existing association without
  rewriting retained links or confusing duplicates with stale archive state.
- Current-chapter locations for retained manuscript quotations in shared review,
  CLI text/table/JSON and native/read-only UI. Locations follow uniquely moved
  passages without modifying dossier bodies or accepting changed anchors.
- Read-only **Inspect candidate passage** in manuscript review opens uniquely
  moved/adjusted quotations before accepting a re-pin, reusing existing resolved
  offsets and guarded source context without changing saved associations.
- Explicit website preflight in CLI and native UI measures prepared HTML/ZIP/file
  sizes and reports unavailable, unpackaged and unattributed dossier media without
  writing or downloading. Mobile rendering and rights verification remain explicit
  unchecked boundaries.
- Manifest capacity increases to 100,000 entries while retaining the 32 MiB
  canonical-object limit; capacity warnings follow the current limit.
- Compressed manifest storage with explicit verified-backup migration, atomic
  layout switch and retryable cleanup. Canonical hashes, HEAD, source bytes and
  accepted revisions remain unchanged; portable backup transport stays stable.
- Guarded `research media-context` corrects retained-media attribution without
  duplicating source identities or media bytes; explicit dossier `--preamble`
  reads/edits and image `--missing-provenance` filtering reduce repair work.
- Explicit project-local tense review decisions shared by native UI, CLI and
  backend: kept/changed-by-author/deferred, guarded by source, analysis and review
  identities; stale decisions do not count as completed. Filters and next-visible
  passage support reading without automatic tasks. Private review state stays
  out of manuscript prose, research records and reading exports.
- `dossier-image --batch` previews a bounded explicit image manifest and applies
  all captures with one dossier revision or none. Optional item hashes bind
  reviewed bytes; relative paths resolve beside the manifest. `dossier-media`
  exposes the existing PDF/MP4/WebM attachment transaction from CLI.
- Versioned PDF/MP4/WebM dossier attachments reuse the image capture dialog,
  immutable source/context records and guarded dossier revision transaction.
  Shared full/section/history/source and reading-site views show document
  download cards and native video controls. Media is limited to 50 MiB, with
  bounded container checks, single-range native reads and explicit original-file
  inclusion in exports. Video/retained-only PDF opts into record/manifest v9; older readers reject
  those archives. Existing PNG/JPEG interfaces and accepted record bytes remain
  unchanged; attachments do not manufacture extraction or linguistic scores.

### Changed
- Remove Piper completely from rendering, native controls and CLI; use the full
  Qwen3-TTS 1.7B CustomVoice model for all audio. Removed profiles require explicit
  preset choices through a read-only migration preview and backed-up apply.
  Removed Piper-only renderer arguments and exact-speed CLI flags have no silent replacement.
- Separate pure multilingual verb rules from parser adaptation, dependency
  composition and scoped evidence/cache ownership without changing measured results.
- Curated reader/companion exports omit inactive workspace controllers and omit
  the offline diagram library when their prepared content cannot request it.
  Later-revealed diagrams retain the library; media, citations and offline reads
  continue through the shared components.
- Native and review-site adapters share supplementary report assembly while
  retaining their character-validation policies and existing public results.
- Documentation disclosure styles no longer leak into embedded workspaces or
  reports through the public Pages wrapper. Native reader controls retain the
  same appearance; demo privacy guidance reflects optional remote processing.
- Reduced the agent discovery index and generated operational reference bundle,
  linking setup, architecture and history instead of repeating them. Current
  audio guidance now describes shared CLI/native profiles and optional Qwen.
- Removed retired screenshot capture paths and reused the existing Python fixture
  runner in five browser suites; the reviewed screenshot catalogue stays canonical.
- Local read-aloud uses constant neutral delivery and explicit speed rather than
  sentence-length pacing or inferred emotions. Shared Markdown prose includes
  quoted blocks and list items; long inputs retain their text across bounded
  segments. The default German voice is single-speaker Thorsten.
- Audio generation rejects missing/failed segments, mismatched PCM, invalid
  chapter/speed selection and unavailable MP3 conversion. Streamed atomic output
  preserves an existing listening copy when synthesis or conversion fails.
- Native passage research and offline exports share a bounded backend context
  projection from one archive snapshot, grouping dossier/claim pins and decisions
  centrally. Opening a passage context no longer fetches separate record versions
  or joins them in the browser; malformed/unavailable data remains explicit.
- Shared control hover/pressed feedback keeps click targets stationary, fixing
  a mobile export retry button that oscillated at the pointer edge.
- Passage context closes on a different chapter/passage or deliberate reading
  beyond the inspected paragraph. Tool switching uses the requested passage;
  compact return navigation leaves record metadata in its viewer.
- Heuristic tense marks expose a labelled, keyboard-accessible review action
  independent of the selected measurement layer.
- Consolidated shared document typography, status recipes and surface/marker
  tokens while retaining token → component → view stylesheet ownership.
- Shorter reading, analysis and manuscript-link help in all seven UI languages;
  storage guidance names retained data instead of promising a format-7 upgrade.
  Manuscript CLI help separates preview, acceptance flags and partial success.
- Distinguish saved manuscript research references from metric overlays through
  neutral dotted marks, explicit localized Research labels and book icons.
  Research context keeps a neutral document identity alongside analysis colors.
- First-analysis help uses three direct actions: choose a measure, inspect a
  counted-text example, and explore the current passage. Opening help remains
  inert; the shorter panel reuses existing reader controls and focus handling.
- Dossiers share a source-order reading surface across research and record
  inspection. Repeated/nested headings retain their order and levels; unique
  section edits stay at the heading. Maps join the contents, media use the
  shared toolbar, and supplemental dossier actions follow the reading content.
- Contributor guidance uses one current product path with reviewed release
  migrations instead of permanent legacy UI modes or compatibility branches.
- Map detail navigation brings the selected geographic entry and its context
  into view, including later entries with repeated names on mobile. The shared
  dossier editor explains route coordinates, saving and playback limitations.
- The strongest tense stage is neutrally labelled “strong difference” instead
  of “strong friction”. Flag rows explain their real tense markers/switch
  criteria and prioritize reading instead of directly generating To-dos.
- Reader-first analysis adds voluntary, initially closed guidance with
  Analysis Off / no metric / selected metric states, shared localized action
  names and explicit paragraph-versus-chapter comparison scope. Focus and overview
  hide it without resetting display choices. Overview passage selection exposes
  its existing tense-flag/opening fallback reason. `profile --help` adds a short
  source-line/counting workflow without changing metrics, thresholds or JSON.
- Public introduction and first-look guide lead with one revision question
  rather than a feature inventory. The demo's chapter-2 task uses native
  sentence-length navigation and explanation controls, with a compact optional
  reading path and an explicit human decision. A linked German introduction
  identifies the English demo and explains local setup without promising a
  desktop installer. Tool comparisons avoid unsupported category-wide exclusions.
- Heatmap cells, style-reference cutoff-hit counts and all style-space loadings
  share a read-only chapter measurement dialog. It retains chapter context and
  shows definitions, units, sample size, manuscript medians and z* for the
  existing 16 metrics, without recomputation or a cross-metric quality ranking.
  Explicit **Read chapter** reuses manuscript navigation; chapter-only metrics
  clear unsupported paragraph layers. Axis loadings remain distinct from
  chapter measurements, and close/Escape restores the original trigger.
- Documentation separates paragraph, chapter and style-axis comparisons,
  corrects obsolete control descriptions and MTLD's inclusive factor threshold,
  consolidates passage-inspection guidance, and distinguishes pushed source,
  installed/running code, deployed Pages and fixed reading exports.

### Fixed
- Preserve grammatical model/scope overrides when reapplying view settings,
  without persisting temporary selections; identical requests retain identical HTML.
- Follow nested verb coordination when inheriting a shared auxiliary, stop at
  finite conjuncts, and reject malformed dependency graphs before composition.
- Limit external FFmpeg conversion to one hour through one shared
  subprocess owner; timeout errors preserve completed outputs and clean temporary audio.
- Preserve sentence boundaries after audio pronunciation replacements through
  one shared segment packer; retain bounded words, source text and structural pauses.
- Stabilize lag-1 autocorrelation at extreme finite scales/offsets and constant
  decimal samples, and preserve near-null Dunning G² with centered deviances.
  Independent high-precision oracle tests cover these numerical changes.
- Keep workspace project identity visible even when the manuscript repeats its
  title, and show analysis navigation only within the analysis overview.
- Align adjacent paragraph review and research buttons with consistent sizing
  and spacing, allowing them to wrap within narrow reading columns.
- Analysis overview navigation uses one wrapping contents list in the existing
  reader header, with a current-section underline instead of a progress track.
  Later sections remain visible on narrow screens; short viewports keep the
  header in document flow and dossier outlines retain their existing indicator.
- Shared hover help waits for deliberate dwell and switches quickly between
  neighboring controls, with canceled pending hints after navigation or actions.
  Structured tool names, descriptions and declared shortcuts reuse localized
  resources; keyboard and explicit touch help remain immediate. Pointer hints
  stay near the cursor instead of clearing the complete toolbar; focus/touch
  retain toolbar clearance.
  Pointer hints now anchor vertically at the dwell point, and sentence evidence
  cards open beside the hovered words instead of the start of the text line.
- Localized paragraph action menus stay anchored clear of their own trigger,
  choose available vertical space and retain scrolling for longer translations.
  Shared reading-dropdown height limits remain owned by their existing layout.
- Text-report `-o`/`--output` now writes the accepted analysis, profile, style,
  quotation, pacing and signal-group reports instead of silently printing to
  stdout. A shared atomic writer preserves failed destinations and rejects
  manuscript path, symlink and hardlink aliases; no duplicate stdout data is emitted.
- Shared mean and median recover finite results when floating intermediate sums
  overflow, using exact-ratio standard-library accumulation only on that path.
  MAD now reuses the same median. German productive perfect cues also cover
  short weak stems and common separable preverbs within existing clause/head
  safeguards; new `sein` licensing and full grammatical classification are not
  inferred from a suffix or prefix.
- Product vocabulary now separates quoted text, signal-group comparisons and
  ending cues from dialogue, narrative distance and suspense interpretations.
  Source-copy badges describe Lixity's verification boundary; passage actions
  name their draft effect. Manual marker actions differ from saved categories,
  research comparison prompts reuse localized reason flags, and publication
  controls distinguish completed-chapter display gates from package selection.
  Known structured export limits receive localized recovery summaries with safe
  expandable technical details. Formula captions use the measured readability
  variant. The central terminology contract lives in `docs/LOCALIZATION.md`.
- Text style passports distinguish insufficient chapter support, zero MAD with
  varying values and genuinely constant observations. Shared standardized
  differences avoid overflow for the newly covered extreme finite inputs while
  preserving ordinary calculations and cutoff boundaries.
- Analysis names distinguish measured noun/adjective endings and word-distribution
  divergence from inferred style. Pacing summaries name mean sentence length;
  language settings explain their analysis/interface scope. Seven-locale search
  and structural help use one authoritative definition, and website receipts
  report download initiation rather than an unverified completed download.
- The nominal-cue measurement is labeled "Noun endings" and explained with
  localized verb/noun examples before comparison mathematics. Suffix matches
  no longer appear to certify a passage's nominal style; counts are unchanged.
- German listed and bounded productive perfect/pluperfect constructions count once across chapter,
  scene and paragraph analysis, including bounded intervening words; `arbeite`
  and its present paradigm no longer trigger the weak-past suffix rule. Review
  decisions are invalidated by the changed analysis policy. Unresolved verb
  constructions remain heuristic cues rather than grammatical verdicts.
  Productive auxiliary/head rules cover unlisted `geschlafen`, `getroffen`,
  `gehabt` and passive-perfect `gebaut/renoviert worden` without list additions.
- German single quotation closers (`‚…‘`) preserve sentence boundaries and exact
  evidence ranges. The sentence regex now derives from one closing-mark list.
- Analysis review actions retain readable dimensions; the passage component
  switches to its existing cards according to available pane width.
- Export data/revision/bundle-limit failures provide structured JSON and actionable native
  messages identifying the first byte/count limit crossing. Bounds remain
  unchanged and partial failures do not invent completed package sizes.
- Passive cues include short regular and selected irregular participles in
  English, French, Spanish, Italian and Portuguese. German state passive remains
  distinct from the existing event-passive cue count.
- New dossiers inherit the research project's language through API, CLI and
  native creation; explicit language overrides and existing dossier languages
  remain authoritative.
- Shared chapter, scene and paragraph tense counting rejects productive past
  guesses that contradict a curated present-only finite form, such as German
  `halten` or Dutch `moeten`. Explicit pattern overrides retain their counting
  contract; compound constructions remain heuristic. The analysis review-policy
  identity changes so previous decisions are marked stale under the new counts.
- Canonical-equivalent Unicode prose uses the same NFC counting projection across
  measurements, CLI and UI evidence. Original manuscript bytes and hashes remain
  unchanged; complete-cluster ranges map back to original source offsets.
- Global UI word totals share corpus scope with sentence/ASL measurements, with
  separate help for narrower paragraph views. Mobile counted-text navigation
  returns each new explanation to its beginning so its count remains visible.
- German `zur` is recognized as a function word, so the default nominal-suffix
  heuristic no longer counts or highlights it as an `-ur` nominal cue. Shared
  corpus, chapter, paragraph and evidence outputs use the same correction.
- Nominal ending cues include listed plural forms in all seven languages.
  Spanish, Italian and Portuguese passive cues include regular plural participles;
  French includes `fut`/`furent`. These remain pattern cues, not grammatical parses.
- Portuguese marked `í`/`ú` hiatus, Dutch diaeresis boundaries and `ij` beside
  another vowel contribute separate syllable nuclei to readability estimates. Recompute affected reports
  before comparing them with earlier outputs.
- Matched quotation/bracket closers separated from terminal punctuation by
  whitespace stay with their original sentence, without consuming a following
  opening quotation or crossing a blank-line block boundary.
- The adjusted deviation's norm avoids overflow/underflow at extreme finite
  scales. ASL uncertainty documentation now identifies the implemented observed-
  population plug-in, rather than calling it a sample standard error.
- Research audit verifies the complete accepted manifest ancestry and reports
  revision-entry capacity, with an advisory warning at 90% of the existing
  25,000-entry limit. Missing or damaged ancestors fail integrity checks.
- Dossier summaries resolve image/media references across the complete selected
  revision, not just the first 500 characters. A read-only paginated
  `research dossier-images` inventory shows current dossier/section placement,
  exact pins, retained hashes/context and unretained ordinary references without
  scanning folders. `dossier-image --replace-reference` exposes the existing
  atomic exact-marker replacement in CLI. Storage-full/quota CLI diagnostics
  point to temporary storage as well as project storage.
- Publication export distinguishes no saved profiles, malformed settings and
  unsaved edits, links directly to profile creation and disables dependent
  controls until a saved profile is selected. Failed dossier catalogues offer
  retry without discarding drafts. Profile-save and media-capture outcomes are
  logged without titles, file paths, tokens or retained content.
- Current dossier records use a full-width reading article rather than a narrow
  metadata cell. Exact ordinary image references can be retained/replaced
  atomically from that viewer; pinned/history/exported views remain read-only.
- PDF source analysis/compare reads the verified text extraction, not binary
  PDF bytes. Retained-only PDFs explicitly require extraction before analysis.
- Reading-website export failures retain HTTP status codes and distinguish
  unreachable application, invalid ZIP response and browser download failures,
  including available technical details, without resetting export options.
- Native website exports log preparation and transport outcomes at normal log
  levels. Bounded, content-free browser receipts correlate response-read,
  ZIP-check and download-start failures with a random export ID; interrupted
  transfers are no longer described as invalid ZIP files.
  Bounded pre-export profile/catalogue receipts additionally distinguish empty,
  invalid and unsaved configuration without logging project identifiers.

## [0.7.5] - 2026-10-22

### Added
- Native **Project overview**, `lixity project [PATH] [--json]` and Python
  `api.inspect_project` share a bounded, read-only project metadata model
  (`lixity-project-structure/1`). Sources, conventional output locations and
  findings remain distinct; existing output provenance is explicitly unknown.
  No folders, role registry or submission bindings are created.
- Read-only `research find-anchor --query-format markdown` accepts copied inline
  emphasis through the shared displayed-text projection and returns the exact
  quote, offsets and paragraph hash. Default queries and write/re-pin selections
  stay literal; case, Unicode, ambiguity and paragraph boundaries stay exact.
  The research guide includes a reviewed lookup-to-selection workflow.
- Dossier section reads support `--format text --body-only` for an editable UTF-8
  draft without display metadata or an extra newline. Nested headings remain;
  unsafe terminal controls require redirected output. The research guide includes
  a synthetic read/edit/diff/guarded-update roundtrip and expected output.
- Authored-record `--update [--dry-run] --compact` provides a small CLI receipt
  with the accepted or candidate version, explicit no-op status and claim warnings.
  Preview receipts list changed fields without copying their values. Existing
  full JSON and Python/API write contracts are unchanged.

### Changed
- Research reads avoid repeated revision-path traversal and repeated archive
  scans for citation batches. Selected history reads serialize change metadata
  without copying full dossier bodies. Tiny records avoid allocating the entire
  read ceiling; large seekable blobs retain their original allocation bound.
  Bounded reads, checksums, schemas,
  pinned citations and fresh per-call archive validation remain in force.
- Manuscript anchor lookup reuses the profiler's exact displayed-text projection
  without calculating linguistic measurements. Chapter Cliff effects use sorted
  tie groups with the same exact values instead of quadratic comparisons. Sn
  robust scale selects the same order statistics in O(n log n) time and linear
  memory for finite samples, retaining its documented medians and scaling.
- Native Analysis exposes its metric selector directly, with independent,
  browser-persisted **Counted text** and **Paragraph comparison** switches.
  None, disabled switches and Off/On retain the author's choices; Focus hides
  both displays temporarily and restores them on exit.
- Violet underlines identify counted spans. Blue/orange raw-value markers and
  direction arrows compare notable paragraphs with their chapter without a
  prose background wash. Measurement cards put quotation/count before a separate
  paragraph/comparison panel; method and counting guidance start collapsed.

### Fixed
- Project output downloads decode filenames once, reject source/configuration
  aliases and unsafe paths, and bound actual descriptor reads. Overview links
  carry the selected project context and reject stale tabs after a switch.
- Literal manuscript anchor lookup now rejects overlapping duplicate quotes as
  ambiguous, including `ana` in `banana`, instead of silently choosing one.
- Overlapping automatic research status reads share only their in-flight
  workspace observation. Explicit refreshes remain fresh; context changes and
  mutations invalidate sharing without retaining settled responses.
- Research tab labels and companion selectors remain readable on narrow screens
  with enlarged text; wrapped research destinations retain aligned control boxes.
- Website exports count authored record versions against the research-history
  limit, rather than every retained source passage. Curated reader/companion
  copies no longer apply a limit for history they do not include. Input-byte,
  prepared-response, bundle-size and integrity checks remain in force.
- Human dossier section reads preserve the actual heading level instead of
  presenting every selected heading as H2. Selected JSON reads add `section_level`;
  implicit preambles have no invented heading level.
- README and installation explain the current 0.x product numbering separately
  from historical 1.x/3.x tags and independent schema versions.

## [0.7.4] - 2026-10-22

### Added
- `lixity doctor [--json]` reports imported/distribution/service versions,
  module/interpreter locations and JSON contract versions without reading a
  manuscript or repairing/restarting anything. A stopped service is valid.
- `pdf --layout document` and the native PDF selector provide neutral A4 text
  for exposés and everyday documents through the shared composer. Authored titles
  and structure remain; entered title/author are metadata only, with no generated
  title page, header/footer, byline, line numbers or analysis.
- Export an explicitly selected project as a static read-only reading website
  through `lixity export-site`, `lixity.site_export` or the native ZIP download.
  Research and original source files are separate opt-ins. A versioned export
  manifest records scope, source identities and file hashes; the copy uses the
  shared product UI with a fail-closed prepared-read transport.
- Curated novel-and-companion and standalone-companion website formats share
  root-local `site_publications` profiles. Explicit dossier versions/sections,
  chapter release gates and optional citations/maps define the selected material.
  A chapter cap removes later content and assets before assembly; reader progress
  is a separate local display aid. Original sources need per-export opt-in.

### Changed
- Maintainer checks run locally by default. Full source/browser/platform jobs
  remain manual GitHub fallbacks; release-tag publishing deploys Pages from the
  same verified ref after package publishing. Local release checks avoid repeating
  documentation tests, and reading-website changes select their own browser area.
  Release arguments now fail before heavy work; checkout-local caches and aligned
  check-only Ruff hooks improve the development loop. Shared browser helpers and
  failed Git comparisons can no longer silently omit affected suites.
- `service status --json` intentionally uses `lixity-service-status/1`:
  `ok` describes successful inspection, so known stopped, starting and unmanaged
  busy states exit 0. `running` indicates readiness; unknown state keeps
  `ok: false`, `running: null` and exit 1. Log paths and raw errors are omitted. Human status and
  other lifecycle JSON keep their existing behavior.
- Simultaneous text evidence and paragraph emphasis have distinct visible keys:
  **Counted text** explains the underline/tint, while **Paragraph comparison**
  explains blue/orange chapter-relative backgrounds. Exact-evidence availability
  stays visible outside the closed settings popup.
- Local phrase echoes already present in JSON now appear in human CLI output and
  the analysis overview, with local counts and explicit chapter-prose word bounds.
- Chapter register feature choices and target rows show their shared units and
  distinguish scene targets from chapter profiles and display-only filtering.
- The research guide has a task index; adapter guidance explains optional scene
  and exact-evidence inputs and shared character configuration.
- One **Explore passage** menu entry groups measurement inspection and saved
  research in the existing paragraph context. Quick hover and touch explanations
  remain available at marked text. The **Passage** context label distinguishes
  that tool from the global **Analysis** display switch.
- Measurement cards give the selected sentence's word count a clear hierarchy,
  separate paragraph comparisons and expandable mapping/method details.
- The landing page explains manuscript analysis, linked research and PDF reading
  copies and browsable reading websites in its existing three compact feature blocks.
- Loaded claim quotations can be collapsed without discarding their contents.
  Ordinary research entry actions show the current version. Earlier linked
  versions remain explicit; a collapsed version list loads on demand without
  changing the displayed entry or discarding an editing draft.
- Research labels use compact version names across all seven UI languages and
  human CLI record/history output; existing JSON fields and flags are unchanged.
- Passage research groups quotations of the same linked claim and separates
  exact associations from current dossier decisions, with distinct counts.
- The six-chapter fictional demo has a stronger receipt/label mystery and about
  15% more text, with richer dossiers, conflicting citations, claim histories,
  explicit decisions, causal links and exact manuscript associations.

### Fixed
- Research archive candidate syncing uses a writable descriptor on Windows.
- Service observation accounts for Windows' different path/descriptor timestamp
  clocks while retaining same-API mutation, identity and ownership checks.
- Human `dossier --diff --format text --section` previews explain nested heading
  scope without another archive read or a JSON/API contract change.
- Installed reading-website exports resolve license metadata beside the loaded
  package, including standard legacy layouts, instead of a shadowing checkout.
- PDF/dashboard CLI exports reject source paths and their symbolic/hard-link
  aliases before writing and again immediately before atomic replacement.
- Button-styled links share the real control box, alignment and wrapping used by
  app buttons; their minimum height also applies inside ordinary Pages prose.
  Long localized headings and checkbox labels wrap at enlarged text sizes.
- Native views, PDF downloads and reading websites consistently use the selected
  project's configuration, including manuscripts in configured subdirectories.
- Configured `motif_regexes` and compatible legacy `motifs` now resolve once
  across chapter measurements, CLI, Python, native panels and the motif panel in
  `build` dashboards. Explicit patterns
  replace configuration; conflicting duplicate names fail clearly. Empty
  patterns consistently count no occurrences.
- An unchanged manuscript Review refresh preserves its row controls, so closing
  a pinned-entry viewer returns keyboard focus to the actual opener. Changed
  reports and filters still refresh, and read failures remain explicit.
- Stale scene assignments report measured scene/divider counts and recovery
  choices without accepting missing assignments or inventing planned text.
- Human style passports label robust deviations as z*, rather than ordinary σ.
- `research dossier show ID --export-edit PATH` no longer injects a conflicting
  implicit inspection flag; export and archive write guards remain unchanged.
- Research lists show complete IDs; dossier lists support exact tag filters and
  `--section --format text` returns the selected section body, including nested
  content and explicit saved versions. `research compare` inherits the selected
  root's project language unless overridden; a missing setting and the Python API
  retain English defaults.
- Sentence word counts use the selected interface language, including singular
  counts; browser labels no longer fall back to the English key.
- Explicit measurement explanations can open from the mobile context inspector
  when its associated paragraph is outside the viewport.
- Reading and analysis settings share a disclosure indicator and keep their
  popup beside its trigger, with internal scrolling on short screens.
- Decision claim choices distinguish identical titles by period, saved version
  and, when still necessary, ID, as the evidence and relation pickers already do.
- Source document/passage controls expose their selected state consistently.
- Stationary content reflow no longer opens incidental hover help; deliberate
  pointer, keyboard and touch explanations retain their existing behavior.
- Repeated hover departures cancel earlier dismissal timers, so an old hover
  cannot close a subsequently opened touch explanation.
- The read-only demo includes record/history fixtures for evidence and causal
  links, so their entry and version controls reach real archive states.

## [0.7.3] - 2026-10-21

### Changed
- The first explicit reader Analysis activation selects Sentence length and
  shows counted text. A sticky, named metric control groups the existing
  selector, highlight preference and interaction help; deliberate None/Off
  preferences remain visible and survive reloads. Paragraph inspection can
  activate analysis directly without silently changing the highlight preference.
- Research version history consolidates selected-version context and provenance,
  localizes read-only choices, omits absent optional fields and preserves pinned
  references, explicit false values, drafts and guarded version navigation.
- Restored button focus after touch no longer opens an incidental help popup;
  immediate keyboard focus and explicitly opened touch help remain available.
- Native project chrome removes the generic analysis slogan and repeated footer.
  A matching authored manuscript title remains in the document while its generated
  sidebar duplicate is suppressed only in reading mode.
- Manuscript analysis can mark exact counted sentences, words,
  patterns and quoted speech, with a hover/touch explanation and keyboard/context
  menu inspection. Evidence shares configured core counters, preserves prose and
  selection, and reports unmappable/unsupported states explicitly.
- `profile --layer KEY --evidence` adds literal source evidence; its opt-in JSON
  schema is `paragraph-layer-evidence/1`. Existing default contracts are unchanged.
- Wide dossier views keep a bounded heading tree to the right of the reading
  document; narrow and companion views retain the compact native disclosure.
- Interface typography uses three shared roles for metadata, controls and body;
  manuscript prose and technical code retain their distinct reading faces.
- Analysis uses one selected metric for quiet transparent paragraph emphasis,
  with value/unit/local-reference hints, comparable coverage, clear controls and
  distinct unavailable/zero results. Colour now matches the chapter-relative z
  used for notable membership; labels correctly describe median/MAD.
- `profile --layer KEY` adds source-anchored human output and opt-in
  `paragraph-layer/1` JSON. `--only-notable` retains full chapter references;
  default profile JSON v2 remains unchanged.
- Declared register/POV selectors filter only style-fingerprint table rows and
  explicitly retain the whole-manuscript reference and existing register policy.
- Analysis and dossiers share heading-navigation presentation. Dossiers gain
  real heading links and compact persistent orientation, with native collapse
  and existing scroll/return owners. Context resizing preserves a reached end.
- Decision/dossier review reads exact saved versions together, including an
  earlier assessed dossier. Delayed impact reads cannot mint acknowledgement
  controls in a newly selected project; writes retain existing guards.
- Public pages use a consistent editorial header and a concrete synthetic
  passage/rhythm/research example, fewer repeated entry links and smaller complete
  screenshot previews. Technical reference remains separately reachable.
- Workspace destinations precede project identity and actions, including long
  titles. Version/license information is secondary; collapse, project dialogs
  and the existing PDF export remain available through the same controls.
- Reader feedback uses distinct persistent and temporary gutters, a legible
  Analysis toggle throughout its transition, and quieter interrupted reveals.
  Context scrollports fit their containing layout without moving the manuscript.
- Explicit workspace choices supersede queued fragment navigation; later passage
  links and direct `#view-…` routes remain available.
- A paragraph's Saved research, association count or marked quotation opens
  exact saved claim/dossier versions in the shared context dock. Current dossier
  decisions are labelled separately; unresolved anchors retain explicit Review.
  Reads are lazy and coalesced, with bounded lists, retry and context guards.
- Current product guidance describes Manuscript & Analysis, Research & Dossiers
  and Project & exports without a blanket experimental label for Research.
  Capability metadata classifies Research as `supported`; response/archive schema
  versions, retention/revision guards and individual integration/export limits
  remain unchanged. The classification does not certify factual accuracy.
- Analysis/export CLI commands can reuse a root-configured manuscript and select
  an explicit project with `--project`. Research manuscript commands share the
  configured-path resolver while preserving retention and revision guards.
- Public entry routes start with concrete manuscript questions, an example and a
  short tour; installation and technical references remain directly reachable.
- Key reader actions explain their purpose on hover and focus. Reading settings
  includes a localized reference to implemented passage-menu, search and close
  keys. Shared controls and canvas labels use central typography roles; fenced
  code and all six prose heading levels retain readable sizes.
- Public entry pages use a shorter product introduction, bounded linked screenshot
  previews and direct documentation routes for first use, installation and reference.
- Analysis overview groups secondary manuscript measurements in a reversible
  disclosure while keeping review routes, navigation and flagged passages visible.
  Scene measurements share a collapsed catalogue with direct routes from the
  comparison rows. Long flags and scene comparisons remain bounded and keyboard
  scrollable; wide chapter, character and scene tables retain visible row identity.
- Dialogue charts show every measured chapter in manuscript order, including
  zero-turn chapters. Pacing labels identify ASL, its units and relative bar scale;
  Hook help explains the existing heuristic without changing its calculation.

### Fixed
- Right-click evidence inspection retains the clicked occurrence instead of
  restarting at the paragraph's first match, including when enabling Analysis
  changes the surrounding layout.
- A touch inspection waits until the opening tap completes before presenting its
  card, so that tap cannot accidentally operate the newly appeared explanation.
  Unavailable browser text verification is distinct from a source-hash mismatch.
- Public installation-link measurement includes the current landing section
  anchor as well as the existing guide and historical anchor.
- Research index failures retain their actual SQLite cause and index path
  instead of attributing storage or corruption errors to missing FTS5 support.
- Research exports retain one accepted snapshot while copying records and blobs,
  verify copied content addresses and preserve an existing backup on failure
  before replacement. Errors after replacement identify uncertain durability.
- Export rejects destinations inside its research store/cache and checks
  restore's existing size ceiling before creating a candidate archive.
- Restore rejects malformed export envelopes and duplicate archive members with
  bounded errors; valid archives keep their format and immutable bytes.
- Service status inspects existing state without creating or repairing folders
  or acquiring the lifecycle writer lock; changing records retain uncertainty.
- Reading settings fit short viewports from their first visible frame. Rapid
  tool reversals and analysis changes preserve the stable reading position
  without rewinding deliberate scrolling after the tool has opened.
- Dossier departures retain a guarded return to their exact saved view, tab,
  scroll position and control without dropping an earlier manuscript return.
  The same return control stays reachable on narrow screens and offsets other
  sticky controls. Project changes and replaced dossier views invalidate it.
- Shared jumps account for nested scrolling and their own sticky controls;
  arrival feedback waits for scrolling to settle, cancels obsolete cues and
  honors live reduced-motion changes. Search no longer leaves permanent arrival
  styling. Navigation does not change source bytes or saved research records.
- Overview section links retain spacing and keyboard reachability on narrow
  screens. The final chapter matrix stays selected at the page bottom, and
  keyboard drills focus the revealed manuscript destination while preserving
  the existing passage/context return.
- Flagged passages expose their existing To-do draft action in the overview.
  Chapter-matrix deviation counts distinguish a measured `0` from unavailable
  `–`; coverage guidance explains the existing paragraph/corpus difference.
  Analysis scores and public API formats are unchanged.
- Chapter charts no longer fade their final rows when all entries already fit,
  or at the end of an overflowing list. Native scrollbars remain visible for
  long Pacing and Showing/Telling chapter lists.
- Empty claim evidence offers a direct route to the existing evidence composer;
  failed reads offer retry instead of appearing empty. Existing claims, retained
  quotations and unsaved drafts keep their separate states.
- Unchanged archive refreshes preserve an opened or loading evidence panel;
  archive, claim or project changes still invalidate it. The public demo marks
  evidence preparation as a local-app action instead of opening a disabled form.
- Research catalogue filters are hidden for genuinely empty collections, while
  active queries and failed or pending refreshes retain their editing context.

## [0.7.2] - 2026-10-20

### Changed
- Public Pages and the read-only demo can count page visits and named CTA events
  through the explicitly configured hosted GoatCounter instance. The Pages-only
  adapter excludes query/hash, forms and selections, respects browser privacy
  signals and stays out of the local app and exported manuscript reports.
- An optional project-only `manuscript` setting supplies existing workspace folder
  selection and omitted input for `scenes` / read-only `research review-manuscript`.
  Explicit paths win; invalid root settings never select an alternate manuscript.
- Scenes output supports canonical chapter/scene filters and the last measured
  scene in document order, preserving full-manuscript references and declaring
  filtered JSON scope. Explicit `scene_analysis.planned` IDs remain visible without
  fabricated measurements; unlisted stale assignments still fail.
- The research data-model reference now documents the implemented entities,
  revision pins, publication process, schema evolution and disposable SQLite
  index, with current architecture/process diagrams. The broader interchange
  proposal remains available as an explicitly historical design.
- The public showcase focuses on one real reader view, the demo and installation.
  README explains purpose, first commands and where to find documentation and
  source. The demo uses a compact return link instead of duplicate site navigation.
- Native Project actions groups New/Open, guidance and PDF export; destinations
  remain directly visible. Service help groups existing workspace, instance and
  analysis options without changing their defaults or behavior.
- Screenshots frame actual viewports or complete tasks. Capture tooling preserves
  native dialog scrolling, readable image ratios and the intended light/dark views.
- Shared light-theme tokens use paper-toned surfaces across the native UI and
  Pages. Clearer chapter typography, compact reader control spacing and quieter
  supporting sections give prose more room while retaining the existing reading
  preferences, initial text size, dark palette and independent passage tools.
- The interactive manuscript stays continuous, with an explicit **Analysis**
  On/Off switch independent of the dossier context tool. Showing diagnostics
  keeps the prose width and navigation choice; it does not implicitly open a
  dock. **Values** explicitly opens the Passage values inspector independently of
  the diagnostic layer;
  **Dossier alongside** opens its own context tool. Dense comparisons open
  in an overview; **Back to passage** restores the prior analysis display choice.
  A shared display coordinator owns
  workspace, tool, overview and reversible focus transitions. Reading settings
  group text size, width and spacing and retain visible source-block position.
  Paragraph **…** buttons,
  right-click and keyboard menus reuse existing values, marker and quote-link
  actions; selection tools appear only when applicable. Desktop manuscript/dossier
  widths use one draggable, keyboard-operated divider; mobile stacks the readers.
- Explicit passage-to-tool requests reveal the stacked tool heading on mobile;
  closing the tool or pressing Escape restores the requesting passage and focus.
  Desktop tools retain their adjacent layout. Optional feedback uses short opacity
  changes on bounded visible elements and a passage gutter; semantic changes stay
  immediate. Live reduced-motion changes cancel active feedback without moving or
  duplicating prose or animating the workspace width.
- Source-backed browser reading retains supported headings, quotations, literal
  code, dividers and notes in source order, including preface/empty chapters and
  the analysis-excluded appendix. Source-span joins reuse each exact profile once,
  including profiles spanning several list items. Unprofiled content has no
  invented measurements or claim saves; analysis/JSON/quote and PDF contracts stay
  unchanged. Unsupported inline syntax remains literal; no editor or automatic
  manuscript image fetching is added.
- Saved manuscript associations open their pinned claim revision; claim/dossier
  views expose scoped saved-quotation routes and exact reviewed passage returns.
  A compact work thread retains the original passage and the viewed saved-record
  identity and revision, with an explicit return. Dossiers group authored notes,
  current-linked claims and retained citations, with routes to global claims and
  decisions. Values includes passage context and the existing saved-research route.
  Dossier revision references remain explicit; retained quote cards are not full
  historical-source readers. No new record, store or implicit repinning is added.
- Research tabs have named tab/panel relationships and explicit narrow-screen
  overflow controls. Lazy Mermaid rendering shows a localized pending state.
- Companion dossiers temporarily collapse desktop project navigation, with an
  accessible manual toggle and restoration of the prior choice when closed.
  Mobile navigation remains visible. Saved exact manuscript associations now
  offer a direct, focused return to their passage alongside the claim action.
- Research creation and association forms start collapsed with reversible labelled
  controls, retained in-memory drafts, nested Escape handling and contextual reveal.
  Shared disclosure arrows provide brief reduced-motion-aware feedback in the app
  and Pages. Dossier catalogue previews omit formatting and fenced code while the
  saved body and API data remain unchanged.
- Shared local tabs, form groups and dialog frames now carry the desktop
  workspace design through analysis, settings and research. Research catalogues
  use separated rows; labels preserve localized casing. Dialog forms scroll
  below their title and close control, including in short windows.
- The interactive workspace puts manuscript and analysis first in a fixed desktop
  project sidebar, with research and settings alongside. Narrow screens retain
  horizontal navigation, with keyboard orientation matched to the layout. Plain
  exported reports keep their document layout.
- Public entry points distinguish the read-only demo from local installation,
  with simpler page framing and clearer open/import guidance. Compact diagram
  frames and grouped style-space controls reduce empty space and uneven wrapping.
- Upgrade guidance uses restart to retain recorded launch settings and explains
  the distinction between released, installed and running code.
- One public Warehouse 4 demo combines the same manuscript, analysis, research,
  images, geography and PDF exports. Former research links open that project;
  public-domain novel analyses remain secondary case studies.
- Embedding adapters can enable manuscript review without association editing.
- The public demo keeps the native workspace views and marks local-only actions
  with installation links. Dossier reading, prepared PDF downloads and the
  claim-evidence matrix use the existing application controls.
- Geography reads share placement coverage, authored route context and approximate
  vertex-chain distances across the API, CLI and map/companion views. Maps add
  selected-feature framing, a legend and a metric scale. Visible maps open with
  OpenStreetMap; the background can be disabled and local vectors/sketches remain
  available offline. Tile requests stop outside the active visible map context.
- Style-space views and CLI output explain projection support, retained variation,
  active cutoffs and chapter scores, with persistent selection, planar inspection
  and numeric loadings. Additive diagnostics preserve existing scores and formats.

### Fixed
- German perception/filter cues include finite present and simple-past forms of
  hören and riechen across shared analysis surfaces. Counts remain lexical,
  context-dependent signals; no full grammar/perception detector is implied.
- Purge accounts for original and extracted-text blob references together,
  preserving shared retained evidence and removing unshared extraction bytes.
  Decision-to-dossier pins are validated at the storage/restore boundary.
  Publication acknowledgement and post-commit cleanup errors identify the
  observed outcome instead of suggesting rollback or successful erasure.
- Configuration discovery warns about permission/I/O failures and present
  non-table `tool`/`tool.lixity` sections instead of silently applying other
  settings. Missing paths and impossible children beneath a file remain quiet.
- Imported style measurements reject non-finite features and invalid standard
  errors before scoring. Low-level structure reports share the English default;
  automatic detection remains explicit. Dialogue, pacing, motifs and showing CLI
  commands share guarded UTF-8/regular-file reads, including nonblocking rejection
  of special file nodes.
- Invalid explicit foreground startup selectors fail before binding or selecting
  a different workspace. Failed project configuration or requested Research setup
  reports incomplete setup, retains created files and keeps the prior selection,
  with a recovery path through **Open Project**.
- Supplied invalid HTTP claim-confidence and evidence-relation values return 400
  without an archive write; only omission receives the existing defaults.
- Research backup import and export validate the complete manifest ancestry before
  accepting or packaging it. Invalid selectors, damaged or incomplete history and
  project/generation mismatches fail explicitly; archive paths reject parent
  traversal. Valid archive formats and record bytes are unchanged.
- French, Spanish, Italian, Portuguese and Dutch word patterns retain straight
  and curly internal apostrophes as documented. First-person sentence starts
  recognize typographic contractions consistently. Token-based measurements can
  change; regenerate affected reports before comparing versions.
- Plain-prose counting avoids unnecessary delimiter scanning while retaining
  the existing Markdown projection and exact source/display identities.
- Downloadable Markdown guides preserve paragraphs and fenced commands inside
  expandable sections. Example generation uses the active checkout's source.
- Heatmap chapter cells reveal their manuscript destination through the shared
  navigation coordinator instead of scrolling a hidden chapter from the overview.
- Validated authored edits whose normalized content is unchanged return the exact
  previous revision without changing archive HEAD, retained bytes or the SQLite
  index. Revision metadata, association validation and concurrent HEAD guards still
  run. Mixed batches revise only changed members; invalid batches remain atomic.
  Decision acknowledgements remain append-only events.
- Sidebar collapse uses a stable glyph beside project identity. Tooltip titles
  update with live state and nested scrolling; responsive settings and wrapped
  URLs stay readable. Paragraph actions and the reader divider have separate
  targets, and revision Close stays reachable in short or enlarged dialogs.
- Analysis Off preserves explicitly opened Passage values; opening Values does
  not force Analysis On. Overview return restores the prior layer and tool.
- Missing/unreadable manuscript files and failed configuration/render rebuilds
  label the last successful dashboard with an **Analysis freshness** notice and
  retry link, preserving its source identity. Explicit analyze/rebuild failures
  return an error; recovery removes the notice only after validation succeeds.
- Asynchronous manuscript association marks preserve native text selections,
  including backward selections and astral characters. Automatic review first
  checks archive readiness and revalidates project context after changes.
- Spanish syllable estimates now count standalone closed-vowel nuclei and apply
  bounded orthographic diphthong, hiatus and silent-vowel rules. Spanish ASW and
  derived readability can change; formula coefficients and JSON fields are
  unchanged. [Rules and limits](docs/METHODS.md#7-language-specific-readability).
- Chapter/rest Jensen–Shannon calculations retain small genuine divergence near
  equality and return zero with no lexical drivers for identical distributions.
  Integer absent-token mass and stable summation preserve the existing definition
  and units. [Numerical details](docs/METHODS.md#8-jensenshannon-divergence-chapter--rest).
- Project-dialog tab switches no longer reset unrelated research revision tabs.
- Disabled actions retain their disabled appearance on hover and press.
- Numbered map labels select their own feature with mouse, touch or keyboard;
  authored label anchors and geometry stacking keep routes and points reachable.
- Escape in research dialogs preserves open paragraphs in the hidden Analysis view.
- Style-axis descriptions use actual positive/negative loadings and distinguish
  an absent pole or zero-variance axis from an opposing stylistic tendency.
- Style-space plots keep chapter details alongside the canvas, with full-width
  scores below and readable axis/chapter labels. Research diagrams retain a
  readable scale on narrow screens through a keyboard-scrollable viewport.

## [0.7.1] - 2026-10-19

### Added
- Exact authored-update dry runs and historical revision comparisons through the
  existing research revision API and CLI.
- Explicit dossier Markdown export, three-way preview and reviewed batch packets;
  application remains bound to the reviewed project and archive snapshot.
- Project-local character profiles with literal aliases and separately declared
  viewpoint chapters, exposed through the existing configuration discovery.
- Guarded dossier retirement through the existing withdrawal/tombstone path,
  with read-only previews and retained historical records and associations.
- Bundled Leaflet geography interaction, offline by default, with explicit,
  nonpersistent OpenStreetMap tile permission; shared PhotoSwipe image/diagram
  zoom and Mermaid tiny rendering with inspectable source and restricted features.

### Changed
- Research prioritizes dossiers, claims and manuscript review. Zotero remains the
  source-library and reading interface; capture selection and alternative local
  imports use compact disclosures. Retained evidence and archive contracts stay intact.
- Research help groups commands and exposes aliases in discovery/completion.
  CLI selectors accept bare UUIDv4 identifiers; archive/API identifiers remain canonical.
- Dossier `--file` now requires an existing readable UTF-8 file. Use `--body` for
  literal text; this intentionally replaces the former missing-path-as-text fallback.
- Consolidated current documentation and retired duplicated status checklists;
  earlier design and implementation notes remain available through fixed Git links.
- Pages use consistent site and parent navigation, reading paths and accessible
  back-to-top links, including the standalone public examples.

### Fixed
- Selected workspace tabs keep readable text when hovered in light and dark themes.
- Cropped documentation captures preserve the full research navigation height.
- Revision preparation shares validation for sections and record fields, preserves
  concurrent unrelated sections and compares prospective changes in one snapshot.
- Name and prose counts exclude Markdown destinations, images and code while
  preserving displayed paragraph anchors and manuscript chapter numbering.
- Research writer diagnostics distinguish contention from read-only, permission
  and other I/O failures without changing the canonical lock location.
- Positional and verb-based dossier reads now honor section, summary and citation
  bounds through the same exact-version reader as named IDs.
- Image galleries include lazy images and fit their exact dimensions after loading.
- Dossier Markdown emphasis preserves link destinations and generated markup,
  preventing formatting from leaking into the geography view.
- Scene overview tables keep numeric values readable on narrow screens;
  documentation captures show the intended first three scenes.
- Research help names supported draft inputs and distinguishes exact quote matching
  from prose counting, explicit claim acceptance and per-association commits.

## [0.7.0] - 2026-10-19

### Added
- A4 editorial PDF copies with line numbers and correction margins through the
  existing CLI and native download composer.
- Optional structured places, areas and character journeys within existing
  dossiers, with a shared editor, offline coordinate view and GeoJSON import.
  Geographic saves require record/manifest v8; ordinary dossier encodings remain unchanged.
- Read-only research preview using attributed historical Hamburg map/photochrom
  sources alongside explicitly fictional scene notes and journey coordinates.

### Changed
- Manuscript PDFs preserve document structure separately from statistical text
  cleaning, with bounded embedded LaTeX text formatting, shared layout handling
  and stable reading typography.
- Zotero captures PNG/JPEG through the existing retained-image pipeline and
  exports them with media-correct filenames. Image captions expose provenance
  and source links in the ordinary dossier reader.
- Settings group project details and analysis choices by purpose, explain
  persistence beside the controls, and distinguish project values from values
  that could not be automatically detected in the manuscript.

### Fixed
- Oversized research records are rejected before publication, preserving the
  previous readable snapshot. Geography editing preserves Unicode and multiline
  metadata and guards pending file imports against concurrent saves.

## [0.6.0] - 2026-10-19

### Changed
- Clearer product descriptions and worked articles on intentional chapter
  registers and local phrase echoes, linked from the README and Pages.
- Configuration discovery exposes corpus/publication model defaults, threshold
  constraints and settings scope through `about --json`; `about` and `schema` accept `--section`
  for a focused JSON response. Metadata and shell completion ignore ambient
  configuration.
- Settings explain analysis and persistence choices beside their controls in
  all seven interface languages. An opt-in, unchecked by default, saves posted
  language and thresholds as project defaults through the existing guarded transaction;
  ordinary Apply keeps session-only analysis choices.
- CLI threshold help, defaults and scalar validation reuse backend policies;
  invalid values report usage errors before reading configuration or manuscripts.
- Onboarding, architecture and automation references defer discoverable details
  to command help and runtime metadata while retaining scientific and data contracts.

## [0.5.0] - 2026-10-19

### Added
- Research record inspection and all six manuscript-association commands support
  readable text output alongside JSON and table views.
- `unlink-manuscript` retracts one manuscript association (history retained).
- `reconcile-manuscript --accept-claim-updates` re-pins associations whose
  claim advanced to a newer revision without creating a parallel link.
- `--latest` flag for `--update` on dossier/claim/decision records: uses the
  current HEAD revision automatically (single-author convenience).
- Authored research records accept `list`, `show ID`, `inspect ID` and implicit
  inspection by ID, alongside their existing named ID options.
- Motifs: echo detector lists n-grams repeating within a short text span
  (`echo_window`, default 300 words) so local word echoes surface for review.
- Style: `chapter_registers` and `register_profiles` in `CorpusConfig` mark
  chapters as intentional registers (e.g. historical notary, child voice); such
  chapters are exempt from deviation/FDR flagging. Validated author target
  ranges are descriptive comparisons alongside the unchanged book baseline.
- Native Settings editor for named chapter registers, feature ranges and chapter
  assignments, with guarded project-local persistence and seven-language labels.
- UI: skip-to-content link, `role="main"` on the chapter pane, `aria-busy` on
  loading states (accessibility).

### Changed
- Research filesystem diagnostics identify the actual failure and affected path.
- Closed paragraphs create their inner layout subtree only when opened and
  release it on close unless retaining a marker draft. Full offline text,
  manuscript search and saved quotation links remain available.
- Regression tests share isolated handler, research command and browser server
  fixtures. Repeated browser workflows are separated from seven-language
  desktop/mobile rendering checks; numerical and structural assertions use
  independent expected values and nonempty measured results.
- Pages and articles expose generated Markdown alternatives through the existing
  guide converter. Canonical URLs, image dimensions, structured metadata and
  meaningful modification dates are checked against the staged publication.
- Documentation and agent guidance focus on workflows and durable contracts;
  exact options come from CLI help and runtime discovery. Repeated feature
  histories, command catalogues and implementation detail are consolidated.

### Fixed
- Reconciliation exits 1 on archive read/write, lock or safety failures instead
  of treating them as skipped associations. Storage causes remain distinguishable
  from ordinary record review conflicts.
- Human research reports render the requested format without losing list rows,
  and escape stored terminal controls in detail and diff output.
- CLI help accurately describes metadata, supported source formats and FDR
  settings. `pdf --json` rejects the unsupported mode before writing a PDF.
- Combined anchor/claim updates now save one association revision;
  `--accept-claim-updates` works alone and with an explicit selected link.
- Explicit batch snapshot guards reject intervening external archive writes;
  manuscript association revisions record their current actor and UTC timestamp.
- Numeric register selectors match chapter numbers exactly, and register names,
  feature bounds and explicit project scope are validated.
- Echo counts require the configured minimum within the local span; independent
  repeated phrases sharing words are no longer discarded by deduplication.
- Low-level MATTR/MTLD/Maas helpers reject invalid window sizes, thresholds and
  impossible token/type counts with `ValueError`; valid/default arithmetic is unchanged.
- USAGE.md: corrected manuscript path requirements, claim re-pin examples and
  format documentation; removed the stale "no manuscript-link CLI command" sentence.
- Pages: comparison tables survive Markdown conversion; article examples and
  evidence-link descriptions reflect their implemented scope. Removed an
  accidentally appended assistant transcript from the v0.4.9 release notes.

## [0.4.9] - 2026-10-16

### Added
- `lixity schema` exports tool metadata (languages, features, heuristics and
  commands) as JSON for discoverable machine integration, alongside
  `lixity about`.

### Fixed
- Manuscript-link commands (`link-manuscript`, `review-manuscript`,
  `find-anchor`, `reconcile-manuscript`) accept the manuscript path
  positionally as the analysis commands do, or via `--manuscript PATH`; exactly
  one of the two forms is required.
- The reader panel's dossier select and refresh button share one top edge (a
  panel margin had overridden the controls row reset and pushed the button 11 px
  below the select).
- Compact controls (`.ctl-sm`) keep the 44 px touch minimum on coarse pointers;
  the size variant previously beat the touch rule on specificity.

### Changed
- The documentation site is rebuilt as a product page: framed application
  windows, a "what makes it different" tile row, a three-step start and
  reordered feature blocks. The staged site now shares `assets/components.css`;
  controls use the shared `.ctl` vocabulary, and the docs suite checks the
  frames and captures the landing page full page.

## [0.4.8] - 2026-10-16

### Added
- UI component layer for stateful panels: the dashboard vendors Preact 10.29.8
  (MIT) and htm 3.1.1 (Apache-2.0) as pinned, integrity-checked files and
  inlines them into the single script - no build step, no runtime network and
  CSP-compatible without `unsafe-eval`. The Zotero catalogue results
  (`assets/zotero-results.js`) and the research record lists
  (`assets/research-cards.js`: sources, dossiers, claims, decisions) run on
  this layer.
- Central logging: one `lixity.*` logger tree with a UTC line format, standard
  levels (`--debug`, `LIXITY_DEBUG`, `LIXITY_LOG_LEVEL`), a redirect-aware
  stderr handler and rotation for the captured service log at service start.
  `docs/INSTALLATION.md` documents the log location and settings.

### Fixed
- Manuscript-link commands (`link-manuscript`, `review-manuscript`,
  `find-anchor`, `reconcile-manuscript`) accept the manuscript path
  positionally like the analysis commands, or via `--manuscript PATH`; exactly
  one of the two forms is required (both together fail).
- The reader panel's dossier select and refresh button line up: a panel margin
  broke the flex-end alignment and pushed the button 11 px below the select.
- Compact controls (`.ctl-sm`) keep the 44 px touch minimum on coarse
  pointers; the rule previously lost to the size variant on specificity.

### Changed
- Controls: the dimension buttons build on the shared control recipe
  (`.dim-ctl` is a compact variant), the field label/help recipes and the
  selected state (`aria-pressed`/`.active`) have one source each.
- Structure: the shared stylesheet vocabulary moved into `assets/components.css`
  (panels, status, focus, tables, badges, controls, layout primitives, renderer
  utilities) with the layer order tokens → components → views, asserted for the
  standalone output. The spinner, micro-label and table recipes are consolidated
  to one source each.
- Structure: the 3,500-line `assets/research.js` is split into seven topic
  modules (`research-core`, `-content`, `-evidence`, `-lists`, `-review`,
  `-workspace`, `-revisions`). `_JS_FILES` concatenates them in the original
  order, so the served bundle and its load-time behaviour are unchanged.
- UI cohesion: radius, type and weight values come from the design-token
  ladders instead of one-off numbers; the workspace switch and the research
  sub-tabs share one tab/control recipe, badges and tags are one pill family,
  and the staged public site uses the same control metrics. The
  `visual-consistency` browser suite now fails when control radii, badge
  pills or sampled text sizes leave the ladders.
- Research workspace: the record lists render through one shared card
  component; the hand-rolled per-card identity diffing was removed. The
  claims evidence panel keeps loaded evidence in the list model, so
  re-renders no longer lose or misplace it.
- Component layer: panels mount through `LixityComponents.mount`, so the
  server-rendered loading placeholder no longer survives beside the first
  rendered list (the empty list hosts show the component tree only).
- Research workspace: the claim timeline is a view switch (List/Timeline)
  inside "Thesen & Belege" instead of a separate top-level tab, with a purpose
  line naming both views; the decisions pane states its scope ("deliberate
  choices with rationale, not historical claims"). No API, archive or route
  changes.
- Documentation: the interpretation guide and METHODS state that
  `filter_density`, modal, passive and nominalisation densities include quoted
  speech, and how to read them together with `dialog_pct`; a narrative-only
  variant is recorded as a candidate, not a current contract.

## [0.4.7] - 2026-10-16

### Fixed
- Sentence segmentation keeps blank-line block boundaries: an unterminated
  block (stage note, salutation, sign) stays one fragment unit instead of
  merging into the next block's sentence. Chapter ASL, scene units, corpus
  sentence statistics and the chapter matrix now agree; recompute older
  reports before comparing.
- The serve dashboard checks the manuscript digest when the page is loaded
  and rebuilds itself when the file changed on disk instead of presenting
  stale numbers.
- Closed scene details no longer reserve an empty 520 px block each; the
  deferred-rendering hint now applies only to open details.
- Count labels use singular forms in all seven languages (`1 Datei`,
  `1 Treffer`, `1 Zuordnung`, ...); four unused label rows were removed.

### Changed
- Style comparisons use documented comparability floors: chapters below 100
  words (`MIN_COMPARABLE_WORDS`, the same floor as the diversity indices)
  receive no z*, effect sizes or FDR marks, and sentence-distribution
  features (staccato, cascade, sentence CV, start entropy, first-person
  starts) need at least five sentences (`MIN_COMPARABLE_SENTENCES`).
  Baselines, dimensions and structural series use only comparable chapters;
  the dashboard marks affected values as unavailable and explains the
  minimum. Showing/telling z-scores, means and rankings apply the same word
  floor and mark shorter chapters `comparable: false` with null z-values.
  Recompute older reports before comparing.

### Added
- `about().heuristics` reports `min_comparable_words` and
  `min_comparable_sentences`; the style panel explains the minimum instead
  of hiding the reference when no chapter reaches the floor. Help texts and
  the chapter-matrix guide name the floors, in all supported languages.

### Security
- The dashboard shell carries a per-response nonce Content Security Policy
  (default-deny scripts, inline styles only) plus `Cross-Origin-Opener-Policy`
  and a `Permissions-Policy` denying device APIs.
- Access and debug logs keep the route without its query string, so research
  context and project tokens never reach log files. `SECURITY.md` documents the
  local-server baseline: loopback bind, Host allow-list, Origin guard, payload
  and artifact limits, and explicit non-goals.
- Manuscript review recognizes `adjusted` anchors: when the paragraph text
  changed but the recorded quote still appears exactly once, review names the
  state (highlighted at its current position) and
  `reconcile-manuscript --accept-moved` or the review tab's accept action
  re-pins the refreshed line span, paragraph hash and offsets as a new link
  revision. Editing the quote itself still requires review.
- Chronology accepts a plain hyphen between four-digit years (`1929-1933`) as
  a same-precision range next to the typographic dashes; the claim-time hint
  documents the form and a test verifies every localized example against the
  grammar.

## [0.4.6] - 2026-10-15

### Added
- `lixity research` manuscript-link commands: `link-manuscript` (explicit
  `--selection` or a `--quote [--line]` resolution), `manuscript-links`,
  `review-manuscript`, `find-anchor` (resolve a displayed-text quote to exact
  anchor fields) and `reconcile-manuscript` (preview or write re-pins for
  uniquely moved anchors). The native route
  `POST /api/research-manuscript-reanchor` and an accept action in the review
  tab complete the workflow; earlier anchors stay in revision history.

### Changed
- Manuscript review is paragraph-level: a changed source-file digest
  (`source_changed`) is informational and no longer marks associations for
  review while their paragraph hash, line span and quote still match; only
  changed, moved, ambiguous, withdrawn or re-pinned contexts need review.
- The dashboard folds whole chapters from their heading, opens paragraphs with
  a visible scroll and an arrival flash, keeps jump anchors precise, offers a
  reload action for stale manuscript contexts and filters long claim lists;
  the format-7 note moved behind a disclosure.
- Manuscript-link routes emit stable 409 `code` values (`stale-context`,
  `stale-archive`) that the dialog maps to localized, actionable messages.

## [0.4.5] - 2026-10-15

### Added
- `lixity research <record> --diff` previews an update as a terminal unified
  diff (dossier bodies line by line, other fields as before/after values)
  without writing; the record commands also name the update requirements in
  their help and error messages.

### Changed
- Research list commands (`claim`, `dossier`, `timeline`) read only the record
  kinds they display plus withdrawal state; a 22k-record archive lists claims
  in 0.38 s instead of 3.4 s. Snapshot digests and JSON envelopes are
  unchanged; write paths and lookups keep full-archive validation.
- Research archive snapshots check paths with plain strings and `os.path`
  calls instead of per-component `pathlib` checks.
- `lixity build` reports an unwritable `exports/` folder (sandbox, read-only
  mount) as one `[error]` line with a `--dry-run` hint instead of a traceback.
  `INSTALLATION.md` notes that product versions such as 1.18.0 or 3.0.1 in
  older notes predate the 0.3.0 renumbering.

## [0.4.4] - 2026-10-15

### Changed
- Installation and citation guidance is consolidated around the two published
  channels: PyPI for installing and upgrading, GitHub Releases for pinned,
  checksum-verified setups and Zenodo for citing a released version.
- First release archived by the Zenodo GitHub integration (concept DOI in
  `CITATION.cff`).

## [0.4.3] - 2026-10-15

### Added
- JOSS software paper draft under `paper/` with cited references, and a
  README research note.

### Changed
- The analysis section navigation and the checkbox rows are central components
  (`ANALYSIS_SECTIONS`, `section_nav`, `checkbox_field`), so new panels and
  controls reuse one markup source instead of a parallel implementation.
- The dashboard script is split into cohesive modules (`tooltips.js`,
  `interactions.js`, `research.js`, `project-ui.js`); `dashboard.js` keeps the
  generic core. Load order preserves the original execution sequence.
- Embedded screenshot dimensions are synchronised from the PNG headers after
  `make screenshots`.
- PyPI is the primary installation path in README, the installation guide, the
  landing page and the `llms` bundle; the pinned release wheel with
  `SHA256SUMS` remains the reproducible alternative.

### Tooling
- The release workflow accepts `workflow_dispatch` with a `tag` input and
  builds for PyPI without touching the immutable GitHub release.
- Repository hygiene covers local process, editor and tool state: `.pypirc`,
  `nohup.out`, logs, pid/socket/database leftovers, editor autosaves and
  additional tool caches are ignored and guarded by the hygiene test.

## [0.4.2] - 2026-10-14

### Added
- The Analysis view keeps a section navigation (flagged passages, sentence
  lengths, scenes, motifs, style, chapter matrix) with scrollspy; only panels
  the document actually renders are offered.

### Changed
- Scene detail tables render off-screen content on demand
  (`content-visibility: auto`) and only show project-target and register-median
  columns when the project defines them.
- On phones the analysis toolbar scrolls with the page instead of covering
  almost half of the viewport while reading.
- Control components are shared across views and modals: one `form-checkbox`
  component, a compact `ctl-sm` button size, canonical section headings, and
  removed one-off classes (`secondary`, `ctl-primary`, `research-check`,
  `publication-enable`).
- Layout uses one global `.row` primitive and spacing utilities on the shared
  `--space` scale; the Pages stylesheet consumes the canonical design tokens
  without alias duplicates.
- Local browser checks run in two groups: `make browser` covers the everyday
  core surfaces in parallel workers, `make browser-full` runs every suite
  sequentially before a release.

### Fixed
- Chapters stay fully rendered while scrolling, so anchor jumps and paragraph
  taps keep their exact target; only scene details defer off-screen rendering.
- The research API validates claim confidence, evidence relations and dossier
  languages at the boundary; unsupported dossier languages raise a clear error
  instead of a raw validation trace. Record schema versions share one declared
  union, so the models carry no type suppressions.

## [0.4.1] - 2026-10-14

## [0.4.0] - 2026-10-14

### Added
- `research dossier|claim|decision|sources` accept an explicit `list` verb, and the
  record lists render as a terminal table (`--format table`, ID/title/revision/date);
  the untrusted-host message names the loopback URL to use. The Project & Settings
  page orders by use: project settings, results (analysis + generated files),
  publication, thresholds, then the confidentiality agreement; the artifact list is
  named "generated files" and the manuscript comparison is collapsed.
- Project folders are recognizable while browsing: `/api/project-paths` reports a
  minimal probe for the listed folder (config, research archive, title, language,
  manuscript) and marks project directories; the Open Project chooser shows that
  line and a badge. The header and the Project view show a compact manuscript line
  (chapters, words, file), and the Project view lists the manuscript before the
  project settings.
- Two public-domain example analyses (Effi Briest in German, Pride and
  Prejudice in English) are published on the documentation site: an
  interactive excerpt of the opening chapters plus the complete PDF report;
  `make examples` regenerates every published example deterministically.
- Research record commands accept an explicit `list` verb
  (`lixity research dossier list`), identical to the default listing; the
  style-drift and distribution-shift headings explain Kendall's tau,
  Wasserstein and KS in all seven languages.
- The research Review tab lists saved manuscript associations with anchor
  state, review flags and the pinned quote; it loads when the tab is opened,
  with the shared review refresh and after a save, and never re-anchors or
  writes.
- A dependency-audit baseline (`make audit`, pip-audit) and a written update
  policy; Dependabot now also covers Python packages, and `release-check` runs
  the audit before producing artifacts.
- Every guide is also published as clean Markdown for AI agents
  (`<page>.html.md`, linked from the page and named in `llms.txt`); a generator
  and a sync test keep the alternates identical to their HTML sources.
- A comparison guide explains which manuscript analysis tool fits which job
  (grammar checkers, corpus tools, stylometry packages, story tools and Lixity),
  with a visible FAQ, source links and a clear statement of where Lixity does
  not fit.
- The public sitemap lists the embedded screenshots as image entries and the
  research guide's walkthrough as a video entry, all verified against the
  staged output; the guide articles carry `dateModified` metadata.
- The project dialogs explain their scope in one line. The import and new-project
  forms ask for an optional author name (used for PDF credits, the title page and
  the NDA) and name what the analysis language affects; the server stores the
  author only in a newly created project config.
- Claim creation and claim revision responses carry a `warnings` list when
  `time_period` is not placeable, and the native claim form shows the accepted
  calendar formats.
- `docs/llms-full.txt` bundles the maintained English documentation in
  reading order for AI agents and offline reading; `scripts/build_llms_full.py
  --check` (part of `make docs-check`) keeps the published bundle in sync.
- `lixity.math_core` is the single source for shared mathematical primitives:
  robust scale and significance z, the normal two-sided tail, ratio, share and
  density totalization, plug-in binomial/Poisson standard errors and the
  published Cliff's-delta bands. `style_fingerprint` re-exports the historical
  names.

### Changed
- `research-record-local/1` adds top-level `kind` and `record_id` (additive;
  the `record` body is unchanged). Scene detection also recognizes spaced
  divider lines (`- - -`, `_ _ _`, `• • •`), em-dash rules (`———`) and the
  asterism (`⁂`); the local server accepts IPv6 loopback `Host` headers.
- Dashboard renderer spacing and sizing use shared utility classes from
  `dashboard.css` instead of inline styles; measured and dynamic values stay
  inline, and `tests/test_inline_styles.py` keeps the migrated patterns out.
- Lixity is relicensed: the repository is open source under AGPL-3.0-or-later,
  with an optional written commercial license for integrations that cannot meet
  the AGPL. Writing for any purpose — including self-publishing — needs no extra
  permission now; the former LNCL-1.0 text stays available as `LICENSE-LNCL-1.0`
  for releases up to v0.3.0.
- Page titles and meta descriptions follow one messaging frame: at most 60
  and 155 characters, audience and job first, one differentiator (local,
  nothing uploaded) and no feature lists; the landing page adds durable
  `WebSite` data so results attribute the content to Lixity.
- Research writes reuse the verified snapshot of the current process while
  HEAD still names it, roughly halving claim creation and revision cost on
  large archives; a commit from another process is still detected and
  rejected, and the strict snapshot guard is unchanged.
- The claim chronology accepts `YYYY-MM` months and same-precision month
  ranges, and `api.revise_record` mirrors the CLI convenience of omitting
  `expected_snapshot` (current revision checked, changed associations still
  need explicit pins).
- The README now leads with a plain-language start for non-technical readers
  and keeps command, API and architecture references in a separate map. The
  landing page adds FAQPage, BreadcrumbList and feature-list structured data,
  package keywords and classifiers were extended, and the public research API
  functions carry complete docstrings.
- The Claims timeline shows each dated claim's placed calendar range, counts
  both sections, names the recognized formats and explains why free-text
  periods such as “present day” stay unplaced by design.
- NDA drafts offer the recipient a signature line or clear consent in text
  form (for example an email reply) and no longer ask the sending project
  representative for a separate handwritten signature on the sent copy; all
  seven language templates and the UI hint say consent, not signing.
- Research & Dossiers leads the Sources tab with the local add-source form;
  Zotero import follows as its own block and the retained list is titled
  **Saved sources** in all seven languages. The read-only source dashboard
  reuses the shared analysis renderer instead of a parallel path, and the
  language lexicons no longer carry internal duplicate entries.
- Public documentation and Pages carry the complete social/SEO head contract:
  Open Graph and Twitter images and titles on every page, per-page
  `TechArticle`/`SoftwareApplication` JSON-LD, refreshed sitemap dates and the
  read-only example named in `llms.txt`. `tests/test_pages.py` enforces the
  contract for every staged page.
- Cohesion pass on the native workspace: the dossier reading control and the
  measurement-note line join the reading toolbar, the project bar no longer
  repeats the manuscript name already shown in the status strip, the project
  panel title mirrors its navigation label, the research header shows the
  archive folder name with the full path as a tooltip, and the Zotero capture
  consent has its own label instead of duplicating the local-source consent.
- Project selection uses one resolver (`workspace.resolve_project_target`) for
  the foreground server, the open-project route and the service scope;
  `research/sections.py` owns the ATX section spans and edits (the research
  facade re-exports them, removing the deferred reverse imports);
  `run_server` raises on an occupied port and prints only when the CLI passes
  `announce=True`.
- Server status details and the no-project title come from the shared label
  packs in all seven languages, and every dashboard surface renders through
  `ui.render_analysis` with one labels/identity/metrics wiring.
- Tense heuristics use whole-word stop lists and curated noun exclusions:
  regular English `-ed` past of listed bases counts again (Pride and Prejudice
  +7 tokens), German `-tet` forms and noun confusions no longer count as past
  (Effi Briest −72 wrongly-as-past tokens), with no losses in the measured
  samples (see `docs/STABILITY.md` row 6).
- Sentence splitting treats `no.`/`co.` as utterance endings, the Spanish
  honorific `d` protects initials, paragraph sentence counts ignore tokenless
  fragments (matching the chapter metric), and `language="auto"` resolves with
  the sample text in the structure reports.
- Capability discovery reports image, PDF and manuscript-link support; the
  language and threshold key lists come from `language.LANGUAGE_CODES` and
  `config.THRESHOLD_KEYS`; co-occurrence degrees are returned in sorted node
  order.
- Dashboard and PDF builds reuse cached chapter splitting, precompiled literal
  patterns and one-pass style-layer bounds; a full novel builds about a quarter
  faster with byte-identical output.
- Release publishing attaches every artifact to a draft, attests them for
  `gh attestation verify` and publishes only the complete draft release;
  repository-level immutable releases protect published assets and tags.

### Fixed
- The analysis report PDF is composed as a document instead of flattened
  Markdown: an unnumbered cover page, real tables with right-aligned numeric
  columns, repeated header rows, whole rows and a PDF outline; the Guiraud
  label prints as `V/√N` instead of raw LaTeX. Book covers start on the
  optical third of the page.
- Chapter and status counters inflect their units (1 Absatz, 0 Auffälligkeiten),
  the reader panel uses the same name as its toolbar control, the footer separates
  product label and title, and an uninitialized research archive now shows the
  localized state instead of the English API message in the reader and
  manuscript-link panels.
- Dashboard artifact links use the served `/artifact/<name>` route instead of a
  bare filename, and the 200 MiB artifact serving limit is enforced.
- The configured dialogue cue compiles case-insensitively in the analysis core
  and profile, matching the documented cue contract; default patterns are
  punctuation-only and unchanged.

## [0.3.0] - 2026-10-12

### Added
- Manual manuscript quote–claim associations with explicit local retention,
  Unicode-codepoint paragraph anchors and exact claim pins. Creation, listing
  and structural review share the Python/native API; first opted-in save uses
  research record/manifest v7. Earlier archives remain unchanged on reads.
- Dossier research and companion readers list current explicitly linked claims
  with the existing claim viewer/history and exact-association saved quote counts.
  Counts do not infer whether prose uses a claim.
- Explicit selected-project publication fields in the existing Settings form
  and configuration loader, with one shared model for optional publisher/printer
  details, edition, year, format ISBNs, rights text, credits and other imprint
  information. A5 reading copies can include entered imprint text; no identity,
  address, copyright or DNB catalog statement is inferred.
- Shared PDF title/author/language metadata, A5 chapter bookmarks and bounded
  page headers. Book body pages retain physical folios; A4 sheets/reports show
  current/total page counts outside the body area.
- Publication guidance distinguishes German state print-imprint requirements,
  voluntary ISBNs/rights notices, separate legal deposit and BFSG ebook scope.
  Exports remain A5 book/A4 sheet/A4 report PDFs, without EPUB or PDF/UA/PDF/X
  certification.

### Changed
- Product version 0.3.0 describes development maturity before 1.0.
  Existing features and historical published releases/tags remain. JSON/storage
  versions are independent; 0.3.0 supports research records/manifests v1–v7.
- A collapsed global PDF menu remains accessible across all three workspace
  views, with one download action and the A5 reading copy default.
  Manuscript search and chapters appear before statistical diagnostics.
- Ordinary authored CLI `--update` requires the reviewed record revision, change
  kind and reason, while the archive-wide snapshot is optional. Same-record
  changes and races fail without retries; an explicit digest stays strict.
  Unchanged association pins remain, and changed associations in convenience
  mode require explicit reviewed versions. Strict Python/HTTP/batch guards stay.
- Release preparation reuses one shared source/tag/artifact checker through
  `make release-check RELEASE_TAG=vX.Y.Z`, including installed-wheel smoke checks.
  Version editing, review, tagging and publishing remain separate actions.
- GitHub Actions are reduced to one `check` job per pull request or `main` push.
  Browser and cross-platform suites run locally through `make browser` or on
  manual dispatch, and the tag workflow only builds, verifies, smoke-installs
  and publishes the reviewed release artifacts. Its third-party publisher is
  pinned to a reviewed commit.
- Dashboard and PDF builds reuse one selected-project configuration read when
  the manuscript and root share a directory. Author and publication settings
  remain project-local when they do not.
- Selected-project title, author and publication are saved together through the
  shared prepared configuration writer. Settings prepares the candidate view
  before committing; validation/read/render/write failures preserve previous
  metadata and session/cache state. Publication saves require selected-context
  tokens, and root metadata changes invalidate stale PDF download tokens.
- Publication stays in a collapsed disclosure within the existing Settings
  form. Dashboard and Pages presentation share the canonical bundled design
  tokens while exported dashboards remain self-contained.

### Fixed
- Project switching scopes a startup/custom title to its original workspace.
  Another book's header and NDA field use that project's identity. An explicit
  service restart into another project clears an inherited title unless replaced.
- Text and binary writes share fail-closed same-directory staging, fsync,
  original-mode preservation and cleanup. Replacement failures propagate
  instead of falling back to direct overwriting; text decoding failures use
  the existing `OSError` read-error boundary.
- Changed artifacts published in the same minute retain distinct versions.
  Stable links/copies are prepared before atomic replacement; failed publication
  preserves the previous stable artifact and reports an error before rotation.
- Marker read/encoding/write failures return clear HTTP 500 JSON errors;
  failed staged writes preserve manuscript bytes and do not report success.
- Genuine TrueType subsets retain glyph metrics and composite outlines,
  Unicode aliases copy correctly, and embedding-permission checks respect
  table versions. Unused font roles do not constrain the requested PDF layout.
- PDF headings and body text no longer share a baseline; first-line paragraph
  indents, long-header bounds and manuscript title detection reuse the shared
  layout/parser paths.

## [3.0.1] - 2026-10-11

### Fixed
- Foreground `serve` and managed `service start`/`restart` accept
  `--min-chapters`, including saved restart values. Previously, the controller
  accepted this option but its worker rejected it before server startup.

## [3.0.0] - 2026-10-11

### Added
- Read-only claim timelines in the CLI, Python API, HTTP API and native Claims
  view. Conservative CE year/ISO date/range placement preserves period labels,
  keeps unplaced periods visible and infers no date from record creation time.
- Authored cause/effect relations between exact claim revisions, with optional
  rationale, active/retracted state and shared correction/history/batch support.
  `results_in` aliases stored `causes` in the same direction; self-links fail,
  authored cycles remain, and no causal truth or additional edges are inferred.
- `research cite --query` resolves one source paragraph or returns ambiguous
  search candidates. Numbered selection requires the displayed snapshot and
  same query; exact `--passage` retrieval remains available.
- **Find source passage** reuses the existing Search/evidence draft flow.
  Optional evidence project/snapshot/claim-revision guards and native root
  tokens reject changed reviewed context; delayed search results are discarded.

### Changed
- **Breaking API change:** claims lists now consistently use
  `research-claims-local/2` with `claims`, `project_id` and `snapshot` from one
  read. The previous v1 list envelope has no alternate compatibility mode.
- Explicit causal relation writes opt storage into `research-local/6` and a
  v6 manifest, which earlier readers reject. Existing v1–v5 archives and their
  source/claim/citation/history bytes remain readable without conversion;
  timeline reads do not upgrade them. Export/restore preserves the existing
  bundle format and complete relation history.

## [2.4.0] - 2026-10-11

### Added
- Packaged `lixity service start|stop|restart|status` lifecycle commands and
  `python -m lixity`, using the installed Python without a source checkout.
  Default startup is an empty application-owned workspace; projects are explicit.
  Ownership/readiness checks and shared launchers replace separate Sh/PowerShell
  lifecycle implementations. Login startup remains an explicit manager choice.
- Native manuscript PDF downloads at the top of Manuscript & Analysis, with
  A5 reading layout as the default, A4 submission sheet and analysis report.
  Generation is explicit and reuses the CLI composer; standalone HTML has no
  download action. PDF attachments create no server export files and change no
  manuscript or research archive.
- `POST /api/manuscript-pdf` accepts a layout and opaque selected-context token,
  rejecting stale contexts instead of exporting a different project's manuscript.
  The response is a PDF attachment, separate from NDA generation.
- Source text selection prepares a claim evidence-link draft with the selected
  text and full retained passage shown before an explicit save. Ambiguous or
  cross-passage selections are refused; citations retain their existing scope.
- An optional Dossier alongside view keeps the manuscript and a chosen saved
  dossier together, with stacked panes on narrow screens. Reading creates no
  archive changes; closing restores analysis panels and retained manuscript state.
- `lixity research link PASSAGE_ID CLAIM_ID` creates an evidence link using the
  existing validation, defaults and version pins. `link-evidence` remains available.

### Changed
- Recommended application installation uses a pinned release wheel with
  uv-managed Python, without a Git prerequisite. uv owns installation, explicit
  release replacement and removal; project storage and application state remain.
- Existing-archive research CLI commands can omit `--project` when the current
  directory itself contains a verified initialized archive. Explicit paths win;
  no parent, environment or previous-project lookup is performed. Initialization
  and restore destinations remain explicit.
- Research status labels use author-facing language while preserving stored
  values and their interpretation limits; a linked source is not factual proof.
- Optional `project_token` on dossier reads binds the companion reader to the
  displayed manuscript selection. Calls without it retain their existing JSON.

### Fixed
- Local HTTP startup no longer performs reverse DNS after binding. This removes
  a confirmed macOS startup stall while preserving the actual bound port and
  readiness checks for foreground and managed servers.

## [2.3.0] - 2026-10-10

### Added
- Goal-oriented welcome steps lead from manuscript import and language confirmation
  to reading a passage. Further tools use a collapsed native disclosure, and empty
  analysis opens the existing import directly without submitting a file.
- A compact review entry links an actual tense-flag candidate in source order (or
  the opening passage), chapter patterns and available sentence rhythm. These are
  routes for human review, not a literary quality ranking.
- A public, read-only synthetic example and a three-minute first-look guide.
  The report is generated by the shared engine with explicit defaults, supports
  existing paragraph/filter/chart interactions, and accepts no uploads or edits.
- `research dossier-image` captures a local PNG/JPEG and revises its dossier in
  one atomic API operation. Explicit retention permission, archive snapshot and
  dossier revision are required; existing validation and image limits apply.
- `lixity pdf --layout report|book|sheet` composes a PDF document without any
  external converter. Fonts are embedded as TrueType subsets with Unicode mappings. Covered
  characters remain searchable and copyable; unsupported visible characters
  fail explicitly. The sheet layout is a fixed grid of up to 30
  lines of at most 60 characters; the book layout is A5 with a serif measure
  and chapter openings.
- The analysis toolbar searches the manuscript itself and filters the chapter
  list to the matching paragraphs, with a match count and step-through. Until
  now only the research archive could be searched. Manuscript text is inserted
  as text nodes, so a phrase that looks like markup stays inert.
- PDF layouts follow measured typographic practice: type size is fitted to the
  real text so lines land in the 45-75 character band, paragraphs are broken by
  a shortest-cost search instead of greedily, justification tightens as well as
  stretches and never stretches a line's last one, book margins mirror for
  double-sided printing, baselines sit on a leading grid, and Markdown emphasis,
  code and table syntax no longer leak into the exported text.

### Changed
- Opened paragraphs show the manuscript text before their measurements and
  marker actions. Paragraph values use a compact native disclosure, localized
  as “Values” in English and “Werte” in German.
- Closed paragraph contents are created when opened with JavaScript enabled;
  the no-JavaScript fallback keeps the complete paragraph text readable.
  Manuscript search still checks the complete embedded paragraph text and renders
  markup-like text safely. The self-contained HTML remains usable offline; the embedded
  manuscript and measurement data still grow with the input.
- Chapter comparison, style reference, dimensions and structural diagnostics
  share one tabbed style area. Existing anchors select the relevant panel;
  keyboard navigation and readable panels without JavaScript are preserved.

### Fixed
- Restarting a stopped local service attempts startup instead of returning
  success after the no-op stop; startup failures retain a nonzero exit status.
- PDF command discovery in `about` and Bash/Zsh completion matches the implemented CLI.
- Active manuscript search takes priority over the flagged-only filter, so
  unflagged matches remain visible. Clearing search restores the selected filter.
- PDF page numbers embed their required digits even when the manuscript has none.
  Final lines obey the page measure, overlong words wrap without losing
  characters, and justified text applies negative word spacing correctly.
- PDF rendering checks every drawn visible character against its selected font
  and reports an unsupported character with its font role and Unicode codepoint.
  Default report fonts prefer DejaVu Sans regular/bold for generated analysis
  symbols; explicit font choices remain supported.
- Research shell-completion command names come from the same parser metadata as
  `about`, including image attachment and the existing revision/review commands.
- Supplied source-context JSON must be an object. Invalid scalar/array/null input
  is reported through the CLI error channel without accepting a capture.
- The security policy links to the current release instead of retaining an old
  version claim. Image guidance distinguishes generated references from evidence.
- Long research titles wrap within their cards on mobile. Project-opening
  guidance explains that CLI work does not switch an already running web server.
- Source/dossier refreshes coalesce pending reads, ignore superseded responses
  and preserve unchanged open details. Full-list reconciliation is linear.
- OCR page timeouts stay within their original budget even when floating-point
  deadline subtraction rounds upward; the shared deadline still expires.
- Default nominal-suffix counts exclude curated function words across corpus,
  chapter and paragraph measurements. Custom regex semantics are preserved.
  Regenerate older nominal-style reports before comparison.
- Unavailable show/tell comparisons use a clear status instead of empty score
  tiles. Paragraph guidance explains density units and small-sample effects;
  an empty marker list is no longer described as a clean manuscript.
- API browser diagnostics report request metadata without retaining response
  contents in the console.

## [2.2.0] - 2026-10-09

### Added
- A project-scoped Author name setting persists in `lixity.toml` and fills the
  project representative in NDA exports. The five recipient/document fields
  and stateless download interface remain unchanged; no personal default is built in.
- A read-only title/author comparison recognizes explicit flat manuscript
  metadata and leading title-page bylines. Missing, unsupported and mismatching
  values are distinct; it neither infers authorship from prose nor edits text.
- Optional `project_author` in project-owned NDA text models, retaining all
  existing placeholders. Unknown fields and invalid configured names fail visibly.

### Fixed
- Saving an author updates only that project field, preserves unrelated TOML,
  comments and line endings, and refuses malformed or concurrently changed files.
  Unavailable projects cannot accidentally store personal data in the server cwd.
- Invalid author metadata does not abort unrelated mathematical analysis;
  identity/NDA consumers report it explicitly. Existing threshold and title
  session behavior remains unchanged.
- Author identity excludes global and ancestor defaults and stays with the
  selected project even for a nested imported manuscript. Unreadable manuscripts
  report an unavailable comparison rather than claiming metadata is missing.
- Workspace tabs and dialog controls inherit the shared UI font. Settings,
  dialogs and research headings reuse text, weight and line-height tokens;
  technical identifiers use the shared monospace role.
- Metadata-only PDF refresh reports retained-extraction verification instead of
  announcing skipped OCR work. Extraction reuse and revision contracts are unchanged.
- Opening a live workspace no longer requests a missing server favicon or emits
  its unrelated console error; the offline dashboard declares an empty inline icon.

## [2.1.0] - 2026-10-08

### Added
- Local PNG/JPEG references in dossier full, section and history views, with
  browser-only preview, explicit retention, exact saved-image versions and
  keyboard enlargement. Capture and dossier revision publish in one commit;
  rejected saves accept neither. Existing archive export/restore and audit apply.
- Section editing reuses the revision editor and canonical heading parser,
  preserving concurrent changes outside the selected subtree. Contextual claim
  and decision actions select the current dossier by title in existing forms.

### Fixed
- Sequential decision acknowledgements advance only tokens from their own
  accepted operation. External changes still require explicit review; current
  flags and counts stay aligned without stealing unrelated draft focus.
- Marker notes have explicit Save/Cancel, visible errors, retained failed drafts
  and a pending guard; real HTTP failure statuses cannot appear successful.
- NDA agreements use shorter, direct wording in all seven languages. The recipient
  field is clearer, output titles omit the software “draft” label, and signing
  guidance stays in the app. The five-field, stateless interface is unchanged.
- Settings share the core numeric policy, preserve exact floats and unposted
  fields, and remove artificial UI ceilings/decimal step rounding. Invalid
  JSON types, nonfinite values and inconsistent bounds fail visibly.
- Image references validate exact project/source/version ownership, including
  purge placeholders. Raster imports never retry external publication conflicts;
  textual analysis rejects image sources before decoding.
- Restored shared layout configuration and inline Markdown helpers keep existing
  book adapters importable; attribute values and links remain treated as data.

### Changed
- The native workspace has one Update analysis action; both HTTP aliases and
  distinct embedding capabilities remain supported. Manuscript selection opens
  its import preview directly; confirmation still creates a separate project.
- Initial research lists reuse the overview response. Optional form details are
  collapsed, paragraph filters have a reset and scene links use actual containing
  chapters. No persistent cache or invented scene positions are introduced.
- Version-purge Tombstones with explicit source ownership use `research-local/2`.
  Existing v1 bytes remain unchanged; 2.0.0 rejects the new owner-bearing records.
  PNG/JPEG source bytes have no fabricated text extraction or passages.
- English documentation and reviewed synthetic screenshots follow current feature
  workflows. Service setup uses one port setting; API examples avoid duplicate
  analysis passes. New browser cases join the existing single Chromium job.

### Removed
- The source-only experimental Unlimited-OCR CPU bridge and its adapter-specific
  parser test. Built-in local Tesseract and the generic external-worker protocol
  remain supported; custom model runtimes belong to their deployment projects.

## [2.0.0] - 2026-10-07

### Added
- Opt-in sequential research checkpoints retain completed extraction across
  interruptions and publication conflicts. Resume verifies files, configuration,
  project and source identity; changed HEAD needs explicit acknowledgement.
  New checkpoint envelopes preserve ordinary ingest and archive contracts.
- Concise editable NDA drafts in all seven interface languages, with name,
  optional address, project name, date and place. Protected disclosure and
  signature sections remain. Native PDF/text downloads do not register people
  or persist agreements, and long text is paginated without truncation.
- A semantic chapter-score table and native rotation/zoom controls accompany
  the 3D plot, including chapter navigation without JavaScript.
- A live `GET /api` index describes registered routes, and research commands
  expose consistent JSON aliases without changing their human-facing defaults.
- Recently opened projects appear on the welcome screen and Open dialog;
  browsing reuses the native chooser, with explicit local history clearing.
- Plain-language revision acknowledgement controls are localized in seven
  languages and pin exact decision/dossier versions in v5 research events.
- The guided OCR/Zotero setup check reads connection metadata without importing
  records, installing software or writing configuration.

### Fixed
- PDF capture extracts a stable copy of the exact retained bytes, preventing
  mismatched evidence if a source file changes during extraction.
- Native NDA export uses the effective project language or an explicit document
  language. Invalid templates are rejected; document responses go directly to
  preview/download without a recipient registry or server file publication.
- Browser debug preferences explicitly save both enabled and disabled values,
  surviving reload with server debug enabled. Request and error-detail logs use
  one UTC timestamp writer.
- Expected client disconnects during cancelled browser requests no longer
  cause false HTTP 500 responses or tracebacks; NDA responses use the shared sender.
- Paragraph chips and style controls have at least 24px targets, or 44px with
  coarse pointers, including the pressed state.

### Changed
- Maintained docs remove private-adapter export/backup claims and explain
  five-field NDA downloads, editable text models and heuristic limits.
- Research overview requests validate one archive snapshot and reuse the
  listing helpers. Source versions are grouped once rather than rescanning
  the archive for every source; there is no persistent cache or output change.

### Removed
- NDA recipient databases, numbering, encryption/unlock/status administration
  and project Python export adapters. `/api/nda-draft` replaces the old NDA
  management actions. Back up prior project NDA data before replacing generated
  drafts; software regeneration does not amend a signed agreement.

## [1.25.0] - 2026-10-06

### Changed
- Style dimensions use standardized tied midranks on one complete chapter set.
  Scores and explained variance share that space; missing chapters are omitted
  from the plot and its coverage is shown. Passport schema 4 adds
  `meta.dimension_space` and `meta.dimension_chapters` without renaming fields.
- Shared supported-prose handling excludes metadata, headings, comments, code
  and footnote definitions from analytical measurements. Quoted prose remains
  measured; paragraph profiles retain their narrower body/list scope. Legacy
  whitespace counts remain separate. Rebuild exports and comparisons after
  these input-scope and numerical corrections; previous scores can change.
- Seven-language UI help uses plain-language definitions and reading examples;
  existing methods, stability, command, research and interpretation guides
  distinguish exploratory signals from calibrated inference. Nominal selections
  and empty diagnostics do not certify prose.
- Syllable calculations reuse word frequencies within each request, without a
  global cache. Empirical distribution comparisons use one sorted linear merge;
  segmentation accumulates centred moments instead of rescanning segments.
- Actions runs native Poppler cases on the primary Linux Python version and
  macOS; other compatibility versions retain all non-native tests. Separate
  browser/platform workflows use built-in path filters, cancellation and caches;
  core checks remain unconditional and release checks install Poppler explicitly.

### Fixed
- Guarded changepoint segmentation now considers every predecessor: the old
  pruning rule could discard the best partition. The legacy `pelt_changepoints`
  name remains, with quadratic time and linear memory. Per-endpoint anchors
  preserve small variances after distant observations or large translations.
- Wasserstein distance integrates empirical CDFs correctly for unequal sample
  sizes. KS returns probability 1 for identical distributions and uses a stable
  limiting-tail calculation for small distances; probabilities remain approximate.
- Sn uses the original low outer/high inner order statistics. Qn uses the modern
  asymptotic factor 2.21914. Neither adds finite-sample correction. The unchanged
  Kendall statistic is labelled tau-a, and the legacy degree-fit helper correctly
  attributes its approximate exponent and discloses its uncalibrated probability.
- MTLD averages the two directional lengths rather than pooling their factors.
  Threshold, partial-factor and short-text policies remain documented.
- Explicit tokenizer flags survive every analytical surface. German/English
  default patterns retain accented words and emphasis; LF/CRLF paragraph boundaries
  agree, and the configured inclusive threshold includes exactly eight words.
- Chapter headings inside code or comments no longer split prose; scene dividers
  around chapter prose are not mistaken for document metadata. Source anchors
  remain unchanged. Structural jump links follow measured chapters when a feature
  is unavailable in an intervening chapter.

## [1.24.1] - 2026-10-04

### Fixed
- Native PDF extraction validates its timeout before checking for Poppler tools,
  so invalid settings fail consistently whether or not Poppler is installed.
  This is the first published artifact release for the features introduced by
  the v1.24.0 source tag; that tag is retained without binary release assets.

## [1.24.0] - 2026-10-04

### Added
- Scene/register reports in the API, CLI and dashboard: existing measured
  features, explicit project targets, separate manuscript-only register
  medians/MAD, sample counts and approximate standard errors. No genre targets
  or literary quality judgments are built in.
- Read-only three-way revision previews, explicit conflict choices and atomic
  groups of authored revisions. Drafts and reasons survive failed saves.
- Decision impact and editorial review views based on explicit links, dates and
  revision pins; these are maintenance candidates, not semantic validation.
- Optional local Tesseract OCR without a worker service, installed-language
  diagnostics and honest versioned provenance (research activity/manifest v4).
- Opt-in text/Markdown research source and audit summaries, bounded human
  lists and an explicitly requested interactive pager. Default JSON is retained.

### Changed
- Shared configuration resolution keeps explicit corpus settings aligned across
  CLI, API and dashboard. Scene measurement reuses the chapter feature engine
  without a second corpus analysis per scene; display reports reuse already
  measured whole chapters when no scene dividers are present.
- Scene terminal reports reuse the shared translated labels, units and number
  formatting. Safe terminal text lives in the common formatter rather than the
  experimental research package; JSON output is unchanged.
- Actions runs the collected Python tests once per environment, cancels
  superseded runs, caches Pip downloads and discovers all platform research
  tests. Release tags retain their dedicated checks instead of a second full
  test matrix; platform and Python coverage are preserved.
- Wheel verification compares every package filename and byte with the current
  source, catching removed modules left in incremental build directories.
- README and the project page introduce six features with contextual screenshots
  and links to related views, replacing the large image galleries. The page uses
  a simpler responsive layout, native full-size image links and a shared theme
  preference across the HTML guides.
- Installation, onboarding, localization and contributor guidance use shorter
  English explanations. German remains the first focus for linguistic resources;
  the default analysis language remains English.
- Screenshot generation reuses the original dashboard and shared browser startup
  helper. `make serve` and `make stop` delegate to the existing port-scoped
  launcher. Dated internal review reports are removed from maintained product
  documentation and the Pages publication boundary.

### Fixed
- Dossier section handling ignores fenced code, rejects ambiguous repeated
  headings and preserves unrelated bytes and line endings. Reads and edits use
  the same subtree boundary, preserving nested notes in a read/edit round trip.
  Existing decision dossier pins are retained when editing their ID list.
- Configured chapter boundaries and empty units use shared numbering; fenced
  scene separators are ignored. Headerless drafts retain every paragraph and
  original line anchor rather than dropping their first line as a title.
- Custom chapter headings are excluded from global prose counts as well as
  chapter measurements. Patterns matching a whole heading retain the following
  prose. Entropy uses stable summation and renders zero without a negative sign.
- New native PDF captures identify Poppler rather than an unrelated OCR model.
  Existing cached provenance is preserved. Native extraction deadlines reject
  incomplete output, and failed worker or Tesseract probes report failure.
- CI uses `actions/setup-node@v7`, whose Node 24 runtime and updated cache code
  remove the Node 20 action-runtime and built-in `punycode` deprecation warnings.
  The browser job continues to test with Node 22.
- Deprecated HD-D sampling arguments and the legacy matrix wrapper remain
  available. Their earlier removal dates are deferred; replacement guidance
  reflects the exact estimator and separate matrix data/rendering interfaces.
- Guides correctly describe phase-based import progress, native NDA support and
  the research archive's introduction in v1.16.0.

## [1.23.0] - 2026-10-03

### Added
- **Local research list filters:** Sources and dossiers can be filtered by title,
  tags and ID; dossiers also match excerpts and section names. Filtering uses
  loaded metadata, keeps opened details and association options, and sends no
  request while typing. Full-text research search remains a separate action.
- **Visual loading feedback for Research Workspace**: Added centralized accessible loading indicators (`loading_state()`, `.loading-spinner`, `.ctl-status.loading`) and localized labels across 7 languages, providing immediate visual feedback in the header and list views while research project data and records are being initialized or retrieved.
- **Structural diagnostics panel in Web UI**: Integrated PELT changepoints (stylistic phase shifts across chapters), Mann-Kendall monotonic trend tests (gradual stylistic drift), and early-vs-late distribution shifts (Wasserstein distance and Kolmogorov-Smirnov test) into the web dashboard style suite (`#structural`), complete with clickable chapter anchors and full localization across 7 languages.
- **Fluid responsiveness enhancements**: Refined multi-column and table layouts across tablet, mobile, and intermediate viewports; enabled fluid clamp sizing for the 3D stylistic space canvas, prevented table scrollbar overflows on compact metadata tables, and improved touch target minimum sizes for mobile devices.
### Changed
- Metric help in all seven languages now distinguishes descriptive signals from
  literary judgement: Guiraud remains length-sensitive, Flesch can exceed 0–100,
  long sentences do not establish syntactic nesting, and style bands are not
  mandatory targets. Show/Tell explains intentional register differences;
  chapter-based scene estimates disclose their units.
- English and German terminal/Markdown reports use neutral sentence-length
  descriptions and no longer infer syntactic complexity or pace from length.
- The deprecated `research_api.claim_matrix(format=...)` compatibility wrapper
  remains available. Its previously announced v1.23 removal is deferred to a
  future release; the data and rendering replacements remain recommended.
- **Workspace navigation:** Research & Dossiers, Manuscript & Analysis, and
  Project & Settings have separate views. New Project, Open Project and optional
  guidance remain accessible from every view.
- **Manuscript selection:** File selection and drag/drop show the filename without
  submitting. The native server's **Continue to import…** opens the existing import
  dialog; confirmation creates a separate project. Embedding hosts with the load
  capability retain **Analyze manuscript now →** and the existing load payload.
- **NDA presentation:** The capability-gated manager is a native details panel,
  collapsed initially; its backend behavior is unchanged.
- **Frontend architecture modularization**: Refactored the monolithic 1600-line `render_dashboard()` in `src/lixity/ui/dashboard.py` into focused, single-responsibility modules: `modals.py` (project creation, open, and research revisions), `research_panel.py` (Zotero ingest, search, dossiers, claims & evidence, editorial decisions, grounding), `narration.py` (sentence distribution, dialogue, characters, pacing, motifs, showing vs. telling), `heatmap.py` (z-score heatmap matrix and self-calibrating style passport reference bands), and `markers_panel.py` (work markers table). Preserved all DOM IDs, CSS class contracts, and multi-language support.
- **Client-side API consistency**: Standardized the research matrix endpoint URL in `dashboard.js` to dynamically prefix `(API || "/api")`, avoiding hardcoded root path assumptions.
- **Touch and tablet research tab responsiveness**: Enhanced `.research-tabs` with clean touch-friendly horizontal swipe scrolling and flex-gap on tablet and mobile viewports.

### Fixed
- Dialogue token counts use the configured word tokenizer for both numerator
  and denominator, matching chapter, paragraph, dialogue and pacing reports and avoiding
  punctuation-only counts above 100%.
- Show/Tell ranking arrays stay empty when chapter balances cannot be
  distinguished. The dashboard shows unavailable comparisons as dashes for
  fewer than three chapters or absent comparative signals.
- Maas a² returns its defined value for a corpus with a single word type when
  the existing 100-token minimum is met.
- A successful OCR worker probe no longer hides an invalid timeout or missing
  rasterizer. PDF extraction warnings survive explicit native fallback through
  local, batch and Zotero import results and appear in dashboard import status.
- Manuscript selection stays locked against duplicate submissions while reading.
  Import previews clear before a replacement read, ignore obsolete completions
  and remain unconfirmable on read failure. The import file picker also supports
  click, Enter and Space without an empty-selector error.
- **Port-scoped server lifecycle**: `scripts/lixity-start.sh` and `scripts/lixity-start.ps1`
  now scope PID and log files per port (`lixity-<PORT>.pid` / `.log`), preventing
  cross-port `stop` signals and ensuring multi-instance isolation.
- **Stale and recycled PID handling**: `status` and `stop` verify port responsiveness
  and automatically clean up stale or recycled PID files without targeting unrelated processes.
- **Config recovery documentation**: corrected `docs/USAGE.md` to remove references to
  non-existent threshold fields in the CLI JSON meta block.

### Documentation
- Regenerated and reviewed 35 screenshots using public-domain analysis text and
  synthetic project/research fixtures; README and Pages galleries include mobile
  states, complete dialog forms and full-size links.
- Methods and workflow guides clarify minimum-data guards, manuscript-only style
  baselines, heuristic limitations, phase progress messages and OCR health checks.

## [1.22.0] - 2026-09-30

### Changed
- `lixity.server` split from one 1655-line module into a focused package
  (`runtime`, `views`, `_state`, `_base`, `routes_project`, `routes_research`,
  `routes_nda`, `routes_markers`, `handler`, `constants`). The public import
  surface is unchanged.
- HTTP routing is declarative via `GET_ROUTES`/`POST_ROUTES` tables, replacing
  the `do_GET`/`do_POST` if-ladders.
- Research API separates data from rendering:
  `compare_source_to_manuscript()` returns only data (the `format` parameter and
  two `@overload` stubs removed), and `claim_matrix_data()` /
  `render_claim_matrix()` replace the mixed `claim_matrix(format=...)`.
- Cross-platform server lifecycle scripts: `scripts/lixity-start.sh`,
  `scripts/lixity-start.ps1`, `scripts/lixity.service`, `scripts/lixity.plist`,
  plus `make serve` and `make stop`.

### Deprecated
- `research_api.claim_matrix(project, format=...)` emits a `DeprecationWarning`
  and will be removed in v1.23.0. Use `claim_matrix_data()`,
  `render_claim_matrix()`, or `claim_matrix_format()`. JSON output and the
  `lixity research matrix` CLI are unchanged.
- `lixity.diversity.hd_d()` and `hd_d_stats()` accepted `seed` and
  `min_samples` as no-ops left over from the superseded Monte Carlo estimator.
  They are now keyword-only, warn when passed, and are removed in v1.24.0.

### Fixed
- **Silent analysis change**: a malformed `lixity.toml` was treated as absent,
  so the run reported default language and thresholds and still exited `0`. A
  present-but-unreadable or unparseable file now warns and names the path.
- **Silent capture truncation**: an undeterminable PDF page count was assumed to
  be 1, so a multi-page document could be captured as one page and still report
  success. The extractor now refuses with actionable guidance.
- **Project NDA adapter**: an adapter raising at import time disabled the
  feature instead of falling back, and the fallback was silent. It is now caught
  as `Exception` (never `BaseException`) and announces itself.
- NDA PDF receipts now contain a valid cross-reference table and declare a font
  resource; previously no text was extractable.
- `lixity serve` reports an occupied port with actionable guidance instead of a
  bare `OSError`.
- `research search --strict` reports a missing index as such instead of blaming
  FTS5 availability.
- The server lifecycle launchers detected readiness by grepping the log for the
  startup banner, which a block-buffered daemon never writes; they now probe
  the port.
- `nda` encrypt/decrypt return annotations no longer depend on the undeclared
  optional `cryptography` package being installed, which broke strict mypy in
  the configuration CI uses.
- The documentation version-drift check now enforces that statements asserting
  the current release name the single source of truth, instead of only checking
  whether its own pinned strings need rewriting.

### Removed
- `layout.py` and `inline_markdown_to_html()`: unreachable code with no
  references outside their own test.
- `vargha_delaney_a()`, `contextlib_suppress()` and `parse_markdown_file()`:
  dead helpers. Vargha–Delaney A was never emitted; `METHODS.md`,
  `STABILITY.md` and `llms.txt` now describe the Cliff's δ labels that are
  actually reported.

### Docs
- `AGENT_PROFILE.md` added and delegated to from `AGENTS.md`, with agent
  operating rules covering verification, formatters, data boundaries,
  escalation, and the silent-degradation failures this release fixed.
- NDA HTTP endpoints documented in `docs/AGENTS.md` §5.2.
- `ARCHITECTURE.md` documents the server package; `docs/research/USAGE.md`
  retitled from "pilot" to "archive".
- `STABILITY.md` gains register rows 52-55; two long-standing rows were
  rendering with the wrong column count because of unescaped `|` in table cells.
- Published-surface audit: six `../` links resolved in the checkout but 404'd on
  Pages, because staging flattens `docs/<name>` to `/<name>`. Now absolute URLs,
  with two tests validating the staged tree rather than the checkout.
- Four documents described the search freshness check as comparing manifest
  timestamps; it compares the recorded snapshot digest. Corrected.

### Verified
- Issues #10, #11 and #12 checked as 30 executable assertions mapped onto their
  stated claims; 30/30 pass. Evidence posted to each issue and all three closed,
  with the remaining work split into #13 and #14.
- 564 tests, 2764 subtests under `-W error`; the staged Pages output resolves
  all 94 of its relative links and heading anchors.


## [1.21.0] – 2026-09-30

### Added

- Research engine — claim-evidence matrix export (Issue #11):
  - `lixity research matrix --format md|csv|json [--output FILE]` generates a
    structured table of claims with linked evidence, confidence levels, and source keys.
  - `claim_matrix()` API for programmatic access.
- Research engine — Zotero batch ingest (Issue #11):
  - `lixity research zotero-ingest --item-key <KEY>` ingests all eligible PDF and
    text attachments of a Zotero parent item with per-attachment error isolation.
  - Multi `--attachment-key` support for batch ingestion in a single call.
  - `lixity research ocr-status --probe` / `ocr_status(probe=True)` pre-flight OCR probe.
  - `--fallback` / `LIXITY_OCR_FALLBACK=1` for Poppler `pdftotext` fallback; reliable
    multi-page PDF detection via `pdfinfo` or binary `/Count` scan.
- Research engine — cross-corpus Markdown grounding report (Issue #11):
  - `lixity research compare --format md [--output FILE]` exports Jaccard similarity,
    Dunning G² key terms, chapter density table, and top-N term breakdowns as Markdown.
  - `compare_source(..., format="md")` API with overloaded return types for mypy strict.
- Web dashboard — research panel improvements:
  - Search-hit highlighting via `<mark class="search-hit">` wrappers in results.
  - Collapsible dossier section outlines in list cards with section overview badges.
  - Compare/grounding card renders Dunning G² key terms with accent border styling.
- Localization: `research_source_key_terms` label added in 7 languages (EN/DE/FR/ES/IT/PT/NL).

## [1.20.0] – 2026-09-29

### Added

- Research workflow ergonomics and friction reduction (Issue #11):
  - Automatic fresh FTS5 search indexing by default when catalogue is stale, with
    an explicit `--strict` flag to fail instead of reindexing.
  - Multi-file batch ingestion returning `research-batch-ingest-local/1` with per-file
    outcomes, error resilience, and progress reporting to stderr with `--progress`.
  - Section-bounded dossier reads via `--summary` and `--section <name>`, as well as
    section-level revision targeting without overwriting entire dossiers.
  - Decision-dossier linking and automated `review_needed` tracking when decisions
    affecting a dossier are added or updated.
  - 4-phase Zotero literature acquisition walkthrough and backup scope comparison
    table in documentation (`docs/research/USAGE.md`).
- Project-isolated NDA management provider and server endpoints (Issue #12):
  - Configurable project capability interface (`ProjectNdaProvider`) with PBKDF2
    key derivation, authenticated encryption (AES-GCM / HMAC fallback), record CRUD,
    and synthetic PDF export.
  - Project isolation: recipient names, notes, passphrases, and keys remain strictly
    in project-owned `<project>/nda/` and are never emitted to server logs.
  - Dynamically enabled NDA management tab in `lixity serve` when projects configure
    `[nda]` or contain project NDA capability.
- Research dashboard web UI improvements (`lixity serve`):
  - Visual `⚠️ Review needed` badge on dossier cards and warning banner in dossier
    inspector with linked decision rationale.
  - Outline summary of sections in dossier inspector view.
  - Scope guidance hint in research search when scoped search yields 0 hits, with
    one-click option to switch to all records.

### Changed

- Reorganized the website and README around manuscript exploration, chapter
  comparison and traceable research. Moved detailed review signals and the
  research CLI walkthrough into the corresponding guides; integration details
  remain with the developer interfaces.
- Harmonized dashboard and Pages action colors, neutral surfaces and local title
  fonts. Increased reading-text and primary-control sizes, strengthened keyboard
  focus and active-tab cues, and respected reduced motion on Pages.
- Heatmap labels now choose contrasting text independently of the system theme;
  data colors and analysis results are unchanged. Narrow file controls wrap
  within the workspace at mobile widths.
- Reviewed installation, onboarding, research and public guides against current
  behavior; clarified release versus main documentation and refreshed example
  screenshots. Corrected documented readability coefficients and syllable units
  to match the existing implementation, without changing calculations.

## [1.19.0] – 2026-09-27

### Added

- Optional Zotero Desktop integration through its local read API: browse explicit
  libraries and collections, inspect attachments, capture selected PDF/text files
  with consent, refresh linked sources and open originals from the dashboard.
  Images, audio and video stay in Zotero; no cloud account or background sync.
- Structured Zotero attachment identities in `research-local/3` captures and v3
  manifests, with duplicate prevention and explicit refresh on changed captures.
  Older readers reject v3; previous quotations and archive history are preserved.
- Additive RIS migration export with source identity tags and original files;
  paired backups of the research archive and an explicitly closed Zotero data
  directory, restored only into a new destination after checksum verification.
  Manuscripts, application profiles and external linked files need separate backup.

- Optional research search scopes for current dossiers, claims and decisions,
  using the shared FTS5 catalogue. Typed `research-search-local/2` hits expose
  record identity, revision and excerpts; default source-only CLI/API search
  retains v1. The seven-language dashboard searches all types by default and
  opens authored hits in the existing revision viewer. History is not indexed.
- Server debug logging through `serve --debug` or `LIXITY_DEBUG`, with browser
  API/runtime diagnostics and `setLixityDebug()` controls (added after v1.18.0).

### Fixed

- Align maintained guides and automation examples with the shipped v1.18.0
  CLI/API contracts, Portuguese UI locale, and released origin URL, PDF/OCR
  diagnostics and unavailable-consistency behavior. Correct research ingest help
  to mention PDF support and the separate scan worker requirement.
- Reuse existing PDF extraction when a refresh changes metadata but retains
  identical original bytes; preserve extracted text and earlier citations.
- Document debug precedence on reload and timestamp scope.
- Preserve source criticism when binding an existing capture to Zotero. Treat
  personal-library aliases as one attachment identity and reject ambiguous links.
- Reject failed, malformed or incomplete configured OCR worker output instead of
  silently falling back. Keep unknown confidence unset and preserve physical page
  order. `LIXITY_OCR_TIMEOUT` accepts 1–3600 seconds (default 120).
- Add an experimental checkout-only Unlimited-OCR CPU adapter with pinned model
  weights, page checksums and truncation checks. Its external runtime and model
  weights are optional and are not bundled in the Python package.

## [1.18.0] – 2026-09-27

### Changed

- Source import now accepts an optional origin URL in the UI, CLI and Python/HTTP
  APIs. URLs are retained as capture context without network access; old citations
  preserve their original provenance. URL-bearing captures require `research-local/2`
  and v2 manifests, which older readers reject. URL-free v1 encoding is preserved.
- Browser OCR setup labels and guidance use all seven workspace locales. Configured
  workers are no longer described as verified or active inference services.
- Consistency displays “–” when no chapter–feature cells are measurable. Empty
  chapters no longer manufacture measurements. Style JSON v4 adds `measured_cells`
  while retaining the legacy numeric consistency sentinel for compatibility.
- Text/PDF browser imports share temporary-file handling and parameter forwarding.
- Public guides cover installation, metric interpretation, origin URLs, PDF/OCR
  setup and backup verification. Pages uses one shared stylesheet, internal guide
  navigation and an expanded sitemap; release and current-main features are distinct.
- Separate local planning under `.planning/` from product documentation; preserve
  earlier tracked plans locally and remove them from public sources. Repository
  guidance documents the boundary, and Pages stages only approved product paths.
  Ignore agent worktrees and test artifacts without hiding public examples or tests.
- Document the verified Unlimited-OCR source pins, custom adapter requirement,
  upstream runtime differences and limits of OCR provenance and diagnostics.
- PDF CI installs Poppler on Linux/macOS; dependency-dependent tests report explicit
  skips elsewhere. The mock worker runs across platforms, and the synthetic
  archive-tampering fixture avoids deprecated implicit tar extraction behavior.

### Added

- **OCR diagnostics and status check**: `lixity research ocr-status` CLI command and
  `/api/research/ocr-status` HTTP endpoint diagnosing poppler tools (`pdftoppm`, `pdftotext`),
  worker executable permissions, configured model identifiers, and actionable setup guidance.
  Included in the research panel status bar. It does not verify model integrity or inference.
- **Staged import progress and native PDF upload**: Base64 binary PDF ingestion directly
  through the browser dashboard with step-by-step progress feedback (`Reading file…` ->
  `Extracting text and passages…` -> `Complete`), button locking during ingestion, and
  CLI progress reporting on stderr via `progress_callback`.
- **Recent projects management**: Quick-access recent projects list in the Open Project modal
  with path chips and single-click removal, persisting in local browser storage.
- **Graceful stale path recovery**: Project folder chooser warns on deleted or inaccessible paths
  and automatically falls back to the user's home folder without breaking the modal UI.

### Fixed

- **Empty manuscript metrics and KPI display**: Text with zero tokens or words now correctly
  evaluates readability (Flesch, LIX) to `0.0` rather than the formula intercept (206.835 / 180.0).
  KPI tiles, Table 1, and Markdown reports display a clean empty indicator `"–"` for ASL, ASW,
  Flesch, LIX, Staccato, Dialogue, and lexical diversity when no tokens are present.
- **Stale manuscript file references**: The server dashboard now detects when an active manuscript
  path no longer exists on disk, displaying a prominent error badge (`"file missing (stale reference)"`)
  and preventing unhandled file errors during analysis.

## [1.17.0] – 2026-09-26

### Added

- Native revision and history workflows for research dossiers, claims, evidence
  links and author decisions, using the existing CLI, API and dashboard.
  Explicit corrections and supersessions preserve logical IDs and accepted
  revisions. Snapshot and revision checks prevent stale drafts from overwriting
  newer work; failed saves retain browser drafts.
- Notices when explicitly cited source passages have a newer capture. Existing
  quotations and authored text remain pinned; evidence links show when they
  refer to an earlier claim revision.
- Offline SVG diagram rendering for dossier bodies: client-side vector diagram
  generator rendering Mermaid flowcharts (`graph TD/LR`) and sequence diagrams
  (`sequenceDiagram`) into responsive SVGs without network requests, CDNs, or
  external runtime libraries. Includes inspectable source toggles and localized
  labels across all seven supported languages.
- Self-hosted Baidu Unlimited-OCR extraction boundary: support for PDF document
  ingestion (`lixity research ingest --file document.pdf`) with dual-blob
  content-addressed storage (original PDF bytes + extracted plain text). Pinned
  to official model snapshot `07dea832e22aefee32ad281d4b80551282e1c168` and
  integration recipe revision `d49ff64afffc1f47ab563dc1c589bc2f78808fa4`.
  Includes 1:1 physical page rastering via `pdftoppm` with SHA-256 digests,
  configurable `LIXITY_OCR_WORKER` sub-process execution, and local `pdftotext`
  extraction fallback.
- Export and restoration for the research archive: `lixity research export`
  packages HEAD, manifests, revision records, blobs and project.json into a
  verified tar.gz with a per-file checksum manifest. `lixity research restore`
  validates the archive and extracts it to a new directory, refusing to
  overwrite an existing project. Disposable search indexes are rebuilt
  separately. The acceptance criterion is a full round trip: export, restore,
  audit, rebuild search, and resolve citations with the same identities and
  verbatim text. Does not introduce a separate archive format; reuses the
  existing storage layout.
- Safe Markdown rendering in dossier detail and history views: headings,
  paragraphs, bold, italic, code blocks, lists, blockquotes, tables and safe
  links rendered client-side from a minimal self-contained renderer with no
  new runtime dependencies. HTML passthrough is disabled. `javascript:` and
  `data:` URIs are suppressed. `lixity:` internal links render as inert code
  spans. A 'Show source' toggle exposes the raw text.
- Property-based tests (Hypothesis `RuleBasedStateMachine`) for
  content-addressable storage invariants: encode determinism, round-trip
  fidelity, snapshot immutability, and contiguous revision history under
  arbitrary commit sequences.
- Mutmut configuration targeting the repository and revision modules for
  mutation testing of data-integrity paths.

### Fixed

- **Purge atomicity**: orphaned record files and blobs are now deleted only
  *after* HEAD has been atomically rotated to the new snapshot. Previously,
  a crash or signal between the unlink calls and `replace_head` could leave
  the archive in a permanently unreadable state. After this fix, an interrupted
  deletion leaves unreferenced-but-harmless files (recovery: re-run purge);
  an interrupted HEAD rotation leaves the old snapshot fully intact.
- **Evidence-ID deduplication**: `create_dossier` now deduplicates passage
  IDs using `dict.fromkeys`, matching the existing `revise_record` behaviour.
  Duplicate evidence references in a single dossier creation call no longer
  produce multiple identical `evidence_refs` entries.

### Compatibility

- The first authored edit writes `research-local/2` revision records and a
  `research-manifest-local/2` snapshot. Existing revision-1 files are retained
  unchanged; reading an archive does not upgrade it. Lixity 1.16.0 cannot read
  a revised archive. Back up the complete archive before upgrading and keep
  all writers on a version supporting native revisions.

## [1.16.0] – 2026-09-26

### Added

- Standalone local `lixity serve` with project creation, explicit manuscript import,
  existing-project opening, live settings and marker controls. Host/Origin checks,
  loopback binding and request limits protect the local HTTP boundary.
- A file and folder browser in Open Project selects existing server-local paths
  without changing the workspace until Open is confirmed. The persistent
  workspace bar keeps New Project, Open Project and Show guidance available in
  loaded projects; guidance can be reopened after dismissal.
- Localized explanations for project and research controls. Shared tooltips work
  by keyboard and touch, stay visible inside dialogs, and preserve related help.
- Experimental explicit-project research workspace: retained UTF-8 sources,
  versioned source context, SQLite/FTS5 search, exact passage citations, dossiers,
  claims, evidence links and author decisions through CLI, Python and HTTP APIs.
  Retention requires permission; source text is evidence, not an accepted claim.
- Integrated research tabs with full source/context and dossier views, passage
  selection for claims/dossiers, claim-to-dossier association, author decisions,
  visible archive root and counts, and distinct empty/uninitialized/unavailable states.
- Research withdrawal, purge preview and integrity audit. Purged passages leave
  content-free reference tombstones so historical evidence chains remain readable
  without retaining their deleted quotes.
- Cross-corpus lexical and stylistic comparison using the shared analysis pipeline.
  Vocabulary overlap is a navigation aid, not proof of factual support.
- All seven language profiles cover project workflows, research controls, templates
  and status labels. English and German remain the most developed linguistic cores.
- Additive `median_sl_exact` JSON metric; text reports display the conventional
  midpoint median for an even number of sentences. The legacy integer `median_sl`
  remains available with its original upper-middle semantics.
- Real-server browser regression for file/folder opening, import/error recovery,
  research creation and source lifecycle, with desktop and seven-locale mobile checks.

### Fixed

- Correct HD-D to hypergeometric expected TTR for a 42-token draw instead of
  the mislabeled windowed Simpson calculation. The minimum is now 100 tokens;
  legacy sampling arguments have no effect, and no population SE is reported.
  Recompute older analyses and dependent style baselines before comparison.
- “Open project” no longer routes file selection or drops silently into new-project
  import. Existing file/folder paths preserve their original research archive,
  including empty manuscripts and initialized research folders without manuscripts.
- Project opening reloads target settings; unsuccessful opening preserves the
  current workspace. Dialog errors remain visible beside editable inputs.
- Imported content preserves submitted whitespace and line endings and cannot
  overwrite an existing manuscript. Generated project settings use valid TOML
  and preserve quoted titles and the selected language.
- Standalone controls show only implemented actions; Run analyses/Rebuild refresh,
  while unsupported export/sync/audit/prune/Drive requests return HTTP 501
  without pretending to produce artifacts. Legacy `/api/load` returns HTTP 409
  rather than replacing a saved copy with the same filename.
- Source, claim and dossier selections survive background list refreshes. A decision
  with no recorded deviation is shown neutrally, without implying factual validation.
- Correct chapter-to-rest JSD probability mass; unequal chapter lengths no longer
  produce negative divergence for identical lexical distributions.
- Use all four cells of the term/non-term contingency table for Dunning G².
  Research comparison uses analyzed prose consistently and reports cross-language
  comparability limits; shared vocabulary does not establish factual support.
- Verify retained source bytes before exposing source-detail quotes, matching the
  integrity checks already used for citations.
- Align token/syllable/readability/dialogue counts with sentence metrics by excluding
  Markdown headings consistently from prose measurements.
- Project TOML works on Python 3.10 through a conditional `tomli` dependency;
  Python 3.11+ continues to use the standard library.
- Rebuilding the research catalogue flushes a writable file descriptor on
  Windows before atomic publication. Browser checks honor an external Python
  environment in CI as well as the local development environment.
- Correct the documented Benjamini–Yekutieli harmonic factor and Maas logarithm
  base to match the existing implementations; no numerical change for these fixes.

### Changed

- English is the default across CLI, API and local server; automatic language
  detection requires an explicit choice and import preserves that choice.
- English onboarding, installation, architecture and methods documentation now
  separates implemented research workflows from planned provider integrations.
- Analysis/style JSON schema versions remain 2/4. Corrected numeric outputs require
  recomputing older analyses before longitudinal comparison. Research stays an
  experimental family of `*-local/1` contracts.
- Refreshed public/synthetic screenshots and project presentation; no private
  manuscripts or real research records are included.

## [1.15.0] – 2026-09-24

### Added

- Explanatory settings form with visible labels, expandable thresholds,
  restore-without-saving and client/server validation in the local adapter.
- FDR-specific matrix markers and chapter filtering, fixed-scale legend,
  Cliff's δ details, and visible reference medians/sample counts.
- Classic serif typography for the project title only; system UI sans elsewhere.
- Shared `lixity.pipeline` orchestration for CLI, API and project adapters,
  with one corpus analysis per complete result and explicit threshold mappings.
- Interactive 3D chapter trajectories with zoom, rotation, localized tooltips,
  per-axis threshold boxes, chapter navigation and responsive feature loadings.
- Browser regression checks and localization contracts for all seven profiles.
- Architecture and localization guides with explicit engine/adapter boundaries.
- Shared project header with engine version and localized non-commercial-use notice.
- Thirteen refreshed public-sample screenshots, including full dimension panels,
  real expanded paragraph context, mobile views and dark-mode diagnostics.

### Changed

- Installation guidance now has one canonical guide for CLI/API/development,
  Windows, updates and first-run verification. `make install` uses `.venv`
  rather than global Python; both installation targets check dependencies.

- Promoted the reviewed `1.15.0.dev0` work to release `1.15.0`.
- CLI/API/core analysis defaults to English. Use `--language de` for German
  or `--language auto` for detection; CLI project language settings are honored.
- Documentation and comments use English; localized resources remain multilingual.
- Canvas animation runs only when rotation is enabled and the page is visible.

### Fixed

- NDA records render through text-safe DOM APIs instead of HTML interpolation;
  artifact links reject executable URL schemes. Added synthetic regressions.

- Public API `min_chapters` now reaches the style core rather than being
  silently ignored; the CLI exposes `--min-chapters`. API threshold mappings
  can explicitly disable current-directory configuration discovery.
- Repository guidance distinguishes analysis from authorized mutations;
  ignore rules cover local agent/browser state and the default HTML export.

- Shared panel and page spacing replaces overlapping margins; mobile charts use
  stacked labels and wide tables scroll instead of crushing their columns.
- Chapter matrix headers explain every column in all seven UI languages;
  shared tooltips now support keyboard focus, Escape and ARIA descriptions.

- Control groups share one spacing and separator rule; the duplicate legacy NDA
  entry form is removed in favor of the encrypted NDA manager.
- Settings display the analysis language unless the host explicitly selects auto.
- CLI configuration follows an explicitly selected manuscript's directory;
  dashboard and workspace builds honor the configured project title.

- Localized settings no longer write decimal commas into HTML number values.
- Matrix color legends reflect the actual color scale rather than the configured
  detection cutoff; reference rows respect the configured minimum sample size.
- Dimension scores are flagged only after all feature contributions are summed.
- Point hit testing matches the rendered projection after zoom/rotation.
- Chapter titles in canvas tooltips are text rather than executable HTML.
- English percentages retain their percent sign; tooltip numbers use their locale.
- Mobile dimension cards retain space for feature labels and avoid overflow.
- Long chapter paragraph strips scroll within their component on mobile.
- Screenshot selection uses exact panel IDs instead of incidental label matches.

## [1.14.0] – 2026-09-24

### Added

- **Substantive Documentation & Presentation Elevation:**
  - `README.md` and GitHub Pages (`docs/index.html`) thoroughly expanded, tightened, and refined in English, emphasizing self-calibrating macro-editing versus external normative style checkers.
  - Added an executive Mathematical Core summary table in `README.md` with clean, platform-independent Unicode notations (`x̃`, `Â₁₂`, `ρ₁`, `τ, S, p`, `G²`).
  - Added in-depth descriptions of the 5 core metric groups and their diagnostic value for macro-editing and developmental line editing.
  - Expanded FAQs in `README.md` and `docs/index.html` covering noise-aware significance shrinkage ($z^*$), non-destructive Markdown editor work markers (Pandoc / Typst / LaTeX pass-through), and pipeline integration.
  - Enhanced persona-workflow cards and comparison matrix on GitHub Pages.
- **English Schema & Model Descriptions:**
  - Translated all Pydantic model field descriptions in `src/lixity/models.py` (`CorpusConfig`, `SentenceDistribution`, `ChapterMetrics`, `CorpusMetrics`, `DossierStatus`, `CorpusAuditReport`) and internal error messages into English for clean API introspection.
- **UI Performance & Accessibility Enhancements:**
  - Throttled tooltip repositioning on scroll and resize via `requestAnimationFrame` tick scheduling to avoid layout thrashing and maintain 60/120 fps fluid scrolling.
  - Added Escape key dismissals to close open paragraph detail panels (`.ptext.open`) and active inline marker note input fields (`.marker-note`).
  - Extended CSS `scroll-margin-top: 4.5rem` to all panels and anchored sections (`.panel`, `section[id]`), preventing sticky toolbars from obscuring content headers upon link activation.
  - Added `user-select: none` to `.kpi-link` tiles to prevent accidental text selection during navigation clicks.
  - Standardized NDA table headers and fallback file upload status text to English in `dashboard.js`.

### Fixed

- **GitHub Markdown & KaTeX Math Rendering:**
  - Removed KaTeX delimiter-backtick collisions in `docs/METHODS.md` that previously caused red parse error boxes on GitHub.
  - Escaped mathematical asterisks (`z\*`) across documentation to eliminate accidental Markdown italics formatting.
  - Replaced unstable combining circumflex diacritics (`Hill &alpha;&#770;` / `Hill α̂`) that produced detached boxes across browser fonts with `Hill tail index`.
  - Normalized schema version indicators (`schema_version 4` for style references) across GitHub Pages and documentation.
- **Typographic, Editorial & Security Updates:**
  - Fixed duplicate word in `docs/USAGE.md` ("Structural structural diagnostics" → "Structural diagnostics").
  - Converted German decimal commas to standard English decimal points in the worked example in `docs/USAGE.md` (`15,57` → `15.57`, `+0,08 pp` → `+0.08 pp`, `−0,0002` → `−0.0002`).
  - Corrected English article and thousands formatting in `docs/STABILITY.md` ("a 8 000-word" → "an 8,000-word chapter", `chapter × feature`).
  - Added missing accent in `CITATION.cff` (`Goh-Barabási`).
  - Updated `SECURITY.md` supported release branch to `1.14.x`.
  - Completed all missing GitHub release comparison links at the bottom of `CHANGELOG.md` from v1.1.0 through v1.9.1.

## [1.13.0] – 2026-09-23

### Changed

- **Layout default leading ≈ 1.50×:** all three `BookLayoutConfig.from_preset`
  presets (`a4`, `taschenbuch`, `mobile`) now set `line_spacing=0.94`
  (Pango factor ≈ 18.0 / 13.2 / 12.8 pt baseline distance at 12 / 8.8 / 8.5 pt).
  Previously mobile and paperback used `0.88` (≈ 1.41×) and A4 used natural
  Pango metrics (≈ 1.33×); the tighter leading was reported as too cramped
  for continuous reading. Typographic defaults for reproducible exports —
  override per call via CLI `--line-spacing` or a custom config.

### Tests

- **`tests/test_layout.py`:** renderer-free assertions on preset
  `line_spacing`, body sizes, and the ≈ 1.50× target (no Cairo/Pango in pytest).

## [1.12.0] – 2026-09-23

### Added

- **Pacing degeneracy flag:** `PacingReport` / JSON gain
  `explicit_scene_breaks` and `scenes_are_chapters` (true when the text has
  no explicit `---`/`* * *` dividers, so scenes ≡ chapters). The CLI prints
  a warning in that case; scene counts are then structure placeholders, not
  pacing evidence.

### Changed

- **`characters` requires names:** empty `--names` / empty API name list
  now fail fast (CLI exit 1 `err_no_names`; `ValueError` via the API)
  instead of returning a silent `figures: []`. No NER — the caller
  supplies the names.

### Documentation

- **Boundary caveats** (USAGE §Known limitations, STABILITY register rows
  45–50, AGENTS §3.5 boundary note, METHODS Track B):
  heuristics measure the text, not ground truth; `signal_counts` is empty
  unless `CorpusConfig.signal_keywords` is set; German filter-verb counts
  (engine ≈ 94) intentionally differ from broader editorial lists (120);
  pacing without explicit dividers is flagged; no external Delta
  stylometry and no dialogue speaker attribution.

## [1.11.0] – 2026-09-23

### Added

- **Packaging & installability:** dynamic version from
  `lixity._version.__version__` (single source for setuptools / `__version__` /
  `--version`), optional-dependencies `dev` extra (`pytest`, `mypy`, `ruff`,
  `build`), richer classifiers (`Environment :: Console`, Python 3.13,
  `Typing :: Typed`, OS Independent), project URLs for the GitHub Pages site
  and security policy.
- **`Makefile`** (`make help|install-dev|test|lint|typecheck|check|build|screenshots|clean`)
  and **`CONTRIBUTING.md`** (dev setup, PR checklist, bug reports).
- **`.github/dependabot.yml`** weekly updates for GitHub Actions.
- **Shell completion parity:** zsh script now covers all commands and the
  style-threshold flags (`--z-mild`…`--flag-min-severity`); bash completion
  gained `--fdr-method`, `--flag-min-severity`, `--dry-run`, `--names`,
  `--motif` and install-path hints; `lixity completion` accepts
  `bash|zsh|sh` as choices.
- **Top-level `--help` epilog** with examples, docs URL and `LIXITY_LANG`.
- **Structural diagnostics** on the style passport (`structural_diagnostics`,
  `schema_version: 4`): PELT changepoints, Mann–Kendall trends, Sn/Qn
  robust scales (alongside MAD), Hill tail index, and summary lists
  (`trending_features`, `segmented_features`); `passport_text` gains a
  “Structural diagnostics” line (en/de). Pure stdlib — no numpy/scipy.
- **Wired structural estimators** (previously standalone-only):
  - `distribution_shift` + `shifted_features`: Wasserstein-1D and
    two-sample KS comparing the first half of chapters against the second
    (both halves ≥ 2);
  - `lexical_structural_diagnostics(text, config)` merges token-level blocks
    into the passport on text-bearing surfaces (`api.fingerprint`,
    CLI `style` / `build` / `dashboard`): `cooccurrence` (content-word
    graph mean degree + Goh–Barabási fitness) and `keyness` (Dunning $G^2$
    early vs late halves). Guards: ≥ 50 content tokens for the graph,
    ≥ 20 per keyness half; single-chapter texts omit `keyness`.
- **`CITATION.cff`**, **`.pre-commit-config.yaml`** (ruff + trailing
  whitespace), **release workflow** (tag → wheel + GitHub Release), and
  **GitHub Pages deploy** (`docs/` on `main`).
- **Injectable statistical thresholds** (`z_mild`, `z_strong`, `fdr_q`,
  `fdr_method`, `dim_score_threshold`, `flag_min_severity`):
  stored on `StyleFingerprint.thresholds`, reported in every passport `meta`,
  and controllable from
  - CLI: `--z-mild`, `--z-strong`, `--fdr-q`, `--fdr-method {bh,by}`,
    `--dim-threshold`, `--flag-min-severity {1,2,3}` on `style`,
    `dashboard`, `build`;
  - API: `api.fingerprint(..., z_mild=…, fdr_q=…, fdr_method=…, …)`
    (same kwargs on `api.passport` / `api.dashboard`);
  - control UI: Settings fields for z\* mild/strong, FDR q, flags severity
    floor and dimension-score threshold, persisted on the embedded server;
  - config file: `[tool.lixity]` in `pyproject.toml`, or `lixity.toml` /
    `~/.config/lixity.toml` via `src/lixity/config.py`
    (CLI > UI session > project > user > code default).
- **Benjamini–Yekutieli FDR** (`fdr_method="by"`, harmonic factor \(c(m)\))
  alongside the default BH path (`fdr_rejects`).
- **Effect sizes on confirmed cells**: Cliff’s δ and Vargha–Delaney
  \(\hat{A}_{12}\) with Romano bands (`effect_label`), exposed as
  passport `effect_magnitudes`.
- **Baseline exchangeability diagnostics**: runs test about the series
  median, lag-1 autocorrelation vs \(1/\sqrt{n}\), `low_power` for
  \(n < 8\) — passport `baseline_diagnostics` + `passport_text` line.
- **`docs/METHODS.md`**: formal catalogue of every estimator (MAD/σ scaling,
  z\*, BH/BY-FDR, Cliff’s δ, runs/ACF, Jacobi dimensions, LD indices,
  readability constants, JSD, layer z, Structural PELT/MK/Sn/Qn/Hill and
  Wasserstein/KS/Dunning/Goh–Barabási — including their passport wiring —)
  with injectability table including the config file; Track B/C research
  and pedagogy backlog (Burrows’ Delta / OHCO-TEI / hermeneutics, tutorials).
- Contract tests for threshold round-trip and sensitivity settings markup
  (z mild/strong, FDR q, flags cut, dimension threshold).

### Changed

- **BREAKING (schema v3 → v4):** style-passport JSON container key renamed
  `wave2_diagnostics` → `structural_diagnostics`; passport text label
  `wave2` → `structural` (en: “Structural diagnostics”, de: “Strukturelle
  Diagnostik”); function `lexical_wave2_diagnostics` →
  `lexical_structural_diagnostics`. Sub-keys (`changepoints`, `trends`,
  `distribution_shift`, `cooccurrence`, `keyness`, …) are unchanged.
  Project-management codenames no longer appear in public contracts.
- **Centralised status codes** in new module `lixity.status`: `Status`
  (UI ok/warn/error/unknown), `Tense` (present/past/mixed/neutral),
  `Severity` (0–3 + `FLAG_MIN_SEVERITY`), `NdaStatus`, and
  `ContractKeys` / `STRUCTURAL_DIAGNOSTICS_KEY` / `SCHEMA_VERSION_*`.
  `style_profile.TENSE_*` / `FLAG_MIN_SEVERITY` now re-export from
  `status`; NDA status list is server-injected (`data-nda-statuses`)
  instead of hard-coded in `dashboard.js`.
- **Feature units localised for all seven UI languages** (en/de/fr/es/it/pt/nl)
  via `FEATURE_UNITS` (was: German override + English fallback only).
- **Install docs** (README, `docs/USAGE.md`, project page, `docs/llms.txt`):
  pipx / uv / pip / pinned-tag options; development via `make install-dev`.
- **`docs/USAGE.md` Development** section now documents `make check`
  (ruff + mypy --strict + pytest -W error) instead of the stale unittest count.
- **GH Pages** (`docs/index.html`): Structural FAQ and feature pills, style
  schema v4, BH/BY, injectable thresholds, structure-module cards, Methods /
  Contributing / Security footer links, installation matrix.
- **`.gitignore`** hardened: agent/tool workspaces (`.remember/`, `.claude/`,
  …), coverage formats, keystores / `.netrc` / swap files, stray
  `*_dashboard.html` / `*_metrics.json` style build artifacts outside
  `exports/`.
- **`SECURITY.md`**: supported-versions table, expanded threat model,
  consumer hardening checklist (pipx/uv, pinned tags, local-only dashboards).
- **Single chapter segmentation**: `split_chapters` moved from `dialogue`
  to `markdown_parser` (re-export kept); `analyzer` and all structure
  modules share one implementation, so chapter titles/numbers can no longer
  drift between reports.
- **Single threshold builder**: `config.resolve_thresholds` is the only
  place that builds `FingerprintThresholds` (kwargs > project config >
  code default); CLI `_thresholds_from_args` and API `_thresholds` both
  call it.
- **`flag_min_severity` end-to-end**: CLI `_thresholds_and_profile` feeds
  `ProfileThresholds` into `ParagraphProfiler` and passes the resolved cut
  to `render_dashboard`; `api.profile` / `api.dashboard` accept
  `flag_min_severity` explicitly.
- Passport `meta` now reports `min_chapters` and `flag_min_severity`
  alongside the z\*/FDR thresholds.
- **Style reference rows are fully clickable**: every `.band-row` jumps to
  that feature's heatmap column (`#feat-<field>`), activates the matching
  style layer when one exists, and preselects “deviations only” when the
  feature has outliers. The red **outlier count** is a nested control that
  opens the strongest outlier chapter (with layer + only-deviations).
- Heatmap column headers expose stable anchors (`id="feat-<field>"`).
- Heatmap legend and “deviations only” cut use `fingerprint.thresholds.z_mild`
  instead of a hardcoded 2.5.
- Research basis (STABILITY §1) extended: robust statistics / multiplicity
  control, readability literature (Amstad…Douma, Weiss & Meurers 2022),
  foregrounding/stylistics angle.
- README condensed with an explicit mathematical-core focus; links to
  METHODS.md.

### Fixed

- Dialogue and nominal style layers now bind correctly:
  `LAYER_FEATURES` uses fingerprint field names (`dialog_pct`,
  `nominalization_density`); `LAYER_PARAGRAPH_ATTR` maps them to the
  `ParagraphProfile` attributes (`dialogue_pct`, `nominal_density`) used by
  `layer_stats`. Previously the dialogue band had no layer and the nominal
  layer produced empty stats.
- Export-format `<select id="fmt">` exposes a short `aria-label` (export)
  instead of the full help sentence; the tooltip moved to `title`.
- USAGE metric table: LIX long-word threshold is **>6 characters in every
  language** (Björnsson), not per-language 6/7/8 (docs inconsistency with
  STABILITY #24 / METHODS §7).
- Book scripts `export_pdf.py` / `export_nda.py`: suppress third-party
  `PyGIDeprecationWarning` for `GLib.unix_signal_add_full` during Pango
  import (system PyGObject, not Lixity code).

## [1.10.0] – 2026-09-22

### Added

- **Flagged passages panel** (`#flags`) directly under the KPIs: every
  paragraph with severity ≥ 2 as a row (severity badge, chapter, line anchor,
  excerpt), sorted by severity then line. Clicking a row jumps straight to
  that paragraph — opens it, scrolls, flashes — with the “flagged only”
  filter preselected; a quick **+ To-do** button writes the work marker
  inline without leaving the list. The “flagged” KPI now targets this panel.
- `ParagraphProfile.is_flagged`, the `FLAG_MIN_SEVERITY` constant and
  `flagged_paragraphs()` (severity desc, line asc) replace the repeated
  `severity >= 2` checks; `classify_severity()` is a documented, tested
  pure function (0–3 truth table).

### Fixed

- **Marker clicks no longer scroll the page**: buttons inside jumpable rows
  (`data-marker-kind`, `data-marker-resolve`, note field) are excluded from
  jump activation in both the click and the keyboard handler.
- **Line jumps land on the paragraph, not just the chapter**: `jumpToLine`
  opens the target `.ptext` panel (via `data-target` or its
  `data-start`/`data-end` span) and activates its chip; chapter scroll remains
  the fallback (e.g. marker lines outside any paragraph span).

### Removed

- Dead aliases: `render_style_report`, `DEFAULT_TEXTE`, and the unused
  `ParagraphProfile.line_label` property (the localised `line_label()` in
  `ui.components` remains the single implementation).

## [1.9.1] – 2026-09-22

### Changed

- **Chapter names wherever they are available**: dialogue, pacing and
  showing rows show `Kap. N · Titel`, the deviation KPI names its chapter,
  the marker table gained a chapter column, and the character span shows the
  first chapter's title on hover.

### Fixed

- **Layout overflow hardened**: the chapter matrix and marker table scroll
  horizontally inside their panels (like the heatmap); long texts wrap or
  ellipsize (KPI labels, dimension loading chips, status details, chapter
  titles, repeated phrases, paragraph text); the pacing and showing lists are
  height-capped with a fade hint; the toolbar select is width-capped.

## [1.9.0] – 2026-09-22

### Added

- **`lixity dialogue`** (and `api.dialogue`): dialogue turn structure — turns
  (quoted segments), mean/median/longest turn, turns per 1,000 words and the
  dialogue paragraph share, per chapter and corpus. Heuristic via the language
  profile's dialogue pattern; no speaker attribution.
- **`lixity characters`** (and `api.characters`): character presence across
  chapters for curated names or alias patterns — mentions, chapters present,
  first/last chapter, longest gap, presence ratio. Appendix and front matter
  are excluded so chapter numbers match the metrics.
- **`lixity pacing`** (and `api.pacing`): scene structure via explicit
  dividers, tempo signals per scene/chapter (ASL, staccato, dialogue) and a
  documented 0–3 chapter hook score.
- **`lixity motifs`** (and `api.motifs`): motif presence (mentions, density,
  chapter span, longest gap) and generic repetition signals — most frequent
  content words and repeated n-grams with their chapter spread.
- Dashboard panels for dialogue structure, character presence, the pacing
  curve and motifs/repetition (clickable, keyboard reachable, seven
  languages).
- **`lixity showing`** (and `api.showing`): self-calibrating showing vs.
  telling balance per chapter (robust z of telling and showing signals
  against the book's own medians; documented MAD→SD fallback).
- **`lixity about --json`** now lists all commands with purpose, output type
  and schema version (agent discovery).
- Curated stop-word lists (de/en) extended with high-frequency adverbs,
  possessives and particles so repetition and driver-word analysis stays
  content-focused.
- **`mypy --strict` is enabled** (147 → 0 errors) and runs in CI; the code
  base is also free of runtime and syntax warnings (`python -W error`).

## [1.8.0] – 2026-09-22

### Changed (breaking, metric-affecting)

- **Sentence segmentation is abbreviation-aware** and shared by corpus and
  chapter metrics (`lixity.sentences`): abbreviations (`Mr.`, `z.B.`, `Dr.`),
  decimal numbers and initials no longer split sentences, closing quotation
  marks stay with the sentence they close. Sentence counts, ASL, CV, Flesch
  and LIX change accordingly (dialogue-heavy texts get more, shorter
  sentences; the chapter matrix was still on the naive regex before).
- **LIX uses the standard long-word threshold** (more than six characters)
  for every language; the previous per-language calibration (7/8 characters)
  deviated from Björnsson. LIX values rise accordingly.
- **Syllable heuristics improved:** German double vowels count as one nucleus
  (`Kaffee`, `Idee`), the English silent-e/-le rule no longer double-counts
  (`table`, `people`).
- **Spanish readability** uses the INFLESZ coefficient 62.35 (matches the
  named scale).

### Changed (structure)

- New core modules: `lixity/sentences.py` (segmentation), `lixity/syllables.py`
  (per-language rule tables as data), `lixity/diversity.py` (HD-D, MTLD,
  MATTR, Maas a², Yule's K). `analyzer.py` is orchestration and metric
  assembly (857 → ~540 lines).
- `SentenceStats` is the one sentence-architecture data structure for corpus
  and chapters; `share_se`/`count_se` are module-level plug-in estimators.
- `language.py`: one profile dataclass, resolved via `dataclasses.replace`
  (was two identical dataclasses with three field lists).
- **Unified UI interaction contract**: every content drill-down is a
  keyboard-reachable `[role="button"]`, driven by one JS selector; focus
  styling covers all targets (documented in `docs/AGENTS.md` §3.4).

### Fixed

- Style-reference band rows are clickable again (the layer mapping was lost
  in a refactor) – as documented since v1.5.0.
- `jacobi_eigh` docstring corrected (one eigenvector per list entry).
- New `tests/test_math_core.py` pins the mathematical core (hand-computed
  readability formulas, published Benjamini-Hochberg example, Jacobi
  properties, Spearman, z*/MAD helpers, lexical-diversity properties).

## [1.7.0] – 2026-09-22

### Changed (breaking)

- **Language-neutral tense values:** `dominance` (chapter metrics) and
  `dominant` (paragraph profiles) are now `present` / `past` / `mixed` /
  `neutral`; display labels come from the language packs. The JSON contract
  version is now **schema_version 2** for `analyze` and `profile`.
- **English is the engine default** for reports and CLI messages; German is
  available via `LIXITY_LANG=de` (Rich report, Markdown report, style
  reference text, build/dashboard messages). Other report languages fall
  back to English.
- **Project corridors are opt-in:** reference corridors and literary
  assessments are no longer engine defaults – projects supply them as
  `texts` (the book project passes its own German corridors). Without them
  the Rich report stays factual (metric + value).
- Report row labels and feature units are localised (`de` / `en` packs).

### Fixed

- Chapter detection: front matter preceded by editorial HTML comments no
  longer becomes chapter 1 (chapter numbering stays correct).
- A chapter without tense markers is classified `neutral` instead of `past`
  (one shared `dominance_from_hits` helper for chapters and paragraphs).
- Style reference: correct singular/plural chapter count; localised units.

### Added

- `LIXITY_LANG` environment variable (`en` default, `de` supported) for
  user-facing CLI messages.

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

[Unreleased]: https://github.com/mfahsold/lixity/compare/v0.9.3...HEAD
[0.9.3]: https://github.com/mfahsold/lixity/compare/v0.9.2...v0.9.3
[0.9.2]: https://github.com/mfahsold/lixity/compare/v0.9.1...v0.9.2
[0.9.1]: https://github.com/mfahsold/lixity/compare/v0.8.2...v0.9.1
[0.9.0]: https://github.com/mfahsold/lixity/compare/v0.8.2...v0.9.0
[0.8.2]: https://github.com/mfahsold/lixity/compare/v0.8.1...v0.8.2
[0.8.1]: https://github.com/mfahsold/lixity/compare/v0.8.0...v0.8.1
[0.8.0]: https://github.com/mfahsold/lixity/compare/v0.7.9...v0.8.0
[0.7.9]: https://github.com/mfahsold/lixity/compare/v0.7.7...v0.7.9
[0.7.7]: https://github.com/mfahsold/lixity/compare/v0.7.6...v0.7.7
[0.7.6]: https://github.com/mfahsold/lixity/compare/v0.7.5...v0.7.6
[0.7.5]: https://github.com/mfahsold/lixity/compare/v0.7.4...v0.7.5
[0.7.4]: https://github.com/mfahsold/lixity/compare/v0.7.3...v0.7.4
[0.7.3]: https://github.com/mfahsold/lixity/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/mfahsold/lixity/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/mfahsold/lixity/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/mfahsold/lixity/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mfahsold/lixity/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/mfahsold/lixity/compare/v0.4.9...v0.5.0
[0.4.9]: https://github.com/mfahsold/lixity/compare/v0.4.8...v0.4.9
[0.4.8]: https://github.com/mfahsold/lixity/compare/v0.4.7...v0.4.8
[0.4.7]: https://github.com/mfahsold/lixity/compare/v0.4.6...v0.4.7
[0.4.6]: https://github.com/mfahsold/lixity/compare/v0.4.5...v0.4.6
[0.4.5]: https://github.com/mfahsold/lixity/compare/v0.4.4...v0.4.5
[0.4.4]: https://github.com/mfahsold/lixity/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/mfahsold/lixity/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/mfahsold/lixity/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/mfahsold/lixity/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/mfahsold/lixity/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mfahsold/lixity/compare/v3.0.1...v0.3.0
[3.0.1]: https://github.com/mfahsold/lixity/compare/v3.0.0...v3.0.1
[3.0.0]: https://github.com/mfahsold/lixity/compare/v2.4.0...v3.0.0
[2.4.0]: https://github.com/mfahsold/lixity/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/mfahsold/lixity/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/mfahsold/lixity/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/mfahsold/lixity/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/mfahsold/lixity/compare/v1.25.0...v2.0.0
[1.25.0]: https://github.com/mfahsold/lixity/compare/v1.24.1...v1.25.0
[1.24.1]: https://github.com/mfahsold/lixity/compare/v1.24.0...v1.24.1
[1.24.0]: https://github.com/mfahsold/lixity/compare/v1.23.0...v1.24.0
[1.23.0]: https://github.com/mfahsold/lixity/compare/v1.22.0...v1.23.0
[1.22.0]: https://github.com/mfahsold/lixity/compare/v1.21.0...v1.22.0
[1.21.0]: https://github.com/mfahsold/lixity/compare/v1.20.0...v1.21.0
[1.20.0]: https://github.com/mfahsold/lixity/compare/v1.19.0...v1.20.0
[1.19.0]: https://github.com/mfahsold/lixity/compare/v1.18.0...v1.19.0
[1.18.0]: https://github.com/mfahsold/lixity/compare/v1.17.0...v1.18.0
[1.17.0]: https://github.com/mfahsold/lixity/compare/v1.16.0...v1.17.0
[1.16.0]: https://github.com/mfahsold/lixity/compare/v1.15.0...v1.16.0
[1.15.0]: https://github.com/mfahsold/lixity/compare/v1.14.0...v1.15.0
[1.14.0]: https://github.com/mfahsold/lixity/compare/v1.13.0...v1.14.0
[1.13.0]: https://github.com/mfahsold/lixity/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/mfahsold/lixity/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/mfahsold/lixity/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/mfahsold/lixity/compare/v1.9.1...v1.10.0
[1.9.1]: https://github.com/mfahsold/lixity/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/mfahsold/lixity/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/mfahsold/lixity/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/mfahsold/lixity/compare/v1.6.1...v1.7.0
[1.6.1]: https://github.com/mfahsold/lixity/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/mfahsold/lixity/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/mfahsold/lixity/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/mfahsold/lixity/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/mfahsold/lixity/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/mfahsold/lixity/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/mfahsold/lixity/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/mfahsold/lixity/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/mfahsold/lixity/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/mfahsold/lixity/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/mfahsold/lixity/releases/tag/v1.0.0
