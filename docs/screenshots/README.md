# Product screenshots

These are browser captures of the actual development version, not mockups.
The default source is `samples/pride-and-prejudice.md`, the public-domain
Austen sample documented in `samples/README.md`. No private manuscript,
NDA record, passphrase or live project server is used.

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
threshold defaults. It writes temporary HTML and a capture manifest under
ignored `.screenshots/`. One Playwright browser captures all views after fonts
and animation frames settle, with reduced motion and fixed viewport sizes.
The command fails on runtime errors, missing panels or mobile page overflow.
`.screenshots/capture-results.json` records actual image dimensions.

## Capture scope

- `dashboard-light` / `dashboard-dark`: desktop overview viewports.
- `dashboard-heatmap`: the upper part of the chapter heatmap, not every chapter.
- `dashboard-layer`: Chapter I with dialogue coloring and three opened paragraphs.
- `dashboard-dimensions`: complete panel, without cutting off the last card.
- `dashboard-markers`: the actual marker panel; three illustrative notes are
  inserted into an in-memory sample copy only.
- `dashboard-settings`: the shared settings form with detection controls expanded.
- `dashboard-reference`: complete reference bands with medians and sample counts.
- `dashboard-mobile`: 390-pixel mobile overview viewport.
- `dashboard-dimensions-mobile` / `dashboard-dimensions-dark`: complete panels.
- `cli-analyze` / `cli-style`: terminal-style excerpts of actual report output.

The screenshot helper selects sections by exact ID. It does not crop whichever
earlier panel happens to mention “markers.” Screenshots illustrate a corpus's
analysis, not validated editorial judgments or benchmark accuracy. Pixel-level
output can vary with OS fonts and browser versions.
