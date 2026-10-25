# Eine Frage, ein Dossier, zurück zur Szene.

Lixity ist eine lokale Recherche- und Überarbeitungswerkstatt für Autorinnen, Autoren und Lektorat. Quellen, Textstellen und eigene Entscheidungen bleiben verbunden. Sprachmuster lassen sich am Text untersuchen; die Entscheidung über die Prosa bleibt beim Menschen.

Aktualisiert am 25. Oktober 2026

## Eine Frage statt eines Zielwerts

Warum klingt dieses Kapitel anders als der Rest? Ist eine Wiederholung beabsichtigt? Auf welcher Quelle beruht dieses Detail? Für einen ersten Versuch genügt eine dieser Fragen.

[Eine Frage in der Demo prüfen](../demo/report.html)

Die schreibgeschützte Demo verwendet ein erfundenes englisches Hafenmanuskript und englische Bedienelemente. Diese Seite erklärt den Einstieg auf Deutsch; sie ist keine deutsche Fassung des Demo-Manuskripts. Kein Konto, keine Installation und kein Upload sind zum Ausprobieren nötig.

Die beiden folgenden Wege beantworten unterschiedliche Fragen: [Welche Quellenfassung trägt die Szene?](#recherche) Oder: [Wie verändert sich der Satzrhythmus?](#rhythmus) Ein einziger nachvollziehbarer Prüfschritt genügt für den Einstieg.

## Welche Quellenfassung trägt die Szene?

Eine vorläufige Notiz verortet die Öffnung einer Kiste am Kai. Ihre unterzeichnete Korrektur nennt dagegen die Zollstation am nächsten Morgen. Der Unterschied entscheidet darüber, was in der nächtlichen Szene bereits sichtbar sein kann.

1. In der [Demo unter **Research → Dossiers**](../demo/report.html#research-manager) das Dossier **Warehouse 4 case notes** öffnen. Es hält die Recherche zur Szene zusammen.

2. Unter **Claims** die Aussage **Where the crate was opened** untersuchen. Die verknüpften Quellenpassagen enthalten die vorläufige Notiz und ihre Korrektur. Die aktuelle Aussage und ihre frühere Fassung bleiben unterscheidbar.

3. Unter **Decisions** die Entscheidung **Keep the inspection at dawn** lesen: Die Kiste bleibt in den Kaiszenen geschlossen; ihr Inhalt wird erst nach dem Transport entdeckt. Beide Quellenpassagen bleiben erhalten.

**Das Ergebnis:** Eine Entscheidung ist mit ihrem Grund wiederauffindbar. Lixity hat weder den Widerspruch selbst aufgelöst noch eine Szene umgeschrieben. Die hier zitierten Quellenpassagen und Ereignisse sind erfunden; es handelt sich um eine Funktionsdemonstration, keine historische Fallstudie.

**Von der Textstelle ins Dossier und wieder zurück**

**Aktueller main-Stand:** Neutrale punktierte Markierungen und der Knopf mit Buchsymbol **Research** kennzeichnen gespeicherte Recherchebezüge. Durchgezogene Analyse-Unterstreichungen zeigen dagegen gezählte Textstellen. Recherchebezüge bleiben auch bei ausgeschalteter Analyse sichtbar.

Am Eröffnungsabsatz führt **… → Explore passage → Research for this passage** zur gespeicherten Verbindung. Ein Titel öffnet den Eintrag; **Linked version** zeigt die genau verknüpfte frühere Fassung. **Back to passage** führt zum Text zurück. **Dossier alongside** hält das Dossier neben dem Manuskript geöffnet.

Quellenpassage, Behauptung und kreative Entscheidung sind getrennte Einträge. Eine gespeicherte Verbindung ist keine automatische Faktenprüfung; auch die historischen Bilder beweisen die erfundenen Ereignisse nicht.

## Passt der kürzere Rhythmus zur Handlung?

1. In der Demo **Inspect chapter 2** wählen und den Anfang von *The Loose Board* lesen: „A board moved. Mara turned.“ Mara versucht, eine Kiste festzuhalten.

2. Beim Absatz **… → Explore passage → Explain measurement** öffnen. Die Erklärung zeigt die gezählten Sätze und Wörter. **Counted text** blendet die Markierungen ein.

3. Über **opening chapter** in der Aufgabenkarte die Hafenbeschreibung im ersten Kapitel vergleichen. Was ändert sich beim Lesen, nicht nur in der Zahl?

**Mögliche Entscheidung:** Den Kontrast beibehalten, weil die kurzen Sätze körperliche Handlungen voneinander trennen. Klingt die Stelle beim Vorlesen dagegen unbeabsichtigt abgehackt, lässt sich im eigenen Entwurf eine Handlung mit ihrer Folge verbinden. Kürzer ist nicht automatisch besser. Der Durchschnitt ist kein Schreibziel.

Der Prüfschritt ist gelungen, wenn sich der Unterschied am Text erklären lässt. Dafür sind weder alle Messgrößen noch eine „Korrektur“ nötig. Das kurze Beispiel demonstriert den Arbeitsgang, nicht die statistische Zuverlässigkeit für jedes Manuskript.

## Mit einem eigenen Manuskript arbeiten

Der Manuskriptimport unterstützt Markdown (`.md`, `.markdown`) und reinen Text (`.txt`). Word/DOCX- oder Scrivener-Dokumente müssen vorher konvertiert werden. PDFs lassen sich getrennt als Recherchequellen aufnehmen.

Lixity ist kostenlos und Open Source; auch ein kommerzielles Buchprojekt benötigt keine zusätzliche Erlaubnis. Besondere Bedingungen für Softwareintegrationen erläutert die [Lizenzübersicht](../LICENSING.md).

Die lokale Anwendung läuft nach der Installation im Browser. Voraussetzung sind derzeit [uv](https://docs.astral.sh/uv/getting-started/installation/) und ein Terminal; Lixity wird als Python-Werkzeug installiert, nicht als klassischer Desktop-Installer. Die [Installationsanleitung für Windows, macOS und Linux](installation.html) ist auf Englisch.

```
uv tool install --python 3.12 --managed-python lixity
uv tool update-shell
```

Danach in einem neuen Terminal die lokale Anwendung starten:

```
lixity service start --open
```

Ein Projekt oder die Importvorschau für das Markdown-Manuskript öffnen und die Sprache **Deutsch** bestätigen. Englisch ist die Voreinstellung; automatische Erkennung ist eine ausdrückliche Wahl. Die eingebaute Analyse läuft lokal. Optionale Integrationen haben eigene [Datengrenzen](../research/USAGE.md).

Die öffentliche Demo folgt dem aktuellen Hauptzweig und kann unveröffentlichte Änderungen zeigen. Das installierbare Paket und sein Funktionsumfang sind über die [Versionshinweise](../releases/v0.7.5.md) und `lixity --version` prüfbar. Die Demo kann weder importieren noch Änderungen speichern.

[English tour with more controls](first-look.html) · [Praxisbeispiel zu Wiederholungen (Englisch)](../blog/local-word-echoes.html)

[Über Lixity](../)[Installation](installation.html)[Lizenz](../LICENSING.md)[Website-Messung](../#website-measurement)[Impressum](../#impressum)
