# Local research archive

**Experimental local research archive system.**
Keep selected text, PDF and PNG/JPEG sources in an explicit local project. Dossiers
bring notes and evidence together; claims record assertions; decisions explain
the author's choices. The workspace preserves saved versions and exact quotations.
Text sources can be analysed separately or compared with a manuscript.
It does not implement the entire [RFC](README.md).

Product versions describe development maturity; response and archive schemas
are independent. v0.7.1 reads research records/manifests v1–v8, including
historical v3.0.1 archives. Reading an archive does not upgrade it. See
[compatibility and limits](#limits) before writing with an older application.
Since v0.7.0, optional dossier geography uses v8. Ordinary dossier encodings stay
unchanged until a geographic save; older readers cannot open v8 archives.

Use `lixity research --help` to discover implemented commands and
`lixity research COMMAND --help` for exact arguments and output formats.
`lixity about --json` reports supported schema versions and command metadata;
`lixity research schema` exports the entity JSON schema. This guide covers
workflows, retained data and semantics that command help cannot establish.

The implementation provides local captures, lexical search, exact citations,
versioned dossiers/claims/decisions, explicit manuscript associations, review,
OCR integration and verified backup/restore. It does not provide remote web
imports, embeddings/semantic search, automatic factual verification, prose
rewriting or automatic Zotero synchronization. Interface text supports seven
languages; research CLI help/errors are English. Labels do not translate sources
or extend language-specific linguistic validation.

## Research workflows

Use Zotero for source collection, bibliographic metadata, ordinary reading,
annotations and general notes. Lixity connects selected evidence to authored
claims, decisions, dossiers and manuscript quotations. Historical maps and
photographs remain source material; character journeys and their scene context
are authored project records.

**Since v0.7.1:** the research view starts with dossiers. The saved
evidence area keeps Zotero selection and optional local import behind compact
disclosures. Revision previews, historical comparisons and explicit Markdown
editing reuse the existing archive. Dossier `--file` now reads an existing UTF-8
file; migrate literal text arguments to `--body`. Archives and citations are unchanged.
Zotero is optional: retained evidence and authorized local imports work without it.

<a id="reading-and-cli-workflows-since-v240"></a>
### Reading and CLI workflows

**Current main, after v0.7.1:** dossier, claim and decision creation starts behind
labelled disclosures, so existing records remain visible first. Evidence
association and cause/effect entry use the same pattern. Click the heading again
to collapse a form; the long creation forms also offer **Collapse** beside Save.
Collapsing and changing research tabs keep the current unsaved fields in memory.
This is not persistent draft storage: reloads and project changes can discard them.
Saving remains a separate explicit action.

Escape inside a disclosure closes its innermost open level and returns keyboard
focus to that heading. Native select menus and dialogs retain their own keyboard
handling. In the manuscript companion, Escape closes an open disclosure before
closing the companion itself. Contextual actions such as **Add historical claim**
or using a retained passage open the corresponding form and focus its next field.
Independent forms stay independent; opening a dossier in the companion replaces
the currently displayed dossier without creating another pane.

Dossier catalogue excerpts are plain-text reading previews. Markdown styling and
fenced code are omitted from the preview only, including code blocks cut short by
the excerpt limit; the saved body and API excerpt remain unchanged. Open the
record for full text, diagrams and provenance. Disclosure arrows use a brief
state transition, disabled when the operating system requests reduced motion.

Existing-archive commands may omit `--project` only when the current directory
itself is a validated initialized research project. No parent directory,
environment, global configuration or last-opened browser project is consulted.
Explicit `--project` wins; `init` requires it and restores require `--to`.
Python/HTTP project selection remains explicit.

```sh
cd ./novel
lixity research sources --format text
lixity research search --query "reading room"
lixity research link PASSAGE_ID CLAIM_ID --relation contextualizes
```

Use returned IDs. v0.7.1 also accepts complete bare UUIDv4 selectors in the
CLI and canonicalizes them to `urn:uuid:…`; API and stored identifiers stay strict.
Grouped help and discovery expose command aliases, including `dossiers`, `claims`
and `decisions`, without separate command implementations.
`link` creates evidence; `link-evidence` also supports
inspection and revisions. In the source reader, selecting text within one
uniquely resolved retained paragraph prepares an evidence draft. Review its
quote and full paragraph context, choose a claim/relation and save separately.
The citation still identifies the whole paragraph, not a sentence-level selector.
Ambiguous or cross-paragraph selections fail; whole-passage actions remain
available for touch use. Preparing a draft writes nothing.

In **Manuscript**, **Dossier alongside** opens a chosen dossier in a
read-only companion. It starts closed with no automatic selection. **Current main
(unreleased):** the manuscript stays continuous and the **Analysis** button has an
explicit On/Off state. A dossier and analysis are alternative context tools;
hiding analysis leaves an active dossier. **Analysis overview** opens dense
comparisons with **Back to passage**, restoring the prior context tool. Refresh
explicitly for the latest dossier.
On desktop, opening the companion temporarily collapses project navigation into
a narrow rail. Use **Show navigation** to access its controls; closing the companion
restores the earlier manual choice. Switching away from manuscript analysis also
restores normal navigation. The navigation toggle is desktop-only; narrow screens
keep their horizontal workspace switcher. These choices last for the current page.
Desktop areas scroll separately. Drag the divider or focus it and use Left/Right
to adjust the manuscript share; Home/End select its 35%/75% limits. The chosen
split is a browser-local preference. Narrow screens stack the documents and hide
the divider. Reading changes neither document, evidence links nor the statistical
baseline. **Focus reading** temporarily hides the companion and navigation;
the same control restores the workspace. A paragraph's **Values** inspector and
the companion replace one another rather than competing for horizontal space.

To connect the manuscript to research, select a nonempty text range within one
paragraph and choose **Link selection to claim** (or Alt+L). The
selection toolbar offers the same action; the paragraph's **…**, right-click or
keyboard context menu also reaches it when the selection is valid. Choose an existing claim,
review the quotation and explicitly allow retention before saving. This creates
an association; it does not turn a manuscript statement into source evidence.
The claim's dossier and retained evidence remain separate authored records.

For the reverse route, open **Review** in Research and use the saved manuscript
associations. **Open claim** opens the association's pinned claim revision, with the latest revision separately available; **Go to manuscript
passage** switches to analysis, reveals the paragraph, clears incompatible passage
filters and focuses the linked text. The return action is offered only when the
current paragraph hash, line range and exact quotation match the resolved anchor.
Moved, adjusted, ambiguous or unavailable anchors remain review tasks, with no
silently inferred jump or re-pin. The manuscript's saved-associations disclosure
provides the same actions while reading.


Claims' **Author review state** labels map to stored `hypothetical` (**Author
assumption**), `evidenced` (**With evidence**) and `disputed` (**Disputed**).
These are author assessments, not probabilities. `evidenced` does not require an
evidence link or verify a source.

### Associate a manuscript quote with a claim

In the continuous manuscript reader, select text within one profiled paragraph. Choose **Link selection to claim** from
the selection/context tools or paragraph action (or press `Alt+L`). Review the exact quote, choose a
current claim, explicitly permit local retention of the quote, then **Save association**.
Selection, choosing a claim and previewing the form write nothing. Saving creates
a distinct `manuscript_claim_link`, with an exact claim-revision pin and paragraph
anchor. It does not edit prose, import the manuscript as a research source, create
source evidence or establish factual support. This workflow requires an explicitly
selected manuscript inside the initialized research project and a compatible
native server; standalone HTML cannot save links.

Only the selected quote, project-relative source path, raw-source SHA-256,
paragraph SHA-256, source line range and Unicode-codepoint offsets are retained,
plus an optional note and ordinary record metadata. The archive stores no full
manuscript blob. Quotes are nonblank and limited to 10,000 codepoints; notes to
2,000 characters. Offsets refer to the displayed `ParagraphProfile.text`, with an
exclusive `end`, rather than UTF-8 bytes or JavaScript UTF-16 units. The paragraph
hash is SHA-256 of that displayed text encoded as UTF-8. This established anchor
projection removes supported emphasis markers, comments and footnote anchors;
link and inline-code syntax remain as text. Soft-wrapped lines are joined and
source line endings normalized, while the raw-source SHA-256 binds the original
bytes. `find-anchor` matches the query exactly, case-sensitively, without fuzzy
matching or Unicode normalization. Use `word` for `*word*`, but retain link/code
syntax present in the paragraph text. Prose counting uses a separate projection
that excludes destinations, images and code. Cross-paragraph, ambiguous or stale
selections fail. Paths escaping the project, including through
symlinks, are rejected. Source bytes are checked again before publication; this
optimistic guard does not lock an external editor.

Saved quotes mark only exact resolved anchors in the shared reader, in the same canonical manuscript DOM. Displaying analysis or an overview preserves
the same text and anchor model. Manuscript search still checks complete text. Review reports
changed source bytes, newer/withdrawn claims, unique moved paragraphs, adjusted
paragraphs whose quote is unchanged, and ambiguous matches. Moved or adjusted
candidates have resolved coordinates but remain pending review until an explicit
re-pin. Ambiguous quotes are not re-pinned; an edited quote requires an explicitly
reviewed, uniquely resolvable replacement through `--new-quote`. These flags
request a human review, not a semantic contradiction check or factual verdict.
Retraction and note/claim revisions use the existing record history and strict
revision API. A uniquely resolvable anchor is re-pinned explicitly: `lixity
research reconcile-manuscript --accept-moved` (or `POST /api/research-manuscript-reanchor`)
writes a new link revision with the resolved line span, refreshed paragraph hash
and offsets for adjusted paragraphs, and the current file digest; the earlier
anchor stays in revision history.

The same flow is scriptable from the CLI.
`--selection` takes the JSON selection object above (literal or a local file);
`--expected-snapshot` / `--expected-source-sha256` default to one initial read
and still fail when the bytes or the archive change before saving.

```sh
lixity research find-anchor --project ./novel novel.md --query "exact quote"
lixity research link-manuscript --project ./novel novel.md \
  --claim-id CLAIM_ID --claim-revision 2 --quote "exact quote" --allow-retention
lixity research manuscript-links --project ./novel
lixity research review-manuscript --project ./novel novel.md
lixity research reconcile-manuscript --project ./novel novel.md            # preview
lixity research reconcile-manuscript --project ./novel novel.md --accept-moved
```

The manuscript path is accepted positionally (like `analyze`, `scenes`, `showing`)
or as `--manuscript PATH`; pass exactly one of the two forms.

<a id="compact-manuscript-link-command-reference"></a>
<a id="end-to-end-manuscript-link-lifecycle"></a>
Use each command's `--help` for flags and output formats. After editing prose,
run `review-manuscript`, preview `reconcile-manuscript`, then explicitly accept
the reviewed change. `--accept-moved` accepts uniquely resolved moved/adjusted
anchors. `--accept-claim-updates` independently re-pins newer claim versions;
combine them to accept both in one revision **per association** when its quote
resolves uniquely. Neither flag accepts the other kind of change. An ambiguous,
changed or unavailable anchor is not repaired by accepting a claim revision;
an edited quote needs the explicit replacement below. Without `--link-id`,
eligible associations use separate commits, so a run can partially succeed.
Inspect `accepted`/`skipped`, then run `review-manuscript` again; the command
does not guarantee that every association is resolved. `claim_changed` remains
until its claim pin is explicitly updated or the association is superseded.
`unlink-manuscript` retracts an association while retaining history and works
when the scoped manuscript is deleted or unreadable. Optional snapshot/revision
guards make retraction strict.

A changed source-file digest (`source_changed`, for example after an edit in an
unrelated chapter) is informational and does not mark an association for review
while its paragraph hash, line span and quote still match exactly. An edit inside
the paragraph but outside the quote reports `anchor_adjusted` and can be accepted
with one command or click. Editing the quote itself reports `anchor_changed`;
the CLI can explicitly re-pin a uniquely resolvable replacement with
`reconcile-manuscript --accept-moved --link-id ID --new-quote "…"`, preserving
the earlier quote in history. Creating a fresh association is also possible.

Python uses `link_manuscript_claim`, `list_manuscript_links` and
`review_manuscript_links`; exact arguments and guarded native payloads are in
the [automation contract](../AGENTS.md#manual-manuscript-associations).
The native **Review** tab lists associations, anchor states and flags without
writing. Reading/listing/reviewing never opts into a newer storage schema.

The first successful permitted save uses record/manifest v7. Historical v3.0.1
cannot read v7; every reader/writer must explicitly support it. Audit, history
and export/restore preserve accepted link records. Exported quotes remain
private manuscript material; there is no full manuscript blob. Restored links
remain unavailable until the manuscript exists at its saved project-relative path.

### Claims linked to a dossier

Both the research dossier reader and **Dossier alongside** show the current
claims explicitly linked to the dossier. **Open claim** uses the existing record
viewer and saved-version history. The reverse list reads current claim records;
it does not reconstruct a historical claim list for an older dossier revision.

Each claim can show an active saved manuscript-quote count. The count joins
explicit links by claim ID and the linked claim revision's pinned dossier ID,
from the same archive snapshot as the claim list. A changed snapshot or failed
read makes the count unavailable. Zero means no matching active saved link in
that snapshot; it does not establish that the claim is unused in the manuscript.
Newer claim/dossier revisions do not silently change an older link's association.
Counts include links pinned to other saved versions of the same logical dossier;
the reader marks that version difference explicitly.

<a id="claim-chronology-and-causeeffect-links-since-v300"></a>
### Claim chronology and cause/effect links

In **Claims**, choose **Timeline** to organize the current claim revisions by
their recorded `time_period`. **List** returns to the ordinary claim cards.
Each dated claim shows its placed calendar range, both sections carry a count,
and the view names the recognized formats and how to place a claim. Every period
label is preserved and the record's creation date is never substituted. Opening
or filtering the timeline changes no archive records or index.

The chronology places valid four-digit CE years (`0001`–`9999`), ISO months
(`YYYY-MM`), ISO calendar dates (`YYYY-MM-DD`) and ranges whose endpoints have the
same precision, for example `1912`, `1912-03`, `1912–1914`, `1912-05-01` and
`1912-05-01 / 1912-05-03`. Ranges accept `–`, `—`, `/`, `..` and a
plain hyphen between two four-digit years (`1924-1926`, spaces optional); ISO
month/day hyphens are never split. Missing periods, invalid
dates/reversed ranges and labels such as `autumn 1912` or `44 BCE` remain visible
under **Unplaced periods** with a reason; free-text periods such as
`present day` stay there on purpose. Temporal placement does not verify
chronology or establish a historical fact. Creating or revising a claim reports
an unplaceable period in the envelope's `warnings` list, and the native claim
form shows the accepted formats under the period field.

```sh
lixity research timeline --project ./sample-project
lixity research timeline --project ./sample-project --format text
lixity research timeline --project ./sample-project --format md --dossier-id DOSSIER_ID
```

`research-timeline-local/1` includes coherent project/snapshot metadata, `dated`
and `unplaced` entries. Original periods and claim revisions remain visible;
placed entries add their parsed range and precision, unplaced entries a reason.
This projects current claims, not earlier archive timelines.

Under **Cause and effect claims**, choose the proposed cause and effect by their
displayed claim labels, review the saved versions and optionally explain your
interpretation, then select **Save cause/effect link**. The link is a separate
authored `ClaimRelation`, distinct from passage-to-claim evidence links.
`causes` is the stored relation; `results_in` is an input alias in the same
cause-to-effect direction. Self-links are rejected. Cycles are allowed as
explicit author assertions; no transitive or reverse links are inferred.

```sh
# Replace placeholders with complete claim IDs from research claim.
lixity research relate --project ./sample-project FROM_CLAIM TO_CLAIM \
  --relation causes --rationale "Author interpretation for review"
lixity research relate --project ./sample-project
lixity research relate --project ./sample-project --claim-id CLAIM_ID --include-retracted
lixity research relate --project ./sample-project --relation-id RELATION_ID --inspect
lixity research relate --project ./sample-project --relation-id RELATION_ID --history
```

New links pin the chosen claim revisions. The CLI/Python API use current
revisions when no explicit pins are supplied; `--from-claim-revision N`,
`--to-claim-revision N` and `--expected-snapshot DIGEST` let automation bind a
reviewed choice. A later claim edit does not retarget a link: its earlier
endpoint labels remain visible and `review_needed` marks newer endpoint revisions.
Creation returns `research-claim-relation-local/1`; listing returns
`research-claim-relations-local/1` with the project, snapshot, archive schema and
exact endpoint/current revision information. Retracted links are omitted unless
`--include-retracted` is supplied.

Use **Edit**/**Saved versions** or the ordinary revision workflow to correct
endpoints, change rationale or retract a relation. Unchanged endpoints keep their
pins; repinning requires explicit revisions. Three-way previews and atomic batches
accept `kind: "claim_relation"`. Retraction appends history. Archive integrity and
linked evidence do not verify causality. A first causal write opts into storage
schema v6; reads do not. See [compatibility](#limits).

<a id="choose-citations-by-keywords-since-v300"></a>

### Choose citations by keywords

In the evidence-link form, select a claim and choose **Find source passage**.
This opens the existing Search view with **Sources** selected and keeps your
claim choice. Search keywords, read the matches and choose **Use for claim** to
return to the draft. Review the full retained paragraph, choose an evidence
relation and save explicitly. Search and draft preparation accept no claim and
write no authored record. Duplicate titles are not treated as identity.

The terminal can also resolve a paragraph without typing its UUID:

```sh
lixity research cite --project ./sample-project --query "reading room"
# For multiple matches, repeat the same query and displayed snapshot:
lixity research cite --project ./sample-project --query "reading room" \
  --pick 2 --expected-snapshot SNAPSHOT_SHA256
```

Exactly one match returns the existing full `research-citation-local/1`
citation. Zero or multiple matches return the unchanged source-search
`research-search-local/1` JSON with exit code `1`; multiple matches also print
safe numbered choices on stderr. No best-ranked hit is accepted silently.
`--pick` selects one of at most 20 displayed matches (`1`–`20`) and requires the
same query plus its displayed snapshot. Changed snapshots, unavailable sources
and out-of-range choices fail; search again before choosing. Ordinary search
may refresh its disposable index, but citation selection creates no claim/link
or source capture. `--passage PASSAGE_ID` remains precise retrieval of an exact
retained citation, including historical captures. It is mutually exclusive with
`--query`; `--pick` and `--expected-snapshot` apply only to query selection.

Both routes identify the complete retained paragraph with its source version,
hash and character offsets. They do not create sentence-level citations,
translate quotations or change lexical search into semantic search.

The native evidence draft binds its selected project, reviewed snapshot and
claim revision. If these change before saving, review the current context rather
than silently linking a newer claim. Python `link_evidence` accepts optional
`expected_project_id`, `expected_snapshot` and `expected_claim_revision` guards;
HTTP evidence creation accepts `project_id`, `research_token`, `expected_snapshot`
and `expected_claim_revision`. Supplied guards reject changed reviewed context;
guarded links also reject withdrawn evidence. Source withdrawal does not erase
historical citations.

Claim lists consistently return `research-claims-local/2` with `claims`,
`project_id` and `snapshot` from one accepted snapshot. Consumers of the earlier
v1 envelope must update; stored claims/history are unchanged.

### Continue an interrupted source import

```sh
lixity research ingest --project ./novel --file source-a.pdf source-b.txt \
  --checkpoint library.json --allow-retention --progress
lixity research ingest --project ./novel --checkpoint library.json \
  --resume --allow-retention --progress
```

A checkpoint remembers ordered files and capture settings. Resume verifies bytes,
project, OCR configuration and source identity, skipping verified completed captures.
Complete prepared extraction can survive interruption/failed publication; interrupted
or unrecorded extraction may run again. Changed files/order/settings need a fresh
checkpoint. Lost completion receipts are recovered from exact accepted identities.

After another archive write, inspect the current archive and acknowledge its digest
with `--expected-snapshot DIGEST` when resuming. This authorizes that retry, without
rebasing decisions or restoring changed/purged captures. Original files must remain
present and unchanged.

Checkpoints are `.json` files under `<project>/.lixity/research/imports/`, including
when absolute paths are supplied. Limits are 1–1,000 files and 64 MiB of JSON
preparation/metadata; even one large or heavily escaped capture can exceed the
budget. Rejection preserves the previous readable checkpoint. Checkpoint imports
do not support `--dry-run`.

Preparation contains private source text outside accepted archive/export bundles.
`ingest --discard-checkpoint library.json` removes preparation/receipts, leaving
accepted records intact. Completed payloads are cleaned after publication.
Purge coordinates with matching checkpoints: busy, unreadable or malformed ones
can block it until explicit discard. Resume never silently restores deleted captures.
Progress phases use stderr; final envelopes are `research-checkpoint-ingest-local/1`
and `research-checkpoint-discard-local/1`. Import exits zero only when complete.

### Read reports in the terminal

```sh
lixity research sources --project ./novel --format text
lixity research audit --project ./novel --format text
lixity research review --project ./novel --json
```

Human reports bound long lists/findings; request JSON for the complete payload.
Output formats/defaults are command-specific: inspect `--help` or
`lixity about --json`. `--pager` requires explicit use with a human format and
interactive input/output; pipes never start one. Progress phases use stderr,
leaving stdout for the result. Imported values remain inert text.
The running server exposes registered routes at `GET /api`; research responses
are JSON. Manuscript PDF and confidentiality-agreement downloads are separate
binary/text attachment workflows.

### Update one reviewed record

`dossier`, `claim` and `decision` accept `list`, `show ID`, `inspect ID` or a
positional ID; explicit update/history modes still work with that ID. Their
`--latest` convenience option selects the current revision and snapshot together;
a later write still fails. Inspect the record first when human review is required.

Ordinary `dossier`, `claim`, `link-evidence`, `decision` and `relate` commands
with `--update` require `--expected-revision`, `--change-kind` and `--reason`.
The archive-wide `--expected-snapshot` is optional for these ordinary updates.
When omitted, the backend checks the reviewed target revision and uses that
read's snapshot for the strict commit. Earlier unrelated writes are allowed;
changed targets and later races fail without retry or rebase. An explicit
snapshot guards the entire archive, including unrelated changes.

```sh
lixity research claim --project ./novel --claim-id CLAIM_ID --update \
  --expected-revision 1 --change-kind correction --reason "Reviewed wording" \
  --statement "A revised author assertion"
```

**Since v0.7.1:** `--update --dry-run` validates the exact proposed
write, including revision, reason, association pins and optional snapshot, without
taking the writer lock or publishing records. It does not merge drafts or promise
that a later commit will succeed. `--diff` instead compares supplied fields with
the current record in one coherent read; it is a comparison, not write validation.
Add `--from-revision N` to compare saved versions, optionally selecting
`--to-revision M`; an omitted destination means the HEAD observed in that read.

```sh
lixity research dossier --project ./novel --dossier-id DOSSIER_ID --diff \
  --section "Smuggling route" --file revised-section.md
lixity research dossier DOSSIER_ID --project ./novel --diff --from-revision 1
```

Unchanged associations retain their exact saved pins. Without an explicit snapshot,
changed associations require explicit reviewed revisions; inspect command help for
the corresponding pin options. Historical comparisons never repin. Python shares
these semantics; HTTP, images, acknowledgements and batches keep explicit guards.

For dossier body input, use `--file existing.md` or `--body "Literal text"`, never
both. v0.7.1 rejects missing, unreadable or non-UTF-8 files before a write;
it no longer interprets a missing filename as body text. This applies equally to
creation, updates, preparation and prospective comparison.

### Resolve conflicting drafts

The revision editor keeps the draft and reason after a conflict and prepares a
comparison of its base revision, the current record and the draft. Under
**Review concurrent changes**, inspect the preview and explicitly choose current
or draft values for overlapping fields. **Use reviewed changes** updates the
draft; save separately. Preparing or selecting a resolution writes nothing.
Another change before saving still rejects the save and keeps the draft.

CLI users can prepare a draft with `--prepare --base-revision N` instead of
`--update`. This is three-way reconciliation of the saved base, current record
and draft, unlike exact update dry-run. Resolve overlapping fields with repeated
`--resolve FIELD=current` or `FIELD=mine`.
Submit the resulting changes with the returned snapshot/revision tokens through
the existing strict update command. Association IDs and revision pins are
compared together; unchanged associations keep their historical pins.
Prepared decision lists include `dossier_revisions`, a map from selected dossier
IDs to existing revision numbers. Keep this map when applying the preview so a
restored draft link retains the revision you inspected.

### Work on one dossier section

Bounded reads accept named IDs, positional IDs and `show`/`inspect`
with the same section/summary/citation controls, including `--revision N`.
Section and summary are distinct modes; summary and citation omission apply only
to reads. Unbounded inspection keeps its record envelope. Section edits still use
the ordinary revision workflow below.

In a dossier, choose **Edit section** beside an unambiguous heading. The existing
revision editor opens that section's content, including its subsections. It keeps
your draft after a failed save. Concurrent changes in other sections remain intact;
overlapping edits need an explicit choice in the preview before saving.

Use `dossier --dossier-id ID --section "Heading"` to read a bounded section;
`--update --file section.md --section "Heading"` replaces only that section's
content, with the usual snapshot, revision and reason requirements. Both reading
and replacing a section include its subsections. Headings inside fenced code are
ignored; repeated heading names reject ambiguous reads/updates. Other text,
line endings and evidence references are preserved. Prepared section drafts
start from the selected base revision, never a silently substituted current body.

Preparation can combine section text and ordinary metadata changes through the
same revision path; unrelated current sections survive. Python entrypoints and
result contracts are in the [automation reference](../AGENTS.md#51-research-api-lixityresearchapi).

### Edit an exported Markdown dossier

**Since v0.7.1:** the archive remains authoritative. Export an
existing dossier, edit the file, preview reconciliation, then apply the reviewed
packet explicitly:

```sh
lixity research dossier ID --project ./novel --export-edit draft.md
# Edit draft.md, retaining its leading lixity-dossier-edit/1 JSON comment.
lixity research dossier ID --project ./novel --prepare --edit-file draft.md
lixity research dossier ID --project ./novel --prepare --edit-file draft.md \
  --output reviewed.json --change-kind correction --reason "Reviewed draft"
lixity research revise-batch --project ./novel --file reviewed.json \
  --apply --expected-snapshot DIGEST
```

Use the snapshot returned with the ready packet. The versioned packet binds the
reviewed project and snapshot; a later archive change requires another preview,
not substituting a newer digest. Applying reads the packet, not later edits to
the Markdown file. Export and packet output require new files outside the archive
and its internal `.lixity` directory; existing files are never overwritten.

The leading comment identifies the project, record and base revision. Its
`fields` object edits title, language, tags, geography and evidence IDs; the
remaining file is the exact body, including ordinary front matter and line endings.
Keep the exported identity fields unchanged. Changed overlapping fields need an
explicit resolution. Unchanged or conflicting previews create no packet; inspect
`has_changes` and `ready` in the result. This is an explicit round trip, with no
new-record import, file watcher, deletion synchronization or automatic repinning.
`ingest` retains source evidence; it does not import authored dossier drafts.

### Keep a visual reference in a dossier

Choose **Add image**, select a local PNG/JPEG, describe it, and confirm retention
permission before saving. Caption, source title/URL, provenance note and section
are optional. Browser preview writes nothing; image capture and dossier revision
commit together or accept neither. A stale save requires refresh and review.
Saving a UTF-8 dossier body does not ingest its images: ordinary relative,
`file:` and HTTP(S) Markdown image paths are neither loaded as images nor retained.
Use **Add image**/`dossier-image` to capture and attach a local image, or reference
an already retained exact version with `lixity:image/SOURCE_ID/VERSION_ID`.

Earlier dossier revisions retain exact image versions. Withdrawn/purged/missing
images show unavailable placeholders. Source-page URLs are metadata, never fetched.
Click an image to enlarge it; Escape closes it. v0.7.1 uses a shared
PhotoSwipe zoom viewer for retained images and rendered diagrams. Images create no text passages,
linguistic scores, OCR or factual verification. Label generated/reconstructed
references in the caption and `context.provenance_note`; retain the actual source
of documentary photographs.

Limits are 16 MiB/image, 64 million pixels and 32 MiB for image-specific HTTP JSON.
Static PNG and supported 8-bit Huffman JPEG containers undergo signature,
structure and dimension checks, not full pixel decoding or authenticity checks.
Animated PNG, SVG and raw HTML images are unsupported; browser decoding can still
reject damaged pixels. Original bytes enter the ordinary audit/backup lifecycle.

For a joint capture/attachment, inspect the dossier and pass its exact tokens:

```sh
lixity research dossier inspect ID --project ./novel
lixity research dossier-image --project ./novel --dossier-id ID \
  --file ./reference.jpg --expected-snapshot DIGEST --expected-revision N \
  --allow-retention --alt "Describe the reference" --section "Location" \
  --context '{"provenance_note":"Generated visual reference; not a documentary photograph."}'
```

Omit `--section` to append. `--context` accepts a JSON object or local JSON-object
file. Ordinary `ingest --file reference.png --allow-retention` captures without
attachment. Python `ingest_image` does the same; `attach_dossier_image` requires
exact dossier snapshot/revision guards. Canonical destinations are
`lixity:image/SOURCE_ID/VERSION_ID` with UUID URNs. Purge identity metadata uses
record schema v2; unprovable older image associations remain missing.

### Review decisions and save related revisions together

**Review** lists structural candidates: dated/unlinked decisions, old pins and
withdrawn references. **Affected dossiers** shows explicit direct/claim-based
links, section outlines and pinned/current revisions. CLI equivalents are
`research decision-impact --decision-id ID` and `research review`.
These reports do not find every affected passage, infer contradictions, verify
history or rewrite documents. Old pins may be intentional; audit is separate.

Choose **Add to change set** in the editor, then **Review change set** to inspect,
edit or remove queued drafts and reasons before saving together. Failed/stale
saves preserve drafts for review. Drafts exist only in that browser tab and are
lost on reload. After an uncertain network result, inspect history before retrying.

```sh
lixity research revise-batch --project ./novel --file changes.json
lixity research revise-batch --project ./novel --file preview.json \
  --apply --expected-snapshot DIGEST
```

Input is an operations list or `research-revision-batch-local/1` preparation
envelope; each operation has `kind`, `id`, `expected_revision`, `changes`,
`change_kind` and `reason`. Preparation writes nothing. Apply validates all
operations before one commit; invalid inputs/races accept none. Duplicate IDs
and references to revisions created by that same batch fail. Existing evidence
and explicitly pinned references stay intact. A versioned preparation envelope
must match the selected project and its reviewed snapshot at application; a raw
operations list uses the explicitly supplied snapshot guard.

### Mark a decision as applied to a reviewed dossier

**Mark as applied** records your assessment for exact linked decision/dossier
revisions; **Needs another check** reopens the pair. Neither inspects prose nor
establishes semantic consistency. Later changes make the acknowledgement stale.
The UI updates your matching controls/counts after success; external changes
still require explicit refresh. Outdated pins/withdrawal warnings remain.

```sh
lixity research mark-applied --project ./novel --decision-id DECISION \
  --dossier-id DOSSIER --expected-snapshot DIGEST \
  --expected-decision-revision 2 --expected-dossier-revision 4
```

`reopen` takes the same guards; both accept `--note`. Stale/foreign targets write
nothing. Events form an explicit supersedes chain, not wall-clock ordering.
The first acknowledgement opts into record/manifest v5; accepted earlier bytes
remain intact. See [archive compatibility](#limits).

### Use local OCR without a worker service

Install Poppler, Tesseract and required language data on the server computer.
Select the backend in that service's environment and restart it:

```sh
export LIXITY_OCR_BACKEND=tesseract
export LIXITY_OCR_LANGUAGES=deu+eng
lixity research ocr-status --probe
```

Backends are `native`, `worker` or `tesseract`. When unset, a configured worker
wins, otherwise native Poppler is default. Explicit `worker_cmd`/`--worker-cmd`
wins over environment. Tesseract defaults to `eng`; requested languages must be
installed. Diagnostics report requested/available/missing data; nothing downloads
or starts automatically. Tesseract renders at 300 dpi with a bounded invocation
deadline; workers retain their 150 dpi protocol. Failures reject unless explicit
native fallback is allowed. A synthetic probe checks execution, not recognition.
New captures identify `tesseract-cli/1` or `poppler-native/1` and require storage
v4. Earlier cached provenance/bytes remain unchanged.

### Keep places and journeys in a dossier

**Since v0.7.0.** Use **Places and routes** in the existing dossier
editor to add named points, paths and areas, with descriptions, periods, actors
and transport choices. Import supported GeoJSON or enter coordinates in the form.
The [harbour example](examples/harbour-geography.json) contains deliberately
fictional positions and journeys. Field help, `research dossier --help` and
`research schema` describe the supported inputs; ordinary revisions and backups
retain them with the dossier.

Coordinates are finite WGS84 longitude/latitude pairs. **Since v0.7.1:** the
numbered sketch and interactive Leaflet vectors work offline. **Current main:**
maps open with OpenStreetMap. Turn off the background or choose the sketch for
offline use; tile requests disclose the viewed area and client IP to the provider
and stop outside the visible map/project context. There is no geocoding, road
routing, travel time calculation or historical verification. Attached map images
remain separate evidence, not georeferenced backgrounds; unknown geometry stays
unplaced.

Only a geographic save opts into record/manifest v8. Later revisions remain v8
even after removing geography; reading ordinary dossiers preserves their older
encoding. Older readers cannot open v8 archives. Section edits affect prose only,
not the dossier's geographic data.

**Current main, after v0.7.1:** select an object in the map or its list to read
its context and frame it. UI help and CLI `--format text` explain the measurements.
Response-only `geography_summary` (`research-geography-summary-local/1`) is
derived from the selected revision, separate from retained v8 records.

<a id="zotero-desktop-bridge-since-v1190"></a>
## Zotero Desktop bridge

Zotero owns the source library and its editable metadata, reading and notes.
Lixity retains explicitly selected evidence versions and authored project records;
these are stable captures, not a second synchronized library. Use **Open in Zotero**
to return to the source. Enable Zotero's **Settings → Advanced → Allow
other applications on this computer to communicate with Zotero**. No account,
cloud API key, plugin or additional Python dependency is required. The bridge
reads the local API and never writes Zotero's database or library.

```bash
# Preview pages; use the returned next_start as --start for further pages.
lixity research zotero --project ./novel --library users/0 --collections
lixity research zotero --project ./novel --library users/0 --query "history" --limit 20
# Replace illustrative keys and SERVER_ID with preview results.
lixity research zotero --project ./novel --library users/0 --collection-key ABCDEFGH
lixity research zotero --project ./novel --library users/0 --item-key ABCDEFGH
lixity research zotero-ingest --project ./novel --library users/0 --attachment-key JKLMNPQR --expected-server-id SERVER_ID --allow-retention --dry-run
lixity research zotero-ingest --project ./novel --library users/0 --attachment-key JKLMNPQR --expected-server-id SERVER_ID --allow-retention
lixity research reindex --project ./novel
```

Every call requires an explicit project and library. Use `users/0` for the local
user library or `groups/<numeric-id>` for a locally available group library.
Preview returns `research-zotero-local/1`, metadata and an instance `server_id`.
An item preview includes a page of attachments. Collections are paged in batches
of 100; item pages accept a limit of 1–100. `next_start` is a continuation hint,
not a total count; a final full page may lead to an empty page. External metadata
and notes remain untrusted evidence.

Capture selects one locally available PDF, UTF-8 text or Markdown attachment.
**Since v0.7.0,** capture also accepts PNG/JPEG through the existing image
pipeline; these visual sources have no text passages or OCR.
The existing ingestion pipeline retains stable bytes, the parent title and origin
URL. `provenance_note` records a bounded summary of creators, date, parent and
attachment versions. `context.external_reference` separately records provider,
server identity, library, parent/attachment keys and versions. This is not a
lossless bibliography export. Invalid URLs or overlong metadata fail without
publishing a capture. Language comes from the flag or project, not Zotero metadata.
Audio, video and unsupported attachments remain in Zotero. Image capture does
not interpret depicted places, extract map coordinates or establish authenticity.
Scanned PDFs require locally installed Tesseract or a configured OCR worker.
See [local OCR setup](#use-local-ocr-without-a-worker-service).

A repeated capture of the same instance/library/attachment finds its existing
active source. Identical bytes and context are a no-op, rather than a duplicate.
If the capture changed, explicitly pass its Lixity `--source-id` to refresh it.
The attachment identity must match; existing source criticism and tags are
preserved. Changed captures preserve earlier citations. A changed research
snapshot fails the operation instead of overwriting concurrent work. Titles and
languages retain the existing source-refresh restrictions. There is no automatic
background synchronization or content-based deduplication across different items.

Structured identity and safe refresh require the server identity provided by
Zotero 10 or later. An older client supporting the local endpoints may create
an unstructured CLI/Python capture, but safe refresh and identity deduplication
are unavailable. The browser requires a previewed server identity for capture.

The research dashboard lets users choose a library and collection, search items,
inspect attachments, open originals in Zotero and capture or refresh selected
eligible attachments after confirming retention. It marks captured attachments
and metadata-version changes. This indication is not a comparison of file bytes.

**Open in Zotero** uses the `zotero://` URL protocol: the Zotero installation
registers that handler for the desktop account, and the running or newly started
Zotero app selects the item. If a click has no effect, the protocol handler is
missing — for example with a manually installed or portable copy; update or
reinstall Zotero's desktop integration. This link is independent of the local API.
When every active source has a structured external reference, the dashboard hides
the separate local-import form. Native CLI/API import remains available for
standalone projects and recovery; retained evidence history is not removed.

The bridge uses GET requests to `127.0.0.1:23119`, with a 10-second socket timeout,
bounded responses, no proxies or redirects. Files must resolve to local regular
files; download cloud-only attachments in Zotero first. Dry runs require retention
consent and validate/extract input, but leave the research store unchanged.
Temporary capture files are removed afterward. Do not grant retention merely
because a file is visible in Zotero: visibility is not redistribution permission.

Python entrypoints are `lixity.research.zotero.collections`, `.browse` and
`.ingest`, with explicit `project` and `library` arguments. They are independent
of manuscript analysis. Standard research export includes retained captures and
provenance, not the external library. Use the paired backup below for both stores.

<a id="literature-acquisition-workflow-url--zotero-reference--attachment--evidence"></a>
### Literature acquisition

A saved reference is metadata, not a retained PDF. Download an attachment in
Zotero, inspect it with `research zotero --item-key ITEM_KEY`, then capture the
selected attachment with the preview's server identity and retention permission.
`zotero-ingest --item-key ITEM_KEY` captures eligible attachments as a
batch. Finally search the retained passages and cite/link the one you reviewed.
Each step has a distinct result; a catalogue entry alone supplies no evidence.

### Additive migration to Zotero

```sh
lixity research zotero-export --project ./novel --output ./zotero-import --allow-retention --dry-run
lixity research zotero-export --project ./novel --output ./zotero-import --allow-retention
```

The destination must not exist. Export produces `library.ris`, `files/` and
`migration.json` (`research-zotero-export-local/1`). It selects the newest active
capture for each active source; withdrawn sources/captures are excluded. Original
bytes, source IDs, context and SHA-256 hashes are retained in the bundle. RIS
contains title, language, tags, origin URL and provenance notes, with an explicit
`lixity-source:<UUID>` tag and attachment file URI. Keep the reviewed bundle at
its exported location while importing RIS: attachment URIs are absolute.

Import `library.ris` through Zotero's import workflow and check its attachments.
This is additive: it neither deletes old Lixity evidence nor reconciles duplicate
Zotero imports. To bind an existing Lixity source, run `zotero-ingest` with its
`--source-id` and the imported attachment key. The parent must retain the exported
migration tag and the attachment bytes must exactly match the current capture.
Binding updates capture provenance while preserving source IDs and older citations.
A filename, title or similar text is never enough to establish this identity.

Before retiring duplicate workflows, compare active source counts and bindings,
audit the research archive, resolve representative old citations, and verify a
paired restore. A successful export is not proof that a project's migration has
finished. Preserve the pre-migration backup until restoration has been tested.

### Paired Zotero/research backup and restore

<a id="backup-scope-comparison"></a>

Close Zotero before starting; `--confirm-zotero-closed` is the caller's explicit
confirmation, not automatic process detection. Specify the **data directory**
containing `zotero.sqlite`, not the application profile.

```sh
lixity research zotero-backup --project ./novel --data-dir /path/to/Zotero --output ./paired-backup --confirm-zotero-closed
lixity research zotero-restore --from ./paired-backup --to ./restored-pair
lixity research audit --project ./restored-pair/project
lixity research reindex --project ./restored-pair/project
```

Both destinations must be new; existing directories are never overwritten.
The bundle contains `research.tar.gz`, a copy of the Zotero data directory, and
`BACKUP.json` (`research-zotero-backup-local/1`) with SHA-256 checksums and sizes.
Backup audits research and checks that Zotero files remain unchanged during
copying. Restore checks the complete inventory, checksums and research archive
before publishing `project/` and `zotero/` beneath the new destination. It does
not switch a running Zotero instance or restart Lixity.

Symlinks and special files are rejected; the paired inventory is limited to
10 GiB. External linked attachments, manuscripts and application profiles are
excluded. Use Zotero stored attachments for self-contained media backup, and
back up excluded project material separately. Verify restored Zotero data in a
separate instance before adopting it; byte verification alone does not establish
application-level usability or that an external attachment was included.

## Try it

Install using the [installation guide](../INSTALLATION.md#cli-current-release)
or a development checkout (`make install-dev`). SQLite must include FTS5;
PDF extraction has the [separate prerequisites](#native-pdfs-versus-scans).
Prepare authorized `notes.txt` and an authored `notes.md` before these commands;
the latter is dossier content, not a second source capture.

```sh
lixity research init --project ./novel --title "Novel research" --language en
lixity research ingest --project ./novel --file ./notes.txt --allow-retention --dry-run
lixity research ingest --project ./novel --file ./notes.txt --allow-retention
lixity research search --project ./novel --query "reading room"
lixity research cite --project ./novel --passage PASSAGE_ID
lixity research dossier --project ./novel --title "Reading room" --file ./notes.md --evidence PASSAGE_ID
lixity research audit --project ./novel
```

Replace `PASSAGE_ID` with a full returned ID. Open the project from the managed
app, or run `lixity serve --research-project ./novel --no-project` in the foreground.
Commands do not switch a running server's project. [Project onboarding](../ONBOARDING.md)
explains the existing-project and new-import paths.

Search selects current captures; old passage IDs still cite original bytes.
Refreshing unchanged bytes/context is a no-op. Native ingestion without
`--source-id` creates a distinct source; identical text does not prove identity.
Zotero uses its structured external identity instead.

`--allow-retention` permits a local copy, not redistribution or factual acceptance.
Passages stay `unreviewed`; evidence relations and author-selected claim states
require human assessment. Decisions are separate authorial records. An unmarked
`deviation_from_fact` does not certify factual accuracy. Exit codes are `0`
success, `1` operational/integrity failure and `2` usage error. Failed audits emit
`ok: false` and exit `1`; other errors use stderr without source contents.

<a id="search-current-authored-records-since-v1190"></a>

## Search current authored records

The default CLI/Python/HTTP search still searches source passages and returns
`research-search-local/1`. Select `--scope all`, `dossiers`, `claims` or
`decisions` to include current authored records with a typed
`research-search-local/2` response:

```sh
lixity research reindex --project ./novel
lixity research search --project ./novel --query "inspector" --scope all
lixity research search --project ./novel --query "inspector" --scope decisions
```

Python: `api.search("./novel", "inspector", scope="all")`.
HTTP: `POST /api/research-search` with `{"query":"inspector","scope":"all"}`.
The dashboard defaults to **All records** and offers the same type filters.
Its details button opens the existing record history with the current revision.

Source hits have `kind: "passage"` and retain their citation fields. Authored
hits have `kind`, `record_id`, `revision`, `title` and a plain-text `excerpt`;
they have no `passage_id` and cannot be used as source citations. Claim hits
include the author-selected `confidence`; decision hits include
`deviation_from_fact`. A match does not make a claim verified or a proposal final.

The shared disposable FTS5 catalogue indexes current dossier bodies/tags, claim
statements/tags/scope, decision rationales/plot impact, and their titles. It does
not index revision history or revision reasons. `all` also indexes source titles
and current source passages. Titles receive extra ranking weight; scores are
lexical relevance, not authority. Query words must all occur in one record;
there is no semantic search, identity resolution or automatic contradiction
resolution. The result limit applies across all matching types. Use type filters
when numerous source hits obscure authored records.

CLI search automatically refreshes stale or missing indexes by default to avoid
interrupting research tasks with manual maintenance detours. Callers who require
strict validation can pass `--strict` to fail fast when the index is not up to date.
When a query produces zero passage hits under the default `sources` scope, the
response warnings suggest trying `--scope all` to search authored records.

### Batch ingestion and non-interactive progress

- **Batch ingest**: Pass multiple files to `lixity research ingest --project ./p --file a.pdf b.txt --allow-retention`.
  It returns `research-batch-ingest-local/1` detailing per-item outcomes (`succeeded`, `failed`, `items`), ensuring
  partial batch success is preserved even if one file fails validation.
- **Progress reporting**: Add `--progress` to `ingest` or `zotero-ingest`. Phase notifications with elapsed
  seconds are streamed to `stderr`, keeping `stdout` strictly machine-readable JSON.
  These are phase-boundary notifications, not periodic heartbeats, JSONL events
  or a per-page stream during worker inference.

<a id="section-bounded-dossier-inspection-and-revision"></a>
For bounded dossier reads/edits use the [section workflow](#work-on-one-dossier-section).

### Claim-evidence matrix export

`research matrix --format md|csv|json` connects claims, evidence, dossiers and
decisions. The dashboard and HTTP export use the same report. Support counts
summarize authored links, and `deviation_from_fact` records an author's explicit
choice; neither is a factual truth score.

## Python API

```python
from lixity.research import api

api.init("./novel", title="Novel research", language="en")
capture = api.ingest("./novel", "notes.txt", allow_retention=True)
results = api.search("./novel", "reading room", limit=5)
# Inspect a returned passage before using api.cite or linking it to a claim.
```

The project argument is mandatory; research discovers no manuscript and reads no
analysis thresholds. `lixity build` neither imports sources nor refreshes research
indexes. The [automation reference](../AGENTS.md#51-research-api-lixityresearchapi)
covers public entrypoints and envelopes.

Source analysis uses the shared engine, selected archived version/language and
explicit overrides. Its interpretation is `source_internal`, with
`context_status: user_supplied_unverified`; manuscript settings are not inherited.
Period, place, genre, translation and language context do not validate a source or
make it a manuscript style baseline. Local title/tag filters search only loaded
metadata; use archive search for retained text.

## Native editing and history

In the dashboard, choose **Edit** on a dossier, claim, evidence link or decision.
Change the fields, select **Correction** for a transcription/wording correction
or **Supersession** for a changed interpretation or authorial choice, and give
a reason. Save keeps the record's ID and adds one immutable revision. **History**
opens earlier accepted versions; it does not restore or overwrite them.

Existing associations retain their saved pins; new associations use the target's
current revision. To associate evidence with a revised claim/dossier, explicitly
change that pin in the editor. Old associations remain inspectable in history;
editing a statement does not turn its old evidence into support for the new wording.

The editor preserves failed drafts. Any archive write after opening makes its
snapshot stale. Use [three-way review](#resolve-conflicting-drafts), or **Reload
current** to discard the draft explicitly; Cancel closes without writing.

Use the [ordinary update workflow](#update-one-reviewed-record) to inspect or
revise through the CLI. Omitted fields stay unchanged; explicit empty optional
values/lists clear them. The [automation reference](../AGENTS.md#51-research-api-lixityresearchapi)
owns Python/HTTP payloads and versioned envelopes.

Source refresh never rewrites authored records. Newer-capture notices compare
explicit citations with the latest capture while preserving the original quote.
Copied text, titles and filenames do not establish source associations.

Historical dossier and evidence-link views resolve their pinned passages.
Claim and decision views show the current evidence links to their pinned claim
revision, with each link's ID and revision; they are not a reconstruction of the
entire archive at an earlier date.

## Storage, lifecycle and recovery

- `research/project.json`: immutable initial project configuration.
- `research/revisions/`: immutable, schema-checked records.
- `research/blobs/`: SHA-256-addressed original source bytes and extracted text; originals are not normalized.
- `research/manifests/`: complete snapshots; `research/HEAD.json` selects one.
- `.lixity/research/`: disposable catalogue and writer lock.

### Withdrawal vs. purge

- **Withdrawal (`withdraw`)**: Preserves the audit trail and archived source text,
  records a tombstone in the manifest, excludes the source or version from default
  search, and marks existing citations as `availability: "withdrawn"`. Analysis
  fails closed for withdrawn sources.
- **Purge (`purge`)**: Permanently removes source records, extraction records,
  and passage records from the store and unlinks unshared original blobs. Citations
  for purged passages fail closed with `ResearchError`. Supports `--dry-run` to preview
  affected records and blobs before deletion. Authored dossiers and evidence
  links remain for their audit trail, but their purged citations are marked
  `availability: "purged"` and expose no deleted quotation text.

**Since v0.7.1:** `withdraw` also retires a dossier through the same
tombstone mechanism. Inspect its revision and snapshot, preview, then repeat the
command without `--dry-run` to accept the retirement:

```sh
lixity research dossier inspect DOSSIER_ID --project ./novel
lixity research withdraw --project ./novel --dossier-id DOSSIER_ID \
  --expected-revision REVISION --expected-snapshot SNAPSHOT \
  --reason "Consolidated into the reviewed dossier" --dry-run
```

Both guards must still match when saving. The dossier disappears from active
lists and search; its bytes, evidence, associations and backups remain. Explicit
revision reads, history and saved-revision comparisons remain available and
identify the withdrawal. Current reads, edits, new associations/repins, image
attachments and fresh acknowledgements reject retired dossiers. Existing pins
survive unrelated revisions of linked records.

`supersession` describes an ordinary revision's intent; it does not retire a
dossier. Retirement does not create a replacement link or merge records. Source
withdrawal and purge keep their existing contracts.

### Cross-corpus comparison and evidence grounding

`compare` requires an explicit source and manuscript, or the deliberate Grounding
action for the loaded manuscript. It returns a separate report without modifying
either text or recalibrating fingerprints. It measures lexical Jaccard/overlap,
shared/exclusive terms, signed full $2\times2$ Dunning $G^2$ keyness, register
contrasts and per-chapter occurrences per 1,000 words. Grounding means vocabulary
occurrence, not entailment, validated chronology or factual support. Term-list
limits affect reported rows, not the comparison's meaning.

```sh
lixity research compare --project ./novel --source-id SOURCE_ID \
  --manuscript ./novel.md --format md --output ./grounding-report.md
```

Counts share core prose scope: body paragraphs, lists and blockquotes, excluding
code/comments/footnote definitions. With chapters, headings/front matter/appendix
are excluded; otherwise remaining document prose is used. Comparison uses code-
default parsing, source language and the explicit manuscript language (English by
default); it does not inherit custom project `chapter_regex`/`appendix_marker`.
Inspect the chapter trace before comparing with a differently configured dashboard.

Cross-language comparisons retain numbers but set `meta.lexical_comparable: false`
and `cross_language_lexical_comparison` in `comparison_limits`; do not read lexical
scores as comparable coverage. Guiraud/register contrasts depend on length,
language and discourse mode. Matching a source is not a writing-quality objective.

Back up the entire `research/` directory, preferably without active writers.
Restore to an explicit root, audit, then reindex. SQLite alone is insufficient;
blobs and passage records contain private source text.

## Export and restoration

```sh
lixity research export --project ./novel --output ./backup-novel.tar.gz
lixity research restore --from ./backup-novel.tar.gz --to ./restored-novel
lixity research audit --project ./restored-novel
lixity research reindex --project ./restored-novel
```

Export packages accepted records/history, manifests, original blobs and project
configuration. `EXPORT_MANIFEST.json` records SHA-256 and byte lengths. Search
indexes and locks are excluded. Restore refuses an existing store or nonempty
project destination, validates safe regular-file paths, checksums/sizes, snapshots,
contiguous history and project identities, then publishes atomically. Symlinks,
devices, absolute paths and traversal fail. This backup excludes manuscripts,
Zotero and application profiles; [paired backup](#paired-zoteroresearch-backup-and-restore)
adds the Zotero data directory.

Writes use an OS lock, immutable publication and atomic HEAD replacement.
Uncommitted objects left after interruption are ignored, not selected by date.
Locks release when the process exits. A stale expected HEAD fails rather than
overwriting another ingestion. Interrupted initialization may leave an incomplete
directory: preserve it for inspection; `init` refuses to overwrite it.
Writer diagnostics distinguish a busy writer from read-only, permission and
other I/O failures at the canonical project lock. A lock file's existence does
not prove contention; no alternate `/tmp` lock or unlocked fallback is used.

Files are flushed before publication; directory syncing is used on POSIX.
If an interrupted authored edit leaves a valid next-revision file outside the
accepted snapshot, the next save preserves its bytes under a content-addressed
`.unpublished` filename in that revision directory before retrying. It is a
recovery artifact, not an accepted revision or an automatic merge. Accepted
history is never replaced; malformed or foreign files stop the save.
## Origin URL and capture provenance

Optional `--origin-url` / `origin_url=` is retained as
`SourceVersion.context.origin_url`, independently of title, tags and
`provenance_note`. Source details, lists and citation context expose it.
Refreshing identical PDF bytes verifies and reuses retained original/extracted
blobs and passage spans. Metadata-only changes create a new capture without
rerunning OCR; identical bytes/context remain a no-op. Earlier citations keep
their original capture.

```sh
lixity research ingest --project ./novel --file ./notes.txt --allow-retention \
  --origin-url https://example.org/archive/notes
```

The URL must be absolute HTTP(S), at most 2,000 characters, without credentials,
whitespace or control characters. It is stored as submitted, never requested or
used to accept a claim. Prefer stable source addresses over signed links with
private query tokens. The browser displays it as escaped text. Failed validation
keeps the draft; successful import clears the field with the rest of the form.

On refresh, an omitted `origin_url` retains the context selected by the existing
API: supplied `context`, or the latest capture's context when omitted. An explicit
URL overrides `context.origin_url`. Changing only the URL creates a new capture;
identical bytes and context remain a no-op. To clear a URL deliberately, supply a
context mapping with `origin_url: null` (and any other metadata to retain).
Earlier citations resolve their own capture and retain the original URL. URLs,
filenames and titles never establish source identity automatically.

URL-bearing captures require schema v2, or v3 when carrying structured Zotero
identity. Capture sequence is distinct from authored-record revision history.
Earlier URL-free records retain their encoding. See [compatibility](#limits).

## Self-hosted PDF and OCR extraction

PDF ingestion retains the original PDF bytes and extracted UTF-8 text as
separate content-addressed blobs:

```sh
lixity research ingest --project ./novel --file ./document.pdf --allow-retention
```

The browser file input also accepts binary PDFs. It reads the selected file as base64 for transport and passes the decoded
bytes through the same import API as text and server-local files. The browser
shows reading/extraction/completion states and prevents duplicate submits while
waiting. This is not a streamed per-page progress feed.
Successful local and Zotero captures also show returned warnings in the import
status. Read those messages; a successful capture is not proof of OCR accuracy.

### Native PDFs versus scans

Install local Poppler tools: `poppler-utils` on Debian/Ubuntu, or `poppler` with
Homebrew. Both `pdftotext` and `pdftoppm` must be visible on the server's PATH.
`pdftoppm` rasterizes physical pages at 150 dpi for native/worker extraction
and 300 dpi for Tesseract; `pdftotext` extracts text layers.
Without page rasterization, the configured scan worker cannot receive normal
page inputs. Native text extraction may still work when the page count can be
determined; `partial` does not indicate a complete OCR setup.

An image-only scan has no usable text layer. Select
[local Tesseract](#use-local-ocr-without-a-worker-service) or a configured
self-hosted worker; Lixity does not install their engines, language data or
models. Run diagnostics in the same environment as the server:

```sh
lixity research ocr-status [--worker-cmd PATH] [--probe]
```

`--probe` (HTTP `?probe=1`) executes a synthetic worker/Tesseract request and
reports execution/latency; native mode has no worker to probe. Success upgrades
only `ready` to `ready (probed)`, never invalid configuration or `partial`.
Inspect `probe.ok` and configuration/dependencies together: the diagnostic CLI
exits `0` even when a probe fails.

The same information is available at `GET /api/research/ocr-status` and in
`GET /api/research/status`. The dashboard maps these codes to localized labels:

| Code | Configuration detected | Action |
| --- | --- | --- |
| `ready` / `ready (probed)` | Selected worker or Tesseract with requested language data, plus pdftoppm | Test an authorized scan and inspect extracted text |
| `native_only` | Native extraction with both Poppler tools | Native PDFs work; select Tesseract or a worker for scans |
| `partial` | Extraction/OCR engine available, pdftoppm missing | Install the rasterizer before multi-page use |
| `misconfigured_worker` | Worker absent/not executable, invalid timeout, or failed probe | Check worker path, permissions, service environment and `LIXITY_OCR_TIMEOUT` |
| `misconfigured_backend` | Invalid backend/native timeout, or unavailable Tesseract/language data | Check `LIXITY_OCR_BACKEND`, `LIXITY_OCR_LANGUAGES`, timeout and local installation |
| `missing_dependencies` | No complete usable setup | Install Poppler and select a scan backend when needed |

Diagnostics establish executable availability; a probe establishes only that
request's execution. Neither verifies model weights, GPU resources or recognition
accuracy. Worker model/recipe identifiers are requested constants, not attestations.

Native extraction refuses an undeterminable page count. If Poppler's `pdfinfo` is
absent and the page tree is not readable in the raw file -- typically because a
modern producer stored it in a compressed object stream -- the capture is
refused with an explicit error rather than silently retaining only the first
page. Install Poppler or configure `LIXITY_OCR_WORKER` to ingest such a file.

Pass `--fallback` (or set `LIXITY_OCR_FALLBACK=1`) to permit native `pdftotext`
extraction if worker execution fails/times out or Tesseract extraction fails.
The result records a warning; review mixed/scanned pages for missing text.
Without explicit fallback, these failures reject the capture.

### Worker interface

Read [Unlimited-OCR integration and deployment boundaries](OCR_INTEGRATION.md)
before provisioning inference. Baidu's official entrypoints do not implement
this custom worker protocol; a separate adapter is required.

Set `LIXITY_OCR_WORKER` to one executable path or a command name on PATH. It is
invoked directly as `[worker, request_file]`, without shell parsing or embedded
arguments. Use an absolute path without `~` for portable service configuration.
`LIXITY_OCR_TIMEOUT` sets the worker subprocess deadline in seconds: an integer
from 1 to 3600, default 120. This is a total invocation deadline, not per page.
Set the variable in the service's environment and restart the server; exporting
it in another terminal does not update an existing process.

The temporary request JSON contains:

```json
{
  "model_snapshot": "<requested model snapshot>",
  "recipe_revision": "<requested recipe revision>",
  "pdf_path": "/absolute/path/to/input.pdf",
  "pages": [{"page_number": 1, "sha256": "<rendered PNG SHA-256>"}]
}
```

The [deployment reference](OCR_INTEGRATION.md) records the integration pins.
The worker provisions its own runtime/models; request identifiers do not attest
that an executable used those weights.
The request includes PDF access and page checksums, not image paths or image
bytes. A worker that needs raster images must obtain them from the local PDF.

Return JSON on stdout; send logs to stderr:

```json
{"blocks": [{"page_number": 1, "text": "Synthetic reading room note."}], "warnings": []}
```

Worker responses are validated before accepting a capture.
Every block needs a nonempty string `text` and an integer `page_number` from the
rendered request pages; at most 5,000 blocks are accepted. Optional `box` contains
four finite numbers. Optional `confidence` must be a finite number from 0 to 1;
omission or `null` means **unknown**, never an implicit score of 1.0. A supplied
score is worker-reported, not an independently calibrated accuracy estimate.

Every requested page must be covered by a block or listed in optional
`completed_pages`. Use that integer list for pages successfully inspected with
no readable text, such as a blank page; never use it to conceal a failed page.
For example, a two-page document with a blank second page may return:

```json
{"blocks": [{"page_number": 1, "text": "Synthetic note."}], "completed_pages": [2], "warnings": []}
```

Warnings, when supplied, must be a list of strings. Blocks are ordered by page
number while retaining their supplied order within each page; their trimmed text
is joined with blank lines. Coverage validates what the worker reports, not
whether it recognized every word. A completely textless document still cannot
be ingested as a searchable source.

A configured worker's nonzero exit or timeout fails the import by default;
explicit `--fallback` / `LIXITY_OCR_FALLBACK` can permit native text extraction
with a warning. Invalid block structure or missing reported page coverage still
fails closed. There is no silent native-text fallback. With no backend or worker configured, native
text-layer extraction remains available and can omit scanned pages; inspect mixed
PDFs for completeness. A successful native import is not an OCR-success claim.

For local scans, use the built-in Tesseract backend described above. Custom model
deployment belongs to a separately maintained adapter implementing this worker
protocol. The former experimental CPU bridge was removed in 2.1.0; its limited
experiment is recorded in [deployment boundaries](OCR_INTEGRATION.md#historical-cpu-experiment).

### What is actually retained

`SourceVersion.blob` identifies original PDF bytes; `Extraction.text_blob` holds
extracted UTF-8. Passages cite exact character spans in that text. Page images,
boxes, confidence and runtime warnings are not retained as audited coordinate or
accuracy records, nor is there an attestation of which model ran.

`research-ingest-local/1` returns `warnings: list[str]` for committed, preview
and unchanged results. Successful local/Zotero batch items preserve them. Clean
or reused extraction returns `[]`; an unchanged response does not recover earlier
warnings. Save needed operational diagnostics separately and verify quotations
against the original scan. Core import is local; a configured worker's network
behavior belongs to its deployment's privacy boundary.

## Safe Markdown and offline diagram rendering

Dossier bodies support headings, emphasis, quotations, lists, code and tables;
raw HTML stays escaped. **Since v0.7.1:** bundled Mermaid tiny 12.2.0
renders supported `mermaid` fences offline instead of the former partial renderer.
The library initializes when a diagram first becomes visible. Image/resource
syntax, click actions and configuration/style directives are disabled; unsupported
or invalid diagrams keep their inspectable source. Rendered SVGs share the local
PhotoSwipe 5.4.4 zoom viewer with images. Neither renderer loads a CDN or uploads
the diagram; map tiles have the separate network boundary above.

**Current main, after v0.7.1:** a small diagram uses a compact frame. Wide diagrams
keep their label size and scroll horizontally within the reader; focus the
viewport and use the arrow keys, or choose **Enlarge diagram**. The source remains
available below it. The renderer preserves the direction and relationships in
your Mermaid source; visual proximity does not establish evidence or causality.

## Limits

Research uses operation-specific `*-local/N` response envelopes and versioned
records/manifests, independently of the product version. It does not implement
the RFC's illustrative `research/1` bundle. Unknown fields/versions fail closed.
Check installed support with `lixity about --json` and entity contracts with
`lixity research schema`.

| First accepted write | Required record/manifest version |
| --- | --- |
| Authored revision or origin URL | v2 |
| Structured Zotero capture | v3 |
| New Poppler/Tesseract provenance | v4 |
| Decision acknowledgement | v5 |
| Causal claim relation | v6 |
| Manuscript quote association | v7 |
| Dossier geography (since v0.7.0) | v8 |

Reading alone does not upgrade archives or rewrite old record bytes. Back up
the complete store before opting in; use compatible readers/writers afterward.
Historical v3.0.1 supports through v6, v0.6.0 through v7, and v0.7.0/v0.7.1 through v8.
Older readers cannot open v8 archives.
Rollback requires the complete pre-upgrade backup, never editing HEAD, schema
labels or provenance by hand. Source identity metadata cannot be edited in place;
refresh creates a new capture.

The 25,000-entry snapshot limit includes retained revisions. Status counts show
current logical records; the audit's `records` count includes their history.

Text inputs are at most 2 MiB and must be valid UTF-8 without NUL bytes.
PDF inputs are at most 50 MiB. Both routes allow at most 5,000 nonempty extracted
passages. Search uses literal Unicode words joined with AND; it is
not stemming, translation or semantic search. BM25 scores are ranks, not truth
probabilities. Language tags do not translate quotations. Empty queries and missing FTS5 support produce errors. Stale indexes refresh
automatically unless strict validation is requested.
Source analysis emits `original_language_supplied` when source context names
an original language; that free-text field alone does not establish historical
language variety. This replaces the earlier experimental
`historical_language` limitation code.

Audits check retained records, hashes and citations, not factual accuracy,
permissions or historical completeness. A citation's `availability` indicates
whether its source is currently available or withdrawn; a purged passage no
longer resolves. The web panel displays those evidence states for linked
passages.
The [licensing rules](../LICENSING.md) still apply; imported sources keep
their own rights.
