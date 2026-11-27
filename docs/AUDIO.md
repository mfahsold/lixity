# Audio, author voice and passage direction

Use audio to record your own voice, rehearse with the teleprompter, or test
optional speech synthesis on a passage or chapter. This manual covers the
desktop app, local browser app and CLI. Read the [workspace manual](WORKSPACE.md)
for project work, the [CLI reference](USAGE.md) for commands, and the
[installation manual](INSTALLATION.md#find-your-setup-task) for app and CLI setup.

> [!NOTE]
> **Feature maturity:** **Local voice recording and the Teleprompter work
> reliably today**—including microphone capture, take export/import, reference
> preparation, and rehearsing aloud with direction cues, phonetics and dossier
> context. **TTS audio generation is still evolving / experimental**: local
> speech workers (ZONOS3, IMS-Toucan, Qwen, Coqui/OpenVoice) and external
> OpenAI-compatible endpoints require optional setup, continue to evolve in
> continuity and controls, and always require human listening review.

The published v0.9.3 includes recording, passage direction, the teleprompter,
and the ZONOS3, IMS-Toucan and OpenAI-compatible adapters. This manual follows
the current checkout, where the updated audio layout, shared IPA and
alternate-spelling lexicon, profile-draft upgrade, assembly level correction,
shared preview planner, and expanded audio diagnostics are unreleased. In
v0.9.3, use profile spelling replacements or the IMS-Toucan profile's IPA
dictionary. Audio settings, direction, timeline and transcript schemas have
independent versions; check your installation with `lixity --version` and the
relevant command's `--help`.

| I want to… | Open in the workspace | Commands and details |
| --- | --- | --- |
| Record a voice or import a take | **Project → Settings → Audio and services → Record author's voice** | `audio-reference` · [Record and review](#author-voice-recording-and-listening) |
| Choose the narrator or edit pronunciation | **Project → Settings → Audio and services → Voice profiles** | [Voice profiles](#voice-profiles) · [Project pronunciations](#project-pronunciations) |
| Choose an input or check its level | **Project → Settings → Audio and services → Microphone and levels** | `audio-microphone`, `audio-calibrate` · [Microphone and calibration](#microphone-settings-and-calibration-audio-microphone-audio-calibrate-audio-reference-record) |
| Hear a paragraph or shape its delivery | **Manuscript → Listen and direct → Listen & direct** | `read-aloud`, `audio-direction` · [Passage direction](#passage-direction) |
| Render, import or review a chapter recording | **Manuscript → Listen and direct → Chapter audio** | `read-aloud`, `audio-import` · [Chapter recordings](#retain-or-import-chapter-audio) |
| Rehearse aloud with cues and record my microphone | **Manuscript → Teleprompter** | [Teleprompter](#manuscript-teleprompter-direction-cues-phonetics-and-synchronized-dossier-images) |
| Export a plan or compare an external recording | **Export direction** or **Inspect external recording** in the manuscript audio panels | `audio-export-plan`, `audio-inspect`, `audio-verify` · [Plan export](#audio-export-and-external-providers) · [Recording inspection](#inspect-and-compare-externally-generated-audio) |
| Check a service or review an audio settings upgrade | **Services & audio queue** or **Voice profiles** in project settings | `audio-status`, `audio-migrate` · [Audio status](#audio-status) · [Settings upgrades](#audio-settings-upgrades-and-recovery) |

Use `lixity read-aloud --help` or `lixity audio-reference --help` for installed
examples and action-specific options. Merely reading help never captures or
synthesizes audio.

## Getting started

1. Open a writable project. To narrate in your own voice, first [record or import
   a reference](#author-voice-recording-and-listening). In **Voice profiles**,
   choose the model, language and voice or reference, then select **Save profiles**.
2. In the manuscript, open **Listen and direct** with the headphones control.
   Choose a passage. Use **Export direction → Preview export** to check what the
   plan carries. For generated sound, configure the selected runtime or provider
   and choose **Preview paragraph**. Listen to the result before saving direction
   or rendering a chapter. [Speech setup](#choose-a-synthesis-route)
3. Switch to **Chapter audio**, choose the chapter and select **Render chapter**.
   Listen and download the WAV from the player. Open **Chapter recording** to
   check whether the project has a recording ready for reader export. [Chapter recordings](#retain-or-import-chapter-audio)

### Which recording to use

- A **paragraph preview** is temporary. Download the WAV during the current job
  if you want to keep a copy.
- A **saved voice reference** pairs a short recording with its reviewed
  transcript. A compatible voice profile can use it to synthesize new speech.
  The Teleprompter records from your microphone and leaves the take for review
  or download. Use **Author's voice** to save a reviewed excerpt as a reference.
- A **retained chapter recording** is a complete WAV for one chapter and manuscript
  revision. A successful chapter render or an explicit chapter WAV import
  retains it. A [reader export](WORKSPACE.md#include-existing-chapter-recordings)
  can include it when the manuscript and chapter still match.

### Choose a synthesis route

TTS generation is optional and still experimental; local voice recording and
the Teleprompter work without any speech model. When you do want generated
speech, choose one of these routes:

| What you want to hear | Choose | Controls available in Lixity |
| --- | --- | --- |
| Your own voice on Apple Silicon | [Local ZONOS3 through MLX-Audio](#mlx-audio-on-apple-silicon) | A saved reference, explicit pauses, model pace, and alternate spellings |
| Your own voice with specific IPA or structured delivery in German or English | [Local IMS-Toucan](#ims-toucan-author-voice-and-phonetic-direction) | A saved reference, IPA, duration, intonation and energy variation, and explicit pauses |
| Free-text direction through a service you choose | [OpenAI-compatible endpoint](#configure-an-openai-compatible-provider) | The provider's voice and model, with documented and explicitly enabled instruction support |

The workspace offers these three routes when creating a profile. Existing
[Qwen](#optional-qwen-audio-worker) and
[Coqui/OpenVoice](#coqui-and-openvoice-worker-setup) profiles keep their voice
and remain available with their configured workers. Retained profiles appear
under their own engine group. The [profile table](#voice-profiles) also covers
F5-TTS settings retained for export and cached audio.

For the CLI, inspect the plan and worker status before synthesis.

```sh
lixity read-aloud --project ./novel --preview --plan-only
lixity audio-status --project ./novel
```

Then generate a short preview and render the chapter with the selected profile.

```sh
lixity read-aloud --project ./novel --preview --speed 1.0 -o preview.wav
lixity read-aloud --project ./novel --chapter 1 --progress -o chapter-1.wav
```

Synthesis sends the effective spoken text to the selected runtime. A configured
Jetson receives it through the operator's SSH forward. An explicitly selected
remote provider receives it during rendering.

Check the prerequisites for the controls you use.

- Planning, direction editing and JSON/SSML export need no model or worker.
- Synthesis needs the exact engine's optional runtime and local model files, or
  an explicitly configured external service. Core analysis dependencies do not
  install inference models.
- MP3 output, WAV normalization and tempo postprocessing can require FFmpeg on
  the Lixity computer. Check [tempo controls](#cache-tempo-and-saved-settings) and
  the prerequisite for the selected engine before rendering.
- Browser recording needs browser microphone permission. Hardware gain and
  calibration use tools and devices on the server computer; they do not grant
  that permission or select the browser's input.
- A voice reference needs a reviewed 1–60 second mono, 24 kHz, 16-bit PCM WAV
  and the exact spoken transcript. A complete chapter recording has
  [different import limits](#retain-or-import-chapter-audio).

## `lixity read-aloud`

The CLI and audio panels compile the manuscript, narrator profiles,
pronunciation substitutions and timing into a speech plan. `audio-export-plan`
outputs an exchange timeline and `--ssml` projects compatible controls into
SSML. `read-aloud --plan-only` outputs Lixity's speech plan JSON. Explicit
providers and optional native workers use the same pause and output pipeline.

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
`--progress` reports completed segments and, after two segments,
a rough remaining-time estimate on stderr. The estimate averages completed
segments; different text lengths, cache hits and model startup can make it
inaccurate, and final encoding and publication are not included. The CLI checks manuscript,
settings and active direction snapshots during rendering and immediately before
publishing; changed or unreadable inputs reject the result and preserve an
existing output. `--no-direction` deliberately excludes the direction ledger.

The shared audio logger emits a random render ID and job/render
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
Switching an existing VoiceDesign or Base profile
to CustomVoice also requires an explicit preset, such as `--engine qwen3
--voice Ryan`. An explicitly supplied reference ID requires a reference-capable
engine. For Base, clear inherited profile instructions with `--instructions ''`; `--no-direction` only omits saved passage directions.

### Voice profiles

Choose an engine that supports the controls you need. This table describes the
adapters available in Lixity.

| Profile engine | Voice choice | Free-text delivery | IPA and structured prosody |
| --- | --- | --- | --- |
| `mlx-audio` | ZONOS3 fixed voice or saved project reference | Unsupported | Unsupported. Pace uses a model condition |
| `ims-toucan` | Saved recording, German or English | Unsupported | Supported |
| `openai-compatible` | Explicit provider model and voice | Requires declared `supports_instructions` and endpoint support | Unsupported |
| `qwen3` | CustomVoice preset | Model-interpreted | Unsupported |
| `qwen3-design` | Voice description | Model-interpreted | Unsupported |
| `qwen3-base` | Saved recording with exact transcript | Unsupported | Unsupported |
| `coqui` | German Thorsten VITS | Unsupported | Unsupported |
| `coqui-reference` | Thorsten plus OpenVoice reference conversion | Unsupported | Unsupported |
| `f5-tts` | Retained profile and compatible external local worker | Unsupported | Unsupported; bundled loader retired |

Every engine uses Lixity's literal spelling substitutions and explicit external
pauses. Tempo is FFmpeg postprocessing except for the fixed local ZONOS3 binding,
which passes `speed` into the model. These controls do not establish word fidelity,
calibrated emotion or speaker similarity.

Saved project audio profiles are shared with the CLI. **Save profiles** stores
the selected profile and its controls through the atomic project settings path.
Keep a profile selected for synthesis and plan export. Removing the last
profile requires audio settings schema `/4` or later. To remove a profile used
by a saved direction, first review or remove every reference to it, including
stale entries and directions attached to other manuscripts in the project.
Draft previews leave settings untouched. Interactive synthesis and profile
settings require a writable workspace.

The preview and chapter controls offer an explicit option to ignore passage
direction (off by default). Enabling it omits saved passage instructions,
voice assignments and range-specific pauses for that render, plus any unsaved
direction draft in the editor, without deleting or rewriting saved directions.
The selected profile's instructions, pronunciation rules, speed and standard
pauses still apply; for a Base profile, clear incompatible profile instructions
separately.

In the current checkout, the CLI and browser share one preview and direction
planner. A paragraph preview selects the target anchored passage first (up to
6,000 characters) and validates only the directions overlapping that passage.
A draft direction must match that passage's exact anchor and current manuscript
text; if the draft refers to another passage or an earlier revision, reselect
the intended paragraph before auditioning it. Full chapter renders still
validate all included directions.

```bash
lixity read-aloud --project ./novel --profile narrator -o reading-copy.wav
lixity read-aloud --project ./novel --profile narrator --chapter 2 -o chapter-2.wav
```

Choose **Render on → This computer / Configured Jetson** in the dialog,
or pass `--speech-target local|jetson` to the CLI. This choice applies to that
render; it is not part of a saved voice profile. The default is local, and an
unavailable target fails explicitly without switching machines or models.
The audio interface groups voices by preset, description or reference recording.
It displays a point-in-time worker status and compares the running model with
the selected profile when both are known. An unreachable worker is unavailable.
A missing or unrecognised model identity leaves the match unknown. Check again
before rendering if the worker has changed since the status was retrieved.
An incompatible delivery instruction remains visible when switching to Base.
Remove it before saving.
Jetson sends the selected synthesis text to your configured machine through SSH;
it does not use a hosted inference provider.

```bash
lixity read-aloud --project ./novel --profile narrator --speech-target jetson --chapter 2 -o chapter-2.wav
```

For remote worker installation, fixed ports and the SSH command, follow
[Jetson audio worker setup](#jetson-audio-worker). Qwen supports
local and Jetson targets; Coqui, Toucan and the retained F5 transport support only
their registered local target. An external profile uses its own validated URL.

### Cache, tempo and saved settings

The browser runs renders in the background and reports completed segments
without holding the initial request open. Cancellation waits for an in-flight
synthesis segment to finish, then blocks publication so any existing output is
preserved.

- **Timeouts:** Native worker requests allow up to 1 hour per segment (a limit,
  not a duration estimate); external providers allow 300 seconds per segment;
  external FFmpeg invocations allow up to 1 hour; local ZONOS3 enforces
  separate startup (120 s) and per-segment response (300 s) deadlines. Timeouts
  fail cleanly, remove temporary files, preserve existing output and record
  `error=timeout` in the [audio diagnostics](INSTALLATION.md#logs) (with ZONOS3
  distinguishing worker startup from waiting for a segment response). The
  FFmpeg deadline limits only the direct child process, not in-process
  inference or arbitrary grandchildren.
- **PCM validation and assembly:** Workers, providers, cache reads and assembly
  all enforce the same 24 kHz mono 16-bit integer-PCM WAV validation, including
  rejecting partial trailing frames. In the current checkout, assembly applies
  bounded level correction after tempo and before up to 5 ms internal edge
  fades: active 100 ms RMS windows outside −32 to −28 dBFS receive a constant
  gain of up to ±6 dB toward that band, capped at a −2 dBFS PCM sample-peak
  ceiling. Very short or low-signal segments and explicit alternate delivery
  receive peak protection only. The assembled render logs a `render_summary`
  event with segment counts, cache hits/misses, maximum applied gain,
  peak-limited segments and alternate-delivery segments; DEBUG segment events
  carry the same gain, RMS and peak figures plus a delivery flag, so level
  differences between spoken sentences can be traced in the log. Both leveling and edge fades preserve internal
  dynamics, pauses and exact sample counts; integrated loudness and
  reconstructed true peaks remain separate measurements, especially after MP3
  encoding.
- **Segment cache:** Chapter renders in the UI and CLI retain verified raw PCM
  segments (before tempo, leveling, fades and pauses) in
  `$XDG_CACHE_HOME/lixity/speech/<project-hash>/` (default
  `~/.cache/lixity/speech/<project-hash>/`), bounded to 2 GiB per project. The
  manuscript folder need not be writable. Cache reads use bounded regular-file
  I/O and verify the schema, `request_sha256`, `byte_length`, `audio_sha256`
  and PCM format before reuse. Repeating a render reuses only segments with the
  same effective spoken text, model family, language, voice/reference and
  delivery controls; pause or leveling changes do not require new synthesis.
  IMS-Toucan bundles complete sentences into fragments of up to 1,800
  characters so its per-utterance duration, pitch and energy predictions keep
  paragraph context. ZONOS3 bundles complete sentences up to the 600-character
  transport bound, below the model's default 2,000-frame generation budget.
  Qwen retains the same 600-character transport bound. Adapter boundaries are
  enforced by the transport worker; the Toucan adapter identity invalidates
  cache entries written for the former sentence-sized chunks.
  On a cache miss during rendering, Lixity re-checks shared native worker
  endpoints—if an eviction makes a mixed-model render infeasible on a shared
  worker, the render fails cleanly and preserves any existing recording (use
  profiles that share one model).

**Reuse completed chapter segments** is enabled by default; uncheck it or pass
`--fresh-audio` for a fresh interpretation:

```bash
lixity read-aloud --project ./novel --profile narrator --chapter 2 --fresh-audio -o chapter-2.wav
```

`--no-audio-cache` renders without reading or retaining segments; previews are
always fresh. The Python renderer opts in with `cache_dir=...` and accepts
`fresh_audio=True` to recompute while refreshing retained segments. Matching
segments can be reused across execution targets (request fresh audio when
comparing CPU and GPU delivery). Cache metadata stores hashes rather than raw
manuscript text, but the WAV files contain spoken project content and must be
treated as private. Missing, corrupt or evicted entries are recomputed when
the worker can serve the required model. The cache is not a saved job ledger:
after restarting the app, start a new chapter job to reuse completed work.
Temporary download expiration does not erase cached segments; delete the cache
folder or pass `--fresh-audio` after replacing local checkpoint files within
the same named model family (the key does not fingerprint model weight bytes).

The selected saved profile is used when `--profile` is omitted. Explicit `--voice`,
`--language` and `--instructions` override that invocation without rewriting the
saved profile. `--speed` applies to every profile in that render without saving
(range `0.5`–`2.0`; new implicit profiles default to `1.1`, saved profiles keep
their explicit rate, and legacy omitted rates stay `1.0`).

For Qwen and other postprocessed adapters, FFmpeg applies `atempo` to each
synthesized or cached segment into a fresh temporary output before explicit
pauses are inserted, so a previous conversion can never replace a missing or
failed segment. `1.0` leaves the audio untouched; if `atempo` returns no
samples for an extremely short segment, the original PCM is kept. The pinned
local ZONOS3 worker receives `speed` directly as its model `speaking_rate`
condition and skips FFmpeg tempo; custom MLX endpoints keep FFmpeg postprocessing
so speed is not applied twice. Neither route promises a precise linear duration ratio; compare
short previews and ASR evidence when pacing and word fidelity matter. Delivery
instructions do not guarantee a speaking rate.

A root `lixity.toml` can define a local Apple Silicon reference profile. Use the
ID returned by `lixity audio-reference create`.

```toml
[audio]
schema_version = "lixity-audio-settings/4"
selected = "narrator"

[audio.profiles.narrator]
name = "Author voice"
engine = "mlx-audio"
language = "de"
voice = "reference"
reference_id = "REPLACE_WITH_SAVED_REFERENCE_ID"
speed = 1.1
paragraph_pause = 0.45
scene_pause = 1.2
```

Profiles are project-only; user and ancestor configurations cannot supply them.
They also accept a `pronunciations` table of literal term-to-spoken-form pairs.
These substitutions affect synthesis text only; see the matching rules below.
A voice profile does not infer character identities or turn words such as “quiet” into acting instructions.

### Pronunciation substitutions

The [shared lexicon](#project-pronunciations) covers recurring words across
voices. Use **This voice profile** in **Pronunciation** for a spelling that only
one voice needs. Expand the editor to search or edit individual entries, or use
**Edit list as text** for bulk spelling replacements. Edit terms containing
`=` individually. Apply or discard the individual edit before choosing
**Save profiles**. The [IMS-Toucan IPA dictionary](#ims-toucan-phonetics-and-structured-direction)
holds phonetics specific to that voice.

#### Project pronunciations

In the checkout, open **Project → Settings → Audio and services → Voice profiles
→ Pronunciation** and choose **Whole project**. Enter the term, an **IPA
transcription**, an **Alternate spelling**, or both. Choose **Add or update
entry**, then **Save profiles**. If the project uses an earlier audio schema,
complete **Review audio settings update** first. The new lexicon uses audio
settings schema `/5`. Keep this field out of projects that still need to open in
v0.9.3, which reads profile IPA and literal spelling replacements.

These are the equivalent entries under audio schema `/5` in the project file.

```toml
[audio.pronunciation_lexicon]
schema_version = "lixity-pronunciation-lexicon/1"

[audio.pronunciation_lexicon.entries]
"Vogel" = { ipa = "ˈfoːɡəl", respelling = "Fohgel" }
```

Entries match whole terms with the same capitalization and take precedence over
overlapping literal spelling replacements. The shared lexicon accepts up to
200 terms, 100 characters per term and 300 per IPA or spelling value. IMS-Toucan
receives the IPA when available. For text-only voices, supply an alternate
spelling to use as input.
If an IPA-only term occurs with one of those voices, the render stops with an
explanation. The timeline and SSML retain the requested IPA with a warning in
that case. When the voice receives the alternate spelling, the export shows the
effective substitution. Use **Export direction → Preview export** to check
which form will be used, then audition a short preview. Enclose each complete
dictionary term within one direction range.

#### Literal spelling replacements

The original text-only project map also remains available. Audio schema
`/2` introduced this table shared by every profile:

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

## Author voice recording and listening

Open **Project → Settings → Audio and services → Record author's voice** to
open the **Author's voice** tab. Use **Mic & levels** to check the input and
**Voice profiles** to assign the saved recording to a narrator.
[Microphone setup](#microphone-settings-and-calibration-audio-microphone-audio-calibrate-audio-reference-record)

1. Choose a reading text and select **Start recording**, or import a take for
   review. The capture limit appears beside the recording controls.
2. Listen to the take and correct the transcript to the words you actually
   spoke. Confirm **I checked that this transcript matches the recording**,
   then choose **Save as author voice for this book**.
3. In **Voice profiles**, select **MLX-Audio ZONOS3 TTS** for a local reference
   on Apple Silicon, or **IMS-Toucan** for German or English with IPA and
   structured delivery. For ZONOS3 set **Voice preset** to **Project voice
   reference**. Choose the saved take in **Reference recording** and select
   **Save profiles**.
4. Check **Speech service** in the profile. In the manuscript, choose
   **Preview paragraph** and listen for omitted or repeated words, pronunciation
   and continuity. Adjust the [pronunciation](#project-pronunciations) or
   [direction](#passage-direction) and audition the passage again if needed.

Help on the controls explains their scope and limits. The shared compact player
shows elapsed and total time, play/pause, seeking, mute and volume. Its live
frequency spectrum displays measured frequency levels during playback or
recording; it is not a recording-quality score.

The short sample is selected initially. Choose the phonetic sample for a longer
read. Recordings use 24 kHz mono 16-bit PCM. Stop when you finish, or let the
recorder stop at the project's recording limit. The timer shows elapsed time and
the limit. Press Enter or Space with the record button focused to start or stop.
Saving requires at least one second. Editing the transcript clears its
confirmation. Saving and activating are separate outcomes. If activation fails,
select the saved recording in a compatible profile and save the profile. If
activation succeeds and the view reports a refresh error, reload to see the new
assignment. **Discard recording** clears the current take and its transcript.
Exported copies remain available for reimport.

In **Author's voice → Choose from recordings**, select **Delete recording** and
confirm to remove an unused recording from the project. When any saved profile
uses it, choose another recording for that profile and save the change first.

Under **Author's voice → Project recording default**, set a whole number from
1 to 60 seconds. **Change recording limit** beside the recording controls
opens the same setting. Select **Save recording limit** to apply it. Clear the
field and save to use the built-in 60-second default. The browser and desktop
recorders use the saved duration for new takes. The CLI uses the same project
override for timed voice reference recording.

The equivalent entry in the project root's `lixity.toml` is:

```toml
[audio_recording]
reference_seconds = 45
```

Use `[tool.lixity.audio_recording]` in a project `pyproject.toml`.
The setting governs capture. Reviewed reference files and SoundCraft excerpts
use the independent format bounds of 1–60 seconds.

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
The updated local workspace also reports a bounded outcome to the
[service log](INSTALLATION.md#logs). Capture, review and saving a reference
produce separate events.

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

### Trim a take locally with SoundCraft

Configure a verified [SoundCraft CLI v0.20.1 release](https://github.com/storytold/soundcraft/releases/tag/v0.20.1)
by setting `LIXITY_SOUNDCRAFT_CLI` to the absolute path of its executable before
starting Lixity. The tool is optional. For a local browser service, set the
variable when starting the service. On macOS, quit Lixity and pass it to the app
with `open -a Lixity --env "LIXITY_SOUNDCRAFT_CLI=/absolute/path/to/soundcraft-cli"`.

In **Author's voice**, record a take within the project limit or import a 24 kHz
mono PCM16 WAV of up to two minutes. Open **Trim an excerpt with SoundCraft**,
enter the start and end times and choose **Create excerpt**. The excerpt must
be shorter than the take and between 1 and 60 seconds. Lixity verifies that the rendered audio contains the
exact selected samples and keeps the original available in the review dialog.
Listen to the excerpt and enter and confirm its own transcript before saving.
The desktop and browser recorders handle microphone capture. SoundCraft only
receives the take selected for local editing in a temporary directory.
[SoundCraft headless commands](https://github.com/storytold/soundcraft/blob/v0.20.1/docs/cli.md)

## Experimental reference voices

ZONOS3 and Qwen Base both reuse immutable project voice references, but they do so
through different adapters. ZONOS3 extracts a 192-dimensional speaker embedding
from the raw recording and does not need a reference transcript at generation time.
Lixity still requires and retains the reviewed transcript because the saved project
reference is a shared, portable record used by Qwen Base and the Studio workflow.

Qwen's [Voice Design then Clone](https://github.com/QwenLM/Qwen3-TTS#voice-design-then-clone)
workflow creates a short reference with VoiceDesign and reuses it with the
separately installed Qwen3-TTS 1.7B Base model. Alternatively, record your own
voice or use another recording you have permission to use. The reference is a
recording and its exact spoken transcript, not a voice-design prompt. Lixity
accepts a 1–60 second, mono, 24 kHz, 16-bit PCM WAV and a UTF-8 transcript of
at most 2,000 characters. A recording may be longer if you select a suitable
continuous excerpt before creating the reference. Takes longer than 30 seconds
require an application and reference worker that support the 60-second limit.
For a quick setup check, 15 seconds can be enough; prefer 30–60 seconds of
continuous speech in the narration style and language you want. A longer clip
is not automatically better: trim leading silence, keep one speaker and avoid
noise gates, denoising or low-pass filtering. The voice library can show
on-demand signal notes for clipping, level, noise, digital pauses and bandwidth;
these are advisory diagnostics, not a quality score.

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
`.lixity/audio-references/`. See [private audio backup](PROJECT_BACKUP.md#back-up-private-audio-separately)
to retain its recording and reviewed transcript. The same JSON contains a `quality` object with
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

### Use a reference with ZONOS3

The fixed local MLX binding loads `mlx-community/ZONOS3-Mini` in an isolated
Python worker. It supports fixed voices and `voice = "reference"` using
the project reference ID. The worker receives only a validated temporary WAV copy;
the original record and transcript remain under `.lixity/audio-references/`.

```bash
lixity audio-reference create --project ./novel \
  --audio voice-work/reference.wav --transcript-file voice-work/reference.txt
lixity audio-status --project ./novel --engine mlx-audio --json
lixity read-aloud --project ./novel --engine mlx-audio --language de \
  --voice reference --reference-id REFERENCE_ID --speed 1.1 \
  --no-direction --preview -o author-preview.wav
```

The status command checks the isolated runtime executable and whether the MLX
checkpoint is cached. It does not load the model or expose filesystem paths. A
`ready` result establishes prerequisites only; it does not establish speech quality.
Implicit ZONOS3 profiles choose a preset from the selected language; Dutch has
no fixed preset in the pinned model and therefore requires a project reference.
At `speed=1.1`, ZONOS3 receives `speed` in `generate()`, which maps to the model's
`speaking_rate` condition. It is not exact `10%` duration arithmetic because the
model samples acoustic output; compare otherwise identical previews when duration
is part of the acceptance criterion. Explicit paragraph and scene pauses remain in
Lixity and are not changed by the model's speed value. The local worker records
bounded token/completion metadata and rejects silent, incomplete,
budget-exhausted or implausibly short output before it can enter the segment
cache. This is a truncation guard, not a speech-recognition check; listening and
text review remain necessary.

For a ZONOS3 render, use pronunciation substitutions and explicit pauses.
Keep the profile and active ranges free of text instructions, or export those
instructions for another engine. To omit all saved passage settings for one
render, including passage pauses and voice assignments, use `--no-direction`
and clear any unsupported profile instructions. Judge accent and naturalness
by listening with the author's consent.

### Use a reference with Qwen Base

Install and start the separate Base checkpoint using the
[Qwen worker setup](#optional-qwen-audio-worker). CustomVoice and
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

Open **Project → Settings → Audio and services → Microphone and levels**
(the **Mic & levels** tab). In the desktop app, the operating system supplies
the actual microphone names and identifies its default. One microphone appears
as text. With several connected microphones, choose an input for level checks
and for **Author's voice** while the manuscript workspace is open. Use
**Refresh devices** after connecting or disconnecting an input. On macOS,
adjust the input volume in **System Settings → Sound → Input** if the device
offers that control. Use **Check level** to speak briefly and see whether the
input came in low, high, in the target range or with no measurable signal.
The check measures one sample and leaves the hardware gain as set.
[macOS sound input settings](https://support.apple.com/en-euro/guide/mac-help/mchlp2567/mac)

In the browser, this tab checks the server computer’s recording hardware.
If it can identify a mixer, it shows the range and any available gain control.
After applying gain, Lixity reads the same mixer and displays the reported
value. Device rounding, rejection and an unavailable confirmation are shown
beside the gain control.
The browser uses its own microphone selection and site permission when
recording **Author's voice**. Server capture and CLI calibration use optional
local tools (`arecord`, `amixer`, `ffmpeg` or `pw-record`). Available devices
and mixer controls depend on the operating system and hardware.
The CLI accepts raw gain values from 0 to 100 within the observed mixer range.
`audio-microphone status --device DEVICE` reads that input's mixer if it can
identify a single capture control on the device. `status` and `set` also accept
an explicit card and control. Recording and calibration use the system's logical
default when `--device` is omitted.
An explicit `--device` stays bound to that input and reports failure
if it cannot be captured. A proposed gain is actionable only when it is bound to
the verified mixer. Use `lixity audio-microphone --help` for action-specific options.
The calibration command measures one test recording and suggests a gain adjustment;
it does not automatically tune the microphone or certify recording quality:

1. **Inspect hardware and set microphone gain:**
   List all detected hardware capture devices and current ALSA mixer levels:

   ```sh
   # View microphone status, active gain, and detected devices:
   lixity audio-microphone status --device 'plughw:CARD=USB,DEV=0'

   # List all audio input hardware:
   lixity audio-microphone devices

   # Set ALSA hardware gain immediately:
   lixity audio-microphone set --card USB --control Capture --gain 35
   ```

2. **Calibrate microphone gain:**
   Set the requested gain once, allow a 4-second preparation countdown, then record
   an 8-second test window:

   ```sh
   lixity audio-calibrate --device 'plughw:CARD=USB,DEV=0' --gain 35
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
   # Display the full phonetic prompt and use the project's recording window:
   lixity audio-reference record --project ./novel --calibration-text --gain 35
   ```

   Pass `--duration` to set the timed window for one command. Without it, the
   CLI uses `audio_recording.reference_seconds` if present. Its built-in defaults
   are 60 seconds for the full phonetic prompt and 15 seconds for a short prompt
   or custom transcript. The selected recording duration does not
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

The teleprompter shows the manuscript, saved direction, pronunciation cues
and linked research context as you read aloud. Recording here captures your
microphone. You can rehearse and save a portable take without a speech model.

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
   - **Typographic controls:** Adjust font size (20–56 px) with **`A−`** and
     **`A+`** or the `-`, `=` and `+` keys. Focus a toolbar control to read its
     shortcut in the tooltip.

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
   Click **Take record** (**Take aufnehmen** in German, `R`) in the prompter
   header and grant microphone access. The Desktop app uses its Rust recorder
   and stops the take automatically after 60 seconds. Browser capture stops at
   the 64 MiB portable WAV limit. The project recording default applies to
   **Author's voice** capture. Pending, recording and failed states appear
   beside the control. Stop to review the PCM WAV take.
   Playback starts only when requested.

6. **Take export, import and author-reference review:**
   Download the WAV and its matching JSON metadata, or hand the take to **Author's voice** for
   review. The `lixity-audio-take/1` JSON binds filename, SHA-256, PCM format and duration to
   a transcript marked `missing`, `draft` or `confirmed`. Import both files together to retain
   that information; a mismatched or corrupt file does not replace the current take.
   A reading script is a draft, not evidence of the words actually recorded. Review and confirm
   the exact transcript before saving a voice reference; editing it requires confirmation again.
   Voice references require 1–60 seconds of 24 kHz mono 16-bit PCM and a
   confirmed transcript of at most 2,000 characters. Download longer recordings
   as takes or prepare a selected excerpt for reference review.
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
checkpoint. Follow [Qwen checkpoint setup](#choose-the-qwen-checkpoint)
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
<a id="experimental-coqui-and-openvoice-audio"></a>

## Experimental Coqui and OpenVoice audio

Lixity can use the German Thorsten VITS voice with an optional OpenVoice V2
conversion based on a saved project-local voice reference. These are separate
optional inference dependencies; analysis does not depend on them. The model
output and any voice similarity need human listening review. Thorsten VITS is
Apache-2.0 licensed and OpenVoice V2 is MIT licensed; check the model terms for
your use. OpenVoice does not list German among its native languages, so German
conversion quality is not guaranteed.

Install and start the optional worker through
[Coqui/OpenVoice setup](#coqui-and-openvoice-worker-setup).
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
playback speed use the existing Lixity pipeline. FFmpeg applies playback speed
after synthesis. Listen at `1.0` as well as your chosen rate.
[Tempo controls and profile defaults](#cache-tempo-and-saved-settings)

The worker stays silent about the
expected discards of the phonetic tie bar, the non-syllabic mark and
typographic quotation marks, which Thorsten's vocabulary cannot represent, and
logs a count of other distinct discarded character types. Listen to the
resulting pronunciation either way. The OpenVoice step mainly changes timbre;
phrasing and intonation come from Thorsten, and the converted voice inherits the
channel of its reference, including a bandwidth limit. Check a reference
before using it through [reference inspection](#experimental-reference-voices). Profiles containing these new engine identifiers
are not readable by older Lixity versions.

<a id="retained-f5-tts-profiles-unreleased"></a>
<a id="retained-f5-tts-profiles"></a>

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
<a id="ims-toucan-phonetics-and-structured-direction"></a>

## IMS-Toucan phonetics and structured direction

`ims-toucan` combines a reviewed author recording with German or English speech,
explicit IPA pronunciation overrides, and structured prosody. The optional local
worker requires the [separate installation](#ims-toucan-author-voice-and-phonetic-direction).
It does not interpret free natural-language acting prompts. Existing instructions
remain available in plan exports; synthesis rejects them rather than ignoring them.

Upgrade earlier audio settings to `/5` through the reviewed backup dialog.
In **Voice profiles**, choose the saved recording and use **Structured
delivery** for narrator defaults. Under **Pronunciation dictionary (IPA)**, enter
one `term=IPA` line per voice-specific term. Write recurring terms in the
[project lexicon](#project-pronunciations) when they should apply across voices.
The profile dictionary permits up to 200 unique terms, with 100 characters per
term and 300 per IPA value. Use **Save profiles** for defaults and **Save passage
direction** for overrides. **Clear delivery overrides** restores inheritance.

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
must use the supported Toucan phoneme inventory. Only overrides that match the
current segment are sent to the worker. Invalid symbols, reserved control tokens
and invalid modifier order return a stable validation code before inference,
so the interface can distinguish an author-correctable pronunciation problem
from a worker runtime failure.

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
- ZONOS3 keeps the same fixed voice or saved reference throughout a render.
  Use a separate short preview to compare other takes.
- `openai-compatible` requires the same endpoint, model and provider voice.
  Delivery instructions also require explicitly declared provider support.
- `ims-toucan`, `qwen3-base`, `coqui-reference` and retained `f5-tts`
  accept a different reference as a delivery recording of the same speaker.
  Check the speaker when selecting each take. These profiles support explicit
  pauses, and IMS-Toucan also supports structured prosody.
- Different engine/language combinations, presets, voice descriptions or provider
  identities are rejected with `NarratorConflict` when they change the configured
  narrator. That check does not guarantee acoustic continuity between segments.

With IMS-Toucan, you can create a second profile from another recording of the
same narrator. Assign it explicitly in **Voice profile for this range** and
listen to the transition. Choose the delivery profile separately for each range.

## Check narration continuity before a chapter render

Select a short passage with several sentences and audition the same passage both
with and without saved direction. For example, replace `12` with a source line
inside the intended paragraph and use the local worker explicitly:

```sh
lixity audio-status --project ./novel
lixity read-aloud --project ./novel --chapter 1 --preview-line 12 --speech-target local -o preview-directed.wav
lixity read-aloud --project ./novel --chapter 1 --preview-line 12 --speech-target local --no-direction -o preview-without-direction.wav
```

Both commands need the selected local runtime and its model available.
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

1. In the manuscript reader, open a paragraph's action menu and choose
   **Passage direction**, or open **Listen and direct** with the headphones.
   The editor sits beside the paragraph on a wide screen and below it on a
   narrow screen.
2. To direct part of the paragraph, select words in **Spoken text** and choose
   **Use selected text / whole passage**. Check the displayed scope before
   editing. With no selection, this action restores the whole passage.
3. Keep the current narrator or choose a compatible delivery profile
   ([single narrator rules](#single-narrator-and-delivery-variation)). Set silence
   before or after the selection. IMS-Toucan exposes **Structured delivery**.
   For free-text direction, read the status beside the text field. When that
   engine cannot apply it, export the written instruction or clear it for
   synthesis. Calm, tension and whisper are editable starting prompts whose
   acoustic effect depends on the model.
4. Under **Export direction**, choose **Selected passage** and **Preview
   export** to inspect spoken text, voice choice, instructions and silence
   without sending text to a model. Use **Preview paragraph** to audition
   the draft. Choose **Save passage direction** to apply the change to
   future renders.
5. Save or discard the draft before directing another passage, closing the
   panel, or exporting or rendering a chapter. Switch to **Chapter audio**
   for chapter playback, retention or comparison. Profile defaults are saved
   separately in **Voice profiles**.

**Audio options** holds advanced choices for the current render, including the
execution target where available and whether to ignore saved passage direction.
The chapter panel also controls segment reuse. Export and recording comparison
have their own text scopes. Reopening the panel loads the saved defaults.

**Services & audio queue** in Project settings reports the actual model identity advertised by each available
local or Jetson worker; an unknown identity is shown as unknown. The dialog also
provides access to open projects and the audio queue.

Direction is retained in `.lixity/audio-directions.json`, separately from both
manuscript prose and `lixity.toml`. Each record binds the project-relative source,
its exact paragraph line/hash identity and a Unicode-code-point range in the
advertised spoken projection. Repeated wording at another location is a different
passage. Changed or moved paragraphs are preserved as stale records and require
explicit review/removal; they are never automatically reassigned. Overlapping
ranges and missing saved profiles fail before synthesis. The passage editor lists
stale records with explicit removal controls. To retain this private metadata
when moving a project, follow [private audio backup](PROJECT_BACKUP.md#back-up-private-audio-separately).

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
replaces that boundary's default. Lixity inserts the pause as PCM silence.

Supported controls depend on the [selected adapter](#voice-profiles). For
example, Qwen CustomVoice receives prepared text, preset speaker, language
and a separate instruction. IMS-Toucan can receive IPA and numeric prosody
controls. External endpoints receive the documented adapter fields. Listen
for word fidelity, pronunciation, continuity and delivery, especially where
a very short directed span joins the surrounding narration.

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
`audio-direction add --project ./novel --chapter 2 --line 42
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
<a id="audio-export-and-external-providers"></a>

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
From the manuscript, open **Listen and direct** and choose **Export direction
→ Preview export** in either audio tab. Choose the plan scope, review the text
and controls, then download the timeline or SSML. This can run offline with the
saved voice profile. Exports identify saved references by an internal ID.
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

### Configure an OpenAI-compatible provider

An external speech profile uses an explicit provider binding and audio settings
schema `/4` or later. For older projects, use the backed-up upgrade:

```bash
lixity audio-migrate --project ./novel --to-schema-4
# Review the preview; use its exact snapshot token and a new backup path:
lixity audio-migrate --project ./novel --to-schema-4 --apply \
  --expected-snapshot TOKEN_FROM_PREVIEW --backup ../novel-audio-schema4.zip
```

The browser offers the same review/apply step in **Voice profiles**. Its preview
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

The endpoint must expose `POST /v1/audio/speech`. Omit `api_key_env` for a
service without authentication. The rendering process
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
fields. In **Voice profiles**, enable **Provider accepts delivery instructions**
only after confirming support for the endpoint and model. This sets
`supports_instructions = true` and allows Lixity to send the `instructions`
field. Verify the result by auditioning a preview. Unsupported direction, local
reference identities and
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

## MLX-Audio on Apple Silicon

### Install the isolated MLX-Audio runtime

For local ZONOS3 synthesis or optional transcription, create a separate Python
3.11+ environment.

```sh
uv venv --python 3.11 "$HOME/.local/share/lixity/runtimes/mlx-audio"
uv pip install --python "$HOME/.local/share/lixity/runtimes/mlx-audio/bin/python" \
  'mlx-audio[stt,tts,server]'
```

For synthesis, fetch `mlx-community/ZONOS3-Mini` into the Hugging Face cache
used by the app. The synthesis worker loads it offline. If you
set `HF_HOME`, `HF_HUB_CACHE` or `XDG_CACHE_HOME`, use the same values for the
download and the Lixity process.

```sh
"$HOME/.local/share/lixity/runtimes/mlx-audio/bin/hf" download mlx-community/ZONOS3-Mini
lixity audio-status --project ./novel --engine mlx-audio --json
```

Confirm `runtime_available` and `model_cached` are true before starting a
preview. These checks inspect prerequisites. A preview tests model loading
and inference.

Lixity loads the model on the first render and reuses the worker between
segments and renders. The worker closes after five idle minutes or when its
owning app or service closes. The model returns 44.1 kHz audio for normalization.

### Choose a fixed voice or project reference

| Lixity language | Fixed voices | Reference |
| --- | --- | --- |
| `de` | `liesel`, `wolfgang` | Supported |
| `en` | `cillian`, `imogen`, `jett`, `morgana`, `rupert`, `sakura`, `savannah`, `thaddeus`, `willow`, `wyatt` | Supported |
| `fr` | `gaspard` | Supported |
| `es` | `rodrigo`, `ximena` | Supported |
| `it` | `ginevra`, `lorenzo` | Supported |
| `pt` | `leonor`, `thiago` | Supported |
| `nl` | No grouped fixed voice in the MLX checkpoint | Reference supported |

These are the intersection of the official voice groups and Lixity's complete
workspace languages, not a claim that only seven languages exist upstream. A
reference is resolved by its opaque content identity, validated and copied to a
private temporary directory for each segment. The temp copy is removed when the
worker returns. In the checkout the warm worker can reuse its most recent
speaker embedding when the reference WAV bytes match and the model exposes the
embedding interface. Lixity stores the exact reviewed transcript in the reference
record. The ZONOS3 binding sends the audio itself for voice conditioning.

```bash
lixity read-aloud --project ./novel --engine mlx-audio --language de \
  --preview --plan-only
lixity read-aloud --project ./novel --engine mlx-audio --language de \
  --preview --speed 1.1 -o preview.wav
```

For ZONOS3, Lixity sends `speed` directly to the model as its `speaking_rate`
condition. The profile default is `1.1`. Lixity assembles explicit pauses
separately. The supported controls in this adapter are listed under
[Voice profiles](#voice-profiles). Test short previews before chapter rendering
to check duration, accent and continuity.

### Run local transcription

For optional transcription, run the MLX-Audio HTTP service in the isolated
environment.

```sh
"$HOME/.local/share/lixity/runtimes/mlx-audio/bin/python" -m mlx_audio.server \
  --host 127.0.0.1 --port 8000
```

For German speech recognition, send one selected audio file to this local
service with Parakeet v3. Convert the normalized word timings for comparison.

```bash
lixity audio-transcribe chapter-2.wav --language de -o chapter-2.asr.json
lixity audio-import-transcript chapter-2.wav chapter-2.asr.json --language de \
  -o chapter-2.words.json
lixity audio-verify chapter-2.wav --plan chapter-2.timeline.json \
  --transcript chapter-2.words.json --language de
```

Transcription is an explicit request to the configured service, limited to a
200 MiB input and a 16 MiB JSON response. If MLX-Audio returns Parakeet sentence
tokens, Lixity retains a flat word list for the import step. Missing timestamps
are not invented. `audio-transcribe` exposes the external evidence; it does not
certify transcription fidelity, and its process does not become a source-writing
or manuscript-editing step automatically.

<a id="inspect-and-compare-externally-generated-audio-unreleased"></a>
<a id="inspect-and-compare-externally-generated-audio"></a>

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
deadline. In **Chapter audio → Inspect external recording**, choose a WAV/FLAC/MP3
and optionally the matching transcript, then **Inspect recording**. The current
chapter/manuscript export scope supplies the plan. The browser limits audio to
96 MiB and transcript JSON to 8 MiB. It shows a bounded comparison and offers the
full audit JSON for download; it does not create a saved chapter recording. See [Methods](METHODS.md) and
[Stability](STABILITY.md) for thresholds and interpretation.

<a id="retain-or-import-chapter-audio-unreleased"></a>
<a id="retain-or-import-chapter-audio"></a>

## Retain or import chapter audio

A complete chapter recording can accompany the same chapter in a
[reader export](WORKSPACE.md#include-existing-chapter-recordings). To generate
one, open **Chapter audio**, select the chapter and choose **Render chapter**.
The player appears when the result is ready. Listen through the chapter and
download its WAV for an external review if needed.

In **Chapter audio**, select the intended chapter, open **Chapter recording**,
choose **Completed chapter WAV** and select **Import chapter WAV**. The browser
accepts at most 48 MiB. **Ready for reader export** confirms that the project
artifact was saved. Import replaces this chapter's previous recording and binds
it to the exact full manuscript revision; it does not check whether the recording
speaks that chapter or infer word/paragraph timing.

**Discard file selection** clears a WAV chosen for import. **Delete chapter
recording** removes the saved recording shown for the selected chapter from
the project after confirmation. Existing exports and the original imported
file keep their copies.

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
CLI retention path. Retained recordings live in `.lixity/audio/exports/`. Copy
them with their metadata using [private audio backup](PROJECT_BACKUP.md#back-up-private-audio-separately).

Reader export includes only recordings matching the exact current manuscript
hash and its selected chapter range. A text change anywhere in the manuscript
makes old recordings ineligible for that new revision. Missing coverage is
reported; mismatched files are not substituted. The selected inventory has a
combined 200 MiB budget and a 1,000-chapter budget. Review each completed
recording before sharing it: a valid hash binds bytes to a revision, not spoken
fidelity or permission to distribute a voice.

## Native speech worker setup

Use a separate runtime for your chosen worker. Start it locally and check its
model with [Audio status](#audio-status) before rendering a paragraph.

<a id="native-audio-model-lifecycle-unreleased"></a>
<a id="native-audio-model-lifecycle"></a>

### Native audio model lifecycle

Qwen (all three variants), Coqui/OpenVoice and IMS Toucan share one worker
lifecycle. Starting a worker binds its loopback service and validates local
settings/assets without importing the inference stack or loading weights. The
first validated synthesis request loads the model in an owned child process.
Keep the worker's separate optional environment and complete local checkpoints.

The default idle interval is **300 seconds after the last completed synthesis**.
The child exits after that interval, releasing model allocations and its inference
runtime. Active synthesis is protected; subsequent requests reuse a resident
model and start a new interval only after completion. Health/capability probes
neither load the model nor extend the interval. The lightweight service remains
available. The next render can therefore take longer while the model loads.

Configure the same option on every supported worker, for example:

```sh
python -m lixity.speech_qwen --model /path/to/CustomVoice --idle-timeout-seconds 900
```

`--idle-timeout-seconds` accepts finite values from 0 to 86400; 0 releases the
model after each completed request. Persist the option in the worker's service
command and restart that worker after changing it. This is shared worker policy,
not a project profile or a setting inferred from whichever manuscript is open.
Existing explicit library loaders remain available to callers that own a model.

`GET /health` distinguishes service readiness (`ready`) from residency
(`model_state`: `unloaded`, `loading`, `loaded`, `failed`), reports `active` and
actual `idle_timeout_seconds`, and includes resolved `runtime` metadata only
while a loaded renderer supplies it. Cold asset validation checks local files;
checkpoint integrity, optional dependencies and hardware compatibility are
resolved on first synthesis. A failed load/render is explicit and a subsequent
request can retry in a fresh child. No checkpoint is downloaded automatically.

### Optional Qwen audio worker

The Qwen worker supports `Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice` and separate
VoiceDesign and reference-based Base checkpoints. The application and CLI share
the same project profiles and rendering controls.

Run the loopback-only worker explicitly on this computer, or on a configured
Jetson reached through an authenticated SSH forward. Neither target is an
automatic fallback. Start with a short preview and verify actual synthesis and
memory headroom; model size and machine memory do not establish throughput.
Install FFmpeg on the Lixity computer for MP3 export and Qwen tempo changes.
[Tempo controls and profile defaults](#cache-tempo-and-saved-settings)

For a project with Piper profiles, use the reviewed migration before rendering.
[Replace removed Piper profiles](#replace-removed-piper-profiles)

Qwen runs in an optional isolated Python 3.12 environment with `qwen-tts` and a
hardware-appropriate PyTorch installation. Install the same Lixity version as
the browser app in that environment. For a published package, replace `VERSION`
in `python -m pip install 'lixity==VERSION'` with your version. For a source build,
use `python -m pip install /path/to/lixity-checkout` with your checkout. Obtain the
complete local CustomVoice checkpoint, including its speech tokenizer, using the
[upstream setup instructions](https://github.com/QwenLM/Qwen3-TTS). Choose the CPU
build of PyTorch for CPU-only use. Neither opening Lixity nor starting the worker
downloads weights or sends manuscript text to an inference provider.

Start the worker explicitly from that environment:

```bash
python -m lixity.speech_qwen --model /path/to/CustomVoice --device cpu --threads 1
```

It binds only to `127.0.0.1:8769` and serializes synthesis through the
[shared on-demand lifecycle](#native-audio-model-lifecycle). CPU operation
supports full chapters. Generation can be much slower than the
result's duration, so use a short preview to choose the voice. Match Torch threads
to the CPU budget assigned to the worker. A heavily throttled four-thread worker
can waste time contending within a one-core quota. Keep workstation CPU/memory
headroom through the operating system rather than silently reducing model size. GPU operation is
optional via `--device cuda`, with an explicit error when unavailable. Worker-only `--attention auto|eager|sdpa` selects the attention implementation.
The default `auto` uses eager attention on CPU and SDPA on CUDA. An operator can
compare an explicit override on the same checkpoint and workload; measure actual
synthesis, memory and output before selecting it. This flag does not establish a
performance improvement and cannot be set by browser input or a voice profile.

On a memory-constrained CUDA machine, an operator can explicitly keep the
talker on the GPU and run audio decoding on the CPU with the same checkpoint:

```bash
python -m lixity.speech_qwen --model /path/to/CustomVoice --device cuda --codec-device cpu --threads 4
```

The default `--codec-device model` keeps the decoder on the selected main device.
Worker-only `--codec-chunk-frames N` accepts 16–300 audio-code frames. The default
300 preserves the installed upstream decoder behavior. A smaller explicit value
uses that decoder's existing chunk algorithm with its 25-frame left context;
it can reduce per-chunk activation memory without changing model weights.
For example, test `--device cuda --codec-device model --codec-chunk-frames 32`
on the actual machine before adopting it. Unsupported decoder interfaces fail
explicitly. Chunking does not bound all model, KV-cache or output allocations,
and this option does not guarantee that a checkpoint fits in RAM.

CPU decoding uses float32 and trades GPU allocations for CPU work; this is an
explicit machine setting, not a voice profile or an automatic fallback. Shared
RAM remains finite. Suitable SSD-backed swap is a separate operating-system
decision; see [NVIDIA's Jetson memory guidance](https://www.jetson-ai-lab.com/tutorials/ram-optimization/).
Validate actual synthesis and memory headroom before scheduling long jobs.

#### Choose the Qwen checkpoint

CustomVoice, VoiceDesign and Base are separate checkpoints. Use a complete local
checkpoint with its tokenizer and the corresponding worker variant:

```sh
python -m lixity.speech_qwen --variant voice-design --model /path/to/VoiceDesign --device cpu --threads 4
python -m lixity.speech_qwen --variant base --model /path/to/Base --device cpu --threads 4
```

These are alternatives, not commands to run simultaneously. Check that no audio
job is active, stop the previous worker through its process manager, and start
the selected variant. All use `127.0.0.1:8769`; changing a profile does not switch
the running model. Check with `lixity audio-status --engine qwen3-base` (or the
matching engine), then follow [reference voices](#experimental-reference-voices)
for the first short test. No checkpoint is downloaded automatically.

### Jetson audio worker

Machine setup is explicit: run the same Qwen worker on the Jetson with its
supported CUDA environment and complete local checkpoint. Keep that worker on
`127.0.0.1:8769` there, and forward laptop port `8770` over authenticated SSH:

```bash
ssh -N -T -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 \
  -o ServerAliveCountMax=3 -L 127.0.0.1:8770:127.0.0.1:8769 USER@JETSON
```

Use your normal verified SSH host key and account. The local CPU worker continues
to use port `8769`; selecting Jetson uses only the fixed loopback forward `8770`.
These native target values cannot supply a host address or inference URL; external
providers use their separately validated explicit profile bindings. Lixity does
not install or start the remote worker or SSH connection. GPU compatibility and
available shared memory must be checked on the actual device; 8 GB does not
guarantee that every input fits.

### Coqui and OpenVoice worker setup

Set up a separate Python environment following the
[maintained Coqui installation guide](https://coqui-tts.readthedocs.io/en/latest/installation.html).
Install `coqui-tts`, matching CPU versions of `torch` and `torchaudio`,
`gruut[de]`, and this Lixity checkout in that environment. For example, this
isolated CPU setup was tested on Linux ARM64:

```sh
uv venv --python 3.11 /path/to/coqui-env
uv pip install --python /path/to/coqui-env/bin/python --torch-backend cpu \
  'torch==2.8.0' 'torchaudio==2.8.0' 'coqui-tts==0.28.0' 'gruut[de]' -e /path/to/lixity
```

For other PyTorch/Coqui versions, check the upstream requirements (including
`torchcodec` where required) before changing this tested combination. Obtain the
[Thorsten VITS model](https://huggingface.co/Thorsten-Voice/VITS) and the
[OpenVoice V2 converter](https://huggingface.co/myshell-ai/OpenVoiceV2/tree/main/converter)
and keep their complete local model directories. Model downloads are an explicit
setup step. The worker does not download models or send manuscript text or
references over the network.

After ensuring no active audio job uses the local worker, start one of these
workers on the same loopback port used by Qwen:

```sh
/path/to/coqui-env/bin/python -m lixity.speech_coqui --model /path/to/thorsten-vits
/path/to/coqui-env/bin/python -m lixity.speech_coqui --model /path/to/thorsten-vits --converter /path/to/OpenVoiceV2/converter
```

The Thorsten directory must contain `model_file.pth` and `config.json`; the
converter directory must contain `checkpoint.pth` and `config.json`. The first
command serves `coqui`, the second `coqui-reference`. Start only one worker at
a time. A reference profile uses `voice = "reference"` and an existing
`reference_id`; a Thorsten profile uses `voice = "thorsten"`. Both require
`language = "de"`. Select the matching profile in the UI or use `--engine` on
the CLI. `audio-status --engine coqui-reference` checks the actual worker.

For settings migration, recording requirements and a first preview, continue with
[Coqui/OpenVoice operation](#experimental-coqui-and-openvoice-audio).

### IMS-Toucan author voice and phonetic direction

The optional `ims-toucan` worker supports German and English with
an explicitly saved author reference, IPA overrides and structured prosody. It
runs in its own environment on local loopback port **8772**. CPU inference is
supported. Check speed and speaker similarity on the intended computer with
the intended recording.

Use a separate Python 3.11 environment and an eSpeak-NG shared library. The
previous inference recipe used PyTorch 2.4.1, which is affected by CVE-2025-32434
even with `weights_only=True`. The current worker checks for a stable PyTorch
release at or above 2.6.0 before loading checkpoints. Select a patched
PyTorch and TorchAudio pair for the platform. Treat the environment as
operator-managed until the complete dependencies and a render are verified
together. [PyTorch advisory](https://github.com/pytorch/pytorch/security/advisories/GHSA-53q9-r3pm-6pq6) ·
[TorchAudio compatibility matrix](https://docs.pytorch.org/audio/stable/installation.html)

The previously tested upstream IMS-Toucan checkout used revision
`3cc2094d9c7123336eda7e299ac0bc90319ca9ff`. Its acoustic assets were
`ToucanTTS.pt` and `Vocoder.pt` from `Flux9665/ToucanTTS` at revision
`e0afe0ef703d2178dd7dc74ec298693ddb10e720`. Its speaker assets came from
`speechbrain/spkrec-ecapa-voxceleb` at revision
`0f99f2d0ebe89ac095bcc5903c4dd8f72b367286`. Keep `hyperparams.yaml`,
`embedding_model.ckpt`, `classifier.ckpt`, `mean_var_norm_emb.ckpt` and
`label_encoder.txt` together in the speaker directory. A macOS Apple Silicon
CPU check used Python 3.11, PyTorch and TorchAudio 2.8.0 and SpeechBrain 1.1.2
with these assets. Verify the provenance of your local source, model and
speaker configuration before use. The worker expects a local copy of every
file and disables Hugging Face network access during startup.

Install the Lixity package or the checkout in the isolated environment so
that its Python can run `lixity.speech_toucan`. Point the worker at the prepared
source tree, acoustic directory and complete speaker directory.

```sh
TOUCAN_ENV="$HOME/.local/share/lixity/runtimes/toucan-venv"
TOUCAN_SOURCE="$HOME/.local/share/lixity/runtimes/IMS-Toucan"
TOUCAN_MODELS="$HOME/.local/share/lixity/models/toucan"
"$TOUCAN_ENV/bin/python" -m lixity.speech_toucan \
  --source "$TOUCAN_SOURCE" --model "$TOUCAN_MODELS/acoustic" \
  --speaker "$TOUCAN_MODELS/speaker" --device cpu --threads 4
```

If the library is installed outside the system search path, set
`PHONEMIZER_ESPEAK_LIBRARY` to its actual shared-library file. Missing eSpeak,
unknown IPA symbols and incomplete checkpoints fail explicitly; the adapter never
falls back to a downloaded phonemizer or silently drops unsupported phones.
The reference acoustic and speaker assets total approximately 395 MiB,
excluding Python packages.
Check the service with `lixity audio-status --engine ims-toucan`.

Continue with the [phonetics and direction workflow](#ims-toucan-phonetics-and-structured-direction)
to create a matching reference profile and audition a paragraph.

The upstream code and published Toucan/ECAPA weights are labeled Apache-2.0.
The Toucan maintainers discuss a training-data provenance question in
[issue 174](https://github.com/DigitalPhonetics/IMS-Toucan/issues/174); this setup
records the published licenses and does not resolve that separate question.

## Audio status

`lixity audio-status [--project PATH] [--engine ENGINE] [--json]` inspects the
selected engine without synthesis. Use `audio-status --help` for the installed
engine choices. With `--project`, status lists saved profile identities and
compares the selected profile's model against the relevant worker. Use `--engine`
to inspect a model explicitly. Qwen has local and Jetson targets. Other native
engines have local transports. `model_matches: null` means the comparison is
unknown. Missing or invalid project settings return a diagnostic. The result
omits manuscript prose and private delivery and pronunciation text.

The `mlx-audio` check uses the isolated runtime and local checkpoint cache for
the fixed [ZONOS3 binding](#mlx-audio-on-apple-silicon). Native HTTP workers
report model identity and residency through their health response. Use a render
to verify inference with the reported model. For an `openai-compatible` profile,
Lixity reports the configuration and leaves readiness unknown until synthesis.

The browser's **Services & audio queue** shows open project views and the
shared FIFO queue with one active render and up to three waiting jobs.
Cancellation and context checks apply before queued work starts. The queue can
leave the execution location of an external or mixed job unknown. See
[service lifecycle](USAGE.md#lixity-service) for view lifetime and application
start/restart behavior.

## Audio settings upgrades and recovery

The minimum settings format is `/3` for Coqui, `/4` for explicit providers and
`/5` for IPA, structured prosody and the shared pronunciation lexicon. Upgrade
only if your current settings are
older than the format you need. Preview the candidate, then apply with its exact
snapshot token and a new backup outside the project. The migration ZIP covers
configuration. Use [private audio backup](PROJECT_BACKUP.md#back-up-private-audio-separately)
for recordings and directions and [configuration recovery](#audio-configuration-recovery)
to check the restored settings in a project copy.

In the development checkout, **Review update** and **Apply reviewed audio
upgrade** can keep an unfinished profile open while updating the saved format.
Choose **Save profiles** afterwards to retain the pending edits. In v0.9.3,
copy any unsaved profile text before discarding that draft, apply the format
upgrade, then reopen **Voice profiles** and enter the changes again.

An upgraded profile still needs its matching synthesis runtime. Check **Speech
service** in **Voice profiles** and follow its setup guide if the local worker
is unavailable. Preview a short passage before rendering the chapter.

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

This section owns recording, voice-profile, direction and synthesis failures.
For install/service failures see [installation troubleshooting](INSTALLATION.md#troubleshooting).

Body paragraphs, quoted blocks and list prose use the shared Markdown text
projection. Link labels are read; destinations, images, code, footnote definitions
and YAML metadata are omitted. Long paragraphs use bounded sentence/word segments
without inserting paragraph pauses between fragments. Recognised editorial
markers are omitted unless `--keep-markers` is supplied. The manuscript is not
edited. Unknown chapters, unsupported voices and unsupported languages fail explicitly.

Writing mono 16-bit PCM WAV at 24 kHz needs no conversion. Install FFmpeg on the
Lixity computer for MP3 output, WAV normalization (including ZONOS3's 44.1 kHz
output) and post-synthesis tempo. Missing, malformed, empty, truncated or
mismatched PCM and failed conversion fail cleanly while preserving any existing
output. See [Cache, tempo and saved settings](#cache-tempo-and-saved-settings)
for level correction, edge fades and timeout limits.

WAV output is capped at 200 MiB during rendering, including inserted silence;
browser jobs offer a temporary download tied to the selected source, settings,
and selection generation, with at most four retained jobs and a 30-minute
retention window after completion. Save the download when needed.
Project/source changes invalidate old results; returning to an earlier project
cannot revive them. Model-generated omissions, repetitions, pronunciation and
expressive reading still need human review; successful encoding or an ASR
transcript does not establish narration quality.

Completed chapter WAVs also have a separate
[retained project artifact](#retain-or-import-chapter-audio). A temporary
job download, a cached segment and a retained chapter are different files with
different lifetimes.

| Symptom | What to check next |
| --- | --- |
| Worker unavailable or model mismatch | Refresh **Services & audio queue** or run `audio-status`. Confirm the worker serves the exact selected model, then test a short render. [Worker lifecycle](#native-audio-model-lifecycle) |
| Unsupported delivery or IPA | Inspect the plan and selected voice. Use IMS-Toucan for IPA and structured prosody or supply an explicit alternate spelling for a text-only voice. Clear incompatible profile instructions separately. `--no-direction` skips passage instructions, voice assignments and pauses for one render. |
| Voice changes between segments | Compare several short directed/undirected previews. Check reference speaker, preset/description and delivery profiles; see [continuity review](#check-narration-continuity-before-a-chapter-render). |
| Source, profile or direction changed during render | Reopen the current project and inspect the updated plan, then start a new job. Context guards prevent publishing audio for stale inputs. |
| Saved passage is stale or draft does not match preview | Review the manuscript location and remove or replace the stale direction explicitly; for a preview draft, reselect the intended paragraph before auditioning. Lixity does not relocate directions by similar wording. |
| Render or conversion timed out (`error=timeout`) | Check the [service log](INSTALLATION.md#logs). For ZONOS3, the error distinguishes worker startup (120 s) from per-segment response (300 s); for FFmpeg, check input size and host load. Existing output is preserved. |
| No microphone or permission denied | Use browser site/system permissions for browser capture; use **Mic & levels** for the server's hardware. See [recording recovery](#author-voice-recording-and-listening). |
| Take cannot become a reference | Check exact transcript confirmation, 1–60 second duration, 24 kHz mono 16-bit PCM and transcript length. Prepare an excerpt if needed. [Trim with SoundCraft](#trim-a-take-locally-with-soundcraft) · [Prepare a reference file](#experimental-reference-voices) |
| Calibration or capture unavailable | Check optional host tools and the actual device/mixer; choose the device and control explicitly. Browser capture may still be available. |
| Chapter render interrupted or cache evicted mid-render | Start the render again to reuse matching completed segments. If a cache eviction makes a mixed-model render infeasible on a shared worker, use profiles that share one model. `--fresh-audio` or the UI reuse switch requests a new interpretation; previews are always fresh. |
| CLI says audio was written but chapter retention failed | Keep the completed output, resolve the project storage/context error, and use `audio-import` with the reviewed source hash. The output may exist even though the command reports failure. |
| Audio inspection cannot compare words | Supply a timestamped transcript bound to those exact audio bytes. Signal measurements alone cannot establish word fidelity. |

### Match an audio failure to a log entry

Open the browser's Network inspector, reproduce the problem and read
`X-Lixity-Diagnostic-Id` on the audio POST response. For a render that later
fails, start with the request that submitted it. Browser microphone failures
before a request appear in the browser console. See [service logs and audio
diagnostics](INSTALLATION.md#logs) for the log location and event meanings.

