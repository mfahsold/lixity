<a id="research-workspace-current-scope-and-design-history"></a>
# Research workspace: manuals and design history

The local research archive retains selected sources, exact quotations
and authored dossiers, claims and decisions. Use the installed interface for
available operations; historical designs do not define current commands or schemas.

## Current references

| Reader and task | Maintained reference |
| --- | --- |
| First research session | [Illustrated walkthrough](../guides/research-pdf.html), then [Try it](USAGE.md#try-it) |
| Author using the browser or CLI | [Research manual and task map](USAGE.md#find-a-task) |
| Manuscript reading, project settings or sharing | [Browser workspace manual](../WORKSPACE.md), [all documentation](../README.md) |
| Program calling Python or HTTP | [Automation contracts](../AGENTS.md#51-research-api-lixityresearchapi) |
| Contributor working on archive persistence | [Local data model](DATA_MODEL.md), [architecture](../ARCHITECTURE.md) |
| Checking an installed capability | [Implemented scope](IMPLEMENTATION.md), `lixity research --help`, `lixity about --json` and `lixity research schema` |

The research manual owns capture, citations, revisions, manuscript associations,
Zotero, media, OCR, backup/recovery and archive compatibility. The data model owns
stored records and invariants. Neither the historical material below nor a
rendered screenshot defines an installed command.

Zotero owns source-library editing and ordinary reading. Lixity preserves selected
versions and their authored relationships. Retention requires permission; a saved
quotation, claim or author decision does not establish factual truth. Source
analysis remains separate from the manuscript baseline.

<a id="3-recommended-stack-and-alternatives"></a>
## Design history

The [original architecture RFC](https://github.com/mfahsold/lixity/blob/123b198db2b3d276b4bba71664e4e6b989377247/docs/research/README.md)
records the September 2026 baseline, platform comparisons, proposed providers,
interchange and implementation sequence. It mixes foundations later implemented
with alternatives that remain unimplemented; its command sketches are not a
runnable reference. The immutable snapshot preserves that discussion without
maintaining a second architecture or task list here.

Related design material:

- The [original interchange proposal](https://github.com/mfahsold/lixity/blob/427e2a3491bacd0b504ce4e3387a019340bd2e67/docs/research/DATA_MODEL.md)
  and [platform evidence](EVIDENCE.md) are design history, not accepted local
  payloads or a current dependency list.
- [September scientific review](SCIENTIFIC_REVIEW_2026-09.md) records historical
  findings; [Methods](../METHODS.md) and [Stability](../STABILITY.md) own current
  estimator conventions and evidence limits.
- [Character knowledge horizon](KNOWLEDGE_HORIZON_RFC.md) remains an unimplemented
  proposal. [Implemented scope](IMPLEMENTATION.md) distinguishes current features
  from deferred capabilities.
- [OCR deployment boundary](OCR_INTEGRATION.md) describes an optional external
  adapter; no inference runtime or model weights ship with Lixity.
