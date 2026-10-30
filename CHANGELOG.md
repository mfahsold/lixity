# Changelog

All notable changes to Lixity are documented in this file.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/);
this project uses [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Standard W3C SSML export (`plan_to_ssml`, `read-aloud --plan-only --ssml`, and
  browser dialog SSML download) to position Lixity as an author's dramaturgy,
  phonetic direction and speech-timeline workbench for external open-source TTS
  engines (OpenedAI Speech, Kokoro, Chatterbox, AllTalk, F5-TTS).
- `audio-reference inspect` and a `quality` object in `audio-reference create`
  report level, noise floor, clipping and spectral bandwidth of a voice
  reference (`lixity-audio-reference-quality/1`), with uncalibrated heuristic
  notes for band-limited, gated, clipped or noisy recordings; formulas in
  `docs/METHODS.md`, limits in `docs/STABILITY.md`.
- Experimental local German Coqui Thorsten VITS audio and optional OpenVoice V2
  reference-voice conversion, reusing project references and speech planning;
  saved profiles require audio schema `/3` and a reviewed backed-up migration.
- An explicit per-render control in the audio dialog to ignore passage direction
  for a preview or chapter without modifying saved direction.
- Privacy-preserving audio diagnostics for job lifecycle and render segments,
  including independent diagnostic IDs and PCM timeline positions.
- Optional project-wide pronunciation rules in audio settings schema `/2`, with
  per-profile overrides and opt-in whole-word/case-insensitive matching; `/1`
  remains unchanged and version 0.7.7 cannot read `/2`.
- `audio-direction add` resolves chapter and source line to a guarded passage
  direction without manually supplying snapshot hashes.

### Changed
- Coqui/OpenVoice guidance states that the converter mainly changes timbre,
  inherits the reference's bandwidth limit and that the 1.2 playback default is
  not tuned for Thorsten.
- Installation guidance explains same-version checkout/tool drift, verified local
  wheel replacement, preservation of optional dependencies and scoped cleanup.
- Audio guidance now follows the selected engine, distinguishing Coqui's local
  runtime and direction limits from Qwen-specific behavior.
- Native audio previews now include all planned segments of the first anchored
  paragraph, enforce the same 6,000-character preview limit as selected passages,
  and fail explicitly when no paragraph or list item can be selected. The
  bounded context excerpt identifies the selected original passage; `truncated`
  is false when that passage is fully rendered, even if its display excerpt is
  abbreviated. Chapter rendering is unchanged.
- Documented the local recording, excerpt, transcript and short preview workflow
  for an explicit Base reference voice.
- CLI, audio dialogs and guidance clarify VoiceDesign continuity, the role of
  passage direction and the trade-offs of reference-based voices.
- CLI audio progress includes a rough remaining-time estimate after two segments.
- Counted-text visibility is remembered per analysis measure; the chapter-strip
  emphasis control and comparison counts use descriptive, neutral labels.
- Tense-pattern badges no longer overlap an active metric overlay; the passage
  inspector and chapter counts follow the configured tense severity threshold.
- The audio dialog distinguishes opening chapter output from starting its render
  and keeps progress and error messages visible while scrolling.

### Fixed
- Coqui worker no longer warns about the expected discard of the phonetic tie
  bar, non-syllabic mark and typographic quotation marks; other discarded
  characters are reported by code point only.
- CLI messages for `--reference-id`, missing references and delivery
  instructions named only Qwen Base although `coqui-reference` uses the same
  controls.
- Reloading a workspace notices external project configuration changes and
  refreshes its context token without overwriting a concurrent change.
- Qwen Base reports incompatible passage text direction with an actionable,
  localized message; ignoring direction remains an explicit per-render choice.

## [0.7.7] - 2026-10-28

### Added
- Reference-based Qwen3-TTS 1.7B Base voices: explicit private project-local
  WAV/transcript references, guarded CLI and browser profiles, reference-bound
  segment caching and explicit per-passage voice selection. Base rejects delivery
  instructions it cannot interpret; it does not infer character speakers.
- Post-synthesis FFmpeg tempo factors for Qwen audio, preserving explicit pauses
  and unmodified cached model segments. New default profiles use 1.2; existing
  saved or formerly omitted values retain their previous meaning.
- Opt-in corpus evaluation of German quotation cues against the separately
  obtained REDEWIEDERGABE corpus and French syllables against Lexique; neither
  corpus is bundled or a representative contemporary literary benchmark.
- The UD token-feature checker reports aligned finite-verb true/false positives,
  false negatives and coverage separately, including false positives on gold
  nonverbs; previous tense-feature denominators remain unchanged.
- Optional local PhonItalia 1.10 benchmark reports aggregate Italian syllable
  agreement and the source digest without bundling or downloading the lexicon.
- Reader websites can explicitly include selected chapter or language
  measurements, or a fuller analysis of capped chapters. Opt-in exports use
  `lixity-read-only-site/2`; the synthetic reader demo shows chapter measurements.
- CLI audio status, fresh paragraph previews by source line and opt-in segment
  progress; long renders reject changed source, settings and active direction.
- Experimental Qwen3-TTS 1.7B VoiceDesign profiles with an explicit voice description, separate model identity and a shared CLI/native audio path. The matching offline worker must be started explicitly.
- Model-independent project-local passage direction with exact paragraph/range
  anchors, saved voice selection, free-form delivery, explicit PCM pauses,
  stale/overlap guards and idempotent atomic saves. CLI `audio-direction`,
  `read-aloud --plan-only` and the seven-language native Audio dialog share one
  planner for previews and chapter renders; Qwen retains its existing full model.

### Changed
- Dossier edit files accept LF and CRLF control headers without changing the
  saved body, including on Windows.
- Passage review links back to its exact saved decision; unmatched decisions
  for the current manuscript are reported and retained in UI and CLI.
- The normal-model threshold expectation is labeled as a model reference,
  not an empirically established count of false findings.
- Tagged releases run reusable full source and browser checks on the same
  commit before publication. Local and cross-platform checks remain separate.
- Style JSON schema 5 replaces the misleading exchangeability verdict and
  averaged lag with nullable, per-feature order indicators and chapter coverage.
  Missing chapters are not treated as adjacent; segmentation reports missing
  data and distribution comparisons preserve the original chapter midpoint.
  Zero-MAD references no longer create artificial standardized scores or enter
  consistency and FDR; available ordinal contrasts are retained separately.
  Flags remain exploratory.
- Showing comparisons with fewer than three sufficiently long chapters now
  report unavailable component scores and means instead of artificial zeros;
  their raw chapter measurements remain available.
- Research source analysis counts only available standardized comparisons in
  its baseline coverage; zero-MAD features are excluded.
- The default German tense heuristic no longer guesses past tense from arbitrary
  `-te/-ten/-test` endings, avoiding adjective false positives; selected cues
  such as `übt` are added. Unlisted regular past forms may now be missed and
  other ambiguities remain. Recompute comparisons; retained observations with
  saved decisions become stale, while disappeared observations are unmatched.
  Existing review storage is preserved.
- Reading website export retains choices within the current project context,
  clears source-file consent when the profile changes and rejects stale downloads.
- Pronunciation replacements can be filtered and edited individually, with
  explicit save/discard protection for project audio drafts. Speech control
  semantics and Qwen adapter capability declarations share one implementation.
- German paragraph-layer reports localize their explanations. Empty selections
  explain actual chapter comparison limits and show a shell-quoted command for
  full evidence; versioned JSON contracts and measurements remain unchanged.
- Audio extraction retains full-source line identities and configured chapter
  boundaries. Direction is resolved before pronunciation replacement and input
  segmentation; multiline delivery instructions normalize to single-line text.

## [0.7.6] - 2026-10-27

### Added
- Explicit Qwen attention and bounded codec-chunk controls, inference-mode
  execution and non-sensitive resolved worker runtime diagnostics for measured
  CPU/CUDA tuning of the same full 1.7B checkpoint.
- Explicit offline grammatical tense analysis in seven languages with installed
  spaCy models or explicit French/Italian Stanza CPU profiles,
  central verb-group composition, chapter-bounded quotation scope, exact evidence,
  model/version review identities and explicit unresolved forms. Scientific
  verification tools distinguish UD token-feature checks from verb-group tests. CLI, native UI,
  scenes and exports share the same implementation; no model download or fallback.
- One-origin native project views with independent tab contexts, scoped API and
  artifact routes, explicit expired-view handling and a bounded shared audio FIFO.
- Native app/audio operational overview with actual local/Jetson model health
  probes, open views and content-free queue states.
- Passage-specific tense review with exact counted cue ranges from the shared
  backend, keyboard-accessible cue navigation and explicit unavailable mappings.
  Mixed/switch triggers precede collapsed counts, help and other paragraph values.
- Explicit worker-only CPU decoder placement for CUDA Qwen inference, retaining
  the same 1.7B checkpoint and portable voice profiles without automatic fallback.
- Per-render local/Jetson Qwen selection in the CLI and native audio dialog,
  using fixed loopback endpoints and an operator-configured SSH forward without
  embedding machine addresses in portable project voice profiles.
- Shared bounded Qwen segment reuse for retrying long CPU renders in the CLI and
  native chapter dialog, with explicit fresh-render controls. Completed segments
  survive failed/cancelled runs; previews remain fresh and final output stays atomic.
- Project-only audio profiles shared by CLI and the native Audio & voices dialog,
  with explicit narrator presets, supported delivery controls, pauses and literal
  pronunciation settings. Draft previews, saved-profile selection and cancellable
  chapter jobs use one validated backend path; read-only snapshots cannot render.
- Optional offline Qwen3-TTS 1.7B CustomVoice worker with explicit CPU/CUDA modes,
  bounded local transport and no automatic model download or backend fallback.
- Single-commit publication batching in `reconcile-manuscript` (parsing manuscript
  paragraphs once and committing all accepted link updates in one transaction) and
  extended `revise-batch` support for source-verified `manuscript_claim_link`
  anchor updates and `decision_acknowledgement` operations.
- Named dossier collections with explicit reading order (`[dossier_collections]`),
  supporting multi-collection membership, unassigned/unavailable visibility,
  portable archive round-trips, read-only website exports, CLI (`dossier --collection`,
  `--set-collection`, `--delete-collection`) and native UI/companion filtering
  without revising dossier records or invalidating pins.
- Configured manuscript terms and props (`[terms]` and `lixity research terms`),
  deriving read-only source-bound candidate occurrences for preferred forms,
  aliases and chapter-scoped alternatives with explicit overlap, out-of-scope and
  Unicode normalization/casefold ambiguity flags and guarded reader navigation.
- `--quote` aliases for manuscript anchor lookup and explicit quote replacement.
- Active manuscript-link duplicate protection across library, CLI and native UI,
  preserving distinct occurrences and reporting the existing association without
  rewriting retained links or confusing duplicates with stale archive state.
- Current-chapter locations for retained manuscript quotations in shared review,
  CLI text/table/JSON and native/read-only UI. Locations follow uniquely moved
  passages without modifying dossier bodies or accepting changed anchors.
- Read-only **Inspect candidate passage** in manuscript review opens uniquely
  moved/adjusted quotations before accepting a re-pin, reusing existing resolved
  offsets and guarded source context without changing saved associations.
- Explicit website preflight in CLI and native UI measures prepared HTML/ZIP/file
  sizes and reports unavailable, unpackaged and unattributed dossier media without
  writing or downloading. Mobile rendering and rights verification remain explicit
  unchecked boundaries.
- Manifest capacity increases to 100,000 entries while retaining the 32 MiB
  canonical-object limit; capacity warnings follow the current limit.
- Compressed manifest storage with explicit verified-backup migration, atomic
  layout switch and retryable cleanup. Canonical hashes, HEAD, source bytes and
  accepted revisions remain unchanged; portable backup transport stays stable.
- Guarded `research media-context` corrects retained-media attribution without
  duplicating source identities or media bytes; explicit dossier `--preamble`
  reads/edits and image `--missing-provenance` filtering reduce repair work.
- Explicit project-local tense review decisions shared by native UI, CLI and
  backend: kept/changed-by-author/deferred, guarded by source, analysis and review
  identities; stale decisions do not count as completed. Filters and next-visible
  passage support reading without automatic tasks. Private review state stays
  out of manuscript prose, research records and reading exports.
- `dossier-image --batch` previews a bounded explicit image manifest and applies
  all captures with one dossier revision or none. Optional item hashes bind
  reviewed bytes; relative paths resolve beside the manifest. `dossier-media`
  exposes the existing PDF/MP4/WebM attachment transaction from CLI.
- Versioned PDF/MP4/WebM dossier attachments reuse the image capture dialog,
  immutable source/context records and guarded dossier revision transaction.
  Shared full/section/history/source and reading-site views show document
  download cards and native video controls. Media is limited to 50 MiB, with
  bounded container checks, single-range native reads and explicit original-file
  inclusion in exports. Video/retained-only PDF opts into record/manifest v9; older readers reject
  those archives. Existing PNG/JPEG interfaces and accepted record bytes remain
  unchanged; attachments do not manufacture extraction or linguistic scores.

### Changed
- Remove Piper completely from rendering, native controls and CLI; use the full
  Qwen3-TTS 1.7B CustomVoice model for all audio. Removed profiles require explicit
  preset choices through a read-only migration preview and backed-up apply.
  Removed Piper-only renderer arguments and exact-speed CLI flags have no silent replacement.
- Separate pure multilingual verb rules from parser adaptation, dependency
  composition and scoped evidence/cache ownership without changing measured results.
- Curated reader/companion exports omit inactive workspace controllers and omit
  the offline diagram library when their prepared content cannot request it.
  Later-revealed diagrams retain the library; media, citations and offline reads
  continue through the shared components.
- Native and review-site adapters share supplementary report assembly while
  retaining their character-validation policies and existing public results.
- Documentation disclosure styles no longer leak into embedded workspaces or
  reports through the public Pages wrapper. Native reader controls retain the
  same appearance; demo privacy guidance reflects optional remote processing.
- Reduced the agent discovery index and generated operational reference bundle,
  linking setup, architecture and history instead of repeating them. Current
  audio guidance now describes shared CLI/native profiles and optional Qwen.
- Removed retired screenshot capture paths and reused the existing Python fixture
  runner in five browser suites; the reviewed screenshot catalogue stays canonical.
- Local read-aloud uses constant neutral delivery and explicit speed rather than
  sentence-length pacing or inferred emotions. Shared Markdown prose includes
  quoted blocks and list items; long inputs retain their text across bounded
  segments. The default German voice is single-speaker Thorsten.
- Audio generation rejects missing/failed segments, mismatched PCM, invalid
  chapter/speed selection and unavailable MP3 conversion. Streamed atomic output
  preserves an existing listening copy when synthesis or conversion fails.
- Native passage research and offline exports share a bounded backend context
  projection from one archive snapshot, grouping dossier/claim pins and decisions
  centrally. Opening a passage context no longer fetches separate record versions
  or joins them in the browser; malformed/unavailable data remains explicit.
- Shared control hover/pressed feedback keeps click targets stationary, fixing
  a mobile export retry button that oscillated at the pointer edge.
- Passage context closes on a different chapter/passage or deliberate reading
  beyond the inspected paragraph. Tool switching uses the requested passage;
  compact return navigation leaves record metadata in its viewer.
- Heuristic tense marks expose a labelled, keyboard-accessible review action
  independent of the selected measurement layer.
- Consolidated shared document typography, status recipes and surface/marker
  tokens while retaining token → component → view stylesheet ownership.
- Shorter reading, analysis and manuscript-link help in all seven UI languages;
  storage guidance names retained data instead of promising a format-7 upgrade.
  Manuscript CLI help separates preview, acceptance flags and partial success.
- Distinguish saved manuscript research references from metric overlays through
  neutral dotted marks, explicit localized Research labels and book icons.
  Research context keeps a neutral document identity alongside analysis colors.
- First-analysis help uses three direct actions: choose a measure, inspect a
  counted-text example, and explore the current passage. Opening help remains
  inert; the shorter panel reuses existing reader controls and focus handling.
- Dossiers share a source-order reading surface across research and record
  inspection. Repeated/nested headings retain their order and levels; unique
  section edits stay at the heading. Maps join the contents, media use the
  shared toolbar, and supplemental dossier actions follow the reading content.
- Contributor guidance uses one current product path with reviewed release
  migrations instead of permanent legacy UI modes or compatibility branches.
- Map detail navigation brings the selected geographic entry and its context
  into view, including later entries with repeated names on mobile. The shared
  dossier editor explains route coordinates, saving and playback limitations.
- The strongest tense stage is neutrally labelled “strong difference” instead
  of “strong friction”. Flag rows explain their real tense markers/switch
  criteria and prioritize reading instead of directly generating To-dos.
- Reader-first analysis adds voluntary, initially closed guidance with
  Analysis Off / no metric / selected metric states, shared localized action
  names and explicit paragraph-versus-chapter comparison scope. Focus and overview
  hide it without resetting display choices. Overview passage selection exposes
  its existing tense-flag/opening fallback reason. `profile --help` adds a short
  source-line/counting workflow without changing metrics, thresholds or JSON.
- Public introduction and first-look guide lead with one revision question
  rather than a feature inventory. The demo's chapter-2 task uses native
  sentence-length navigation and explanation controls, with a compact optional
  reading path and an explicit human decision. A linked German introduction
  identifies the English demo and explains local setup without promising a
  desktop installer. Tool comparisons avoid unsupported category-wide exclusions.
- Heatmap cells, style-reference cutoff-hit counts and all style-space loadings
  share a read-only chapter measurement dialog. It retains chapter context and
  shows definitions, units, sample size, manuscript medians and z* for the
  existing 16 metrics, without recomputation or a cross-metric quality ranking.
  Explicit **Read chapter** reuses manuscript navigation; chapter-only metrics
  clear unsupported paragraph layers. Axis loadings remain distinct from
  chapter measurements, and close/Escape restores the original trigger.
- Documentation separates paragraph, chapter and style-axis comparisons,
  corrects obsolete control descriptions and MTLD's inclusive factor threshold,
  consolidates passage-inspection guidance, and distinguishes pushed source,
  installed/running code, deployed Pages and fixed reading exports.

### Fixed
- Preserve grammatical model/scope overrides when reapplying view settings,
  without persisting temporary selections; identical requests retain identical HTML.
- Follow nested verb coordination when inheriting a shared auxiliary, stop at
  finite conjuncts, and reject malformed dependency graphs before composition.
- Limit external FFmpeg conversion to one hour through one shared
  subprocess owner; timeout errors preserve completed outputs and clean temporary audio.
- Preserve sentence boundaries after audio pronunciation replacements through
  one shared segment packer; retain bounded words, source text and structural pauses.
- Stabilize lag-1 autocorrelation at extreme finite scales/offsets and constant
  decimal samples, and preserve near-null Dunning G² with centered deviances.
  Independent high-precision oracle tests cover these numerical changes.
- Keep workspace project identity visible even when the manuscript repeats its
  title, and show analysis navigation only within the analysis overview.
- Align adjacent paragraph review and research buttons with consistent sizing
  and spacing, allowing them to wrap within narrow reading columns.
- Analysis overview navigation uses one wrapping contents list in the existing
  reader header, with a current-section underline instead of a progress track.
  Later sections remain visible on narrow screens; short viewports keep the
  header in document flow and dossier outlines retain their existing indicator.
- Shared hover help waits for deliberate dwell and switches quickly between
  neighboring controls, with canceled pending hints after navigation or actions.
  Structured tool names, descriptions and declared shortcuts reuse localized
  resources; keyboard and explicit touch help remain immediate. Pointer hints
  stay near the cursor instead of clearing the complete toolbar; focus/touch
  retain toolbar clearance.
  Pointer hints now anchor vertically at the dwell point, and sentence evidence
  cards open beside the hovered words instead of the start of the text line.
- Localized paragraph action menus stay anchored clear of their own trigger,
  choose available vertical space and retain scrolling for longer translations.
  Shared reading-dropdown height limits remain owned by their existing layout.
- Text-report `-o`/`--output` now writes the accepted analysis, profile, style,
  quotation, pacing and signal-group reports instead of silently printing to
  stdout. A shared atomic writer preserves failed destinations and rejects
  manuscript path, symlink and hardlink aliases; no duplicate stdout data is emitted.
- Shared mean and median recover finite results when floating intermediate sums
  overflow, using exact-ratio standard-library accumulation only on that path.
  MAD now reuses the same median. German productive perfect cues also cover
  short weak stems and common separable preverbs within existing clause/head
  safeguards; new `sein` licensing and full grammatical classification are not
  inferred from a suffix or prefix.
- Product vocabulary now separates quoted text, signal-group comparisons and
  ending cues from dialogue, narrative distance and suspense interpretations.
  Source-copy badges describe Lixity's verification boundary; passage actions
  name their draft effect. Manual marker actions differ from saved categories,
  research comparison prompts reuse localized reason flags, and publication
  controls distinguish completed-chapter display gates from package selection.
  Known structured export limits receive localized recovery summaries with safe
  expandable technical details. Formula captions use the measured readability
  variant. The central terminology contract lives in `docs/LOCALIZATION.md`.
- Text style passports distinguish insufficient chapter support, zero MAD with
  varying values and genuinely constant observations. Shared standardized
  differences avoid overflow for the newly covered extreme finite inputs while
  preserving ordinary calculations and cutoff boundaries.
- Analysis names distinguish measured noun/adjective endings and word-distribution
  divergence from inferred style. Pacing summaries name mean sentence length;
  language settings explain their analysis/interface scope. Seven-locale search
  and structural help use one authoritative definition, and website receipts
  report download initiation rather than an unverified completed download.
- The nominal-cue measurement is labeled "Noun endings" and explained with
  localized verb/noun examples before comparison mathematics. Suffix matches
  no longer appear to certify a passage's nominal style; counts are unchanged.
- German listed and bounded productive perfect/pluperfect constructions count once across chapter,
  scene and paragraph analysis, including bounded intervening words; `arbeite`
  and its present paradigm no longer trigger the weak-past suffix rule. Review
  decisions are invalidated by the changed analysis policy. Unresolved verb
  constructions remain heuristic cues rather than grammatical verdicts.
  Productive auxiliary/head rules cover unlisted `geschlafen`, `getroffen`,
  `gehabt` and passive-perfect `gebaut/renoviert worden` without list additions.
- German single quotation closers (`‚…‘`) preserve sentence boundaries and exact
  evidence ranges. The sentence regex now derives from one closing-mark list.
- Analysis review actions retain readable dimensions; the passage component
  switches to its existing cards according to available pane width.
- Export data/revision/bundle-limit failures provide structured JSON and actionable native
  messages identifying the first byte/count limit crossing. Bounds remain
  unchanged and partial failures do not invent completed package sizes.
- Passive cues include short regular and selected irregular participles in
  English, French, Spanish, Italian and Portuguese. German state passive remains
  distinct from the existing event-passive cue count.
- New dossiers inherit the research project's language through API, CLI and
  native creation; explicit language overrides and existing dossier languages
  remain authoritative.
- Shared chapter, scene and paragraph tense counting rejects productive past
  guesses that contradict a curated present-only finite form, such as German
  `halten` or Dutch `moeten`. Explicit pattern overrides retain their counting
  contract; compound constructions remain heuristic. The analysis review-policy
  identity changes so previous decisions are marked stale under the new counts.
- Canonical-equivalent Unicode prose uses the same NFC counting projection across
  measurements, CLI and UI evidence. Original manuscript bytes and hashes remain
  unchanged; complete-cluster ranges map back to original source offsets.
- Global UI word totals share corpus scope with sentence/ASL measurements, with
  separate help for narrower paragraph views. Mobile counted-text navigation
  returns each new explanation to its beginning so its count remains visible.
- German `zur` is recognized as a function word, so the default nominal-suffix
  heuristic no longer counts or highlights it as an `-ur` nominal cue. Shared
  corpus, chapter, paragraph and evidence outputs use the same correction.
- Nominal ending cues include listed plural forms in all seven languages.
  Spanish, Italian and Portuguese passive cues include regular plural participles;
  French includes `fut`/`furent`. These remain pattern cues, not grammatical parses.
- Portuguese marked `í`/`ú` hiatus, Dutch diaeresis boundaries and `ij` beside
  another vowel contribute separate syllable nuclei to readability estimates. Recompute affected reports
  before comparing them with earlier outputs.
- Matched quotation/bracket closers separated from terminal punctuation by
  whitespace stay with their original sentence, without consuming a following
  opening quotation or crossing a blank-line block boundary.
- The adjusted deviation's norm avoids overflow/underflow at extreme finite
  scales. ASL uncertainty documentation now identifies the implemented observed-
  population plug-in, rather than calling it a sample standard error.
- Research audit verifies the complete accepted manifest ancestry and reports
  revision-entry capacity, with an advisory warning at 90% of the existing
  25,000-entry limit. Missing or damaged ancestors fail integrity checks.
- Dossier summaries resolve image/media references across the complete selected
  revision, not just the first 500 characters. A read-only paginated
  `research dossier-images` inventory shows current dossier/section placement,
  exact pins, retained hashes/context and unretained ordinary references without
  scanning folders. `dossier-image --replace-reference` exposes the existing
  atomic exact-marker replacement in CLI. Storage-full/quota CLI diagnostics
  point to temporary storage as well as project storage.
- Publication export distinguishes no saved profiles, malformed settings and
  unsaved edits, links directly to profile creation and disables dependent
  controls until a saved profile is selected. Failed dossier catalogues offer
  retry without discarding drafts. Profile-save and media-capture outcomes are
  logged without titles, file paths, tokens or retained content.
- Current dossier records use a full-width reading article rather than a narrow
  metadata cell. Exact ordinary image references can be retained/replaced
  atomically from that viewer; pinned/history/exported views remain read-only.
- PDF source analysis/compare reads the verified text extraction, not binary
  PDF bytes. Retained-only PDFs explicitly require extraction before analysis.
- Reading-website export failures retain HTTP status codes and distinguish
  unreachable application, invalid ZIP response and browser download failures,
  including available technical details, without resetting export options.
- Native website exports log preparation and transport outcomes at normal log
  levels. Bounded, content-free browser receipts correlate response-read,
  ZIP-check and download-start failures with a random export ID; interrupted
  transfers are no longer described as invalid ZIP files.
  Bounded pre-export profile/catalogue receipts additionally distinguish empty,
  invalid and unsaved configuration without logging project identifiers.

## [0.7.5] - 2026-10-22

### Added
- Native **Project overview**, `lixity project [PATH] [--json]` and Python
  `api.inspect_project` share a bounded, read-only project metadata model
  (`lixity-project-structure/1`). Sources, conventional output locations and
  findings remain distinct; existing output provenance is explicitly unknown.
  No folders, role registry or submission bindings are created.
- Read-only `research find-anchor --query-format markdown` accepts copied inline
  emphasis through the shared displayed-text projection and returns the exact
  quote, offsets and paragraph hash. Default queries and write/re-pin selections
  stay literal; case, Unicode, ambiguity and paragraph boundaries stay exact.
  The research guide includes a reviewed lookup-to-selection workflow.
- Dossier section reads support `--format text --body-only` for an editable UTF-8
  draft without display metadata or an extra newline. Nested headings remain;
  unsafe terminal controls require redirected output. The research guide includes
  a synthetic read/edit/diff/guarded-update roundtrip and expected output.
- Authored-record `--update [--dry-run] --compact` provides a small CLI receipt
  with the accepted or candidate version, explicit no-op status and claim warnings.
  Preview receipts list changed fields without copying their values. Existing
  full JSON and Python/API write contracts are unchanged.

### Changed
- Research reads avoid repeated revision-path traversal and repeated archive
  scans for citation batches. Selected history reads serialize change metadata
  without copying full dossier bodies. Tiny records avoid allocating the entire
  read ceiling; large seekable blobs retain their original allocation bound.
  Bounded reads, checksums, schemas,
  pinned citations and fresh per-call archive validation remain in force.
- Manuscript anchor lookup reuses the profiler's exact displayed-text projection
  without calculating linguistic measurements. Chapter Cliff effects use sorted
  tie groups with the same exact values instead of quadratic comparisons. Sn
  robust scale selects the same order statistics in O(n log n) time and linear
  memory for finite samples, retaining its documented medians and scaling.
- Native Analysis exposes its metric selector directly, with independent,
  browser-persisted **Counted text** and **Paragraph comparison** switches.
  None, disabled switches and Off/On retain the author's choices; Focus hides
  both displays temporarily and restores them on exit.
- Violet underlines identify counted spans. Blue/orange raw-value markers and
  direction arrows compare notable paragraphs with their chapter without a
  prose background wash. Measurement cards put quotation/count before a separate
  paragraph/comparison panel; method and counting guidance start collapsed.

### Fixed
- Project output downloads decode filenames once, reject source/configuration
  aliases and unsafe paths, and bound actual descriptor reads. Overview links
  carry the selected project context and reject stale tabs after a switch.
- Literal manuscript anchor lookup now rejects overlapping duplicate quotes as
  ambiguous, including `ana` in `banana`, instead of silently choosing one.
- Overlapping automatic research status reads share only their in-flight
  workspace observation. Explicit refreshes remain fresh; context changes and
  mutations invalidate sharing without retaining settled responses.
- Research tab labels and companion selectors remain readable on narrow screens
  with enlarged text; wrapped research destinations retain aligned control boxes.
- Website exports count authored record versions against the research-history
  limit, rather than every retained source passage. Curated reader/companion
  copies no longer apply a limit for history they do not include. Input-byte,
  prepared-response, bundle-size and integrity checks remain in force.
- Human dossier section reads preserve the actual heading level instead of
  presenting every selected heading as H2. Selected JSON reads add `section_level`;
  implicit preambles have no invented heading level.
- README and installation explain the current 0.x product numbering separately
  from historical 1.x/3.x tags and independent schema versions.

## [0.7.4] - 2026-10-22

### Added
- `lixity doctor [--json]` reports imported/distribution/service versions,
  module/interpreter locations and JSON contract versions without reading a
  manuscript or repairing/restarting anything. A stopped service is valid.
- `pdf --layout document` and the native PDF selector provide neutral A4 text
  for exposés and everyday documents through the shared composer. Authored titles
  and structure remain; entered title/author are metadata only, with no generated
  title page, header/footer, byline, line numbers or analysis.
- Export an explicitly selected project as a static read-only reading website
  through `lixity export-site`, `lixity.site_export` or the native ZIP download.
  Research and original source files are separate opt-ins. A versioned export
  manifest records scope, source identities and file hashes; the copy uses the
  shared product UI with a fail-closed prepared-read transport.
- Curated novel-and-companion and standalone-companion website formats share
  root-local `site_publications` profiles. Explicit dossier versions/sections,
  chapter release gates and optional citations/maps define the selected material.
  A chapter cap removes later content and assets before assembly; reader progress
  is a separate local display aid. Original sources need per-export opt-in.

### Changed
- Maintainer checks run locally by default. Full source/browser/platform jobs
  remain manual GitHub fallbacks; release-tag publishing deploys Pages from the
  same verified ref after package publishing. Local release checks avoid repeating
  documentation tests, and reading-website changes select their own browser area.
  Release arguments now fail before heavy work; checkout-local caches and aligned
  check-only Ruff hooks improve the development loop. Shared browser helpers and
  failed Git comparisons can no longer silently omit affected suites.
- `service status --json` intentionally uses `lixity-service-status/1`:
  `ok` describes successful inspection, so known stopped, starting and unmanaged
  busy states exit 0. `running` indicates readiness; unknown state keeps
  `ok: false`, `running: null` and exit 1. Log paths and raw errors are omitted. Human status and
  other lifecycle JSON keep their existing behavior.
- Simultaneous text evidence and paragraph emphasis have distinct visible keys:
  **Counted text** explains the underline/tint, while **Paragraph comparison**
  explains blue/orange chapter-relative backgrounds. Exact-evidence availability
  stays visible outside the closed settings popup.
- Local phrase echoes already present in JSON now appear in human CLI output and
  the analysis overview, with local counts and explicit chapter-prose word bounds.
- Chapter register feature choices and target rows show their shared units and
  distinguish scene targets from chapter profiles and display-only filtering.
- The research guide has a task index; adapter guidance explains optional scene
  and exact-evidence inputs and shared character configuration.
- One **Explore passage** menu entry groups measurement inspection and saved
  research in the existing paragraph context. Quick hover and touch explanations
  remain available at marked text. The **Passage** context label distinguishes
  that tool from the global **Analysis** display switch.
- Measurement cards give the selected sentence's word count a clear hierarchy,
  separate paragraph comparisons and expandable mapping/method details.
- The landing page explains manuscript analysis, linked research and PDF reading
  copies and browsable reading websites in its existing three compact feature blocks.
- Loaded claim quotations can be collapsed without discarding their contents.
  Ordinary research entry actions show the current version. Earlier linked
  versions remain explicit; a collapsed version list loads on demand without
  changing the displayed entry or discarding an editing draft.
- Research labels use compact version names across all seven UI languages and
  human CLI record/history output; existing JSON fields and flags are unchanged.
- Passage research groups quotations of the same linked claim and separates
  exact associations from current dossier decisions, with distinct counts.
- The six-chapter fictional demo has a stronger receipt/label mystery and about
  15% more text, with richer dossiers, conflicting citations, claim histories,
  explicit decisions, causal links and exact manuscript associations.

### Fixed
- Research archive candidate syncing uses a writable descriptor on Windows.
- Service observation accounts for Windows' different path/descriptor timestamp
  clocks while retaining same-API mutation, identity and ownership checks.
- Human `dossier --diff --format text --section` previews explain nested heading
  scope without another archive read or a JSON/API contract change.
- Installed reading-website exports resolve license metadata beside the loaded
  package, including standard legacy layouts, instead of a shadowing checkout.
- PDF/dashboard CLI exports reject source paths and their symbolic/hard-link
  aliases before writing and again immediately before atomic replacement.
- Button-styled links share the real control box, alignment and wrapping used by
  app buttons; their minimum height also applies inside ordinary Pages prose.
  Long localized headings and checkbox labels wrap at enlarged text sizes.
- Native views, PDF downloads and reading websites consistently use the selected
  project's configuration, including manuscripts in configured subdirectories.
- Configured `motif_regexes` and compatible legacy `motifs` now resolve once
  across chapter measurements, CLI, Python, native panels and the motif panel in
  `build` dashboards. Explicit patterns
  replace configuration; conflicting duplicate names fail clearly. Empty
  patterns consistently count no occurrences.
- An unchanged manuscript Review refresh preserves its row controls, so closing
  a pinned-entry viewer returns keyboard focus to the actual opener. Changed
  reports and filters still refresh, and read failures remain explicit.
- Stale scene assignments report measured scene/divider counts and recovery
  choices without accepting missing assignments or inventing planned text.
- Human style passports label robust deviations as z*, rather than ordinary σ.
- `research dossier show ID --export-edit PATH` no longer injects a conflicting
  implicit inspection flag; export and archive write guards remain unchanged.
- Research lists show complete IDs; dossier lists support exact tag filters and
  `--section --format text` returns the selected section body, including nested
  content and explicit saved versions. `research compare` inherits the selected
  root's project language unless overridden; a missing setting and the Python API
  retain English defaults.
- Sentence word counts use the selected interface language, including singular
  counts; browser labels no longer fall back to the English key.
- Explicit measurement explanations can open from the mobile context inspector
  when its associated paragraph is outside the viewport.
- Reading and analysis settings share a disclosure indicator and keep their
  popup beside its trigger, with internal scrolling on short screens.
- Decision claim choices distinguish identical titles by period, saved version
  and, when still necessary, ID, as the evidence and relation pickers already do.
- Source document/passage controls expose their selected state consistently.
- Stationary content reflow no longer opens incidental hover help; deliberate
  pointer, keyboard and touch explanations retain their existing behavior.
- Repeated hover departures cancel earlier dismissal timers, so an old hover
  cannot close a subsequently opened touch explanation.
- The read-only demo includes record/history fixtures for evidence and causal
  links, so their entry and version controls reach real archive states.

## [0.7.3] - 2026-10-21

### Changed
- The first explicit reader Analysis activation selects Sentence length and
  shows counted text. A sticky, named metric control groups the existing
  selector, highlight preference and interaction help; deliberate None/Off
  preferences remain visible and survive reloads. Paragraph inspection can
  activate analysis directly without silently changing the highlight preference.
- Research version history consolidates selected-version context and provenance,
  localizes read-only choices, omits absent optional fields and preserves pinned
  references, explicit false values, drafts and guarded version navigation.
- Restored button focus after touch no longer opens an incidental help popup;
  immediate keyboard focus and explicitly opened touch help remain available.
- Native project chrome removes the generic analysis slogan and repeated footer.
  A matching authored manuscript title remains in the document while its generated
  sidebar duplicate is suppressed only in reading mode.
- Manuscript analysis can mark exact counted sentences, words,
  patterns and quoted speech, with a hover/touch explanation and keyboard/context
  menu inspection. Evidence shares configured core counters, preserves prose and
  selection, and reports unmappable/unsupported states explicitly.
- `profile --layer KEY --evidence` adds literal source evidence; its opt-in JSON
  schema is `paragraph-layer-evidence/1`. Existing default contracts are unchanged.
- Wide dossier views keep a bounded heading tree to the right of the reading
  document; narrow and companion views retain the compact native disclosure.
- Interface typography uses three shared roles for metadata, controls and body;
  manuscript prose and technical code retain their distinct reading faces.
- Analysis uses one selected metric for quiet transparent paragraph emphasis,
  with value/unit/local-reference hints, comparable coverage, clear controls and
  distinct unavailable/zero results. Colour now matches the chapter-relative z
  used for notable membership; labels correctly describe median/MAD.
- `profile --layer KEY` adds source-anchored human output and opt-in
  `paragraph-layer/1` JSON. `--only-notable` retains full chapter references;
  default profile JSON v2 remains unchanged.
- Declared register/POV selectors filter only style-fingerprint table rows and
  explicitly retain the whole-manuscript reference and existing register policy.
- Analysis and dossiers share heading-navigation presentation. Dossiers gain
  real heading links and compact persistent orientation, with native collapse
  and existing scroll/return owners. Context resizing preserves a reached end.
- Decision/dossier review reads exact saved versions together, including an
  earlier assessed dossier. Delayed impact reads cannot mint acknowledgement
  controls in a newly selected project; writes retain existing guards.
- Public pages use a consistent editorial header and a concrete synthetic
  passage/rhythm/research example, fewer repeated entry links and smaller complete
  screenshot previews. Technical reference remains separately reachable.
- Workspace destinations precede project identity and actions, including long
  titles. Version/license information is secondary; collapse, project dialogs
  and the existing PDF export remain available through the same controls.
- Reader feedback uses distinct persistent and temporary gutters, a legible
  Analysis toggle throughout its transition, and quieter interrupted reveals.
  Context scrollports fit their containing layout without moving the manuscript.
- Explicit workspace choices supersede queued fragment navigation; later passage
  links and direct `#view-…` routes remain available.
- A paragraph's Saved research, association count or marked quotation opens
  exact saved claim/dossier versions in the shared context dock. Current dossier
  decisions are labelled separately; unresolved anchors retain explicit Review.
  Reads are lazy and coalesced, with bounded lists, retry and context guards.
- Current product guidance describes Manuscript & Analysis, Research & Dossiers
  and Project & exports without a blanket experimental label for Research.
  Capability metadata classifies Research as `supported`; response/archive schema
  versions, retention/revision guards and individual integration/export limits
  remain unchanged. The classification does not certify factual accuracy.
- Analysis/export CLI commands can reuse a root-configured manuscript and select
  an explicit project with `--project`. Research manuscript commands share the
  configured-path resolver while preserving retention and revision guards.
- Public entry routes start with concrete manuscript questions, an example and a
  short tour; installation and technical references remain directly reachable.
- Key reader actions explain their purpose on hover and focus. Reading settings
  includes a localized reference to implemented passage-menu, search and close
  keys. Shared controls and canvas labels use central typography roles; fenced
  code and all six prose heading levels retain readable sizes.
- Public entry pages use a shorter product introduction, bounded linked screenshot
  previews and direct documentation routes for first use, installation and reference.
- Analysis overview groups secondary manuscript measurements in a reversible
  disclosure while keeping review routes, navigation and flagged passages visible.
  Scene measurements share a collapsed catalogue with direct routes from the
  comparison rows. Long flags and scene comparisons remain bounded and keyboard
  scrollable; wide chapter, character and scene tables retain visible row identity.
- Dialogue charts show every measured chapter in manuscript order, including
  zero-turn chapters. Pacing labels identify ASL, its units and relative bar scale;
  Hook help explains the existing heuristic without changing its calculation.

### Fixed
- Right-click evidence inspection retains the clicked occurrence instead of
  restarting at the paragraph's first match, including when enabling Analysis
  changes the surrounding layout.
- A touch inspection waits until the opening tap completes before presenting its
  card, so that tap cannot accidentally operate the newly appeared explanation.
  Unavailable browser text verification is distinct from a source-hash mismatch.
- Public installation-link measurement includes the current landing section
  anchor as well as the existing guide and historical anchor.
- Research index failures retain their actual SQLite cause and index path
  instead of attributing storage or corruption errors to missing FTS5 support.
- Research exports retain one accepted snapshot while copying records and blobs,
  verify copied content addresses and preserve an existing backup on failure
  before replacement. Errors after replacement identify uncertain durability.
- Export rejects destinations inside its research store/cache and checks
  restore's existing size ceiling before creating a candidate archive.
- Restore rejects malformed export envelopes and duplicate archive members with
  bounded errors; valid archives keep their format and immutable bytes.
- Service status inspects existing state without creating or repairing folders
  or acquiring the lifecycle writer lock; changing records retain uncertainty.
- Reading settings fit short viewports from their first visible frame. Rapid
  tool reversals and analysis changes preserve the stable reading position
  without rewinding deliberate scrolling after the tool has opened.
- Dossier departures retain a guarded return to their exact saved view, tab,
  scroll position and control without dropping an earlier manuscript return.
  The same return control stays reachable on narrow screens and offsets other
  sticky controls. Project changes and replaced dossier views invalidate it.
- Shared jumps account for nested scrolling and their own sticky controls;
  arrival feedback waits for scrolling to settle, cancels obsolete cues and
  honors live reduced-motion changes. Search no longer leaves permanent arrival
  styling. Navigation does not change source bytes or saved research records.
- Overview section links retain spacing and keyboard reachability on narrow
  screens. The final chapter matrix stays selected at the page bottom, and
  keyboard drills focus the revealed manuscript destination while preserving
  the existing passage/context return.
- Flagged passages expose their existing To-do draft action in the overview.
  Chapter-matrix deviation counts distinguish a measured `0` from unavailable
  `–`; coverage guidance explains the existing paragraph/corpus difference.
  Analysis scores and public API formats are unchanged.
- Chapter charts no longer fade their final rows when all entries already fit,
  or at the end of an overflowing list. Native scrollbars remain visible for
  long Pacing and Showing/Telling chapter lists.
- Empty claim evidence offers a direct route to the existing evidence composer;
  failed reads offer retry instead of appearing empty. Existing claims, retained
  quotations and unsaved drafts keep their separate states.
- Unchanged archive refreshes preserve an opened or loading evidence panel;
  archive, claim or project changes still invalidate it. The public demo marks
  evidence preparation as a local-app action instead of opening a disabled form.
- Research catalogue filters are hidden for genuinely empty collections, while
  active queries and failed or pending refreshes retain their editing context.

## [0.7.2] - 2026-10-20

### Changed
- Public Pages and the read-only demo can count page visits and named CTA events
  through the explicitly configured hosted GoatCounter instance. The Pages-only
  adapter excludes query/hash, forms and selections, respects browser privacy
  signals and stays out of the local app and exported manuscript reports.
- An optional project-only `manuscript` setting supplies existing workspace folder
  selection and omitted input for `scenes` / read-only `research review-manuscript`.
  Explicit paths win; invalid root settings never select an alternate manuscript.
- Scenes output supports canonical chapter/scene filters and the last measured
  scene in document order, preserving full-manuscript references and declaring
  filtered JSON scope. Explicit `scene_analysis.planned` IDs remain visible without
  fabricated measurements; unlisted stale assignments still fail.
- The research data-model reference now documents the implemented entities,
  revision pins, publication process, schema evolution and disposable SQLite
  index, with current architecture/process diagrams. The broader interchange
  proposal remains available as an explicitly historical design.
- The public showcase focuses on one real reader view, the demo and installation.
  README explains purpose, first commands and where to find documentation and
  source. The demo uses a compact return link instead of duplicate site navigation.
- Native Project actions groups New/Open, guidance and PDF export; destinations
  remain directly visible. Service help groups existing workspace, instance and
  analysis options without changing their defaults or behavior.
- Screenshots frame actual viewports or complete tasks. Capture tooling preserves
  native dialog scrolling, readable image ratios and the intended light/dark views.
- Shared light-theme tokens use paper-toned surfaces across the native UI and
  Pages. Clearer chapter typography, compact reader control spacing and quieter
  supporting sections give prose more room while retaining the existing reading
  preferences, initial text size, dark palette and independent passage tools.
- The interactive manuscript stays continuous, with an explicit **Analysis**
  On/Off switch independent of the dossier context tool. Showing diagnostics
  keeps the prose width and navigation choice; it does not implicitly open a
  dock. **Values** explicitly opens the Passage values inspector independently of
  the diagnostic layer;
  **Dossier alongside** opens its own context tool. Dense comparisons open
  in an overview; **Back to passage** restores the prior analysis display choice.
  A shared display coordinator owns
  workspace, tool, overview and reversible focus transitions. Reading settings
  group text size, width and spacing and retain visible source-block position.
  Paragraph **…** buttons,
  right-click and keyboard menus reuse existing values, marker and quote-link
  actions; selection tools appear only when applicable. Desktop manuscript/dossier
  widths use one draggable, keyboard-operated divider; mobile stacks the readers.
- Explicit passage-to-tool requests reveal the stacked tool heading on mobile;
  closing the tool or pressing Escape restores the requesting passage and focus.
  Desktop tools retain their adjacent layout. Optional feedback uses short opacity
  changes on bounded visible elements and a passage gutter; semantic changes stay
  immediate. Live reduced-motion changes cancel active feedback without moving or
  duplicating prose or animating the workspace width.
- Source-backed browser reading retains supported headings, quotations, literal
  code, dividers and notes in source order, including preface/empty chapters and
  the analysis-excluded appendix. Source-span joins reuse each exact profile once,
  including profiles spanning several list items. Unprofiled content has no
  invented measurements or claim saves; analysis/JSON/quote and PDF contracts stay
  unchanged. Unsupported inline syntax remains literal; no editor or automatic
  manuscript image fetching is added.
- Saved manuscript associations open their pinned claim revision; claim/dossier
  views expose scoped saved-quotation routes and exact reviewed passage returns.
  A compact work thread retains the original passage and the viewed saved-record
  identity and revision, with an explicit return. Dossiers group authored notes,
  current-linked claims and retained citations, with routes to global claims and
  decisions. Values includes passage context and the existing saved-research route.
  Dossier revision references remain explicit; retained quote cards are not full
  historical-source readers. No new record, store or implicit repinning is added.
- Research tabs have named tab/panel relationships and explicit narrow-screen
  overflow controls. Lazy Mermaid rendering shows a localized pending state.
- Companion dossiers temporarily collapse desktop project navigation, with an
  accessible manual toggle and restoration of the prior choice when closed.
  Mobile navigation remains visible. Saved exact manuscript associations now
  offer a direct, focused return to their passage alongside the claim action.
- Research creation and association forms start collapsed with reversible labelled
  controls, retained in-memory drafts, nested Escape handling and contextual reveal.
  Shared disclosure arrows provide brief reduced-motion-aware feedback in the app
  and Pages. Dossier catalogue previews omit formatting and fenced code while the
  saved body and API data remain unchanged.
- Shared local tabs, form groups and dialog frames now carry the desktop
  workspace design through analysis, settings and research. Research catalogues
  use separated rows; labels preserve localized casing. Dialog forms scroll
  below their title and close control, including in short windows.
- The interactive workspace puts manuscript and analysis first in a fixed desktop
  project sidebar, with research and settings alongside. Narrow screens retain
  horizontal navigation, with keyboard orientation matched to the layout. Plain
  exported reports keep their document layout.
- Public entry points distinguish the read-only demo from local installation,
  with simpler page framing and clearer open/import guidance. Compact diagram
  frames and grouped style-space controls reduce empty space and uneven wrapping.
- Upgrade guidance uses restart to retain recorded launch settings and explains
  the distinction between released, installed and running code.
- One public Warehouse 4 demo combines the same manuscript, analysis, research,
  images, geography and PDF exports. Former research links open that project;
  public-domain novel analyses remain secondary case studies.
- Embedding adapters can enable manuscript review without association editing.
- The public demo keeps the native workspace views and marks local-only actions
  with installation links. Dossier reading, prepared PDF downloads and the
  claim-evidence matrix use the existing application controls.
- Geography reads share placement coverage, authored route context and approximate
  vertex-chain distances across the API, CLI and map/companion views. Maps add
  selected-feature framing, a legend and a metric scale. Visible maps open with
  OpenStreetMap; the background can be disabled and local vectors/sketches remain
  available offline. Tile requests stop outside the active visible map context.
- Style-space views and CLI output explain projection support, retained variation,
  active cutoffs and chapter scores, with persistent selection, planar inspection
  and numeric loadings. Additive diagnostics preserve existing scores and formats.

### Fixed
- German perception/filter cues include finite present and simple-past forms of
  hören and riechen across shared analysis surfaces. Counts remain lexical,
  context-dependent signals; no full grammar/perception detector is implied.
- Purge accounts for original and extracted-text blob references together,
  preserving shared retained evidence and removing unshared extraction bytes.
  Decision-to-dossier pins are validated at the storage/restore boundary.
  Publication acknowledgement and post-commit cleanup errors identify the
  observed outcome instead of suggesting rollback or successful erasure.
- Configuration discovery warns about permission/I/O failures and present
  non-table `tool`/`tool.lixity` sections instead of silently applying other
  settings. Missing paths and impossible children beneath a file remain quiet.
- Imported style measurements reject non-finite features and invalid standard
  errors before scoring. Low-level structure reports share the English default;
  automatic detection remains explicit. Dialogue, pacing, motifs and showing CLI
  commands share guarded UTF-8/regular-file reads, including nonblocking rejection
  of special file nodes.
- Invalid explicit foreground startup selectors fail before binding or selecting
  a different workspace. Failed project configuration or requested Research setup
  reports incomplete setup, retains created files and keeps the prior selection,
  with a recovery path through **Open Project**.
- Supplied invalid HTTP claim-confidence and evidence-relation values return 400
  without an archive write; only omission receives the existing defaults.
- Research backup import and export validate the complete manifest ancestry before
  accepting or packaging it. Invalid selectors, damaged or incomplete history and
  project/generation mismatches fail explicitly; archive paths reject parent
  traversal. Valid archive formats and record bytes are unchanged.
- French, Spanish, Italian, Portuguese and Dutch word patterns retain straight
  and curly internal apostrophes as documented. First-person sentence starts
  recognize typographic contractions consistently. Token-based measurements can
  change; regenerate affected reports before comparing versions.
- Plain-prose counting avoids unnecessary delimiter scanning while retaining
  the existing Markdown projection and exact source/display identities.
- Downloadable Markdown guides preserve paragraphs and fenced commands inside
  expandable sections. Example generation uses the active checkout's source.
- Heatmap chapter cells reveal their manuscript destination through the shared
  navigation coordinator instead of scrolling a hidden chapter from the overview.
- Validated authored edits whose normalized content is unchanged return the exact
  previous revision without changing archive HEAD, retained bytes or the SQLite
  index. Revision metadata, association validation and concurrent HEAD guards still
  run. Mixed batches revise only changed members; invalid batches remain atomic.
  Decision acknowledgements remain append-only events.
- Sidebar collapse uses a stable glyph beside project identity. Tooltip titles
  update with live state and nested scrolling; responsive settings and wrapped
  URLs stay readable. Paragraph actions and the reader divider have separate
  targets, and revision Close stays reachable in short or enlarged dialogs.
- Analysis Off preserves explicitly opened Passage values; opening Values does
  not force Analysis On. Overview return restores the prior layer and tool.
- Missing/unreadable manuscript files and failed configuration/render rebuilds
  label the last successful dashboard with an **Analysis freshness** notice and
  retry link, preserving its source identity. Explicit analyze/rebuild failures
  return an error; recovery removes the notice only after validation succeeds.
- Asynchronous manuscript association marks preserve native text selections,
  including backward selections and astral characters. Automatic review first
  checks archive readiness and revalidates project context after changes.
- Spanish syllable estimates now count standalone closed-vowel nuclei and apply
  bounded orthographic diphthong, hiatus and silent-vowel rules. Spanish ASW and
  derived readability can change; formula coefficients and JSON fields are
  unchanged. [Rules and limits](docs/METHODS.md#7-language-specific-readability).
- Chapter/rest Jensen–Shannon calculations retain small genuine divergence near
  equality and return zero with no lexical drivers for identical distributions.
  Integer absent-token mass and stable summation preserve the existing definition
  and units. [Numerical details](docs/METHODS.md#8-jensenshannon-divergence-chapter--rest).
- Project-dialog tab switches no longer reset unrelated research revision tabs.
- Disabled actions retain their disabled appearance on hover and press.
- Numbered map labels select their own feature with mouse, touch or keyboard;
  authored label anchors and geometry stacking keep routes and points reachable.
- Escape in research dialogs preserves open paragraphs in the hidden Analysis view.
- Style-axis descriptions use actual positive/negative loadings and distinguish
  an absent pole or zero-variance axis from an opposing stylistic tendency.
- Style-space plots keep chapter details alongside the canvas, with full-width
  scores below and readable axis/chapter labels. Research diagrams retain a
  readable scale on narrow screens through a keyboard-scrollable viewport.

## [0.7.1] - 2026-10-19

### Added
- Exact authored-update dry runs and historical revision comparisons through the
  existing research revision API and CLI.
- Explicit dossier Markdown export, three-way preview and reviewed batch packets;
  application remains bound to the reviewed project and archive snapshot.
- Project-local character profiles with literal aliases and separately declared
  viewpoint chapters, exposed through the existing configuration discovery.
- Guarded dossier retirement through the existing withdrawal/tombstone path,
  with read-only previews and retained historical records and associations.
- Bundled Leaflet geography interaction, offline by default, with explicit,
  nonpersistent OpenStreetMap tile permission; shared PhotoSwipe image/diagram
  zoom and Mermaid tiny rendering with inspectable source and restricted features.

### Changed
- Research prioritizes dossiers, claims and manuscript review. Zotero remains the
  source-library and reading interface; capture selection and alternative local
  imports use compact disclosures. Retained evidence and archive contracts stay intact.
- Research help groups commands and exposes aliases in discovery/completion.
  CLI selectors accept bare UUIDv4 identifiers; archive/API identifiers remain canonical.
- Dossier `--file` now requires an existing readable UTF-8 file. Use `--body` for
  literal text; this intentionally replaces the former missing-path-as-text fallback.
- Consolidated current documentation and retired duplicated status checklists;
  earlier design and implementation notes remain available through fixed Git links.
- Pages use consistent site and parent navigation, reading paths and accessible
  back-to-top links, including the standalone public examples.

### Fixed
- Selected workspace tabs keep readable text when hovered in light and dark themes.
- Cropped documentation captures preserve the full research navigation height.
- Revision preparation shares validation for sections and record fields, preserves
  concurrent unrelated sections and compares prospective changes in one snapshot.
- Name and prose counts exclude Markdown destinations, images and code while
  preserving displayed paragraph anchors and manuscript chapter numbering.
- Research writer diagnostics distinguish contention from read-only, permission
  and other I/O failures without changing the canonical lock location.
- Positional and verb-based dossier reads now honor section, summary and citation
  bounds through the same exact-version reader as named IDs.
- Image galleries include lazy images and fit their exact dimensions after loading.
- Dossier Markdown emphasis preserves link destinations and generated markup,
  preventing formatting from leaking into the geography view.
- Scene overview tables keep numeric values readable on narrow screens;
  documentation captures show the intended first three scenes.
- Research help names supported draft inputs and distinguishes exact quote matching
  from prose counting, explicit claim acceptance and per-association commits.

## [0.7.0] - 2026-10-19

### Added
- A4 editorial PDF copies with line numbers and correction margins through the
  existing CLI and native download composer.
- Optional structured places, areas and character journeys within existing
  dossiers, with a shared editor, offline coordinate view and GeoJSON import.
  Geographic saves require record/manifest v8; ordinary dossier encodings remain unchanged.
- Read-only research preview using attributed historical Hamburg map/photochrom
  sources alongside explicitly fictional scene notes and journey coordinates.

### Changed
- Manuscript PDFs preserve document structure separately from statistical text
  cleaning, with bounded embedded LaTeX text formatting, shared layout handling
  and stable reading typography.
- Zotero captures PNG/JPEG through the existing retained-image pipeline and
  exports them with media-correct filenames. Image captions expose provenance
  and source links in the ordinary dossier reader.
- Settings group project details and analysis choices by purpose, explain
  persistence beside the controls, and distinguish project values from values
  that could not be automatically detected in the manuscript.

### Fixed
- Oversized research records are rejected before publication, preserving the
  previous readable snapshot. Geography editing preserves Unicode and multiline
  metadata and guards pending file imports against concurrent saves.

## [0.6.0] - 2026-10-19

### Changed
- Clearer product descriptions and worked articles on intentional chapter
  registers and local phrase echoes, linked from the README and Pages.
- Configuration discovery exposes corpus/publication model defaults, threshold
  constraints and settings scope through `about --json`; `about` and `schema` accept `--section`
  for a focused JSON response. Metadata and shell completion ignore ambient
  configuration.
- Settings explain analysis and persistence choices beside their controls in
  all seven interface languages. An opt-in, unchecked by default, saves posted
  language and thresholds as project defaults through the existing guarded transaction;
  ordinary Apply keeps session-only analysis choices.
- CLI threshold help, defaults and scalar validation reuse backend policies;
  invalid values report usage errors before reading configuration or manuscripts.
- Onboarding, architecture and automation references defer discoverable details
  to command help and runtime metadata while retaining scientific and data contracts.

## [0.5.0] - 2026-10-19

### Added
- Research record inspection and all six manuscript-association commands support
  readable text output alongside JSON and table views.
- `unlink-manuscript` retracts one manuscript association (history retained).
- `reconcile-manuscript --accept-claim-updates` re-pins associations whose
  claim advanced to a newer revision without creating a parallel link.
- `--latest` flag for `--update` on dossier/claim/decision records: uses the
  current HEAD revision automatically (single-author convenience).
- Authored research records accept `list`, `show ID`, `inspect ID` and implicit
  inspection by ID, alongside their existing named ID options.
- Motifs: echo detector lists n-grams repeating within a short text span
  (`echo_window`, default 300 words) so local word echoes surface for review.
- Style: `chapter_registers` and `register_profiles` in `CorpusConfig` mark
  chapters as intentional registers (e.g. historical notary, child voice); such
  chapters are exempt from deviation/FDR flagging. Validated author target
  ranges are descriptive comparisons alongside the unchanged book baseline.
- Native Settings editor for named chapter registers, feature ranges and chapter
  assignments, with guarded project-local persistence and seven-language labels.
- UI: skip-to-content link, `role="main"` on the chapter pane, `aria-busy` on
  loading states (accessibility).

### Changed
- Research filesystem diagnostics identify the actual failure and affected path.
- Closed paragraphs create their inner layout subtree only when opened and
  release it on close unless retaining a marker draft. Full offline text,
  manuscript search and saved quotation links remain available.
- Regression tests share isolated handler, research command and browser server
  fixtures. Repeated browser workflows are separated from seven-language
  desktop/mobile rendering checks; numerical and structural assertions use
  independent expected values and nonempty measured results.
- Pages and articles expose generated Markdown alternatives through the existing
  guide converter. Canonical URLs, image dimensions, structured metadata and
  meaningful modification dates are checked against the staged publication.
- Documentation and agent guidance focus on workflows and durable contracts;
  exact options come from CLI help and runtime discovery. Repeated feature
  histories, command catalogues and implementation detail are consolidated.

### Fixed
- Reconciliation exits 1 on archive read/write, lock or safety failures instead
  of treating them as skipped associations. Storage causes remain distinguishable
  from ordinary record review conflicts.
- Human research reports render the requested format without losing list rows,
  and escape stored terminal controls in detail and diff output.
- CLI help accurately describes metadata, supported source formats and FDR
  settings. `pdf --json` rejects the unsupported mode before writing a PDF.
- Combined anchor/claim updates now save one association revision;
  `--accept-claim-updates` works alone and with an explicit selected link.
- Explicit batch snapshot guards reject intervening external archive writes;
  manuscript association revisions record their current actor and UTC timestamp.
- Numeric register selectors match chapter numbers exactly, and register names,
  feature bounds and explicit project scope are validated.
- Echo counts require the configured minimum within the local span; independent
  repeated phrases sharing words are no longer discarded by deduplication.
- Low-level MATTR/MTLD/Maas helpers reject invalid window sizes, thresholds and
  impossible token/type counts with `ValueError`; valid/default arithmetic is unchanged.
- USAGE.md: corrected manuscript path requirements, claim re-pin examples and
  format documentation; removed the stale "no manuscript-link CLI command" sentence.
- Pages: comparison tables survive Markdown conversion; article examples and
  evidence-link descriptions reflect their implemented scope. Removed an
  accidentally appended assistant transcript from the v0.4.9 release notes.

## [0.4.9] - 2026-10-16

### Added
- `lixity schema` exports tool metadata (languages, features, heuristics and
  commands) as JSON for discoverable machine integration, alongside
  `lixity about`.

### Fixed
- Manuscript-link commands (`link-manuscript`, `review-manuscript`,
  `find-anchor`, `reconcile-manuscript`) accept the manuscript path
  positionally as the analysis commands do, or via `--manuscript PATH`; exactly
  one of the two forms is required.
- The reader panel's dossier select and refresh button share one top edge (a
  panel margin had overridden the controls row reset and pushed the button 11 px
  below the select).
- Compact controls (`.ctl-sm`) keep the 44 px touch minimum on coarse pointers;
  the size variant previously beat the touch rule on specificity.

### Changed
- The documentation site is rebuilt as a product page: framed application
  windows, a "what makes it different" tile row, a three-step start and
  reordered feature blocks. The staged site now shares `assets/components.css`;
  controls use the shared `.ctl` vocabulary, and the docs suite checks the
  frames and captures the landing page full page.

## [0.4.8] - 2026-10-16

### Added
- UI component layer for stateful panels: the dashboard vendors Preact 10.29.8
  (MIT) and htm 3.1.1 (Apache-2.0) as pinned, integrity-checked files and
  inlines them into the single script - no build step, no runtime network and
  CSP-compatible without `unsafe-eval`. The Zotero catalogue results
  (`assets/zotero-results.js`) and the research record lists
  (`assets/research-cards.js`: sources, dossiers, claims, decisions) run on
  this layer.
- Central logging: one `lixity.*` logger tree with a UTC line format, standard
  levels (`--debug`, `LIXITY_DEBUG`, `LIXITY_LOG_LEVEL`), a redirect-aware
  stderr handler and rotation for the captured service log at service start.
  `docs/INSTALLATION.md` documents the log location and settings.

### Fixed
- Manuscript-link commands (`link-manuscript`, `review-manuscript`,
  `find-anchor`, `reconcile-manuscript`) accept the manuscript path
  positionally like the analysis commands, or via `--manuscript PATH`; exactly
  one of the two forms is required (both together fail).
- The reader panel's dossier select and refresh button line up: a panel margin
  broke the flex-end alignment and pushed the button 11 px below the select.
- Compact controls (`.ctl-sm`) keep the 44 px touch minimum on coarse
  pointers; the rule previously lost to the size variant on specificity.

### Changed
- Controls: the dimension buttons build on the shared control recipe
  (`.dim-ctl` is a compact variant), the field label/help recipes and the
  selected state (`aria-pressed`/`.active`) have one source each.
- Structure: the shared stylesheet vocabulary moved into `assets/components.css`
  (panels, status, focus, tables, badges, controls, layout primitives, renderer
  utilities) with the layer order tokens → components → views, asserted for the
  standalone output. The spinner, micro-label and table recipes are consolidated
  to one source each.
- Structure: the 3,500-line `assets/research.js` is split into seven topic
  modules (`research-core`, `-content`, `-evidence`, `-lists`, `-review`,
  `-workspace`, `-revisions`). `_JS_FILES` concatenates them in the original
  order, so the served bundle and its load-time behaviour are unchanged.
- UI cohesion: radius, type and weight values come from the design-token
  ladders instead of one-off numbers; the workspace switch and the research
  sub-tabs share one tab/control recipe, badges and tags are one pill family,
  and the staged public site uses the same control metrics. The
  `visual-consistency` browser suite now fails when control radii, badge
  pills or sampled text sizes leave the ladders.
- Research workspace: the record lists render through one shared card
  component; the hand-rolled per-card identity diffing was removed. The
  claims evidence panel keeps loaded evidence in the list model, so
  re-renders no longer lose or misplace it.
- Component layer: panels mount through `LixityComponents.mount`, so the
  server-rendered loading placeholder no longer survives beside the first
  rendered list (the empty list hosts show the component tree only).
- Research workspace: the claim timeline is a view switch (List/Timeline)
  inside "Thesen & Belege" instead of a separate top-level tab, with a purpose
  line naming both views; the decisions pane states its scope ("deliberate
  choices with rationale, not historical claims"). No API, archive or route
  changes.
- Documentation: the interpretation guide and METHODS state that
  `filter_density`, modal, passive and nominalisation densities include quoted
  speech, and how to read them together with `dialog_pct`; a narrative-only
  variant is recorded as a candidate, not a current contract.

## [0.4.7] - 2026-10-16

### Fixed
- Sentence segmentation keeps blank-line block boundaries: an unterminated
  block (stage note, salutation, sign) stays one fragment unit instead of
  merging into the next block's sentence. Chapter ASL, scene units, corpus
  sentence statistics and the chapter matrix now agree; recompute older
  reports before comparing.
- The serve dashboard checks the manuscript digest when the page is loaded
  and rebuilds itself when the file changed on disk instead of presenting
  stale numbers.
- Closed scene details no longer reserve an empty 520 px block each; the
  deferred-rendering hint now applies only to open details.
- Count labels use singular forms in all seven languages (`1 Datei`,
  `1 Treffer`, `1 Zuordnung`, ...); four unused label rows were removed.

### Changed
- Style comparisons use documented comparability floors: chapters below 100
  words (`MIN_COMPARABLE_WORDS`, the same floor as the diversity indices)
  receive no z*, effect sizes or FDR marks, and sentence-distribution
  features (staccato, cascade, sentence CV, start entropy, first-person
  starts) need at least five sentences (`MIN_COMPARABLE_SENTENCES`).
  Baselines, dimensions and structural series use only comparable chapters;
  the dashboard marks affected values as unavailable and explains the
  minimum. Showing/telling z-scores, means and rankings apply the same word
  floor and mark shorter chapters `comparable: false` with null z-values.
  Recompute older reports before comparing.

### Added
- `about().heuristics` reports `min_comparable_words` and
  `min_comparable_sentences`; the style panel explains the minimum instead
  of hiding the reference when no chapter reaches the floor. Help texts and
  the chapter-matrix guide name the floors, in all supported languages.

### Security
- The dashboard shell carries a per-response nonce Content Security Policy
  (default-deny scripts, inline styles only) plus `Cross-Origin-Opener-Policy`
  and a `Permissions-Policy` denying device APIs.
- Access and debug logs keep the route without its query string, so research
  context and project tokens never reach log files. `SECURITY.md` documents the
  local-server baseline: loopback bind, Host allow-list, Origin guard, payload
  and artifact limits, and explicit non-goals.
- Manuscript review recognizes `adjusted` anchors: when the paragraph text
  changed but the recorded quote still appears exactly once, review names the
  state (highlighted at its current position) and
  `reconcile-manuscript --accept-moved` or the review tab's accept action
  re-pins the refreshed line span, paragraph hash and offsets as a new link
  revision. Editing the quote itself still requires review.
- Chronology accepts a plain hyphen between four-digit years (`1929-1933`) as
  a same-precision range next to the typographic dashes; the claim-time hint
  documents the form and a test verifies every localized example against the
  grammar.

## [0.4.6] - 2026-10-15

### Added
- `lixity research` manuscript-link commands: `link-manuscript` (explicit
  `--selection` or a `--quote [--line]` resolution), `manuscript-links`,
  `review-manuscript`, `find-anchor` (resolve a displayed-text quote to exact
  anchor fields) and `reconcile-manuscript` (preview or write re-pins for
  uniquely moved anchors). The native route
  `POST /api/research-manuscript-reanchor` and an accept action in the review
  tab complete the workflow; earlier anchors stay in revision history.

### Changed
- Manuscript review is paragraph-level: a changed source-file digest
  (`source_changed`) is informational and no longer marks associations for
  review while their paragraph hash, line span and quote still match; only
  changed, moved, ambiguous, withdrawn or re-pinned contexts need review.
- The dashboard folds whole chapters from their heading, opens paragraphs with
  a visible scroll and an arrival flash, keeps jump anchors precise, offers a
  reload action for stale manuscript contexts and filters long claim lists;
  the format-7 note moved behind a disclosure.
- Manuscript-link routes emit stable 409 `code` values (`stale-context`,
  `stale-archive`) that the dialog maps to localized, actionable messages.

## [0.4.5] - 2026-10-15

### Added
- `lixity research <record> --diff` previews an update as a terminal unified
  diff (dossier bodies line by line, other fields as before/after values)
  without writing; the record commands also name the update requirements in
  their help and error messages.

### Changed
- Research list commands (`claim`, `dossier`, `timeline`) read only the record
  kinds they display plus withdrawal state; a 22k-record archive lists claims
  in 0.38 s instead of 3.4 s. Snapshot digests and JSON envelopes are
  unchanged; write paths and lookups keep full-archive validation.
- Research archive snapshots check paths with plain strings and `os.path`
  calls instead of per-component `pathlib` checks.
- `lixity build` reports an unwritable `exports/` folder (sandbox, read-only
  mount) as one `[error]` line with a `--dry-run` hint instead of a traceback.
  `INSTALLATION.md` notes that product versions such as 1.18.0 or 3.0.1 in
  older notes predate the 0.3.0 renumbering.

## [0.4.4] - 2026-10-15

### Changed
- Installation and citation guidance is consolidated around the two published
  channels: PyPI for installing and upgrading, GitHub Releases for pinned,
  checksum-verified setups and Zenodo for citing a released version.
- First release archived by the Zenodo GitHub integration (concept DOI in
  `CITATION.cff`).

## [0.4.3] - 2026-10-15

### Added
- JOSS software paper draft under `paper/` with cited references, and a
  README research note.

### Changed
- The analysis section navigation and the checkbox rows are central components
  (`ANALYSIS_SECTIONS`, `section_nav`, `checkbox_field`), so new panels and
  controls reuse one markup source instead of a parallel implementation.
- The dashboard script is split into cohesive modules (`tooltips.js`,
  `interactions.js`, `research.js`, `project-ui.js`); `dashboard.js` keeps the
  generic core. Load order preserves the original execution sequence.
- Embedded screenshot dimensions are synchronised from the PNG headers after
  `make screenshots`.
- PyPI is the primary installation path in README, the installation guide, the
  landing page and the `llms` bundle; the pinned release wheel with
  `SHA256SUMS` remains the reproducible alternative.

### Tooling
- The release workflow accepts `workflow_dispatch` with a `tag` input and
  builds for PyPI without touching the immutable GitHub release.
- Repository hygiene covers local process, editor and tool state: `.pypirc`,
  `nohup.out`, logs, pid/socket/database leftovers, editor autosaves and
  additional tool caches are ignored and guarded by the hygiene test.

## [0.4.2] - 2026-10-14

### Added
- The Analysis view keeps a section navigation (flagged passages, sentence
  lengths, scenes, motifs, style, chapter matrix) with scrollspy; only panels
  the document actually renders are offered.

### Changed
- Scene detail tables render off-screen content on demand
  (`content-visibility: auto`) and only show project-target and register-median
  columns when the project defines them.
- On phones the analysis toolbar scrolls with the page instead of covering
  almost half of the viewport while reading.
- Control components are shared across views and modals: one `form-checkbox`
  component, a compact `ctl-sm` button size, canonical section headings, and
  removed one-off classes (`secondary`, `ctl-primary`, `research-check`,
  `publication-enable`).
- Layout uses one global `.row` primitive and spacing utilities on the shared
  `--space` scale; the Pages stylesheet consumes the canonical design tokens
  without alias duplicates.
- Local browser checks run in two groups: `make browser` covers the everyday
  core surfaces in parallel workers, `make browser-full` runs every suite
  sequentially before a release.

### Fixed
- Chapters stay fully rendered while scrolling, so anchor jumps and paragraph
  taps keep their exact target; only scene details defer off-screen rendering.
- The research API validates claim confidence, evidence relations and dossier
  languages at the boundary; unsupported dossier languages raise a clear error
  instead of a raw validation trace. Record schema versions share one declared
  union, so the models carry no type suppressions.

## [0.4.1] - 2026-10-14

## [0.4.0] - 2026-10-14

### Added
- `research dossier|claim|decision|sources` accept an explicit `list` verb, and the
  record lists render as a terminal table (`--format table`, ID/title/revision/date);
  the untrusted-host message names the loopback URL to use. The Project & Settings
  page orders by use: project settings, results (analysis + generated files),
  publication, thresholds, then the confidentiality agreement; the artifact list is
  named "generated files" and the manuscript comparison is collapsed.
- Project folders are recognizable while browsing: `/api/project-paths` reports a
  minimal probe for the listed folder (config, research archive, title, language,
  manuscript) and marks project directories; the Open Project chooser shows that
  line and a badge. The header and the Project view show a compact manuscript line
  (chapters, words, file), and the Project view lists the manuscript before the
  project settings.
- Two public-domain example analyses (Effi Briest in German, Pride and
  Prejudice in English) are published on the documentation site: an
  interactive excerpt of the opening chapters plus the complete PDF report;
  `make examples` regenerates every published example deterministically.
- Research record commands accept an explicit `list` verb
  (`lixity research dossier list`), identical to the default listing; the
  style-drift and distribution-shift headings explain Kendall's tau,
  Wasserstein and KS in all seven languages.
- The research Review tab lists saved manuscript associations with anchor
  state, review flags and the pinned quote; it loads when the tab is opened,
  with the shared review refresh and after a save, and never re-anchors or
  writes.
- A dependency-audit baseline (`make audit`, pip-audit) and a written update
  policy; Dependabot now also covers Python packages, and `release-check` runs
  the audit before producing artifacts.
- Every guide is also published as clean Markdown for AI agents
  (`<page>.html.md`, linked from the page and named in `llms.txt`); a generator
  and a sync test keep the alternates identical to their HTML sources.
- A comparison guide explains which manuscript analysis tool fits which job
  (grammar checkers, corpus tools, stylometry packages, story tools and Lixity),
  with a visible FAQ, source links and a clear statement of where Lixity does
  not fit.
- The public sitemap lists the embedded screenshots as image entries and the
  research guide's walkthrough as a video entry, all verified against the
  staged output; the guide articles carry `dateModified` metadata.
- The project dialogs explain their scope in one line. The import and new-project
  forms ask for an optional author name (used for PDF credits, the title page and
  the NDA) and name what the analysis language affects; the server stores the
  author only in a newly created project config.
- Claim creation and claim revision responses carry a `warnings` list when
  `time_period` is not placeable, and the native claim form shows the accepted
  calendar formats.
- `docs/llms-full.txt` bundles the maintained English documentation in
  reading order for AI agents and offline reading; `scripts/build_llms_full.py
  --check` (part of `make docs-check`) keeps the published bundle in sync.
- `lixity.math_core` is the single source for shared mathematical primitives:
  robust scale and significance z, the normal two-sided tail, ratio, share and
  density totalization, plug-in binomial/Poisson standard errors and the
  published Cliff's-delta bands. `style_fingerprint` re-exports the historical
  names.

### Changed
- `research-record-local/1` adds top-level `kind` and `record_id` (additive;
  the `record` body is unchanged). Scene detection also recognizes spaced
  divider lines (`- - -`, `_ _ _`, `• • •`), em-dash rules (`———`) and the
  asterism (`⁂`); the local server accepts IPv6 loopback `Host` headers.
- Dashboard renderer spacing and sizing use shared utility classes from
  `dashboard.css` instead of inline styles; measured and dynamic values stay
  inline, and `tests/test_inline_styles.py` keeps the migrated patterns out.
- Lixity is relicensed: the repository is open source under AGPL-3.0-or-later,
  with an optional written commercial license for integrations that cannot meet
  the AGPL. Writing for any purpose — including self-publishing — needs no extra
  permission now; the former LNCL-1.0 text stays available as `LICENSE-LNCL-1.0`
  for releases up to v0.3.0.
- Page titles and meta descriptions follow one messaging frame: at most 60
  and 155 characters, audience and job first, one differentiator (local,
  nothing uploaded) and no feature lists; the landing page adds durable
  `WebSite` data so results attribute the content to Lixity.
- Research writes reuse the verified snapshot of the current process while
  HEAD still names it, roughly halving claim creation and revision cost on
  large archives; a commit from another process is still detected and
  rejected, and the strict snapshot guard is unchanged.
- The claim chronology accepts `YYYY-MM` months and same-precision month
  ranges, and `api.revise_record` mirrors the CLI convenience of omitting
  `expected_snapshot` (current revision checked, changed associations still
  need explicit pins).
- The README now leads with a plain-language start for non-technical readers
  and keeps command, API and architecture references in a separate map. The
  landing page adds FAQPage, BreadcrumbList and feature-list structured data,
  package keywords and classifiers were extended, and the public research API
  functions carry complete docstrings.
- The Claims timeline shows each dated claim's placed calendar range, counts
  both sections, names the recognized formats and explains why free-text
  periods such as “present day” stay unplaced by design.
- NDA drafts offer the recipient a signature line or clear consent in text
  form (for example an email reply) and no longer ask the sending project
  representative for a separate handwritten signature on the sent copy; all
  seven language templates and the UI hint say consent, not signing.
- Research & Dossiers leads the Sources tab with the local add-source form;
  Zotero import follows as its own block and the retained list is titled
  **Saved sources** in all seven languages. The read-only source dashboard
  reuses the shared analysis renderer instead of a parallel path, and the
  language lexicons no longer carry internal duplicate entries.
- Public documentation and Pages carry the complete social/SEO head contract:
  Open Graph and Twitter images and titles on every page, per-page
  `TechArticle`/`SoftwareApplication` JSON-LD, refreshed sitemap dates and the
  read-only example named in `llms.txt`. `tests/test_pages.py` enforces the
  contract for every staged page.
- Cohesion pass on the native workspace: the dossier reading control and the
  measurement-note line join the reading toolbar, the project bar no longer
  repeats the manuscript name already shown in the status strip, the project
  panel title mirrors its navigation label, the research header shows the
  archive folder name with the full path as a tooltip, and the Zotero capture
  consent has its own label instead of duplicating the local-source consent.
- Project selection uses one resolver (`workspace.resolve_project_target`) for
  the foreground server, the open-project route and the service scope;
  `research/sections.py` owns the ATX section spans and edits (the research
  facade re-exports them, removing the deferred reverse imports);
  `run_server` raises on an occupied port and prints only when the CLI passes
  `announce=True`.
- Server status details and the no-project title come from the shared label
  packs in all seven languages, and every dashboard surface renders through
  `ui.render_analysis` with one labels/identity/metrics wiring.
- Tense heuristics use whole-word stop lists and curated noun exclusions:
  regular English `-ed` past of listed bases counts again (Pride and Prejudice
  +7 tokens), German `-tet` forms and noun confusions no longer count as past
  (Effi Briest −72 wrongly-as-past tokens), with no losses in the measured
  samples (see `docs/STABILITY.md` row 6).
- Sentence splitting treats `no.`/`co.` as utterance endings, the Spanish
  honorific `d` protects initials, paragraph sentence counts ignore tokenless
  fragments (matching the chapter metric), and `language="auto"` resolves with
  the sample text in the structure reports.
- Capability discovery reports image, PDF and manuscript-link support; the
  language and threshold key lists come from `language.LANGUAGE_CODES` and
  `config.THRESHOLD_KEYS`; co-occurrence degrees are returned in sorted node
  order.
- Dashboard and PDF builds reuse cached chapter splitting, precompiled literal
  patterns and one-pass style-layer bounds; a full novel builds about a quarter
  faster with byte-identical output.
- Release publishing attaches every artifact to a draft, attests them for
  `gh attestation verify` and publishes only the complete draft release;
  repository-level immutable releases protect published assets and tags.

### Fixed
- The analysis report PDF is composed as a document instead of flattened
  Markdown: an unnumbered cover page, real tables with right-aligned numeric
  columns, repeated header rows, whole rows and a PDF outline; the Guiraud
  label prints as `V/√N` instead of raw LaTeX. Book covers start on the
  optical third of the page.
- Chapter and status counters inflect their units (1 Absatz, 0 Auffälligkeiten),
  the reader panel uses the same name as its toolbar control, the footer separates
  product label and title, and an uninitialized research archive now shows the
  localized state instead of the English API message in the reader and
  manuscript-link panels.
- Dashboard artifact links use the served `/artifact/<name>` route instead of a
  bare filename, and the 200 MiB artifact serving limit is enforced.
- The configured dialogue cue compiles case-insensitively in the analysis core
  and profile, matching the documented cue contract; default patterns are
  punctuation-only and unchanged.

## [0.3.0] - 2026-10-12

### Added
- Manual manuscript quote–claim associations with explicit local retention,
  Unicode-codepoint paragraph anchors and exact claim pins. Creation, listing
  and structural review share the Python/native API; first opted-in save uses
  research record/manifest v7. Earlier archives remain unchanged on reads.
- Dossier research and companion readers list current explicitly linked claims
  with the existing claim viewer/history and exact-association saved quote counts.
  Counts do not infer whether prose uses a claim.
- Explicit selected-project publication fields in the existing Settings form
  and configuration loader, with one shared model for optional publisher/printer
  details, edition, year, format ISBNs, rights text, credits and other imprint
  information. A5 reading copies can include entered imprint text; no identity,
  address, copyright or DNB catalog statement is inferred.
- Shared PDF title/author/language metadata, A5 chapter bookmarks and bounded
  page headers. Book body pages retain physical folios; A4 sheets/reports show
  current/total page counts outside the body area.
- Publication guidance distinguishes German state print-imprint requirements,
  voluntary ISBNs/rights notices, separate legal deposit and BFSG ebook scope.
  Exports remain A5 book/A4 sheet/A4 report PDFs, without EPUB or PDF/UA/PDF/X
  certification.

### Changed
- Product version 0.3.0 describes development maturity before 1.0.
  Existing features and historical published releases/tags remain. JSON/storage
  versions are independent; 0.3.0 supports research records/manifests v1–v7.
- A collapsed global PDF menu remains accessible across all three workspace
  views, with one download action and the A5 reading copy default.
  Manuscript search and chapters appear before statistical diagnostics.
- Ordinary authored CLI `--update` requires the reviewed record revision, change
  kind and reason, while the archive-wide snapshot is optional. Same-record
  changes and races fail without retries; an explicit digest stays strict.
  Unchanged association pins remain, and changed associations in convenience
  mode require explicit reviewed versions. Strict Python/HTTP/batch guards stay.
- Release preparation reuses one shared source/tag/artifact checker through
  `make release-check RELEASE_TAG=vX.Y.Z`, including installed-wheel smoke checks.
  Version editing, review, tagging and publishing remain separate actions.
- GitHub Actions are reduced to one `check` job per pull request or `main` push.
  Browser and cross-platform suites run locally through `make browser` or on
  manual dispatch, and the tag workflow only builds, verifies, smoke-installs
  and publishes the reviewed release artifacts. Its third-party publisher is
  pinned to a reviewed commit.
- Dashboard and PDF builds reuse one selected-project configuration read when
  the manuscript and root share a directory. Author and publication settings
  remain project-local when they do not.
- Selected-project title, author and publication are saved together through the
  shared prepared configuration writer. Settings prepares the candidate view
  before committing; validation/read/render/write failures preserve previous
  metadata and session/cache state. Publication saves require selected-context
  tokens, and root metadata changes invalidate stale PDF download tokens.
- Publication stays in a collapsed disclosure within the existing Settings
  form. Dashboard and Pages presentation share the canonical bundled design
  tokens while exported dashboards remain self-contained.

### Fixed
- Project switching scopes a startup/custom title to its original workspace.
  Another book's header and NDA field use that project's identity. An explicit
  service restart into another project clears an inherited title unless replaced.
- Text and binary writes share fail-closed same-directory staging, fsync,
  original-mode preservation and cleanup. Replacement failures propagate
  instead of falling back to direct overwriting; text decoding failures use
  the existing `OSError` read-error boundary.
- Changed artifacts published in the same minute retain distinct versions.
  Stable links/copies are prepared before atomic replacement; failed publication
  preserves the previous stable artifact and reports an error before rotation.
- Marker read/encoding/write failures return clear HTTP 500 JSON errors;
  failed staged writes preserve manuscript bytes and do not report success.
- Genuine TrueType subsets retain glyph metrics and composite outlines,
  Unicode aliases copy correctly, and embedding-permission checks respect
  table versions. Unused font roles do not constrain the requested PDF layout.
- PDF headings and body text no longer share a baseline; first-line paragraph
  indents, long-header bounds and manuscript title detection reuse the shared
  layout/parser paths.

## [3.0.1] - 2026-10-11

### Fixed
- Foreground `serve` and managed `service start`/`restart` accept
  `--min-chapters`, including saved restart values. Previously, the controller
  accepted this option but its worker rejected it before server startup.

## [3.0.0] - 2026-10-11

### Added
- Read-only claim timelines in the CLI, Python API, HTTP API and native Claims
  view. Conservative CE year/ISO date/range placement preserves period labels,
  keeps unplaced periods visible and infers no date from record creation time.
- Authored cause/effect relations between exact claim revisions, with optional
  rationale, active/retracted state and shared correction/history/batch support.
  `results_in` aliases stored `causes` in the same direction; self-links fail,
  authored cycles remain, and no causal truth or additional edges are inferred.
- `research cite --query` resolves one source paragraph or returns ambiguous
  search candidates. Numbered selection requires the displayed snapshot and
  same query; exact `--passage` retrieval remains available.
- **Find source passage** reuses the existing Search/evidence draft flow.
  Optional evidence project/snapshot/claim-revision guards and native root
  tokens reject changed reviewed context; delayed search results are discarded.

### Changed
- **Breaking API change:** claims lists now consistently use
  `research-claims-local/2` with `claims`, `project_id` and `snapshot` from one
  read. The previous v1 list envelope has no alternate compatibility mode.
- Explicit causal relation writes opt storage into `research-local/6` and a
  v6 manifest, which earlier readers reject. Existing v1–v5 archives and their
  source/claim/citation/history bytes remain readable without conversion;
  timeline reads do not upgrade them. Export/restore preserves the existing
  bundle format and complete relation history.

## [2.4.0] - 2026-10-11

### Added
- Packaged `lixity service start|stop|restart|status` lifecycle commands and
  `python -m lixity`, using the installed Python without a source checkout.
  Default startup is an empty application-owned workspace; projects are explicit.
  Ownership/readiness checks and shared launchers replace separate Sh/PowerShell
  lifecycle implementations. Login startup remains an explicit manager choice.
- Native manuscript PDF downloads at the top of Manuscript & Analysis, with
  A5 reading layout as the default, A4 submission sheet and analysis report.
  Generation is explicit and reuses the CLI composer; standalone HTML has no
  download action. PDF attachments create no server export files and change no
  manuscript or research archive.
- `POST /api/manuscript-pdf` accepts a layout and opaque selected-context token,
  rejecting stale contexts instead of exporting a different project's manuscript.
  The response is a PDF attachment, separate from NDA generation.
- Source text selection prepares a claim evidence-link draft with the selected
  text and full retained passage shown before an explicit save. Ambiguous or
  cross-passage selections are refused; citations retain their existing scope.
- An optional Dossier alongside view keeps the manuscript and a chosen saved
  dossier together, with stacked panes on narrow screens. Reading creates no
  archive changes; closing restores analysis panels and retained manuscript state.
- `lixity research link PASSAGE_ID CLAIM_ID` creates an evidence link using the
  existing validation, defaults and version pins. `link-evidence` remains available.

### Changed
- Recommended application installation uses a pinned release wheel with
  uv-managed Python, without a Git prerequisite. uv owns installation, explicit
  release replacement and removal; project storage and application state remain.
- Existing-archive research CLI commands can omit `--project` when the current
  directory itself contains a verified initialized archive. Explicit paths win;
  no parent, environment or previous-project lookup is performed. Initialization
  and restore destinations remain explicit.
- Research status labels use author-facing language while preserving stored
  values and their interpretation limits; a linked source is not factual proof.
- Optional `project_token` on dossier reads binds the companion reader to the
  displayed manuscript selection. Calls without it retain their existing JSON.

### Fixed
- Local HTTP startup no longer performs reverse DNS after binding. This removes
  a confirmed macOS startup stall while preserving the actual bound port and
  readiness checks for foreground and managed servers.

## [2.3.0] - 2026-10-10

### Added
- Goal-oriented welcome steps lead from manuscript import and language confirmation
  to reading a passage. Further tools use a collapsed native disclosure, and empty
  analysis opens the existing import directly without submitting a file.
- A compact review entry links an actual tense-flag candidate in source order (or
  the opening passage), chapter patterns and available sentence rhythm. These are
  routes for human review, not a literary quality ranking.
- A public, read-only synthetic example and a three-minute first-look guide.
  The report is generated by the shared engine with explicit defaults, supports
  existing paragraph/filter/chart interactions, and accepts no uploads or edits.
- `research dossier-image` captures a local PNG/JPEG and revises its dossier in
  one atomic API operation. Explicit retention permission, archive snapshot and
  dossier revision are required; existing validation and image limits apply.
- `lixity pdf --layout report|book|sheet` composes a PDF document without any
  external converter. Fonts are embedded as TrueType subsets with Unicode mappings. Covered
  characters remain searchable and copyable; unsupported visible characters
  fail explicitly. The sheet layout is a fixed grid of up to 30
  lines of at most 60 characters; the book layout is A5 with a serif measure
  and chapter openings.
- The analysis toolbar searches the manuscript itself and filters the chapter
  list to the matching paragraphs, with a match count and step-through. Until
  now only the research archive could be searched. Manuscript text is inserted
  as text nodes, so a phrase that looks like markup stays inert.
- PDF layouts follow measured typographic practice: type size is fitted to the
  real text so lines land in the 45-75 character band, paragraphs are broken by
  a shortest-cost search instead of greedily, justification tightens as well as
  stretches and never stretches a line's last one, book margins mirror for
  double-sided printing, baselines sit on a leading grid, and Markdown emphasis,
  code and table syntax no longer leak into the exported text.

### Changed
- Opened paragraphs show the manuscript text before their measurements and
  marker actions. Paragraph values use a compact native disclosure, localized
  as “Values” in English and “Werte” in German.
- Closed paragraph contents are created when opened with JavaScript enabled;
  the no-JavaScript fallback keeps the complete paragraph text readable.
  Manuscript search still checks the complete embedded paragraph text and renders
  markup-like text safely. The self-contained HTML remains usable offline; the embedded
  manuscript and measurement data still grow with the input.
- Chapter comparison, style reference, dimensions and structural diagnostics
  share one tabbed style area. Existing anchors select the relevant panel;
  keyboard navigation and readable panels without JavaScript are preserved.

### Fixed
- Restarting a stopped local service attempts startup instead of returning
  success after the no-op stop; startup failures retain a nonzero exit status.
- PDF command discovery in `about` and Bash/Zsh completion matches the implemented CLI.
- Active manuscript search takes priority over the flagged-only filter, so
  unflagged matches remain visible. Clearing search restores the selected filter.
- PDF page numbers embed their required digits even when the manuscript has none.
  Final lines obey the page measure, overlong words wrap without losing
  characters, and justified text applies negative word spacing correctly.
- PDF rendering checks every drawn visible character against its selected font
  and reports an unsupported character with its font role and Unicode codepoint.
  Default report fonts prefer DejaVu Sans regular/bold for generated analysis
  symbols; explicit font choices remain supported.
- Research shell-completion command names come from the same parser metadata as
  `about`, including image attachment and the existing revision/review commands.
- Supplied source-context JSON must be an object. Invalid scalar/array/null input
  is reported through the CLI error channel without accepting a capture.
- The security policy links to the current release instead of retaining an old
  version claim. Image guidance distinguishes generated references from evidence.
- Long research titles wrap within their cards on mobile. Project-opening
  guidance explains that CLI work does not switch an already running web server.
- Source/dossier refreshes coalesce pending reads, ignore superseded responses
  and preserve unchanged open details. Full-list reconciliation is linear.
- OCR page timeouts stay within their original budget even when floating-point
  deadline subtraction rounds upward; the shared deadline still expires.
- Default nominal-suffix counts exclude curated function words across corpus,
  chapter and paragraph measurements. Custom regex semantics are preserved.
  Regenerate older nominal-style reports before comparison.
- Unavailable show/tell comparisons use a clear status instead of empty score
  tiles. Paragraph guidance explains density units and small-sample effects;
  an empty marker list is no longer described as a clean manuscript.
- API browser diagnostics report request metadata without retaining response
  contents in the console.

## [2.2.0] - 2026-10-09

### Added
- A project-scoped Author name setting persists in `lixity.toml` and fills the
  project representative in NDA exports. The five recipient/document fields
  and stateless download interface remain unchanged; no personal default is built in.
- A read-only title/author comparison recognizes explicit flat manuscript
  metadata and leading title-page bylines. Missing, unsupported and mismatching
  values are distinct; it neither infers authorship from prose nor edits text.
- Optional `project_author` in project-owned NDA text models, retaining all
  existing placeholders. Unknown fields and invalid configured names fail visibly.

### Fixed
- Saving an author updates only that project field, preserves unrelated TOML,
  comments and line endings, and refuses malformed or concurrently changed files.
  Unavailable projects cannot accidentally store personal data in the server cwd.
- Invalid author metadata does not abort unrelated mathematical analysis;
  identity/NDA consumers report it explicitly. Existing threshold and title
  session behavior remains unchanged.
- Author identity excludes global and ancestor defaults and stays with the
  selected project even for a nested imported manuscript. Unreadable manuscripts
  report an unavailable comparison rather than claiming metadata is missing.
- Workspace tabs and dialog controls inherit the shared UI font. Settings,
  dialogs and research headings reuse text, weight and line-height tokens;
  technical identifiers use the shared monospace role.
- Metadata-only PDF refresh reports retained-extraction verification instead of
  announcing skipped OCR work. Extraction reuse and revision contracts are unchanged.
- Opening a live workspace no longer requests a missing server favicon or emits
  its unrelated console error; the offline dashboard declares an empty inline icon.

## [2.1.0] - 2026-10-08

### Added
- Local PNG/JPEG references in dossier full, section and history views, with
  browser-only preview, explicit retention, exact saved-image versions and
  keyboard enlargement. Capture and dossier revision publish in one commit;
  rejected saves accept neither. Existing archive export/restore and audit apply.
- Section editing reuses the revision editor and canonical heading parser,
  preserving concurrent changes outside the selected subtree. Contextual claim
  and decision actions select the current dossier by title in existing forms.

### Fixed
- Sequential decision acknowledgements advance only tokens from their own
  accepted operation. External changes still require explicit review; current
  flags and counts stay aligned without stealing unrelated draft focus.
- Marker notes have explicit Save/Cancel, visible errors, retained failed drafts
  and a pending guard; real HTTP failure statuses cannot appear successful.
- NDA agreements use shorter, direct wording in all seven languages. The recipient
  field is clearer, output titles omit the software “draft” label, and signing
  guidance stays in the app. The five-field, stateless interface is unchanged.
- Settings share the core numeric policy, preserve exact floats and unposted
  fields, and remove artificial UI ceilings/decimal step rounding. Invalid
  JSON types, nonfinite values and inconsistent bounds fail visibly.
- Image references validate exact project/source/version ownership, including
  purge placeholders. Raster imports never retry external publication conflicts;
  textual analysis rejects image sources before decoding.
- Restored shared layout configuration and inline Markdown helpers keep existing
  book adapters importable; attribute values and links remain treated as data.

### Changed
- The native workspace has one Update analysis action; both HTTP aliases and
  distinct embedding capabilities remain supported. Manuscript selection opens
  its import preview directly; confirmation still creates a separate project.
- Initial research lists reuse the overview response. Optional form details are
  collapsed, paragraph filters have a reset and scene links use actual containing
  chapters. No persistent cache or invented scene positions are introduced.
- Version-purge Tombstones with explicit source ownership use `research-local/2`.
  Existing v1 bytes remain unchanged; 2.0.0 rejects the new owner-bearing records.
  PNG/JPEG source bytes have no fabricated text extraction or passages.
- English documentation and reviewed synthetic screenshots follow current feature
  workflows. Service setup uses one port setting; API examples avoid duplicate
  analysis passes. New browser cases join the existing single Chromium job.

### Removed
- The source-only experimental Unlimited-OCR CPU bridge and its adapter-specific
  parser test. Built-in local Tesseract and the generic external-worker protocol
  remain supported; custom model runtimes belong to their deployment projects.

## [2.0.0] - 2026-10-07

### Added
- Opt-in sequential research checkpoints retain completed extraction across
  interruptions and publication conflicts. Resume verifies files, configuration,
  project and source identity; changed HEAD needs explicit acknowledgement.
  New checkpoint envelopes preserve ordinary ingest and archive contracts.
- Concise editable NDA drafts in all seven interface languages, with name,
  optional address, project name, date and place. Protected disclosure and
  signature sections remain. Native PDF/text downloads do not register people
  or persist agreements, and long text is paginated without truncation.
- A semantic chapter-score table and native rotation/zoom controls accompany
  the 3D plot, including chapter navigation without JavaScript.
- A live `GET /api` index describes registered routes, and research commands
  expose consistent JSON aliases without changing their human-facing defaults.
- Recently opened projects appear on the welcome screen and Open dialog;
  browsing reuses the native chooser, with explicit local history clearing.
- Plain-language revision acknowledgement controls are localized in seven
  languages and pin exact decision/dossier versions in v5 research events.
- The guided OCR/Zotero setup check reads connection metadata without importing
  records, installing software or writing configuration.

### Fixed
- PDF capture extracts a stable copy of the exact retained bytes, preventing
  mismatched evidence if a source file changes during extraction.
- Native NDA export uses the effective project language or an explicit document
  language. Invalid templates are rejected; document responses go directly to
  preview/download without a recipient registry or server file publication.
- Browser debug preferences explicitly save both enabled and disabled values,
  surviving reload with server debug enabled. Request and error-detail logs use
  one UTC timestamp writer.
- Expected client disconnects during cancelled browser requests no longer
  cause false HTTP 500 responses or tracebacks; NDA responses use the shared sender.
- Paragraph chips and style controls have at least 24px targets, or 44px with
  coarse pointers, including the pressed state.

### Changed
- Maintained docs remove private-adapter export/backup claims and explain
  five-field NDA downloads, editable text models and heuristic limits.
- Research overview requests validate one archive snapshot and reuse the
  listing helpers. Source versions are grouped once rather than rescanning
  the archive for every source; there is no persistent cache or output change.

### Removed
- NDA recipient databases, numbering, encryption/unlock/status administration
  and project Python export adapters. `/api/nda-draft` replaces the old NDA
  management actions. Back up prior project NDA data before replacing generated
  drafts; software regeneration does not amend a signed agreement.

## [1.25.0] - 2026-10-06

### Changed
- Style dimensions use standardized tied midranks on one complete chapter set.
  Scores and explained variance share that space; missing chapters are omitted
  from the plot and its coverage is shown. Passport schema 4 adds
  `meta.dimension_space` and `meta.dimension_chapters` without renaming fields.
- Shared supported-prose handling excludes metadata, headings, comments, code
  and footnote definitions from analytical measurements. Quoted prose remains
  measured; paragraph profiles retain their narrower body/list scope. Legacy
  whitespace counts remain separate. Rebuild exports and comparisons after
  these input-scope and numerical corrections; previous scores can change.
- Seven-language UI help uses plain-language definitions and reading examples;
  existing methods, stability, command, research and interpretation guides
  distinguish exploratory signals from calibrated inference. Nominal selections
  and empty diagnostics do not certify prose.
- Syllable calculations reuse word frequencies within each request, without a
  global cache. Empirical distribution comparisons use one sorted linear merge;
  segmentation accumulates centred moments instead of rescanning segments.
- Actions runs native Poppler cases on the primary Linux Python version and
  macOS; other compatibility versions retain all non-native tests. Separate
  browser/platform workflows use built-in path filters, cancellation and caches;
  core checks remain unconditional and release checks install Poppler explicitly.

### Fixed
- Guarded changepoint segmentation now considers every predecessor: the old
  pruning rule could discard the best partition. The legacy `pelt_changepoints`
  name remains, with quadratic time and linear memory. Per-endpoint anchors
  preserve small variances after distant observations or large translations.
- Wasserstein distance integrates empirical CDFs correctly for unequal sample
  sizes. KS returns probability 1 for identical distributions and uses a stable
  limiting-tail calculation for small distances; probabilities remain approximate.
- Sn uses the original low outer/high inner order statistics. Qn uses the modern
  asymptotic factor 2.21914. Neither adds finite-sample correction. The unchanged
  Kendall statistic is labelled tau-a, and the legacy degree-fit helper correctly
  attributes its approximate exponent and discloses its uncalibrated probability.
- MTLD averages the two directional lengths rather than pooling their factors.
  Threshold, partial-factor and short-text policies remain documented.
- Explicit tokenizer flags survive every analytical surface. German/English
  default patterns retain accented words and emphasis; LF/CRLF paragraph boundaries
  agree, and the configured inclusive threshold includes exactly eight words.
- Chapter headings inside code or comments no longer split prose; scene dividers
  around chapter prose are not mistaken for document metadata. Source anchors
  remain unchanged. Structural jump links follow measured chapters when a feature
  is unavailable in an intervening chapter.

## [1.24.1] - 2026-10-04

### Fixed
- Native PDF extraction validates its timeout before checking for Poppler tools,
  so invalid settings fail consistently whether or not Poppler is installed.
  This is the first published artifact release for the features introduced by
  the v1.24.0 source tag; that tag is retained without binary release assets.

## [1.24.0] - 2026-10-04

### Added
- Scene/register reports in the API, CLI and dashboard: existing measured
  features, explicit project targets, separate manuscript-only register
  medians/MAD, sample counts and approximate standard errors. No genre targets
  or literary quality judgments are built in.
- Read-only three-way revision previews, explicit conflict choices and atomic
  groups of authored revisions. Drafts and reasons survive failed saves.
- Decision impact and editorial review views based on explicit links, dates and
  revision pins; these are maintenance candidates, not semantic validation.
- Optional local Tesseract OCR without a worker service, installed-language
  diagnostics and honest versioned provenance (research activity/manifest v4).
- Opt-in text/Markdown research source and audit summaries, bounded human
  lists and an explicitly requested interactive pager. Default JSON is retained.

### Changed
- Shared configuration resolution keeps explicit corpus settings aligned across
  CLI, API and dashboard. Scene measurement reuses the chapter feature engine
  without a second corpus analysis per scene; display reports reuse already
  measured whole chapters when no scene dividers are present.
- Scene terminal reports reuse the shared translated labels, units and number
  formatting. Safe terminal text lives in the common formatter rather than the
  experimental research package; JSON output is unchanged.
- Actions runs the collected Python tests once per environment, cancels
  superseded runs, caches Pip downloads and discovers all platform research
  tests. Release tags retain their dedicated checks instead of a second full
  test matrix; platform and Python coverage are preserved.
- Wheel verification compares every package filename and byte with the current
  source, catching removed modules left in incremental build directories.
- README and the project page introduce six features with contextual screenshots
  and links to related views, replacing the large image galleries. The page uses
  a simpler responsive layout, native full-size image links and a shared theme
  preference across the HTML guides.
- Installation, onboarding, localization and contributor guidance use shorter
  English explanations. German remains the first focus for linguistic resources;
  the default analysis language remains English.
- Screenshot generation reuses the original dashboard and shared browser startup
  helper. `make serve` and `make stop` delegate to the existing port-scoped
  launcher. Dated internal review reports are removed from maintained product
  documentation and the Pages publication boundary.

### Fixed
- Dossier section handling ignores fenced code, rejects ambiguous repeated
  headings and preserves unrelated bytes and line endings. Reads and edits use
  the same subtree boundary, preserving nested notes in a read/edit round trip.
  Existing decision dossier pins are retained when editing their ID list.
- Configured chapter boundaries and empty units use shared numbering; fenced
  scene separators are ignored. Headerless drafts retain every paragraph and
  original line anchor rather than dropping their first line as a title.
- Custom chapter headings are excluded from global prose counts as well as
  chapter measurements. Patterns matching a whole heading retain the following
  prose. Entropy uses stable summation and renders zero without a negative sign.
- New native PDF captures identify Poppler rather than an unrelated OCR model.
  Existing cached provenance is preserved. Native extraction deadlines reject
  incomplete output, and failed worker or Tesseract probes report failure.
- CI uses `actions/setup-node@v7`, whose Node 24 runtime and updated cache code
  remove the Node 20 action-runtime and built-in `punycode` deprecation warnings.
  The browser job continues to test with Node 22.
- Deprecated HD-D sampling arguments and the legacy matrix wrapper remain
  available. Their earlier removal dates are deferred; replacement guidance
  reflects the exact estimator and separate matrix data/rendering interfaces.
- Guides correctly describe phase-based import progress, native NDA support and
  the research archive's introduction in v1.16.0.

## [1.23.0] - 2026-10-03

### Added
- **Local research list filters:** Sources and dossiers can be filtered by title,
  tags and ID; dossiers also match excerpts and section names. Filtering uses
  loaded metadata, keeps opened details and association options, and sends no
  request while typing. Full-text research search remains a separate action.
- **Visual loading feedback for Research Workspace**: Added centralized accessible loading indicators (`loading_state()`, `.loading-spinner`, `.ctl-status.loading`) and localized labels across 7 languages, providing immediate visual feedback in the header and list views while research project data and records are being initialized or retrieved.
- **Structural diagnostics panel in Web UI**: Integrated PELT changepoints (stylistic phase shifts across chapters), Mann-Kendall monotonic trend tests (gradual stylistic drift), and early-vs-late distribution shifts (Wasserstein distance and Kolmogorov-Smirnov test) into the web dashboard style suite (`#structural`), complete with clickable chapter anchors and full localization across 7 languages.
- **Fluid responsiveness enhancements**: Refined multi-column and table layouts across tablet, mobile, and intermediate viewports; enabled fluid clamp sizing for the 3D stylistic space canvas, prevented table scrollbar overflows on compact metadata tables, and improved touch target minimum sizes for mobile devices.
### Changed
- Metric help in all seven languages now distinguishes descriptive signals from
  literary judgement: Guiraud remains length-sensitive, Flesch can exceed 0–100,
  long sentences do not establish syntactic nesting, and style bands are not
  mandatory targets. Show/Tell explains intentional register differences;
  chapter-based scene estimates disclose their units.
- English and German terminal/Markdown reports use neutral sentence-length
  descriptions and no longer infer syntactic complexity or pace from length.
- The deprecated `research_api.claim_matrix(format=...)` compatibility wrapper
  remains available. Its previously announced v1.23 removal is deferred to a
  future release; the data and rendering replacements remain recommended.
- **Workspace navigation:** Research & Dossiers, Manuscript & Analysis, and
  Project & Settings have separate views. New Project, Open Project and optional
  guidance remain accessible from every view.
- **Manuscript selection:** File selection and drag/drop show the filename without
  submitting. The native server's **Continue to import…** opens the existing import
  dialog; confirmation creates a separate project. Embedding hosts with the load
  capability retain **Analyze manuscript now →** and the existing load payload.
- **NDA presentation:** The capability-gated manager is a native details panel,
  collapsed initially; its backend behavior is unchanged.
- **Frontend architecture modularization**: Refactored the monolithic 1600-line `render_dashboard()` in `src/lixity/ui/dashboard.py` into focused, single-responsibility modules: `modals.py` (project creation, open, and research revisions), `research_panel.py` (Zotero ingest, search, dossiers, claims & evidence, editorial decisions, grounding), `narration.py` (sentence distribution, dialogue, characters, pacing, motifs, showing vs. telling), `heatmap.py` (z-score heatmap matrix and self-calibrating style passport reference bands), and `markers_panel.py` (work markers table). Preserved all DOM IDs, CSS class contracts, and multi-language support.
- **Client-side API consistency**: Standardized the research matrix endpoint URL in `dashboard.js` to dynamically prefix `(API || "/api")`, avoiding hardcoded root path assumptions.
- **Touch and tablet research tab responsiveness**: Enhanced `.research-tabs` with clean touch-friendly horizontal swipe scrolling and flex-gap on tablet and mobile viewports.

### Fixed
- Dialogue token counts use the configured word tokenizer for both numerator
  and denominator, matching chapter, paragraph, dialogue and pacing reports and avoiding
  punctuation-only counts above 100%.
- Show/Tell ranking arrays stay empty when chapter balances cannot be
  distinguished. The dashboard shows unavailable comparisons as dashes for
  fewer than three chapters or absent comparative signals.
- Maas a² returns its defined value for a corpus with a single word type when
  the existing 100-token minimum is met.
- A successful OCR worker probe no longer hides an invalid timeout or missing
  rasterizer. PDF extraction warnings survive explicit native fallback through
  local, batch and Zotero import results and appear in dashboard import status.
- Manuscript selection stays locked against duplicate submissions while reading.
  Import previews clear before a replacement read, ignore obsolete completions
  and remain unconfirmable on read failure. The import file picker also supports
  click, Enter and Space without an empty-selector error.
- **Port-scoped server lifecycle**: `scripts/lixity-start.sh` and `scripts/lixity-start.ps1`
  now scope PID and log files per port (`lixity-<PORT>.pid` / `.log`), preventing
  cross-port `stop` signals and ensuring multi-instance isolation.
- **Stale and recycled PID handling**: `status` and `stop` verify port responsiveness
  and automatically clean up stale or recycled PID files without targeting unrelated processes.
- **Config recovery documentation**: corrected `docs/USAGE.md` to remove references to
  non-existent threshold fields in the CLI JSON meta block.

### Documentation
- Regenerated and reviewed 35 screenshots using public-domain analysis text and
  synthetic project/research fixtures; README and Pages galleries include mobile
  states, complete dialog forms and full-size links.
- Methods and workflow guides clarify minimum-data guards, manuscript-only style
  baselines, heuristic limitations, phase progress messages and OCR health checks.

## [1.22.0] - 2026-09-30

### Changed
- `lixity.server` split from one 1655-line module into a focused package
  (`runtime`, `views`, `_state`, `_base`, `routes_project`, `routes_research`,
  `routes_nda`, `routes_markers`, `handler`, `constants`). The public import
  surface is unchanged.
- HTTP routing is declarative via `GET_ROUTES`/`POST_ROUTES` tables, replacing
  the `do_GET`/`do_POST` if-ladders.
- Research API separates data from rendering:
  `compare_source_to_manuscript()` returns only data (the `format` parameter and
  two `@overload` stubs removed), and `claim_matrix_data()` /
  `render_claim_matrix()` replace the mixed `claim_matrix(format=...)`.
- Cross-platform server lifecycle scripts: `scripts/lixity-start.sh`,
  `scripts/lixity-start.ps1`, `scripts/lixity.service`, `scripts/lixity.plist`,
  plus `make serve` and `make stop`.

### Deprecated
- `research_api.claim_matrix(project, format=...)` emits a `DeprecationWarning`
  and will be removed in v1.23.0. Use `claim_matrix_data()`,
  `render_claim_matrix()`, or `claim_matrix_format()`. JSON output and the
  `lixity research matrix` CLI are unchanged.
- `lixity.diversity.hd_d()` and `hd_d_stats()` accepted `seed` and
  `min_samples` as no-ops left over from the superseded Monte Carlo estimator.
  They are now keyword-only, warn when passed, and are removed in v1.24.0.

### Fixed
- **Silent analysis change**: a malformed `lixity.toml` was treated as absent,
  so the run reported default language and thresholds and still exited `0`. A
  present-but-unreadable or unparseable file now warns and names the path.
- **Silent capture truncation**: an undeterminable PDF page count was assumed to
  be 1, so a multi-page document could be captured as one page and still report
  success. The extractor now refuses with actionable guidance.
- **Project NDA adapter**: an adapter raising at import time disabled the
  feature instead of falling back, and the fallback was silent. It is now caught
  as `Exception` (never `BaseException`) and announces itself.
- NDA PDF receipts now contain a valid cross-reference table and declare a font
  resource; previously no text was extractable.
- `lixity serve` reports an occupied port with actionable guidance instead of a
  bare `OSError`.
- `research search --strict` reports a missing index as such instead of blaming
  FTS5 availability.
- The server lifecycle launchers detected readiness by grepping the log for the
  startup banner, which a block-buffered daemon never writes; they now probe
  the port.
- `nda` encrypt/decrypt return annotations no longer depend on the undeclared
  optional `cryptography` package being installed, which broke strict mypy in
  the configuration CI uses.
- The documentation version-drift check now enforces that statements asserting
  the current release name the single source of truth, instead of only checking
  whether its own pinned strings need rewriting.

### Removed
- `layout.py` and `inline_markdown_to_html()`: unreachable code with no
  references outside their own test.
- `vargha_delaney_a()`, `contextlib_suppress()` and `parse_markdown_file()`:
  dead helpers. Vargha–Delaney A was never emitted; `METHODS.md`,
  `STABILITY.md` and `llms.txt` now describe the Cliff's δ labels that are
  actually reported.

### Docs
- `AGENT_PROFILE.md` added and delegated to from `AGENTS.md`, with agent
  operating rules covering verification, formatters, data boundaries,
  escalation, and the silent-degradation failures this release fixed.
- NDA HTTP endpoints documented in `docs/AGENTS.md` §5.2.
- `ARCHITECTURE.md` documents the server package; `docs/research/USAGE.md`
  retitled from "pilot" to "archive".
- `STABILITY.md` gains register rows 52-55; two long-standing rows were
  rendering with the wrong column count because of unescaped `|` in table cells.
- Published-surface audit: six `../` links resolved in the checkout but 404'd on
  Pages, because staging flattens `docs/<name>` to `/<name>`. Now absolute URLs,
  with two tests validating the staged tree rather than the checkout.
- Four documents described the search freshness check as comparing manifest
  timestamps; it compares the recorded snapshot digest. Corrected.

### Verified
- Issues #10, #11 and #12 checked as 30 executable assertions mapped onto their
  stated claims; 30/30 pass. Evidence posted to each issue and all three closed,
  with the remaining work split into #13 and #14.
- 564 tests, 2764 subtests under `-W error`; the staged Pages output resolves
  all 94 of its relative links and heading anchors.


## [1.21.0] – 2026-09-30

### Added

- Research engine — claim-evidence matrix export (Issue #11):
  - `lixity research matrix --format md|csv|json [--output FILE]` generates a
    structured table of claims with linked evidence, confidence levels, and source keys.
  - `claim_matrix()` API for programmatic access.
- Research engine — Zotero batch ingest (Issue #11):
  - `lixity research zotero-ingest --item-key <KEY>` ingests all eligible PDF and
    text attachments of a Zotero parent item with per-attachment error isolation.
  - Multi `--attachment-key` support for batch ingestion in a single call.
  - `lixity research ocr-status --probe` / `ocr_status(probe=True)` pre-flight OCR probe.
  - `--fallback` / `LIXITY_OCR_FALLBACK=1` for Poppler `pdftotext` fallback; reliable
    multi-page PDF detection via `pdfinfo` or binary `/Count` scan.
- Research engine — cross-corpus Markdown grounding report (Issue #11):
  - `lixity research compare --format md [--output FILE]` exports Jaccard similarity,
    Dunning G² key terms, chapter density table, and top-N term breakdowns as Markdown.
  - `compare_source(..., format="md")` API with overloaded return types for mypy strict.
- Web dashboard — research panel improvements:
  - Search-hit highlighting via `<mark class="search-hit">` wrappers in results.
  - Collapsible dossier section outlines in list cards with section overview badges.
  - Compare/grounding card renders Dunning G² key terms with accent border styling.
- Localization: `research_source_key_terms` label added in 7 languages (EN/DE/FR/ES/IT/PT/NL).

## [1.20.0] – 2026-09-29

### Added

- Research workflow ergonomics and friction reduction (Issue #11):
  - Automatic fresh FTS5 search indexing by default when catalogue is stale, with
    an explicit `--strict` flag to fail instead of reindexing.
  - Multi-file batch ingestion returning `research-batch-ingest-local/1` with per-file
    outcomes, error resilience, and progress reporting to stderr with `--progress`.
  - Section-bounded dossier reads via `--summary` and `--section <name>`, as well as
    section-level revision targeting without overwriting entire dossiers.
  - Decision-dossier linking and automated `review_needed` tracking when decisions
    affecting a dossier are added or updated.
  - 4-phase Zotero literature acquisition walkthrough and backup scope comparison
    table in documentation (`docs/research/USAGE.md`).
- Project-isolated NDA management provider and server endpoints (Issue #12):
  - Configurable project capability interface (`ProjectNdaProvider`) with PBKDF2
    key derivation, authenticated encryption (AES-GCM / HMAC fallback), record CRUD,
    and synthetic PDF export.
  - Project isolation: recipient names, notes, passphrases, and keys remain strictly
    in project-owned `<project>/nda/` and are never emitted to server logs.
  - Dynamically enabled NDA management tab in `lixity serve` when projects configure
    `[nda]` or contain project NDA capability.
- Research dashboard web UI improvements (`lixity serve`):
  - Visual `⚠️ Review needed` badge on dossier cards and warning banner in dossier
    inspector with linked decision rationale.
  - Outline summary of sections in dossier inspector view.
  - Scope guidance hint in research search when scoped search yields 0 hits, with
    one-click option to switch to all records.

### Changed

- Reorganized the website and README around manuscript exploration, chapter
  comparison and traceable research. Moved detailed review signals and the
  research CLI walkthrough into the corresponding guides; integration details
  remain with the developer interfaces.
- Harmonized dashboard and Pages action colors, neutral surfaces and local title
  fonts. Increased reading-text and primary-control sizes, strengthened keyboard
  focus and active-tab cues, and respected reduced motion on Pages.
- Heatmap labels now choose contrasting text independently of the system theme;
  data colors and analysis results are unchanged. Narrow file controls wrap
  within the workspace at mobile widths.
- Reviewed installation, onboarding, research and public guides against current
  behavior; clarified release versus main documentation and refreshed example
  screenshots. Corrected documented readability coefficients and syllable units
  to match the existing implementation, without changing calculations.

## [1.19.0] – 2026-09-27

### Added

- Optional Zotero Desktop integration through its local read API: browse explicit
  libraries and collections, inspect attachments, capture selected PDF/text files
  with consent, refresh linked sources and open originals from the dashboard.
  Images, audio and video stay in Zotero; no cloud account or background sync.
- Structured Zotero attachment identities in `research-local/3` captures and v3
  manifests, with duplicate prevention and explicit refresh on changed captures.
  Older readers reject v3; previous quotations and archive history are preserved.
- Additive RIS migration export with source identity tags and original files;
  paired backups of the research archive and an explicitly closed Zotero data
  directory, restored only into a new destination after checksum verification.
  Manuscripts, application profiles and external linked files need separate backup.

- Optional research search scopes for current dossiers, claims and decisions,
  using the shared FTS5 catalogue. Typed `research-search-local/2` hits expose
  record identity, revision and excerpts; default source-only CLI/API search
  retains v1. The seven-language dashboard searches all types by default and
  opens authored hits in the existing revision viewer. History is not indexed.
- Server debug logging through `serve --debug` or `LIXITY_DEBUG`, with browser
  API/runtime diagnostics and `setLixityDebug()` controls (added after v1.18.0).

### Fixed

- Align maintained guides and automation examples with the shipped v1.18.0
  CLI/API contracts, Portuguese UI locale, and released origin URL, PDF/OCR
  diagnostics and unavailable-consistency behavior. Correct research ingest help
  to mention PDF support and the separate scan worker requirement.
- Reuse existing PDF extraction when a refresh changes metadata but retains
  identical original bytes; preserve extracted text and earlier citations.
- Document debug precedence on reload and timestamp scope.
- Preserve source criticism when binding an existing capture to Zotero. Treat
  personal-library aliases as one attachment identity and reject ambiguous links.
- Reject failed, malformed or incomplete configured OCR worker output instead of
  silently falling back. Keep unknown confidence unset and preserve physical page
  order. `LIXITY_OCR_TIMEOUT` accepts 1–3600 seconds (default 120).
- Add an experimental checkout-only Unlimited-OCR CPU adapter with pinned model
  weights, page checksums and truncation checks. Its external runtime and model
  weights are optional and are not bundled in the Python package.

## [1.18.0] – 2026-09-27

### Changed

- Source import now accepts an optional origin URL in the UI, CLI and Python/HTTP
  APIs. URLs are retained as capture context without network access; old citations
  preserve their original provenance. URL-bearing captures require `research-local/2`
  and v2 manifests, which older readers reject. URL-free v1 encoding is preserved.
- Browser OCR setup labels and guidance use all seven workspace locales. Configured
  workers are no longer described as verified or active inference services.
- Consistency displays “–” when no chapter–feature cells are measurable. Empty
  chapters no longer manufacture measurements. Style JSON v4 adds `measured_cells`
  while retaining the legacy numeric consistency sentinel for compatibility.
- Text/PDF browser imports share temporary-file handling and parameter forwarding.
- Public guides cover installation, metric interpretation, origin URLs, PDF/OCR
  setup and backup verification. Pages uses one shared stylesheet, internal guide
  navigation and an expanded sitemap; release and current-main features are distinct.
- Separate local planning under `.planning/` from product documentation; preserve
  earlier tracked plans locally and remove them from public sources. Repository
  guidance documents the boundary, and Pages stages only approved product paths.
  Ignore agent worktrees and test artifacts without hiding public examples or tests.
- Document the verified Unlimited-OCR source pins, custom adapter requirement,
  upstream runtime differences and limits of OCR provenance and diagnostics.
- PDF CI installs Poppler on Linux/macOS; dependency-dependent tests report explicit
  skips elsewhere. The mock worker runs across platforms, and the synthetic
  archive-tampering fixture avoids deprecated implicit tar extraction behavior.

### Added

- **OCR diagnostics and status check**: `lixity research ocr-status` CLI command and
  `/api/research/ocr-status` HTTP endpoint diagnosing poppler tools (`pdftoppm`, `pdftotext`),
  worker executable permissions, configured model identifiers, and actionable setup guidance.
  Included in the research panel status bar. It does not verify model integrity or inference.
- **Staged import progress and native PDF upload**: Base64 binary PDF ingestion directly
  through the browser dashboard with step-by-step progress feedback (`Reading file…` ->
  `Extracting text and passages…` -> `Complete`), button locking during ingestion, and
  CLI progress reporting on stderr via `progress_callback`.
- **Recent projects management**: Quick-access recent projects list in the Open Project modal
  with path chips and single-click removal, persisting in local browser storage.
- **Graceful stale path recovery**: Project folder chooser warns on deleted or inaccessible paths
  and automatically falls back to the user's home folder without breaking the modal UI.

### Fixed

- **Empty manuscript metrics and KPI display**: Text with zero tokens or words now correctly
  evaluates readability (Flesch, LIX) to `0.0` rather than the formula intercept (206.835 / 180.0).
  KPI tiles, Table 1, and Markdown reports display a clean empty indicator `"–"` for ASL, ASW,
  Flesch, LIX, Staccato, Dialogue, and lexical diversity when no tokens are present.
- **Stale manuscript file references**: The server dashboard now detects when an active manuscript
  path no longer exists on disk, displaying a prominent error badge (`"file missing (stale reference)"`)
  and preventing unhandled file errors during analysis.

## [1.17.0] – 2026-09-26

### Added

- Native revision and history workflows for research dossiers, claims, evidence
  links and author decisions, using the existing CLI, API and dashboard.
  Explicit corrections and supersessions preserve logical IDs and accepted
  revisions. Snapshot and revision checks prevent stale drafts from overwriting
  newer work; failed saves retain browser drafts.
- Notices when explicitly cited source passages have a newer capture. Existing
  quotations and authored text remain pinned; evidence links show when they
  refer to an earlier claim revision.
- Offline SVG diagram rendering for dossier bodies: client-side vector diagram
  generator rendering Mermaid flowcharts (`graph TD/LR`) and sequence diagrams
  (`sequenceDiagram`) into responsive SVGs without network requests, CDNs, or
  external runtime libraries. Includes inspectable source toggles and localized
  labels across all seven supported languages.
- Self-hosted Baidu Unlimited-OCR extraction boundary: support for PDF document
  ingestion (`lixity research ingest --file document.pdf`) with dual-blob
  content-addressed storage (original PDF bytes + extracted plain text). Pinned
  to official model snapshot `07dea832e22aefee32ad281d4b80551282e1c168` and
  integration recipe revision `d49ff64afffc1f47ab563dc1c589bc2f78808fa4`.
  Includes 1:1 physical page rastering via `pdftoppm` with SHA-256 digests,
  configurable `LIXITY_OCR_WORKER` sub-process execution, and local `pdftotext`
  extraction fallback.
- Export and restoration for the research archive: `lixity research export`
  packages HEAD, manifests, revision records, blobs and project.json into a
  verified tar.gz with a per-file checksum manifest. `lixity research restore`
  validates the archive and extracts it to a new directory, refusing to
  overwrite an existing project. Disposable search indexes are rebuilt
  separately. The acceptance criterion is a full round trip: export, restore,
  audit, rebuild search, and resolve citations with the same identities and
  verbatim text. Does not introduce a separate archive format; reuses the
  existing storage layout.
- Safe Markdown rendering in dossier detail and history views: headings,
  paragraphs, bold, italic, code blocks, lists, blockquotes, tables and safe
  links rendered client-side from a minimal self-contained renderer with no
  new runtime dependencies. HTML passthrough is disabled. `javascript:` and
  `data:` URIs are suppressed. `lixity:` internal links render as inert code
  spans. A 'Show source' toggle exposes the raw text.
- Property-based tests (Hypothesis `RuleBasedStateMachine`) for
  content-addressable storage invariants: encode determinism, round-trip
  fidelity, snapshot immutability, and contiguous revision history under
  arbitrary commit sequences.
- Mutmut configuration targeting the repository and revision modules for
  mutation testing of data-integrity paths.

### Fixed

- **Purge atomicity**: orphaned record files and blobs are now deleted only
  *after* HEAD has been atomically rotated to the new snapshot. Previously,
  a crash or signal between the unlink calls and `replace_head` could leave
  the archive in a permanently unreadable state. After this fix, an interrupted
  deletion leaves unreferenced-but-harmless files (recovery: re-run purge);
  an interrupted HEAD rotation leaves the old snapshot fully intact.
- **Evidence-ID deduplication**: `create_dossier` now deduplicates passage
  IDs using `dict.fromkeys`, matching the existing `revise_record` behaviour.
  Duplicate evidence references in a single dossier creation call no longer
  produce multiple identical `evidence_refs` entries.

### Compatibility

- The first authored edit writes `research-local/2` revision records and a
  `research-manifest-local/2` snapshot. Existing revision-1 files are retained
  unchanged; reading an archive does not upgrade it. Lixity 1.16.0 cannot read
  a revised archive. Back up the complete archive before upgrading and keep
  all writers on a version supporting native revisions.

## [1.16.0] – 2026-09-26

### Added

- Standalone local `lixity serve` with project creation, explicit manuscript import,
  existing-project opening, live settings and marker controls. Host/Origin checks,
  loopback binding and request limits protect the local HTTP boundary.
- A file and folder browser in Open Project selects existing server-local paths
  without changing the workspace until Open is confirmed. The persistent
  workspace bar keeps New Project, Open Project and Show guidance available in
  loaded projects; guidance can be reopened after dismissal.
- Localized explanations for project and research controls. Shared tooltips work
  by keyboard and touch, stay visible inside dialogs, and preserve related help.
- Experimental explicit-project research workspace: retained UTF-8 sources,
  versioned source context, SQLite/FTS5 search, exact passage citations, dossiers,
  claims, evidence links and author decisions through CLI, Python and HTTP APIs.
  Retention requires permission; source text is evidence, not an accepted claim.
- Integrated research tabs with full source/context and dossier views, passage
  selection for claims/dossiers, claim-to-dossier association, author decisions,
  visible archive root and counts, and distinct empty/uninitialized/unavailable states.
- Research withdrawal, purge preview and integrity audit. Purged passages leave
  content-free reference tombstones so historical evidence chains remain readable
  without retaining their deleted quotes.
- Cross-corpus lexical and stylistic comparison using the shared analysis pipeline.
  Vocabulary overlap is a navigation aid, not proof of factual support.
- All seven language profiles cover project workflows, research controls, templates
  and status labels. English and German remain the most developed linguistic cores.
- Additive `median_sl_exact` JSON metric; text reports display the conventional
  midpoint median for an even number of sentences. The legacy integer `median_sl`
  remains available with its original upper-middle semantics.
- Real-server browser regression for file/folder opening, import/error recovery,
  research creation and source lifecycle, with desktop and seven-locale mobile checks.

### Fixed

- Correct HD-D to hypergeometric expected TTR for a 42-token draw instead of
  the mislabeled windowed Simpson calculation. The minimum is now 100 tokens;
  legacy sampling arguments have no effect, and no population SE is reported.
  Recompute older analyses and dependent style baselines before comparison.
- “Open project” no longer routes file selection or drops silently into new-project
  import. Existing file/folder paths preserve their original research archive,
  including empty manuscripts and initialized research folders without manuscripts.
- Project opening reloads target settings; unsuccessful opening preserves the
  current workspace. Dialog errors remain visible beside editable inputs.
- Imported content preserves submitted whitespace and line endings and cannot
  overwrite an existing manuscript. Generated project settings use valid TOML
  and preserve quoted titles and the selected language.
- Standalone controls show only implemented actions; Run analyses/Rebuild refresh,
  while unsupported export/sync/audit/prune/Drive requests return HTTP 501
  without pretending to produce artifacts. Legacy `/api/load` returns HTTP 409
  rather than replacing a saved copy with the same filename.
- Source, claim and dossier selections survive background list refreshes. A decision
  with no recorded deviation is shown neutrally, without implying factual validation.
- Correct chapter-to-rest JSD probability mass; unequal chapter lengths no longer
  produce negative divergence for identical lexical distributions.
- Use all four cells of the term/non-term contingency table for Dunning G².
  Research comparison uses analyzed prose consistently and reports cross-language
  comparability limits; shared vocabulary does not establish factual support.
- Verify retained source bytes before exposing source-detail quotes, matching the
  integrity checks already used for citations.
- Align token/syllable/readability/dialogue counts with sentence metrics by excluding
  Markdown headings consistently from prose measurements.
- Project TOML works on Python 3.10 through a conditional `tomli` dependency;
  Python 3.11+ continues to use the standard library.
- Rebuilding the research catalogue flushes a writable file descriptor on
  Windows before atomic publication. Browser checks honor an external Python
  environment in CI as well as the local development environment.
- Correct the documented Benjamini–Yekutieli harmonic factor and Maas logarithm
  base to match the existing implementations; no numerical change for these fixes.

### Changed

- English is the default across CLI, API and local server; automatic language
  detection requires an explicit choice and import preserves that choice.
- English onboarding, installation, architecture and methods documentation now
  separates implemented research workflows from planned provider integrations.
- Analysis/style JSON schema versions remain 2/4. Corrected numeric outputs require
  recomputing older analyses before longitudinal comparison. Research stays an
  experimental family of `*-local/1` contracts.
- Refreshed public/synthetic screenshots and project presentation; no private
  manuscripts or real research records are included.

## [1.15.0] – 2026-09-24

### Added

- Explanatory settings form with visible labels, expandable thresholds,
  restore-without-saving and client/server validation in the local adapter.
- FDR-specific matrix markers and chapter filtering, fixed-scale legend,
  Cliff's δ details, and visible reference medians/sample counts.
- Classic serif typography for the project title only; system UI sans elsewhere.
- Shared `lixity.pipeline` orchestration for CLI, API and project adapters,
  with one corpus analysis per complete result and explicit threshold mappings.
- Interactive 3D chapter trajectories with zoom, rotation, localized tooltips,
  per-axis threshold boxes, chapter navigation and responsive feature loadings.
- Browser regression checks and localization contracts for all seven profiles.
- Architecture and localization guides with explicit engine/adapter boundaries.
- Shared project header with engine version and localized non-commercial-use notice.
- Thirteen refreshed public-sample screenshots, including full dimension panels,
  real expanded paragraph context, mobile views and dark-mode diagnostics.

### Changed

- Installation guidance now has one canonical guide for CLI/API/development,
  Windows, updates and first-run verification. `make install` uses `.venv`
  rather than global Python; both installation targets check dependencies.

- Promoted the reviewed `1.15.0.dev0` work to release `1.15.0`.
- CLI/API/core analysis defaults to English. Use `--language de` for German
  or `--language auto` for detection; CLI project language settings are honored.
- Documentation and comments use English; localized resources remain multilingual.
- Canvas animation runs only when rotation is enabled and the page is visible.

### Fixed

- NDA records render through text-safe DOM APIs instead of HTML interpolation;
  artifact links reject executable URL schemes. Added synthetic regressions.

- Public API `min_chapters` now reaches the style core rather than being
  silently ignored; the CLI exposes `--min-chapters`. API threshold mappings
  can explicitly disable current-directory configuration discovery.
- Repository guidance distinguishes analysis from authorized mutations;
  ignore rules cover local agent/browser state and the default HTML export.

- Shared panel and page spacing replaces overlapping margins; mobile charts use
  stacked labels and wide tables scroll instead of crushing their columns.
- Chapter matrix headers explain every column in all seven UI languages;
  shared tooltips now support keyboard focus, Escape and ARIA descriptions.

- Control groups share one spacing and separator rule; the duplicate legacy NDA
  entry form is removed in favor of the encrypted NDA manager.
- Settings display the analysis language unless the host explicitly selects auto.
- CLI configuration follows an explicitly selected manuscript's directory;
  dashboard and workspace builds honor the configured project title.

- Localized settings no longer write decimal commas into HTML number values.
- Matrix color legends reflect the actual color scale rather than the configured
  detection cutoff; reference rows respect the configured minimum sample size.
- Dimension scores are flagged only after all feature contributions are summed.
- Point hit testing matches the rendered projection after zoom/rotation.
- Chapter titles in canvas tooltips are text rather than executable HTML.
- English percentages retain their percent sign; tooltip numbers use their locale.
- Mobile dimension cards retain space for feature labels and avoid overflow.
- Long chapter paragraph strips scroll within their component on mobile.
- Screenshot selection uses exact panel IDs instead of incidental label matches.

## [1.14.0] – 2026-09-24

### Added

- **Substantive Documentation & Presentation Elevation:**
  - `README.md` and GitHub Pages (`docs/index.html`) thoroughly expanded, tightened, and refined in English, emphasizing self-calibrating macro-editing versus external normative style checkers.
  - Added an executive Mathematical Core summary table in `README.md` with clean, platform-independent Unicode notations (`x̃`, `Â₁₂`, `ρ₁`, `τ, S, p`, `G²`).
  - Added in-depth descriptions of the 5 core metric groups and their diagnostic value for macro-editing and developmental line editing.
  - Expanded FAQs in `README.md` and `docs/index.html` covering noise-aware significance shrinkage ($z^*$), non-destructive Markdown editor work markers (Pandoc / Typst / LaTeX pass-through), and pipeline integration.
  - Enhanced persona-workflow cards and comparison matrix on GitHub Pages.
- **English Schema & Model Descriptions:**
  - Translated all Pydantic model field descriptions in `src/lixity/models.py` (`CorpusConfig`, `SentenceDistribution`, `ChapterMetrics`, `CorpusMetrics`, `DossierStatus`, `CorpusAuditReport`) and internal error messages into English for clean API introspection.
- **UI Performance & Accessibility Enhancements:**
  - Throttled tooltip repositioning on scroll and resize via `requestAnimationFrame` tick scheduling to avoid layout thrashing and maintain 60/120 fps fluid scrolling.
  - Added Escape key dismissals to close open paragraph detail panels (`.ptext.open`) and active inline marker note input fields (`.marker-note`).
  - Extended CSS `scroll-margin-top: 4.5rem` to all panels and anchored sections (`.panel`, `section[id]`), preventing sticky toolbars from obscuring content headers upon link activation.
  - Added `user-select: none` to `.kpi-link` tiles to prevent accidental text selection during navigation clicks.
  - Standardized NDA table headers and fallback file upload status text to English in `dashboard.js`.

### Fixed

- **GitHub Markdown & KaTeX Math Rendering:**
  - Removed KaTeX delimiter-backtick collisions in `docs/METHODS.md` that previously caused red parse error boxes on GitHub.
  - Escaped mathematical asterisks (`z\*`) across documentation to eliminate accidental Markdown italics formatting.
  - Replaced unstable combining circumflex diacritics (`Hill &alpha;&#770;` / `Hill α̂`) that produced detached boxes across browser fonts with `Hill tail index`.
  - Normalized schema version indicators (`schema_version 4` for style references) across GitHub Pages and documentation.
- **Typographic, Editorial & Security Updates:**
  - Fixed duplicate word in `docs/USAGE.md` ("Structural structural diagnostics" → "Structural diagnostics").
  - Converted German decimal commas to standard English decimal points in the worked example in `docs/USAGE.md` (`15,57` → `15.57`, `+0,08 pp` → `+0.08 pp`, `−0,0002` → `−0.0002`).
  - Corrected English article and thousands formatting in `docs/STABILITY.md` ("a 8 000-word" → "an 8,000-word chapter", `chapter × feature`).
  - Added missing accent in `CITATION.cff` (`Goh-Barabási`).
  - Updated `SECURITY.md` supported release branch to `1.14.x`.
  - Completed all missing GitHub release comparison links at the bottom of `CHANGELOG.md` from v1.1.0 through v1.9.1.

## [1.13.0] – 2026-09-23

### Changed

- **Layout default leading ≈ 1.50×:** all three `BookLayoutConfig.from_preset`
  presets (`a4`, `taschenbuch`, `mobile`) now set `line_spacing=0.94`
  (Pango factor ≈ 18.0 / 13.2 / 12.8 pt baseline distance at 12 / 8.8 / 8.5 pt).
  Previously mobile and paperback used `0.88` (≈ 1.41×) and A4 used natural
  Pango metrics (≈ 1.33×); the tighter leading was reported as too cramped
  for continuous reading. Typographic defaults for reproducible exports —
  override per call via CLI `--line-spacing` or a custom config.

### Tests

- **`tests/test_layout.py`:** renderer-free assertions on preset
  `line_spacing`, body sizes, and the ≈ 1.50× target (no Cairo/Pango in pytest).

## [1.12.0] – 2026-09-23

### Added

- **Pacing degeneracy flag:** `PacingReport` / JSON gain
  `explicit_scene_breaks` and `scenes_are_chapters` (true when the text has
  no explicit `---`/`* * *` dividers, so scenes ≡ chapters). The CLI prints
  a warning in that case; scene counts are then structure placeholders, not
  pacing evidence.

### Changed

- **`characters` requires names:** empty `--names` / empty API name list
  now fail fast (CLI exit 1 `err_no_names`; `ValueError` via the API)
  instead of returning a silent `figures: []`. No NER — the caller
  supplies the names.

### Documentation

- **Boundary caveats** (USAGE §Known limitations, STABILITY register rows
  45–50, AGENTS §3.5 boundary note, METHODS Track B):
  heuristics measure the text, not ground truth; `signal_counts` is empty
  unless `CorpusConfig.signal_keywords` is set; German filter-verb counts
  (engine ≈ 94) intentionally differ from broader editorial lists (120);
  pacing without explicit dividers is flagged; no external Delta
  stylometry and no dialogue speaker attribution.

## [1.11.0] – 2026-09-23

### Added

- **Packaging & installability:** dynamic version from
  `lixity._version.__version__` (single source for setuptools / `__version__` /
  `--version`), optional-dependencies `dev` extra (`pytest`, `mypy`, `ruff`,
  `build`), richer classifiers (`Environment :: Console`, Python 3.13,
  `Typing :: Typed`, OS Independent), project URLs for the GitHub Pages site
  and security policy.
- **`Makefile`** (`make help|install-dev|test|lint|typecheck|check|build|screenshots|clean`)
  and **`CONTRIBUTING.md`** (dev setup, PR checklist, bug reports).
- **`.github/dependabot.yml`** weekly updates for GitHub Actions.
- **Shell completion parity:** zsh script now covers all commands and the
  style-threshold flags (`--z-mild`…`--flag-min-severity`); bash completion
  gained `--fdr-method`, `--flag-min-severity`, `--dry-run`, `--names`,
  `--motif` and install-path hints; `lixity completion` accepts
  `bash|zsh|sh` as choices.
- **Top-level `--help` epilog** with examples, docs URL and `LIXITY_LANG`.
- **Structural diagnostics** on the style passport (`structural_diagnostics`,
  `schema_version: 4`): PELT changepoints, Mann–Kendall trends, Sn/Qn
  robust scales (alongside MAD), Hill tail index, and summary lists
  (`trending_features`, `segmented_features`); `passport_text` gains a
  “Structural diagnostics” line (en/de). Pure stdlib — no numpy/scipy.
- **Wired structural estimators** (previously standalone-only):
  - `distribution_shift` + `shifted_features`: Wasserstein-1D and
    two-sample KS comparing the first half of chapters against the second
    (both halves ≥ 2);
  - `lexical_structural_diagnostics(text, config)` merges token-level blocks
    into the passport on text-bearing surfaces (`api.fingerprint`,
    CLI `style` / `build` / `dashboard`): `cooccurrence` (content-word
    graph mean degree + Goh–Barabási fitness) and `keyness` (Dunning $G^2$
    early vs late halves). Guards: ≥ 50 content tokens for the graph,
    ≥ 20 per keyness half; single-chapter texts omit `keyness`.
- **`CITATION.cff`**, **`.pre-commit-config.yaml`** (ruff + trailing
  whitespace), **release workflow** (tag → wheel + GitHub Release), and
  **GitHub Pages deploy** (`docs/` on `main`).
- **Injectable statistical thresholds** (`z_mild`, `z_strong`, `fdr_q`,
  `fdr_method`, `dim_score_threshold`, `flag_min_severity`):
  stored on `StyleFingerprint.thresholds`, reported in every passport `meta`,
  and controllable from
  - CLI: `--z-mild`, `--z-strong`, `--fdr-q`, `--fdr-method {bh,by}`,
    `--dim-threshold`, `--flag-min-severity {1,2,3}` on `style`,
    `dashboard`, `build`;
  - API: `api.fingerprint(..., z_mild=…, fdr_q=…, fdr_method=…, …)`
    (same kwargs on `api.passport` / `api.dashboard`);
  - control UI: Settings fields for z\* mild/strong, FDR q, flags severity
    floor and dimension-score threshold, persisted on the embedded server;
  - config file: `[tool.lixity]` in `pyproject.toml`, or `lixity.toml` /
    `~/.config/lixity.toml` via `src/lixity/config.py`
    (CLI > UI session > project > user > code default).
- **Benjamini–Yekutieli FDR** (`fdr_method="by"`, harmonic factor \(c(m)\))
  alongside the default BH path (`fdr_rejects`).
- **Effect sizes on confirmed cells**: Cliff’s δ and Vargha–Delaney
  \(\hat{A}_{12}\) with Romano bands (`effect_label`), exposed as
  passport `effect_magnitudes`.
- **Baseline exchangeability diagnostics**: runs test about the series
  median, lag-1 autocorrelation vs \(1/\sqrt{n}\), `low_power` for
  \(n < 8\) — passport `baseline_diagnostics` + `passport_text` line.
- **`docs/METHODS.md`**: formal catalogue of every estimator (MAD/σ scaling,
  z\*, BH/BY-FDR, Cliff’s δ, runs/ACF, Jacobi dimensions, LD indices,
  readability constants, JSD, layer z, Structural PELT/MK/Sn/Qn/Hill and
  Wasserstein/KS/Dunning/Goh–Barabási — including their passport wiring —)
  with injectability table including the config file; Track B/C research
  and pedagogy backlog (Burrows’ Delta / OHCO-TEI / hermeneutics, tutorials).
- Contract tests for threshold round-trip and sensitivity settings markup
  (z mild/strong, FDR q, flags cut, dimension threshold).

### Changed

- **BREAKING (schema v3 → v4):** style-passport JSON container key renamed
  `wave2_diagnostics` → `structural_diagnostics`; passport text label
  `wave2` → `structural` (en: “Structural diagnostics”, de: “Strukturelle
  Diagnostik”); function `lexical_wave2_diagnostics` →
  `lexical_structural_diagnostics`. Sub-keys (`changepoints`, `trends`,
  `distribution_shift`, `cooccurrence`, `keyness`, …) are unchanged.
  Project-management codenames no longer appear in public contracts.
- **Centralised status codes** in new module `lixity.status`: `Status`
  (UI ok/warn/error/unknown), `Tense` (present/past/mixed/neutral),
  `Severity` (0–3 + `FLAG_MIN_SEVERITY`), `NdaStatus`, and
  `ContractKeys` / `STRUCTURAL_DIAGNOSTICS_KEY` / `SCHEMA_VERSION_*`.
  `style_profile.TENSE_*` / `FLAG_MIN_SEVERITY` now re-export from
  `status`; NDA status list is server-injected (`data-nda-statuses`)
  instead of hard-coded in `dashboard.js`.
- **Feature units localised for all seven UI languages** (en/de/fr/es/it/pt/nl)
  via `FEATURE_UNITS` (was: German override + English fallback only).
- **Install docs** (README, `docs/USAGE.md`, project page, `docs/llms.txt`):
  pipx / uv / pip / pinned-tag options; development via `make install-dev`.
- **`docs/USAGE.md` Development** section now documents `make check`
  (ruff + mypy --strict + pytest -W error) instead of the stale unittest count.
- **GH Pages** (`docs/index.html`): Structural FAQ and feature pills, style
  schema v4, BH/BY, injectable thresholds, structure-module cards, Methods /
  Contributing / Security footer links, installation matrix.
- **`.gitignore`** hardened: agent/tool workspaces (`.remember/`, `.claude/`,
  …), coverage formats, keystores / `.netrc` / swap files, stray
  `*_dashboard.html` / `*_metrics.json` style build artifacts outside
  `exports/`.
- **`SECURITY.md`**: supported-versions table, expanded threat model,
  consumer hardening checklist (pipx/uv, pinned tags, local-only dashboards).
- **Single chapter segmentation**: `split_chapters` moved from `dialogue`
  to `markdown_parser` (re-export kept); `analyzer` and all structure
  modules share one implementation, so chapter titles/numbers can no longer
  drift between reports.
- **Single threshold builder**: `config.resolve_thresholds` is the only
  place that builds `FingerprintThresholds` (kwargs > project config >
  code default); CLI `_thresholds_from_args` and API `_thresholds` both
  call it.
- **`flag_min_severity` end-to-end**: CLI `_thresholds_and_profile` feeds
  `ProfileThresholds` into `ParagraphProfiler` and passes the resolved cut
  to `render_dashboard`; `api.profile` / `api.dashboard` accept
  `flag_min_severity` explicitly.
- Passport `meta` now reports `min_chapters` and `flag_min_severity`
  alongside the z\*/FDR thresholds.
- **Style reference rows are fully clickable**: every `.band-row` jumps to
  that feature's heatmap column (`#feat-<field>`), activates the matching
  style layer when one exists, and preselects “deviations only” when the
  feature has outliers. The red **outlier count** is a nested control that
  opens the strongest outlier chapter (with layer + only-deviations).
- Heatmap column headers expose stable anchors (`id="feat-<field>"`).
- Heatmap legend and “deviations only” cut use `fingerprint.thresholds.z_mild`
  instead of a hardcoded 2.5.
- Research basis (STABILITY §1) extended: robust statistics / multiplicity
  control, readability literature (Amstad…Douma, Weiss & Meurers 2022),
  foregrounding/stylistics angle.
- README condensed with an explicit mathematical-core focus; links to
  METHODS.md.

### Fixed

- Dialogue and nominal style layers now bind correctly:
  `LAYER_FEATURES` uses fingerprint field names (`dialog_pct`,
  `nominalization_density`); `LAYER_PARAGRAPH_ATTR` maps them to the
  `ParagraphProfile` attributes (`dialogue_pct`, `nominal_density`) used by
  `layer_stats`. Previously the dialogue band had no layer and the nominal
  layer produced empty stats.
- Export-format `<select id="fmt">` exposes a short `aria-label` (export)
  instead of the full help sentence; the tooltip moved to `title`.
- USAGE metric table: LIX long-word threshold is **>6 characters in every
  language** (Björnsson), not per-language 6/7/8 (docs inconsistency with
  STABILITY #24 / METHODS §7).
- Book scripts `export_pdf.py` / `export_nda.py`: suppress third-party
  `PyGIDeprecationWarning` for `GLib.unix_signal_add_full` during Pango
  import (system PyGObject, not Lixity code).

## [1.10.0] – 2026-09-22

### Added

- **Flagged passages panel** (`#flags`) directly under the KPIs: every
  paragraph with severity ≥ 2 as a row (severity badge, chapter, line anchor,
  excerpt), sorted by severity then line. Clicking a row jumps straight to
  that paragraph — opens it, scrolls, flashes — with the “flagged only”
  filter preselected; a quick **+ To-do** button writes the work marker
  inline without leaving the list. The “flagged” KPI now targets this panel.
- `ParagraphProfile.is_flagged`, the `FLAG_MIN_SEVERITY` constant and
  `flagged_paragraphs()` (severity desc, line asc) replace the repeated
  `severity >= 2` checks; `classify_severity()` is a documented, tested
  pure function (0–3 truth table).

### Fixed

- **Marker clicks no longer scroll the page**: buttons inside jumpable rows
  (`data-marker-kind`, `data-marker-resolve`, note field) are excluded from
  jump activation in both the click and the keyboard handler.
- **Line jumps land on the paragraph, not just the chapter**: `jumpToLine`
  opens the target `.ptext` panel (via `data-target` or its
  `data-start`/`data-end` span) and activates its chip; chapter scroll remains
  the fallback (e.g. marker lines outside any paragraph span).

### Removed

- Dead aliases: `render_style_report`, `DEFAULT_TEXTE`, and the unused
  `ParagraphProfile.line_label` property (the localised `line_label()` in
  `ui.components` remains the single implementation).

## [1.9.1] – 2026-09-22

### Changed

- **Chapter names wherever they are available**: dialogue, pacing and
  showing rows show `Kap. N · Titel`, the deviation KPI names its chapter,
  the marker table gained a chapter column, and the character span shows the
  first chapter's title on hover.

### Fixed

- **Layout overflow hardened**: the chapter matrix and marker table scroll
  horizontally inside their panels (like the heatmap); long texts wrap or
  ellipsize (KPI labels, dimension loading chips, status details, chapter
  titles, repeated phrases, paragraph text); the pacing and showing lists are
  height-capped with a fade hint; the toolbar select is width-capped.

## [1.9.0] – 2026-09-22

### Added

- **`lixity dialogue`** (and `api.dialogue`): dialogue turn structure — turns
  (quoted segments), mean/median/longest turn, turns per 1,000 words and the
  dialogue paragraph share, per chapter and corpus. Heuristic via the language
  profile's dialogue pattern; no speaker attribution.
- **`lixity characters`** (and `api.characters`): character presence across
  chapters for curated names or alias patterns — mentions, chapters present,
  first/last chapter, longest gap, presence ratio. Appendix and front matter
  are excluded so chapter numbers match the metrics.
- **`lixity pacing`** (and `api.pacing`): scene structure via explicit
  dividers, tempo signals per scene/chapter (ASL, staccato, dialogue) and a
  documented 0–3 chapter hook score.
- **`lixity motifs`** (and `api.motifs`): motif presence (mentions, density,
  chapter span, longest gap) and generic repetition signals — most frequent
  content words and repeated n-grams with their chapter spread.
- Dashboard panels for dialogue structure, character presence, the pacing
  curve and motifs/repetition (clickable, keyboard reachable, seven
  languages).
- **`lixity showing`** (and `api.showing`): self-calibrating showing vs.
  telling balance per chapter (robust z of telling and showing signals
  against the book's own medians; documented MAD→SD fallback).
- **`lixity about --json`** now lists all commands with purpose, output type
  and schema version (agent discovery).
- Curated stop-word lists (de/en) extended with high-frequency adverbs,
  possessives and particles so repetition and driver-word analysis stays
  content-focused.
- **`mypy --strict` is enabled** (147 → 0 errors) and runs in CI; the code
  base is also free of runtime and syntax warnings (`python -W error`).

## [1.8.0] – 2026-09-22

### Changed (breaking, metric-affecting)

- **Sentence segmentation is abbreviation-aware** and shared by corpus and
  chapter metrics (`lixity.sentences`): abbreviations (`Mr.`, `z.B.`, `Dr.`),
  decimal numbers and initials no longer split sentences, closing quotation
  marks stay with the sentence they close. Sentence counts, ASL, CV, Flesch
  and LIX change accordingly (dialogue-heavy texts get more, shorter
  sentences; the chapter matrix was still on the naive regex before).
- **LIX uses the standard long-word threshold** (more than six characters)
  for every language; the previous per-language calibration (7/8 characters)
  deviated from Björnsson. LIX values rise accordingly.
- **Syllable heuristics improved:** German double vowels count as one nucleus
  (`Kaffee`, `Idee`), the English silent-e/-le rule no longer double-counts
  (`table`, `people`).
- **Spanish readability** uses the INFLESZ coefficient 62.35 (matches the
  named scale).

### Changed (structure)

- New core modules: `lixity/sentences.py` (segmentation), `lixity/syllables.py`
  (per-language rule tables as data), `lixity/diversity.py` (HD-D, MTLD,
  MATTR, Maas a², Yule's K). `analyzer.py` is orchestration and metric
  assembly (857 → ~540 lines).
- `SentenceStats` is the one sentence-architecture data structure for corpus
  and chapters; `share_se`/`count_se` are module-level plug-in estimators.
- `language.py`: one profile dataclass, resolved via `dataclasses.replace`
  (was two identical dataclasses with three field lists).
- **Unified UI interaction contract**: every content drill-down is a
  keyboard-reachable `[role="button"]`, driven by one JS selector; focus
  styling covers all targets (documented in `docs/AGENTS.md` §3.4).

### Fixed

- Style-reference band rows are clickable again (the layer mapping was lost
  in a refactor) – as documented since v1.5.0.
- `jacobi_eigh` docstring corrected (one eigenvector per list entry).
- New `tests/test_math_core.py` pins the mathematical core (hand-computed
  readability formulas, published Benjamini-Hochberg example, Jacobi
  properties, Spearman, z*/MAD helpers, lexical-diversity properties).

## [1.7.0] – 2026-09-22

### Changed (breaking)

- **Language-neutral tense values:** `dominance` (chapter metrics) and
  `dominant` (paragraph profiles) are now `present` / `past` / `mixed` /
  `neutral`; display labels come from the language packs. The JSON contract
  version is now **schema_version 2** for `analyze` and `profile`.
- **English is the engine default** for reports and CLI messages; German is
  available via `LIXITY_LANG=de` (Rich report, Markdown report, style
  reference text, build/dashboard messages). Other report languages fall
  back to English.
- **Project corridors are opt-in:** reference corridors and literary
  assessments are no longer engine defaults – projects supply them as
  `texts` (the book project passes its own German corridors). Without them
  the Rich report stays factual (metric + value).
- Report row labels and feature units are localised (`de` / `en` packs).

### Fixed

- Chapter detection: front matter preceded by editorial HTML comments no
  longer becomes chapter 1 (chapter numbering stays correct).
- A chapter without tense markers is classified `neutral` instead of `past`
  (one shared `dominance_from_hits` helper for chapters and paragraphs).
- Style reference: correct singular/plural chapter count; localised units.

### Added

- `LIXITY_LANG` environment variable (`en` default, `de` supported) for
  user-facing CLI messages.

## [1.6.1] – 2026-09-22

### Fixed

- **Markdown report:** punctuation rows now use their own texts. Previously
  the `colons` matcher also matched inside `semicolons`, so the semicolon row
  displayed the colon text.

### Changed

- `CorpusAuditReport` carries a generic `tracked_chapters` mapping instead of
  the book-specific `kap23_words` / `kap24_words` / `kap25_words` fields —
  project data belongs to the adapter, not the engine.
- Documentation tightened: leaner README (features and quick start instead of
  marketing comparisons and duplicated CLI reference), single stability
  register `docs/STABILITY.md` (replaces `docs/ITERATION-2.md` and
  `docs/ITERATION-3.md`), compact security policy, condensed "Known
  limitations" with a pointer to the register.

### Removed

- `lixity.visualizer` compatibility shim — import the renderer from
  `lixity.ui` (`from lixity.ui import render_dashboard`).
- Committed sample dashboard artifact (`samples/effi-briest-dashboard.html`,
  2.4 MB); it is reproducible from the sample manuscript.

## [1.6.0] – 2026-09-22

### Added

- **Component status strip**: one dot per component (manuscript, analysis,
  dossiers, exports, NDA, markers) with a one-word state, supplied by the
  embedding tool; undeterminable components render `unknown` instead of a
  fake `ok`.
- **Work-marker notes**: clicking a marker kind opens an inline note field —
  `Enter` saves the marker with `note="…"`, `Esc` cancels. Labels in all
  seven languages.
- **Drill-down filters**: KPI tiles, band rows, dimension loadings, matrix
  rows and heatmap cells now navigate *and* preselect the matching view
  ("flagged only" / "deviations only" plus the style layer).
- **Busy states**: action buttons disable and spin while a server action
  runs, so latency is visible and double-clicks are avoided.
- `docs/llms.txt`, `docs/robots.txt`, `docs/sitemap.xml` and
  `docs/STABILITY.md` (single stability register).
- `samples/README.md` documenting sample provenance and licensing
  (Project Gutenberg #5323, public domain).

### Changed

- **Style-layer colour semantics**: colour encodes the *absolute value span*
  (min–max per dimension) so narrow bands stay readable; the legend prints
  the concrete min/max values, and the ring (|z| ≥ 1.5) remains the
  deviation-specific channel.
- **One JSON serializer**: the whole CLI and all artifact writers serialise
  through a single `orjson` helper (`OPT_NON_STR_KEYS`, deterministic
  output) instead of mixed `json` calls.
- Dependencies updated and validated in both project environments
  (pydantic 2.13.5, rich 15.0.0, orjson 3.12.0); the declared floors are
  unchanged, so existing installations keep working.
- README, `docs/USAGE.md`, `docs/AGENTS.md` (§3.4 dashboard DOM hooks) and
  the project page now cover the new UI, licensing/attribution and
  agent-readable surfaces.

### Fixed

- Zero-value heatmap cells use the neutral surface colour (previously they
  punched dark holes into the light theme and vice versa).
- Marker notes are escaped on write, so quotes and line breaks cannot break
  the marker comment.

### Removed

- Legacy payload helpers (`layer_colors`) and the short layer labels
  (`layer_below_short` / `layer_above_short`); `layer_stats` is the single
  source for layer values and deviations.

## [1.5.0] – 2026-09-22

### Added

- **Everything relevant is clickable**: KPI tiles jump to their panel (or
  activate the matching style layer), style-reference band rows and dimension
  loading bars open the layer, chapter-matrix rows jump to the chapter and
  work-marker rows jump to the containing chapter — mouse and keyboard.
- **Style-layer v2**: deviations (|z| ≥ 1.5) are ring-marked and counted in
  the legend, "only deviations" dims the rest, and "next deviation" walks
  through the marked passages one by one (opens the paragraph and scrolls).
- **Plain-language tooltips** in all seven languages: short, concrete, with a
  reading direction ("higher = …") instead of formulas; the heatmap formula
  moved to the docs.
- `docs/STABILITY.md` stays the reference for the stability register.

### Changed

- **"Style passport" is now "Style reference"** (de: *Stilreferenz*,
  fr: *Référence de style*, es/it/pt/nl analogous) – clearer name for the
  self-calibrated style norm. The API (`fingerprint`/`passport`) and the
  JSON schema are unchanged.
- Style layer is framed as **"Deviations"** (the select lists the dimensions),
  with short scale words ("below · above") and guidance on demand.
- KPI labels balance their line breaks; chapter-matrix micro-bars render as a
  thin underline instead of a block behind the number.

### Fixed

- Style-layer payload carries the robust z value (used for marking, counting
  and navigation); the legend count uses correct singular/plural.

## [1.4.0] – 2026-09-22

### Added

- **Centralised UI package `lixity.ui`** – renderer (`dashboard.py`),
  reusable components (`components.py`) and assets (CSS/JS) in one place;
  `lixity.visualizer` remains as a compatibility shim.
- **"Show, don't tell" dashboard**: style-passport **band chart** (range,
  median tick, outlier dots; numbers on demand in the tooltip), dimension
  **loading bars**, KPI **proportion bars**, chapter-matrix micro-bars and a
  self-dismissing hint instead of permanent instructions.
- **UI contract tests** (`tests/test_ui_contract.py`): every DOM id the
  script uses exists in the render, every help key and core label key is
  translated in all seven languages, and the visual components are rendered.
- **CI packaging job** verifying that the wheel contains the UI assets and
  the `py.typed` marker.
- `docs/STABILITY.md` – research findings, critical assessment and the
  stability register (with severity, evidence, mitigation); "Known
  limitations" section in `docs/USAGE.md`.

### Changed

- **Micro-interactions**: hover/press feedback on chips and buttons, animated
  paragraph expand (grid-rows), heatmap row/column highlight, translucent
  sticky toolbar, tooltip fade; `prefers-reduced-motion` disables animation.
- **Lexical-diversity guards** per Bestgen (2024/2025): MTLD and Maas a²
  require ≥ 100 tokens, otherwise `null` (all LD indices are unreliable on
  very short texts).
- Label-pack merge order documented (`docs/AGENTS.md` §3.3).

### Fixed

- Chapter-matrix micro-bars are rendered (replaces the unused placeholder);
  dead CSS rules removed.

## [1.3.1] – 2026-09-22

### Added

- Dashboard control panel shows a **manuscript-format hint**
  (`Markdown (.md), UTF-8 · chapters as “## Title”`), localized in all seven
  languages.

### Changed

- `docs/USAGE.md`: clearer manuscript-format section plus a step-by-step
  operating flow for the dashboard (KPIs → heatmap → style layer → paragraph).

## [1.3.0] – 2026-09-22

### Added

- **Idempotent workspace build** (`lixity build [FILE] [--dry-run]`): discovers
  the manuscript in a folder (`<folder>.md`, `manuscript.md`/`manuskript.md`,
  or the only `.md` file), creates `exports/` (with `exports/archive/`) and
  `nda/`, and publishes `_metrics.json`, `_profile.json`, `_style.json`,
  `_style_passport.txt`, `_report.md` and `_dashboard.html`. Identical input
  causes **zero writes**; changed input creates one timestamped version,
  updates the stable name and rotates older versions into the archive
  (last 10 kept per family). New module `lixity.workspace`.
- **Language-calibrated readability**: Flesch-type formulas per profile
  (Amstad, Flesch, Kandel-Moles, Szigriszt-Pazos, Franchina-Vacca, Martins,
  Douma), per-language syllable heuristics and a `flesch_variant` field.
- **Length-invariant lexical diversity**: MTLD (McCarthy & Jarvis 2010),
  MATTR (Covington & McFall 2010) and Maas a² – in JSON, reports and dashboard.
- Productive tense patterns for German (weak preterite, Perfekt) and English
  (regular `-ed`), complementing the curated verb forms.
- **Locale-aware number rendering** (`lixity.format`): one source of truth for
  CLI reports, style passport and dashboard – comma decimals and spaced
  percentages for de/es/it/pt/nl, narrow-space grouping for French.
- Reproducible screenshots: `scripts/make_screenshots.py` renders CLI reports
  and dashboard sections with headless Chromium.
- Worked example in README/USAGE: Fontane's *Effi Briest* as reference corpus
  and a sequel draft measured against its style corridor (`samples/`).

### Changed

- **Style layer overlay, reworked**: selecting a layer now colours the whole
  paragraph strip (blue = below, orange = above the chapter mean; tense stays
  on the top edge), with a legend, per-layer guidance ("what to look for"),
  exact values in the tooltip, and the active colour on the expanded
  paragraph. Heatmap cells are clickable and jump to the chapter while
  activating the matching layer; zero cells render calm.
- LIX long-word thresholds are calibrated per language (> 6/7/8 letters).
- Dashboard KPI grid grouped into **Scope · Rhythm · Language · Vocabulary ·
  Style**; locale-aware numbers; keyboard focus outlines and
  Escape-to-close tooltips.
- **Performance**: JSD chapter divergence iterates only the chapter's own
  vocabulary (closed form for absent types, ~4× faster), MATTR runs in O(N)
  with an incremental type counter, syllable/comment regexes are precompiled
  and a duplicated sentence scan was removed – analysis of the 95k-word
  reference corpus drops from ~3.0 s to ~1.7 s.
- **Architecture**: dashboard CSS/JS moved to `lixity/assets/` (editable,
  lintable, shipped as package data); locale-aware number rendering
  centralised in `lixity.format`; language data typed (`TypedDict`,
  annotated registries); `py.typed` marker added; `mypy` configured and
  enforced in CI.
- `punctuation` uses language-neutral keys (`periods`, `commas`, …); display
  names are localized.
- Chapter dominance uses canonical values (Präsens/Präteritum/Gemischt).

### Fixed

- All pre-existing type errors resolved (`mypy` clean across 18 modules and
  the test suite).
- Jensen-Shannon chapter divergence is now bit-identical across processes
  (deterministic iteration) – reproducible artifacts.
- Dutch passive regex no longer matches plain copula sentences.
- French first-person starters handle elision (`J'aime`).
- English `read` is no longer counted in both present and past.

### Security

- `SECURITY.md` documents the threat model (offline, no shell, escaped
  output, no secrets on disk).
- `.gitignore` hardened for secrets and private stores (`*.enc`, `*.key`,
  `*.pem`, `.env*`, `secrets/`).
- Artifact writes are `fsync`ed before the atomic rename (durability).

## [1.2.0] – 2026-09-22

### Added

- **Measurement uncertainty**: every style feature carries a documented
  standard error (`ChapterMetrics.style_se`: Poisson for count densities,
  binomial for shares, plug-ins for ASL/CV/starter entropy via Miller-Madow,
  HD-D sample dispersion). Deviations are now **significance-adjusted**:
  `z* = (x − median) / √(σ² + SE²)` – noisy small chapters cannot produce
  false alarms.
- **Multiple-testing control**: the passport reports the statistically
  expected false positives at |z*| ≥ 2.5 and the **Benjamini-Hochberg FDR
  set** (q = 0.05) across all chapter×feature cells.
- **Self-calibrated style dimensions**: Spearman correlation matrix of the
  features, eigendecomposed via cyclic Jacobi rotations (pure stdlib) –
  the manuscript's own abstract style axes with loadings, variance share,
  per-chapter scores and flagged chapters (Biber-style, but no pre-defined
  registers). Redundant feature pairs (|ρ| ≥ 0.8) are reported.
- **Work markers** (`markers.py`): editor-visible, renderer-invisible
  `<!-- LIXITY-MARKER id="…" kind="…" note="…" -->` lines with deterministic
  content-hash IDs; add/list/resolve/update, idempotent, sanitised notes;
  set/resolve from the dashboard (local control server) or the Python API.
- **Agent interface**: stable `lixity.api` facade (`analyze`, `profile`,
  `fingerprint`/`passport`, `dashboard`, `markers`, `add_marker`,
  `resolve_marker`, `about`) with self-describing meta blocks, plus CLI
  `about`, `completion bash|zsh`, `--version` and defined exit codes.
- `docs/AGENTS.md`: machine-facing contracts (commands, JSON schemas,
  interpretation heuristics, Python API).
- New tests: significance adjustment, Benjamini-Hochberg, Jacobi
  eigendecomposition, Spearman, markers lifecycle, API facade, CLI surface.

### Changed

- `style --json` passport is now schema version 2 (meta block with
  expected false positives and FDR q; `dimensions`, `fdr_flagged`,
  `redundant_features`, feature units).
- Dashboard: style-dimensions panel, significance-adjusted heatmap cells
  with effect-size tooltips, false-positive/FDR footnote, work-marker panel
  and per-paragraph marker buttons (control mode).
- Language profiles: project-neutral signal keywords (empty defaults –
  leitmotifs belong to `CorpusConfig.signal_keywords` / `motif_regexes`).
- Release kit: `api.py`, `markers.py`, current CLI/CI/pyproject templates,
  richer `.gitignore`, SEO-optimised README and GitHub Pages
  (meta description, Open Graph, Twitter cards, JSON-LD).

## [1.1.0] – 2026-09-22

### Added

- **Self-calibrating style fingerprint** (`style_fingerprint.py`): register-neutral
  consistency analysis. For 16 descriptive features (ASL, staccato, hypotaxis,
  sentence CV, dialogue, function words, perception filters, modals, passive,
  nominalisations, adjectives, long words, starter entropy, first-person starts,
  Guiraud R, HD-D) the engine derives the manuscript's own house style
  (robust median/MAD) and flags chapters only by deviation from it (robust z).
- **Jensen-Shannon chapter divergence** with additive, interpretable driver
  words (leave-one-out, content-word filtered) per chapter.
- **HD-D** (McCarthy & Jarvis 2010) and per-chapter **Guiraud R** as
  length-robust lexical diversity measures (TTR stays for continuity).
- **`lixity style manuscript.md`**: style passport as text or JSON
  (`--json`) – self-calibrated feature bands usable as constraints for
  authoring/editing (human or assisting LLM).
- **Dashboard**: chapter × feature heatmap with diverging z-colour scale,
  style-passport panel (median, ±2σ band, outliers), consistency KPI,
  top-deviant KPI, drift column in the chapter matrix, and a style-layer
  overlay for the chapter strips (ASL/function/dialogue/filter/modal/
  nominal/passive, within-chapter normalised).
- Per-paragraph style densities (perception filters, modals, nominalisations,
  passive) in the paragraph detail line and chip tooltips.
- Style-pattern data per language (`STYLE_DATA`: first-person starters,
  passive markers, nominal/adjective suffixes) – empty for `generic`, so all
  metrics degrade gracefully without the profile.
- New tests (`tests/test_style_fingerprint.py`): robust statistics, HD-D
  determinism, JSD driver words, passport structure, heatmap/layer rendering.

### Changed

- `ChapterMetrics`/`CorpusMetrics` extended with the style features
  (all fields defaulted – existing payloads stay valid).
- `LanguageProfile`/`ResolvedLanguage` carry the new style patterns;
  `CorpusConfig` accepts optional overrides (`passive_regex`, `nominal_regex`,
  `adjective_regex`, `first_person_starters`).
- Dashboard KPI row extended (Guiraud R, HD-D, staccato, first-person starts,
  consistency, top deviant).

## [1.0.2] – 2026-09-22

### Fixed

- `lixity dashboard` crashed with `NameError: name 'os' is not defined`
  (`os` was imported only in the `__main__` branch).
- `lixity dashboard` now accepts the documented `-o` shorthand for `--output`.

### Added

- Screenshots (CLI report, dashboard light/dark) generated from the reference
  manuscript, embedded in the README and the project page.
- `docs/USAGE.md`: full command-line, library and configuration reference with
  a metric glossary and troubleshooting section.
- `CHANGELOG.md`.
- CI matrix testing Python 3.10 and 3.12 plus a pinned lint step.
- `[project.urls]` metadata for repository, docs, changelog and issues.

### Changed

- README and GitHub Pages rewritten for readability, with a quick start, a
  dashboard guide and a worked example.
- Requires Python 3.10 or newer (previously `>= 3.9`, which was EOL and
  inconsistent with the configured Ruff target `py310`).
- Modernised type annotations (`X | None`, builtin generics), sorted imports,
  precise exception handling in `FileUtils`; all 99 Ruff findings resolved and
  the rule set pinned in `pyproject.toml`.

## [1.0.1] – 2026-09-22

### Changed

- English code comments, documentation and generated CLI/site text.

## [1.0.0] – 2026-09-22

### Added

- Initial release: corpus metrics (ASL, TTR, Guiraud R, Yule's K, Flesch, LIX,
  dialogue and function-word ratios, punctuation densities, perception
  filters), paragraph-accurate tense profiles, single-file HTML dashboard,
  seven language profiles plus a neutral fallback, and idempotent publication
  helpers.

[Unreleased]: https://github.com/mfahsold/lixity/compare/v0.7.7...HEAD
[0.7.7]: https://github.com/mfahsold/lixity/compare/v0.7.6...v0.7.7
[0.7.6]: https://github.com/mfahsold/lixity/compare/v0.7.5...v0.7.6
[0.7.5]: https://github.com/mfahsold/lixity/compare/v0.7.4...v0.7.5
[0.7.4]: https://github.com/mfahsold/lixity/compare/v0.7.3...v0.7.4
[0.7.3]: https://github.com/mfahsold/lixity/compare/v0.7.2...v0.7.3
[0.7.2]: https://github.com/mfahsold/lixity/compare/v0.7.1...v0.7.2
[0.7.1]: https://github.com/mfahsold/lixity/compare/v0.7.0...v0.7.1
[0.7.0]: https://github.com/mfahsold/lixity/compare/v0.6.0...v0.7.0
[0.6.0]: https://github.com/mfahsold/lixity/compare/v0.5.0...v0.6.0
[0.5.0]: https://github.com/mfahsold/lixity/compare/v0.4.9...v0.5.0
[0.4.9]: https://github.com/mfahsold/lixity/compare/v0.4.8...v0.4.9
[0.4.8]: https://github.com/mfahsold/lixity/compare/v0.4.7...v0.4.8
[0.4.7]: https://github.com/mfahsold/lixity/compare/v0.4.6...v0.4.7
[0.4.6]: https://github.com/mfahsold/lixity/compare/v0.4.5...v0.4.6
[0.4.5]: https://github.com/mfahsold/lixity/compare/v0.4.4...v0.4.5
[0.4.4]: https://github.com/mfahsold/lixity/compare/v0.4.3...v0.4.4
[0.4.3]: https://github.com/mfahsold/lixity/compare/v0.4.2...v0.4.3
[0.4.2]: https://github.com/mfahsold/lixity/compare/v0.4.1...v0.4.2
[0.4.1]: https://github.com/mfahsold/lixity/compare/v0.4.0...v0.4.1
[0.4.0]: https://github.com/mfahsold/lixity/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/mfahsold/lixity/compare/v3.0.1...v0.3.0
[3.0.1]: https://github.com/mfahsold/lixity/compare/v3.0.0...v3.0.1
[3.0.0]: https://github.com/mfahsold/lixity/compare/v2.4.0...v3.0.0
[2.4.0]: https://github.com/mfahsold/lixity/compare/v2.3.0...v2.4.0
[2.3.0]: https://github.com/mfahsold/lixity/compare/v2.2.0...v2.3.0
[2.2.0]: https://github.com/mfahsold/lixity/compare/v2.1.0...v2.2.0
[2.1.0]: https://github.com/mfahsold/lixity/compare/v2.0.0...v2.1.0
[2.0.0]: https://github.com/mfahsold/lixity/compare/v1.25.0...v2.0.0
[1.25.0]: https://github.com/mfahsold/lixity/compare/v1.24.1...v1.25.0
[1.24.1]: https://github.com/mfahsold/lixity/compare/v1.24.0...v1.24.1
[1.24.0]: https://github.com/mfahsold/lixity/compare/v1.23.0...v1.24.0
[1.23.0]: https://github.com/mfahsold/lixity/compare/v1.22.0...v1.23.0
[1.22.0]: https://github.com/mfahsold/lixity/compare/v1.21.0...v1.22.0
[1.21.0]: https://github.com/mfahsold/lixity/compare/v1.20.0...v1.21.0
[1.20.0]: https://github.com/mfahsold/lixity/compare/v1.19.0...v1.20.0
[1.19.0]: https://github.com/mfahsold/lixity/compare/v1.18.0...v1.19.0
[1.18.0]: https://github.com/mfahsold/lixity/compare/v1.17.0...v1.18.0
[1.17.0]: https://github.com/mfahsold/lixity/compare/v1.16.0...v1.17.0
[1.16.0]: https://github.com/mfahsold/lixity/compare/v1.15.0...v1.16.0
[1.15.0]: https://github.com/mfahsold/lixity/compare/v1.14.0...v1.15.0
[1.14.0]: https://github.com/mfahsold/lixity/compare/v1.13.0...v1.14.0
[1.13.0]: https://github.com/mfahsold/lixity/compare/v1.12.0...v1.13.0
[1.12.0]: https://github.com/mfahsold/lixity/compare/v1.11.0...v1.12.0
[1.11.0]: https://github.com/mfahsold/lixity/compare/v1.10.0...v1.11.0
[1.10.0]: https://github.com/mfahsold/lixity/compare/v1.9.1...v1.10.0
[1.9.1]: https://github.com/mfahsold/lixity/compare/v1.9.0...v1.9.1
[1.9.0]: https://github.com/mfahsold/lixity/compare/v1.8.0...v1.9.0
[1.8.0]: https://github.com/mfahsold/lixity/compare/v1.7.0...v1.8.0
[1.7.0]: https://github.com/mfahsold/lixity/compare/v1.6.1...v1.7.0
[1.6.1]: https://github.com/mfahsold/lixity/compare/v1.6.0...v1.6.1
[1.6.0]: https://github.com/mfahsold/lixity/compare/v1.5.0...v1.6.0
[1.5.0]: https://github.com/mfahsold/lixity/compare/v1.4.0...v1.5.0
[1.4.0]: https://github.com/mfahsold/lixity/compare/v1.3.1...v1.4.0
[1.3.1]: https://github.com/mfahsold/lixity/compare/v1.3.0...v1.3.1
[1.3.0]: https://github.com/mfahsold/lixity/compare/v1.2.0...v1.3.0
[1.2.0]: https://github.com/mfahsold/lixity/compare/v1.1.0...v1.2.0
[1.1.0]: https://github.com/mfahsold/lixity/compare/v1.0.2...v1.1.0
[1.0.2]: https://github.com/mfahsold/lixity/compare/v1.0.1...v1.0.2
[1.0.1]: https://github.com/mfahsold/lixity/compare/v1.0.0...v1.0.1
[1.0.0]: https://github.com/mfahsold/lixity/releases/tag/v1.0.0
