# Dashboard browser regression

Run after installing the Python development environment, FFmpeg and Playwright
with Chromium. FFmpeg creates synthetic media for the dossier-media suite;
install `axe-core` as well to run the audio direction accessibility audit.
Playwright and axe-core are optional tooling, not Lixity runtime dependencies.

```sh
make browser          # everyday core surfaces (fast group, 3 workers)
make browser-changed  # only the suites affected by modified git paths
make browser-full     # every suite, run before a release (3 workers)
# or: python3 scripts/run_browser_suites.py --area research --jobs 3
```

`--list` prints the suite names, `--group fast|full` selects the everyday core
surfaces or everything, `--area NAME` runs one surface (`docs`, `research`,
`analysis`, `project`, `sharing`, `tokens`), `--changed [BASE]` maps modified git paths
to the affected areas (falling back to the full set when a shared foundation
changed), `--jobs N` runs independent suites in parallel, `--only NAME`
selects suites and `--start NAME` resumes after a failure.
After a parallel run, the runner reports all failed suites with an `--only`
command; completion order does not define a safe `--start` position. Repeat
the full suite before a release after fixing a failure.

A failed Git comparison, including an invalid `BASE`, stops selection with an
error. Shared support files and runner changes select all suites, as do unknown
or deleted suite paths; they never silently select zero tests. Only an exact
registered root-level suite path selects that suite alone. Selection is an
iteration aid, not a substitute for the complete pre-release run.

Shared jump and tooltip changes select the full set: they affect research,
dialogs and the generated demo as well as the manuscript surface.
The `sharing` area covers the reading-website exporter, prepared transport,
reader/companion rendering, publication settings and public examples. Use
`--area sharing` for those boundaries; shared UI foundations still select the
full set.

Completed runs end with a summary of completed/selected suites, passed, failed,
not run and elapsed time. Failures include a sorted list of suite names and exit
codes. Sequential runs stop at the first failure; parallel runs finish all
selected suites before summarizing. A failed run retains a nonzero exit code.

Before starting suites, the runner executes the support directory's Node tests.
These check disposable-server startup, malformed readiness data, early exits,
timeouts and cleanup. Research-status support tests cover pending-only sharing,
exact-context isolation, explicit refresh, failed-read retry and mutation invalidation.
`--list` only lists suites. Native-server helpers keep
readiness and termination handling shared without replacing the real HTTP flows.
Large Python-generated JSON fixtures use a disposable file-backed transport.
Complete dashboard HTML and bundled assets are retained without a fixed stdout
pipe budget; success, generation failures and malformed JSON all clean up files.
After staging, public-docs and visual-consistency checks remove their site copies
even if browser launch or assertions fail; screenshots remain available in the
reported artifact directory.

Public-docs checks also bound product previews, preserve their complete aspect
ratios and native full-size links, and verify the desktop introduction layout.
Lazy images are inspected after scrolling to them and decoding their bytes.
A held image response checks reserved preview space and stable following content.

Localized suites retain all seven languages at desktop and mobile widths for
rendering, labels and submitted machine values. Language-independent interaction
and conflict scenarios run once per relevant viewport. Native server saves and
intercepted responses cover different boundaries and remain separate.

The project-structure suite checks the native read-only overview in seven locales,
desktop/mobile navigation, literal filenames, encoded output downloads, stale
project rejection and mismatched research contexts. Synthetic source, settings
and output bytes must remain unchanged after inspection.

The audio-pronunciations suite edits and filters synthetic pronunciation entries
at desktop and mobile widths, checks duplicate/draft guards and verifies saved
project settings retain unrelated replacements, including keys containing `=`.

The audio-profile-delete suite uses a synthetic native project at desktop and
mobile widths. It checks that referenced profiles remain selectable, removing an
unreferenced profile is a visible draft, and saving persists the removal.

The structural-coverage suite renders missing and partial chapter measurements
in all seven locales on desktop and mobile. It checks that unavailable results
are explained and not shown with success badges.

The anchor-navigation suite checks real nested scroll areas, short mobile
viewports, single arrival feedback, superseded jumps and live reduced motion.
Dossier-return uses a disposable native archive to check exact returns, saved
revisions, drafts, stale contexts and the same visible return control through
responsive changes. Contextual-help exercises localized hover/focus help, actual
keyboard bindings and the scrollable reading-settings reference, including its
first visible frame after resizing a closed menu to a short viewport. Typography-
localization checks complete prose heading roles, noncompounding code sizes,
intentional font roles and real source toolbars in all seven languages.

The scroll-regions suite checks six-row and long chapter charts in seven locales,
desktop/mobile and both themes. It samples the rendered final bar to detect faded
data, then verifies real keyboard, wheel and touch scrolling. Native `scrollend`
separates inputs so an unfinished keyboard animation cannot overwrite a wheel
result. Screenshots use only synthetic text.

The section-navigation suite checks shared analysis links and actual dossier
headings, compact current-section orientation, duplicate headings, nested scroll
areas and reduced motion in all seven locales. The analysis-scope suite combines
declared register/POV filters with FDR selection, reset and exact hidden-row jumps;
the whole-manuscript reference must remain unchanged.

The metric-overlays suite checks all seven paragraph metrics, raw-value/direction
markers with a clear prose background, independent counted-text/comparison
switches, Focus restoration, unavailable and valid zero results, Analysis Off,
and preserved native selection/source identities.
The analysis-evidence suite additionally checks exact verified text ranges,
hover, touch and keyboard inspection, Unicode offsets, asynchronous cancellation,
search/research mark coexistence and explicit unavailable mappings. Its geometry
check counts repeated rectangle reads rather than setting a wall-clock threshold.
The linguistic-reference suite uses manually annotated original-language literary
excerpts from `tests/fixtures/literary_reference.json`. It compares actual CLI,
backend and displayed counts, units and source ranges in all seven languages,
NFC/NFD forms and desktop/mobile viewports. It also checks distinct corpus/profile
scopes and keeps a new mobile explanation's count visible after navigation.
These are bounded counting and rendering regressions; scientific interpretation
and unresolved linguistic limits stay centralized in
[`docs/STABILITY.md`](../../docs/STABILITY.md#core-validation-status).
The analysis-triage-layout suite checks the native decision list at 1440, 1280,
1024, 768 and 320 px: readable action dimensions, columns/cards fitting the
available pane and keyboard navigation without manuscript writes.
The shared **Explore passage** entry opens the existing context inspector, with
separate **Explain measurement** and **Research for this passage** actions. Native desktop
and mobile checks cover localized sentence word counts, paragraph comparison
scope and explanation opening when the mobile inspector moves prose offscreen.
Its disposable native first-entry flow enables Analysis through the visible control
without preselecting a metric, then checks the directly visible selector and
independent switches, compact quote/count cards, separate paragraph comparisons,
collapsed method guidance, direct inspection from Off or Focus reading, deliberate
None/disabled displays, keyboard operation and restored preferences across reloads
at 1440 and 320×480 pixels.
Analysis-navigation also checks the shared chapter measurement dialog from
heatmap cells and style-space loadings: all 16 metrics, chapter retention,
chapter-only layer limits, explicit manuscript navigation, metric switching and
Escape/focus restoration without writes.
Missing browser identity-verification support remains distinct from a hash mismatch.
The decision-review suite reads exact decision/dossier versions side by side,
stacks them on mobile, and checks read failures, late root-bound responses and
the existing guarded acknowledgement/reopen writes.

The claim-evidence-actions suite exercises empty evidence, the existing claim-bound
composer and source-search handoff without saving. It checks preserved drafts,
read failures/retry, stale responses and read-only capability boundaries at desktop
and mobile widths. Research-presentation checks all five authored record types
in seven locales: current entries by default, explicit earlier pins, a collapsed
lazy version list that never selects a record implicitly, one change reason,
localized fields, optional values and keyboard tab changes with retained drafts.
The list-filters suite also covers genuinely empty collections,
arrival of the first records and filters with no matches; failed reads remain
distinct from accepted empty results.

The pages-analytics suite intercepts the public origin and GoatCounter pixel
endpoint; no real counts are sent. It checks page paths and fixed link events,
privacy preferences, disabled configuration, failures and untrusted query data.
The actual generated demo runs with its unchanged CSP at desktop and mobile
widths, including prepared PDF download, installation navigation and read-only
controls. A download event records a successful prepared-file request, not proof
that the user saved the file. Local reports and other hosts remain unmeasured.

`scripts/browser_tools.cjs` probes common local Playwright and Chromium
locations automatically; `PLAYWRIGHT_MODULE` and
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` remain optional overrides.
`PYTHON_BIN` optionally overrides `.venv/bin/python`.
The style-space test generates a synthetic manuscript, checks canvas interaction,
keyboard/touch rotation and zoom, semantic chapter-score links with JavaScript
enabled and disabled, tooltip escaping, idle rendering, touch targets and mobile
layout, and prints its temporary screenshot
directory. It does not read any private manuscript or contact a server.

The debug test uses an intercepted synthetic host. It checks explicit enabled
and disabled preferences across reloads, window/server defaults, unavailable
local storage, API diagnostic gating and desktop/mobile rendering. Browser
API logs retain request metadata without response contents. Preferences do not
change server logging. Backend request/error UTC timestamps
are checked separately in `tests/test_server_debug.py`.

Browser suites are local-first: run `make browser` after UI changes and before
preparing a release. The manual `browser` workflow (Actions → browser → Run
workflow) runs the same script in one Chromium job on demand; screenshots stay
temporary and are not uploaded as persistent CI artifacts. The manual
`research-platforms` workflow covers macOS and Windows.

The research test starts its own disposable loopback server and archive. It checks
persistent New/Open/Show guidance actions after dismissal and in a loaded project,
server-local file/folder opening with an empty manuscript, file-picker and drag/drop
import (including preserved submitted bytes), cancellation, failed submit recovery,
and standalone capability gating. It also covers source/dossier detail views,
claim/evidence/decision creation, unavailable archive state, withdrawal and purge.
It renders all seven workspace languages at 320 pixels and also checks desktop
and 390-pixel layouts. It leaves screenshots under `/tmp/lixity-research-ui-*` and
stops its server on completion. It does not select or alter a running user project.
Set `PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` to use an existing Chromium installation.

The list-filters suite uses a disposable synthetic archive. It checks source and
dossier metadata matching, inert titles, preserved detail DOM, no API requests
while typing, delayed list refresh, complete association options and their
selected values. It inspects all seven languages at 1440 and 320 pixels and saves
screenshots under `/tmp/lixity-list-filters-*`.

The research-chronology suite checks the read-only claim timeline, explicit
cause/effect saves and revisions, keyword evidence selection, stale project and
draft responses, and inert data in all seven languages at 1440 and 320 pixels.
It uses a disposable archive and retains only temporary synthetic screenshots.

The ui-usability suite holds real synthetic HTTP create responses to check
single pending saves, preservation of newer drafts, nearby feedback, guarded
matrix downloads and shared keyboard tabs. It also checks reversible creation
disclosures, retained drafts, innermost Escape/focus, reduced-motion arrows and
plain dossier excerpts with line/table boundaries. The publication-settings suite uses
the existing Settings endpoint to check explicit metadata, fresh save tokens,
stale-token refusal, pending drafts and seven localized desktop/mobile forms.

The project-controls suite checks manuscript file/drop selection and inert
filenames, explicit native import confirmation, the existing embedding load
payload, persistent New/Open/guidance across the three views, and the initially
explicit NDA capability gating. Its synthetic examples and intercepted
requests exercise desktop/mobile layouts and seven languages. A native synthetic
workspace also checks actual worker model identity, an unknown model, refresh,
and preserved project navigation at desktop and mobile widths. Screenshots stay
under `/tmp/lixity-project-controls-*`.

The manuscript-pdf suite checks the native manuscript download controls in all
seven locales at 1440 and 320 pixels. It verifies explicit project-bound requests,
exact downloaded bytes for editorial, book, sheet and report layouts, pending controls,
inert error messages, refused non-PDF responses and retry without losing the
chosen layout. Empty projects keep a disabled action; standalone and embedding
reports without the capability expose none, and disabled JavaScript prevents
incomplete form submission. Intercepted cases use synthetic responses; an additional
disposable native server verifies real PDF composition, extracted text and
unsupported-math rejection without changing the manuscript. Screenshots
and downloaded fixtures stay under `/tmp/lixity-manuscript-pdf-*`.

Run `node tests/browser/manuscript-links-native.cjs` for the real native quote–claim
save flow. It starts a disposable loopback server and synthetic archive, renders
the actual dashboard, and saves distinct quotes at 1440 and 320 pixels with
explicit retention. It checks exact codepoint offsets around an astral character,
current claim-version pins, archive format 7, real review reads, inert HTML-like
text, search-highlight overlap and lazy paragraph reopening, then validates the
saved records through a fresh repository read. Manuscript bytes remain unchanged;
no HTTP responses are mocked and screenshots stay under
`/tmp/lixity-manuscript-links-native-*`.

Run `node tests/browser/project-switch-native.cjs` for the real native project
switch regression. Two synthetic projects have distinct configured titles and
manuscripts; Alpha starts with an explicit startup title override. Actual Open
Project submission and reload at 1440 and 320 pixels must select Beta's source,
research root, heading and NDA project-name field, while reopening the same
project retains its explicit override. The test checks manuscript/config bytes
stay unchanged and no NDA is generated or downloaded. It mocks no responses and
keeps screenshots under `/tmp/lixity-project-switch-native-*`.

The workspace-reader suite checks the optional manuscript/dossier companion
view in seven locales at desktop and mobile widths. It verifies context-bound
reads, a read-only dossier, safe rendering, retry, restored analysis panels and
retained manuscript state. Screenshots stay under `/tmp/lixity-workspace-reader-*`.

The workbench-transitions suite checks explicit passage requests for Values and
Dossier at 1440, 390 and 320 pixels: the requested context is visible, closing
returns to the requesting paragraph with its keyboard focus, and desktop view
navigation retains the passage. Normal-motion cases deterministically hold the
opening layout frame while reversing or changing Analysis, and check deliberate
scrolling after a tool settles. Other cases cover tool switching and a live reduced-motion preference change. Source identity,
overflow, runtime errors and unintended writes remain checked throughout.
Screenshots stay under `/tmp/lixity-workbench-transitions-*`.

The manuscript-reader suite checks the continuous manuscript, explicit **Analysis**
On/Off layer and comparison overview in seven languages at 1440 and 320 pixels. Synthetic
paragraph text and source anchors must remain identical across modes, contextual
tools and companion changes. It exercises ellipsis/right-click/keyboard menus,
focus restoration, paragraph Values, reversible marker drafts, exact selection
transfer into the existing claim dialog, text size, width/spacing preferences,
focus mode and desktop pointer/keyboard divider adjustment. The reader must not
introduce horizontal page overflow or implicit writes; text resembling HTML stays
inert. Screenshots remain under `/tmp/lixity-manuscript-reader-*`. These cases
verify the browser behavior they exercise, not prose-editing capability or full
accessibility conformance.

The passage inspector names the source lines and routes saved-association review
to that paragraph. Local **Passage values** remains independent of global
Analysis, including overview return; the English 390-pixel touch case also
returns from research with the local tool intact.

The manuscript-selection suite covers delayed first-review responses and
annotation changes while native text remains selected, including backward
selections, UTF-16 offsets around emoji, cross-paragraph ranges and transfer
into the existing claim dialog. Its disposable native projects verify that
continuous reading does not request manuscript review before research setup,
that same-page initialization enables review, and that switching projects does
not reuse the previous archive's initialization state.

The dossier-claims suite uses a disposable native research archive to read the
current claim associations from dossier detail and the companion reader. It
checks titled rows, author-assigned review states, saved versions, inert titles,
shared claim history, empty lists, retry and delayed/wrong-root responses in
seven locales at 1440 and 320 pixels. It makes no research writes through the UI;
synthetic screenshots stay under `/tmp/lixity-dossier-claims-*`.
It also checks dossier notes/citations sections and project-wide record routes;
opening the full Claims list preserves an unsubmitted claim draft.

The research-selection suite uses a disposable synthetic archive to select
source text and prepare an evidence draft. It checks selection boundaries,
Unicode offsets, unavailable sources, project changes, explicit save and the
full retained passage's immutable citation. Screenshots and fixtures stay in `/tmp`.

The research-status suite holds real native reads at 1440 and 390 pixels to
verify shared startup observations, fresh explicit refresh and safe settlement
order. Leaving and returning to a token context cannot reuse its departed pending
read. The journey performs no writes and preserves synthetic project bytes;
screenshots stay under `/tmp/lixity-research-status-*`.

The research suite also exercises native record revisions: edit and history for dossiers,
claims, evidence links and decisions; cancellation; concurrent and failed saves
that preserve drafts; newer-source notices with original quotations retained;
and history dialogs across all seven locales at 320 pixels.

Grouped revisions cover explicit draft selection, replacement and removal;
cancelled review; stale previews and guided conflict resolution; failed saves;
and one atomic save with preserved reference pins. Drafts remain local to the
browser tab until submitted.

It also checks localized OCR status/fallback labels and imports a source with an
origin URL.

The research suite also filters search to current dossiers, verifies typed
revision results without source-citation actions, opens their revision viewer,
and captures the search view at desktop and mobile widths.

The research suite also mocks the Zotero local bridge: collection filtering,
attachment inspection, inert external titles, retention consent and instance-bound
capture, a fully mapped archive with direct import hidden, and continued evidence
access while Zotero is unavailable followed by successful retry. It renders the
Zotero controls at desktop and mobile widths. These
fixtures do not establish compatibility with a running Zotero installation or
validate a real library migration.

The docs suite stages the Pages publication set and loads the homepage, all
guides and articles, blog index and public reports through intercepted local
routes at 1440, 390 and 320 pixels. Representative homepage, guide, article and
report surfaces also cover light/dark themes with JavaScript enabled and
disabled. It checks canonical URLs, assets, console
errors, overflow, navigation, heading order and explicit content-image dimensions.
The read-only example also exercises keyboard paragraph expansion, filters,
chapter links and chart controls, with no API or external requests. Screenshots
stay under `/tmp/lixity-public-docs-*`.

The visual-consistency suite compares shared color roles between Pages and a
synthetic dashboard in light/dark mode at 1440 and 320 pixels. It checks primary
action contrast and target size, keyboard focus, reduced motion, increased text
spacing and theme switching. Paragraph chips and dimension controls are measured
with mouse/coarse pointers, including pressed paragraph targets. Screenshots stay
under `/tmp/lixity-visual-consistency-*`.
These targeted checks are not a full WCAG conformance audit.
The same suite checks short-window project dialogs: focused fields remain
visible, optional controls and footer actions remain reachable, disabled
buttons do not acquire enabled hover feedback, and switching project tabs
does not reset the separate research revision editor.

The analysis-overview suite checks the reversible manuscript-measurements
disclosure, retained values and open state, complete bounded flag lists, explicit
To-do draft/cancel, keyboard scrolling and pinned chapter/character identity. It
distinguishes measured zero from unavailable chapter comparisons in seven locales
at 1440 and 320 pixels, and checks expanded standalone values without JavaScript.
Screenshots stay under `/tmp/lixity-analysis-overview-*`.

The analysis-navigation suite checks section selection at the page bottom,
hidden targets, keyboard paragraph/chapter focus, nested disclosure reveal and
hidden Style-tab routes. Normal/reduced-motion journeys preserve exact passage
position, suspended Values and unrelated toolbar focus. Seven desktop/mobile
locales check link spacing and horizontal arrow-key reachability without undoing
the vertical content jump. Synthetic screenshots stay under
`/tmp/lixity-analysis-navigation-*`; browsing performs no writes.

The analysis-narration suite retains all 17 synthetic dialogue chapters in
manuscript order, including measured zero, and exercises bounded keyboard
scrolling and the final chapter route. It checks localized pacing ASL units,
relative bar-scale guidance and reversible Hook heuristic help in seven locales
at 1440 and 320 pixels. Screenshots stay under `/tmp/lixity-analysis-narration-*`.

The scenes suite renders seven locales at desktop and mobile widths. It checks
actual per-scene observations, inert project labels, direct comparison-row routes,
grouped keyboard-operated disclosures, readable bounded scrolling tables and
unavailable values. Screenshots stay under `/tmp/lixity-scenes-ui-*`.

The settings suite uses synthetic intercepted responses and disposable native
projects. It verifies locale-safe values, validation before submission, reset
without saving, FDR row filtering, mobile layout and the title's serif font. For
audio races, a real ready-status response is held until the target or manuscript
context changes. The test waits until the browser has consumed it before asserting
that audio stays hidden. A separate renderer gate keeps cancellation in flight;
neither check relies on a fixed inference delay.

The register-settings suite uses a disposable native project to verify register
and chapter-assignment saves, target validation, duplicate removal, inert names,
unchanged manuscript bytes and preservation of newer rows during pending saves.
It renders seven locales at 1440 and 320 pixels; screenshots stay under
`/tmp/lixity-register-settings-*`.

The layout test covers every panel at 1440, 768, 390 and 320 pixels, including
long chapter strips, consistent panel spacing, readable scrolling tables,
expanded settings/paragraphs and keyboard-accessible chapter matrix tooltips.
Synthetic screenshots are written to `/tmp/lixity-layout-*.png`.

The overlay-layout suite checks seven locales with synthetic documents. It covers
the sidebar control beside product identity, stable disclosure state and focus
after resize; reading settings at 390/320 by 480 pixels with enlarged text;
paragraph-action clearance at 901/1024 pixels and split limits; reachable revision
Close; and long provenance text wrapping. It records no manuscript writes and
keeps screenshots under `/tmp/lixity-overlay-layout-*`. The tooltip suite separately
checks updated action text and dismissal on nested scroll/resize.

The NDA draft suite checks the five-field form in seven languages at desktop
and mobile widths: local-calendar defaults, validation, inert preview, pending
and failed requests, private logging, reload behavior and exact PDF/TXT download
bytes. It uses intercepted synthetic responses and writes only under
`/tmp/lixity-nda-draft-*`. For download assertions, use a Chromium executable whose
temporary files are visible to Playwright; Snap's private `/tmp` can cause
`download.saveAs` to fail with `ENOENT`. The existing
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH` override can select a bundled Chromium.

The setup-guide suite checks explicit OCR/Zotero metadata requests without an
archive, no automatic diagnostic calls, connection/readiness distinctions,
inert advanced messages and seven-language desktop/mobile rendering. It performs
no installation, configuration write or library/attachment browse.

The manuscript-search suite checks unopened paragraph contents stay outside the
live document, text precedes the collapsed Values disclosure, closing releases
rendered text, and the complete embedded manuscript remains searchable. It also
checks style-tab selection, keyboard navigation and existing metric jumps at
1440 and 320 pixels, including inert manuscript text containing a script terminator.
The loaded review entry opens a real passage with keyboard focus and links to
existing chapter/rhythm views. The setup suite also checks the empty-analysis
import shortcut without submitting or retaining a file.

The project-history suite checks recent-project links and clear history at
desktop/mobile sizes in seven languages, including blocked storage, malformed
entries, cancellation and unsuccessful opens. The decision-acknowledgement suite
checks exact displayed-version tokens, explicit applied/reopen actions, failed
requests preserving the view and stale/withdrawn warnings. Both use synthetic
fixtures and never connect to a running user's project.

The minimal-workflows suite checks explicit marker Save/Cancel, failed requests
with retained notes, duplicate-submit prevention, paragraph filter reset and
the one native analysis action at desktop/mobile widths in seven languages.

The dossier-images suite uses a disposable research archive and synthetic PNG/JPEG
files. It checks local preview and cancellation, byte/pixel limits before decoding,
atomic attachment, exact saved-version conflicts, full/section/history rendering,
withdrawal/purge placeholders, keyboard enlargement and inert hostile metadata.
No external image is fetched and no running user project is selected. Screenshots
remain temporary; these cases run in the existing single Chromium job.

The dossier-media suite additionally needs `ffmpeg` with libx264/libvpx to create
short synthetic MP4/WebM clips; it retains no third-party media fixtures.
It checks the shared PDF/video attachment dialog, explicit consent/cancellation,
exact downloaded PDF bytes, actual WebM playback, pinned-history immutability,
source-file export scope, no remote requests and 1440/320-pixel native/companion
layouts. Run with a canonical temporary directory when testing project paths:
`TMPDIR="$PWD/.artifacts" PYTHONPATH=src node tests/browser/dossier-media.cjs`.

The dossier-workflows suite exercises titled contextual claim/decision forms and
the shared section editor against a disposable server: preserved drafts and pins,
body-only preparation, unrelated concurrent-section preservation, explicit
overlapping conflict choices and desktop/mobile rendering in seven languages.

The manuscript-links test uses synthetic intercepted responses in seven locales
at 1440 and 320 pixels, with its origin-return checks also at 390 pixels. It
verifies explicit quotation retention, current claim version pins, Unicode codepoint selection offsets, inert source text, overlapping
search/link highlights and lazy reopening. Additional cases reject metrics and
cross-paragraph selections, conflicting snapshots, changed sources, copied
projects and unavailable/read-failed sources; moved and ambiguous anchors stay
review hints. Held reads/writes verify context guards, pending deduplication and
preservation of a newer draft. Screenshots remain under `/tmp`.

The work thread shows the originating manuscript lines and one return action;
record identity and pinned/current versions stay in the record viewer. History/edit
transitions must not duplicate those details in navigation. Returning or changing
source context clears the thread. These cases also inspect the
thread in both themes and with desktop navigation collapsed.

Passage research consumes the shared backend projection. Native browser checks
assert no record/dossier reads for summary composition, then exercise explicit
viewers, exact historical pins, mixed/missing/unavailable model failures and late
responses after passage/source/project/navigation changes. Backend grouping,
bounded association counts and one-snapshot/no-write behavior are tested in
Python; export tests compare frozen context data with the same native projection.

When a temporary-filesystem quota is exhausted, browser fixtures can fail before
Chromium starts even when `df` reports free space. Keep evidence on local disk
and give the runner a task-local temporary directory instead of changing system
quotas or deleting another task's output. On POSIX shells, for example:

```sh
mkdir -p .artifacts/browser-temp
TMPDIR="$PWD/.artifacts/browser-temp" make browser-full
```

Keep `TMPDIR` short when using a deeply nested worktree. Chromium creates a
Unix socket below it; an overlong path fails with `Socket path too long` before
the app opens. In that case, use a short local directory such as
`$HOME/.cache/lixity-tests` instead.

`.artifacts/` is ignored. Review synthetic captures before publishing any file;
never place private manuscripts or credentials in test artifacts. Remove or
archive only outputs owned by the completed task. The browser helpers and their
Python fixture children inherit `TMPDIR`.
