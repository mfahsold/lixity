# Walkthrough videos

Short recorded flows of the local dashboard. The published files are generated
from synthetic fixtures only; no private project or manuscript appears in them.

| File | Purpose |
| --- | --- |
| `research-timeline.mp4` | H.264 video embedded in the research guide |
| `research-timeline.gif` | Loop for the README and chat previews |
| `research-timeline.png` | Poster frame and video thumbnail |
| `analysis-review.mp4` / `.gif` / `.png` | Chapter cell, paragraph Values and style dimensions walkthrough |
| `editorial-loop.mp4` / `.gif` / `.png` | Flagged passages, an opened paragraph and a marker note written on the passage |

The three guide walkthroughs carry short step captions that name what the recording is
doing; the recorder overlays them inside the page, so MP4, GIF and poster show
the same sequence.

Regenerate with `make videos` (needs headless Chromium and ffmpeg):

1. `scripts/make_screenshots.py --video` records the scripted flows and writes
   WebM files to `.artifacts/screenshots/videos/`.
2. `scripts/make_videos.py` converts them into this directory and checks the
   size limits from its `WALKTHROUGHS` table.

`scripts/stage_pages.py` publishes this directory together with the guides and
screenshots. Review a recording before committing it; keep it under the limits
and free of real projects, names or unpublished text.

## Homepage product tour

`product-tour.webm` (AV1) and `product-tour.mp4` (H.264 fallback) show the same
48-second tour: reading, passage values, chapter comparison, research dossiers,
a historical reference image and a return to reading. The first three scenes
use the light theme, the last three the dark theme. The manuscript and research
remain the reviewed synthetic project. Camera zooms, focus rings, the pointer
and crossfades are recording annotations, not additional product controls.

The homepage selects one supported source, with no audio track. It starts once
when at least half the video is visible, unless reduced motion or data saving
is requested. An explicit pause is respected; leaving the viewport or hiding
the tab pauses playback. Native controls and a localized play/pause button stay
available. Without JavaScript, the poster and native playback controls remain.
A failed video offers the interactive demo instead.

Captions are rendered at page resolution from the six localized transcript
items in each homepage. They stay outside the camera zoom; seeking updates the
caption. The complete transcript remains readable without playback or JavaScript.
The app recording itself is English; all seven homepage languages supply their
own captions and controls. Technical documentation remains English.

To regenerate just this recording:

```sh
python3 scripts/make_screenshots.py --video --only product-tour
.venv/bin/python scripts/make_videos.py --only product-tour
make docs-sync
```

The recorder checks that actions fit six eight-second scenes. The encoder rejects
timing drift and enforces a 4 MB limit per video source. It uses 1440×900 at 20 fps,
slow H.264 compression and AV1 compression, removes audio and metadata, and emits
a WebP poster. Inspect small UI text and motion before accepting new encodings.
