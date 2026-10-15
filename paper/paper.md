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
    orcid: 0000-0000-0000-0000  # TODO: real ORCID before submission
    affiliation: 1
affiliations:
  - name: ROST Services GmbH
    index: 1
date: 14 October 2026
bibliography: paper.bib
---

# Summary

Lixity is an offline, deterministic text-linguistics engine for literary
manuscripts. It reads a Markdown manuscript and reports sentence rhythm
(mean length, standard deviation, staccato and cascade shares, sentence-start
entropy), lexical diversity (HD-D and MTLD [@mccarthy2010mtld], MATTR [@covington2010mattr], Maas, Yule's K, TTR),
language-calibrated readability for seven languages [@flesch1948yardstick], dialogue share,
paragraph-level heuristic tense profiles, and a **self-calibrating style
reference**: each chapter is compared against the manuscript's own robust
median/MAD baseline, with noise-adjusted deviations (`z*`), nominal
Benjamini-Hochberg or Benjamini-Yekutieli selections [@benjamini1995fdr], and ordinal effect
sizes [@cliff1993dominance]. Exploratory structural diagnostics (guarded changepoints, Mann-Kendall
trends [@kendall1938rank], robust scales, distribution distances, keyness and co-occurrence
tails) describe *where* a manuscript changes, not whether it is good.

The same pipeline drives a command-line interface, a JSON/Python API, a
single-file interactive HTML dashboard and three PDF layouts (A4 analysis
report, A5 reading copy, 30×60 submission sheet) composed in pure Python
without a browser or converter. An experimental research workspace stores
sources, quotations, claims and author decisions in a local, append-only
archive with cryptographic snapshot guards, so that scholarly evidence stays
next to the writing decision it informed.

# Statement of need

Authors, editors and small research projects can measure their texts with
cloud grammar checkers, corpus query suites or research stylometry packages,
but none of these combines four properties that literary revision actually
needs:

1. **Self-calibration instead of external norms.** Fixed readability or
   style conventions cannot know a manuscript's own voice. Lixity builds the
   reference from the manuscript itself (robust median/MAD) and reports how
   uncertain each measurement is.
2. **Paragraph-level evidence.** Every number can be traced to the passage
   that produced it; tense flags and deviations open the source lines instead
   of a score without context.
3. **Local, deterministic operation.** No account, no upload and no cloud
   inference: fixed text and settings produce identical output, which makes
   results reproducible for case studies and review.
4. **Evidence beside the decision.** The optional research archive links
   quotations to claims and author decisions with exact revision pins, so a
   writing choice can be revisited together with the sources behind it.

Lixity deliberately does **not** attempt authorship attribution, automatic
error correction or a quality verdict. Its heuristics are documented,
language-specific and comparable only within one language; the interface
states these limits instead of hiding them.

# State of the field

Grammar and style assistants (e.g. LanguageTool, ProWritingAid) focus on
rule-based corrections and offer limited quantitative calibration. Corpus
tools (AntConc, Voyant, Sketch Engine) provide powerful counting and
concordancing but no manuscript-relative reference and no tense profiling.
Research stylometry packages such as `stylo` [@eder2016stylometry] are excellent for authorship
studies (e.g. Burrows's Delta [@burrows2002delta]) but assume an R workflow and a multi-text corpus rather than one
manuscript under revision. Lixity fills the gap between these worlds: one
manuscript, its own baseline, paragraph-level reading aids, and interfaces
(CLI, API, dashboard, PDF) that a single author can use without a research
environment. Lixity's JSON contracts (`analyze` schema 2, `style` schema 4)
and its archived research records (schemas 1–7) are versioned so that
measurements can be recomputed and compared across revisions.

# Software design

Lixity is pure Python 3.10+ with a small dependency set (pydantic, rich,
orjson). All views share one pipeline, so the CLI, the Python API, the
dashboard and the PDF composer cannot diverge in what they measure. Feature
definitions live in per-language profiles; missing coverage degrades to
`generic` instead of guessing. Statistical primitives are centralized in one
module to keep the API and the reports consistent. The test suite covers the
statistics, storage guards, localization packs, PDF pagination and the
rendered dashboard; browser suites exercise the published surfaces. The
software is released under AGPL-3.0-or-later with an optional commercial
license for closed-source integrations, and package metadata, release
artifacts and citation metadata are maintained in the repository.

# Research impact

Lixity was developed while writing a debut novel and has been used to review
six-chapter and full-novel drafts for rhythm, tense consistency and dialogue
distribution. For digital-humanities work, its paragraph-level tense
profiles, self-calibrating bands and versioned JSON make small stylistic
case studies reproducible without a corpus infrastructure. The PDF report
layout is designed to be archived alongside the analysis settings that
produced it, and the research archive keeps quotations and claims citable
with exact source and revision pins. Deposits of released versions receive
DOIs via Zenodo (concept DOI 10.5281/zenodo.23390297) so that a specific
measurement can be cited.

# AI usage disclosure

Generative AI tools were used during development under continuous human
review:

- **Tools and scope.** AI coding assistants were used in a coding-agent
  environment for code generation and refactoring, test scaffolding,
  documentation drafting and copy-editing; paper text was drafted with AI
  assistance. <!-- TODO maintainer before submission: name the tools/models and
  approximate versions/periods, e.g. "Anthropic Claude via OpenCode (2025-2026),
  OpenAI GPT via ..., GitHub Copilot ...". -->
- **Human review.** The maintainer reviewed, edited and validated every
  AI-assisted output, ran the test and browser suites before releases, and made
  the design decisions, measurement definitions and release choices.
- **Correspondence.** Communication with JOSS editors and reviewers is written
  by the maintainer (no AI assistance, unless translation is needed and
  disclosed).

# Acknowledgements

Thanks to the Project Gutenberg editions used as public-domain example texts.

# References
