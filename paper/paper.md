---
title: "Lixity: local, self-calibrating text linguistics for literary manuscripts"
tags:
  - Python
  - stylometry
  - digital humanities
  - computational linguistics
  - text analysis
authors:
  - name: Matthias Fahsold
    affiliation: 1
affiliations:
  - name: ROST Services GmbH
    index: 1
date: 24 November 2026
bibliography: paper.bib
---

# Summary

Lixity is a local tool for studying how the language of a literary manuscript
changes across chapters and revisions. For example, a researcher can identify a
chapter with unusually short sentences for that work and inspect the passages
behind the comparison. Its default analysis runs offline and deterministically.
It reads a Markdown manuscript and reports sentence rhythm
(mean length, standard deviation, staccato and cascade shares, sentence-start
entropy), lexical diversity (HD-D and MTLD [@mccarthy2010mtld], MATTR [@covington2010mattr], Maas, Yule's K, TTR),
language-calibrated readability for seven languages [@flesch1948yardstick], dialogue share,
paragraph-level heuristic tense profiles, and a **self-calibrating style
reference**: each chapter is compared against the manuscript's own robust
median/MAD baseline, with noise-adjusted deviations (`z*`), nominal
false-discovery-rate selections [@benjamini1995fdr], and ordinal effect
sizes [@cliff1993dominance]. Exploratory structural diagnostics (guarded changepoints, Mann-Kendall
trends [@kendall1938rank], robust scales, distribution distances, keyness and co-occurrence
tails) describe *where* a manuscript changes, not whether it is good.

The same pipeline supplies the command-line interface, Python API and local
browser workspace. Lixity can export an interactive HTML report and PDFs,
including an analysis report and a reading copy. Its research workspace stores
sources, quotations, claims and author decisions in a local, append-only
archive with cryptographic snapshot guards, so that scholarly evidence stays
next to the writing decision it informed.

# Statement of need

Literary revision and small digital-humanities studies can both require a
chapter comparison within one work, a way back to the source passage and
enough information to repeat the calculation later. Lixity combines these
tasks in one workflow:

1. **Self-calibration instead of external norms.** Fixed readability or
   style conventions cannot know a manuscript's own voice. Lixity builds the
   reference from the manuscript itself (robust median/MAD) and reports how
   uncertain each measurement is.
2. **Paragraph-level evidence.** Tense cues and supported reader measurements
   can open their source lines. The interface reports unavailable evidence
   explicitly when a result cannot be mapped to a passage.
3. **Local, deterministic operation.** No account, no upload and no cloud
   inference: fixed text and settings produce identical output, which makes
   results reproducible for case studies and review.
4. **Evidence beside the decision.** The optional research archive links
   quotations to claims and author decisions with exact revision pins, so a
   writing choice can be revisited together with the sources behind it.

Lixity supports close reading and exploratory measurement. Its language-specific
heuristics are documented, and manuscript-relative comparisons use one analysis
language and a common set of settings.

# State of the field

Corpus tools such as AntConc support concordance and word-distribution
queries; research stylometry packages such as `stylo` [@eder2016stylometry]
support comparative studies across texts, including authorship studies based
on Burrows's Delta [@burrows2002delta]. Lixity uses the chapters of an evolving
manuscript as its comparison units. Existing concordance or stylometry
functions could provide some of these measurements. The separate package
supports the workflow of retaining a local source revision, configuring a
within-work comparison, and returning from the result to the corresponding
passage and saved research. Its JSON reports and research archive use
documented, independently versioned formats.

# Software design

The released analysis engine runs on Python 3.10+. The CLI, Python API,
dashboard and PDF composer reuse the analysis pipeline. Explicit language
profiles give a repeatable default configuration and support narrower
heuristic coverage where evidence is limited. The manuscript-relative
reference offers context for local differences, at the cost of comparing
against chapters that can themselves contain intentional changes in register.
The default engine favors inspectable patterns and leaves grammatical or
editorial interpretation to the reader. The test suite covers the
statistics, storage guards, localization packs, PDF pagination and the
rendered dashboard; browser suites exercise the published surfaces. The
software is released under AGPL-3.0-or-later with an optional commercial
license for closed-source integrations, and package metadata, release
artifacts and citation metadata are maintained in the repository.

# Research impact statement

The maintainer used Lixity to review the rhythm, tense cues and quotation
distribution of drafts during writing. An openly documented exploratory
analysis uses the Project Gutenberg editions of Theodor Fontane's *Effi Briest*
and Jane Austen's *Pride and Prejudice*. It applies the same question to each
work: how do average sentence lengths differ inside recognized quotation
spans and in the surrounding prose? The [case study][case-study] describes
the measures and their limits. The tagged [sample corpus][samples] includes
the input Markdown and its provenance. The `dialogue` command emits the
chapter and corpus values as JSON with an explicit analysis language, and
[the v0.9.2 archive][release-doi] identifies the software version needed to
repeat the analysis. These measurements describe the two editions under
their respective language profiles. They do not establish a quality target or
a genre-wide norm. The case study is maintainer-led.

[case-study]: https://lixity.de/blog/literary-quality-and-editorial-metrics.html#classic-data
[samples]: https://github.com/mfahsold/lixity/tree/v0.9.2/samples
[release-doi]: https://doi.org/10.5281/zenodo.24514421

# AI usage disclosure

Generative AI tools were used during development and while preparing this
paper. **Tools and places of use:** OpenAI Codex (code drafts, refactoring,
test scaffolding, and copy-editing of this paper draft); GitHub Copilot (code
and documentation, recorded as a `Co-authored-by` trailer on ten commits
between 23 and 30 October 2026); Cursor (editor assistance and repository
rules); opencode (one early commit, 23 September 2026). The model versions
behind these tools were not recorded in the repository at the time of use.
The measurements and examples reported here come from the deterministic
analysis engine shipped with the release, not from a language model.

**Review:** The author reviewed, edited and validated every AI-assisted
output, checked the references and the reported values against the released
version, and made the design decisions, the scope and the conclusions of this
paper. The author remains responsible for the accuracy, originality,
licensing and ethical compliance of the submitted material.

# Acknowledgements

Thanks to the Project Gutenberg editions used as public-domain example texts.

# Conflict of interest and funding

The author is employed by ROST Services GmbH, which offers commercial
licences for Lixity alongside the AGPL-3.0-or-later release. This dual
licensing is a commercial interest that the author discloses; it did not
determine the measurements, the choice of examples or the conclusions of this
paper. The work received no project-specific third-party funding, and no
funder reviewed the manuscript before submission.

# References
