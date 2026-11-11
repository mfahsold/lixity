# Audio, author voice and passage direction

Use audio to listen through a manuscript, review pronunciation and pacing, record
your own voice, or prepare a direction plan for another service. This manual owns
the audio workflow in both the local browser app and the CLI. The
[documentation map](README.md), [browser workspace manual](WORKSPACE.md) and
[CLI reference](USAGE.md) cover the surrounding project workflow; install models
and workers through [Installation](INSTALLATION.md#optional-qwen-audio-worker).

The workflows below are available in 0.8.0; optional workers and models still
require their documented setup. Later source-only additions are marked
**unreleased** and are not a promise about an installed package. Check
`lixity --version` and each command's `--help`. Audio settings, direction, timeline and transcript schema
numbers are independent of the application version.

| I want to… | Start here | CLI route |
| --- | --- | --- |
| Hear a short passage or chapter | [Getting started](#getting-started) | `read-aloud` |
| Record or import my own voice | [Author voice](#author-voice-recording-and-listening) | `audio-reference` |
| Set the recording level | [Microphone and calibration](#microphone-settings-and-calibration-audio-microphone-audio-calibrate-audio-reference-record) | `audio-microphone`, `audio-calibrate` |
| Read and record with cues | [Teleprompter](#manuscript-teleprompter-direction-cues-phonetics-and-synchronized-dossier-images) | Browser workflow |
| Correct spoken names or use IPA | [Spelling substitutions](#pronunciation-substitutions) and [Toucan phonetics](#ims-toucan-phonetics-and-structured-direction-unreleased) | Project profile configuration |
| Shape delivery for a passage | [Passage direction](#passage-direction) | `audio-direction` |
| Export direction without synthesis | [JSON/SSML and providers](#audio-export-and-external-providers-unreleased) | `audio-export-plan` |
| Inspect a recording against a plan | [Audio inspection](#inspect-and-compare-externally-generated-audio-unreleased) | `audio-inspect`, `audio-verify`, `audio-import-transcript` |
| Keep chapter audio for a reader export | [Chapter recording import](#retain-or-import-chapter-audio-unreleased) | `audio-import` |
| Check a worker or change settings format | [Audio status](#audio-status) and [schema upgrades](#audio-settings-upgrades-and-recovery) | `audio-status`, `audio-migrate` |

Use `lixity read-aloud --help` or `lixity audio-reference --help` for installed
examples and action-specific options. Merely reading help never captures or
synthesizes audio.

## Getting started

1. Open the intended project and manuscript in the
   [local workspace](WORKSPACE.md). Audio profiles and saved references belong to
   that explicit project. For command-line work, use `--project ./novel`.
2. Open **Project → Settings → Audio and services**. Choose **Voice profiles**
   to select the engine, language, voice or recording and standard pauses.
   Save profile changes explicitly. The current manuscript control is
   **Listen and direct**; it opens the **Listen & direct** tab.
3. Inspect a plan first. **Export direction → Preview export** works without a
   running synthesis service. It still needs valid project/profile settings.
4. To generate audio, install and start a matching worker using
   [Installation](INSTALLATION.md#optional-qwen-audio-worker), or configure an
   [explicit external provider](#audio-export-and-external-providers-unreleased).
   **Services & audio queue** and `audio-status` report the currently available
   native model; status does not install or switch one.
5. Choose **Preview paragraph** for a short passage, listen to its actual words
   and delivery, then render the chapter. Save a download when needed. The
   [chapter recording rules](#retain-or-import-chapter-audio-unreleased) explain
   what is retained for reader exports.

```sh
lixity read-aloud --project ./novel --preview --plan-only
lixity audio-status --project ./novel
lixity read-aloud --project ./novel --preview --speed 1.0 -o preview.wav
lixity read-aloud --project ./novel --chapter 1 --progress -o chapter-1.wav
```

Only the last two commands synthesize audio. Plan JSON includes manuscript text
and private direction. Local workers keep synthesis on the configured computer;
a configured Jetson receives text through the operator's SSH forward, and an
explicit remote provider receives the effective spoken text when rendering.

Prerequisites depend on the task:

- Planning, direction editing and JSON/SSML export need no model or worker.
- Synthesis needs the exact engine's optional runtime and local model files, or
  an explicitly configured external service. Core analysis dependencies do not
  install inference models.
- MP3 output and a render tempo other than `1.0` require FFmpeg on the computer
  running Lixity, even when synthesis runs on a Jetson. New default profiles use
  `1.2`; use an explicit `--speed 1.0` for a WAV preview without tempo conversion.
- Browser recording needs browser microphone permission. Hardware gain and
  calibration use tools and devices on the server computer; they do not grant
  that permission or select the browser's input.
- A voice reference needs a reviewed 1–30 second mono, 24 kHz, 16-bit PCM WAV
  and the exact spoken transcript. A complete chapter recording has
  [different import limits](#retain-or-import-chapter-audio-unreleased).

## `lixity read-aloud`

**Speech planning, direction & audio generation:**
Version 0.7.7 separates dramaturgy and passage direction from raw synthesis.
The CLI and native dialog compile the manuscript, narrator delivery profiles,
pronunciation substitutions and timing into structured plans. In 0.8.0, use
`audio-export-plan` for the exchange timeline, or `--ssml` for an SSML
projection with explicit limitations. `--plan-only` retains the native speech
plan JSON contract. Explicit external providers and optional native workers
share rendering, pauses and atomic audio publication.

```bash
lixity read-aloud manuscript.md --language en --ssml > manuscript.ssml
lixity read-aloud manuscript.md --language de --chapter 2 --voice Ryan -o chapter-2.wav
lixity read-aloud --project ./novel --language de -o reading-copy.wav
```

`--preview` renders the first anchored paragraph or list item, and
`--preview-line N` selects the anchored paragraph or list item containing source line N.
Quote blocks do not currently have selectable preview anchors.
A chapter selection constrains either preview. Preview skips headings and uses a
separate default `-preview.wav` output; it does not read or write the segment
cache. `--plan-only` can be combined with either preview without synthesizing.
In 0.8.0, `--progress` reports completed segments and, after two segments,
a rough remaining-time estimate on stderr. The estimate averages completed
segments; different text lengths, cache hits and model startup can make it
inaccurate, and final encoding and publication are not included. The CLI checks manuscript,
settings and active direction snapshots during rendering and immediately before
publishing; changed or unreadable inputs reject the result and preserve an
existing output. `--no-direction` deliberately excludes the direction ledger.

In 0.8.0, the shared audio logger emits a random render ID and job/render
states at INFO. With `LIXITY_SPEECH_LOG_LEVEL=DEBUG` set before startup it also
records segment boundaries and timing, requested
preset/model variant, cache outcome and indicators showing whether effective
instructions, the voice description or the selected reference changed from the
previous segment. It does not log their contents or the manuscript. This helps locate a
change to audition; it does not determine whether the voice actually changed.
Native jobs and their renders share an ID; a current worker records this ID
alongside its own request ID when the optional correlation header is present.
The separate worker and a standalone
CLI do not automatically write into the managed app's log; see
[Logs](INSTALLATION.md#logs) for capture, rotation and privacy limitations.

`--chapter` selects a one-based chapter number. Without an explicit file, the
command uses the selected project's configured manuscript or folder discovery.
For native synthesis without saved audio settings, the default is one Qwen narrator using preset
`Ryan`, the project language and empty delivery instructions. English remains the
language default. `--voice` selects a Qwen preset, such as `Ryan` or `Aiden`.
The Qwen-supported languages are `en`, `de`, `fr`, `es`, `it`, `pt`, `ru`, `zh`, `ja`
and `ko`: six of the seven analysis languages, with Dutch (`nl`) unsupported.
Choose a supported speech language explicitly for a Dutch project; there is no
automatic language or backend fallback. Preset language support does not certify
native pronunciation. Review the model license before distributing output.
In 0.8.0, explicitly switching an existing VoiceDesign or Base profile
to CustomVoice also requires an explicit preset, such as `--engine qwen3
--voice Ryan`. An explicitly supplied reference ID requires a reference-capable
engine. For Base, clear inherited profile instructions with `--instructions ''`; `--no-direction` only omits saved passage directions.

### Voice profiles

Choose the engine for its supported controls before choosing a model or recording.
The following describes Lixity's current adapters, not every upstream model:

| Profile engine | Voice choice | Free-text delivery | IPA and structured prosody |
| --- | --- | --- | --- |
| `qwen3` | CustomVoice preset | Model-interpreted | Unsupported |
| `qwen3-design` | Voice description | Model-interpreted | Unsupported |
| `qwen3-base` | Saved recording with exact transcript | Unsupported | Unsupported |
| `coqui` | German Thorsten VITS | Unsupported | Unsupported |
| `coqui-reference` | Thorsten plus OpenVoice reference conversion | Unsupported | Unsupported |
| `ims-toucan` | Saved recording, German or English | Unsupported | Supported |
| `openai-compatible` | Explicit provider model and voice | Only with declared `supports_instructions` | Unsupported |
| `f5-tts` | Retained profile and compatible external local worker | Unsupported | Unsupported; bundled loader retired |

Every engine uses Lixity's literal spelling substitutions and explicit external
pauses. Render tempo is separate FFmpeg postprocessing. These controls do not
establish word fidelity, calibrated emotion or speaker similarity.

Saved project audio profiles are shared with the CLI. In the current
native interface, open **Project → Settings → Audio and services → Voice profiles**
to create or edit a profile,
including its model, delivery, standard pauses and pronunciation replacements.
The pronunciation editor can be expanded and searched. Filter and edit individual
entries, or open the text editor for bulk changes. Apply or discard an individual
entry draft before saving. Terms containing `=` are edited individually rather
than in the bulk editor. **Save project audio settings** stores the selected profile
and its controls through the normal atomic project settings path. A profile can be
removed as a draft before saving; the last profile cannot
be removed. A profile referenced by saved passage direction cannot be removed,
including references in stale direction entries or other manuscript sources.
Review or remove those references first. Use **Listen and direct** in the
manuscript to audition and direct a passage; the active project profile is shown
there. **Audio export and recordings** in the same settings section opens chapter
selection, generation progress and the resulting download. The
passage dialog also links directly to chapter output and retains the selected
chapter; save or discard any direction draft before switching. Draft
previews do not save settings. Read-only exports do not offer synthesis or expose
audio settings. The unified dialog and these entry points are available in 0.8.0.

In 0.8.0, the preview and chapter controls offer an explicit option to
ignore passage direction. It is off when the dialog opens. Enabling it omits
saved passage instructions, voice assignments and range-specific pauses for that
render; an unsaved direction draft is also omitted from the preview but remains
in the editor. The selected profile's instructions, pronunciation rules, speed
and standard pauses still apply. No saved direction is deleted or rewritten.
For a Base profile, clear any incompatible instructions in the profile as well.

```bash
lixity read-aloud --project ./novel --profile narrator -o reading-copy.wav
lixity read-aloud --project ./novel --profile narrator --chapter 2 -o chapter-2.wav
```

Choose **Render on → This computer / Configured Jetson** in the dialog,
or pass `--speech-target local|jetson` to the CLI. This choice applies to that
render; it is not part of a saved voice profile. The default is local, and an
unavailable target fails explicitly without switching machines or models.
In 0.8.0, the native audio interface names the choices by how the voice
is selected: a preset, a description or a reference recording. It also displays
a point-in-time worker status and compares a known loaded model with the selected
profile's model. An unreachable worker is unavailable; a missing or unrecognised
model identity leaves the match unknown. The display neither downloads a checkpoint
nor switches a worker. Check again before rendering if the worker has changed
since the status was retrieved. An incompatible delivery instruction remains
visible when switching to Base; remove it explicitly before saving.
Jetson sends the selected synthesis text to your configured machine through SSH;
it does not use a hosted inference provider.

```bash
lixity read-aloud --project ./novel --profile narrator --speech-target jetson --chapter 2 -o chapter-2.wav
```

For remote worker installation, fixed ports and the SSH command, follow
[Jetson audio worker setup](INSTALLATION.md#jetson-audio-worker). Qwen supports
local and Jetson targets; Coqui, Toucan and the retained F5 transport support only
their registered local target. An external profile uses its own validated URL.

### Cache, tempo and saved settings

The browser starts a background render and reports completed segments without
holding the initial request open. Cancellation waits for an in-flight synthesis
segment to return, then prevents publication. Native worker requests allow up to
one hour for a segment; this is a limit, not an estimate of chapter duration.
For external providers, the request timeout is 300 seconds per segment.

Long CPU renders can be retried without recomputing every completed segment.
Chapter jobs in the native UI and CLI renders retain verified segments in
`$XDG_CACHE_HOME/lixity/speech/<project-hash>/` (default
`~/.cache/lixity/speech/<project-hash>/`), bounded to 2 GiB per project.
The manuscript folder need not be writable.
Repeating the render reuses only requests with the same synthesis text, named
model family, language, preset voice and delivery instructions. Changes to pauses
are applied when assembling the output; they do not require new speech. Progress
includes reused segments. The final WAV/MP3 still appears only after successful
completion, so cancellation or failure preserves an existing output.

The **Reuse completed chapter segments** option is enabled by default;
uncheck it for a fresh interpretation. CLI users can request the same explicitly:

```bash
lixity read-aloud --project ./novel --profile narrator --chapter 2 --fresh-audio -o chapter-2.wav
```

`--no-audio-cache` renders without reading or retaining segments.
Previews are always fresh. The Python renderer
opts in with `cache_dir=...`, and accepts `fresh_audio=True` to recompute while
refreshing retained segments. Matching segments can be reused across execution
targets; request fresh audio when comparing CPU and GPU delivery.
Cache metadata stores request/audio hashes rather
than raw manuscript text, but the WAV files contain spoken project content and
must be treated as private. Missing, corrupt or evicted entries are recomputed.
The cache is not a saved job ledger: after restarting the app, start a new chapter
job to reuse its completed work. Temporary download expiration does not erase
these retained segments. Remove the derived folder to discard it. After replacing
local checkpoint files within the same named model family, request fresh audio
or clear the cache; the key does not fingerprint model weight bytes.

External FFmpeg conversion is limited to one hour per invocation.
A timeout fails the export, preserves an existing completed output and removes
temporary files. It does not restart a service or switch engines. This limits
the direct child process, not in-process inference or arbitrary grandchildren.

The selected saved profile is used when `--profile` is omitted. Explicit `--voice`,
`--language` and `--instructions` override that invocation without rewriting the
saved profile. In 0.7.7, `--speed 1.2` sets a playback tempo factor for all
profiles in that render; it does not modify saved profiles. Profile speed ranges
from 0.5 to 2.0. New default profiles use 1.2; existing saved profiles retain their
explicit rate, and previously omitted rates remain 1.0. FFmpeg applies `atempo`
to each synthesized or cached speech segment before the explicitly configured
pauses are inserted; speed 1.0 leaves the original speech untouched. If FFmpeg
returns no samples for an extremely short segment, the original segment is kept.
Qwen has no
precise native rate control, and delivery instructions do not guarantee a speaking
rate. Postprocessing can change perceived quality; compare short previews by ear.
The factor applies to model audio, including its internal pauses, so the overall
chapter's words per minute will not necessarily increase by exactly that factor.

A root `lixity.toml` can contain:

```toml
[audio]
schema_version = "lixity-audio-settings/1"
selected = "narrator"

[audio.profiles.narrator]
name = "Narrator"
engine = "qwen3"
language = "de"
voice = "Ryan"
speed = 1.2
instructions = "Read calmly and clearly, without whispering."
paragraph_pause = 0.45
scene_pause = 1.2
```

Profiles are project-only; user and ancestor configurations cannot supply them.
They also accept a `pronunciations` table of literal term-to-spoken-form pairs.
These substitutions affect synthesis text only; see the matching rules below.
A voice profile does not infer character identities or turn words such as “quiet” into acting instructions.

### Pronunciation substitutions

Version 0.8.0 also supports an optional project-wide lexicon. To opt in, change
the audio schema to `/2` and add a table shared by every profile:

```toml
[audio]
schema_version = "lixity-audio-settings/2"
selected = "narrator"
pronunciation_matching = { case_sensitive = false, whole_words = true }

[audio.pronunciations]
"Lixity" = "Lik-si-tee"

[audio.profiles.narrator]
engine = "qwen3"
pronunciations = { "Lixity" = "Liksity" }
```

Profile entries override project entries with the same exact key. Matching defaults
to case-sensitive literal substitution, including inside longer words. The optional
`pronunciation_matching` settings shown above change this for all profiles in the
project: `case_sensitive = false` uses Python's Unicode case-insensitive regex
matching, while `whole_words = true` requires the entire literal term, including
multiword or punctuation-bearing terms, to have no adjoining Unicode word character
or combining mark. This is not language-specific word segmentation or Unicode
normalization; preview with real text, particularly for scripts without spaces.
Replacement text retains its configured spelling and is not automatically
capitalized. Keys that the case-insensitive matcher considers equivalent are
rejected as ambiguous, including conflicts between global and profile entries;
an exact-key profile override remains valid. The combined project and profile map is limited to
200 distinct entries per profile. The UI's profile editor retains the project
table when saving; the project-wide table is currently edited in the project
configuration. Affected spoken segments get new cache keys when their substituted
text changes. Existing `/1` projects retain their behavior and need no migration.
Once a project uses `/2`, Lixity 0.7.7 and older installations do not accept its
audio settings: keep a backup and use a current version to render or edit them.

`qwen3` uses the
`Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` checkpoint and its nine presets.
Qwen lists the presets' native languages as Chinese, English, Japanese or Korean;
none is listed as a native German voice. They can still synthesize German, and
individual pronunciation and accent must be assessed by listening. See Qwen's
[speaker descriptions](https://github.com/QwenLM/Qwen3-TTS#custom-voice-generate).
Explicit style instructions, structural pauses and pronunciation settings are
shared by CLI and UI. Version 0.7.7 also offers separate experimental
VoiceDesign and reference-based Base checkpoints described below.
There is no automatic backend fallback.

The shared control model separates literal spoken-form substitutions, free-text
delivery direction and explicit PCM silence. Qwen receives substituted text;
CustomVoice and VoiceDesign interpret direction while Base rejects it. Neither
pronunciation nor acting is guaranteed. The
adapter advertises these capabilities in `control_support` and explicitly reports
that IPA/phoneme input, SSML and native model speed control are unsupported. This describes
Lixity's implementation, not every capability of every Qwen-derived model.
For comparison, [W3C SSML](https://www.w3.org/TR/speech-synthesis11/) and
[PLS lexicons](https://www.w3.org/TR/pronunciation-lexicon/) define structured
speech and pronunciation controls, while implementations vary by voice and model
([Amazon Polly](https://docs.aws.amazon.com/polly/latest/dg/supportedtags.html),
[Azure Speech](https://learn.microsoft.com/en-us/azure/ai-services/speech-service/speech-synthesis-markup-pronunciation),
[ElevenLabs](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/pronunciation-dictionaries)).
Lixity does not silently translate unsupported phonemes or markup into text.

## Author voice recording and listening

In 0.8.0, these entry points open one dialog with four tabs:

- **Author's voice**: read a sample or custom text, record a take, listen before
  saving, upload a studio WAV, and review the project's saved references.
- **Voice profiles**: choose the model, voice reference, language, delivery,
  tempo and standard pauses; edit pronunciation replacements and inspect the
  speech service. Save or discard profile drafts explicitly.
- **Listen & direct**: select a chapter or passage, edit its direction, preview
  or generate audio, export JSON/SSML, and inspect an external recording with an
  optional timestamped transcript. Export remains available without synthesis.
- **Mic & levels**: inspect local capture hardware, set its gain and run
  calibration. These controls affect the server computer's hardware; browser
  recording uses the input selected in the browser's permission prompt.

Help on the controls explains their scope and limits. The shared compact player
shows elapsed and total time, play/pause, seeking, mute and volume. Its live
frequency spectrum displays measured frequency levels during playback or
recording; it is not a recording-quality score.

The short sample is selected initially. Recordings use 24 kHz mono 16-bit PCM,
with a 30-second limit; saving requires at least one second. Before saving,
review the transcript in the take card and retain only words actually spoken.
Check **I checked that this transcript matches the recording** before saving;
editing the text clears that confirmation. **Save as author voice for this book**
retains the reference explicitly. Saving and activating are separate outcomes:
if activation fails, the recording may already be saved. Read the result before
retrying, and select a valid reference profile from the recordings list.
A successful activation refreshes the project view; reload if the UI reports
that the saved settings could not be refreshed.

Browser recording requires microphone access. If access is denied, allow the
microphone for the current local address in the browser's site permissions,
check the system's microphone permissions, and retry. Lixity cannot grant that
permission itself. A pending request is shown explicitly, and leaving the
recording tab or closing the dialog stops capture. A WAV upload remains an
alternative. Hardware calibration does not change browser permissions.

If Firefox has saved a block, remove that microphone permission using the icon
beside the address, then start recording again and allow the new request.
Permissions belong to the origin: `localhost` and `127.0.0.1` are separate.
The state beside the recording button reports requests, active recording and
failures. Failed starts also write a `[Lixity:error]` diagnostic to the browser
console, even with debug logging disabled. It identifies the failed stage and
browser capabilities without recording audio, transcripts or device identifiers.
Microphone access happens in the browser; a failed permission request does not
reach the server and therefore does not appear in the service log.

To import a studio recording, choose its PCM WAV and optionally its exported
**Take metadata (JSON, optional)**, then **Load take for review**. The sidecar
checks the audio bytes and restores its transcript; without it, enter the words
you actually spoke and confirm them. Loading a take does not save it to the
project. The take stays bound to the project/manuscript context in which you
recorded or imported it; reopen that context before saving.

**Download WAV** and **Download transcript metadata** keep a portable take before
saving a voice reference. A longer or incompatible recording can remain
available for listening and download without qualifying as a reference. Use the
[reference preparation steps](#experimental-reference-voices) to make a deliberate
excerpt or format conversion, then import it again. Recordings in the saved list
are selected by readable text and duration; internal IDs are for configuration
and machine output.

## Experimental reference voices

Qwen's [Voice Design then Clone](https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone)
workflow creates a short reference with VoiceDesign and reuses it with the
separately installed Qwen3-TTS 1.7B Base model. Alternatively, record your own
voice or use another recording you have permission to use. The reference is a
recording and its exact spoken transcript, not a voice-design prompt. Lixity
accepts a 1–30 second, mono, 24 kHz, 16-bit PCM WAV and a UTF-8 transcript of
at most 2,000 characters. A recording may be longer if you select a suitable
continuous excerpt before creating the reference.

Start and stop the recording yourself. For example, on a Linux desktop with
PipeWire's `pw-record` and a selected default microphone, the following creates
a private working directory and records until you press **Ctrl+C**:

```sh
mkdir -m 700 voice-work
pw-record --rate 24000 --channels 1 --format s16 voice-work/recording.wav
```

Choose a new directory and file name; a recording command may overwrite an
existing file. A graphical recorder may also be used. Keep the audio clear,
single-speaker and reasonably free of background sound. Listen to it and choose
an uninterrupted excerpt that begins and ends between spoken phrases. If you
stumbled, a clean later passage may work; do not transcribe words outside the
selected excerpt. Audio quality, the speaker's accent and the outcome need a
human listening check.

For example, with FFmpeg, this command selects seconds 0–20 and converts to the
required format. The time values are only an example: adjust them to the actual
recording and listen to the result to ensure they do not cut off words.

```sh
ffmpeg -ss 0 -i voice-work/recording.wav -t 20 -ac 1 -ar 24000 -c:a pcm_s16le voice-work/reference.wav
ffprobe -v error -show_entries stream=codec_name,sample_rate,channels:format=duration -of default=noprint_wrappers=1 voice-work/reference.wav
```

Write exactly what is spoken in the selected excerpt to
`voice-work/reference.txt` as UTF-8 text, including any spoken changes from a
prepared script. Listen and review any automatic transcript; transcription can
mishear names, short words or inflections. Do not include speech outside the
excerpt. The format check does not establish transcript accuracy or sound quality.
Then register the reference in an explicit project:

```sh
lixity audio-reference create --project ./novel --audio voice-work/reference.wav --transcript-file voice-work/reference.txt
```

The returned JSON `id` identifies an immutable project-local record in
`.lixity/audio-references/`; include the private reference audio and transcript
in a protected project backup. The same JSON contains a `quality` object with
level, noise floor, clipping and bandwidth measurements. Check an existing
reference with `lixity audio-reference inspect --project ./novel --reference-id ID`.
A `band_limited` or `digitally_silent_pauses` note means the recording lacks
high frequencies or room sound, for example because it was recorded at 16 kHz,
low-passed, gated or denoised before conversion to 24 kHz; generated voices can
inherit that limit. Record the reference again at 44.1 or 48 kHz without gate, denoiser or
low-pass and convert it only at the end. The notes are uncalibrated heuristics
([methods](METHODS.md#12-voice-reference-signal-diagnostics-audio-reference-inspect));
listen before deciding. The original working files are separate and may
also contain sensitive voice data. Creating the same reference again is
idempotent. The browser also records, imports and saves references through
[Author's voice](#author-voice-recording-and-listening); select saved recordings
there by their text and duration.

### Use a reference with Qwen Base

Install and start the separate Base checkpoint using the
[Qwen worker setup](INSTALLATION.md#optional-qwen-audio-worker). CustomVoice and
VoiceDesign workers cannot serve Base requests. With the Base worker ready,
check the variant and render a short preview, replacing `REFERENCE_ID` with the
ID returned by `audio-reference create`:

```sh
lixity audio-status --project ./novel --engine qwen3-base
lixity read-aloud --project ./novel --preview --speech-target local \
  --engine qwen3-base --voice reference --reference-id REFERENCE_ID \
  --instructions '' --no-direction --speed 1.0 -o reference-preview.wav
```

These overrides affect this CLI invocation, not saved project settings. The
preview retains the selected profile's pronunciation rules and standard pauses;
`--no-direction` also omits saved passage voice assignments and pauses. On CPU,
synthesis can take substantially longer than the resulting audio; use a short
preview and measure on the actual machine. Listen for intelligibility, accent
and continuity before a longer export. If the reference is suitable, add a
project profile with `engine = "qwen3-base"`, `voice = "reference"` and the
returned `reference_id`. Adjust or duplicate pronunciation settings as needed.

Qwen Base does not accept separate delivery instructions. Nonempty profile or
passage instructions fail rather than being ignored; explicit pauses, speech
rate postprocessing and pronunciation substitutions still apply. `--no-direction`
is a deliberate baseline that ignores *all* saved passage directions, including
their delivery assignments. For reference engines, delivery references are intended to come from the same
speaker. Lixity checks profile compatibility but cannot verify the speaker in a
recording; see the [single narrator rules](#single-narrator-and-delivery-variation). Reusing a reference encourages consistency, but accent, identity,
naturalness and pronunciation still require listening.

## Microphone settings and calibration (`audio-microphone`, `audio-calibrate`, `audio-reference record`)

In the browser, open **Project → Settings → Audio and services → Microphone and levels**
(the **Mic & levels** tab). Inspect the detected input and mixer range before
changing gain; a read-only hardware range must be changed in the system audio
settings. These settings control the server computer, even when the browser is
on another machine.

Hardware capture uses optional local tools (`arecord`, `amixer`, `ffmpeg` or
`pw-record`). Available devices and mixer controls depend on the operating system
and hardware. These controls are separate from browser microphone permission.
The CLI accepts raw gain values 0–100; the actual mixer range depends on hardware.
For `audio-microphone`, `--card` and `--control` apply only to `set`; status reads
the default mixer. `--device` applies to calibration, and capture fallbacks can
use other inputs. These are not device autodetection guarantees. Inspect the
chosen mixer and the resulting recording; calibration recommendations are a
separate heuristic, not a dB conversion. Use `lixity audio-microphone --help` for
the installed action-specific options.
The calibration command measures one test recording and suggests a gain adjustment;
it does not automatically tune the microphone or certify recording quality:

1. **Inspect hardware and set microphone gain:**
   List all detected hardware capture devices and current ALSA mixer levels:

   ```sh
   # View microphone status, active gain, and detected devices:
   lixity audio-microphone

   # List all audio input hardware:
   lixity audio-microphone devices

   # Set ALSA hardware gain immediately:
   lixity audio-microphone set --gain 35
   ```

2. **Calibrate microphone gain:**
   Set the requested gain once, allow a 4-second preparation countdown, then record
   an 8-second test window:

   ```sh
   lixity audio-calibrate --gain 35
   ```

   During the 8-second recording, perform 3× loud "POPP", 2× hand claps, and 1× spoken phrase
   ("Eins zwei drei"). The command analyzes peak level, clipping, noise floor, and dynamic
   range, providing an immediate verdict:
   - **`Kalibriert fuer Aufnahmen!`** (peaks between −13 and −7 dBFS): Within this heuristic target band.
   - **`ZU HEISS`** (Peaks above −7 dBFS): Danger of clipping; lowers gain recommendation.
   - **`MEHR LUFT ALS NOETIG`** (Peaks below −13 dBFS): Room for higher level.

3. **Option A: Record reference voice directly (terminal prompt):**
   Authors can record their own voice using a phonetically balanced calibration text (standard
   IPA reference passage "Der Nordwind und die Sonne" / "The North Wind and the Sun"):

   ```sh
   # Display teleprompter, count down 2s, and record phonetically balanced reference:
   lixity audio-reference record --project ./novel --calibration-text --gain 35
   ```

   The terminal displays a suggested passage. The selected recording duration does not
   prove that all of it was spoken: review the audio and ensure the supplied transcript
   matches it. This CLI path saves the immutable reference directly to
   `.lixity/audio-references/`; use the browser review card or a raw WAV first when
   you need to correct the transcript before saving.

   You can also pass custom transcripts:
   ```sh
   lixity audio-reference record --project ./novel --duration 15 --gain 35 \
     --transcript "Hier spricht die Autorin mit ruhiger Erzählstimme."
   ```

   Or record to a raw WAV file first:
   ```sh
   lixity audio-reference record --project ./novel --duration 15 --gain 35 -o voice-work/reference.wav
   ```

4. **Option B: Generate synthetic reference from calibration text:**
   Lixity can generate a synthetic reference from the calibration text using a
   running, separately installed VoiceDesign worker. This synthesizes and saves
   a reference; it is not an export-only action:

   ```sh
   lixity audio-reference generate --project ./novel --language de \
     --voice-description "A calm, warm German narrator voice with natural pacing."
   ```

5. **Inspect calibration texts:**
   To view the calibration texts directly or pipe them into scripts:

   ```sh
   lixity audio-reference calibration-text --language de --variant phonetic
   lixity audio-reference calibration-text --language de --variant short
   ```
<a id="manuscript-teleprompter-direction-cues-phonetics-and-synchronized-dossier-images"></a>

## Manuscript teleprompter: direction cues, phonetics and dossier context

The current-main teleprompter combines the manuscript reading view, saved
direction, pronunciation cues and linked research context. It can be used
without synthesizing speech:

1. **Opening the Teleprompter:**
   In the manuscript reader view, click the **Teleprompter** button in the reader controls
   toolbar or press the keyboard shortcut **`P`**. The prompter opens at the currently selected or active paragraph.
   Choose a chapter in its header. `D` toggles the context drawer; `Esc` closes
   the prompter. Keyboard shortcuts do not replace text entry in its fields.

2. **Reading Runway & Smooth Auto-Scroll:**
   - **Eye-level Focus Ribbon:** A subtle focal guide bar rests at 30% viewport height, keeping the
     speaker's line of sight fixed and comfortable.
   - **Variable Speed (WPM):** Adjust the scrolling pace with the speed slider or **`↑` / `↓`** arrow
     keys (60–240, default: 130). This is an approximate scrolling setting, not measured
     speech timing or automatic tracking of your voice.
   - The active paragraph follows the reading position inside the scroll pane,
     including within long paragraphs. The chapter selector follows that passage.
     Initial text size is 28 px and can be adjusted with the size controls;
     active text has no full-paragraph highlight box.
   - **Play / Pause:** Toggle scrolling with the **`Space`** bar or the top toolbar button.
   - **Typographic Controls:** Adjust font size on the fly with **`A−`** and **`A+`** (20–56px).

3. **Phonetic Pronunciations and Vocal Direction Cues:**
   The prompter requests the selected profile's manuscript speech plan without generating audio.
   Its reading text includes the same spelling substitutions as synthesis. All current passage
   directions, inherited structured prosody and pauses appear as cues; explicit IPA overrides
   appear as ruby annotations. `pronunciations` are spelling substitutions, while `phonemes`
   contain IPA. Stale or unavailable plans show an error and clear previous cues rather than
   presenting them as current.

4. **Research context:**
   The context drawer is separate from the recording card. Exact passage associations
   resolve their pinned dossier revisions and retained image versions, with withdrawn
   images shown explicitly. When no exact passage-context row exists, up to two
   title/tag matches may appear as labelled suggestions. They are not verified links.
   Loading and failed reads are visible; there is no inferred chapter fallback.

5. **Integrated Recording:**
   Click **Take record** (**Take aufnehmen** in German, `R`) in the prompter header and grant browser microphone access.
   Pending, recording and failed states are visible beside the control. Hardware mixer
   calibration does not grant browser permission. Stop to review the PCM WAV take; playback
   starts only when requested.

6. **Take export, import and author-reference review:**
   Download the WAV and its matching JSON metadata, or hand the take to **Author's voice** for
   review. The `lixity-audio-take/1` JSON binds filename, SHA-256, PCM format and duration to
   a transcript marked `missing`, `draft` or `confirmed`. Import both files together to retain
   that information; a mismatched or corrupt file does not replace the current take.
   A reading script is a draft, not evidence of the words actually recorded. Review and confirm
   the exact transcript before saving a voice reference; editing it requires confirmation again.
   Longer recordings remain downloadable, but voice references require 1–30 seconds of
   24 kHz mono 16-bit PCM and a confirmed transcript of at most 2,000 characters.
   The browser does not silently trim or convert incompatible imports. Portable takes are
   limited to 64 MiB WAV, 1 MiB metadata and 100,000 transcript characters.

## Audio and video playback

In the browser UI, Lixity provides integrated media players across workflows.
Playback begins only when requested. Player rate controls affect listening to
that file; they do not rewrite it or change the saved synthesis tempo.

- **Manuscript read-aloud and proofing:** The rendered speech player includes quick-access
  playback rate chips (`0.8×`, `1.0×`, `1.25×`, `1.5×`) and ±5-second skip buttons for
  reviewing individual phrases.
- **Research evidence and dossiers:** Audio (`audio/*`) and video (`video/*`) evidence
  attachments are rendered with native HTML5 players supporting byte-range seeking (HTTP 206)
  and local file download.

## Experimental Qwen VoiceDesign

Version 0.7.7 can use the separately installed Qwen3-TTS 1.7B VoiceDesign
checkpoint. Follow [Qwen checkpoint setup](INSTALLATION.md#choose-the-qwen-checkpoint)
and select `qwen3-design` in a project profile. Its `voice` is `design`,
and `voice_description` contains the desired voice characteristics. The normal
`instructions` and passage direction remain separate delivery instructions;
Qwen receives the description followed by the effective direction.

For an unsaved CLI audition or plan, use `--engine qwen3-design
--voice-description 'A natural, clear German narrator.'` with `read-aloud`.
`--plan-only` needs no worker. A worker serves one selected model variant; a
profile and its selected target must use the same variant. There is no automatic
download, fallback, or calibrated native pace control. Identical
descriptions do not guarantee the same voice across independently generated
segments. Listen for accent, pronunciation and continuity before a long render.
The planner can start a separate synthesis at paragraph boundaries, directed
ranges and the 600-character transport limit; it does not necessarily split
every sentence. For a single narrator, avoid direction that asks for different
voice types or named character voices. Even when all ranges use the same saved
profile, changing the free-text direction can change how VoiceDesign sounds.
The cache can reproduce a previously generated segment but cannot establish a
common voice identity across separately generated segments.
The cache distinguishes the model, voice description and effective direction.
Passage direction must retain the same engine, language and voice description
as the narrator. A cached segment does not authorize a conflicting passage
profile; current planning rejects that mismatch before rendering. Cache entries
can still be evicted while a render is in progress.

<a id="experimental-coqui-and-openvoice-audio-unreleased"></a>

## Experimental Coqui and OpenVoice audio

Lixity can use the German Thorsten VITS voice with an optional OpenVoice V2
conversion based on a saved project-local voice reference. These are separate
optional inference dependencies; analysis does not depend on them. The model
output and any voice similarity need human listening review. Thorsten VITS is
Apache-2.0 licensed and OpenVoice V2 is MIT licensed; check the model terms for
your use. OpenVoice does not list German among its native languages, so German
conversion quality is not guaranteed.

Install and start the optional worker through
[Coqui/OpenVoice setup](INSTALLATION.md#experimental-coqui-and-openvoice-audio-unreleased).
A Thorsten profile uses `engine = "coqui"`, `voice = "thorsten"` and
`language = "de"`; an OpenVoice profile uses `engine = "coqui-reference"`,
`voice = "reference"`, an existing `reference_id` and `language = "de"`.
Select the matching profile or use a one-off CLI `--engine` override.
`lixity audio-status --engine coqui-reference` checks the actual worker.

Saved Coqui profiles require audio settings schema `/3`, which older versions
cannot read. Before adding one to an existing project, preview the explicit
migration, review its JSON snapshot, then apply it with a new backup outside
the project (replace `TOKEN` with the reviewed snapshot):

```sh
lixity audio-migrate --project ./novel --to-schema-3
lixity audio-migrate --project ./novel --to-schema-3 --apply \
  --expected-snapshot TOKEN --backup /safe/location/novel-audio-backup.zip
```

<a id="audio-configuration-recovery"></a>

The migration checks for changes and backs up the original project configuration
before writing. Protect the backup; it does not contain the manuscript or the
private voice references, which need separate backups. For recovery, stop writes,
preserve the current configuration and work on a separate project copy. Restore
the configuration files listed in the backup's `manifest.json` `files` object.
If `lixity.toml` is absent from that list, it did not exist before migration:
after preserving and reviewing any later edits, remove the migration-created
`lixity.toml` from the recovery copy as well. Otherwise it overrides the restored
`pyproject.toml` settings. Check the recovered project with a compatible version
before resuming. Test the procedure on a restored copy before migrating a working
project. CLI one-off engine overrides do not change project settings.

Neither Coqui profile interprets free-text delivery instructions. Saved passage
instructions fail explicitly; `--no-direction` also omits passage voice
assignments and extra pauses. Pronunciation substitutions, explicit pauses and
playback speed use the existing Lixity pipeline. Playback speed is applied after
synthesis with FFmpeg; the 1.2 default is a product default, not a tuned value
for Thorsten, so compare 1.0 with listening. The worker stays silent about the
expected discards of the phonetic tie bar, the non-syllabic mark and
typographic quotation marks, which Thorsten's vocabulary cannot represent, and
warns with code points about any other discarded character. Listen to the
resulting pronunciation either way. The OpenVoice step mainly changes timbre;
phrasing and intonation come from Thorsten, and the converted voice inherits the
channel of its reference, including a bandwidth limit. Check a reference
before using it through [reference inspection](#experimental-reference-voices). Profiles containing these new engine identifiers
are not readable by older Lixity versions.

<a id="retained-f5-tts-profiles-unreleased"></a>

## Retained F5-TTS profiles

The earlier experimental bundled F5 loader did not implement the upstream
vocoder, vocabulary and reference-input contracts correctly. It has been retired
and fails explicitly before loading inference dependencies or downloading models.
New profiles no longer offer this unsupported bundled runtime.

Existing `f5-tts` profiles, immutable references, plan exports and valid cached
segments are retained. The fixed local HTTP transport on port 8771 remains usable
with an explicitly operated compatible worker; status queries probe that socket.
Cache identity now includes both the F5 model and its reference, correcting a
collision in the earlier experimental path. No existing project is automatically
converted to another voice.

For local author-reference synthesis with phonetic/structured controls, create a
separate IMS-Toucan profile after the reviewed schema upgrade below. An explicitly
configured external provider is another option. Neither preserves an F5 voice by
assumption; audition the new profile before using it for a full export.

<a id="ims-toucan-phonetics-and-structured-direction-unreleased"></a>

## IMS-Toucan phonetics and structured direction

`ims-toucan` combines a reviewed author recording with German or English speech,
explicit IPA pronunciation overrides, and structured prosody. The optional local
worker requires the [separate installation](INSTALLATION.md#ims-toucan-author-voice-and-phonetic-direction).
It does not interpret free natural-language acting prompts. Existing instructions
remain available in plan exports; synthesis rejects them rather than ignoring them.

The audio dialog uses one profile/direction workflow with capability-specific
controls. Upgrade existing settings to `/5` through the reviewed backup dialog
before adding Toucan. In **Voice profiles**, choose the saved recording,
open **Pronunciation dictionary (IPA)** for one `term=IPA` entry per line and
use **Structured delivery** for numeric controls. The dictionary permits at
most 200 unique terms, with 100 characters per term and 300 per IPA value.
**Clear delivery overrides** restores inheritance/defaults rather than guessing
new values. Profile and passage controls have separate save actions.

For the same reviewed migration from the CLI:

```sh
lixity audio-migrate --project ./novel --to-schema-5
lixity audio-migrate --project ./novel --to-schema-5 --apply \
  --expected-snapshot TOKEN_FROM_PREVIEW --backup ../novel-audio-schema5.zip
```

A newly created explicit configuration can use:

```toml
[audio]
schema_version = "lixity-audio-settings/5"
selected = "author"
[audio.profiles.author]
name = "Author voice"
engine = "ims-toucan"
language = "de"
voice = "reference"
reference_id = "REPLACE_WITH_SAVED_REFERENCE_ID"
speed = 1.0
[audio.profiles.author.phonemes]
Vogel = "ˈfoːɡəl"
[audio.profiles.author.prosody]
duration_scaling_factor = 1.1
pitch_variance_scale = 0.8
energy_variance_scale = 1.0
```

The CLI identifier comes from `audio-reference create`; the browser selects
recordings by their readable names. The source manuscript is never rewritten.
Existing `pronunciations` are literal spelling replacements. The separate
`phonemes` map contains IPA: case-sensitive, whole-word, longest-first matches
are applied after spelling replacements. A multiword override is never split
across model requests. Unsupported symbols fail before synthesis; IPA input
must use the supported Toucan phoneme inventory.

Profile prosody supplies defaults. A passage direction's sparse `prosody` object
overrides only its explicitly supplied fields; empty fields inherit defaults:

| Field | Range | Meaning |
| --- | --- | --- |
| `duration_scaling_factor` | 0.5–2.0 | Scale predicted phone durations; higher is slower |
| `pitch_variance_scale` | 0–2.0 | Scale intonation variation, not absolute pitch |
| `energy_variance_scale` | 0–2.0 | Scale predicted energy variation, not playback volume |
| `pause_duration_scaling_factor` | 0–3.0 | Scale model-internal pauses |
| `prosody_creativity` | 0–1.2 | Variation in predicted prosody |

Authored `pause_before`/`pause_after` remain exact external PCM silence. `speed`
remains the separate post-synthesis FFmpeg tempo factor. Neither is replaced by
the model's duration scaling. For a short test without changing saved settings:

```sh
lixity read-aloud --project ./novel --engine ims-toucan \
  --reference-id SAVED_REFERENCE_ID --instructions '' --no-direction \
  --preview --speed 1.0 -o preview.wav
```

The direction ledger and plan/timeline exports use schema `/2` when phonetic or
structured prosody data requires it. Existing records retain their previous
representations when no new fields are present. SSML exports emit IPA phoneme
elements; Toucan-specific numeric controls carry explicit portability warnings.
Unsupported engines reject these controls. Audio cache identity includes the
model, reference, IPA map and structured prosody. No model is automatically
selected for an existing project and no saved voice is silently converted.

## Single narrator and delivery variation

Read-aloud is a manuscript proofing workflow: passage profiles must remain
compatible with the selected narrator while changing delivery, pauses or tempo.
It does not infer characters or cast an audiobook from dialogue.

- `qwen3` uses the same preset; `qwen3-design` uses the same voice description.
  Their free-text delivery instructions can still change perceived voice.
- `openai-compatible` requires the same endpoint, model and provider voice.
  Delivery instructions also require explicitly declared provider support.
- Reference engines (`qwen3-base`, `coqui-reference`, `ims-toucan`, retained
  `f5-tts`) accept a different reference as a delivery recording of the same
  speaker. Lixity cannot verify who speaks in a recording; keeping the speaker
  consistent remains the author's responsibility. Free-text acting prompts are
  unsupported by these engines; Toucan instead supports structured prosody.
- Different engine/language combinations, presets, voice descriptions or provider
  identities are rejected with `NarratorConflict` when they change the configured
  narrator. That check does not guarantee acoustic continuity between segments.

Record calm and urgent delivery references of the same narrator if needed, and
listen to transitions before choosing them for passage profiles.

## Check narration continuity before a chapter render

Select a short passage with several sentences and audition the same passage both
with and without saved direction. For example, replace `12` with a source line
inside the intended paragraph and use the local worker explicitly:

```sh
lixity audio-status --project ./novel
lixity read-aloud --project ./novel --chapter 1 --preview-line 12 --speech-target local -o preview-directed.wav
lixity read-aloud --project ./novel --chapter 1 --preview-line 12 --speech-target local --no-direction -o preview-without-direction.wav
```

Both commands need a reachable local worker serving the selected profile's model;
CPU synthesis can be slow. The comparison keeps the selected profile, its
pronunciation rules, speed and default pauses. `--no-direction` excludes all saved
passage directions, including their voice assignments and custom pauses; it does
not remove the profile's own instructions. Each preview is generated afresh, so
differences can also reflect sampling and segmentation, not just the direction.
Listen to several short previews and, if needed, repeat them before drawing a
conclusion or rendering a chapter. `--plan-only` inspects the segment plan without
starting the model; its JSON contains private manuscript text and instructions.

If VoiceDesign still drifts, compare a suitable CustomVoice preset or a Base
profile built from one reviewed reference. CustomVoice presets are not certified
as native German voices; Base does not interpret free-text delivery direction.
Neither option guarantees continuity. Changing an instruction only affects new
renders; an existing WAV is not changed automatically.

## Passage direction

The native manuscript **Listen and direct** dialog can attach an author's direction
to an exact passage or selected range. Open it from the manuscript, choose the
passage, and select text in the read-only **Spoken text** field for a smaller
range. With no selection, **Use selected text / whole passage** restores the
whole passage. Choose a compatible delivery profile or inherit the current narrator
(see [single narrator rules](#single-narrator-and-delivery-variation)),
write local direction, and optionally set silence before/after in seconds.
The calm/tension/whisper choices are editable English prompt starting points,
not measured emotion controls. Under **Export direction**, choose **Selected passage** and **Preview export**
to inspect spoken text, voice choice, combined instructions and silence without
calling a model. A passage preview uses the draft; chapter/manuscript export or
generation requires saving or discarding it first. **Save passage direction**
retains the direction explicitly.
Profile settings and passage direction have separate save actions.

**Services & audio queue** in Project settings reports the actual model identity advertised by each available
local or Jetson worker; an unknown identity is shown as unknown. The dialog also
provides access to open projects and the audio queue.

Direction is retained in `.lixity/audio-directions.json`, separately from both
manuscript prose and `lixity.toml`. Each record binds the project-relative source,
its exact paragraph line/hash identity and a Unicode-code-point range in the
advertised spoken projection. Repeated wording at another location is a different
passage. Changed or moved paragraphs are preserved as stale records and require
explicit review/removal; they are never automatically reassigned. Overlapping
ranges and missing saved profiles fail before synthesis. The native dialog lists
stale records with explicit removal controls. Saved direction is private author
metadata and must be included in project backups when it should survive a move.

The shared planner first resolves ranges, then applies the selected profile's
literal pronunciation substitutions, then splits at direction and transport
boundaries. It never interprets bracketed manuscript text as acting instructions.
Longer pronunciation keys win. By default matching is case-sensitive and can
match within a word; the optional project matching policy is described under
[pronunciation substitutions](#pronunciation-substitutions). Replacement is one
non-recursive pass. A substitution spanning two
direction ranges does not match across their boundary.

A directed range uses its explicitly selected saved profile, otherwise the
invocation's current profile. Its local direction is appended to that profile's
instructions. CLI voice/language/instruction overrides affect the invocation's
default profile; explicitly referenced profiles keep their own settings. Newlines
in instructions become spaces. Silence after a range is inherited at paragraph
end or zero inside the paragraph unless supplied explicitly; supplied silence
replaces that boundary's default rather than adding a second pause. Pauses are
inserted as PCM silence by Lixity, not requested probabilistically from Qwen.

This data model takes separation of voice, pronunciation and pauses from SSML,
without claiming SSML compliance. Qwen receives ordinary `text`, `speaker`,
`language` and a separate `instruct`. Tone, emphasis and pace are model-interpreted;
there is no calibrated emotion intensity, exact speaking-rate/pitch control,
IPA phoneme input, guaranteed nonverbal effect or automatic character assignment.
Very short directed spans can sound disconnected. No cross-segment dramatic
memory or seamless multi-character performance is promised. Audio must be heard
and checked for word fidelity, pronunciation, voice continuity and delivery.

CLI observation and plan inspection need no running worker:

```bash
lixity audio-direction inspect --project ./novel
lixity read-aloud --project ./novel --chapter 1 --plan-only
```

To render a new comparison while omitting saved direction, explicitly synthesize:

```sh
lixity read-aloud --project ./novel --chapter 1 --no-direction --fresh-audio -o neutral.wav
```

`audio-direction inspect` returns paragraph anchors/spoken text, saved ranges,
stale flags, and the `source_sha256`, `settings_sha256`, `direction_sha256`
snapshots. Its JSON and plan output contain private prose and instructions.
In 0.8.0, `audio-direction add --project ./novel --chapter 2 --line 42
--instruction "Quietly." --pause-after 0.4` selects the spoken passage at that
source line and saves the direction without manually copying hashes. Optional
`--start` and `--end` select offsets in Unicode code points in the spoken
projection; `--profile-id` selects an existing saved voice profile. Inspect the
source and resulting direction to verify the intended passage. The command
rejects an existing identical range, overlaps, and concurrent changes; use
`inspect` and `save` for an explicit replacement.
To save, put one direction object in a private JSON file: `anchor` copied exactly
from inspection, optional code-point `start`/`end` (default whole paragraph),
optional `profile_id`, `instructions`, `pause_before`, nullable `pause_after`
and a sparse `prosody` object for structured delivery. Pause values are seconds
from 0 to 10; free-text instructions are limited to 2,000 characters.
`audio-direction save --project ./novel --input direction.json` additionally
requires `--expected-source`, `--expected-settings`, `--expected-direction` with
the three observed hashes. When changing a saved range’s bounds, pass its original
`--replace-id ID`; the original range is replaced under the same snapshot guards.
Removal uses `audio-direction remove --project ./novel
--id ID` with the same guards. Concurrent source/settings/direction changes reject
writes instead of overwriting another edit. Identical saves are idempotent.
`--no-direction` ignores saved passage direction for that invocation; it does not
delete it. The selected profile, pronunciation rules, speed and default pauses
remain active, so this is not a comparison without those influences.
Saved offsets use the marker-stripped spoken projection. `--keep-markers` is
rejected when retaining editorial markers would shift a directed passage; use
`--no-direction` for that deliberate alternative.
Cache reuse keys include the effective text/profile instructions; edited direction
cannot accidentally reuse audio synthesized with different instructions.

<a id="audio-export-and-external-providers-unreleased"></a>

## Audio export and external providers

Export a direction plan without synthesis or reading saved voice-reference bytes:

```bash
lixity audio-export-plan --project ./novel > manuscript.timeline.json
lixity audio-export-plan --project ./novel --chapter 2 --ssml > chapter-2.ssml
lixity read-aloud --project ./novel --preview-line 42 --timeline > passage.timeline.json
```

`audio-export-plan` defaults to JSON: `lixity-audio-timeline/1`, or `/2` when
phonetic/structured controls require it. `--ssml` selects
SSML. `read-aloud --timeline` and `--ssml` imply export-only behavior;
`read-aloud --plan-only` keeps the native speech-plan contract (`/1`, or `/2`
when those controls require it).
The browser offers JSON/SSML downloads for a passage, chapter or manuscript.
In 0.8.0, open the audio dialog from **Project → Settings → Audio and services** or **Listen and direct**
in the manuscript. In the **Listen & direct** tab, **Export direction → Preview
export** prepares downloads separately from the **Generate audio** controls.
Export does not require a running speech service. Voice profiles, author recordings,
microphone configuration and services/queue controls share the audio section of
Project settings. Recording references are selected by reading text and duration;
their internal identifiers remain in stored settings and machine exports.
JSON retains effective text, original spoken text, pronunciation substitutions,
direction, profile choices and pause values. Speech start times and durations
are unknown before synthesis; planned pauses are not measured timestamps.
Profile metadata includes configured provider URLs/model IDs and credential
environment-variable names, never resolved key values. Review that metadata when
sharing a plan outside the project.
SSML is a projection: inspect its warnings for controls without portable
representation, including free-form delivery, reference voices and provider
voice mappings. Export does not guarantee that a particular engine accepts all
SSML features. No export starts a worker or contacts a provider.

An external speech profile uses an explicit provider binding. Upgrade existing
settings through the backed-up migration before saving schema `/4`:

```bash
lixity audio-migrate --project ./novel --to-schema-4
# Review the preview; use its exact snapshot token and a new backup path:
lixity audio-migrate --project ./novel --to-schema-4 --apply \
  --expected-snapshot TOKEN_FROM_PREVIEW --backup ../novel-audio-schema4.zip
```

The browser offers the same review/apply step in voice profiles. Its preview
identifies retained profiles and whether an implicit narrator will become saved.
Keep the backup and follow the [audio configuration recovery procedure](#audio-configuration-recovery)
on a project copy before relying on a rollback. An older application may not read
schema `/4` or later profiles.
For an unconfigured project whose language has no native default, schema `/4`
keeps an explicit empty selection; create an external profile and enter its
endpoint/model/voice without changing the project language. Explicit external
CLI overrides can also export before any audio settings are saved.

Example project settings, with an explicitly chosen model and provider voice:

```toml
[audio]
schema_version = "lixity-audio-settings/4"
selected = "narrator"

[audio.profiles.narrator]
engine = "openai-compatible"
language = "de"
base_url = "http://127.0.0.1:8000/v1"
model = "your-installed-model"
voice = "your-provider-voice"
speed = 1.0
supports_instructions = false
# Optional: the name of an environment variable, never its secret value.
api_key_env = "LIXITY_SPEECH_API_KEY"
```

Omit `api_key_env` for a service without authentication. The rendering process
must have the named variable set; absence fails before sending a request.
For the managed browser app, use a name beginning with `LIXITY_`: the systemd
launcher forwards these variables by name. Start or restart the service from
the environment containing that variable; exporting it in a different terminal
does not update an already running process. CLI renders use their own environment.
HTTPS is supported for remote services. Plain HTTP requires localhost, loopback
or a private LAN IP. Credential-bearing URLs, queries, fragments and redirects
are rejected. Provider status reports configured/unknown without contacting the
service. Only an explicit render sends the effective spoken text. A remote
provider therefore changes the privacy boundary for that render.

```bash
lixity read-aloud --project ./novel --profile narrator --chapter 2 -o chapter-2.wav
# Per-invocation binding; does not save project settings:
lixity read-aloud --project ./novel --engine openai-compatible \
  --base-url http://127.0.0.1:8000/v1 --model your-installed-model \
  --voice your-provider-voice --language de --speed 1.0 -o reading-copy.wav
```

The adapter sends standard `model`, `input`, `voice` and `response_format="wav"`
fields. It sends `instructions` only when the profile explicitly declares
`supports_instructions=true`; this is an operator declaration, not a verified
provider capability. Unsupported direction, local reference identities and
voice descriptions fail explicitly. Voice names and model IDs are provider
values; Qwen's preset/language restrictions do not apply. The selected language
still controls Lixity's text planning; provider pronunciation support requires
auditioning. `--speech-target jetson` applies to native workers, not these URLs.

Responses are bounded to 32 MiB per segment with a 300-second request timeout.
Mono 16-bit 24 kHz WAV is accepted directly; other WAV sample formats require
FFmpeg normalization. Invalid or truncated PCM fails without publishing output.
The adapter requires no Lixity-specific response headers. External cache entries
include endpoint, model, voice, adapter identity and credential-variable name;
they never contain the key value. Request fresh audio after changing the model
behind an existing provider model ID. Existing native workers, profiles,
reference data and cache keys retain their behavior.

<a id="inspect-and-compare-externally-generated-audio-unreleased"></a>

## Inspect and compare externally generated audio

```bash
lixity audio-inspect chapter-2.wav
lixity audio-verify chapter-2.wav --plan chapter-2.timeline.json --language de
lixity audio-verify chapter-2.wav --plan chapter-2.timeline.json \
  --transcript chapter-2.words.json --language de

# Convert external ASR output (e.g. OpenAI Whisper or faster-whisper) to lixity-audio-transcript/1:
lixity audio-import-transcript chapter-2.wav whisper-output.json -o chapter-2.words.json --language de
```

`audio-inspect` and `audio-verify` emit `lixity-audio-audit/1` JSON and read the supplied files locally.
`audio-inspect` accepts optional `--plan` and `--transcript`; `audio-verify`
requires `--plan`. WAV, FLAC and MP3 are supported, with FFmpeg required for
compressed formats and WAV formats outside the standard-library PCM reader.
No recognizer or remote transcription request runs. Signal observations include
duration, sample format, per-channel/aggregate level, clipping, DC offset and
heuristic silence intervals. They are not a quality score.

Text comparison requires a supplied word-timing transcript whose `audio_sha256`
matches the exact original audio bytes:

```json
{
  "schema_version": "lixity-audio-transcript/1",
  "audio_sha256": "SHA256_OF_EXACT_AUDIO_FILE_BYTES",
  "model": "external-recognizer-id",
  "words": [
    {"text": "Hello", "start": 0.10, "end": 0.30},
    {"text": "world", "start": 0.40, "end": 0.80}
  ]
}
```

`model` is optional; absence means unknown provenance. Each `text` is one token
in the explicitly selected language. Times are finite seconds within the audio
duration, ordered and nonoverlapping. Transcript differences describe the
supplied recognition evidence, not proven missing spoken words. A missing word
has no known audio timestamp; neighboring timings only bracket its possible
location. Pause comparisons require aligned adjacent segments with no extra
transcript words between them. An observed gap can contain breathing or noise;
measured silence overlap is reported separately.

Without a transcript, text alignment and plan-pause verification remain unknown,
even when signal inspection succeeds. Source/audio mismatch, unsupported decoding
and exceeded limits fail explicitly. Core limits include 2 GiB source audio,
six hours, 500 million decoded samples, 1 GiB temporary decoded data, 16 MiB JSON,
100,000 transcript words and 10,000 plan segments; decoding has a 120-second
deadline. In **Listen & direct → Inspect external recording**, choose a WAV/FLAC/MP3
and optionally the matching transcript, then **Inspect recording**. The current
chapter/manuscript export scope supplies the plan. The browser limits audio to
96 MiB and transcript JSON to 8 MiB. It shows a bounded comparison and offers the
full audit JSON for download; it does not create a saved chapter recording. See [Methods](METHODS.md) and
[Stability](STABILITY.md) for thresholds and interpretation.

<a id="retain-or-import-chapter-audio-unreleased"></a>

## Retain or import chapter audio

A complete chapter recording can accompany the same chapter in a
[reader export](WORKSPACE.md#include-existing-chapter-recordings-unreleased). It is separate from a 1–30 second voice
reference and from a teleprompter take's optional transcript metadata.

In **Listen & direct**, select the intended chapter, open **Chapter recording**,
choose **Completed chapter WAV** and select **Import chapter WAV**. The browser
accepts at most 48 MiB. **Ready for reader export** confirms that the project
artifact was saved. Import replaces this chapter's previous recording and binds
it to the exact full manuscript revision; it does not check whether the recording
speaks that chapter or infer word/paragraph timing.

For larger recordings or scripts, use the CLI with an explicit project, chapter
and the full `source_sha256` from `audio-direction inspect`:

```sh
lixity audio-direction inspect --project ./novel
lixity audio-import --project ./novel --chapter 2 --audio chapter-2.wav \
  --source-sha256 REVIEWED_FULL_MANUSCRIPT_SHA256
```

Use `--manuscript manuscript.md` on both commands when selecting a nondefault
manuscript in that project. Import accepts complete mono/stereo 16-bit PCM WAV
at 8–192 kHz, up to 200 MiB; it does not convert MP3/FLAC or infer chapter
alignment. Source or settings changes during import reject publication.
The result uses `lixity-chapter-audio/1` JSON with the source/audio hashes,
chapter, origin and measured format/duration.

Successful browser chapter generation retains its WAV in the project. CLI
`read-aloud --project ./novel --chapter N -o chapter.wav` also retains completed
WAV output; previews, manuscript-wide renders and MP3 files do not take that
CLI retention path. Retained recordings live in `.lixity/audio/exports/`, outside the
segment cache and temporary job download. Include them in project backups.

Reader export includes only recordings matching the exact current manuscript
hash and its selected chapter range. A text change anywhere in the manuscript
makes old recordings ineligible for that new revision. Missing coverage is
reported; mismatched files are not substituted. The selected inventory has a
combined 200 MiB budget and a 1,000-chapter budget. Review each completed
recording before sharing it: a valid hash binds bytes to a revision, not spoken
fidelity or permission to distribute a voice.

## Audio status

`lixity audio-status [--project PATH] [--engine ENGINE] [--json]` inspects
registered native workers without synthesis. Engines are `qwen3`, `qwen3-design`,
`qwen3-base`, `coqui`, `coqui-reference`, `f5-tts`, `ims-toucan` and
`openai-compatible`. Qwen has local and Jetson targets; the other native engines
have local transports only. With an explicit project, it lists saved
profile identities and compares the selected profile's model with each worker. `--engine` explicitly compares a model variant
even without a saved profile. `model_matches: null` means no model identity or selected profile is known; it
is not a successful or failed match. It does not output manuscript prose, voice
descriptions, pronunciation replacements or delivery instructions. Missing or
invalid project settings fail explicitly. This is a snapshot, not a guarantee
that the worker will remain available during a later render. For a selected
external profile, status reports `configured: true`, `state: unknown` and
`model_matches: null`; it does not probe either the provider or native workers.
The browser's **Services & audio queue** shows open project views and the shared
FIFO queue: one active render and up to three waiting jobs. Cancellation and
context checks apply before queued work starts. **Ready** requires the expected
model's health response; it does not establish GPU acceleration. External-provider
status is unknown without probing, and the queue does not establish the execution
location of an external or mixed job. See [service lifecycle](USAGE.md#lixity-service)
for view lifetime and application start/restart behavior.

## Audio settings upgrades and recovery

Use the reviewed migration matching the feature you need: `/3` for Coqui,
`/4` for explicit providers, `/5` for IPA and structured prosody. Preview first,
review the snapshot, then apply with that exact token and a new backup outside
the project. The feature sections show the respective commands. Back up private
voice references and direction separately; a migration ZIP covers configuration.
Follow [configuration recovery](#audio-configuration-recovery) on a project copy.

### Replace removed Piper profiles

Piper has been removed. Existing saved Piper profiles fail with migration
guidance; a Qwen voice is not an exact replacement for their timbre or precise
speed. Preview explicit replacements before applying them:

```bash
lixity audio-migrate --project ./novel --replace narrator=Ryan
```

The command prints a JSON dry run and its `snapshot` token, without changing files.
Supply one `--replace PROFILE=VOICE` for every Piper profile; repeat the option for
multiple profiles. Optional `--instructions PROFILE=TEXT` chooses a new delivery
style explicitly; otherwise migrated instructions are empty. Review the choices,
then repeat them with the returned token and a new backup path outside the project:

```bash
lixity audio-migrate --project ./novel --replace narrator=Ryan \
  --apply --backup /backups/novel-audio-before-qwen.zip \
  --expected-snapshot REVIEWED_TOKEN
```

Migration preserves profile IDs, selected profile, names, languages, pauses and
pronunciation replacements. Speed becomes `1.0`; no timbre or exact pace equivalence
is assumed. The non-overwriting ZIP backup contains the original root configuration
files and a verification manifest, with private file permissions (`0600` on POSIX).
It contains no manuscript bytes. Keep it in private project storage: configuration
can contain private metadata and pronunciation text. Source/configuration changes
or changed replacement/style choices invalidate the reviewed snapshot. Apply verifies the backup before the atomic
settings update and never edits the manuscript. For recovery, use the
[audio configuration recovery procedure](#audio-configuration-recovery), including the check for a
newly created `lixity.toml`; do not replace manuscript or retained research files. Rendering restored Piper
settings requires a compatible prior application version.

## Troubleshooting and limits

Body paragraphs, quoted blocks and list prose use the shared Markdown text
projection. Link labels are read; destinations, images, code, footnote definitions
and YAML metadata are omitted. Long paragraphs use bounded sentence/word segments
without inserting paragraph pauses between fragments. Recognised editorial
markers are omitted unless `--keep-markers` is supplied. The manuscript is not
edited. Unknown chapters, unsupported voices and unsupported languages fail explicitly.

WAV output at speed 1.0 needs no FFmpeg; other tempo factors and MP3 output require
FFmpeg on the machine running Lixity before synthesis, including for Jetson workers.
Missing, malformed,
empty or mismatched PCM and failed conversion are errors. Streamed atomic output
preserves an existing file on failure. The native job result offers a temporary download:
WAV output is capped at 200 MiB during rendering, including inserted silence;
results are bound to the selected source/settings and selection generation, with
at most four retained jobs and a 30-minute retention window after completion.
Save the download when needed. Project/source changes invalidate old results;
returning to an earlier project cannot revive them. Model-generated omissions,
repetitions, pronunciation and expressive reading still need human review.
Successful encoding or an ASR transcript does not establish narration quality.

Completed chapter WAVs also have a separate
[retained project artifact](#retain-or-import-chapter-audio-unreleased). A temporary
job download, a cached segment and a retained chapter are different files with
different lifetimes.

| Symptom | What to check next |
| --- | --- |
| Worker unavailable or model mismatch | Refresh **Services & audio queue** or run `audio-status`; have the operator start the exact selected model through [Installation](INSTALLATION.md#optional-qwen-audio-worker). A listening port alone is not model readiness. |
| Unsupported delivery or IPA | Inspect the plan and chosen engine. Remove incompatible profile instructions explicitly; `--no-direction` removes saved passage direction only. IPA/prosody require Toucan. |
| Voice changes between segments | Compare several short directed/undirected previews. Check reference speaker, preset/description and delivery profiles; see [continuity review](#check-narration-continuity-before-a-chapter-render). |
| Source, profile or direction changed during render | Reopen the current project and inspect the updated plan, then start a new job. Context guards prevent publishing audio for stale inputs. |
| Saved passage is stale | Review the manuscript location and remove or replace the stale direction explicitly. Lixity does not relocate it by similar wording. |
| No microphone or permission denied | Use browser site/system permissions for browser capture; use **Mic & levels** for the server's hardware. See [recording recovery](#author-voice-recording-and-listening). |
| Take cannot become a reference | Check exact transcript confirmation, 1–30 second duration, 24 kHz mono 16-bit PCM and transcript length. Export and prepare an excerpt deliberately; no automatic trimming/conversion occurs. |
| Calibration or capture unavailable | Check optional host tools and the actual device/mixer; choose the device and control explicitly. Browser capture may still be available. |
| Chapter render interrupted | Start it again to reuse matching completed segments. `--fresh-audio` or the UI reuse switch requests a new interpretation; previews are always fresh. |
| CLI says audio was written but chapter retention failed | Keep the completed output, resolve the project storage/context error, and use `audio-import` with the reviewed source hash. The output may exist even though the command reports failure. |
| Audio inspection cannot compare words | Supply a timestamped transcript bound to those exact audio bytes. Signal measurements alone cannot establish word fidelity. |

