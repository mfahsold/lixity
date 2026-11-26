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
`product-tour-portrait.mp4` (H.264) show the same 60-second tour in the
fictional Warehouse 4 workspace. Each of the six scenes lasts ten seconds.

| Time | Task shown |
| --- | --- |
| 0–10 s | Open a suggestion and read the manuscript passage |
| 10–20 s | See which 22 of the receipt sentence's 31 words count as function words |
| 20–30 s | Compare a shorter unsaved draft of the same sentence with the original under the same settings |
| 30–40 s | Inspect a chapter's sentence-length rhythm in the matrix |
| 40–50 s | Open the Warehouse 4 exhibit book and see the receipt with its blank receiving line |
| 50–60 s | Download the saved exhibit book version and confirm the PDF |

The recorder uses the English fixture in a disposable local workspace. The
comparison leaves the original manuscript untouched. The last scene checks that
the download contains a complete PDF from the saved exhibit book version.

The scenes alternate dark and light, starting in dark mode. Each scene shows the
Lixity icon and name and a short English title. Layouts use geometry recorded
from the app to enlarge the result in each format. The paced pointer is a
recording annotation.

The homepage prefers the 9:16 source in portrait viewports and offers the two
landscape formats as fallbacks. Playback starts once
when at least half the video is visible, unless reduced motion or data saving
is requested. An explicit pause is respected. Leaving the viewport or hiding
the tab pauses playback. Native controls and a localized play/pause button stay
available. Without JavaScript, the landscape poster and native playback controls
remain.
A failed video offers the interactive demo instead.

Captions are rendered at page resolution from the six localized transcript
items in each homepage. Each complete sentence stays visible for its scene and
seeking updates the caption. All seven homepage languages supply captions and
playback controls. The complete transcript remains readable without playback or
JavaScript.

To record the tour again and rebuild the website and social formats, run the
following commands.

```sh
.venv/bin/python scripts/make_screenshots.py --video --only product-tour
.venv/bin/python scripts/make_videos.py --only product-tour
make docs-sync
```

The recorder checks that actions fit the six scenes. The encoder composes the
formats from the raw frames and capture geometry. Both website landscape codecs
use the same 1440×900 layout. The portrait layout is 1080×1920 for the website
and social channels. The horizontal social layout is 1600×900. Every version
contains 1,500 frames at 25 fps and no audio. The encoder takes the landscape
WebP and 540×960 portrait PNG posters at about 15 seconds. The size limit is
4 MB per video, with a 3.5 MB limit for the horizontal social file. Inspect UI
text, framing, pointer motion and caption alignment before accepting an export.

The homepage uses both encoded posters. `make docs-sync` adds a content
fingerprint to the player sources, posters and download links. The underlying
media paths remain stable for existing links.

## Social video downloads

`social-hook-16x9.mp4` and `social-hook-9x16.mp4` both contain the full tour.
Their filenames keep existing links valid. The full build encodes one portrait
master and copies the website MP4 byte for byte to the social filename.

After capture, regenerate just the social formats from the raw frames with the
following command. Use the full tour build to publish matching portrait files.

```sh
.venv/bin/python scripts/make_videos.py --only social
```

Review scene titles and results at each intended display size.
The [reviewed asset handoff](../screenshots/README.md#maintain-the-one-package)
packages both formats with stills, text alternatives and byte hashes.

## Portrait master and FilmCraft workflow

FilmCraft CLI is available for editable cuts and layout experiments with the
synthetic recordings. Keep working projects and previews in the ignored
`.artifacts/filmcraft/` directory. Generate the published files with the encoder
above so the frame, size and staging checks run as part of the docs workflow.
[FilmCraft CLI guide](https://github.com/storytold/filmcraft/blob/main/docs/agents.md)

For a headless review, assemble and inspect the project with the CLI.

```sh
filmcraft-cli --save-as .artifacts/filmcraft/lixity-product-tour-v2/lixity-tour-v2.fcproj run setup.jsonl
filmcraft-cli --project <proj> inspect sequence   # assembled clip, marker order, fps
filmcraft-cli --project <proj> import <media>     # RAW bin only, synthetic source
filmcraft-cli --project <proj> render --seconds 15 --out /tmp/beat.png
filmcraft-cli --project <proj> exec markers.exportCsv '{"path":"review.csv"}'
filmcraft-cli --project <proj> exec file.exportMedia '{"path":"preview.mp4","format":"h264","range":"custom","startSeconds":0,"endSeconds":2,"wait":true,"audio":false}'
```

Check rendered frames at 5, 15, 25, 35, 45 and 55 seconds. Check the CSV for
seven markers per sequence, including the six caption keys and the end marker.
FilmCraft probe exports must report `offlineMedia==[]` and `warnings==[]`.
Check the final frame count, geometry, square pixels, constant frame rate,
single video stream and byte limits before staging the tour in `docs/videos/`.
