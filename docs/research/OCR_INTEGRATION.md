# Unlimited-OCR integration and deployment boundaries

Reviewed against upstream on 2026-09-27. This document describes the implemented
Lixity boundary and the requirements of an independently deployed adapter. It is
not a claim that Lixity ships a model server or a production-tested adapter.
For import commands and the exact worker JSON, see [Research usage](USAGE.md#worker-interface).

## Assessment

Separating GPU inference from the analysis engine is compatible with upstream
deployment options. The integration is nevertheless incomplete: Lixity invokes
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
| Timeout | Worker subprocess is limited to 120 seconds | Upstream cold start or long-document processing can exceed the limit |
| Failure | Some worker failures fall back to native extraction | Successful PDF import does not establish successful model inference |
| Native fallback | Only readable text-layer pages contribute text; without rasterization, only page one is attempted | Mixed scanned/native documents need explicit completeness inspection |
| Worker response | A lightweight parser reads `blocks`, optional boxes/confidence, and warnings | This is not a complete schema-validation or page-completeness guarantee |
| Missing confidence | Runtime block parsing currently defaults to `1.0` | Do not display or interpret that default as measured certainty |
| Archive | Original PDF, extracted UTF-8 text and exact text spans are retained | Page images, boxes, warnings and verified runtime/model identities are not persisted |
| Activity label | PDF imports use the legacy `baidu-unlimited-ocr/1` boundary identifier, including native fallback | The identifier is not proof that Baidu inference ran |

Archive integrity verifies retained bytes and text-span citations. It does not
verify recognition against the page image. A successful restore or citation
audit must not be presented as an OCR-accuracy result.

## Deployment and acceptance criteria

A persistent, privately operated vLLM service with a small protocol adapter is a
reasonable integration choice for Lixity's lightweight host process. This is an
architectural recommendation based on the official serving interface, not a
bundled or validated Lixity backend. Transformers can serve as a reference path;
SGLang is another supported upstream option. Choose one runtime and validate it
before adding additional backends.

The adapter must resolve PDF access across process/container boundaries, use
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
are useful integration tests but cannot establish model accuracy.

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
subprocess, ingestion, citations and archive restoration. It does not download
or run Unlimited-OCR weights. Dependency-dependent native tests explicitly skip
when Poppler is unavailable; Linux and macOS CI install it. An environment
without the required inference hardware or an explicitly configured service
can validate the boundary and its failure behavior, but cannot certify scan OCR.
