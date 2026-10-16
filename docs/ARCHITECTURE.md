# Architecture and integration boundaries

This document describes the maintained shared architecture. Changes introduced in
0.3.0 are labeled **Since v0.3.0**. Product version
numbers describe development maturity; JSON and research storage schemas have
their own independent versions. Historical release numbers remain unchanged.
The shared pipeline and explicit API threshold mappings were introduced
in 1.15.0; integrated local project/research workflows arrived in 1.16.0, followed
by native editing, the self-hosted OCR boundary, offline diagrams and verified
export/restoration in 1.17.0.

Experimental extension: [local research workspace](research/USAGE.md).
`lixity.research` owns explicit-project ingestion (UTF-8 text and PDFs), immutable snapshots,
exact citations, BagIt-style export/restoration, and a rebuildable SQLite/FTS5 index. It does not import into
`lixity.pipeline`. The reverse direction exists for presentation: `research.analysis`
renders source dashboards through `lixity.ui`, and `ui.dossier_images` reads
`research.limits`; the archive itself never becomes pipeline input.
Existing analyze/profile v2 and style v4 remain unchanged.
The workspace also stores dossiers, claims, evidence links and author decisions with full native revision history.
The [research RFC](research/README.md) additionally proposes broader review workflows
and hybrid vector search. The implemented manual manuscript associations are
described below; the RFC is not an implementation reference. Section spans and
section edits live in `research/sections.py`; `research.api` re-exports them.

## Layers

| Layer | Responsibility | Must not own |
| --- | --- | --- |
| Language resources | Lexicons, patterns, labels, formula coefficients | Project-specific character lists or file paths |
| Analysis core | Metrics, paragraph profiles, uncertainty and statistical diagnostics | HTTP sessions, exports or UI state |
| `lixity.pipeline` | Resolve document language; assemble one analysis result | Implicit file reads or mutable global project state |
| CLI / `lixity.api` | Input/output contracts and threshold resolution | Duplicate analysis algorithms |
| UI | Render results using shared components and bundled assets | Recompute statistical decisions in JavaScript |
| `publication` / `pdf_export` | Validate entered publication data; compose shared PDF bytes | Infer legal identities, establish rights or write output files |
| `lixity.server` | Loopback transport, request guards, one shared dashboard assembly and selected-workspace transitions | A second renderer, a second analysis path or CLI/service lifecycles |
| `config` / `io` / `workspace` | Explicit project metadata, atomic byte I/O and manuscript discovery | Implicit ancestor/user defaults or duplicate writers |
| `lixity.service` | Managed local process lifecycle (start/stop/restart/status) | Adopting externally managed units |
| Project adapters | Manuscript access, publication actions and local services | Copies of the engine |

`lixity.math_core` is the single mathematical vocabulary of the analysis core
(robust scale, significance z, normal tail, ratio/share/density totalization,
plug-in standard errors and published effect bands). Heuristics import it
instead of restating formulas; `style_fingerprint` re-exports the historical
names for callers.

The native server is a package rather than one module, because it is the only
place where transport, state and view assembly meet. `runtime` owns bind checks
and startup; `views` composes the dashboard from the shared pipeline and domain
reports and stays independent of HTTP; `_state` declares the selected-workspace
state and the shared cache publication (`publish_dashboard`/`refresh`). Serving
the dashboard shell re-renders when the manuscript digest changed since the last
render (`refresh_when_source_changed`), so a cached view never presents stale
numbers; workspace transitions are published by `runtime` and the project routes;
`_base` owns response helpers and the Host/Origin guards; `routes_project`,
`routes_research`, `routes_manuscript_research`, `routes_pdf`, `routes_nda` and
`routes_markers` each own their handlers and are composed with `discovery` and
`pdf_context` into one `BaseHTTPRequestHandler` in `handler`. Handlers parse and
shape requests and then delegate; research handlers call `lixity.research.api`
rather than touching the repository, and project handlers own explicit project
transitions (open/create/settings/import) without duplicating analysis. Because
each group is a plain class, a route module can be read and type-checked on its
own.

Research overview requests use `research.api.project_overview` to collect the
existing lists from one fully validated archive snapshot. Source versions are
grouped once for that view rather than rescanning the archive for each source.
The response contract is unchanged; there is no persistent cache.

The development server keeps one selected workspace per process. Opening a
project selects its existing directory and research archive; importing browser
file bytes creates a project at an explicit destination. A browser filename does
not establish the original file's parent directory. An initialized research
project can be opened before a manuscript exists. Research storage remains
explicit in the API even when the server chooses it from an opened workspace.
All surfaces resolve an explicit selector through
`workspace.resolve_project_target`, and `run_server` raises on an occupied port
while printing only when the CLI passes `announce=True`.

`analyze_document(text, config, thresholds)` returns `DocumentAnalysis` with
corpus metrics, chapter profiles, paragraph profiles and the fingerprint.
The metrics are calculated once and reused during fingerprint construction.
`profile_document` and `fingerprint_document` support narrower requests.

## Manual manuscript associations

**Since v0.3.0:** `research.manuscript` owns `ManuscriptClaimLink`, separate
from imported source passages/evidence. Creation retains only an explicitly
permitted quote and an immutable `paragraph-profile-text/1` anchor: project-relative
path, raw-source and displayed-paragraph hashes, source lines and Unicode
codepoint offsets. It pins the exact reviewed claim revision and writes
`research-local/7` with manifest v7 on the first opted-in save. Existing archives
remain unchanged on reads. Product v0.3.0 supports schemas v1–v7 independently
of the historical product numbering; historical v3.0.1 supports only v1–v6.

`pipeline.paragraph_identity` supplies the same paragraph identity to rendering
and the research API. `FileUtils.read_source_snapshot` binds raw bytes and decoded
text in one read; manual creation checks source containment and bytes again
before publication. `manuscript_review_data` accepts the existing validated
repository snapshot and pipeline paragraphs, avoiding duplicate analysis or a
second archive read. It derives structural change flags without mutating anchors,
repinning claims or proving factual support. Unique moved/duplicate paragraph
candidates remain unresolved. Missing and unreadable sources remain distinct.

`server.routes_manuscript_research` validates selected manuscript and archive
tokens before delegating to the shared API. The native reader marks only exact
resolved quote spans, supports lazy paragraph rendering and preserves complete
text search. Dossier research/companion readers reuse the existing claim viewer
and history for a reverse list of current claim associations. Saved quote counts
join explicit links by their pinned dossier ID using one coherent snapshot;
counts span saved dossier versions and disclose differing revision pins;
zero counts do not establish manuscript nonuse. There is no automatic evidence
linking, manuscript import or semantic analysis in this association workflow.

Ordinary authored CLI updates may omit the archive snapshot, while requiring
the exact reviewed record revision, change kind and reason. The CLI forwards
its current read's snapshot to the same strict backend writer; record changes
and races fail without retry. Explicit snapshots and Python/HTTP/batch/image/
acknowledgement writes retain their existing strict guards. Unchanged association
pins remain; changed associations require explicit reviewed pins in convenience
mode. This does not introduce another persistence or reconciliation path.

## Configuration and multiple projects

Project author identity reuses `author_name` in the existing configuration loader,
but only from an explicit project's root config; user/ancestor defaults are excluded.
`save_project_author` updates only the explicit project's `lixity.toml` after
validating the scalar and verifying that other parsed settings remain intact.
An optimistic file-identity/content check precedes atomic replacement; it is not
an external editor lock. The UI, NDA renderer and pure `project_identity` checker
consume that same value. Identity comparisons read a bounded syntax subset and
never rewrite manuscripts or affect linguistic measurements.

**Since v0.3.0:** `publication.PublicationSettings` and
`PUBLICATION_FIELDS` define the optional imprint data and field bounds once.
The existing configuration loader excludes publication data from user/ancestor
defaults; the settings renderer and PDF composer consume that same model.
`project_identity.project_title` supplies one code-aware title resolver.
`pdf_export.compose_pdf` remains the single in-memory entrypoint for CLI and
native manuscript downloads, with explicit analysis configuration and project
identity inputs. The CLI owns output-path writes; the native route returns
bytes after checking selected context. A5 front matter uses only entered data;
A4 sheet/report composition keeps its existing purpose and body constraints.
PDF Info/Lang, chapter outlines and page furniture reuse `pdf_document` rather
than a second writer. Syntax validation is not a publication-compliance check.

`config.prepare_project_settings` constructs one validated candidate for title,
author and publication while checking that other TOML values remain intact.
The settings route renders the complete candidate dashboard first, commits
through `PreparedProjectSettings`, then publishes session/cache state. Decode,
validation, render or replacement failures do not publish the candidate.
Selected-context tokens include source/root and digests of both root configs;
publication saves require one, and PDF downloads reject stale metadata tokens.
The commit guard checks observed config identity and bytes before replacement;
it does not lock other processes or turn a manuscript path into a content pin.
Root configuration snapshots accept regular nonsymlink files and verify the
opened descriptor's identity; special files fail before a blocking read.

**Since v0.3.0:** text and binary output share
`FileUtils.atomic_write_bytes_if_changed`: a same-directory stage, complete
write, flush, original-mode preservation, fsync and atomic replacement. The
optional `before_replace` guard runs immediately before a changed replacement;
unchanged bytes skip it. Errors propagate, staging is cleaned and there is no
system-temporary or direct-overwrite fallback. Settings consumers can supply
their optimistic identity/content guard through this same entrypoint.
`Workspace.publish` uses finer timestamps plus a repeated-instant sequence,
recognizes historical minute names and prepares its stable link/copy before
replacement. Failed stable publication raises before archive rotation.

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
Section preparation uses the same code-aware ATX heading parser as dossier reads
and image placement. It reconciles the selected subtree while preserving unrelated
current text. The UI receives canonical unambiguous heading choices from the API.
See [implemented workflows and limits](research/USAGE.md#research-workflows).

Local images reuse `Source`, immutable `SourceVersion` and content-addressed
`Blob` records. They have no fabricated extraction or passages and are rejected
by textual analysis. A shared image-reference resolver feeds dossier reads,
history, validation and audit. An attachment publishes its capture and dossier
revision in one repository commit with exact concurrency tokens. Purge retains
the source/version identity needed for honest unavailable placeholders, not the
removed image bytes. Limits live in `research/limits.py`; the UI receives them
from those constants. Rendering and local preview belong to `ui/assets/dossier-images.js`,
while thin server routes perform project-bound input and binary-response handling.

## Presentation and trust boundaries

The dashboard is a self-contained HTML file. Python bundles CSS and the
dashboard/style-space scripts; no CDN, JavaScript framework or frontend build
is required. Chapter-title tooltips are created as text nodes, not executable
markup. Rendering and point picking share projected coordinates. Animation
is scheduled only while rotation is enabled and the page is visible.

**Since 2.0.0:** `ui/dimensions.py` renders a semantic score
table from the same measured points as the canvas payload. It exposes chapter
titles, actual dimension scores and descriptive flag text with native chapter
links, including when JavaScript is disabled. Native rotation/zoom buttons call
the existing projection renderer. No second renderer or frontend dependency is
introduced. The table omits unmeasured chapters and columns for absent axes.

### Visual consistency and evidence

The local dashboard and Pages use the same
neutral surfaces and blue action palette. **Since v0.3.0:**
`ui/assets/design-tokens.css` owns the shared color, type, spacing and control
roles. Dashboards bundle it into self-contained output; Pages stages the same
bytes and imports them from its existing stylesheet. Surface-specific rules
remain in the existing stylesheets; there is no additional theme store.
Filled actions use `#245b85` with white text in both themes, while
links and focus rings use a lighter blue on dark surfaces. Analytical diverging
colors retain their meaning. Heatmap text selects black or white from the actual
cell luminance, independently of the surrounding theme.

The presentation follows these evidence-informed constraints:

- [WCAG contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html)
  guides text contrast; visible focus outlines supplement color changes.
- [WCAG target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
  specifies a 24 CSS-pixel minimum with exceptions. Primary workspace controls
  use at least 40 pixels and 44 on coarse pointers as a product choice. Since
  2.0.0, paragraph chips and dimension controls use 24×24 pixels, or
  44×44 on coarse pointers, with no pressed-state shrinking. This does not
  establish target-size conformance for every compact data mark.
- [NN/g's controlled eye-tracking experiment](https://www.nngroup.com/articles/flat-ui-less-attention-cause-uncertainty/)
  supports retaining visible button boundaries and link cues. Its findability
  tasks do not establish a Lixity-specific productivity improvement.
- [Reading research reviewed by Kevin Larson](https://learn.microsoft.com/en-us/typography/develop/word-recognition)
  informs the use of mixed-case labels rather than forced uppercase. System sans
  fonts serve controls and reading text; local serif fonts distinguish titles.
  Native controls inherit the UI font; shared size, weight and line-height
  tokens keep equivalent settings, dialog and research roles consistent.
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
does not start an HTTP service or send documents.
Shared `BookLayoutConfig` geometry and `inline_markdown_to_html` fragments remain
available to existing book adapters; they do not publish a book. Project author
and contact fields are explicit, with no personal contact default. The fragment
helper escapes attribute values and accepts HTTP(S), mailto, relative and fragment
links; executable schemes stay inert.
Server adapters must validate origins, hosts, request sizes and payloads,
restrict file/action access, and handle their own session lifecycle.

Since 2.0.0, `nda.py` is a pure five-field document generator.
`nda_templates.py` contains friendly text models in seven languages. The server
resolves the project language or an explicit document override, substitutes
literal values in the model or a confined UTF-8 template, and returns PDF/text
bytes. The browser previews inert text and downloads a Blob. The generator
has no recipient registry and creates no server files. Reviewed/signed documents
remain under the user's own storage policy.

Browser debug selection uses an explicit saved `1`/`0` before
window/server defaults. The server's response mixin supplies the shared UTC
writer for both request lines and error details. This separates a browser's
diagnostic preference from the server process's logging setting.

Project and research interface labels use the same language-profile resources
as the analysis dashboard. Python escapes the localized label dictionary into
an HTML attribute; JavaScript renders records as escaped text and applies
locale labels without changing stored identifiers or numerical results.
Seven interface languages do not imply equal linguistic validation: English
and German currently have the deepest coverage. Shared statistical routines
operate on language-dependent heuristic inputs.

### Component vocabulary and markup rules

New markup reuses the documented vocabulary instead of introducing parallel
controls:

- Surfaces: `.panel` for a bordered region, `.ctl-group` for a labelled form
  block, `.research-card`/`.research-timeline` for authored-record lists, and
  `.notice-box` for boundary notes.
- Controls: `.ctl` for neutral buttons and inputs, `.ctl.primary` for the one
  primary action per form, `.chip` for compact filter or shortcut targets, and
  `.ctl-status` for live success and error messages. Help terms come from
  `help_term`; they stay dotted-underlined, keyboard reachable and localized.
- Structure: shared heading styles for `h2`/`h3`, `.section-heading` for a
  research sub-block, and `.ctl-note` for secondary prose such as empty states,
  limits and measurement notes.
- Measurements use tabular numbers (`font-variant-numeric: tabular-nums`) and
  keep their unit in the label, not in the value.

Rules for changes:

- Every visible string comes from the seven-language label packs; no hardcoded
  English in markup.
- Prefer native elements (`button`, `select`, `details`, `dialog`) and the
  existing `data-*` interaction hooks over new custom widgets.
- Keep one primary action per form; secondary actions stay neutral.
- Avoid new inline styles for spacing or sizing. Layout uses the utility
  classes in `dashboard.css`: a tenth-rem margin scale (`.mt-N`, `.mb-N`,
  `.my-N`, `.ml-N`, where N is the value in tenths, so `.mb-5` is
  `margin-bottom: .5rem`), `.w-full`, `.grow`, `.form-col`/`.form-col-wide`,
  `.field-wide`/`.field-narrow`, `.num-left`/`.num-right`, `.text-note`,
  `.text-small`, `.gap-sm` and `.select-code`. Repeated component shapes
  (`.research-dossier-outline`, `.research-subpanel`, `.research-passage-card`,
  `.research-warning-box`, `.research-block-heading`, `.badge-sm`,
  `.ctl-compact`) live next to the research styles.
- Inline `style` remains reserved for measured or dynamic values: bar and
  track widths, positions, heatmap background colours and data-driven
  alignments, plus the functional `display:none` toggle on tab panes.
  `tests/test_inline_styles.py` fails when a forbidden spacing or typography
  pattern reappears in rendered markup or in the assets.
- Responsive stacking is a CSS decision (single column at 640 px), not a second
  markup tree; new panels must survive 320 px without horizontal overflow.

### Stateful panels: the component layer (vendored Preact + HTM)

The shell, static exports and most panels stay server-rendered: one Python
renderer feeds the live dashboard, the single-file export and the tests. For
stateful panels, new work uses a small client component layer instead of ad-hoc
string building:

- `src/lixity/ui/assets/vendor/` vendors **Preact 10** (MIT) and **htm**
  (Apache-2.0) as pinned UMD/IIFE files. No package manager or build step is
  involved; `_JS_FILES` inlines them into the single dashboard script, so the
  page stays self-contained, works offline and needs no `unsafe-eval` under the
  nonce CSP (htm is pure string parsing, not `new Function`).
- Components render into an existing host element and own only their subtree;
  the Zotero catalogue results (`assets/zotero-results.js`) are the first panel
  on this layer. Components call the shared `uiLabel`/`uiCountFormat` helpers,
  so localization keeps one source.
- Keep the DOM contract stable: class names and `data-*` hooks used by the
  delegated click handlers and the browser suites are part of a component's
  output. Actions stay in the plain event handlers; components render.
- Never write `textContent`/`innerHTML` into a component host: unmount first
  (`LixityZoteroResults.clear`) or render the message through the component;
  preact patches against its own vnode tree.
- Components receive plain data; business rules (pagination, capture matching,
  context tokens) stay in the panel script. Vendor updates follow
  `vendor/README.md` (registry tarball, integrity check, browser suites).
- New stateful panels start as components; the remaining hand-built renderers
  (research lists, revision dialogs) migrate incrementally.

## First-run journey (server contract)

An empty workspace renders the welcome hero with three actions, the quickstart
steps and one optional link to the published public-domain examples. That link
points at the documentation site, opens in a new browser tab and is
presentation only: the app itself stays usable offline.

After `project-create`, `project-open` or `load`, the server answers with
`reload: true`. A fresh render chooses its default view from the content: a
manuscript with chapters opens **Manuscript & Analysis**, while a research-only
archive opens **Research & Dossiers**. Recent projects are browser-local (local
storage); the server keeps no journey state. Standalone read-only reports
(`controls=False`) render no welcome hero, no example link and no project
actions. The example link and the quickstart copy come from the same seven
language packs as the rest of the workspace, so the journey is localized like
every other control.

## Repository tooling

Maintained developer tooling lives in `scripts/` and is intentionally not
packaged. `check_release.py` builds, verifies and smoke-installs release
archives for the tag workflow; `sync_docs.py` owns release pins and the
current-version claim scan; `stage_pages.py` owns the public Pages boundary;
`make_screenshots.py` with `capture_screenshots.cjs` regenerates reviewed
public imagery; `run_browser_suites.py` with `browser_tools.cjs` runs the local
and manually dispatched browser checks; the `lixity-start.sh`/`.ps1`,
`lixity.service` and `lixity.plist` files are compatibility entrypoints that
delegate to `lixity service`. Workflow contracts are documented in
`CONTRIBUTING.md`; no script is a second implementation of engine behavior.

## Verification

- Python tests cover orchestration, configuration precedence, language resources
  and final-score dimension flagging.
- `tests/browser/style-space.cjs` checks synthetic dashboard interactions,
  tooltip escaping, idle rendering and mobile layout using optional Playwright.
- `tests/browser/research.cjs` uses a disposable loopback server and synthetic
  source archive to check project opening, record creation, evidence lifecycle
  states and responsive research controls.
- The wheel includes the bundled UI assets (five stylesheets and five scripts), Python modules and the typing marker.
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
