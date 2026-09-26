# Local research pilot

**In local development (target `1.16.0.dev0`), unreleased and not in release `v1.15.0`.**
This pilot archives local UTF-8 text, attaches versioned source criticism context and tags,
resolves exact citations, manages dossiers with cited evidence, provides an interactive web
management UI in `lixity serve`, connects to the analysis pipeline, and performs cross-corpus
grounding comparisons against manuscripts. It does not implement the entire [RFC](README.md).

| Available in development | Not implemented |
| --- | --- |
| Explicit project, immutable captures, paragraph citations | Claims, author decisions (probabilistic) |
| SQLite/FTS5 lexical search, instant index rebuild | Embeddings, dense hybrid search, Qdrant, Haystack |
| Local text / Markdown input, original bytes retained | PDF/OCR, Zotero, network imports, archive exchange |
| Versioned source criticism context & core analysis adapter | Multi-tenant team services, cloud hosting |
| Controlled withdrawal & physical purge with dry-run preview | Automated factual proof or rewriting prose |
| Read-only HTML source dashboard with localized context | Ambient configuration discovery |
| Integrity audit and snapshot conflict detection | Ambient manuscript detection |
| Source listing & tagging (`lixity research sources`) | External web scrapers |
| Dossier creation & inspection (`lixity research dossier`) | Automatic claim reconciliation |
| Cross-corpus linguistic grounding (`lixity research compare`) | Full-document OCR |
| Interactive web research panel in `lixity serve` | |

## Try it

Use a development checkout: `make install-dev`, then activate `.venv`.
Existing release installations do not acquire these commands automatically.
Requires SQLite with FTS5; no additional Python dependencies or models.

```bash
lixity research init --project ./novel --title "Novel research" --language en
lixity research ingest --project ./novel --file ./notes.txt --allow-retention --dry-run
lixity research ingest --project ./novel --file ./notes.txt --context ./context.json --allow-retention
lixity research reindex --project ./novel
lixity research sources --project ./novel
lixity research search --project ./novel --query "reading room" --limit 5
lixity research audit --project ./novel
```

Use a `passage_id` from search and a `source_id` from ingestion:

```bash
lixity research cite --project ./novel --passage urn:uuid:YOUR-PASSAGE-UUID
lixity research analyze --project ./novel --source-id urn:uuid:YOUR-SOURCE-UUID
lixity research dashboard --project ./novel --source-id urn:uuid:YOUR-SOURCE-UUID > source.html
lixity research compare --project ./novel --source-id urn:uuid:YOUR-SOURCE-UUID --manuscript ./novel.md
lixity research dossier --project ./novel --title "Reading Room Notes" --body "Opened in 1924." --evidence urn:uuid:YOUR-PASSAGE-UUID
lixity research dossier --project ./novel --list
lixity research withdraw --project ./novel --source-id urn:uuid:YOUR-SOURCE-UUID --reason "License revoked"
lixity research purge --project ./novel --source-id urn:uuid:YOUR-SOURCE-UUID --dry-run
lixity research purge --project ./novel --source-id urn:uuid:YOUR-SOURCE-UUID --reason "GDPR deletion"
lixity research ingest --project ./novel --file ./revised-notes.txt \
  --source-id urn:uuid:YOUR-SOURCE-UUID --allow-retention
lixity research reindex --project ./novel
lixity research schema

# Or launch the interactive web dashboard with integrated research panel:
lixity serve --research-project ./novel --no-project
```

Replace the uppercase placeholders with returned IDs. Search uses the newest
capture of each source. Earlier passage IDs still cite their original bytes.
Repeating a refresh with unchanged bytes is a no-op. Without `--source-id`, each
ingestion creates a distinct source; identical text is not proof of identity.

`--allow-retention` confirms that you may keep a local copy. It does **not** grant
copyright permission, authorize redistribution or accept a factual claim.
Passages remain `unreviewed`. All commands emit JSON (except `dashboard` which emits HTML);
exit codes are `0` success, `1` operational/integrity failure and `2` CLI usage error.
A failed audit returns `ok: false` and exit code `1`. Other errors go to stderr without source contents.

## Python API

```python
from lixity.research import api

api.init("./novel", title="Novel research", language="en")
capture = api.ingest("./novel", "notes.txt", allow_retention=True, context={"genre": "diary", "tags": ["archive"]})
api.reindex("./novel")
sources = api.list_sources("./novel")
results = api.search("./novel", "reading room", limit=5)
if results["hits"]:
    citation = api.cite("./novel", results["hits"][0]["passage_id"])
    dossier = api.create_dossier(
        "./novel",
        title="Reading Room Record",
        body="Verified opening in 1924.",
        evidence_ids=[results["hits"][0]["passage_id"]],
        tags=["milestone"],
    )
dossiers = api.list_dossiers("./novel")
analysis = api.analyze_source("./novel", capture["source_id"])
html = api.source_dashboard("./novel", capture["source_id"])
comparison = api.compare_source("./novel", capture["source_id"], "novel.md")
api.withdraw("./novel", capture["source_id"], reason="License revoked")
preview = api.purge("./novel", capture["source_id"], dry_run=True)
report = api.audit("./novel")
```

The project argument is mandatory. Research never discovers a project from a
manuscript or reads analysis thresholds. `lixity build` remains unchanged and
never imports sources or refreshes research indexes.

## Storage, lifecycle and recovery

- `research/project.json`: immutable initial project configuration.
- `research/revisions/`: immutable, schema-checked records.
- `research/blobs/`: SHA-256-addressed original UTF-8 bytes; no normalization.
- `research/manifests/`: complete snapshots; `research/HEAD.json` selects one.
- `.lixity/research/`: disposable catalogue and writer lock.

### Withdrawal vs. purge

- **Withdrawal (`withdraw`)**: Preserves the audit trail and archived source text,
  records a tombstone in the manifest, excludes the source or version from default
  search, and marks existing citations as `availability: "withdrawn"`. Analysis
  fails closed for withdrawn sources.
- **Purge (`purge`)**: Permanently removes source records, extraction records,
  and passage records from the store and unlinks unshared original blobs. Citations
  for purged passages fail closed with `ResearchError`. Supports `--dry-run` to preview
  affected records and blobs before deletion.

### Cross-corpus comparison and evidence grounding

- **Linguistic comparison (`compare`)**: Connects an archived research source with a literary
  manuscript without modifying either document. Computes:
  1. Lexical overlap and alignment (Jaccard similarity, Szymkiewicz–Simpson overlap coefficient,
     top shared terms, exclusive source terms).
  2. Keyness differential using Dunning's $G^2$ log-likelihood ratio (identifying terms significantly
     over-represented in the research source vs. the manuscript corpus).
  3. Register and stylistic contrast (sentence length ASL delta, dialogue ratio delta,
     lexical diversity Guiraud's $R$ and Yule's $K$ deltas, staccato and kaskade deltas).
  4. Per-chapter evidence grounding (mapping occurrences of source vocabulary and top key
     terms across individual manuscript chapters, reporting grounding density per 1,000 words).

Back up the **entire `research/` directory**, preferably while no writer is
running. Restore it to an explicit project root, run `audit`, then `reindex`.
Never restore only SQLite. Do not commit private source text to a public
repository: both blobs and passage records contain it.

Writes use an OS lock, immutable publication and atomic HEAD replacement.
Uncommitted objects left after interruption are ignored, not selected by date.
Locks release when the process exits. A stale expected HEAD fails rather than
overwriting another ingestion. Interrupted initialization may leave an incomplete
directory: preserve it for inspection; `init` refuses to overwrite it.

Files are flushed before publication; directory syncing is used on POSIX.
Power-loss guarantees remain filesystem/platform-specific, not certified by the
interruption tests. Use a local filesystem, not a shared drive. Internal symlinks
are rejected; a project directory is not a hostile multiuser sandbox.

## Limits

The experimental schemas are `research-local/1` and operation-specific `*-local/1`
envelopes, not the RFC's illustrative `research/1` bundle. Unknown fields and
versions are rejected. No migration of existing dossiers or the RFC fixture is
claimed. Source identity metadata cannot yet be edited; refresh creates a new
source version, not a changed old record.

Inputs are at most 2 MiB and 5,000 nonempty paragraphs. Only valid UTF-8 without
NUL bytes is accepted. Search uses literal Unicode words joined with AND; it is
not stemming, translation or semantic search. BM25 scores are ranks, not truth
probabilities. Language tags do not translate quotations. Empty queries, stale
indexes and missing FTS5 support produce errors, not silent fallbacks.

Audits check retained records, hashes and citations, not factual accuracy,
permissions or historical completeness.
The [non-commercial licensing rules](../LICENSING.md) still apply.
