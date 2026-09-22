# Lixity

**Lixity** – aus dem mathematischen Kern: **T**TR (Type-Token-Ratio),
**Y**ule's Characteristic K und **LIX** (Läsbarhetsindex).

Quantitative Textlinguistik, Stilometrie, absatzgenaue Tempusprofile und
idempotente Publikationspipelines für literarische Markdown-Manuskripte.
Sprachneutral (`de`, `en`, `fr`, `es`, `it`, `pt`, `nl` + generischer Fallback,
Spracherkennung über Funktionswörter).

## Installation

```bash
pip install git+https://github.com/mfahsold/lixity.git
```

## Nutzung

```bash
lixity analyze manuskript.md              # Korpuskennzahlen (Rich-Report)
lixity analyze manuskript.md --json       # maschinenlesbar
lixity profile manuskript.md              # Tempusprofile je Absatz (JSON)
lixity dashboard manuskript.md -o ui.html # Single-File-HTML-Dashboard
```

Als Bibliothek:

```python
from lixity import CorpusConfig, CorpusAnalyzer, ParagraphProfiler

config = CorpusConfig(language="auto")
metrics = CorpusAnalyzer(config).analyze_text(open("manuskript.md").read())
```

## Lizenz

**Lixity Non-Commercial License 1.0 (LNCL-1.0)** – frei für Forschung, Lehre und
klar nicht-kommerzielle Projekte. Kommerzielle Nutzung nur mit schriftlicher
Lizenz auf Anfrage: **mfahsold@googlemail.com**. Source-available, ausdrücklich
keine OSI-Open-Source-Lizenz.
