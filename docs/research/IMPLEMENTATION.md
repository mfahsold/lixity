# Portable research implementation

## First slice

Implementation status: unreleased pilot under local development (target `1.16.0.dev0`; not in release `v1.15.0`). Commands and limits are
documented in [USAGE.md](USAGE.md). This is not a release announcement.

Implement the source-to-citation path before provider integration or editorial
review. The RFC remains the target architecture; this slice does not implement
the entire first increment. Its experimental contract is `research-local/1`,
separate from the illustrative `research/1` bundle and existing analysis schemas.

Use Python 3.10+, existing Pydantic and the standard library. Keep research I/O
out of `lixity.pipeline`. No model downloads, remote calls or new dependencies.

## Execution plan

1. `research/models.py`: strict project/source/version/activity/extraction/passage
   contracts, pinned references, blob descriptors and schema export. Reject
   unsupported versions, unknown fields, invalid offsets and cross-project links.
2. `research/repository.py`: explicit project root, immutable objects, a
   hash-addressed manifest and atomic HEAD publication under an OS lock. Retain
   original UTF-8 bytes and old citations after source refresh. Fail closed on
   corrupt objects, path escapes, conflicts and incomplete initialization.
3. `research/catalogue.py`: disposable SQLite/FTS5 projection tied to one manifest.
   Search only the newest version of each source; exact historical citations
   remain resolvable. Reject stale indexes rather than silently mixing snapshots.
4. `research/analysis.py`: lean research analysis adapter reusing the existing
   `lixity.pipeline` without ambient configuration, mapping paragraphs to exact
   passage citations and source criticism context, with localized read-only dashboard.
5. `research/api.py` and `research/cli.py`: init, local text ingest with context,
   reindex, search, cite, audit, schema, analyze, dashboard, withdraw and purge
   with dry-run preview. Require explicit project selection and local retention
   confirmation. JSON stdout; errors on stderr; dry-run does not write.
6. `research/models.py` & `research/api.py`: Source tagging, Dossier entities with
   verifiable evidence references, source listing, and dossier retrieval.
7. `server.py` & `ui/dashboard.py`: Interactive research management panel in the
   `lixity serve` development dashboard (Sources ingest/listing, FTS5 search,
   visual Dossier creation, and Manuscript grounding comparison).
8. Synchronize README, Pages, agent/API guidance and the implementation status.

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
- Web server endpoints (`/api/research/*`) correctly dispatch and handle errors.
- Run the existing checks; analysis output schemas and pipeline remain unchanged.

## Deferred explicitly

Probabilistic claim synthesis, author decisions, migration of legacy third-party dossiers,
PDF/OCR pipelines, Zotero synchronization, hybrid vector retrieval, and multi-tenant
shared cloud services remain separate future increments. Local text ingestion does not imply permission to
redistribute sources. This pilot is not a hostile multiuser filesystem service.
