# Why is this passage marked?

By [Matthias Fahsold](https://github.com/mfahsold) · Published 26 October 2026 · Updated 27 October 2026 · 5 minutes

**Lixity 0.7.6:** this walkthrough follows the current manuscript and research review workflow. The local app keeps independent project views; optional installed grammar models extend tense analysis, and the optional Qwen3-TTS 1.7B worker shares listening profiles with the CLI. Existing Piper profiles require explicit, backed-up migration. See the [release notes](../releases/v0.7.6.md), [validation limits](../STABILITY.md#grammatical-tense) and [installation guide](../guides/installation.html).

A paragraph is marked while the toolbar shows a different measurement. A research panel still refers to a scene that has already scrolled away. The reader has to work out what the software means before returning to the manuscript.

That is an editorial problem as well as an interface problem. An author needs the reason for reviewing a passage. An editor needs to explain an observation in terms the author can examine. A coloured edge alone supplies neither.

The useful loop is short: **read the passage, inspect the reason, make a contextual decision, return to the text.** Lixity brings manuscript analysis and linked research into that loop. The current workflow makes their separate questions clearer.

## 1. Ask what the signal actually measures

The default tense-pattern signal counts heuristic markers of present and past forms. It can indicate a mixture within a paragraph or a change from the previous paragraph. The selected measurement layer answers its own question, such as sentence length or literal perception-word matches. Those are separate observations.

Optional installed syntax models instead compose contextual verb groups. Their evidence retains the model identity, quotation scope and unresolved forms. A controlled construction check is different from accuracy on a literary manuscript; the [configuration guide](../USAGE.md#grammatical-tense) and [measured limits](../STABILITY.md#grammatical-tense) explain the distinction.

Consider this invented contrast:

Mara closed the gate and pocketed the key. Every morning, the porter checks the seal and writes down the number.

The second sentence could describe a standing routine within a past-tense narrative. It could also be an accidental change of tense during revision. This example illustrates the editorial distinction; it is not a claim that these two short sentences meet a particular detection threshold.

The software cannot infer that intention reliably from marker counts. A useful explanation exposes the counts, their heuristic limits and the exact passage. The author or editor supplies the reading that turns them into a decision.

In the local app, the labelled **Tense pattern · review** action opens that explanation directly. It is separate from **Explain measurement**, which inspects the selected analysis layer. A change of rhythm, voice or tense can be a reason to preserve a passage.

## 2. Keep the context attached to the chosen passage

Following research should make the scene easier to understand. A dossier from a previous chapter becomes distracting when it appears to explain the paragraph currently being read.

The reader retires the old passage context on an explicit chapter or passage change. Deliberately continuing through the manuscript beyond an inspected paragraph also closes its old context. Scrolling within the open research tool keeps that tool available. Switching tools uses the passage that was explicitly requested.

The return control retains the destination and one action. Record titles and revision metadata belong with the record being inspected. Repeating them in the primary navigation makes a short route harder to recognise.

On a narrow screen, opening a tool can move it above the prose. A useful return therefore restores the reading position and keyboard focus as well as selecting the Manuscript view. These behaviours are checked with synthetic projects; passing those checks does not substitute for feedback from people reading a long draft.

## 3. Separate the current record from the version used

Suppose two quotations refer to the same historical dossier, and one quotation was linked to an earlier version of a claim. A later correction should remain discoverable alongside the exact version used at the time.

The passage context shows a current dossier or claim once within its group. Distinct **Linked version** controls preserve the earlier pins. Each version's association disclosure retains its own quotation, confidence and dossier revision; multiple versions have visible version labels before they are expanded. Dossier-wide decisions appear once beside their related claims.

This answers two different reading questions: what does the record say now, and what was linked to this sentence? A saved association records that connection. It does not automatically verify the claim, accept a new version or establish that a decision has been incorporated into the prose.

The backend prepares these summaries from one archive snapshot for both the live reader and an offline review export. Opening the context no longer asks the browser to assemble several independently fetched record versions. Full records remain available through their explicit viewers. The [automation contracts](../AGENTS.md) document the versioned data model.

## 4. Turn the observation into an editorial conversation

1. **Read around the mark.** Identify who is speaking, the time frame and the passage's purpose.

2. **Inspect the stated reason.** Keep a counted word or sentence separate from its chapter comparison and from saved research.

3. **Follow the evidence when it matters.** Read the retained source passage and the author's explicit decision. Check which versions were linked.

4. **Explain the judgement.** A useful note can say why a tense change works, why a repeated phrase deserves discussion, or which detail needs another source.

5. **Prepare the right copy.** Use an editorial PDF or a fixed review website for a discussion. A curated companion shares selected background material. These are reading exports rather than live collaborative editing.

Built-in manuscript analysis runs locally, and Lixity does not automatically rewrite prose. Markdown and plain-text manuscripts are supported; Word/DOCX and Scrivener documents need conversion. Optional integrations have their own [data boundaries](../research/USAGE.md).

## Try one question

The invented Warehouse 4 project follows a suspicious harbour delivery through six short English chapters. A preliminary source account and its correction place an event differently; the author keeps both and records a creative decision.

[Follow the passage and its research](../guides/first-look.html#decision) [Einführung auf Deutsch](../guides/first-look-de.html#recherche)

The public example needs no account or manuscript upload. It is a fixed, read-only snapshot, so the controls visible there depend on the deployed build. For another concrete reading question, explore [nearby repeated phrases](local-word-echoes.html) or read [why a chapter may sound different on purpose](intentional-registers.html).

[All guides](../#guides)[Articles](index.html)[Source code](https://github.com/mfahsold/lixity)[License](../LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
