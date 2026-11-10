# Lixity CLI and project reference

<a id="lixity--usage--reference"></a>
<a id="lixity-usage-reference"></a>

Use this handbook to select commands, produce reports and configure a project.
For a first session, start with [Onboarding](ONBOARDING.md). Browser navigation
belongs to the [workspace manual](WORKSPACE.md); recording, listening and speech
belong to the [audio manual](AUDIO.md). The [research manual](research/USAGE.md)
owns retained sources, citations, dossiers, Zotero, backups and OCR.
[Automation contracts](AGENTS.md) define JSON envelopes and HTTP requests.

- [Run a first analysis](#quick-start)
- [Explore linguistic questions](#linguistic-text-analysis)
- [Choose a command](#which-command-for-which-question)
- [Read command workflows](#command-reference)
- [Inspect a project](#lixity-project)
- [Review and record a decision](#lixity-analysis-review)
- [Export a dashboard, PDF or website](#lixity-dashboard)
- [Start or inspect the app](#lixity-service)
- [Interpret results](#understanding-the-metrics)
- [Prepare a manuscript](#manuscript-format--how-to-operate-lixity)
- [Configure a project](#configuration-corpusconfig)
- [Use the Python library](#library)
- [Troubleshoot](#troubleshooting)

Examples use `manuscript.md` and `./novel` as placeholders for your own UTF-8
Markdown file and project folder. Analysis and ordinary file exports do not
require a running browser service. Commands marked **unreleased** require the
current development version; inspect `lixity --version` and installed `--help`
before using them.

## Installation

The [installation guide](INSTALLATION.md) covers supported systems, isolated
CLI/Python environments, updates, removal and shell completion. Commands here
assume `lixity` is on your `PATH`. For a source checkout, use
[CONTRIBUTING.md](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md).

## Use the installed help

```sh
lixity --help
lixity analyze --help
lixity research --help
lixity research ingest --help
lixity service --help
```

**Since 0.8.0:** top-level commands are grouped by task. Command
help includes examples, prerequisites, output behavior and a link to the relevant
manual. Dense audio and export options are grouped by purpose; research help
states defaults and distinguishes inspection from retention or other writes.
Help describes the installed code and works without a project or running service.
Examples use illustrative paths and IDs; replace them with your reviewed inputs.
Reading help does not execute those examples, start audio or access a worker.

Help is in English. `LIXITY_LANG` selects localized reports/messages; it does
not change the help or select the manuscript's analysis language. Use the
per-command `--language` option for analysis or speech, as described there.
`lixity about --json` exposes installed metadata for automation; it is not a
replacement for reading a command's applicable options and write effects.

## Report language

Reports and CLI messages use English by default; `LIXITY_LANG=de` selects
German presentation. Other presentation languages fall back to English. This
is separate from the manuscript's analysis language: use `--language de`,
for example, or explicit `--language auto` for detection. Weak or ambiguous
evidence selects the generic profile. See [Localization](LOCALIZATION.md) for
coverage and project-supplied report text.

## Quick start

```bash
lixity analyze manuscript.md --language en
lixity dashboard manuscript.md --language en -o dashboard.html
```

`analyze` prints a terminal report; `dashboard` writes a browsable HTML file.
Both leave the manuscript unchanged. Set the manuscript's actual language;
English is the default and automatic detection requires `--language auto`.
To work from a project with a configured manuscript, use an explicit root:

```bash
lixity analyze --project ./novel --json -o analysis.json
lixity project --project ./novel
```

Configure the root-local [default manuscript](#default-manuscript) before omitting
the file. Quote paths containing spaces, for example `"drafts/My novel.md"`.
[Choose another command](#which-command-for-which-question) for focused analysis
or a different output.

## Linguistic text analysis

Use Lixity for exploratory, descriptive work on prose: compare sentence lengths
between chapters, inspect vocabulary diversity, or trace a readability result
back to its counts. The same engine serves manuscript revision and linguistic
questions; there is no separate research-only analysis mode.

Choose a question you can check against the actual passages:

| Question | Start with | Keep comparable |
| --- | --- | --- |
| Does sentence rhythm change between sections? | Sentence-length measurements and chapter comparison | Chapter boundaries, punctuation treatment and analysis language |
| Does vocabulary diversity differ between samples? | TTR, HD-D and MTLD, then inspect the counted words | Sample length, genre, edition and tokenization settings |
| Where do particular expressions recur? | Motif patterns and their chapter distribution | Pattern definitions, case handling and the same text projection |

These are descriptive comparisons. For a collection of documents, analyze each
explicitly and retain its identity with the output; do not treat one manuscript's
internal reference as a population norm. The research archive stores evidence
and citations separately and does not automatically add sources to that reference.

1. Define the question and text scope before inspecting the results. Keep a copy
   of the input, its source and edition, and any conversion or cleaning steps.
2. Choose the actual language explicitly. Keep chapter boundaries and settings
   consistent across runs; a different segmentation changes the comparison.
3. Export the measurements and inspect the counted passages in the dashboard.
   An unexpected value is a reason to inspect the text and method.
4. Record the Lixity version, input checksum, configuration and exact command
   alongside the output. Preserve unavailable values and warnings in downstream
   work rather than treating them as zero.

For an English UTF-8 text named `sample.md`:

```sh
lixity --version
lixity about --json > capabilities.json
lixity analyze sample.md --language en --json -o analysis.json
lixity dashboard sample.md --language en -o dashboard.html
```

These commands read the input and create reports; they do not alter the text.
Use `--language de` for German, for example. Browser language does not select an
analysis language. For project work, retain the root-local configuration too.
The [JSON contracts](AGENTS.md#3-json-contracts) describe result envelopes;
[Methods](METHODS.md) defines TTR, HD-D, MTLD, sentence measures and readability.

**Interpretation:** chapter comparisons use this text's internal reference,
not a representative language corpus. Length, genre, segmentation and language
resources affect comparisons. Readability is a model estimate, not a reader
study; lexical diversity is not writing quality. Lexical tense cues are not a
complete grammatical parse. Optional syntax models have separate installation
and interpretation limits. Lixity does not establish authorship, causal effects
or equivalent validation across languages. See [Stability](STABILITY.md) and
[Localization](LOCALIZATION.md) before comparing datasets.

## Which command for which question?

| Question | Command | Key numbers |
| :--- | :--- | :--- |
| How does the manuscript read overall? | [`lixity analyze`](#lixity-analyze) | ASL, CV, TTR, HD-D, MTLD, Flesch, LIX, dialogue, registers |
| Where do heuristic tense markers change or mix? | [`lixity profile`](#lixity-profile) | per paragraph: dominant tense, mix, switch, severity 0–3 |
| How does each chapter differ from this manuscript's reference? | [`lixity style`](#lixity-style) | median/MAD bands, z\*, FDR set, style dimensions |
| How is the dialogue structured? | [`lixity dialogue`](#lixity-dialogue) | turns, turn lengths, turns per 1,000 words, dialogue paragraphs |
| Who appears where — and when not? | [`lixity characters`](#lixity-characters) | mentions, chapters present, span, longest gap |
| Where do scene lengths and endings differ? | [`lixity pacing`](#lixity-pacing) | scenes, scene length, ASL curve, ending-cue count 0–3 |
| How does one scene compare with declared registers or targets? | [`lixity scenes`](#scene-registers-and-project-targets) | scene selection, register references and planned scenes |
| Which tense observations have I reviewed? | [`lixity analysis-review`](#lixity-analysis-review) | current observations and explicitly saved kept/changed/later decisions |
| What repeats itself? | [`lixity motifs`](#lixity-motifs) | motif presence, top content words, repeated n-grams |
| How do word-pattern and quotation/short-sentence cues vary? | [`lixity showing`](#lixity-showing) | standardized signal groups and their difference; not a narrative classification |
| I want to browse the available analysis panels | [`lixity dashboard`](#lixity-dashboard) | self-contained HTML; research and writes require the local app |
| I want a foreground server for development or integration | [`lixity serve`](#lixity-serve) | loopback HTTP server, live settings, manuscript upload, research panel |
| I want to start or manage the installed app | [`lixity service`](#lixity-service) | managed start, stop, restart and status without a source checkout |
| Which installation and service am I using? | [`lixity doctor`](#lixity-doctor) | package versions, module/interpreter location, contracts and owned service status |
| Which files are sources or outputs, and are their locations usable? | [`lixity project --project PATH`](#lixity-project) | read-only roles, existing outputs and bounded structure findings |
| I want to manage and cite research sources | [`lixity research`](#lixity-research) | immutable archives, citations, dossiers, manuscript grounding |
| I want a printable document, report or reading copy | [`lixity pdf`](#lixity-pdf) | neutral/editorial A4, A4 report, A5 book, 30×60 sheet |
| I want a planned or rendered listening copy | [`lixity read-aloud`](AUDIO.md#lixity-read-aloud) | project voice profiles, explicit direction and optional native/external speech engines; capabilities and setup in the audio manual |
| I want to share a browsable reading copy | [`lixity export-site`](#lixity-export-site) | static website, optional research and original sources |
| I want a reproducible artifact set | [`lixity build`](#lixity-build) | `exports/`, archive rotation |
| What can the engine do? | [`lixity about --json`](#lixity-about-and-lixity-completion) | languages, features, thresholds, commands |
| What does the installed tool expose? | [`lixity schema`](#lixity-about-and-lixity-completion) | capability metadata, equivalent to `about --json`; not an analysis-result JSON Schema |

## Command reference

Choose the command above for a task, or use these groups:

- Analysis: [analyze](#lixity-analyze), [profile](#lixity-profile),
  [grammatical tense](#grammatical-tense), [dialogue](#lixity-dialogue),
  [characters](#lixity-characters), [pacing](#lixity-pacing),
  [scenes and registers](#scene-registers-and-project-targets), [motifs](#lixity-motifs),
  [showing](#lixity-showing), [style](#lixity-style).
- Project and review: [project](#lixity-project), [analysis-review](#lixity-analysis-review),
  [research](#lixity-research), [audio](AUDIO.md).
- Outputs: [dashboard](#lixity-dashboard), [pdf](#lixity-pdf),
  [export-site](#lixity-export-site), [build](#lixity-build).
- Application and discovery: [serve](#lixity-serve), [service](#lixity-service),
  [doctor](#lixity-doctor), [about, schema and completion](#lixity-about-and-lixity-completion).

### Common options

The installed CLI owns exact arguments, accepted values and defaults:

```bash
lixity --help
lixity style --help
```

Use `lixity COMMAND --help` for any command below. Explicit analysis options
override project settings. English is the default analysis language; automatic
detection requires `--language auto`. `lixity about --json` lists installed
commands, formats, feature identifiers, languages and thresholds. `lixity schema`
emits the same capability metadata, not a JSON Schema for every result.
[Automation contracts](AGENTS.md) describe versioned output envelopes and exit
codes; a running server advertises registered operations at `GET /api`.

`analyze`, `profile`, `style`, `dialogue`, `pacing` and `showing`
accept `-o PATH` / `--output PATH` for their text or JSON report. Without it,
report data goes to stdout. With it, a successful result is written atomically
and stdout stays empty; diagnostics remain on stderr. A failed report/write
preserves an existing destination. The manuscript and its aliases cannot be
used as the report destination. PDF and dashboard keep their own file formats.

```bash
lixity analyze manuscript.md --language en --json -o analysis.json
lixity profile manuscript.md --language en --layer asl -o paragraph-review.txt
```

`dialogue`, `pacing`, `motifs` and `showing` use the same guarded manuscript
reader as `analyze`: invalid UTF-8 or a special file node returns processing
failure (exit 1), without waiting for a pipe writer or publishing a result.

### `lixity project`

Inspect the selected project without a running service:

```bash
lixity project --project /path/to/book
lixity project /path/to/book --json
```

Without a selector, the CLI inspects the current directory only. It reads root
`pyproject.toml`/`lixity.toml`, never user or ancestor settings. Manuscript
selection reuses the configured relative path and existing workspace discovery;
the live overview also identifies disagreement with the currently selected file.
Missing optional research/output folders are normal. Ambiguous or unavailable
sources, invalid settings, unsafe links and source/configuration aliases produce
explicit findings. Exit 1 means an error finding or an unavailable inspection;
warnings and an unassigned manuscript alone do not fail the command.

**Available** means the filesystem metadata was accessible. It does not certify
research integrity, output contents or freshness. Existing outputs always show
**Source and generation history unknown**: filenames and modification times do
not prove which manuscript/configuration generated them. Run `research audit`
for archive integrity and `build` to produce analysis outputs deliberately.
Submission documents remain **Unassigned**; this view does not guess which
dossier is an exposé or invent a second folder convention.

Inspection reads no manuscript/output contents or research history. Configuration
reads stop at 1 MiB per file; discovery and output scans stop at 2,000 directory
entries and return at most 200 output files. Reaching a limit is reported as an
incomplete inspection, not a clean bill of health. Nested output folders are not
inventoried. The native view requires a current selected-project context; a changed
or oversized configuration can require reopening the view or CLI inspection.
Downloads recheck their file and project context when opened.

This feature creates, edits, moves and deletes no files. Git, backups, private
recipient records and unknown project files remain outside its remit. Static
reports and exported reading websites contain no local project inventory or
live structure controls.

### `lixity analyze`

Use the terminal report for corpus size, sentence rhythm, vocabulary,
readability, dialogue and chapter measurements:

```bash
lixity analyze manuscript.md --language en
```

Add `--json` for the versioned metrics envelope. Counts distinguish full input,
prose and regex tokens; `clean_words` retains its legacy whitespace count.
`median_sl` retains the integer upper median; `median_sl_exact` averages the
middle pair. Dialogue percentages divide quoted tokens by tokens under the
same configured `word_regex`, including chapter `dialog_pct`. Regenerate both
sides of a comparison with the same analysis version. See
[metric definitions](#understanding-the-metrics) and
[JSON contracts](AGENTS.md#3-json-contracts).

<a id="grammatical-german-tense"></a>

### Grammatical tense

Since v0.7.6, explicitly installed local syntax models can replace lexical
tense cues with contextual verb-group analysis in de/en/fr/es/it/pt/nl. This is optional: the default
installation retains lightweight, incomplete pattern counts. Installing a model
does not silently change existing projects. Languages without an explicitly selected model retain their existing
profiles. No model or manuscript data is downloaded/uploaded during analysis.

For a new isolated application installation, install the extra and the
explicit model wheel in the same environment (network access is needed here):

```sh
uv tool install --python 3.12 "lixity[linguistics]" --with https://github.com/explosion/spacy-models/releases/download/de_core_news_md-3.8.0/de_core_news_md-3.8.0-py3-none-any.whl
```

For an existing tool installation, review its recorded additional requirements
first: replacing it can remove other installed models and dependencies. See
[updates and removal](INSTALLATION.md#updates-and-removal).

For a Python project, use `python -m pip install --upgrade "lixity[linguistics]"`
and install that model wheel into the same environment. The model is a separate
upstream artifact, not bundled in the Lixity wheel. Its published metadata lists
MIT licensing. Pin and review model versions independently; restart the app after
changing models. The core package still supports Python 3.10+; model/runtime wheel
availability is a separate platform prerequisite. Python 3.12 is the tested setup.

The initial CPU model choices were checked separately, not assumed equally
accurate. Models and their training data have separate licenses; none are
bundled in Lixity. Review the selected artifact's current terms before reuse:

| Analysis language | Initial tested model | Runtime | Published model terms |
| --- | --- | --- | --- |
| German | `de_core_news_md` 3.8.0 | spaCy | MIT |
| English | `en_core_web_md` 3.8.0 | spaCy | MIT |
| French | `stanza:fr_gsd`, resources 1.15.0, GSD nocharlm | Stanza CPU | Apache-2.0 model repository; GSD data CC BY-SA4.0 |
| Spanish | `es_core_news_md` 3.8.0 | spaCy | GPL-3.0 |
| Italian | `stanza:it_markit`, resources 1.15.0, MarkIT nocharlm | Stanza CPU | Apache-2.0 model repository; MarkIT data CC BY4.0 |
| Portuguese | `pt_core_news_md` 3.8.0 | spaCy | CC BY-SA4.0 |
| Dutch | `nl_core_news_md` 3.8.0 | spaCy | CC BY-SA4.0 |

Other supported-language spaCy pipelines can be explicitly selected; they need
a parser and POS/morphology annotations and their actual language must match.
The Italian spaCy models' CC BY-NC-SA terms are why the initial tested Italian
setup uses MarkIT instead. This records published terms, not blanket clearance
of every training source or voice model. See official
[spaCy model metadata](https://github.com/explosion/spacy-models/tree/master/meta)
and the [Stanza Italian](https://huggingface.co/stanfordnlp/stanza-it) and
[French](https://huggingface.co/stanfordnlp/stanza-fr) model repositories.

The Stanza profiles require `lixity[linguistics-stanza]` and a suitable CPU
PyTorch installation. Use the interpreter of the same environment that runs
Lixity; obtain resources explicitly during setup, never during analysis:

```python
import stanza
stanza.download("fr", package=None, processors={
    "tokenize": "gsd_nocharlm", "mwt": "gsd", "pos": "gsd_nocharlm",
    "lemma": "gsd_nocharlm", "depparse": "gsd_nocharlm",
})
stanza.download("it", package=None, processors={
    "tokenize": "markit_nocharlm", "mwt": "markit", "pos": "markit_nocharlm",
    "lemma": "markit_nocharlm", "depparse": "markit_nocharlm",
})
```

`STANZA_RESOURCES_DIR` can explicitly select the machine's resource directory;
use the same location during setup and app startup. The adapter selects only
these named processors, CPU mode and `download_method=None`; it does not select
a default/combined model if resources are missing. Set project `language="fr"`
with `tense_model="stanza:fr_gsd"`, or `it` with `stanza:it_markit`. For spaCy,
install the selected official 3.8.0 model wheel in the same environment, as in
the German example above. Pipeline failures are explicit; a single word whose
morphology is unknown is retained as an unresolved group instead of aborting
an otherwise annotated chapter.

Enable it explicitly at the project root, outside any TOML section:

```toml
language = "de"
tense_model = "de_core_news_md"
tense_scope = "narration"
```

Or select it for one invocation:

```sh
lixity profile draft.md --language de --tense-model de_core_news_md --tense-scope narration
lixity analyze draft.md --language de --tense-model de_core_news_md --json
```

`analyze`, `profile`, `analysis-review`, `style`, `dashboard`, `build`, `scenes` and foreground
`serve` accept these overrides. Saved project settings apply to CLI, native app,
Python pipeline and exports. `tense_scope = "all"` counts indicative verb groups
inside and outside recognized quotations; `narration` excludes recognized quoted
spans. This is quotation scope, not automatic narrator, thought or speaker
attribution. Scope is resolved over canonical chapter prose, including blockquote
context, before individual paragraphs are analyzed. Unmatched and unsupported
quotation formats can be missed; quotes do not continue across chapter boundaries.

A perfect construction such as `hat lange gesungen` counts once as past;
its auxiliary does not also count as present. Resolved present forms populate the present bucket; preterite, imperfect,
perfect, pluperfect and anterior perfect populate past. English and Dutch models
often omit Mood: those finite forms retain `mood="unmarked"` rather than being
relabeled indicative, but can contribute a resolved morphological tense. Future, conditional, modal,
subjunctive, imperative and nonfinite/unresolved groups do not populate them.
`ParagraphProfile.tense_analysis` and profile JSON preserve the detailed
`grammatical-tense/1` groups, exact component ranges, mood, voice, quotation scope,
selection and unresolved reasons. Component offsets address canonical counting
text; the existing evidence layer separately maps the enclosing cue span to
original displayed prose. It may contain intervening words. A coordinated
predicate can share an auxiliary with another predicate. The passage inspector
shows exclusions and unresolved groups, including paragraphs without a warning.

Explicit tense regex overrides cannot be combined with `tense_model`.
Missing models, annotation failures and paragraphs over 250,000 characters fail
explicitly; they never silently fall back to pattern counts. Parser model, model
version, spaCy version and composition policy are part of saved review identity.
Changing those settings invalidates prior review decisions rather than accepting
old decisions under a new measurement. Recompute reports after enabling a model.

The initial model comparison and known errors are documented in
[Stability](STABILITY.md#grammatical-tense). A grammatical form is not an
editorial error; historical present, recollections and dialogue need human review.

### `lixity profile`

Locate paragraph-level tense mixtures, switches and style densities with
source line anchors:

```bash
lixity profile manuscript.md > profile.json
```

This command emits JSON. Language-neutral `dominant` values (`present`, `past`,
`mixed`, `neutral`) become localized labels in reports. Without an explicit grammatical model, tense classification
counts incomplete lexical and pattern cues: `mixed` requires at least two markers per tense and
at least 25% minority share. `switch` compares consecutive dominant tenses;
severity 0–3 prioritizes review. See the [classification contract](AGENTS.md)
for the truth table and direct-library threshold controls.

**Since v0.7.7:** the default German patterns no longer treat an unknown
`-te/-ten/-test` ending as sufficient evidence of past tense. This avoids some
adjective matches and adds selected cues such as `übt`, but unlisted regular
past forms such as `flatterten` can now be missed; other ambiguous matches remain.
Recompute analyses before comparing with v0.7.6 results. Saved decisions for
observations that remain are marked stale; disappeared observations are counted
as unmatched. Stored decisions are not altered automatically.

Densities are counts per 1,000 words, not percentages; short paragraphs can have
large values from few matches. Nominalization suffix cues exclude curated
function words unless a project regex override is supplied. They remain
heuristics rather than a grammatical parse.

Inspect the same selected paragraph metric
from the terminal, without printing manuscript prose:

```bash
lixity profile manuscript.md --layer asl
lixity profile --layer filter --only-notable
lixity profile --layer filter --only-notable --json
```

Choices are `asl`, `function`, `dialogue`, `filter`, `modal`, `nominal` and
`passive`. Human output lists source-file/line anchors, raw values/units and local
z. `--only-notable` filters output after computing all chapter references; it
requires `--layer`. The summary keeps full profiled/comparable/notable counts
separate from rows shown. Empty human selections
explain the actual chapter limits (too few measurable paragraphs, zero MAD or no
measurable values) and provide a shell-quoted full-evidence command. German
analysis reports also use German explanations; machine identifiers remain stable.
Configured manuscript omission follows the existing
[project resolver](#default-manuscript). Without `--layer`, profile retains its
existing JSON v2 output, including when `--json` is omitted.

With `--layer --json`, the opt-in envelope is `paragraph-layer/1`; unavailable
comparisons have `z: null` and `notable: null`, while measured zero remains zero.
Densities remain word-pattern counts per 1,000 words, not exact token spans or a
grammatical interpretation. See [the contract](AGENTS.md#311-opt-in-paragraph-layers).

Since v0.7.3, add `--evidence` to a selected layer for literal counted spans:

```sh
lixity profile --layer filter --evidence
lixity profile --layer asl --evidence --json
```

Human output includes bounded quoted examples and source lines. JSON uses the
separate opt-in `paragraph-layer-evidence/1` envelope with exact Unicode-codepoint
offsets and paragraph hashes; default profile and `paragraph-layer/1` outputs are
unchanged. `--only-notable` still filters after full chapter references. Mapping
status distinguishes available, partial and unavailable evidence; measured zero
remains zero. See [the evidence contract](AGENTS.md#311-opt-in-paragraph-layers).

### `lixity analysis-review`

Read the current tense observations and saved decisions for an explicit project.
Reading creates no files. To save, choose an observation and copy all three exact
identity values from that read into the write command below; `ID`, `SOURCE`,
`ANALYSIS` and `REVIEW` are placeholders. Status is `kept`, `changed` or `later`.
The [workspace review procedure](WORKSPACE.md#save-review-decisions) uses the same
observations and guards.

```sh
lixity analysis-review --project ./novel --json
lixity analysis-review --project ./novel --observation ID --status kept \
  --expected-source-sha256 SOURCE --expected-analysis-sha256 ANALYSIS \
  --expected-review-sha256 REVIEW --json
```

The human-readable CLI also reports the unmatched count when it is nonzero;
the versioned JSON reports it as `unmatched_decisions`.
Use exact identities from the current read. A stale tab/writer/settings/source
returns an error; read again before deciding. **Changed by me** is explicitly
self-reported. State lives in `.lixity/analysis-review.json` with schema
`lixity-analysis-review-state/1`, bounded to 10,000 decisions and 4 MiB.
Reads create no files. Writes reuse the project writer lock and atomic file
writer; no research archive is initialized. Back up this local project state
separately from the Research archive if those decisions matter.

The entire source digest and resolved configuration/threshold signature bind
a decision. Even an unrelated text edit makes an earlier matching decision
stale; edited/moved paragraphs can instead appear as new observations, while the
prior decision is retained but unmatched. This is a conservative review boundary,
not semantic change detection or a “since last session” diff. Reading exports
do not serialize decisions or allow saves. No review data is sent to analytics.

### `lixity dialogue`

Inspect quoted-speech segments, their lengths and chapter distribution:

```bash
lixity dialogue manuscript.md
```

A turn is a quotation segment, without speaker attribution. A dialogue paragraph
has at least half its words inside detected quotations (configurable via
`dialogue_paragraph_share`). `--json` returns these summary and per-chapter
measurements for automation.

Beyond turn counts, `lixity dialogue` reports these quotation-based summaries:

- **Short turns** (≤ 12 words by default, configurable via `short_turn_max_words`):
  counts short quotation segments; it does not identify speakers or exchanges.
- **Long turns** (≥ 80 words by default, configurable via `long_turn_min_words`):
  counts extended quotation segments; it does not classify monologues.
- **Voice contrast (`ASL Δ`)**: difference between dialogue sentence length and narration
  sentence length (`dialogue_asl − narration_asl`). Its sign describes this manuscript's
  quotation/narration length difference; it does not identify a character's voice or register.

The browser dialogue chart retains every
measured chapter in manuscript order, including chapters with zero detected
turns. Long charts scroll within their bounded area rather than showing only
the chapters with the most dialogue. Click any chapter row to jump directly to
that chapter in the manuscript reader.

### `lixity characters`

Count supplied names or alias patterns across chapters:

```bash
lixity characters manuscript.md --name "Alex|Alexander" --name Morgan --json
```

Matching is whole-word and case-insensitive, excludes appendix/front matter,
and reports mentions, mention-based chapter span and longest gap. A match does
not establish physical presence, speaker identity or viewpoint. v0.7.1
can use [project-local literal profiles](#character-profiles) when explicit names
are omitted. Explicit names replace configured selections, including an empty
selection; the standalone command rejects empty names rather than discovering entities.
The [structure-result contract](AGENTS.md#35-structure-modules-dialogue-characters-pacing-motifs-showing)
documents all dialogue, character, pacing, motif and showing result fields.

### `lixity pacing`

Inspect scene lengths, sentence-length curves and chapter-ending cues:

```bash
lixity pacing manuscript.md
```

Explicit Markdown dividers split scenes. With no dividers,
`explicit_scene_breaks=0` and `scenes_are_chapters=true`: scene counts are chapter
placeholders and give no independent pacing evidence. Tempo proxies are sentence
length, staccato share (sentences ≤ `short_sentence_max`), dialogue share and scene length.
The hook score (0–3) adds one for each closing cue: at most eight words (configurable via
`hook_short_sentence`), terminal `?`/`!`/`…`, and closing dialogue. It measures these cues,
not suspense or reader response.

Pacing analysis also examines paragraph-local coherence and rhythmic monotony:
- **Adjacent sentence overlap (`sentence_overlap_pct`)**: share of consecutive within-paragraph
  sentence pairs that share at least one content word (empirical baseline: ~24% in literary reference novels).
  Narrows the gap between developmental macro-flow and line editing.
- **Repeated start runs (`repeated_start_runs`)**: runs of 3 or more consecutive sentences
  in a single paragraph opening with the identical word token (configurable via `monotony_min_run`),
  surfacing unintentional grammatical repetition or deliberate anaphora.

Text summaries identify the chapters with the shortest and
longest mean sentence length. The historical JSON keys `fastest_chapter` and
`slowest_chapter` retain their ASL-based meaning; they do not measure narrative
speed or reading time.

The pacing panel labels average sentence length
as **ASL**, gives its words-per-sentence unit and explains that bars are scaled
to the largest chapter average. The **Hook** help describes the same 0–3
heuristic; it adds no new suspense or quality score.

In the browser's **Pacing & scenes** and **Showing/telling** panels, long chapter
charts scroll within their bounded area. Use the mouse wheel or touch, or focus
a chapter row and use the keyboard's scrolling keys. All rows remain readable
at the end; a short chart that already fits needs no inner scrolling.

### Scene registers and project targets

Without chapter headings, a draft is measured as one chapter and keeps all its
prose. A leading `# Title` supplies its title; scene dividers still split the draft.

Use `lixity scenes manuscript.md --language de` to inspect each scene separately;
add `--json` for the scene envelope (schema version 1). The dashboard
shows the same observations in **Scenes & style registers**. Chapters serve as
scenes when there are no explicit dividers.

The scene comparison table stays visible in a
bounded scrolling region. Choose a scene's linked title to reveal its detailed
measurements inside **Scene measurements**. The catalogue and each scene use
native, reversible disclosures; close either summary when finished. These are
the same observations and project-defined comparisons, without a new analysis
or API format.

For everyday checks in a selected project:

```bash
lixity scenes --chapter 2
lixity scenes --scene 2:1 --json
lixity scenes --latest
lixity scenes --chapter 2 --latest
```

The optional file defaults to the current workspace's manuscript; configure it
explicitly as described [below](#default-manuscript). Chapter numbers and
`chapter:scene` IDs are the numbers printed by Lixity, not numbers embedded in
heading titles. `--latest` means the last **measurable scene in document order**,
not the most recently edited scene. It excludes plans. `--scene` and `--latest`
are mutually exclusive; a supplied `--chapter` must agree with `--scene`.
Unknown selections fail rather than return an empty success.

Filters reduce output after the entire manuscript is validated and measured.
They preserve scene IDs, measurements and full-manuscript register references;
they do not speed up analysis or hide invalid assignments elsewhere. Filtered
JSON adds `scenes.selection` with `chapter`, `scene`, `latest`, `selected_count`,
`total_count` and `reference_scope: "full_manuscript"`. Counts refer to measured
rows; when plans are configured, `selected_planned_count` and
`total_planned_count` describe those separately. Unfiltered JSON has no selection
object and retains its existing shape.

Register assignments and targets belong to your project. For example:

```toml
[scene_analysis.assignments]
"1:1" = "close narration"
"1:2" = "close narration"
"2:1" = "report"

[scene_analysis.groups."close narration".targets]
asl = [8, 15]
filter_density = { upper = 2 }

[scene_analysis.groups.report.targets]
modal_density = { lower = 3 }
```

Save this in the project's `lixity.toml` (or under `[tool.lixity.scene_analysis]`
in `pyproject.toml`). These numbers illustrate settings, not recommended prose.
Assignments use chapter:scene numbers; review them after inserting or removing
scenes. Invalid assignments are reported instead of silently moving a register.
Since v0.7.4, the error names measured scene and recognized divider counts for
each affected chapter, or states that the chapter is absent. Review missing
standalone dividers, removed/merged scenes and configuration; blank lines alone
do not separate scenes. Explicitly planned scenes remain separate from measurements.
Each group gets its own manuscript-only median and MAD, with at least two
available observations per feature. Unassigned scenes have no register baseline.
Research sources never enter these references.

To plan an unwritten scene without disabling stale-assignment checks, explicitly
list its assigned ID:

```toml
[scene_analysis]
planned = ["3:1"]

[scene_analysis.assignments]
"1:1" = "voice"
"3:1" = "voice"

[scene_analysis.groups.voice.targets]
asl = [8, 15]
```

`planned` must be a unique list of valid assignment IDs. Missing assignments not
listed there still fail. A plan has no analyzable text, measurements or baseline
membership. CLI output labels it separately; the analysis panel has an expandable
**Planned scenes** section. Once its text is measurable, the same ID appears as an
ordinary measured scene. Review positional IDs after inserting/removing scenes.
JSON adds `planned_items` only when a nonempty `planned` list is configured; its
rows contain `id`, `chapter`, `scene`, `group` and `state: "planned"`. It becomes
empty once all listed IDs are measurable. No plans are inferred from headings,
blank lines or missing assignments. A completely empty workspace still opens its
existing setup view; the CLI can inspect its plans without inventing measurements.

Targets use the fields reported by `lixity about --json`, such as `asl`,
`filter_density`, `modal_density`, `nominalization_density`, `passive_density`,
`sentence_cv` and `start_entropy`. `feat_*` names are translated display keys,
not API functions. HD-D uses **0–1**, not 28–48; staccato is **≤6 words** and
the long-sentence share is **>25 words**. Rhythm proxies do not measure musical BPM.

The report includes actual word/sentence counts, observations, approximate core
standard errors and descriptive target positions (below/within/above). HD-D is
unavailable below 100 tokens; CV needs at least two sentences. Zero plug-in
standard errors are withheld, and HD-D has no population error estimate.
These are not validated confidence intervals or a literary-quality score.
Analyze/profile use schema 2; the style schema and its migration are described
in [automation contracts](AGENTS.md).

### `lixity canvas`

Export manuscript scenes and chapters into the open [JSON Canvas 1.0](https://jsoncanvas.org/spec/1.0/) format.
The generated `.canvas` file arranges scenes visually in chapter groups with connected narrative sequence edges, ready to open in visual canvas tools such as Obsidian Canvas:

```bash
lixity canvas manuscript.md -o storyboard.canvas
```

### `lixity motifs`

Configured motifs use the root-local `[motif_regexes]` table. The compatible
legacy `[motifs]` spelling is also accepted. Since v0.7.4, distinct names from
both tables combine consistently in chapter measurements, the live dashboard,
the motif panel in `build` dashboards, CLI and Python reports. Other optional
`build` panels retain their existing scope. Identical duplicates deduplicate;
different patterns under the same name fail explicitly. Prefer one table for a new project.
`--motif NAME=REGEX` replaces configured motifs for that invocation. In Python,
an omitted mapping inherits configuration; an explicit `{}` suppresses curated
motifs while leaving generic repetition analysis available. An empty configured
regex counts no occurrences, consistently with other empty cue patterns.

Track a curated regular-expression motif alongside frequent content words and
repeated n-grams:

```bash
lixity motifs manuscript.md --motif 'door=\bdoor\w*\b' --json
```

The report counts and locates repetition across chapters; deliberate repetition
is not an error. Function/stop words are excluded from top-word counts. See
[local repetition echoes](#local-repetition-echoes) for nearby clusters and
phrase-overlap handling.

### `lixity showing`

Compare a heuristic chapter balance against this manuscript's own baseline:

```bash
lixity showing manuscript.md
```

The word-pattern group combines perception/thought, modal, passive and noun-ending
cues per 1,000 words. The second group combines quoted-word and short-sentence
shares. The equally weighted group means yield `balance = show_z − tell_z`:
positive means the second group is higher relative to this manuscript's baseline,
negative means the first is higher. This does not classify narrative distance,
showing/telling or scene quality. Zero MAD falls back to standard deviation.

Comparison needs at least three chapters above the word-count floor. With fewer,
the app and CLI show `–`, JSON component scores and means are `null`, and raw
measurements remain available. Identical balances yield empty
`most_telling`/`most_showing` ranks. Empty ranks mean no distinguishable
ordering, not identical artistic effect.

The native **Analysis overview → Signal-group comparison** panel
shows these chapter values and links back to the manuscript. Review-workspace
website copies include that analysis; reader copies include it only
when full analysis is explicitly selected. Companion copies exclude it. Reader
copies recalculate on the capped chapters using default rules and thresholds.
Bar length shows the magnitude of the balance; its signed number gives the
direction between the two groups relative to this manuscript. For concrete wording, enable manuscript **Analysis**
and choose a component such as **Perception filters**, **Modals**, **Noun endings** or
**Passive patterns**. **Counted text** marks the exact
lexical cues independently of **Paragraph comparison**. Inspect a marked span
to read its count and counting rule.

The composite is chapter-level; it is not a word-by-word showing/telling
classification. It does not distinguish abstract adjectives from sensory verbs.
A marked perception verb is a counted filter cue, not proof of telling or a
request to remove it. Interpret the chapter contrast together with the scene's
purpose and the [heuristic limits](STABILITY.md#linguistic-proxies-and-literary-interpretation).

### `lixity style`

Compare chapter features with the manuscript's own style baseline:

```bash
lixity style manuscript.md --json
```

Inspect active thresholds in the JSON `meta` or dashboard legend rather than
assuming defaults. `lixity style --help` lists available overrides.

The reference describes sentence patterns, vocabulary and heuristic markers
against this manuscript's own baseline. Raw deviations, nominal FDR selections
and exploratory dimensions answer different questions; none establishes literary
quality or a guaranteed false-discovery rate. [Methods](METHODS.md) owns the
mathematical definitions; [Stability](STABILITY.md) describes inference limits.

Select a chapter in the style space, inspect its
values and open its passage. The view and CLI explain their coverage, axes,
cutoffs and unavailable values in place; JSON exposes `dimension_diagnostics`.

**Available in 0.8.0:** when dimension scores are available, **Start your review → Open
3D style space** opens this view directly. A dashed ring marks an axis cutoff;
a separate solid outer ring marks the selected chapter, including when both
apply. These cutoff marks include axes hidden in a flat projection and are not
the FDR selection. The blue–orange comparison scale elsewhere shows signed
deviations, not this binary cutoff. Loading bars use `+` and `−` for direction;
their lengths are relative within each axis. When fewer than three dimensions
are available, zero coordinates fill the display only; they are not measurements.

Compare scenes within their intended register and read the passages. A
deliberate change of voice can explain a deviation; the style reference does
not prescribe a writing target or decide whether to edit.

### `lixity dashboard`

```bash
lixity dashboard manuscript.md -o dashboard.html
```

The output is one self-contained HTML file with manuscript text, measurements
and offline navigation; it needs no CDN or external requests. Identical input
and settings produce identical output. The panels cover sentence rhythm,
dialogue, curated character presence, scenes, motifs, word-pattern signal groups,
chapter style, paragraph profiles and work markers as data permits. See the
[workspace manual](WORKSPACE.md) to move from measurements to passages.
A compatible server provides explicit project actions and marker saves.

### `lixity pdf`

Create a local reading copy without a browser or external converter:

```sh
lixity pdf manuscript.md --layout book --author "Example Writer" -o reading.pdf
# Since v0.7.0: an annotation copy with page and line numbers.
lixity pdf manuscript.md --layout editor -o editorial.pdf
# Since v0.7.4: neutral A4 text without generated title/header material.
lixity pdf expose.md --layout document -o expose.pdf
```

| Layout | Page | Purpose |
| :--- | :--- | :--- |
| `editor` (since v0.7.0) | A4 | Editorial reading with line numbers and room for comments |
| `document` (since v0.7.4) | A4 | Neutral text with authored headings; no added title page, headers, footers or line numbers |
| `report` | A4 | Analysis report with cover page and repeated table headers |
| `book` | A5 | Continuous reading with serif text, mirrored margins and chapter openings |
| `sheet` | A4 | Submission grid, at most 30 lines per page and 60 characters per line |

Output defaults in the selected workspace root; `-o` selects another path. Unchanged input,
settings and fonts produce identical output. The manuscript is not modified.
PDF and dashboard CLI exports reject the source path and its symbolic/hard-link
aliases, before writing and again immediately before atomic replacement.
The [native download form](WORKSPACE.md#download-a-manuscript-pdf) uses the same composer
without writing a CLI output path.

Title selection prefers an explicit override, the selected project's title,
supported manuscript title metadata/heading, then the filename. Fenced code is
not a title candidate. `--author` overrides project `author_name`; an explicitly
empty value clears the byline. PDF metadata includes title/author when present
and the resolved language. A5 has chapter bookmarks and body-page title/author
headers; title/imprint pages omit decorations but count toward physical folios.
A4 editorial, sheet and report headers and page footers sit outside the prose/grid area.
The neutral `document` layout retains the authored first title and other headings;
configured title/author overrides affect metadata only. It adds no byline,
analysis, imprint, title page or running furniture.
The optional `draft_notice` project setting (or `--draft-notice` override) adds
a running-header notice in the other four layouts; `document` omits it.
An empty override clears the notice. See
[publication settings](#publication-settings) for optional A5 imprint text.

Fonts come from the host and can be pinned per role with CLI options listed by
`lixity pdf --help`, or `LIXITY_PDF_FONT_TEXT`, `_HEADING`, `_ITALIC`, `_BOLD_ITALIC`,
`_MONO`, `_SANS` and `_SANS_BOLD`. Only used glyphs are embedded, with searchable/copyable text maps.
Missing fonts, embedding restrictions or missing glyphs fail explicitly; a
glyph error identifies its font role and Unicode codepoint. Each role requires
a single-face TrueType outline font; collections and CFF outlines are
unsupported. There is no automatic mixed-script fallback, contextual shaping
or bidirectional layout. Font coverage alone does not establish correct
rendering for every script.

Since v0.7.0, manuscript structure is preserved independently of the analysis text:
prefaces, subheadings, scene breaks, lists, quotations and notes survive export.
Inline emphasis uses font styles; note definitions retain their text. Embedded
LaTeX text formatting is a bounded subset, never executed as TeX. Unsupported
TeX constructs report an error rather than silently changing the manuscript.
Compare the same six-chapter *The Crate at Warehouse 4* manuscript as an
[A4 document](demo/warehouse-4-document.pdf),
[editorial copy](demo/warehouse-4-editor.pdf),
[reading copy](demo/warehouse-4-book.pdf),
[submission grid](demo/warehouse-4-sheet.pdf) or
[analysis report](demo/warehouse-4-report.pdf).

The composer wraps paragraphs and overlong words but does not hyphenate, place
images, typeset mathematics, create page-numbered tables of contents or alternate
recto/verso running heads. Image references remain labelled text. See
[Architecture](ARCHITECTURE.md) for the shared composition boundary.

These fixed-layout PDFs are for everyday documents, editing, analysis, reading and submission.
There is no EPUB/DOCX export, custom trim size, bleed/crop marks, print color management, printer preflight or
PDF/UA/PDF/X certification. Searchable text, metadata and bookmarks alone do
not establish accessibility or production compliance.

### `lixity export-site`

Prepare a portable website from an explicitly selected project. Check the package
first, then export to a new directory:

```bash
lixity export-site --project ./novel --preflight --json
lixity export-site --project ./novel -o review-copy
```

`--preflight` writes nothing and cannot be combined with `--output`. Ordinary
export requires `-o` and refuses existing destinations. `--json` returns the
export manifest; it does not replace the website files. The default `review`
mode contains the manuscript and analysis. Add `--include-research` only when
internal records, history and cited excerpts belong in the recipient's copy.

For a curated reading copy, save a root-local publication profile first:

```bash
lixity export-site --project ./novel -o reader-copy --mode reader \
  --publication-profile readers --max-chapter 4
```

`--mode companion` exports only the selected background. Reader/companion modes
use an explicit profile instead of `--include-research`. Optional `--analysis`
and `--include-audio` apply to reader mode only. See the workspace manual for
[format and inclusion choices](WORKSPACE.md#export-a-reading-website),
[publication profile TOML](WORKSPACE.md#curate-a-reader-publication),
[chapter audio](WORKSPACE.md#include-existing-chapter-recordings-unreleased),
[sharing limits](WORKSPACE.md#sharing-limits-and-automation) and
[preflight reports](WORKSPACE.md#check-a-reading-website-before-exporting).
Export creates local files; it does not upload or publish them.

### `lixity serve`

Run a foreground local server for a selected manuscript or project:

```bash
lixity serve ./novel --open
```

The terminal remains attached; Ctrl+C stops this instance. Use `--no-project`
for an empty workspace, or `--port 9000` for an explicitly separate instance.
The default address is `http://127.0.0.1:8765/`. An invalid explicit selector
fails before startup; a valid folder without a unique manuscript can open empty.
For the ordinary installed app, use [`service start --open`](#lixity-service).
See [server setup](INSTALLATION.md#running-the-server) for lifecycle details and
the [workspace manual](WORKSPACE.md) for browser tasks.

### `lixity service`

One regular app instance supports independent
project views in multiple tabs. Project selection returns a scoped view URL
under the same origin instead of replacing every tab's selection. In 0.8.0, use **Project → Settings → Audio and services → Services & audio queue**
to revisit open views, close an idle view or refresh worker/queue status.
The startup view stays available. At most 16 views are retained; their URLs
expire on server restart and return HTTP 410 instead of selecting another project.
Reopen the project from the home address after restarting. Additional ports are
for explicitly separate development instances, not ordinary project selection.
Launch overrides belong to the startup view; newly opened projects use their
own configuration instead of inheriting another book's analysis language or thresholds.

Audio jobs share one FIFO in that app: one render plus at most three waiting
jobs from other contexts. The dialog reports a waiting position. Cancellation
and stale-source checks apply before queued work starts; completed outputs retain
their own bounded retention window. **Ready** for a target means its expected
model answered the health probe, not merely that the tunnel port accepted TCP.
The existing external worker and SSH-forward lifecycle remains separate; status
does not install models, start a tunnel or establish that GPU acceleration works.
**Available in 0.8.0:** the worker checks cover the local and configured Jetson workers,
not external providers. The queue does not identify where an external or mixed
job runs; its processing location is shown as unknown.

Start the installed workspace without keeping a terminal open:

```sh
lixity service start --open
```

Use `status`, `restart` and `stop` to manage the owned instance. Start defaults
to an empty workspace in an application-owned directory unless a project or
`LIXITY_DIR` is specified. `start` takes fresh launch settings; `restart` reuses
saved settings with explicit overrides, even after a stop. Neither restores a
later browser project choice. An already running instance is reported without
changing its settings. Restarting into a different project clears the prior
title unless explicitly replaced; plain restart keeps the saved title.

The controller manages its own instances. Stop foreground `lixity serve` with
Ctrl+C and OS-managed startup units through their manager. A busy port never
permits terminating an unrelated listener. Backend selection is per invocation;
repeat an explicit backend on restart. `LIXITY_*` environment values, including
OCR settings, are inherited on launch and are not saved as startup settings.
Use `lixity service --help` for lifecycle arguments, or
[installation and service setup](INSTALLATION.md#running-the-server).
For foreground `lixity serve PATH`, an invalid explicit path fails before startup.
A valid directory without a unique manuscript can open an empty workspace;
`lixity serve --no-project` intentionally starts without selecting a project.

**Changed in v0.7.4:** `lixity service status --json` uses the status-specific
`lixity-service-status/1` contract: `schema_version`, `ok`, `running`, `state`,
`port`, `url`, `pid`, `backend`, `installed_version`, `running_version` and
`message`. `ok` means the inspection succeeded: known `running`, `starting`,
`stopped` and unmanaged-port `busy` states exit 0. `running` means a ready owned
instance; it is false for the other known states. An unreadable, invalid or
changing state remains `unknown`, with `ok: false`, `running: null` and exit 1.
Unavailable metadata can be null; log paths, launch settings and raw errors are
omitted. Scripts parsing the older lifecycle envelope must update explicitly.

Human `service status` keeps its existing exit codes: a ready owned instance
exits 0; stopped, starting, busy and unknown states exit 1. JSON for `start`,
`restart` and `stop` remains `lixity-service-local/1` with its existing fields and
success semantics; stopping an already stopped instance succeeds. Stop preserves
saved launch settings and logs.

Status does not create or repair storage or
acquire the lifecycle writer lock. Missing private folders are a normal stopped
state. Unsafe, unreadable or changing records report uncertainty; status does not
change runtime locations to work around a permission error. Lifecycle commands
prepare their private storage when explicitly requested.

### `lixity doctor`

Inspect the installation and owned service without opening a manuscript project:

```sh
lixity doctor
lixity doctor --json --port 9000
```

Since v0.7.4, `doctor` compares the imported CLI version, installed distribution
metadata and a running service's reported version. It reports the module and
interpreter paths, supported JSON contract versions and the shared read-only
service observation. It does not install, repair, restart, create service storage
or read manuscript/project configuration. Version agreement does not establish
that an installation matches an unreleased source checkout.
Use this optional diagnostic when investigating installation/service issues;
ordinary writes and exports use their own validation and revision/context guards.

JSON uses `lixity-doctor/1` with `ok`, `installation`, `service`, `schemas` and
`issues` (each issue has `code` and `severity`). A consistent installation with a
stopped service is healthy and exits 0; reported mismatches or unavailable
metadata/status exit 1. The port uses `--port`, then `LIXITY_PORT`, then 8765.
An out-of-range numeric port or invalid `LIXITY_PORT` returns `ok: false` and
`error: {code: "invalid-service-port", message: ...}` under the same schema, with
exit 1. A non-integer explicit `--port` is a normal argument usage error (exit 2).

### `lixity build`

Create the reproducible artifact set for a project:

```bash
lixity build manuscript.md --dry-run
```

Remove `--dry-run` to write `exports/<slug>_metrics.json` (v2), `_profile.json`
(v2), `_style.json` (v5), `_style_passport.txt` (legacy filename), `_report.md`
and `_dashboard.html`. Identical content causes zero writes. Changed artifacts
get unique timestamped versions and atomically replace stable links or fallback
copies; the last 10 versions per artifact family remain in `exports/archive/`.
A failed replacement preserves the previous stable artifact and reports an error.

An explicit manuscript path wins. Otherwise discovery uses the selected root's
[configured manuscript](#default-manuscript), then tries `<folder>.md`,
then `manuscript.md`/`manuskript.md`, then a sole Markdown file (ignoring
README/AGENTS/LICENSE/NDA). `--dry-run` displays the plan without writing.

### `lixity about` and `lixity completion`

`lixity about --json` describes installed capabilities and thresholds;
`lixity schema` is its JSON metadata alias. Plain `about` gives a terminal summary.
**Since v0.6.0:** `--section languages|features|heuristics|commands|configuration`
returns one section plus version metadata as JSON. See [configuration discovery](#configuration-corpusconfig)
for scope and older-release alternatives. For Bash/Zsh setup, follow
[shell completion](INSTALLATION.md#optional-shell-completion).

<a id="research-search-scopes-since-v1190"></a>
<a id="research-search-scopes"></a>
<a id="claim-chronology-causal-interpretations-and-keyword-citations-since-v300"></a>
<a id="claim-chronology-causal-interpretations-and-keyword-citations"></a>
<a id="zotero-integration-since-v1190"></a>
<a id="zotero-integration"></a>
<a id="research-batch-workflow-and-index-ergonomics-since-v1200"></a>
<a id="research-workflows-and-index-ergonomics"></a>

### `lixity research`

Research is a separate, explicit-project workspace. Its
[usage guide](research/USAGE.md) owns retained source capture, authored records,
lexical search, chronology, citations, Zotero, OCR, backups and archive versions.
Use `lixity research COMMAND --help` for installed arguments/formats and `GET /api`
for a running server's operations. Confirm permission to retain source bytes
before ingesting. Retrieved passages are evidence to review, not accepted claims.

Useful entrypoints: [source/current-record search](research/USAGE.md#search-current-authored-records),
[chronology and causal interpretations](research/USAGE.md#claim-chronology-and-causeeffect-links),
[keyword citations](research/USAGE.md#choose-citations-by-keywords),
[Zotero capture and recovery](research/USAGE.md#zotero-desktop-bridge),
[author revisions and acknowledgements](research/USAGE.md#research-workflows).
Use the same supported application version for every archive writer; product
release numbers, archive versions and response schemas are independent.

<a id="worked-example-a-sequel-in-the-authors-style"></a>
## Literary case study

The [Fontane case study](blog/effi-briest-case-study.html) explores a reference
built from a public-domain novel. Its linked excerpt and complete-book report
have different chapter sets and can have different baselines. These are named
case-study artifacts; the [Warehouse 4 project](demo/report.html) is the product
walkthrough. Matching any reference distribution does not establish literary quality.

## Work markers (editor-visible)

See [Work markers](WORKSPACE.md#work-markers-editor-visible) for the explicit
manuscript-write workflow and [automation contracts](AGENTS.md) for marker APIs.

## Understanding the metrics

Compare scenes or narrative voices using comparable language, passage length,
chapter boundaries and discourse mode. Inspect the prose alongside the values:
a dialogue scene and an expository scene may deliberately differ. Neither
short sentences nor low perception-filter counts establish effective pacing,
immersion or a writing defect. There is no automatic narrator-voice assessment.

| Metric | Definition | Interpretation limits |
| :--- | :--- | :--- |
| **ASL** | average sentence length in words | describes length, not syntactic complexity or dramatic pace by itself |
| **Median / σ** | middle sentence length and spread | a low median with high σ means short base plus bursts |
| **TTR** | type-token ratio V/N | sensitive to length, topic and tokenization; no universal novel target |
| **Guiraud R** | V / √N | remains length-dependent; compare with sampling and corpus context |
| **Yule's K** | vocabulary repetition measure | repetition does not establish a stable narrator or a quality verdict |
| **ASW** | average syllables per word | a language-dependent heuristic input to readability formulas |
| **MTLD** | mean segment length until TTR ≤ 0.72 (forward/backward averaged) | larger values mean longer diverse segments; requires ≥ 100 tokens |
| **MATTR** | moving-average TTR over a 50-token window | describes local repetition; compare the same window and tokenization |
| **Maas a²** | (log₁₀ N − log₁₀ V) / (log₁₀ N)² | requires ≥ 100 tokens; lower means more types at the same N, not better prose |
| **Flesch** | language-calibrated Flesch family (Amstad for German) | formula output is not clipped to 0–100; not reader comprehension |
| **LIX** | ASL + share of long words (Björnsson: more than six characters, all languages) | a surface-structure estimate, not a universal difficulty or quality threshold |
| **Quoted words** | share of configured word tokens inside detected quotations | quotation and token regexes affect counts; neither speaker attribution nor dialogue classification |
| **Function words** | share of articles, pronouns, prepositions, conjunctions, particles, auxiliaries, modals | language-profile counts describe grammatical patterns, not artistic value |
| **Perception filters** | curated word-pattern matches (e.g. German "hörte", "roch", "fühlte") | lexical cues include environmental descriptions and idioms; they do not classify narrator mediation or narrative distance |
| **Sentence classes** | staccato ≤ 6, medium 7–15, long 16–25, very long > 25 words | length bins; the legacy `complex_*` keys do not establish syntactic nesting |
| **Tense severity** | 0 = neutral, 1 = watch, 2 = conspicuous, 3 = strong friction | flags switches and mixtures for review |

The 100-token minimum is a local short-text policy, not a reliability guarantee.
Maas is valid for a one-type text: 100 repetitions produce `maas_a2=0.5`.

Percentages use counts over their stated text scope. Chapter profile quotation
and function-word shares aggregate integer hits and tokens before rounding; they
are not averages of rounded paragraph rates. The manuscript function-word KPI
uses the corpus count, including text outside narrower paragraph-profile coverage.
Older result payloads without that corpus measurement show it as unavailable.
Unavailable estimates are `null` in JSON and shown as `–` in the dashboard;
legacy zero values on empty input must not be interpreted as measured quality.

Use actual JSON fields when automating: corpus metrics have `asl`,
`dialog_ratio`, `filter_density` and `nominalization_density`; chapter metrics
use `asl`, `dialog_pct`, `filter_density` and `nominalization_density`.
The style passport stores these feature identifiers in `features[].feature`
and its deviation/FDR entries. Display keys such as `feat_asl` and `feat_dialog`
belong to localized labels, not callable API functions or result fields.

<a id="unavailable-consistency-and-empty-manuscripts-since-v1180"></a>

### Unavailable consistency and empty manuscripts

Dashboard/text reports show `–` without measurable chapter–feature cells.
Empty chapters contribute no measurements; one chapter or fewer than configured
`min_chapters` is insufficient for a baseline. Style JSON reports
`measured_cells`: when zero, legacy `consistency: 1.0` is an unavailable sentinel,
not 100%. Otherwise consistency counts cells with `abs(z*) < z_mild`, not whole
chapters. See [interpretation](guides/interpretation.html) for short-text limits.

## Manuscript format & how to operate lixity

**Format (Markdown, UTF-8):**

- **Chapters** are level-2 headings: `## Title`. Everything before the first
  `##` is front matter and is not analysed when chapter headings exist. Without
  chapter headings, all prose is measured as one chapter. The boundary regex is
  configurable (`CorpusConfig.chapter_regex`).
- **Appendix** starts at `## Anmerkungen und Literaturverzeichnis`
  (`CorpusConfig.appendix_marker`); it is excluded from prose metrics.
- **Paragraphs** are separated by blank lines. Hard line breaks inside a
  paragraph are joined automatically – no manual reformatting needed.
- **Dialogue** in typographic quotes (`»…«`, `„…“`, `“…”`) feeds the dialogue
  ratio.
- **Work markers** are invisible HTML comments
  (`<!-- LIXITY-MARKER id="…" kind="…" note="…" -->`) placed directly above the
  paragraph. HTML dashboards include their notes; prose/PDF text omits the
  comments. They move with the paragraph when editing. Other HTML comments are
  ignored by the analysis.
- Explicit project title/metadata can supply the title; filenames remain the
  artifact naming basis.

For review, use [chapter measurements](WORKSPACE.md#style-area) or a paragraph's measurement
explanation, then read the passage against its intended purpose. A highlighted
value is not an editing instruction.

Line anchors in reports and dashboards refer to lines in the source file, so
findings stay navigable in the editor.
Shared counting excludes inline code, images and
Markdown link destinations while retaining visible link labels. This measurement
projection does not change displayed paragraph text, saved quote identities or
chapter numbering; a chapter without countable prose still retains its number.

## Known limitations & stability

[Methods](METHODS.md) documents estimator conventions;
[Stability](STABILITY.md) records evidence and inference limits.

- Minimum sizes (HD-D/MTLD/Maas ≥100 tokens; MATTR ≥50) are availability
  floors, not reliability guarantees. Short inputs can yield unstable values.
- Syllable, suffix and tense patterns are language-specific heuristics without
  established gold-standard error rates here; cross-language comparisons need
  separate justification. Curated filter-verb counts differ from broader
  editorial definitions.
- `signal_counts` is empty unless project `signal_keywords` supplies thematic
  patterns. Vocabulary/JSD contrasts are in-corpus diagnostics, without external
  Delta authorship attribution or automatic narrator-voice assessment.
- Research source analysis is `source_internal`; explicit source–manuscript
  comparisons remain separate. Retained sources never become the manuscript's
  baseline automatically. Period/place/genre labels are unverified context.
- Determinism is byte-identical on the same interpreter; Python versions may
  differ in the final floating-point bits. Offline dashboard size grows with
  embedded text/data even though paragraphs are rendered on demand.
- Numeric details and keyboard/touch controls complement color scales, but
  pointer-operated canvas points and automated checks do not establish full
  accessibility conformance.

<a id="ai-agent-interface"></a>

## Library

### High-Level API Facade (`lixity.api`)

Use the deterministic facade for scripting. This example selects English and
explicit code defaults instead of discovering unrelated project configuration:

```python
from pathlib import Path
from lixity import api

text = Path("manuscript.md").read_text(encoding="utf-8")
metrics = api.analyze(text, language="en")["metrics"]
reference = api.fingerprint(text, language="en", project_config={})
html = api.dashboard(text, language="en", title="Example", project_config={})
Path("dashboard.html").write_text(html, encoding="utf-8")
```

Each convenience call analyzes independently. To reuse one analysis across
several outputs or integrate multiple projects, use the
[shared pipeline and configuration guidance](ARCHITECTURE.md#configuration-and-multiple-projects).
[Automation contracts](AGENTS.md) describe facade inputs, envelopes and marker
operations; `api.about()` returns runtime capability metadata.

### Low-Level Classes

Use `CorpusAnalyzer`, `CorpusConfig`, `ParagraphProfiler` and renderers for direct
object-model control; the [architecture reference](ARCHITECTURE.md) explains
these boundaries. Low-level structure reports also default to English when no
configuration is supplied. Automatic language detection is explicit and needs a text sample:
`resolve_language(CorpusConfig(language="auto"), sample_text=text)`.
Without a sample, `auto` resolves to `generic`; the CLI supplies its manuscript
automatically. `FileUtils.atomic_write_if_changed(path, text)` provides atomic,
idempotent output writes.

## Configuration (`CorpusConfig`)

Legacy CLI commands with an explicit manuscript path load settings relative to
that manuscript; otherwise workspace discovery starts in the current directory.
The `--project` and configured-omission modes added in v0.7.3 instead use strict
settings from the selected root; see [default manuscript](#default-manuscript).
Project settings live in `lixity.toml` or `[tool.lixity]` in `pyproject.toml`.
An explicit CLI option overrides its project value. Configured title affects
dashboard/build presentation; artifact names still follow the manuscript name.

Use `--min-chapters` on style/dashboard/build or server startup, or
`api.fingerprint(..., min_chapters=4)`, to require more usable chapters before a
style baseline is available. The minimum is 2; fewer usable chapters mean
unavailable evidence, not a perfectly consistent style.

For API project isolation, pass `project_config={}` to `profile`, `fingerprint`,
`passport` or `dashboard` to avoid implicit threshold lookup. A supplied mapping
provides thresholds and known `CorpusConfig` fields; explicit options win.
Language and title remain explicit API arguments. See
[configuration precedence](ARCHITECTURE.md#configuration-and-multiple-projects).

In the native workspace, **Apply** persists title, `author_name`, publication
and chapter register settings in the selected project's `lixity.toml`; language
and detection thresholds keep session behavior by default. Author/publication identity
comes only from the explicit selected root, excluding user/ancestor defaults.
Empty author clears it. Failed validation or saves keep previous metadata and
the active view; failed submissions retain the draft. Reload after a project or
root-config change instead of submitting stale values. An optimistic conflict
guard rejects observed concurrent changes; it is not an external-editor lock.

**Since v0.6.0:** check **Save analysis defaults for this project**
before **Apply** to persist the posted language and detection thresholds in that
project's `lixity.toml`. It starts unchecked and requires the current selected
project context. Unposted settings stay unchanged; `auto` remains an explicit
saved choice. The same transaction saves metadata and defaults together or neither.

The identity check compares configured title/author with explicit manuscript
metadata: flat leading YAML strings or a leading Markdown title page with
`by`, `von`, `Author:` or `Autor:`. It normalizes Unicode/whitespace and reports
missing, unsupported and unavailable evidence separately from a mismatch. A
missing manuscript value means it was not automatically detected in these
formats, not that the project setting is empty. The optional comparison does
not infer authorship or edit the manuscript. A display byline does not
identify a publisher or printer.

An existing unreadable/malformed config emits a warning naming the file and
ignores those settings. This includes non-table `tool`/`tool.lixity` sections in
`pyproject.toml` and failed permission/I/O checks while locating a config. Missing
files and paths that cannot exist beneath a file are silent. Check `meta.language`
and active thresholds after a warning, or supply explicit options. Invalid stored
publication fields remain visible for correction while analysis stays available.

**Since v0.6.0:** discover configuration keys, defaults and
constraints with:

```bash
lixity schema --section configuration
```

The `configuration` object (`lixity-configuration/1`) reports accepted keys,
project-only keys, uninterpreted keys, native-settings persistence/session scope,
and component schemas for corpus, threshold and publication settings. v0.7.1
also exposes the owning character-profile schema. Defaults
are annotations, not active project/server values. Scene and NDA settings retain
their owning component's validation; this is not a
single complete project-file schema. Threshold comments also state finite-number
requirements and `z_mild <= z_strong`, validated by the backend.

Older releases provide `lixity about --json` and `lixity COMMAND --help`; Python
callers can inspect `CorpusConfig.model_json_schema()` for corpus fields. Optional
`None` linguistic patterns use the selected language profile's defaults.
`phrases` and `capabilities` are accepted but uninterpreted by the bundled engine.
Configured cue regular expressions and signal/motif maps are syntax-checked before
analysis. A malformed pattern produces a configuration error; it does not silently
fall back to a language default or replace an existing output with a partial result.
Valid capturing groups and scoped flags retain their normal matching semantics.

### Default manuscript

In the selected project's root `lixity.toml`, set an optional relative path:

```toml
manuscript = "drafts/manuscript.md"
```

The equivalent is `manuscript` under `[tool.lixity]` in the root
`pyproject.toml`; root `lixity.toml` takes precedence. This is project data, never
inherited from user settings or an ancestor directory. Paths are relative to the
selected root, may contain spaces and must remain inside it, including symlinks.
Absolute paths and parent traversal are rejected. An explicit manuscript argument
wins. When selecting a configured default, an invalid/unreadable configuration
or missing/nonregular configured file fails selection instead of choosing another
manuscript. Explicit-file analysis retains its existing configuration warnings.

The published v0.7.2 release uses this setting for folder selection (Open
Project, service startup and `build`), omitted `scenes` input and read-only
Research manuscript review. Text-taking Python APIs do not discover files.

All manuscript analysis/export commands accept
`--project PATH`: `analyze`, `profile`, `dialogue`, `pacing`, `showing`, `style`,
`motifs`, `characters`, `dashboard`, `pdf`, `scenes` and `build`. With no file,
these commands use the selected root's configured manuscript. Only `scenes` and
`build` retain their existing conventional-file discovery when no default is set.

```bash
lixity analyze --project ./novel
lixity scenes --project ./novel --latest
lixity research review-manuscript --project ./novel
```

New explicit-project/configured-omission analysis reads settings only from that
root, excluding user and ancestor defaults. Language, title and registers belong
to the same root even when its manuscript is nested. Explicit CLI options win.
With `--project`, relative files belong to that root and absolute files must
also remain inside it. Without this option, an explicit file retains legacy
path/configuration behavior. Conventional discovery by `scenes`/`build` without
`--project` also retains its existing settings merge. Commands do not select
another running server's project. Project build exports and default PDF output belong to the
selected workspace root.

Research `review-manuscript`, `find-anchor`, `link-manuscript`,
`unlink-manuscript`, `reconcile-manuscript` and `compare` can reuse the validated
Research project's root-local default. They do not guess from other Markdown
files. Existing positional/option forms, acceptance, retention and snapshot
requirements remain. Read-only review retains informative `missing`/`unreadable`
source states. See the [research reference](research/USAGE.md).

### Character profiles

Define literal aliases and optional author-declared
viewpoint chapters in the selected project's configuration:

```toml
[characters.Alex]
aliases = ["Alexander", "A. Rivers"]
pov_in_chapters = [1, 3]
```

The profile name is also matched. Aliases are literal text, unlike legacy `names`
and explicit `--name` regular-expression patterns. Explicit name selections win;
an existing `characters` table, even empty, replaces legacy `names`. Profiles come
only from the explicit project root, not user/ancestor defaults. The CLI and
dashboard share this resolver; Python accepts explicit `project_config`.

Declared viewpoint appears separately as `declared_pov_chapters`; it does not
increase mention counts or fill mention gaps. Chapter numbers must exist in the
current manuscript. No pronoun resolution, narrator inference or named-entity
recognition is performed. Use configuration discovery for accepted fields and bounds.

For an existing adapter that keeps its own figure list, move the reviewed names
into `[characters]` profiles, then omit explicit `--name`/`--names` selections
when calling `lixity characters --project ./novel`. Pass the same root-local
settings as `project_config` to Python APIs; an explicit adapter name list still
overrides the profiles. Review literal aliases rather than mechanically copying
regex syntax, and never use a pronoun such as `I` as an alias for a viewpoint.
Verify the resulting mentions and declared POV separately. This does not edit
the manuscript or infer character presence.

### Chapter register settings

In the native workspace, **Project → Settings → Chapter registers** edits named
registers, optional feature bounds and chapter assignments. Since v0.7.4,
feature choices and target rows show the shared units, including per-1,000-word
densities and HD-D's 0–1 scale. The register comparison table links directly
to chapter headings in the manuscript reader (`#ch-N`).

Authors and editors can insert curated starter register templates with one click:
- **Dialogue scene (`dialogue_scene`)**: quoted text 45–85%, ASL 8–16, staccato share 20–55%.
- **Action scene (`action_scene`)**: ASL 7–14, staccato share 25–60%, passive density ≤ 4 / 1,000 words.
- **Reflective narration (`reflective_narration`)**: ASL 16–28, quoted text ≤ 25%, HD-D 0.82–0.95.
- **Epistolary (`epistolary`)**: ASL 16–32, first-person starts 8–35%.
- **Technical / institutional record (`technical_record`)**: ASL 14–28, passive density 5–18 / 1,000 words, nominal style 15–45 / 1,000 words.

#### Editorial threshold presets

Under **Project → Settings → Detection thresholds**, choose from four pre-calibrated editorial profiles or keep individual custom values:
- **Balanced review (`balanced`, default)**: `|z*| ≥ 2.5`, `z_strong = 3.5`, Benjamini–Hochberg `q = 0.05`, paragraph severity floor ≥ 2.
- **Developmental editing (`developmental`)**: `|z*| ≥ 3.0`, `z_strong = 4.0`, `q = 0.02`, severity floor 3 (focuses on macro-structural chapter shifts and severe tense friction).
- **Line editing (`line_editing`)**: `|z*| ≥ 2.0`, `z_strong = 3.0`, `q = 0.10`, severity floor ≥ 1 (fine pass surfacing subtle chapter deviations and all paragraph tense notes).
- **Conservative multiplicity (`conservative_by`)**: `|z*| ≥ 2.5`, Benjamini–Yekutieli FDR under arbitrary dependence (`fdr_method = "by"`).

In the CLI, select presets via `--preset {balanced,developmental,line_editing,conservative_by}` across `analyze`, `profile`, `style`, `dashboard`, `pdf`, and `build`. Explicit CLI flags (such as `--z-mild`) override preset values.

#### Configurable structural thresholds (`[tool.lixity]` / `lixity.toml`)

To eliminate hardcoded assumptions during genre-specific fine-tuning, the following thresholds can be configured in root `lixity.toml` or `pyproject.toml`:
- `short_sentence_max` (default `6`): upper word limit for staccato sentences.
- `medium_sentence_max` (default `15`): upper word limit for medium sentences.
- `long_sentence_max` (default `25`): threshold above which sentences count as long/complex.
- `short_turn_max_words` (default `12`): upper word limit for rapid dialogue turns.
- `long_turn_min_words` (default `80`): lower word limit for extended monologue turns.
- `dialogue_paragraph_share` (default `0.5`): share of quoted words to classify a paragraph as dialogue.
- `hook_short_sentence` (default `8`): word limit for punchy chapter-closing sentences.
- `monotony_min_run` (default `3`): minimum consecutive sentences with identical start token.
rebuilds and saves both tables together in the selected project's `lixity.toml`.
It requires the current project token and preserves newer browser drafts during
pending saves. Resetting detection thresholds does not reset registers.

```toml
[register_profiles.formal]
asl = [15, 35]
passive_density = { lower = 5 }

[chapter_registers]
"2" = "formal"
```

A range may be `[lower, upper]`, a scalar exact target, or a table with `lower`
and/or `upper`. Omit one table bound for an open interval (TOML has no `null`).
Empty profiles label intentional registers without targets. Names must be
nonempty single-line text of at most 100 characters; unknown profiles/features, invalid bounds
and unmatched chapter selectors fail explicitly. Numeric selectors match exactly
one chapter. Otherwise full titles take precedence, then the longest matching
partial title, with lexical order breaking equal-length ties. Number assignments
take precedence over title assignments.

The report lists each target's measured value and `below`, `within`, `above` or
`unavailable` position. The usual chapter measurement floors still apply.
Register assignment expresses author intent; it is not evidence of a stylistic
or factual defect. Scene registers remain separately configured through the
existing `scene_analysis` settings.

### Local repetition echoes

Since v0.7.4, human `lixity motifs FILE` output and the analysis overview also
show **Local phrase echoes**, including local count, chapter and inclusive
chapter-prose word bounds. These remain separate from whole-book repeated phrase
counts. The overview links to the chapter, not an invented exact line anchor.

`lixity motifs FILE --json` and `api.motifs` add `echoes` alongside repeated
phrases and content-word counts. Each echo contains `term`, `chapter`, `count`,
`first_word` and `last_word`. The detector retains the densest local cluster per
term/chapter (earliest tie); its default span is 300 words and its default minimum
is two occurrences. Word offsets are 1-based chapter-prose token positions,
including the final token of the last occurrence. Shifted n-grams are deduplicated
when their recorded occurrences overlap by at least two tokens in the same
repeated passage; independent phrases sharing words remain separate.

These are lexical review hints: punctuation is discarded during tokenization,
and deliberate repetition is not an error. `echo_window`, `echo_min_count` and
`top_echoes` are keyword arguments of `lixity.motifs.motif_report`; they are not
CLI flags or project configuration keys.

### Publication settings

In the native workspace, open **Project → Settings → A5 book PDF details**. The
disclosure is collapsed initially and disabled without an explicit project.
The inclusion checkbox controls the A5 `book` layout; sheets and analysis
reports omit the imprint. All text fields are optional and empty by default.
Only entered nonempty text is emitted: an enabled, entirely empty configuration
adds no blank imprint page. A single imprint section starts after the title
page; long addresses or credits can flow onto additional pages.

The same fields can be entered in the selected root's `lixity.toml`:

```toml
title = "Example manuscript"
author_name = "Example Writer"

[publication]
enabled = true
publisher_name = "Example Press"
publisher_address = "Example Street 1\nExample Town"
```

These example identities are synthetic. Enter confirmed information for your
own project; Lixity does not derive it from prose, a pen name or a project path.

**Since v0.6.0:** `configuration.publication_schema` in the
[installed configuration metadata](#configuration-corpusconfig) supplies keys,
defaults, text bounds and validation notes from the shared model/field registry.
Its extension annotations describe checks beyond ordinary JSON Schema.

Validation does not verify assigned ISBNs, addresses, rights ownership or legal
completeness. No copyright statement or Deutsche Nationalbibliothek catalog claim
is generated automatically.

#### Germany: print and digital publication

For printed works, imprint requirements depend on the applicable Bundesland.
For example, Bavaria and North Rhine-Westphalia require printer and publisher
names or registered business names and addresses; self-publishing identifies
the author or editor in the publisher role. Enter that identity explicitly,
independently of a display pen name. See [BayPrG Article 7](https://www.gesetze-bayern.de/Content/Document/BayPrG-7)
and [NRW Landespressegesetz § 8](https://recht.nrw.de/lrgv/gesetz/18052021-pressegesetz-fuer-das-land-nordrhein-westfalen-landespressegesetz-nrw/).

Digital provider/website duties are separate from a printed-book imprint.
[MStV § 18](https://www.gesetze-bayern.de/Content/Document/MStV-18) requires
provider name/address information for telemedia beyond purely personal or family
purposes. [DDG § 5](https://www.gesetze-im-internet.de/ddg/__5.html) adds contact
and applicable business disclosures for businesslike digital services normally
offered for payment. Check the actual provider and distribution channel; these
rules do not mean every ebook must contain every website-imprint field. Lixity's
entered publication data does not validate or publish a website imprint.

An ISBN is voluntary. When ISBNs are used, separately available formats such as
print, PDF and EPUB use distinct identifiers; a single digital field describes
only the selected digital edition. See the [German ISBN agency FAQ](https://german-isbn.de/faq/faq-isbn).
Copyright protection generally arises without registration or a notice; an
optional entered rights notice does not establish ownership. See [WIPO's copyright FAQ](https://www.wipo.int/en/web/copyright/faq-copyright).
Legal deposit of print and digital publications is a separate process; saving
metadata or generating a PDF performs no deposit. See [DNBG § 14](https://www.gesetze-im-internet.de/dnbg/__14.html).

The BFSG covers consumer e-book services provided after 28 June 2025. Scope and
exceptions matter, including the microenterprise exemption for services under
§ 3(3). See [BFSG § 1](https://www.gesetze-im-internet.de/bfsg/__1.html)
and [§ 3](https://www.gesetze-im-internet.de/bfsg/__3.html).
Lixity exports A4 document/editorial/sheet/report and A5 book PDFs. These
fixed layouts do not include EPUB, DOCX, custom trim sizes or certified PDF/UA/PDF/X files;
an imprint, searchable text or bookmarks do not establish BFSG compliance.

### Project NDA configuration (`[nda]`)

The [five-field generator](#nda-agreements) works without configuring a store.
Optional project settings select a document language or text model:

```toml
[nda]
# language = "de"                    # optional explicit language override
# template = "agreements/nda.txt"     # optional project-owned UTF-8 model
```

`language` takes precedence over the resolved server/project language, then
project configuration and English. Supported codes are `en`, `de`, `fr`, `es`,
`it`, `pt` and `nl`. `template` must be nonempty UTF-8 text inside the project,
at most 2 MiB; paths and symlinks escaping the project are rejected.

The literal placeholders are `{{recipient_name}}`, `{{recipient_address}}`,
`{{project_title}}`, `{{date}}`, `{{place}}` and optional `{{project_author}}`.
The project author comes from the project-wide `author_name` setting. Existing
five-field models remain supported. Unknown fields are rejected;
supplied values remain literal data. Generation and downloads are described
[below](#nda-agreements).

## NDA agreements

Under **Project**, enter the recipient's name, optional **Address**, **Project
name**, **Date** and **Place**. A real loaded project name can be prefilled;
an empty workspace leaves it blank. The date defaults to the browser's local
calendar day. Choose **Preview** to read the full friendly agreement, then
**Download PDF** or **Download text**. The address may span several lines.
The output is titled **Confidentiality agreement**. It offers the recipient a
signature line or a clear consent in text form, for example a reply to the email
that delivered the document; the sending project representative needs no separate
handwritten signature on this sent copy. Review the details together before
consenting; generating or downloading a file records no consent and no signature.
The representative's name is filled from **Author name** in project Settings.
The five NDA input fields remain unchanged. Without a configured author, the
download keeps a blank name line for manual completion.

The native generator uses the resolved project language or the optional
`nda.language` override. Seven localized text models are available. Preview
shows text literally, and the browser downloads a paginated PDF or editable
UTF-8 text. The request returns the document directly; generation creates no
server files or recipient registry. Details remain in the current form for a
retry and are not saved across reloads. JavaScript and a compatible live server
are required for the form; standalone analysis HTML has no NDA controls.

Native PDF text is limited to Windows-1252 Western Latin characters. If a name
or other value requires a broader repertoire, download UTF-8 text and render it
with your local document editor. Keep reviewed and signed copies in your own
project storage. Language selection does not choose a law or jurisdiction.

The wording is editable to fit the project. Language selection and filled fields
do not establish universal enforceability.
For trade-secret rules and disclosure exceptions, see
[§5 GeschGehG](https://www.gesetze-im-internet.de/geschgehg/__5.html) and
[Directive (EU) 2016/943](https://eur-lex.europa.eu/eli/dir/2016/943/oj/eng).
[WIPO's trade-secret overview](https://www.wipo.int/en/web/trade-secrets) provides
broader background. These references do not validate a particular agreement.

## Troubleshooting

| Symptom | Check and next action |
| :--- | :--- |
| `lixity: command not found` | Follow [PATH setup](INSTALLATION.md#cli-current-release). For a checkout, use `.venv/bin/lixity`; for a tool install, confirm `uv tool list`, run `uv tool update-shell` and open a new terminal. |
| `No such file` or no selected manuscript | Check the current directory and quote paths with spaces. Run `lixity project --project PATH`; configure the root-local [default manuscript](#default-manuscript) or pass the file explicitly. |
| Configuration warning or unexpected language | Read the named configuration file and check `meta.language` and active thresholds. `--language en` is explicit; `auto` must be requested. Strict project selection can fail where legacy explicit-file mode warns; see [configuration](#configuration-corpusconfig). |
| All paragraphs are neutral or no tense flags appear | Confirm the analysis language and inspect `profile` evidence. Short text and incomplete heuristic patterns can have no recognized cues; neutral does not establish grammatical consistency. An optional [grammatical model](#grammatical-tense) must be installed and selected explicitly. |
| Appendix or front matter affects measurements unexpectedly | Check chapter headings, `chapter_regex` and `appendix_marker` against the [manuscript format](#manuscript-format--how-to-operate-lixity). |
| Style values show `–` or a layer has no notable rows | Inspect the stated sample size and MAD requirements. Unavailable comparisons differ from measured zero; see [empty and short manuscripts](#unavailable-consistency-and-empty-manuscripts). |
| Saved HTML does not reflect an edit | Re-run `dashboard` or `build` and open the exact output path. Static files are snapshots; live app recovery is described under [source availability](WORKSPACE.md#source-availability-and-saved-analysis). |
| The installed CLI and open app behave differently | Run `lixity doctor` and `lixity service status`. Package installation does not update an already running process; follow [updates and removal](INSTALLATION.md#updates-and-removal). |
| Website export refuses a destination or exceeds a limit | Choose a new output directory. Run [preflight](WORKSPACE.md#check-a-reading-website-before-exporting) and narrow the included publication scope when a disclosed budget is exceeded. |
| Audio or research action is unavailable | Use [audio troubleshooting](AUDIO.md#troubleshooting-and-limits) or [research prerequisites](research/USAGE.md). A static export cannot save local project changes. |

<a id="debug-logging-since-v1190"></a>

### Debug logging

Start with `lixity serve /absolute/path/to/project --debug` or `LIXITY_DEBUG=1`
(`true`/`yes` also work). This enables backend request logging and a browser
debug default. Browser-console `setLixityDebug(true)`/`false` saves an explicit
choice across reloads when local storage works; remove `lixity_debug` to restore
the server/window default. With blocked storage, the choice lasts for the page.
It does not change backend logging; restart with the intended server setting.

Warnings/errors still log. API diagnostics show method, URL, status and duration
without copying response bodies. Backend debug lines carry UTC timestamps;
browser diagnostics do not. Logs may contain source text or paths, so review
before sharing.

## Dashboard workflow

The [browser workspace manual](WORKSPACE.md) owns reading, review, project controls
and sharing. These topic links preserve earlier bookmarks.

### A connected first session

See [A connected first session](WORKSPACE.md#a-connected-first-session).

### Inspect project structure

See [Inspect project structure](WORKSPACE.md#inspect-project-structure).

<a id="download-a-manuscript-pdf-since-v240"></a>

### Download a manuscript PDF

See [Download a manuscript PDF](WORKSPACE.md#download-a-manuscript-pdf).

### Export a reading website

See [Export a reading website](WORKSPACE.md#export-a-reading-website).

<a id="include-existing-chapter-recordings-unreleased"></a>

#### Include existing chapter recordings

See [Include existing chapter recordings](WORKSPACE.md#include-existing-chapter-recordings-unreleased).

#### Curate a reader publication

See [Curate a reader publication](WORKSPACE.md#curate-a-reader-publication).

#### Sharing limits and automation

See [Sharing limits and automation](WORKSPACE.md#sharing-limits-and-automation).

#### Check a reading website before exporting

See [Check a reading website before exporting](WORKSPACE.md#check-a-reading-website-before-exporting).

<a id="start-a-review-since-v230"></a>

### Start a review

See [Start a review](WORKSPACE.md#start-a-review).

<a id="read-a-dossier-beside-the-manuscript-since-v240"></a>

### Read a dossier beside the manuscript

See [Read a dossier beside the manuscript](WORKSPACE.md#read-a-dossier-beside-the-manuscript).

<a id="link-a-manuscript-quote-to-a-claim-v030"></a>

### Link a manuscript quote to a claim

See [Link a manuscript quote to a claim](WORKSPACE.md#link-a-manuscript-quote-to-a-claim).

<a id="reading-paragraphs-since-v230"></a>

### Reading paragraphs

See [Reading paragraphs](WORKSPACE.md#reading-paragraphs).

### Searching the manuscript

See [Searching the manuscript](WORKSPACE.md#searching-the-manuscript).

### Source availability and saved analysis

See [Source availability and saved analysis](WORKSPACE.md#source-availability-and-saved-analysis).

<a id="style-area-since-v230"></a>

### Style area

See [Style area](WORKSPACE.md#style-area).

### Settings and interpretation

See [Settings and interpretation](WORKSPACE.md#settings-and-interpretation).

### Style-space navigation

See [Style-space navigation](WORKSPACE.md#style-space-navigation).

## Audio commands and workflows

The [audio manual](AUDIO.md) owns recording, voice profiles, direction, synthesis,
playback and audio verification. Setup remains in [Installation](INSTALLATION.md).

<a id="audio-export-and-external-providers-unreleased"></a>

### Audio export and external providers

See [Audio export and external providers](AUDIO.md#audio-export-and-external-providers-unreleased).

<a id="inspect-and-compare-externally-generated-audio-unreleased"></a>

### Inspect and compare externally generated audio

See [Inspect and compare externally generated audio](AUDIO.md#inspect-and-compare-externally-generated-audio-unreleased).

### Audio status

See [Audio status](AUDIO.md#audio-status).

### `lixity read-aloud`

See [lixity read-aloud](AUDIO.md#lixity-read-aloud).

<a id="author-voice-recording-and-listening"></a>

See [Author voice recording and listening](AUDIO.md#author-voice-recording-and-listening).

### Experimental Qwen VoiceDesign

See [Experimental Qwen VoiceDesign](AUDIO.md#experimental-qwen-voicedesign).

<a id="experimental-coqui-and-openvoice-audio-unreleased"></a>

### Experimental Coqui and OpenVoice audio

See [Experimental Coqui and OpenVoice audio](AUDIO.md#experimental-coqui-and-openvoice-audio-unreleased).

### Experimental reference voices

See [Experimental reference voices](AUDIO.md#experimental-reference-voices).

### Microphone settings and calibration (`audio-microphone`, `audio-calibrate`, `audio-reference record`)

See [Microphone settings and calibration (audio-microphone, audio-calibrate, audio-reference record)](AUDIO.md#microphone-settings-and-calibration-audio-microphone-audio-calibrate-audio-reference-record).

### Manuscript Teleprompter: Direction cues, phonetics, and synchronized dossier images

See [Manuscript Teleprompter: Direction cues, phonetics, and synchronized dossier images](AUDIO.md#manuscript-teleprompter-direction-cues-phonetics-and-synchronized-dossier-images).

### Audio and video playback

See [Audio and video playback](AUDIO.md#audio-and-video-playback).

<a id="retained-f5-tts-profiles-unreleased"></a>

### Retained F5-TTS profiles

See [Retained F5-TTS profiles](AUDIO.md#retained-f5-tts-profiles-unreleased).

<a id="ims-toucan-phonetics-and-structured-direction-unreleased"></a>

### IMS-Toucan phonetics and structured direction

See [IMS-Toucan phonetics and structured direction](AUDIO.md#ims-toucan-phonetics-and-structured-direction-unreleased).

### Single narrator and delivery variation

See [Single narrator and delivery variation](AUDIO.md#single-narrator-and-delivery-variation).

### Check narration continuity before a chapter render

See [Check narration continuity before a chapter render](AUDIO.md#check-narration-continuity-before-a-chapter-render).

### Passage direction

See [Passage direction](AUDIO.md#passage-direction).

## Development

Use [CONTRIBUTING.md](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md)
for checkout setup, supported checks, browser suites and documentation generation.
`make help` lists the maintained entrypoints.

## License

GNU Affero General Public License v3.0 or later (AGPL-3.0-or-later) – see [`LICENSE`](https://github.com/mfahsold/lixity/blob/main/LICENSE).
Commercial licensing on request: mfahsold@googlemail.com.
