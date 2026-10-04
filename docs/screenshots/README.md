# Product screenshots

Browser captures of **v1.24.0**, taken on **4 October 2026**. The
[project page](https://mfahsold.github.io/lixity/) introduces each feature with
a selected image. Use the links below for related views and full-size images.

## Browse by feature

| Feature | Views |
| --- | --- |
| Manuscript overview | [Light](dashboard-light.png), [dark](dashboard-dark.png), [mobile](dashboard-mobile.png), [empty workspace](dashboard-welcome.png) |
| Chapter comparisons | [Heatmap excerpt](dashboard-heatmap.png), [reference bands](dashboard-reference.png), [settings](dashboard-settings.png) |
| Scene registers | [Scene excerpt](dashboard-scenes.png), [mobile](dashboard-scenes-mobile.png) |
| Style and annotations | [Dimensions](dashboard-dimensions.png), [dark](dashboard-dimensions-dark.png), [mobile](dashboard-dimensions-mobile.png), [paragraph layers](dashboard-layer.png), [work markers](dashboard-markers.png) |
| Project setup | [New project](dashboard-project-modal.png), [open project](dashboard-project-open.png), [mobile](dashboard-project-open-mobile.png) |
| Manuscript import | [Preview and confirmation](dashboard-project-import.png), [mobile](dashboard-project-import-mobile.png) |
| Project settings | [Settings and file picker](dashboard-project-settings.png), [mobile](dashboard-project-settings-mobile.png), [expanded NDA panel](dashboard-nda.png), [mobile](dashboard-nda-mobile.png) |
| Research sources | [Source report](dashboard-research.png), [source list](dashboard-research-sources.png), [mobile](dashboard-research-sources-mobile.png) |
| Research dossiers | [Filtered list](dashboard-research-dossiers.png), [mobile](dashboard-research-dossiers-mobile.png) |
| Research search | [Passage results](dashboard-research-search.png), [mobile](dashboard-research-search-mobile.png) |
| Claims and decisions | [Claims](dashboard-research-claims.png), [mobile](dashboard-research-claims-mobile.png), [decisions](dashboard-research-decisions.png), [mobile](dashboard-research-decisions-mobile.png) |
| Research review | [Decision links and revision pins](dashboard-research-review.png), [mobile](dashboard-research-review-mobile.png) |
| Related revisions | [Change set preview](dashboard-research-change-set.png), [mobile](dashboard-research-change-set-mobile.png) |
| Terminal reports | [Analysis](cli-analyze.png), [style](cli-style.png), [research](cli-research.png) |

## Data and capture scope

Analysis views use the public-domain Austen sample documented in
[samples/README.md](https://github.com/mfahsold/lixity/blob/main/samples/README.md).
Project paths, research sources, dossiers, claims and decisions are synthetic.
Marker notes exist only in an in-memory copy. The NDA view shows a locked demo
store without agreements or a passphrase. These examples contain no private
manuscripts, archives, credentials or running user projects.

Desktop/mobile overviews show a viewport; the heatmap shows its upper section.
Scene images show the first three scenes, with the first expanded. Their sample
register is an illustrative assignment; its values come from the analysis.
Dialog images include the complete form: the capture tool expands their scroll
containers temporarily, while the application retains normal scrolling. Other
panels show their full content. Terminal images are report excerpts except for
the complete synthetic research search/citation response.

Local source/dossier filters search loaded metadata. Research Search searches
retained text separately. Selecting a manuscript does not submit it; confirming
import creates a separate project. Source integrity and citations do not certify
facts, and style measurements do not establish literary quality.

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
ignored `.screenshots/`; browser actions use those fixtures. It creates no user
projects or agreements. Captures use fixed widths and reduced motion and fail
on runtime errors, missing panels or mobile page overflow.

Review the images before publishing. `.screenshots/capture-results.json` records
PNG dimensions; update the corresponding HTML image attributes if they change.
Fonts and browser versions can affect pixel output. Use only reviewed synthetic
or public-domain data for repository screenshots.
