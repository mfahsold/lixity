# Which manuscript analysis tool fits your work?

Four families of tools answer different questions about a manuscript. This page compares them by workflow: what each is good at, what it does not do, and where Lixity fits. None of them replaces an editor, and none of the descriptions below rank the tools against each other.

Maintained by the Lixity project · Updated 13 October 2026

## The four families at a glance

**Grammar and style checkers** correct sentences and suggest phrasing. **Corpus and concordance tools** explore texts and collections quantitatively. **Stylometry and NLP packages** measure text through scripts. **Story and structure tools** work on plot, scenes and characters. Lixity adds a fifth job: measuring language patterns across one manuscript and always linking a number back to its passage.

## Choose a grammar or style checker if…

…you want sentence-level corrections, readability scores and phrasing suggestions while you write. Established examples are [LanguageTool](https://languagetool.org/), [ProWritingAid](https://prowritingaid.com/), [AutoCrit](https://www.autocrit.com/) and [Grammarly](https://www.grammarly.com/). They typically work through an account, and several offer manuscript-level reports in addition to in-line checking. Their suggestions are prescriptive by design: the tool proposes a change.

## Choose a corpus or concordance tool if…

…your question is about collections of texts rather than one manuscript: word frequencies, collocations, keywords or parallel passages. [AntConc](https://www.laurenceanthony.net/software/antconc/) and [Voyant Tools](https://voyant-tools.org/) are widely used in teaching and research. They are strong at exploration; they do not model a book project, revision state or citation workflow.

## Choose a stylometry or NLP package if…

…you are comfortable in a shell or notebook and need reproducible numbers for a study: authorship attribution, vocabulary measures or syntactic annotations. The R package [stylo](https://cran.r-project.org/package=stylo), [spaCy](https://spacy.io/), [NLTK](https://www.nltk.org/) and statistical helpers such as textstat are the usual building blocks. They are scriptable and citable; they bring no reading interface, no project structure and no editorial workflow.

## Choose a story or structure tool if…

…your next decision is about plot, pacing, scenes or character arcs rather than language. [Fictionary](https://fictionary.co/) and [Scrivener](https://www.literatureandlatte.com/scrivener/) with its ecosystem work at the story level. They help you plan and restructure; they do not measure sentence rhythm, dialogue share or tense patterns.

## Choose Lixity if…

…you want to see how *your* manuscript behaves over its chapters and keep the evidence next to your decisions: sentence rhythm, vocabulary, dialogue and tense; chapter comparisons against the book's own baseline; passages behind every signal; and a local research archive that ties sources and quotations to claims and writing decisions. Analysis runs on your computer, there is no account, and nothing is uploaded. German and English are the deepest language profiles.

Start with the [read-only example report](../demo/report.html) or the [three-minute first look](first-look.html); no installation is needed for either.

## Where Lixity does not fit

- **Grammar and spelling correction:** Lixity does not fix sentences or suggest phrasing; use a checker for that.

- **Plot and character development:** no story structure, scene planning or character arcs.

- **Fact checking:** a retained quotation records what a source says; it does not verify a historical claim.

- **Collaborative editing:** the workspace is single-user and local by design.

- **Publishing production:** PDF export is fixed-layout (A4 report, A5 reading copy, A4 sheets); there is no EPUB or print preflight.

## Frequently asked questions

**Is Lixity an alternative to Grammarly or ProWritingAid?**

No. Grammar and style checkers correct sentences and suggest phrasing. Lixity measures patterns such as sentence rhythm, vocabulary, dialogue and tense across your manuscript and links every number to the passage it came from. It does not fix grammar or rewrite prose.

**Does my manuscript leave my computer when I use Lixity?**

No. Analysis, dashboards and PDF export run locally. There is no account and no cloud service; nothing is uploaded.

**Is Lixity free?**

Yes. Lixity is open source under the AGPL-3.0-or-later, so private, research and commercial writing — including self-publishing — needs no extra permission. A separate written commercial license is available for closed-source integrations.

**Which languages does Lixity support?**

German and English have the deepest linguistic resources; French, Spanish, Italian, Portuguese and Dutch have localized interfaces and analysis resources with narrower coverage. Mathematical identifiers stay language-neutral.

**Does Lixity use AI to write or judge my text?**

No. Lixity computes deterministic statistics from your text and documents their limits. It generates no prose and produces no quality score; the author judges the text.

Tool names and links point to the official pages of their projects and vendors. Descriptions here are based on the public documentation available in October 2026 and are not endorsements.

[Lixity home](../) · [License and commercial use](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md) · [Legal notice](../#impressum)
