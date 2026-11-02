# Quickstart Guide 🚀

This guide walks you from initial installation through reviewing your first manuscript in Lixity.

---

## 1. Installation

Lixity requires Python 3.10 or newer. Install the package via PyPI:

```bash
pip install lixity
```

For speech synthesis and Poppler-based PDF inspection, optional system dependencies are documented in [docs/INSTALLATION.md](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md).

---

## 2. Starting the Workbench

Start the local background service:

```bash
lixity service start
```

Open your browser at:
`http://localhost:8765/`

---

## 3. Opening a Manuscript

1. Click on **Project** in the navigation bar or use **Open Project**.
2. Select your manuscript file in CommonMark Markdown (`.md`) or plain UTF-8 text (`.txt`).
3. Lixity automatically parses the chapter headings (`# Chapter Title` or `## Chapter Title`).

> [!TIP]
> **Importing from Scrivener or Word:**  
> Export from Scrivener via *File → Export → Files* as Markdown (`.md`). From Microsoft Word, save as plain text (`.txt`) or convert with Pandoc.

---

## 4. The Three Main Workspaces

1. **📖 Manuscript (Reading View):**  
   Distraction-free continuous prose reading. Statistical deviations (e.g. tense shifts, extreme sentence lengths) are subtly highlighted. Open research dossiers side-by-side in the companion panel.
2. **🔬 Research & Dossiers:**  
   Organize historical context, source quotes, and author decisions. Run vocabulary grounding comparisons between reference materials and chapters.
3. **📁 Project:**  
   Manage metadata, thresholds, register templates, audio direction, and PDF export (A4 editorial copy with line numbers, A5 book layout, analysis report).
