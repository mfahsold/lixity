# Rust evaluation (proposed scope and acceptance criteria)

**Status: proposed evaluation only. No rebuild decision has been taken.
Research reviewed 2026-11-10.**
This document owns the question "under which measurable conditions would a
Rust implementation (engine parts and/or performance-critical UI paths) be
preferable to the current Python implementation", the evidence required to
answer it, and the acceptance gates for any follow-up proposal. It does not
authorize a rewrite, a new package, or a new required dependency. A full
engine rewrite or a native (non-browser) UI remains out of scope and would
need its own RFC. This evaluation assumes the public contracts stay stable:
CLI behavior, JSON/archive schema versions and `docs/AGENTS.md` automation
semantics do not change silently.

## Product decision under evaluation

Keep the author-facing product identical while answering, with numbers,
whether moving hot paths to Rust improves performance, idempotency,
mathematical rigor or security enough to justify the cost. "Maschinennah"
in this evaluation means: measurable render and interaction budgets inside
the existing local browser app (e.g. large-document rendering, list
virtualization, worker-based analysis scheduling) — not a native UI toolkit.

## Evidence and alternatives

Prefer, in this order, before any language change:

1. Profile first: `cProfile`/timers on real book-scale manuscripts; publish
   the top hot spots with inputs and hardware before optimizing anything.
2. Algorithmic work in Python: complexity fixes, caching with content
   identity, incremental analysis keyed on revisions.
3. Isolate the boundary: if one hot spot dominates, evaluate a minimal
   native extension behind the existing Python API (stable ABI, same JSON),
   not a rewrite.
4. Only then compare against a Rust spike on identical inputs.

## What the current implementation gives us

- Single `lixity` Python distribution; runtime deps limited to `pydantic`,
  `rich`, `orjson`; statistics in stdlib only (no numpy/scipy).
- Deterministic offline analysis (Python 3.10+), content revisions and
  evidence links for retained sources.
- Formula documentation in `docs/METHODS.md`, stability caveats in
  `docs/STABILITY.md`, trust boundaries in `SECURITY.md`.

## Proposed evaluation protocol

- Fixed corpus: at least one public-domain book-scale manuscript plus the
  existing synthetic fixtures; inputs, seeds and hardware recorded.
- Metrics, each with a pre-registered target: wall-clock per pipeline stage,
  peak RSS, result-byte identity across runs and machines (idempotency),
  cold-start time, install size and dependency count.
- UI budgets: first-render and interaction handlers measured against stated
  millisecond budgets on reference desktop and mobile viewports; regressions
  fail the gate (see `tests/browser/README.md` for the harness).
- Security review per `SECURITY.md` trust boundaries for any new binary
  component (build provenance, supply chain, file-system and loopback
  exposure). New required dependencies need explicit discussion first.
- Mathematical changes: formula documentation in `docs/METHODS.md` and
  caveats in `docs/STABILITY.md` updated together with the code; behavior
  changes reflected in `CHANGELOG.md` under `[Unreleased]`.

## Acceptance gates before any Rust follow-up proposal

1. Profiled evidence shows a hot spot where Python is the binding
   constraint (not algorithm, I/O or caching), with reproducible numbers.
2. A Spike meets every pre-registered target above while keeping all
   public contracts byte-compatible (CLI output, JSON/archive schemas,
   `docs/AGENTS.md` semantics).
3. Packaging story resolved: one distribution, offline install, Linux-first
   without regressing documented availability; no silent new requirements.
4. Browser-verified UI states (desktop + mobile) show no regression, and
   accessibility properties of the current app are preserved.
5. The follow-up proposal quantifies maintenance cost (build matrix,
   release flow in `CONTRIBUTING.md`, docs-sync artifacts) against the
   measured gain. Without this, the evaluation outcome is "stay on Python".

## Open questions (assumptions flagged)

- The interpretation of "maschinennah" above is the author's proposal;
  confirm or correct it before spending evaluation effort.
- Which pipeline stage, if any, is actually too slow today — no accepted
  measurement exists yet, so gate 1 is currently unmet by definition.
