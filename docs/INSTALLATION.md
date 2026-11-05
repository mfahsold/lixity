# Install, verify and update Lixity

Lixity runs on your computer on Linux, macOS and Windows. It is
**open source under AGPL-3.0-or-later**. Install the published package
(`lixity` on [PyPI](https://pypi.org/project/lixity/)) or the pinned release
wheel with the commands below. Any writing purpose is covered;
a separate written commercial license exists only for closed-source
integrations. See [licensing](LICENSING.md) before installation.
Analysis runs offline; downloading Python, the package and dependencies requires
network access. No manuscript upload, account or API key is required.

> **Version scope:** this documentation describes **v0.7.9**. Verify packages at
> [GitHub releases](https://github.com/mfahsold/lixity/releases/latest) and
> [PyPI](https://pypi.org/project/lixity/). The product uses the pre-1.0 **0.x** line.
> Historical **1.x** and **3.x** tags predate the product-number reset; a larger
> historical number does not mean a newer release. Product, JSON response and
> archive schema versions are independent.

## Find your setup task

[All documentation](README.md) · [First session](ONBOARDING.md) ·
[Workspace](WORKSPACE.md) · [CLI](USAGE.md) · [Audio](AUDIO.md)

| Task | Section |
| --- | --- |
| Install the application | [Current release](#cli-current-release) · [uv prerequisites](#install-uv-if-it-is-not-available) |
| Start with a manuscript | [First result](#first-useful-result) |
| Update or uninstall | [Updates and removal](#updates-and-removal) |
| Start, stop, restart, inspect logs or change ports | [Running the server](#running-the-server) |
| Start automatically after login | [Optional login startup](#optional-startup-at-login) |
| Add PDF/OCR or Zotero support | [Research prerequisites](#optional-research-prerequisites) · [Server access](#server-environment-and-project-access) |
| Configure speech generation | [Qwen](#optional-qwen-audio-worker) · [Coqui/OpenVoice](#experimental-coqui-and-openvoice-audio-unreleased) · [IMS-Toucan](#ims-toucan-author-voice-and-phonetic-direction) · [External providers](#external-speech-providers-and-local-audio-inspection-unreleased) |
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

See the [release notes](releases/v0.7.9.md)
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
project. **Project → Settings → Audio and services → Services & audio queue** lists open views and verifies each actual audio worker.
A view URL is valid only while this server runs; after restart, reopen the project
from the app home. Custom ports remain available for explicit development instances.

The app opens `http://127.0.0.1:8765/` with an empty workspace; it does not
search your terminal's current folder. Choose **Open Project** for an existing
folder or **Analyze a manuscript** to preview a copy into a new project.
Confirm the manuscript language, then read a passage in **Manuscript**.
Use **Analysis** for diagnostics or **… → Explore passage** for one paragraph.
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
Short text may leave measurements unavailable. The [workspace manual](WORKSPACE.md) owns browser workflows;
[CLI reference](USAGE.md) owns commands and configuration. Built-in analysis runs locally. Optional
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

### External speech providers and local audio inspection (unreleased)

Direction/timeline and SSML export need no speech model, worker or API key.
For synthesis, run a separately managed service that implements
`POST /v1/audio/speech`, then explicitly configure its base URL, model and voice
in an `openai-compatible` profile. The minimal Lixity installation adds no
inference dependency and does not install or start that service. HTTPS endpoints
and explicitly configured local HTTP addresses (localhost, loopback or private
LAN IPs) are supported. URLs cannot contain credentials, query parameters or
fragments. Optional authentication refers to an environment-variable name via
`api_key_env`; set the actual key in the environment of the process that renders.
For `lixity service start`/`restart`, prefer `LIXITY_SPEECH_API_KEY` or another
`LIXITY_`-prefixed name: the managed systemd launcher forwards that prefix by
name without putting values in its command line or service record. Supply the
variable in the new start/restart environment; an already running service does
not inherit later terminal changes. Direct CLI rendering can use any valid name.
Opening a dialog, exporting a plan or checking provider status sends no text.
Provider readiness remains unknown until an explicit render.

Existing settings require the reviewed `audio-migrate --to-schema-4` workflow
before saving an external profile. Keep its backup and use a compatible reader;
older releases cannot read schema `/4`. Existing native profiles and retained
reference recordings need no conversion to keep their current behavior.

Providers return WAV. Mono 16-bit PCM at 24 kHz needs no decoder; other supported
WAV formats require FFmpeg on the Lixity host for normalization. MP3 output and
non-1.0 playback speed also require FFmpeg. Local `audio-inspect` reads PCM WAV
with the standard library; other WAV formats, FLAC and MP3 require FFmpeg.
`audio-verify` does not install or run speech recognition. Supply a timestamped
transcript explicitly when text or pause comparison is wanted. See the
[audio usage guide](AUDIO.md#audio-export-and-external-providers-unreleased).

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
The commands below own worker setup; [the audio manual](AUDIO.md#lixity-read-aloud)
owns profiles, reference recordings, synthesis and output inspection.
In 0.7.7, new audio profiles default to a 1.2 playback tempo factor;
FFmpeg is required on the Lixity host for any factor other than 1.0 and for MP3.
The factor is applied after synthesis, not by the Qwen model.

Piper support has been removed. Existing Piper profiles require an explicit
`audio-migrate` dry run and reviewed apply with a new backup outside the project.
The migration preserves source files and never assumes an equivalent Qwen timbre
or precise speed; see the same [read-aloud guide](AUDIO.md#lixity-read-aloud).

Qwen runs in an optional isolated Python 3.12 environment with `qwen-tts` and a
hardware-appropriate PyTorch installation. Install the development checkout into
that environment (`python -m pip install -e /path/to/lixity`) and obtain the
complete local CustomVoice checkpoint, including its speech tokenizer, using the
[upstream setup instructions](https://github.com/QwenLM/Qwen3-TTS). Choose the CPU
build of PyTorch for CPU-only use. Neither opening Lixity nor starting the worker
downloads weights or sends manuscript text to an inference provider.

Start the worker explicitly from that environment:

```bash
python -m lixity.speech_qwen --model /path/to/CustomVoice --device cpu --threads 1
```

It binds only to `127.0.0.1:8769`, loads the local model once and serializes
synthesis. CPU operation supports full chapters; generation can be much slower than the
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

### Experimental Coqui and OpenVoice audio (unreleased)

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
[Coqui/OpenVoice operation](AUDIO.md#experimental-coqui-and-openvoice-audio-unreleased).

### IMS-Toucan author voice and phonetic direction

**Unreleased.** The optional `ims-toucan` worker supports German and English with
an explicitly saved author reference, IPA overrides and structured prosody. It
uses local loopback port **8772**, independently of Qwen/Coqui (8769) and F5 (8771).
The worker is separate from the normal Lixity environment; no inference dependency
is added to the core package. CPU inference is supported; speed and speaker
similarity must be measured on the actual computer and reference recording.

Use a separate Python 3.11 environment and an eSpeak-NG shared library. The
following inference-only setup pins the upstream checkout and model revisions;
it intentionally excludes training and GUI dependencies. Run it from a Lixity
source checkout. Installation downloads packages and weights; subsequent worker
startup requires all files locally and disables Hugging Face network access.

```sh
TOUCAN_ENV="$HOME/.local/share/lixity/runtimes/toucan-venv"
TOUCAN_SOURCE="$HOME/.local/share/lixity/runtimes/IMS-Toucan"
TOUCAN_MODELS="$HOME/.local/share/lixity/models/toucan"
uv venv --python 3.11 "$TOUCAN_ENV"
uv pip install --python "$TOUCAN_ENV/bin/python" -e . \
  'torch==2.4.1' 'torchaudio==2.4.1' 'numpy==1.23.5' 'scipy==1.9.3' \
  'librosa==0.9.2' 'soundfile==0.12.1' 'speechbrain==0.5.13' \
  'huggingface-hub==0.25.2' 'phonemizer==3.2.1' 'matplotlib==3.9.2' \
  'dotwiz==0.4.0' 'einops==0.7.0' 'dragonmapper==0.2.6' \
  'pypinyin==0.47.1' 'tqdm==4.64.1' 'hyperpyyaml==1.2.2' \
  'setuptools==80.9.0' 'imageio==2.34.0' 'ruamel.yaml==0.18.6'
git clone --branch MassiveScaleToucan https://github.com/DigitalPhonetics/IMS-Toucan.git "$TOUCAN_SOURCE"
git -C "$TOUCAN_SOURCE" checkout 3cc2094d9c7123336eda7e299ac0bc90319ca9ff
"$TOUCAN_ENV/bin/huggingface-cli" download Flux9665/ToucanTTS \
  ToucanTTS.pt Vocoder.pt --revision e0afe0ef703d2178dd7dc74ec298693ddb10e720 \
  --local-dir "$TOUCAN_MODELS/acoustic"
"$TOUCAN_ENV/bin/huggingface-cli" download speechbrain/spkrec-ecapa-voxceleb \
  embedding_model.ckpt classifier.ckpt mean_var_norm_emb.ckpt hyperparams.yaml label_encoder.txt \
  --revision 0f99f2d0ebe89ac095bcc5903c4dd8f72b367286 --local-dir "$TOUCAN_MODELS/speaker"
"$TOUCAN_ENV/bin/python" -m lixity.speech_toucan \
  --source "$TOUCAN_SOURCE" --model "$TOUCAN_MODELS/acoustic" \
  --speaker "$TOUCAN_MODELS/speaker" --device cpu --threads 4
```

If the library is installed outside the system search path, set
`PHONEMIZER_ESPEAK_LIBRARY` to its actual shared-library file. Missing eSpeak,
unknown IPA symbols and incomplete checkpoints fail explicitly; the adapter never
falls back to a downloaded phonemizer or silently drops unsupported phones.
The model assets above total approximately 395 MiB, excluding Python packages.
Check the service with `lixity audio-status --engine ims-toucan`.

In the audio dialog, review and apply the backed-up settings upgrade to schema
`/5`, then create a reference profile and choose a named recording. Existing
profiles are retained. See the
[phonetics and direction workflow](AUDIO.md#ims-toucan-phonetics-and-structured-direction-unreleased).
Free-text acting instructions remain export metadata and cannot be rendered by
this adapter. The structured controls scale duration and prosodic variation;
they do not prescribe an exact emotion, calibrated pitch or words per minute.

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

#### Refresh an existing local checkout installation

For a machine deliberately testing unreleased checkout changes, update both
installations explicitly. After all app jobs and separate CLI renders finish,
stop the dashboard using its current installation. From the checkout:

```sh
.venv/bin/lixity service stop
make install-dev
make build
```

`make build` replaces the managed `dist/` archives only after comparing their
modules and UI assets against the current source. Install that newly built wheel
with `uv tool install --reinstall-package lixity` and its actual path, as in the
[pinned-wheel instructions](#pinned-release-and-installation-scope). A development
build is not a published release even when its filename matches one. Preserve
the tool's recorded additional requirements and constraints when replacing it;
do not silently remove language adapters or model packages.

Compare `lixity doctor --json` with `.venv/bin/lixity doctor --json`: their
`installation.module_path` and `installation.interpreter` identify the two
environments. Matching version strings alone do not prove matching code, and
`doctor` does not compare the installed files with a checkout. For an isolated
wheel installation, compare packaged module and UI-asset bytes against source
when exact parity is required. Do not mask an outdated installation with
`PYTHONPATH` and then report the installed CLI as updated.

Restart with the installation intended to own the dashboard, for example
`lixity service restart`, then reload browser tabs and reopen project views.
Optional audio workers retain their own environments; verify the selected
engine using `lixity audio-status --project ./my-novel --json` and perform a short
explicit synthesis check. A healthy app service does not establish worker readiness.
See [experimental Coqui/OpenVoice setup](AUDIO.md#experimental-coqui-and-openvoice-audio-unreleased)
for the separate German synthesis and reference-conversion dependencies.

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

Lixity's structured diagnostic events use one logging tree (`lixity.*`) with a single UTC
line format and standard levels; stdout stays the result channel of the CLI,
and the service appends the process' stderr to `service-PORT.log`. `lixity service start` and `restart` print that path. Status does not print it;
use the state-folder table above to locate `service-PORT.log` without restarting,
then use `tail -f` to follow it on systems with that command.

| Setting | Effect |
| --- | --- |
| `--debug` (start/restart) | DEBUG level; controlled request routes and error status |
| `LIXITY_DEBUG=1` | Same as `--debug` for the foreground server |
| `LIXITY_LOG_LEVEL` | Explicit level name (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `LIXITY_SPEECH_LOG_LEVEL=DEBUG` | Enable audio segment details without enabling other server debug output |

Starting the service rotates an oversized `service-PORT.log` to
`service-PORT.log.1` … `.3` (oldest dropped). The file can grow between starts;
this is not continuous rotation. On current main, request diagnostics retain only
known route names, methods and status; workspace identifiers, query strings,
unrecognized paths and response error text are omitted. Other stderr output can
still include contextual details; inspect logs before sharing them.

On current main, audio jobs and renders add technical events to the same logger.
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

For longer guides, retain a matching source checkout and start at `docs/README.md`.
The workspace, CLI, audio and research manuals are separate Markdown files.
Open these or the generated `docs/llms-full.txt` in a local text or Markdown reader. The bundle combines the references; it is not a rendered
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
