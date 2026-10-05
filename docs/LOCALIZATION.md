# Language and localization contract

## Defaults and developer language

Documentation, comments and docstrings are English. Localized resources,
quoted material and linguistic examples retain their intended language.
Machine-readable keys and mathematical identifiers remain language-neutral.

Analysis language and report language are separate settings:

| Setting | Purpose |
| --- | --- |
| `--language de`, `--language en`, or another supported code | Selects the manuscript's linguistic profile. An explicit CLI flag overrides project settings; English is the default. API callers use the `language` argument. |
| `--language auto` | Requests detection explicitly. Weak or ambiguous evidence resolves to `generic`. |
| `LIXITY_LANG` | Selects CLI/report presentation independently of analysis. Message packs currently cover German and English. |
| Dashboard language | Uses resources for all seven supported languages, including workspace and research controls. |

Research CLI help and errors are English; JSON keys are language-neutral.
Sources, quotations, filenames, external metadata, claim titles and author
decisions are preserved as entered. Localization does not translate or verify
research content. Some backend errors may still appear in English in the browser.

## Localization below the interface

Supported profiles are German (`de`), English (`en`), French (`fr`), Spanish
(`es`), Italian (`it`), Portuguese (`pt`) and Dutch (`nl`). German and English
currently have the most extensive linguistic heuristics and language-specific
fixtures. The other five profiles have localized presentation and linguistic
resources with more limited coverage and validation. Equal interface coverage
does not establish equal accuracy across languages or genres.

| Concern | What changes with the language |
| --- | --- |
| Words and sentences | Word patterns, abbreviations and sentence-boundary rules |
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
German and English default word patterns include precomposed accented words;
they do not normalize Unicode or cover every combining-mark spelling. Explicit
word patterns retain their own flags. Syllable calculation reuses word
frequencies within a request, preserving the same heuristic values without a
global cache.

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
