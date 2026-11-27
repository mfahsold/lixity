---
name: lixity-filmcraft
description: Create, revise or diagnose Lixity product tours, software walkthroughs, website screen recordings and social video cuts. Use for clips with cropped controls, shot planning, FilmCraft editing or media delivery checks.
---

# Lixity FilmCraft production

Work from the Lixity checkout that contains `scripts/product_tour_edit.py` and
`docs/videos/README.md`. If this skill has been copied elsewhere, find the
checkout from the current directory with `git rev-parse --show-toplevel` and
verify those files. Open `docs/videos/README.md` from that checkout for the
commands, artifact paths and Warehouse 4 cue plan. The
[repository copy](https://github.com/mfahsold/lixity/blob/main/docs/videos/README.md)
is a fallback for reading the procedure.
Use FFmpeg for a direct check of an existing file. Use the FilmCraft CLI and
the runbook's fonts for editing. Use Playwright and Chromium for a new take.

## Choose the production path

- **A viewer reports a defect.** Identify the exact exported asset, displayed
  timestamp, affected browser or placement and build receipt if available.
  Follow the runbook's “Diagnose a review finding” section before choosing
  what to recapture or rebuild. On a fresh checkout, use
  the direct FFmpeg spot check and the affected browser.
- For an author action, record the disposable Warehouse 4 project in the
  writable local browser workspace. For a public website action, start from the
  staged Pages build. For a short reference walkthrough, use the matching
  guide capture. Use the installed desktop app only for a desktop-specific
  claim or when the brief calls for it.
- Recapture when the shown behavior, interface, source language, theme or shot
  timing has changed. Reuse verified source footage for a cut, crop or title
  change. Check the rendered page for player, poster selection or caption
  changes. Keep the requested formats and destinations in view.
- Record only approved public material in disposable profiles. Use the
  synthetic fixture for Lixity examples. Keep editable projects, raw takes,
  draft reviews and delivery proofs under `.artifacts/`.

## Plan actions before decoration

For each beat, write down the viewer question, the visible starting state, the
action and the observable result. Assign a crop for each destination and a
readable hold for the result. Give prominence to real product changes such as
finding a marked sentence, opening its linked claim, typing a revision or
checking the actual export. Match every title and caption to what the viewer
can observe. Use an inset when it supplies distinct context or shows the
control being used. Keep fixture content recognizable as content inside Lixity.

## Capture and compose

- Before recording, exercise the path in the intended viewport and theme.
  Verify the visible target, action and resulting state. Capture complete
  control groups, dialog sections and wrapped lines. Measure a new region
  when a menu, scroll offset or result changes. Keep the action time and the
  settled picture time distinct.
- Drive the existing headless FilmCraft composer for the tracked tour.
  Use “FilmCraft tools” in the runbook to inspect the project, source status
  or a short range. A configured FilmCraft
  MCP client can inspect the same synthetic project. Keep capture, inset,
  titles and brand editable. Vary position at scene boundaries, preserve reading
  order and compare versions at the same scale. Check rendered text bounds and
  viewing size.
- Review in order from the first frame to the call to action. Start with the
  frames on each side of every cut and check each hold. Step through
  consecutive frames around defects and play back pointer movement, typing
  and transitions. Classify a finding by the first layer that shows it
  (source UI, capture, FilmCraft, encode or player) and fix that layer.

## Deliver and verify

Use the runbook to decode current exports with `make video-review`, verify
responsive playback and the equivalent walkthrough, and synchronize generated
Pages references after replacing media. Use the runbook's “Accessible delivery”
section for silent and narrated media and review the intended social placement. Record the
format, time, frame and file identity for review findings. Follow the
repository publication procedure when rollout or sharing has been requested.
