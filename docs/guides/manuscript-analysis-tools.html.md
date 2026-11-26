# Which manuscript analysis tool fits your work?

Pick a passage and decide what you want to learn about it. You might look for a repeated phrase, reconsider the order of a scene or prepare a draft for an editor. Try the same passage in the tools that support that task.

Updated 26 November 2026

<a id="families"></a>

## Choose a tool by task

| Your task | Examples to evaluate | What to try |
| --- | --- | --- |
| Polish sentences or review an entire draft | [ProWritingAid](https://help.prowritingaid.com/article/318-what-is-manuscript-analysis), [AutoCrit](https://www.autocrit.com/story-analyzer-plus/), [Papyrus](https://papyrus.de/features/style-analysis) | Open a passage-level suggestion and review the same issue across the book. |
| Draft and organize chapters | [Scrivener](https://www.literatureandlatte.com/scrivener/overview), [Papyrus](https://papyrus.de/) | Move a scene, compare an earlier version and export the draft. |
| Review story structure | [Fictionary](https://fictionary.co/writers-software/) | Tag a scene, inspect the arc across scenes and check the editorial notes. |
| Collaborate or keep Markdown notes | [Ellipsus](https://help.ellipsus.com/support/solutions/articles/205000067329), [Obsidian](https://obsidian.md/help/data-storage) | Use Ellipsus to review a shared draft and comments. Use Obsidian to link and read notes stored as local files. |
| Explore a collection or run a study | [AntConc](https://www.laurenceanthony.net/software/antconc/), [Voyant](https://docs.voyant-tools.org/docs/tutorial-local.html), [stylo](https://cran.r-project.org/package=stylo) | Inspect a concordance or reproduce a measurement across a collection. Voyant also offers a local server. |
| Review a passage beside its sources | [Lixity](#lixity) | Read the words behind a measurement, revisit a saved quotation and compare an edit with the previous version. |

<a id="checkers"></a>

## Grammar and style review

Use a checker for suggested corrections or feedback on clarity. AutoCrit and ProWritingAid offer reports that cover a manuscript and point to individual passages. Papyrus combines style and readability analysis with book-writing tools. Its chapter chart compares each chapter with the document average and links back to the text. Check the edition you plan to use. ProWritingAid, for example, requires internet access. [AutoCrit reports](https://help.autocrit.com/en/collections/2339242-interpreting-autocrit-results) · [ProWritingAid requirements](https://help.prowritingaid.com/article/99-what-do-i-need-to-use-prowritingaid) · [Papyrus chapter statistics](https://support.papyrusauthor.com/wiki/style-statistics/)

<a id="corpus"></a>

## Explore a collection of texts

Use a corpus tool to compare word frequencies, recurring combinations or passages across a collection. [AntConc](https://www.laurenceanthony.net/software/antconc/) and [Voyant Tools](https://voyant-tools.org/) let you examine words in context. Try a small collection first and see how you can return to the source passage.

<a id="stylometry"></a>

## Run a study from a shell or notebook

Use a statistical or language-processing package for work such as authorship attribution, vocabulary measurement or syntactic annotation. The R package [stylo](https://cran.r-project.org/package=stylo), [spaCy](https://spacy.io/) and [NLTK](https://www.nltk.org/) provide different building blocks. Run a small test with a known input, record the settings and check whether you can reproduce the result.

<a id="story"></a>

## Plan scenes and review structure

Fictionary organizes story elements by scene. Scrivener lets you arrange chapters and scenes and compare a section with an earlier snapshot. If you already draft in another app, export a chapter as `.docx`, Markdown or plain text to review a copy in Lixity. [Fictionary](https://fictionary.co/writers-software/) · [Scrivener](https://www.literatureandlatte.com/scrivener/overview) · [Import a manuscript](installation.html#first-dashboard)

<a id="assistants"></a>

## Review suggestions from an AI assistant

Before sharing a manuscript with an assistant, check the service’s features, costs and data-handling terms. Read any proposed change in context. Lixity’s chapter comparisons can help you find a passage to revisit. Open the paragraph’s measurements and line references to see what changed in the text.

<a id="lixity"></a>

## Follow a result back to the manuscript

In Lixity, open the words behind a measurement such as sentence length, quoted words or a repeated phrase. Compare chapters using the same manuscript as a reference, or compare an edit with the saved version under the same settings. Use what you notice to decide where to read next. [Methods and limits](interpretation.html)

When the background matters, open the dossier beside the passage and revisit the retained source revision behind a saved quotation. Then choose what to share in a dossier PDF or a reading copy. In **Story rehearsal**, you can also write a beat such as a delayed answer and try a different order for your cards. [Research and exports](research-pdf.html) · [Story rehearsal](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#compare-scene-evidence-and-rehearse-an-intent)

Start with [the blank signature in Warehouse 4](first-look.html#receipt). The walkthrough takes you from a sentence about the receipt into the linked research. You can inspect the same material in the [read-only demo](../demo/report.html) without installing Lixity. For an example on a public-domain novel, read the [Fontane case study](../blog/effi-briest-case-study.html).

<a id="limits"></a>

## Where Lixity does not fit

- **Grammar and spelling correction.** Use a checker for suggested corrections or wording.

- **Plot and character development.** Lixity helps you inspect scenes and named characters you define. Use developmental editing for advice on their arcs.

- **Fact checking.** A retained quotation records what its source says. Verify the claim against the evidence yourself.

- **Collaborative editing.** Lixity is a local, single-user workspace. Use a shared editor for simultaneous writing.

- **Publishing production.** Lixity exports PDFs and reading websites for review. Use production tools for EPUB or print preflight.

<a id="faq"></a>

## Frequently asked questions

**Is Lixity an alternative to Grammarly or ProWritingAid?**

Use Grammarly or ProWritingAid for sentence-level suggestions. ProWritingAid also offers feedback on chapters and whole manuscripts. Use Lixity to inspect measured patterns in context and compare versions of a passage under the same settings.

**Does my manuscript leave my computer when I use Lixity?**

Built-in analysis, dashboard generation and PDF export run on your computer without an account. Optional integrations handle data according to the services you configure. A speech provider receives the text for the audio you ask it to generate.

**Is Lixity free?**

Yes. Lixity is open source under the AGPL-3.0-or-later, so private, research and commercial writing (including self-publishing) needs no extra permission. A separate written commercial license is available for closed-source integrations.

**Which languages does Lixity support?**

The interface is available in German, English, French, Spanish, Italian, Portuguese and Dutch. Analysis coverage depends on the language. German and English have the most extensive profiles.

**How does Lixity analyze my text?**

Built-in analysis computes deterministic measurements for features such as sentence length and repeated phrases. Open the passage behind a result and decide whether to revise it.

Use the linked documentation to check platform support and how the tool handles your files. When you try your passage, see how easily you can return to the draft from a result.

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
