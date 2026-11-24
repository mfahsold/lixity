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

## Implementation and release status

| Area | Available or verified | Next evidence |
| --- | --- | --- |
| Installation | The published Python package serves the local browser app and CLI. Native test installers cover Apple Silicon, Intel macOS, Windows x64 and Linux x64. | Verify signed packages on clean systems, then generate the public download catalog from the verified release. [Desktop distribution](https://github.com/mfahsold/lixity/blob/main/desktop/README.md#remaining-work-before-distribution) |
| Close reading and revision | The shared workspace links findings to passages, supports draft and saved comparisons, and recovers interrupted editing sessions. Synthetic tests cover the browser workflow and the German and English passage return in macOS WKWebView at standard and compact sizes. | Observe authors and editors completing the same task. Check input methods, assistive technology and the other native WebViews. [Editing workflow](WORKSPACE.md#write-a-manuscript) |
| Research and project recovery | Dossiers retain source and manuscript evidence. Project bundles restore the selected saved text, configuration and archived research. | Exercise a fresh-profile restore and verify saved content hashes and retained evidence. Exercise draft recovery in the original workspace. [Project backup](PROJECT_BACKUP.md) |
| Large projects | The editor reuses measurements for unchanged chapters. Local tests and benchmarks distinguish initial reading, evidence loading, snapshot calculation and archive search. | Measure the complete workflows with the same inputs across the desktop platforms. [Desktop and large-project priorities](RUST_EVALUATION_RFC.md#desktop-and-large-project-priorities) |

## What should come next

### First public desktop release

Prepare one version and source commit. Verify the signed candidate for the
four desktop targets, then complete fresh installation, upgrade and rollback
for the seven installer files. Qualify the exact file hashes before publishing.
Verify the published install links and first-run instructions in the seven
interface languages. [Installer qualification](https://github.com/mfahsold/lixity/blob/main/desktop/README.md#review-and-publish-one-candidate)

### Author and editor pilot

Use the same synthetic project for the first launch, a passage review and a
saved change. Ask participants to follow a finding, explain what was measured,
and return to the text. Include a recoverable edit and a dossier with a pinned
source. Capture completion, friction and accessibility observations. Run native
checks for the platform-specific interactions separately from the browser suite.
[Workspace manual](WORKSPACE.md) · [Test selection](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#select-the-checks-for-your-change)

### Next performance and revision improvements

Compare candidate improvements on the same input, source revision and platform
before changing the underlying implementation. Keep project preservation and
traceable evidence in the acceptance checks.

| Priority | What to verify |
| --- | --- |
| Large-project reading | Compare launch to first readable passage, evidence latency, scroll frame times and memory. Start with the existing live-reader workload on each desktop WebView. |
| Revision workflow | Verify interrupted saves, undo and edits from multiple windows. Gather examples where a named revision checkpoint would help during real work. |
| Archive search | Measure validated archive reads and index queries separately. Preserve exact citations and detection of changed or unavailable sources. |

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
