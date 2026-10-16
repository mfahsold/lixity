# Security policy

Report suspected vulnerabilities privately to **mfahsold@googlemail.com**.
Include the version, command, environment and a minimal synthetic reproduction.
Do not send real manuscripts, NDA records, passphrases or credentials. Avoid
publishing exploit details before maintainers can assess the report.

## Versions and scope

Reports should identify the exact tag or commit; see the
[current release](https://github.com/mfahsold/lixity/releases/latest). Fixes are developed
on `main`; backports are evaluated case by case. A development version is not
a production-support guarantee.

## Trust boundaries

- The analysis engine runs locally without a cloud service. Installation and
  update tools access package/source hosts; project adapters may use networks.
- Analysis commands read manuscripts. `build`/`dashboard` write generated
  artifacts; marker APIs return modified text for the caller to persist.
- Dashboard HTML embeds manuscript content, titles and potentially editorial
  notes. Treat it as private even without the original Markdown file.
- Renderers escape text and use text-based tooltips; this reduces specific XSS
  risks, not a blanket guarantee for every renderer or host integration.
- The bundled local HTTP server is a separate boundary from the pure analysis
  engine. NDA encryption, publication exports and document delivery belong to
  project adapters; review those integrations independently. The baseline
  below names its concrete controls and their limits.
- Custom regular expressions and large inputs can consume CPU or memory.
  Hosts accepting untrusted inputs should impose size, time and concurrency
  limits and must not execute unrestricted user-supplied expressions.
- Atomic file replacement protects write integrity, not confidentiality or
  authorization. Callers choose writable destinations and file permissions.
- The experimental research pilot retains original text/PDF files and excerpts in
  `research/`. Treat both as private. Explicit retention confirmation does not
  grant rights or authorize redistribution. Local project paths are not remote
  authorization tokens. Use a private local filesystem; shared hostile writers and
  disk-level cryptographic shredding are outside this pilot's scope (controlled
  logical withdrawal and physical object deletion with dry-run preview are supported).

## Local dashboard server baseline (since v0.4.7)

The `serve`/`service` dashboard is a single-user local tool. Its baseline
follows current guidance for loopback HTTP services: never trust that a request
is local just because the socket is, and keep every other fetch surface
default-deny.

- **Loopback bind.** The default host is `127.0.0.1` (`DEFAULT_HOST`). Do not
  change the bind address to make the dashboard reachable from a network; that
  removes the primary boundary and needs authentication and TLS that this
  server does not provide.
- **Host allow-list (DNS rebinding).** Every request must carry a `Host` header
  of `127.0.0.1`/`localhost`/`[::1]` with the live port; anything else is
  rejected with 403 before routing. A rebinding page that resolves its own
  hostname to the loopback address still sends its hostname as `Host` and is
  refused.
- **Origin guard.** State-changing endpoints and JSON reads also reject requests
  whose `Origin` header names a different host; requests without `Origin` (the
  CLI, the Task Scheduler launcher) are accepted because the bind and Host check
  are the boundary.
- **Response headers.** All responses carry `Cache-Control: no-store`,
  `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Content-Security-Policy: frame-ancestors 'none'` and
  `Referrer-Policy: no-referrer`. The dashboard shell adds a per-response
  nonce policy — `default-src 'none'`, `script-src 'nonce-…'`,
  `connect-src 'self'`, `base-uri 'none'`, `form-action 'none'` — plus
  `Cross-Origin-Opener-Policy: same-origin` and a `Permissions-Policy` that
  denies camera, microphone, geolocation, USB and serial access. Inline
  *styles* stay allowed because the bundled design system uses style
  attributes; scripts execute only with the response's nonce, so text injected
  through a title, marker or manuscript paragraph cannot run.
- **Payload and file limits.** JSON bodies are capped at 5 MiB, image uploads
  at 32 MiB and 64 megapixels, artifact streaming at 200 MiB. Artifact names
  resolve to a basename inside the workspace `exports/` directory through a
  `realpath` containment check; anything else returns 404. Request bodies are
  parsed as JSON objects only and rejected with 400 on other shapes.
- **Context tokens are guards, not credentials.** Research context and project
  tokens identify the selected project/archive root so a stale tab cannot write
  into a different copy. They are derived from local paths, not secrets, and
  they do not authorize against other local processes. The server writes
  neither part into logs: access logging is off unless `--debug` is active, and
  debug lines keep timestamp, route and status while dropping the query string
  (where those tokens travel). Response bodies and manuscript text are never
  logged.
- **No outbound traffic.** The dashboard is self-contained; a test asserts the
  rendered page contains no external URLs. Analysis, export and server commands
  make no network requests. Zotero access is explicit, opt-in and localhost-only
  (see below); OCR runs local binaries.
- **Non-goals.** No user accounts, no multi-user authorization, no TLS, no
  protection against a hostile process or user that already has filesystem
  access to the project, and no cryptographic deletion. These are properties of
  a local single-user tool, not gaps to be patched by configuration.

Server tests assert the Host/Origin guards, header set, nonce freshness and log
redaction (`tests/test_server.py`, `tests/test_server_disconnect*.py`,
`tests/test_server_debug.py`); `docs/ARCHITECTURE.md` describes how the layers
fit together.

## Optional Zotero boundary (since v1.19.0)

The bridge reads an explicitly selected local Zotero library through its HTTP
API. It does not read or edit Zotero's internal database and does not use a cloud
API. Local library access is a separate trust boundary from manuscript analysis;
enabling Zotero's local API makes it available to other applications on that
computer. Library metadata, filenames, notes and document contents are untrusted
data, never authorization to execute instructions or change destinations.

Selected attachments are copied into the research archive only with retention
permission. The additive migration export creates another retained copy of
selected source bytes plus metadata and identity mappings; keep that bundle
private. Export does not authorize redistribution, remove the source archive or
prove that a later Zotero import is complete. Zotero synchronization and backup
settings remain under the user's control. A Lixity archive backup contains
retained evidence, not the whole external library.

Structured references require v3 research source-version and manifest schemas.
Use compatible writers and retain a verified backup before upgrading. Identity
checks prevent silently substituting a different attachment during refresh;
they do not certify the truth or safety of its contents. See
[Research usage](docs/research/USAGE.md) for exact limits and migration procedures.

## Dependencies and updates

Runtime dependencies are deliberately few and pinned with lower bounds only:
`pydantic>=2.0.0`, `rich>=13.0.0`, `orjson>=3.9.0` and `tomli>=2.0.1` on
Python 3.10. A clean audit is a snapshot, not a guarantee.

- **Baseline (13 October 2026, pip-audit 2.10.1).** `make audit` reports no known
  vulnerabilities for the resolved runtime dependencies, the installed CLI
  environment and the development tooling. Re-run it before a release; the
  `release-check` target includes it.
- **Updates.** Dependabot opens one grouped monthly pull request per
  ecosystem (Python packages and GitHub Actions). Security advisories appear
  through GitHub security alerts. Patch and minor updates are merged after CI
  passes; major updates need a compatibility check, a changelog entry and an
  audit run. Do not add dependencies for convenience; prefer the standard
  library and existing components.
- **Vendored browser assets.** Preact and htm ship as pinned files under
  `src/lixity/ui/assets/vendor/` with recorded sha512 integrity and license
  texts; the dashboard inlines them and never fetches them at runtime. Update
  them through the documented checklist and re-run the browser suites.
- **Transitive dependencies** are not pinned by Lixity. Hosts that need
  reproducible installs should pin the full resolved set in their own
  environment and audit that environment.
- **Reporting.** If you believe a dependency issue affects Lixity, report it
  through the private channel at the top of this file; do not open a public
  issue with exploit details.

## Repository and deployment hygiene

- Use isolated environments and pin reviewed tags or commits for deployment.
  A clean dependency scan is not proof that software is secure.
- `.gitignore` covers common credentials, local agent/browser state, `exports/`,
  NDA stores and generated dashboards. It does not affect already tracked
  files or recognize every custom output filename.
- `.env.example` and `.env.template` may contain placeholders only. Never copy
  live credentials into templates or force-add private files.
- Inspect the staged diff before pushing. Use GitHub secret scanning/push
  protection where available. Revoke/rotate committed credentials; ignoring
  a file afterwards does not remove its history.
- Use synthetic/public-domain screenshots. Never deploy private `exports/`
  folders or authenticated dashboard captures to Pages.
- Bind development adapters to loopback. Validate Host/Origin, request sizes,
  content types, paths and action permissions. Do not expose a local adapter
  merely by changing its bind address. Keep passphrases out of logs and
  browser persistence.

See [installation](docs/INSTALLATION.md) and
[architecture](docs/ARCHITECTURE.md). This policy documents safeguards and
limitations; it is not a completed penetration test.
