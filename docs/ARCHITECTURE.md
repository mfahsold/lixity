# Architecture and integration boundaries

This document describes Lixity `1.15.0`. The shared pipeline and explicit
API threshold mappings require this release or newer.

Proposed extension: [research workspace RFC](research/README.md), with an
evidence model, archive and third-party integration plan. This is a design under
discussion; it does not describe implemented research commands or dependencies.

## Layers

| Layer | Responsibility | Must not own |
| --- | --- | --- |
| Language resources | Lexicons, patterns, labels, calibrated coefficients | Project-specific character lists or file paths |
| Analysis core | Metrics, paragraph profiles, uncertainty and statistical diagnostics | HTTP sessions, exports or UI state |
| `lixity.pipeline` | Resolve document language; assemble one analysis result | Implicit file reads or mutable global project state |
| CLI / `lixity.api` | Input/output contracts and threshold resolution | Duplicate analysis algorithms |
| UI | Render results using shared components and bundled assets | Recompute statistical decisions in JavaScript |
| Project adapters | Manuscript access, publication actions and local services | Copies of the engine |

`analyze_document(text, config, thresholds)` returns `DocumentAnalysis` with
corpus metrics, chapter profiles, paragraph profiles and the fingerprint.
The metrics are calculated once and reused during fingerprint construction.
`profile_document` and `fingerprint_document` support narrower requests.

## Configuration and multiple projects

```python
from pathlib import Path
from lixity.config import load_project_config, resolve_thresholds
from lixity.pipeline import analyze_document, resolve_document_config

manuscript = Path("/projects/example/manuscript.md")
text = manuscript.read_text(encoding="utf-8")
settings = load_project_config(manuscript)
config, language = resolve_document_config(
    text,
    settings.get("language", "en"),
    **{key: settings[key] for key in ("chapter_regex", "appendix_marker") if key in settings},
)
thresholds = resolve_thresholds(project_config=settings)
analysis = analyze_document(text, config, thresholds)
```

The loader searches from the supplied path and merges supported project and
user settings. A supplied threshold mapping prevents implicit configuration
discovery inside `resolve_thresholds`; `{}` selects code defaults only.
Explicit threshold arguments take precedence over the mapping.

This is not a global project-session framework. The convenience API's
`profile`, `fingerprint`/`passport` and `dashboard` accept `project_config`
for threshold resolution: `{}` avoids implicit discovery, while `None`
retains current-directory discovery for compatibility. Language, title and
corpus overrides remain separate explicit arguments. Adapters should pass the intended configuration and
keep manuscript-specific characters, motifs and artifacts within that project.

## Presentation and trust boundaries

The dashboard is a self-contained HTML file. Python bundles CSS and the
dashboard/style-space scripts; no CDN, JavaScript framework or frontend build
is required. Chapter-title tooltips are created as text nodes, not executable
markup. Rendering and point picking share projected coordinates. Animation
is scheduled only while rotation is enabled and the page is visible.

Optional mutation controls need a separate project server. The engine alone
does not start an HTTP service, store an NDA passphrase or send documents.
Server adapters must validate origins, hosts, request sizes and payloads,
restrict file/action access, and handle their own session lifecycle.

## Verification

- Python tests cover orchestration, configuration precedence, language resources
  and final-score dimension flagging.
- `tests/browser/style-space.cjs` checks synthetic dashboard interactions,
  tooltip escaping, idle rendering and mobile layout using optional Playwright.
- The wheel includes both UI scripts, CSS, Python modules and the typing marker.
- Adapter tests belong with their projects; no private manuscript is needed
  for the engine's regression suite.
