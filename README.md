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

## Phase 1 Status

Implemented: configuration, structured logging, request correlation, FastAPI app factory, health endpoint, centralized API errors, provider/retriever contracts, and foundation tests.

Not implemented: persistence, FAQ ingestion, chunking, lexical or vector search, fusion, reranking, model clients, prompts, and grounded generation. Model/provider settings are placeholders; no model has been selected or loaded.
