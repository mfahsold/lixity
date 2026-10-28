# A three-minute first look

Start with one question: does chapter 2's shorter rhythm fit its action?

[Kurze Einführung auf Deutsch](first-look-de.html)

Updated 23 October 2026

This walkthrough follows the generated demo. It uses the same reading website export available in **Project actions → Reading website**. Its manuscript, analysis and chosen Research are a fixed snapshot; importing and saving require a local project. See [how to make your own reading website](research-pdf.html#reading-website).

## 1. Open the example and read a chapter

[Open the demo project](../demo/report.html)

*The Crate at Warehouse 4* has six invented English chapters. No installation, account or upload is needed. Choose **Inspect chapter 2** in the demo's opening task card. It uses the application's actual manuscript navigation and sentence-length controls; no changes can be saved.

[Video walkthrough](../videos/analysis-review.mp4)

*Warehouse 4: explore a passage and compare its chapter. Recorded with v0.7.5 using the same app controls as the demo; current-main annotation styling may differ.*

## 2. Inspect one difference

A board moved. Mara turned. The crate tipped towards the drain.

1. Read the first paragraph of **The Loose Board**. What is Mara doing, and where do you pause?

2. Choose its **… → Explore passage → Explain measurement**. Inspect the actual sentences and their word counts. Turn on **Counted text** if you want marks in the prose.

3. Read chapter 1's harbour description using the **opening chapter** link in the task card. Compare the reading experience, not just the averages.

**A possible decision:** keep the short beats because they separate physical actions. Or, if the scene sounds mechanically chopped when read aloud, try joining an action to its consequence in your own draft. The measurement explains the difference; it cannot decide whether the rhythm works. These short synthetic chapters are not a calibration corpus.

You have completed the first check when you can explain the contrast in the text. Stop there, or follow the research trail below. [Use the same workflow with your manuscript](installation.html).

**More controls, marks and chapter comparisons**

Choose a paragraph's **… → Explore passage** to open its right context. **Explain measurement** opens the counted text; **Research for this passage** follows the passage’s explicit links. The separate **Analysis** switch shows diagnostics across the manuscript; the **Passage** inspector works with Analysis On or Off. Use **Analysis overview** to compare sentence rhythm in the setting and action chapters, then **Back to passage** to resume reading.

**In the read-only demo:** turn **Analysis** on. The first switch-on selects **Sentence length** unless you already saved a metric choice. Choose the metric with the directly visible **Measure** selector; **Counted text** and **Paragraph comparison** are independent switches. Violet underlines identify counted spans. Blue/orange raw-value markers with down/up arrows compare notable paragraphs with their chapter, adding only a subtle paragraph-edge wash. Hover or tap a mark for its explanation; the compact card puts the quotation/count before a separate paragraph comparison. **Read these marks** keeps the method collapsed until opened.

**Since v0.7.6:** neutral dotted marks and a book-icon **Research** count identify saved research links. Their pattern stays distinct from solid counted-text underlines and the paragraph comparison colors, including with Analysis Off. Open the Research control to follow the exact saved connection; this is an author association, not an automatic fact check.

**Explore passage → Explain measurement** also works by keyboard or right-click with Analysis Off; it enables Analysis while preserving both display-switch preferences. Escape closes the explanation. A sentence's word count and its paragraph's comparison are different measurements. Deliberate **None** and either disabled switch survive Off/On and reload. **Focus reading** hides both displays temporarily and restores the previous choices on exit.

**Since v0.7.3:** expand **Manuscript measurements** for the secondary numbers, then collapse the same summary to return to the compact overview. A linked scene title reveals its detailed **Scene measurements**; both disclosure levels can be closed again. The passage return keeps your earlier reading context.

Ask what changed: the kind of scene, what the character is doing, or how the sentences are arranged. These short chapters demonstrate a workflow; their numbers are not a quality verdict. [The mark key](interpretation.html#analysis-marks) explains the colors and scopes. [Reader controls and coverage](../USAGE.md#reading-paragraphs) covers text size, focus, keyboard access and supported formatting.

## 3. Follow a quotation into research

Someone had tried the eastern gate of Warehouse 4.

**In the read-only demo:** this opening quotation has an explicitly saved association. Follow it from the manuscript:

1. At the opening paragraph, choose **… → Explore passage → Research for this passage**. The right context shows its linked claim and dossier while the text stays visible.

2. Open a title to read the current entry and its sources, or choose **Linked version** for the exact earlier version used by the association. **Versions** expands its history without changing the entry. A retained source and an authored claim are separate records; the association does not establish factual truth.

3. Close the viewer and use **Back to passage** to resume reading. On narrow screens the context sits above the text; its close button or Escape returns to the paragraph.

**Explore dossiers and review**

In [**Research → Dossiers**](../demo/report.html#research-manager), open **Warehouse 4 case notes**. Its **Sections** list follows the actual headings; close and reopen it as needed. Choose **Dossier alongside** to keep the dossier beside the manuscript.

From an open dossier, **Back to dossier** restores its saved version and reading position after you follow a connection. **Review** also lists the saved quotation; **Go to manuscript passage** follows its exact text match. [Reader guidance](../USAGE.md#reading-paragraphs) covers controls and keyboard shortcuts.

People, events and journeys are fictional. The historical images do not verify them. Maps in this website use local sketches and geographic shapes without requesting online map tiles. [Sources and PDF copies](research-pdf.html) explains retention and saving in the local app.

## Read with selected analysis

Open the [synthetic reading copy](../demo/reader/), choose **Analysis** above the story, and inspect its chapter overview. Choose **Back to reading copy** to return to the story and its selected background. This example deliberately includes chapter figures for all six chapters; reading progress does not hide analysis. In your own export, select only the analysis you want to share and use a chapter cap to omit later content.

## 4. Choose a PDF copy

Use the direct PDF links below or in the demo page; the exported website does not generate new PDFs. Compare the same manuscript as an [editorial copy](../demo/warehouse-4-editor.pdf), [reading copy](../demo/warehouse-4-book.pdf), [submission sheets](../demo/warehouse-4-sheet.pdf) or [analysis report](../demo/warehouse-4-report.pdf). The [PDF guide](research-pdf.html#manuscript-export) explains their purposes and limits.

## Use your own project

Manuscript input supports Markdown (`.md`, `.markdown`) and plain text (`.txt`). Convert Word/DOCX or Scrivener documents before import. PDFs can be retained separately as Research sources.

[Install the local app](installation.html), then open your project or preview a manuscript import. Analysis runs on your computer. JavaScript enables the demo's interactive controls; manuscript text, tables, credits and PDF links remain readable without it.

In the local app, open **Project** for a read-only overview of the selected manuscript, research folder and existing outputs. It inspects metadata without rebuilding analysis; output source and generation history remain unknown. The exported demo has no local project-folder view. [Project inspection and CLI](../USAGE.md#inspect-project-structure).

Lixity is open source under AGPL-3.0-or-later. Writing and self-publishing need no extra permission; a separate written commercial license exists for closed-source integrations. See [licensing](../LICENSING.md).

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](../LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
