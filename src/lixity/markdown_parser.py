"""
scripts/engine/markdown_parser.py
=================================
Generischer, projektneutraler Markdown-Parser und Inline-Konverter.

Diese Engine-Schicht ist bewusst frei von PyCairo/Pango- und Projekt-
Abhängigkeiten, damit sie von allen Publikationsadaptern (export_pdf.py,
export_epub.py, create_excerpt.py) deterministisch geteilt werden kann.

Bietet:
- ``parse_markdown_blocks``: Wandelt Markdown-Text in semantische Blöcke
  (h1/h2/h3, Absätze, Zitatblöcke, Listenpunkte, Trennlinien, Fußnoten).
  Jeder Block trägt Zeilenanker (``start_line``/``end_line``, 1-basiert) für
  die präzise Rückverfolgung im Manuskript (Lektorats- und Analyse-UI).
- ``parse_markdown_file``: Datei-Variante mit UTF-8-Lesehandling.
- ``inline_markdown_to_html``: Konvertiert Inline-Markup in sicheres XHTML5
  (für EPUB 3.3); inklusive EPUB-Fußnoten-Verweisgenerierung.

Redaktionelle HTML-Kommentare (``<!-- PRÜFEN ... -->``) werden grundsätzlich
und restlos herausgefiltert, damit sie niemals in Publikationsausgaben
erscheinen.
"""

import re
import html as html_mod
from typing import Dict, List, Optional, Any

_FN_REF_PATTERN = re.compile(r"\[\^([^\]]+)\]")
_FN_REF_STRIP_PATTERN = re.compile(r"\[\^([^\]]+)\]")


def strip_inline_markup(text: str) -> str:
    """Entfernt Inline-Markdown (Kommentare, Fußnotenanker, Betonungen) für die Zählung.

    Der Klartext bleibt lesbar; die Funktion ist die gemeinsame Bereinigungsstufe
    von Analyzer, Stilprofil und weiteren Analyse-Werkzeugen.
    """
    text = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
    text = _FN_REF_STRIP_PATTERN.sub("", text)
    text = re.sub(r"\*\*\*(.*?)\*\*\*", r"\1", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.*?)(?<!\*)\*(?!\*)", r"\1", text)
    return text.strip()
_LINK_PATTERN = re.compile(r"\[([^\]]+)\]\(([^)\s]+)\)")


def parse_markdown_blocks(content: str) -> List[Dict[str, Any]]:
    """Parst Markdown-Inhalt in semantische Blöcke und filtert redaktionelle HTML-Kommentare."""
    # Redaktionelle Kommentare (<!-- ... -->) restlos entfernen
    clean_content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    lines = clean_content.splitlines()

    blocks: List[Dict[str, Any]] = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip("\r\n")
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped == "---":
            blocks.append({"type": "divider", "start_line": i + 1, "end_line": i + 1})
            i += 1
            continue

        if stripped.startswith("# "):
            blocks.append(
                {"type": "h1", "text": stripped[2:].strip(), "start_line": i + 1, "end_line": i + 1}
            )
            i += 1
            continue

        if stripped.startswith("## "):
            blocks.append(
                {"type": "h2", "text": stripped[3:].strip(), "start_line": i + 1, "end_line": i + 1}
            )
            i += 1
            continue

        if stripped.startswith("### "):
            blocks.append(
                {"type": "h3", "text": stripped[4:].strip(), "start_line": i + 1, "end_line": i + 1}
            )
            i += 1
            continue

        # Zitate und Callout-Blöcke
        if stripped.startswith(">"):
            start_line = i + 1
            paras = []
            cur_p = []
            while i < len(lines):
                q_line = lines[i].rstrip("\r\n").strip()
                if q_line.startswith(">"):
                    content_q = q_line[1:].strip()
                    if content_q == "":
                        if cur_p:
                            paras.append(" ".join(cur_p))
                            cur_p = []
                    else:
                        cur_p.append(content_q)
                    i += 1
                else:
                    break
            if cur_p:
                paras.append(" ".join(cur_p))
            blocks.append(
                {"type": "quote_block", "paras": paras, "start_line": start_line, "end_line": i}
            )
            continue

        # Fußnotendefinitionen [^id]: Text
        fn_match = re.match(r"^\[\^([^\]]+)\]:\s*(.*)", stripped)
        if fn_match:
            start_line = i + 1
            fn_id = fn_match.group(1)
            fn_text = [fn_match.group(2).strip()]
            i += 1
            while i < len(lines):
                next_line = lines[i].rstrip("\r\n")
                if next_line.startswith("    ") or next_line.startswith("\t"):
                    fn_text.append(next_line.strip())
                    i += 1
                elif lines[i].strip() and not lines[i].strip().startswith("[^"):
                    fn_text.append(lines[i].strip())
                    i += 1
                else:
                    break
            blocks.append(
                {
                    "type": "footnote_def",
                    "id": fn_id,
                    "text": " ".join(fn_text),
                    "start_line": start_line,
                    "end_line": i,
                }
            )
            continue

        # Listenpunkte
        if stripped.startswith("- ") or stripped.startswith("* "):
            start_line = i + 1
            item_text = [stripped[2:].strip()]
            i += 1
            while i < len(lines):
                n_line = lines[i].rstrip("\r\n")
                if n_line.strip() and not (n_line.strip().startswith(("- ", "* ", "#"))):
                    item_text.append(n_line.strip())
                    i += 1
                else:
                    break
            blocks.append(
                {
                    "type": "list_item",
                    "text": " ".join(item_text),
                    "start_line": start_line,
                    "end_line": i,
                }
            )
            continue

        # Fließtext-Absatz
        start_line = i + 1
        para_lines = [line.strip()]
        has_break = [line.endswith("  ")]
        i += 1
        while i < len(lines):
            raw_l = lines[i].rstrip("\r\n")
            if not raw_l.strip() or raw_l.strip().startswith(("#", ">", "---", "- ", "* ", "[^")):
                break
            has_break.append(raw_l.endswith("  "))
            para_lines.append(raw_l.strip())
            i += 1

        parts = []
        for idx_p, p_text in enumerate(para_lines):
            parts.append(p_text)
            if idx_p < len(para_lines) - 1:
                if has_break[idx_p]:
                    parts.append("\n")
                else:
                    parts.append(" ")
        blocks.append(
            {"type": "p", "text": "".join(parts), "start_line": start_line, "end_line": i}
        )

    return blocks


def parse_markdown_file(filepath: str) -> List[Dict[str, Any]]:
    """Liest eine Markdown-Datei UTF-8-sicher und parst sie in semantische Blöcke."""
    with open(filepath, "r", encoding="utf-8") as f:
        return parse_markdown_blocks(f.read())


def inline_markdown_to_html(
    text: str,
    fn_counter: Optional[Dict[str, int]] = None,
    document_id: str = "doc",
) -> str:
    """Konvertiert Inline-Markdown in sicheres XHTML5-Fragment für EPUB 3.3.

    - ``**fett**`` → ``<strong>``, ``*kursiv*`` → ``<em>``, ``***x***`` → beides.
    - ``[^id]`` → EPUB-Fußnotenanker (``epub:type="noteref"``) mit eindeutiger id.
    - ``[Text](url)`` → ``<a href="url">``.
    - Zeilenumbrüche (doppeltes Leerzeichen in Quelle) → ``<br/>``.
    - ``fn_counter`` gewährleistet dokumentweit eindeutige Referenz-IDs.
    """
    if not text:
        return ""

    if fn_counter is None:
        fn_counter = {}

    # 1. Wörtliche Asteriske schützen
    text = text.replace(r"\*", "\x01ASTERISK\x02")

    # 2. HTML-eskapieren
    text = html_mod.escape(text, quote=False)

    # 3. Fußnotenreferenzen [^id] mit eindeutiger Anker-ID
    def fn_ref(m: re.Match) -> str:
        fn_id = m.group(1)
        n = fn_counter.get(fn_id, 0) + 1
        fn_counter[fn_id] = n
        return (
            f'<a epub:type="noteref" id="fnref{fn_id}-{document_id}-{n}" '
            f'href="#fn{fn_id}" role="doc-noteref" class="fnref">{fn_id}</a>'
        )

    text = _FN_REF_PATTERN.sub(fn_ref, text)

    # 4. Fett-kursiv, fett, kursiv
    text = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", text)

    # 5. Links [Text](url)
    text = _LINK_PATTERN.sub(r'<a href="\2">\1</a>', text)

    # 6. Harte Zeilenumbrüche
    text = text.replace("\n", "<br/>\n")

    # 7. Wörtliche Asteriske wiederherstellen
    text = text.replace("\x01ASTERISK\x02", "*")

    return text
