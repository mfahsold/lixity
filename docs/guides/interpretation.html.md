# Understand manuscript metrics and style consistency

Lixity describes patterns in the manuscript you provide. Its style reference compares chapters with that manuscript's own baseline. A signal is a reason to inspect a passage in context; it is not an objective quality score or an instruction to rewrite it.

Maintained by the Lixity project · Updated 10 October 2026

## What does consistency measure?

Consistency is the proportion of measured chapter–feature cells whose noise-adjusted deviation stays below the active mild threshold. A cell is one feature in one chapter, such as sentence length in chapter two. This is not simply the percentage of chapters that pass a test.

The baseline uses the chapter median and median absolute deviation (MAD). The default mild threshold is `|z*| < 2.5`; project and session settings can change it. A high percentage indicates fewer threshold crossings in this particular analysis. It does not certify narrative continuity, factual accuracy or literary merit. Constant features may remain within the band, so even a measured 100% needs contextual interpretation.

Retained research sources do not enter this manuscript baseline. An archived source is analyzed against its own chapters (`source_internal`); source–manuscript comparison is a separate, explicit lexical and register report. Travel accounts, monographs and their period or genre labels are evidence and user-supplied context, not an automatic writing standard. Archive integrity checks retained bytes and citations, not historical truth.

## Why does an empty manuscript show “–”?

Since v1.18.0, the dashboard and text style report show a dash when no chapter–feature cells can be measured. This includes empty or heading-only manuscripts and material below the configured chapter minimum. A dash means unavailable, not zero quality or perfect consistency.

For API compatibility, style JSON schema version 4 retains the historical numeric `consistency` value. The new `measured_cells` field identifies the supporting count. When it is zero, the retained value `1.0` is a compatibility sentinel and must not be displayed as 100%. Older JSON without the field cannot establish availability from that number alone.

## Compare scenes within a register

The Scenes & style registers view measures scenes separately. Assign registers and target ranges in project settings; each register has its own manuscript-only median. Counts and approximate standard errors show the data behind the values. Targets are your choices, not automatic writing rules. [Set up scene comparisons](../USAGE.md#scene-registers-and-project-targets).

## How much text is enough?

A token floor is an implementation policy, not a quality threshold. Maas remains defined for repetition: 100 repetitions of one token give `maas_a2 = 0.5`. Guiraud `V/√N` still depends on length and corpus composition. Flesch-family values can fall outside 0–100; they estimate surface structure, not reader understanding.

The showing/telling panel displays “–” with an explanation when there are fewer than three chapters or no comparative signals. Numeric fallback zeros remain in JSON for compatibility; they do not justify a ranking.

## A practical review loop

1. Check the manuscript path, selected language and chapter boundaries. English is the default; automatic language detection is an explicit choice.

2. Inspect an unusual chapter in the matrix or style bands. Distinguish raw threshold crossings from the separately computed FDR-selected cells.

3. Open the associated paragraphs and read the passage. A dialogue scene or deliberate change of narrator may explain the pattern.

4. Record your interpretation or a work marker if useful. A diagnostic does not decide whether to edit.

5. After changing the manuscript, compare results using the same analysis version, language and thresholds.

**Since v2.3.0:** an opened paragraph shows the passage first, followed by a compact **Values** disclosure (**Werte** in German). Expand it to inspect the measurements. The matrix, reference bands, dimensions and structural diagnostics share one style area with tabs; links to their existing anchors select the relevant panel. Without JavaScript, all available style panels remain readable.

For example, a synthetic chapter consisting of short dialogue may differ sharply from a descriptive chapter. That contrast can be intentional. Neither moving both toward a common average nor maximizing consistency is a general writing objective.

For a scene or narrative-voice comparison, choose passages with comparable language, scope and discourse mode, then read the source text alongside sentence rhythm, dialogue, vocabulary and register measures. A dialogue-heavy scene and an expository scene need not share a target distribution. Short sentences do not establish dramatic pace, and few perception-filter verbs do not establish immersion. The tools do not identify speakers or validate a narrator's artistic voice.

## Signals and questions for review

Use this reference to connect a measurement with a question to investigate. None of these signals establishes a writing defect.

## Does FDR make a flagged passage objectively wrong?

No. Benjamini–Hochberg and Benjamini–Yekutieli require valid input probabilities to control false discoveries. Lixity's normal-tail probabilities have not been calibrated for comparisons against a baseline estimated from the same chapters. The configured q is therefore not a guarantee of the manuscript's false-alarm rate. A dot is a selection for review, not statistical confirmation or a judgment of prose quality.

## What can tense and pacing labels tell me?

Tense labels, dialogue detection, pacing indicators and showing/telling patterns are language-dependent heuristics. Quoted speech, ambiguous word forms and unconventional punctuation can affect them. A friction rating locates mixed signals; it does not determine whether a flashback or tense change is mistaken. Read the original paragraph before making an editorial decision.

Without explicit scene dividers, `scenes_are_chapters` is true: scene counts are chapter placeholders, not detected narrative transitions. Dialogue shares count quoted and total words with the same configured token regex; quotation marks still do not identify a speaker.

## Read the values as well as the colors

Use the labels, numerical values and selected thresholds alongside a chart's colors. Interface accent colors identify links and controls; analysis colors encode a particular measure or state. A prominent or saturated cell does not necessarily represent a large effect, a reliable estimate or a writing problem. Theme preference does not change the underlying analysis.

Style axes summarize patterns in ranked chapter measurements. Their variance labels describe this rank space, not the variance of raw word counts or a quality score. Only chapters with all required measurements appear in the plot; its footer shows coverage. At least three complete chapters and three varying features are needed, which does not establish a reliable narrator or register classification. See the [methods notes](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md#5-exploratory-style-dimensions).

Display label keys such as `feat_asl` are not API functions or result fields. Read actual model keys: corpus metrics use `asl`, `dialog_ratio` and `filter_density`; chapter metrics use `asl`, `dialog_pct` and `filter_density`. Style feature identifiers appear in `features[].feature` and deviation/FDR entries. Keep the scope and units with each reported value.

## Are the seven languages equally accurate?

The interface and language profiles cover English, German, French, Spanish, Italian, Portuguese and Dutch. English and German have the deepest linguistic heuristics. Complete translations of interface text do not establish equal linguistic accuracy. Mathematical identifiers stay language-neutral; quotations retain their original language.

Read the [estimator definitions and scientific references](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md), [stability and limitations](https://github.com/mfahsold/lixity/blob/main/docs/STABILITY.md), and [JSON contracts](https://github.com/mfahsold/lixity/blob/main/docs/AGENTS.md). For a first run, follow the [synthetic dashboard example](installation.html#first-dashboard).

[Lixity home](../) · [License and commercial use](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md) · [Legal notice](../#impressum)
