# Lixity Desktop Host (Rust / Tauri v2)

Cross-platform native desktop host for **macOS**, **Windows**, and **Linux** sharing the
single canonical Lixity analysis engine and UI. The host is unreleased.

## Architecture

- **Rust host (`src-tauri/`)**: launches the bundled relocatable Python 3.12 runtime on an
  ephemeral loopback port (`127.0.0.1:0`), passes a per-launch 256-bit secret and single-use
  handshake nonce over `stdin`, authenticates the WebView via `HttpOnly` session cookie, and
  exposes a minimal frozen `window.lixityDesktop` bridge:
  - Native OS folder/file dialogs (`pick_project_directory`, `pick_import_file`)
  - Atomic blob and streaming loopback exports with SHA-256 verification (`save_blob`, `save_export_stream`)
  - Cross-platform interactive & timed 24 kHz mono PCM microphone capture and level calibration (`cpal` + `hound`)
  - 7-language native OS menu bar with dynamic Recent Projects submenu (`generated/menu-locales.json`)
  - Direct access to the shared Analysis overview from View, with native page
    zoom and a theme preference that persists across desktop sessions
  - Drag-and-drop project/manuscript opening, single-instance handoff, macOS Dock reopen, window geometry persistence, and dirty-editor/active-audio close guards
  - Explicit opt-in GitHub Releases version check (zero automatic background traffic)
- **Isolated Python runtime (`scripts/build_runtime_bundle.py`)**: builds a self-contained
  relocatable `python-build-standalone` 3.12 runtime plus Lixity and its core dependencies.
  `scripts/smoke_desktop_runtime.py` verifies isolated operation with `python -I -B`
  and checks that running the app leaves bundled Python bytecode unchanged.

## Native Installers

| Platform | Release build matrix | Additional packaging assets |
| --- | --- | --- |
| macOS (Apple Silicon and Intel) | `.dmg` containing `Lixity.app` | Homebrew Cask template |
| Windows (x64) | NSIS `.exe` (seven languages, per-user), WiX `.msi` | WinGet manifest templates |
| Linux (x64) | `.deb`, `.AppImage` | RPM configuration, Flatpak manifest, AppStream metadata |

The isolated runtime manifest also describes ARM64 Windows and Linux targets.
Those targets, RPM and Flatpak require their own installer verification.
Clean-machine installation, upgrades, rollback and distribution signatures
remain release gates.

## Local Build & Verification

```sh
# 1. Build Lixity wheel and isolated desktop runtime bundle
python -m build --wheel --outdir dist
python desktop/scripts/build_runtime_bundle.py --auto-uv --output desktop/build/runtime/current
python desktop/scripts/smoke_desktop_runtime.py desktop/build/runtime/current

# 2. Verify menu locales and icons
python desktop/scripts/generate_menu_locales.py --check
python desktop/scripts/generate_desktop_icons.py --check

# 3. Test, lint and bundle native installers (requires Rust stable + tauri-cli v2)
cargo test --locked --manifest-path desktop/Cargo.toml --all-targets
cargo clippy --locked --manifest-path desktop/Cargo.toml --all-targets -- -D warnings
(cd desktop && cargo tauri build -- --locked)

# 4. Verify installer containers and emit SHA256SUMS
python desktop/scripts/verify_desktop_artifacts.py desktop/target/release/bundle --target "$(rustc -vV | awk '/host:/ {print $2}')"
```

## CI Workflows

- `.github/workflows/desktop.yml` — runs isolated runtime smoke tests, `cargo test`, and
  `cargo clippy -- -D warnings` on Ubuntu 22.04, macOS, and Windows. Dispatch with
  `build_bundle=true` to also compile, verify, and upload native installers.
- `.github/workflows/desktop-release.yml` — builds and verifies the release matrix,
  combines `SHA256SUMS-desktop.txt`, renders Homebrew and WinGet manifests, and
  generates GitHub build provenance attestations. The workflow packages macOS
  disk images after signing the embedded app. The build outputs are CI artifacts.
