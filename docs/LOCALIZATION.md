# Language and localization contract

## Defaults and developer language

Documentation, comments and docstrings are English. Localized resource values,
quoted material and linguistic fixtures retain their intended language.
Machine-readable keys and tense identifiers remain language-neutral.

From `1.15.0.dev0`, CLI/API analysis and `CorpusConfig` default to English.
CLI `--language` overrides the project's `language` setting; without either,
English applies. API callers select their language through the argument.
`auto` is explicit and resolves to `generic` for weak or ambiguous evidence.

`LIXITY_LANG` controls CLI/report presentation independently of manuscript
analysis. Its current message packs are English and German. It does not
select the manuscript's linguistic model. Dashboard resources cover all seven
supported languages; full CLI-message parity remains separate work.

## Localization below the interface

| Concern | Language-dependent behavior |
| --- | --- |
| Tokenization and sentence segmentation | Word patterns and abbreviation/segmentation rules |
| Tense and style signals | Present/past markers, function words, pronouns, modality, passive and nominal patterns |
| Readability | Syllable estimator and named language-specific coefficient set |
| Presentation | Labels, scientific help text, decimal/grouping separators and percentage units |
| Generic profile | Reduced heuristics; not a validated model for an unknown language |

Supported profiles: English (`en`), German (`de`), French (`fr`), Spanish
(`es`), Italian (`it`), Portuguese (`pt`) and Dutch (`nl`). Do not infer equal
accuracy from equal resource-key coverage.

## Mathematics and scientific interpretation

Median/MAD normalization, measurement-error adjustment, multiple-testing
correction and eigendecomposition are shared mathematics. Translating a UI
must not change their numerical results. Linguistic inputs to those methods
can differ by language; cross-language scores are not automatically comparable.

Readability formulas use language-specific coefficients already listed in
`METHODS.md`. Results are not clipped to 0–100. A high or low score is a
model output, not a diagnosis of literary quality. The generic profile uses
fallback coefficients, not an empirically calibrated model for every language.

Syllable counts, tense classification and stylistic patterns are deterministic
heuristics, not a full morphological parser. Accuracy for dialect, historical
spelling, code-switching or unusual vocabulary needs separate evaluation.

## Acceptance criteria for language work

1. Supply and test the linguistic resources; do not substitute English patterns.
2. Provide complete nonempty label/help keys and review translation quality.
3. Document formula provenance and unsupported analyses without inventing
   coefficients merely to produce a number.
4. Test known numeric examples and language-specific positive/negative fixtures.
5. Keep locale formatting at the presentation boundary; JSON numbers stay numeric.
6. Distinguish resource-coverage and dispatch tests from empirical validation.

`tests/test_localization.py` checks defaults, explicit auto detection, label-key
coverage, coefficient dispatch and number formatting. Existing linguistic and
mathematical suites provide additional fixtures. These tests alone do not
establish a language-wide accuracy percentage.
