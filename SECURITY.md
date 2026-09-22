# Security Policy

## Reporting a vulnerability

Please report suspected vulnerabilities privately to
**mfahsold@googlemail.com** (PGP not required). You will receive an
acknowledgement within a few days. Please do not open a public issue for
security problems before a fix is available.

## Supported versions

Only the latest release on `main` receives security fixes.

## Design properties (why lixity is low-risk by construction)

- **Local and offline**: lixity makes no network calls, has no telemetry,
  no accounts and no cloud dependencies. All analysis runs in-process.
- **Read-only on manuscripts**: `analyze`, `profile`, `style` and `dashboard`
  never modify the input. Only explicit marker commands (`add_marker`,
  `resolve_marker`, control-server actions) write, and only to the
  manuscript's own work-marker comment lines.
- **No shell execution**: the engine never invokes a shell and never passes
  user input to `subprocess`. The only subprocess use is the development-only
  screenshot helper, which runs a resolved Chromium binary with a fixed argv.
- **Injection-safe output**: every manuscript-derived string is HTML-escaped
  before it enters the dashboard (chapter titles, paragraph text, marker
  notes, tooltips). Work markers cannot break out of their comment boundary
  (`-->` is neutralised).
- **Atomic, durable writes**: artifacts are written to a temp file in the
  target directory, `fsync`ed, then atomically replaced; unchanged content
  causes zero writes. Published artifacts are created with mode `0644`.
- **No secrets on disk**: the optional NDA store (book-project integration)
  keeps only ciphertext; passphrases are never stored.
- **Deterministic**: identical input yields byte-identical output, so
  artifacts can be verified by hash.

## Hardening for operators

- Keep `.gitignore` entries for `*.enc`, `*.key`, `*.pem`, `.env*` and
  `secrets/` intact — private keys and encrypted stores must never be
  committed.
- Run `ruff check` and `mypy` (see `pyproject.toml`) before releases; CI
  does this automatically.
- The optional local control server (book-project integration) binds to
  `127.0.0.1` only and uses a fixed action whitelist.
