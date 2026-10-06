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

Implemented: application foundation, FAQ persistence/ingestion, BM25 and vector baselines, hybrid RRF, bounded cross-encoder reranking, and retrieval evaluation.

Apply the local schema migration before using knowledge-base endpoints:

```bash
uv run alembic upgrade head
uv run python scripts/ingest_faqs.py data/raw/sample_faqs.jsonl
```

The sample includes one intentional duplicate. `POST /knowledge-base/faqs/bulk` accepts JSON records (up to 1,000 per call) and reports partial validation failures. The CLI supports UTF-8 JSON arrays and JSONL; malformed JSONL records are reported without aborting valid records. Duplicate identity uses normalized question, product, and version; valid duplicates count as accepted and are separately reported.

The evaluation JSONL schema and `data/evaluation/sample_retrieval.jsonl` provide labeled query-to-FAQ examples. Its five synthetic queries validate the workflow only and are not representative production data.

Not implemented: LLM generation, grounding, confidence scoring, knowledge-gap detection, automatic abstention, or answer sending. The embedding and reranker models are initial baselines only, not final selections.

Run the app after applying migrations with `uv run uvicorn support_assistant.main:create_app --factory --reload`.

## Retrieval Benchmarks

After applying migrations and loading the sample corpus, run any independent or combined retrieval mode:

```bash
uv run python scripts/evaluate_retrieval.py --dataset data/evaluation/sample_retrieval.jsonl --retriever bm25 --output /tmp/bm25.json
uv run python scripts/evaluate_retrieval.py --dataset data/evaluation/sample_retrieval.jsonl --retriever vector --output /tmp/vector.json
uv run python scripts/evaluate_retrieval.py --dataset data/evaluation/sample_retrieval.jsonl --retriever hybrid --output /tmp/hybrid.json
uv run python scripts/evaluate_retrieval.py --dataset data/evaluation/sample_retrieval.jsonl --retriever hybrid-reranker --output /tmp/hybrid-reranker.json
```

The vector baseline defaults to `sentence-transformers/all-MiniLM-L6-v2`. Model loading is explicit and may download weights the first time; subsequent runs use the local model and document-embedding caches. Override the model with `--model` or `SUPPORT_ASSISTANT_EMBEDDING_MODEL`. The demo evaluation file has only five synthetic queries and is for pipeline verification, not meaningful model selection.

Run hybrid RRF and hybrid plus cross-encoder baselines with `--retriever hybrid` and `--retriever hybrid-reranker`. RRF defaults (`BM25=20`, `vector=20`, `fusion=20`, `rrf_k=60`) and reranker output (`5`) are configurable through `SUPPORT_ASSISTANT_` settings. The cross-encoder baseline is `cross-encoder/ms-marco-MiniLM-L6-v2`; its first run may download model weights. Neither RRF nor cross-encoder scores represent confidence.
