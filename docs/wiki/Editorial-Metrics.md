# Understanding editorial metrics

Read a passage before deciding whether a measurement matters. The
[interpretation guide](https://mfahsold.github.io/lixity/guides/interpretation.html)
is the maintained introduction; [Methods](https://mfahsold.github.io/lixity/METHODS.md)
defines formulas and [Stability](https://mfahsold.github.io/lixity/STABILITY.md)
describes validation and limits.

## What a signal means

Some displays compare a passage with its chapter or manuscript; others use
configured thresholds or language-specific formulas. Check the displayed unit,
baseline and active settings. There is no universal z-score rule for every
measure. A strong difference may be intentional, and an unavailable value is not
zero or a favorable result.

| Measure | Use it to ask | It does not establish |
| --- | --- | --- |
| Average sentence length | Where does sentence rhythm change? | A universal ideal length, pacing or quality |
| Tense cues | Which counted forms explain this flag? | Full grammatical parsing or an accidental tense error |
| Dialogue | How much recognized quoted speech appears here? | Who speaks when attribution is unavailable |
| Repetition | Is a nearby recurrence purposeful? | Whether a repeated word should be removed |
| Lexical diversity | How do comparable samples differ? | Text-length independence or vocabulary quality |

FDR adjustments qualify statistical comparisons under their assumptions; they
do not certify meaningful prose differences or eliminate false positives. See
the methods for the scope of each correction. Keep the manuscript, counted-text
examples and coverage warnings in view when making an editorial decision.

[Workspace manual](https://mfahsold.github.io/lixity/WORKSPACE.md) ·
[CLI analysis commands](https://mfahsold.github.io/lixity/USAGE.md#which-command-for-which-question)
