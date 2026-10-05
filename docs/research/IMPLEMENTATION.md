# Portable research implementation

## Implemented experimental pilot

The local workspace remains experimental. The first UTF-8 pilot shipped in
`v1.16.0`; current implemented commands and limits are documented in
[USAGE.md](USAGE.md). The [RFC](README.md) describes additional proposals.

The source-to-citation path and manual claim, evidence-link and decision records
are implemented, alongside PDF extraction, authored revision history and verified
archive export/restoration, explicit reconciliation previews, atomic related-record
revisions and structural editorial review. Local contracts
use `research-local/1` and `/2`; v1.19.0 adds `/3` for source versions carrying
a structured external reference, with a corresponding v3 manifest. New readers
preserve support for v1/v2; older readers reject v3. Native Poppler and Tesseract
activities use `research-local/4` and a v4 manifest; old v1–v3 records remain
readable without rewriting their provenance. See
[OCR compatibility](USAGE.md#use-local-ocr-without-a-worker-service).
Release v1.20.0 added
batch ingestion (`research-batch-ingest-local/1`), auto-fresh query index
caching, section-bounded dossier reading, and decision-dossier review tracking.
These contracts remain separate from the illustrative `research/1` bundle and
existing analysis schemas.

It uses Python 3.10+, existing Pydantic and the standard library. Python 3.10
loads TOML project settings through the conditional `tomli` dependency.
Research I/O stays out of `lixity.pipeline`. Native PDF extraction uses optional
Poppler tools; scans require local Tesseract or a configured OCR worker. The optional
Zotero bridge calls a local HTTP API. Installing Lixity does not download models
or contact a cloud library.

## Components

1. `research/models.py`: strict project/source/version/activity/extraction/passage
   contracts, pinned references, blob descriptors and schema export. Reject
   unsupported versions, unknown fields, invalid offsets and cross-project links.
2. `research/repository.py`: explicit project root, immutable objects, a
   hash-addressed manifest and atomic HEAD publication under an OS lock. Retain
   original source bytes and old citations after source refresh. Fail closed on
   corrupt objects, path escapes, conflicts and incomplete initialization.
3. `research/catalogue.py`: disposable SQLite/FTS5 projection tied to one manifest.
   Search only the newest version of each source; exact historical citations
   remain resolvable. v1.19.0 also indexes current dossier, claim and
   decision revisions through explicit scopes. Since v1.20.0, search checks
   current snapshot digest and refreshes stale projections automatically unless `--strict`
   is requested.
4. `research/analysis.py`: lean research analysis adapter reusing the existing
   `lixity.pipeline` without ambient configuration, mapping paragraphs to exact
   passage citations and source criticism context, with localized read-only dashboard.
5. `research/api.py` and `research/cli.py`: init, local text/PDF ingest with context,
   multi-file `research ingest --file ...`, section-bounded dossier reads,
   reindex, search, cite, audit, schema, analyze, dashboard, withdraw and purge
   with dry-run preview. `research revise-batch` previews related authored-record
   updates and applies them in one commit only after explicit selection. Require
   explicit project selection and local retention
   confirmation. JSON stdout; errors on stderr; `--progress` reports phase changes.
6. `research/models.py` and `research/api.py`: source tagging, dossiers with
   passage references and structured sections, manually recorded claims with
   scope and confidence, evidence links with explicit relations, and authorial
   decisions with dossier associations. A decision linked to a dossier updates
   its review status (`review_needed`), keeping the revision loop transparent.
   A selected `evidenced` confidence value or an unset deviation flag is not
   an automated fact check.
7. `server/routes_research.py` and shared `ui/research_panel.py` within
   `ui/dashboard.py`: interactive research management panel in the
   `lixity serve` dashboard (source ingest/listing and full source detail,
   FTS5 search with direct evidence selection, dossier creation and detail,
   dossier-linked claims, evidence/decision controls, reconciliation/change-set
   previews, structural review, and manuscript
   grounding comparison). Opening an existing project path attaches its
   `research/` archive, including research-only roots with no manuscript;
   importing manuscript text creates a new project. Manuscript comparison
   remains unavailable until a manuscript is loaded.
8. `research/zotero.py` (since v1.19.0): optional local-library preview and selected
   PDF/text capture, structured attachment identity, explicit source refresh and
   additive RIS export with original bytes and a mapping manifest. The bridge
   calls the local API; it does not modify Zotero's internal database.
9. `research/revisions.py` and `research/editorial.py`: immutable authored-record
   revisions, pinned associations, read-only reconciliation and batch preparation,
   and atomic batch application against an expected snapshot. Decision-impact
   and review reports use explicit links, dates and revision pins; they do not
   infer semantic contradictions or rewrite dossiers/manuscripts.

## Zotero and evidence ownership (since v1.19.0)

Zotero can lead bibliography and media management while Lixity owns the evidence
needed for analysis, citations, claims, dossiers and decisions. Keeping retained
captures in Lixity is intentional: changing or removing a Zotero attachment must
not silently change an existing quotation. Migration is additive and preserves
the original archive; a completed file export alone is not a verified migration.

Native Zotero 10.0.3 on Linux ARM64 has been exercised with synthetic text/PDF
imports and bridge text capture, refresh and search. This demonstrates that local
path, not compatibility with every platform, library or media format. Automated
tests use synthetic API responses and archives. Images, audio and video remain
managed externally; the bridge does not transcribe them or establish scan accuracy.

Follow [Research usage](USAGE.md) for migration and restore procedures. A Lixity
archive export preserves retained evidence, not the whole external Zotero library.
Keep and validate the two stores' backups before retiring any prior workflow.
There is no automatic background or cloud synchronization.

## Current integration boundary

The released pilot includes reliable research-panel state (including
status errors, record counts and selection retention), explicit display of
withdrawn or unavailable citations, neutral labels for authorial decisions,
seven-language interface coverage in the research and workspace views,
opening research-only project roots, regression checks, and synchronized user
documentation. English and German still have the deepest analysis heuristics;
interface translation does not change research JSON or certify a claim. Source
and dossier details are available in the web panel, as are direct search-to-
evidence actions and dossier association from the claim form. Purged passage
references stay visible as unavailable in retained authored records, without
exposing deleted quotation text. The CLI and Python API accept structured source
criticism context; the web import form provides the supported title, tags and
origin-URL fields described in [Research usage](USAGE.md).

Comparison uses chapter body prose for both source and manuscript where
chapters exist, excluding headings, front matter and the configured appendix
from lexical counts, register contrasts and chapter traces. Signed keyness
uses the full term/nonterm $2\times2$ G² table. On a language mismatch the
result retains numeric overlap but adds `meta.lexical_comparable: false` and
`comparison_limits: ["cross_language_lexical_comparison"]`; the web panel
warns that lexical scores are not directly comparable. Source analysis uses
`original_language_supplied` in place of the earlier experimental
`historical_language` limitation code, since a supplied original-language
field does not itself imply historical language variety.

## Verification scope

Synthetic tests cover Unicode/CRLF citation offsets and schema validation;
source refresh with preserved old citations; cross-project references and
tampered blobs/manifests/revisions; interrupted HEAD publication, locks and stale
snapshots; verified restore/reindex and FTS input; CLI exit codes and no-write
dry-runs; withdrawal and purge; authored-record API/CLI round trips and evidence
integrity; and HTTP research dispatch/error envelopes. Reconciliation and batch
tests cover preserved pins and rejection of stale/invalid operations without a
partial commit. Native PDF tests use synthetic documents; Tesseract and worker
protocol tests use synthetic engines/responses, not a recognition-quality corpus.

These checks exercise local contracts, not historical accuracy or every external
OCR/Zotero environment. Research storage and analysis schemas remain separate.
See [contributor checks](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md)
for execution and platform coverage.

## Deferred explicitly

Probabilistic claim synthesis, automated factual certification, migration of legacy third-party dossiers,
a bundled production OCR runtime, automatic Zotero synchronization, hybrid vector
retrieval, and multi-tenant shared cloud services remain separate future increments.
Local retention does not imply permission to redistribute sources. This pilot is not a hostile multiuser filesystem service.
