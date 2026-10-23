# Finde die Stellen, die du noch einmal lesen solltest.

Du überarbeitest einen Romanentwurf? Lixity macht Sprachmuster sichtbar und hält die Recherche hinter einer Textstelle erreichbar. Die eingebaute Analyse läuft lokal auf deinem Rechner, ohne Konto und ohne automatisches Umschreiben. Du entscheidest, was eine Auffälligkeit bedeutet.

Aktualisiert am 23. Oktober 2026

## Eine Frage statt eines Zielwerts

Warum klingt dieses Kapitel anders als der Rest? Ist eine Wiederholung beabsichtigt? Auf welcher Quelle beruht dieses Detail? Für einen ersten Versuch genügt eine dieser Fragen.

[Eine Frage in der Demo prüfen](../demo/report.html)

Die schreibgeschützte Demo verwendet ein erfundenes englisches Hafenmanuskript und englische Bedienelemente. Diese Seite erklärt den Einstieg auf Deutsch; sie ist keine deutsche Fassung des Demo-Manuskripts. Kein Konto, keine Installation und kein Upload sind zum Ausprobieren nötig.

## Passt der kürzere Rhythmus zur Handlung?

1. Wähle in der Demo **Inspect chapter 2**. Lies den Anfang von *The Loose Board*: „A board moved. Mara turned.“ Mara versucht, eine Kiste festzuhalten.

2. Öffne beim Absatz **… → Explore passage → Explain measurement**. Du siehst die gezählten Sätze und Wörter. Mit **Counted text** lassen sich die Markierungen einblenden.

3. Vergleiche über **opening chapter** in der Aufgabenkarte die Hafenbeschreibung im ersten Kapitel. Was ändert sich beim Lesen, nicht nur in der Zahl?

**Mögliche Entscheidung:** Die kurzen Sätze trennen körperliche Handlungen voneinander; du behältst den Kontrast. Klingt die Stelle beim Vorlesen dagegen unbeabsichtigt abgehackt, könntest du im eigenen Entwurf eine Handlung mit ihrer Folge verbinden. Kürzer ist nicht automatisch besser. Der Durchschnitt ist kein Schreibziel.

Der erste Prüfschritt ist gelungen, wenn du den Unterschied am Text erklären kannst. Du musst dafür weder alle Messgrößen verstehen noch etwas „korrigieren“. Das kurze Beispiel demonstriert den Arbeitsgang, nicht die statistische Zuverlässigkeit für jedes Manuskript.

**Danach: die Quelle hinter einer Textstelle wiederfinden**

**Aktueller main-Stand:** Neutrale punktierte Markierungen und der Knopf mit Buchsymbol **Research** kennzeichnen gespeicherte Recherchebezüge. Die durchgezogenen Analyse-Unterstreichungen zeigen dagegen gezählte Textstellen. Recherchebezüge bleiben auch bei ausgeschalteter Analyse sichtbar.

Der Eröffnungsabsatz enthält eine gespeicherte Verbindung zur Recherche. Wähle **… → Explore passage → Research for this passage**. Öffne den verknüpften Eintrag oder seine **Linked version**; mit **Back to passage** kehrst du zum Text zurück.

Quellenpassage, Behauptung und kreative Entscheidung sind getrennte Einträge. Im Beispiel widersprechen sich ein vorläufiger Bericht und seine Korrektur über den Ort einer Kistenöffnung. Die frühere Fassung bleibt nachvollziehbar. Das ist keine automatische Faktenprüfung; auch die historischen Bilder beweisen die erfundenen Ereignisse nicht.

## Dasselbe mit deinem Manuskript

Der Manuskriptimport unterstützt Markdown (`.md`, `.markdown`) und reinen Text (`.txt`). Word/DOCX- oder Scrivener-Dokumente müssen vorher konvertiert werden. PDFs lassen sich getrennt als Recherchequellen aufnehmen.

Lixity ist kostenlos und Open Source; auch ein kommerzielles Buchprojekt benötigt keine zusätzliche Erlaubnis. Besondere Bedingungen für Softwareintegrationen erläutert die [Lizenzübersicht](../LICENSING.md).

Die lokale Anwendung öffnest du nach der Installation im Browser. Du brauchst derzeit [uv](https://docs.astral.sh/uv/getting-started/installation/) und ein Terminal; Lixity wird als Python-Werkzeug installiert, nicht als klassischer Desktop-Installer. Die [Installationsanleitung für Windows, macOS und Linux](installation.html) ist auf Englisch.

```
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Öffne danach ein neues Terminal und starte die lokale Anwendung:

```
lixity service start --open
```

Öffne ein Projekt oder die Importvorschau für dein Markdown-Manuskript und bestätige die Sprache **Deutsch**. Englisch ist die Voreinstellung; automatische Erkennung ist eine ausdrückliche Wahl. Beginne wieder mit einer Frage und einer Textstelle. Optionale Integrationen haben eigene [Datengrenzen](../research/USAGE.md).

[English tour with more controls](first-look.html) · [Praxisbeispiel zu Wiederholungen (Englisch)](../blog/local-word-echoes.html)

[Über Lixity](../)[Installation](installation.html)[Lizenz](../LICENSING.md)[Website-Messung](../#website-measurement)[Impressum](../#impressum)
