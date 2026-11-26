![](../assets/mark.svg)

# Install Lixity and open your manuscript

Choose a desktop preview for your computer or install the published browser app and CLI from PyPI. The desktop app includes its runtime. Built-in manuscript analysis runs on your computer with either installation.

Updated 26 November 2026

<a id="desktop"></a>

## Desktop downloads

These v0.9.3 desktop preview builds are available as direct downloads without a GitHub account. macOS builds use ad hoc signing, and Windows builds are unsigned. For a PyPI installation, use the [published local browser app and CLI](#install).

<a id="macos"></a>

### Mac

macOS 12 or later

[**Mac with Apple silicon**Preview · Lixity_0.9.3_aarch64.dmg · 27.3 MiB](https://github.com/mfahsold/lixity/releases/download/desktop-preview-v0.9.3/Lixity_0.9.3_aarch64.dmg)

[**Mac with an Intel processor**Preview · Lixity_0.9.3_x64.dmg · 36.7 MiB](https://github.com/mfahsold/lixity/releases/download/desktop-preview-v0.9.3/Lixity_0.9.3_x64.dmg)

[Mac setup steps](#macos-setup)

<a id="windows"></a>

### Windows

64-bit Intel or AMD PCs

[**Windows Setup**Preview · Lixity_0.9.3_x64-setup.exe · 14.8 MiB](https://github.com/mfahsold/lixity/releases/download/desktop-preview-v0.9.3/Lixity_0.9.3_x64-setup.exe)

[**Windows MSI (German)**Preview · Lixity_0.9.3_x64_de-DE.msi · 21.2 MiB](https://github.com/mfahsold/lixity/releases/download/desktop-preview-v0.9.3/Lixity_0.9.3_x64_de-DE.msi)

[**Windows MSI (English)**Preview · Lixity_0.9.3_x64_en-US.msi · 21.2 MiB](https://github.com/mfahsold/lixity/releases/download/desktop-preview-v0.9.3/Lixity_0.9.3_x64_en-US.msi)

[Windows setup steps](#windows-setup)

<a id="linux"></a>

### Linux

64-bit Intel or AMD PCs

[**Ubuntu and Debian**Preview · Lixity_0.9.3_amd64.deb · 46.2 MiB](https://github.com/mfahsold/lixity/releases/download/desktop-preview-v0.9.3/Lixity_0.9.3_amd64.deb)

[**Linux AppImage**Preview · Lixity_0.9.3_amd64.AppImage · 117.8 MiB](https://github.com/mfahsold/lixity/releases/download/desktop-preview-v0.9.3/Lixity_0.9.3_amd64.AppImage)

[Linux setup steps](#linux-setup)

<a id="installer-check-heading"></a>

### Check the installer

Choose the downloaded installer. If it came in a ZIP, extract it first. Your browser checks the file on this computer.

Select the downloaded installer

[Preview release desktop-preview-v0.9.3](https://github.com/mfahsold/lixity/releases/tag/desktop-preview-v0.9.3) · [Check SHA-256 sums](https://github.com/mfahsold/lixity/releases/download/desktop-preview-v0.9.3/SHA256SUMS-desktop.txt) · [Source commit](https://github.com/mfahsold/lixity/commit/b3bfee6f83498c10d6fcb8eb3702f278ba761e48) · [Published browser app and CLI](#install).

Choose a download that matches your operating system and processor. Verify the installer before opening it.

<a id="macos-setup"></a>

### Install on macOS

Desktop builds require macOS 12 or later.

1. Open **About This Mac** from the Apple menu. Choose the Apple silicon DMG if you see an Apple chip, or the Intel DMG if you see an Intel processor.

2. If you downloaded a ZIP archive, extract the DMG first. Verify the DMG, open it in Finder and drag **Lixity.app** into **Applications**. The preview disk image has a **Start Here** guide.

3. When the copy is complete, eject the disk image and open **Lixity** from **Applications**.

Test builds use ad hoc signing. If macOS shows a security alert, check its wording and follow the [macOS installation and security guidance](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#macos-desktop-dmg).

<a id="windows-setup"></a>

### Install on Windows

1. Check **Settings → System → About → System type**. The current desktop builds target x64 PCs.

2. If you downloaded a ZIP archive, extract the installer first. Verify the setup `.exe` and open it to install for your account. Use the English or German MSI for deployment testing. GitHub Actions ZIPs include **Start Here - Windows.html**.

3. Open **Lixity** from the Start menu. On systems missing WebView2, setup needs internet access to get the Microsoft runtime.

Windows may flag an unsigned test build as an unknown publisher or unrecognized app. If system policy blocks installation, use the [published browser app and CLI](#install). See the [Windows verification and installation steps](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#windows-desktop-test) and [Microsoft’s WebView2 installation options](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution).

<a id="linux-setup"></a>

### Install on Linux

1. Check the system information in your desktop settings for an x86-64 or AMD64 system. Verify the downloaded `.deb` or `.AppImage`. If it came in a ZIP, extract it before verification. GitHub Actions ZIPs include **Start Here - Linux.html**.

2. On Debian or Ubuntu, open the verified `.deb` with your package installer and start **Lixity** from the applications menu. To run the verified `.AppImage` from its folder, allow it to execute in the file's properties and open it.

For Linux testing, use a build whose workflow passed the installed-app runtime check. If an earlier DEB reports a missing ALSA library, see the [Linux troubleshooting steps](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#linux-desktop-test). For an AppImage FUSE error, follow the [instructions for your distribution](https://docs.appimage.org/user-guide/troubleshooting/fuse.html).

**SHA-256 verification instructions**

Compare your installer with the checksum for its filename. Use the linked SHA-256 list for direct downloads, or the checksum file included in your GitHub Actions ZIP. See the command for [macOS](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#macos-desktop-dmg), [Windows](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#windows-desktop-test), or [Linux](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#linux-desktop-test).

<a id="desktop-first-launch"></a>

### First launch

1. Choose **Try the example offline** to preview the bundled Warehouse 4 manuscript in English. Confirm the destination and choose **Import and analyze manuscript** to create an editable copy. The default project directory is `~/Lixity`.

2. In **Manuscript**, open a marked sentence to see what Lixity counted. Return to the passage to keep reading, or choose **Write** to try an edit. [Follow a marked passage in the public demo](first-look.html#passage)

3. When you are ready to work on your own text, choose **Open a project folder**, **Import a manuscript**, or **Start writing**. The import preview shows the new destination and analysis language before you confirm.

If startup fails, the error dialog can open the log folder. After the app opens, choose **Tools → Open Logs Folder**. You can also find it at the [log location for your operating system](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#find-the-desktop-logs).

This source guide describes **v0.9.3**. See the [release notes](https://github.com/mfahsold/lixity/blob/main/docs/releases/v0.9.3.md) for the changes in that version. The browser app and CLI below install from [PyPI](https://pypi.org/project/lixity/). Use `lixity --version` to check your installation and [Latest on GitHub](https://github.com/mfahsold/lixity/releases/latest) to find the published release. Historical 1.x and 3.x tags predate the version reset.

**Published local browser app and CLI (no GitHub account required)**

<a id="requirements"></a>

## Install with a Python environment

If you already have Python 3.10 or later, you can install Lixity in a virtual environment. For direct analysis commands, see the [CLI quick start](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md#quick-start).

```
python -m venv .venv
# Activate the environment for your shell, then run:
python -m pip install lixity
lixity --version
lixity doctor
```

Both the virtual environment and uv setup download the published package. After installation, built-in analysis runs offline. The release wheel and checksums are available on [GitHub Releases](https://github.com/mfahsold/lixity/releases/latest). See the [requirements for PDF import](research-pdf.html#ocr) if you work with scanned sources.

Lixity is open source under AGPL-3.0-or-later. You can write and self-publish with it. A separate commercial license is available for closed-source integrations. [Licensing guide](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)

## Install with uv

Use [uv](https://docs.astral.sh/uv/getting-started/installation/) to install Lixity as a command-line tool with managed Python 3.12.

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
```

After installation succeeds, start Lixity from the same terminal:

```
uv tool run lixity service start --open
```

To run `lixity` directly in later terminals, run `uv tool update-shell` once and open a new terminal. Use `uv tool run lixity --version` to check your installed version.

<a id="first-dashboard"></a>

## Start the workspace

The default browser address is `http://127.0.0.1:8765/`. Starting without a project path or `LIXITY_DIR` opens an empty workspace. If Lixity is already running on that port, `start --open` opens the existing workspace.

1. Choose **Open a project folder** to continue in an existing folder. To copy a manuscript into a new project, choose **Import a manuscript** and review the import preview. Confirm the analysis language.

2. Read one paragraph in **Manuscript**. Turn on **Analysis**, choose **Sentence length**, then choose **Text matches** to read a counted sentence. [First session](https://github.com/mfahsold/lixity/blob/main/docs/ONBOARDING.md#read-and-explore)

3. Use **Analysis overview** for chapter comparisons, then **Back to passage** to return.

English is the default analysis language. Choose automatic detection explicitly when you need it. The [Warehouse 4 walkthrough](first-look.html) shows the same reading task in a fixed public example.

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

`main` changes over time and unreleased commits can share a version number. Verify the installation, run `uv tool run lixity service restart --open` to restore recorded launch settings and reload your browser.

**Generate an offline HTML report instead**

Download the demo's [Warehouse 4 manuscript](https://github.com/mfahsold/lixity/blob/main/docs/research/examples/harbour-manuscript.md) and save it as `warehouse-4.md`, then run:

```
lixity dashboard warehouse-4.md --language en -o warehouse-4.html
```

Open `warehouse-4.html` in your browser. This generates an analysis report from the same six chapters; the public demo also includes prepared research records. The short synthetic manuscript exercises the workflow, not a reliable literary baseline. Read [how to interpret the results](interpretation.html). English is the default; use `--language de` for German or explicit `--language auto` for detection.

<a id="audio"></a>

## Optional speech and audio tools

Use the teleprompter to rehearse a passage, or export its timing and delivery cues as JSON or SSML. To generate speech, configure a local engine or a compatible service, then listen to a short passage before rendering a chapter. The configured service receives the spoken text. The audio manual covers author voice recordings, model setup and the external provider configuration. [Get started with audio](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md#getting-started)

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

In Lixity, choose **Help → Check for Updates** to check for a published desktop update for your system. Before replacing a preview, save your work, finish any audio jobs and close Lixity. Verify the replacement installer, then check that your project opens in the new build. Keep the previous installer for rollback.

- **macOS.** Open the new DMG and replace **Lixity** in **Applications**.

- **Windows.** Run the new installer of the same type you previously used.

- **Linux.** Upgrade the Debian package with your package manager, or replace the AppImage file and keep it executable.

See the [desktop download section](#desktop) for available installers and the [desktop update guide](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#update-a-desktop-test-build) for verification and rollback. Keep manuscript and research folders in their current locations during an app update.

**Update the browser and CLI build**

For a PyPI installation, stop each managed instance before upgrading:

```
uv tool run lixity service stop
uv tool upgrade lixity
uv tool run lixity --version
uv tool run lixity service restart --open
```

Use the same port to stop and restart each instance. After restart, reload the browser at the address the service reports. `uv tool run lixity doctor --port 9000` compares the installed package with the service on port 9000. For an installation pinned to a wheel, install the new release wheel explicitly. See [archive compatibility](https://github.com/mfahsold/lixity/blob/main/docs/research/USAGE.md#storage-lifecycle-and-recovery) when sharing research data with older readers.

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
