# Portable research implementation

## Implemented experimental pilot

Implementation status: experimental local workspace in `v1.19.0`. The first UTF-8 pilot shipped in `v1.16.0`.
Commands and limits are documented in [USAGE.md](USAGE.md).

The source-to-citation path and manual claim, evidence-link and decision records
are implemented, alongside PDF extraction, authored revision history and verified
archive export/restoration. The RFC remains a target architecture. Local contracts
use `research-local/1` and `/2`; v1.19.0 adds `/3` for source versions carrying
a structured external reference, with a corresponding v3 manifest. New readers
preserve support for v1/v2; older readers reject v3. These contracts remain separate
from the illustrative `research/1` bundle and existing analysis schemas.

It uses Python 3.10+, existing Pydantic and the standard library. Python 3.10
loads TOML project settings through the conditional `tomli` dependency.
Research I/O stays out of `lixity.pipeline`. Native PDF extraction uses optional
Poppler tools; scans require a separately configured OCR worker. The optional
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
   remain resolvable. v1.19.0 also indexes the current dossier, claim and
   decision revisions through explicit scopes; the CLI default remains source
   passages. Reject stale indexes rather than silently mixing snapshots.
4. `research/analysis.py`: lean research analysis adapter reusing the existing
   `lixity.pipeline` without ambient configuration, mapping paragraphs to exact
   passage citations and source criticism context, with localized read-only dashboard.
5. `research/api.py` and `research/cli.py`: init, local text/PDF ingest with context,
   reindex, search, cite, audit, schema, analyze, dashboard, withdraw and purge
   with dry-run preview. Require explicit project selection and local retention
   confirmation. JSON stdout; errors on stderr; ingestion dry-run leaves the
   research archive unchanged.
6. `research/models.py` and `research/api.py`: source tagging, dossiers with
   passage references, manually recorded claims with scope and confidence,
   evidence links with explicit relations, and authorial decisions. A selected
   `evidenced` confidence value or a decision without a deviation flag is not
   an automated fact check.
7. `server.py` & `ui/dashboard.py`: Interactive research management panel in the
   `lixity serve` dashboard (source ingest/listing and full source detail,
   FTS5 search with direct evidence selection, dossier creation and detail,
   dossier-linked claims, evidence/decision controls, and manuscript
   grounding comparison). Opening an existing project path attaches its
   `research/` archive, including research-only roots with no manuscript;
   importing manuscript text creates a new project. Manuscript comparison
   remains unavailable until a manuscript is loaded.
8. `research/zotero.py` (since v1.19.0): optional local-library preview and selected
   PDF/text capture, structured attachment identity, explicit source refresh and
   additive RIS export with original bytes and a mapping manifest. The bridge
   calls the local API; it does not modify Zotero's internal database.

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

## Acceptance checks

- Test-first source ingestion, Unicode/CRLF quotation offsets and schema failures.
- Refresh a source; old citations still resolve, default search uses new text.
- Reject cross-project references and tampered blobs/manifests/revisions.
- Simulate failure before HEAD publication; ignore uncommitted objects.
- Exercise lock contention, stale expected heads, restore/reindex and FTS input.
- Exercise CLI success/error/usage codes and no-write dry-runs.
- Controlled withdrawal marks citations and excludes sources from search.
- Purge with dry-run preview removes records and unshared original blobs.
- Dossier creation validates evidence references and integrity invariants.
- Web server action endpoints (`/api/research-*`) dispatch and handle errors.
- Claim, evidence-link and decision records round-trip through the API and CLI.
- Run the existing checks; analysis output schemas and pipeline remain unchanged.

## Deferred explicitly

Probabilistic claim synthesis, automated factual certification, migration of legacy third-party dossiers,
a bundled production OCR runtime, automatic Zotero synchronization, hybrid vector
retrieval, and multi-tenant shared cloud services remain separate future increments.
Local retention does not imply permission to redistribute sources. This pilot is not a hostile multiuser filesystem service.
