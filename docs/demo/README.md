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
  to return. **Chapter audio** plays the reviewed first-chapter recording made
  with the generic eSpeak NG English voice.
- [Companion only](companion/index.html) presents that context without novel or
  analysis bytes. This example is capped at chapter 3: later entries and their
  resources are omitted before the website is assembled.

Both start with no chapters marked as read. **Finished reading through** reveals
the author's selected notes for that progress; **Open later notes** temporarily
previews later material within the exported range. Progress stays in the local
browser. Hiding notes is a reading aid, not content protection: a chapter cap
must omit later material from the export itself.

Start with **Try the draft examples → Check a sticky sentence**. Choose
**Paragraph details → Explain this passage** to see the 22 function words
within 31 counted words and read them in context. Then try **Compare chapters 1
and 2** to compare average sentence length across scenes.
[First-look walkthrough](../guides/first-look.html#passage)

The manuscript is a deliberately rough draft. Open **Try the draft examples**
for direct links to a wordy sentence in **The Blank Line**, a past-to-present
tense slip in **Morning Handover**, and a phrase repeated by three speakers in
**Questions on the Quay**. That chapter also includes a long reply. Compare
the tags and the quoted words, then check how the customs note uses passive
phrasing for a different purpose. The highlights give you a passage to review
and a reason for looking there.

Choose **Research →
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
ways into the same case notes.
Historical map/photo sources have
[reviewed credits and file hashes](../assets/research/sources.json). People,
customs records, incidents and journeys are invented; the visuals do not verify
them, and coordinates are not georeferenced to the map image.

Open **Character: Mara** in Dossiers to see the saved chapter table and read
her appearances in context. Download [the same dossier version](warehouse-4-dossier.pdf)
from **Download this project**. The PDF includes the saved excerpts and a
pinned witness quotation from the fictional archive.

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
  [reading copy](warehouse-4-book.pdf), [submission sheets](warehouse-4-sheet.pdf),
  [analysis report](warehouse-4-report.pdf) and [plain A4 document](warehouse-4-document.pdf).
- [Mara’s dossier PDF](warehouse-4-dossier.pdf) with the saved character review
  and pinned source quotation shown in the product tour.

The author-workspace demo supports exploring manuscript analysis, retained
research, a dossier alongside the manuscript, prepared PDF downloads and a
claim-evidence matrix. Use manuscript search and research list filters to
find passages and records in the prepared snapshot.
Use **Manuscript** and **Research** to switch workspace views. Both use the same
prepared, read-only project snapshot.
Use the local app to import a project, edit, search or compare the full research
archive, or generate new analysis and PDFs.
[Installation guide](../guides/installation.html)

The published documentation and author-workspace demo use the configured
GoatCounter counter for page paths and named links. A PDF event records a click
on a prepared-file link, not a completed save to disk. The public-only wrapper includes explicit
reviewed analytics configuration and a matching content policy. The production
snapshot transport has no analytics exceptions or write routes. Local application
views, the two curated examples and ordinary exported reading websites carry no
counter. See the [website measurement notice](../index.html#website-measurement).

The generating version, provenance notice and unchanged distribution-license
appendix stay outside the analyzed manuscript. The short text is a demonstration,
not a calibration corpus, benchmark or literary-quality score. Public pages use
only reviewed synthetic/public-domain material and explicit code defaults.

## Regenerate

### Open the synthetic project locally

Create an editable copy from a source checkout with the demo fixture builder.

```sh
.venv/bin/python scripts/example_project.py --output .artifacts/warehouse-4-project
.venv/bin/lixity project --project .artifacts/warehouse-4-project
```

The destination must not exist; the command never replaces an existing project.
Open that folder through **Open Project** in the local app. It contains
`lixity.toml`, the six-chapter manuscript, retained research, immutable revisions,
manuscript associations and the `readers` publication profile. It uses the normal
project layout, not a separate demo file format. Keep personal edits in your own
copy; public regeneration continues to use the reviewed synthetic inputs.

For an unwrapped local analysis/research website, use the regular export command:

```sh
.venv/bin/lixity export-site --project .artifacts/warehouse-4-project --include-research -o .artifacts/warehouse-4-review
```

[`scripts/example_project.py`](../../scripts/example_project.py) creates the
editable project and owns its checked source inputs.
[`scripts/build_examples.py`](../../scripts/build_examples.py) creates a
disposable copy, adds Mara’s reviewed dossier version and calls the production
exporter through [`scripts/example_publications.py`](../../scripts/example_publications.py).
The [screenshot adapter](../../scripts/make_screenshots.py) also starts from the
shared fixture and adds the HTTP responses used for capture.

The public build checks the synthetic manuscript bytes and reviewed assets.
Keep local changes in the editable copy and use the normal export path for
projects you have permission to share.

### Rebuild the public examples

From the checkout, use `make examples` to rebuild the three websites, their
inventories and the PDF downloads. It also rebuilds the linked Fontane and
Austen [case studies](../../samples/README.md#generated-artifacts). When changes
affect the embedded images, refresh the [screenshots](../screenshots/README.md)
before rebuilding the examples. The [video guide](../videos/README.md)
describes recording and encoding.

After changing `samples/first-look.md`, refresh the reviewed chapter-one audio
provenance before running `make examples`.

```sh
PYTHONPATH=src .venv/bin/python scripts/build_demo_audio.py --reuse-recording
```

This checks the exact speech text for chapter one and verifies the WAV's
checksum before recording the new full manuscript checksum. If the speech text
changes, run the command without `--reuse-recording` on a machine with eSpeak NG
and review the new clip before building the reader demo.

Follow the [generation and preview procedure](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#generate-and-preview)
for documentation tests and local review. `scripts/stage_pages.py` verifies
the three approved website inventories, including the five manuscript PDF
layouts, Mara’s dossier PDF and the reviewed resources. It also stages the
compatibility entry. Keep source archives, private manuscripts, credentials
and local build outputs outside the staged site.
