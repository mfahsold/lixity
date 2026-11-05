# Schnelleinstieg in Lixity

Die [bebilderte Einführung](https://mfahsold.github.io/lixity/guides/first-look-de.html)
führt durch das gemeinsame Demoprojekt. In der
[schreibgeschützten Demo](https://mfahsold.github.io/lixity/demo/report.html)
kannst du ohne Installation lesen und recherchieren.

## 1. Installation

Die [Installationsanleitung](https://mfahsold.github.io/lixity/INSTALLATION.md)
beschreibt die isolierte Installation, Voraussetzungen und Updates.
Optionale Sprachdienste benötigen eine eigene Umgebung.

## 2. Den lokalen Arbeitsbereich starten

```sh
lixity service start --open
```

Die Standardadresse ist `http://127.0.0.1:8765/`.

## 3. Ein Manuskript laden

**Projekt öffnen** verbindet einen vorhandenen Projektordner samt Recherchearchiv.
**Manuskript analysieren** zeigt eine Importvorschau und erstellt nach Bestätigung
eine Kopie in einem neuen Projekt. Diese beiden Aktionen sind nicht austauschbar.

Für Markdown verwende UTF-8 und Kapitelüberschriften wie `## Kapitelname`, sofern
das Projekt kein eigenes Kapitelmuster festlegt. Der noch unveröffentlichte
Dateiimport akzeptiert auch jeweils eine `.txt`- oder `.docx`-Datei.
Prüfe Zielordner und Analysesprache vor dem Bestätigen. Englisch ist die
Standardsprache; automatische Spracherkennung muss ausdrücklich gewählt werden.

## 4. Die drei Hauptansichten

Lies zunächst einen Absatz im **Manuskript**. Schalte **Analyse** ein, wenn du
Messwerte sehen möchtest; das Absatzmenü **…** öffnet die Werkzeuge zur Textstelle.
**Recherche** enthält Quellen, Thesen und Dossiers. Unter **Projekt** findest du
Projektverwaltung und Einstellungen. Ein Ansichtswechsel speichert keine
Entscheidung und verändert den Text nicht.

Das [UI-Handbuch](https://mfahsold.github.io/lixity/WORKSPACE.md), die
[CLI-Referenz](https://mfahsold.github.io/lixity/USAGE.md) und das
[Audio-Handbuch](https://mfahsold.github.io/lixity/AUDIO.md) beschreiben die weiteren
Schritte auf Englisch. Nach einem Serverneustart öffnest du das Projekt erneut
über die Startseite; alte Projektansichts-URLs sind dann ungültig.
