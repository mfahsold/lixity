# Architecture and integration boundaries

This document describes the shared architecture through v1.24.1.
The shared pipeline and explicit API threshold mappings were introduced
in 1.15.0; integrated local project/research workflows arrived in 1.16.0, followed
by native editing, the self-hosted OCR boundary, offline diagrams and verified
export/restoration in 1.17.0.

Experimental extension: [local research workspace](research/USAGE.md).
`lixity.research` owns explicit-project ingestion (UTF-8 text and PDFs), immutable snapshots,
exact citations, BagIt-style export/restoration, and a rebuildable SQLite/FTS5 index. It does not import into
`lixity.pipeline`. Existing analyze/profile v2 and style v4 remain unchanged.
The workspace also stores dossiers, claims, evidence links and author decisions with full native revision history.
The [research RFC](research/README.md) additionally specifies broader review workflows,
manuscript anchors, and hybrid vector search; those are not current dependencies.

## Layers

| Layer | Responsibility | Must not own |
| --- | --- | --- |
| Language resources | Lexicons, patterns, labels, formula coefficients | Project-specific character lists or file paths |
| Analysis core | Metrics, paragraph profiles, uncertainty and statistical diagnostics | HTTP sessions, exports or UI state |
| `lixity.pipeline` | Resolve document language; assemble one analysis result | Implicit file reads or mutable global project state |
| CLI / `lixity.api` | Input/output contracts and threshold resolution | Duplicate analysis algorithms |
| UI | Render results using shared components and bundled assets | Recompute statistical decisions in JavaScript |
| `lixity.server` | Loopback HTTP transport, request parsing and response envelopes | Analysis decisions, project state resolution, domain logic |
| Project adapters | Manuscript access, publication actions and local services | Copies of the engine |

The native server is a package rather than one module, because it is the only
place where transport, state and domain calls meet. `runtime` owns bind checks
and startup; `views` owns dashboard rendering and is independent of HTTP;
`_state` owns workspace state and is the single writer via `refresh()`; `_base`
owns response helpers and the Host/Origin guards; `routes_project`,
`routes_research`, `routes_nda` and `routes_markers` each own their handlers and
are composed into one `BaseHTTPRequestHandler` in `handler`. Route handlers
parse and shape requests and then delegate; they do not resolve project state or
reimplement domain rules, and the research routes call `lixity.research.api`
rather than touching the repository. Because each group is a plain class, a
route module can be read and type-checked on its own.

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
    project_config=settings,
)
thresholds = resolve_thresholds(project_config=settings)
analysis = analyze_document(text, config, thresholds)
```

The loader searches from the supplied path and merges supported project and
user settings. A supplied threshold mapping prevents implicit configuration
discovery inside `resolve_thresholds`; `{}` selects code defaults only.
Explicit threshold arguments take precedence over the mapping.

`resolve_document_config` applies known corpus settings from
an explicit mapping. Explicit arguments take precedence; language remains an
explicit choice. The convenience API's `profile`, `fingerprint`/`passport` and
`dashboard` accept this mapping as well as thresholds: `{}` avoids implicit
discovery, while `None` retains threshold discovery for compatibility. Chapter,
paragraph and scene numbering use the same configured, nonempty chapter units.
The existing Markdown parser defines supported measurement prose: paragraphs,
list items and quoted prose, omitting metadata, headings, comments, code and
footnote definitions. Paragraph profiles intentionally cover body/list blocks
only; legacy whitespace counts remain separate. Token regex flags are preserved,
while linguistic cue patterns have their own case-insensitive compiler. See
[Methods](METHODS.md) for exact scopes and numerical conventions.
Scene reports reuse the chapter measurement engine and compare only explicit
register groups within the manuscript. They do not read research sources or
provide quality scores. Adapters should pass the intended configuration and
keep manuscript-specific characters, motifs and artifacts within that project.

Lixity provides read-only three-way revision preparation and atomic
revision groups. These reuse the strict revision validator and one repository
commit. Decision impact and editorial review follow recorded links, dates and
revision pins; they do not infer semantic contradictions or rewrite documents.
See [implemented workflows and limits](research/USAGE.md#research-workflows).

## Presentation and trust boundaries

The dashboard is a self-contained HTML file. Python bundles CSS and the
dashboard/style-space scripts; no CDN, JavaScript framework or frontend build
is required. Chapter-title tooltips are created as text nodes, not executable
markup. Rendering and point picking share projected coordinates. Animation
is scheduled only while rotation is enabled and the page is visible.

### Visual consistency and evidence

The local dashboard and Pages use the same
neutral surfaces and blue action palette. The existing stylesheets remain separate
so exported dashboards stay self-contained; browser checks compare the common
color roles. Filled actions use `#245b85` with white text in both themes, while
links and focus rings use a lighter blue on dark surfaces. Analytical diverging
colors retain their meaning. Heatmap text selects black or white from the actual
cell luminance, independently of the surrounding theme.

The presentation follows these evidence-informed constraints:

- [WCAG contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
  guides text contrast; visible focus outlines supplement color changes.
- [WCAG target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
  specifies a 24 CSS-pixel minimum with exceptions. Primary workspace controls
  use at least 40 pixels and 44 on coarse pointers as a product choice; this is
  not a claim that every compact data mark meets the enhanced 44-pixel criterion.
- [NN/g's controlled eye-tracking experiment](https://www.nngroup.com/articles/flat-ui-less-attention-cause-uncertainty/)
  supports retaining visible button boundaries and link cues. Its findability
  tasks do not establish a Lixity-specific productivity improvement.
- [Reading research reviewed by Kevin Larson](https://learn.microsoft.com/en-us/typography/develop/word-recognition)
  informs the use of mixed-case labels rather than forced uppercase. System sans
  fonts serve controls and reading text; local serif fonts distinguish titles.
  No single typeface, blue hue or line width is asserted to be universally optimal.
- Reading paragraphs use relative font sizes, generous leading and a 72-character
  maximum measure where appropriate. This is a design choice, not an empirical
  optimum. [WCAG text spacing](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html)
  concerns preserving content and functionality when users override spacing;
  its override values are not mandatory default typography.

Desktop/mobile rendering, keyboard focus, text-spacing overrides, reduced motion
and both themes are checked with synthetic content. Automated checks and the
selected contrast audits do not constitute a complete accessibility certification
or replace testing with readers and assistive technologies.

Pages publishes `sitemap.xml` containing the canonical landing page and HTML
guides. Submit its public URL in Google Search Console; a sitemap aids discovery
but does not guarantee indexing. The project-path `robots.txt` is a policy
template, not the effective host-root crawler policy. Keep sitemap entries in
step with the HTML publication boundary and use real modification dates.

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

## External research libraries (since v1.19.0)

The optional `research.zotero` adapter lets Zotero Desktop lead media
and bibliographic cataloguing. Lixity owns selected immutable evidence captures,
analysis, claims, dossiers and author decisions. It calls the documented local
HTTP API, rather than reading Zotero's database or incorporating its application
code. This boundary avoids maintaining another general media manager and keeps
existing projects independent of Zotero availability after capture.

This follows the separation used by [Zettlr's reference-manager integration](https://docs.zettlr.com/en/editor/citations.html),
though Zettlr primarily reads exported bibliographies and Lixity captures evidence
through the [Zotero local API](https://www.zotero.org/support/dev/web_api/v3/local_api).
[novelWriter's tags and references](https://novelwriter.io/docs/usage/tags_and_references.html)
illustrate the complementary authoring concern: connecting story notes and scenes.

The intended commercial value is the path from source to evidence, linguistic
analysis and an explicit author decision. The expected maintenance benefit is an
engineering judgment, not measured sales ROI. The adapter is optional, adds no
runtime dependency and leaves Lixity's license unchanged. Zotero is a separately
installed product; no bundled distribution or license compatibility claim is made.

The adapter also exports active source captures as an additive RIS bundle with
original files and a mapping manifest. Import happens through Zotero's supported
import workflow. The export does not delete local sources, alter citations or
write Zotero's database. The bridge uses stable external attachment identities
to distinguish a repeated capture from an explicit refresh. A migration source
tag and matching original-byte checksum allow an existing evidence source to be
associated with its imported Zotero attachment. Titles alone never establish identity.

Source versions with `external_reference` use `research-local/3`; their snapshots
use `research-manifest-local/3`. Readers support prior v1/v2 records without
rewriting them. Older applications reject v3 instead of silently dropping the
external identity. Evidence captures and references remain in Lixity backups;
Zotero's library and unselected media require their own backup.

Zotero is optional for existing analysis and retained evidence. There is no
automatic background or cloud synchronization. Images, audio and video can be
managed in Zotero, but are not made searchable evidence by the PDF/text bridge.
See [research usage](research/USAGE.md#zotero-desktop-bridge-since-v1190)
for implemented behavior and portability limits.
