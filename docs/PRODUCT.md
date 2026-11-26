# Product direction and capability boundaries

## The promise

Lixity helps writers revise a manuscript and editors discuss it in context.
Open the passage behind a measurement, decide what to revisit and keep the
exact source behind a research note within reach. When the draft is ready for
feedback, share the passages and background you choose.

The local workspace includes writing, reading and research. Built-in analysis
runs offline. The interface supports seven languages. Measurement coverage
varies by language. [Language support](LOCALIZATION.md) · [Architecture](ARCHITECTURE.md)

## Benefits we can demonstrate

| You want to… | What to show |
| --- | --- |
| See why a sentence was marked | Open a counted result in **Manuscript**, explain the count and return to the paragraph. [First look](guides/first-look.html#passage) |
| Decide whether to revise a passage | Compare the draft with the saved text in **Write** under the same settings. Check which version was saved and how to recover earlier text. [Writing and recovery](WORKSPACE.md#write-a-manuscript) |
| Revisit the research behind a scene | Open **Research for this passage** and follow a quotation or dossier to its retained version. [Dossiers beside the manuscript](WORKSPACE.md#read-a-dossier-beside-the-manuscript) |
| Try a different reveal order | Write an intended beat in **Story rehearsal** and try another order for the cards. Review a card again after the associated text changes. [Story rehearsal](WORKSPACE.md#compare-scene-evidence-and-rehearse-an-intent) |
| Hear how a passage reads | Rehearse in the **Teleprompter** or record a short reading. Set up the selected speech service to generate audio. [Audio guide](AUDIO.md) |
| Share the material a reader needs | Prepare a manuscript PDF, a saved dossier PDF or a reading website with the chapters and background you select. Check the prepared copy before sharing. [Reading website](WORKSPACE.md#export-a-reading-website) |

The [Warehouse 4 demo](demo/report.html) is a fixed example for close reading.
Use a synthetic local project to demonstrate editing, saving, recovery and
new exports. Use the same passage and task when assessing other tools.
[Workflow comparison and sources](guides/manuscript-analysis-tools.html)

## Capability boundaries

- **Measurements support review.** Show the words, the counting rule and any
  limit that affects interpretation. Identify the version, text, language
  profile and settings when comparing results.
  [Methods](METHODS.md) · [Validation and limits](STABILITY.md)
- **The project holds its text, decisions and evidence.** Saved references can
  point to a specific source revision. Review the selected project and file
  inventory when exporting, backing up or restoring.
  [Research guide](research/USAGE.md) · [Project backup](PROJECT_BACKUP.md)
- **Recording and generated speech have distinct setup needs.** Recording
  needs access to the selected microphone. Synthesis needs the chosen optional
  runtime or a configured provider. An explicitly selected remote provider
  receives the text required for rendering. [Audio guide](AUDIO.md)

<a id="implementation-and-release-status"></a>

## Installation and availability

The [download guide](guides/installation.html#desktop) leads with the desktop
app and the setup steps for each system. It identifies which downloads are
qualified public releases and which are Actions test builds. The local browser
app and CLI are published on GitHub and PyPI. The first project funding is
intended for the public desktop installer rollout and the Android and iOS /
iPadOS ports. [Project funding and payment status](guides/support.html)
[Desktop distribution](https://github.com/mfahsold/lixity/blob/main/desktop/README.md#public-desktop-downloads) ·
[Releases](https://github.com/mfahsold/lixity/releases) ·
[Changelog](https://github.com/mfahsold/lixity/blob/main/CHANGELOG.md)

<a id="what-should-come-next"></a>

## How to judge progress

| Workflow | Evidence to collect |
| --- | --- |
| First session | Ask a first-time user to choose the offline sample, confirm its destination, explain one finding and return to the same paragraph. Then ask them to find **Write**. Repeat with keyboard, touch, larger text and a narrow window. [First session](ONBOARDING.md) |
| Desktop distribution | Verify the exact candidate files and their hashes. Exercise a fresh installation, first launch, upgrade and rollback on each supported system. Open the sample in the installed app. [Installer qualification](https://github.com/mfahsold/lixity/blob/main/desktop/README.md#review-and-publish-one-candidate) |
| Revision and research | Ask an author or editor to make a recoverable change and open a dossier with a pinned source. Check the saved result after reopening, including interruption, conflict or restore when relevant. [Writing and recovery](WORKSPACE.md#write-a-manuscript) |
| Audio | Observe a real capture and playback, including permission handling and microphone selection. Record which runtime was used for any synthesis result. [Author voice](AUDIO.md#author-voice-recording-and-listening) |
| Large projects | Time readiness, readable text, the first evidence jump and return on the same input. Measure archive validation separately from index queries. Keep evidence, saved project data and recovery in the checks when changing implementation. [Desktop and large-project priorities](RUST_EVALUATION_RFC.md#desktop-and-large-project-priorities) |

Keep observation records free of private manuscript text and search terms. For
public discovery, compare visits to the demo and installation guide, search
impressions and clicks over comparable periods. Record language and referral
context before attributing changes to copy or discovery work.

<a id="reuse-before-building"></a>

Build on the existing editor and shared engine. Compare implementation
alternatives on the same inputs and acceptance checks.
[Architecture](ARCHITECTURE.md#evolution-without-a-second-product-path) ·
[Archived product assessment](https://github.com/mfahsold/lixity/blob/d78968750b99ec27e8bfbae195c60bad7ff45fc0/docs/PRODUCT.md)
