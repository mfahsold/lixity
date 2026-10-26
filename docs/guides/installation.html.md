# Install Lixity and open a manuscript locally

Explore sentence rhythm, vocabulary and style patterns in your Markdown manuscript. Lixity runs its analysis on your computer and saves a dashboard you can open in a browser. No account or manuscript upload is required.

Updated 23 October 2026

**Version line:** The current release is **v0.7.6**, in the pre-1.0 **0.x** line. Historical **1.x** and **3.x** tags predate the numbering reset. A larger historical number does not mean a newer release; product and schema versions are independent.

## What do I need?

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). It installs the published package and supplies managed Python 3.12; no Git or separate Python install is needed. Lixity is on [PyPI](https://pypi.org/project/lixity/); every release also ships a pinned wheel with checksums on [GitHub Releases](https://github.com/mfahsold/lixity/releases), and released versions are archived on Zenodo for citation (concept DOI [10.5281/zenodo.23390297](https://doi.org/10.5281/zenodo.23390297)). Installation needs an internet connection. Analysis runs offline afterward. PDF import has [additional requirements](research-pdf.html#ocr).

**License:**

Lixity is open source under AGPL-3.0-or-later; every writing purpose is covered, including self-publishing. A separate written commercial license exists only for closed-source integrations. Read the

[licensing guide](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)

.

## Install Lixity

**uv is not installed yet**

First check `uv --version`. Windows with WinGet:

```
winget install --id=astral-sh.uv -e
```

macOS with Homebrew already installed:

```
brew install uv
```

For Linux or other setups, follow the [official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/). Open a new terminal and check `uv --version`. This installs uv; the next step installs Lixity.

```
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Open a new terminal, then verify and start the app:

```
lixity --version
lixity doctor
lixity service start --open
```

If `lixity` is not found, check `uv tool list`, run `uv tool update-shell` and open a new terminal. `uv tool dir --bin` shows the executable directory. The health check reports installation/service issues, not linguistic validity.

This installs the current release, **v0.7.6**, from PyPI in uv's [isolated tool environment](https://docs.astral.sh/uv/concepts/tools/). Shell integration applies to new terminals. See the [release notes](../releases/v0.7.6.md) for changes and compatibility.

## Start the workspace

The managed app opens `http://127.0.0.1:8765/`. Its default is an empty workspace; it does not search your terminal's current folder. Choose **Open Project** for an existing folder or **Analyze a manuscript** for an import preview. Confirm the language and read a passage before interpreting its measurements.

1. Open your existing project or confirm an import preview, including the manuscript language.

2. Read in **Manuscript**. Choose a paragraph's **… → Explore passage** for its inspector. The separate **Analysis** switch shows diagnostics across the manuscript.

3. Use **Analysis overview** for chapter comparisons, then **Back to passage** to return. **PDF export** offers editorial, reading, submission and report copies.

English is the default analysis language; automatic detection is an explicit choice. The [first-session guide](../ONBOARDING.md) explains project selection. For a short example before importing, try the [Warehouse 4 walkthrough](first-look.html). Its public demo cannot import, edit or save.

Check the app, stop it and return later:

```
lixity service status
lixity service stop
lixity service start --open
```

Open the project again, or provide its path when starting. `restart --open` restores recorded launch settings, including the startup project; a later project choice in the browser is separate. [Service lifecycle](#restart) explains the difference.

**Pinned release wheel**

For a reproducible setup, verify the release wheel against its `SHA256SUMS`, then install it instead:

```
uv tool install --python 3.12 --managed-python --reinstall-package lixity "https://github.com/mfahsold/lixity/releases/download/v0.7.6/lixity-0.7.6-py3-none-any.whl"
```

A pinned wheel keeps its fixed source URL; replace it explicitly when updating. See the [installation reference](../INSTALLATION.md#updates-and-removal).

**Development builds instead**

To test unreleased changes, install Git, stop the managed service and replace the installation with:

```
uv tool install --python 3.12 --managed-python --reinstall-package lixity "git+https://github.com/mfahsold/lixity.git@main"
```

`main` changes over time and unreleased commits can share a version number. Verify the installation, run `lixity service restart --open` to restore recorded launch settings and reload your browser.

**Generate an offline HTML report instead**

Download the demo's [Warehouse 4 manuscript](../research/examples/harbour-manuscript.md) and save it as `warehouse-4.md`, then run:

```
lixity dashboard warehouse-4.md --language en -o warehouse-4.html
```

Open `warehouse-4.html` in your browser. This generates an analysis report from the same six chapters; the public demo also includes prepared research records. The short synthetic manuscript exercises the workflow, not a reliable literary baseline. Read [how to interpret the results](interpretation.html). English is the default; use `--language de` for German or explicit `--language auto` for detection.

## Optional Zotero Desktop

For source capture, install Zotero 10 or later on the same computer and enable its local API in Settings → Advanced. Download the attachments you need. Lixity can browse collections and retain selected PDF/text and PNG/JPEG attachments with your permission. Retention permits a local copy, not redistribution or factual acceptance. No cloud account is needed. See [Zotero capture and migration](research-pdf.html#zotero); audio and video remain in Zotero.

## Open an existing project and research archive

With the service stopped, an explicit project can be supplied when starting:

```
lixity service start --open /absolute/path/to/project
```

Replace the example path with your project folder. Open `http://127.0.0.1:8765/` and check the project name in the workspace bar. **Open Project** switches this server to an existing folder and its research. CLI analysis, research and build commands do not switch an already running server. **New Project → Import Manuscript** creates a separate project from uploaded text.

For a research-only workspace, an initialized archive can be opened without a manuscript. Source records remain available; comparing sources with manuscript text needs a loaded manuscript.

Switch between Research, Manuscript, and Project. New Project, Open Project and optional guidance are available in every view. Selecting or dropping a manuscript opens its preview directly; confirm to create a separate project. Source and dossier filters narrow their lists; Research → Search looks through retained text.

The [first-session guide](../ONBOARDING.md) explains these controls.

## Running the server day to day

The workspace uses `http://127.0.0.1:8765/` by default. Built-in analysis runs on your computer; optional integrations have their own setup and data handling. Tabs connected to one server share its active project.

```
lixity service status
lixity service restart
lixity service stop
```

After a computer restart, start the service again; no reimport is needed. Restart uses the saved launch settings, not a later project choice in the browser. A browser reload alone does not update running code.

Since v3.0.1, foreground `serve` and managed start/restart accept `--min-chapters N`, an integer of at least 2 (default 2). Restart retains the saved threshold unless overridden. See the [service command reference](../USAGE.md#lixity-service).

The controller manages its own instances. A foreground `lixity serve` process still stops with `Ctrl+C`; external systemd, launchd or Task Scheduler entries use their own manager. Login startup is an explicit advanced choice in the [setup reference](../INSTALLATION.md#optional-startup-at-login). Start Zotero for new captures; retained research stays readable while it is closed.

PyPI installations use `uv tool upgrade lixity`; wheel-pinned installations require the new release URL. Restart the workspace after updating. Product versions describe development maturity and are independent of research storage versions; consult the [archive compatibility guidance](../research/USAGE.md#storage-lifecycle-and-recovery) before sharing an archive with older readers.

## Update or remove Lixity

For a PyPI installation, stop each managed instance before upgrading:

```
lixity service stop
uv tool upgrade lixity
lixity --version
lixity service restart --open
```

Restart restores recorded launch settings even after stopping; a project selected later in the browser is not a startup setting. For a custom port, use `--port 9000` with both stop and restart. Pass an explicit project to override the recorded startup choice. `uv tool upgrade lixity` selects the newest PyPI release; a pinned wheel keeps its fixed URL and is replaced explicitly.

For removal, stop all managed instances and disable any login-startup entry you configured, then run `uv tool uninstall lixity`. Manuscript folders and research archives remain. See the [complete update/removal reference](../INSTALLATION.md#updates-and-removal).

## The project exists, but the server cannot open it

The chooser shows folders available to the computer and account running Lixity. A container or service account may have different access from your terminal. Check the project path and permissions, then restart the intended server. Use Open Project to reconnect the original folder rather than importing another copy.

If port 8765 is already occupied, identify the existing server or use `--port 9000`. Changing ports leaves the previous instance running. See [installation troubleshooting](../INSTALLATION.md#troubleshooting).

## Using the Python API?

Install Lixity in your Python project's own environment. The isolated command-line installation does not make `import lixity` available to other Python programs. See the [Python setup commands](../INSTALLATION.md#python-api-project-environment).

Continue with the [full installation reference](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md), [shared pipeline architecture](https://github.com/mfahsold/lixity/blob/main/docs/ARCHITECTURE.md), or [research source workflow](research-pdf.html).

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](../LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
