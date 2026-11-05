# Audio direction and listening

Listening can help an author notice phrasing, rhythm and dialogue that deserves
another look. Lixity supports passage direction, pronunciation controls, author
recordings, local synthesis and explicitly configured external providers.
Measurements and generated speech remain aids to human review.

The [Audio manual](../AUDIO.md) is the canonical guide for both CLI and browser
workflows. It labels current-main features as unreleased and explains which
operations need a worker, a microphone, a saved reference or FFmpeg.

| Task | Guide |
| --- | --- |
| Start with a passage preview | [Getting started](../AUDIO.md#getting-started) |
| Record, import and review an author voice | [Author voice](../AUDIO.md#author-voice-recording-and-listening) |
| Set gain or use the teleprompter | [Microphone calibration](../AUDIO.md#microphone-settings-and-calibration-audio-microphone-audio-calibrate-audio-reference-record) · [Teleprompter](../AUDIO.md#manuscript-teleprompter-direction-cues-phonetics-and-synchronized-dossier-images) |
| Shape delivery and pronunciation | [Passage direction](../AUDIO.md#passage-direction) · [Spelling substitutions](../AUDIO.md#pronunciation-substitutions) · [Toucan IPA/prosody](../AUDIO.md#ims-toucan-phonetics-and-structured-direction-unreleased) |
| Export a plan or use a provider | [JSON, SSML and external services](../AUDIO.md#audio-export-and-external-providers-unreleased) |
| Check an external recording | [Signal inspection and transcript comparison](../AUDIO.md#inspect-and-compare-externally-generated-audio-unreleased) |
| Add chapter audio to a reader export | [Retain or import chapter audio](../AUDIO.md#retain-or-import-chapter-audio-unreleased) |
| Install a matching speech worker | [Installation](../INSTALLATION.md#optional-qwen-audio-worker) |

Local synthesis does not send text to a hosted inference provider. A remote
provider is an explicit choice and receives spoken text during a render. A
voice reference and its transcript are private project data. Piper is removed;
the [migration procedure](../AUDIO.md#audio-settings-upgrades-and-recovery)
requires reviewed replacements and a backup.

Literal spelling replacements, IPA, free-text acting instructions and exact
pauses are distinct controls with different engine support. Neither successful
encoding nor an audio audit establishes narration quality. The
[single narrator rules](../AUDIO.md#single-narrator-and-delivery-variation)
check configured identities; reference recordings still require the author to
verify that they use the same speaker.

For project navigation and the rest of the CLI, start with the
[documentation map](../README.md).
