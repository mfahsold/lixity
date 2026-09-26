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
uv tool install --python 3.12 "git+https://github.com/mfahsold/lixity.git@v1.16.0"
lixity --version
lixity about
```

The current release is **v1.16.0**. The tag includes the integrated local project/research workspace,
seven-language workflows and numerical corrections. For reproducible automation, pin this tag or
its reviewed full commit hash. Read the [migration notes](releases/v1.16.0.md).

If `lixity` is not found, run `uv tool update-shell`, open a new terminal and
retry. `uv tool list` shows the installed source. A tool installation does not
make `import lixity` available to a different Python environment.

### Development builds instead

Release `v1.16.0` includes the experimental [local research pilot](research/USAGE.md).
Research search requires SQLite with FTS5; OCR and external provider integrations
remain planned features.

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
selected source/ref: a pinned tag or commit does not move to `main`.
Restart any running adapter/server after an engine update.

If you already use pipx, the equivalent alternative is
`pipx install "git+https://github.com/mfahsold/lixity.git@v1.16.0"`, followed by
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
export remains read-only. NDA management and publication-specific exports require
a project adapter; see [Onboarding](ONBOARDING.md).

## Python API: project environment

Linux/macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install "git+https://github.com/mfahsold/lixity.git@v1.16.0"
.venv/bin/python -m pip check
.venv/bin/python -c "import lixity; print(lixity.__version__)"
```

Windows PowerShell (no activation or execution-policy change needed):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install "git+https://github.com/mfahsold/lixity.git@v1.16.0"
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
| Wrong version after update | Check `uv tool list` and `command -v lixity` (PowerShell: `Get-Command lixity`). |
| Dependency build error | Try a supported CPython version with binary wheels, e.g. 3.12; retain the full installer error. |
| HTML lacks settings/NDA controls | Expected for a standalone export; these belong to the embedding adapter. |

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
[contributor guide](../CONTRIBUTING.md) for the next steps.
