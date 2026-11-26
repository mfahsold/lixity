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
manuscript. `product-tour.webm` (AV1), `product-tour.mp4` (H.264 fallback), and
`product-tour-portrait.mp4` (H.264) share the same 60-second cut.

| Time | Story and evidence |
| --- | --- |
| 0–5 s | A close view of the dispatch receipt shows the missing signature |
| 5–14 s | Read the original passage in the dark workspace |
| 14–27 s | Open the real explanation for 22 of 31 counted words and compare the shorter unsaved draft under the same settings |
| 27–42 s | Open the exhibit book, read the 18:40 return and compare it with the 20:00 dispatch |
| 42–52 s | Return to the final manuscript line and cut back to the blank receiving field |
| 52–60 s | Download the saved exhibit book and see the corresponding page from the actual PDF |

The recorder uses an English fixture in a disposable workspace. It verifies
22 highlighted words and the unchanged manuscript after comparison. The
export recording checks the saved revision in the filename, verifies the PDF
and renders the page that contains the two ledger entries. The two dated
facsimiles are authored assets for the fictional case.

Georgia sets the opening and closing titles and the manuscript quotations.
Inter sets brand, labels and counts. A consistent left gutter gives the eye a
reference after each cut.
Dark ink frames the manuscript, lilac frames measured details and paper frames
source evidence. The opening title and final demo link use eight-frame fades.
The other changes use direct cuts, including the return to the same signature
line. Phone and landscape frames have independent compositions. Short live
workspace actions lead into held details or typed excerpts with space to read.
[FilmCraft graphics](https://github.com/storytold/filmcraft/blob/main/docs/graphics.md) · [Match cuts](https://www.adobe.com/creativecloud/video/post-production/cuts-in-film/match-cut.html)

The homepage prefers the portrait source in portrait viewports and offers the
landscape formats as fallbacks. It starts playback only when at least half of
the player is visible and respects reduced motion, data saving and explicit
pause. Leaving the viewport or hiding the tab pauses playback. Native controls,
localized play/pause controls and a readable transcript remain available.
A failed video offers the interactive demo instead.

The six beats in `product-tour-timing.json` set cue boundaries for the seven
localized captions. Captions render at page resolution and update on seeking.
The short on-frame labels follow the English demonstration. The film is silent.

### Rebuild and review

```sh
.venv/bin/python scripts/make_screenshots.py --video --only product-tour
.venv/bin/python scripts/make_videos.py --only product-tour
make docs-sync
```

The browser records six actions and stores their decoded frame anchors, crop
geometry, and source fingerprints. The encoder validates that material before
`scripts/product_tour_edit.py` assembles the three FilmCraft projects. They keep
backgrounds on V1, original clips and stills on V2/V3, editable labels on V4 and
the logo on V5. Each canvas gets six beat markers and an end marker. FilmCraft
exports lossless PNG sequences. FFmpeg encodes each destination from those
frames and checks timing and geometry before replacing the public assets.

Both website landscape codecs share the 1440×900 sequence. The website and
social portrait MP4s share the 1080×1920 sequence. The horizontal social frame
is 1600×900. Every file has 1,500 frames at 25 fps, square pixels and a single
picture stream. Every file has a 4 MB budget, with 3.5 MB for horizontal social.
The landscape WebP and 540×960 portrait posters come from the opening scene at
two seconds. `make docs-sync` fingerprints the player sources, posters and
download links while keeping their base filenames stable.

Editable local projects and 360-pixel review frames live under
`.artifacts/filmcraft/warehouse-4-tour/`. Use the program monitor to confirm
that the opening receipt, explanations, before/after text, ledger and PDF can
be read. Verify that the brand stays within the left gutter and social overlays
or page captions leave the final link clear. Check the intended destination on
a phone because controls differ by placement.
[FilmCraft CLI guide](https://github.com/storytold/filmcraft/blob/main/docs/agents.md) · [Portrait placement overlays](https://support.google.com/google-ads/answer/9128498?hl=en-1-2)

```sh
filmcraft-cli --project .artifacts/filmcraft/warehouse-4-tour/warehouse-4-1080x1920.fcproj inspect sequence
filmcraft-cli --project .artifacts/filmcraft/warehouse-4-tour/warehouse-4-1080x1920.fcproj render --seconds 39 --scale 0.333333 --out /tmp/warehouse-4-ledger.png
```

## Social video downloads

`social-hook-16x9.mp4` and `social-hook-9x16.mp4` both contain the full tour.
Their filenames keep existing links valid. The full build copies the website
portrait MP4 byte for byte to the portrait social filename. To rebuild only the
social destinations, run `.venv/bin/python scripts/make_videos.py --only social`.
The [reviewed asset handoff](../screenshots/README.md#maintain-the-one-package)
packages both formats with stills, text alternatives and byte hashes.
