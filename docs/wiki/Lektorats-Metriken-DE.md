# Lektorats-Metriken verstehen 📊

Lixity berechnet quantitative Signale, um Lektorierenden und Schreibenden gezielte Ansatzpunkte für die Überarbeitung zu bieten. Dieser Leitfaden erklärt die wichtigsten Kennzahlen.

---

## 1. Das Grundprinzip: Manuskripteigenes Normalmodell

Lixity vergleicht Ihr Buch **nicht mit externen Richtlinien**, sondern setzt jedes Kapitel und jeden Absatz ins Verhältnis zum **Gesamtstil Ihres eigenen Werks**.

* **Normaler Korridor ($z \le 2$):** Typisches Spektrum Ihres Textes.
* **Milde Abweichung ($z > 2$):** Signifikant anders als der Buchdurchschnitt. Ein guter Ort zum Nachprüfen.
* **Starke Abweichung ($z > 3$):** Seltene Spitze oder starker Registerwechsel (z. B. plötzlicher Satzstakkato in einer Actionszene oder ein sehr langer Monolog).

---

## 2. Kernmetriken im Überblick

### 📏 ASL (Average Sentence Length / Mittlere Satzlänge)
* **Was wird gemessen:** Die durchschnittliche Anzahl der Wörter pro Satz in einem Absatz oder Kapitel.
* **Lektoratspraxis:** Kurze Sätze ($ASL < 8$) erzeugen Tempo, Atemlosigkeit oder Stakkato. Lange Sätze ($ASL > 25$) verlangsamen das Erzähltempo und eignen sich für Reflexion oder Atmosphäre.
* **Signalgruppe:** Zeigt, wo das Tempo innerhalb einer Szene abrupt bricht.

### ⏱️ Tempusverteilung & Tempuswechsel
* **Was wird gemessen:** Häufungen von Präsens- und Vergangenheitsformen auf Satz- und Absatzebene.
* **Lektoratspraxis:** Unbeabsichtigte Tempuswechsel (z. B. unbemerktes Hineinrutschen ins Präsens während einer Präteritum-Erzählung) werden sichtbar gemacht. Rückblenden und Zitate werden im Kontext bewertet.

### 💬 Dialog-Kadenz & Stimmkontrast
* **Was wird gemessen:** 
  * Dialoganteil (in Prozent der Wörter).
  * Kurze Repliken ($1–12$ Wörter) vs. lange Monologe ($\ge 80$ Wörter).
  * Satzlängen-Kontrast zwischen direkter Rede ($ASL_{Dialog}$) und begleitender Narration ($ASL_{Narration}$).
* **Lektoratspraxis:** Stimmen Figuren unterschiedlich schnell? Hebt sich die Erzählerstimme vom gesprochenen Satzrhythmus ab?

### 🔄 Wortwiederholungen & Phrasenechos
* **Was wird gemessen:** Wiederkehr seltener Inhaltswörter oder identischer Mehrwortphrasen im Abstand von wenigen Absätzen (Nahdistanz).
* **Lektoratspraxis:** Hilft bei der Bereinigung unbewusster Wortdopplungen vor der Drucklegung.

### 🔠 Lexikalische Diversität (MTLD & MATTR)
* **Was wird gemessen:** Wortschatzreichtum unabhängig von der reinen Textlänge (robuster als einfache Type-Token-Ratios).
* **Lektoratspraxis:** Erkennung von Wortwiederholungsschleifen in deskriptiven Passagen.

---

## 3. False Discovery Rate (FDR)

Bei Romanen mit 50.000 bis 150.000 Wörtern treten statistische Zufallsabweichungen naturgemäß auf. Lixity wendet moderne Benjamini-Hochberg- bzw. Benjamini-Yekutieli-FDR-Filter an, damit Sie nicht von statistischem Rauschen überflutet werden, sondern nur die substanziellen Textstellen hervorgehoben sehen.
