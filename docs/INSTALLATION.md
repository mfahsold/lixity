# Install, verify and update Lixity

Lixity runs on your computer on Linux, macOS and Windows. It is
**open source under AGPL-3.0-or-later**. Install it from GitHub using the
commands below; it is not distributed on PyPI. Any writing purpose is covered;
a separate written commercial license exists only for closed-source
integrations. See [licensing](LICENSING.md) before installation.
Analysis runs offline; downloading Python, the package and dependencies requires
network access. No manuscript upload, account or API key is required.

Use the isolated **uv tool** installation for the application and CLI. Install
[uv](https://docs.astral.sh/uv/getting-started/installation/) first if needed.
uv installs the published release wheel and supplies managed Python 3.12;
neither Git nor a separate Python installation is needed for this route.
The engine supports Python 3.10 or newer. Python API and editable developer
environments are [separate advanced routes](#python-api-project-environment).

## CLI: current release

These commands work in a terminal, including Windows PowerShell:

```sh
uv tool install --python 3.12 --managed-python --reinstall-package lixity "https://github.com/mfahsold/lixity/releases/download/v0.4.0/lixity-0.4.0-py3-none-any.whl"
uv tool update-shell
```

Open a new terminal, then verify and start the app:

```sh
lixity --version
lixity service start --open
```

The current release is **v0.4.0**. This command selects a fixed release so that
reinstalling it uses the same wheel. Read the [release notes](releases/v0.4.0.md)
for changes and compatibility information.

`uv tool update-shell` configures shell integration once; it does not change an
already open terminal. **Open Project** reconnects an existing
manuscript folder; **Analyze a manuscript** opens the import preview. The default
service starts without a project and does not search the terminal's directory.
`uv tool list` shows the installed source. A tool installation does not make
`import lixity` available to a different Python environment.

This uses uv's [isolated tool environment](https://docs.astral.sh/uv/concepts/tools/)
and [managed Python support](https://docs.astral.sh/uv/concepts/python-versions/#requiring-or-disabling-managed-python-versions).
uv accepts [HTTPS wheel sources](https://docs.astral.sh/uv/concepts/projects/dependencies/#url).

### Optional research prerequisites

<details>
<summary>PDF/OCR and Zotero setup for research</summary>

The experimental research workspace is included. Text and Markdown sources need
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

### Development builds instead

<details>
<summary>Follow unreleased source changes</summary>

To follow unreleased changes, install [Git](https://git-scm.com/downloads), then
use this **instead**:

```sh
uv tool install --python 3.12 --managed-python --reinstall-package lixity "git+https://github.com/mfahsold/lixity.git@main"
```

`main` changes over time. Review
[release notes](https://github.com/mfahsold/lixity/releases) before switching.
Stop the managed service before replacing its installation, verify the new
version, then start it again. This does not alter manuscript files.

</details>

### Updates and removal

Version 0.3.0 resets the product number to reflect development maturity
before 1.0 while retaining existing features and historical releases. Package
managers may select historical 3.0.1 as numerically newer. Choose the exact
v0.3.0 wheel explicitly; do not rely on an unconstrained upgrade or a
product-number comparison for archive compatibility. v0.3.0 reads research
schemas v1–v7; historical v3.0.1 cannot read opt-in manuscript-link v7 archives.
Installing new files does not restart a running workspace; restart explicitly
after the upgrade.

When upgrading from a historical build before v2.4.0, stop its instance through the
original foreground terminal (Ctrl+C), checkout launcher or configured OS
manager before replacing the installation. That version has no `service`
command, and the new controller deliberately does not adopt its process.

```sh
lixity service stop
uv tool install --python 3.12 --managed-python --reinstall-package lixity "https://github.com/mfahsold/lixity/releases/download/v0.4.0/lixity-0.4.0-py3-none-any.whl"
lixity --version
lixity service start --open
```

Replace the URL with the published wheel for the release you intend to install.
`--reinstall-package lixity` refreshes that package without forcing ownership
of another installer's entrypoint. `uv tool upgrade lixity` retains the original
source and constraints;
it does not select a newer release wheel. See the official
[tool update reference](https://docs.astral.sh/uv/reference/cli/#uv-tool-install).
If you start with an explicit project, pass that path again after updating.

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

If you already use pipx, install the published wheel with
`pipx install "https://github.com/mfahsold/lixity/releases/download/v0.4.0/lixity-0.4.0-py3-none-any.whl"`,
then use `pipx ensurepath` if necessary. Keep using that installer to replace or
remove its installation rather than overwriting its executable with uv.

</details>

## First useful result

The installed app opens an empty workspace. Choose **Analyze a manuscript**,
confirm its preview language and read the first linked passage. To return to a
saved folder, choose **Open Project**. See [Onboarding](ONBOARDING.md).

<details>
<summary>Generate an offline report from the CLI</summary>

Create a UTF-8 Markdown file named `manuscript.md` in your manuscript folder.
Use `## Chapter title` headings and blank lines between paragraphs. Then run:

```sh
lixity analyze manuscript.md --language en
lixity build manuscript.md --language en
```

Open `exports/manuscript_dashboard.html` in your browser. The build also saves
metrics and written reports. Very short texts cannot support a meaningful style
reference; unavailable results are expected.

Use `--language de` for German, or explicit `--language auto` for detection.
English is the default. A local `lixity.toml` can hold:

```toml
language = "de"
title = "My manuscript"
```

**Since v0.3.0:** selected-project title, `author_name` and an
optional `[publication]` table feed the shared CLI/native PDF composer. These
additions are prepared for v0.3.0; use a development checkout until its wheel is
published.
No new renderer, runtime dependency or EPUB exporter is installed.
See [publication configuration and limits](USAGE.md#publication-settings).

For interactive project and research workflows, run `lixity service start --open`
and choose your project in the workspace. The standalone HTML
export remains read-only. The server's persistent workspace bar offers
**Open Project** for an existing folder and its research archive, and
**New Project → Import Manuscript** to create a separate project from uploaded text.
See [Onboarding](ONBOARDING.md) for this workflow. Since 2.0.0, the workspace includes a five-field NDA generator with preview and PDF/editable-text
downloads in the project language; see [NDA guidance](USAGE.md#nda-agreements).
It creates no server files or recipient registry. For characters outside the
native Windows-1252 PDF repertoire, download UTF-8 text for your local editor.

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

All tabs connected to one server share its active project. **Open Project**
changes that live workspace; CLI analysis, research and build commands do not.
`start` uses fresh launch settings. `restart` uses recorded launch settings plus
explicit overrides, even after a stop; a project selected later in the browser
does not replace the startup project. After updates or OCR environment
changes, restart the appropriate managed instance; a browser reload alone does
not load new code. Supply OCR variables in the new start/restart environment;
their values are not saved as launch settings.

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
reports readiness, installed/running versions, backend and log path; see the
[command contract](USAGE.md#lixity-service) for states and exit codes.

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

These advanced source installs require Git and an existing Python 3.10+.

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install "git+https://github.com/mfahsold/lixity.git@v0.4.0"
.venv/bin/python -m pip check
.venv/bin/python -c "import lixity; print(lixity.__version__)"
```

Windows PowerShell (no activation or execution-policy change needed):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "git+https://github.com/mfahsold/lixity.git@v0.4.0"
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
