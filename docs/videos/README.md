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

Every walkthrough carries short step captions that name what the recording is
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
