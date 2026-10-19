# Sample corpus – provenance and licensing

[`first-look.md`](first-look.md) is the canonical manuscript for the single
Warehouse 4 demonstration: analysis, research and exports use these same bytes.
The historical novels are separate case-study and validation inputs.
Their public-domain text retains its source notices; original repository
examples follow the repository [LICENSE](../LICENSE), as listed below.
The unmodified Project Gutenberg source files keep their original
header and license notice and must not be redistributed without it.

| File | Work | Source | Legal status |
| :--- | :--- | :--- | :--- |
| `effi-briest-pg5323.txt` | *Effi Briest*, Theodor Fontane (1895) | [Project Gutenberg #5323](https://www.gutenberg.org/ebooks/5323) | public domain (author died 1898); unmodified PG file with header |
| `effi-briest.md` | same work, Markdown conversion | derived from the PG file | public domain; front matter + `## ` chapter headings |
| `pride-and-prejudice-pg1342.txt` | *Pride and Prejudice*, Jane Austen (1813) | [Project Gutenberg #1342](https://www.gutenberg.org/ebooks/1342) | public domain (author died 1817); unmodified PG file with header |
| `pride-and-prejudice.md` | same work, Markdown conversion | derived from the PG file | public domain; 61 chapters, ~122k words |
| `effi-briest-folge/` | *Annie* – original sequel draft (first chapter) | written by the repository author | see the source notice and repository LICENSE |
| `first-look.md` | *The Crate at Warehouse 4* – six short English chapters | synthetic demonstration; people, dialogue and incident are invented | original repository example content under AGPL-3.0-or-later |

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
committed. The synthetic [`first-look.md`](first-look.md) is an explicit exception:
[`docs/demo/report.html`](../docs/demo/report.html) combines analysis and research
in one read-only project. Its [regeneration recipe](../docs/demo/README.md) also
produces four PDF layouts and the identical public manuscript copy. It uses
explicit English defaults, without discovering local project settings.
The example is not a benchmark or calibration corpus.

Two public-domain case studies remain available for their corresponding articles:
[`docs/examples/effi-briest.html`](../docs/examples/effi-briest.html) and
[`docs/examples/pride-and-prejudice.html`](../docs/examples/pride-and-prejudice.html)
show the first three chapters each, with the complete work as a PDF report next
to them. `make examples` regenerates the project demo and the case-study artifacts.

Regenerate the historical examples locally:

```bash
lixity dashboard samples/effi-briest.md -o /tmp/effi-briest-dashboard.html
lixity build samples/pride-and-prejudice.md
```
