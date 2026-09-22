# Security policy

Report suspected vulnerabilities privately to **mfahsold@googlemail.com**
(no PGP required; acknowledgement within a few days). Only the latest release
on `main` receives fixes.

Lixity is low-risk by construction: it runs fully offline (no network calls,
telemetry or accounts), is read-only on manuscripts for `analyze` / `profile`
/ `style` / `dashboard`, never invokes a shell or `subprocess` (the development-only screenshot
helper runs a resolved Chromium binary with a fixed argv), HTML-escapes
every manuscript-derived string before it enters the dashboard, and writes
artifacts atomically (temp file + `fsync` + replace; unchanged content causes
zero writes). The optional NDA store keeps only ciphertext — passphrases are
never stored. Keep the `.gitignore` entries for `*.enc`, `*.key`, `*.pem` and
`.env*` intact.
