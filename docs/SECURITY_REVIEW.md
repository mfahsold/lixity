# Targeted security review — 2026-09-24

Scope: dashboard rendering, public artifact links, repository ignore rules and
installation boundaries. This is not a penetration test, dependency audit,
credential-history scan or audit of every project adapter.

## SEC-01 — NDA record DOM injection (fixed)

Impact: a malicious record field returned by an adapter could become HTML in
the local dashboard and execute in that page's context. Access to an adapter
record source is a precondition; this review does not establish an unauthenticated
remote path to modify records.

`src/lixity/ui/assets/dashboard.js`, `ndaRender`, previously interpolated
record IDs, names, contact details and PDF names into `innerHTML`. It now
creates elements and assigns `textContent`, values and dataset properties.
The browser regression uses synthetic markup in all relevant fields, checks
that no elements or injected attributes are created, and preserves action IDs.

## SEC-02 — executable artifact URLs (fixed)

Impact: escaping an HTML attribute alone did not reject a supplied
`javascript:` or `data:` artifact URL. This depended on an embedding adapter
passing an untrusted link and a user activating it.

`src/lixity/ui/components.py`, `artifact_href`, now accepts relative paths or
HTTP(S) URLs only; executable schemes, control characters and ambiguous
backslash/protocol-relative forms are excluded. `render_dashboard` applies
this at the artifact-link boundary. Regression cases cover executable URLs
and ordinary relative PDF links.

## SEC-03 — accidental publication safeguards (improved)

`.gitignore` now includes the default `lixity-dashboard.html`, local agent
state, Playwright authentication state and common development outputs.
Placeholder environment templates remain trackable. Ignore-rule checks
confirm private patterns are excluded while the public site and samples remain
trackable. No matching credential/private-store filenames were found among
tracked files in the targeted filename check; file contents and history were
not exhaustively scanned.

## Remaining boundaries

- Adapters must validate requests and filesystem access independently.
- Generated HTML is sensitive data, even after XSS hardening.
- Custom regexes and large inputs require resource limits in untrusted hosts.
- Artifacts, cached data and screenshots should be reviewed before publication.
- Update/release processes should pin reviewed refs; GitHub Pages does not make
  a private development server safe to expose.

See [SECURITY.md](../SECURITY.md) for reporting and deployment guidance.
