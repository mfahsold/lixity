# Proposed research data model and contracts

[RFC](README.md) · [Evidence](EVIDENCE.md)

Status: target design specification for the complete RFC. The experimental
`v1.16.0` pilot implements the immutable source-to-passage subset using strict
schema `research-local/1`
(`Project`, `Source`, `SourceVersion`, `Activity`, `Extraction`, `Passage`,
`Tombstone`) together with Dossiers, Claims, EvidenceLinks and Decisions in
the pilot's own schema. See [USAGE.md](USAGE.md) and [IMPLEMENTATION.md](IMPLEMENTATION.md).
The broader interchange model below remains a proposal.
[The synthetic interchange example](examples/evidence-chain.json) illustrates a
complete source-to-decision chain; it is not a production database.

## 1. Common envelope and identity

Each record has `id` (UUID URI), `kind`, `revision` (positive integer), `project_id`,
`created_at`, `created_by`, and `schema_version`. Timestamps use RFC 3339 UTC;
actors may be local pseudonymous IDs. `schema_version` describes the interchange
contract, not the application release. Revisions never identify confidence.

Cross-record references contain both `id` and `revision`. A manifest pins all
accepted revisions and their exact UTF-8 byte hashes. Mutable head pointers are
resolved only when creating a new revision, not when replaying an old decision.
SHA-256 identifies bytes, while UUID identifies an entity across revisions.
Never deduplicate claims or sources solely because their text, title or URL matches.

`Project` defines allowed languages, optional independent narrative strands,
entity alias tables, relative paths and provider policy. The current manifest
pointer lives in a separate `HEAD.json`, outside the domain entity hash graph.
An object has one project scope in the first implementation. Cross-project reuse
is an explicit import with provenance and permissions, not global implicit search.

Common optional metadata: `tags`, `supersedes` (revision reference),
`external_identifiers`, `visibility` and `review` with actor/time/rationale.
Secrets, absolute local paths, access tokens and signed object-store URLs are
excluded from interchange.

## 2. Entity contracts

| Entity | Required domain fields | Invariants |
| --- | --- | --- |
| `Source` | `source_type`, `title`, `identifiers`, `bibliography`, `access` | Identifies an item/work. Zotero mapping includes API origin, server identity where available, library type/ID, item key and observed version. Bibliographic edition identity must not be collapsed into a URL. |
| `SourceVersion` | `source_ref`, `captured_at`, `availability`, `acquisition`, `rights` | An immutable manifestation/capture. Available bytes require a blob descriptor; metadata-only records cannot claim text was extracted. Corrected metadata creates another record revision. |
| `Extraction` | `source_version_ref`, `activity_ref`, `text_blob`, `representation`, `warnings` | Refers to original input and exact derived bytes. Stores parser/model/schema/configuration versions and normalization rules via the activity. Failed runs do not create successful extractions. |
| `Passage` | `extraction_ref`, `selector`, `verbatim`, `language`, `verification` | Locator applies to one retained representation. Quote must match that representation. A corrected passage gets a new revision and never silently retargets old citations. |
| `Claim` | `statement`, `claim_type`, `scope`, `status` | `claim_type`: source_report, interpretation, hypothesis. `status`: unreviewed, reviewed, disputed, superseded, withdrawn. Reviewed means reviewed by a person, not proven true. Its review pins the EvidenceLink revisions examined. |
| `EvidenceLink` | `claim_ref`, `passage_ref`, `relation`, `rationale`, `review` | Relation: supports, contradicts, qualifies, contextualizes. Unreviewed links remain suggestions. Reject a link to a missing or incompatible project record. |
| `Dossier` | `title`, `language`, `claim_refs`, `evidence_refs`, `decision_refs`, Markdown body | Authored prose lives only in the Markdown revision. Referenced records carry structured facts. Generated sections have explicit boundaries and activity references. |
| `Decision` | `statement`, `status`, `scope`, `considered_claim_refs`, `considered_evidence_refs` | Status: proposed, accepted, superseded, rejected. Accepted requires an explicit author actor and time. May deliberately depart from evidence with a reason. |
| `ManuscriptAnchor` | manuscript-relative path, manuscript checksum, selector, `target_refs`, relation | Targets explicit Claim/Decision revisions. Can be resolved, ambiguous or orphaned; line number alone is insufficient. |
| `Activity` | `operation`, `inputs`, `agent`, `parameters`, start/end/status | Represents capture, extraction, translation, synthesis, review or export; record versions and hashes, not secrets or hidden reasoning. |
| `Tombstone` | target revision/ID, operation, actor, time, reason | Distinguishes withdrawn, provider-removed and purged. Preserves non-sensitive identity needed to diagnose broken references. |

A blob descriptor contains `sha256`, `byte_length`, `media_type` and an opaque
`storage_key`, normally `sha256/<hex>`. The project backend resolves that key.
An S3 ETag is not a substitute for the digest. `rights` distinguishes local
retention, use of excerpts and redistribution; `unknown` is a valid explicit
value, not permission. `availability` includes available, metadata_only,
restricted and missing.

Historical evidence traversal uses those explicit EvidenceLink revision lists,
then each link's pinned Passage/Claim revisions. It never expands an old decision
against all currently existing reverse links. New or revised links enter a review
queue and require a new claim review, dossier or decision revision to change its
recorded evidence context. A reviewed assertion without evidence uses an explicit
empty list and a rationale explaining the gap; reviewed is not synonymous with
supported. Cross-record cycles between a Claim and its reviewed EvidenceLink are
allowed; supersession cycles are not.

Structured `scope` contains referenced places/entities, narrative strand IDs and
`valid_time`. Valid time has optional start/end, precision and an uncertainty
description. Omitted dates mean unknown. Historical dates use a documented ISO
date profile where representable and preserve the original label for ambiguous
or non-Gregorian dates; do not coerce them into an exact modern timestamp.
Publication and access dates remain separate bibliographic/acquisition fields.

## 3. Selectors and citation resolution

Use a W3C Web Annotation-compatible selection over an explicitly identified
representation. Text selectors contain exact/prefix/suffix plus zero-based
Unicode code-point offsets `[start, end)` into the stored UTF-8 decoded text.
Specify Unicode normalization and line-ending handling in `Extraction`; avoid
normalizing a second time during resolution.

For PDFs, also store the physical page number (one-based), printed page label
when available, bounding box with units/origin/page dimensions, and native Docling
item reference when available. A passage may have multiple page regions. Map and
validate native item-local `charspan` values into the retained text representation;
they are not automatically global Markdown-export offsets. A PDF page number,
printed label and OCR text offset are different
coordinates. For web captures, record WARC record ID/target URI and the extracted
representation. Selectors referencing decoded text are not offsets into raw HTML.

Resolution order:

1. Resolve the pinned passage, extraction and original source version.
2. Check retained blob lengths and hashes.
3. Validate the positional substring against the exact quote.
4. If a newer extraction is requested, try a quote match with surrounding context
   and offer a migration proposal. Ambiguous/no matches require review.
5. Return title, version, original location, exact excerpt and availability state.

An old citation continues to use its original extraction. Missing original bytes
must be visible even if a retained quote still resolves. A successful checksum
check establishes integrity, not factual accuracy or permission to distribute.

## 4. Interchange and adapter mappings

| Boundary | Mapping |
| --- | --- |
| Zotero → Source | Preserve native item JSON, library/key/version; attach CSL-JSON as a citation projection. A DOI match suggests a duplicate but does not auto-merge editions or captures. |
| CSL-JSON file → Source | Import bibliography and allocate internal IDs. Record importer activity; no Zotero sync capability is inferred from a citation export. |
| SourceVersion → archive | Direct PDF/image/audio bytes or WARC/WACZ references; capture method, date, completeness and rights accompany the hash. |
| Docling → Extraction/Passage | Preserve native structured output and provenance; map selected regions into retained text selectors. OCR confidence, when present, remains a tool-specific diagnostic. |
| Records → PROV | Source/extraction/dossier revisions are Entities; transformation runs are Activities; people/tools are Agents. Export `wasDerivedFrom`, `wasGeneratedBy` and association links where supported by records. |
| Passage → Web Annotation | Target the immutable representation with quote/position selectors; Lixity-specific coordinates use a declared extension context. |
| Project/dossier snapshot → RO-Crate | Root Dataset plus permitted File/contextual entities, author/tool provenance, identifiers and relationships. Validate the declared export profile; JSON-LD syntax alone is not conformance. |
| Records → Qdrant | Derive points from indexing chunks; payload includes project, index generation, source version and passage revision references. Provider point IDs are disposable. |
| Records → Obsidian | Markdown dossiers and optional properties/Bases views. File renames do not change entity IDs. Regular Markdown remains usable outside Obsidian. |

## 5. Search result and research audit contracts

A proposed `ResearchSearchResult` envelope contains:

```json
{
  "schema_version": "research-search/1",
  "project_id": "urn:uuid:00000000-0000-4000-8000-000000000001",
  "mode": "evidence",
  "manifest_generation": 7,
  "index_generation": "hybrid-profile-a-7",
  "completeness": "complete",
  "hits": [],
  "warnings": [],
  "unsupported_questions": []
}
```

`complete` means the requested operation finished against the declared scope,
not that all relevant knowledge in the world was found. Each hit contains
passage/source revision references, a verbatim excerpt, locator, evidence type,
review status, score type and retrieval route. Similarity scores are not calibrated
probabilities of truth. Indexing prefixes and generated translations are labeled
separately. Stale/partial states include a reason and affected scope.

`ResearchAuditReport` must report separately: invalid references, unavailable
objects, citation mismatches, ambiguous anchors, pending source changes,
disputed claims, unreviewed links and index lag. It does not reuse `all_synced`
as a claim of truth. Optional projection into existing `DossierStatus` describes
only synchronization, retaining the old contract.

## 6. Example and validation obligations

The [example JSON](examples/evidence-chain.json) accompanies
[a synthetic source](examples/synthetic-source.txt) and
[an authored dossier](examples/dossier.md). It uses fictional places and explicitly
states that its content is fabricated for validation. Byte hashes, sizes, selector
positions and record references can be checked locally without network access.
The bundle embeds records for readability; production storage uses immutable
per-entity revisions and manifests. It omits service deployment and real credentials.

Future schema validation must reject unknown core fields except within a named
`extensions` object; validate enum values and field types. Application validation
must additionally enforce referential integrity, acyclic supersession, monotonically
increasing revisions, project scope, decision authorization, blob fixity and selector
resolution. JSON Schema alone cannot establish those cross-record properties.

Migration is explicit: retain the prior schema, produce a preview and new snapshot,
validate references, and switch the manifest only after success. An unsupported
future version produces an actionable error, never a silent best-effort import.
