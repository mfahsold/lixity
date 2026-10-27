# Product screenshots

One reviewed catalog serves the website, screenshot capture and outreach assets:
[manifest.json](manifest.json). It contains each image's task, role, literal alt
text, caption and destination. The product introduction uses the **lead** image;
**support** images explain the next reading or research task. **Guide** and
**reference** images belong in the relevant instructions, not in every post.

## Start with a question

The opening image shows the actual explanation of “A board moved.”: three words
in the selected sentence, 4.4 words per sentence in its paragraph, and a separate
chapter comparison. Read the scene before deciding whether to revise. The
analysis-off reading view supplies context; it is not an analysis demonstration.

Empty review queues cannot demonstrate a finding. Dark and mobile variants are
layout examples rather than new benefits. Long timelines and research reviews
need their full-size links. Retained historical visuals need a source and scene
context; a map alone does not demonstrate a fact-checking workflow. The catalog
keeps specific guide views and existing article images without publishing every
capture variant.

## Catalog

<!-- catalog:start -->

| Task | View | Role and scope |
| --- | --- | --- |
| Why does this passage feel faster? | [dashboard-measurement-focus.png](dashboard-measurement-focus.png) | lead: Inspect the literal count and its separate paragraph comparison, then read the scene. |
| Where should I look next? | [dashboard-heatmap.png](dashboard-heatmap.png) | support: Compare chapters within this invented manuscript; colors do not grade writing. |
| What does the saved source say? | [dashboard-research-search.png](dashboard-research-search.png) | support: Read the retained source passage before following its claim and authored decision. |
| What did the author decide? | [dashboard-research-decisions.png](dashboard-research-decisions.png) | support: An authored creative choice, not an automatically verified fact. |
| Does the rhythm fit the scene? | [dashboard-reader-focus.png](dashboard-reader-focus.png) | support: Return to prose to make the editorial decision; this view does not demonstrate analysis. |
| Where are the workspace tools? | [dashboard-light.png](dashboard-light.png) | reference: Orientation view; use the explanation card for a readable analysis preview. |
| Can I read with a dark theme? | [dashboard-dark.png](dashboard-dark.png) | reference: Retained for published article links; a theme variant, not a separate product benefit. |
| Can I read on a narrow screen? | [dashboard-mobile.png](dashboard-mobile.png) | reference: A responsive reading example; prose continues below the viewport. |
| How do I leave an editorial note? | [dashboard-editorial.png](dashboard-editorial.png) | guide: The note is written by the user, not inferred by the analysis. |
| How do I start with a manuscript? | [dashboard-project-import.png](dashboard-project-import.png) | guide: Previewing a file and creating a project are separate actions. |
| Where do I configure chapter registers? | [dashboard-project-settings.png](dashboard-project-settings.png) | guide: Setup reference; a chapter label is not a literary judgment. |
| Where does a scene keep its research? | [dashboard-research-dossiers.png](dashboard-research-dossiers.png) | guide: Dossier orientation; follow a concrete passage for the evidence workflow. |
| How is a claim linked to evidence? | [dashboard-research-claims.png](dashboard-research-claims.png) | guide: A claim is an authored assertion, separate from its evidence. |
| What changed after an edit? | [dashboard-research-review.png](dashboard-research-review.png) | reference: Detailed full-size reference, unsuitable as a small social card. |
| When are the recorded events placed? | [dashboard-research-timeline.png](dashboard-research-timeline.png) | reference: Long full-size reference; a placed event is not a verified chronology. |
| Which visual source was retained? | [dashboard-dossier-image.png](dashboard-dossier-image.png) | guide: A visual research source; the invented incident is not verified by this map. |
| How does a retained map fit on mobile? | [dashboard-dossier-image-mobile.png](dashboard-dossier-image-mobile.png) | reference: A specific responsive visual-source reference, not another lead image. |
| Can I inspect a source image closely? | [dashboard-dossier-image-zoom.png](dashboard-dossier-image-zoom.png) | guide: Shows the image viewer, not a manuscript fact-check. |
| Can I retain a visual setting reference? | [dashboard-dossier-photo.png](dashboard-dossier-photo.png) | guide: Setting reference with provenance; not evidence for the fictional scene. |
| How are evidence, claims and decisions related? | [dashboard-dossier-diagram.png](dashboard-dossier-diagram.png) | guide: An explanatory authored diagram, not an automatically inferred evidence chain. |
| How do I inspect declared places and journeys? | [dashboard-dossier-geography.png](dashboard-dossier-geography.png) | guide: The demonstration positions and journeys are synthetic. |
| Can I use Lixity from the terminal? | [cli-analyze.png](cli-analyze.png) | reference: Developer reference; not the lead image for an author-facing introduction. |

<!-- catalog:end -->

## Data and limits

All product captures use [The Crate at Warehouse 4](../demo/report.html), the
six-chapter synthetic manuscript owned by `samples/first-look.md`. They were
captured from current development on 27 October 2026; installed releases can
show an earlier interface. A Fontane or Austen article must identify these as
interface illustrations, not measurements of that literary work.

Historical Hamburg map and photochrom references retain their
[source credits and hashes](../assets/research/sources.json). People, events,
positions and journeys are invented. Notes and decisions are authored examples.
No private manuscript, archive or running user project is used. An intact source
or a saved assertion is not a guarantee of factual correctness. Audio has no
reviewed capture here and these images establish nothing about voice quality.

Native controls and full component boundaries are preserved. The reading view
uses Analysis Off; the explanation and overlay views use Analysis On. Dialogs
retain their normal scrolling. Crops do not invent controls or results.

## Maintain the one package

From the repository root:

```sh
.venv/bin/python scripts/make_screenshots.py
.venv/bin/python scripts/make_screenshots.py --only dashboard-measurement-focus.png
.venv/bin/python scripts/make_screenshots.py --outreach-package /tmp/lixity-outreach-package
```

Normal capture selects this manifest and updates the catalog table and embedded
image dimensions. `--only` accepts reviewed names. Package preparation copies
only lead/support images into a new directory, with questions, captions, alt
text, destination URLs, source revision, working-tree status and byte hashes.
It does not recapture images, send posts or alter an approval queue. Exact post
copy and publication records belong in the separate outreach workspace; one
current package there points to these assets rather than maintaining another
screenshot selection. The package remains a draft until a separate publication.

Playwright with Chromium and the development Python environment are required
for capture. Browser fixtures and diagnostic output stay in ignored
`.artifacts/screenshots/`. Use synthetic or reviewed public-domain material only.
Pages stages only manifest-listed images; adding a PNG alone never publishes it.
