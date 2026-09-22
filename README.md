# Lixity

**Lixity** – from its mathematical core: **T**TR (Type-Token Ratio),
**Y**ule's Characteristic K and **LIX** (Läsbarhetsindex).

Quantitative text linguistics, stylometry, paragraph-accurate tense profiles and
idempotent publication pipelines for literary Markdown manuscripts.
Language-neutral (`de`, `en`, `fr`, `es`, `it`, `pt`, `nl` + generic fallback,
language detection via function words).

## Installation

```bash
pip install git+https://github.com/mfahsold/lixity.git
```

## Usage

```bash
lixity analyze manuscript.md              # corpus metrics (Rich report)
lixity analyze manuscript.md --json       # machine-readable
lixity profile manuscript.md              # tense profiles per paragraph (JSON)
lixity dashboard manuscript.md -o ui.html # single-file HTML dashboard
```

As a library:

```python
from lixity import CorpusConfig, CorpusAnalyzer, ParagraphProfiler

config = CorpusConfig(language="auto")
metrics = CorpusAnalyzer(config).analyze_text(open("manuscript.md").read())
```

## License

**Lixity Non-Commercial License 1.0 (LNCL-1.0)** – free for research, teaching and
clearly non-commercial projects. Commercial use only with a written license on
request: **mfahsold@googlemail.com**. Source-available, explicitly not an
OSI open-source license.
