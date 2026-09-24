# Security policy

Report suspected vulnerabilities privately to **mfahsold@googlemail.com**
(no PGP required; acknowledgement within a few days). Please include a
minimal reproduction (sample manuscript + command) where possible.

## Supported versions

| Version | Supported |
| :--- | :--- |
| 1.14.x (latest `main` / release tag) | ✅ fixes |
| older tags | ❌ upgrade first |

Only the latest release on `main` receives fixes.

## Threat model (why Lixity is low-risk by construction)

- **Fully offline**: no network calls, telemetry, accounts or phone-home.
- **Read-only on manuscripts** for `analyze` / `profile` / `style` /
  `dashboard` (work markers are optional, explicit writes via API/UI action).
- **Never invokes a shell or `subprocess`** (the development-only screenshot
  helper runs a resolved Chromium binary with a fixed argv).
- **HTML-escapes** every manuscript-derived string before it enters the
  dashboard (no XSS from prose content).
- **Atomic artifact writes** (temp file + `fsync` + replace); unchanged
  content causes zero writes.
- **Optional NDA store keeps only ciphertext** — passphrases are never
  stored.

Keep the `.gitignore` entries for `*.enc`, `*.key`, `*.pem`, `*.p12`,
`id_rsa*`, `.netrc` and `.env*` intact so secrets never enter the repository.

## Hardening checklist for consumers

- Prefer `pipx` / `uv tool install` (isolated environment) over a shared
  system Python.
- Pin installs for reproducible pipelines:
  `pip install "git+https://github.com/mfahsold/lixity.git@<tag>"`.
- Treat dashboard HTML as **local documents**: open them from disk or a
  trusted host; they embed your manuscript text.
- Enable GitHub secret scanning / push protection on forks that receive
  private material.
