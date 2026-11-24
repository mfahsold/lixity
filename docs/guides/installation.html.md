# Install Lixity and open a manuscript locally

Find the right installer for your computer and open your first manuscript. Lixity works locally without an account. See the [installation manual](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md) for optional tools and troubleshooting.

Updated 24 November 2026

<a id="desktop"></a>

## Desktop downloads

Desktop installers are in testing. You can start today with the [published local browser app](#install).

Already have a desktop test installer? Follow the steps for your computer.

<a id="macos"></a>

### macOS

Desktop builds require macOS 12 or later.

1. In the Apple menu, open **About This Mac**. Match an Apple chip to the Apple Silicon DMG, or an Intel processor to the Intel DMG.

2. Open the DMG, then drag **Lixity** onto **Applications**. The **Start Here – Hier starten** file inside the image explains the steps offline.

3. Open **Lixity** from **Applications**. Eject the disk image after the copy completes.

See the [macOS installation notes](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#macos-desktop-dmg) for test builds and the location of the desktop log.

<a id="windows"></a>

### Windows

1. Check **Settings → System → About → System type**. The current desktop builds target x64 PCs.

2. Open the setup `.exe` to install for your account. Use the `.msi` when your organisation's deployment process calls for it.

3. Open **Lixity** from the Start menu. On systems missing WebView2, setup needs internet access to get the Microsoft runtime.

If setup cannot download the runtime, see [Microsoft’s WebView2 installation options](https://learn.microsoft.com/en-us/microsoft-edge/webview2/concepts/distribution#online-only-deployment).

<a id="linux"></a>

### Linux

The current desktop builds target x86-64. On Debian or Ubuntu, open the `.deb` with your package installer. It needs WebKitGTK 4.1 and GTK 3. After installation, open **Lixity** from the applications menu.

To run the `.AppImage` from its folder, allow it to execute in the file's properties and open it. If it reports a FUSE error, follow the [AppImage instructions for your distribution](https://docs.appimage.org/user-guide/troubleshooting/fuse.html).

<a id="desktop-first-launch"></a>

### First launch

Choose **Open a project folder**, **Import a manuscript**, or **Start writing** in the welcome window. Choose **Try the example offline** to preview the bundled English manuscript. Confirm to save an editable local copy. New projects use `~/Lixity` by default, and the form shows the destination before saving.

If the workspace cannot start, the error dialog can open the log folder. After the app opens, use **Tools → Open Logs Folder**. The [first-session guide](first-look.html) walks through reading your first finding.

This source guide describes **v0.9.1**. Its changes are listed in the source [release notes](https://github.com/mfahsold/lixity/blob/main/docs/releases/v0.9.1.md). The regular install uses the package published on [PyPI](https://pypi.org/project/lixity/). Check `lixity --version` and [Latest on GitHub](https://github.com/mfahsold/lixity/releases/latest) for the published version. Historical 1.x and 3.x tags predate the version reset.

<a id="requirements"></a>

## What does the published browser app need?

Install [uv](https://docs.astral.sh/uv/getting-started/installation/). It installs the published package and supplies managed Python 3.12; no Git or separate Python install is needed. Lixity is on [PyPI](https://pypi.org/project/lixity/); every release also ships a pinned wheel with checksums on [GitHub Releases](https://github.com/mfahsold/lixity/releases), and released versions are archived on Zenodo for citation (concept DOI [10.5281/zenodo.23390297](https://doi.org/10.5281/zenodo.23390297)). Installation needs an internet connection. Analysis runs offline afterward. PDF import has [additional requirements](research-pdf.html#ocr).

**License:**

Lixity is open source under AGPL-3.0-or-later; every writing purpose is covered, including self-publishing. A separate written commercial license exists only for closed-source integrations. Read the

[licensing guide](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)

.

<a id="install"></a>

## Install the published browser app

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

Open a new terminal, then check the installed package and start the app:

```
lixity --version
lixity service start --open
```

If your terminal cannot find `lixity`, check `uv tool list`, run `uv tool update-shell` and open a new terminal. `uv tool dir --bin` shows the executable directory.

<a id="first-dashboard"></a>

## Start the workspace

The default browser address is `http://127.0.0.1:8765/`. A fresh start opens an empty workspace unless you supply a project path or set `LIXITY_DIR`. If Lixity is already running on that port, `start --open` opens the existing workspace.

1. Choose **Open Project** to continue in an existing folder. To copy a manuscript into a new project, choose **Analyze a manuscript** and review the import preview. Confirm the analysis language.

2. Read in **Manuscript**. Choose a paragraph's **… → Paragraph details** for its inspector. The separate **Analysis** switch shows diagnostics across the manuscript.

3. Use **Analysis overview** for chapter comparisons, then **Back to passage** to return.

English is the default analysis language; automatic detection is an explicit choice. The [first-session guide](https://github.com/mfahsold/lixity/blob/main/docs/ONBOARDING.md) explains project selection. For a short example before importing, try the [Warehouse 4 walkthrough](first-look.html). Its public demo cannot import, edit or save.

**Pinned release wheel**

For a reproducible setup, download the wheel from a [published release](https://github.com/mfahsold/lixity/releases/latest) and verify it against that release's `SHA256SUMS`. Replace `VERSION` below with the downloaded file's version and use its actual local path:

```
uv tool install --python 3.12 --managed-python --reinstall-package lixity "./lixity-VERSION-py3-none-any.whl"
```

A pinned wheel keeps its fixed source; replace it explicitly when updating. A prepared source version does not establish that a wheel has been published. See the [installation reference](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#updates-and-removal).

**Development builds instead**

To test unreleased changes, install Git, stop the managed service and replace the installation with:

```
uv tool install --python 3.12 --managed-python --reinstall-package lixity "git+https://github.com/mfahsold/lixity.git@main"
```

`main` changes over time and unreleased commits can share a version number. Verify the installation, run `lixity service restart --open` to restore recorded launch settings and reload your browser.

**Generate an offline HTML report instead**

Download the demo's [Warehouse 4 manuscript](https://github.com/mfahsold/lixity/blob/main/docs/research/examples/harbour-manuscript.md) and save it as `warehouse-4.md`, then run:

```
lixity dashboard warehouse-4.md --language en -o warehouse-4.html
```

Open `warehouse-4.html` in your browser. This generates an analysis report from the same six chapters; the public demo also includes prepared research records. The short synthetic manuscript exercises the workflow, not a reliable literary baseline. Read [how to interpret the results](interpretation.html). English is the default; use `--language de` for German or explicit `--language auto` for detection.

<a id="audio"></a>

## Optional audio export and speech providers

**Audio workflow:** timeline JSON and SSML export need no synthesis engine. Explicit OpenAI-compatible providers use a configured endpoint, model and voice; authentication can reference an environment variable. Imported WAV/FLAC/MP3 inspection stays local, with FFmpeg required for compressed or non-PCM input. Text comparison additionally needs an audio-hash-bound timed transcript. Existing audio settings require a reviewed, backed-up schema upgrade before saving an external profile. See the [audio setup and commands](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md#audio-export-and-external-providers-unreleased).

<a id="zotero"></a>

## Optional Zotero Desktop

For source capture, install Zotero 10 or later on the same computer and enable its local API in Settings → Advanced. Download the attachments you need. Lixity can browse collections and retain selected PDF, text, PNG and JPEG attachments with your permission. Retention permits a local copy, not redistribution or factual acceptance. No cloud account is needed. See [Zotero capture and migration](research-pdf.html#zotero); audio and video remain in Zotero.

<a id="existing-project"></a>

## Open an existing project and research archive

When the app is running, open its home address in a new browser tab and choose **Project actions → Open Project** to keep a second project open on the same port.

With the service stopped, launch directly into a project. Replace `./My Novel` with your folder. Keep the quotes around paths containing spaces.

```
lixity service start "./My Novel" --open
```

To change the startup project of an already running service, restart with the new path:

```
lixity service restart "./My Novel" --open
```

Check the project name after it opens. A separate CLI command, `lixity project --project "./My Novel"`, inspects a folder independently of the browser.

An initialized research archive can also open as a research-only workspace. Load a manuscript when you want to compare it with sources.

<a id="restart"></a>

## Running the server day to day

Use `status` to find the address and state of the managed service. Use `stop` to close it or `restart --open` to reopen it with its saved startup settings.

```
lixity service status
lixity service restart --open
lixity service stop
```

A project you open in the browser belongs to that view for the current session. After a restart, return to the home address reported by the service. Use **Open Project** to reconnect additional projects. For a foreground `lixity serve` session, press `Ctrl+C` in its terminal. See the [service command reference](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md#lixity-service) for startup settings and [the setup reference](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#optional-startup-at-login) for opening at login.

<a id="custom-port"></a>

### Use a different port

If port 8765 is occupied, inspect it with `lixity service status --port 8765`. Reuse the browser address if a managed instance is ready. Choose a free port when you need a separate app process, and use that port for its browser address and every service or diagnostic command.

```
lixity service start "./My Novel" --port 9000 --open
```

This example opens `http://127.0.0.1:9000/`. Any service on port 8765 keeps running.

- Check the address and state with `lixity service status --port 9000`.

- Check installed and running versions with `lixity doctor --port 9000`.

- Reload the service with `lixity service restart --port 9000 --open`.

- Close that instance with `lixity service stop --port 9000`.

<a id="updates"></a>

## Update or remove Lixity

<a id="desktop-updates"></a>

### Update a desktop build

In Lixity, choose **Help → Check for Updates** to review published desktop availability for your system. Quit Lixity before replacing a test build, then open the replacement and check that your project opens. Keep the earlier installer if you are testing an upgrade.

- **macOS.** Open the new DMG and replace **Lixity** in **Applications**.

- **Windows.** Run the new installer of the same type you previously used.

- **Linux.** Upgrade the Debian package with your package manager, or replace the AppImage file and keep it executable.

See the [desktop download section](#desktop) for available installers and the [desktop update guide](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#update-a-desktop-test-build) for verification and rollback. Keep manuscript and research folders in their current locations during an app update.

<a id="browser-updates"></a>

### Update the browser and CLI build

For a PyPI installation, stop each managed instance before upgrading:

```
lixity service stop
uv tool upgrade lixity
lixity --version
lixity service restart --open
```

Use the same port to stop and restart each instance. After restart, reload the browser at the address the service reports. `lixity doctor --port 9000` compares the installed package with the service on port 9000. For an installation pinned to a wheel, install the new release wheel explicitly. See [archive compatibility](https://github.com/mfahsold/lixity/blob/main/docs/research/USAGE.md#storage-lifecycle-and-recovery) when sharing research data with older readers.

For removal, stop all managed instances and disable any login-startup entry you configured, then run `uv tool uninstall lixity`. Manuscript folders and research archives remain. See the [complete update/removal reference](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#updates-and-removal).

<a id="troubleshooting"></a>

## The project exists, but the server cannot open it

The chooser shows folders available to the computer and account running Lixity. A container or service account may have different access from your terminal. Check the project path and permissions, then restart the intended server. Use Open Project to reconnect the original folder rather than importing another copy.

If the browser shows an unexpected project or version, check its address against `lixity service status` and inspect the same port with `lixity doctor`. See [installation troubleshooting](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#troubleshooting).

<a id="python-api"></a>

## Using the Python API?

Install Lixity in your Python project's own environment. The isolated command-line installation does not make `import lixity` available to other Python programs. See the [Python setup commands](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#python-api-project-environment).

Continue with the [full installation reference](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md), [shared pipeline architecture](https://github.com/mfahsold/lixity/blob/main/docs/ARCHITECTURE.md), or [research source workflow](research-pdf.html).

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
