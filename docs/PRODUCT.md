# Product direction and capability boundaries

Reviewed against the development checkout on 2026-11-23, following the 0.8.2
release. This page records demonstrated capabilities and proposed improvements.
Installation guides and release notes identify available builds. Consult
[Workspace](WORKSPACE.md), [Editing scope](MANUSCRIPT_EDITING_RFC.md) and
[Installation](INSTALLATION.md) for current behavior and availability.

## The promise

**Read closely. Trace the evidence. Understand your text.**

Lixity brings writing, close reading and traceable research into one local
manuscript workspace. Open the passage behind a measurement, decide whether to
revise it and keep the research that shaped the scene. Prepare a reading copy
with the material you choose.

Primary audience: novelists revising a manuscript, initially German-speaking,
with multilingual product introductions. Editors and people exploring language
are additional audiences. These are product choices, not demonstrated market
segments. Technical documentation remains English-only.

## Benefits we can demonstrate

| Benefit | Existing evidence and demonstration | Boundary to keep explicit |
| --- | --- | --- |
| Find a passage worth revisiting | Inspect the words behind a sentence warning. Open examples from a rhythm or word-pattern comparison and return to the scene. [Analysis workflow](WORKSPACE.md#explore-language-in-the-browser) | Read a measured difference in context before deciding whether to revise. [Methods](METHODS.md) |
| Read with fewer distractions | Continuous prose, focus reading, search, optional analysis marks and passage tools; [workspace](WORKSPACE.md) | Source editing is a distinct workflow, included in 0.8.1. |
| Keep the reasoning behind a scene | Follow a manuscript quote through retained sources, claims, dossiers and author decisions. [Research manual](research/USAGE.md) | Links preserve the evidence version you accepted. Evaluate a claim and decide what the manuscript should do with it. |
| Review where a character appears | Development checkout shows chapter counts, complete matching passages and surrounding sentences, with a preview for additions to a saved dossier. [Dossier workflow](research/USAGE.md#manuscript-driven-dossier-drafts) | The search measures counted names and configured variants. Read the scene for implicit appearances and pronouns. |
| Revisit language questions consistently | CLI and Python API reuse the offline analysis engine with explicit settings; [methods](METHODS.md) | Reproducibility depends on text, software, language resources and settings. Translated interfaces do not imply equal analysis coverage. |
| Hear and rehearse prose | Teleprompter, pronunciation and direction planning, recording and selected synthesis services; [audio](AUDIO.md) | Microphone permission, optional workers and service data boundaries must stay visible. |
| Share the right amount of context | Reading websites, curated companion material and manuscript PDFs. The development checkout provides a PDF of the selected saved dossier version. [Website export](WORKSPACE.md#export-a-reading-website) · [Dossier PDF](WORKSPACE.md#download-a-dossier-pdf) | Check the files and evidence before sharing. Use the verified backup workflow for restoration. |
| Write without restarting the workflow | CodeMirror, conditional autosave, recovery and revision-bound reading; [editing workflow](WORKSPACE.md#write-a-manuscript-unreleased) | Browser reload loses undo; recovery cannot guarantee keystrokes that never reached storage. |

Use the public Warehouse 4 project to show what an author can decide after
reading a measured passage. The demo supports inspection of the fixed project.
Record any writing, archive saving or download scenes in a synthetic local
project. Label local actions when the public demo uses a fixed copy.

## What should come next

This ranking is an assessment of current workflow gaps, not a count of feature
requests. Finish the edit–review–recover loop before adding more metrics.

| Priority | Proposed improvement | Current gap and acceptance evidence |
| --- | --- | --- |
| P0 — shipped in 0.8.1 | Distraction-free auto-hide chrome & unified toolbars | Single-row reader and editor bars with semantic clustering; scroll-direction and inactivity auto-hide with instant keyboard/hover reveal and CLS = 0; browser-tested across seven locales. |
| P0 — shipped in 0.8.1 | Compare conflicts and recovery copies | Three identified texts, editable candidate, deliberate apply and revision-checked save. Cancellation and intervening external changes are browser-tested. Manual comparison has no automatic merge or line-level diff. |
| P0 — shipped in 0.8.1 | Protect cross-view drafts | Persistent editor; research forms guard close/reload, block disposal during pending requests and retain failed saves. Chromium and Firefox tests exercise actual navigation cancellation. Browser unload is still best effort. |
| P0 — release qualification remains | Prove real writing input and recovery behavior | Synthetic long-text and browser tests exist. Real IME, dead keys, screen readers, process interruption and disk failure need acceptance runs. Do not infer power-loss durability from atomic replacement. |
| P1 — shipped in 0.8.1 | Search and replace in writing | Localized CodeMirror search supports case, words, regex and undoable replace-all. Selection-only scope and a persistent match counter remain optional usability work; long-text performance needs a measured baseline. |
| P1 — shipped in 0.8.1 | Verified project backup and restore | Explicit manuscript/settings/attachment inventory plus retained research; hash verification, research audit and fresh no-replace destination. [Backup boundaries](PROJECT_BACKUP.md) exclude drafts, editor journal and unselected files. Stop writers first. |
| P1 — shipped in 0.8.1 with explicit limits | Exact passage to writing | Revision-bound reader selection maps literal single-paragraph text with source context; repeated quotes, Unicode and CRLF are tested. Transformed Markdown and cross-paragraph selections are reported as unmappable. Arbitrary metric coordinates remain a separate integration. |
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
- Can an author find a character's appearances, review a manuscript addition
  and download the intended dossier version? Compare the PDF with that saved
  revision, including its last passage and pinned source quotations.
- Can a project be restored in a fresh directory with the same manuscript and
  valid evidence references? Verify the inventory and content hashes.
- For public discovery, compare tour-to-demo and installation-guide visits over
  consistent periods, alongside search impressions and clicks. Keep language and
  referral context; one day of traffic cannot establish the effect of a copy change.

A useful next milestone is a demonstrably recoverable revision session, not a
larger feature list. Revisit this ranking after observed author sessions and
before claiming the integrated editor is ready for routine manuscript work.
