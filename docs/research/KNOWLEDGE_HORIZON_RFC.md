# Proposal: character knowledge horizon

**Not implemented.** No knowledge-attribution record, command, check or UI is
registered. This page preserves the problem and unresolved design constraints;
it does not reserve a schema version or define an API.

<a id="1-problem"></a>
## Problem

In multi-timeline fiction, a character may refer to an event or fact before they
could have learned it. Existing claim periods, causal interpretations and
manuscript associations do not represent who knows what when. Character aliases
and author-declared viewpoint chapters also do not establish knowledge.

An eventual review aid could compare explicit author assertions about knowledge
with authored periods. Availability in a time interval would still not prove that
a figure learned a fact, or that the assertion is historically true.

## Design constraints

- Reuse existing claim references, period resolution, revision history and
  explicit-project boundaries before considering additional record types.
- Knowledge and learning times must be author-entered. Do not infer them from
  pronouns, dialogue, tense, name mentions or record creation timestamps.
- Missing/unclear periods and incompatible precision must remain unknown or
  incomparable. Overlapping intervals cannot establish a definite ordering.
- A review signal must remain advisory: no blocked writes, automatic reacceptance,
  rewritten prose or silently updated claim pins.
- Any future extension needs its own reviewed compatibility decision. An older
  design's suggested schema number is not a reservation or migration contract.

<a id="11-open-questions-for-decision"></a>
## Open decisions

- Can existing authored claims/dossiers express the useful workflow, or is a new
  relation justified? A second character registry or store is not assumed.
- How should a figure identity relate to existing literal aliases, and how should
  uncertain or missing learning times be represented?
- Which periods are meaningfully comparable, and how should later claim revisions
  be presented for review without inferring a contradiction?

These decisions require a concrete author workflow before implementation.
Installed behavior is documented in [Research usage](USAGE.md), not this proposal.

## Historical draft

The [original full proposal](https://github.com/mfahsold/lixity/blob/123b198db2b3d276b4bba71664e4e6b989377247/docs/research/KNOWLEDGE_HORIZON_RFC.md)
preserves its illustrative model, commands and implementation sequence. Those
interfaces were never implemented; use the current schema before designing any
extension. [Research architecture history](README.md#design-history) records the
broader original design.
