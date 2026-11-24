# Rust evaluation for the shared analysis engine

The Rust/Tauri desktop host and the analysis engine have independent
acceptance criteria. Desktop work owns native windows, OS integrations and
installer verification. This evaluation applies to individual hot paths in
the existing analysis engine and records which measured kernels qualify for
production integration.
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

Profile again after the request-local reuse described below. Use equivalent
text, token patterns and quote ranges when comparing any remaining duplicate
work across the analyzer and supplementary reports. Include memory and the
cost of looking up or building keys. Compare exact reporting and evidence
before profiling a different native boundary.

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
  for worker scheduling as well as input conversion. This first experiment
  measured the C interface and result parity on Apple Silicon.
  [Goose C interface](https://aardappel.github.io/goose/docs/goose_spec.html#711-exporting-goose-functions-to-c)
- **2026-11-24 · Reuse quotation counts within one analysis.** Paragraph
  evidence reuses the latest counts for the same normalized text and quote
  ranges. Pacing shares counts when a chapter forms a single scene. The
  count-only path skips extracting token strings. On Apple Silicon with
  Python 3.12.16, four runs of the full analysis with reader evidence and
  supplementary reports produced identical result digests on all three
  inputs. Median elapsed time changed from 3.310 to 3.215 s for *Pride and
  Prejudice*, 2.761 to 2.689 s for *Effi Briest* and 2.399 to 2.305 s for
  120 synthetic chapters. The medians of the three warm runs were 3.304 to
  3.215 s, 2.757 to 2.685 s and 2.387 to 2.301 s respectively. Peak resident
  memory across the runs changed from 244.27 to 245.42 MiB.
- **2026-11-24 · Compare the same quotation-membership interface.** On Apple
  Silicon, three alternating runs per implementation used the current
  Python pipeline and the same two books and synthetic manuscript. Python
  prepared the word spans for identical batch interfaces in Rust and Goose.
  Goose ran on a dedicated worker thread. All metrics, evidence, and report
  digests matched. Median full-analysis times in Python, Rust, and Goose were
  3.328 / 3.507 / 3.547 s for *Pride and Prejudice*, 2.781 / 2.869 / 3.092 s for
  *Effi Briest*, and 2.331 / 2.405 / 2.509 s for the synthetic manuscript.
  Goose calls including worker handoffs took 68–111 ms per analysis. Python
  regex preparation and packing took 234–313 ms. Both native implementations
  increased total time at this boundary. Evaluate a boundary that can avoid
  preparing and packing token spans only if profiling still identifies it as
  a substantial part of the workload.
- **2026-11-24 · Motif ranking.** A standard-library Rust process ranked
  repetitions and chapter echoes from the Python pipeline's normalized tokens.
  Python applied the configured tokenization and kept evidence offsets and the
  report projection. The comparison covered 936 report cases in seven languages,
  including custom token patterns, evidence variants and ranking limits. All
  full-pipeline digests matched. Four alternating runs per implementation on
  Apple M2 Pro used Python 3.12.16 and Rust 1.100. Including request packing,
  process startup and response decoding, median warm ranking latency changed
  from 190 to 65 ms for *Pride and Prejudice*, 149 to 54 ms for *Effi Briest*, and
  57 to 39 ms for the 120-chapter synthetic manuscript. Warm median total time
  changed from 3.397 to 3.321 s, 2.847 to 2.750 s, and 2.407 to 2.424 s
  respectively. The production engine keeps the Python path because the
  full-pipeline gains missed the 5% qualification target. The Apple Silicon
  prototype was about 544 KiB. Cross-platform installation was outside this
  measurement.
