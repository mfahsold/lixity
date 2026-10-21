# Product screenshots

Browser captures of the maintained dashboard. The
[project page](https://mfahsold.github.io/lixity/) introduces the reader and
links to the demo. Use the links below for related views and full-size images.
All product captures follow [*The Crate at Warehouse 4*](../demo/report.html):
the same six-chapter manuscript, research records and project metadata.

## Browse by feature

| Feature | Views |
| --- | --- |
| Continuous manuscript reader | [Light](dashboard-light.png), [dark](dashboard-dark.png), [mobile](dashboard-mobile.png), [empty workspace](dashboard-welcome.png) |
| Chapter comparisons | [Heatmap excerpt](dashboard-heatmap.png), [reference bands](dashboard-reference.png), [settings](dashboard-settings.png) |
| Scene registers | [Scene excerpt](dashboard-scenes.png), [mobile](dashboard-scenes-mobile.png) |
| Style and annotations | [Dimensions](dashboard-dimensions.png), [dark](dashboard-dimensions-dark.png), [mobile](dashboard-dimensions-mobile.png), [exact passage overlay excerpt](dashboard-layer.png), [work markers](dashboard-markers.png) |
| Editorial loop | [Flag queue (empty in this sample)](dashboard-flags.png), [note written on a passage](dashboard-editorial.png) |
| Project setup | [New project](dashboard-project-modal.png), [open project](dashboard-project-open.png), [mobile](dashboard-project-open-mobile.png) |
| Manuscript import | [Preview and confirmation](dashboard-project-import.png), [mobile](dashboard-project-import-mobile.png) |
| Project settings | [Project settings](dashboard-project-settings.png), [mobile](dashboard-project-settings-mobile.png), [expanded NDA panel](dashboard-nda.png), [mobile](dashboard-nda-mobile.png) |
| Retained evidence | [Source report](dashboard-research.png), [capture list](dashboard-research-sources.png), [mobile](dashboard-research-sources-mobile.png) |
| Research dossiers | [Filtered dossier overview](dashboard-research-dossiers.png), [mobile](dashboard-research-dossiers-mobile.png) |
| Visual references | [Historical map](dashboard-dossier-image.png), [mobile map](dashboard-dossier-image-mobile.png), [photochrom](dashboard-dossier-photo.png), [mobile photochrom](dashboard-dossier-photo-mobile.png) |
| Places and journeys | [Coordinate sketch](dashboard-dossier-geography.png), [mobile](dashboard-dossier-geography-mobile.png) |
| Research search | [Passage results](dashboard-research-search.png), [mobile](dashboard-research-search-mobile.png) |
| Claims and decisions | [Claims](dashboard-research-claims.png), [mobile](dashboard-research-claims-mobile.png), [decisions](dashboard-research-decisions.png), [mobile](dashboard-research-decisions-mobile.png) |
| Claim chronology | [Timeline with axis, badges and placement hint](dashboard-research-timeline.png), [mobile](dashboard-research-timeline-mobile.png) |
| Research review | [Saved manuscript quote and claim revision](dashboard-research-review.png), [mobile](dashboard-research-review-mobile.png) |
| Related revisions | [Change set preview](dashboard-research-change-set.png), [mobile](dashboard-research-change-set-mobile.png) |
| Terminal reports | [Analysis](cli-analyze.png), [style](cli-style.png), [research](cli-research.png) |

## Data and capture scope

Analysis and research views use the synthetic
[Warehouse 4 manuscript](../research/examples/harbour-manuscript.md), whose owning
source is `samples/first-look.md`. Project paths, author settings, research prose,
claims and decisions belong to the same invented project.
Marker notes exist only in an in-memory copy. The NDA view previews a synthetic
five-field draft without storing agreements or recipient records. Research visuals
use a historical Hamburg map excerpt and a Photochrom Print Collection harbour
view; [source metadata, credits and file hashes](../assets/research/sources.json)
identify the reviewed public-domain originals. Geographic points and journeys
are authored demonstration data, not positions derived from those images or
verified historical routes. These examples contain no private
manuscripts, archives, credentials or running user projects.

Desktop reader entrances end after the complete opening chapter. Mobile reader
overviews and the standalone source report show honest viewports, so reading
continues below the image. Other captures frame complete widgets or end at an
explicit task boundary: research lists show a complete matching dossier, claim or decision; source lists
end after the complete source context and document controls,
and the editorial view ends after the selected paragraph and its note controls.
Follow the full-size image links above to inspect the actual framing.
The reader captures use **Analysis Off**; chapter comparisons and
scenes open **Analysis overview**. Passage captures use the same native paragraph
actions and optional **Analysis On** layer. These captures represent v0.7.3;
older installed packages can show an earlier interface.
Scene images show the first three scenes, with the first expanded. Their sample
register is an illustrative assignment; its values come from the analysis.
Dialog images show the native scrollable confirmation state, including the header,
Close control and confirmation actions. Content above the current scroll position
remains available in the application; the camera does not expand native dialogs.
Dossier list descriptions are bounded reading previews, not the full saved note;
**View details** opens the complete content. Terminal images are report excerpts
except for the complete synthetic research search/citation response.

Local source/dossier filters search loaded metadata. Research Search searches
retained text separately. Selecting a manuscript does not submit it; confirming
import creates a separate project. Source integrity and citations do not certify
facts, and style measurements do not establish literary quality. Image sources
contain no text passages or linguistic scores.

## Regenerate

Install the Python development environment, Node.js and Playwright with Chromium,
then run:

```sh
.venv/bin/python scripts/make_screenshots.py
```

Playwright is optional capture/test tooling. If installed outside the checkout,
set `PLAYWRIGHT_MODULE=/absolute/path/to/playwright`. To choose a browser, set
`PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/absolute/path/to/chromium`.

The generator reuses the analysis pipeline and research API with explicit default
thresholds. Temporary HTML, synthetic responses and the capture manifest stay in
ignored `.artifacts/screenshots/`; browser actions use those fixtures. It creates no user
projects or stored agreements. Captures use fixed widths and reduced motion and fail
on runtime errors, missing panels or mobile page overflow.

Review the images before publishing. `.artifacts/screenshots/capture-results.json` records
PNG dimensions; update the corresponding HTML image attributes if they change.
Fonts and browser versions can affect pixel output. Use only reviewed synthetic
or public-domain data for repository screenshots.

## Walkthrough videos

[../videos/research-timeline.mp4](../videos/research-timeline.mp4) is a recorded
walkthrough of the claims timeline with a synthetic cursor, published with a
GIF and a poster. Regenerate both parts with `make videos`:

1. `scripts/make_screenshots.py --video` replays the scripted flow against the
   synthetic fixture and writes WebM recordings to `.artifacts/screenshots/videos/`.
2. `scripts/make_videos.py` converts them with ffmpeg into `docs/videos/`
   (MP4, GIF, poster) and enforces size limits.

Flows are code in `scripts/capture_screenshots.cjs`; keep recordings short and
free of private projects.
