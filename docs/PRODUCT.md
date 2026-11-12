# Product direction and capability boundaries

Reviewed against the development checkout on 2026-11-10. This is a maintained
product reference, not a release announcement. Implementation status below distinguishes unreleased capabilities from remaining
proposals; no delivery dates are implied. Consult
[Workspace](WORKSPACE.md), [Editing scope](MANUSCRIPT_EDITING_RFC.md) and
[Installation](INSTALLATION.md) for current behavior and availability.

## The promise

**Read closely. Trace the evidence. Understand your text.**

Lixity brings close reading, traceable research and linguistic analysis into one
local manuscript workspace. Its distinctive value is the connection between a
measurement, the passage behind it, its research and a selected reading export.
Integrated writing extends that connection; it is implemented in development,
not yet released. Lead with practical outcomes, then show the mechanism.

Primary audience: novelists revising a manuscript, initially German-speaking,
with multilingual product introductions. Editors and people exploring language
are additional audiences. These are product choices, not demonstrated market
segments. Technical documentation remains English-only.

## Benefits we can demonstrate

| Benefit | Existing evidence and demonstration | Boundary to keep explicit |
| --- | --- | --- |
| Find a passage worth revisiting | Chapter comparisons, counted-text explanations and navigation back to prose; [analysis workflow](WORKSPACE.md#explore-language-in-the-browser) | Differences are not errors, quality scores or authorship proof. |
| Read with fewer distractions | Continuous prose, focus reading, search, optional analysis marks and passage tools; [workspace](WORKSPACE.md) | Source editing is a distinct, currently unreleased workflow. |
| Keep the reasoning behind a scene | Retained sources, claims, dossiers, author decisions and manuscript quotations; [research manual](research/USAGE.md) | Storing a claim does not verify it. Links preserve their accepted evidence rather than silently adopting new versions. |
| Revisit language questions consistently | CLI and Python API reuse the offline analysis engine with explicit settings; [methods](METHODS.md) | Reproducibility depends on text, software, language resources and settings. Translated interfaces do not imply equal analysis coverage. |
| Hear and rehearse prose | Teleprompter, pronunciation and direction planning, recording and selected synthesis services; [audio](AUDIO.md) | Microphone permission, optional workers and service data boundaries must stay visible. |
| Share the right amount of context | Reading websites, curated companion material, analysis and printable PDF; [export workflow](WORKSPACE.md#export-a-reading-website) | Reading copies are snapshots, not project backups or collaborative editors. |
| Write without restarting the workflow (unreleased) | CodeMirror, conditional autosave, recovery and revision-bound reading; [editing workflow](WORKSPACE.md#write-a-manuscript-unreleased) | Browser reload loses undo; recovery cannot guarantee keystrokes that never reached storage. |

The public synthetic demo demonstrates reading, comparisons and evidence without
requesting a private manuscript. It does not demonstrate saving. Do not describe
the demo video as an editor demonstration until it actually includes that flow.

## What should come next

This ranking is an assessment of current workflow gaps, not a count of feature
requests. Finish the edit–review–recover loop before adding more metrics.

| Priority | Proposed improvement | Current gap and acceptance evidence |
| --- | --- | --- |
| P0 — implemented, unreleased | Distraction-free auto-hide chrome & unified toolbars | Single-row reader and editor bars with semantic clustering; scroll-direction and inactivity auto-hide with instant keyboard/hover reveal and CLS = 0; browser-tested across seven locales. |
| P0 — implemented, unreleased | Compare conflicts and recovery copies | Three identified texts, editable candidate, deliberate apply and revision-checked save. Cancellation and intervening external changes are browser-tested. Manual comparison has no automatic merge or line-level diff. |
| P0 — implemented, unreleased | Protect cross-view drafts | Persistent editor; research forms guard close/reload, block disposal during pending requests and retain failed saves. Chromium and Firefox tests exercise actual navigation cancellation. Browser unload is still best effort. |
| P0 — release qualification remains | Prove real writing input and recovery behavior | Synthetic long-text and browser tests exist. Real IME, dead keys, screen readers, process interruption and disk failure need acceptance runs. Do not infer power-loss durability from atomic replacement. |
| P1 — implemented, unreleased | Search and replace in writing | Localized CodeMirror search supports case, words, regex and undoable replace-all. Selection-only scope and a persistent match counter remain optional usability work; long-text performance needs a measured baseline. |
| P1 — implemented, unreleased | Verified project backup and restore | Explicit manuscript/settings/attachment inventory plus retained research; hash verification, research audit and fresh no-replace destination. [Backup boundaries](PROJECT_BACKUP.md) exclude drafts, editor journal and unselected files. Stop writers first. |
| P1 — implemented with explicit limits, unreleased | Exact passage to writing | Revision-bound reader selection maps literal single-paragraph text with source context; repeated quotes, Unicode and CRLF are tested. Transformed Markdown and cross-paragraph selections are reported as unmappable. Arbitrary metric coordinates remain a separate integration. |
| P2 — after the core loop | Named manuscript versions and comparison | Automatic recovery and undo are not deliberate versions. Add explicit checkpoints with a readable comparison and non-destructive restore, reusing the conflict comparison UI. Keep research revision semantics separate. |
| P2 — lower adoption effort | First-run project setup and Linux packaging | Follow the existing installation/lifecycle strategy: create or open one project, show writable paths and validate an upgrade/rollback on a clean Linux installation. A desktop shell or Rust rewrite alone does not solve these workflow gaps. |

## Reuse before building

CodeMirror already has dedicated search and merge packages. Evaluate them against
the pinned editor adapter rather than creating a second editor. The upstream
[search repository](https://github.com/codemirror/search) and
[merge repository](https://github.com/codemirror/merge) now point to their new
hosting locations. Package availability is not an integration or safety test.
The merge UI must not decide which manuscript version is authoritative.

If browser-side draft persistence is added, treat it as a supplementary recovery
layer. Browser storage is origin-scoped and subject to retention rules; it cannot
replace a verified project backup. See [MDN storage quotas and eviction](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria).

Do not prioritize cloud collaboration, automatic prose rewriting, a new combined
quality score or a broad rewrite ahead of these gaps. These would introduce new
product and data boundaries without finishing the current local workflow.

## How to judge progress

Use voluntary sessions on synthetic projects first; these are proposed measures,
not telemetry already collected. Never record manuscript text or search terms.

- Can a new user open the demo, explain one measurement and return to its passage
  without instructions? Record task completion and where they hesitate.
- Can an author edit, undo, read the saved revision and resolve a staged conflict
  without an external editor? Record lost context and unsuccessful recovery.
- Can a reviewer distinguish unchanged, moved and ambiguous research links after
  edits? Inspect retained evidence, not just the displayed badge.
- Can a project be restored in a fresh directory with the same manuscript and
  valid evidence references? Verify the inventory and content hashes.
- For public discovery, compare tour-to-demo and installation-guide visits over
  consistent periods, alongside search impressions and clicks. Keep language and
  referral context; one day of traffic cannot establish the effect of a copy change.

A useful next milestone is a demonstrably recoverable revision session, not a
larger feature list. Revisit this ranking after observed author sessions and
before claiming the integrated editor is ready for routine manuscript work.
