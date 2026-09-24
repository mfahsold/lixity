# Security policy

Report suspected vulnerabilities privately to **mfahsold@googlemail.com**.
Include the version, command, environment and a minimal synthetic reproduction.
Do not send real manuscripts, NDA records, passphrases or credentials. Avoid
publishing exploit details before maintainers can assess the report.

## Versions and scope

The current development checkout is **1.15.0.dev0**; the published release is
**v1.14.0**. Reports should identify the exact tag or commit. Fixes are developed
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
- HTTP servers, NDA encryption, export tools and document delivery belong to
  adapters, not the engine's security boundary. Review them independently.
- Custom regular expressions and large inputs can consume CPU or memory.
  Hosts accepting untrusted inputs should impose size, time and concurrency
  limits and must not execute unrestricted user-supplied expressions.
- Atomic file replacement protects write integrity, not confidentiality or
  authorization. Callers choose writable destinations and file permissions.

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
