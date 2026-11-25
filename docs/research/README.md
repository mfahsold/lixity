<a id="research-workspace-current-scope-and-design-history"></a>
# Research workspace: manuals and design history

The local research archive retains selected sources, exact quotations and
authored dossiers, claims and decisions. Start with an illustrated example or
choose the reference for the work you are doing.

## Current references

| Reader and task | Maintained reference |
| --- | --- |
| First research session | [Illustrated walkthrough](../guides/research-pdf.html), then [Try it](USAGE.md#try-it) |
| Author using the browser or CLI | [Research manual and task map](USAGE.md#find-a-task) |
| Manuscript reading, project settings or sharing | [Browser workspace manual](../WORKSPACE.md), [all documentation](../README.md) |
| Program calling Python or HTTP | [Automation contracts](../AGENTS.md#51-research-api-lixityresearchapi) |
| Contributor working on archive persistence | [Local data model](DATA_MODEL.md), [architecture](../ARCHITECTURE.md) |
| Check an installed command's syntax | `lixity research --help`, then `lixity research COMMAND --help` |
| Discover installed contracts or inspect record shapes | [CLI, HTTP and MCP discovery](../AGENTS.md#choose-the-interface), `lixity research schema` for the archive entity schema, [research compatibility](USAGE.md#limits) |
| Choose a backup or restore procedure | [Backup scopes](../PROJECT_BACKUP.md), [research recovery](USAGE.md#export-and-restoration) |
| Set up PDF extraction or an OCR adapter | [PDF and OCR workflow](USAGE.md#self-hosted-pdf-and-ocr-extraction), [adapter validation](OCR_INTEGRATION.md#validation-scope) |

Zotero owns source-library editing and ordinary reading. Lixity preserves selected
versions and their authored relationships. Retention requires permission. Retained
quotations support the author's review, and source analysis uses a separate baseline.

<a id="3-recommended-stack-and-alternatives"></a>
## Design history

- The [original architecture RFC](https://github.com/mfahsold/lixity/blob/123b198db2b3d276b4bba71664e4e6b989377247/docs/research/README.md)
  and [platform evidence](EVIDENCE.md) record the September 2026 design basis and
  provider comparisons.
- The [original interchange proposal](https://github.com/mfahsold/lixity/blob/427e2a3491bacd0b504ce4e3387a019340bd2e67/docs/research/DATA_MODEL.md)
  and [synthetic interchange example](examples/evidence-chain.json) illustrate a
  proposed export and schema. The [local data model](DATA_MODEL.md) describes the
  accepted archive format.
- The [September scientific review](SCIENTIFIC_REVIEW_2026-09.md) records earlier
  findings. [Methods](../METHODS.md) and [Stability](../STABILITY.md) cover current
  estimator conventions and evidence limits.
- The [character knowledge horizon RFC](KNOWLEDGE_HORIZON_RFC.md) is an
  unimplemented proposal with open design decisions.
- The [former implementation overview](IMPLEMENTATION.md) links to the archived
  status documents and to their maintained replacements.
