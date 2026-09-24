# Dashboard browser regression

Run after installing the Python development environment and Playwright with
Chromium. Playwright is optional tooling, not a Lixity runtime dependency.

```sh
node tests/browser/style-space.cjs
```

If Playwright is installed outside this repository, set `PLAYWRIGHT_MODULE` to
its module directory. `PYTHON_BIN` optionally overrides `.venv/bin/python`.
The test generates a synthetic manuscript, checks canvas interaction, tooltip
escaping, idle rendering and mobile layout, and prints its temporary screenshot
directory. It does not read any private manuscript or contact a server.
