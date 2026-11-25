# Which manuscript analysis tool fits your work?

Start with the decision you want to make. Finding a repeated phrase, revising a scene and sharing a draft with an editor each call for a different workflow. Use these examples to decide what to try with your own text.

Updated 25 November 2026

<a id="families"></a>

## Choose a tool by task

| Your task | Examples to evaluate | What to try |
| --- | --- | --- |
| Polish sentences or review an entire draft | [ProWritingAid](https://help.prowritingaid.com/article/318-what-is-manuscript-analysis), [AutoCrit](https://www.autocrit.com/story-analyzer-plus/), [Papyrus](https://papyrus.de/features/style-analysis) | Open a passage-level suggestion and review the same issue across the book. |
| Draft and organize chapters | [Scrivener](https://www.literatureandlatte.com/scrivener/overview), [Papyrus](https://papyrus.de/) | Move a scene, compare an earlier version and export the draft. |
| Review story structure | [Fictionary](https://fictionary.co/writers-software/) | Tag a scene, inspect the arc across scenes and check the editorial notes. |
| Collaborate or keep Markdown notes | [Ellipsus](https://help.ellipsus.com/support/solutions/articles/205000067329), [Obsidian](https://obsidian.md/help/data-storage) | Use Ellipsus to review a shared draft and comments. Use Obsidian to link and read notes stored as local files. |
| Explore a collection or run a study | [AntConc](https://www.laurenceanthony.net/software/antconc/), [Voyant](https://docs.voyant-tools.org/docs/tutorial-local.html), [stylo](https://cran.r-project.org/package=stylo) | Inspect a concordance or reproduce a measurement across a collection. Voyant also offers a local server. |
| Review a passage and keep the reasoning with your project | [Lixity](#lixity) | Follow counted text, decide on a revision, open an exact source citation and share the selected reading copy. |

<a id="checkers"></a>

## Choose a grammar or style checker if…

…you want suggested corrections, clarity feedback or a broader editorial report. AutoCrit and ProWritingAid document whole-manuscript reports and passage-level findings. Papyrus combines in-text style and readability analysis with book-writing tools. Check the edition and its operating requirements. ProWritingAid, for example, documents internet access as a requirement. [AutoCrit reports](https://help.autocrit.com/en/collections/2339242-interpreting-autocrit-results) · [ProWritingAid requirements](https://help.prowritingaid.com/article/99-what-do-i-need-to-use-prowritingaid) · [Papyrus style analysis](https://papyrus.de/features/style-analysis)

<a id="corpus"></a>

## Choose a corpus or concordance tool if…

…your question is about collections of texts rather than one manuscript: word frequencies, collocations, keywords or parallel passages. [AntConc](https://www.laurenceanthony.net/software/antconc/) and [Voyant Tools](https://voyant-tools.org/) offer corpus exploration. Check the individual tool for the reading, project and citation workflow you need; the category alone does not establish those limits.

<a id="stylometry"></a>

## Choose a stylometry or NLP package if…

…you are comfortable in a shell or notebook and need reproducible numbers for a study: authorship attribution, vocabulary measures or syntactic annotations. The R package [stylo](https://cran.r-project.org/package=stylo), [spaCy](https://spacy.io/), [NLTK](https://www.nltk.org/) and statistical helpers such as textstat provide building blocks. A manuscript-reading and editorial workflow may require additional integration.

<a id="story"></a>

## Choose a story or structure tool if…

…your next decision is about plot, scenes or character arcs. Fictionary visualizes scene-level story elements. Scrivener combines chapter and scene organization with snapshots and section comparison. If you already draft in another app, export a chapter as Word, Markdown or plain text to review a copy in Lixity. [Fictionary](https://fictionary.co/writers-software/) · [Scrivener](https://www.literatureandlatte.com/scrivener/overview) · [Import a manuscript](installation.html#first-dashboard)

<a id="assistants"></a>

## Or combine Lixity with an AI writing or editing assistant if…

…you want suggestions, rewrites or developmental feedback. Review the chosen service’s current features, costs and data-handling terms before supplying a manuscript. An assistant’s response depends on its model, instructions and the context you provide; read and assess its proposals yourself.

Lixity’s built-in analysis computes documented statistics from your manuscript without generating prose or a quality score. Chapter comparisons help you choose where to read; paragraph disclosures provide local text, measurements and source lines. You can use those observations when reviewing an assistant’s suggestions.

<a id="lixity"></a>

## Choose Lixity if…

…you want to follow a difference back to the words that produced it. Inspect a measurement such as sentence length, quoted words or a repeated phrase. Compare chapters against the manuscript's own reference, or compare a draft and its saved revision using the same settings. Treat the measurement as a prompt for reading. [Methods and limits](interpretation.html)

Keep the background beside the passage when it affects your decision. Open a dossier or the exact retained source revision behind a saved link. In **Story rehearsal**, write a beat such as a delayed answer or a revelation and try a different order for your cards. Save the cards when you want to keep the experiment. Share a dossier PDF or a reading copy with the chapters and notes you select. Built-in analysis runs on your computer without a Lixity account. German and English have the deepest language profiles. [Research and exports](research-pdf.html) · [Story rehearsal](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#compare-scene-evidence-and-rehearse-an-intent)

Explore [*The Crate at Warehouse 4*](../demo/report.html), one read-only project with manuscript analysis, research and PDF layouts, using the [first-look walkthrough](first-look.html). No installation is needed. The separate [Fontane case study](../blog/effi-briest-case-study.html) examines a public-domain novel; it is not another product demo.

<a id="limits"></a>

## Where Lixity does not fit

- **Grammar and spelling correction:** Lixity does not fix sentences or suggest phrasing; use a checker for that.

- **Plot and character development:** supplied scene groups and literal character names support inspection, not automatic plot advice, inferred character arcs or a developmental edit.

- **Fact checking:** a retained quotation records what a source says; it does not verify a historical claim.

- **Collaborative editing:** the workspace is single-user and local by design.

- **Publishing production:** fixed-layout PDFs and reading websites provide review and reading copies, not EPUB production or print preflight.

<a id="faq"></a>

## Frequently asked questions

**Is Lixity an alternative to Grammarly or ProWritingAid?**

Grammar and style checkers suggest sentence-level corrections. Lixity compares chapter patterns such as sentence rhythm, vocabulary, dialogue and tense, and provides paragraph-level text, measurements and source lines for review. It does not fix grammar or rewrite prose.

**Does my manuscript leave my computer when I use Lixity?**

Built-in analysis, dashboard generation and PDF export run locally without cloud calls or an account. Optional integrations and separately configured workers have their own setup and data handling.

**Is Lixity free?**

Yes. Lixity is open source under the AGPL-3.0-or-later, so private, research and commercial writing (including self-publishing) needs no extra permission. A separate written commercial license is available for closed-source integrations.

**Which languages does Lixity support?**

German and English have the deepest linguistic resources; French, Spanish, Italian, Portuguese and Dutch have localized interfaces and analysis resources with narrower coverage. Mathematical identifiers stay language-neutral.

**Does Lixity use AI to write or judge my text?**

No. Lixity computes deterministic statistics from your text and documents their limits. It generates no prose and produces no quality score; the author judges the text.

The links document the workflows cited here. Check the current edition, platform support and data handling when evaluating a tool. Try the same passage in the tools that look relevant and compare how easily you can find the evidence and return to your draft.

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
