# Which manuscript analysis tool fits your work?

Four families of tools answer different questions about a manuscript. This page compares them by workflow: what each is good at, what it does not do, and where Lixity fits. None of them replaces an editor, and none of the descriptions below rank the tools against each other.

Updated 23 October 2026

## The families at a glance

**Grammar and style checkers** focus on sentences and phrasing. **Corpus and concordance tools** explore texts and collections quantitatively. **Stylometry and NLP packages** measure text through scripts. **Story and structure tools** focus on plot, scenes and characters. These categories overlap; they describe starting workflows, not exclusive feature lists. Lixity's focus is comparing language patterns within a manuscript and following their exact text and research context.

| Tool family | Primary focus | Runs locally | Account needed | Typical fit |
| --- | --- | --- | --- | --- |
| Grammar and style checkers | Sentence corrections, style suggestions | Partly (offline editions exist) | Usually yes | Line-level polishing |
| Corpus and concordance tools | Concordances, frequencies, collections | Yes | No | Research on text collections |
| Stylometry and NLP packages | Scriptable measurement and models | Yes | No | Academic and automated analysis |
| Story and structure tools | Plot, scenes, characters, planning | Partly | Often yes | Developmental editing and outlining |
| Lixity | Language patterns across one manuscript, linked to passages | Yes | No | Revision review with evidence |

## Choose a grammar or style checker if…

…you want sentence-level corrections, readability scores and phrasing suggestions while you write. Established examples are [LanguageTool](https://languagetool.org/), [ProWritingAid](https://prowritingaid.com/), [AutoCrit](https://www.autocrit.com/) and [Grammarly](https://www.grammarly.com/). They typically work through an account, and several offer manuscript-level reports in addition to in-line checking. Their suggestions are prescriptive by design: the tool proposes a change.

## Choose a corpus or concordance tool if…

…your question is about collections of texts rather than one manuscript: word frequencies, collocations, keywords or parallel passages. [AntConc](https://www.laurenceanthony.net/software/antconc/) and [Voyant Tools](https://voyant-tools.org/) offer corpus exploration. Check the individual tool for the reading, project and citation workflow you need; the category alone does not establish those limits.

## Choose a stylometry or NLP package if…

…you are comfortable in a shell or notebook and need reproducible numbers for a study: authorship attribution, vocabulary measures or syntactic annotations. The R package [stylo](https://cran.r-project.org/package=stylo), [spaCy](https://spacy.io/), [NLTK](https://www.nltk.org/) and statistical helpers such as textstat provide building blocks. A manuscript-reading and editorial workflow may require additional integration.

## Choose a story or structure tool if…

…your next decision is about plot, scenes or character arcs. [Fictionary](https://fictionary.co/) and [Scrivener](https://www.literatureandlatte.com/scrivener/) offer story-development or writing workflows. Their language and pacing features can overlap with other categories. Compare the current product documentation and a concrete task rather than assuming that a story tool cannot measure language.

## Or combine Lixity with an AI writing or editing assistant if…

…you want suggestions, rewrites or developmental feedback. Review the chosen service’s current features, costs and data-handling terms before supplying a manuscript. An assistant’s response depends on its model, instructions and the context you provide; read and assess its proposals yourself.

Lixity’s built-in analysis computes documented statistics from your manuscript without generating prose or a quality score. Chapter comparisons help you choose where to read; paragraph disclosures provide local text, measurements and source lines. You can use those observations when reviewing an assistant’s suggestions.

## Choose Lixity if…

…you want to see how *your* manuscript behaves over its chapters and keep the evidence next to your decisions: sentence rhythm, vocabulary, dialogue and tense; comparisons against the book’s own baseline; paragraph text and measurements for review; and a local research archive connecting sources and quotations to claims and writing decisions. Built-in analysis runs on your computer without cloud calls or an account. German and English have the deepest language profiles.

Explore [*The Crate at Warehouse 4*](../demo/report.html), one read-only project with manuscript analysis, research and PDF layouts, using the [first-look walkthrough](first-look.html). No installation is needed. The separate [Fontane case study](../blog/effi-briest-case-study.html) examines a public-domain novel; it is not another product demo.

## Where Lixity does not fit

- **Grammar and spelling correction:** Lixity does not fix sentences or suggest phrasing; use a checker for that.

- **Plot and character development:** supplied scene groups and literal character names support inspection, not automatic plot advice, inferred character arcs or a developmental edit.

- **Fact checking:** a retained quotation records what a source says; it does not verify a historical claim.

- **Collaborative editing:** the workspace is single-user and local by design.

- **Publishing production:** fixed-layout PDFs and reading websites provide review/reading copies, not EPUB production or print preflight.

## Frequently asked questions

**Is Lixity an alternative to Grammarly or ProWritingAid?**

Grammar and style checkers suggest sentence-level corrections. Lixity compares chapter patterns such as sentence rhythm, vocabulary, dialogue and tense, and provides paragraph-level text, measurements and source lines for review. It does not fix grammar or rewrite prose.

**Does my manuscript leave my computer when I use Lixity?**

Built-in analysis, dashboard generation and PDF export run locally without cloud calls or an account. Optional integrations and separately configured workers have their own setup and data handling.

**Is Lixity free?**

Yes. Lixity is open source under the AGPL-3.0-or-later, so private, research and commercial writing — including self-publishing — needs no extra permission. A separate written commercial license is available for closed-source integrations.

**Which languages does Lixity support?**

German and English have the deepest linguistic resources; French, Spanish, Italian, Portuguese and Dutch have localized interfaces and analysis resources with narrower coverage. Mathematical identifiers stay language-neutral.

**Does Lixity use AI to write or judge my text?**

No. Lixity computes deterministic statistics from your text and documents their limits. It generates no prose and produces no quality score; the author judges the text.

Tool names link to official project/vendor pages. This is a workflow comparison, not a complete or continuously verified feature inventory, ranking or endorsement. Check current versions, platform support and data handling before choosing.

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](../LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
