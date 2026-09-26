# Architecture and integration boundaries

This document describes Lixity `1.16.0`. The shared pipeline and explicit
API threshold mappings were introduced in 1.15.0; the integrated local
project/research workflows described here require 1.16.0.

Experimental extension included in `1.16.0`: [local research pilot](research/USAGE.md).
`lixity.research` owns explicit-project ingestion, immutable snapshots, exact
citations and a rebuildable SQLite/FTS5 index. It does not import into
`lixity.pipeline`. Existing analyze/profile v2 and style v4 remain unchanged.
The pilot also stores dossiers, claims, evidence links and author decisions.
The [research RFC](research/README.md) additionally specifies review workflows,
manuscript anchors, OCR and hybrid search; those are not current dependencies.

## Layers

| Layer | Responsibility | Must not own |
| --- | --- | --- |
| Language resources | Lexicons, patterns, labels, calibrated coefficients | Project-specific character lists or file paths |
| Analysis core | Metrics, paragraph profiles, uncertainty and statistical diagnostics | HTTP sessions, exports or UI state |
| `lixity.pipeline` | Resolve document language; assemble one analysis result | Implicit file reads or mutable global project state |
| CLI / `lixity.api` | Input/output contracts and threshold resolution | Duplicate analysis algorithms |
| UI | Render results using shared components and bundled assets | Recompute statistical decisions in JavaScript |
| Project adapters | Manuscript access, publication actions and local services | Copies of the engine |

The development server keeps one selected workspace per process. Opening a
project selects its existing directory and research archive; importing browser
file bytes creates a project at an explicit destination. A browser filename does
not establish the original file's parent directory. An initialized research
project can be opened before a manuscript exists. Research storage remains
explicit in the API even when the server chooses it from an opened workspace.

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

Project and research interface labels use the same language-profile resources
as the analysis dashboard. Python escapes the localized label dictionary into
an HTML attribute; JavaScript renders records as escaped text and applies
locale labels without changing stored identifiers or numerical results.
Seven interface languages do not imply equal linguistic validation: English
and German currently have the deepest coverage. Shared statistical routines
operate on language-dependent heuristic inputs.

## Verification

- Python tests cover orchestration, configuration precedence, language resources
  and final-score dimension flagging.
- `tests/browser/style-space.cjs` checks synthetic dashboard interactions,
  tooltip escaping, idle rendering and mobile layout using optional Playwright.
- `tests/browser/research.cjs` uses a disposable loopback server and synthetic
  source archive to check project opening, record creation, evidence lifecycle
  states and responsive research controls.
- The wheel includes both UI scripts, CSS, Python modules and the typing marker.
- Adapter tests belong with their projects; no private manuscript is needed
  for the engine's regression suite.
