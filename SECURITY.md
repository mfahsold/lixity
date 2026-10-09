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
  project adapters; review those integrations independently.
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
