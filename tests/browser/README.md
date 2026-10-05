# Dashboard browser regression

Run after installing the Python development environment and Playwright with
Chromium. Playwright is optional tooling, not a Lixity runtime dependency.

```sh
node tests/browser/style-space.cjs
node tests/browser/settings.cjs
node tests/browser/layout.cjs
node tests/browser/research.cjs
node tests/browser/list-filters.cjs
node tests/browser/project-controls.cjs
node tests/browser/scenes.cjs
node tests/browser/docs.cjs
node tests/browser/visual-consistency.cjs
```

If Playwright is installed outside this repository, set `PLAYWRIGHT_MODULE` to
its module directory. `PYTHON_BIN` optionally overrides `.venv/bin/python`.
The test generates a synthetic manuscript, checks canvas interaction, tooltip
escaping, idle rendering and mobile layout, and prints its temporary screenshot
directory. It does not read any private manuscript or contact a server.

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
collapsed capability-gated NDA panel. Its synthetic examples and intercepted
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

The docs suite loads public static files through intercepted
local routes: all four HTML pages at 1440, 390 and 320 pixels, with JavaScript
enabled and disabled. It checks canonical URLs, assets, console errors, overflow
and navigation, heading order and explicit content-image dimensions; screenshots
stay under `/tmp/lixity-public-docs-*`.

The visual-consistency suite compares shared color roles between Pages and a
synthetic dashboard in light/dark mode at 1440 and 320 pixels. It checks primary
action contrast and target size, keyboard focus, reduced motion, increased text
spacing and theme switching. Screenshots stay under `/tmp/lixity-visual-consistency-*`.
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
It also exercises NDA records containing hostile HTML/attribute payloads;
all values must remain inert text and action IDs must remain intact.
Synthetic screenshots are written to `/tmp/lixity-layout-*.png`.
