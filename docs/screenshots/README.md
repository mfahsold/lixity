# Product screenshots

These are browser captures of the **v1.23.0 UI** on **3 October 2026**.
They show the three workspace views, native
manuscript picker, import confirmation, local research filters and collapsible
NDA controls alongside the existing analysis panels.

The default analysis source is `samples/pride-and-prejudice.md`, the public-domain
Austen sample documented in `samples/README.md`. Project files, server-local paths,
customs-case sources, dossiers, claims and decisions are synthetic. Marker notes
are added only to an in-memory sample copy. The NDA preview uses a locked demo
store with no agreements or passphrase. No private manuscript, source archive,
credential or running user project is used.

## Regeneration

Install the Python development environment, Node.js, and optional Playwright
with Chromium. Playwright is capture/test tooling, not a runtime dependency.

```bash
.venv/bin/python scripts/make_screenshots.py
```

If Playwright is installed outside the checkout:

```bash
PLAYWRIGHT_MODULE=/absolute/path/to/playwright \
  .venv/bin/python scripts/make_screenshots.py
```

The Python generator uses the shared analysis pipeline with explicit code
threshold defaults and builds a disposable synthetic research archive through
the implemented research API. It writes temporary HTML, fixture responses and
a capture manifest under ignored `.screenshots/`. Browser requests use those
local fixtures; the browser capture does not submit project creation or create
agreements.

One Playwright browser captures all views after fonts and animation frames
settle, with reduced motion and fixed desktop/mobile widths. The command
fails on runtime errors, missing panels or mobile page overflow.
Dialog captures include the complete form and its confirmation controls: the
capture helper temporarily expands scroll containers, so these images show
full content rather than only the initially visible viewport. In the application,
long dialogs retain normal scrolling. Other panel captures also include their
full content unless a bounded viewport or heatmap excerpt is specified below.
`.screenshots/capture-results.json` records the actual PNG dimensions; the Pages
gallery's `width` and `height` attributes must match those results. Review both
desktop and mobile images and their captions after regeneration. Use only
reviewed public-domain or synthetic material for repository screenshots.

## Capture scope

- `dashboard-light` / `dashboard-dark`: desktop Manuscript & Analysis overview
  viewports, with the persistent workspace actions and three view tabs.
- `dashboard-heatmap`: the upper part of the chapter heatmap, not every chapter.
- `dashboard-layer`: Chapter I with dialogue coloring and three opened paragraphs.
- `dashboard-welcome`: initial empty workspace viewport with global New/Open
  actions, view tabs and optional quickstart guidance.
- `dashboard-project-modal`: native dialog on the Start new manuscript tab,
  with narrative structure templates (Minimal, 3-Act, Research).
- `dashboard-project-open` / `dashboard-project-open-mobile`: native Open Project
  dialog and synthetic server-local file/folder chooser. Selection remains
  separate from confirmation; opening reconnects the existing archive.
- `dashboard-project-settings` / `dashboard-project-settings-mobile`: complete
  Project & Settings view, including the native manuscript picker and initially
  collapsed NDA manager. Choosing or dropping a file sends no request.
- `dashboard-project-import` / `dashboard-project-import-mobile`: the import
  dialog after selecting a synthetic manuscript, with its local preview and
  explicit confirmation. Confirmation creates a separate project; it does not
  reopen an existing archive.
- `dashboard-nda` / `dashboard-nda-mobile`: expanded locked-state preview of the
  native details panel, which starts collapsed. No agreement is created or shown.
- `dashboard-dimensions`: complete panel, without cutting off the last card.
- `dashboard-markers`: the actual marker panel; five illustrative notes are
  inserted into an in-memory sample copy only.
- `dashboard-settings`: the shared settings form with detection controls expanded.
- `dashboard-reference`: complete reference bands with medians and sample counts.
- `dashboard-mobile`: 390-pixel Manuscript & Analysis overview viewport.
- `dashboard-dimensions-mobile` / `dashboard-dimensions-dark`: complete panels.
- `cli-analyze` / `cli-style`: terminal-style excerpts of actual report output.
- `dashboard-research`: standalone source dashboard with synthetic, user-supplied
  source criticism context; the metadata is not independently verified.
- `dashboard-research-sources` / `dashboard-research-sources-mobile`: retained
  synthetic customs-case sources with a local metadata filter and opened details.
  Matching uses loaded titles, tags and IDs, not retained source text.
- `dashboard-research-dossiers` / `dashboard-research-dossiers-mobile`: synthetic
  dossiers filtered by loaded metadata, including excerpts and section names.
  Full dossier bodies are outside this filter's scope.
- `dashboard-research-search` / `dashboard-research-search-mobile`: explicit
  full-text search of the synthetic archive, with passage IDs, excerpts and reuse
  actions. This is separate from typing into a local list filter.
- `dashboard-research-claims` / `dashboard-research-decisions`: the integrated
  research manager with a synthetic claim, archive-checked citation link and two
  contrasting editorial decisions. `-mobile` variants capture the same views
  at 390 pixels. Read-only browser responses are built from the real research
  API in ignored `.screenshots/research-workspace-fixture.json`; the displayed
  project path is shortened to `./research-demo` for portable screenshots.
- `cli-research`: complete terminal search and citation responses from the
  synthetic archive, with wrapped JSON, passage IDs and character offsets.

The screenshot helper selects sections by exact ID. It does not crop whichever
earlier panel happens to mention “markers.” Screenshots illustrate a corpus's
analysis, not validated editorial judgments or benchmark accuracy. Pixel-level
output can vary with OS fonts and browser versions.

The research demonstration is generated in `scripts/make_screenshots.py`.
Its customs case and provenance labels are fictional test data, separate from
the public-domain Austen sample used for manuscript analysis views. Source
integrity checks and retained quotations do not establish factual accuracy;
claims and editorial decisions remain human review records.
