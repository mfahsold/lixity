# Unlimited-OCR integration and deployment boundaries

Reviewed against upstream on 2026-09-27. This document describes the implemented
v1.19.0 Lixity boundary and the requirements of an independently deployed adapter.
A source checkout also contains an experimental CPU adapter; no model server,
weights or production-tested inference runtime ship with the Python package.
For import commands and the exact worker JSON, see [Research usage](USAGE.md#worker-interface).

## Assessment

Separating GPU inference from the analysis engine is compatible with upstream
deployment options. Lixity invokes
a custom executable and expects `blocks` JSON; Baidu's entrypoints do not
implement that protocol. Setting `LIXITY_OCR_WORKER` to upstream `infer.py`,
`vllm`, or a server URL does not bridge the two interfaces.

The existing model and source pins are current at the review date:

| Item | Verified upstream revision | Meaning in Lixity |
| --- | --- | --- |
| Hugging Face model repository | `07dea832e22aefee32ad281d4b80551282e1c168` | Requested model snapshot, not a loaded-weight attestation |
| Baidu GitHub repository | `d49ff64afffc1f47ab563dc1c589bc2f78808fa4` | `recipe_revision` identifies Baidu source/README, **not** a vLLM version or image digest |

Both upstream heads were last modified on 2026-07-29 when checked through the
[model API](https://huggingface.co/api/models/baidu/Unlimited-OCR) and
[Baidu commit](https://github.com/baidu/Unlimited-OCR/commit/d49ff64afffc1f47ab563dc1c589bc2f78808fa4).
Runtime dependencies, container digest, model code and preprocessing still need
their own deployment records. A constant in a request cannot verify them.

## Official routes

The [Baidu README at the reviewed revision](https://github.com/baidu/Unlimited-OCR/blob/d49ff64afffc1f47ab563dc1c589bc2f78808fa4/README.md)
documents Transformers, vLLM and SGLang. Transformers uses NVIDIA CUDA and BF16;
its tested environment includes Python 3.12.3, CUDA 12.9 and Transformers 4.57.1.
Single images support `gundam` or `base`. Multi-page inference uses `base`,
1024-pixel image size, a 32,768-token length setting, n-gram size 35 and window
1024. Its PDF example rasterizes at 300 dpi. These are reference settings, not
an accuracy or arbitrary-document-size guarantee.

The README's SGLang prose says `kernels==0.9.0`, while its command installs
`0.11.7`. Treat that as an upstream inconsistency requiring runtime validation.
The supplied development wheel is a specific dependency, not evidence that any
SGLang installation supports the model.

The [official vLLM recipe](https://recipes.vllm.ai/baidu/Unlimited-OCR) requires
the Unlimited-OCR n-gram logits processor, a literal `<image>` prompt prefix,
`skip_special_tokens=False` and per-request n-gram arguments. It disables prefix
and multimodal processor caches. Its example uses an OpenAI-compatible HTTP
endpoint and a 3,600-second client timeout. Single-image window size is 128;
multi-image requests use 1024. Missing recipe settings can cause empty output
or repetition.

That recipe still says the architecture is unavailable in a stable wheel.
However, the [vLLM v0.29.0 source](https://github.com/vllm-project/vllm/blob/v0.29.0/vllm/model_executor/models/unlimited_ocr.py)
contains its implementation. The corresponding
[versioned API reference](https://docs.vllm.ai/en/v0.29.0/api/vllm/model_executor/models/unlimited_ocr/)
documents attention-backend constraints and different single-/multi-image
processing. This establishes source inclusion, not a tested Lixity deployment
or compatibility with every GPU. Pin and test an actual runtime; do not combine
flags, wheels and image tags from different instructions without validation.

Baidu's [batch inference script](https://github.com/baidu/Unlimited-OCR/blob/d49ff64afffc1f47ab563dc1c589bc2f78808fa4/infer.py)
converts PDF pages to separate image requests, starts or reuses SGLang, and saves
page Markdown. This differs from the README's combined multi-page inference.
The script uses a 300-second server startup allowance and 1,200-second request
timeout. It prints progress to stdout and accepts command-line options; it does
not read Lixity's request JSON or emit its response envelope. Its per-page
processing is a legitimate upstream path, but should not be described as
one-shot processing of a complete document.

## Output and provenance

The [pinned model implementation](https://huggingface.co/baidu/Unlimited-OCR/blob/07dea832e22aefee32ad281d4b80551282e1c168/modeling_unlimitedocr.py)
handles layout markers including `<|ref|>`, `<|det|>` and multi-page `<PAGE>`
boundaries. `infer_multi` returns text and an output-token count. The code
supports more than one grounding-marker form; its visualizer interprets box
coordinates from generated text. An adapter must parse these as untrusted data,
never execute generated expressions, and test page-boundary preservation.
There is no basis here for inventing a calibrated confidence value for each
recognized block.

Lixity's current behavior has these narrower guarantees:

| Area | Implemented behavior | Operational consequence |
| --- | --- | --- |
| Invocation | One executable receives a temporary JSON filename | A separate protocol adapter is required |
| Input images | Poppler renders at 150 dpi; JSON includes only PDF path and page checksums | A worker must render its own input; 300-dpi images will not match those PNG checksums |
| Timeout | `LIXITY_OCR_TIMEOUT`: integer 1–3600 seconds, default 120, for the whole subprocess | Size the deadline for cold start and every page; this is not a per-page budget |
| Failure | Configured worker failure, timeout, invalid response or incomplete page coverage rejects capture | No silent fallback to native extraction after worker failure |
| Native fallback | Only readable text-layer pages contribute text; without rasterization, only page one is attempted | Mixed scanned/native documents need explicit completeness inspection |
| Worker response | Validates block types, finite boxes/confidence, warnings and coverage of requested pages; stable sorting by page | Coverage relies on worker declarations and cannot establish recognition accuracy |
| Missing confidence | Missing or null confidence remains unknown | Worker-supplied numbers are not independently calibrated certainty |
| Archive | Original PDF, extracted UTF-8 text and exact text spans are retained | Page images, boxes, warnings and verified runtime/model identities are not persisted |
| Activity label | PDF imports use the legacy `baidu-unlimited-ocr/1` boundary identifier, including native fallback | The identifier is not proof that Baidu inference ran |

With a worker configured, an invalid `LIXITY_OCR_TIMEOUT` is reported by
`ocr-status` as `misconfigured_worker`, with corrective guidance. Diagnostics
inspect configuration and executable availability; they do not run model inference.

Archive integrity verifies retained bytes and text-span citations. It does not
verify recognition against the page image. A successful restore or citation
audit must not be presented as an OCR-accuracy result.

## Experimental CPU adapter

Version 1.19.0's source checkout includes
`scripts/ocr_unlimited_cpu_worker.py`.
It is optional experimental tooling, not an installed package entrypoint or a
managed model service. It downloads nothing and requires a separately prepared
Python environment, Poppler and a local model directory. The public package's
lightweight dependencies do not install PyTorch or Transformers.

The tested preparation used Python 3.12, CPU PyTorch 2.10.0 and Transformers
4.57.1, with the model snapshot above and the local-device port from
[upstream PR #56](https://github.com/baidu/Unlimited-OCR/pull/56), pinned at
`a5e743e3225c51515e8b7c0dbdfd561ae1070eb8`. Its
`infer_transformers.py` and `patch_model_for_local.py` are external reviewed
runtime inputs, not automatically fetched by Lixity. Prepare the patched model
and dependencies explicitly; the upstream CUDA-only model is not a drop-in CPU
installation. `LIXITY_UNLIMITED_OCR_HOME` identifies a directory containing
`infer_transformers.py` and `model/` (configuration, tokenizer, patched code and
weights). Run the adapter with that environment's Python, for example through
an executable wrapper selected by `LIXITY_OCR_WORKER`.

The adapter checks the requested snapshot/recipe and the weights SHA-256
`2bc48a7a110061ea58fff65d3169367eebe3aee371ca6968dc2219c1b2855fc6`, configures
offline Hugging Face/Transformers use, and runs with four CPU threads. It renders
at 150 dpi and checks each PNG against the request. Pages are processed in numeric
order, separately, with base/image size 1024, n-gram size 35/window 128 and a
4,096-token maximum. End-of-sequence is required: truncated generation fails.
Known detection delimiters are removed as data; unhandled model control tokens
or empty recognized pages fail rather than entering the evidence archive. The
adapter reports no recognition confidence and cannot currently accept blank
pages through `completed_pages`, although the core protocol supports that field.
The renderer has its own 120-second limit; the overall subprocess deadline still
applies. Runtime imports and patched model code require independent review:
a weight checksum does not attest to every executable input.

A local ARM64 CPU smoke test processed a synthetic two-page image-only PDF in
95.128 seconds. This establishes feasibility for that small input and environment,
not a general speed estimate, OCR accuracy result or acceptance of complex layouts,
handwriting, blank pages, mixed documents or arbitrary document lengths. Inspect
recognized text before relying on it. The default 120-second deadline leaves
limited headroom; provision and test an explicit deadline for the intended workload.

## Deployment and acceptance criteria

A persistent, privately operated vLLM service with a small protocol adapter is a
reasonable integration choice for Lixity's lightweight host process. This is an
architectural recommendation based on the official serving interface, not a
bundled or validated Lixity backend. Transformers can serve as a reference path;
SGLang is another supported upstream option. Choose one runtime and validate it
before adding additional backends.

Any additional adapter must resolve PDF access across process/container boundaries, use
consistent rasterization, translate the chosen upstream request/response format,
and keep logs off JSON stdout. It must detect empty/truncated responses, failed
pages and repeated output. Verify the actual snapshot and runtime independently
of the requested identifiers. Treat document content as evidence, not as model
instructions that can change endpoints or invoke tools.

Use a synthetic scan with known text and no text layer for acceptance. Confirm
that native extraction returns no text, then check model output, page ordering,
completeness, special-character handling and citation round trips. Include a
multi-page scan and a mixed native/scanned PDF. Test worker absence, malformed
responses, timeouts and partial output. Native text extraction and a mock worker
are useful integration tests but cannot establish model accuracy. The protocol
accepts optional `completed_pages` for successfully inspected textless pages;
missing pages otherwise fail. Declaring completion is the worker's assertion,
not independent proof. See [the response contract](USAGE.md#worker-interface).

## Hosted Baidu service is a different integration

Baidu's [Unlimited-OCR cloud API documentation](https://ai.baidu.com/ai-doc/OCR/fmr1p39gb),
updated 2026-09-10, describes asynchronous task submission and polling. It accepts
file data or a file URL and returns result download URLs for Markdown and JSON;
the documented URLs expire after 30 days. That requires authentication, task
tracking, explicit upload permission and durable result capture. Lixity does
not implement this API. The source `origin_url` field is provenance metadata;
it never authorizes a cloud upload or supplies a download URL to a service.

## Validation scope

Lixity's automated suite tests native Poppler extraction, a synthetic worker
subprocess, response validation, incomplete-page rejection, configurable timeout,
unknown confidence, CPU-output delimiter handling, ingestion, citations and archive
restoration. It does not download
or run Unlimited-OCR weights. Dependency-dependent native tests explicitly skip
when Poppler is unavailable; Linux and macOS CI install it. An environment
without the required inference hardware or an explicitly configured service
can validate the boundary and its failure behavior, but cannot certify scan OCR.
