# Sample corpus – provenance and licensing

## `effi-briest-pg5323.txt`

Unmodified source file from **Project Gutenberg eBook #5323**:
<https://www.gutenberg.org/ebooks/5323> (*Effi Briest*, Theodor Fontane,
first published 1895). The file includes the original Project Gutenberg
header and license notice and must not be redistributed without it.

## `effi-briest.md`

A Markdown conversion of the novel for analysis with Lixity (chapter
headings as `## `). The underlying text is **public domain** (Fontane died
in 1898; the work is public domain in the USA and in the EU). The Markdown
conversion is provided as a test and demonstration corpus.

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
```
