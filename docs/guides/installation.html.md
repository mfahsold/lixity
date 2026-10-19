# Install Lixity and open a manuscript locally

Explore sentence rhythm, vocabulary and style patterns in your Markdown manuscript. Lixity runs its analysis on your computer and saves a dashboard you can open in a browser. No account or manuscript upload is required.

Maintained by the Lixity project · Updated 19 October 2026

## What do I need?

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). It installs the published package and supplies managed Python 3.12; no Git or separate Python install is needed. Lixity is on [PyPI](https://pypi.org/project/lixity/); every release also ships a pinned wheel with checksums on [GitHub Releases](https://github.com/mfahsold/lixity/releases), and released versions are archived on Zenodo for citation (concept DOI [10.5281/zenodo.23390297](https://doi.org/10.5281/zenodo.23390297)). Installation needs an internet connection. Analysis runs offline afterward. PDF import has [additional requirements](research-pdf.html#ocr).

**License:**

Lixity is open source under AGPL-3.0-or-later; every writing purpose is covered, including self-publishing. A separate written commercial license exists only for closed-source integrations. Read the

[licensing guide](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)

.

## Install Lixity

```
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Open a new terminal, then verify and start the app:

```
lixity --version
lixity service start --open
```

This installs the current release from PyPI in uv's [isolated tool environment](https://docs.astral.sh/uv/concepts/tools/). For a pinned, checksum-verified setup, install the release wheel instead — `uv tool install --python 3.12 --managed-python --reinstall-package lixity "https://github.com/mfahsold/lixity/releases/download/v0.7.0/lixity-0.7.0-py3-none-any.whl"` — and verify it against the SHA256SUMS file on the release page. Shell integration configures new terminals; it does not change an already open one. See the [release notes](../releases/v0.7.0.md) for changes and compatibility.

**Development builds instead**

For unreleased development work, install Git, stop the managed service and replace the installation with:

`uv tool install --python 3.12 --managed-python --reinstall-package lixity "git+https://github.com/mfahsold/lixity.git@main"`

`main`

changes over time. Verify the version before starting again. Most users should stay on the current release. See the

[update instructions](../INSTALLATION.md#updates-and-removal)

.

## Start the workspace

The managed app opens `http://127.0.0.1:8765/`. Its default is an empty workspace; it does not search your terminal's current folder. Choose **Open Project** for an existing folder or **Analyze a manuscript** for an import preview. Confirm the language and read a passage before interpreting its measurements.

1. Choose **Analyze a manuscript** (or **New Project**) and confirm the preview: title, analysis language and optional author name.

2. Read the **Start your review** panel first: **Open passage**, **Explore chapters** or **Open sentence rhythm**.

3. Work from a flagged passage or open any paragraph, expand **Values** and write a marker note if something needs another look.

4. Export the result with **PDF export**: A5 reading copy, A4 manuscript sheets or the A4 analysis report.

The [first-session guide](../ONBOARDING.md) describes every stage, and the [public-domain examples](https://mfahsold.github.io/lixity/examples/effi-briest.html) show a finished analysis without installation.

**Generate an offline HTML report instead**

Save this synthetic text as

`sample.md`

. Two short chapters are sufficient to exercise the workflow, but not to establish a reliable stylistic baseline.

`## Chapter 1 The rain stopped. Mara opened the window. The street was quiet. ## Chapter 2 At the library, Mara examined a handwritten catalogue while the keeper searched the shelves.`

`lixity dashboard sample.md --language en -o sample-dashboard.html`

Open

`sample-dashboard.html`

in your browser. Use a longer manuscript with several chapters for more informative results, and read

[how to interpret them](interpretation.html)

. Choose

`--language de`

for German or

`--language en`

for English. English is the default;

`--language auto`

explicitly requests detection.

## Optional Zotero Desktop

For source capture, install Zotero 10 or later on the same computer and enable its local API in Settings → Advanced. Download the attachments you need. Lixity can browse collections and retain selected PDF/text attachments with your permission. No cloud account is needed. See [Zotero capture and migration](research-pdf.html#zotero); images, audio and video remain in Zotero.

## Open an existing project and research archive

With the service stopped, an explicit project can be supplied when starting:

```
lixity service start --open /absolute/path/to/project
```

Replace the example path with your project folder. Open `http://127.0.0.1:8765/` and check the project name in the workspace bar. **Open Project** switches this server to an existing folder and its research. CLI analysis, research and build commands do not switch an already running server. **New Project → Import Manuscript** creates a separate project from uploaded text.

For a research-only workspace, an initialized archive can be opened without a manuscript. Source records remain available; comparing sources with manuscript text needs a loaded manuscript.

Switch between Research & Dossiers, Manuscript & Analysis, and Project & Settings. New Project, Open Project and optional guidance are available in every view. Selecting or dropping a manuscript opens its preview directly; confirm to create a separate project. Source and dossier filters narrow their lists; Research → Search looks through retained text.

The [first-session guide](../ONBOARDING.md) explains these controls. The NDA generator downloads agreement text with name, optional address, project, date and place; it does not keep a recipient register.

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

Stop each managed instance before replacing the package. Use the published wheel for the desired release:

```
lixity service stop
uv tool upgrade lixity
lixity --version
lixity service start --open
```

For a custom port, use `lixity service stop --port 9000` with that instance's port before updating. Pass an explicit project again if you want one at startup. `uv tool upgrade lixity` selects the newest PyPI release; a pinned wheel keeps its fixed URL and is replaced explicitly.

For removal, stop all managed instances and disable any login-startup entry you configured, then run `uv tool uninstall lixity`. Manuscript folders and research archives remain. See the [complete update/removal reference](../INSTALLATION.md#updates-and-removal).

## The project exists, but the server cannot open it

The chooser shows folders available to the computer and account running Lixity. A container or service account may have different access from your terminal. Check the project path and permissions, then restart the intended server. Use Open Project to reconnect the original folder rather than importing another copy.

If port 8765 is already occupied, identify the existing server or use `--port 9000`. Changing ports leaves the previous instance running. See [installation troubleshooting](../INSTALLATION.md#troubleshooting).

## Using the Python API?

Install Lixity in your Python project's own environment. The isolated command-line installation does not make `import lixity` available to other Python programs. See the [Python setup commands](../INSTALLATION.md#python-api-project-environment).

Continue with the [full installation reference](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md), [shared pipeline architecture](https://github.com/mfahsold/lixity/blob/main/docs/ARCHITECTURE.md), or [research source workflow](research-pdf.html).

[Lixity home](../) · [Report a reproducible issue](https://github.com/mfahsold/lixity/issues) · [Legal notice](../#impressum)
