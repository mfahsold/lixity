# Lixity Desktop (Rust / Tauri v2)

Cross-platform standalone desktop host for **macOS**, **Windows**, and **Linux**.

## Architecture

- **One product path:** Reuses the single Lixity Python engine and browser workspace (`src/lixity/`).
- **Isolated Python 3.12 runtime bundle:** Built by `desktop/scripts/build_runtime_bundle.py` from relocatable `python-build-standalone` 3.12 + the verified Lixity wheel + `pydantic`, `rich`, `orjson`. Optional OCR, linguistics and speech-synthesis workers remain outside the core bundle.
- **Authenticated loopback transport:** `sidecar.rs` spawns `python -I -m lixity serve --_desktop-mode --host 127.0.0.1 --port 0`, sends a 256-bit secret and single-use handshake nonce over stdin (never CLI argv), and locks webview navigation strictly to the exact bound loopback origin.
- **Cross-platform parity in Rust:**
  - Native OS file/folder/save dialogs (`tauri-plugin-dialog`) & atomic streaming exports (`downloads.rs`)
  - Cross-platform 24 kHz mono PCM microphone recording & calibration (`audio_capture.rs` via `cpal` + `hound` across CoreAudio, WASAPI, PipeWire/ALSA)
  - Crash-safe child termination (`PR_SET_PDEATHSIG` on Linux, Job Objects on Windows, parent-PID watchdog on macOS)
  - Localized 7-language native OS menus generated from `src/lixity/locales/*.json` (`desktop/scripts/generate_menu_locales.py`)

## Build & verify locally

```bash
# 1. Build the Lixity wheel (if not already in dist/)
make build

# 2. Generate 7-language desktop menu catalogs
.venv/bin/python desktop/scripts/generate_menu_locales.py

# 3. Build an isolated local Python 3.12 core runtime bundle
.venv/bin/python desktop/scripts/build_runtime_bundle.py --auto-uv --output desktop/build/runtime/current

# 4. Verify the isolated runtime bundle under a stripped environment
.venv/bin/python desktop/scripts/smoke_desktop_runtime.py desktop/build/runtime/current

# 5. Check and test the Rust desktop host (requires rustup / cargo)
cargo check --manifest-path desktop/Cargo.toml
cargo test --manifest-path desktop/Cargo.toml
```
