# Walkthrough videos

The guide walkthroughs and homepage tour show the synthetic Warehouse 4
workspace. The public-domain case studies have their own reports.
[Effi Briest](../examples/effi-briest.html) · [Pride and Prejudice](../examples/pride-and-prejudice.html)

| File | Purpose |
| --- | --- |
| `research-timeline.mp4` | H.264 video embedded in the research guide |
| `research-timeline.gif` | Loop for the README and chat previews |
| `research-timeline.png` | Poster frame and video thumbnail |
| `analysis-review.mp4` / `.gif` / `.png` | Chapter cell, paragraph Values and style dimensions walkthrough |
| `editorial-loop.mp4` / `.gif` / `.png` | Flagged passages, an opened paragraph and a marker note written on the passage |

The recorder overlays short step captions in the three guide walkthroughs.
The MP4, GIF and poster use those same frames.

Regenerate all reviewed recordings with `make videos`. Install the pinned
Playwright browser tools with `make browser-tools`. For the full encoding
pass, put `ffprobe` and FFmpeg with `libx264`, `libaom-av1`, `libwebp` and
`drawtext` on PATH.

1. `scripts/make_screenshots.py --video` records the scripted flows and writes
   WebM files to `.artifacts/screenshots/videos/`.
2. `scripts/make_videos.py` converts them into this directory and checks the
   size limits from its `WALKTHROUGHS` table.

`scripts/stage_pages.py` stages the reviewed files listed in
`scripts/make_videos.py`. Review the encoded recording and verify that it
contains only the approved fictional project before committing it.

## Homepage product tour

`product-tour.webm` (AV1), `product-tour.mp4` (H.264 fallback), and
`product-tour-portrait.mp4` (H.264) show the same 48-second tour in the
fictional Warehouse 4 workspace. Six eight-second scenes follow the tasks in
one project.

| Time | Task shown |
| --- | --- |
| 0–8 s | Open an analysis suggestion and jump to the manuscript passage |
| 8–16 s | Open the explanation and see the exact words counted |
| 16–24 s | Compare an unsaved draft and the manuscript under the same settings |
| 24–32 s | Open a chapter's sentence-length measurement in the matrix |
| 32–40 s | Open Mara’s saved dossier and see the chapter table and passages |
| 40–48 s | Download the displayed dossier version as a PDF |

The recorder starts a disposable local Lixity workspace. The comparison leaves
the manuscript unchanged. The last scene checks that the download contains a
complete PDF from the saved dossier version. The app uses the English fixture.
Captions explain each task in the homepage’s language.

Each scene allows time to orient, follow a deliberate action and read the result.
The camera stays fixed, with no animated zoom or burned-in English scene labels.
The paced pointer is a recording annotation, not an additional product control.

The homepage prefers the 9:16 source in portrait viewports and offers the two
landscape formats as fallbacks. Playback starts once
when at least half the video is visible, unless reduced motion or data saving
is requested. An explicit pause is respected; leaving the viewport or hiding
the tab pauses playback. Native controls and a localized play/pause button stay
available. Without JavaScript, the landscape poster and native playback
controls remain.
A failed video offers the interactive demo instead.

Captions are rendered at page resolution from the six localized transcript
items in each homepage. Each complete sentence appears without a typing animation
and remains visible for its scene; seeking updates the caption. All seven homepage
languages supply captions and playback controls. The complete transcript remains
readable without playback or JavaScript. Technical documentation remains English.

To record the tour again and rebuild its derived social excerpts:

```sh
.venv/bin/python scripts/make_screenshots.py --video --only product-tour
.venv/bin/python scripts/make_videos.py --only product-tour
make docs-sync
```

The recorder checks that actions fit six eight-second scenes. The encoder
checks the scene boundaries and final duration and enforces a 4 MB limit per
tour video source.
The 1440×900 landscape and 1080×1920 portrait videos each have 1,200 frames
at 25 fps and no audio. The landscape encoder produces H.264 and AV1 plus a
WebP still. The portrait encoder produces H.264 and a 540×960 PNG poster.
Inspect small UI text, framing, cursor motion and caption alignment before
accepting new encodings.

The homepage uses both encoded posters. `make docs-sync` incorporates a short
content fingerprint in each player video and poster URL so a refreshed page
loads the corresponding export. Public direct-download and sharing URLs stay
stable.

## Social excerpts

`social-hook-16x9.mp4` and `social-hook-9x16.mp4` show the same twelve-second
sequence. The clip opens the exact explanation for one underlined sentence
from the passage scene and holds on the result for four seconds. Use a caption
that invites the reader to find out what was counted.

The 1600×900 landscape file preserves the full workspace. The 1080×1920 portrait
file frames the manuscript more tightly and leaves room for readable titles.
Both put the Lixity mark, product name and question above the workspace. They
enlarge the actual evidence card as a picture-in-picture detail after it opens.
The crop is defined in `product-tour-timing.json` and should be checked against
any new recording. Both clips are silent with English text overlays.
The full product tour has localized captions. The landscape limit is 3.5 MB
and the portrait limit is 4 MB.

Regenerate them from an existing validated homepage MP4 with:

```sh
.venv/bin/python scripts/make_videos.py --only social
```

Review the caption, passage and evidence card at each intended display size.
The [reviewed asset handoff](../screenshots/README.md#maintain-the-one-package)
packages both formats with stills, text alternatives and byte hashes.

## Portrait master and FilmCraft workflow

The encoder reframes the raw capture for each of the six scenes. Each crop
centers the action at phone widths. The homepage shows localized captions below
the player in portrait viewports. The portrait tour runs for 48 seconds, and
the social excerpts run for 12 seconds.

Use [FilmCraft CLI](https://github.com/storytold/filmcraft/blob/main/docs/agents.md)
for editable cuts and picture-in-picture experiments with the synthetic source.
Keep working projects and previews in an ignored local directory
(`.artifacts/filmcraft/`, never `docs/`). The published
formats are generated by the encoder above so their frame, size and staging
checks remain part of the usual docs workflow.

Headless MCP loop (no window needed):

```sh
filmcraft-cli --save-as .artifacts/filmcraft/lixity-product-tour-v2/lixity-tour-v2.fcproj run setup.jsonl
filmcraft-cli --project <proj> inspect sequence   # assembled clip, marker order, fps
filmcraft-cli --project <proj> import <media>     # RAW bin only, synthetic source
filmcraft-cli --project <proj> render --seconds 10 --out /tmp/beat.png
filmcraft-cli --project <proj> exec markers.exportCsv '{"path":"review.csv"}'
filmcraft-cli --project <proj> exec file.exportMedia '{"path":"preview.mp4","format":"h264","range":"custom","startSeconds":0,"endSeconds":2,"wait":true,"audio":false}'
```

Each export must report `offlineMedia==[]` and `warnings==[]`; tour and social
masters have exactly one video stream and no audio. Check `render_frame` at
2/10/20/28/36/44 s, the marker CSV (7 per sequence with caption keys), frame
count, geometry, 1:1 SAR, CFR and byte budgets before promoting anything to
`docs/videos/`. Use the synthetic Warehouse 4 fixture for these recordings.
