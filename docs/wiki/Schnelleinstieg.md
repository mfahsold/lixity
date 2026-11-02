# Schnelleinstieg in Lixity 🚀

Dieser Leitfaden führt Sie in wenigen Minuten von der Installation bis zur ersten Manuskriptprüfung.

---

## 1. Installation

Lixity erfordert Python 3.10 oder neuer. Die Installation erfolgt unkompliziert über PyPI:

```bash
pip install lixity
```

Für Audio-Funktionen (Sprachsynthese) und Poppler-basierte PDF-Vergleiche können optionale Systempakete ergänzt werden (siehe [docs/INSTALLATION.md](https://github.com/mfahsold/lixity/blob/main/docs/INSTALLATION.md)).

---

## 2. Den lokalen Arbeitsbereich starten

Starten Sie den lokalen Hintergrunddienst mit:

```bash
lixity service start
```

Öffnen Sie anschließend Ihren Webbrowser unter:
`http://localhost:8765/`

---

## 3. Ein Manuskript laden

1. Klicken Sie in der Navigationsleiste auf **Projekt** oder nutzen Sie den Button **Projekt öffnen**.
2. Wählen Sie Ihre Manuskriptdatei im Markdown- (`.md`) oder Text-Format (`.txt`).
3. Lixity liest die Kapitelstruktur automatisch ein (Standard: Markdown-Überschriften `# Kapitelname` oder `## Kapitelname`).

> [!TIP]
> **Aus Scrivener oder Word importieren:**  
> Exportieren Sie Ihren Text in Scrivener einfach über *Ablage → Exportieren → Datei(en)* als Markdown (.md). In Microsoft Word speichern Sie den Text als UTF-8-Nur-Text (.txt) oder wandeln ihn mit Pandoc um.

---

## 4. Die drei Hauptansichten

Die Benutzeroberfläche gliedert sich in drei Kernbereiche:

1. **📖 Manuskript (Leseansicht):**  
   Fokussierter Lesemodus mit kontinuierlichem Textfluss. Auffällige Passagen (z. B. Tempushäufungen, Satzlängenextreme) werden durch diskrete Farbtöne markiert. Rechts kann ein Recherche-Dossier parallel geöffnet werden.
2. **🔬 Recherche & Dossiers:**  
   Verwalten Sie historische Notizen, Sachbelege, Zotero-Quellen und kreative Entscheidungen. Führen Sie Wortschatz-Abgleiche zwischen Quelldokumenten und Kapiteln durch.
3. **📁 Projekt:**  
   Metadaten, Projekteinstellungen (Lektoratsschwellenwerte, Register-Ziele), Audio-Regie und PDF-Exporte (Lektoratsfassung A4 mit Zeilennummern, Buchlayout A5, Analysebericht).
