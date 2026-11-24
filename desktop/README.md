# Lixity desktop host

The Rust/Tauri v2 app opens the Lixity workspace in an operating-system window.
It uses the shared manuscript editor, analysis, and research views. The desktop
host and native installers are under development. The published installation
path is the Python package and its local browser workspace.
[Installation guide](../docs/INSTALLATION.md#packaging-direction)
· [Published releases](https://github.com/mfahsold/lixity/releases)

## Implemented

- One bundled Python 3.12 runtime serves the shared workspace on an
  authenticated loopback port. Additional windows use distinct workspace views
  on that port. [Desktop host boundary](../docs/ARCHITECTURE.md#desktop-host-boundary)
- The project name appears in the native window title. On macOS, the title bar
  shares the workspace background and uses the system window controls, gestures,
  Window menu and fullscreen command.
- Native menus in seven languages, folder and file dialogs, drag-and-drop,
  recent projects, macOS Dock reopen, window geometry, theme and zoom. Open
  requests wait until the workspace is ready. Settings, recent projects and
  window geometry use atomic file replacement. Menus include the shared
  Analysis overview. HTTPS and mail links open through the operating system
  from both current-window and new-window links.
- Native save dialogs, atomic exports and streamed manuscript PDFs, dossier
  PDFs and reading-site ZIPs with SHA-256 receipts. Analysis, research records
  and document bytes remain the responsibility of the shared application.
- Native 24 kHz mono PCM recording and level calibration for the teleprompter
  and Author's voice. Interactive takes belong to their window and stop at
  30 seconds. Closing a window can prompt when there are unsaved edits or
  active audio. The last workspace checks the audio queue off the window
  event loop and asks before closing if the queue status is unavailable.
- A user-triggered check for public desktop packages and a manual install path.
  [Update a desktop test build](../docs/INSTALLATION.md#update-a-desktop-test-build)

## Native installers

| Platform | Release build matrix | Other packaging assets |
| --- | --- | --- |
| macOS (Apple Silicon and Intel) | `.dmg` containing `Lixity.app` | Homebrew Cask template |
| Windows (x64) | NSIS per-user `.exe` with seven installer languages, WiX `.msi` with German and English | WinGet manifest templates |
| Linux (x64) | `.deb` and `.AppImage` | RPM configuration, Flatpak manifest, AppStream metadata |

The runtime manifest also describes Windows and Linux ARM64. Those targets,
RPM and Flatpak await installer qualification.

## Local build and verification

Use the checkout's development environment, Rust stable with Clippy,
Node.js/npm, `uv` with managed Python 3.12, and the Tauri prerequisites for your
OS. Start from the checkout root.
[Development setup](../CONTRIBUTING.md#development-setup)
· [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)

### macOS app bundle

```sh
.venv/bin/python desktop/scripts/build_macos_app.py --offline
```

The script builds a fresh wheel and runtime, packages the app, applies an ad-hoc
signature and smoke-tests the runtime embedded in the signed bundle. Its final
JSON reports the app path and runtime smoke result. Use `--offline` once build
inputs have been cached. Omit it on an initial build that needs to fetch
dependencies. Add `--dmg` to build a disk image with the same packager as CI.
It mounts the image read-only, verifies the embedded signature and starts a
synthetic authenticated workspace from the embedded runtime. The smoke imports
a synthetic manuscript from the welcome screen into a temporary user directory.
The disk image includes the offline **Start Here – Hier starten** guide for Finder.
The final JSON
also includes the image path and SHA-256. The packager uses `diskutil image`
where it supports building from a folder. It uses `hdiutil` on older macOS
versions. Quit any running copy before launching the reported bundle in Finder
or with `open "/path/to/Lixity.app"`. To open a particular project, append
`--args "/path/to/project/lixity.toml"` to the `open` command. A project folder
or manuscript path also works. Development builds can share a version number
with the installed app. Use the exact reported bundle path when retesting a
fix. The app starts and owns its bundled runtime.

### Rust and native WebView checks

On a fresh checkout, prepare `desktop/build/runtime/current` for the direct
Cargo commands. The development app builder creates its runtime separately.
Run the following with the checkout development environment active.

```sh
uv python install 3.12
python scripts/check_release.py --build
python desktop/scripts/build_runtime_bundle.py --auto-uv --output desktop/build/runtime/current
python desktop/scripts/smoke_desktop_runtime.py desktop/build/runtime/current
```

```sh
cargo test --locked --manifest-path desktop/Cargo.toml --all-targets
cargo clippy --locked --manifest-path desktop/Cargo.toml --all-targets -- -D warnings
```

On macOS, run the native WebView smoke on a logged-in desktop session.

```sh
cargo run --locked --manifest-path desktop/Cargo.toml --features webview-smoke --example webview_smoke
```

The smoke exercises the generated workspace capability, bridge and navigation
callbacks against a synthetic loopback fixture in WKWebView. The runtime
smoke checks Python startup and session authentication. Use the manual checks
below for the author workflow, operating-system interactions and hardware.
Chromium and browser WebKit tests cover the shared UI.
[Browser verification](../tests/browser/README.md)

### Installer workflows

- The desktop checks run the isolated runtime smoke, Rust tests, Clippy and
  dependency checks. Dispatch with
  `build_bundle=true` to also build, verify and upload installers on three OSes.
  [Desktop checks workflow](../.github/workflows/desktop.yml)
- The desktop release build covers the four targets above. Its Apple packaging
  steps sign the embedded app before building the disk image and smoke-test the
  runtime from the mounted image. The build uploads
  verified installers, checksums, Homebrew and WinGet manifests and build
  provenance as workflow artifacts. Developer ID signing and notarization
  require configured credentials.
  [Desktop release workflow](../.github/workflows/desktop-release.yml)

## Remaining work before distribution

| Order | Work | Required evidence |
| --- | --- | --- |
| 1 | Verify the same candidate on the release matrix. | Rust checks, packaged runtime smoke, installer checksums and build provenance for all four targets. |
| 2 | Exercise the app as an author on clean desktop sessions. | Open and switch projects, type and undo with real IME and dead keys, use the keyboard and screen reader, follow an analysis finding to the manuscript, open help and license links, export a dossier PDF, and verify microphone permission, recording and playback. Cover WKWebView, WebView2 and WebKitGTK. Use a synthetic or public-domain manuscript. |
| 3 | Exercise installation, upgrade and rollback. | Test a fresh user without development tools, the operating system's trust checks, bundled runtime cleanup on exit, project and settings retention, and relaunch after upgrading or rolling back. Confirm any first-install dependencies, including the WebView2 bootstrapper on Windows. |
| 4 | Prepare distribution and first-run help. | Verify public macOS signing and notarization and Windows publisher signing. Show how to open an existing manuscript or try an example and explain how to diagnose unavailable optional tools. Publish platform requirements and installation steps with the verified artifacts. |

[Tauri distribution and signing guide](https://tauri.app/distribute/#signing)

### Public desktop downloads

The [Pages installation guide](../docs/guides/installation.html#desktop) uses the
reviewed catalog at `docs/desktop-downloads.json`. Its empty catalog directs
readers to the published browser app while native builds are in testing.
After native release qualification and approved publication, use the flattened
workflow artifact directory with the per-target manifests and
`SHA256SUMS-desktop.txt`. From the checkout root, record the public release:

```sh
gh api repos/mfahsold/lixity/releases/tags/vX.Y.Z > /tmp/lixity-release.json
python -m scripts.desktop_downloads --release-info /tmp/lixity-release.json --artifacts-dir dist-desktop
make docs-sync
make docs-check
```

The catalog tool compares the installers and checksum list with the attached
GitHub assets by name, size and SHA-256. It expects a public stable release and
all supported targets. Check platform signatures and attestations during
release qualification. Review the catalog and generated install guide together
before the authorized Pages deployment.

### Update delivery

Use the same distribution channel for updates as for installation. Direct
downloads currently use a manual replacement of the verified desktop bundle.
Homebrew, WinGet and repository-installed Linux packages should be updated by
their package managers. A separate `uv` installation uses its own update path.
[User update instructions](../docs/INSTALLATION.md#updates-and-removal)

Keep app-managed installation behind a release gate. The Tauri v2 Updater
supports signed macOS app archives, Windows NSIS/MSI installers and Linux
AppImages. OS publisher signing and macOS notarization are additional platform
checks. Before enabling the updater for direct desktop downloads:

1. Protect and back up the release-only signing key outside the repository.
   Embed the matching public key in the installed app. Serve release metadata
   over HTTPS and generate one stable update entry per qualified OS and
   architecture from the published, signed release assets.
2. Require explicit confirmation before replacing program files or restarting.
   Reuse the editor and audio close guards and leave installation ownership with
   the package manager for its channels.
3. Test an upgrade from an already installed build on each supported target.
   Cover invalid signatures, interrupted downloads, a retry and manual rollback
   to a compatible verified build. Verify drafts, project settings, research and
   audio output with a synthetic project.

[Tauri signing and verification](https://v2.tauri.app/plugin/updater/#signing-updates)
· [Tauri release metadata](https://v2.tauri.app/plugin/updater/#static-json-file)
· [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution)

## Host follow-ups

- Extend teleprompter recording past the current 30-second cap once the host can
  hand off bounded on-disk audio and clean it up after saving or cancelling.

Any move of the shared analysis engine to Rust starts with an end-to-end
measurement and a parity check at the existing boundary.
[Rust analysis evaluation](../docs/RUST_EVALUATION_RFC.md)
