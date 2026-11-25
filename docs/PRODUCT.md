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
| See why a sentence was marked | Open one counted result in **Manuscript**. Explain the count in your own words and return to the paragraph. [First look](guides/first-look.html#passage) |
| Decide whether to revise a passage | Use **Write** and compare the open draft with the saved text under the same settings. Check what was saved and how to recover earlier text. [Writing workflow](WORKSPACE.md#write-a-manuscript) |
| Revisit the research behind a scene | Open **Research for this passage** and follow a quotation or dossier to the exact retained version. Review matching names and variants when building a character dossier. [Research workflow](WORKSPACE.md#read-a-dossier-beside-the-manuscript) |
| Try a different reveal order | In **Story rehearsal**, write an intended beat and try another order for the cards. Open a scene again when its saved anchor needs review. [Story rehearsal](WORKSPACE.md#compare-scene-evidence-and-rehearse-an-intent) |
| Share the material a reader needs | Export a manuscript PDF, a saved dossier PDF or a reading website with selected chapters and background. Open the prepared copy before sharing. [Reading website](WORKSPACE.md#export-a-reading-website) |
| Hear how a passage reads | Open the **Teleprompter** or record a short reading. Configure a separate service when you need generated speech. [Audio guide](AUDIO.md) |

The Warehouse 4 demo is a fixed example. Use it to show how you can follow a
result to the prose and decide what to revisit. Demonstrate editing, saving and
generating new exports in a synthetic local project. [Demo](demo/report.html)

Scrivener and Papyrus support writing and organization, AutoCrit and
ProWritingAid surface manuscript findings, and Fictionary supports scene-level
developmental editing. Lixity's demonstrable workflow is following counted text
to an editorial choice, keeping an exact citation beside that decision, and
selecting what a reader receives. Compare tools using the same passage and task.
[Workflow comparison and sources](guides/manuscript-analysis-tools.html)

For a repeatable language comparison, record the text, software version,
language profile and project settings. Consult the release notes for shipped
features and the changelog for work on the current branch.
[Methods](METHODS.md) · [Validation and limits](STABILITY.md) ·
[Releases](https://github.com/mfahsold/lixity/releases) ·
[Changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md)

## Implementation and release status

| Area | Available or verified | Next evidence |
| --- | --- | --- |
| Installation | GitHub and PyPI publish the local browser app and CLI. Actions test builds cover Apple Silicon, Intel macOS, Windows x64 and Linux x64. The download guide uses the qualified desktop catalog to show public availability. | Verify the first public desktop candidate on clean systems, then generate the catalog from that release. [Desktop distribution](https://github.com/mfahsold/lixity/blob/main/desktop/README.md#remaining-work-before-distribution) |
| Close reading and revision | The shared workspace links findings to passages, supports draft and saved comparisons, and recovers interrupted editing sessions. Synthetic tests cover the browser workflow and the German and English passage return in macOS WKWebView at standard and compact sizes. | Observe authors and editors completing the same task. Check input methods, assistive technology and the other native WebViews. [Editing workflow](WORKSPACE.md#write-a-manuscript) |
| Research and project recovery | Dossiers retain source and manuscript evidence. Project bundles restore the selected saved text, configuration and archived research. | Exercise a fresh-profile restore and verify saved content hashes and retained evidence. Exercise draft recovery in the original workspace. [Project backup](PROJECT_BACKUP.md) |
| Large projects | The editor reuses measurements for unchanged chapters. Local tests and benchmarks distinguish initial reading, evidence loading, snapshot calculation and archive search. | Measure the complete workflows with the same inputs across the desktop platforms. [Desktop and large-project priorities](RUST_EVALUATION_RFC.md#desktop-and-large-project-priorities) |

## What should come next

### One task from the website to the manuscript

Keep the opening journey focused on a visible result. The homepage and read-only
example show one marked sentence. The download guide identifies the available
channel and platform before showing verification and setup. The welcome screen
offers an existing project, import, writing and a bundled sample. The sample
needs a clear destination and a next action after creation. Start with a counted
passage, then reveal chapter comparison, writing, research and sharing as each
becomes relevant. Keep voice profiles and worker setup in the audio task.
[Download guide](guides/installation.html) · [First session](ONBOARDING.md)

In the next walkthrough, ask a first-time user to distinguish the sample from
a personal manuscript and explain what creating the sample does. Check that
they can open the evidence, close it, continue at the same paragraph and find
**Write** when ready. Repeat with keyboard and touch, a narrow window and
larger text. Verify the same actions in each system WebView before qualifying
its installer.

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
