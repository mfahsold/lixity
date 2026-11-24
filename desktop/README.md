# Lixity desktop host

The Rust/Tauri v2 app opens the Lixity workspace in an operating-system window.
It uses the shared manuscript editor, analysis, and research views. The desktop
app is the intended first install for authors. The download guide shows the
current availability. Native installers are in qualification, and the existing
public release provides the Python package and its local browser workspace.
[Installation guide](../docs/INSTALLATION.md#packaging-direction)
· [Published releases](https://github.com/mfahsold/lixity/releases)

## Implemented

- One bundled Python 3.12 runtime serves the shared workspace on an
  authenticated loopback port. Additional windows use distinct workspace views
  on that port. [Desktop host boundary](../docs/ARCHITECTURE.md#desktop-host-boundary)
- System Status asks the Rust host to read the Python runtime inventory using
  the same authenticated loopback transport as window handshakes and the
  closing-time audio check. The shared dialog renders that inventory.
- The project name appears in the native window title. On macOS, the title bar
  shares the workspace background and uses the system window controls, gestures,
  Window menu and fullscreen command.
- Native menus in seven languages, folder and file dialogs, drag-and-drop,
  recent projects, macOS Dock reopen, window geometry, theme and zoom. Open
  requests wait until the workspace is ready. Settings, recent projects and
  window geometry use atomic file replacement. Reader text size, width,
  spacing, measurement, counted-text settings and paragraph comparison
  preferences survive changes of loopback port. Menus include the shared
  Analysis overview. HTTPS and mail links open through the operating system
  from both current-window and new-window links.
- The system menu and desktop welcome view use one native recent-project list.
  The desktop imports its previous browser-local entries once. Removing a
  project from the list or clearing history preserves its files.
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

## Download a test build

Sign in to GitHub, open the desktop-release workflow and select a successful
run for the commit you want to test. Under **Artifacts**, download the archive
for your operating system and processor. The workflow keeps these test builds
for 30 days. [Desktop release builds](https://github.com/mfahsold/lixity/actions/workflows/desktop-release.yml)
· [GitHub artifact download instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)

| Platform | Workflow artifact | Installer files |
| --- | --- | --- |
| macOS Apple Silicon | `desktop-installers-aarch64-apple-darwin` | `Lixity_VERSION_aarch64.dmg` |
| macOS Intel | `desktop-installers-x86_64-apple-darwin` | `Lixity_VERSION_x64.dmg` |
| Windows x64 | `desktop-installers-x86_64-pc-windows-msvc` | `Lixity_VERSION_x64-setup.exe`, `Lixity_VERSION_x64_de-DE.msi` or `Lixity_VERSION_x64_en-US.msi` |
| Linux x64 | `desktop-installers-x86_64-unknown-linux-gnu` | `Lixity_VERSION_amd64.deb` or `Lixity_VERSION_amd64.AppImage` |

Extract the ZIP and open its folder. The installer files,
`SHA256SUMS-TARGET.txt` and `desktop-artifacts-TARGET.json` sit together. The
filenames contain the version of the selected run in place of `VERSION`.
Verify the checksum from that folder before opening the installer.
New Windows and Linux test archives also include a platform-specific
**Start Here** HTML guide for offline setup.

- On macOS, verify the matching SHA-256 file before opening the disk image.
  Ad hoc images mount as **Lixity Test Build**, with **Start Here.html** inside.
  [macOS test build instructions](../docs/INSTALLATION.md#macos-desktop-dmg)
- On Windows, run `Get-FileHash -Algorithm SHA256 -LiteralPath .\Lixity_VERSION_x64-setup.exe`
  in PowerShell with the extracted installer filename. Compare the hash with
  that filename's entry in `SHA256SUMS-x86_64-pc-windows-msvc.txt`. Open the
  verified per-user setup executable or the MSI in your preferred installer language.
- On Linux, run `sha256sum -c SHA256SUMS-x86_64-unknown-linux-gnu.txt`. Open the
  verified `.deb` with your package installer on a Debian-based distribution.
  For the AppImage, give the file execute permission and launch it.
  [Troubleshooting missing runtime libraries](../docs/INSTALLATION.md#linux-desktop-test)
  [Linux test build instructions](../docs/guides/installation.html#linux)

Actions archives are temporary development builds. Public stable installers
are listed in the installation guide after release qualification. The same
guide links to the published browser package. [Installation guide](https://mfahsold.github.io/lixity/guides/installation.html#desktop)

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
The disk image mounts as **Lixity Test Build** and includes **Start Here.html**
for Finder. The output directory contains the DMG and its companion
`SHA256SUMS-TARGET.txt`. The final JSON reports both paths and the image's
SHA-256. The packager uses `diskutil image`
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
callbacks against a synthetic loopback fixture in WKWebView. It calls the
production Rust System Status command and checks that its authenticated
loopback request returns the expected inventory. It initializes the production
opener configuration and verifies the two license link destinations.
The runtime smoke checks Python startup and session authentication. Use the
manual checks below for the author workflow, operating-system interactions
and hardware.
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
  provenance as workflow artifacts. Set `notarize_macos=true` on dispatch
  for a Developer ID candidate. Both macOS jobs import the certificate into
  an isolated runner keychain and verify app and DMG notarization.
  [Desktop release workflow](../.github/workflows/desktop-release.yml)
- Both Linux installer jobs install the finished DEB in a clean Ubuntu 22.04
  container without recommended packages and check that its Rust host loads
  every shared library and its packaged runtime serves an authenticated first
  session. To repeat locally with Docker, run
  `bash desktop/scripts/smoke_linux_deb.sh /path/to/Lixity_VERSION_amd64.deb`.

## Remaining work before distribution

| Order | Work | Required evidence |
| --- | --- | --- |
| 1 | Verify the same candidate on the release matrix. | Rust checks, packaged runtime smoke, installer checksums and build provenance for all four targets. |
| 2 | Exercise the app as an author on clean desktop sessions. | Open and switch projects, type and undo with real IME and dead keys, use the keyboard and screen reader, follow an analysis finding to the manuscript, open help and license links, export a dossier PDF, and verify microphone permission, recording and playback. Cover WKWebView, WebView2 and WebKitGTK. Use a synthetic or public-domain manuscript. |
| 3 | Exercise installation, upgrade and rollback. | Test a fresh user without development tools, the operating system's trust checks, bundled runtime cleanup on exit, project and settings retention, and relaunch after upgrading or rolling back. Confirm any first-install dependencies, including the WebView2 bootstrapper on Windows. |
| 4 | Prepare distribution and first-run help. | Verify public macOS signing and notarization and Windows publisher signing. Show how to open an existing manuscript or try an example and explain how to diagnose unavailable optional tools. Publish platform requirements and installation steps with the verified artifacts. |

[Tauri distribution and signing guide](https://tauri.app/distribute/#signing)

### Public desktop downloads

The [installation guide](../docs/guides/installation.html#desktop) reads
`docs/desktop-downloads.json`. A public desktop release uses one reviewed set of
installers and Python archives for the same commit. Prepare a new version
following the [release procedure](../CONTRIBUTING.md#preparing-a-release).

Before requesting a signed candidate build, check which repository-level
signing settings are present. Run this read-only command from the checkout
with an authenticated GitHub CLI:

```sh
python scripts/release_channels.py doctor --root . --repo mfahsold/lixity --desktop-signing
```

Read `desktop_signing` in the report. Empty lists mean the required names are
present. A `null` list means GitHub could not confirm that category. The check
reads names only. A signed candidate run verifies whether the configured
credentials are usable.

#### Configure macOS signing

Set these credentials in GitHub Actions secrets before dispatching
`desktop-release.yml` with `notarize_macos=true`.

| Secret | Value |
| --- | --- |
| `APPLE_DEVELOPER_ID_P12_BASE64` | Base64 of the Developer ID Application certificate and private key exported as PKCS#12 |
| `APPLE_DEVELOPER_ID_P12_PASSWORD` | Password protecting the PKCS#12 export |
| `APPLE_NOTARY_KEY_P8_BASE64` | Base64 of the notarization API private key |
| `APPLE_NOTARY_KEY_ID` and `APPLE_NOTARY_ISSUER_ID` | API key ID and issuer from App Store Connect |

The signer must belong to the authorized Apple Developer team. The workflow
removes the isolated keychain at the end of the job.
[Developer ID](https://developer.apple.com/developer-id/) ·
[Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution/)

#### Configure Windows signing

Use an Azure Artifact Signing account with a Public Trust certificate profile.
Grant the Entra application the **Artifact Signing Certificate Profile Signer**
role scoped to that certificate profile. Set the GitHub repository variables
`LIXITY_AZURE_SIGNING_ENDPOINT`, `LIXITY_AZURE_SIGNING_ACCOUNT` and
`LIXITY_AZURE_SIGNING_PROFILE`. Set `AZURE_TENANT_ID`, `AZURE_CLIENT_ID` and
`AZURE_CLIENT_SECRET` as Actions secrets for that application. Dispatch
`desktop-release.yml` with `sign_windows=true`. Credentials are scoped to the
opt-in Windows signing steps. Tauri invokes the signing command during
bundling, and the workflow checks the timestamped Authenticode signatures
before it records installer checksums.
[Azure Artifact Signing setup](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart) ·
[Tauri Windows signing](https://v2.tauri.app/distribute/sign/windows/)

#### Review and publish one candidate

1. Dispatch the desktop build with `notarize_macos=true` and
   `sign_windows=true` at the reviewed release commit on `main`. Download the
   combined signed artifact from that exact successful run. Test runs publish
   their combined output as `lixity-desktop-test-bundle`.
   Set `release_tag`, `release_sha` and `desktop_run` to the prepared version,
   full commit SHA and GitHub Actions run ID.

   ```sh
   gh run download "$desktop_run" --name lixity-desktop-release-bundle --dir desktop-candidate
   python -m desktop.scripts.qualify_desktop_release --artifacts-dir desktop-candidate \
     --tag "$release_tag" --source-sha "$release_sha" --template > desktop-qualification.json
   ```

2. Verify each exact installer on a fresh user environment. On macOS, check
   Developer ID, the notarization ticket and Gatekeeper on both architectures.
   On Windows, verify Authenticode on the installer and installed executable,
   including the two MSI languages and the per-user EXE. On Linux, check Debian
   package dependencies and run the AppImage without the CI extraction override.
   Install, open a synthetic project, upgrade and roll back. Check that the
   project and preferences survive each transition. Record the OS version and
   the review evidence for each SHA-256 in the generated JSON.
   [Windows signature verification](https://learn.microsoft.com/en-us/windows/win32/seccrypto/using-signtool-to-verify-a-file-signature)

3. Run the same qualification and build-provenance checks used by the tag
   workflow. The command stages the exact eligible files in an empty location.

   ```sh
   python scripts/release_channels.py stage-desktop --root . --tag "$release_tag" \
     --expected-commit "$release_sha" --repo mfahsold/lixity \
     --artifacts-dir desktop-candidate --qualification desktop-qualification.json \
     --desktop-dist desktop-reviewed
   ```

4. Set `DESKTOP_RELEASE_TAG`, `DESKTOP_RELEASE_RUN_ID` and
   `DESKTOP_RELEASE_QUALIFICATION` for the reviewed tag, run and JSON.
   The qualification receipt becomes a public release asset, so use
   publishable review notes and evidence references. Push the reviewed tag
   through the regular release procedure. The workflow stages the same
   installer bytes, validates the combined draft and verifies the immutable
   release after publication.

5. From the tagged checkout, record a reviewed copy of the public catalog
   from the immutable release. The catalog command checks the remote tag,
   downloads the desktop assets, and verifies GitHub digests, the qualification
   receipt and hosted build attestations before writing the output.

```sh
catalog_dir=$(mktemp -d)
python scripts/release_channels.py record-desktop-catalog --root . \
  --tag "$release_tag" --expected-commit "$release_sha" --repo mfahsold/lixity \
  --catalog-output "$catalog_dir/desktop-downloads.json"
```

Copy that file to `docs/desktop-downloads.json` in the publishing checkout.
Review the diff together with the generated installation guide.

```sh
cp "$catalog_dir/desktop-downloads.json" docs/desktop-downloads.json
make docs-sync
make docs-check
```

Verify the published catalog and installation guide from the Pages publishing
commit after deploying that checkout. Follow the
[Pages publication procedure](../CONTRIBUTING.md#publish-and-verify-pages).

### Update delivery

Use the same distribution channel for updates as for installation. Direct
downloads currently use a manual replacement of the verified desktop bundle.
Homebrew, WinGet and repository-installed Linux packages should be updated by
their package managers. A separate `uv` installation uses its own update path.
[User update instructions](../docs/INSTALLATION.md#updates-and-removal)

To replace an installed macOS development build, commit the tested checkout,
save open work and quit Lixity. Run the local build with explicit update intent.

```sh
.venv/bin/python desktop/scripts/build_macos_app.py --offline --dmg --update-installed
```

The command verifies the app and disk image before applying the update. It
compares the installed version and code signature, stages the replacement
and preserves the old bundle at the backup path in `local_update`. It can
replace a different build of the same test version. The app needs to be closed
and both bundles must have ad-hoc signatures. If the replacement fails
verification, the previous bundle is restored. Reopen Lixity and check the
selected project. For a manual rollback, quit Lixity and use the backup
listed in `rollout.json`.
**Tools → System Status & Extensions** shows the source commit for builds
installed with this command.

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
