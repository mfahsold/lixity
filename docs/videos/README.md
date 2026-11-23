# Walkthrough videos

Short recorded flows of the local dashboard. Guide walkthroughs use synthetic
fixtures; the homepage tour also uses public-domain classics. No private project
or manuscript appears in these files.

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

Regenerate with `make videos` (needs headless Chromium, ffmpeg and ffprobe):

1. `scripts/make_screenshots.py --video` records the scripted flows and writes
   WebM files to `.artifacts/screenshots/videos/`.
2. `scripts/make_videos.py` converts them into this directory and checks the
   size limits from its `WALKTHROUGHS` table.

`scripts/stage_pages.py` publishes this directory together with the guides and
screenshots. Review a recording before committing it; keep it under the limits
and free of real projects, names or unpublished text.

## Homepage product tour

`product-tour.webm` (AV1) and `product-tour.mp4` (H.264 fallback) show the same
48-second tour in the fictional Warehouse 4 workspace. Six eight-second scenes
follow the tasks in one project.

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

The homepage selects one supported source, with no audio track. It starts once
when at least half the video is visible, unless reduced motion or data saving
is requested. An explicit pause is respected; leaving the viewport or hiding
the tab pauses playback. Native controls and a localized play/pause button stay
available. Without JavaScript, the poster and native playback controls remain.
A failed video offers the interactive demo instead.

Captions are rendered at page resolution from the six localized transcript
items in each homepage. Each complete sentence appears without a typing animation
and remains visible for its scene; seeking updates the caption. All seven homepage
languages supply captions and playback controls. The complete transcript remains
readable without playback or JavaScript. Technical documentation remains English.

To regenerate just this recording:

```sh
.venv/bin/python scripts/make_screenshots.py --video --only product-tour
.venv/bin/python scripts/make_videos.py --only product-tour
make docs-sync
```

The recorder checks that actions fit six eight-second scenes. The encoder checks
the scene boundaries and final duration and enforces a 4 MB limit per video source.
It emits exactly 1,200 frames at 25 fps, with a 1440×900 frame, H.264 and AV1
compression, no audio or metadata, and a WebP poster. Inspect small UI text,
framing, cursor motion and caption alignment before accepting new encodings.

## Social excerpts

`social-hook-16x9.mp4` and `social-hook-9x16.mp4` are separate 30-second excerpts
for social sharing. They take six seconds each from the passage jump, evidence,
comparison, character dossier and PDF scenes of the validated homepage MP4.
The full tour also covers the chapter matrix.

The landscape file uses a 1600×900 frame with the complete app recording centered
between side margins. The portrait file uses 1080×1920 and fits the complete app
frame above a short hook; neither format crops away app controls. Social excerpts
carry English text overlays, unlike the homepage's localized captions. The
portrait keeps its brand and hook outside the app frame. The landscape limit is
3.5 MB and the portrait limit is 4 MB.

Regenerate them from an existing validated homepage MP4 with:

```sh
.venv/bin/python scripts/make_videos.py --only social
```

Review both layouts at their intended display sizes. The portrait preserves
context but cannot make all desktop interface text readable on a small phone.
