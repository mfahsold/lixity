# Lixity Onboarding Guide

Welcome to Lixity — the privacy-first, local analysis engine and research workspace for writers, editors, and scholars.

This guide provides an end-to-end walkthrough for both non-technical writers and developers: how projects are structured, how files are organized, and how to get the most out of Lixity via the interactive web dashboard and the command-line interface (CLI).

---

## 1. Core Principles

- **100% Local & Private**: Lixity never uploads manuscript texts, notes, or research documents to the cloud. All computation happens entirely on your local machine.
- **Statistical Rigor over Subjective Scoring**: Lixity is not an automated grammar checker or an instruction to rewrite prose. It provides descriptive, statistically sound diagnostics (such as FDR-controlled Benjamini-Hochberg error control at $q=0.05$) to support human editorial judgment.
- **Plain-Text Transparency**: All projects, manuscripts, and configurations use open standard formats: Markdown (`.md`) and JSON (`.json`). You can edit your book in Obsidian, VS Code, Ulysses, iA Writer, or standard text editors.

---

## 2. Anatomy of a Lixity Project

A Lixity project is simply a folder on your computer containing three core elements:

```text
my-novel/
├── lixity.json              # Project configuration and style thresholds
├── manuscript.md            # Your book's text structured with chapter headings
└── research/                # Optional evidence archive & research workspace
    ├── manifest.json        # Snapshot head and cryptographic state
    ├── objects/             # Retained UTF-8 source texts (SHA-256 hashed)
    └── research.db          # Disposable SQLite FTS5 search index
```

### 1. The Project Configuration (`lixity.json`)
The `lixity.json` file records metadata and customized analysis baselines:
```json
{
  "schema_version": "lixity-config/1",
  "project": {
    "title": "The Shadow over the Dunes",
    "language": "en",
    "genre": "historical-fiction"
  },
  "manuscript": {
    "path": "manuscript.md"
  },
  "style": {
    "z_mild": 2.5,
    "z_strong": 3.5,
    "fdr_q": 0.05
  }
}
```

### 2. The Manuscript File (`manuscript.md`)
Your novel or manuscript is written in clean, standard Markdown:
- **Chapters**: Defined with top-level or second-level headings (e.g., `# Chapter 1: The Arrival` or `## Act I`).
- **Scenes**: Separated by standard paragraph breaks or horizontal rules (`---`).
- **Editorial Markers**: Inline non-destructive markers (e.g., `<!-- LIXITY-MARKER kind="factcheck" note="Verify train timetable in 1912" -->`).

### 3. The Research Workspace (`research/`, Optional)
For historical novels, non-fiction, or detailed worldbuilding:
- **Sources**: Archived reference documents with explicit local retention confirmation (`--allow-retention`).
- **Passages**: Verifiable, immutable verbatim excerpt citations.
- **Claims**: Factual hypotheses or historical assertions (`hypothetical`, `evidenced`, or `disputed`).
- **Evidence Links**: Direct references linking passage citations to claims (`supports`, `contradicts`, `qualifies`, `contextualizes`).
- **Decisions**: Explicit logs of artistic choices and intentional deviations from historical fact.

---

## 3. Web Dashboard Onboarding (`lixity serve`)

The easiest way to work with Lixity is the built-in native development server:

```sh
# Start with an empty workspace
lixity serve --no-project --port 8765

# Or open an existing project directory directly
lixity serve --project ./my-novel --port 8765
```

Navigate to `http://127.0.0.1:8765` in your browser.

### Creating or Importing a Project in the UI

1. Click **+ Neues Projekt / New Project** in the header or welcome screen.
2. Choose one of two tabs:
   - **Manuskript importieren (Import Manuscript)**:
     - Drag & drop your `.md` or `.txt` file into the dropzone.
     - Lixity instantly scans the file, detecting the title, word count, chapter divisions, and language.
     - Click **Manuskript importieren & analysieren** to initialize the project folder and launch the dashboard.
   - **Neues Manuskript beginnen (Start New Manuscript)**:
     - Enter your working title.
     - Pick a narrative template:
       - **Minimal**: Single chapter for freeform writing.
       - **3-Akt-Struktur (3-Act Structure)**: Setup, Confrontation, and Resolution headings.
       - **Recherche-Roman (Research Novel)**: Complete template with integrated local `research/` archive.
     - Click **Projekt anlegen (Create Project)**.

### Navigating Dashboard Sections

- **Key Metrics & Style Passport**: Average sentence length (ASL), dialogue ratio, vocabulary variety (Guiraud's $R$, Yule's $K$), staccato/cascade rhythms.
- **Interactive 3D Style Space**: Visualizes chapters along their principal stylistic components to reveal narrative pacing and tonal drift.
- **FDR Anomaly Flags**: Identifies paragraphs with statistically significant stylistic shifts while strictly controlling for false discoveries ($q=0.05$).
- **Research & Grounding Panel**: Ingest historical source texts, search via full-text FTS5, organize dossiers, and compare vocabulary overlap between research sources and manuscript chapters.

---

## 4. Command-Line Interface (CLI) Quickstart

For terminal users and script automations:

### Step 1: Initialize a Project
```sh
# Create a 3-act novel project in English
lixity init my-novel --title "The Glass Fortress" --language en --template three_act

# Switch into project folder
cd my-novel
```

### Step 2: Analyze the Manuscript
```sh
# Generate a terminal summary report
lixity analyze manuscript.md

# Inspect detailed style fingerprint and baselines
lixity style manuscript.md --json

# Export an interactive HTML report
lixity report manuscript.md --out report.html
```

### Step 3: Manage Research & Evidence
```sh
# Ingest historical source material
lixity research ingest research/ --file historical_letter_1912.txt --allow-retention --title "Letter from Zürich" --tags "swiss,1912,correspondence"

# Search across sources
lixity research search research/ --query "Zürich"

# Record a historical claim
lixity research claim research/ \
  --title "Café Treffpunkt 1912" \
  --statement "The café served as a confidential meeting point in autumn 1912." \
  --confidence evidenced \
  --place "Zürich"

# Link evidence to claim
lixity research link-evidence research/ \
  --claim-id "<CLAIM_UUID>" \
  --passage-id "<PASSAGE_UUID>" \
  --relation supports \
  --rationale "Corroborated by eyewitness letter dated Oct 1912."

# Record an authorial decision (artistic license)
lixity research decision research/ \
  --title "Postpone café meeting to 1914" \
  --rationale "Heightens pre-war dramatic tension for Act II." \
  --claim-id "<CLAIM_UUID>" \
  --deviation-from-fact \
  --impact-on-plot "Increases the urgency of the protagonist's escape."

# Compare research vocabulary against manuscript chapters
lixity research compare research/ --source-id "<SOURCE_UUID>" --manuscript manuscript.md
```

---

## 5. Frequently Asked Questions (FAQ)

### Where are my files saved when using the Web UI?
When you drop a file or create a project in the Web Dashboard, Lixity saves everything into a local directory on your drive (by default in a subfolder named after your book title). You have full ownership of all files at all times.

### Can I use Lixity with other writing software?
Yes. Since `manuscript.md` is standard Markdown, you can write in Scrivener (via Markdown sync), Obsidian, iA Writer, VS Code, or any other editor. When you save your file in your editor, simply reload or refresh Lixity to view updated metrics.

### What does "Deviation from fact" mean in the research workspace?
Historical novelists frequently alter minor dates or merge historical figures for narrative momentum. Lixity lets you explicitly flag intentional deviations so that your research notes distinguish between verified historical facts and deliberate artistic choices.

### How do I update Lixity?
```sh
uv tool upgrade lixity
```

For complete architectural details and technical references, visit [docs/ARCHITECTURE.md](ARCHITECTURE.md) and [docs/research/USAGE.md](research/USAGE.md).
