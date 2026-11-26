# One project, three reading websites

[*The Crate at Warehouse 4*](report.html) is the shared product walkthrough.
Its six synthetic English chapters come from
[`samples/first-look.md`](../../samples/first-look.md); the published
[manuscript](../research/examples/harbour-manuscript.md) contains identical bytes.
Analysis, research, screenshots and PDF layouts use that same project.
Mara recognises the number on a torn label as the number she copied on an
unsigned dispatch receipt. The foreman can dock her wages if the load goes
missing. Read the six chapters to see what she can put her name to when the
ledger raises a second question about the same number.

Two curated examples use the same production export and manuscript:

- [Read with context](reader/index.html) combines the six chapters with ten
  selected companion entries and a chapter analysis. Use **Analysis** from the
  reading page and **Back to reading copy** to return. In **Chapter audio**,
  choose either of the first two chapters to play or download its reviewed
  synthetic recording. Both use the local Qwen Ryan preset. The Eastern Gate
  runs for 88 seconds and The Loose Board for 113 seconds. Each recording has a
  manifest with the manuscript, spoken plan and audio checksums.
- [Companion only](companion/index.html) presents six selected entries through
  chapter 3. Its export excludes the manuscript, chapter analysis, chapter audio
  tracks and all later companion entries and resources.

Both start with no chapters marked as read. **Finished reading through** reveals
the author's selected notes for that progress; **Open later notes** temporarily
previews later material within the exported range. Progress stays in the local
browser. Hiding notes is a reading aid, not content protection: a chapter cap
must omit later material from the export itself.

The captioned watchman reconstruction is available after chapter 3. The
transfer counterfoil follows chapter 4, the dispatch receipt follows chapter 5,
and the receiving-signature note and ledger follow chapter 6. The full reader
includes all six chapters and its selected chapter analysis from the start.

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
The project retains nine sources, nine claims, four author decisions and seven
exact manuscript associations. Eight claims carry dates in the timeline. The
remaining claim records a future research question in the undated group.
Compare the conflicting inspection accounts and open the pinned older version
of the warehouse entry claim. Open **Warehouse 4 exhibit book** for the
captioned watchman statement and its transcript, the transfer counterfoil,
and facsimiles of the blue dispatch receipt and office ledger. The watchman
reports a direction of flight. The statement ends at the basin.

The two public-domain visual references and two fictional document facsimiles
are available as four retained images. The historical map and harbour view
have [reviewed credits and file hashes](../assets/research/sources.json).
The geography view contains nine authored features, including four journeys.
These include Mara’s walk to the office and a possible cart transfer to the
station. Use the map to discuss what the text places and what still needs an
author decision. The historical images give visual setting context. The
fictional routes are approximate and use independent coordinates.

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
  and pinned source quotation. The homepage tour opens the exhibit book and
  exports its dispatch-receipt dossier.

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
project layout. Open **Listen and direct** in chapter 3 to inspect the
paragraph direction on the watchman's answer. The project uses a local Qwen
Ryan narrator preset, with explicit tempo and paragraph / scene pauses. Export
the plan without a worker using `lixity audio-export-plan --project
.artifacts/warehouse-4-project --chapter 3 --timeline`. Keep personal edits in
your own copy. Public regeneration uses the reviewed synthetic inputs.

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

After changing `samples/first-look.md`, check or refresh the provenance for
both reviewed chapter recordings before running `make examples`.

```sh
PYTHONPATH=src .venv/bin/python scripts/build_demo_audio.py --chapter 1 --reuse-recording
PYTHONPATH=src .venv/bin/python scripts/build_demo_audio.py --chapter 2 --reuse-recording
```

Each command checks the chapter’s exact spoken text and the WAV checksum
before recording the new full manuscript checksum. If the spoken text
changes, generate and review a new recording for that chapter before building
the reader demo. Running the command without `--reuse-recording` uses the local
eSpeak NG engine and writes a new WAV and provenance record.

Follow the [generation and preview procedure](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#generate-and-preview)
for documentation tests and local review. `scripts/stage_pages.py` verifies
the three approved website inventories, including the five manuscript PDF
layouts, Mara’s dossier PDF and the reviewed resources. It also stages the
compatibility entry. Keep source archives, private manuscripts, credentials
and local build outputs outside the staged site.
