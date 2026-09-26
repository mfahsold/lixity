# Dashboard browser regression

Run after installing the Python development environment and Playwright with
Chromium. Playwright is optional tooling, not a Lixity runtime dependency.

```sh
node tests/browser/style-space.cjs
node tests/browser/settings.cjs
node tests/browser/layout.cjs
node tests/browser/research.cjs
```

If Playwright is installed outside this repository, set `PLAYWRIGHT_MODULE` to
its module directory. `PYTHON_BIN` optionally overrides `.venv/bin/python`.
The test generates a synthetic manuscript, checks canvas interaction, tooltip
escaping, idle rendering and mobile layout, and prints its temporary screenshot
directory. It does not read any private manuscript or contact a server.

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

The settings test intercepts all requests to a synthetic host. It verifies
locale-safe values, validation before submission, reset without saving, FDR
row filtering, mobile layout and the serif font being limited to the title.

The layout test covers every panel at 1440, 768, 390 and 320 pixels, including
long chapter strips, consistent panel spacing, readable scrolling tables,
expanded settings/paragraphs and keyboard-accessible chapter matrix tooltips.
It also exercises NDA records containing hostile HTML/attribute payloads;
all values must remain inert text and action IDs must remain intact.
Synthetic screenshots are written to `/tmp/lixity-layout-*.png`.
