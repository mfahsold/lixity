# One project, three reading websites

[*The Crate at Warehouse 4*](report.html) is the shared product walkthrough.
Its six synthetic English chapters come from
[`samples/first-look.md`](../../samples/first-look.md); the published
[manuscript](../research/examples/harbour-manuscript.md) contains identical bytes.
Analysis, research, screenshots and PDF layouts use that same project.

Two curated examples use the same production export and manuscript:

- [Read with context](reader/index.html) combines the six chapters with selected
  dossier passages, diagrams and images, plus an explicitly selected chapter
  analysis. Use **Analysis** from the reading page and **Back to reading copy**
  to return. The internal research archive is not included.
- [Companion only](companion/index.html) presents that context without novel or
  analysis bytes. This example is capped at chapter 3: later entries and their
  resources are omitted before the website is assembled.

Both start with no chapters marked as read. **Finished reading through** reveals
the author's selected notes for that progress; **Open later notes** temporarily
previews later material within the exported range. Progress stays in the local
browser. Hiding notes is a reading aid, not content protection: a chapter cap
must omit later material from the export itself.

Start with chapter 1's setting and chapter 2's action, then choose **Research →
Dossiers → View details** on **Warehouse 4 case notes**. **Dossier alongside**
opens its reading companion. In **Review**, follow the eastern-gate quote
through **Linked version** to its pinned claim, dossier and source references, or use
**Go to manuscript passage** to read the quote. Starting from a manuscript
paragraph's association preserves an origin: close the record viewer and
choose **Back to passage** to return there. This author-workspace demo uses the
production review-mode website export: titles open current entries, explicit
linked-version controls retain older pins, and **Versions** expands the history
without switching the displayed entry.
The case notes connect six claims, three decisions and five exact manuscript
quotations. Explore conflicting inspection accounts, a qualified witness report,
an authored cause/effect link and a corrected claim whose earlier manuscript
links remain pinned. The timeline, diagrams, map and images provide different
ways into the same two dossiers.
Historical map/photo sources have
[reviewed credits and file hashes](../assets/research/sources.json). People,
customs records, incidents and journeys are invented; the visuals do not verify
them, and coordinates are not georeferenced to the map image.

## Public artifacts

- `report.html`: the production `prepare_site` export with native manuscript
  and research views, an inline prepared-read snapshot and reviewed visual assets.
  There is no live Zotero connection or access to a user's running service.
- `manifest.json`: exact artifact inventory, hashes, source snapshot and
  disclosure scope for `report.html`; source files have digest-based names in
  `assets/sources/`.
- `reader/` and `companion/`: the curated reading websites, each with its own
  manifest, selected resources and license notices.
- `research.html`: compatibility entry to `report.html#research-manager`.
- The same six chapters as an [editorial copy](warehouse-4-editor.pdf),
  [reading copy](warehouse-4-book.pdf), [submission sheets](warehouse-4-sheet.pdf)
  and [analysis report](warehouse-4-report.pdf).

The author-workspace demo supports exploring manuscript analysis, retained
research, a dossier alongside the manuscript, prepared PDF downloads and a
claim-evidence matrix.
Editing, project administration, archive Search and Compare are unavailable in
the reading copy. Manuscript search and research list filters remain available.
At the top of the demo, **Read the manuscript** and **Explore research** switch
the native workspace views; both use the same prepared, read-only project
snapshot.
The demo cannot import or save; generating new analysis or PDFs requires the
[local app](../guides/installation.html).

The published documentation and author-workspace demo use the configured
GoatCounter counter for page paths and named links. A PDF event records activation of a prepared-file
link, not a completed filesystem save. The public-only wrapper includes explicit
reviewed analytics configuration and a matching content policy. The production
snapshot transport has no analytics exceptions or write routes. Local application
views, the two curated examples and ordinary exported reading websites carry no
counter. See the [website measurement notice](../index.html#website-measurement).

The generating version, provenance notice and unchanged distribution-license
appendix stay outside the analyzed manuscript. The short text is a demonstration,
not a calibration corpus, benchmark or literary-quality score. Public pages use
only reviewed synthetic/public-domain material and explicit code defaults.

## Regenerate

After [installation](../INSTALLATION.md), use `make examples` for the three
websites and PDFs, `make screenshots` for product captures, and `make videos`
for walkthroughs.
These entrypoints reuse the existing analysis, research and PDF APIs. Fontane
and Austen outputs under `examples/` remain named literary case studies linked
from the relevant articles; they are not alternative demo projects.

Review the output and run `make docs-check` plus the public-documentation browser
check in [`tests/browser/README.md`](../../tests/browser/README.md). The explicit
Pages boundary includes the three website bundles and their verified manifests,
the compatibility entry, four PDFs and reviewed visual assets. Source archives,
private manuscripts, credentials and local build state remain excluded.
