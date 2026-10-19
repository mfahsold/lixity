# Agent operating rules

Read with [AGENTS.md](AGENTS.md), which defines repository scope and data
boundaries. [CONTRIBUTING.md](CONTRIBUTING.md) owns contributor checks;
[docs/AGENTS.md](docs/AGENTS.md) documents the shipped automation interface.
These rules address observed repository failures, not a scientific agent persona.
Add a rule only for a demonstrated failure that existing checks cannot prevent.

## Verify before asserting

Read the current implementation before describing it. Report what you actually
ran, distinguish verified results from inference, and name unavailable checks.
Passing tests establish only their assertions; confirm that those assertions
cover the requested behavior. Check an issue's premise against the base before
implementing it. Fix an incorrect verification before changing correct code.

## Keep changes reviewable

Inspect `git status --short`, `git diff` and `git diff --stat` after an edit pass.
Investigate unexpected size or scope; undo unrelated formatter changes and
reapply the intended edit surgically. Prefer exact patches for large files.
Read only the relevant symbols and search references before removing code.
Do not repeat large file or tool output when a targeted query answers the question.

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
Use the affected checks in [CONTRIBUTING.md](CONTRIBUTING.md), inspect the final
diff, and report exactly what passed or remains unverified. Document intentional
public behavior changes in the existing maintained entrypoints.

## Escalation

Ask only for a maintainer decision that the authorized task does not resolve:
a public-contract change, materially different user-visible designs, removal of
a documented capability, or necessary verification unavailable in this environment.
First use the code, tests and history to resolve factual questions. Existing
authorization persists; do not ask to repeat work already requested. A source
change alone does not authorize a release or restart a running service.
