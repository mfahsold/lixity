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
claim-evidence matrix.
Editing, project administration, archive Search and Compare are unavailable in
the reading copy. Manuscript search and research list filters remain available.
Use **Manuscript** and **Research** to switch workspace views. Both use the same
prepared, read-only project snapshot.
The demo cannot import or save; generating new analysis or PDFs requires the
[local app](../guides/installation.html).

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

Project creation lives in `scripts/example_project.py`; screenshot HTTP fixtures
are a separate adapter in `scripts/make_screenshots.py`.
`scripts/example_publications.py` owns the Pages wrappers, metadata and
publication profiles. Screenshot and example generation call the shared demo
builder. It creates the same ordinary project, adds Mara’s reviewed dossier
version, and passes the project through the production exporter.
No screenshot fixture is needed to create or export the editable project.

A future real-book sample should be a separately prepared, explicitly selected
project using this same export path. This generator accepts no private manuscript
input. The public build still checks the synthetic manuscript bytes and reviewed
assets; changing a local project does not authorize publishing it.

### Rebuild the public examples

After [installation](../INSTALLATION.md), use `make examples` for the three
websites and PDFs, `make screenshots` for product captures, and `make videos`
for walkthroughs. The full video build uses Chromium and FFmpeg with libx264,
libaom-av1, libwebp, and the `drawtext` filter.
These entrypoints reuse the existing analysis, research and PDF APIs. Fontane
and Austen outputs under `examples/` remain named literary case studies linked
from the relevant articles; they are not alternative demo projects.

After changing `samples/first-look.md`, refresh the reviewed chapter-one audio
provenance before running `make examples`.

```sh
PYTHONPATH=src .venv/bin/python scripts/build_demo_audio.py --reuse-recording
```

This checks the exact speech text for chapter one and verifies the WAV's
checksum before recording the new full manuscript checksum. If the speech text
changes, run the command without `--reuse-recording` on a machine with eSpeak NG
and review the new clip before building the reader demo.

Review the output and run `make docs-check` plus the public-documentation browser
check in [`tests/browser/README.md`](../../tests/browser/README.md). The explicit
Pages boundary includes the three website bundles and their verified manifests,
the compatibility entry, five PDFs and reviewed visual assets. Source archives,
private manuscripts, credentials and local build state remain excluded.
