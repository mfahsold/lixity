# Dashboard browser regression

Run after installing the Python development environment and Playwright with
Chromium. Playwright is optional tooling, not a Lixity runtime dependency.

```sh
node tests/browser/style-space.cjs
node tests/browser/debug.cjs
node tests/browser/nda-draft.cjs
node tests/browser/setup-guide.cjs
node tests/browser/project-history.cjs
node tests/browser/decision-acknowledgement.cjs
node tests/browser/minimal-workflows.cjs
node tests/browser/dossier-images.cjs
node tests/browser/dossier-workflows.cjs
node tests/browser/settings.cjs
node tests/browser/layout.cjs
node tests/browser/research.cjs
node tests/browser/list-filters.cjs
node tests/browser/manuscript-search.cjs
node tests/browser/project-controls.cjs
node tests/browser/scenes.cjs
node tests/browser/docs.cjs
node tests/browser/visual-consistency.cjs
```

If Playwright is installed outside this repository, set `PLAYWRIGHT_MODULE` to
its module directory. `PYTHON_BIN` optionally overrides `.venv/bin/python`.
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

The separate browser workflow runs every suite above in one Chromium job
on pull requests and pushes to `main` that change `src/`, `tests/browser/`,
`tests/test_ui_contract.py` (shared Python fixtures), `docs/`, `scripts/`,
`pyproject.toml` or `.github/workflows/`, and on manual dispatch. Newer pushes cancel
superseded runs. Browser binaries are downloaded for each run; screenshots stay
temporary and are not uploaded as persistent CI artifacts.

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

The project-controls suite checks manuscript file/drop selection and inert
filenames, explicit native import confirmation, the existing embedding load
payload, persistent New/Open/guidance across the three views, and the initially
explicit NDA capability gating. Its synthetic examples and intercepted
requests exercise desktop/mobile layouts and seven languages; screenshots stay
under `/tmp/lixity-project-controls-*`.

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

The docs suite stages the Pages publication set and loads six HTML pages through
intercepted local routes at 1440, 390 and 320 pixels, in light and dark themes,
with JavaScript enabled and disabled. It checks canonical URLs, assets, console
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

The scenes suite renders seven locales at desktop and mobile widths. It checks
actual per-scene observations, inert project labels, keyboard-operated
disclosures, readable scrolling tables and unavailable values. Screenshots stay
under `/tmp/lixity-scenes-ui-*`.

The settings test intercepts all requests to a synthetic host. It verifies
locale-safe values, validation before submission, reset without saving, FDR
row filtering, mobile layout and the serif font being limited to the title.

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
