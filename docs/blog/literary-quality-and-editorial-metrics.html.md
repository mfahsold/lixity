# What makes a novel read well? Literary research, editorial craft and manuscript data

Published 2 November 2026 · Updated 26 November 2026 · 10 minutes · [Deutsche Fassung](leseguete-und-lektoratsmetriken-de.html)

When an author and an editor sit down with a 350-page manuscript, they rarely argue about a single Flesch readability number. Developmental and line editors ask structural and rhythmic questions instead: *Do the characters sound distinct from the narrator, or does every dialogue turn read like an essay? Where does a chapter's tempo stall because four sentences in a row open with the same pronoun? When a chapter shifts into a long letter or an internal reckoning, is that shift deliberate?*

Literary and reading research can suggest which features to inspect. To track a change during revision, start with passages in the same manuscript and compare them under the same settings. The study of readers’ judgments is a separate question.

<a id="research"></a>

## 1. What empirical studies of novels and editing actually found

These four examples connect editing practice and empirical research to questions you can ask of a manuscript.

- **Developmental and line editing.** One pass asks what a scene does in the book. Another asks whether a tense change or a repeated phrase works in a particular paragraph. A chapter comparison can give you a place to start the second pass.

- **Readers judge books in context.** The Dutch National Reader Survey gathered responses from nearly 14,000 readers about a corpus of 401 novels. The researchers examined how judgments of literariness relate to factors including genre and the reader’s profile. [Koolen, van Dalen-Oskam, van Cranenburgh and Nagelhout (2020)](https://doi.org/10.1016/j.poetic.2020.101439).

- **Narrative language changes over a story.** In a corpus of about 40,000 traditional narratives, Boyd and colleagues measured several word categories associated with setting the scene, moving the plot forward and cognitive tension. These are patterns across texts. Lixity's sentence-length comparison answers a narrower question about a chapter or passage. [Boyd, Blackburn and Pennebaker (2020)](https://doi.org/10.1126/sciadv.aba2196).

- **Cohesion has several dimensions.** Coh-Metrix measures links at several levels of language and discourse. Lixity's local overlap measure asks whether adjacent sentences in a paragraph share an eligible word. Reread those sentences to see what the recurrence does. [Graesser, McNamara, Louwerse and Cai (2004)](https://doi.org/10.3758/BF03195564).

<a id="classic-data"></a>

## 2. Measuring two complete public-domain novels with Lixity

To see how these signals behave on real books rather than toy paragraphs, we can run Lixity on the two complete public-domain novels bundled in the repository: Theodor Fontane's *Effi Briest* (1895, Project Gutenberg #5323, 36 chapters) and Jane Austen's *Pride and Prejudice* (1813, Project Gutenberg #1342, 61 chapters).

| Observable measurement | *Effi Briest* (Fontane, 1895, DE) | *Pride and Prejudice* (Austen, 1813, EN) | What an author or editor checks |
| --- | --- | --- | --- |
| Chapters / prose words | 36 chapters · 95,449 words | 61 chapters · 117,916 words | Overall manuscript scale and chapter granularity |
| Lexical diversity (MTLD / HD-D) | 132.4 / 0.901 | 102.3 / 0.872 | Vocabulary breadth independent of chapter length |
| Overall mean sentence length (ASL) | 15.31 words/sentence | 20.15 words/sentence | Baseline sentence span across the whole book |
| Short-sentence share (staccato ≤ 6 words) | 31.7% | 15.6% | Share of brief utterances and rapid beats |
| Quoted-word share & span count | 55.4% (1,875 quoted spans) | 45.2% (1,731 quoted spans) | Balance between quoted speech and narration |
| Short quoted spans (≤ 12 words) | 49.9% of spans (936) | 45.2% of spans (783) | Rapid back-and-forth exchange vs. extended speeches |
| Long quoted spans (≥ 80 words) | 58 spans | 138 spans | Extended monologues or letters inside quotation marks |
| Quoted ASL vs. Narration ASL | 11.20 vs. 21.10 words/sentence | 13.67 vs. 23.39 words/sentence | Whether characters speak in shorter sentences than the narrator |
| Voice contrast (ASL Δ = quotes − narration) | **−9.90 words/sentence** | **−9.73 words/sentence** | Separation between spoken cadence and narrative prose |
| Adjacent sentence overlap (cohesion) | 23.7% of adjacent pairs | 23.6% of adjacent pairs | Within-paragraph content-word chaining from sentence to sentence |
| Repeated sentence starts (runs ≥ 3) | 5 runs across 36 chapters | 21 runs across 61 chapters | Candidates for deliberate anaphora or unintended start monotony |

Look at the **Voice contrast (ASL Δ)** row in both novels. In Fontane's German text and Austen's English text, the measured difference between recognized quotations and unquoted prose is close to **10 words per sentence**:

- In *Effi Briest*, unquoted narration averages **21.10 words per sentence**, while recognized quoted spans average **11.20 words per sentence** (`ASL Δ = −9.90`), and half of all quoted spans (`49.9%`) are 12 words or shorter.

- In *Pride and Prejudice*, unquoted narration averages **23.39 words per sentence**, while quoted spans average **13.67 words per sentence** (`ASL Δ = −9.73`), with `45.2%` short spans.

An `ASL Δ` near zero means the two measured averages are close. If a draft's dialogue feels stiff, read a passage alongside the surrounding prose. Are the sentence shapes and turns of phrase doing the work you want?

<a id="chapter-drills"></a>

## 3. Separating chapter-level counts from editorial readings

Start with what Lixity counted, then return to the chapter to interpret it. Claims about how a wider audience experiences the passage require reader-response evidence. [Evidence levels and limits](https://github.com/mfahsold/lixity/blob/main/docs/STABILITY.md).

### Case A: *Pride and Prejudice* (banter, summary prose, and Darcy's letter)

In Austen's novel, jumping from the **Pacing & scenes** panel to the **Quoted passages** chapter disclosure flags four chapters whose surface counts move away from the novel's baseline:

| Chapter & narrative moment | Quoted share | Short spans (≤ 12 w.) | Quoted ASL | Narration ASL | ASL Δ | Adjacent overlap |
| --- | --- | --- | --- | --- | --- | --- |
| Ch. 1–2: Mr. & Mrs. Bennet's opening banter | 78.8% / 71.2% | 40.6% / 59.4% | 12.87 / 11.36 | 12.00 / 10.45 | +0.87 / +0.91 | 16.0% / 11.5% |
| Ch. 15: Mr. Collins's introduction and courtship | 3.0% | 50.0% | 25.50 | 36.62 | −11.12 | **47.1%** |
| Ch. 35: Darcy's letter to Elizabeth | 87.6% | 0.0% | **27.39** | 26.57 | **+0.81** | 31.7% |
| Ch. 49: Family reaction to Lydia's settlement | 62.5% | **69.5%** | **9.21** | 13.27 | −4.06 | 12.1% |

- **Chapter 35 — count vs. reading:** **What Lixity counts (L0/L1)** is 87.6% of words inside quotation marks, `short_turn_pct` at **0.0%**, and `Quoted ASL` at **27.39 words per sentence** (`ASL Δ = +0.81`). The counts do not identify the genre or speaker. **Returning to the text (L3)** shows that the quoted span is Mr. Darcy's formal letter explaining Wickham and Jane; in Lixity, an author writing an epistolary chapter like this can assign an explicit `epistolary` [chapter register](intentional-registers.html) so its sentence length is reviewed against letter targets rather than dialogue norms.

- **Chapter 15 — count vs. reading:** **What Lixity counts (L0/L1)** is an unquoted narration ASL of **36.62 words** and within-paragraph adjacent sentence overlap of **47.1%** (nearly double the novel's 23.6% mean). That overlap count only records shared lowercased non-function words between consecutive sentences. **Returning to the text (L3)** supplies the editorial context: Austen's summary of Mr. Collins's introduction and designs on Longbourn repeats names and estate terms across adjacent clauses.

- **Chapter 49 — count vs. reading:** **What Lixity counts (L0/L1)** is 69.5% of 59 quoted spans at 12 words or fewer, with quoted ASL at **9.21 words**. **Returning to the text (L3)** shows brief exchanges reacting to news of Lydia and Wickham's settlement; whether that rhythm feels hurried to readers is a separate reader-response question (L4).

### Case B: *Effi Briest* (conversational parlor vs. Innstetten's discovery of the letters)

In Fontane's novel, the same surface counts highlight chapters where quotation share, sentence length and token overlap shift sharply; only returning to the prose connects those counts to Fontane's *Plauderton* or dramatic tension:

| Chapter & narrative moment | Quoted share | Short spans (≤ 12 w.) | Quoted ASL | Narration ASL | ASL Δ | Adjacent overlap |
| --- | --- | --- | --- | --- | --- | --- |
| Ch. 3: Garden preparations and brief exchanges at Hohen-Cremmen | 19.2% | 64.3% | 7.26 | 27.65 | **−20.40** | 33.8% |
| Ch. 10: Arrival in Kessin; Innstetten explains the house | 85.8% | 39.3% | 12.02 | 11.63 | **+0.40** | 22.2% |
| Ch. 26: Discovery of Crampas's letters and duel decision | 25.7% | 66.7% | 9.29 | 29.16 | −19.87 | **46.6%** |
| Ch. 33: Late Berlin scenes and medical advice | 62.5% | **68.4%** | 9.62 | 22.13 | −12.51 | 25.0% |

In **Chapter 26**, **what Lixity counts (L0/L1)** is a surface shift across four measures: recognized quoted words drop to **25.7%** (`Quoted ASL = 9.29` words, `66.7%` of quoted spans ≤ 12 words), unquoted narration averages **29.16 words per sentence** (`ASL Δ = −19.87`), and within-paragraph adjacent sentence overlap reaches **46.6%** — the highest chapter value in the novel (versus `23.7%` overall). Those counts do not prove psychological pressure or that every paragraph “hammers on the same nouns”: overlap only records that consecutive sentences share at least one lowercased non-function word. **Returning to the text (L3 editorial reading)** supplies the narrative context — Innstetten's discovery of Major Crampas's letters and his exchange with Wüllersdorf — and lets a human reader judge how the recurring terms and long unquoted sentences work in that scene; any claim about actual reader experience belongs to empirical reader-response evidence (L4), which surface counts cannot establish.

<a id="workflow"></a>

## 4. An editorial workflow ordered by how authors and editors actually work

To make these signals practical during daily revision, Lixity organizes the **Analysis overview** in the order an author or editor moves through a draft:

1. **Immediate passage check (*Flagged passages* & *Work markers*).** Start with paragraphs that exhibit severe tense friction or open editorial notes, and record whether a passage was kept on purpose, revised, or deferred.

2. **Rhythm and registers (*Pacing & scenes*, *Scenes & style registers*).** Check average sentence length, rule-based closing cues and runs of repeated sentence openings. Compare a letter or flashback with the ranges you assigned to its register.

3. **Voice, dialogue & sentence craft (*Quoted passages*, *Sentence lengths*, *Signal-group comparison*).** Check whether spoken turns have a distinct cadence from narration (`dialogue_asl`, `narration_asl`, `asl_contrast`), inspect short rapid turns (≤ 12 words) versus monologue blocks (≥ 80 words). Then review perception filters, modal verbs, passive cues and noun endings.

4. **Cast & continuity (*Character name mentions*, *Motifs & repetition*).** Track character presence gaps across chapters and catch unintentional 300-word local phrase echoes.

5. **Corpus baseline & reference (*Style* heatmap, Style Passport, 3D Style Space, and *Chapter matrix*).** Compare all chapters side by side against the manuscript's self-calibrated median/MAD corridor.

You can run the new dialogue and pacing reports directly from the CLI or inspect them in the browser dashboard:

```
lixity dialogue samples/effi-briest.md --language de
lixity pacing samples/pride-and-prejudice.md --language en
```

<a id="limits"></a>

## 5. Methodological boundaries: what these numbers do not claim

Every measurement in Lixity is a deterministic rule over surface text, documented in [METHODS.md](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md) and bounded in [STABILITY.md](https://github.com/mfahsold/lixity/blob/main/docs/STABILITY.md):

- **Quoted spans are not speaker turns.** Lixity detects quotation marks using the active language profile. A single utterance interrupted by an unquoted reporting clause (`"Come here," she said, "and shut the gate."`) counts as two shorter quoted spans and leaves the reporting clause in unquoted narration. Quoted letters or quoted thoughts also count as quoted spans unless you inspect them via chapter registers.

- **Lexical overlap is surface token sharing, not semantic coherence.** Adjacent sentence overlap (`sentence_overlap_pct`) checks whether consecutive sentences in a paragraph share at least one lowercased content word (excluding the profile's function-word list). It does not resolve pronouns, synonyms or inflected stems across languages.

- **Repeated sentence openings can be deliberate art.** A run of three or more sentences starting with the same word (`repeated_start_runs`) marks a passage for human inspection; only the author or editor can decide whether it is rhetorical anaphora or unintended monotony.

- **No score is a verdict.** Neither voice contrast, nor lexical diversity, nor cohesion predicts commercial sales or literary merit on its own. They exist to point your eye to the exact chapter and paragraph where your manuscript's voice or rhythm shifts.

If you are weighing these signals against other kinds of manuscript software, the [comparison of manuscript analysis tools](../guides/manuscript-analysis-tools.html) explains what a local, descriptive approach does and does not cover.

**Explore the live reports:**

Open the interactive

[Effi Briest](../examples/effi-briest.html)

and

[Pride and Prejudice](../examples/pride-and-prejudice.html)

examples or the

[Warehouse 4 demo](../demo/report.html)

directly in your browser.

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
