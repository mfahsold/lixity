# Adding a manuscript editor changes more than the text box

By [Matthias Fahsold](https://github.com/mfahsold) · Published 11 November 2026 · 6 minutes

A manuscript workspace can show a useful observation: this chapter uses a different sentence rhythm, this quotation supports a research note, this passage deserves another look. Once the author can edit the manuscript in the same application, each observation needs a second question: which version of the text does it describe?

That is the problem we are working through in Lixity, an open-source local workspace for close reading, linguistic analysis and traceable research. The integrated editor described here is implemented in development and remains **unreleased**. The public demo is read-only.

## Preserve the writing session

Lixity's development editor uses CodeMirror 6. The practical goal is modest: write, undo, inspect the result, and return without rebuilding the writing session.

Moving to the reading view should not discard the editor and its undo history. “Read and refresh” opens the ordinary workspace for the saved text revision while retaining the writing buffer. Returning to writing keeps that session available. Browser reload is a different boundary: it still resets undo.

That distinction matters. “Undo survives autosave” does not mean “undo survives every failure.” The product needs to say what is kept, where it is kept, and which actions end a session.

## Treat saving as a conditional operation

A local application still has concurrent writers. An author may open the same Markdown file in another editor, or another process may replace it. Autosave must not treat the last request to arrive as automatically authoritative.

The current implementation detects conflicting external changes and stops ordinary autosave. It keeps the open draft available for review. Conflict and recovery comparison presents identified texts and an editable candidate; applying a result is deliberate and the save checks the revision again.

This is manual comparison, not an automatic merge or a line-by-line diff interface. That is an intentional boundary of the current implementation, not a claim that conflict resolution is solved for every document.

## Bind analysis to the saved text

A measurement can remain mathematically correct for yesterday's manuscript and still be misleading beside today's paragraph. Lixity therefore checks the saved revision when returning to reading and identifies stale analysis.

The same principle applies to navigation. Opening a passage in the editor requires a defensible mapping to source text. Literal selections within one paragraph have revision-aware mapping. Transformed Markdown and cross-paragraph selections can be reported as unmappable. Guessing at a location would look convenient until it edits the wrong passage.

The objective is not to hide every boundary. It is to make a boundary understandable when the application cannot cross it reliably.

## Keep evidence separate from changing prose

Research quotations are not live pointers that should silently adopt whatever the author writes next. A retained quotation records what supported a link or decision at the time it was saved.

After manuscript changes, moved, changed or ambiguous relationships need review. The saved quotation remains unchanged. This lets the author distinguish the history of an observation from the current wording of the manuscript.

That separation also limits what the software claims. Retaining a source does not verify its assertions. A statistical signal does not decide whether a sentence should be rewritten. The application connects evidence to human review; it does not replace that review.

## Recovery and backup are different tools

The development work also includes verified project backup and restore. The selected saved manuscript, settings, attachments and retained research have an explicit inventory and integrity checks. Restore uses a fresh destination rather than overwriting an existing project.

Unsaved drafts and the editor recovery journal are excluded from that backup. Writers should be stopped before taking it. Recovery copies, undo history, reading exports and a verified project backup each cover a different need; presenting them as interchangeable would create false confidence.

The automated tests exercise writing, navigation, conflicts and recovery using synthetic projects, including long manuscripts. Real input methods, assistive technology and interruption scenarios still need acceptance work. Atomic replacement alone is not proof of power-loss durability.

## A useful next milestone

For us, the next milestone is a recoverable revision session: an author can write, inspect the saved result, understand a conflict and return to work without losing their place. More analysis metrics can wait until that loop is dependable.

The released reading workflow can already be explored without an account or manuscript upload. The demo uses a fictional harbour manuscript with linked research notes.

[Explore the read-only Lixity workspace](../demo/report.html) [Review the editor's development scope](../WORKSPACE.md#write-a-manuscript-unreleased) [Source code](https://github.com/mfahsold/lixity)

[All guides](../#guides)[Articles](index.html)[Source code](https://github.com/mfahsold/lixity)[License](../LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
