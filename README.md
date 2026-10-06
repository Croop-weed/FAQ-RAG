# Customer Support Assistant

An API foundation for a production-oriented SaaS customer support assistant. The project is being built as an explicit, testable retrieval-augmented generation system; this phase establishes the application structure without implementing retrieval or generation.

## Architecture

FastAPI routes depend on application wiring and typed schemas. Settings are loaded with `pydantic-settings`; application errors are handled centrally; request IDs flow through structured logs and response headers. Future generation and retrieval implementations will satisfy local protocols so vendor and storage choices remain outside business logic.

## Development

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
uv sync
cp .env.example .env
uv run pytest
uv run uvicorn support_assistant.main:create_app --factory --reload
```

The API is available at `http://127.0.0.1:8000`; the lightweight health check is `GET /health`. `.env` values use the `SUPPORT_ASSISTANT_` prefix and override development defaults. Do not commit `.env` or put secrets in logs.

Run quality checks with:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

## Phase Status

Implemented: configuration, structured logging, request correlation, FastAPI app factory, centralized API errors, provider/retriever contracts, FAQ persistence, knowledge-base API, JSON/JSONL ingestion, and typed retrieval-evaluation examples.

Apply the local schema migration before using knowledge-base endpoints:

```bash
uv run alembic upgrade head
uv run python scripts/ingest_faqs.py data/raw/sample_faqs.jsonl
```

The sample includes one intentional duplicate. `POST /knowledge-base/faqs/bulk` accepts JSON records (up to 1,000 per call) and reports partial validation failures. The CLI supports UTF-8 JSON arrays and JSONL; malformed JSONL records are reported without aborting valid records. Duplicate identity uses normalized question, product, and version; valid duplicates count as accepted and are separately reported.

The evaluation JSONL schema and `data/evaluation/sample_retrieval.jsonl` establish labeled query-to-FAQ examples for later Recall@K, Precision@K, MRR, hit-rate, reranker, and abstention evaluation. They do not calculate metrics.

Not implemented: chunking, lexical or vector search, embeddings, fusion, reranking, model clients, prompts, grounded generation, confidence scoring, or answer generation. Model/provider settings remain placeholders; no model has been selected or loaded.

Run the app after applying migrations with `uv run uvicorn support_assistant.main:create_app --factory --reload`.
