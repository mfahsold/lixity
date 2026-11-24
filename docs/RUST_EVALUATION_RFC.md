# Rust evaluation for the shared analysis engine

The Rust/Tauri desktop host and the analysis engine have independent
acceptance criteria. Desktop work owns native windows, OS integrations and
installer verification. This evaluation applies to individual hot paths in
the existing analysis engine and records the evidence for keeping two measured
kernels in Python.
[Desktop host boundary](ARCHITECTURE.md#desktop-host-boundary)

The native desktop host uses Rust with Tauri. The Goose systems language can
also be evaluated for a small, measured analysis bottleneck. Goose generates C
and can export functions to another host. Evaluate an isolated quotation-span
kernel with the same fixtures as the Rust prototype. Include input conversion,
runtime initialization, Python-to-native calls and cross-platform bundle costs
when comparing both candidates with the current Python implementation.
[Goose language and compiler](https://aardappel.github.io/goose/docs/command_line.html#8-writing-the-c-yourself)

The shared Python distribution supports Python 3.10 and later. Its runtime
dependencies are `pydantic`, `rich`, `orjson` and `tomli` on Python 3.10.
Statistical code uses the standard library. The evaluation preserves
deterministic offline analysis, immutable revisions, evidence links and
the published CLI, JSON and archive contracts.
[Automation contracts](AGENTS.md)

## Next experiment

Run the existing pipeline benchmark and profile a book-scale analysis on the
same revision. Use the bundled public-domain books and synthetic chapters.
Record the source revision, input size, language, machine and individual
runs. Identify the stage that costs authors the most time and check for
algorithmic repetition, cache misses and I/O before choosing a Rust boundary.
Keep profiles and scratch results in `.artifacts/`.
[Performance procedure](https://github.com/mfahsold/lixity/blob/main/CONTRIBUTING.md#investigating-performance)

The November 24 baseline on Apple Silicon with Python 3.12.16 used three runs
per input. Median whole-pipeline time was 3.12 s for *Pride and Prejudice*,
2.62 s for *Effi Briest* and 2.22 s for the 120-chapter synthetic manuscript.
The analyzer and paragraph/chapter profiling were the two largest stages on
all three inputs. Measure the cost of quotation extraction within those stages
before choosing a boundary.

Measure request-local reuse of equivalent quotation counts first. The
prototype below counted repeated work in the analyzer and supplementary
reports. Share a result only for equivalent text, token pattern and quote
ranges. Keep the cache within one analysis and include memory and the cost of
looking up or building keys. Compare exact reporting and evidence before
profiling a different native boundary.

## Acceptance criteria

1. Set targets before writing the spike. Measure stage time, end-to-end
   latency, peak memory, cold start and install size. Use the same corpus,
   configuration, iterations and hardware throughout, with separate cold and
   warm runs.
2. Preserve deterministic bytes for the same inputs and settings. Extend
   parity fixtures around offsets, empty or missing measurements and language
   differences. Keep the public API and storage formats unchanged.
3. Account for the release and maintenance cost on macOS, Windows and Linux.
   Keep the published Python distribution, offline analysis and CLI availability.
   Review any new binary or required dependency with the existing security and
   release procedures. [Security policy](https://github.com/mfahsold/lixity/blob/main/SECURITY.md)
4. When the change affects interactive analysis, verify timings and keyboard
   access in the shared browser UI on desktop and mobile. Verify the relevant
   native WebViews when the interaction depends on the host.
   [Browser verification](https://github.com/mfahsold/lixity/blob/main/tests/browser/README.md)
5. Document any intentional change in mathematical meaning as a separate
   decision. Record formulas and limits together, and update the changelog.
   [Methods](METHODS.md) · [Stability](STABILITY.md)

Retain the Python implementation when the complete operation misses the
agreed targets. Keep the measurements so later work can revisit the decision
if the workload or available boundary changes.

## Evaluation log

- **2026-11-11 · Nominal-suffix kernel.** The Rust regex/PyO3 prototype for
  `language.count_nominal_matches` was about 2.2× faster in isolation.
  The kernel took roughly 1 ms per book-scale run and surrounding work
  accounted for roughly 0.25 s. The projected whole-pipeline gain was below
  5%. The Python implementation remained in use. The same investigation
  recorded a byte-identical analyzer memoization result of about 42% on
  `analyze`.
- **2026-11-24 · Quotation membership.** On Apple Silicon with Python
  3.12.16, profiling attributed about 8–10% of runtime to
  `quotation._memberships`, including Python regex iteration and match
  extraction. A dependency-free Rust spike classified pre-extracted
  code-point spans. Its output matched exactly for 22 fixture spans
  and 2,353,850 word matches across *Pride and Prejudice*, *Effi Briest*
  and the 120-chapter synthetic benchmark. Three runs per corpus yielded
  3.75–4.51 ms for the Rust kernel. Extracting and packing its input in
  Python and calling Rust once per book took 312–373 ms altogether.
  The Python replay took 268–316 ms. The projected full pipeline was
  1.82–1.96% slower, missing the 5% minimum gain. The production operation
  remains in Python.
- **Workspace quotation extraction and counting.** On Apple Silicon with
  Python 3.12.16, three runs per corpus used `analyze_document` with evidence
  and supplementary reports. An in-process Rust prototype included UTF-8
  conversion, range preparation, default token extraction and quotation
  counting. Python still recognized quote delimiters and ran custom token
  regexes. All report and evidence digests matched. Separate comparisons
  covered 21,011 text scopes and capture cases across seven language profiles.
  Median overall time changed from 3.38 to 3.23 s for *Pride and Prejudice*,
  2.88 to 2.68 s for *Effi Briest* and 2.43 to 2.23 s for the synthetic book.
  The gains were 4.46%, 6.90% and 8.21%. One book missed the 5% threshold.
  Equivalent text, token pattern and quote ranges accounted for repeated
  work over 51–68% of the characters processed by count-only calls. The
  production engine remains in Python while shared counting, memory and
  packaging costs are evaluated.
- **Goose C interface.** Goose v2026.4 generated standalone C from an isolated
  quotation-span kernel. Clang built an Apple Silicon dynamic library. A
  single-threaded Python test matched the reference for 2,045 fixed and boundary
  cases and 100,000 seeded synthetic spans. Goose requires an exported function
  to run on the runtime's initializing thread. A Lixity benchmark must account
  for worker scheduling as well as input conversion. End-to-end latency and
  behavior on Windows, Linux and macOS 12 remain unmeasured.
  [Goose C interface](https://aardappel.github.io/goose/docs/goose_spec.html#711-exporting-goose-functions-to-c)
