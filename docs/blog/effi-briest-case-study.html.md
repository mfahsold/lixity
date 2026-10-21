# A reference corridor from *Effi Briest*: measuring a draft against its own model

Posted 15 October 2026 · 7 minutes · [All articles](index.html)

## The problem with external style rules

Style guides can tell you that a mean sentence length of 12 words is “brisk” and 24 words is “dense”. What they cannot tell you is whether *your* novel already lives at 19, whether chapter 4 broke that pattern on purpose, or whether the break holds for three chapters straight. Fixed norms make every manuscript an exception; a reference built from the manuscript itself is what actually describes change.

## The idea: a corridor from the manuscript's own chapters

Lixity computes, for each style feature (sentence length, staccato share, dialogue share, perception filters, modals, passive voice, nominalisations, adjectives, long words, sentence-start entropy, first-person starts, lexical diversity measures and more), a robust description of the chapters you already wrote: a **median** and a spread derived from the median absolute deviation. From that it derives a **band** — a reference corridor — and reports for every chapter how far it sits outside it.

Two details keep this useful instead of noisy:

- **Noise adjustment.** The distance from the median is divided by a combination of the manuscript's descriptive spread and the chapter feature's estimated standard error (`z*`). A larger estimated error reduces the reported deviation. The spread is not an estimate of uncertainty in the median itself.

- **Multiple comparisons.** Eligible chapter–feature cells enter a Benjamini–Hochberg (or Benjamini–Yekutieli) selection rule. The report also gives an expected-hit count under a standard-normal reference model. That count is not a measured number of false findings, and the probabilities used for prose features have not been calibrated ([methods](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md)).

## Walkthrough: the public example

Open the [Effi Briest case study](../examples/effi-briest.html) in the browser. The read-only dashboard contains the novel's opening three chapters; its linked [PDF report](../examples/effi-briest-report.pdf) covers the complete public-domain novel. The two reports use different chapter sets, so their reference baselines need not match. The interactive excerpt shows the three views discussed here:

1. **The chapter map (heatmap).** Rows are chapters, columns are features; colour encodes the noise-adjusted deviation from the manuscript's own reference. Scanning a row tells you which feature moved in that chapter; scanning a column tells you where a feature drifts over the book. A selected set of cells is the FDR set — the rest are visible but unselected.

2. **The style reference (bands).** Each feature shows its corridor, the median tick and the strongest outliers as dots. This is the “what is normal here” view — the part a fixed style rule cannot provide.

3. **The chapter matrix (drift column).** The reference summary of every chapter: words, sentence length, dialogue share, function words, tense, flags and the number of selected deviations.

A useful question is “what changed in this chapter, and was it on purpose?”. Deviations are questions to the text: a chapter that sheds dialogue may be a solitary interior section; a jump in nominalisation may be a documentary letter; a drop in sentence length may be the action scene you intended. These are possible interpretations, not conclusions the measurements establish.

## Try it on your own draft

For a quick reference from the command line:

```
uv tool install --python 3.12 --managed-python lixity
lixity style manuscript.md --json
```

Or open the interactive view: `lixity service start --open`, then choose **Open Project**. The style panels are in the **Manuscript & Analysis** view; the section navigation above the chapters jumps to **Style** directly.

## What it does not say

Linguistic extraction depends on the selected language and its marker lists; the statistical definitions of median, MAD and the selection rules stay the same. Cross-language values are not a common literary norm. Missing standard errors mean that no error estimate is available, not that a measurement is certain. BH and BY have false-discovery guarantees only when their input probabilities and other assumptions are valid. Estimating the reference from the same chapters and applying a normal tail to `z*` does not establish those conditions. Here, the selected cells are an exploratory review list. No deviation is an error, and no result is a quality score.

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](../LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
