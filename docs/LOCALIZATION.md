# Language and localization contract

## Defaults and developer language

Documentation, comments and docstrings are English. Localized resources,
quoted material and linguistic examples retain their intended language.
Machine-readable keys and mathematical identifiers remain language-neutral.

CLI analysis language and CLI report language can be selected independently.
The native dashboard currently follows its analysis profile:

| Setting | Purpose |
| --- | --- |
| `--language de`, `--language en`, or another supported code | Selects the manuscript's linguistic profile. An explicit CLI flag overrides project settings; English is the default. API callers use the `language` argument. |
| `--language auto` | Requests detection explicitly. Weak or ambiguous evidence resolves to `generic`. |
| `LIXITY_LANG` | Selects CLI/report presentation independently of analysis. Message packs currently cover German and English. |
| Dashboard language | Follows the manuscript's resolved analysis profile, using all seven UI resource packs. The native language control is not an independent interface-language preference. |

Detection uses the text the caller supplies. `pipeline.resolve_document_config`
resolves `auto` before analysis. Direct `CorpusAnalyzer` text, file and unit
analysis resolve `auto` separately for each input unless a representative
`sample_text` binds the analyzer to one profile. Profile helpers on an unbound
analyzer use `generic`. For direct `ParagraphProfiler` calls, supply a sample
or resolve `auto` to a concrete key before passing the parsed blocks.

Research CLI help and errors are English; JSON keys are language-neutral.
Sources, quotations, filenames, external metadata, claim titles and author
decisions are preserved as entered. Localization does not translate or verify
research content. Known structured export-limit failures receive localized
summaries and recovery guidance. Exact technical diagnostics remain available in
English; unknown backend failures are not guessed or presented as known cases.

## Public website language

The seven static product introductions have distinct URLs, reciprocal `hreflang`
links and native language names in the switcher. With JavaScript enabled, a
supported saved preference takes priority over the browser's ordered language
list. Regional preferences such as `de-DE` and `pt-BR` match the corresponding
available language. Unsupported languages leave the current page unchanged.

A visible suggestion offers a single-click switch; there is no automatic
redirect. A manual choice (including staying on the current page) is stored as
`lixity-site-language` in local storage when available. Blocked storage does not
prevent navigation. Without JavaScript, the ordinary language links still work.
Direct links remain authoritative; technical manuals stay in English and never
show a language suggestion. Website preferences never change manuscript analysis,
project configuration or the local app's interface language.

The Sandbox uses a German or English interface. Its entry from the German
product page uses `?lang=de`; the other product pages open `?lang=en`. This
explicit selection takes precedence over a linked sample's language and the
shared website preference. A plain Sandbox URL uses a supported saved website
preference or the browser's languages. Switching within the Sandbox updates
its URL while retaining the current text and the saved website preference.
Public demo links identify the English reading and analysis interface.

## Product vocabulary and ownership

This is the central terminology contract. [Methods](METHODS.md) owns formulas,
counting rules and limitations; [Research data model](research/DATA_MODEL.md)
owns retained records and relations. The existing language resource packs own
translations, not a second glossary service or a separate runtime term registry.

The interface distinguishes **observation**, **interpretation**, **action**,
**saved state** and **author intent**. A short familiar name accompanies the
scope and basis of each measurement or operation. Technical terms and stable
command and JSON identifiers stay available for reproducibility.

| Concept | DE / EN display direction | Meaning and excluded inference |
| --- | --- | --- |
| Counted pattern | Nomen-Endungen / Noun endings | Selected ending matches, not a grammatical noun classification or a nominal-style verdict. |
| Quoted-text measurement | Text in Anführungszeichen / Quoted words | Recognized quoted spans in the manuscript; neither proof of dialogue nor research-source citations. |
| Reader measurement switch | Gezählte Stellen unterstreichen / Underline counted passages | Marks the source text that entered the selected calculation. |
| Reader comparison switch | Abweichende Absätze markieren / Mark differing paragraphs | Shows each marked paragraph's value and its chapter reference in the same unit. |
| Reader tense action | Zeitformhinweise prüfen / Review tense findings | Opens the cues for a possible tense change. The chapter filter retains each matching chapter's surrounding text. |
| Statistical comparison | Vergleiche innerhalb der Schwelle / Comparisons within the limit | Measurable chapter/feature cells inside the selected bound, not plot coherence or quality. Unavailable is not zero. |
| Composite comparison | Signalgruppen im Vergleich / Signal-group comparison | Word-pattern cues versus quotation/short-sentence shares; not validated narrative distance or show/tell classification. |
| Ending cues | Schlussmerkmale / Ending cues | Three closing-pattern checks, not suspense or chapter effectiveness. |
| Manual marker action | Zur Sachprüfung markieren / Mark for fact-check | Opens an editable marker draft; no fact check or saved write occurs before explicit save. Marker-category names remain distinct. |
| Analysis review decision | Bewusst gelassen / Kept intentionally | An explicit author decision about an exact analysis observation; not proof of a repaired manuscript or a research assessment. |
| Source copy | Quellenkopie / Source copy | Retained bytes/context at a version; not an accepted claim or Lixity-verified source content. Byte integrity and content truth are separate. |
| Source excerpt | Quellenausschnitt / Source excerpt | A retained passage or selected source text; extraction and OCR can be imperfect. |
| Claim and evidence link | These und Belegverknüpfung / Claim and evidence link | An authored assertion and an explicit relation to a source passage. Confidence is an author assessment, not system probability. |
| Dossier | Dossier / Dossier | Curated research text, media and references; copying a passage into its draft is not a saved link. |
| Research change prompt | Abgleich offen / Comparison pending | Recorded versions, dates or an author request justify comparison; they do not establish contradiction or required rewriting. |
| Output generation history | Erzeugungsverlauf der Ausgabedatei / Output generation history | Details recorded for generated output files; an unknown history says nothing about research-source attribution. |
| Publication selection | Ausgewähltes Begleitmaterial / Selected background | Explicit dossier entries in a reading package; no generated synopsis or publication action is implied. |
| Chapter display gate | Anzeigen nach abgeschlossenem Kapitel / Show after completing chapter | Display after chapter N is marked finished; zero means from the start. This is not access control or physical exclusion from the files. The separate export chapter cap controls package selection. |
| Operation receipt | Download gestartet / Download started | A download was initiated; the application cannot establish that the recipient saved the file. |

### Evidence levels for analysis claims

The claim ladder is a binding copy and display rule for analysis claims in the
interface. Its levels identify the kind of evidence required. They carry no
meaning as scores, confidence grades or ranks. Use the exact metric and scope
in the label or its immediate explanation. Keep the level and its name visible
on the measurement track, detail, or author-intent section. A tooltip or color
alone is insufficient. Use the existing translation packs in all supported
interface languages. [Formulas, guards and sources](METHODS.md#scene-evidence-and-dramaturgical-rehearsal)

| Level | Evidence | Allowed DE / EN example | Limit |
| --- | --- | --- | --- |
| L0 · Measurement | Text matched by a stated rule. Show the observed count and the denominator for a share. | Anteil erkannter Zitatwörter / Share of recognized quoted words | A defined text property. Reader effects require separate evidence. |
| L1 · Comparison | A derived difference with the comparison scope, units, applicable sample floors and available uncertainty. | Sätze werden kürzer, zweite Hälfte −2,5 Wörter pro Satz / Sentences are shorter in the second half, −2.5 words per sentence | This says how the measurement changes within this text. Do not infer speed, significance, or suspense. |
| L2 · Distribution | Counts or a spread across stated classes with their limits. | Zwölf kurze Zitatblöcke / Twelve short quotation blocks | Block length is textual. Speaker identity, fictional duration and discourse function require other evidence. |
| L3 · Author intent | A reading question, author-entered intent, voice note, or effect hypothesis. | Wem gehört hier das Wort? / Who has the floor here? | Keep the question open and label saved hypotheses as authored. A measurement cannot create an intent card. |
| L4 · Reader response | Observations from an identified study with its sample, materials and conditions. | Readers in the cited experiment reported suspense even when they knew the ending. | Cite this in research documentation. Do not attach study outcomes to an individual passage as a prediction. |
| L5 · Literary quality | Outside the product's evidence model. | — | No verdict, score, ranking or recommendation about literary quality. |

For a review state, describe the operation or current evidence, for example
**Erneut prüfen / Review again** after a source change. A state change says
which source was reviewed. It establishes no new interpretation.

### Resource boundaries and editorial style

Each resolved key has one authoritative definition. Analysis measurement names
and help stay in `language_data.py`; workspace actions, source states, publication
controls and structural help stay in `workspace_labels.py`. Search controls also
belong to the workspace pack. `language.py` composes these packs; it must not
silently overwrite competing definitions. `tests/test_interpretation_labels.py`
checks that invariant, while existing localization tests check completeness and
placeholders. Separate action keys are appropriate when a stored category and an
action have different meanings; they do not create new stored marker kinds.

German app-owned copy avoids direct address where possible: `Quelle öffnen`,
`Dossier gespeichert`, `Vergleich nicht verfügbar`. Keep sentences concrete and
short rather than replacing address with bureaucratic passive phrasing. Preserve
first-person examples, consent assertions, quoted text and authored content.
Other languages use coherent local phrasing; German syntax is not a translation
template. The `pt` and `es` packs still require native editorial review before
claiming a consistent regional voice. No regional compatibility modes are implied.

### Review in context

Review a complete interaction: visible name, explanation, empty/error state,
accessible name, resulting object, persistence and return path. Ask authors or
editors to predict the effect before clicking and to explain what is known,
unknown or saved afterwards. A preference for a term is not evidence that it is
understood. Compare alternatives with the same underlying data and include
unavailable results, non-text sources, unsaved drafts and failed operations.
Resource parity and desktop/mobile browser checks establish coverage and layout;
they do not replace native-language review or author comprehension studies.

## Localization below the interface

Supported profiles are German (`de`), English (`en`), French (`fr`), Spanish
(`es`), Italian (`it`), Portuguese (`pt`) and Dutch (`nl`). German and English
currently have the most extensive linguistic heuristics and language-specific
fixtures. The other five profiles have localized presentation and linguistic
resources with more limited coverage and validation. Equal interface coverage
does not establish equal accuracy across languages or genres.
The [core validation status](STABILITY.md#core-validation-status)
separates manually annotated literary counting examples from unresolved grammar,
Unicode, dialogue and syllable limitations.

| Concern | What changes with the language |
| --- | --- |
| Words and sentences | Word patterns, abbreviations and sentence-boundary rules (sentence boundaries never cross blank lines) |
| Tense and style signals | Present/past markers, function words, pronouns, modality, passive and nominal patterns |
| Readability | Syllable estimation and the named language-specific coefficient set |
| Presentation | Labels, scientific explanations, decimal/grouping separators and percentage units |
| Generic profile | Reduced fallback heuristics, not a validated model for an unknown language |

OCR badges resolve stable diagnostic codes through the same workspace label
packs. `ready` describes configuration, not recognition quality. Source URLs
and quotations are never translated. See [research limits](research/USAGE.md).

## Mathematics and scientific interpretation

Median/MAD normalization, measurement-error adjustment, multiple-testing
correction and eigendecomposition use the same mathematics in every language.
Translation must not change these numerical results. Their linguistic inputs
can differ; cross-language scores are not automatically comparable. JSON
numbers stay numeric; locale formatting applies only to displayed reports.

Readability coefficients are documented in [Methods](METHODS.md). Results are
not clipped to 0–100 and do not diagnose literary quality. The generic profile
uses fallback coefficients, not a model calibrated for every language.

Syllable counts, tense classification and stylistic patterns are deterministic
heuristics, not a full grammatical parser. Dialect, historical spelling,
code-switching and unusual vocabulary need separate evaluation.
The shared prose-counting projection normalizes to NFC, so canonically equivalent
accent spellings have the same token, cue and syllable counts. Manuscript bytes,
display text and anchor hashes retain their supplied representation; literal
evidence maps back to original codepoint ranges. This is not full grapheme-aware
word segmentation for every combining-mark sequence. Explicit word/cue patterns
retain their flags and operate on the canonical counting text; document-boundary
patterns address the original source. Hyphenated compounds stay one token under
the German and English defaults and split under the other five profiles;
apostrophes remain word-internal there. Syllable calculation reuses word
frequencies within a request, preserving the same heuristic values without a
global cache.

v0.7.2 corrects the five profiles' internal-apostrophe patterns for both `'` and
`’`. First-person sentence-start matching treats these two forms alike without
changing the original token used for starter diversity or the manuscript text.
These are orthographic counting conventions, not grammatical segmentation of
clitics. Recompute affected token-based and sentence-start results before
comparing reports from earlier versions.

The German v0.7.2 perception/filter list also adds finite indicative present and
simple-past forms of *hören* and *riechen*. Neutral positive and negative fixtures
cover shared corpus/chapter/paragraph/scene counting and explicit overrides.
This does not validate perception, grammatical roles or all German inflections;
see [the cue-list limits](METHODS.md#perceptionfilter-word-cues).

## Acceptance criteria for language work

Prioritize German linguistic resources and scientific explanations, then English,
then the other supported languages. Documentation remains English; this priority
does not change the default analysis language or imply equal validation.

1. Supply and test linguistic resources; do not substitute English patterns.
2. Provide complete, nonempty label/help keys and review translation quality.
3. Document formula sources and unavailable analyses; do not invent coefficients.
4. Test known numeric examples and language-specific positive/negative fixtures.
5. Apply locale formatting only when displaying results; keep JSON numbers numeric.
6. Distinguish coverage and dispatch tests from empirical validation.

`tests/test_localization.py` checks defaults, explicit detection, resource keys,
coefficient selection and number formatting. Linguistic and mathematical suites
add specific examples. Together, they do not establish a language-wide accuracy
percentage.

**Since v0.7.3:** contextual action help, the visible keyboard
reference and internal-reference descriptions use the same seven UI label packs.
Browser checks cover pack/placeholder parity, document language, real source
toolbars and reading controls at desktop and narrow widths. Full translated
sentences are kept intact; technical key names and identifiers stay stable.
These checks establish coverage and layout, not a professional translation review
or equal linguistic-analysis accuracy across the seven languages.

### Direction for deeper grammatical analysis

The lightweight, transparent profile remains the default. Since v0.7.6,
explicit local grammatical tense models are implemented for all seven analysis
languages through the shared verb-group engine. See
[setup and model selection](USAGE.md#grammatical-tense) and
[language-specific evidence and limits](STABILITY.md#grammatical-tense).
Model language, installed version and policy identity remain separate from
lexical cues. Analysis never downloads a model, silently falls back or sends
manuscript text to a remote parser. Exact source anchors are retained; saved
decisions are rechecked when the measurement identity changes.

Synthetic construction checks and the bounded UD token-feature comparison are
different measurements. Neither establishes representative verb-group
precision/recall on literary manuscripts, nor equal accuracy across languages.
Missing mood, ambiguous constructions and upstream parser errors remain visible.
