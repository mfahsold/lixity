# Evidence and platform selection

[Return to the RFC](README.md). Checked 2026-09-25. This is a targeted selection
of primary publications and official documentation, not a systematic review.
Study findings, engineering reports and our architecture inferences are separated.
No experiments below were reproduced for this documentation PR. Versioned links
are used where practical; current product documentation may change.

## Research that changes the architecture

| Reference and status | Relevant finding | Limit and design inference |
| --- | --- | --- |
| Li et al., **Retrieval Augmented Generation or Long-Context LLMs? A Comprehensive Study and Hybrid Approach**, EMNLP Industry 2024, peer-reviewed. [Paper](https://aclanthology.org/2024.emnlp-industry.66/) | On the tested models/tasks, sufficiently resourced long context performed better on average; routing could reduce cost. | Older models and prices are not current performance guarantees. Provide both retrieval and bounded full-document reading, measured on the same tasks. |
| Günther et al., **Late Chunking: Contextual Chunk Embeddings Using Long-Context Embedding Models**, arXiv v3, July 2025, preprint. [Paper](https://arxiv.org/html/2409.04701v3) | Contextualizing before pooling chunk embeddings improved retrieval in their experiments. | Requires compatible token embeddings/pooling; context can also distract. Preserve structure and offsets; benchmark this as an optional index strategy. |
| Anthropic, **Introducing Contextual Retrieval**, September 2024, engineering report. [Report](https://www.anthropic.com/engineering/contextual-retrieval) | Contextualized lexical and semantic retrieval, followed by reranking, reduced retrieval failures in the reported setup. | Vendor experiment, not a universal answer-accuracy result. Generated contextual prefixes must be stored separately from source quotations. |
| Ru et al., **RAGChecker**, NeurIPS Datasets and Benchmarks 2024, peer-reviewed. [Proceedings](https://proceedings.neurips.cc/paper_files/paper/2024/hash/27245589131d17368cccdfa990cbf16e-Abstract.html) | Claim-level diagnostics separate retrieval coverage from generation problems and correlate with human assessments in their evaluation. | English/text evaluation and imperfect automated judges. Measure evidence recall, answer support, contradiction, citation resolution and abstention separately. |
| Su et al., **BRIGHT: A Realistic and Challenging Benchmark for Reasoning-Intensive Retrieval**, ICLR 2025, peer-reviewed. [Proceedings](https://proceedings.iclr.cc/paper_files/paper/2025/hash/7a0f8055c838df8e62329a76c7c6403d-Abstract-Conference.html) | Conventional embedding performance transferred poorly to reasoning-intensive queries; reasoning could improve retrieval. | Does not justify agentic search for every lookup. Distinguish exact evidence search from inspectable, bounded exploratory query decomposition. |
| Ouyang et al., **HoH**, ACL 2025, peer-reviewed. [Proceedings](https://aclanthology.org/2025.acl-long.301/) | Coexisting current/outdated sources caused retrieval and generation errors; recency interventions involved tradeoffs. | Wikipedia revision tasks do not prescribe how to interpret historical material. Store source versions and multiple date roles; newer is not necessarily the correct historical evidence. |
| Kuissi et al., **Still Fresh?**, arXiv v1, March 2026, preprint. [Paper](https://arxiv.org/html/2603.04532v1) | A technical corpus changed substantially while most evaluation questions remained supportable after evidence was re-judged. | One domain and two snapshots. Retain stable questions but refresh corpus snapshots and relevance labels; a stable URL is not stable evidence. |

These additional sources support the design of adaptable context selection,
versioned evidence and measurable retrieval. They do not establish a single best
vector database, model or writing application.

## Complementary evidence about writers and evidence access

- **Guo et al., From Pen to Prompt**, Creativity & Cognition 2025: interviews and
  observed sessions with 18 already AI-using writers show diverse, deliberate
  workflows. This is qualitative evidence for preserving author choice, not a
  representative survey or proof of better books. [Original](https://arxiv.org/html/2411.03137v4).
- **Wallat et al., Correctness is not Faithfulness**, ICTIR 2025: citation support
  and actual model reliance are different properties. Keep inspectable source
  passages; do not treat generated citations as proof of the model's reasoning.
  [Original](https://doi.org/10.1145/3731120.3744592).
- **Gao et al., A Reproducible Benchmark and Evidence-Retrieval Software Framework
  for Silicon Detector R&D Literature**, July 2026 preprint: hybrid retrieval was
  strongest for exact evidence in their corpus, whereas graphs supported broader
  discovery. This is a useful specialized case, not a transferable accuracy claim.
  [Versioned original](https://arxiv.org/html/2606.24725v3).
- **Edge et al., From Local to Global**, February 2025 revision: graph-based
  summaries improved broad corpus-level answers in the tested setting. This
  motivates an exploration mode, not treating generated graph edges as facts.
  [Versioned original](https://arxiv.org/html/2404.16130v2).

## Verified platform capabilities and integration constraints

### Bibliography and authoring

Zotero exposes native JSON and citation export formats. Preserve origin, library,
key and version along with CSL-JSON; citation exports alone omit synchronization
identity. In Zotero 10+, its local API has a server identity and version scope
distinct from the Web API. Version/deletion polling and cursor advancement belong in the connector.
The first implementation should be read-only. [API formats](https://www.zotero.org/support/dev/web_api/v3/basics),
[local API](https://www.zotero.org/support/dev/web_api/v3/local_api),
[synchronization](https://www.zotero.org/support/dev/web_api/v3/syncing).

Obsidian edits a local Markdown vault; Bases supplies property-driven views. It
can be a client for dossiers without becoming the evidence repository protocol.
No Obsidian plugin is required for the proposed core workflow.
[Storage](https://obsidian.md/help/data-storage), [Bases](https://obsidian.md/help/bases).

### Extraction, retrieval and composition

Docling's document model retains structured content and provenance. The extraction
adapter should preserve its JSON and original page references rather than only
plain Markdown. Models may download on first use; provision assets and isolate
network access for a reproducible offline profile.
[Document model](https://docling-project.github.io/docling/concepts/docling_document/),
[provenance reference](https://docling-project.github.io/docling/reference/docling_document/#docling_core.types.doc.document.ProvenanceItem),
[offline options](https://github.com/docling-project/docling/blob/main/docs/usage/advanced_options.md).

SQLite FTS5 offers lexical indexing and ranking. Qdrant supports filtered, named
vector queries and fusion; the Python client's local mode is positioned for
development/prototyping/testing. A supported service profile requires operational
validation. Use one chosen lexical route in a hybrid query to avoid double-counting.
[FTS5](https://www.sqlite.org/fts5.html),
[Qdrant hybrid queries](https://qdrant.tech/documentation/search/hybrid-queries/),
[Python client](https://github.com/qdrant/qdrant-client).

BGE-M3 is a candidate because its model card describes multilingual dense, sparse
and multivector outputs. These are different inference paths: a dense-only encoder
does not automatically produce sparse vectors. Evaluate a pinned revision and
hardware profile; do not select from a generic leaderboard alone.
[Model card](https://huggingface.co/BAAI/bge-m3).

Haystack supplies composable retrieval/generation pipelines. Keep its types behind
an adapter and pin the tested major version: documentation and integrations evolve.
It does not supply Lixity's canonical entity identity or author-review semantics.
[Pipeline documentation](https://docs.haystack.deepset.ai/docs/pipelines).

Open WebUI already offers knowledge collections, hybrid search and bounded/full
context options. It demonstrates reusable presentation capabilities, but its chat
workflow is not a replacement for the proposed source/claim/revision contract.
[Knowledge documentation](https://docs.openwebui.com/features/workspace/knowledge/).

### Preservation and interchange

W3C Web Annotation defines quote and position selectors. Positions are relative
to a specific text representation; they must be pinned to an extraction version.
PROV distinguishes entities, activities and agents. Lixity can map its records
to these vocabularies without requiring an RDF server.
[Web Annotation model](https://www.w3.org/TR/annotation-model/),
[PROV overview](https://www.w3.org/TR/prov-overview/).

WARC captures web resources and acquisition metadata. WACZ packages web archives;
Browsertrix is an existing capture platform. Original PDFs can be archived directly.
Capture completeness and authentication context must be recorded.
[WARC 1.1](https://iipc.github.io/warc-specifications/specifications/warc-format/warc-1.1/),
[WACZ](https://specs.webrecorder.net/wacz/1.1.1/),
[Browsertrix](https://docs.browsertrix.com/).

RO-Crate packages research artefacts and relationships in JSON-LD. The proposed
initial export profile targets the explicitly documented 1.2 structure, not an
unpinned claim to implement the newest release. Export is a boundary format, not
the transactional authoring store. [RO-Crate 1.2](https://www.researchobject.org/ro-crate/specification/1.2/structure).

Object-store versioning is recovery, not content identity. AWS S3 deletion in a
versioned bucket normally creates a delete marker; earlier versions remain.
Other S3-compatible backends require capability tests. Lixity's checksums and
purge semantics must not rely on an ETag or a provider URL.
[S3 versioning](https://docs.aws.amazon.com/AmazonS3/latest/userguide/versioning-workflows.html).

### Licensing and packaging

Verified upstream declarations include Zotero AGPLv3, Docling MIT with separately
licensed models, Qdrant Apache-2.0, SQLite public-domain status and BGE-M3 MIT.
These are component declarations, not a legal determination about any combined
distribution, and do not grant rights to imported material. Record exact dependency
and model versions/licenses when packaging the optional runtime.
[Zotero](https://www.zotero.org/support/licensing),
[Docling](https://github.com/docling-project/docling),
[Qdrant](https://github.com/qdrant/qdrant),
[SQLite](https://www.sqlite.org/copyright.html),
[BGE-M3](https://huggingface.co/BAAI/bge-m3).
