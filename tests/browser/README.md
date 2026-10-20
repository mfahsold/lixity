# Dashboard browser regression

Run after installing the Python development environment and Playwright with
Chromium. Playwright is optional tooling, not a Lixity runtime dependency.

```sh
make browser          # everyday core surfaces (fast group, 3 workers)
make browser-changed  # only the suites affected by modified git paths
make browser-full     # every suite, run before a release (3 workers)
# or: python3 scripts/run_browser_suites.py --area research --jobs 3
```

`--list` prints the suite names, `--group fast|full` selects the everyday core
surfaces or everything, `--area NAME` runs one surface (`docs`, `research`,
`analysis`, `project`, `tokens`), `--changed [BASE]` maps modified git paths
to the affected areas (falling back to the full set when a shared foundation
changed), `--jobs N` runs independent suites in parallel, `--only NAME`
selects suites and `--start NAME` resumes after a failure.

Before starting suites, the runner executes the support directory's Node tests.
These check disposable-server startup, malformed readiness data, early exits,
timeouts and cleanup. `--list` only lists suites. Native-server helpers keep
readiness and termination handling shared without replacing the real HTTP flows.
Large Python-generated JSON fixtures use a disposable file-backed transport.
Complete dashboard HTML and bundled assets are retained without a fixed stdout
pipe budget; success, generation failures and malformed JSON all clean up files.

Localized suites retain all seven languages at desktop and mobile widths for
rendering, labels and submitted machine values. Language-independent interaction
and conflict scenarios run once per relevant viewport. Native server saves and
intercepted responses cover different boundaries and remain separate.

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
requests exercise desktop/mobile layouts and seven languages; screenshots stay
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
navigation retains the passage. Normal-motion cases cover immediate reversal,
tool switching and a live reduced-motion preference change. Source identity,
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

The research-selection suite uses a disposable synthetic archive to select
source text and prepare an evidence draft. It checks selection boundaries,
Unicode offsets, unavailable sources, project changes, explicit save and the
full retained passage's immutable citation. Screenshots and fixtures stay in `/tmp`.

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

The scenes suite renders seven locales at desktop and mobile widths. It checks
actual per-scene observations, inert project labels, keyboard-operated
disclosures, readable scrolling tables and unavailable values. Screenshots stay
under `/tmp/lixity-scenes-ui-*`.

The settings test intercepts all requests to a synthetic host. It verifies
locale-safe values, validation before submission, reset without saving, FDR
row filtering, mobile layout and the serif font being limited to the title.

The register-settings suite uses a disposable native project to verify register
and chapter-assignment saves, target validation, duplicate removal, inert names,
unchanged manuscript bytes and preservation of newer rows during pending saves.
It renders seven locales at 1440 and 320 pixels; screenshots stay under
`/tmp/lixity-register-settings-*`.

The layout test covers every panel at 1440, 768, 390 and 320 pixels, including
long chapter strips, consistent panel spacing, readable scrolling tables,
expanded settings/paragraphs and keyboard-accessible chapter matrix tooltips.
Synthetic screenshots are written to `/tmp/lixity-layout-*.png`.

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

The dossier-workflows suite exercises titled contextual claim/decision forms and
the shared section editor against a disposable server: preserved drafts and pins,
body-only preparation, unrelated concurrent-section preservation, explicit
overlapping conflict choices and desktop/mobile rendering in seven languages.

The manuscript-links test uses synthetic intercepted responses in seven locales
at 1440 and 320 pixels. It verifies explicit quotation retention, current claim
version pins, Unicode codepoint selection offsets, inert source text, overlapping
search/link highlights and lazy reopening. Additional cases reject metrics and
cross-paragraph selections, conflicting snapshots, changed sources, copied
projects and unavailable/read-failed sources; moved and ambiguous anchors stay
review hints. Held reads/writes verify context guards, pending deduplication and
preservation of a newer draft. Screenshots remain under `/tmp`.
