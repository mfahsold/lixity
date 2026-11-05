# From chapter comparisons to spoken direction: 3D style space and speech-plan export

By [Matthias Fahsold](https://github.com/mfahsold) · Published 2 November 2026 · Updated 5 November 2026 · 7 minutes

When an author revises a long draft, two questions often meet in the same chapter: why does this chapter stand apart in the book's own style comparison, and how does the passage sound when read aloud with deliberate pacing and voice direction?

Lixity makes both steps inspectable without turning exploratory statistics or synthetic audio into automated verdicts. Every number points back to a specific chapter or paragraph so a human reader can decide whether the difference belongs to the scene.

## 1. Read 3D chapter coordinates alongside each axis's spread

In the **Analysis overview**, the review entry links directly to the exploratory 3D style space when chapter dimension scores are available. Each point represents one eligible chapter projected onto the first three principal axes of standardized low-to-high feature ranks. A solid ring identifies the currently selected chapter; a dashed ring marks chapters whose absolute score reaches the active raw coordinate cutoff (`|Score| ≥ 2.5` by default) on any computed axis, including axes beyond the first three.

Because principal components have different eigenvalues, a raw coordinate of `2.5` does not represent the same relative distance on every axis. On the first dimension, whose variance across chapters is larger, `2.5` may sit little more than one sample standard deviation from zero; on a third dimension with tighter spread, the same `2.5` cutoff can sit more than two sample standard deviations out.

Each style-dimension card and the cutoff explanation report the raw threshold together with its multiple of that axis's sample standard deviation—for example, `|Score| ≥ 2.5 (≈ 1.18 SD)` on Dimension 1 versus `|Score| ≥ 2.5 (≈ 2.09 SD)` on Dimension 3. That context shows why a chapter crosses the raw threshold on one axis more readily than on another, while keeping the exploratory coordinate ring separate from the noise-adjusted `z*` heatmap and Benjamini–Hochberg FDR selections. See the [methods reference](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md#5-exploratory-style-dimensions) and [interpretation guide](../guides/interpretation.html#visuals).

## 2. Cleaner boundaries for quotations and lexical tense cues

When you follow a chapter from the overview back into the manuscript, paragraph-level highlights and counts agree with what is on the page:

- **Cross-paragraph quotation spans:** when a recognized quotation span crosses a paragraph break, each overlapping paragraph receives its covered quoted words in the paragraph quotation-share calculation. Configured `dialogue_regex` patterns with multiple capture groups also use the first group consistently across corpus, chapter and paragraph views. Quotation detection remains a punctuation heuristic and does not identify speakers.

- **Lexical tense refinements:** Lixity's default paragraph tense signal is a fast lexical heuristic rather than a syntactic parser. German past-tense suffix matching avoids counting arbitrary `-te/-ten/-test` endings on nouns or adjectives as preterite verbs, and the default Spanish tense heuristic avoids double-counting an adjacent present-tense `haber` auxiliary (`he`, `has`, `ha`, `hemos`, `habéis`, `han`) followed by a regular past participle (`-ado`, `-ido`) as a separate present-tense marker. Compound forms with intervening adverbs or irregular participles remain heuristic; optional installed grammar models provide contextual verb-group analysis when needed ([validation limits](https://github.com/mfahsold/lixity/blob/main/docs/STABILITY.md#grammatical-tense)).

- **Contextual navigation help:** every destination in the top analysis navigation bar, the right-hand section outline, the **Back to passage** control and the reader speech button provides a localized tooltip across all seven interface languages. Activating an action control that transfers focus to a replacement button suppresses incidental tooltip popups so keyboard and pointer navigation stay unobstructed.

## 3. Export speech direction without locking into one audio engine

Reading a scene aloud is one of the oldest ways to test sentence rhythm, dialogue turns and local word echoes. Lixity stores project-local passage direction in `.lixity/audio-directions.json`, shares voice profiles between the CLI and browser workbench, supports FFmpeg tempo post-processing (`--speed`) without altering explicit pauses, and connects to separately installed speech workers. Qwen VoiceDesign, Qwen Base, Coqui/OpenVoice and IMS-Toucan have distinct voice and direction capabilities; selecting a profile does not start or replace a worker.

At the same time, Lixity's core strength is understanding manuscript structure—scenes, paragraphs, pronunciation rules, pause timing and authored delivery notes—not bundling every neural TTS stack inside the analysis engine:

1. **Provider-independent JSON and SSML export:** in **Listen & direct → Export direction** (or via `lixity audio-export-plan` and `lixity read-aloud --timeline` / `--ssml`), you can export the effective speech plan for a passage, a chapter or the entire manuscript without contacting any synthesis service. The `lixity-audio-timeline` JSON format preserves source-line provenance, spoken-form pronunciation substitutions, authored passage direction, voice bindings and explicit pause durations. The W3C SSML export projects supported breaks and substitutions while listing explicit portability warnings for controls that portable SSML cannot represent.

2. **Configurable OpenAI-compatible HTTP speech providers:** projects using audio settings schema `/4` (via the reviewed, backed-up `audio-migrate --to-schema-4` workflow) can bind a profile to an explicit HTTP speech endpoint, model and voice, referencing an environment-variable name for any API key. Credentials are never written into project files, and prose is sent only when you explicitly start a render.

3. **Local recording inspection and transcript-bound verification:** `lixity audio-inspect` measures local WAV, FLAC or MP3 recordings (duration, peak/RMS levels, clipping and silence spans). When you also supply a timestamped transcript bound to the recording's SHA-256 hash, `lixity audio-verify` compares planned words and pause spans against the transcript. Lixity runs no automatic speech recognizer; missing transcript evidence is reported as unknown rather than as a passed check.

```
# Export a chapter's speech plan as JSON or portable SSML without synthesis
lixity audio-export-plan manuscript.md --project ./novel --chapter 2 -o ch2-plan.json
lixity audio-export-plan manuscript.md --project ./novel --chapter 2 --ssml -o ch2-plan.ssml

# Inspect a rendered WAV/FLAC/MP3 recording locally
lixity audio-inspect ./ch2-recording.wav --json
```

See the [audio export and provider guide](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md#audio-export-and-external-providers-unreleased) for exact schema migration steps, privacy boundaries and recovery instructions.

## 4. Separate spoken words, IPA and delivery controls

**Current main, unreleased:** IMS-Toucan adds a German/English author-reference path with real IPA overrides and structured passage-level duration, pitch-variation, energy-variation and pause controls. Spelling substitutions remain a separate field. Free acting prompts are preserved for export but rejected for Toucan synthesis; they are not silently translated into emotions or numeric controls.

The reviewed audio-settings schema `/5` migration preserves existing profiles. Plans using the new controls use version `/2`; older-feature plans keep their existing contract. The Teleprompter and export preview consume the same canonical spoken text and control summaries. [Controls, examples and limits](../AUDIO.md#ims-toucan-phonetics-and-structured-direction-unreleased).

Microphone takes and paired WAV/JSON imports use one review path. A transcript must describe the actual recording and be explicitly confirmed; a reading script alone is not evidence. The [author-voice workflow](../AUDIO.md#author-voice-recording-and-listening) explains capture, playback, review and save.

**Reader audio, unreleased:** a static reading copy can opt into existing chapter recordings matching its manuscript and chapter cap. This distributes audio for listening; it does not export the author’s private voice reference or start synthesis on the reader’s device. [Choose recorded chapter audio](../WORKSPACE.md#include-existing-chapter-recordings-unreleased).

## Try the workflow in the updated demo

The read-only [Warehouse 4 demo workspace](../demo/report.html) has been regenerated from the current development checkout. Open **Analysis overview**, follow the direct link into the **3D style space** to inspect the per-axis standard-deviation labels, test the localized tooltips along the analysis bar, or follow a saved quotation into its [linked research dossier](../guides/first-look.html#decision).

For your own manuscript, install the published release or test the development branch locally via the [installation guide](../guides/installation.html#development-builds).

[All guides](../#guides)[Articles](index.html)[Source code](https://github.com/mfahsold/lixity)[License](../LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
