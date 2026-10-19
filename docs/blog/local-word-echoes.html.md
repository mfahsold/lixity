# Finding repeated phrases close together

By [Matthias Fahsold](https://github.com/mfahsold) · Published 19 October 2026 · 4 minutes

A phrase used four times across a novel may be unobtrusive. The same phrase used three times in one short passage may catch the ear. Lixity's **local repetition echoes** locate this second pattern: repeated word sequences inside a bounded span of chapter prose. The result is a place to listen again, with a count you can check.

Repetition can make a refrain, sustain a character's vocabulary or give a sentence its rhythm. An echo supplies no instruction to replace words. Read the passage aloud and ask whether hearing that phrase again produces the effect you intended.

## Get an echo report

In Lixity 0.5.0, run the existing motif report against a Markdown manuscript:

```
lixity motifs manuscript.md --language en --json
```

Look for `echoes` in the JSON result. By default, it finds sequences of three words occurring at least twice within 300 words, separately for each chapter. Each row supplies the phrase, chapter number, local count and first and last word positions. The words are lowercased and punctuation is discarded; a sequence can cross a sentence boundary. Sequences consisting entirely of function words or stopwords are skipped.

## Count one example yourself

Save this literal synthetic text as `manuscript.md`. The fragments keep the counting easy; they are a demonstration, with no claim to be polished prose.

```
## Bell

Bright copper bell.
Beyond the valley a narrow footpath crossed quiet fields and led past empty cottages toward the dark and distant ridge.
Bright copper bell. Bright copper bell. Bright copper bell.
```

The heading is outside the chapter's prose count. The first phrase occupies words 1–3; the following sentence has 20 words. The final three occurrences start at words 24, 27 and 30. Here is the result for `bright copper bell`:

| Window | Local count | First word | Last word |
| --- | --- | --- | --- |
| 300 words (default) | 4 | 1 | 32 |
| 10 words (Python example) | 3 | 24 | 32 |

The shorter window retains the **cluster containing the most occurrences**, rather than the first pair it encounters. Its count excludes the distant opening occurrence. Equal counts use the earliest cluster. For this small-window demonstration, the lower-level Python call is:

```
from lixity.models import CorpusConfig
from lixity.motifs import motif_report

report = motif_report(
    text, config=CorpusConfig(language="en"), echo_window=10,
)
```

Here, `text` contains the exact Markdown above. The command-line report uses the 300-word default; `echo_window` is a Python argument, with no corresponding CLI flag or project setting.

The complete last occurrence must fit inside the window. For `Bright copper bell. Blue river flows. Bright copper bell.`, both occurrences occupy words 1–9. A nine-word window admits the pair; an eight-word window does not. `last_word` is the last word of the final occurrence, with positions counted from 1.

## One repeated passage can produce several phrases

Consider a second, separate synthetic chapter:

```
## Lantern

The bright silver lantern. The bright silver lantern.
```

Both `the bright silver` and `bright silver lantern` repeat. Their actual occurrences overlap by two tokens in each copy of the same passage. Lixity keeps one representative: `the bright silver`, count 2, words 1–7. The reported bounds describe that representative, rather than the whole four-word expression.

This deduplication requires at least two overlapping tokens in the recorded occurrences. Shared vocabulary alone is insufficient. In this third example:

```
## Doors

Red wooden door. Appears. Red wooden door. Closes.
Red metal door. Opens. Red metal door.
```

`red wooden door` remains a separate echo from `red metal door`. Each occurs twice, at words 1–7 and 9–15 respectively. They share words, but their occurrences describe different passages.

## Turn the count into a reading decision

Locate the reported chapter and read through the span, including its surrounding sentences. Ask whether the recurrence is audible, whether it belongs to the speaker and whether its spacing supports the scene. Sometimes the repeated noun is clearer than a synonym. Sometimes the third occurrence gives away an accidental habit.

The detector matches literal token sequences. It does not recognize every paraphrase, infer thematic significance or judge rhetorical intention. One row describes the strongest local cluster for that term in that chapter; it is not an inventory of every cluster. The report also caps the returned list. A missing row therefore does not establish that the prose is free of repetition.

Try the short Bell fixture first, then inspect one result in your own draft. The [local echo reference](https://github.com/mfahsold/lixity/blob/main/docs/USAGE.md#local-repetition-echoes) explains the returned fields and lower-level parameters when you need more detail.

[Lixity home](../) · [Blog](index.html) · [Report a reproducible issue](https://github.com/mfahsold/lixity/issues) · [Legal notice](../#impressum)
