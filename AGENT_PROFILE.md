# Agent operating rules

Follow the repository's scope, data boundaries, maintainer procedures and
shipped automation contract. [Repository guidance](AGENTS.md) ·
[Maintainer procedures](CONTRIBUTING.md) · [Automation contract](docs/AGENTS.md)

## Work with authors and maintainers

Be direct, curious and precise. Lead with the result or blocker. Describe the
change in the vocabulary of the person using it. Use the visible label when
explaining where to click. If evidence changes the explanation, say what you
observed and revise it. Acknowledge a confirmed mistake and continue from the
corrected facts.

## Verify before asserting

Read the current implementation before describing it. Report what you actually
ran, distinguish verified results from inference, and name unavailable checks.
Passing tests establish only their assertions; confirm that those assertions
cover the requested behavior. Check an issue's premise against the base before
implementing it. Fix an incorrect verification before changing correct code.

For a warning, reproduce it in the emitting runtime and verify the same
operation after the fix. Record deliberate compatibility cases with their
replacement path. [Warning triage](CONTRIBUTING.md#trace-runtime-warnings)

For an interaction regression, assert the author-visible outcome after the
actual trigger. An open disclosure or a Playwright field fill can succeed while
the field starts outside the viewport. Hold a pending response explicitly when
testing ordering.

For an analytical adapter, exercise a measured positive case and an unavailable
case. Compare exact counts, denominators, units and boundary decisions against
the shared analysis result. Check the effective method and settings on both
sides of a delta. When changing comparisons or archive references, exercise an
existing archived record and a missing source. Check that saved revisions and
evidence still point to their original records and that an unavailable
comparison stays visible.

Before moving behavior across Python, Rust or JavaScript, identify which layer
owns the decision and search the other entry points for copies. Move the
decision and its verification together. Once a replacement qualifies, remove
the superseded implementation from the production path. Use a real producer
fixture at the boundary to test values, units and unavailable results.
[Analysis ownership](docs/ARCHITECTURE.md#analysis-ownership-across-python-rust-and-javascript)

For release artifacts, verify the real build output against the input contract
of the pinned publication tool before pushing the tag.
Exercise generated PDF wording with a supported fallback font. A locally
preferred font can hide missing glyphs in the platform fallback.

Select non-sensitive fields before printing diagnostics. Raw webhook URLs,
environment values and service command lines can contain credentials; do not
render those responses wholesale, even during read-only checks.

### Verify the running workspace

For an authorized restart, record the project selections to restore in the
local working context. Reopen them on the same managed port after the restart.
Runtime workspace URLs belong to their server process. Check package version,
running version and source identity, then repeat the affected action in the
appropriate project views. Report which views were restored and which could not
be verified. [Rollout procedure](docs/INSTALLATION.md#refresh-a-checkout-or-a-packaged-service)

## Keep changes reviewable

Inspect `git status --short`, `git diff` and `git diff --stat` after an edit pass.
Investigate unexpected size or scope; undo unrelated formatter changes and
reapply the intended edit surgically. Prefer exact patches for large files.
Read only the relevant symbols and search references before removing code.
Do not repeat large file or tool output when a targeted query answers the question.

## Prevent UI clipping and layout collisions

Check live geometry at the affected breakpoints from 320px to 2560px.

- Propagate the measured height of all sticky bars into paragraph and anchor
  `scroll-margin-top` so the destination remains visible.
- Keep desktop toolbars on one row from 1024px to 2560px. Use progressive
  container-query label collapsing to fit the available toolbar width.
- Open floating cards clear of active sidebars and keep one dismiss control
  per surface.
- Verify `scrollWidth <= clientWidth` for localized controls and labels in
  Playwright before reporting a pass.

## Evolve one current product path

Implement the agreed current behavior; do not add legacy UI modes or parallel
compatibility branches to preserve an obsolete presentation. Identify concrete
data or workflow conflicts and discuss unresolved choices before implementing
them. Existing authorization for a change does not require another design gate.

When existing projects need conversion, provide an explicit, reviewed migration
with backup, validation and recovery instructions through the release workflow
in [CONTRIBUTING.md](CONTRIBUTING.md). Preserve retained source bytes, immutable
revisions and evidence references. Removing an old UI does not authorize deleting
history, rewriting accepted records or inventing an automatic migration command.

## Fail explicitly when an answer is unknown

Undeterminable is different from absent. A failed measurement must return an
unknown value with an explanation, rather than a plausible default. Distinguish
missing, unreadable and malformed input. A fallback that can change a result
must report itself through the existing warning channel; configuration failures
must not silently look like an intentional default. Preserve uncertainty across
library, CLI and HTTP boundaries.

At a plugin boundary, catch ordinary adapter exceptions broadly enough to
report degradation; let interrupts and other `BaseException` subclasses propagate.
Normal valid paths must remain warning-free: the suite runs under `-W error`.

## Verify the requested behavior

Treat acceptance criteria as checkable requirements. Promote durable behavior
to maintained tests; keep one-off issue scripts and reports in ignored
`.planning/` or `/tmp`. Never cite those local files as public documentation.
Use the [affected checks](CONTRIBUTING.md#select-the-checks-for-your-change),
inspect the final diff, and report what passed or remains unverified. Document
intentional public behavior changes in the existing maintained entry points.

For desktop issues, record which surface you exercised. `lixity doctor` can
verify the managed browser service. Browser tests with a mocked bridge cover
UI behavior, while the [desktop checks](desktop/README.md) exercise the Rust
host, its bundled runtime and the real WebView separately. Use synthetic
projects for native verification.

## Record durable project lessons

Treat `/remember` as an explicit request to capture a confirmed decision or
lesson. Keep a note when it is likely to affect future work and has a clear
scope, a concrete example or verification, and a maintained home. Record
operating rules here, maintainer procedures in their guide, and product
contracts where users already look for them. Update the existing guidance in
place. Add a rule for a demonstrated failure only when existing checks leave
that failure uncovered. [Documentation ownership](CONTRIBUTING.md#where-work-belongs)

Keep unresolved hypotheses and one-off session details in ignored local
planning. Keep private manuscript text, research data, credentials and project
paths out of shared lessons. If a lesson is already recorded, refer to the
existing entry.

## Escalation

Ask only for a maintainer decision that the authorized task does not resolve:
a public-contract change, materially different user-visible designs, removal of
a documented capability, or necessary verification unavailable in this environment.
First use the code, tests and history to resolve factual questions. Existing
authorization persists; do not ask to repeat work already requested. A source
change alone does not authorize a release or restart a running service.
