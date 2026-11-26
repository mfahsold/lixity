# Lixity desktop host

The Rust/Tauri v2 app opens the Lixity workspace in an operating-system window.
It uses the shared manuscript editor, analysis, and research views. Choose your
platform in the download guide to install it. Desktop downloads currently lead
to test builds. The app includes the runtime it needs.
[Download Lixity](https://lixity.de/guides/installation.html#desktop)
· [Installation reference](../docs/INSTALLATION.md#download-the-desktop-app)

| Build | Where to find it | How to verify its identity |
| --- | --- | --- |
| Local macOS development build | Checkout build output or the app replaced by the local rollout command | Exact checkout commit for a rollout, app bundle path and ad-hoc code signature |
| Hosted desktop test build | Selected GitHub Actions run | Run source commit, platform target, installer SHA-256 and build manifest |
| Public desktop installer | Published release and desktop download catalog | Published tag, installer SHA-256, attestation and accepted platform trust evidence |

The [published browser app and CLI](../docs/INSTALLATION.md#cli-current-release)
are available as an alternative.

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
  and Author's voice. Interactive takes belong to their window. Author's voice
  passes the project's saved duration to the native host, with a maximum of
  60 seconds. Closing a window can prompt when there are unsaved edits or
  active audio. The last workspace checks the audio queue off the window
  event loop and asks before closing if the queue status is unavailable.
- A user-triggered check for public desktop packages and a manual install path.
  [Update a desktop test build](../docs/INSTALLATION.md#update-a-desktop-test-build)

## Native installers

| Platform | Installer build targets | Other packaging assets |
| --- | --- | --- |
| macOS (Apple Silicon and Intel) | `.dmg` containing `Lixity.app` | Homebrew Cask template |
| Windows (x64) | NSIS per-user `.exe` with seven installer languages, WiX `.msi` with German and English | WinGet manifest templates |
| Linux (x64) | `.deb` and `.AppImage` | RPM configuration, Flatpak manifest, AppStream metadata |

The runtime manifest also describes Windows and Linux ARM64. Those targets,
RPM and Flatpak await installer qualification.

## Download a test build

1. Choose the archive for your computer in the
   [desktop downloads](https://lixity.de/guides/installation.html#desktop).
   Preview prereleases download directly without a GitHub account; Actions test
   archives require signing in to GitHub.
2. Extract it if it came in a ZIP and use the
   [installer checker](https://lixity.de/guides/installation.html#installer-check)
   to compare the installer with the companion SHA-256 list on your computer.
   On macOS, open the DMG and drag Lixity to **Applications**. On Windows,
   open the `-setup.exe`. On Debian or Ubuntu, open the `.deb` with a
   graphical package installer, or run the AppImage using its file properties.
3. Open Lixity and choose **Try the example offline**.
   [First session](../docs/ONBOARDING.md)

<details>
<summary>Find a different test run and identify its files</summary>

To find a different test build, open the desktop-release workflow, choose a
successful run for the intended commit, and download its archive under
**Artifacts**. The workflow keeps test builds for 30 days.
[Desktop release builds](https://github.com/mfahsold/lixity/actions/workflows/desktop-release.yml)
· [GitHub artifact download instructions](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/download-workflow-artifacts)

| Platform | Workflow artifact | Installer files | Setup |
| --- | --- | --- | --- |
| Mac with Apple silicon | `Lixity-Desktop-Mac-Apple-Silicon` | `Lixity_VERSION_aarch64.dmg` | [macOS](../docs/INSTALLATION.md#macos-desktop-dmg) |
| Mac with an Intel processor | `Lixity-Desktop-Mac-Intel` | `Lixity_VERSION_x64.dmg` | [macOS](../docs/INSTALLATION.md#macos-desktop-dmg) |
| Windows 64-bit Intel or AMD | `Lixity-Desktop-Windows-64-bit` | `Lixity_VERSION_x64-setup.exe`, `Lixity_VERSION_x64_de-DE.msi` or `Lixity_VERSION_x64_en-US.msi` | [Windows](../docs/INSTALLATION.md#windows-desktop-test) |
| Linux 64-bit Intel or AMD | `Lixity-Desktop-Linux-64-bit` | `Lixity_VERSION_amd64.deb` or `Lixity_VERSION_amd64.AppImage` | [Linux](../docs/INSTALLATION.md#linux-desktop-test) |

Older runs display the full build target in names such as
`desktop-installers-aarch64-apple-darwin`. The download guide links to each
archive by its artifact ID, and the installer files retain their verified names.

Extract the ZIP to keep the installer, `SHA256SUMS-TARGET.txt` and
`desktop-artifacts-TARGET.json` together. Use the platform setup instructions
to verify the checksum before opening the installer. An ad-hoc DMG contains
**Start Here.html**. Windows and Linux test archives from the desktop-release
workflow include a platform-specific offline start guide on the test path.

Keep the run ID, source commit, target and SHA-256 together if you report a
finding. Different test builds can print the same version.

</details>

To update the installation guide's test links, set `docs/desktop-test-build.json`
to one reviewed successful run. Match each target to its artifact ID on that run
and use the earliest expiration of the four archives. Populate `installers`
from the verified files in the same run, with their exact sizes and SHA-256
digests. To offer direct, login-free, non-expiring downloads for unsigned/ad-hoc
preview builds before signing credentials are configured, dispatch
`desktop-release.yml` on `main` with `publish_preview_release=true` and record
the resulting `desktop-preview-vX.Y.Z` tag as `"preview_release_tag"` in
`docs/desktop-test-build.json`. Run `make docs-sync` and `make docs-check`. The
public download catalog is filled through the separate
[qualification and publication procedure](#public-desktop-downloads).

## Local build and verification

Use the checkout's development environment, Rust stable with Clippy,
Node.js/npm, `uv` with managed Python 3.12, and the Tauri prerequisites for your
OS. Start from the checkout root.
[Development setup](../CONTRIBUTING.md#development-setup)
· [Tauri prerequisites](https://v2.tauri.app/start/prerequisites/)

Desktop CI and release builds share the [runtime build action](../.github/actions/build-desktop-runtime/action.yml).
It installs a pinned `uv` and provisions the selected CPython 3.12 patch in the
runner's temporary directory. It builds the wheel with `uv build` and
smoke-tests the bundled runtime. Review both pins together when updating the
standalone Python build used by the installer matrix.

### macOS app bundle

```sh
.venv/bin/python desktop/scripts/build_macos_app.py --offline
```

The script builds a fresh wheel and runtime, packages a local development app,
applies an ad-hoc signature and smoke-tests the embedded runtime. Its final
JSON reports the app path and runtime smoke result. Use `--offline` once build
inputs are cached. Omit it on an initial build that needs to fetch dependencies.
Use the same absolute `CARGO_TARGET_DIR` for temporary worktrees to reuse one
compilation cache. The build locks that cache through app assembly and copies
each completed bundle to its own build directory under the current checkout.
The default cache is `desktop/build/macos-local/target`.
Add `--dmg` to package the app with the CI disk-image script. It mounts the
image read-only, verifies the embedded signature and exercises the embedded
runtime again. The runtime smoke checks an authenticated welcome workspace
and imports synthetic manuscript bytes through its local HTTP API into a
temporary user directory. The native WebView check exercises the window and
bridge separately.
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
callbacks against a synthetic loopback fixture in WKWebView. It checks the
production Rust System Status command, its authenticated loopback inventory,
and the recording limit passed through the native bridge. It initializes the
production opener configuration and verifies the two license link destinations.
The runtime smoke checks Python startup and session authentication. Use the
manual checks below for the author workflow, operating-system interactions
and hardware.
Chromium and browser WebKit tests cover the shared UI.
[Browser verification](../tests/browser/README.md)

### Linux WebKitGTK smoke

This optional check uses the exact installed DEB from a selected build. Use its
matching source checkout and a disposable Ubuntu 22.04 x86-64 VM or runner.
Verify the installer SHA-256 before installing it with APT. Install these QA
tools in the same environment:

```sh
sudo apt install xvfb xauth openbox xdotool dbus-x11 at-spi2-core \
  python3-gi python3-pyatspi gir1.2-webkit2-4.1 iproute2
```

Run as an ordinary user. The script uses `sudo` to create a private network
namespace with only loopback, then runs the probes as that user:

```sh
bash desktop/scripts/smoke_linux_webview.sh \
  /path/to/Lixity_VERSION_amd64.deb EXPECTED_SHA256 /path/to/new-evidence-directory
```

The smoke verifies the installer digest and compares the installed payload with
the package's file inventory. A stock WebKitGTK page supplies the rendering
control. A fresh Lixity session must paint the welcome action, show the import
preview before writing project files, and display the first chapter after
confirmation. The saved manuscript must match the bundled example byte for
byte. The evidence directory receives the environment, screenshots,
accessibility trees and probe logs. Inspect the screenshots for layout issues.

The check uses Xvfb and software rendering inside the test session. Clean APT
dependency verification, physical desktop graphics, Wayland and AppImage FUSE
remain separate checks.

### Installer workflows

Everyday macOS Rust tests, Clippy, WKWebView smoke and local `.app`/`.dmg`
builds run locally (see [macOS app bundle](#macos-app-bundle) and
[Rust and native WebView checks](#rust-and-native-webview-checks)). Hosted
desktop workflows are manual `workflow_dispatch` runs reserved for cross-OS
verification and installer builds (Linux, Windows, Intel Mac), signing and
hosted build provenance attestations:

- The desktop checks workflow runs the isolated runtime smoke, Rust tests,
  Clippy and `cargo-deny` dependency checks on Linux, macOS and Windows.
  Dispatch with `build_bundle=true` to also build, verify and upload installers
  on all three OSes.
  [Desktop checks workflow](../.github/workflows/desktop.yml)
- The desktop release build targets all four rows. Apple jobs sign the app
  before creating its DMG and smoke-test the runtime from the mounted image.
  Each run records the installer checksums and build provenance and produces
  Homebrew and WinGet manifests. Test runs can use ad-hoc macOS signing and
  Windows installers without a publisher signature. Request both signing
  options for [public desktop qualification](#public-desktop-downloads).
  [Desktop release workflow](../.github/workflows/desktop-release.yml)
- Both installer workflows retry a failed per-platform upload once on the same
  runner using the already verified files. A second upload failure fails the
  platform job. The release workflow checks the complete installer inventory
  and checksums again before attesting the combined bundle.
- Both Linux installer jobs install the finished DEB in a clean Ubuntu 22.04
  container without recommended packages and check that its Rust host loads
  every shared library and its packaged runtime serves an authenticated first
  session. To repeat locally with Docker, run
  `bash desktop/scripts/smoke_linux_deb.sh /path/to/Lixity_VERSION_amd64.deb`.

## Remaining work before distribution

Attach results to the exact source commit and installer SHA-256. The hosted
build, installed runtime, system WebView and platform trust each have their
own evidence.

| Check | How to establish it | Further evidence for public distribution |
| --- | --- | --- |
| Build and contents | Match the successful matrix run, installer manifest, signature state and checksum to the selected candidate. | Review the release-eligible bundle and attestation for that commit. |
| Installed runtime | Verify synthetic offline analysis and welcome import from the packaged Python, session authentication and listener cleanup. Use the clean Ubuntu container check for the DEB dependencies. | Retry on fresh user systems without development tools. Verify first-install WebView2 or Linux package dependencies and exercise a real AppImage launch. |
| Native author workflow | Use the WKWebView smoke on macOS and the installed DEB WebKitGTK probe on Linux. Chromium and browser WebKit check the shared interface. | Exercise WKWebView, WebView2 and WebKitGTK on the relevant platforms. Write and undo using an IME and dead keys, use the screen reader, follow passage evidence, open help, export a dossier and verify microphone permission, recording and playback. |
| Trust, upgrade and rollback | Validate platform trust for the exact artifacts. Upgrade and roll back the same synthetic project. | Record Developer ID, notarization and Gatekeeper on both Mac architectures, Windows publisher signatures, and the project, settings and research readback after each transition. |

The `4efec747` candidate for v0.9.3 passed a local Apple Silicon development
rollout. The mounted DMG and installed Python 3.12.16 runtime passed the
synthetic import and analysis checks. The installed host opened a synthetic
workspace and closed its loopback listener on exit. The rollout preserved a
verified v0.9.2 backup. CoreAudio enumeration returned one input on that host.
Actual recording, fresh-user platform trust and each hosted target have
their own qualification evidence.

Record the OS and WebView versions, graphics mode, installer SHA-256, install
scope and author workflow results in the existing qualification receipt.
Use a synthetic or public-domain manuscript and preserve the same saved text,
preferences and archived evidence for the upgrade and rollback readbacks.

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

#### Local macOS development rollout

Commit the candidate and use a clean checkout of that exact commit (or a clean
temporary `git worktree` reusing `CARGO_TARGET_DIR` when the main checkout has
unrelated local edits). Save open work, finish or cancel active and queued
audio, then quit Lixity and its bundled engine. Run the local build with
explicit update intent.

```sh
.venv/bin/python desktop/scripts/build_macos_app.py --offline --dmg --update-installed
```

The command verifies the app and disk image before replacing the existing
ad-hoc-signed bundle at `/Applications/Lixity.app`. It can replace a different
build of the same test version. The `local_update` result records the commit,
both code hashes and the backup path in `rollout.json`. If the staged or
installed bundle fails verification, the previous bundle is preserved or
restored. Keep the backup for manual rollback.

After the replacement, verify the installed bundle and launch a synthetic
project. Open **Tools → System Status & Extensions** to confirm the source
commit and bundled runtime. Check a local analysis result and confirm that
the bundled engine exits when you quit. Desktop and browser services have
separate lifecycles. For manual rollback, quit the app before restoring the
verified backup listed in `rollout.json`.
[Desktop logs](../docs/INSTALLATION.md#find-the-desktop-logs)

#### App-managed updates

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

- Extend teleprompter recording beyond one minute once the host can
  hand off bounded on-disk audio and clean it up after saving or cancelling.

Any move of the shared analysis engine to Rust starts with an end-to-end
measurement and a parity check at the existing boundary.
[Rust analysis evaluation](../docs/RUST_EVALUATION_RFC.md)
