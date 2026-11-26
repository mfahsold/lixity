# Product direction and capability boundaries

## The promise

Lixity helps writers and editors see how language changes across a manuscript.
Compare chapters, open the text behind a measurement and check the effect of
a revision under the same analysis settings. Keep the exact source behind a
research note within reach. When the draft is ready for feedback, share the
passages and background you choose.

The local workspace includes writing, reading and research. Built-in analysis
runs offline. The **interface** is localized in seven languages (German,
English, French, Spanish, Italian, Portuguese and Dutch); **language-dependent
analysis coverage** varies by language and is deepest for German and English
(English is the default analysis language). [Language support](LOCALIZATION.md) · [Architecture](ARCHITECTURE.md)

## What Lixity counts — and what it cannot prove

| What Lixity counts (L0/L1) | What Lixity cannot prove (L3–L5) |
| --- | --- |
| **Deterministic surface counts:** words, sentences, recognized quotation spans, local phrase echoes and language-profile lexical cues. | **Literary quality or editorial verdicts:** measurements support human review; no deviation is a mistake, a prose grade or an instruction to rewrite. |
| **Internal draft comparisons:** chapter-to-chapter shifts and revision diffs under the same settings (medians, MAD corridors, exploratory `z*` / FDR review shortlists). | **Calibrated significance or reader effect:** baselines belong to the supplied draft, not a genre norm; exploratory shortlists are not calibrated p-values or measured reader reactions. |
| **Explicit evidence links:** passage locations for every count and version-pinned links to retained research records. | **Deep syntax, speaker identity or factual truth:** default cues are lexical heuristics; quotation spans are punctuation-based; optional grammar models remain bounded by documented parser limits; retaining a source does not verify its claim. |

Full formulas live in [Methods](METHODS.md); empirical bounds and known failure modes live in [Validation and limits](STABILITY.md).

## Benefits we can demonstrate

| You want to… | What to show |
| --- | --- |
| See how sentence rhythm changes across chapters | Compare the two chapters in **Analysis overview**. Open the passage and inspect the counted sentences. Return to the draft to decide whether the contrast serves the scene. [Chapter comparison](guides/first-look.html#contrast) |
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
| Chapter comparison | Ask a writer or editor to explain a difference between two chapters, find the contributing text and return to the reading position. Repeat when the comparison is unavailable and check whether they can still find measured passages. Record where they needed help. [Analysis marks and limits](guides/interpretation.html#analysis-marks) |
| Desktop distribution | Verify the exact candidate files and their hashes. Exercise a fresh installation, first launch, upgrade and rollback on each supported system. Open the sample in the installed app. [Installer qualification](https://github.com/mfahsold/lixity/blob/main/desktop/README.md#review-and-publish-one-candidate) |
| Revision and research | Ask an author or editor to make a recoverable change and open a dossier with a pinned source. Check the saved result after reopening, including interruption, conflict or restore when relevant. [Writing and recovery](WORKSPACE.md#write-a-manuscript) |
| Audio | Observe a real capture and playback, including permission handling and microphone selection. Record which runtime was used for any synthesis result. [Author voice](AUDIO.md#author-voice-recording-and-listening) |
| Large projects | Time readiness, readable text, the first evidence jump and return on the same input. Measure archive validation separately from index queries. Keep evidence, saved project data and recovery in the checks when changing implementation. [Desktop and large-project priorities](RUST_EVALUATION_RFC.md#desktop-and-large-project-priorities) |

Keep observation records free of private manuscript text and search terms. Use
the [task-based user study protocol](https://github.com/mfahsold/lixity/blob/main/docs/USER_STUDY_PROTOCOL.md) for structured
author and editor comprehension and usability sessions. For public discovery,
compare visits to the demo and installation guide, search impressions and
clicks over comparable periods. Record language and referral context before
attributing changes to copy or discovery work.

<a id="reuse-before-building"></a>

Build on the existing editor and shared engine. Compare implementation
alternatives on the same inputs and acceptance checks.
[Architecture](ARCHITECTURE.md#evolution-without-a-second-product-path) ·
[Archived product assessment](https://github.com/mfahsold/lixity/blob/d78968750b99ec27e8bfbae195c60bad7ff45fc0/docs/PRODUCT.md)
