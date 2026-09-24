# Dashboard browser regression

Run after installing the Python development environment and Playwright with
Chromium. Playwright is optional tooling, not a Lixity runtime dependency.

```sh
node tests/browser/style-space.cjs
node tests/browser/settings.cjs
node tests/browser/layout.cjs
```

If Playwright is installed outside this repository, set `PLAYWRIGHT_MODULE` to
its module directory. `PYTHON_BIN` optionally overrides `.venv/bin/python`.
The test generates a synthetic manuscript, checks canvas interaction, tooltip
escaping, idle rendering and mobile layout, and prints its temporary screenshot
directory. It does not read any private manuscript or contact a server.

The settings test intercepts all requests to a synthetic host. It verifies
locale-safe values, validation before submission, reset without saving, FDR
row filtering, mobile layout and the serif font being limited to the title.

The layout test covers every panel at 1440, 768, 390 and 320 pixels, including
long chapter strips, consistent panel spacing, readable scrolling tables,
expanded settings/paragraphs and keyboard-accessible chapter matrix tooltips.
It also exercises NDA records containing hostile HTML/attribute payloads;
all values must remain inert text and action IDs must remain intact.
Synthetic screenshots are written to `/tmp/lixity-layout-*.png`.
