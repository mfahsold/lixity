# From chapter comparisons to spoken direction: 3D style space and speech-plan export

By [Matthias Fahsold](https://github.com/mfahsold) · Published 2 November 2026 · Updated 25 November 2026 · 7 minutes

When an author revises a long draft, two questions often meet in the same chapter. Why does this chapter stand apart in the book's own style comparison? And how does the passage sound when read aloud with deliberate pacing and voice direction?

Lixity makes both steps inspectable without turning exploratory statistics or synthetic audio into automated verdicts. Every number points back to a specific chapter or paragraph so a human reader can decide whether the difference belongs to the scene.

<a id="style-space-spread"></a>

## 1. Read 3D chapter coordinates alongside each axis's spread

Open **Analysis overview → Compare chapters → Style** to see the exploratory 3D style space when chapter dimension scores are available. Each point represents one eligible chapter projected onto the first three principal axes of standardized low-to-high feature ranks. A solid ring identifies the currently selected chapter. A dashed ring marks chapters whose absolute score reaches the active raw coordinate cutoff (`|Score| ≥ 2.5` by default) on any computed axis, including axes beyond the first three.

Because principal components have different eigenvalues, a raw coordinate of `2.5` does not represent the same relative distance on every axis. On the first dimension, whose variance across chapters is larger, `2.5` may sit little more than one sample standard deviation from zero. On a third dimension with tighter spread, the same `2.5` cutoff can sit more than two sample standard deviations out.

Each style-dimension card and the cutoff explanation report the raw threshold together with its multiple of that axis's sample standard deviation. For example, `|Score| ≥ 2.5 (≈ 1.18 SD)` on Dimension 1 versus `|Score| ≥ 2.5 (≈ 2.09 SD)` on Dimension 3. That context shows why a chapter crosses the raw threshold on one axis more readily than on another. The exploratory coordinate ring stays separate from the noise-adjusted `z*` heatmap and Benjamini–Hochberg FDR selections. See the [methods reference](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md#5-exploratory-style-dimensions) and [interpretation guide](../guides/interpretation.html#visuals).

<a id="quotation-and-tense-boundaries"></a>

## 2. Cleaner boundaries for quotations and lexical tense cues

When you follow a chapter from the overview back into the manuscript, paragraph-level highlights and counts agree with what is on the page:

- **Cross-paragraph quotation spans:** when a recognized quotation span crosses a paragraph break, each overlapping paragraph receives its covered quoted words in the paragraph quotation-share calculation. Configured `dialogue_regex` patterns with multiple capture groups also use the first group consistently across corpus, chapter and paragraph views. Quotation detection remains a punctuation heuristic and does not identify speakers.

- **Lexical tense refinements:** Lixity's default paragraph tense signal is a fast lexical heuristic rather than a syntactic parser. German past-tense suffix matching avoids counting arbitrary `-te/-ten/-test` endings on nouns or adjectives as preterite verbs, and the default Spanish tense heuristic avoids double-counting an adjacent present-tense `haber` auxiliary (`he`, `has`, `ha`, `hemos`, `habéis`, `han`) followed by a regular past participle (`-ado`, `-ido`) as a separate present-tense marker. Compound forms with intervening adverbs or irregular participles remain heuristic; optional installed grammar models provide contextual verb-group analysis when needed ([validation limits](https://github.com/mfahsold/lixity/blob/main/docs/STABILITY.md#grammatical-tense)).

- **Contextual navigation help:** every destination in the top analysis navigation bar, the right-hand section outline, the **Back to passage** control and the reader speech button provides a localized tooltip across all seven interface languages. Activating an action control that transfers focus to a replacement button suppresses incidental tooltip popups so keyboard and pointer navigation stay unobstructed.

<a id="speech-plan-export"></a>

## 3. Export speech direction without locking into one audio engine

Reading a scene aloud is one of the oldest ways to test sentence rhythm, dialogue turns and local word echoes. Lixity stores project-local passage direction in `.lixity/audio-directions.json`. It shares voice profiles between the CLI and browser workbench and supports FFmpeg tempo post-processing (`--speed`) without altering explicit pauses, and connects to separately installed speech workers. Qwen VoiceDesign, Qwen Base, Coqui/OpenVoice and IMS-Toucan have distinct voice and direction capabilities; selecting a profile does not start or replace a worker.

Lixity uses manuscript structure to carry paragraph context, pronunciation rules, pauses and delivery notes into the plan. Choose the export, render or inspection workflow for the passage you are reviewing.

1. **Provider-independent JSON and SSML export.** Use **Listen and direct → Export direction** for a chapter or the manuscript. In the CLI, `lixity audio-export-plan` exports the same scopes, and `--preview-line` can select an anchored passage. No synthesis service is contacted. Timeline JSON preserves source lines, spoken-form pronunciation substitutions, authored direction, voice bindings and explicit pauses. SSML projects compatible controls and reports portability limits.

2. **OpenAI-compatible HTTP speech providers.** Audio settings schema `/4` or later can bind a profile to an explicit speech endpoint, model and voice. Set any API key through the profile's named environment variable. The service receives the selected prose when you start a render.

3. **Local recording inspection and transcript-bound verification.** `lixity audio-inspect` reports duration, peak and RMS levels, clipping and silence spans for WAV, FLAC or MP3 files. With a timestamped transcript bound to the recording's SHA-256 hash, `lixity audio-verify` compares planned words and pauses against that evidence. Missing transcript evidence is reported as unknown. To prepare transcript evidence separately, `lixity audio-transcribe` can send one selected file to its configured transcription service.

```
# Export a chapter's speech plan as JSON or portable SSML without synthesis
lixity audio-export-plan manuscript.md --project ./novel --chapter 2 -o ch2-plan.json
lixity audio-export-plan manuscript.md --project ./novel --chapter 2 --ssml -o ch2-plan.ssml

# Inspect a rendered WAV/FLAC/MP3 recording locally
lixity audio-inspect ./ch2-recording.wav --json
```

The audio manual covers provider configuration, privacy boundaries and reviewed settings upgrades. [Audio export and provider guide](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md#audio-export-and-external-providers)

<a id="phonetic-direction"></a>

## 4. Separate spoken words, IPA and delivery controls

The optional IMS-Toucan worker uses a saved author reference for German or English. It supports IPA overrides and passage-level duration, pitch variation, energy variation and pause controls. Spelling substitutions have their own field. Free acting prompts are preserved in exports, and Toucan synthesis reports them as unsupported. [IMS-Toucan setup](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md#ims-toucan-author-voice-and-phonetic-direction)

The reviewed audio settings schema `/5` migration preserves existing profiles. Timelines containing phonetic or prosody controls use schema `/2`. The teleprompter and export preview use the same spoken text and control summaries. [Controls, examples and limits](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md#ims-toucan-phonetics-and-structured-direction)

Microphone takes and paired WAV/JSON imports use one review path. A transcript must describe the actual recording and be explicitly confirmed; a reading script alone is not evidence. The [author-voice workflow](https://github.com/mfahsold/lixity/blob/main/docs/AUDIO.md#author-voice-recording-and-listening) explains capture, playback, review and save.

A static reading copy can include existing chapter recordings that match its manuscript revision and chapter selection. Listeners receive the selected chapter WAVs. The author’s reference recording stays in the project. [Choose recorded chapter audio](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#include-existing-chapter-recordings)

<a id="try"></a>

## Explore the chapter comparison in the demo

In the read-only demo, open **Analysis overview → Compare chapters → Style** to inspect the per-axis labels, or follow a saved quotation into its research dossier. [Warehouse 4 demo](../demo/report.html) · [Follow a research link](../guides/first-look.html#decision)

To direct and record your own manuscript, open it in the installed app. [Install Lixity](../guides/installation.html)

[All guides](../#guides)[Articles](index.html)[Source code](https://github.com/mfahsold/lixity)[License](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
