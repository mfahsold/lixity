# RFC: Character knowledge horizon (proposal, not implemented)

**Status:** proposal only. Nothing in this document is implemented, shipped or
registered in any schema. It records a design candidate raised by a
multi-timeline manuscript review and the corresponding Lixity limitations, so
that a later decision to build it starts from a concrete, small, honest
boundary.

**Last updated:** 2026-10-17. **Owner:** product (Lixity research workspace).
**Related:** `docs/research/DATA_MODEL.md` (entity contracts), `docs/research/USAGE.md`
(implemented commands), `docs/research/IMPLEMENTATION.md` (deferred items),
`src/lixity/research/models.py` (record kinds), `src/lixity/research/timeline.py`
(period grammar).

## 1. Problem

In multi-timeline fiction, a character in scene A can easily reference, fear or
plan around a fact that only exists in scene B, which is set later. Readers
notice this immediately; authors catch it late, usually by hand. Lixity currently
stores **facts** (claims, decisions, sources) and **periods** (claims carry
`scope.time_period`, the timeline places them), but it has no notion of *who knew
what, when*. The review state covers archive integrity and anchor movement, not
anachronistic character knowledge.

## 2. Goal

A read-only check that, given an authored assertion "figure X knows fact Y at
time T", reports whether Y was available to X at T. The check is advisory: it
warns, it never rewrites, never blocks a commit, and never infers knowledge
from prose.

## 3. Non-goals

- No automatic detection of knowledge from manuscript prose. Lixity already
  measures tense and dialogue; turning either into "character knowledge" would be
  an unsupported inference. All links are explicit and authored.
- No character model beyond the existing `Claim.scope.actors` list and the
  dossiers. No psychometric profile, no arc, no motive.
- No blocking of archive writes. A mismatch is a review signal, not an error
  (mirrors `ManuscriptState.AMBIGUOUS`/`CHANGED`: unresolved stays unresolved).
- No new storage backend. Reuse the existing append-only, content-addressed
  research store and the manifest schema machinery.

## 4. Data model

### 4.1 Reuse first

`Claim` already carries `scope.time_period`, `scope.place` and `scope.actors`.
`timeline()` already resolves a period into a sort key and a precision. The
period grammar and precision semantics are defined and tested there and must not
be duplicated.

### 4.2 New record: `KnowledgeAttribution`

One new authored record kind, append-only, schema bump to `research-local/8` and
`research-manifest-local/8` (older readers remain readable):

```text
KnowledgeAttribution (AuthoredRecord)
  figure: str                    # free-text figure name; no entity registry
  fact_ref: Claim ref            # the claim the figure is asserted to know
  learned_at: str                # a period label (same grammar as Claim.scope.time_period)
  learned_where: str | None      # optional dossier/source/scene label, free text
  confidence: "asserted" | "inferred-by-author" | "uncertain"
  status: proposed | accepted | superseded | rejected
  actor, change, revision, ...   # inherited from AuthoredRecord
```

`figure` is free text deliberately: there is no character entity registry, and
introducing one would couple this feature to a manuscript model Lixity does not
have. The same string must be reused by the author; case-sensitive matching is
documented.

`fact_ref` pins a Claim revision, exactly like `ManuscriptClaimLink.claim_ref`.
A claim revision change invalidates the attribution (review_needed), mirroring
`claim_changed`.

`learned_at` uses the same period grammar as `Claim.scope.time_period`. It is
authored, not inferred: the author states when the figure could have learned the
fact.

`confidence` is the author's own assessment of how sure they are that the
figure knew it; it is not a computed probability.

### 4.3 Schema impact

- New record kind `knowledge_attribution` in the entity union and validation.
- Manifest schema bumps to v8 only when a `research-local/8` record is committed;
  v1-v7 archives stay readable without rewriting.
- `research audit` gains one invariant: every `KnowledgeAttribution.fact_ref`
  resolves to a Claim in the same snapshot.

## 5. Period comparison

Reuse `timeline.py`'s resolution. A period resolves to `(start, end, precision)`
or `None` (unplaced). Comparison rules, in order:

1. If either period is unplaced → result `unknown` (no verdict; the author must
   place it first).
2. If precisions differ → result `incomparable` (a year vs a month cannot be
   ordered safely).
3. Otherwise: `fact_period.end <= scene_period.start` → `available`;
   `fact_period.start > scene_period.end` → `anachronistic`;
   overlap → `ambiguous`.

The check never claims a fact was learned; it only reports availability.

## 6. Commands

Minimal, append-only, consistent with existing commands:

- `research knowledge-add --project DIR --figure NAME --claim-id ID [--claim-revision N]
   --learned-at PERIOD [--learned-where LABEL] [--confidence asserted|inferred-by-author|uncertain]
   [--expected-snapshot DIGEST] [--actor ...]` — creates a `KnowledgeAttribution`.
- `research knowledge-list --project DIR [--figure NAME] [--claim-id ID]` — list.
- `research knowledge-check --project DIR --figure NAME --at PERIOD` — read-only:
  for every attribution to that figure whose fact period is before or equal to
  `at`, report `available`; for those strictly after, `anachronistic`; unplaced
  or mismatched precision → `unknown`/`incomparable`. Output is a sorted list,
  not a verdict.
- `research review-knowledge` (or fold into the existing review tab) — read-only
  list of attributions whose fact claim was revised or withdrawn since
  attribution (review_needed).

No `--dry-run` is needed for the read-only commands; `knowledge-add` is
append-only and idempotent via the usual snapshot guards.

## 7. UI

Fold into the existing Research tabs rather than adding a top-level tab: a
"Knowledge" sub-view inside *Claims & evidence*, parallel to *List/Timeline*.
Rows: figure, fact (claim title, revision), learned-at, status, check result.
The check result is a labelled badge (`available`/`anachronistic`/`unknown`/
`incomparable`), never a verdict. Clicking a row opens the claim and its
revision history.

## 8. Limits and honesty (must ship in the docs)

- Knowledge attributions are **authored assertions**, not verified facts. A figure
  "knowing" something is the author's design decision, not evidence.
- Periods are authored labels; the check compares labels, it does not establish
  historical truth, source reliability or chronology.
- No automatic detection from prose: no verb-pattern matching, no NLP over
  character dialogue. The author links explicitly.
- A claim revision invalidates attributions (review_needed); the author re-links
  or re-accepts.
- The check is a review aid, like `ManuscriptState.ADJUSTED`/`CHANGED`:
  unresolved stays unresolved, nothing is auto-fixed.

## 9. Compatibility

- Older readers (v1-v7) cannot read `research-local/8` records. Append-only: an
  archive only opts into v8 when the first `KnowledgeAttribution` is committed;
  archives without one stay at v7 and remain readable.
- Export/restore keeps the bundle format; knowledge attributions travel as
  ordinary records.

## 10. Effort and ordering

- Data model + validation + tests: small (one record, one invariant).
- Commands: 3 thin commands reusing `timeline.py` resolution.
- UI: small sub-view; reuse the card component from slice 1.
- Documentation: USAGE (commands, grammar, honesty), DATA_MODEL (entity row),
  IMPLEMENTATION (deferred → implemented), METHODS note.
- Suggested order: model → commands → tests → UI → docs → browser suite.

## 11. Open questions (for decision)

1. **Free-text figure names vs a figure registry.** Free text is simpler and
   avoids coupling to a manuscript model Lixity does not have; the cost is
   inconsistent spelling. Should aliases be added (like `characters` alias
   patterns), or is exact matching the right discipline?
2. **Should `learned_at` be required?** Allowing `unknown` keeps partial
   drafts working; requiring it forces the author to place the fact first
   (which is what the check needs). Recommend: required, with a clear error.
3. **Should `knowledge-check` also consider dossiers and decisions**, or only
   claims? Start with claims (the cleanest facts); extend later if needed.
4. **Should the check be part of `review-manuscript`/`review`?** Probably not:
   manuscript review is about anchors, not figure knowledge. Keep separate.

## 12. Explicitly not in scope

- No character-arc or motive inference.
- No automatic extraction from prose.
- No new storage backend or sync protocol.
- No blocking of writes on a mismatch.
EOF
echo "RFC geschrieben:"; wc -l docs/research/KNOWLEDGE_HORIZON_RFC.md; head -6 docs/research/KNOWLEDGE_HORIZON_RFC.md