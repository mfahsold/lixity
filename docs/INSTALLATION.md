# Install, verify and update Lixity

Lixity runs on your computer on Linux, macOS and Windows. It is
**source-available under LNCL-1.0, for non-commercial use**. Install it from
GitHub using the commands below; it is not distributed on PyPI.
Books intended for sale, including self-publishing, require a separate written
commercial license. See [licensing examples](LICENSING.md) before installation.
Analysis runs offline; downloading Python, the package and dependencies requires
network access. No manuscript upload, account or API key is required.

## Choose one installation route

| Need | Route |
| --- | --- |
| Use the command line across several manuscript folders | Isolated `uv tool` installation below |
| Import `lixity` from your own Python project | Project virtual environment |
| Edit the engine or develop an adapter | Editable checkout |

Use **Python 3.12** for these examples; Python 3.10 or newer is supported.
Install [Git](https://git-scm.com/downloads) and
[uv](https://docs.astral.sh/uv/getting-started/installation/) first if needed.
Do not run multiple installation routes into the same environment, use `sudo
pip`, or bypass an externally managed Python environment.

## CLI: current release

These commands work in a terminal, including Windows PowerShell:

```sh
uv tool install --python 3.12 "git+https://github.com/mfahsold/lixity.git@v1.24.1"
lixity --version
lixity about
```

The current release is **v1.24.1**. This command selects a fixed release so that
reinstalling it uses the same source. Read the [release notes](releases/v1.24.1.md)
for changes and compatibility information.

If `lixity` is not found, run `uv tool update-shell`, open a new terminal and
retry. `uv tool list` shows the installed source. A tool installation does not
make `import lixity` available to a different Python environment.

### Optional research prerequisites

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

### Development builds instead

To follow unreleased changes, use this **instead**:

```sh
uv tool install --python 3.12 "git+https://github.com/mfahsold/lixity.git@main"
```

`main` changes over time. Review
[release notes](https://github.com/mfahsold/lixity/releases) before switching.
To deliberately replace an existing installation, repeat the chosen command
with `--force`. This does not alter manuscript files.

### Updates and removal

```sh
uv tool upgrade lixity
lixity --version
```

To select a newer release, repeat the installation command with its new tag and
`--force`. `uv tool upgrade lixity` stays within the chosen source: it does not
move a fixed tag or commit to another release. Remove the CLI with
`uv tool uninstall lixity`. After updating, restart any running server or adapter;
see [Running the server](#running-the-server).

If a terminal reports an older version than your checkout, compare `lixity
--version` with `.venv/bin/lixity --version` (`.venv\Scripts\lixity.exe --version`
on Windows). They may be separate installations. Use `command -v lixity` on
Linux/macOS or `Get-Command lixity` in PowerShell, then inspect `uv tool list`.
A non-editable tool installed from a local folder is a copy: changing the
folder does not update the installed tool. Reinstall the chosen release or
development source explicitly, verify its version, and restart its service.

If you already use pipx, the equivalent alternative is
`pipx install "git+https://github.com/mfahsold/lixity.git@v1.24.1"`, followed by
`pipx ensurepath` if necessary; update with `pipx upgrade lixity`.

## First useful result

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

For interactive project and research workflows, run `lixity serve manuscript.md`
or start the project wizard with `lixity serve --no-project`. The standalone HTML
export remains read-only. The server's persistent workspace bar offers
**Open Project** for an existing folder and its research archive, and
**New Project → Import Manuscript** to create a separate project from uploaded text.
See [Onboarding](ONBOARDING.md) for this workflow. Native encrypted NDA tracking
is built in for configured projects; publication-specific exports use project adapters.

## Running the server

`lixity serve` starts the local workspace at `http://127.0.0.1:8765/` by default.
The built-in analysis runs on your computer; optional integrations have their own
setup and data handling. All tabs connected to one server share its active project.

```sh
# Simplest: foreground, Ctrl+C to stop
lixity serve /path/to/project --open        # --open launches the browser automatically

# Open a project on a custom port
lixity serve /path/to/project --port 9000

# Start without preloading a project (open one from the dashboard wizard)
lixity serve --no-project
```

If port 8765 is already occupied, Lixity prints a clear error with the kill command.
Identify the existing server before stopping it, or choose another port.
After an update or a change to OCR settings, stop the old server with Ctrl+C and
restart it on the same port. Reloading the browser does not update running code.

### Managed background start (Linux and macOS)

The source checkout includes an optional launcher for use without an open terminal:

```sh
scripts/lixity-start.sh start            # start in background
scripts/lixity-start.sh status           # check if running
scripts/lixity-start.sh restart          # stop then start
scripts/lixity-start.sh stop             # stop (SIGTERM, SIGKILL after 5 s)

# Custom port or project directory
LIXITY_PORT=9000 LIXITY_DIR=/path/to/project scripts/lixity-start.sh start
scripts/lixity-start.sh start --port 9000 --open /path/to/project
```

The launcher keeps port-specific process records and logs in `$XDG_RUNTIME_DIR`,
or `~/.local/share/lixity` when unavailable. `status` checks the running process
and port; `start` prints the log path.

From an editable checkout you can also use `make`:

```sh
make serve                     # start background instance on default port
make serve LIXITY_PORT=9000    # custom port
make stop                      # stop the managed instance
```

### Managed background start (Windows)

Use the Windows launcher with Windows PowerShell 5.1 or PowerShell 7+:

```powershell
# Allow user-scope script execution (once per machine):
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

.\scripts\lixity-start.ps1 start               # start in background
.\scripts\lixity-start.ps1 status              # check if running
.\scripts\lixity-start.ps1 restart             # stop then start
.\scripts\lixity-start.ps1 stop                # stop the running process
.\scripts\lixity-start.ps1 start -Port 9000    # custom port
.\scripts\lixity-start.ps1 start -Open         # also open the browser
```

Process records and logs are in `%LOCALAPPDATA%\lixity\`. Its `stop` command
terminates the background process; a foreground server is stopped with Ctrl+C.

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
```

The template explains port changes and service options. If you deliberately
need it running without a login session, use `loginctl enable-linger $USER`.
The service must be able to write to its project folder.

### Auto-start on login — macOS (launchd agent)

Optional: edit the [launchd template](https://github.com/mfahsold/lixity/blob/main/scripts/lixity.plist)
to point to your executable and project folder, then register it:

```sh
# Edit the plist: set the correct path to your lixity binary (check: which lixity)
# and optionally set a WorkingDirectory for your project.
nano scripts/lixity.plist

cp scripts/lixity.plist ~/Library/LaunchAgents/com.lixity.serve.plist
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.lixity.serve.plist

# Management
launchctl kickstart -k gui/$(id -u)/com.lixity.serve   # restart
launchctl kill SIGTERM gui/$(id -u)/com.lixity.serve   # stop
tail -f /tmp/lixity-stdout.log                        # live log

# Disable auto-start
launchctl bootout gui/$(id -u)/com.lixity.serve
```

### Auto-start on login — Windows (Task Scheduler)

Optional: register the launcher in Task Scheduler to start at login:

```powershell
$script    = Join-Path $PWD "scripts\lixity-start.ps1"
$action    = New-ScheduledTaskAction -Execute "powershell.exe" `
              -Argument "-NonInteractive -WindowStyle Hidden -File `"$script`" start"
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

### After a computer restart (quick reference)

If you do not use one of the auto-start methods above, reopen a terminal and run:

```sh
lixity serve /absolute/path/to/project --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765/`. No reinstall or reimport is needed. Reapply any OCR
environment settings; they are not saved in project settings. Start Zotero for
new captures; retained evidence stays readable while it is closed.

## Python API: project environment

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install "git+https://github.com/mfahsold/lixity.git@v1.24.1"
.venv/bin/python -m pip check
.venv/bin/python -c "import lixity; print(lixity.__version__)"
```

Windows PowerShell (no activation or execution-policy change needed):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "git+https://github.com/mfahsold/lixity.git@v1.24.1"
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
| `git` or `uv` not found | Install the prerequisite and reopen the terminal. |
| `lixity` not found | Use `uv tool update-shell`, or the chosen venv's executable directly. |
| `externally-managed-environment` | Use `uv tool` or a venv; do not use `--break-system-packages`. |
| Project settings ignored | Check `lixity.toml` syntax and the selected project path; explicit CLI flags take precedence. |
| Wrong version or old controls after update | Check `uv tool list` and `command -v lixity` (PowerShell: `Get-Command lixity`), then stop the old server and restart on the same port. Check that the browser uses that address. |
| Dependency build error | Try a supported CPython version with binary wheels, e.g. 3.12; retain the full installer error. |
| HTML lacks project or research actions | A standalone export is read-only. Use `lixity serve` for the local workspace; native NDA tracking also needs a configured project. |

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
Run `lixity research ocr-status` to check configuration. Image-only scans need a
separately configured `LIXITY_OCR_WORKER`; native extraction cannot read them.
See [the extraction contract](research/USAGE.md#self-hosted-pdf-and-ocr-extraction).
The [Unlimited-OCR integration guide](research/OCR_INTEGRATION.md) describes the
optional experimental CPU adapter and its separate runtime setup. Upstream
`infer.py` cannot be used directly as a `LIXITY_OCR_WORKER` executable.

The [browser installation guide](https://mfahsold.github.io/lixity/guides/installation.html)
provides a synthetic first-dashboard example and links to interpretation and
source/PDF workflows.
