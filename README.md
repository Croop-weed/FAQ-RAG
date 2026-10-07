# Customer Support Assistant

A Python backend for a SaaS customer-support assistant. It stores curated FAQ knowledge, provides independently benchmarked lexical and semantic retrieval, combines retrieval rankings, reranks a bounded candidate pool, and contains an internal grounded-draft generation service.

The product goal is to reduce repetitive work for support agents by finding verified company knowledge and preparing a draft. **The AI does not send customer replies.** A human must review, edit, and send any response. The current application does not yet expose a draft endpoint or wire the generation service into FastAPI.

This README is the starting map for developers and coding agents. It describes current behavior, including what is deliberately unfinished; it is not a promise that every named placeholder module is implemented.

## Status

| Phase | Purpose | Repository status |
|---|---|---|
| 1 | Application foundation | Implemented: settings, FastAPI factory, health, request IDs, logging, error handling, DI foundation |
| 2 | Knowledge base and FAQ ingestion | Implemented: FAQ schemas/model, async persistence, repository/service, JSON/JSONL ingestion, API, migration |
| 3 | Retrieval baselines and evaluation | Implemented: BM25Plus, embedding provider, FAISS cosine retrieval, evaluation metrics and CLI |
| 4 | Hybrid retrieval | Implemented: rank-only Reciprocal Rank Fusion and `HybridRetriever` |
| 5 | Cross-encoder reranking | Implemented: bounded reranker protocol/adapter and benchmark mode |
| 6 | Grounded generation and evidence | Implemented as callable internal services/schemas with an Ollama adapter; **not wired into the app or exposed through an API route** |
| 7 | Confidence, knowledge gap & abstention | Implemented: `ConfidenceService`, `KnowledgeGapService`, `EvidenceSupportEvaluator`, `Phase7DraftService`, typed decisions (`ACCEPT`, `REVIEW`, `ABSTAIN`), and structured abstention |
| Later | Agent workflow, public draft API endpoints, and production hardening | Not implemented |

“Implemented” describes code and tests in this repository, not production readiness. In particular, the current evaluation set is synthetic and small, and the LLM provider defaults to disabled.

## Product Flow

```text
Curated FAQ JSON/JSONL
        |
        v
Loader -> validation/normalization -> deterministic deduplication -> FAQ repository -> SQL database
                                                                     |
Customer query                                                    active FAQ corpus
        |                                                            |
        +-----------------------+------------------------------------+
                                |
                   +------------+------------+
                   |                         |
                   v                         v
              BM25Plus                Embedding provider -> FAISS cosine index
                   |                         |
                   +------ ranked IDs -------+
                                |
                         RRF rank fusion
                                |
                    bounded candidate pool
                                |
                    cross-encoder reranker
                                |
                   final reranked FAQ IDs
                                |
                  Phase7DraftService (callable pipeline)
                                |
                 configured LLMProvider, if enabled
                                |
                   GroundedDraft + citations
                                |
                 EvidenceSupportEvaluator -> KnowledgeGapService -> ConfidenceService
                                |
                  Decision: ACCEPT / REVIEW / ABSTAIN (or structured abstention answer=null)
                                |
                       Human review/send
```

Retrieval can be run independently from generation. Generation receives only the final reranked evidence selected by its caller. A citation points to a supplied FAQ; it does not establish that the generated answer is correct.

## Repository Map

```text
.
├── data/
│   ├── raw/sample_faqs.jsonl                 # fictional Orbit Desk FAQs; includes one intentional duplicate
│   └── evaluation/                           # five synthetic labeled queries and saved benchmark JSON
├── docs/
│   ├── architecture.md
│   └── decisions/                            # ADRs 0001-0007

├── migrations/                               # Alembic environment and initial FAQ migration
├── scripts/
│   ├── ingest_faqs.py                        # thin FAQ ingestion CLI wrapper
│   └── evaluate_retrieval.py                 # BM25/vector/hybrid/reranker benchmark CLI
├── src/support_assistant/
│   ├── api/                                  # FastAPI wiring, errors, health and knowledge-base routes
│   ├── core/                                 # settings, logging, application exceptions
│   ├── db/                                   # SQLAlchemy FAQ model, sessions and repositories
│   ├── generation/                           # provider contract, Ollama adapter, prompt and draft service
│   ├── ingestion/                            # FAQ loaders/validation/pipeline and evaluation JSONL loader
│   ├── observability/                        # currently an empty metrics placeholder
│   ├── retrieval/                            # documents, BM25, embeddings, FAISS, RRF, reranker, evaluator
│   ├── schemas/                              # Pydantic request/domain/result contracts
│   ├── services/                             # implemented knowledge-base service plus empty future placeholders
│   └── main.py                               # FastAPI factory and request-ID middleware
└── tests/
    ├── unit/                                 # deterministic component tests (including fake model/providers)
    ├── integration/                          # app, API, SQLite, and CLI integration tests
    └── evaluation/                           # currently empty retrieval-quality test placeholder
```

All key paths below are relative to the repository root.

## Application And API

### `src/support_assistant/main.py`

- `create_app(settings=None, *, llm_provider=None) -> FastAPI` is the application factory. It reads/provides `Settings`, configures structured logging, creates a lazy async `Database` engine, stores settings/database/optional provider on `app.state`, mounts the health and knowledge-base routers, and registers centralized exception handlers.
- `RequestContextMiddleware` accepts an incoming UUID `X-Request-ID` or creates one, binds it to structlog context for the request, and returns it on HTTP responses.
- The lifespan disposes the database engine. It does not create the schema, load embedding/reranker models, or build retrieval indexes.
- `llm_provider` is optional application state; `create_app` does not call `create_llm_provider`, construct a `GenerationService`, or mount a draft route.

Run with:

```bash
uv run uvicorn support_assistant.main:create_app --factory --reload
```

### Mounted routes

`src/support_assistant/api/routes/health.py` mounts `GET /health`, returning `HealthResponse(status="ok", service=settings.app_name)`. It is a liveness response only; it does not check database or model readiness.

`src/support_assistant/api/routes/knowledge_base.py` mounts:

| Method and path | Behavior |
|---|---|
| `POST /knowledge-base/faqs` | Validate and create one FAQ; responds 201 |
| `POST /knowledge-base/faqs/bulk` | Accept 1–1,000 JSON records and return per-record ingestion results/errors |
| `GET /knowledge-base/faqs` | List/filter/page FAQs (`offset`, `limit`, `status`, `category`, `product`, `version`) |
| `GET /knowledge-base/faqs/{faq_id}` | Fetch by FAQ ID |
| `PATCH /knowledge-base/faqs/{faq_id}` | Update selected FAQ fields, including status |

Routes call `KnowledgeBaseService` through `api/dependencies.py`; the handlers do not contain ingestion or persistence policy. There is no mounted retrieval or draft-generation endpoint. `api/routes/drafts.py` is empty.

`api/errors.py` maps application, Starlette HTTP, validation, and unexpected errors into `{ "error": { "code", "message", "request_id" } }`. Unexpected errors are logged server-side and return a generic response. `core/exceptions.py` contains FAQ and generation domain errors.

### Dependency wiring

In `api/dependencies.py`, `get_database_session` obtains a transaction-scoped session from app state; `get_faq_repository` builds the SQLAlchemy adapter; `get_knowledge_base_service` builds the service. `get_llm_provider` only reads the optional provider from app state and currently has no mounted route consumer.

## Knowledge Base And Ingestion

### FAQ contract and database

- `schemas/faq.py`: `FAQStatus` (`active`, `inactive`, `draft`), `FAQCreate`, `FAQUpdate`, `FAQRead`, `FAQListResponse`, and typed ingestion result/error schemas. `faq_identity` normalizes question/product/version for duplicate comparison; `faq_identity_key` hashes that identity for persistence.
- `db/models.py`: SQLAlchemy 2.x `Base` and `FAQModel`. One row stores both question and answer, optional category/product/version/region/source, JSON tags, status and timestamps. A unique digest enforces the same identity. Status, status/category, status/product, and status/version indexes support common filtering. There are no embedding/vector columns.
- `db/session.py`: `Database(database_url)` owns `AsyncEngine` and `async_sessionmaker`; `session()` yields a session within `session.begin()` and `dispose()` releases the engine. Creating `Database` does not itself connect. Schema creation is Alembic’s job.
- `db/repositories/faq_repository.py`: `FAQRepository` is the persistence protocol. `SqlAlchemyFAQRepository` implements create/create-many, get, filtered paginated list, update, deactivate, identity lookup, and count. Retrieval ranking is not repository behavior.
- `services/knowledge_base_service.py`: `KnowledgeBaseService` coordinates FAQ create, ingestion, list, get, update and deactivate; it depends on `FAQRepository`, not ORM queries.
- `migrations/env.py` reads `Settings.database_url`; `migrations/versions/20261007_0001_faqs.py` creates/drops the initial FAQ table/indexes. No migration changes are made by normal app startup.

The configured development database is SQLite/aiosqlite. SQLAlchemy 2.x and JSON fields avoid a database-specific vector extension; PostgreSQL has not been validated in this repository. FAQ records belong in the database; derived BM25/FAISS indexes and document embeddings are built/cached outside the FAQ table.

### Ingestion path

```text
File (.json array or .jsonl) or API JSON records
 -> ingestion/loaders.py (file path only)
 -> ingestion/validation.py (record validation and normalization)
 -> ingestion/pipeline.py (batch duplicate detection)
 -> FAQRepository.create_many (one transaction from caller)
 -> FAQIngestionResult
```

- `load_faq_records(Path)` in `ingestion/loaders.py` accepts UTF-8 `.json` arrays and `.jsonl`. A malformed JSONL line becomes a validation issue; malformed JSON documents, unsupported suffixes, or unreadable input raise `FAQLoadError`.
- `normalize_faq_record(record, record_number)` trims/collapses whitespace while retaining paragraph boundaries, normalizes optional metadata/tags, validates through `FAQCreate`, and returns typed issues rather than silently discarding malformed records.
- `FAQIngestionPipeline.ingest(...)` validates each record, keeps the first duplicate identity in the batch, checks existing repository identities, and calls `create_many` for new records. A valid duplicate counts as accepted and is separately counted; it is not overwritten. `updated_records` remains zero.
- The API bulk request limits the body to 1–1,000 records. File ingestion is CLI-only, not an arbitrary upload route.
- `ingestion/cli.py:ingest_file` uses the same loader/pipeline/repository path. `scripts/ingest_faqs.py` only invokes `main()`.

## Retrieval System

Retrieval’s semantic unit is one complete FAQ. `retrieval/documents.py:build_retrieval_documents` projects active `FAQRead` records into stable, ID-preserving `RetrievalDocument(faq_id, question, answer, metadata)` values; inactive/draft records are excluded. The `.content` property is `question + newline + answer`.

### Lexical retrieval

`retrieval/bm25_search.py` defines `LexicalRetriever` and `BM25Retriever`. The constructor sorts documents by FAQ ID, rejects duplicate IDs, tokenizes question+answer case-insensitively, and builds one in-memory `rank_bm25.BM25Plus` index. `search(query, top_k=5)` validates query/top-K and returns `RetrievalCandidate` records with source score, rank and `retrieval_stage="bm25"`. Ties sort by FAQ ID. Scores are ranking values, not probabilities.

### Semantic retrieval

`retrieval/embeddings.py` defines `EmbeddingProvider` (`model_name`, `dimension`, `embed_documents`, `embed_query`), `SentenceTransformerEmbeddingProvider`, and `DocumentEmbeddingCache`. The provider imports/loads Sentence Transformers only when constructed. `DocumentEmbeddingCache` writes validated `.npz` vectors keyed by model plus ordered FAQ IDs/content.

`retrieval/vector_search.py` defines a vector-search protocol, `FAISSVectorIndex`, and `EmbeddingVectorRetriever`. The local index is `faiss.IndexFlatIP` over L2-normalized float32 vectors, so the score is cosine similarity. It maintains a deterministic FAQ-ID/vector mapping and sorts tied scores by FAQ ID. The default embedding setting is `sentence-transformers/all-MiniLM-L6-v2` (384 dimensions in the stored sample benchmark), but it is an initial baseline only. No production vector database exists.

### Hybrid and reranking

- `retrieval/fusion.py:RankFusionStrategy` is the fusion contract. `ReciprocalRankFusion.fuse` sums `1 / (rrf_k + rank)` contributions by FAQ ID. It never compares/adds raw BM25 and vector scores. Duplicates across lists merge; duplicate IDs inside one list are rejected; ties sort by FAQ ID. Default `rrf_k=60` is a configurable starting point.
- `retrieval/pipeline.py:HybridRetriever.search` independently calls lexical and vector retrievers with `bm25_top_k` and `vector_top_k`, then returns the `fusion_top_k` RRF candidates. Failure from either backend propagates; there is no silent degraded mode.
- `retrieval/reranker.py:Reranker` accepts query, candidates, and an FAQ-ID-to-document map. `CrossEncoderReranker` explicitly constructs/reuses Sentence Transformers `CrossEncoder` (`cross-encoder/ms-marco-MiniLM-L6-v2` baseline), scores `(query, question + answer)` pairs, and orders by cross-encoder score with FAQ-ID tie-breaking. Its score is not confidence and is not added to the RRF score; RRF score/source ranks remain metadata.
- `CrossEncoderRerankingRetriever` asks `HybridRetriever` for its bounded fused pool, reranks that pool only, and returns at most `rerank_top_k` (default 5). `search_detailed` returns `RetrievalExecution` with reranker latency.

`bm25_top_k=20`, `vector_top_k=20`, `fusion_top_k=20`, `rrf_k=60`, and `rerank_top_k=5` are configuration defaults, not tuned optima.

## Retrieval Evaluation

- `schemas/evaluation.py`: `EvaluationExample` has stable/content-derived `query_id`, query, relevant FAQ IDs (multiple allowed), optional metadata, difficulty, notes. `EvaluationDataset` includes structured invalid-row records. `EvaluationResult` stores metrics, failures/confused FAQ counts, configuration, and model/build/timing metadata.
- `ingestion/evaluation.py:load_evaluation_dataset` loads JSONL while collecting malformed/duplicate-ID issues; `load_evaluation_jsonl` is the strict compatibility helper that raises when issues exist.
- `retrieval/metrics.py:compute_retrieval_metrics` calculates Recall@1/3/5, MRR, Hit Rate@K, and mean/p50/p95 latency. Recall@K is the per-query fraction of all relevant IDs returned in top K, averaged over valid queries. MRR uses the first relevant rank; no hit yields zero. Hit Rate@K is the fraction of queries with at least one relevant ID in top K.
- `retrieval/evaluator.py:evaluate_retriever` is generic over a search protocol. It excludes queries whose relevant IDs do not exist in the active corpus, records failures by query ID/FAQ ID (not raw query text), and captures detailed reranker timing when the retriever supports it.
- `retrieval/benchmark.py:load_active_corpus` pages through active FAQ records; `run_benchmark` invokes the evaluator; `export_result` writes JSON.
- `scripts/evaluate_retrieval.py` supports `--retriever bm25|vector|hybrid|hybrid-reranker`, `--dataset`, `--output`, `--model`, `--reranker-model`, and `--top-k`. It needs a migrated/configured DB and active FAQs. Vector modes may download models on first use. Default saved outputs go to `data/evaluation/results/`.

The committed `sample_retrieval.jsonl` has five synthetic queries and the sample corpus has nine active FAQs. Stored results are plumbing demonstrations, not statistically meaningful evidence of real-user quality. The result files currently record perfect metrics for the sample. Do not use these figures to select production models.

## Grounded Generation

### Provider and service boundaries

- `generation/providers.py`: `LLMProvider.generate(prompt) -> GenerationResult` is the application contract; `GenerationResult` contains text/model/latency/optional token usage. `OllamaLLMProvider` adapts the Ollama async client, requests JSON with temperature 0, maps transport timeouts/provider errors, and is created by `create_llm_provider(Settings)`. There is no fallback. Ollama is the only concrete LLM provider currently implemented.
- `generation/prompts.py:build_grounded_prompt` builds versioned (`grounded-support-v1`) prompt text. Customer question and evidence are JSON encoded and clearly delimited. Instructions request evidence-based support prose, no invented facts or fabricated citations, and a plain statement when supplied evidence is insufficient. This is model instruction, not an enforced confidence/abstention policy.
- `generation/service.py:GenerationService.generate_draft(query, evidence)` validates input/evidence IDs, takes at most `generation_evidence_top_k` (default 5), constructs the prompt, applies `asyncio.timeout`, validates `GeneratedDraftContent`, rejects blank answers, duplicate citations, and citations whose FAQ IDs were not supplied. Citations are built by the application from evidence objects. The draft preserves all evidence actually supplied and provider/model/timing/token/prompt-version metadata.
- `RetrievalGenerationService.draft_answer(query)` calls its injected reranked retriever with `final_top_k`, resolves only those FAQ IDs in its supplied document mapping, converts them to `EvidenceItem`, and delegates to `GenerationService`. `create_retrieval_generation_service` is a composition helper using settings. Neither is invoked from `create_app`; no customer-facing draft route exists.

A citation provides traceability to evidence supplied/selected. It does not prove entailment or correctness. Generation/provider errors use safe `GenerationError` subclasses and the existing API handler envelope, but no generation endpoint currently exposes them. Logs include provider/model/evidence count/latency/outcome category, not query, prompt, answer, or raw provider payload.

## Confidence, Knowledge-Gap Detection & Abstention

Phase 7 introduces a production-oriented confidence assessment and knowledge-gap evaluation layer that inspects query, retrieved evidence, and generated draft text to determine whether knowledge base support is sufficient.

### Design Principles and Decision Hierarchy

- **No LLM Self-Reported Confidence**: Confidence is derived strictly from measurable application-level signals (cross-encoder reranker score, score margin between candidates, citation validity ratio, evidence support score, and knowledge-gap checks). It NEVER asks the LLM "how confident are you?".
- **Three-State Decision Model**:
  - `ACCEPT`: Strong reranked evidence and verified support; safe to present as an agent draft.
  - `REVIEW`: Evidence is relevant but support is uncertain or score margin is narrow; requires human verification.
  - `ABSTAIN`: Insufficient supporting evidence, low reranker scores, or unsupported claims; the system explicitly abstains rather than returning an ungrounded answer.
- **Human Review Mandatory**: Even `ACCEPT` indicates safety for internal draft presentation, NOT automatic sending to customers.

### Key Components

- `generation/grounding.py`: Defines the `EvidenceSupportEvaluator` protocol and `HeuristicEvidenceSupportEvaluator` implementation. Evaluates sentence-level token overlap between answer claims and evidence text, checks citation validity, and identifies unsupported claims.
- `services/knowledge_gap_service.py`: `KnowledgeGapService` inspects the query, evidence, and optional draft for knowledge gaps (empty evidence, low reranker score below threshold, unmatched query terms, draft refusal phrases) without executing retrieval or calling LLMs directly.
- `services/confidence_service.py`: `ConfidenceService` computes explainable confidence scores from measurable signals and applies decision boundaries (`ACCEPT`, `REVIEW`, `ABSTAIN`).
- `services/draft_service.py`: `Phase7DraftService` orchestrates the complete end-to-end pipeline from query retrieval through reranking, generation, grounding, and confidence scoring.

### Structured Abstention Result

When evidence is insufficient, `Phase7DraftService` returns a structured abstention result with `answer: None`:

```json
{
    "decision": "ABSTAIN",
    "confidence": 0.15,
    "answer": null,
    "reason": "Abstained: Knowledge gap detected - Top reranked evidence score (0.15) is below knowledge-gap threshold (0.25).",
    "citations": [...]
}
```

### Configurable Thresholds

Settings in `core/config.py`:
- `confidence_accept_threshold` (default `0.75`)
- `confidence_review_threshold` (default `0.45`)
- `min_evidence_reranker_score` (default `0.30`)
- `min_supporting_evidence_count` (default `1`)
- `knowledge_gap_threshold` (default `0.25`)

## Module Reference

This table covers architectural modules. Empty files and intentionally unfinished boundaries are called out explicitly; do not infer implementation from their names.

| Path | Responsibility and extension point |
|---|---|
| `src/support_assistant/main.py` | `create_app`, request-ID middleware, lifespan, router registration. Add app-wide wiring here only; feature policy belongs in services. |
| `src/support_assistant/api/dependencies.py` | FastAPI request-state providers for settings, optional LLM provider, DB session, FAQ repository, and knowledge-base service. Generation composition is not currently provided here. |
| `src/support_assistant/api/errors.py` | `register_exception_handlers` and safe error-envelope handlers. Add domain errors through the exception hierarchy rather than serializing them in routes. |
| `src/support_assistant/api/routes/health.py` | `GET /health`; process liveness only. |
| `src/support_assistant/api/routes/knowledge_base.py` | FAQ create/bulk/list/get/patch HTTP adapter. Keep it thin and delegate to `KnowledgeBaseService`. |
| `src/support_assistant/api/routes/drafts.py` | Empty placeholder; no draft HTTP endpoint. |
| `src/support_assistant/core/config.py` | `Settings`, typed defaults and `SUPPORT_ASSISTANT_` environment loading, including Phase 7 confidence and knowledge gap thresholds. |
| `src/support_assistant/core/logging.py` | `configure_logging(Settings)` configures structured JSON logs, environment and request context. Avoid logging customer content/secrets. |
| `src/support_assistant/core/exceptions.py` | `AppException`, FAQ errors, and `GenerationError` subclasses/status codes. API responses are mapped centrally. |
| `src/support_assistant/db/models.py` | SQLAlchemy `Base` and `FAQModel`; single FAQ row and indexes. Do not add embeddings/reranker results here. |
| `src/support_assistant/db/session.py` | `Database` owns async engine/session factory; `session()` provides transaction lifecycle, `dispose()` closes engine. |
| `src/support_assistant/db/repositories/faq_repository.py` | `FAQRepository` protocol and `SqlAlchemyFAQRepository`; persistence only, no rank/search logic. `draft_repository.py` is empty. |
| `src/support_assistant/services/knowledge_base_service.py` | `KnowledgeBaseService` applies FAQ rules and coordinates `FAQRepository`/`FAQIngestionPipeline`. |
| `src/support_assistant/services/draft_service.py` | `Phase7DraftService` end-to-end pipeline service orchestrating retrieval, cross-encoder reranking, grounded LLM generation, evidence support evaluation, knowledge-gap detection, and confidence scoring. |
| `src/support_assistant/services/confidence_service.py` | `ConfidenceService` and `create_confidence_service`; derives explainable confidence scores from measurable signals and decides `ACCEPT`, `REVIEW`, or `ABSTAIN`. |
| `src/support_assistant/services/knowledge_gap_service.py` | `KnowledgeGapService` and `create_knowledge_gap_service`; inspects query, evidence, and draft to detect knowledge gaps without calling LLMs directly. |
| `src/support_assistant/ingestion/loaders.py` | `load_faq_records(Path)` for JSON array/JSONL; typed `LoadedFAQRecords`/`FAQLoadError`. |
| `src/support_assistant/ingestion/validation.py` | `_normalize_content` and `normalize_faq_record`; explicit validation issues. |
| `src/support_assistant/ingestion/pipeline.py` | `FAQIngestionPipeline.ingest`; validate batch, dedupe, query repository identities, bulk create. |
| `src/support_assistant/ingestion/cli.py`, `scripts/ingest_faqs.py` | CLI orchestration and thin executable wrapper. Keep CLI separate from ingestion policy. |
| `src/support_assistant/ingestion/evaluation.py` | `load_evaluation_dataset` structured JSONL loader and strict `load_evaluation_jsonl`. |
| `src/support_assistant/ingestion/chunking.py` | Empty placeholder; FAQ retrieval currently uses each full FAQ as one document. |
| `src/support_assistant/retrieval/documents.py` | `build_retrieval_documents` converts active `FAQRead` values to stable FAQ-level retrieval documents. |
| `src/support_assistant/retrieval/bm25_search.py` | `LexicalRetriever` and `BM25Retriever`; independent BM25Plus corpus index. |
| `src/support_assistant/retrieval/embeddings.py` | `EmbeddingProvider`, Sentence Transformers adapter, and content-addressed document embedding cache. |
| `src/support_assistant/retrieval/vector_search.py` | `VectorRetriever`, `FAISSVectorIndex`, and text-facing `EmbeddingVectorRetriever`. |
| `src/support_assistant/retrieval/fusion.py` | `RankFusionStrategy` and `ReciprocalRankFusion`; ranks only, never source score magnitudes. |
| `src/support_assistant/retrieval/pipeline.py` | `HybridRetriever`; sequential lexical/vector calls then RRF. Backend errors propagate. |
| `src/support_assistant/retrieval/reranker.py` | `Reranker`, `CrossEncoderReranker`, `CrossEncoderRerankingRetriever`; bounded cross-encoder stage. |
| `src/support_assistant/retrieval/evaluator.py` | `SearchRetriever`, `DetailedSearchRetriever`, `evaluate_retriever`; dataset/corpus validation, metrics input and failures. |
| `src/support_assistant/retrieval/metrics.py` | `compute_retrieval_metrics`; offline Recall/MRR/Hit Rate/latency calculations. |
| `src/support_assistant/retrieval/benchmark.py` | `load_active_corpus`, `run_benchmark`, `export_result`; database repository to generic evaluator boundary. |
| `src/support_assistant/retrieval/exceptions.py` | Retrieval, embedding, dataset, reranking failures. |
| `src/support_assistant/generation/providers.py` | `LLMProvider`, `GenerationResult`, `TokenUsage`, Ollama protocol adapter, `create_llm_provider`. |
| `src/support_assistant/generation/prompts.py` | `PROMPT_VERSION` and `build_grounded_prompt`; prompt construction only. |
| `src/support_assistant/generation/service.py` | `GenerationService`, `RetrievalGenerationService`, `RerankedRetriever` protocol, and explicit settings-based factories. |
| `src/support_assistant/generation/grounding.py` | `EvidenceSupportEvaluator` protocol and `HeuristicEvidenceSupportEvaluator`; sentence-level grounding, citation validity, and unsupported claims detection. |
| `src/support_assistant/schemas/confidence.py` | `ConfidenceDecision`, `ConfidenceAssessment`, `EvidenceSupportResult`, `KnowledgeGapAssessment`, `EvaluatedGroundedDraft`. |
| `src/support_assistant/schemas/faq.py` | Pydantic FAQ create/update/read/list/ingestion types and identity helpers. |
| `src/support_assistant/schemas/retrieval.py` | `RetrievalDocument`, `RetrievalCandidate`, `RetrievalResult`, `RetrievalExecution`. Shared retrieval contracts. |
| `src/support_assistant/schemas/evaluation.py` | Evaluation examples/datasets/diagnostics, metrics, failures, latency and benchmark result models. |
| `src/support_assistant/schemas/draft.py` | `EvidenceItem`, `DraftCitation`, `GeneratedDraftContent`, `GenerationMetadata`, `GroundedDraft`. |
| `src/support_assistant/schemas/health.py`, `errors.py` | Typed health and standard API error envelopes. |
| `src/support_assistant/schemas/query.py` | Empty placeholder; evaluation examples currently live in `schemas/evaluation.py`. |
| `src/support_assistant/observability/metrics.py` | Empty placeholder; no runtime metrics exporter/instrumentation. Benchmark metrics are `retrieval/metrics.py`. |

| `src/support_assistant/api/routes/drafts.py` | Empty placeholder; no public generation API. |

## Key Contracts And Classes

| Contract/class | Responsibility | Inputs / output | Current consumer / extension point |
|---|---|---|---|
| `Settings` | Typed application and model configuration | environment/file values → validated settings | `create_app`, scripts, provider/retrieval construction |
| `FAQRepository` | Persistence contract | FAQ schemas and filters ↔ FAQ reads | `KnowledgeBaseService`, ingestion pipeline; swap SQL backend adapter here |
| `EmbeddingProvider` | Model-neutral embedding operations and metadata | texts/query → float vectors | `EmbeddingVectorRetriever`, cache; alternative model adapter implements same contract |
| `LexicalRetriever` / `VectorRetriever` | Responsibility-specific search contracts | query or vector + top-K → ranked candidates | `HybridRetriever` consumes lexical and text-facing vector search |
| `RankFusionStrategy` | Ranked-list fusion contract | candidate rankings + top-K → fused candidates | `HybridRetriever`; RRF is implementation |
| `Reranker` | Candidate precision stage | query + candidate IDs + document mapping + top-K → reordered candidates | `CrossEncoderRerankingRetriever`; replace model implementation here |
| `LLMProvider` | Vendor-neutral asynchronous generation | prompt → text/model/latency/usage | `GenerationService`; Ollama is current adapter |
| `KnowledgeBaseService` | FAQ application rules | API values → repository operations/result | knowledge-base API routes and ingestion caller |
| `FAQIngestionPipeline` | Batch validate/dedupe/persist coordination | numbered untrusted records → `FAQIngestionResult` | CLI or bulk API via service |
| `HybridRetriever` | Independent lexical/vector orchestration | query → RRF-ranked bounded candidates | evaluation CLI; later application composition |
| `CrossEncoderRerankingRetriever` | Hybrid pool reranking | query → final candidates plus detailed reranker timing | evaluation CLI and `RetrievalGenerationService` |
| `GenerationService` | Grounded model draft and citation validation | query + evidence → `GroundedDraft` | callable directly or through `RetrievalGenerationService`; not app-wired |
| `RetrievalGenerationService` | Small retrieval-to-draft composition | query → reranked candidates → evidence → draft | constructed explicitly with retriever/documents/settings; no current endpoint |
| `EvidenceSupportEvaluator` | Answer grounding & citation validity evaluator | query + answer + evidence + cited_ids → `EvidenceSupportResult` | `ConfidenceService`; pluggable contract for future NLI or LLM judge verifiers |
| `KnowledgeGapService` | Knowledge sufficiency & gap detection | query + evidence + optional draft → `KnowledgeGapAssessment` | `ConfidenceService` and pipeline pre/post generation abstention checks |
| `ConfidenceService` | Multi-signal confidence calculation and decision policy | query + draft + evidence → `ConfidenceAssessment` | `Phase7DraftService`; applies `ACCEPT`, `REVIEW`, or `ABSTAIN` decision boundaries |
| `Phase7DraftService` | End-to-end retrieval, reranking, generation, grounding, & confidence pipeline | query → `EvaluatedGroundedDraft` | Primary Phase 7 pipeline; returns structured abstention (`answer: None`) when evidence is insufficient |

`RetrievalCandidate.score` is a stage-specific ranking value. BM25, cosine, RRF and cross-encoder values have different meanings/scales; none is a probability or confidence. Do not combine them numerically without a separately designed and evaluated method.

## Data Flows

### FAQ ingestion

```text
JSON array / JSONL file             API bulk JSON records
          |                                  |
          v                                  v
load_faq_records(Path)               FAQBulkRequest
          |                                  |
          +-------------- numbered records --+
                          |
                          v
             normalize_faq_record per record
                          |
                          v
          first-in-batch dedupe by normalized
              question + product + version
                          |
                          v
      repository identity lookup + create_many
                          |
                  transaction commit
                          |
                          v
                   FAQIngestionResult
```

File loader handles malformed JSONL lines individually; malformed JSON array/file encoding/suffix is a fatal load error. FAQ text whitespace is normalized without joining paragraphs. Duplicate valid records are accepted and reported separately; existing answers are not updated by ingestion.

### Retrieval

```text
active FAQRead records
 -> build_retrieval_documents (stable FAQ ID, question + answer)
 -> BM25Plus search + embedding query / FAISS cosine search
 -> ReciprocalRankFusion over rank positions only
 -> configured fusion_top_k pool
 -> optional CrossEncoder query/document-pair reranking
 -> rerank_top_k candidates
```

Indexes are explicitly constructed, not module globals. Document embeddings are computed/cached per model/corpus; each vector query embeds only the query. The evaluation script loads active FAQs from the existing repository in pages; retrieval algorithms do not query SQLAlchemy themselves.

### Draft generation (callable service; not currently exposed by app)

```text
query -> injected CrossEncoderRerankingRetriever -> final candidate IDs
      -> supplied RetrievalDocument mapping -> at most generation_evidence_top_k EvidenceItems
      -> versioned JSON-delimited grounded prompt -> injected LLMProvider
      -> JSON answer + cited FAQ IDs -> schema validation
      -> reject unknown/duplicate citations -> construct DraftCitation from supplied evidence
      -> GroundedDraft(answer, citations, provided evidence, generation metadata)
```

The prompt asks for evidence-only factual grounding and says to state when supplied evidence is insufficient. This is not a guarantee and does not implement a confidence/abstention decision. Citation validation proves only that a cited ID was in supplied evidence; it does not prove semantic support.

## Configuration Reference

`src/support_assistant/core/config.py:Settings` uses Pydantic Settings. Environment variables use the `SUPPORT_ASSISTANT_` prefix and override defaults; `.env` is read when present. `.env.example` documents names only. Do not put secrets in source control.

| Setting | Default | Purpose / notes |
|---|---|---|
| `APP_NAME` | `customer-support-assistant` | FastAPI metadata and health service value |
| `ENVIRONMENT` | `development` | Environment label in structured logs; accepted values are development/test/staging/production |
| `LOG_LEVEL` | `INFO` | Structlog filter threshold |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/support_assistant.db` | Async SQLAlchemy connection URL |
| `LLM_PROVIDER` | `not-configured` | Only `ollama` is currently constructed by `create_llm_provider` |
| `LLM_MODEL` | `not-configured` | Required configured Ollama model name; no automatic model selection |
| `OLLAMA_HOST` | `http://localhost:11434` | Ollama server endpoint |
| `LLM_TIMEOUT_SECONDS` | `45.0` | Async generation deadline; must be positive |
| `GENERATION_EVIDENCE_TOP_K` | `5` | Maximum evidence items handed to the provider; range 1–10 |
| `EMBEDDING_MODEL` | `sentence-transformers/all-MiniLM-L6-v2` | Initial retrieval benchmark baseline, not a final selection |
| `RERANKER_MODEL` | `cross-encoder/ms-marco-MiniLM-L6-v2` | Initial cross-encoder baseline |
| `BM25_TOP_K` | `20` | Lexical candidate request size |
| `VECTOR_TOP_K` | `20` | Semantic candidate request size |
| `FUSION_TOP_K` | `20` | RRF candidate pool cap |
| `RRF_K` | `60` | RRF rank constant |
| `RERANK_TOP_K` | `5` | Final cross-encoder result count and retrieval-to-generation default |
| `EVALUATION_TOP_K` | `5` | CLI cutoff; must be >=5 to report Recall@5 (hybrid mode evaluates the configured fusion pool) |
| `EMBEDDING_CACHE_DIR` | `models/cache/embeddings` | Local `.npz` document-vector cache; ignored model/cache artifacts are not committed |

Provider/model IDs are configuration, never business-logic literals. Ollama is deliberately opt-in: set `SUPPORT_ASSISTANT_LLM_PROVIDER=ollama` and `SUPPORT_ASSISTANT_LLM_MODEL` to a locally available model. The app factory does not automatically construct it.

## Errors, Logging, Privacy

- `AppException` carries safe message, code and HTTP status; FAQ and generation errors specialize it. `retrieval/exceptions.py` separately covers retrieval/embedding/evaluation/reranking failures; they are not currently API routes.
- API handlers standardize errors and request IDs. Validation errors do not include Pydantic internals. Unexpected API errors are logged with traceback server-side and return a generic response.
- `configure_logging(Settings)` configures JSON structlog events with UTC timestamp, level, environment and bound request ID. Generation logs provider/model, elapsed latency, evidence/citation counts, and a reason/error type; it does not log prompt/query/answer or raw provider payload. Benchmark logs use dataset/retriever/counts, not query text.
- Do not log API keys, authorization data, database URLs, full customer conversations, prompts, answers, or complete uploaded data. FAQ/evidence values can themselves contain sensitive business content.
- Retrieval similarity, BM25, RRF and cross-encoder scores are ranking signals, **not confidence**. No confidence calibration or abstention is implemented.

## Tests And Evaluation

The repository currently has **65 collected tests** (65 passed on the last Phase 6 validation). `tests/unit/` exercises deterministic components and fake providers/models; `tests/integration/` covers app/request IDs, FAQ API, isolated temporary SQLite repositories, and CLI-to-pipeline behavior. `tests/evaluation/test_retrieval_quality.py` is empty, so it does not add an evaluation test.

Generation tests in `tests/unit/test_generation.py` inject fake LLM/Ollama clients; they do not require a live Ollama server. Retrieval unit tests use mock embeddings/cross-encoder; model weights are only loaded by explicit benchmark/provider construction. DB tests use temporary or in-memory SQLite, not the developer’s configured DB.

The evaluation schema supports multiple relevant FAQ IDs, stable/content-derived query IDs, difficulty and metadata. `sample_retrieval.jsonl` has five synthetic queries and `data/raw/sample_faqs.jsonl` is fictional Orbit Desk content. Current result files have perfect metrics on this tiny sample; this is pipeline validation only, not evidence of production quality. A larger human-reviewed golden dataset is needed before model selection or quality claims.

Recorded benchmark artifacts:

| Mode | Recall@1/3/5 | MRR | Hit Rate@5 | Mean / P50 / P95 latency |
|---|---|---:|---:|---|
| BM25Plus | 1.000 / 1.000 / 1.000 | 1.000 | 1.000 | 0.13 / 0.11 / 0.22 ms |
| MiniLM vector | 1.000 / 1.000 / 1.000 | 1.000 | 1.000 | 9.14 / 8.13 / 12.29 ms |
| Hybrid RRF | 1.000 / 1.000 / 1.000 | 1.000 | 1.000 | 8.53 / 8.06 / 11.16 ms |
| Hybrid + reranker | 1.000 / 1.000 / 1.000 | 1.000 | 1.000 | 64.21 / 63.51 / 67.69 ms |

The hybrid result had nine available candidates because the active sample corpus has nine records (the configured pool is capped at 20). Reranking added approximately 55.25 ms mean reranker-stage latency in that run without changing sample metrics. These small synthetic results must not be used to select production models. Existing JSON results are stored under `data/evaluation/results/`.

## Important Modules And Contracts

### Core and API

| Module | Public names / responsibility | Calls / important boundary |
|---|---|---|
| `core/config.py` | `Settings` | Single settings model for DB, retrieval, model, timeout and evidence limits; consumers receive settings rather than reading environment directly. |
| `core/logging.py` | `configure_logging(settings)` | Process-level structlog setup; uses `sys.__stderr__` so test capture streams are not retained. |
| `core/exceptions.py` | `AppException`, FAQ and generation exception classes | API handlers translate safe exceptions; provider errors must not include vendor payloads. |
| `main.py` | `create_app`, `RequestContextMiddleware` | Composes API/DB lifecycle. It currently mounts health and knowledge-base routers only. |
| `api/dependencies.py` | `get_settings`, `get_llm_provider`, `get_database_session`, `get_faq_repository`, `get_knowledge_base_service` | FastAPI wiring from `app.state` to session/repository/service. The optional provider getter is not used by a mounted route. |
| `api/errors.py` | `register_exception_handlers` and handlers | Stable JSON API envelope with request ID; no business logic. |
| `api/routes/health.py` | `health` | Typed liveness response only. |
| `api/routes/knowledge_base.py` | `FAQBulkRequest`, create/bulk/list/get/update route handlers | Request/response validation and service calls; API pagination caps limit at 200 and bulk count at 1,000. |

### Persistence And Knowledge Base

| Module | Public names / responsibility | Important callers |
|---|---|---|
| `db/models.py` | SQLAlchemy `Base`, `FAQModel` | Alembic metadata and repository adapter. One row is one complete FAQ. |
| `db/session.py` | `Database` | App state/dependency and CLI; creates async engine/session factory, transaction context, disposal. |
| `db/repositories/faq_repository.py` | `FAQRepository`, `SqlAlchemyFAQRepository` | KnowledgeBaseService and ingestion pipeline. Persistence only; no relevance ranking. |
| `services/knowledge_base_service.py` | `KnowledgeBaseService` | Routes validation rules and repository calls; ingestion delegated to pipeline. |
| `schemas/faq.py` | `FAQStatus`, FAQ request/read/result schemas, `faq_identity`, `faq_identity_key` | Shared domain/API/ingestion representations; not SQLAlchemy models. |

### Ingestion And Evaluation Data

| Module | Public names / responsibility | Important behavior |
|---|---|---|
| `ingestion/loaders.py` | `LoadedFAQRecords`, `FAQLoadError`, `load_faq_records` | UTF-8 `.json` array or `.jsonl`; malformed JSONL records are structured per-line errors. |
| `ingestion/validation.py` | `normalize_faq_record` | Normalize text/metadata/tags, validate a record, return issues without silently dropping it. |
| `ingestion/pipeline.py` | `FAQIngestionPipeline.ingest` | First-in-batch-wins dedupe on normalized question+product+version, repository check, batch create. Existing duplicates are not overwritten. |
| `ingestion/cli.py`, `scripts/ingest_faqs.py` | `ingest_file`, `main`; thin script wrapper | Reuses same loader/pipeline/database transaction as API path. |
| `schemas/evaluation.py` | `EvaluationExample`, `EvaluationDataset`, `EvaluationResult`, metrics/failure models | Query labels and machine-readable evaluation results. |
| `ingestion/evaluation.py` | `load_evaluation_dataset`, `load_evaluation_jsonl` | Structured invalid row handling and strict compatibility loader. |

### Retrieval And Benchmark

| Module | Public names / responsibility | Inputs → outputs |
|---|---|---|
| `retrieval/documents.py` | `build_retrieval_documents` | Active `FAQRead` records → deterministic FAQ-level docs; keeps FAQ ID and source metadata. |
| `retrieval/bm25_search.py` | `LexicalRetriever`, `BM25Retriever` | Query+top-K → BM25Plus candidates; one index per instance, deterministic ties. |
| `retrieval/embeddings.py` | `EmbeddingProvider`, `SentenceTransformerEmbeddingProvider`, `DocumentEmbeddingCache` | Model-neutral vector protocol; explicit model loading and validated local `.npz` cache. |
| `retrieval/vector_search.py` | `VectorRetriever`, `FAISSVectorIndex`, `EmbeddingVectorRetriever` | Normalized embeddings → FAISS cosine-ranked candidates; FAQ IDs preserved. |
| `retrieval/fusion.py` | `RankFusionStrategy`, `ReciprocalRankFusion` | ranked lists → rank-only fused candidates. |
| `retrieval/pipeline.py` | `TextRetriever`, `HybridRetriever` | Query → independent BM25/vector calls → RRF. Sequential; either backend error propagates. |
| `retrieval/reranker.py` | `CrossEncoderModel`, `Reranker`, `CrossEncoderReranker`, `CrossEncoderRerankingRetriever` | Query/candidate/document map → cross-encoder ordering; stage timing via `RetrievalExecution`. |
| `retrieval/metrics.py` | `compute_retrieval_metrics` | labeled/retrieved FAQ ID lists and latencies → Recall@K, MRR, Hit Rate@K, mean/P50/P95. |
| `retrieval/evaluator.py` | `SearchRetriever`, `DetailedSearchRetriever`, `evaluate_retriever` | generic retriever+dataset+active FAQ IDs → metrics/failures; does not branch on concrete retriever type. |
| `retrieval/benchmark.py` | `load_active_corpus`, `run_benchmark`, `export_result` | Repository active FAQs to generic benchmark and JSON export. |
| `scripts/evaluate_retrieval.py` | CLI `main`, internal `_run` | Constructs one of four retrieval modes and records load/build/query latency; depends on migrated DB and active FAQ rows. |

### Generation

| Module | Public names / responsibility | Important behavior |
|---|---|---|
| `generation/providers.py` | `LLMProvider`, `OllamaChatClient`, `TokenUsage`, `GenerationResult`, `OllamaLLMProvider`, `create_llm_provider` | Async vendor contract and Ollama adapter; client is constructed once. Default configuration refuses use; unsupported provider never falls back. |
| `generation/prompts.py` | `PROMPT_VERSION`, `build_grounded_prompt` | Delimits JSON question/evidence, asks not to invent facts or citations, instructs to state insufficient evidence. Not an enforcement or confidence mechanism. |
| `generation/service.py` | `GenerationService`, `RetrievalGenerationService`, `RerankedRetriever`, creation helpers | Evidence input→bounded prompt/provider→typed draft and validated application-built citations. Internal callable services; not invoked by `main.create_app`. |
| `schemas/draft.py` | `EvidenceItem`, `DraftCitation`, `GeneratedDraftContent`, `GenerationMetadata`, `GroundedDraft` | Model output schema permits answer and cited FAQ IDs only; outer draft includes exact supplied evidence. |

### Supporting Schemas, Observability, And Empty Boundaries

| Module | Actual status |
|---|---|
| `schemas/health.py`, `schemas/errors.py` | Implemented Pydantic health/error response schemas. |
| `schemas/query.py` | Empty; no separate query request schema is currently used. |
| `observability/metrics.py` | Empty; no runtime metrics exporter. Retrieval benchmark metrics live in `retrieval/metrics.py`. |
| `generation/grounding.py` | Empty; citation ID validation currently lives in `GenerationService`; no semantic entailment checker. |
| `services/draft_service.py`, `services/confidence_service.py`, `services/knowledge_gap_service.py` | Empty placeholders. |
| `db/repositories/draft_repository.py` | Empty; generated drafts are not persisted. |
| `ingestion/chunking.py` | Empty; retrieval uses whole FAQ records, not chunks. |
| `api/routes/drafts.py` | Empty; no public draft endpoint. |
| `tests/evaluation/test_retrieval_quality.py`, `tests/integration/test_retrieval_pipeline.py`, `tests/integration/test_draft_api.py` | Empty test placeholders; do not count as implemented evaluations/integrations. |
| `tests/unit/test_bm25_search.py`, `test_confidence.py`, `test_fusion.py`, `test_grounding.py` | Empty legacy placeholders; current tests live in `test_bm25_baseline.py`, `test_rrf_hybrid.py`, `test_generation.py`, etc. |
| `observability/__init__.py`, package `__init__.py` files | Empty package markers. |

## Configuration And Dependencies

`pyproject.toml` is the authority for runtime/development dependencies and tool config. Project requires Python `>=3.12`; build/install/run through `uv`. Direct dependencies by role:

| Area | Direct packages | Purpose |
|---|---|---|
| HTTP/application | `fastapi[standard]`, `httpx` | FastAPI/Uvicorn and provider HTTP timeout types |
| Persistence/migrations | `sqlalchemy[asyncio]`, `aiosqlite`, `alembic` | Async ORM, local SQLite and schema migration |
| Retrieval/ML | `rank-bm25`, `numpy`, `faiss-cpu`, `sentence-transformers` | BM25Plus, vector arrays/index, embedding and cross-encoder baseline adapters |
| LLM adapter | `ollama` | Optional Ollama async client; not contacted unless explicitly configured/called |
| Configuration/logging | `pydantic-settings`, `structlog` | Typed environment settings and structured logs |
| Development | `pytest`, `ruff`, `mypy` | Tests, lint/format, static typing |

No LangChain/LlamaIndex, hosted LLM SDK, vector database, cache service, or database vector extension is declared.

## Running And Extending

### Setup and checks

```bash
uv sync
cp .env.example .env  # optional local overrides; generation defaults to disabled
uv run alembic upgrade head
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run uvicorn support_assistant.main:create_app --factory --reload
```

The app runs on the Uvicorn default `127.0.0.1:8000`; health is `GET /health`. Apply migration before using knowledge-base endpoints. Do not run tests against the configured developer DB: integration tests build isolated temporary databases.

### Ingest FAQ data

```bash
uv run python scripts/ingest_faqs.py data/raw/sample_faqs.jsonl
```

Input may also be a UTF-8 `.json` array. The CLI reports aggregate counts and a safe first validation issue; it does not print FAQ answers.

### Run retrieval benchmarks

```bash
uv run python scripts/evaluate_retrieval.py --dataset data/evaluation/sample_retrieval.jsonl --retriever bm25
uv run python scripts/evaluate_retrieval.py --dataset data/evaluation/sample_retrieval.jsonl --retriever vector
uv run python scripts/evaluate_retrieval.py --dataset data/evaluation/sample_retrieval.jsonl --retriever hybrid
uv run python scripts/evaluate_retrieval.py --dataset data/evaluation/sample_retrieval.jsonl --retriever hybrid-reranker
```

The benchmark uses active records in `Settings.database_url`; it does not ingest data. Vector/hybrid modes can download MiniLM weights on first use, and hybrid-reranker can download cross-encoder weights. Use `--output PATH` to select a JSON destination. Default result paths are in `data/evaluation/results/`.

### Enable a generation service

The repo does not currently expose a draft HTTP endpoint or compose retrieval/generation at app startup. A caller must explicitly provide a configured `Settings`, an already built reranked retriever, a mapping of active FAQ IDs to `RetrievalDocument`s, and `create_retrieval_generation_service(...)`. To create the Ollama provider, set `SUPPORT_ASSISTANT_LLM_PROVIDER=ollama` and `SUPPORT_ASSISTANT_LLM_MODEL` to a model already available to the Ollama server. The provider factory never selects a model or falls back. No live Ollama request is part of the normal test suite.

### Extension points

- **New LLM provider:** implement `generation.providers.LLMProvider.generate(prompt) -> GenerationResult`. Add explicit selection in `create_llm_provider(settings)` and any provider-specific settings in `core/config.py`. Do not import/construct the SDK in `GenerationService`, a route, or at module import.
- **New retriever:** implement the search contract returning `RetrievalCandidate` with stable FAQ IDs/ranks. For hybrid use, adapt it to the text retriever shape consumed by `HybridRetriever`; keep its indexing/model lifecycle explicit. Do not alter RRF to combine raw scores.
- **New reranker:** implement `Reranker.rerank(query, candidates, documents, top_k)`. Use only the bounded hybrid pool. Preserve FAQ IDs and do not label its score confidence.
- **FAQ field:** update Pydantic FAQ schemas, SQLAlchemy `FAQModel`, reversible Alembic migration, repository create/update mapping, ingestion normalization/validation, API response behavior, retrieval document projection if the field belongs there, and unit/integration tests. Avoid modifying the DB schema for derived embeddings/scores.
- **Settings:** add a typed field to `core/config.py`, document its environment variable in `.env.example`, inject `Settings` into construction/composition, and test default plus environment override. Do not read env variables throughout business logic.
- **Service:** place business rules in a responsibility-specific service, depend on protocols/repositories, and compose it from a caller/dependency. Routes should validate, call the service, and serialize typed results only.
- **API endpoint:** add a router function with typed schema and FastAPI dependency, mount it in `main.create_app`, map domain errors via the existing exception hierarchy, and test request ID/error envelope behavior. Do not expose retrieval/generation until product/API scope is intentionally designed.

## Rules For Future Development

1. Preserve API → service → repository boundaries; routes are adapters, not business logic.
2. Depend on the local provider/retriever protocols rather than vendor SDKs in application services.
3. Do not load embedding, cross-encoder, or LLM models at Python module import.
4. Do not initialize retrieval indexes at import or put mutable indexes in module globals.
5. Keep FAQ question and answer as one knowledge/retrieval item; there is no chunking implementation yet.
6. RRF consumes ranks, not BM25/cosine score magnitudes.
7. Similarity, RRF, and reranker scores are ranking signals, never probabilities/confidence.
8. Keep hybrid candidate pool and final reranked evidence bounded/configurable.
9. Only send selected evidence to generation; never the entire database.
10. Validate model-returned FAQ IDs against evidence supplied and construct citations in application code.
11. Do not log prompts, full customer queries/conversations, answers, credentials, or provider payloads.
12. Do not automatically send customer responses; generation is an internal draft only.
13. Use fake providers/models for deterministic tests; standard pytest must not need Ollama or model downloads.
14. Keep `docs/architecture.md` and the numbered ADRs aligned with real behavior; clearly mark unfinished placeholders.
15. Do not add frameworks or distributed services without a concrete requirement.

## Azure AI Search + Hugging Face Setup

This repository supports an end-to-end production RAG pipeline backed by **Azure AI Search** for hybrid retrieval/ranking and **Hugging Face** for embeddings (`BAAI/bge-small-en-v1.5`) and LLM generation (`Qwen/Qwen3-8B`).

Follow these steps to configure and run the pipeline:

### 1. Create Azure AI Search Resource
Create an Azure AI Search service in the Azure Portal or via Azure CLI.

### 2. Obtain Search Endpoint
Copy your Azure AI Search URL (e.g. `https://<YOUR-SEARCH-SERVICE>.search.windows.net`).

### 3. Obtain API Key
Obtain an admin key or query key from your Azure AI Search resource settings.

### 4. Create Hugging Face Access Token
Create a Hugging Face account and generate an API User Access Token (`hf_...`) with read access to inference endpoints.

### 5. Configure `.env`
Copy `.env.example` to `.env` and fill in your credentials:

```env
SUPPORT_ASSISTANT_HF_API_KEY=hf_xxxxxxxxxxxxxxxxxxxxxxxxx
SUPPORT_ASSISTANT_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
SUPPORT_ASSISTANT_LLM_PROVIDER=huggingface
SUPPORT_ASSISTANT_LLM_MODEL=Qwen/Qwen3-8B

SUPPORT_ASSISTANT_AZURE_SEARCH_ENDPOINT=https://<YOUR-SEARCH-SERVICE>.search.windows.net
SUPPORT_ASSISTANT_AZURE_SEARCH_API_KEY=xxxxxxxxxxxxxxxxxxxxxxxx
SUPPORT_ASSISTANT_AZURE_SEARCH_INDEX=faq-index
```

### 6. Install Dependencies
Install all required dependencies using `uv`:

```bash
uv sync
```

### 7. Run Azure Search Index Setup
Create or update the Azure AI Search index schema (384-dimensional vector field + HNSW profile):

```bash
python scripts/setup_azure_search.py
```

### 8. Sync FAQs to Azure Search
Synchronize active database FAQs into Azure AI Search using Hugging Face embeddings:

```bash
python scripts/sync_faqs_to_azure_search.py
```

### 9. Test Hugging Face Integration
Verify Hugging Face BGE embeddings (384-dim) and Qwen3-8B generation:

```bash
python scripts/test_huggingface.py
```

### 10. Test Azure Search Integration
Verify Azure AI Search connectivity and hybrid search execution:

```bash
python scripts/test_azure_search.py
```

### 11. Run End-to-End Pipeline Verification
Execute full end-to-end query processing (Retrieval → Generation → Phase 7 Evaluation):

```bash
python scripts/test_e2e_pipeline.py
```

### 12. Run the Application
Start the FastAPI server:

```bash
uv run uvicorn support_assistant.main:create_app --factory --reload
```

---

## Limitations And Deferred Work


- There is no public retrieval or draft API, and `create_app` does not instantiate retrieval models or compose generation. Current production API routes are health and FAQ knowledge-base operations only.
- LLM generation has an Ollama adapter and unit/fake-client tests but no live-server integration test. Provider is `not-configured` by default; a model must be installed/configured externally.
- The prompt requests evidence-grounded output, but does not technically guarantee entailment. Citation-ID validity does not verify that each sentence is supported by its cited FAQ.
- Phase 7 implements `ConfidenceService`, `KnowledgeGapService`, `EvidenceSupportEvaluator`, and `Phase7DraftService` with structured abstention decisions (`ACCEPT`, `REVIEW`, `ABSTAIN`). Empirical calibration of heuristic confidence scores against larger human-labeled golden evaluation datasets remains ongoing work.
- `observability/metrics.py` is empty: there is no runtime metrics exporter. Retrieval metrics are offline benchmark calculations.
- Draft persistence and agent review/send workflow are not implemented. No customer message is sent by this code.
- The five-query evaluation data is synthetic, and current perfect stored scores are not meaningful production-quality evidence. Build a human-reviewed golden set before choosing final models or claims.
- Production database deployment, authentication, load/throughput testing, provider availability policy, and broader privacy controls remain future hardening work.

## Development Cycle

1. Read this file, the relevant ADR, and the owning module/test before editing.
2. Find the existing protocol/schema/service boundary and change the smallest responsible layer.
3. Add deterministic tests with fake providers/indexes or isolated SQLite where appropriate.
4. Run the focused test first, then `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest`, and `uv run mypy src`.
5. Review `git diff --check` and the diff for unintended changes; update docs when contracts/status change.
6. Do not commit or push unless explicitly requested.
