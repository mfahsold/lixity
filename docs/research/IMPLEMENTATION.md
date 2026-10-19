# Implemented research scope

The local research workspace is experimental. [Research usage](USAGE.md) owns
workflows and compatibility; [automation contracts](../AGENTS.md#51-research-api-lixityresearchapi)
own request/result contracts. Use `lixity research --help`, `research schema` and
`about --json` to inspect the installed version rather than treating a status
page as a command reference.

## Current scope

The shared archive supports authorized text/PDF/PNG/JPEG capture, lexical search,
exact citations, authored records and immutable history, explicit manuscript quote
associations, chronology, causal interpretations, review and verified backup/restore.
Zotero capture is read-only; source editing and ordinary library work stay in
Zotero. Audio/video are unsupported. PDF extraction uses optional local tools or
an explicitly configured worker, not a bundled inference runtime.

**Since v0.7.1:** exact update dry runs, saved-revision comparisons
and explicit Markdown dossier export/reconciliation reuse the same revision path.
Guarded dossier retirement reuses source withdrawal's tombstone storage.
Interactive geography works offline; optional map tiles require separate network
permission. [Research workflows](USAGE.md#research-workflows) document these additions
and their installed-version boundary.

[Architecture](../ARCHITECTURE.md) owns component responsibilities and project
isolation. Preparation is read-only with respect to the archive; accepted writes
validate reviewed revisions/pins and commit against one snapshot. Conflicts do not
authorize retries, automatic repinning or prose edits. Product numbers, response
schemas and archive versions are independent; see [compatibility](USAGE.md#limits).

## Verification limits

[Contributor checks](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md)
cover synthetic domain, transport and browser behavior. They establish neither
historical truth nor recognition accuracy, external-library completeness or
compatibility with every OCR/Zotero environment. Archive integrity and source
criticism remain distinct. Private manuscripts are not required as test fixtures.

## Deferred capabilities

There is no semantic/vector retrieval, automated factual certification, arbitrary
third-party note import, automatic Zotero synchronization or shared multi-tenant
cloud service. The [knowledge-horizon proposal](KNOWLEDGE_HORIZON_RFC.md) is not
implemented. These boundaries are not an execution backlog or a promise to ship.

## Historical status

The [earlier implementation overview](https://github.com/mfahsold/lixity/blob/123b198db2b3d276b4bba71664e4e6b989377247/docs/research/IMPLEMENTATION.md)
retains the original component inventory, release sequence and validation notes.
Current behavior belongs to the references above, not that historical snapshot.
