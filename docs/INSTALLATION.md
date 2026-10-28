# Install, verify and update Lixity

Lixity runs on your computer on Linux, macOS and Windows. It is
**open source under AGPL-3.0-or-later**. Install the published package
(`lixity` on [PyPI](https://pypi.org/project/lixity/)) or the pinned release
wheel with the commands below. Any writing purpose is covered;
a separate written commercial license exists only for closed-source
integrations. See [licensing](LICENSING.md) before installation.
Analysis runs offline; downloading Python, the package and dependencies requires
network access. No manuscript upload, account or API key is required.

> **Version scope:** this documentation describes **v0.7.7**. Verify packages at
> [GitHub releases](https://github.com/mfahsold/lixity/releases/latest) and
> [PyPI](https://pypi.org/project/lixity/). The product uses the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the product-number reset; a larger
> historical number does not mean a newer release. Product, JSON response and
> archive schema versions are independent.

## Where Lixity is published

| Channel | Use it for | Notes |
|---|---|---|
| [`lixity` on PyPI](https://pypi.org/project/lixity/) | normal install and upgrades | `uv tool install lixity`; pipx and pip work as well |
| [GitHub Releases](https://github.com/mfahsold/lixity/releases) | pinned, checksum-verified setups | wheel, sdist and `SHA256SUMS`; build attestations via `gh attestation verify` |
| Zenodo | citing a released version | releases are archived automatically; concept DOI `10.5281/zenodo.23390297` (see [`CITATION.cff`](https://github.com/mfahsold/lixity/blob/main/CITATION.cff)) |

Use the isolated **uv tool** installation for the application and CLI. Install
[uv](https://docs.astral.sh/uv/getting-started/installation/) first if needed.
uv installs the published release wheel and supplies managed Python 3.12;
neither Git nor a separate Python installation is needed for this route.
The engine supports Python 3.10 or newer. Python API and editable developer
environments are [separate advanced routes](#python-api-project-environment).

### Install uv if it is not available

Check `uv --version` first. On Windows with WinGet, run in PowerShell:

```powershell
winget install --id=astral-sh.uv -e
```

On macOS with Homebrew already installed:

```sh
brew install uv
```

For Linux, macOS without Homebrew, or Windows without WinGet, use the
[official uv installation instructions](https://docs.astral.sh/uv/getting-started/installation/).
Open a new terminal after installation and check `uv --version` before continuing.
These install uv, not Lixity; the next command installs the application.

## CLI: current release

These commands work in a terminal, including Windows PowerShell:

```sh
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Open a new terminal, then verify and start the app:

```sh
lixity --version
lixity doctor
lixity service start --open
```

See the [release notes](releases/v0.7.7.md)
for changes and compatibility. `uv tool update-shell` configures new terminals;
it does not change the terminal already open.

If `lixity` is not found, run `uv tool list` to confirm that Lixity is installed,
then `uv tool update-shell` and open a new terminal. `uv tool dir --bin` reports
the executable directory. Reinstalling the app does not repair an old terminal's
PATH. Once the command resolves, `lixity doctor` checks the installation/service;
it does not certify linguistic accuracy or source truth.

## First useful result

**Since v0.7.6:** use one regular app address. Opening a project
creates an independent view under that same address; existing tabs keep their
project. **App and audio** lists open views and verifies each actual audio worker.
A view URL is valid only while this server runs; after restart, reopen the project
from the app home. Custom ports remain available for explicit development instances.

The app opens `http://127.0.0.1:8765/` with an empty workspace; it does not
search your terminal's current folder. Choose **Open Project** for an existing
folder or **Analyze a manuscript** to preview a copy into a new project.
Confirm the manuscript language, then read a passage in **Manuscript**.
Use **Analysis** for diagnostics or **… → Values** for one paragraph.
[Onboarding](ONBOARDING.md) explains the next steps.

Check, stop and return to the managed workspace with:

```sh
lixity service status
lixity service stop
lixity service start --open
```

Open your project again, or supply its path while the service is stopped:
`lixity service start --open ./my-novel`. For the full saved launch settings,
use `lixity service restart --open`; it restores the startup project, not a later
browser selection. [Service lifecycle](#running-the-server) covers custom ports,
logs and startup at login.

For a terminal result instead:

```sh
lixity analyze manuscript.md --language en
```

English is the default; `--language auto` explicitly requests detection.
Short text may leave measurements unavailable. [Usage](USAGE.md) owns exports,
configuration and PDF behavior. Built-in analysis runs locally. Optional
[map backgrounds](research/USAGE.md#keep-places-and-journeys-in-a-dossier) and
[OCR workers](research/OCR_INTEGRATION.md) have separate network/data boundaries.

### Pinned release and installation scope

<details>
<summary>Reproducible wheel installation and Python environments</summary>

For a checksum-verified setup, download the wheel from the chosen
[published release](https://github.com/mfahsold/lixity/releases/latest) and verify
it against that release's `SHA256SUMS`. Then install the downloaded file, replacing
`VERSION` below with its actual version and using the file's real local path.
A prepared version in this checkout does not establish that a wheel is published:

```sh
uv tool install --python 3.12 --managed-python --reinstall-package lixity "./lixity-VERSION-py3-none-any.whl"
```

`uv tool list` shows the installed source. This uses uv's
[isolated tool environment](https://docs.astral.sh/uv/concepts/tools/) and
[managed Python](https://docs.astral.sh/uv/concepts/python-versions/#requiring-or-disabling-managed-python-versions).
uv accepts [HTTPS wheels](https://docs.astral.sh/uv/concepts/projects/dependencies/#url).
A tool installation does not make `import lixity` available in another Python
environment; use the [Python project route](#python-api-project-environment).

</details>

### Optional research prerequisites

<details>
<summary>PDF/OCR and Zotero setup for research</summary>

The research workspace is included. Text and Markdown sources need
no OCR setup. Search needs SQLite with FTS5 support. Text PDFs need Poppler;
image-only scans need locally installed Tesseract or a configured OCR worker. See
[PDF and OCR setup](#server-environment-and-project-access).

For Zotero capture, install Zotero 10 or later on the same computer and enable
its local API in Settings → Advanced. Lixity reads `127.0.0.1:23119`; it does
not install or launch Zotero, modify its database or configure synchronization.
No cloud account is needed.
See the [Zotero setup and migration reference](research/USAGE.md#zotero-desktop-bridge-since-v1190).
Back up existing archives before creating v3 captures and use compatible versions
for all readers and writers. Installing Lixity does not download an OCR model.

</details>

### Optional Qwen audio worker

Version 0.7.7 supports `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` and also
supports separate VoiceDesign and reference-based Base checkpoints. The application and
CLI share its project profiles and rendering controls. Audio runtime dependencies
are optional: use a separate Python 3.12 environment with `qwen-tts`, a compatible
PyTorch build and a complete local checkpoint, including its speech tokenizer.
The core application install does not install or download model weights.

Run the loopback-only worker explicitly on this computer, or on a configured
Jetson reached through an authenticated SSH forward. Neither target is an
automatic fallback. Start with a short preview and verify actual synthesis and
memory headroom; model size and machine memory do not establish throughput.
[Read-aloud setup and limits](USAGE.md#lixity-read-aloud) covers CPU/CUDA placement,
the fixed ports, private segment reuse and worker commands. Optional worker
`--attention auto|eager|sdpa` is an explicit machine setting; compare actual
workloads before choosing an override, without assuming a speed improvement.
In 0.7.7, new audio profiles default to a 1.2 playback tempo factor;
FFmpeg is required on the Lixity host for any factor other than 1.0 and for MP3.
The factor is applied after synthesis, not by the Qwen model.

Piper support has been removed. Existing Piper profiles require an explicit
`audio-migrate` dry run and reviewed apply with a new backup outside the project.
The migration preserves source files and never assumes an equivalent Qwen timbre
or precise speed; see the same [read-aloud guide](USAGE.md#lixity-read-aloud).

### Development builds instead

<details>
<summary>Follow unreleased source changes</summary>

To test unreleased source changes, install
[Git](https://git-scm.com/downloads), then use this **instead**:

```sh
uv tool install --python 3.12 --managed-python --reinstall-package lixity "git+https://github.com/mfahsold/lixity.git@main"
```

`main` changes over time; an unreleased checkout can differ from the published
release and demo. Review
[release notes](https://github.com/mfahsold/lixity/releases) before switching.
Stop the managed service before replacing its installation, verify the new
version, then run `lixity service restart --open` to reuse the recorded launch
settings. A checkout, installed package and running service can contain different
code even when `--version` matches: unreleased commits retain the release number.
Reload browser tabs after the restart.

</details>

### Updates and removal

Version 0.3.0 reset the product number to reflect development maturity before
1.0 while retaining historical tags and features. For a pinned installation,
choose the wheel under [CLI: current release](#cli-current-release), not the
numerically largest historical tag. Product and archive schema versions are
independent: back up research before an upgrade and inspect the
[reader/writer compatibility limits](research/USAGE.md#limits). Installing new
files does not restart a running workspace.

Before stopping the app, check **App and audio** for active or queued audio
jobs and let them finish or cancel them deliberately. Separate CLI renders are
not shown there. Note the startup project and port, and preserve any separately
installed tool dependencies or language models when replacing the installation.
For a uv tool, `uv tool list --show-with --show-extras` shows recorded additional
requirements. The app and an optional audio worker are separate services;
updating or restarting one does not update the other.

When upgrading from a historical build before v2.4.0, stop its instance through the
original foreground terminal (Ctrl+C), checkout launcher or configured OS
manager before replacing the installation. That version has no `service`
command, and the new controller deliberately does not adopt its process.

```sh
lixity service stop
uv tool upgrade lixity
lixity --version
lixity service restart --open
```

`uv tool upgrade lixity` selects the highest compatible, non-yanked version
available under the tool's PyPI constraints, not the most recently published by
date. A tool installed from a pinned wheel keeps that fixed URL — replace it
with `uv tool install --reinstall-package lixity` and the new wheel URL.
`--reinstall-package lixity` refreshes that package without forcing ownership
of another installer's entrypoint. See the official
[tool update reference](https://docs.astral.sh/uv/reference/cli/#uv-tool-install).
`restart` reuses recorded launch settings even after `stop`. Plain `start` opens
an empty workspace unless you provide a project; it does not reuse those settings.
A project selected later in the browser is not the recorded startup project. Pass
that project explicitly to `restart` when you want it to become the launch default.
To roll back, choose and verify the intended older release wheel and its
checksum, check archive compatibility, and restore a compatible backup if needed
before using that version. Reopen projects and verify the installed version and
service after the restart; do not assume older code can read newer archives.

Before updates or removal, stop each managed instance using its port, for example
`lixity service stop --port 9000` for a custom-port instance. Before removal,
disable any login-startup entry you configured under systemd, launchd or Task
Scheduler. Then remove only Lixity:

```sh
lixity service stop
uv tool uninstall lixity
```

This removes the isolated tool installation, not your manuscript folders or
research archives. Keep shared uv and Python installations used by other tools.
Externally configured startup entries use their [own manager](#optional-startup-at-login).

If a terminal reports an older version than your checkout, compare `lixity
--version` with `.venv/bin/lixity --version` (`.venv\Scripts\lixity.exe --version`
on Windows). They may be separate installations. Use `command -v lixity` on
Linux/macOS or `Get-Command lixity` in PowerShell, then inspect `uv tool list`.
A non-editable tool installed from a local folder is a copy: changing the
folder does not update the installed tool. Reinstall the chosen release or
development source explicitly, verify its version, and restart its service.

<details>
<summary>Alternative for existing pipx users</summary>

If you already use pipx, install the published package with `pipx install lixity`
(or the pinned wheel URL for an exact release), then use `pipx ensurepath` if
necessary. Keep using that installer to replace or
remove its installation rather than overwriting its executable with uv.

</details>

## Running the server

Use the packaged service controller from any terminal; no source checkout is
needed. It starts the same Python installation that provides your `lixity`
command and checks its managed instance before reporting readiness.

```sh
lixity service start --open
lixity service status
lixity service restart
lixity service stop
```

The default address is `http://127.0.0.1:8765/`. Start uses an empty workspace
in an application-owned working directory, rather than discovering a manuscript
in your terminal's current folder. An explicit `LIXITY_DIR` also chooses a startup
project. With the service stopped, you can choose an
explicit project and another port:

```sh
lixity service start --open --port 9000 ./my-novel
lixity service status --port 9000
lixity service stop --port 9000
```

Linux uses a user systemd manager when available; other supported environments
use the detached-process backend. Login startup remains a separate explicit
choice. The controller manages instances it created, not arbitrary foreground
servers or external startup units. If another process owns the port, identify
that instance or choose another port; do not assume the controller owns it.

Project views on one server have independent selected projects. **Open Project**
creates a view; CLI analysis, research and build commands do not change it.
`start` uses fresh launch settings. `restart` uses recorded launch settings plus
explicit overrides, even after a stop; a project selected later in the browser
does not replace the startup project. After updates or OCR environment
changes, restart the appropriate managed instance; a browser reload alone does
not load new code. Supply OCR variables in the new start/restart environment;
their values are not saved as launch settings.

Reloading the dashboard validates the selected
manuscript before serving saved analysis. If it is missing/unreadable or a rebuild
fails, the app retains its last successful view with an **Analysis freshness**
notice and **Retry refresh**. Restore the file/access or correct the input/settings,
then retry; the notice clears after successful validation. That saved view is not
evidence that the source is current. With no prior successful snapshot, the usual
missing-file view remains. This request-time check does not watch external
configuration changes or replace a service restart after installing new code.

Since v3.0.1, foreground `serve` and managed start/restart accept
`--min-chapters N` (an integer of at least 2, default 2). Restart retains the
saved threshold unless overridden; see the [service command reference](USAGE.md#lixity-service).

<details>
<summary>Backend selection, stored launch settings and logs</summary>

`--backend auto` prefers an available Linux user systemd manager and otherwise
uses a detached process. `--backend process` explicitly chooses the latter;
`--backend systemd` fails when no usable user manager exists. These managed units
are transient and do not enable startup at login. Backend selection applies to
each invocation and is not saved: repeat `--backend process` on restart to keep
that choice; otherwise restart uses `auto`. `lixity service status --json`
reports readiness, installed/running versions and backend without log paths; see the
[command contract](USAGE.md#lixity-service) for states and exit codes.
Since v0.7.4, its `lixity-service-status/1` response exits 0 for a known stopped,
starting or unmanaged-port busy state as well as a running instance. Check
`running` for readiness; unknown state exits 1 with `running: null`. Human
stopped status still exits 1; other lifecycle JSON is unchanged.
Since v0.7.3, status reads existing storage without creating
folders, repairing permissions or waiting for a lifecycle write. Unreadable or
changing state remains uncertain; it does not trigger an alternate runtime path.

Use `lixity doctor --json` (or `--port PORT` for another instance) to compare the
imported CLI, distribution and running-service versions, module/interpreter
locations and JSON contract versions. It reads no manuscripts or project
configuration and performs no repair, installation or restart. A healthy stopped
service is valid; mismatches or unavailable metadata/status exit 1. See
[diagnostic output](USAGE.md#lixity-doctor) before acting on its findings.

Saved launch settings and `service-PORT.log` live separately from the package:

| Platform | Default state folder |
| --- | --- |
| Linux | `$XDG_STATE_HOME/lixity/service`, or `~/.local/state/lixity/service` |
| macOS | `~/Library/Application Support/lixity/service` |
| Windows | `%LOCALAPPDATA%\lixity\service` |

Runtime records use `$XDG_RUNTIME_DIR/lixity-service` when set, otherwise
`runtime/lixity-service` inside that state folder. `LIXITY_SERVICE_STATE_DIR`
and `LIXITY_SERVICE_RUNTIME_DIR` explicitly override these locations. Stop
retains launch settings and logs; uv uninstall removes the tool environment,
leaving application state and user imports intact. There is no cleanup command
that deletes project storage.

#### Logs

Every diagnostic goes through one logging tree (`lixity.*`) with a single UTC
line format and standard levels; stdout stays the result channel of the CLI,
and the service appends the process' stderr to `service-PORT.log`. `lixity
service status` prints that path, so `tail -f` follows a running server.

| Setting | Effect |
| --- | --- |
| `--debug` (start/restart) | DEBUG level; request lines and error details |
| `LIXITY_DEBUG=1` | Same as `--debug` for the foreground server |
| `LIXITY_LOG_LEVEL` | Explicit level name (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |

`service-PORT.log` is bounded: starting the service rotates an oversized log
to `service-PORT.log.1` … `.3` (oldest dropped). Request logs never contain
query strings, so context tokens and selectors stay out of the file; log
records and runtime files never contain manuscript text.

Reading-website exports log a random export ID, preparation size/time and socket
write outcome at the default INFO level; disconnected clients produce a WARNING.
The native browser reports response-read, ZIP-check or download-start failures
back to the same local service, using only that ID, a fixed stage and an error
class. Neither exception messages, filenames, project tokens nor document bytes
are included in those receipts. A `body_written` line means the server wrote the
response, not that the browser saved it; `download_started` is a browser receipt,
not proof that a file was saved. If the service is unreachable, receipt delivery
can also fail; the shared browser console logger records that failure.
For `response_read`/`AbortError` after `body_written`, also check the browser's
temporary storage and user quota: a quota can be exhausted despite free space
reported by `df`. That observation alone does not prove an invalid ZIP.

</details>

For a foreground server, including development and embedding use, keep the
existing command and stop it with Ctrl+C:

```sh
lixity serve --no-project --open
```

`lixity service stop` does not stop an unrelated foreground `serve` process.
The same CLI is available as `python -m lixity` in an environment containing
Lixity. From a source checkout, `scripts/lixity-start.sh`,
`scripts/lixity-start.ps1` and `make serve` / `make stop` delegate to this shared
controller; they are compatibility entrypoints, not separate lifecycle engines.

### Optional startup at login

<details>
<summary>Explicit Linux, macOS and Windows startup managers</summary>

Use these advanced options only when you want startup at login. They do not
replace the primary service workflow. A unit or task you configure independently
is managed and disabled with its own OS manager before removal or replacement.
The template commands assume a source checkout, or that you saved the linked
templates in a `scripts/` folder. Stop the managed instance on the chosen port
before enabling a separate login-startup entry.

### Auto-start on login — Linux (systemd user service)

Optional: use the [systemd template](https://github.com/mfahsold/lixity/blob/main/scripts/lixity.service)
to start at login. Edit its executable path and project directory before enabling it:

```sh
mkdir -p ~/.config/systemd/user
cp scripts/lixity.service ~/.config/systemd/user/lixity.service

# Edit ExecStart to point to your lixity binary (check: which lixity)
nano ~/.config/systemd/user/lixity.service

systemctl --user daemon-reload
systemctl --user enable --now lixity    # enable + start immediately

# Management
systemctl --user status  lixity
systemctl --user restart lixity
journalctl --user -u lixity -f          # live log

# Disable login startup before removing the installation
systemctl --user disable --now lixity
```

The template explains port changes and service options. If you deliberately
need it running without a login session, use `loginctl enable-linger $USER`.
The service must be able to write to its project folder.

### Auto-start on login — macOS (launchd agent)

Optional: edit the [launchd template](https://github.com/mfahsold/lixity/blob/main/scripts/lixity.plist)
to point to your executable. To preload a project, replace `--no-project` in its
ProgramArguments with the explicit project path, then register it:

```sh
# Edit the plist: set the correct path to your lixity binary (check: which lixity)
# and choose an explicit startup project only if wanted.
nano scripts/lixity.plist

cp scripts/lixity.plist ~/Library/LaunchAgents/com.lixity.serve.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lixity.serve.plist

# Management
launchctl kickstart -k gui/$(id -u)/com.lixity.serve   # restart
launchctl bootout gui/$(id -u)/com.lixity.serve        # stop and unload
tail -f /tmp/lixity-stdout.log                        # live log

# Disable auto-start
launchctl bootout gui/$(id -u)/com.lixity.serve
launchctl disable gui/$(id -u)/com.lixity.serve
```

### Auto-start on login — Windows (Task Scheduler)

Optional: register the installed foreground server in Task Scheduler to start
at login. Use its executable directly; no PowerShell launcher or execution-policy
change is needed:

```powershell
$binary    = (Get-Command lixity -CommandType Application).Source
$action    = New-ScheduledTaskAction -Execute $binary `
              -Argument "serve --no-project --host 127.0.0.1 --port 8765"
$trigger   = New-ScheduledTaskTrigger -AtLogOn -User $env:USERNAME
$settings  = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName "Lixity Dashboard" `
    -Action $action -Trigger $trigger -Settings $settings -RunLevel Limited
```

Manage it from Task Scheduler GUI (`taskschd.msc`) or PowerShell:

```powershell
Start-ScheduledTask  -TaskName "Lixity Dashboard"
Stop-ScheduledTask   -TaskName "Lixity Dashboard"
Unregister-ScheduledTask -TaskName "Lixity Dashboard" -Confirm:$false  # remove
```

</details>

### After a computer restart (quick reference)

Run `lixity service start --open` again, or use your explicitly configured
login-startup manager. Your project remains in its folder;
reinstallation or reimport is unnecessary. Reapply any OCR environment settings,
which are not saved in project settings. Start Zotero for new captures;
retained evidence stays readable while it is closed.

## Python API: project environment

These advanced development installs follow `main` and require Git and an existing
Python 3.10+. For a published version, use a tag that exists in GitHub releases.

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install "git+https://github.com/mfahsold/lixity.git@main"
.venv/bin/python -m pip check
.venv/bin/python -c "import lixity; print(lixity.__version__)"
```

Windows PowerShell (no activation or execution-policy change needed):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "git+https://github.com/mfahsold/lixity.git@main"
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -c "import lixity; print(lixity.__version__)"
```

Use the same environment's `python -m pip install --upgrade` command and
explicit source URL to update. Do not update an unrelated global Python.

## Editable checkout

```sh
git clone https://github.com/mfahsold/lixity.git
cd lixity
make install-dev
make check
```

On Linux/macOS, `make install` creates `.venv` without development tools;
both installation targets check dependency compatibility and print the version.
Neither changes the global Python installation. You can select another
environment using `VENV=/path/to/environment` and interpreter using `PYTHON=python3.12`.

Without make, create the environment as above and use its Python to run
`-m pip install -e ".[dev]"`, then `-m pip check` and `-m pytest -W error -q -p no:asyncio`.
Keep an editable engine checkout separate from manuscript folders; reuse the
package rather than copying engine code into every book project.

For contributors, `make check` is the everyday local source check and
`make browser` covers rendered changes. Before preparing a release, use
`make release-check RELEASE_TAG=vX.Y.Z`, plus `make browser-full` for UI changes.
Tagged releases first run the full source and browser gates, then build and
attest packages and deploy Pages from the published tag. The research-platform
workflow remains a manual cross-platform check; manual Pages dispatch is a
deliberate preview. See [release preparation](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#preparing-a-release)
for the gates and recovery. Pushing `main` alone updates neither the deployed
site nor a local installation.

Installing an update changes the installed package, not another checkout or an
already running process; restart the managed service to load it. A **Reading
website** / `lixity export-site` output is a separate fixed project snapshot:
regenerate it deliberately after source/archive changes. It neither publishes
to Pages nor follows later edits automatically.

A local Linux check does not replace Windows/macOS verification for
platform-sensitive changes. See
[contributor checks](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup)
for the canonical paths and focused/manual-full platform options.

## Read documentation offline

Installed command help and schema discovery work without a network connection:
use `lixity COMMAND --help`, `lixity research COMMAND --help`,
`lixity about --json` and `lixity research schema`. They describe the code in
that installation; they do not require the workspace service.

For longer guides, retain a matching source checkout and open `docs/USAGE.md`,
`docs/research/USAGE.md` or the generated `docs/llms-full.txt` in a local text or
Markdown reader. The bundle combines the references; it is not a rendered
documentation website. Package installations do not include these guides, and
there is no `lixity docs --serve` command. Contributors can preview the approved
Pages tree using the existing
[documentation preview workflow](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#updating-documentation-and-pages).
External links and public-site analytics remain separate from offline reading.

## Troubleshooting

| Symptom | Action |
| --- | --- |
| `uv` not found | Install uv and reopen the terminal. Git is needed only for source installs. |
| `lixity` not found | Use `uv tool update-shell`, or the chosen venv's executable directly. |
| `externally-managed-environment` | Use `uv tool` or a venv; do not use `--break-system-packages`. |
| Project settings ignored | Check `lixity.toml` syntax and the selected project path; explicit CLI flags take precedence. |
| Wrong version or old controls after update | Check `uv tool list` and `command -v lixity` (PowerShell: `Get-Command lixity`), then stop the old server and restart on the same port. Check that the browser uses that address. |
| Dependency build error | Try a supported CPython version with binary wheels, e.g. 3.12; retain the full installer error. |
| HTML lacks project or research actions | A standalone export is read-only. Use `lixity service start --open` for the local workspace and PDF/NDA download actions. |
| Analysis freshness notice remains | Read the missing/unreadable/rebuild message, restore source access or correct invalid input/settings, then use **Retry refresh**. Saved measurements retain their earlier source identity until validation succeeds. |

## Optional shell completion

Bash:

```sh
mkdir -p ~/.local/share/bash-completion/completions
lixity completion bash > ~/.local/share/bash-completion/completions/lixity
```

For Zsh, generate `_lixity` in a **user-writable directory on `$fpath`** and
initialize completion with `autoload -Uz compinit; compinit`. Do not assume
the first existing `$fpath` directory is writable.

See the [usage reference](USAGE.md), [architecture](ARCHITECTURE.md) and
[contributor guide](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md) for the next steps.

## Server environment and project access

The folder browser sees files available to the server process. A service account,
container or sandbox may have different access from your terminal. If a project
cannot be opened, check the process user, folder permissions and mounted paths.
Use **Open Project** to reconnect the original archive rather than importing
another copy. Keep private project data outside the engine checkout.

For PDF import, make `pdftotext` and `pdftoppm` available in that same environment.
Debian/Ubuntu package: `poppler-utils`; Homebrew package: `poppler`.
Run `lixity research ocr-status` to check configuration. Image-only scans need
local Tesseract and selected language data, or a configured `LIXITY_OCR_WORKER`.
Set `LIXITY_OCR_BACKEND=tesseract` for local recognition. `deu+eng` is an example
German/English language selection; choose the actual scan languages in
`LIXITY_OCR_LANGUAGES`. Restart the server manually with those environment values.

Since 2.0.0, **Research → Set up OCR and Zotero** offers an explicit
metadata-only check even before opening a project. It installs nothing and writes
no configuration. A reachable Zotero API does not establish library, collection
or attachment access; those remain separate explicit browse actions.
See [the extraction contract](research/USAGE.md#self-hosted-pdf-and-ocr-extraction).
The [Unlimited-OCR integration guide](research/OCR_INTEGRATION.md) describes the
external-worker boundary and the limited historical CPU experiment. Upstream
`infer.py` cannot be used directly as a `LIXITY_OCR_WORKER` executable.

The [browser installation guide](https://mfahsold.github.io/lixity/guides/installation.html)
provides a synthetic first-dashboard example and links to interpretation and
source/PDF workflows.
