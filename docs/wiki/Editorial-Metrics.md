# Understanding Editorial Metrics 📊

Lixity computes quantitative signals to give authors and editors actionable entry points for revisions.

---

## 1. The Core Principle: Manuscript Normal Model

Lixity evaluates your book **against itself**, comparing chapters and paragraphs to the overall baseline of your own manuscript rather than imposing external rules.

* **Expected baseline ($z \le 2$):** Within the typical stylistic range of your manuscript.
* **Mild deviation ($z > 2$):** Noticeably different from the book's baseline. A helpful invitation to take a second look.
* **Strong deviation ($z > 3$):** A notable peak or register change (e.g., sharp staccato sentences during an action scene, or an unusually long monologue).

---

## 2. Key Metrics Explained

### 📏 ASL (Average Sentence Length)
* **What it measures:** The mean number of words per sentence across a paragraph or chapter.
* **Editorial insight:** Short sentences ($ASL < 8$) convey urgency, speed, or disorientation. Long sentences ($ASL > 25$) slow down pacing, fostering reflection or atmospheric immersion.
* **Signal groups:** Highlights sudden tempo shifts between consecutive scenes.

### ⏱️ Tense Consistency & Modulation
* **What it measures:** Ratio and clustering of present and past verb cues at paragraph level.
* **Editorial insight:** Catches unintentional slippage into present tense during past-tense narration. Intentional flashbacks, reflections, and dialogue remain contextualized.

### 💬 Dialogue Cadence & Voice Contrast
* **What it measures:**
  * Quoted dialogue share as a percentage of total words.
  * Short exchanges ($1–12$ words) versus long speeches ($\ge 80$ words).
  * Sentence length contrast between direct dialogue ($ASL_{Dialogue}$) and narrative prose ($ASL_{Narration}$).
* **Editorial insight:** Do characters speak in distinct rhythms? Does narration feel noticeably longer or shorter than spoken dialogue?

### 🔄 Repetitions & Phrase Echoes
* **What it measures:** Recurrence of distinctive content words or multi-word phrases within close proximity (adjacent paragraphs).
* **Editorial insight:** Helps polish inadvertent word echoes before typesetting and publication.

### 🔠 Lexical Diversity (MTLD & MATTR)
* **What it measures:** Vocabulary richness calculated independent of text length, avoiding the sample-size bias of standard Type-Token Ratios.
* **Editorial insight:** Flags repetitive phrasing loops in descriptive passages.

---

## 3. False Discovery Rate (FDR)

In book-length manuscripts ($50{,}000$ to $150{,}000$ words), random statistical fluctuations naturally occur. Lixity applies Benjamini-Hochberg and Benjamini-Yekutieli FDR corrections so you are presented with meaningful editorial signals rather than statistical noise.
