# Product direction and capability boundaries

## The promise

Find the passage you want to work on. Lixity helps you read a manuscript closely,
trace a measurement back to its words and keep the sources that shaped a scene
within reach. When you are ready for feedback, share a reading copy with the
background you choose.

Lixity is designed for novelists revising a manuscript. Editors can use the same
tools to discuss a sentence or compare chapters. The interface supports seven
languages, with different measurement coverage in each. [Language support](LOCALIZATION.md)

## Benefits we can demonstrate

| You want to… | What to show |
| --- | --- |
| See where sentences get shorter | Compare sentence lengths, open a counted sentence and read it in context. Decide whether the change works for the scene. [Analysis workflow](WORKSPACE.md#explore-language-in-the-browser) |
| Go from a finding to a revision | Read the passage, open the Markdown editor and compare the draft with the saved text. Autosave and recovery have documented limits. [Writing workflow](WORKSPACE.md#write-a-manuscript) |
| Revisit the research behind a scene | Follow a linked quotation to a retained source and its saved revision. Keep notes in dossiers and follow links to related claims and decisions. [Research manual](research/USAGE.md) |
| Find a character across the book | Review matching names and configured variants with the surrounding sentences. The matches can help you find passages for a dossier. [Dossier workflow](research/USAGE.md#manuscript-driven-dossier-drafts) |
| Hear how the page reads | Rehearse a passage with the teleprompter or record your reading. Audio synthesis uses separately configured tools or services. [Audio guide](AUDIO.md) |
| Share just the material a reader needs | Export a manuscript PDF, a saved dossier PDF or a reading website with selected background notes. Verify the recipient's copy before sharing. [Workspace manual](WORKSPACE.md#export-a-reading-website) |

The Warehouse 4 demo is a fixed example. Use it to show how you can follow a
result to the prose and decide what to revisit. Demonstrate editing, saving and
generating new exports in a synthetic local project. [Demo](demo/report.html)

For a repeatable language comparison, record the text, software version,
language profile and project settings. Consult the release notes for shipped
features and the changelog for work on the current branch.
[Methods](METHODS.md) · [Validation and limits](STABILITY.md) ·
[Releases](https://github.com/mfahsold/lixity/releases) ·
[Changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md)

## What should come next

These priorities describe evidence to gather for future release decisions.

| Priority | What to verify |
| --- | --- |
| Recoverable revision | Edit, undo, compare saved and draft text and recover from an external change. Check real IME, dead keys, screen readers and interrupted saves. Ask authors where deliberate named checkpoints would help. |
| Findings that lead back to the text | Ask someone to open a measurement, explain why the passage appeared and return to it without help. Include short and multilingual manuscripts. |
| Research you can pick up again | After an edit, distinguish unchanged, moved and ambiguous links. Open a saved dossier PDF and verify its passages and pinned source quotations. |
| A clean first run | Install, update and roll back on macOS, Windows and Linux. Check signing, open an existing project and verify that it can still be edited and exported. [Desktop installer targets](INSTALLATION.md#packaging-direction) |
| A project you can restore | Restore a project in a fresh directory. Verify the inventory, content hashes and retained evidence links. [Project backup](PROJECT_BACKUP.md) |

The previous product assessment records earlier writing and architecture proposals.
[Archived product assessment](https://github.com/mfahsold/lixity/blob/d78968750b99ec27e8bfbae195c60bad7ff45fc0/docs/PRODUCT.md)

<a id="reuse-before-building"></a>

Use the existing editor and shared analysis engine to test these workflows.
Evaluate implementation alternatives against the same inputs and checks.
[Architecture](ARCHITECTURE.md#evolution-without-a-second-product-path) ·
[Archived editor alternatives](MANUSCRIPT_EDITING_RFC.md#evidence-and-alternatives)

## How to judge progress

Start with voluntary sessions on synthetic projects. Record whether a person
completes the task, where they hesitate and whether they can recover their place
or draft. Keep manuscript text and search terms out of the observation record.

For public discovery, compare tour-to-demo and installation-guide visits,
search impressions and clicks over comparable periods. Record the language and
referral context for each period before attributing a change to new copy.
