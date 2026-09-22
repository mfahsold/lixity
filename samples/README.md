# Sample corpus – provenance and licensing

## `effi-briest-pg5323.txt` / `effi-briest.md`

Unmodified source file from **Project Gutenberg eBook #5323**
(<https://www.gutenberg.org/ebooks/5323>, *Effi Briest*, Theodor Fontane,
1895) plus a Markdown conversion (front matter, chapter headings as `## `).
The underlying text is **public domain** (Fontane died in 1898; public domain
in the USA and the EU). The `.txt` file keeps the original Project Gutenberg
header and license notice and must not be redistributed without it.

## `pride-and-prejudice-pg1342.txt` / `pride-and-prejudice.md`

Unmodified source file from **Project Gutenberg eBook #1342**
(<https://www.gutenberg.org/ebooks/1342>, *Pride and Prejudice*, Jane Austen,
1813) plus a Markdown conversion. **Public domain** (Austen died in 1817).
The `.txt` file keeps the original header and license notice.

Conversion (reproducible): body between the first `Chapter I.]` heading and
the printer note, Project Gutenberg header/footer and the illustration list
removed, `[Illustration …]` blocks stripped, `CHAPTER I.` / `Chapter I.]`
headings converted to `## Chapter I`, blank line after every heading,
front matter `# Pride and Prejudice` / `*Jane Austen*` added.

## `effi-briest-folge/`

An **original** stylistic exercise: the first chapter of a sequel written
against the measured style corridor of *Effi Briest*. It is an original
work, not part of the novel, and is covered by the Lixity Non-Commercial
License 1.0 (`../LICENSE`).

## Generated artifacts

Generated analysis artifacts (dashboards, metrics JSON) are not committed —
they are reproducible and would only bloat the repository. Regenerate them
any time:

```bash
lixity dashboard samples/effi-briest.md -o /tmp/effi-briest-dashboard.html
lixity build samples/pride-and-prejudice.md
```
