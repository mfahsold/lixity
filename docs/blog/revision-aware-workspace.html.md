# Adding a manuscript editor changes more than the text box

By [Matthias Fahsold](https://github.com/mfahsold) · Published 11 November 2026 · Updated 20 November 2026 · 6 minutes

A manuscript workspace can show a useful observation: this chapter uses a different sentence rhythm, this quotation supports a research note, this passage deserves another look. Once the author can edit the manuscript in the same application, each observation needs a second question: which version of the text does it describe?

That is the problem we are working through in Lixity, an open-source local workspace for close reading, linguistic analysis and traceable research. The local app includes the manuscript editor. The public demo is read-only.

<a id="session"></a>

## Preserve the writing session

Choose **Write** in the local manuscript workspace to open the CodeMirror editor. Undo and redo stay available while the editor saves changes in the background. **Saved locally** confirms that the file was updated.

Choose **Close writing** to return to reading. When the file has changed, Lixity reloads the reader and recalculates its analysis. That reload starts a new undo history. If saving fails, the editor stays open so you can review the draft.

<a id="save"></a>

## Treat saving as a conditional operation

A local application still has concurrent writers. An author may open the same Markdown file in another editor, or another process may replace it. Autosave must not treat the last request to arrive as automatically authoritative.

The current implementation detects conflicting external changes and stops ordinary autosave. It keeps the open draft available for review. Conflict and recovery comparison presents identified texts and an editable candidate; applying a result is deliberate and the save checks the revision again.

This is manual comparison, not an automatic merge or a line-by-line diff interface. That is an intentional boundary of the current implementation, not a claim that conflict resolution is solved for every document.

<a id="analysis"></a>

## Bind analysis to the saved text

A measurement can remain mathematically correct for yesterday's manuscript and still be misleading beside today's paragraph. Lixity therefore checks the saved revision when returning to reading and identifies stale analysis.

To edit after reviewing a finding, use its link to the manuscript, then choose **Write**. The editor opens at the visible source block.

The objective is not to hide every boundary. It is to make a boundary understandable when the application cannot cross it reliably.

<a id="evidence"></a>

## Keep evidence separate from changing prose

Research quotations are not live pointers that should silently adopt whatever the author writes next. A retained quotation records what supported a link or decision at the time it was saved.

After manuscript changes, moved, changed or ambiguous relationships need review. The saved quotation remains unchanged. This lets the author distinguish the history of an observation from the current wording of the manuscript.

That separation also limits what the software claims. Retaining a source does not verify its assertions. A statistical signal does not decide whether a sentence should be rewritten. The application connects evidence to human review; it does not replace that review.

<a id="recovery"></a>

## Recovery and backup are different tools

Verified project backup includes the selected saved manuscript, settings, attachments and retained research in its inventory. Restore checks the inventory and uses a fresh destination.

Unsaved drafts and the editor recovery journal are excluded from that backup. Writers should be stopped before taking it. Recovery copies, undo history, reading exports and a verified project backup each cover a different need; presenting them as interchangeable would create false confidence.

The automated tests exercise writing, navigation, conflicts and recovery using synthetic projects, including long manuscripts. Real input methods, assistive technology and interruption scenarios still need acceptance work. Atomic replacement alone is not proof of power-loss durability.

<a id="next"></a>

## Try one revision

In the local app, write a short change and wait for **Saved locally**. Close writing to read the saved passage. The workspace manual shows how to compare versions and keep a separate copy of a draft.

The released reading workflow can already be explored without an account or manuscript upload. The demo uses a fictional harbour manuscript with linked research notes.

[Explore the read-only Lixity workspace](../demo/report.html) [Write a manuscript](https://github.com/mfahsold/lixity/blob/main/docs/WORKSPACE.md#write-a-manuscript) [Source code](https://github.com/mfahsold/lixity)

[All guides](../#guides)[Articles](index.html)[Source code](https://github.com/mfahsold/lixity)[License](https://github.com/mfahsold/lixity/blob/main/docs/LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
