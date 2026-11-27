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
pass, put `ffprobe` and FFmpeg with `libx264` and an AV1 encoder (`libsvtav1`
or `libaom-av1`) on PATH. The WebP poster needs `cwebp` or `libwebp` in FFmpeg.
The product tour also uses FilmCraft CLI 0.20.1 or newer, Georgia Regular and
Inter SemiBold.

1. `scripts/make_screenshots.py --video` records the scripted flows and writes
   WebM files to `.artifacts/screenshots/videos/`.
2. `scripts/make_videos.py` converts them into this directory and checks the
   size limits from its `WALKTHROUGHS` table.

`scripts/stage_pages.py` stages the reviewed files listed in
`scripts/make_videos.py`. Review the encoded recording and verify that it
contains only the approved fictional project before committing it.

## Homepage product tour

**Why is this sentence marked?** follows one revision in the fictional
Warehouse 4 manuscript. The 65-second tour starts in the running workspace and
leads to the exported reading copy.

| Time | Story and evidence |
| --- | --- |
| 0–4 s | Find the marked sentence in the Lixity manuscript view. |
| 4–13 s | Open its explanation and inspect the 22 counted function words out of 31. |
| 13–26 s | Follow the research link from the next paragraph to the saved record. |
| 26–36 s | Type the shorter version and compare the 31-word sentence with the 12-word draft. |
| 36–46 s | Apply the draft, save it explicitly and return to the revised text. |
| 46–54 s | Choose the scope of the reading website and check the export. |
| 54–61 s | Open the exported reading copy and check the sentence the reader receives. |
| 61–65 s | Invite viewers to check the same passage in the read-only demo. |

The recorder uses one disposable copy of the English project. It verifies the
counted words, the original text during comparison and the revised sentence
after saving. The reading copy comes from the same workspace and shows the
saved revision. The source documents are fictional facsimiles.

### Type, picture and motion

Use Georgia for the film title and Inter for editorial labels. Open on the
marked manuscript in the workspace. Keep the cursor, the goal of the action
and its result legible together. Hold briefly after each action so viewers can
see the explanation, linked record, draft status and final export. Stack the
current and draft panes in portrait using the same source frames for each. Review
the mobile controls at their actual display size.

In the checkout, the eight cues in `docs/videos/product-tour-timing.json` set
the cue boundaries for the seven localized captions and the written walkthrough.
The film is silent, with English labels on the frames. The homepage displays
captions below the video and updates them on seeking. The homepage prefers
the portrait source in portrait viewports, with landscape fallbacks.
Playback respects reduced motion, data saving, explicit pause and page
visibility. Native controls and the written walkthrough remain available.
If playback fails, the page offers the interactive demo.

### Rebuild and review

```sh
.venv/bin/python scripts/make_screenshots.py --video --only product-tour
.venv/bin/python scripts/make_videos.py --only product-tour
make docs-sync
```

The browser records one continuous author session and stores frame anchors
for six shots, crop geometry and source fingerprints. The encoder verifies
the recording before `scripts/product_tour_edit.py` assembles the three
FilmCraft projects.
FilmCraft renders PNG sequences. FFmpeg encodes the public variants from these
frames and checks timing and geometry before replacing the assets.

Both website landscape codecs share the 1440×900 sequence. The website and
social portrait MP4s share the 1080×1920 sequence. The horizontal social frame
is 1600×900. Every video has 1,625 frames at 25 fps, square pixels and one
picture stream. The tour encodes retain the capture's sRGB transfer
with explicit limited-range BT.709 video metadata. The file budget is 4 MB,
with 3.5 MB for horizontal social.
The landscape WebP and 540×960 portrait posters use the opening scene at
two seconds. `make docs-sync` fingerprints the player sources, posters and
download links while preserving the base filenames.

Editable local projects and FilmCraft review frames are in
`.artifacts/filmcraft/warehouse-4-tour/`. The input recordings and hashes are
in `.artifacts/screenshots/videos/product-tour.json`. A successful encode
writes a local `receipt-*.json` alongside the FilmCraft projects. It records
input and output hashes, the tools used and encoder settings.

Review the encoded videos and posters for publication and sharing. Use the
optional browser capture to inspect the staged player and captions. Review
the narrow mobile player around 340 CSS pixels wide as well as landscape.
The browser suite records the screenshots in its local evidence directory.

```sh
ffprobe -v error -count_frames -select_streams v:0 \
  -show_entries stream=width,height,avg_frame_rate,nb_read_frames:format=duration \
  docs/videos/product-tour-portrait.mp4
PYTHON_BIN="$PWD/.venv/bin/python" node tests/browser/home-tour.cjs --review-frames
```

- At the first frame and 2 s, identify the question and the manuscript. The
  poster uses the same opening.
- Between 4 and 13 s, check the transition from the marked sentence to the
  count. Between 13 and 26 s, follow the click from the adjacent paragraph
  into its research and find the saved record.
- Between 26 and 46 s, read the text as it changes in the comparison. Watch
  for the draft and saved states and verify the revised text in the reader.
- From 46 to 61 s, review the export choice and its preflight, then check the
  exported reading copy. After 61 s, verify the demo invitation. Keep both ends
  of each relevant line clear of player controls and social overlays.
- Play the first and last beats on the desktop and phone layouts. Check the
  page captions and transcript against the visible action. Review the
  downloaded formats before preparing social copy.

[FilmCraft CLI guide](https://github.com/storytold/filmcraft/blob/main/docs/agents.md)
· [Portrait placement overlays](https://support.google.com/google-ads/answer/9128498?hl=en-1-2)

```sh
filmcraft-cli --project .artifacts/filmcraft/warehouse-4-tour/warehouse-4-1080x1920.fcproj inspect sequence
filmcraft-cli --project .artifacts/filmcraft/warehouse-4-tour/warehouse-4-1080x1920.fcproj render --seconds 23 --scale 0.333333 --out /tmp/warehouse-4-research.png
```

## Social video downloads

`social-hook-16x9.mp4` and `social-hook-9x16.mp4` both contain the full tour.
Their filenames keep existing links valid. The full build copies the website
portrait MP4 byte for byte to the portrait social filename. To rebuild the
portrait variants and their shared poster, run
`.venv/bin/python scripts/make_videos.py --only portrait`. The `--only social`
mode updates that same portrait group and the horizontal social file.
Run `make docs-sync` after either partial build.
The [reviewed asset handoff](../screenshots/README.md#maintain-the-one-package)
packages both formats with stills, text alternatives and byte hashes.
