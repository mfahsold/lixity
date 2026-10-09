# Sample corpus – provenance and licensing

The two historical source works are **public domain** and are **not** covered
by the Lixity Non-Commercial License. The original sequel draft and the invented
first-look example are not public domain; their license status is listed below.
The unmodified Project Gutenberg source files keep their original
header and license notice and must not be redistributed without it.

| File | Work | Source | Legal status |
| :--- | :--- | :--- | :--- |
| `effi-briest-pg5323.txt` | *Effi Briest*, Theodor Fontane (1895) | [Project Gutenberg #5323](https://www.gutenberg.org/ebooks/5323) | public domain (author died 1898); unmodified PG file with header |
| `effi-briest.md` | same work, Markdown conversion | derived from the PG file | public domain; front matter + `## ` chapter headings |
| `pride-and-prejudice-pg1342.txt` | *Pride and Prejudice*, Jane Austen (1813) | [Project Gutenberg #1342](https://www.gutenberg.org/ebooks/1342) | public domain (author died 1817); unmodified PG file with header |
| `pride-and-prejudice.md` | same work, Markdown conversion | derived from the PG file | public domain; 61 chapters, ~122k words |
| `effi-briest-folge/` | *Annie* – original sequel draft (first chapter) | written by the repository author | © the author; covered by the LNCL-1.0 (`../LICENSE`) |
| `first-look.md` | *An invented night shift* – six short English chapters | synthetic text created for the Lixity first-look demonstration; no real manuscript or incident | original repository example content under the existing LNCL-1.0 (`../LICENSE`); no new permissions granted |

**Reproducible conversion** (Effi Briest): front matter, `## Erstes Kapitel` …
headings, text otherwise unchanged from the PG file.

**Reproducible conversion** (Pride and Prejudice): body between the first
`Chapter I.]` heading and the printer note; Project Gutenberg header/footer
and the illustration list removed; `[Illustration …]` blocks stripped;
`CHAPTER I.` / `Chapter I.]` headings converted to `## Chapter I`; blank line
after every heading; front matter `# Pride and Prejudice` / `*Jane Austen*`
added.

## Generated artifacts

Generated analysis artifacts (dashboards, metrics JSON) are normally not
committed. The small, synthetic [`first-look.md`](first-look.md) report is an
explicit exception: [`docs/demo/report.html`](../docs/demo/report.html) is the
read-only public demonstration. Its [regeneration recipe](../docs/demo/README.md)
uses English and shared code defaults, without discovering local project
settings. The example is not a benchmark or calibration corpus.

Regenerate the historical examples locally:

```bash
lixity dashboard samples/effi-briest.md -o /tmp/effi-briest-dashboard.html
lixity build samples/pride-and-prejudice.md
```
