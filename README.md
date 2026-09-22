# Lixity

**Lixity measures how a manuscript reads.** It turns a Markdown manuscript into
quantitative text linguistics: sentence rhythm, vocabulary richness, readability,
dialogue share and paragraph-accurate tense profiles — as a colour-coded
terminal report, as JSON, or as a single-file HTML dashboard.

The name is an acronym of its mathematical core: **T**TR (Type-Token Ratio),
**Y**ule's characteristic K and **LIX** (Läsbarhetsindex).

![Lixity CLI report](docs/screenshots/cli-analyze.png)

## What you get

Lixity is made for authors, editors and literary scholars who want evidence
about style instead of gut feeling. It answers questions like:

- **How does my prose move?** Sentence-length architecture from staccato
  fragments (≤ 6 words) to complex hypotaxes (> 25 words), plus punctuation
  density per 1,000 words.
- **Is my vocabulary rich or repetitive?** TTR, Guiraud R (length-stabilised)
  and Yule's K, each with a reference corridor and a plain-language assessment.
- **How readable is it?** Flesch Reading Ease (German Amstad adaptation) and
  LIX (Läsbarhetsindex).
- **Where does the tense shift?** Present/past dominance for every paragraph,
  with line anchors and severity flags for tense switches and mixtures.
- **How much dialogue is there?** Quoted-speech share per chapter and overall.
- **Where do I tell instead of show?** Counts of perception filters.

All of it runs offline, is deterministic, and speaks seven languages
(`de`, `en`, `fr`, `es`, `it`, `pt`, `nl`) plus a neutral fallback.

## Quick start

Requires Python 3.10 or newer.

```bash
pip install git+https://github.com/mfahsold/lixity.git

lixity analyze manuscript.md               # Rich report in the terminal
lixity analyze manuscript.md --json        # the same numbers as JSON
lixity profile manuscript.md               # tense profiles per paragraph (JSON)
lixity dashboard manuscript.md -o ui.html  # single-file HTML dashboard
```

Lixity reads plain Markdown: chapters are `##` headings, the appendix starts at
`## Anmerkungen und Literaturverzeichnis` (both configurable), and HTML comments
are ignored. Line numbers in reports and dashboards always refer to the source
file, so every finding stays clickable in your editor.

## The dashboard

![Lixity dashboard – light](docs/screenshots/dashboard-light.png)

The dashboard is one self-contained HTML file — no CDN, no framework, no data
leaves your machine. It shows the corpus KPIs, the sentence-length distribution
and a chapter map in which every paragraph is a coloured chip:

- **green** = present tense, **ochre** = past tense, **violet** = mixed,
  **grey** = neutral (too few tense markers),
- a red underline marks flagged paragraphs: a tense switch against the
  paragraph before it, or a strong mixture within the paragraph,
- click a chip to reveal the paragraph text, its line anchor and its stats.

Because the output is deterministic, regenerating an unchanged manuscript
produces an identical file — safe for Git, no diff noise.

![Lixity dashboard – dark](docs/screenshots/dashboard-dark.png)

## Example: »Eigentlich werde ich nie wütend«

The screenshots and numbers in this README come from a real reference
manuscript: a 55k-word German autofictional novel, 25 chapters, one Markdown
source file.

| Metric | Value | What it says |
| :--- | ---: | :--- |
| Words (full text / prose) | 55,331 / 53,306 | ~221 standard pages (250 words each) |
| Chapters / paragraphs / sentences | 25 / 427 / 5,505 | complete novel structure |
| Average sentence length (ASL) | 9.63 words | short, paratactic rhythm |
| Median / σ sentence length | 8 / 6.63 words | laconic base with dynamic bursts |
| Type-Token Ratio (TTR) | 0.1784 | homogeneous vocabulary |
| Guiraud R | 41.11 | length-stabilised lexical spread |
| Yule's Characteristic K | 51.92 | stable narrator idiom |
| Flesch Reading Ease (DE) | 69.0 | easy reading flow |
| LIX | 34.0 | accessible prose (< 40) |
| Dialogue ratio | 5.02 % | dialogue as accent, not carrier |
| Perception filters ("showing") | 94 | little telling |

The sentence-length architecture makes the rhythm visible: 38.5 % staccato
sentences (≤ 6 words) against only 2.9 % complex hypotaxes (> 25 words). In the
dashboard, the chapter map then shows where present-tense scenes, past-tense
passages and tense mixtures sit — paragraph by paragraph.

## Command line at a glance

| Command | Output | Typical use |
| :--- | :--- | :--- |
| `lixity analyze FILE` | Rich report or JSON | whole-corpus metrics and assessments |
| `lixity profile FILE` | JSON | paragraph tense/style profiles with line anchors |
| `lixity dashboard FILE` | HTML file (`-o`) | visual chapter map for editing sessions |

All commands accept `--language auto|de|en|fr|es|it|pt|nl|generic`
(default: `auto` — detection via function words, with a safe fallback to
`generic`). `analyze` and `profile` support `--json`; `dashboard` supports
`-o/--output`.

Full reference: [`docs/USAGE.md`](docs/USAGE.md).

## Library

```python
from lixity import CorpusConfig, CorpusAnalyzer
from lixity.language import resolve_language

text = open("manuscript.md", encoding="utf-8").read()
resolved = resolve_language(CorpusConfig(language="auto"), sample_text=text)
metrics = CorpusAnalyzer(CorpusConfig(language=resolved.key)).analyze_text(text)

print(metrics.asl, metrics.ttr, metrics.yules_k, metrics.lix)
```

`auto` needs a text sample for stop-word detection (the CLI passes the
manuscript automatically); `resolve_language` returns the detected key, name and
localised labels. See [`docs/USAGE.md`](docs/USAGE.md) for profiling, dashboard
rendering and all configuration options.

## Languages

`de`, `en`, `fr`, `es`, `it`, `pt`, `nl` and a neutral `generic` fallback
(metrics only, no tense classification). Unknown or ambiguous input degrades
gracefully instead of failing. Adding a language is a data-layer entry — no code
changes.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m unittest discover -s tests -v   # 43 tests, no network needed
.venv/bin/ruff check src tests                      # lint (rule set pinned in pyproject.toml)
```

The test suite is pure `unittest`; CI runs lint and tests on Python 3.10 and
3.12 with `PYTHONPATH=src`.

## Documentation

- [`docs/USAGE.md`](docs/USAGE.md) – full CLI, library and configuration
  reference, plus a glossary of all metrics.
- [`docs/index.html`](docs/index.html) – project page (GitHub Pages).
- [`CHANGELOG.md`](CHANGELOG.md) – release history.

## License

**Lixity Non-Commercial License 1.0 (LNCL-1.0)** – free for research, teaching and
clearly non-commercial projects. Commercial use only with a written license on
request: **mfahsold@googlemail.com**. Source-available, explicitly not an
OSI open-source license.
