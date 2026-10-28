# Stability & known limitations

Use this page to judge what a result can support. Formula details live in
[METHODS.md](METHODS.md); machine-readable thresholds and availability policies
come from `lixity about --json`. This page keeps interpretation and integration
limits that a passing check cannot resolve. Statistical signals support human
review, not a prose grade.

## 1. Research findings (state of the art)

### Release verification and limits

The maintained suite checks English defaults, language resource-key coverage,
readability-coefficient dispatch and locale formatting. These are software
contracts, not empirical validation of linguistic accuracy across seven
languages. No language-wide accuracy percentage is established by this suite.

The 3D chapter view is exploratory: its dimensions are corpus-specific, signs
are fixed by convention, and per-axis thresholds are not simultaneous confidence
regions. Native rotation/zoom buttons and a chapter-score table provide keyboard and touch access to the displayed scores,
flag status and chapter navigation. Individual canvas points remain pointer-operated.
These targeted checks do not establish full assistive-technology coverage.

Engine tests use synthetic/public samples. Project adapters and optional local
servers have separate trust boundaries and need their own tests; core test
success is not a security certification for an arbitrary adapter.

<a id="grammatical-german-tense"></a>

### Grammatical tense

The optional local model path covers all seven supported analysis languages and
is a contextual grammatical measurement, not a
linguistic correctness guarantee. The standard installation uses incomplete
lexical patterns. In v0.7.6 German unknown adjectives ending in `-ten` can match
past cues. Current main removes that unrestricted German suffix rule and adds
selected forms such as `übt`; unlisted regular past forms such as `flatterten`
can now be missed. Listed forms and auxiliary/participle matches can still be
ambiguous: for example, `Ich habe gelben Stoff` can still produce a spurious
past cue from `habe gelben`. This changes counts and dependent results, so regenerate analyses and
review previous decisions. Other languages retain their existing patterns. To use
the contextual path, explicitly select an installed model as described in
[Usage](USAGE.md#grammatical-tense).

The initial construction comparison used 40 newly written German sentences with
manually assigned verb-group tense/mood labels, available in
`tests/fixtures/german_verb_groups.json`. All systems used the same Lixity
composition rules. It is a development construction set, not an independent,
representative or held-out literary benchmark. Final matching-sentence counts:

| Installed parser | Fully matching cases / 40 |
| --- | --- |
| spaCy `de_core_news_md` 3.8.0 | 39 |
| spaCy `de_core_news_sm` 3.8.0 | 36 |
| ZDL `de_zdl_lg` 4.0.0 | 33 |
| Stanza 1.15.0, German HDT resources | 31 |

These numbers evaluate complete sentence label sequences on this set, not token
accuracy or editorial-warning precision. Stanza was compared through a temporary
UD adapter; the shipped runtime uses spaCy. The small model sometimes mistakes
modal/coordinate forms; the tested HDT models supplied incorrect mood features
for several subjunctives. This supports selecting `de_core_news_md` as the initial
CPU option, not declaring it universally superior. Model load/memory and
long-manuscript throughput were not established by the short construction score.
Reproduce the spaCy comparison from a development checkout with installed models:

```sh
python scripts/check_grammatical_tense.py de_core_news_sm de_core_news_md de_zdl_lg
```

The remaining md error is `Übe jeden Tag!`, tagged as indicative present rather
than imperative. In the separate existing public-domain *Effi Briest* excerpt,
the model correctly tags seven preterite predicates but misreads adjectival
`weiß` in `blau und weiß gestreiftes …` as a present verb. That is a real false
positive, not an accepted gold label. Ambiguous `sein` constructions may be
reported unresolved. Indirect/free indirect discourse and semantic narrative
time are not recognized automatically. Selecting `narration` only excludes spans
recognized by the configured quotation pattern, including its capture convention;
it must not be presented as reliable speaker attribution.

Future, subjunctive and unresolved groups stay inspectable rather than being
silently turned into past/present evidence. A zero count is the number of
resolved selected indicative groups, not proof that the paragraph contains no
verbs or tense changes. Model absence or failure is an explicit error. Optional
model execution was checked on Linux ARM/Python 3.12; core portability checks do
not establish optional spaCy model compatibility on every supported platform.

#### Additional language construction checks

The manually labeled synthetic cases in `tests/fixtures/multilingual_verb_groups.json`
check whole finite-group **tense sequences**, separately from the German
**tense-plus-mood** score above. These are development regression cases, not
independent or representative literary evaluation sets:

| Language / selected model | Matching tense sequences |
| --- | --- |
| English / spaCy medium 3.8.0 | 13 / 14 |
| French / Stanza GSD nocharlm 1.15.0 | 14 / 15 |
| Spanish / spaCy medium 3.8.0 | 14 / 14 |
| Italian / Stanza MarkIT nocharlm 1.15.0 | 17 / 17 |
| Portuguese / spaCy medium 3.8.0 | 15 / 16 |
| Dutch / spaCy medium 3.8.0 | 15 / 15 |

The English model misses a coordinated predicate, French treats `partie` as a
noun in an anterior-perfect example, and Portuguese mistakes synthetic
pluperfect `escrevera` for present. The French spaCy medium baseline matched
10/15 on the same cases, including future/conditional mistakes, motivating the
explicit Stanza option. No model is declared universally best. English/Dutch
missing Mood stays `unmarked`; conditionals and modal forms are separate, not
ordinary past. Unknown morphology, ambiguous `zijn` state/perfect-passive
readings and incompatible finite carriers stay unresolved. Analytic prospective
constructions and indirect/free indirect discourse are not comprehensively
classified. A matching tense sequence does not validate mood, voice, aspect,
quotation interpretation or warning usefulness.

#### Official scientific corpus feature checks

[Universal Dependencies 2.18](https://universaldependencies.org/) (15 May 2026)
provides the official token-annotation reference. The first 100 sentences in file
order from each tagged test partition were checked locally, 700 total. Selected
models parsed all 700 after unknown word morphology was retained explicitly.
This is a bounded **token-feature agreement** check, not a compound verb-group
tense benchmark or a representative accuracy estimate:

| Treebank, r2.18 test | Indicative token Tense matches / eligible |
| --- | --- |
| [German HDT](https://universaldependencies.org/treebanks/de_hdt/index.html) | 49 / 55 |
| [English EWT](https://universaldependencies.org/treebanks/en_ewt/index.html) | 141 / 169 |
| [French GSD](https://universaldependencies.org/treebanks/fr_gsd/index.html), selected Stanza | 149 / 149 |
| [Spanish AnCora](https://universaldependencies.org/treebanks/es_ancora/index.html) | 195 / 201 |
| [Italian MarkIT](https://universaldependencies.org/treebanks/it_markit/index.html) | 265 / 269 |
| [Portuguese Bosque](https://universaldependencies.org/treebanks/pt_bosque/index.html) | 109 / 111 |
| [Dutch Alpino](https://universaldependencies.org/treebanks/nl_alpino/index.html) | 154 / 162 |

Eligible gold features enter the denominator before prediction/alignment checks.
English had 28 eligible finite-word alignment misses; Portuguese had two.
English omitted Mood for 90 aligned eligible words and Dutch for all 162.
Missing gold features are reported separately; they are not invented as gold
labels. Many-to-many expanded word spans are not guessed. HDT has converted
manual morphology; GSD German features have different annotation provenance.
MarkIT includes partially corrected automatic morphology. Training overlap,
annotation conversion, domains and the small ordered prefixes limit interpretation.
Raw external corpus bytes are not bundled; reproducible tools accept explicit
local files and report their SHA256 and caller-supplied provenance:

```sh
python scripts/check_linguistic_corpus.py --conllu de_hdt-ud-test.conllu --language de --model de_core_news_md --limit 100 --corpus UD_German-HDT --release 2.18 --license "CC BY-SA4.0" --source https://raw.githubusercontent.com/UniversalDependencies/UD_German-HDT/r2.18/de_hdt-ud-test.conllu
```

#### Finite-verb detection, separately from feature agreement

The evaluator additionally reports `finite_verb_detection` over **all uniquely
aligned gold words**, including nonverbs. A positive requires `VERB` or `AUX`
and `VerbForm=Fin`. This exposes false-positive finite verbs on gold adjectives
or nouns that the gold-verb-conditioned feature table above cannot measure.
The [CoNLL-U format](https://universaldependencies.org/format.html) distinguishes
syntactic words, surface tokens and morphology; expanded many-to-many spans
remain unscored rather than being guessed into alignment.

The independent 28 October 2026 rerun used the same official r2.18 test files,
first 100 sentences per language and local model versions listed above. French
was rerun with both the earlier spaCy medium baseline and selected Stanza GSD.
All original feature metrics, including eligible Tense denominators, matched
the retained previous reports exactly. No sentence failed source reconstruction
or parsing in these eight runs. Counts below are **conditional on unique exact
alignment**, not end-to-end detection across excluded words:

| Test partition / parser | Aligned / all gold words | TP / FP / FN | Precision / recall |
| --- | ---: | ---: | ---: |
| German HDT / spaCy md | 1656 / 1700 | 119 / 5 / 4 | 0.960 / 0.967 |
| English EWT / spaCy md | 2110 / 2202 | 166 / 4 / 12 | 0.976 / 0.933 |
| French GSD / spaCy md baseline | 2395 / 2584 | 149 / 1 / 9 | 0.993 / 0.943 |
| Spanish AnCora / spaCy md | 2944 / 3076 | 220 / 2 / 2 | 0.991 / 0.991 |
| Italian MarkIT / Stanza | 2868 / 3224 | 292 / 2 / 4 | 0.993 / 0.986 |
| Portuguese Bosque / spaCy md | 1563 / 1797 | 128 / 0 / 0 | 1.000 / 1.000 |
| Dutch Alpino / spaCy md | 2049 / 2049 | 157 / 5 / 5 | 0.969 / 0.969 |
| French GSD / Stanza | 2414 / 2584 | 158 / 0 / 0 | 1.000 / 1.000 |

The JSON separately reports gold/predicted alignment misses and unscored words
from source/parse failures. A gold verb without unambiguous finiteness is not
invented as a negative: one aligned French word per run and one Portuguese word
were excluded from detection labels. Missing predicted verb finiteness is
counted explicitly; it misses a known gold finite verb rather than manufacturing
a resolved prediction. Undefined precision/recall denominators produce `null`.
Italian MarkIT, Portuguese and French Stanza each had one aligned prediction
without verb finiteness in this bounded rerun.

These are token-detection and token-feature checks. They do not validate composed
verb-group tense, narration attribution, editorial warnings or literary quality.
The ordered sample, alignment exclusions, corpus annotation provenance and
possible training overlap prevent representative accuracy or a general parser
ranking. In particular, perfect scores on the selected aligned subset do not
establish perfect detection in excluded spans or unseen literary text.

### Core validation status

**Since v0.7.6:** seven short original-language literary excerpts have manually
transcribed sentence boundaries and orthographic tokens in
[`tests/fixtures/literary_reference.json`](https://github.com/mfahsold/lixity/blob/main/tests/fixtures/literary_reference.json).
They cover 375 tokens and 14 sentences, with edition URLs, extraction locators
and public-domain provenance. The same expectations check corpus, chapter and
paragraph counts and the real CLI. Native browser checks compare displayed
sentence counts, paragraph means, localized units and exact highlights with the
same annotations in all seven languages, NFC/NFD spellings and desktop/mobile.
The expected tokens are not generated by the engine.

| Measurement | Evidence so far | What it does not establish |
| --- | --- | --- |
| Words and sentences | Manual literary boundaries/tokens agree across backend, CLI and UI on the reference excerpts. | Representative per-language segmentation accuracy. |
| Unicode and literal evidence | Canonical-equivalent counting, original hashes/offsets and complete-cluster mappings have positive and negative fixtures. | Full grapheme-aware tokenization or guessed mappings across excluded Markdown regions. |
| Nominal, passive and other lexical cues | Controlled positive/negative examples check listed patterns, agreement variants and overrides. | Contextual part-of-speech, voice, tense or nominal-style classification. |
| Syllables and readability | Selected dictionary divisions and named coefficient arithmetic are checked. | Language-wide pronunciation accuracy, comprehension or novel-quality prediction. |
| Statistical comparisons | Controlled formula/edge cases check robust spread, adjusted deviations, lexical estimators and rank-space computations. | Calibrated chapter p-values, independent sentences or genre-wide inference. |
| Presentation | Real localized values, units, source ranges, scope distinctions and mobile visibility are exercised. | A measured author/editor comprehension or usability-study result. |

The works are Fontane's *Effi Briest*, Austen's *Pride and Prejudice*, Flaubert's
*Madame Bovary*, Cervantes's *Don Quijote*, Collodi's *Pinocchio*, Queirós's
*Os Maias* and Multatuli's *Max Havelaar*. Per-excerpt counts and provenance
remain in the reference fixture, rather than being duplicated here.

These are regression examples, not a representative literary corpus or a
held-out evaluation of grammar, syllables, readability or literary quality.
Historical spelling and deliberately short selections limit generalization.
Passing them establishes the stated counting conventions on those passages.

Reference units must agree before comparing systems. Lixity's orthographic
tokens differ from UD's syntactic words: contractions and clitics can be one
written token but several syntactic words. An annotated-corpus evaluation must
reconstruct the surface tokens and compare character boundaries, rather than
label every token-total difference a bug. See the
[UD evaluation protocol](https://universaldependencies.org/conll18/evaluation.html)
and [tokenization conventions](https://universaldependencies.org/u/overview/tokenization.html).
Similarly, [UD tense features](https://universaldependencies.org/u/feat/Tense.html)
describe words, which need not have the tense of an entire compound construction.

External sentence-boundary audits must record the treebank release, test
partition, source/license hashes, sample rule and reconstruction protocol.
Exact sentence-end precision/recall can be measured against UD `# text` units
without treating syntactic word counts as orthographic gold. Joining units into
artificial paragraphs tests boundary stress cases, but loses natural paragraph
context: unpunctuated headings and colon-separated units can then appear as
missed boundaries. Such scores describe agreement under that protocol, not
language-wide or novel-specific accuracy. Exclude forced batch-final boundaries
from scoring and keep undefined rates unknown rather than reporting zero.

Bounded corrections have separate positive and negative fixtures: regular
plural passive participles in Spanish, Italian and Portuguese, French
`fut`/`furent`, nominal ending number variants and German `zur`. The
[Italian](https://universaldependencies.org/it/dep/aux-pass.html) and
[French](https://universaldependencies.org/fr/dep/aux-pass.html) UD examples
provide grammatical references, not measured precision/recall for these regexes.
Portuguese marked hiatus is checked against dictionary syllabifications such as
[saída](https://dicionario.priberam.org/sa%C3%ADda) and
[saúde](https://dicionario.priberam.org/sa%C3%BAde); Dutch trema boundaries follow
[official language advice](https://www.vlaanderen.be/team-taaladvies/taaladviezen/idee-ideeen-ideeen-ideen).
Dutch `ij` is counted separately from adjacent vowels, following dictionary
divisions such as [bij.en](https://anw.ivdnt.org/article/bij) and
[bij.een](https://anw.ivdnt.org/article/bijeen). Paired closing quotation marks
separated from terminal punctuation by spaces remain in their original sentence;
negative fixtures distinguish a following opening quote and blank-line boundaries.
Their effects reach syllables-per-word and the declared readability formula.

The Italian counter was compared post hoc against the `word` and `SumSylls`
fields in [PhonItalia 1.10](https://github.com/stefanocoretta/phonItaliaR/tree/main/data-raw/phonItalia-1.10)
(source TSV SHA-256 `22d22409c1fc3ad2844f47543f3017c50ef9d3f95f5196093ff2203d7f071b17`).
Run `PYTHONPATH=src python scripts/evaluate_phonitalia.py PATH_TO_WORDFORMS_TSV`
to reproduce aggregate agreement without copying the lexicon into Lixity.
Of 120,000 rows, 4,170 were excluded by the alphabetic-word/positive-count
filter; 90,134 of 115,830 remaining rows agreed exactly (77.82%), with mean
absolute difference 0.230 syllables. The sample contains 90,681 distinct
spellings, so repeated forms retain row weight. These are lexicon agreements,
not a language-wide accuracy estimate: pronunciation, dialect, token frequency,
syllabification conventions and literary usage vary. No separate literary
holdout or human listening evaluation was used.

The same command also compares the production estimator with an **experimental,
unshipped** rising-diphthong rule. It groups case-normalized NFC spellings,
excludes the 16 spellings with differing source counts and partitions the 90,665
remaining word types by SHA-256 modulo five. On the 18,156-type comparison
partition, exact agreement rises from 13,944 to 17,248 and mean absolute
difference falls from 0.2405 to 0.0505; nevertheless, 469 forms become worse
while 3,771 improve. This partition was inspected during development and is
not an untouched holdout; these figures do not measure performance on novels
or token-weighted text. The candidate incorrectly merges common hiatuses such
as `io` and `mio`, because unmarked stress cannot reliably be inferred from the
letters alone. It was therefore not enabled. Italian phonology distinguishes
[rising diphthongs](https://www.treccani.it/enciclopedia/dittongo_%28Enciclopedia-dell%27Italiano%29/)
from [hiatuses](https://www.treccani.it/enciclopedia/iato_%28Enciclopedia-dell%27Italiano%29/);
pronunciation varies with lexical and linguistic context. A larger independent
literary evaluation and a suitable stress-aware pronunciation resource remain
necessary before changing this counter.

For French, `PYTHONPATH=src python scripts/evaluate_lexique.py PATH_TO_TSV`
compares an experimental removal of the final `-ent` deduction with the
`1_Mot` and `26_SyllNb` fields of [Lexique 4.10](https://www.lexique.org/databases/Lexique410/Lexique4.1.zip)
(New et al., 2026; CC BY-SA 4.0; extracted TSV SHA-256
`f112ad487334c8ab702e6b95cf08110b2ac534d1896e1643f9c669f91a139a84`).
Among 12,705 unique alphabetic `-ent` spellings with one agreed count, 7,011
improve but 5,594 become worse; 26 ambiguous spellings are excluded. This is
type-weighted agreement with the lexicon, not accuracy on literary text. Its
syllable counts are algorithmically derived from phonological forms with final
schwas removed; real speakers can pronounce those schwas in some contexts.
The French counter remains unchanged: distinguishing spoken endings from
silent verb inflections requires additional contextual evidence.

The audit also reproduces unresolved weaknesses:

| Area | Observed limitation and interpretation |
| --- | --- |
| Unicode | NFC equivalence is corrected, preserving source bytes and offsets. Combining sequences without a precomposed letter can still exceed the word patterns' coverage; the mapper does not claim full grapheme segmentation. See [Unicode UAX #29](https://www.unicode.org/reports/tr29/). |
| Tense | Curated present-only forms no longer also count as productive past candidates. Listed German perfect/pluperfect pairs count as one construction across chapter, scene and paragraph analysis, with bounded intervening words. Unlicensed auxiliary/participle combinations retain both cues; regional/transitive variants, unlisted forms and other languages can still produce spurious mixed classifications. A `mixed` result is not proof of a grammatical tense switch. English `read` and Portuguese `falamos` require context. |
| Dialogue | Quoted-segment patterns miss conventional dialogue dashes and some single-quote styles. Zero detected quotation words does not establish absence of speech. |
| Syllables | Italian rising diphthongs such as `fiore`/`buono` remain overcounted; `paura` is undercounted. Broadly merging vowels would introduce other hiatus errors. French `vraiment`/`moment` are undercounted by the final `-ent` rule, which also serves silent verb endings; neither issue is resolved by spelling alone. The corrected Dutch `ij` rule is not a complete pronunciation model. |
| Sentence spans | Sentence-final abbreviations can merge sentences. Paired spaced closers and German single `‚…‘` closers have direct boundary/evidence controls, but quotation pairing and abbreviation tables are incomplete; a matching total does not guarantee correct boundaries. |
| Nominal/passive cues | Word endings and auxiliary patterns do not resolve lexical category, adjectival participles or syntactic voice. Short regular and selected irregular passive forms have positive/negative controls; German `ist geöffnet` state passive remains outside the event-passive cue pattern. Coverage is improved, not complete. |

Readability research evaluates defined tasks and datasets, often combining
lexical, syntactic and discourse features. It does not make a syllable/length
formula a comprehension test for these novels; see
[Lee et al. (2021)](https://aclanthology.org/2021.emnlp-main.834/).
Future corpus evaluation must report per-language boundary precision/recall,
cue precision/recall against appropriate annotations and the dataset/genre;
arithmetic tests, UI localization and highlighted count agreement are separate
checks. No novel-wide accuracy percentage is claimed here.

Potential external references include [Corpus REDEWIEDERGABE](https://aclanthology.org/2020.lrec-1.100/),
whose historical German material distinguishes direct, indirect and other
speech or thought representation, and [GermAnProse](https://aclanthology.org/2026.latechclfl-1.25/),
which provides narrative annotations for four German short prose texts. Neither
is a representative contemporary multilingual benchmark; annotation schemes,
text editions, permitted uses and span/token conventions must be checked before
comparison. GermAnProse has not been evaluated in this project.

An exploratory comparison against the fictional subset of the
[REDEWIEDERGABE consensus corpus](https://github.com/redewiedergabe/corpus)
(commit `45abfcf5f9c2a3d9a903f5c68f8f5b36bbce5563`, CC BY-NC-SA 4.0)
can be reproduced with `PYTHONPATH=src python scripts/evaluate_redewiedergabe.py
PATH_TO_DATA_MAIN_XML`. The script retains and outputs only aggregate counts;
the corpus remains a separately supplied resource. It flattens the TEI body,
preserving Unicode codepoint offsets and nested spans, and compares the German
production quotation and word regexes with `direct`/`speech` annotations at
word-token level. Mixed-medium, borderline direct spans and tokens crossing
annotation or match boundaries are excluded. This matches the exact patterns,
not the full Markdown manuscript preprocessing pipeline.

For 395 fictional samples (aggregate source SHA-256
`4cd63654a362794be47effe6856ac1526660fbd13a6a31c817c4c95266c9fd3f`),
the comparison has 39,455 true positives, 1,681 positive disagreements,
17,501 negative disagreements and 143,202 true negatives; 527 ambiguous and
zero boundary-crossing tokens were excluded. The resulting token precision is
95.9% and recall 69.3%. These are disagreements between quotation-mark cues
and direct-speech annotations: quoted thoughts or writing may be positive
disagreements even when the quotation cue is correct. Excerpt boundaries,
historical conventions, tokenization and annotation scope matter, and the
inspected corpus is not a held-out or representative contemporary evaluation.

### Manual manuscript association limits

Manually selected quotes require explicit retention and exact source/paragraph/claim
pins. Anchor review detects structural changes, not semantic contradictions or
factual support. Moved or ambiguous quotes require review; claim pins change only
through an explicit revision. Zero saved links do not prove a claim is unused.
The source recheck is optimistic and does not lock manuscript editors. Backups
include retained private quotes; this workflow creates no full manuscript blob.
See [retention and compatibility](research/USAGE.md#associate-a-manuscript-quote-with-a-claim).

### Research and external-library limits

Zotero owns bibliography and reading; Lixity retains selected evidence and authored
records. Their backup requirements are separate. An integrity audit verifies
retained bytes, references and citations; it cannot verify historical truth,
chronology or the completeness of an external library. Native integration checks
are bounded synthetic tests, not certification of every platform or collection.

Source analysis uses its own `source_internal` reference and unverified supplied
context. Retaining a historical source does not make it a manuscript style norm;
lexical overlap does not establish factual support or appropriate context.
Search does not resolve contradictory prose or accept a hypothesis for the author.

PNG/JPEG images retain exact source versions and stay outside text analysis.
Header validation and browser preview do not establish complete codec validity or
historical authenticity. Geographic coordinates and routes are authored data;
rendering a map does not verify a journey or sightline. An unavailable image
never silently resolves to a different version.

RIS migration is additive; verify attachment identities, retained citations and
restoration before retiring a workflow. Automatic background/cloud synchronization,
audio/video transcription, image OCR and visual AI are not implemented. PDF
extraction or an external OCR worker does not establish recognition accuracy.
Current media, provider and schema boundaries live in [Research usage](research/USAGE.md).

### Robust comparisons and statistical claims

Median/MAD and the noise-adjusted $z^*$ describe contrast within the supplied
manuscript. A normal-consistency multiplier does not make arbitrary chapter
features normally distributed. Missing SE means no estimated measurement error;
zero event counts or constant samples do not establish certainty.

BH/BY are established selection procedures **given valid null probabilities**
and their dependence conditions. Lixity's normal-tail probabilities use a
baseline estimated from the same chapters; their calibration is not established.
BY and the exploratory runs/lag diagnostics do not repair that gap.
`fdr_flagged` means selected under the implemented model, and
`expected_false_positives` is a standard-normal reference expectation, not an
observed error count. Cliff's delta describes ordinal contrast, not quality.
Definitions and active thresholds: [METHODS §§1–4](METHODS.md#1-robust-house-style-baseline).

Style axes now use PCA of standardized tied midranks on one common complete
chapter set. Covariance, explained variance and scores share that rank space;
missing measurements are not imputed. At least three complete chapters and
three varying baseline-usable features are required, with constant columns
dropped on that set. Incomplete chapters have no dimension scores. Complete-case selection and small samples still limit interpretation. Score flags are
descriptive and do not validate prose quality or simultaneous confidence.
See [METHODS §5](METHODS.md#5-exploratory-style-dimensions).

### Lexical diversity

Length, local vocabulary and estimator parameters affect different indices.
[Bestgen (2024)](https://doi.org/10.1111/lang.12630) studies English learner essays
and monologues; 60 tokens is one truncation condition, not a universal floor.
Its main experiment uses a 50-token draw/window parameter, so it does not
directly calibrate Lixity's 42-token HD-D.
[Kyle et al. (2024)](https://doi.org/10.1017/S0272263123000402) assesses optimized
oral-task variants, not Lixity's defaults on German novels. Neither establishes
genre-wide reliability for the local 100-token policy. Guiraud remains sensitive
to length; fixed-window MATTR and fixed-draw HD-D still depend on their parameters
and the supplied vocabulary distribution.

HD-D is exact expected TTR for a fixed draw. Exact computation removes Monte Carlo
error, not population uncertainty. MTLD variants also differ in direction
averaging, threshold and trailing-factor rules. Compare measurements only after
aligning formulas, parameters and segmentation; regenerate historical reports
when those contracts changed. See [formula and guard details](METHODS.md#6-lexical-diversity-indices).

### Linguistic proxies and literary interpretation

Analysis shares a bounded Markdown prose projection. Link labels contribute;
destinations, images, code, comments and excluded document regions do not.
Paragraph profiles preserve displayed text and source anchors separately from
counting. The configured token rules and narrower paragraph scope do not imply
complete CommonMark support or linguistic token accuracy. See
[analysis scope](METHODS.md) for the unit and denominator of each measurement.

Passive, tense, adjective, nominalization and modality fields count lexical
markers or suffixes. For example, German `werden` also marks future tense or
becoming; English `been` also appears in active perfect constructions. These
counts do not identify syntactic voice or distinguish epistemic uncertainty
from obligation. Sentence segmentation and syllables are also heuristic;
utterance abbreviations (`no.`, `co.`) split sentences and tokenless
fragments do not count as sentences.
Suffix cues over-include on purpose-ambiguous words: English nominal `-th`
counts *month/health/truth*, German adjective `-ig`/`-al` count
*König/Saal*, German nominal `-ik`/`-ur` count *Musik/Natur*. Modal lexicons
have unequal morphology coverage (German and Dutch include preterite forms,
the other profiles only present), so `modal_density` is not comparable across
languages.

Readability coefficient tests verify the declared formulas, not their original
calibration or reader comprehension. Amstad's original coefficient page and
calibration protocol have not been verified here. Scores may fall outside 0–100
and are not comparable across language formulas. [German PALME research
(2026)](https://aclanthology.org/2026.bea-1.6/) separates controlled detector tests
from graded-reader evaluation; its results do not validate Lixity's regex cues.

Showing/telling is a composite of those visible signals. Empty rankings and
zero fallback scores do not establish equal artistic effect. Without explicit
dividers, pacing scenes are chapter placeholders. Short sentences, perception
verbs and vocabulary contrast do not establish immersion, tension or a reason
to rewrite. Scene/register targets are explicit author preferences, never
hardcoded genre norms. [Underwood's expert discussion](https://tedunderwood.com/2024/01/05/can-language-models-predict-the-next-twist-in-a-story/)
illustrates why surface predictability and narrative experience differ.

Dialogue turns are quotation segments without speaker attribution. Character
mentions depend on supplied names or literal project aliases; declared viewpoint
chapters are separate metadata, not inferred first-person presence. There is no
NER or coreference. Hook and repetition scores also locate surface patterns;
deliberate calm endings and repeated motifs can be appropriate author choices.

### Structural diagnostics

These diagnostics preserve their declared numerical definitions; an exact
implementation does not validate the underlying model:

- `pelt_changepoints` uses exact unpruned dynamic programming: $O(n^2)$
  time and $O(n)$ storage. The retained singleton/zero-variance guard violates
  the PELT pruning premise, so no pruning or linear-time claim is made.
  Anchored variance updates reduce cancellation; exact optimization of this
  guarded objective does not validate its Gaussian model or a narrative break.
  [Killick et al., Theorem 3.1](https://arxiv.org/abs/1101.1438v3).
- Sn uses the original low outer/high inner medians and factor 1.1926. Qn
  preserves its pairwise-distance rank with modern factor 2.21914; neither
  applies finite-sample correction. Normal-consistency factors, finite bias
  corrections and robustness remain distinct. [Original paper](https://wis.kuleuven.be/stat/robust/papers/publications-1993/rousseeuwcroux-alternativestomedianad-jasa-1993.pdf),
  [maintained reference](https://cran.r-project.org/web/packages/robustbase/robustbase.pdf).
- Early/late Wasserstein integrates the exact empirical-CDF difference;
  merged CDFs also give KS $D$, with $D=0$ returning $p=1$ and stable survival
  evaluation. The same asymptotic probability model remains: ties, short
  samples, serial dependence and fitted distributions are not calibrated by
  this numerical correction. Mann–Kendall `tau` remains tau-a, with a
  tie-corrected approximate normal probability for $S$, not tau-b.
- The graph exponent follows the approximate discrete estimator in
  [Clauset–Shalizi–Newman Eq. 3.7](https://arxiv.org/abs/0706.1062v2).
  The current continuous fitted CDF and ordinary KS probability do not implement
  its refitted goodness-of-fit procedure. Graph degrees are dependent too;
  neither a fit distance nor a small sample certifies a scale-free graph.

Early/late splits are chapter-count midpoints, not learned narrative boundaries.
Signed Dunning keyness ranks token contrast; it has no multiplicity adjustment.
Chapter-to-rest JSD is raw divergence in nats, not its square-root distance or
an external Delta authorship test. Inspect driver words in context. Formula
details and unchanged field contracts: [METHODS §4c](METHODS.md#4c-structural-diagnostics-structural_diagnostics).

**Accessibility / data visualisation (WCAG 2.2).**
- Colour must never be the only channel (SC 1.4.1, 1.3.3): the heatmap
  prints the numeric z* values, the band chart encodes band/median/outliers
  by position and shape, every chip reveals tense + value as text on click.
- Contrast targets are 3:1 for relevant non-text UI and 4.5:1 for normal text.
  Lixity chooses heatmap text from each cell’s luminance and
  tests the full blue/orange scale. This does not certify every canvas mark or
  every color-vision condition; numeric labels remain essential.
- WCAG 2.5.8 has a 24×24 CSS-pixel minimum with defined exceptions. Paragraph
  chips and dimension controls use at least 24×24,
  increasing to 44×44 for coarse pointers. Pressed chips retain their target
  size, and long strips scroll horizontally. These checks do not establish
  conformance for the entire interface or every canvas mark.
- Diverging scales have a meaningful midpoint: zero deviation from the
  within-manuscript reference (median in the robust style calculation).
- See [visual design rationale](ARCHITECTURE.md#visual-consistency-and-evidence)
  for evidence, typography choices and the limits of automated UI checks.

## 2. Stability register

The current cross-cutting limits below replace the completed-bug checklist.
Historical fixes and release-specific evidence remain in [CHANGELOG](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md),
[release notes](https://github.com/mfahsold/lixity/tree/main/docs/releases) and the
[archived register and verification snapshot](https://github.com/mfahsold/lixity/blob/123b198db2b3d276b4bba71664e4e6b989377247/docs/STABILITY.md#2-stability-register).

| Surface | Remaining boundary | Maintained reference |
| :--- | :--- | :--- |
| Numerical reproducibility | Floating-point last bits can differ across interpreters/platforms. | [Methods](METHODS.md) |
| Large dashboards | Bundled assets and full offline text increase document size; opening paragraph details lazily does not remove the retained text payload. | [Architecture](ARCHITECTURE.md) |
| Workspace status | File-derived status is advisory; timestamps and restored files can be misleading. Unknown is not success. | [Workspace interfaces](AGENTS.md) |
| Optional project adapters | Core checks do not verify a project's launcher, export tools or local runtime. | [Installation](INSTALLATION.md) |
| Publication formats | Font coverage and layout limits remain; no EPUB, PDF/UA or PDF/X certification is claimed. | [PDF export](USAGE.md#download-a-manuscript-pdf) |
| Agreement drafts | Built-in PDF fonts do not cover every script; download text for external rendering and retain reviewed documents in project storage. | [Project interface](AGENTS.md) |

Empty optional signal fields, unavailable small-sample metrics and missing
rankings must be interpreted using their configuration/availability metadata.
They are not evidence of no signal or equal literary effect.
