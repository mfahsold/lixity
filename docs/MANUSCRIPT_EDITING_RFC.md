# Integrated manuscript editing

**Status: first native implementation is unreleased; broader design remains proposed.
Research reviewed 2026-11-10.**
The current source includes a locally bundled CodeMirror 6 editor, conditional
autosave and recovery for selected UTF-8 Markdown/text manuscripts. See the
[workspace manual](WORKSPACE.md#write-a-manuscript-unreleased) for its limits.
Research textareas retain deliberate revision saves, with cross-view draft guards.
The development editor also includes localized search/replace, manual three-text
conflict/recovery comparison and validated literal reader selections.
[Project backup](PROJECT_BACKUP.md) has a separate explicit inventory and excludes
editor recovery state. These additions do not close the acceptance gaps below.
This document owns the proposed editing boundary, evidence and acceptance criteria.
The editing API has its own `lixity-editor/1` schema; archive contracts are unchanged.
Requirements below describe the target, not completed acceptance gates.

The native read/write transition now retains the editor instance and undo history
while opening a revision-bound instance of the existing reader/analysis workspace.
A full browser reload still discards undo. Source changes during rendering are
rejected; external changes while reading pause writes on return. Research link
review reuses the existing resolver without modifying retained evidence. Browser
draft caching, named versions, automatic anchor migration and incremental analysis
are not implemented. Real IME, screen-reader and power-loss testing
remain outstanding. Recovery uses a local journal, not a system-wide file lock.

## Product decision

Let an author move from a finding to its passage, edit that passage in the same
workspace, and return to reading without losing selection or research context.
Offer **Read / Write** in the manuscript workspace, with the existing dossier
beside it. Use the shared typography, themes, localization and keyboard patterns.
Avoid a separate full-screen writing product or a modal containing the whole book.

Prefer a source-preserving Markdown editor with a restrained prose presentation.
Keep syntax visible around the caret initially; hiding it everywhere would add
selection, accessibility and composition risks before the basic workflow works.
Use ordinary prose typography, wrapping and a comfortable measure; line numbers,
code completion, bracket pairing and automatic indentation are not defaults for
novel writing. Formatting actions must be undoable editor transactions.

## Evidence and alternatives

Primary sources support mechanisms, not a claim that one editor is universally
best. Current documentation and recent maintainer discussions are more useful
here than popularity rankings. Historical standards are identified as such.

| Evidence | Consequence for Lixity |
| --- | --- |
| [CodeMirror system guide](https://codemirror.net/docs/guide/) describes transactions, viewport rendering and position mapping. Offsets count UTF-16 code units; line breaks count as one. | Keep one editor state, map selections through changes, and benchmark wrapped prose. Never equate browser offsets with Python string indices or raw-byte offsets. |
| [Reference manual](https://codemirror.net/docs/ref/) supplies wrapping, decorations and configurable extensions. [Changelog](https://codemirror.net/docs/changelog/) records continuing composition and accessibility fixes, including September 2026 fixes. | Pin a tested package set and review upstream changes. Decorations belong in the editor extension system, not direct edits to its DOM. No claim is made here about the latest available package version. |
| [September 2026 spellcheck discussion](https://discuss.codemirror.net/t/native-spellcheck-is-never-applied-to-a-codemirror-6-editing-host-on-chromium-152-electron-44/9886) includes a maintainer reply and the original reporter's correction: their reproduction worked in plain Chrome and failed in Electron. A later participant still reported a different Chrome problem. | Native spellcheck needs integration tests in the actual host. This thread neither establishes a universal CodeMirror defect nor guarantees our configuration will work. Test a future desktop shell independently. |
| [Tiptap Markdown documentation](https://tiptap.dev/docs/editor/markdown) currently labels its JSON/Markdown bridge beta and lists limitations. | Rich text remains an alternative if visual authoring becomes the stronger requirement. It requires explicit round-trip tests for Lixity syntax; semantic equivalence alone does not preserve source bytes. |
| [MDN beforeunload](https://developer.mozilla.org/en-US/docs/Web/API/Window/beforeunload_event) warns that unload notifications are unreliable, especially on mobile. | Save during work. Use visibility changes as an additional flush opportunity and an unsaved-change warning only while needed; neither is a durability guarantee. |
| [MDN storage](https://developer.mozilla.org/en-US/docs/Web/API/Storage_API/Storage_quotas_and_eviction_criteria) explains origin isolation, quotas and eviction. | Browser recovery is supplementary. A different localhost port is a different origin, and browser cleanup can remove drafts. |
| [RFC 9110, section 13.1.1](https://www.rfc-editor.org/rfc/rfc9110.html#section-13.1.1), published 2022, defines If-Match for conditional writes. | Require a strong base revision and reject stale saves. HTTP preconditions still need correct server-side coordination. |
| [W3C Web Annotation](https://www.w3.org/TR/annotation-model/), a 2017 Recommendation, defines position and exact-quote/context selectors. | Combine position mapping with quote verification and source revision. A nearby or repeated quotation is not proof of identity. |
| [Ink & Switch Patchwork](https://www.inkandswitch.com/project/patchwork/) is a 2024–2026 exploration of version control for creative work. | Distinguish transient undo, automatic recovery and deliberate named versions. This is research inspiration, not evidence that we need its storage implementation or collaborative editing now. |

A native textarea is still suitable for small fields, but extending it into a
book editor would make Lixity own selection, history and decoration machinery.
CodeMirror is the preferred middle ground. A rich-text document model should be
reconsidered only against demonstrated author needs and preservation tests.
Neither React nor a Rust rewrite is a prerequisite for this boundary.

## What the current implementation gives us

The following records the integration boundaries, not a power-loss durability
guarantee. The native editing slice now supplies the byte-preserving store and
shared in-process writer lock; the remaining limitations are noted below.

| Current component | Reuse | Gap before manuscript editing |
| --- | --- | --- |
| `ui/assets/markdown-editor.js` | Shared formatting vocabulary and localized controls | Textarea mutations and list continuation are not a manuscript transaction model. The key handler has no explicit composition guard; native undo behavior needs tests. |
| `io.py`, `FileUtils.read_source_snapshot` | A digest of original bytes and a consistent read | The analysis representation normalizes CRLF/CR. It does not retain the serialization metadata needed for faithful editing. |
| `FileUtils.atomic_write_bytes_if_changed` | Same-directory staging, file flush/fsync, permission preservation and atomic replacement | Atomic replacement prevents partial files, not competing edits. There is no parent-directory fsync in this helper; power-loss durability must not be overstated. |
| `server/routes_markers.py` | Existing explicit source-editing actions now share `SOURCE_WRITE_LOCK` with manuscript saves | Marker requests still have no expected manuscript revision. The shared in-process lock does not coordinate external editors or separate server processes. |
| Project-settings transactions described in [Architecture](ARCHITECTURE.md) | Explicit project identity, validation and optimistic checks | Their configuration guards are not a manuscript content revision or an external-editor lock. |
| `ui/assets/research-revisions.js` | Conflict/revision UX and retained drafts | Research revisions have deliberate meaning. Do not turn each manuscript autosave into an accepted research revision. |

## Proposed ownership and save protocol

The browser owns the live editing buffer and undo history. The local server owns
project resolution, source-byte revisions and filesystem writes. The analysis
engine consumes immutable snapshots. Existing public JSON schemas remain stable;
any new editing protocol must declare its own version and capabilities.

1. Open a server-selected manuscript, never a client-supplied arbitrary file path.
   Return a document identity, original-byte revision, editable text and explicit
   encoding/newline metadata. Unsupported encodings or mixed line endings need a
   visible conversion decision or read-only access, not silent normalization.
2. Route editor changes through transactions. Coalesce saves after a short idle
   period with a maximum wait during continuous typing. Measure these intervals
   before choosing defaults; do not serialize the entire book on every keypress.
3. Send the base revision and a unique operation identifier. Serialize Lixity's
   writers per document, including markers and multiple tabs. Check the current
   source identity and bytes before replacement. Deduplicate retries after a lost
   response so a successful write is not misreported as a new conflict.
4. Acknowledge a revision only after the specified persistence operation succeeds.
   An acknowledgement for an older buffer must not mark newer typing as saved.
   Keep at most one in-flight write per client and a coalesced pending state.
5. On conflict, retain the local draft and offer comparison/reload/save-a-copy.
   Never automatically choose the newest timestamp. External programs do not
   obey our lock: detect changes and preserve recoverable versions, and document
   the remaining check-to-replace race instead of promising universal locking.

Opening and closing an unchanged document must leave its bytes untouched.
Preserve comments, work markers, final newline and supported line endings.
Imported originals, such as DOCX, remain retained originals; edit an explicit
working copy rather than promising lossless Word round trips.

Use a local recovery journal with an explicit retention policy and bounded size.
Recovery data is manuscript content: exclude it from publication, diagnostic
uploads and version control. A browser draft cache may supplement it, with
storage failures reported. Recovery after process termination, disk-full errors
and power loss are different guarantees and require separate fault tests.

Display localized states such as **Saving**, **Saved locally**, **Unsaved** and
**Conflict** without stealing focus. A failed save stays visible and retryable.
Undo changes the current buffer; autosave persists it. Named versions and restore
remain intentional actions, with restoration creating a recoverable new version.

## Analysis, research links and navigation

Tag every analysis request/result with the exact input revision and configuration
identity. Reject out-of-order results. While typing, mark prior measurements as
outdated; do not make the old report appear to describe the new prose. Schedule
full analysis independently from saving. An incremental analysis path must prove
parity with the shared engine before replacing full analysis.

Map transient positions through editor changes. Verify retained quotations against
their original revision and exact text with context; if ambiguous or deleted,
show an unresolved reference. Never rewrite retained evidence to fit edited prose.
Moving a paragraph or changing a chapter heading must not silently attach its
review decision to a different passage.

Specify coordinate units at every boundary: CodeMirror UTF-16 offsets, normalized
analysis text positions and original file bytes are different spaces. Include
emoji, combining marks, CRLF, RTL text and repeated passages in contract tests.
Preserve caret/selection and a passage anchor when switching Read/Write, opening
a dossier or returning from an analysis finding. Do not depend on pixel scroll
coordinates alone after wrapping or font changes.

## Integration and accessibility

Load the editor bundle on entering Write. Keep public read-only exports free of
editing dependencies and save capabilities. Bundle locally with a lockfile and
license inventory; no CDN, telemetry or runtime Node installation is required.
Review package licenses and transitive assets before adding the dependency.

Share the editor adapter and toolbar commands with research fields where useful,
but keep their different save semantics outside that adapter. Preserve one
current product path rather than a permanent old/new editor switch.

Do not intercept Enter during IME composition or replace the editor during active
composition. Test accented dead keys, Japanese/Chinese input, RTL selection,
dictation and mobile keyboards. Synthetic events cannot establish real IME support.
Keep Tab navigation escapable and test screen-reader labels and announcements.
Do not announce every keystroke or save transition. Treat native spellchecking
as optional browser behavior, not Lixity's deterministic linguistic analysis.
Any external spelling service needs a separate privacy and dependency decision.

## Acceptance gates before enabling writes

| Area | Required evidence |
| --- | --- |
| Source fidelity | Byte-identical no-op; explicit handling of CRLF, BOM, unsupported encodings and mixed newlines; marker/comment preservation |
| Persistence | Two tabs, external edit, marker race, lost acknowledgement/retry, permission failure, disk-full, crash during staging, restart and recovery |
| Editing | Undo/redo across formatting and autosave; cut/paste, large paste, find/replace, selection after view switches; no focus jumps |
| Input/accessibility | Chromium and Firefox browser tests; real IME/dead-key and screen-reader checks; actual Linux desktop host tested separately |
| Scale | Synthetic 50k/150k/300k-word books, long paragraphs and dense annotations; record hardware, load time, memory and typing/scroll latency distributions |
| Analysis | Revision mismatch and reordered-result rejection; edited/deleted/repeated-quote anchors; unchanged deterministic results for the same snapshot |
| Packaging/privacy | Offline packaged install, lazy-loaded assets, license inventory, read-only exports without write controls, no private fixtures |

Performance figures are not yet measured. Viewport rendering is a useful mechanism,
not proof that long wrapped manuscripts or thousands of decorations meet our needs.
Establish a reproducible baseline before selecting latency and memory budgets.

The first implementation should validate a synthetic Markdown manuscript with
Read/Write, undo, conflict-safe local saving and recovery. Rich-text hiding,
collaborative CRDTs, cloud sync, tracked-change review and a backend rewrite are
separate decisions after this foundation works. No migration of existing projects
or manuscript mutation is authorized by this RFC alone.
