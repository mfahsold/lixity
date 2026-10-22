# What's new in Lixity 0.7.5: clearer marks and project structure

Updated 22 October 2026 · First posted 16 October 2026 · 8 minutes

Lixity 0.7.5 separates the words a measurement counted from a paragraph's chapter comparison. A local project overview identifies sources, output locations and structural findings without reorganizing files. Section drafts now complete a read/edit/diff/update roundtrip, while research reads avoid unnecessary repeated work. See the [release notes and upgrade details](../releases/v0.7.5.md).

## Sources and outputs in one local view

Open **Project** or run `lixity project --project /path/to/book` for a read-only metadata inspection. Source locations, existing output files and structural findings stay distinct. A file's presence is not proof of freshness, and output provenance remains unknown. The overview moves nothing and is absent from exported reading websites. See [project inspection](../USAGE.md#inspect-project-structure).

## A reading copy without an installation

Choose **Project actions → Reading website** to download a ZIP. A reader can unzip it and open `index.html`, or you can put the folder on a static website host. They need no Lixity installation or account. The copy retains manuscript reading, analysis and navigation; editing, imports and project administration stay in the local app.

The default review workspace includes manuscript analysis and work-marker notes. Two curated formats instead share the novel with selected background material, or a standalone companion without novel text. Choose dossier sections and release chapters in Project settings; readers confirm progress explicitly. For an excerpt, an export chapter limit physically omits later material. Internal Research is an explicit review-workspace choice; original source files always need another opt-in. Local progress only hides content already in the copy. Review the scope before sharing; the download does not publish anything. The [reading website guide](../guides/research-pdf.html#reading-website) explains the workflow and limits.

## Follow the evidence and return to the sentence

Choose a paragraph’s **… → Explore passage → Research for this passage**. Its saved claims and dossiers open in the right context while the manuscript stays visible. A title opens the current entry; **Linked version** opens the exact earlier version used by the association. Expanding **Versions** shows the history without switching the displayed entry. **Back to passage** takes you back to your reading.

The [three-minute first look](../guides/first-look.html) follows this loop in the invented Warehouse 4 project. Its public demo uses the same production website export, with prepared PDF copies linked directly from the page.

## See what was counted and what was compared

Choose the visible metric, then switch **Counted text** and **Paragraph comparison** independently. Violet underlines identify counted words or sentences. Blue/orange raw-value markers and arrows compare notable paragraphs with their chapter, without tinting the prose background. Inspection puts the concrete quotation and count before the separate comparison. A sentence's word count and a paragraph's comparison answer different questions; neither is a quality verdict. The [interpretation guide](../guides/interpretation.html) explains these descriptive signals and their limits.

## Historical notes: Lixity 0.4.8

The following notes describe the 0.4.8 release line, first published on 16 October 2026. They are retained as history. Use the linked guides above for the current interface.

### Small chapters no longer shout

Short texts are noisy. A three-sentence stage note can look extreme in a z-score table — not because the writing is extreme, but because three sentences are simply not much to measure. So comparisons now have a floor, and they tell you when they cannot say something useful:

- Chapters under **100 words** get no z-scores, no effect sizes, no FDR marks.

- Features about sentence variety (staccato, cascade, sentence length variation) need at least **five sentences**.

- Showing/telling comparisons use the same 100-word floor and mark short chapters “not comparable” instead of giving them a ranking.

Unavailable chapter comparisons appear as a dash or “not comparable”. Rebuild older reports before comparing them with newer outputs, because the counting and withholding rules changed. These floors limit comparisons; they do not make the remaining measurements reliable by themselves.

On the same theme: sentence counting now respects blank-line boundaries. A salutation, a stage note or a sign-off stays one unit, and chapter rhythm, scene units and the corpus statistics finally agree with each other.

### The dashboard notices when your manuscript changed

The local dashboard checks your manuscript when the page loads. If the file changed on disk since the last build, it rebuilds itself instead of showing yesterday’s numbers with today’s confidence.

### Review manuscript associations after edits

A manuscript association connects a quote you explicitly select in your draft to an exact saved revision of a research claim. Its anchor records the quote, paragraph identity and source lines. Citations to retained research-source passages are a separate kind of evidence link. When you edit the manuscript, review distinguishes these cases:

- **An unchanged paragraph moved**: a uniquely located anchor is marked *moved*. **A paragraph changed outside the quote**: one remaining exact occurrence of the quote is marked *adjusted*. Both require your explicit acceptance before saving a new anchor revision. Use the review tab or `lixity research reconcile-manuscript --project ./novel draft.md --accept-moved`.

- **Changed inside the quote**: the link stays in review. Lixity never re-pins it on its own, because only you can decide whether the meaning survived.

Small thing, same spirit: you can now type a plain hyphen between years (`1929-1933`). Lixity reads it as the range you meant.

### A calmer research workspace

The research side keeps sources, dossiers, claims, decisions and evidence in one local archive. Recent polish:

- The **timeline is a view**, not a separate world: switch between **List** and **Timeline** right where your claims live. The decisions pane says what it is for — deliberate choices with a reason, not historical claims.

- **Zotero stays a catalogue, visibly.** Cards show a quiet *Zotero ↗* link and a type line; tags filter the list. Capturing a source into your archive is still a deliberate click, never a background sync.

- Evidence panels keep their citations when other lists refresh — nothing you loaded gets rebuilt under your hands.

### One look, everywhere

The interface had accumulated separate choices for corners, text sizes, spacing and loading states. Shared styles and components now give those controls a more consistent presentation:

- **One scale** for corners, text sizes and spacing — shared by the app and the documentation site.

- **Shared controls**: the workspace switch and research tabs use the same control family. Badges, tags and touch spacing follow shared styles.

- **A component layer** now renders the list panels (plain vendored JavaScript, no build step). It also fixed a real annoyance: the “Loading…” placeholder no longer lingers next to the loaded list.

- Regression checks cover selected shared styles and loading states to help catch inconsistent changes.

### Logs you can actually find

Diagnostics now go through one logging setup: one line format, standard levels, and a log file that stays bounded (older entries are rotated, not deleted silently). `--debug`, `LIXITY_DEBUG` and `LIXITY_LOG_LEVEL` choose how much you see, and `lixity service status` prints the path. Request logs keep the route but never the query string, so research context and project tokens stay out of the file — and log records never contain manuscript text.

### Your privacy, in plain words

Built-in analysis and dashboard generation run on your computer without cloud calls or an account. Optional integrations and separately configured workers have their own setup and data handling. The browser page only runs the scripts that ship with it (that is what the strict Content Security Policy means). Loopback bind, host allow-list, payload limits and explicit non-goals are written down in the project’s `SECURITY.md`. The statistical signals support your review; they are not a quality score, and they are not an instruction to rewrite your prose.

## Try it

- [Demo report](../demo/report.html) — invented text, opens in your browser, no install.

- [Effi Briest](../examples/effi-briest.html) and [Pride and Prejudice](../examples/pride-and-prejudice.html) — literary case studies with interactive opening-chapter dashboards and PDF analyses of the complete public-domain novels.

- [First look](../guides/first-look.html) — a three-minute tour of chapter comparisons and paragraphs with local measurements.

- For your own manuscript: `uv tool install --python 3.12 --managed-python lixity`, then `lixity service start --open`.

If you try it: tell me which passage surprised you — that is the feedback that shapes the next release.

[All guides](../#guides)[Articles](../blog/index.html)[Source code](https://github.com/mfahsold/lixity)[License](../LICENSING.md)[Website measurement](../#website-measurement)[Legal notice](../#impressum)
