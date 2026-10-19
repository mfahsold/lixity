# Finding tense switches in a novel — and deciding which ones matter

Posted 15 October 2026 · 6 minutes · [Blog](index.html)

## A tense break is rarely a typo

The base tense of a novel is a choice. Past tense can suggest a narrator looking back; present tense can bring a scene closer. A shift between them may be deliberate, accidental or part of quoted speech. The useful question is whether the shift does what you intended in this passage. A list of candidate passages can give that review a starting point.

## What Lixity shows you

Lixity reads your manuscript on your own computer and assigns supported body paragraphs and list items a heuristic tense reading: **present**, **past**, **mixed** or **neutral**. It also assigns a tense-friction rating from 0 to 3. These paragraph profiles omit blockquotes, code and headings; they do not parse every grammatical construction.

Out of that come two lists, and they answer different questions:

- **Flagged passages** (rating 2 or higher by default) are candidates for a second look.

- **The chapter line** summarizes the chapter's dominant tense markers. It supplies a comparison for the paragraph, rather than determining how a reader experiences the scene.

One honest sentence: these readings come from verb forms and markers, not from a grammar parse. Dialogue, nested clauses and reported speech all shape the counts. That is exactly why the last step is always a person reading the passage — not a number.

## The review loop, step by step

Start with the [read-only synthetic demo](../demo/report.html) if you want to see the controls before installing. For your own manuscript, use the local project workflow:

1. **Install and open.** `uv tool install --python 3.12 --managed-python lixity`, then `lixity service start --open` and choose **Open Project** for your manuscript folder. (Windows, macOS and Linux are covered in the [installation guide](../guides/installation.html).) If you just want to see the loop first: the [demo report](../demo/report.html) opens in your browser, no install.

2. **Start with the review panel.** **Start your review** offers **Open passage** (the first paragraph above your threshold, in reading order), **Explore chapters** and **Open sentence rhythm**.

3. **Work the flagged list.** The **Flagged passages** panel lists every paragraph at or above your threshold, sorted by strength and line. Click a row and the paragraph opens, the page scrolls, the passage flashes — with the “flagged only” filter set, so the rest of the page gets out of your way.

4. **Read the context before you judge.** Inside the opened paragraph, **Values** shows the source lines and the measurements. Then look at the scene: is the switch carried by a letter, a memory, an interior monologue? The chapter line in the header shows you the norm you are comparing against.

5. **Write your decision where you read it.** The marker buttons (**+ To-do**, **+ Check**, **+ Attention**) leave a review note in the manuscript as a Markdown comment. It stays invisible while you read and shows up later in the **Work markers** panel.

## When a switch is on purpose

A high rating measures a change, not a mistake. These cases are usually intentional:

- **Letters and documents.** A quoted letter often shifts into present or into a different register; readers expect the frame to change.

- **Flashbacks and frame stories.** Moving from present to past may be exactly what the structure asked for.

- **Free indirect speech.** A character’s inner voice can pull the tense along — effective, but easy to overuse.

- **A scene turn.** One present-tense paragraph at the end of a past-tense chapter can be a strong, deliberate accent.

The flagged list decides none of this. It can bring a pattern to your attention, but it can also miss tense changes or flag an intentional passage. Read the surrounding prose before making a decision.

## What this can and cannot do

Verb-form patterns miss irony, ellipsis and unusual syntax. Dialogue and reported speech affect the counts. Chapters below 100 words are excluded from the manuscript's chapter-style comparisons; that separate size floor does not validate a paragraph's tense flag. The `flag_min_severity` setting (1–3) controls which paragraph ratings appear in the list; its default is 2. Lixity does not automatically rewrite prose. Saving a work marker is an explicit write of a Markdown comment in the native project; the published examples are read-only. The [interpretation guide](../guides/interpretation.html) and the [methods document](https://github.com/mfahsold/lixity/blob/main/docs/METHODS.md) explain the details.

## Try it without installing

The [demo report](../demo/report.html) is made from invented text and opens in your browser. The interactive [Effi Briest](../examples/effi-briest.html) and [Pride and Prejudice](../examples/pride-and-prejudice.html) dashboards show the opening three chapters. Each example links to a PDF analysis of the complete public-domain novel. For your own manuscript, install, open the project and review one chapter.

[Lixity home](../) · [Blog](index.html) · [Report a reproducible issue](https://github.com/mfahsold/lixity/issues) · [Legal notice](../#impressum)
