# Security policy

Report suspected vulnerabilities privately to **mfahsold@googlemail.com**.
Include the installed version or commit, affected command or interface, operating
system and a minimal synthetic reproduction. Keep private manuscripts, signed
agreements, credentials and passphrases out of the report. Coordinate public
disclosure with the maintainer.

## Versions and scope

The [latest published release](https://github.com/mfahsold/lixity/releases/latest)
identifies the Python package for the CLI, API and local browser workspace.
Desktop test installers identify their source commit in their build manifest.
This policy also covers the current source. Include the exact desktop build
or installed package version when reporting a finding.
Fixes are developed on `main` and backports are evaluated case by case.

## Trust boundaries

- Built-in analysis and bundled interface assets run locally. Package
  installation, update checks and optional integrations have separate network
  paths. Live map basemaps can request OpenStreetMap tiles for the area in view.
- Manuscripts, portable dashboards, reading editions, exported PDFs and
  backups can contain private material. Review what an export includes
  before sharing. Use a private filesystem and OS storage protection for
  manuscripts, archives and recordings.
- Research storage retains approved originals, excerpts and revision history.
  Withdrawal preserves historical references. Supported source purge has a
  dry run and removes eligible stored objects. Retention requires permission,
  and redistribution is a separate decision.
  [Research usage and limits](docs/research/USAGE.md#limits)
- The NDA form previews draft text and returns a PDF or text download without
  writing a server-side agreement copy or recipient registry. Signing, consent,
  delivery and private storage are handled outside Lixity.
  [NDA agreements](docs/USAGE.md#nda-agreements)
- MCP tools are read-only and exchange results over local stdio. The connected
  client controls where it sends inputs and results.
  [MCP contract](docs/AGENTS.md#model-context-protocol-mcp-server)

## Local dashboard server baseline

The browser service is for one user on loopback. It trusts local processes
with access to its port or project files. Network hosting, shared authorization
and TLS are outside the supported server configuration.

- The server accepts only the `127.0.0.1` and `localhost` bind options. It
  rejects non-loopback `Host` names or a supplied port that differs from
  the listening port. API reads, writes and artifact requests require
  `Sec-Fetch-Site: same-origin` or `none` and a matching `Origin` when those
  headers are present. Local clients can omit the headers.
- Private responses use `Cache-Control: no-store` by default, MIME sniffing
  protection and a no-referrer policy. The live workspace uses a per-response
  script nonce, a narrowly scoped capture worklet, and a default-deny Content
  Security Policy. The editor frame stays same-origin. Served HTML artifacts
  are sandboxed with `default-src 'none'`. Browser microphone access is scoped
  to an eligible live authoring workspace and subject to device permissions.
- JSON POSTs require a bounded content length and object payload. The general
  limit is 5 MiB. Research image routes accept up to 32 MiB of JSON with
  separate decoded image limits of 16 MiB and 64 million pixels. Research
  media and chapter audio upload routes accept up to 72 MiB of JSON. The audio
  audit route allows a 138 MiB envelope and at most 96 MiB of decoded audio.
  Manuscript comparison accepts up to 48 MiB plus 1 KiB of JSON, with at most
  4 MiB per editor text after decoding. The trim route derives its envelope
  from at most 120 seconds of supported PCM input. The relevant upload routes
  validate base64 and the decoded format.
- Artifact delivery checks containment in the selected project's export root,
  uses bounded regular-file reads up to 200 MiB and checks file identity
  around the read. Retained PDF/video delivery can serve a single bounded
  byte range against the selected source version. Research archive restoration
  checks the declared regular-file inventory and checksums before publishing it.
  Verify provenance separately when accepting an archive.
- Project, research and manuscript context checks guard writes and exact
  reads against stale selections. A conflicting selection or revision returns
  HTTP 409 on those guarded routes. Context tokens identify state. Desktop
  session authentication has its own credential.
- Request threads use a 15-second socket timeout. The local revision store and
  derived research catalogue set SQLite `trusted_schema=OFF`. DOCX import
  bounds the source and streamed document XML to 32 MiB each, the ZIP to 4,096
  entries and converted UTF-8 to 16 MiB.
- Debug HTTP logs keep controlled route, method and status information and
  omit query strings and request content. Review captured stderr and worker
  diagnostics before sharing them.
  [Logging](docs/ARCHITECTURE.md#logging)

## Desktop host boundary

The Rust/Tauri host launches its bundled Python runtime on an OS-assigned
loopback port. A per-launch secret and single-use handshake nonce travel over
stdin. The WebView exchanges the nonce for an HttpOnly session cookie.
Privileged host requests use the separate secret, which stays in the host.
The host confines workspace navigation to the exact launched origin and opens
allowed HTTPS and mail links through the OS. Native commands use the
workspace capability and validate their inputs.
[Desktop architecture](docs/ARCHITECTURE.md#desktop-host-boundary)

Use the checksum and source revision supplied with each desktop test build.
Public desktop distribution requires qualified installers, including macOS
Developer ID signing and notarization and Windows publisher signing. The
public download catalog has no qualified installers. **Check for Updates**
reads the channel catalog. Installation is a separate, manual step.
[Installation and updates](docs/INSTALLATION.md#update-a-desktop-test-build) ·
[Release qualification](desktop/README.md#public-desktop-downloads)

## Speech and audio

Treat voice references, transcripts, passage direction and chapter audio as
private project data. Use microphone capture and retained reference recordings
with the speaker's permission. Render and export only to the configured target
and the chosen destination. Retained reference WAVs are bounded to 3 MiB.
Local inspection and optional tools have route-specific input limits.
[Audio workflow and providers](docs/AUDIO.md#audio-export-and-external-providers)

IMS-Toucan checks its PyTorch version before opening local checkpoints. The
current worker requires a stable release at or above 2.6.0 to address
CVE-2025-32434. Verify the separately managed runtime and its model assets.
[Worker setup](docs/INSTALLATION.md#ims-toucan-author-voice-and-phonetic-direction) ·
[PyTorch advisory](https://github.com/pytorch/pytorch/security/advisories/GHSA-53q9-r3pm-6pq6)

An explicitly configured speech provider can receive selected manuscript text
and, where the provider supports references, voice data and a transcript.
The OpenAI-compatible adapter accepts HTTPS or HTTP to an allowed local address,
rejects URL credentials, query strings and fragments, and checks destinations
for disallowed link-local, multicast and unspecified addresses. Its standard
client bypasses environment proxies and rejects redirects. Provider keys belong
in the configured environment variable. Audio POST failures can include a
diagnostic ID for matching redacted log records.
[Audio diagnostics](docs/AUDIO.md#match-an-audio-failure-to-a-log-entry)

## Optional Zotero boundary

The bridge uses the opt-in local HTTP API for an explicitly selected Zotero
library. Library metadata and attachment contents are untrusted input. Selected
attachments can be retained with permission. An additive migration export can
contain these private bytes and identity mappings. A Lixity research backup
covers retained evidence. Zotero library backup remains a separate operation.
[Zotero Desktop bridge](docs/research/USAGE.md#zotero-desktop-bridge)

## Dependencies and updates

The current source requires `pydantic>=2.4.0`, `rich>=13.0.0` and
`orjson>=3.11.6`, plus `tomli>=2.0.1` on Python 3.10. Isolated builds use
`setuptools>=84.1.0`. Dependabot groups monthly GitHub Actions, Python and
npm editor updates. The development dependency and pre-commit hook pin the same
Ruff version. Shipped browser assets have recorded versions, hashes and notices.
[Dependency workflow](.github/workflows/dependencies.yml) ·
[Vendor inventory](src/lixity/ui/assets/vendor/README.md)

`make audit` checks the runtime closure resolved for its interpreter.
When developing on Python 3.10, point `AUDIT_PYTHON` at a separate Python 3.11+
environment with pip-audit for `make audit` and `make release-check`. This lets
the auditor use a patched filelock. CI resolves the Python 3.10 runtime and
audits that exact hashed resolution with an isolated Python 3.12 auditor.
Use `pip-audit --path` for a specific installed environment. Audit the runtime,
development and optional integration environments separately.

## Repository and deployment hygiene

- Use private project storage, isolated development environments and reviewed
  release tags. Check the staged changes before publishing.
- Follow [the ignore rules](.gitignore) for local secrets, state and outputs.
  Existing tracked files need explicit review. Keep credential templates to
  placeholders and rotate credentials exposed in repository history.
- Publish only intended public or synthetic material to Pages. Review every
  export, log and screenshot for private manuscript data and metadata before
  sharing it.

Relevant checks cover [HTTP guards and serving](tests/test_server.py),
[debug logging](tests/test_server_debug.py), [desktop authentication](tests/test_server_desktop.py),
[Word input](tests/test_manuscript_import.py), [retained media](tests/test_research_media.py),
[archive restoration](tests/test_research_archive.py) and
[speech providers](tests/test_speech_providers.py).
