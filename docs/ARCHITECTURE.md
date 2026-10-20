# Architecture and integration boundaries

This document records shared responsibilities and integration boundaries.
Product maturity, response schemas and research storage versions are independent.
[Usage](USAGE.md) owns workflows; [automation](AGENTS.md) owns request and result
contracts; [research usage](research/USAGE.md) describes implemented archive behavior.
The [research RFC](research/README.md) includes unimplemented proposals.

`lixity.research` owns explicit-project captures, immutable snapshots, citations,
authored records and a rebuildable SQLite/FTS5 index. It does not import into
`lixity.pipeline`. Source analysis may use the shared engine and UI, but research
sources never join manuscript baselines automatically.

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
| `config` / `io` / `workspace` | Explicit project metadata, atomic byte I/O and manuscript discovery | Implicit identity/publication defaults or duplicate writers |
| `lixity.service` | Managed local process lifecycle (start/stop/restart/status) | Adopting externally managed units |
| Project adapters | Manuscript access, publication actions and local services | Copies of the engine |

`lixity.math_core` is the single mathematical vocabulary of the analysis core
(robust scale, significance z, normal tail, ratio/share/density totalization,
plug-in standard errors and published effect bands). Heuristics import it
instead of restating formulas; `style_fingerprint` re-exports the historical
names for callers.

The server separates transport (`runtime`, `_base`, `handler`), selected-workspace
state (`_state`), dashboard assembly (`views`) and domain route groups. Registered
route tables drive dispatch and discovery. Handlers validate and shape requests,
then delegate to the shared pipeline or `research.api`; they do not implement a
second renderer, analysis algorithm or archive writer.

One process has one selected workspace. Opening selects an existing project;
importing browser bytes creates one at an explicit destination. A browser filename
does not identify its original parent directory. An archive may open without a
manuscript. `workspace.resolve_project_target` resolves explicit selectors; API
research calls stay explicitly scoped. An occupied port fails startup.

`DocumentAnalysis` reuses corpus/chapter measurements for the fingerprint and
renderers. Narrower profile/fingerprint requests use the same pipeline. Dashboard
refresh detects changed manuscript bytes before serving cached measurements.
Research overviews reuse one validated archive snapshot without a persistent cache.

## Manual manuscript associations

`research.manuscript` owns `ManuscriptClaimLink`, separate from imported source
evidence. Explicitly permitted quote retention pins a reviewed claim revision and
an immutable `paragraph-profile-text/1` anchor: project-relative path, source and
displayed-paragraph hashes, source lines and Unicode-codepoint offsets. The first
opted-in save requires record/manifest v7; reads never upgrade existing archives.
Historical v3.0.1 supports only v1–v6 despite its higher product number.

`pipeline.paragraph_identity` supplies the same identity to rendering and research.
`FileUtils.read_source_snapshot` binds raw bytes and decoded text; creation checks
source containment and bytes again before publication. Review uses the validated
archive snapshot and existing pipeline paragraphs. It preserves anchors and claim
pins, distinguishes missing from unreadable sources, and leaves ambiguous or moved
candidates for explicit review. It does not infer factual support.

Manuscript routes validate both selected manuscript and archive contexts before
calling the API. Saved-quote counts join explicit associations from one coherent
snapshot, disclose differing revision pins and do not establish manuscript use or
nonuse. Rendering preserves exact resolved quote spans and complete text search.

Ordinary authored CLI updates require a reviewed revision, change kind and reason;
when the archive snapshot is omitted, the backend's current read guards the same
strict writer. Changed associations require reviewed pins; races fail without retry.
`research.revisions` shares candidate validation across exact writes,
dry runs and batch preparation. Prospective comparison uses one snapshot for both
values; historical comparison resolves saved revisions without repinning. Section
reconciliation changes only the selected body subtree while ordinary field changes
use the same candidate. HTTP, images, acknowledgements and batches retain their
explicit guards. No preview establishes that a future write will succeed.

`research.dossier_edit` encodes an explicit leading JSON comment and
the exact body as a Markdown draft. It validates identity/base and delegates to
existing three-way preparation; ready changes become ordinary batch operations.
Versioned reviewed packets bind project and snapshot through the shared backend.
The archive stays authoritative: there is no parallel store, watcher or two-way
sync. Exports use exclusive publication outside the archive/internal directory.
The canonical project writer lock remains the only mutex; diagnostic error types
distinguish contention, read-only/permission failures and other I/O errors.

## Configuration and multiple projects

Explicit root settings own author identity, publication, chapter registers and
project-local character profiles; user/ancestor defaults cannot supply them.
`project_identity` compares only bounded
manuscript metadata syntax, without rewriting text or affecting measurements.
`PublicationSettings`/`PUBLICATION_FIELDS` supply field validation to configuration,
settings and PDF composition. `pdf_export.compose_pdf` composes bytes for CLI and
HTTP; callers own output writes. Front matter uses entered data, and syntax checks
do not establish publication compliance.

Since v0.7.0, manuscript PDFs use one presentation projection
(`manuscript_document`) of the shared Markdown blocks. It retains structure and readable
inline styles rather than using the statistical prose filter. Book, editorial
and submission layouts share block placement and the same PDF document engine;
the analysis report retains its metric tables. Editorial geometry reuses
`BookLayoutConfig`, which also remains available to embedding adapters.

`config.prepare_project_settings` validates one settings candidate while
preserving unrelated TOML values. The route renders that candidate,
commits through `PreparedProjectSettings`, then publishes session/cache state.
Decode, validation, render or replacement failures publish none of the candidate.
Selected-context tokens bind source/root and both root config digests. Publication/
register saves and manuscript PDF downloads reject stale required context. Config
reads accept regular nonsymlink files and verify the opened descriptor's identity.
The optimistic commit guard checks observed identity and bytes immediately before
replacement; it is neither an external-editor lock nor a manuscript content pin.

**Since v0.6.0:** explicitly requested language/threshold defaults
reuse this transaction and its project token. Session-only Apply remains the
default. Installed configuration metadata derives publication bounds from the
same model/field registry used by rendering and validation.

`FileUtils.atomic_write_bytes_if_changed` is the shared text/binary writer:
same-directory staging, complete write, flush, mode preservation, fsync and atomic
replacement. Unchanged bytes skip replacement and its optional guard. Errors
propagate, temporary stages are cleaned, and no direct-overwrite fallback exists.
`Workspace.publish` preserves distinct same-minute artifacts, recognizes historical
archive names and prepares the stable artifact before replacement. Failure stops
before archive rotation.

`load_project_config(path)` searches from its supplied path and merges supported
project/user settings. Pass the intended mapping to `resolve_document_config` and
`resolve_thresholds`; explicit options win. An empty mapping selects code defaults
without discovery. The facade's `profile`, `fingerprint`/`passport` and `dashboard`
accept that mapping; `None` retains threshold discovery for compatibility.
Use `analyze_document(text, config, thresholds)` when several outputs need the same
measurements. Project adapters own their characters, motifs, paths and artifacts.

The shared Markdown parser defines measurement prose and chapter numbering.
Inline counting retains visible link labels and excludes link targets,
images and code. It stays separate from displayed paragraph text and quote identity;
zero-token chapters retain their source numbering. `characters.CharacterProfile`
owns literal alias/declared-POV validation and its discoverable schema; one resolver
serves CLI, API and dashboard. Declared POV stays separate from lexical mention counts.
Paragraph profiles cover body/list blocks; legacy whitespace counts remain
separate. Token regex flags are preserved, while linguistic cue patterns have a
case-insensitive compiler. [Methods](METHODS.md) defines exact scopes and numerical
conventions. Scene groups compare only explicitly assigned manuscript observations.

Research revision preparation, section edits and grouped saves reuse strict
validation and one repository commit. Section reads, preparation and image placement
share the code-aware ATX heading parser. Review follows recorded links and revision
pins, without inferring contradictions. Images reuse immutable source/version/blob
records, never fabricated text passages; textual analysis rejects them. Attachment
and dossier revision publish atomically. Purge retains identity for honest unavailable
placeholders, not image bytes. Shared limits come from `research.limits`.

## Presentation and trust boundaries

The dashboard is a self-contained HTML file. Python bundles CSS and scripts; no
CDN or frontend build step is required. Chapter-title tooltips use text nodes,
not executable markup. Rendering and point picking share projected coordinates. Animation
is scheduled only while rotation is enabled and the page is visible. The live
shell applies a per-response script nonce and default-deny CSP; bundled components
require no `unsafe-eval`.

Research media reuse bundled PhotoSwipe 5.4.4 for retained images and
generated diagrams. Mermaid tiny 12.2.0 owns diagram syntax/layout and initializes
only when a diagram first becomes visible; restrictions disable resource loading,
click actions and configuration directives, with source retained on failure.
Leaflet 1.9.4 provides geographic vectors. **Current main, after v0.7.1:** visible
maps load OpenStreetMap tiles by default; users can turn off the background or
choose the offline sketch. Tile requests stop outside the visible map/project
context. Tiles reveal the client IP and viewed area;
attached historical images remain independent evidence, not calibrated basemaps.

### Logging

`src/lixity/log.py` is the one logging entry point. Modules log through
`get_logger()` under the `lixity` tree; the CLI keeps stdout as its result
channel and sends diagnostics through logging. Lines use a single UTC format
(`YYYY-MM-DD HH:MM:SS UTC LEVEL lixity.<area> message`) with standard levels,
resolved from an explicit argument, else `LIXITY_LOG_LEVEL`, else DEBUG while
`LIXITY_DEBUG`/`--debug` is active, else INFO.

The managed service appends the child's stderr to `service-PORT.log`;
`rotate_service_log()` bounds that file at service start (one writer per file,
rotated to `.1`–`.3`). The stderr handler follows `sys.stderr` at emit time,
so `redirect_stderr`, the captured service descriptor and tests all see the
same stream. Request logs never contain query strings — context tokens and
selectors travel there — and log records never contain manuscript text.

`ui/dimensions.py` renders a semantic score table from the same measured points
as the canvas. It keeps chapter titles, available scores and native chapter links
usable without JavaScript; native rotation/zoom controls call the same projection
renderer. Unmeasured chapters and absent axes are omitted.

### Visual consistency and evidence

The local dashboard and Pages share `ui/assets/design-tokens.css`; components and
surface styles own actual color, typography, spacing and control rules. Heatmap
text selects contrast from cell luminance. Native controls, visible boundaries,
focus outlines and non-color cues support navigation. [WCAG contrast](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html),
[target size](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html)
and [text-spacing overrides](https://www.w3.org/WAI/WCAG22/Understanding/text-spacing.html)
inform the checks; defaults are product choices, not universal typographic optima.
Exact tokens and dimensions belong to CSS and executable checks rather than a
second prose specification.

The manuscript is the primary workspace. Analysis supports passage selection
and interpretation; retained evidence and authored dossiers provide context.
These are connected views over the same project, not independent products.

**Current main, after v0.7.1:** interactive dashboards use a fixed project sidebar
on wide screens, with manuscript/analysis first, research second and settings
third. Narrow screens keep a horizontal switcher. Tab orientation and keyboard
navigation change together; the sidebar scrolls independently if its controls
exceed the viewport. Plain exported reports retain their document layout.
Both presentations use the same renderer, labels, data and action handlers.
The desktop navigation uses the shared `ctl` toggle. Companion reading applies a
temporary collapse override only in the analysis view; closing restores the manual
choice. Responsive changes keep the mobile switcher available. Exact manuscript
return actions reuse the existing paragraph navigation and the same anchor matcher
as inline association marks, with a current project/source context check on click.

### Shared manuscript reader

**Current main (unreleased):** `ui/manuscript_reader.py` emits one shared control
surface for interactive dashboards. Bundled `manuscript-reader.js` and
`manuscript-reader.css` enhance the existing paragraph tree: **Read** renders
continuous text; **Inspect** retains the established chapter strips, comparisons
and lazy paragraph interaction. There is no second manuscript projection or text
copy. Source text, paragraph hashes, line anchors, search and association matching
keep their existing owners. Plain exports retain the inspection layout, and the
no-JavaScript fallback remains a static document.

The canonical tree comes from `ParagraphProfiler`'s analysis projection: prose
and list-item paragraphs with chapter titles. It excludes subheadings, block
quotations, dividers, code and footnote definitions; pipe tables retain literal
text rather than a table layout. Upstream appendix exclusion remains in force.
This is distinct from `manuscript_document`, used for structured manuscript PDFs;
reading controls do not change analytical coverage or source-anchor semantics.

The reader uses native buttons, selects and disclosures with shared `ctl` styles
and the seven-language label pack. Size, width, spacing and mode preferences live
in browser storage; denied or malformed storage falls back to usable defaults.
Focus mode is reversible and temporary. Layout changes capture the first visible
paragraph and restore its viewport position after reflow where possible, rather
than persisting a second text offset or editing manuscript content.

Paragraph ellipsis buttons, pointer context menus and keyboard context-menu
shortcuts share the same action builder. A valid single-paragraph selection
offers a small toolbar. Marker and claim actions delegate to the established
handlers, including their explicit save, capability and retention checks; no
parallel write API is introduced. Values reuse the paragraph's measured markup
in a closable inspector. Opening the inspector closes the companion and opening
the companion closes the inspector, keeping one side tool active. Menus expose
arrow/Home/End navigation and restore trigger focus on Escape.
Association refreshes skip unchanged annotation DOM and preserve native selection
endpoints when marks change. Automatic review uses the existing research-status
read before requesting archive records; context-bound pending reads are coalesced
and invalidated on project changes.

The companion's desktop `separator` supports pointer dragging and keyboard
adjustment over a bounded manuscript-width share. The split is a local display
preference, hidden when readers stack on narrow screens. Images, geographic maps
and style-space retain their existing PhotoSwipe, Leaflet and canvas interactions;
manuscript dragging continues to select text. The reader does not create a
free-panning manuscript canvas or a manuscript editor.

The interface follows a reading-first hierarchy: a passage or visual comes
before its detailed measurements; advanced explanations stay near the control
that needs them. Diagram frames follow content width within the reader, and
wide diagrams retain their label scale in a scrollable viewport. Style-space
navigation groups paired actions at responsive widths. Pages uses the shared
tokens and stylesheet, with direct demo and installation entry points and
screenshots of the same native components rather than a parallel product UI.

Native `details` elements own research composer visibility. Their field DOM stays
mounted across collapse and tab switches, preserving in-memory drafts without
introducing another state store. Shared disclosure helpers reveal ancestors for
contextual navigation and collapse the innermost level with focus restoration.
The companion delegates nested disclosure Escape handling before closing itself.
The shared component stylesheet also supplies disclosure affordances to Pages;
reduced-motion preferences disable arrow transitions. Catalogue previews derive
plain text using the existing safe renderer, without changing API contracts.

Publication and execution are separate boundaries. The Pages demo follows the
reviewed source checkout; the release badge names the published package. A local
installation replaces package files, while the managed service must restart to
load them. Unreleased builds can have the same product version, so parity checks
compare relevant asset bytes rather than relying on a version string alone.

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

`ui.components` and `assets/components.css` own shared panels, controls, fields,
status messages, badges and layout primitives. Views reuse them and the stable
[data hooks](AGENTS.md#34-dashboard-interaction-contract-for-embedding-and-ui-automation).
Visible strings come from the seven-language packs; mathematical identifiers stay
language-neutral. Prefer native elements and one primary action per form.

Local view tabs (style views, research and dialogs) share one component recipe:
a selected underline and surface distinguish navigation from primary actions.
Each tablist has an accessible name; project-dialog tabs explicitly name their
panels. The shared keyboard controller keeps one tab stop, follows orientation
and uses manual activation for research views that fetch data. Dialog switching
is scoped to the containing dialog so it cannot reset another editor.

Native `<dialog>` supplies modality, Escape and focus restoration. The shared
dialog frame keeps the title and close action above a scrolling form, uses
dynamic viewport height, and allows footer actions to wrap. Tabbed forms scroll
in their pane; direct forms scroll in the body. Avoid introducing competing
scroll containers or a custom focus trap. The [WAI dialog pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/)
and [WCAG focus visibility](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum)
guide this behavior; targeted tests do not constitute a full accessibility audit.

Field groups, form rows, labels, disabled actions and feedback use the shared
component layer. Disabled buttons do not show enabled hover/pressed feedback.
Labels preserve localized casing. Research catalogues use separated rows within
their enclosing panel; nested evidence and detail surfaces retain their own
boundaries. Keep these view-specific layouts in `dashboard.css`.

Inline styles are reserved for measured/dynamic values. Layout and responsive
stacking belong in shared CSS; `tests/test_inline_styles.py` checks forbidden
spacing/typography patterns. New panels must remain usable at 320 px.

### Design system: one scale, one control language

CSS bundles in token → component → view order. The shared token and component
owners above apply to Pages and the dashboard; browser checks sample token use,
focus, contrast and text spacing.

### Stateful panels: the component layer (vendored Preact + HTM)

The Python renderer feeds both the live workspace and standalone exports.
Stateful research lists use vendored Preact/HTM through `LixityComponents`;
`vendor/README.md` owns the update procedure. Components own only their mounted
subtree, receive plain data and use shared localization helpers. Unmount before
imperative writes to their hosts; async card content belongs in the list model.
Stable class/data hooks remain part of component output. Domain actions, context
guards and pagination stay in panel scripts. Record keys preserve current details
or invalidate stale card state according to each renderer's refresh contract. Other panels migrate only
when their state requires it; a new component is not a second business-rule layer.

## First-run journey (server contract)

Empty workspaces offer create/open/import actions. After a successful workspace
transition, a fresh render opens manuscript analysis when chapters exist, otherwise
research. Recent projects live only in browser storage. Standalone read-only
reports expose no project actions or welcome journey. Shared language packs own
the copy; the optional public-example link does not affect offline operation.

## Repository tooling

Developer tools in `scripts/` operate releases, documentation staging, public
examples and browser checks; they are not packaged engine behavior. Existing
platform startup scripts delegate to `lixity service`. [CONTRIBUTING.md](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md)
owns workflows and checks; `make help` lists entrypoints.

## Verification

Python checks cover domain behavior, orchestration, language resources, transport
and versioned contracts. Optional browser suites inspect synthetic desktop/mobile
workflows. Release verification compares packaged modules, UI assets and typing
metadata against source bytes. Adapter tests belong with their project; no private
manuscript is required. See [contributor checks](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#development-setup).

## External research libraries (since v1.19.0)

Zotero owns acquisition, bibliographic editing, ordinary reading and notes.
Lixity owns retained evidence, authored project records and manuscript associations.
The optional `research.zotero` adapter captures selected evidence through the
[local HTTP API](https://www.zotero.org/support/dev/web_api/v3/local_api); it never
reads or writes Zotero's database. Keep the attachment selector and source-return
actions small. The retained passage reader serves evidence selection and review.
Captures preserve the version used by a claim independently of Zotero; they are
not a live library mirror. UI consolidation preserves source IDs, historical
citations and storage contracts.

The adapter adds no runtime dependency and bundles no Zotero application code.
Its additive RIS export preserves sources/citations and delegates import to
Zotero's supported workflow. Stable external attachment identities distinguish
repeated captures from refreshes; migration tags plus original-byte checksums can
associate an existing evidence source. Titles never establish identity.

Source versions with `external_reference` use `research-local/3`; their snapshots
use `research-manifest-local/3`. Readers support prior v1/v2 records without
rewriting them. Older applications reject v3 instead of silently dropping the
external identity. Evidence captures and references remain in Lixity backups;
Zotero's library and unselected media require their own backup.

Zotero is optional for existing analysis and retained evidence. There is no
automatic background or cloud synchronization. Since v0.7.0 it also captures
PNG/JPEG through the shared image pipeline; visual sources have no text passages.
Audio/video and other unsupported media remain managed in Zotero.
See [research usage](research/USAGE.md#zotero-desktop-bridge-since-v1190)
for implemented behavior and portability limits.

Since v0.7.0, optional, bounded GeoJSON is stored within existing Dossier revisions
(record/manifest v8). The same revision, conflict, search and backup paths apply;
ordinary dossiers retain their older encoding until a geographic save. Older
readers cannot open v8 archives. A shared offline coordinate view
serves dossier, history and manuscript-companion readers. Images remain separate
versioned sources; neither their presence nor a route line establishes geographic
calibration, navigability or historical accuracy.
