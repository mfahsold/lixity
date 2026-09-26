# Native Research Revisions Implementation Plan

**Goal:** Implement issue #9: revise dossiers, claims, evidence links and author decisions through the native UI, CLI and API while preserving logical identity, immutable history and source provenance.

**Architecture:** Extend the existing immutable repository and atomic snapshot publication. Keep latest-record views for normal listing and a verified revision index for pinned references. Add one shared revision API and editor flow, with explicit correction/supersession reasons and optimistic concurrency. No manuscript or live research mutation is part of development.

**Specification:** [Issue #9](https://github.com/mfahsold/lixity/issues/9), including its explicitly separate Markdown rendering, portable backup/restore and PDF/OCR follow-ups.

**Execution:** Independent storage, interface and UI tasks in `/tmp/lixity-issue-9`; root integrates the public API, documentation and end-to-end tests. The current server continues using the unchanged released checkout.

## Constraints and review focus

- Preserve existing revision-1 objects byte for byte. Opening an archive must not migrate it.
- New authored revisions keep IDs and increment revision numbers. Version the changed storage contract explicitly; older software must fail closed after the first revision.
- Pinned claim/dossier/evidence/decision references resolve the exact historical revision; list views show one latest item per logical ID.
- Retain an already accepted purged citation as unavailable, but reject newly attaching a purged passage.
- Validate all retained revisions and prevent gaps, kind changes, identity changes and stale writes before publishing HEAD.
- Require expected snapshot and revision, change kind and reason. No automatic retry or source-driven rewriting.
- Preserve unsaved browser drafts on validation/network/conflict errors and provide an explicit reload-current action.
- Technical docs and CLI remain English; new UI labels cover all seven supported languages.
- Tests and screenshots use synthetic text; private feedback informs scope but is never a fixture.

## 1. Immutable storage

Files: `research/models.py`, `research/repository.py`, new storage regression tests.

- [ ] Demonstrate that a second dossier revision is currently rejected.
- [ ] Add authored revision metadata (previous revision, correction/supersession, reason) and the versioned contract.
- [ ] Keep a latest-record index and a complete revision index. `Snapshot.get(ref, type)` resolves pinned references; `Snapshot.latest(id, type)` resolves current identity.
- [ ] Commit revision N+1 only after checking the expected snapshot, immutable predecessor and full reference graph.
- [ ] Test old archives, byte preservation, history integrity, stale commits, publication failure, retained purged references and rejection of new purged references.

## 2. Shared public API

Files: `research/revisions.py`, `research/api.py`, new API regression tests.

Interfaces:

```python
get_record(project, kind, record_id, *, revision=None)
record_history(project, kind, record_id)
revise_record(project, kind, record_id, *, changes, expected_snapshot,
              expected_revision, change_kind, reason, actor="local-author")
```

`kind` is `dossier`, `claim`, `evidence_link` or `decision`. Read/revise returns `research-record-local/1` with `project_id`, `snapshot`, `record`, `latest_revision`, `is_latest`, `citations` and `source_updates`. History returns `research-history-local/1` with revision metadata. Unknown change fields are rejected.

- [ ] Tests revise all four entities and inspect their original revisions.
- [ ] Reuse existing validation and ID-to-reference conversion; omitted fields preserve current values and optional fields can be cleared explicitly.
- [ ] Existing dossier detail and record lists return latest content without increasing logical counts. Creation pins the latest referenced authored record.
- [ ] Calculate newer-source notices from explicit passage provenance; never infer associations from filenames or titles.
- [ ] Test stale snapshot/revision, foreign IDs, immutable-field attempts, invalid fields, source refresh, purge, and audit after edits.

## 3. CLI and HTTP

Files: `research/cli.py`, `server.py`, CLI/server tests.

- [ ] Add `GET research/record?kind=&id=&revision=` and `GET research/history?kind=&id=`.
- [ ] Add `POST research-record-revise` with the shared API arguments; conflicts return 409, validation returns 400, and failed operations do not select or mutate another project.
- [ ] Extend native entity commands with explicit update/history/inspect modes, keeping existing create/list behavior. Update options must not apply creation defaults to omitted fields.
- [ ] Test native CLI and HTTP edits, stale submissions, explicit field clearing and malformed payloads.

## 4. UI and localization

Files: dashboard renderer/script/styles, workspace labels, UI contracts and browser tests.

- [ ] Add Edit and History actions to all four authored record views.
- [ ] Reuse a native dialog with fields appropriate to the kind, explicit correction/supersession, required reason, Save and Cancel.
- [ ] Load record and snapshot on editor entry; preserve the draft on failure and reject late responses after cancel/navigation.
- [ ] Show revision metadata, read-only historical content and newer-source notices, retaining exact original citations.
- [ ] Render desktop and mobile flows, keyboard controls, all locales, cancellation, conflict and error recovery with synthetic archives.

## 5. Documentation, review and integration

- [ ] Update existing research usage, automation contracts and changelog with exact commands, schema compatibility, source-version limits and recovery behavior.
- [ ] Run `make check`, all affected browser suites, a new complete edit/history browser flow, and an independent final review.
- [ ] Review staged files for private content. Commit only product code, tests and durable documentation.
- [ ] Integrate only verified work. Keep one live server; coordinate any restart because the author is actively using the selected project.
- [ ] Report the implemented issue scope and separately retained feedback. Do not close issue #9 before its acceptance criteria and distribution requirements are satisfied.
