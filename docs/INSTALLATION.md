# Install, verify and update Lixity

## Download the desktop app

1. Open [Desktop downloads](guides/installation.html#desktop) and pick the
   installer for your operating system and processor. Direct preview downloads
   from GitHub Releases are available without an account. GitHub Actions test
   archives require a sign-in.
2. If your download is a ZIP, extract it. Use the
   [installer checker](guides/installation.html#installer-check) to verify the
   installer on your computer. For a manual check, use the SHA-256 list linked
   beside the direct downloads or included in the ZIP. Follow the setup steps
   for your platform.
   [macOS](#macos-desktop-dmg) · [Windows](#windows-desktop-test) · [Linux](#linux-desktop-test)
3. Open **Lixity** and choose **Try the example offline** in the welcome window.
   The app starts its bundled Python runtime. [First session](ONBOARDING.md)

The checker confirms file integrity against the list. Publisher trust depends
on the platform's signing checks. The download page shows the current desktop
availability. Use the [published browser app and CLI](#cli-current-release) as
an alternative.

<a id="macos-desktop-dmg"></a>

### Install a macOS test build from a disk image

1. Open **Apple menu → About This Mac**. Choose **Apple Silicon** if it shows
   an Apple chip, or **Intel** if it shows an Intel processor.
   [macOS downloads](guides/installation.html#macos)
2. If the disk image came in a ZIP, extract it in Finder. Verify the `.dmg`
   against the companion SHA-256 list, then open the disk image. Drag **Lixity.app** onto the
   **Applications** shortcut in the disk image window and wait for the copy
   to finish. Ad hoc images mount as **Lixity Test Build** and include
   **Start Here.html**.
3. Eject the disk image in Finder, then open **Applications → Lixity**.
   The [first-session guide](ONBOARDING.md) covers starting a manuscript and
   opening the bundled example.

Local development builds use ad hoc signing. Gatekeeper may block them at
first launch. Use Apple's guidance for the exact alert and confirm the copy
with the maintainer. If the app is blocked, use the
[published browser app and CLI](#cli-current-release).
[Apple's macOS app alerts](https://support.apple.com/en-us/102445)

<details>
<summary>Terminal checksum commands and clean-profile testing</summary>

Run the matching command in the installer folder. Use the actual filename
and compare its SHA-256 with the matching entry in the download's checksum
list. Filenames use `aarch64` for Apple Silicon and `x64` or `x86_64` for Intel.

```sh
# Apple Silicon
shasum -a 256 ./Lixity_VERSION_aarch64.dmg
# Intel
shasum -a 256 ./Lixity_VERSION_x64.dmg
```

For a clean-profile test, use a separate macOS account and copy the app to a
folder in that account. Close any running copy of Lixity before opening the
test build.

</details>

<a id="windows-desktop-test"></a>

### Install a Windows x64 test build

1. Open **Settings → System → About** and check that **System type** shows an
   x64-based processor. [Windows download](guides/installation.html#windows)
2. If the installer came in a ZIP, right-click it in File Explorer and choose
   **Extract All**. Verify the installer against the SHA-256 list, then open the file ending in
   `-setup.exe` to install for your Windows account.
3. Open **Lixity** from the Start menu. Setup can download the Microsoft Edge
   WebView2 Runtime if the machine lacks it, which requires internet access.
   [Microsoft WebView2 distribution](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)

Windows can show an unknown publisher or an unrecognized app alert for a
test build without a publisher signature. Keep the system's protection
settings in place. If policy blocks the installer, record the exact alert
and use the [published browser app and CLI](#cli-current-release) on that
machine.
[Microsoft SmartScreen guidance](https://learn.microsoft.com/windows/apps/package-and-deploy/smartscreen-reputation)

<details>
<summary>PowerShell checksum command and MSI deployment</summary>

Open PowerShell in the installer folder. Use the actual installer filename
and compare its SHA-256 with the matching entry in the download's checksum
list.

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath '.\Lixity_VERSION_x64-setup.exe'
```

Use the English `Lixity_VERSION_x64_en-US.msi` or German
`Lixity_VERSION_x64_de-DE.msi` when testing MSI deployment. Run the verified
EXE in a clean test account or use a test VM for MSI deployment.
For offline setups, Microsoft provides a standalone WebView2 installer.
[Microsoft WebView2 distribution](https://learn.microsoft.com/microsoft-edge/webview2/concepts/distribution)

</details>

<a id="linux-desktop-test"></a>

### Install a Linux x86-64 test build

1. Choose a Linux x86-64 installer. If it came in a ZIP, extract it with your
   file manager. Verify the chosen installer against the download's SHA-256 list.
   [Linux download](guides/installation.html#linux)
2. On Debian or Ubuntu, open the `.deb` in your graphical package installer
   if available. Then open **Lixity** from the applications menu.
3. For an AppImage, allow the file to run as a program in its properties.
   Open the AppImage and keep it in that folder for later sessions.
   [AppImage quickstart](https://docs.appimage.org/introduction/quickstart.html)

<details>
<summary>Terminal checksum and installation commands</summary>

Check that `uname -m` reports `x86_64`. Run the matching command from the
installer folder. Use the actual filename and compare its SHA-256 with the
matching entry in the download's checksum list.

```sh
sha256sum ./Lixity_VERSION_amd64.deb
sha256sum ./Lixity_VERSION_amd64.AppImage
```

In a test system or VM, run `sudo apt install ./Lixity_VERSION_amd64.deb`
with the actual filename. APT can resolve the WebKitGTK 4.1, GTK 3 and ALSA
dependencies declared by the package. If using the AppImage, you can allow
execution with `chmod u+x ./Lixity_VERSION_amd64.AppImage` instead.
[Ubuntu package installation](https://ubuntu.com/server/docs/tutorial/managing-software/#installing-a-deb-file)

</details>

Follow [AppImage FUSE troubleshooting](https://docs.appimage.org/user-guide/troubleshooting/fuse.html)
if your distribution reports a FUSE error. The
[published browser app and CLI](#cli-current-release) can run when the desktop
host lacks the required libraries.

If a Linux test build reports missing `libasound.so.2`, install the ALSA
runtime through your package manager. Ubuntu 22.04 provides `libasound2`,
and Ubuntu 24.04 provides `libasound2t64`.

### Check the first desktop session

Choose **Try the example offline** in a test account or VM. Review the preview,
then confirm to save an editable copy in a new folder. Open a passage, inspect
one finding and return to the passage. Save a small edit before checking an
upgrade or rollback. Confirm the text, settings and any retained research
after reopening the test project. Keep the installer, filename, SHA-256, OS
version and any failure details with your test record.
[First session](ONBOARDING.md) · [Desktop updates and rollback](#update-a-desktop-test-build)

### Find the desktop logs

In the desktop app, choose **Tools → Open Logs Folder**. Use the same action
in the startup error dialog if the workspace could not open. To inspect optional
extensions, use **Tools → System Status & Extensions**. If the window does
not open, check the folder for your platform.

| Platform | Desktop log folder |
| --- | --- |
| macOS | `~/Library/Application Support/lixity/service` |
| Windows | `%LOCALAPPDATA%\lixity\service` |
| Linux | `$XDG_STATE_HOME/lixity/service` or `~/.local/state/lixity/service` |

The desktop engine writes diagnostics to `desktop-sidecar.log`. Look for
`desktop_engine_ready` to identify the engine process, app build and versions,
then read the audio events from that session. The previous log can be in
`desktop-sidecar.log.1` after rotation at engine start. The separately
installed browser service uses [its own per-port log](#logs). Review log
details before sharing.

## Find your setup task

Built-in analysis runs offline without a manuscript upload, account or API key.
Lixity is **open source under AGPL-3.0-or-later** and may be used for commercial
writing. A separate written commercial license covers closed-source integrations.
[Licensing](LICENSING.md)

> This manual follows the source checkout. Verify the installed release at
> [GitHub releases](https://github.com/mfahsold/lixity/releases/latest) and
> [PyPI](https://pypi.org/project/lixity/). The product uses the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the product-number reset; a larger
> historical number does not mean a newer release. Product, JSON response and
> archive schema versions are independent.

[All documentation](README.md) · [First session](ONBOARDING.md) ·
[Workspace](WORKSPACE.md) · [CLI](USAGE.md) · [Audio](AUDIO.md)

| Task | Section |
| --- | --- |
| Install or open the desktop app | [Download](guides/installation.html#desktop) · [macOS](#macos-desktop-dmg) · [Windows](#windows-desktop-test) · [Linux](#linux-desktop-test) |
| Install the published browser app and CLI | [Current release](#cli-current-release) · [uv prerequisites](#install-uv-if-it-is-not-available) |
| Start with a manuscript | [First result](#first-useful-result) |
| Update or uninstall | [Desktop test builds](#update-a-desktop-test-build) · [CLI and browser app](#update-the-cli-and-browser-app) |
| Start, stop, restart, inspect logs or change ports | [Running the server](#running-the-server) |
| Start automatically after login | [Optional login startup](#optional-startup-at-login) |
| Add PDF/OCR or Zotero support | [Research prerequisites](#optional-research-prerequisites) · [Server access](#server-environment-and-project-access) |
| Configure an author voice or speech provider | [Speech synthesis setup](#speech-synthesis-setup) |
| Set up transcription on Apple Silicon | [MLX-Audio](#mlx-audio-on-apple-silicon) |
| Check a native speech worker | [Model lifecycle and health](#native-audio-model-lifecycle) |
| Use a separate Jetson worker | [Authenticated forward](#jetson-audio-worker) |
| Use Lixity from Python or develop it | [Python API environment](#python-api-project-environment) · [Editable checkout](#editable-checkout) |
| Resolve a setup problem | [Troubleshooting](#troubleshooting) · [Offline help](#read-documentation-offline) |

The normal application install is enough for analysis and the workspace. Choose
optional tools only for the task that needs them. Audio operations, recordings
and voice settings are documented in [the audio manual](AUDIO.md); this page owns
runtime installation and lifecycle.

## Where Lixity is published

| Channel | Use it for | Notes |
|---|---|---|
| [Desktop download guide](guides/installation.html#desktop) | desktop app | shows the verified public installers when available and the test route while they are being qualified |
| [`lixity` on PyPI](https://pypi.org/project/lixity/) | browser app and CLI | `uv tool install lixity`; pipx and pip work as well |
| [GitHub Releases](https://github.com/mfahsold/lixity/releases) | pinned, checksum-verified setups | published packages and checksum lists; build attestations via `gh attestation verify` |
| Zenodo | citing a released version | releases are archived automatically; concept DOI `10.5281/zenodo.23390297` (see [`CITATION.cff`](https://github.com/mfahsold/lixity/blob/main/CITATION.cff)) |

Use the isolated **uv tool** installation for the browser app and CLI. Install
[uv](https://docs.astral.sh/uv/getting-started/installation/) first if needed.
uv installs the published release wheel and supplies managed Python 3.12;
neither Git nor a separate Python installation is needed for this route.
The engine supports Python 3.10 or newer. Python API and editable developer
environments are [separate advanced routes](#python-api-project-environment).

### Packaging direction

PyPI distributes the published browser app and CLI. GitHub Releases provides
the wheel, source archive and checksums. The desktop download guide reads the
verified installer catalog and offers preview installers while stable desktop
installers undergo qualification.
[Current release](https://github.com/mfahsold/lixity/releases/latest)
[Desktop downloads](guides/installation.html#desktop)

The **Rust / Tauri v2 desktop host** in `desktop/` bundles an isolated
`python-build-standalone` 3.12 runtime alongside the shared Python analysis
engine and UI. The release build matrix targets macOS disk images for Apple
Silicon and Intel, Windows x64 NSIS and WiX installers, and Linux x64 Debian
packages and AppImages. The host adds native OS menus, folder and save dialogs,
atomic streaming exports and cross-platform `cpal`+`hound` microphone capture.
Opening a project's `lixity.toml` loads the manuscript selected for its folder.

The desktop host runs its own loopback engine. Manuscript folders and retained
research archives live outside the installed app. Python 3.12 is the bundled
desktop baseline. The standalone Python package supports Python 3.10 and later.
Optional speech and OCR workers remain separate from the core desktop application.
[Desktop installation by operating system](guides/installation.html#desktop)

The shared analysis core remains in Python (`src/lixity/`); Rust currently
implements the native desktop host rather than a second analysis engine. See
[`desktop/README.md`](https://github.com/mfahsold/lixity/blob/main/desktop/README.md)
and the [architecture evolution criteria](ARCHITECTURE.md#evolution-without-a-second-product-path).
Clean-machine checks must cover installation, upgrade, rollback and preservation
of project data. OS signing and notarization remain release gates.

For GitHub Actions test builds, sign in to GitHub and choose the archive for
your platform from the intended run. For a test kit supplied by the maintainer,
keep the installers, start guide and checksum list together.

### Open a local macOS development build

The [desktop maintainer guide](https://github.com/mfahsold/lixity/blob/main/desktop/README.md)
shows how to build and verify `Lixity.app`. Start that app with a project:

```sh
open -a "/path/to/Lixity.app" --args "/path/to/project/lixity.toml"
```

You can also open the app from Finder and choose **Open a project folder**.
If the app is already running, send it a file-open request with
`open -a "/path/to/Lixity.app" "/path/to/project/lixity.toml"`. The desktop app
starts its own engine. To manage the browser workspace, use
[the service commands](#running-the-server).

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

## CLI: current release

Install Lixity and launch the browser app from the same terminal. Both
commands work in Windows PowerShell, macOS and Linux.

```sh
uv tool install --python 3.12 --managed-python lixity
uv tool run lixity service start --open
```

For later sessions, run the second command again. After installation,
`uv tool run` uses the installed tool environment even if the `lixity`
executable directory is missing from the terminal's PATH. You can check your
version and the local service from that terminal as well.

```sh
uv tool run lixity --version
uv tool run lixity doctor
```

Use the [published release notes](https://github.com/mfahsold/lixity/releases/latest)
for changes and compatibility of the installed release. The
[development notes](releases/v0.9.3.md) describe this source version.

To use direct `lixity` commands in future terminals, run `uv tool update-shell`
and open a new terminal. `uv tool list` confirms which tools are installed.
`uv tool dir --bin` shows the directory to add to PATH in a custom shell.
[uv tool environments](https://docs.astral.sh/uv/concepts/tools/)

## First useful result

Use **Open a project folder** to reconnect an existing folder. Choose **Import
a manuscript** to preview copying a file into a new local project. The
[first-session guide](ONBOARDING.md) also covers writing from scratch and
trying the read-only example.

In the desktop app, reopen a project with **File → Recent Projects**. In the
browser app, start from the same app address in a new tab for each project.
Tabs with the same workspace URL share its selected project. Reopen a project
from the home address after a service restart. [Service management](#running-the-server)

For an initial result in your terminal, run:

```sh
lixity analyze manuscript.md --language en
```

Use the manuscript's actual language. The [CLI reference](USAGE.md) covers
language selection, configuration and focused analysis commands.

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

<a id="external-speech-providers-and-local-audio-inspection-unreleased"></a>
<a id="external-speech-providers-and-local-audio-inspection"></a>

### Speech synthesis setup

Choose the runtime for the audio controls you need. Recording an author take,
editing direction and exporting a plan work without installing a synthesis
model.

| Need | Setup |
| --- | --- |
| Use a local reference voice on Apple Silicon | [MLX-Audio ZONOS3](#mlx-audio-on-apple-silicon) |
| Use a local reference voice with IPA and structured delivery in German or English | [IMS-Toucan](#ims-toucan-author-voice-and-phonetic-direction) |
| Send free-text instructions to a compatible local or remote service | [OpenAI-compatible provider](#external-speech-providers-and-local-audio-inspection) |
| Use another existing profile | [Qwen](#optional-qwen-audio-worker) · [Coqui/OpenVoice](#experimental-coqui-and-openvoice-audio) · [Jetson worker](#jetson-audio-worker) |

Then [save a reference and hear a short preview](AUDIO.md#author-voice-recording-and-listening).
The three listed adapters are in v0.9.3. The checkout adds
[project-wide IPA and alternate spellings](AUDIO.md#project-pronunciations).
Use profile pronunciation controls when working with v0.9.3.

### External speech providers and local audio inspection

Speech-plan and SSML export work without a model, worker or API key. To render
with a separate service exposing `POST /v1/audio/speech`, configure an
`openai-compatible` profile with its base URL, model and voice.
Lixity accepts HTTPS and explicitly configured local HTTP addresses
(localhost, loopback or private LAN IPs). Use `api_key_env` for the name of the
environment variable. Supply the secret to the process that will render. The
managed systemd launcher forwards variables with the `LIXITY_` prefix by name,
so use a name such as `LIXITY_SPEECH_API_KEY` when launching that service.
A running app keeps the environment it received at startup. Enable **Provider
accepts delivery instructions** in **Voice profiles** after confirming the
endpoint and model can use the `instructions` field. Rendering sends the
effective spoken text to the configured address.
[Provider configuration](AUDIO.md#audio-export-and-external-providers)

Install FFmpeg for audio workflows that use WAV normalization, MP3 export or
FLAC/MP3 inspection. [Audio formats and limits](AUDIO.md#troubleshooting-and-limits)

### MLX-Audio on Apple Silicon

For local ZONOS3 synthesis or optional transcription, create a separate Python
3.11+ environment.

```sh
uv venv --python 3.11 "$HOME/.local/share/lixity/runtimes/mlx-audio"
uv pip install --python "$HOME/.local/share/lixity/runtimes/mlx-audio/bin/python" \
  'mlx-audio[stt,tts,server]'
```

Lixity uses that environment to start an isolated worker for synthesis with
`mlx-community/ZONOS3-Mini`. The `mlx-audio` profile supports a saved project
reference or a fixed voice and uses the model's pace control. For a first
setup, fetch the model into the Hugging Face cache used by the app. This
download is a separate step so the synthesis worker can run offline. If you
set `HF_HOME`, `HF_HUB_CACHE` or `XDG_CACHE_HOME`, use the same values for the
download and the Lixity process.

```sh
"$HOME/.local/share/lixity/runtimes/mlx-audio/bin/hf" download mlx-community/ZONOS3-Mini
lixity audio-status --project ./novel --engine mlx-audio --json
```

Confirm `runtime_available` and `model_cached` are true before starting a
preview. These checks inspect prerequisites. A preview tests model loading
and inference.

For optional transcription, run the MLX-Audio HTTP service in that environment.

```sh
"$HOME/.local/share/lixity/runtimes/mlx-audio/bin/python" -m mlx_audio.server \
  --host 127.0.0.1 --port 8000
```

Try a [reference voice preview](AUDIO.md#use-a-reference-with-zonos3) to check
word fidelity and timbre. The [MLX-Audio workflow](AUDIO.md#mlx-audio-on-apple-silicon)
covers fixed voices, render examples and transcription.

<a id="native-audio-model-lifecycle-unreleased"></a>
<a id="native-audio-model-lifecycle"></a>

### Native audio model lifecycle

Qwen (all three variants), Coqui/OpenVoice and IMS Toucan share one worker
lifecycle. Starting a worker binds its loopback service and validates local
settings/assets without importing the inference stack or loading weights. The
first validated synthesis request loads the model in an owned child process.
Keep the worker's separate optional environment and complete local checkpoints.

The default idle interval is **300 seconds after the last completed synthesis**.
The child exits after that interval, releasing model allocations and its inference
runtime. Active synthesis is protected; subsequent requests reuse a resident
model and start a new interval only after completion. Health/capability probes
neither load the model nor extend the interval. The lightweight service remains
available. The next render can therefore take longer while the model loads.

Configure the same option on every supported worker, for example:

```sh
python -m lixity.speech_qwen --model /path/to/CustomVoice --idle-timeout-seconds 900
```

`--idle-timeout-seconds` accepts finite values from 0 to 86400; 0 releases the
model after each completed request. Persist the option in the worker's service
command and restart that worker after changing it. This is shared worker policy,
not a project profile or a setting inferred from whichever manuscript is open.
Existing explicit library loaders remain available to callers that own a model.

`GET /health` distinguishes service readiness (`ready`) from residency
(`model_state`: `unloaded`, `loading`, `loaded`, `failed`), reports `active` and
actual `idle_timeout_seconds`, and includes resolved `runtime` metadata only
while a loaded renderer supplies it. Cold asset validation checks local files;
checkpoint integrity, optional dependencies and hardware compatibility are
resolved on first synthesis. A failed load/render is explicit and a subsequent
request can retry in a fresh child. No checkpoint is downloaded automatically.

### Optional Qwen audio worker

The Qwen worker supports `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` and separate
VoiceDesign and reference-based Base checkpoints. The application and CLI share
the same project profiles and rendering controls.

Run the loopback-only worker explicitly on this computer, or on a configured
Jetson reached through an authenticated SSH forward. Neither target is an
automatic fallback. Start with a short preview and verify actual synthesis and
memory headroom; model size and machine memory do not establish throughput.
Install FFmpeg on the Lixity computer for MP3 export and Qwen tempo changes.
[Tempo controls and profile defaults](AUDIO.md#cache-tempo-and-saved-settings)

For a project with Piper profiles, use the reviewed migration before rendering.
[Replace removed Piper profiles](AUDIO.md#replace-removed-piper-profiles)

Qwen runs in an optional isolated Python 3.12 environment with `qwen-tts` and a
hardware-appropriate PyTorch installation. Install the same Lixity version as
the browser app in that environment. For a published package, replace `VERSION`
in `python -m pip install 'lixity==VERSION'` with your version. For a source build,
use `python -m pip install /path/to/lixity-checkout` with your checkout. Obtain the
complete local CustomVoice checkpoint, including its speech tokenizer, using the
[upstream setup instructions](https://github.com/QwenLM/Qwen3-TTS). Choose the CPU
build of PyTorch for CPU-only use. Neither opening Lixity nor starting the worker
downloads weights or sends manuscript text to an inference provider.

Start the worker explicitly from that environment:

```bash
python -m lixity.speech_qwen --model /path/to/CustomVoice --device cpu --threads 1
```

It binds only to `127.0.0.1:8769` and serializes synthesis through the
[shared on-demand lifecycle](#native-audio-model-lifecycle). CPU operation
supports full chapters. Generation can be much slower than the
result's duration, so use a short preview to choose the voice. Match Torch threads
to the CPU budget assigned to the worker. A heavily throttled four-thread worker
can waste time contending within a one-core quota. Keep workstation CPU/memory
headroom through the operating system rather than silently reducing model size. GPU operation is
optional via `--device cuda`, with an explicit error when unavailable. Worker-only `--attention auto|eager|sdpa` selects the attention implementation.
The default `auto` uses eager attention on CPU and SDPA on CUDA. An operator can
compare an explicit override on the same checkpoint and workload; measure actual
synthesis, memory and output before selecting it. This flag does not establish a
performance improvement and cannot be set by browser input or a voice profile.

On a memory-constrained CUDA machine, an operator can explicitly keep the
talker on the GPU and run audio decoding on the CPU with the same checkpoint:

```bash
python -m lixity.speech_qwen --model /path/to/CustomVoice --device cuda --codec-device cpu --threads 4
```

The default `--codec-device model` keeps the decoder on the selected main device.
Worker-only `--codec-chunk-frames N` accepts 16–300 audio-code frames. The default
300 preserves the installed upstream decoder behavior. A smaller explicit value
uses that decoder's existing chunk algorithm with its 25-frame left context;
it can reduce per-chunk activation memory without changing model weights.
For example, test `--device cuda --codec-device model --codec-chunk-frames 32`
on the actual machine before adopting it. Unsupported decoder interfaces fail
explicitly. Chunking does not bound all model, KV-cache or output allocations,
and this option does not guarantee that a checkpoint fits in RAM.

CPU decoding uses float32 and trades GPU allocations for CPU work; this is an
explicit machine setting, not a voice profile or an automatic fallback. Shared
RAM remains finite. Suitable SSD-backed swap is a separate operating-system
decision; see [NVIDIA's Jetson memory guidance](https://www.jetson-ai-lab.com/tutorials/ram-optimization/).
Validate actual synthesis and memory headroom before scheduling long jobs.

#### Choose the Qwen checkpoint

CustomVoice, VoiceDesign and Base are separate checkpoints. Use a complete local
checkpoint with its tokenizer and the corresponding worker variant:

```sh
python -m lixity.speech_qwen --variant voice-design --model /path/to/VoiceDesign --device cpu --threads 4
python -m lixity.speech_qwen --variant base --model /path/to/Base --device cpu --threads 4
```

These are alternatives, not commands to run simultaneously. Check that no audio
job is active, stop the previous worker through its process manager, and start
the selected variant. All use `127.0.0.1:8769`; changing a profile does not switch
the running model. Check with `lixity audio-status --engine qwen3-base` (or the
matching engine), then follow [reference voices](AUDIO.md#experimental-reference-voices)
for the first short test. No checkpoint is downloaded automatically.

### Jetson audio worker

Machine setup is explicit: run the same Qwen worker on the Jetson with its
supported CUDA environment and complete local checkpoint. Keep that worker on
`127.0.0.1:8769` there, and forward laptop port `8770` over authenticated SSH:

```bash
ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 -L 127.0.0.1:8770:127.0.0.1:8769 USER@JETSON
```

Use your normal verified SSH host key and account. The local CPU worker continues
to use port `8769`; selecting Jetson uses only the fixed loopback forward `8770`.
These native target values cannot supply a host address or inference URL; external
providers use their separately validated explicit profile bindings. Lixity does
not install or start the remote worker or SSH connection. GPU compatibility and
available shared memory must be checked on the actual device; 8 GB does not
guarantee that every input fits.

<a id="experimental-coqui-and-openvoice-audio-unreleased"></a>
<a id="experimental-coqui-and-openvoice-audio"></a>

### Experimental Coqui and OpenVoice audio

Set up a separate Python environment following the
[maintained Coqui installation guide](https://coqui-tts.readthedocs.io/en/latest/installation.html).
Install `coqui-tts`, matching CPU versions of `torch` and `torchaudio`,
`gruut[de]`, and this Lixity checkout in that environment. For example, this
isolated CPU setup was tested on Linux ARM64:

```sh
uv venv --python 3.11 /path/to/coqui-env
uv pip install --python /path/to/coqui-env/bin/python --torch-backend cpu \
  'torch==2.8.0' 'torchaudio==2.8.0' 'coqui-tts==0.28.0' 'gruut[de]' -e /path/to/lixity
```

For other PyTorch/Coqui versions, check the upstream requirements (including
`torchcodec` where required) before changing this tested combination. Obtain the
[Thorsten VITS model](https://huggingface.co/Thorsten-Voice/VITS) and the
[OpenVoice V2 converter](https://huggingface.co/myshell-ai/OpenVoiceV2/tree/main/converter)
and keep their complete local model directories. Model downloads are an explicit
setup step. The worker does not download models or send manuscript text or
references over the network.

After ensuring no active audio job uses the local worker, start one of these
workers on the same loopback port used by Qwen:

```sh
/path/to/coqui-env/bin/python -m lixity.speech_coqui --model /path/to/thorsten-vits
/path/to/coqui-env/bin/python -m lixity.speech_coqui --model /path/to/thorsten-vits --converter /path/to/OpenVoiceV2/converter
```

The Thorsten directory must contain `model_file.pth` and `config.json`; the
converter directory must contain `checkpoint.pth` and `config.json`. The first
command serves `coqui`, the second `coqui-reference`. Start only one worker at
a time. A reference profile uses `voice = "reference"` and an existing
`reference_id`; a Thorsten profile uses `voice = "thorsten"`. Both require
`language = "de"`. Select the matching profile in the UI or use `--engine` on
the CLI. `audio-status --engine coqui-reference` checks the actual worker.

For settings migration, recording requirements and a first preview, continue with
[Coqui/OpenVoice operation](AUDIO.md#experimental-coqui-and-openvoice-audio).

### IMS-Toucan author voice and phonetic direction

The optional `ims-toucan` worker supports German and English with
an explicitly saved author reference, IPA overrides and structured prosody. It
runs in its own environment on local loopback port **8772**. CPU inference is
supported. Check speed and speaker similarity on the intended computer with
the intended recording.

Use a separate Python 3.11 environment and an eSpeak-NG shared library. The
previous inference recipe used PyTorch 2.4.1, which is affected by CVE-2025-32434
even with `weights_only=True`. The current worker checks for a stable PyTorch
release at or above 2.6.0 before loading checkpoints. Select a patched
PyTorch and TorchAudio pair for the platform. Treat the environment as
operator-managed until the complete dependencies and a render are verified
together. [PyTorch advisory](https://github.com/pytorch/pytorch/security/advisories/GHSA-53q9-r3pm-6pq6) ·
[TorchAudio compatibility matrix](https://docs.pytorch.org/audio/stable/installation.html)

The previously tested upstream IMS-Toucan checkout used revision
`3cc2094d9c7123336eda7e299ac0bc90319ca9ff`. Its acoustic assets were
`ToucanTTS.pt` and `Vocoder.pt` from `Flux9665/ToucanTTS` at revision
`e0afe0ef703d2178dd7dc74ec298693ddb10e720`. Its speaker assets came from
`speechbrain/spkrec-ecapa-voxceleb` at revision
`0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`. Keep `hyperparams.yaml`,
`embedding_model.ckpt`, `classifier.ckpt`, `mean_var_norm_emb.ckpt` and
`label_encoder.txt` together in the speaker directory. A macOS Apple Silicon
CPU check used Python 3.11, PyTorch and TorchAudio 2.8.0 and SpeechBrain 1.1.2
with these assets. Verify the provenance of your local source, model and
speaker configuration before use. The worker expects a local copy of every
file and disables Hugging Face network access during startup.

Install the Lixity package or the checkout in the isolated environment so
that its Python can run `lixity.speech_toucan`. Point the worker at the prepared
source tree, acoustic directory and complete speaker directory.

```sh
TOUCAN_ENV="$HOME/.local/share/lixity/runtimes/toucan-venv"
TOUCAN_SOURCE="$HOME/.local/share/lixity/runtimes/IMS-Toucan"
TOUCAN_MODELS="$HOME/.local/share/lixity/models/toucan"
"$TOUCAN_ENV/bin/python" -m lixity.speech_toucan \
  --source "$TOUCAN_SOURCE" --model "$TOUCAN_MODELS/acoustic" \
  --speaker "$TOUCAN_MODELS/speaker" --device cpu --threads 4
```

If the library is installed outside the system search path, set
`PHONEMIZER_ESPEAK_LIBRARY` to its actual shared-library file. Missing eSpeak,
unknown IPA symbols and incomplete checkpoints fail explicitly; the adapter never
falls back to a downloaded phonemizer or silently drops unsupported phones.
The reference acoustic and speaker assets total approximately 395 MiB,
excluding Python packages.
Check the service with `lixity audio-status --engine ims-toucan`.

In **Voice profiles**, review and apply the backed-up settings upgrade if the
project uses a schema before `/5`. Create an IMS-Toucan reference profile, choose a
saved recording and listen to a paragraph. Use the [phonetics and direction
workflow](AUDIO.md#ims-toucan-phonetics-and-structured-direction) to set
pronunciation, duration or prosodic variation. Export free-text acting
instructions for a service that supports them.

The upstream code and published Toucan/ECAPA weights are labeled Apache-2.0.
The Toucan maintainers discuss a training-data provenance question in
[issue 174](https://github.com/DigitalPhonetics/IMS-Toucan/issues/174); this setup
records the published licenses and does not resolve that separate question.

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
Stop the managed service before replacing its installation, verify the installed
code, then run `lixity service restart --open` to reuse the recorded launch settings.
Reload browser tabs after the restart. Follow the
[checkout refresh checks](#refresh-a-checkout-or-a-packaged-service) when
comparing a development build with local source; version strings alone do not
establish parity.

</details>

### Updates and removal

The desktop app includes its own Python runtime. Update the whole desktop
bundle through its installation channel. Use the existing Python tool manager
for a separately installed CLI and browser app. Review project compatibility
and back up before a release that changes the project or research format.
[Research compatibility limits](research/USAGE.md#limits)

#### Update a desktop test build

For a desktop test build, use the verified installer supplied for that test.
Test builds can share a version string, so check the source revision or the
artifact's SHA-256. **Help → Check for Updates…** checks the public desktop
channel when you are online. Installation is a separate manual step.
[Desktop downloads and platform instructions](guides/installation.html#desktop)

Save any open drafts and finish or deliberately cancel recordings and audio
jobs. Quit Lixity before replacing the application. Keep your manuscripts,
research archives and application settings during a normal update.

| Installed package | Update route |
| --- | --- |
| macOS disk image | Open the verified DMG for your Mac, drag the new app to **Applications** and confirm replacement. Eject the image and start Lixity from **Applications**. |
| Windows installer | Run the verified installer for the same architecture. Use the same setup type and scope as before. Let your administrator or deployment manager update a managed MSI installation. |
| Linux `.deb` | Open the verified newer package with the system package installer. Use the package manager for an installation from a managed repository. |
| Linux AppImage | Make the verified new file executable and launch it. Update any launcher or shortcut that still points to the previous file. |

Reopen a project and confirm that the manuscript and expected settings are
available. If you need to roll back, quit Lixity and use the earlier verified
installer or bundle from the same channel. For a project-format change, use
the release-specific rollback procedure and a compatible backup.
[Check startup diagnostics](#find-the-desktop-logs)

When an installation is owned by an external package manager, use its normal
update command. Lixity currently provides templates for future Homebrew and
WinGet distribution.
[Homebrew upgrade](https://docs.brew.sh/Manpage#upgrade-options-installed_formulainstalled_cask-)
· [WinGet upgrade](https://learn.microsoft.com/en-us/windows/package-manager/winget/upgrade)
· [Debian package management](https://www.debian.org/doc/manuals/debian-handbook/apt.en.html)

#### Update the CLI and browser app

Version 0.3.0 reset the product number to reflect development maturity before
1.0 while retaining historical tags and features. For a pinned installation,
choose the wheel under [CLI: current release](#cli-current-release), not the
numerically largest historical tag. Product and archive schema versions are
independent: back up research before an upgrade and inspect the
[reader/writer compatibility limits](research/USAGE.md#limits). Installing new
files does not restart a running workspace.

Before stopping the app, check **Project → Settings → Audio and services → Services & audio queue** for active or queued audio
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
uv tool run lixity service stop
uv tool upgrade lixity
uv tool run lixity --version
uv tool run lixity service restart --open
```

`uv tool upgrade lixity` selects the highest compatible, non-yanked version
available under the tool's PyPI constraints, not the most recently published by
date. A tool installed from a pinned wheel keeps that fixed URL — replace it
with `uv tool install --reinstall-package lixity` and the new wheel URL.
`--reinstall-package lixity` refreshes that package without forcing ownership
of another installer's entrypoint. See the official
[uv tool upgrade reference](https://docs.astral.sh/uv/concepts/tools/#upgrading-tools).
See [startup project and port settings](#running-the-server) if you want a
different startup project or run the service on a custom port.
To roll back, choose and verify the intended older release wheel and its
checksum, check archive compatibility, and restore a compatible backup if needed
before using that version. Reopen projects and verify the installed version and
service after the restart; do not assume older code can read newer archives.

Before updates or removal, stop each managed instance using its port, for example
`uv tool run lixity service stop --port 9000` for a custom-port instance. Before removal,
disable any login-startup entry you configured under systemd, launchd or Task
Scheduler. Then remove only Lixity:

```sh
uv tool run lixity service stop
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

<a id="refresh-an-existing-local-checkout-installation"></a>

#### Refresh a checkout or a packaged service

Choose the executable and port used by the browser tab you want to update.
`lixity doctor --port 8765 --json` pairs the invoked installation with its
observation of that listener. In a checkout, use `.venv/bin/lixity doctor`
with the same port. Module and interpreter paths identify the environment.
Version strings identify the version declared by each build. For exact source
parity, compare the installed modules and UI assets with the verified wheel.

For a checkout service, run `make doctor` to check the virtual environment and
listener together. If the editable package metadata is stale or development
dependencies changed, refresh the environment with `make install-dev`.
Finish active renders, save open drafts and record the project selections you
want to reopen. The runtime workspace URLs last for one server process. Then
run `make restart` and `make doctor` with the same `LIXITY_PORT` if you chose a
custom port. Reopen the recorded projects at that address and verify the
affected action in each selected view. Keep local project paths out of shared
rollout reports.

For a packaged checkout build, build and test the wheel before stopping the
service:

```sh
.venv/bin/python scripts/check_release.py --build --smoke
lixity service status --port 8765 --json
lixity service stop --port 8765
# Install the verified wheel from dist/ using the existing tool installer.
lixity service restart --port 8765
lixity doctor --port 8765 --json
```

Use the verified wheel's actual path in the
[pinned-wheel instructions](#pinned-release-and-installation-scope). Preserve any
recorded tool requirements and constraints for language adapters or model
packages. The commands above use the normal port. Use the same actual port for
each action if the service runs elsewhere. A local checkout build can use the
same version string as a published package.

Open the app home address after restarting, reopen additional project views and
exercise the changed feature in the running browser app. An existing scoped
view URL belongs to the earlier process.
Optional audio workers retain their own environments; verify the selected
engine using `lixity audio-status --project ./my-novel --json` and perform a short
explicit synthesis check. For the separate runtime and model prerequisites,
see [speech synthesis setup](#speech-synthesis-setup).

Remove only specifically identified unused build/test environments or old
unreferenced candidate wheels after verification. Do not use `make clean` as a
general installation repair: it also removes current distribution artifacts.
Retain backups, manuscript and research data, voice references, audio outputs,
model checkpoints and environments still used by optional workers. Do not
uninstall shared uv/Python runtimes or prune unrelated tools.

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

Project views on one server have independent selections. **Open Project** creates
a view. CLI analysis, research and build commands keep that view's selection.
`start` uses fresh launch settings. `restart` reuses the saved settings even
after a stop and accepts explicit overrides. To set a browser-selected project
as the launch default, pass its path to `restart`. After changing the installed
code or OCR environment, restart the intended instance. Supply OCR variables in
that launch environment. [Refresh and verify a build](#refresh-a-checkout-or-a-packaged-service)

If the reader shows an **Analysis freshness** notice, follow the
[source recovery steps](WORKSPACE.md#source-availability-and-saved-analysis).

<details>
<summary>Backend selection, stored launch settings and logs</summary>

`--backend auto` prefers an available Linux user systemd manager and otherwise
uses a detached process. `--backend process` explicitly chooses the latter.
`--backend systemd` fails when no usable user manager exists. These managed units
are transient and do not enable startup at login. Backend selection applies to
each invocation and is not saved: repeat `--backend process` on restart to keep
that choice; otherwise restart uses `auto`. `lixity service status --json`
reports readiness, installed and running versions, and backend. Check
`running` for readiness. See the [command contract](USAGE.md#lixity-service)
for exit codes and unknown states.

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

Lixity's structured diagnostic events use one logging tree (`lixity.*`) with a single UTC
line format and standard levels; stdout stays the result channel of the CLI,
and the service appends the process' stderr to `service-PORT.log`. `lixity service start` and `restart` print that path. Status does not print it;
use the state-folder table above to locate `service-PORT.log` without restarting,
then use `tail -f` to follow it on systems with that command.

An interrupted buffered response appears at DEBUG level during ordinary
navigation. Interrupted server error responses, streamed transfers and the
correlated website download failure remain visible at WARNING level.

| Setting | Effect |
| --- | --- |
| `--debug` (start/restart) | DEBUG level; controlled request routes and error status |
| `LIXITY_DEBUG=1` | Same as `--debug` for the foreground server |
| `LIXITY_LOG_LEVEL` | Explicit level name (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LIXITY_SPEECH_LOG_LEVEL=DEBUG` | Enable audio segment details without enabling other server debug output |

Starting the service rotates an oversized `service-PORT.log` to
`service-PORT.log.1` … `.3` (oldest dropped). The file can grow between starts;
this is not continuous rotation. In 0.8.0, request diagnostics retain only
known route names, methods and status; workspace identifiers, query strings,
unrecognized paths and response error text are omitted. Other stderr output can
still include contextual details; inspect logs before sharing them.

In 0.8.0, audio jobs and renders add technical events to the same logger.
A random diagnostic ID correlates a native job with its render without using the
job's access identifier. INFO events record queue and render state and segment
count; DEBUG additionally records each segment's requested model variant and
preset, cache outcome, elapsed time and bounds on the assembled PCM timeline.
Change indicators show whether the instruction, voice description or reference
selection differs from the preceding segment without recording their values.
The client also sends the random render ID as an optional HTTP header; a current
worker logs it alongside its own request ID. Missing or malformed IDs become
`unknown`. This client-supplied value is only a correlation hint, not proof of
identity, and older workers can ignore it.
Set `LIXITY_SPEECH_LOG_LEVEL=DEBUG` before starting the CLI or managed service
to retain those details without enabling general server debugging. Other values
leave the normal log-level inheritance in effect. They can show boundaries but
cannot identify a voice or judge its sound. They do not contain manuscript or
instruction text, reference audio, project paths or raw exception messages.
The events describe the requested engine, not the model weight bytes or hardware
that produced a cached segment. Existing WAV files acquire no retroactive log.

On newer builds, native worker failures add `speech_transport` with the fixed
engine, target, failure category and HTTP status where available. Match its
diagnostic ID to `audio_job` or `render_end`. A ready preview is temporary.
`audio_job` reports whether a chapter render was retained and gives a reason
when the job no longer matches its workspace. `audio_reference_saved`
identifies a stored recording separately from activation and view refresh.
`capture_failed` distinguishes missing capture tools from failed attempts.

The audio tools report allowlisted `audio_client` observations for blocked
render requests, microphone capture, save failures and generated playback.
A recording ready for review is still a draft. `audio_reference_saved`
confirms that the project has a saved reference.
`generated_audio_playing` means playback began in the browser. When the render
request supplied a diagnostic ID, playback uses that same ID. These observations
contain no text, reference identities, URLs, device names or raw errors.

The managed application captures its own stderr in `service-PORT.log`. A separate
CLI or speech-worker process writes to its own stderr and is not automatically
merged into that file. To retain a CLI run, deliberately redirect stderr to a
new private file, for example:

```sh
(umask 077; LIXITY_SPEECH_LOG_LEVEL=DEBUG lixity read-aloud --project ./novel --chapter 1 --speech-target local --progress -o chapter.wav 2> audio-diagnostics.log)
```

The shell umask applies when creating the file; check permissions separately if
the file already exists. The command above renders audio using the selected
profile and requires a matching local worker.
That captures **all** stderr, including other CLI errors or progress messages,
not only the redacted logger events; inspect it before sharing. Worker logs also
remain separate, and rotation of a redirected file is the operator's responsibility.

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

On Linux, `scripts/install-desktop-linux.sh` adds a per-user application menu
entry from the checkout. It can find an installed uv tool even when the uv tool
bin directory is outside `PATH`. The launcher calls `lixity service start --open`
to open the managed instance on its selected port. Run the script with
`--uninstall` to remove the menu entry and icon.

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

For the browser app, run `lixity service restart --open` to reuse the recorded
launch settings or `lixity service start --open` for a fresh workspace. If you
configured a separate login-startup manager, use that manager. For a macOS
development build, open `Lixity.app` from Finder and select a recent project.
Your project remains in its folder. Reapply any OCR environment settings.
Start Zotero for new captures. Retained evidence stays readable while it is
closed.

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

Follow the [contributor guide](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup)
for development verification and release qualification. Reload an editable
installation through the [checkout refresh procedure](#refresh-a-checkout-or-a-packaged-service).
A generated reading website is a fixed project snapshot. Refresh it with
[an explicit export](WORKSPACE.md#export-a-reading-website) after manuscript or
archive changes.

## Read documentation offline

Installed command help and schema discovery work without a network connection:
use `lixity COMMAND --help`, `lixity research COMMAND --help`,
`lixity about --json` and `lixity research schema`. They describe the code in
that installation; they do not require the workspace service.

For longer guides, retain a matching source checkout and start at `docs/README.md`.
The workspace, CLI, audio and research manuals are separate Markdown files.
Open these or the generated `docs/llms-full.txt` in a local text or Markdown reader. The bundle combines the references; it is not a rendered
documentation website. Package installations do not include these guides, and
there is no `lixity docs --serve` command. Contributors can preview the approved
Pages tree using the existing
[documentation preview workflow](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#updating-documentation-and-pages).
External links and public-site analytics remain separate from offline reading.

## Troubleshooting

This section owns install, service lifecycle and environment failures.
For command/config failures see [USAGE troubleshooting](USAGE.md#troubleshooting);
for reading/review failures see [workspace troubleshooting](WORKSPACE.md#troubleshooting);
for recording/synthesis failures see [audio limits](AUDIO.md#troubleshooting-and-limits).

| Symptom | Action |
| --- | --- |
| The Mac opens the disk image again | Eject it in Finder and open **Applications → Lixity**. [Copy the app first](#macos-desktop-dmg). |
| The desktop window does not start | Open the copy in **Applications** and check [the desktop log](#find-the-desktop-logs). For a macOS security alert, check the test build's source and checksum. [Apple's macOS app alerts](https://support.apple.com/en-us/102445) |
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

**Research → Set up OCR and Zotero** offers an explicit
metadata-only check even before opening a project. It installs nothing and writes
no configuration. A reachable Zotero API does not establish library, collection
or attachment access; those remain separate explicit browse actions.
See [the extraction contract](research/USAGE.md#self-hosted-pdf-and-ocr-extraction).
The [Unlimited-OCR integration guide](research/OCR_INTEGRATION.md) describes the
external-worker boundary and the limited historical CPU experiment. Upstream
`infer.py` cannot be used directly as a `LIXITY_OCR_WORKER` executable.

The [installation guide](https://lixity.de/guides/installation.html)
includes desktop downloads and a first-session example. It also links to
interpretation and source/PDF workflows.
