# One read-only demo project

[*The Crate at Warehouse 4*](report.html) is the shared product walkthrough.
Its six synthetic English chapters come from
[`samples/first-look.md`](../../samples/first-look.md); the published
[manuscript](../research/examples/harbour-manuscript.md) contains identical bytes.
Analysis, research, screenshots and PDF layouts use that same project.

Start with chapter 1's setting and chapter 2's action, then choose **Research →
Dossiers → View details** on **Warehouse 4 case notes**. **Dossier alongside**
opens its reading companion. In **Review**, follow the eastern-gate quote
through **Linked version** to its pinned claim, dossier and source references, or use
**Go to manuscript passage** to read the quote. Starting from a manuscript
paragraph's association preserves an origin: close the record viewer and
choose **Back to passage** to return there. The development demo follows current
main: titles open current entries, explicit linked-version controls retain older
pins, and **Versions** expands the history without switching the displayed entry.
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

- `report.html`: the existing application renderer with all three workspace
  views, a bounded `research-data.json` fixture and reviewed visual assets.
  There is no live Zotero connection or access to a user's running service.
- `research.html`: compatibility entry to `report.html#research-manager`.
- The same six chapters as an [editorial copy](warehouse-4-editor.pdf),
  [reading copy](warehouse-4-book.pdf), [submission sheets](warehouse-4-sheet.pdf)
  and [analysis report](warehouse-4-report.pdf).

Browser controls support exploring manuscript analysis, retained research, a dossier
alongside the manuscript, prepared PDF downloads and a claim-evidence matrix.
Actions marked **Local app**, including Search and Compare, remain visible as
disabled previews with an [installation link](../guides/installation.html).
The public demo cannot import, edit or save; generating new analysis or PDFs
requires the local app.

Only the published website and demo use the configured GoatCounter counter for
page paths and named links. A PDF event records a successful prepared-file
request, not a completed filesystem save. The public adapter permits only the
reviewed analytics configuration read in addition to its existing fixtures and
prepared downloads. Local application views and exported reports carry no
counter. See the [website measurement notice](../index.html#website-measurement).

The generating version, provenance notice and unchanged distribution-license
appendix stay outside the analyzed manuscript. The short text is a demonstration,
not a calibration corpus, benchmark or literary-quality score. Public pages use
only reviewed synthetic/public-domain material and explicit code defaults.

## Regenerate

After [installation](../INSTALLATION.md), use `make examples` for the demo and
PDFs, `make screenshots` for product captures, and `make videos` for walkthroughs.
These entrypoints reuse the existing analysis, research and PDF APIs. Fontane
and Austen outputs under `examples/` remain named literary case studies linked
from the relevant articles; they are not alternative demo projects.

Review the output and run `make docs-check` plus the public-documentation browser
check in [`tests/browser/README.md`](../../tests/browser/README.md). The explicit
Pages boundary includes the demo page, compatibility entry, read-only fixture,
four PDFs and reviewed visual assets. Source archives, private manuscripts,
credentials and local build state remain excluded.
