# Local research pilot

**Experimental local research archive system in `v1.17.0`.**
This component archives local UTF-8 text and PDF documents, attaches versioned source criticism context and tags,
resolves exact citations, manages dossiers with cited evidence, provides an interactive web
management UI in `lixity serve`, connects to the analysis pipeline, and performs cross-corpus
grounding comparisons against manuscripts. Authors can record claims,
passage-to-claim evidence relations and authorial decisions, with full native revision history.
It does not implement the entire [RFC](README.md).

| Available in `v1.17.0` | Not implemented |
| --- | --- |
| Explicit project, immutable captures, paragraph citations | Embeddings, dense hybrid search, Qdrant, Haystack |
| SQLite/FTS5 lexical search, instant index rebuild | Zotero, network imports |
| Local text / Markdown input, original bytes retained | Multi-tenant team services, cloud hosting |
| PDF ingestion with self-hosted Baidu Unlimited-OCR boundary | Automated factual proof or rewriting prose |
| Safe Markdown & offline SVG diagram rendering (flowcharts, sequence) | Ambient configuration discovery |
| BagIt-style archive export and restore with cryptographic verification | Ambient manuscript detection |
| Native revisions for dossiers, claims, evidence links & decisions | External web scrapers |
| Versioned source criticism context & core analysis adapter | |
| Controlled withdrawal & physical purge with dry-run preview | |
| Read-only HTML source dashboard with localized context | |
| Integrity audit and snapshot conflict detection | |
| Source listing & tagging (`lixity research sources`) | |
| Dossier creation, editing & history (`lixity research dossier`) | |
| User-recorded claims & scope (`lixity research claim`) | |
| Evidence linking with relations (`lixity research link-evidence`) | |
| Authorial decisions & fact deviations (`lixity research decision`) | |
| Cross-corpus linguistic grounding (`lixity research compare`) | |
| Interactive web research panel in `lixity serve`: source/dossier details, search-to-evidence actions, dossier-linked claims, decisions | |

The server dashboard offers interface text for seven languages. English and
German have the deepest linguistic analysis heuristics; language selection
does not translate archived quotations or turn lexical search into semantic
search. The research CLI's help and errors are English.

## Try it

Install `v1.16.0` or use a development checkout (`make install-dev`), then
activate `.venv` if applicable.
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
lixity research dossier --project ./novel --title "Reading Room Notes" --file "Notes about a possible 1924 opening." --evidence urn:uuid:YOUR-PASSAGE-UUID
lixity research dossier --project ./novel
lixity research claim --project ./novel --title "Archive Founding" --statement "Founded in 1924." --confidence evidenced
lixity research claim --project ./novel
lixity research link-evidence --project ./novel --claim-id urn:uuid:YOUR-CLAIM-UUID --passage-id urn:uuid:YOUR-PASSAGE-UUID --relation supports
lixity research decision --project ./novel --title "Move date to 1914" --rationale "Plot tension" --claim-id urn:uuid:YOUR-CLAIM-UUID --deviation-from-fact
lixity research decision --project ./novel
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

`hypothetical`, `evidenced` and `disputed` are user-selected claim labels, not
computed probabilities or factual verdicts. A claim can exist without an
evidence link. Links record a `supports`, `contradicts`, `qualifies` or
`contextualizes` relation to a specific passage; the source and relation still
need human review. Decisions are separate authorial records, optionally tied
to a claim. An absent `--deviation-from-fact` flag means no deviation was
marked, not that the decision was verified as factually faithful.

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
        body="Notes about a possible 1924 opening.",
        evidence_ids=[results["hits"][0]["passage_id"]],
        tags=["milestone"],
    )
    claim = api.create_claim(
        "./novel",
        title="Reading Room 1924",
        statement="The reading room was opened in 1924.",
        confidence="evidenced",
    )
    link = api.link_evidence(
        "./novel",
        claim_id=claim["claim_id"],
        passage_id=results["hits"][0]["passage_id"],
        relation="supports",
    )
    decision = api.record_decision(
        "./novel",
        title="Shift date to 1914",
        rationale="Dramatic tension before war.",
        claim_id=claim["claim_id"],
        deviation_from_fact=True,
    )
dossiers = api.list_dossiers("./novel")
claims = api.list_claims("./novel")
decisions = api.list_decisions("./novel")
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

In the local server, **Open Project** takes a path to an existing workspace
folder or manuscript file on the server's filesystem and attaches that
workspace's `research/` archive when present. **Browse files and folders** lets
you browse the server computer's paths from its home directory, move with
**Home** or **Parent folder**, select a manuscript or the current folder, and then
confirm with **Open**; a typed path remains available. This is not a native OS
file dialog or a browser upload. An initialized research-only folder opens
without a manuscript. Source and record management remain available there;
manuscript comparison needs a loaded manuscript. **New Project → Import
Manuscript** accepts selected or dropped `.md`/`.txt` bytes and creates a
separate project. Use Open Project when returning to an existing research
archive. Source ingestion in the research panel has its own explicit local
retention confirmation.
Select a source or dossier for full details and verified citations. Search
results can feed a selected passage into **Use for claim** or **Use for dossier**;
the claim form can also associate an existing dossier. These actions record
the author's links and notes, not a factual verdict.

## Native editing and history

Version 1.17.0 adds explicit revisions to the research workflow. In the
dashboard, choose **Edit** on a dossier, claim, evidence link or decision.
Change the fields, select **Correction** for a transcription/wording correction
or **Supersession** for a changed interpretation or authorial choice, and give
a reason. Save keeps the record's ID and adds one immutable revision. **History**
opens earlier accepted versions; it does not restore or overwrite them.

An edit does not create an additional active dossier. Existing associations
remain pinned to the versions they originally referenced. For example, changing
a claim does not make its old supporting link evidence for the revised statement;
the UI shows the earlier claim revision for review. Creating a new association
uses the target's current revision. Submitting an unchanged association keeps
its original pin. To review an association against a revised claim or dossier,
explicitly change its associated revision in the editor. The earlier association
remains inspectable in history.

The editor preserves its draft when validation, a request or a conflict fails.
If any archive write occurred since the editor was opened, saving returns a
conflict. **Reload current** explicitly discards the draft and loads the current
record; nothing is silently merged or retried. Cancel closes the editor without
writing.

The same operations extend the existing commands:

```sh
lixity research dossier --project ./novel --dossier-id DOSSIER_ID --inspect
lixity research dossier --project ./novel --dossier-id DOSSIER_ID --update \
  --expected-snapshot SNAPSHOT_SHA256 --expected-revision 1 \
  --change-kind correction --reason "Correct a transcription" \
  --title "Revised reading room notes" --file "The corrected working note."
lixity research dossier --project ./novel --dossier-id DOSSIER_ID --history
lixity research dossier --project ./novel --dossier-id DOSSIER_ID --revision 1
```

Use the `snapshot` and `record.revision` returned by `--inspect`. The equivalent
commands are `claim --claim-id`, `link-evidence --evidence-link-id` and
`decision --decision-id`, with the same update/history flags and their existing
content flags. Omitted update fields stay unchanged. An empty optional value
clears it; empty comma-separated tags/actors/evidence clear those lists.
`--no-deviation-from-fact` explicitly clears the decision flag.
Use `--claim-revision N` on evidence links or decisions, or
`--dossier-revision N` on claims, to select an exact associated revision during
an update. Leaving that option out preserves an unchanged association's pin.

```python
current = api.get_record("./novel", "dossier", dossier_id)
updated = api.revise_record(
    "./novel", "dossier", dossier_id,
    changes={"body": "The corrected working note."},
    expected_snapshot=current["snapshot"],
    expected_revision=current["record"]["revision"],
    change_kind="correction", reason="Correct a transcription",
)
history = api.record_history("./novel", "dossier", dossier_id)
original = api.get_record("./novel", "dossier", dossier_id, revision=1)
```

Source refresh never rewrites authored records. A newer-capture notice compares
explicit passage citations with the source's latest available capture; the
original quote remains visible. Copied body text alone does not establish an
association with a source, and neither filenames nor titles are used to guess
one. Existing historical imports can therefore remain unchanged until the
author explicitly revises them.

Historical dossier and evidence-link views resolve their pinned passages.
Claim and decision views show the current evidence links to their pinned claim
revision, with each link's ID and revision; they are not a reconstruction of the
entire archive at an earlier date.

## Storage, lifecycle and recovery

- `research/project.json`: immutable initial project configuration.
- `research/revisions/`: immutable, schema-checked records.
- `research/blobs/`: SHA-256-addressed original text/PDF bytes and extracted text; original bytes are not normalized.
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
  affected records and blobs before deletion. Authored dossiers and evidence
  links remain for their audit trail, but their purged citations are marked
  `availability: "purged"` and expose no deleted quotation text.

### Cross-corpus comparison and evidence grounding

- **Linguistic comparison (`compare`)**: Connects an archived research source with a literary
  manuscript without modifying either document. Computes:
  1. Lexical overlap and alignment (Jaccard similarity, Szymkiewicz–Simpson overlap coefficient,
     top shared terms, exclusive source terms).
  2. Signed keyness differential using a full term/nonterm $2\times2$ Dunning
     $G^2$ log-likelihood table; values can change from development builds.
  3. Register and stylistic contrast (sentence length ASL delta, dialogue ratio delta,
     lexical diversity Guiraud's $R$ and Yule's $K$ deltas, staccato and kaskade deltas).
  4. Per-chapter evidence grounding (mapping occurrences of source vocabulary and top key
     terms across individual manuscript chapters, reporting grounding density per 1,000 words).

Comparison counts and register contrasts use chapter body prose when chapters
exist, excluding headings, front matter and the configured appendix. If no
chapter is detected, the remaining text is used after excluding headings and
the configured appendix. A cross-language comparison still returns numeric
overlap but sets `meta.lexical_comparable: false` and includes
`"cross_language_lexical_comparison"` in `comparison_limits`; its lexical
scores should not be interpreted as directly comparable vocabulary coverage.

Back up the **entire `research/` directory**, preferably while no writer is
running. Restore it to an explicit project root, run `audit`, then `reindex`.
Never restore only SQLite. Do not commit private source text to a public
repository: both blobs and passage records contain it.

## Export and restoration

Lixity provides explicit commands to package and restore authoritative research stores
with cryptographic checksum verification:

```sh
lixity research export --project ./novel --output ./backup-novel.tar.gz
lixity research restore --from ./backup-novel.tar.gz --to ./restored-novel
```

The archive packages all accepted records, revisions, snapshot manifests,
original source blobs, and project configuration into a gzip-compressed tar archive.
It includes an explicit `EXPORT_MANIFEST.json` with SHA-256 digests and byte
lengths for every file. Disposable search indexes (`catalogue.sqlite3`) and lock
files are excluded.

Restoration requires a clean target directory (it refuses to overwrite an
existing research store or non-empty project directory). Before placing the store,
restoration verifies:
1. Member path safety (rejects path traversal, absolute paths, symlinks, and device nodes).
2. SHA-256 checksum and byte length of every extracted file against `EXPORT_MANIFEST.json`.
3. Snapshot rules, contiguous revision histories, and project identities.
4. Moves the verified store into place atomically.

After restoring, audit and rebuild the search index:
```sh
lixity research audit --project ./restored-novel
lixity research reindex --project ./restored-novel
```

Writes use an OS lock, immutable publication and atomic HEAD replacement.
Uncommitted objects left after interruption are ignored, not selected by date.
Locks release when the process exits. A stale expected HEAD fails rather than
overwriting another ingestion. Interrupted initialization may leave an incomplete
directory: preserve it for inspection; `init` refuses to overwrite it.

Files are flushed before publication; directory syncing is used on POSIX.
If an interrupted authored edit leaves a valid next-revision file outside the
accepted snapshot, the next save preserves its bytes under a content-addressed
`.unpublished` filename in that revision directory before retrying. It is a
recovery artifact, not an accepted revision or an automatic merge. Accepted
history is never replaced; malformed or foreign files stop the save.
## Origin URL and capture provenance

Current main adds an optional **Origin URL** field to the browser source import,
`--origin-url` to the CLI and `origin_url=` to `api.ingest`. The value is retained
as `SourceVersion.context.origin_url`, independently of title, tags and
`provenance_note`. Source details, source listings and citation context expose it.

```sh
lixity research ingest --project ./novel --file ./notes.txt --allow-retention \
  --origin-url https://example.org/archive/notes
```

```python
api.ingest("./novel", "notes.txt", allow_retention=True,
           origin_url="https://example.org/archive/notes",
           context={"tags": ["archive"], "provenance_note": "Author-supplied context."})
```

The URL must be absolute HTTP(S), at most 2,000 characters, without credentials,
whitespace or control characters. It is stored as submitted, never requested or
used to accept a claim. Prefer stable source addresses over signed links with
private query tokens. The browser displays it as escaped text. Failed validation
keeps the draft; successful import clears the field with the rest of the form.

On refresh, an omitted `origin_url` retains the context selected by the existing
API: supplied `context`, or the latest capture's context when omitted. An explicit
URL overrides `context.origin_url`. Changing only the URL creates a new capture;
identical bytes and context remain a no-op. To clear a URL deliberately, supply a
context mapping with `origin_url: null` (and any other metadata to retain).
Earlier citations resolve their own capture and retain the original URL. URLs,
filenames and titles never establish source identity automatically.

**Compatibility:** source versions carrying a URL use `research-local/2`, still
at record revision 1, with a `research-manifest-local/2` snapshot. Their sequence
counts source captures; it is separate from authored-record revision history.
URL-free v1 records omit the new field entirely and retain their old encoding.
Reading an old archive does not migrate it. Lixity 1.17.0 and earlier reject
URL-bearing source records, including when they already support authored v2
revisions. Back up before this write, use compatible builds for every writer,
and restore the complete pre-upgrade backup to roll back. Do not edit schemas
or delete provenance fields by hand.

## Self-hosted PDF and OCR extraction

PDF ingestion retains the original PDF bytes and extracted UTF-8 text as
separate content-addressed blobs:

```sh
lixity research ingest --project ./novel --file ./document.pdf --allow-retention
```

Current main also accepts native binary PDF upload through the browser file
input. It reads the selected file as base64 for transport and passes the decoded
bytes through the same import API as text and server-local files. The browser
shows reading/extraction/completion states and prevents duplicate submits while
waiting. This is not a streamed per-page progress feed.

### Native PDFs versus scans

Install local Poppler tools: `poppler-utils` on Debian/Ubuntu, or `poppler` with
Homebrew. Both `pdftotext` and `pdftoppm` must be visible on the server's PATH.
`pdftoppm` rasterizes physical pages at 150 dpi; `pdftotext` extracts text layers.
Without page rasterization, native fallback only attempts page one, so treat
`partial` as incomplete setup rather than full multi-page support.

An image-only scan has no usable text layer and requires an external self-hosted
worker. Lixity does not install or start that worker. Run current-main diagnostics
in the same environment as the server:

```sh
lixity research ocr-status
```

The same information is available at `GET /api/research/ocr-status` and in
`GET /api/research/status`. The dashboard maps these codes to localized labels:

| Code | Configuration detected | Action |
| --- | --- | --- |
| `ready` | Executable worker and pdftoppm found | Test an authorized scan and inspect extracted text |
| `native_only` | Both Poppler tools, no worker | Native PDFs work; configure a worker for scans |
| `partial` | Worker or pdftotext available, pdftoppm missing | Install the rasterizer before multi-page use |
| `misconfigured_worker` | Configured worker missing or not executable | Check path, permissions and service environment |
| `missing_dependencies` | No complete usable setup | Install Poppler and optionally a scan worker |

Diagnostics inspect executable availability, not model weights, snapshot
integrity, GPU resources, worker connectivity or recognition accuracy. The
returned model/recipe identifiers are configuration constants, not attestations.
`ready` therefore means configured, not an end-to-end health check.

### Worker interface

Set `LIXITY_OCR_WORKER` to one executable path or a command name on PATH. It is
invoked directly as `[worker, request_file]`, without shell parsing or embedded
arguments. Use an absolute path without `~` for portable service configuration.
Set the variable in the service's environment and restart the server; exporting
it in another terminal does not update an existing process.

The temporary request JSON contains:

```json
{
  "model_snapshot": "07dea832e22aefee32ad281d4b80551282e1c168",
  "recipe_revision": "d49ff64afffc1f47ab563dc1c589bc2f78808fa4",
  "pdf_path": "/absolute/path/to/input.pdf",
  "pages": [{"page_number": 1, "sha256": "<rendered PNG SHA-256>"}]
}
```

Those are the implementation's Baidu Unlimited-OCR integration pins (recipe date
2026-07-29). The worker must arrange its own runtime and model provisioning;
this interface does not prove that an arbitrary executable uses those weights.
The request includes PDF access and page checksums, not image paths or image
bytes. A worker that needs raster images must obtain them from the local PDF.

Return JSON on stdout; send logs to stderr:

```json
{"blocks": [{"page_number": 1, "text": "Synthetic reading room note."}], "warnings": []}
```

Optional block fields are `box` and `confidence`. The implementation joins
nonempty block text with blank lines, times out the worker after 120 seconds,
and may use native text extraction if the worker fails. Validate the extracted
text against a known scan. Do not infer OCR success from successful extraction
of an existing PDF text layer.

### What is actually retained

`SourceVersion.blob` points to original PDF bytes; `Extraction.text_blob` points
to extracted UTF-8 text. Passages cite exact character spans in that text.
The extraction boundary computes page images, boxes and warnings, but the current
archive does **not** persist those as audited page/coordinate/confidence records.
Likewise, it does not persist an attestation of which model ran. Inspect the
original PDF for visual verification and retain operational diagnostics separately
when needed. Core import is local; a user-configured worker has its own network
behavior and must be deployed according to the project's privacy requirements.

## Safe Markdown and offline diagram rendering

Dossier body text supports a safe Markdown subset and offline SVG diagram rendering directly in the browser without external dependencies, CDNs, or network access:
- **Safe Markdown**: Paragraphs, headings (h1–h6), bold, italic, blockquotes, ordered/unordered lists, code spans, code blocks, and GFM tables. Raw HTML is strictly escaped to prevent cross-site scripting (XSS).
- **Offline diagrams**: Fenced code blocks with `mermaid` syntax are parsed and converted to native inline SVGs by Lixity's built-in vector generator. Supported types include flowcharts (`graph TD`, `graph LR`) and sequence diagrams (`sequenceDiagram`).
- **Source inspectability**: Any rendered diagram provides a collapsible "Show diagram source" control to view the raw specification.

## Limits

The released pilot uses `research-local/1` and operation-specific `*-local/1`
envelopes, not the RFC's illustrative `research/1` bundle. Native editing in version 1.17.0 adds `research-local/2` for authored revisions and
`research-manifest-local/2` for snapshots containing them. The first accepted edit
upgrades that snapshot; reading a revision-1 archive does not rewrite any files.
Older Lixity versions reject the new snapshot. Back up the whole archive before
upgrading, use the same supported version for all writers, and restore the full
backup if reverting to 1.16.0. Never edit HEAD or revision files to downgrade.
Unknown fields and versions are rejected. Source identity metadata cannot yet
be edited; refresh creates a new source version, not a changed old record.
The 25,000-entry snapshot limit includes retained revisions. Status counts show
current logical records; the audit's `records` count includes their history.

Text inputs are at most 2 MiB and must be valid UTF-8 without NUL bytes.
PDF inputs are at most 50 MiB. Both routes allow at most 5,000 nonempty extracted
passages. Search uses literal Unicode words joined with AND; it is
not stemming, translation or semantic search. BM25 scores are ranks, not truth
probabilities. Language tags do not translate quotations. Empty queries, stale
indexes and missing FTS5 support produce errors, not silent fallbacks.
Source analysis emits `original_language_supplied` when source context names
an original language; that free-text field alone does not establish historical
language variety. This replaces the earlier experimental
`historical_language` limitation code.

Audits check retained records, hashes and citations, not factual accuracy,
permissions or historical completeness. A citation's `availability` indicates
whether its source is currently available or withdrawn; a purged passage no
longer resolves. The web panel displays those evidence states for linked
passages.
The [non-commercial licensing rules](../LICENSING.md) still apply.
