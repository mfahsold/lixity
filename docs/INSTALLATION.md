# Install, verify and update Lixity

Lixity runs locally on Linux, macOS and Windows. It is **source-available under
LNCL-1.0, for non-commercial use**, and is installed from GitHub, not PyPI.
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

Python **3.12 is a practical default**. The engine and project TOML settings support 3.10+; Python 3.10 uses a small
conditional `tomli` dependency, while 3.11+ uses `tomllib`. Git is required for
the GitHub source commands. Install [Git](https://git-scm.com/downloads) and
[uv](https://docs.astral.sh/uv/getting-started/installation/) first if needed.
Do not run multiple installation routes into the same environment, use `sudo
pip`, or bypass an externally managed Python environment.

## CLI: current release

These commands work in a terminal, including Windows PowerShell:

```sh
uv tool install --python 3.12 "git+https://github.com/mfahsold/lixity.git@v1.22.0"
lixity --version
lixity about
```

The current release is **v1.22.0**. The tag includes the local project/research workspace,
Zotero capture and paired backup tools, search across current authored records,
seven-language workflows and numerical corrections. For reproducible automation, pin this tag or
its reviewed full commit hash. Read the [release notes](releases/v1.20.0.md).

If `lixity` is not found, run `uv tool update-shell`, open a new terminal and
retry. `uv tool list` shows the installed source. A tool installation does not
make `import lixity` available to a different Python environment.

### Optional research prerequisites

The experimental research workspace is included in the release; it does not
require a development installation. Research search requires SQLite with FTS5.
For text PDFs, install Poppler separately; scanned PDFs require a configured OCR
worker. Neither Zotero nor an OCR model is installed with the Python package.

Zotero is a separate optional application. Install a native build for your operating
system and enable its local API in Settings → Advanced. Use Zotero 10 or later for
stable local instance identity and safe capture refresh. Lixity connects only to
`127.0.0.1:23119`; it does not install Zotero, launch it, modify its database or
configure synchronization. A cloud account is unnecessary for this local workflow.
See the [Zotero setup and migration reference](research/USAGE.md#zotero-desktop-bridge-since-v1190).
Back up the existing archive before creating v3 captures; all readers and writers
must support that format. Installing a newer package does not migrate sources
or change a running server.

### Development builds instead

To follow unreleased changes, use this **instead**:

```sh
uv tool install --python 3.12 "git+https://github.com/mfahsold/lixity.git@main"
```

`main` can change and is not a release pin. Review
[release notes](https://github.com/mfahsold/lixity/releases) before switching.
To deliberately replace an existing installation, repeat the chosen command
with `--force`. This does not alter manuscript files.

### Updates and removal

```sh
uv tool upgrade lixity
lixity --version
```

To remove the CLI later, run `uv tool uninstall lixity`. Upgrades respect the
selected source/ref: a pinned tag or commit does not move to a newer release or
`main`. To adopt a different release, repeat the installation command with its
explicit tag and `--force`.
Restart any running adapter/server after an engine update.

Use one active server for ordinary interactive use. Stop the previous server
(Ctrl+C in its terminal) before starting the updated one on the same port,
normally `8765`. Starting another port leaves the old process running with its
previously loaded Python code and dashboard. A browser reload or a fresh CLI
version check does not update that running process, including with an editable
installation. All browser tabs connected to one server share its active project.

If you already use pipx, the equivalent alternative is
`pipx install "git+https://github.com/mfahsold/lixity.git@v1.22.0"`, followed by
`pipx ensurepath` if necessary; update with `pipx upgrade lixity`.

## First useful result

Create a UTF-8 Markdown file named `manuscript.md` in your manuscript folder.
Use `## Chapter title` headings and blank lines between paragraphs. Then run:

```sh
lixity analyze manuscript.md --language en
lixity build manuscript.md --language en
```

Open `exports/manuscript_dashboard.html` in your browser. The first build also
creates JSON metrics, a report and a style passport. Very short texts cannot
support a meaningful style reference; unavailable results are expected.

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
**New Project → Import Manuscript** for a new project from browser file bytes.
See [Onboarding](ONBOARDING.md) for the chooser and research flow. NDA management
and publication-specific exports require a project adapter.

## Running the server

`lixity serve` starts a loopback-only HTTP server on `127.0.0.1:8765` (default port).
Open `http://127.0.0.1:8765/` in your browser. The server is strictly local:
no manuscript bytes leave your machine. All browser tabs share one running instance.

```sh
# Simplest: foreground, Ctrl+C to stop
lixity serve /path/to/project --open        # --open launches the browser automatically

# Open a project on a custom port
lixity serve /path/to/project --port 9000

# Start without preloading a project (open one from the dashboard wizard)
lixity serve --no-project
```

If port 8765 is already occupied, Lixity prints a clear error with the kill command.
Use `--port <PORT>` to start on a different port instead.

### Managed background start (Linux and macOS)

`scripts/lixity-start.sh` in the source checkout manages a PID-file-backed
background instance, so you can start, stop and check status without keeping a
terminal open:

```sh
scripts/lixity-start.sh start            # start in background
scripts/lixity-start.sh status           # check if running
scripts/lixity-start.sh restart          # stop then start
scripts/lixity-start.sh stop             # stop (SIGTERM, SIGKILL after 5 s)

# Custom port or project directory
LIXITY_PORT=9000 LIXITY_DIR=/path/to/project scripts/lixity-start.sh start
scripts/lixity-start.sh start --port 9000 --open /path/to/project
```

State lives in `${XDG_RUNTIME_DIR:-~/.local/share/lixity}/`: `lixity.pid` and
`lixity.log` (rotated to `lixity.log.1` on every start). `status` verifies that
the recorded PID is still a Lixity process, so a recycled PID is not mistaken
for a running server.

From an editable checkout you can also use `make`:

```sh
make serve                     # start background instance on default port
make serve LIXITY_PORT=9000    # custom port
make stop                      # stop the managed instance
```

### Managed background start (Windows)

`scripts/lixity-start.ps1` provides the same lifecycle on Windows. It runs on
Windows PowerShell 5.1 and PowerShell 7+:

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

State lives in `%LOCALAPPDATA%\lixity\`. Windows offers no console-signal
delivery for a detached process, so `stop` terminates the process rather than
performing the interrupt-based shutdown that `lixity serve` does on Ctrl+C.

### Auto-start on login — Linux (systemd user service)

`scripts/lixity.service` starts Lixity automatically at login. Install it once
per user account:

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

# To start even without an open login session:
loginctl enable-linger $USER
```

The port comes from the unit's `Environment=LIXITY_PORT=` line and is referenced
as `${LIXITY_PORT}`. systemd performs plain variable substitution only, so a
shell-style `${LIXITY_PORT:-8765}` default is **not** expanded and would pass a
non-numeric value to `--port`. To change the port, override both lines:

```sh
systemctl --user edit lixity
# → add under [Service]:
#   Environment=LIXITY_PORT=9000
#   ExecStart=%h/.local/bin/lixity serve --host 127.0.0.1 --port ${LIXITY_PORT}
```

The unit deliberately omits `ProtectSystem=`/`ProtectHome=`. The server writes
`exports/` and the research archive inside the manuscript project directory, so
a read-only filesystem would break it for any project outside your home
directory.

### Auto-start on login — macOS (launchd agent)

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

For a fully automated start on Windows login without a visible PowerShell window,
register the script as a Task Scheduler task:

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

Open `http://127.0.0.1:8765`. No reinstall or reimport is needed for an existing
project. If you use OCR environment variables, supply the same values again;
shell variables are not saved in project settings. Retained evidence is readable
while Zotero is closed, but capturing new attachments requires Zotero running.

## Python API: project environment

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install "git+https://github.com/mfahsold/lixity.git@v1.22.0"
.venv/bin/python -m pip check
.venv/bin/python -c "import lixity; print(lixity.__version__)"
```

Windows PowerShell (no activation or execution-policy change needed):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "git+https://github.com/mfahsold/lixity.git@v1.22.0"
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
| HTML lacks interactive settings | Expected for a standalone export; use `lixity serve` for the local workspace controls. NDA management requires a project adapter. |

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

Start the server with the intended project explicitly:

```sh
lixity serve /absolute/path/to/project --host 127.0.0.1 --port 8765
```

The folder browser sees the server process's filesystem. If an existing project
is unavailable after a restart, check the process user, sandbox/container mounts,
directory permissions and the explicit project argument. A path that works in
your terminal is not necessarily visible to a service running in isolation.
Use **Open Project** to reconnect the original archive; manuscript upload creates
a separate project and is not a repair for missing filesystem access.

Updating the package or exporting an environment variable does not change an
already running server. Restart the intended service, then verify the displayed
project path. Keep private archives outside the engine checkout.

For PDF import, make `pdftotext` and `pdftoppm` available in that same environment.
Debian/Ubuntu package: `poppler-utils`; Homebrew package: `poppler`.
Run `lixity research ocr-status` (available since v1.18.0). Scans require a separately
configured `LIXITY_OCR_WORKER`; native extraction cannot read an image-only page.
See [the extraction contract](research/USAGE.md#self-hosted-pdf-and-ocr-extraction).
The [Unlimited-OCR integration guide](research/OCR_INTEGRATION.md) compares the
official inference routes and this custom boundary. Upstream `infer.py` is not
a drop-in `LIXITY_OCR_WORKER` executable. The Python package installs neither a
model runtime nor a worker executable. The source checkout includes an experimental
CPU adapter; its separately prepared runtime is described in that guide.

The [browser installation guide](https://mfahsold.github.io/lixity/guides/installation.html)
provides a synthetic first-dashboard example and links to interpretation and
source/PDF workflows.
