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
The product tour also uses FilmCraft
CLI 0.20.1 or newer, Georgia Regular, Inter SemiBold and Poppler (`pdftotext`
and `pdftoppm`).

1. `scripts/make_screenshots.py --video` records the scripted flows and writes
   WebM files to `.artifacts/screenshots/videos/`.
2. `scripts/make_videos.py` converts them into this directory and checks the
   size limits from its `WALKTHROUGHS` table.

`scripts/stage_pages.py` stages the reviewed files listed in
`scripts/make_videos.py`. Review the encoded recording and verify that it
contains only the approved fictional project before committing it.

## Homepage product tour

**The Blank Line** follows an unsigned receipt through the fictional Warehouse 4
manuscript. Can Mara sign for an arrival she never saw? The 60-second tour
follows one sentence through an unsaved revision, the records behind the scene
and the saved exhibit PDF.

| Time | Story and evidence |
| --- | --- |
| 0–5 s | See the unsigned field on the receipt. Read Mara’s question. |
| 5–14 s | Read the scene where Mara tries to fit together the torn forms. |
| 14–27 s | Inspect the 22 counted function words. Hold the original 31-word sentence and the 12-word unsaved draft together with their counts. |
| 27–42 s | Open the exhibit book, find the two sources and compare the ledger’s 18:40 return with the receipt’s 20:00 dispatch. Both carry the number 17. |
| 42–52 s | Return to the manuscript. Mara signs her own note. The author leaves the receipt’s receiving line blank. |
| 52–60 s | Download the exhibit book, see the saved version on the PDF, and end with the demo address. |

The recorder uses an English fixture in a disposable workspace. It verifies
the counted words and checks that the manuscript remains on the saved version
after the draft comparison. Before rendering the selected PDF page, it checks
the saved revision in the filename and finds the office ledger with both
times in the extracted text. The receipt and ledger are facsimiles created for
the fictional case.

### Type, picture and motion

Use Georgia for the title and manuscript quotations. Inter identifies the
workspace, viewing steps and totals. Dark ink frames the manuscript, lilac the
measured details and paper the source records. Keep an inset around meaningful
text in moving shots as well as stills. Use the close views to make each piece
of evidence readable, from the two columns in the comparison to the dates and
number in the side-by-side records.

The opening asks the question immediately. Give each shot its own evidence.
Keep the two changed passages and their word counts on screen together for the
full comparison. Use the settled reader capture and let a slight push settle
into a reading hold. Bring in the return entry first and add the dispatch
entry beside it. Use warmer backing under the paper so the separate sources are
easy to distinguish. Show the signing action in the manuscript and give its
closing sentence one large Georgia setting. In the export, frame the actual
download control before showing its confirmation and the title and version on
the PDF. End with the demo address. The localized captions describe the visible
evidence for readers who need larger text or another language.

Fit the captures to their own framing, including a 12% target increase in
projected area before applying the safe inset. Give close views more height where
portrait width is constrained. Review the actual crop and scale at phone size.

In the checkout, the six scenes in `docs/videos/product-tour-timing.json` set
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

The browser records six actions and stores decoded frame anchors, crop
geometry and source fingerprints. The encoder verifies the recording before
`scripts/product_tour_edit.py` assembles the three FilmCraft projects.
FilmCraft renders PNG sequences. FFmpeg encodes the public variants from these
frames and checks timing and geometry before replacing the assets.

Both website landscape codecs share the 1440×900 sequence. The website and
social portrait MP4s share the 1080×1920 sequence. The horizontal social frame
is 1600×900. Every video has 1,500 frames at 25 fps, square pixels and one
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

- At the first frame and 2 s, read the full question and identify the blank
  signature. The poster should show the same opening.
- At 10 s, verify that the torn forms and Mara’s account are in view. At
  16.5 s, check the opening of the explanation. At 18.5 s, read the count in
  the card. At 21.5 and 25 s, verify that the same comparison and its two
  distinct excerpts remain visible, with space between their labels and text.
- At 32 s, read the return entry. At 39 s, read both times and both instances
  of 17. At 49 s, read the single large setting of the final manuscript line.
- At 54.5 s, identify the actual PDF download. At 55.8 s, read the dossier
  title and version on the PDF. At 57.5 and 59 s, check the demo address.
  Keep the start and end of each relevant line visible
  during motion and clear of player controls or social overlays.
- Play the first and last beats on the desktop and phone layouts. Check the
  page captions and transcript against the visible action. Review the
  downloaded formats before preparing social copy.

[FilmCraft CLI guide](https://github.com/storytold/filmcraft/blob/main/docs/agents.md)
· [Portrait placement overlays](https://support.google.com/google-ads/answer/9128498?hl=en-1-2)

```sh
filmcraft-cli --project .artifacts/filmcraft/warehouse-4-tour/warehouse-4-1080x1920.fcproj inspect sequence
filmcraft-cli --project .artifacts/filmcraft/warehouse-4-tour/warehouse-4-1080x1920.fcproj render --seconds 39 --scale 0.333333 --out /tmp/warehouse-4-ledger.png
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
