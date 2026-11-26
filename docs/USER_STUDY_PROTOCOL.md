# Task-based user study protocol

## 1. Purpose and scope

Automated tests verify deterministic counts, interface layout and save/recovery
contracts, but they do not establish whether authors and editors understand
Lixity's measurements or complete revision tasks without misinterpreting them
([Validation and limits](STABILITY.md#core-validation-status)).

This protocol defines a repeatable, task-based usability and comprehension
study with **5–8 authors and editors** to evaluate:

1. **Passage traceability:** whether participants can trace a chapter or
   paragraph deviation candidate back to its exact passage and return to their
   reading position.
2. **Epistemic comprehension:** whether participants accurately separate
   **what Lixity counted (L0/L1)** from **editorial interpretation (L3)** and
   **literary-quality verdicts (L5)**, and where interface copy causes
   over-interpretation.
3. **Edit / save / reopen roundtrip:** whether participants can make a
   deliberate edit in **Write**, confirm local saving, observe recalculated
   counts and verify persistence after reopening the project.

## 2. Participants and recruitment

- **Sample size:** 5–8 participants (aim for a balanced mix of fiction or
  long-form non-fiction authors and developmental or line editors).
- **Language background:** Native or professional working proficiency in German
  and/or English (matching Lixity's deepest analysis profiles).
- **Exclusion criteria:** Contributors who have authored Lixity code, copy or
  documentation are excluded from the participant pool.
- **Session length:** 45–60 minutes per participant, conducted individually
  (in person or via screen-sharing video call) using think-aloud narration.

## 3. Environment and materials

- **Build:** Record the exact Lixity version (`lixity --version` or **About
  Lixity**), operating system, desktop vs. browser surface and viewport width.
- **Fixture:** Use a synthetic or public-domain project (never a participant's
  unpublished private manuscript during a recorded study session):
  - **English sessions:** an editable local copy of the synthetic *Warehouse 4*
    project (`samples/first-look.md` / **Try the example offline**).
  - **German sessions:** an editable local copy of a short synthetic or
    public-domain German chapter fixture (e.g., *Effi Briest* opening chapters).
- **Reset:** Start every session from a fresh, unmodified copy of the fixture
  with default settings (`Analysis Off` on initial load).

## 4. Session procedure and participant prompts

### Briefing (5 minutes)

Explain think-aloud narration, emphasize that the software — not the
participant — is being tested, and confirm informed consent before starting.

- **EN prompt:** *"We are testing whether Lixity's explanations and controls
  are clear. There are no right or wrong answers. Please say out loud what you
  expect to happen and what you think a number means. You can pause or stop at
  any time."*
- **DE prompt:** *"Wir prüfen, ob die Erklärungen und Bedienelemente von Lixity
  verständlich sind. Es gibt keine richtigen oder falschen Antworten. Bitte
  sprechen Sie laut aus, was Sie erwarten und was eine Zahl Ihrer Meinung nach
  bedeutet. Sie können jederzeit pausieren oder abbrechen."*

### Task 1 — Trace a deviation candidate back to its passage (10–15 minutes)

- **EN prompt:** *"Open the analysis overview and find one chapter or passage
  that stands out from the rest of the draft. Tell me in your own words what
  Lixity counted there. Then jump to the exact passage in the manuscript, read
  its surrounding paragraph, and return to where you started."*
- **DE prompt:** *"Öffnen Sie die Analyse-Übersicht und suchen Sie ein Kapitel
  oder eine Textstelle, die vom Rest des Entwurfs abweicht. Erklären Sie in
  eigenen Worten, was Lixity dort gezählt hat. Springen Sie dann zur genauen
  Textstelle im Manuskript, lesen Sie den umgebenden Absatz und kehren Sie zu
  Ihrem Ausgangspunkt zurück."*
- **Success criteria:** Participant locates a flagged chapter/passage, reaches
  the exact passage in **Manuscript**, inspects its explanation or values, and
  returns cleanly without losing orientation.

### Task 2 — Misinterpretation and limits probe (10 minutes)

Immediately after Task 1, probe how the participant interprets the measurement.

- **EN prompt:** *"Based only on what Lixity showed you for that passage, does
  this mean the passage has a writing problem or needs to be rewritten? What
  can this number tell you, and what can it not tell you?"*
- **DE prompt:** *"Bedeutet das, was Lixity Ihnen für diese Stelle gezeigt hat,
  dass hier ein Schreibfehler vorliegt oder der Text umgeschrieben werden muss?
  Was kann diese Zahl aussagen – und was nicht?"*
- **Follow-up (if the participant mentions statistical flags or language
  support):** Ask what they think an exploratory `z*` / FDR mark means, or
  whether they expect equal analysis depth across all seven interface
  languages.

### Task 3 — Edit, save and reopen roundtrip (10–15 minutes)

- **EN prompt:** *"Suppose you decide to revise two sentences in that passage.
  Switch to the writing view, make a small edit, and verify that your change is
  saved locally. Return to reading to check how the measurement changed. Then
  close and reopen the project (or reload the page) and confirm your edit is
  still there."*
- **DE prompt:** *"Angenommen, Sie möchten zwei Sätze an dieser Stelle
  überarbeiten. Wechseln Sie in den Schreibmodus, nehmen Sie eine kleine
  Änderung vor und prüfen Sie, ob sie lokal gespeichert wurde. Kehren Sie zum
  Lesen zurück und beobachten Sie, wie sich die Messung verändert. Schließen
  und öffnen Sie danach das Projekt erneut (oder laden Sie die Seite neu) und
  prüfen Sie, ob Ihre Änderung erhalten geblieben ist."*
- **Success criteria:** Participant enters **Write**, edits text, recognizes
  the **Saved locally** confirmation, observes refreshed analysis after closing
  **Write**, and confirms persistence after reopening.

### Task 4 (Optional) — Research dossier and version pin check (5–10 minutes)

- **EN prompt:** *"Open the research linked to a passage in Chapter 1. Can you
  tell the difference between what the source record says now and the version
  that was linked when the note was saved?"*
- **DE prompt:** *"Öffnen Sie die Recherche zu einer Textstelle in Kapitel 1.
  Können Sie erkennen, worin sich der aktuelle Stand der Quelle von der
  verknüpften Fassung unterscheidet?"*

### Debrief (5 minutes)

Ask which label, chart or step was most confusing and what single change would
have made the session clearer.

## 5. Misinterpretation and friction logging

Record observations in a structured table using pseudonymized IDs (`P01`–`P08`):

| Field | Values / guidance |
| --- | --- |
| `participant_id` | Pseudonymized code (`P01`–`P08`), role (`author` / `editor`), session language (`de` / `en`) |
| `task_id` | `T1`, `T2`, `T3`, `T4` |
| `timestamp` | Elapsed `MM:SS` from session start |
| `completion_code` | `0` (failed/abandoned), `1` (completed with hint), `2` (completed independently) |
| `epistemic_code` | `0` (verdict/proof slip), `1` (partial distinction), `2` (clean L0/L1 vs. L3/L5 distinction) |
| `misinterpretation_type` | `none`, `quality_verdict_slip`, `significance_slip`, `grammar_or_speaker_overclaim`, `language_parity_assumption`, `save_state_uncertainty`, `navigation_disorientation` |
| `trigger_surface` | Exact UI panel, label or control name where the issue occurred |
| `observation` | Factual summary of behavior and short verbatim quote (no private text) |

## 6. Inter-rater coding rubric

Two raters independently code every session log (or transcript excerpt) for
`completion_code`, `epistemic_code` and `misinterpretation_type`:

### Task completion (`completion_code`)

- **2 — Independent completion:** Completes all required steps without
  facilitator intervention.
- **1 — Assisted completion:** Completes after one neutral prompt or UI hint
  (facilitator records the exact hint given).
- **0 — Incomplete / abandoned:** Cannot complete, gives up, or finishes in an
  unintended state (e.g., leaves unsaved changes thinking they were saved).

### Epistemic accuracy (`epistemic_code`)

- **2 — Accurate distinction:** Correctly states what Lixity counted (L0/L1)
  and recognizes that deciding whether to revise requires reading the passage
  in context (L3), not following a score.
- **1 — Partial distinction:** Hedges or mixes surface counts with vague
  quality assumptions (e.g., *"it probably means the chapter is too dense,
  though maybe it's intentional"*).
- **0 — Misinterpretation / verdict slip:** Treats a count, deviation or flag
  as proof of an error, grammatical failure, statistical significance or low
  literary quality (L5).

### Agreement and reconciliation

- Compute exact percentage agreement and Cohen's $\kappa$ (or Krippendorff's
  $\alpha$ if more than two raters participate) across all coded task items
  before reconciliation.
- Record all disagreements in a reconciliation table and resolve them by
  consensus; report both pre-reconciliation agreement and reconciled counts.

## 7. Privacy, consent and data handling

- **Informed consent:** Obtain written or recorded verbal consent before each
  session, explaining what is logged, whether screen/audio is recorded, how
  long recordings are retained, and the right to withdraw without penalty.
- **No private manuscripts:** Participants work exclusively on the provided
  synthetic or public-domain fixture during recorded sessions. Do not collect
  unpublished author prose, private research archives or personal search terms.
- **Storage boundary:** Store raw recordings, consent forms and identity-to-ID
  keys exclusively in local private storage outside the Git repository (never
  under `docs/` or tracked paths; see [Where work belongs](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#where-work-belongs)).
- **Publication:** Publish only aggregated counts, anonymized quotes (stripped
  of identifying details) and concrete UI/copy revisions.

## 8. Reporting and methodological limits

Every study report produced under this protocol must include:

1. Exact Lixity build version, OS/browser matrix and fixture identifier.
2. Participant count, role split (authors vs. editors) and session language
   split (DE vs. EN).
3. Task completion counts (`0` / `1` / `2`), epistemic accuracy counts
   (`0` / `1` / `2`), misinterpretation frequencies by category and
   pre-reconciliation inter-rater agreement.
4. Concrete copy, layout or workflow changes motivated by the findings.

**Scope limit:** A qualitative task-based study with 5–8 participants is
designed to surface comprehension hazards, navigation friction and copy
defects. It does not establish population-level prevalence, statistically
representative usability rates or general literary-editing efficacy.
