# ADR 0001: Provider and Retriever Abstractions

- Status: Accepted
- Date: 2026-10-07

## Context

The customer support assistant is expected to use language generation, embeddings, lexical retrieval, vector retrieval, and reranking. Provider vendors, embedding models, search engines, and vector databases may change as quality, latency, deployment constraints, licensing, and corpus size become clearer. Application services and API routes should not need to change when those implementation choices change.

## Decision

Define small Python protocols at the module that owns each behavior:

- `LLMProvider` in `generation.providers`
- `EmbeddingProvider` in `retrieval.embeddings`
- `LexicalRetriever` in `retrieval.bm25_search`
- `VectorRetriever` in `retrieval.vector_search`
- `Reranker` in `retrieval.reranker`

Use a shared typed retrieval candidate and a typed generation result. Inject provider instances through application wiring; do not construct vendor clients in routes or business services. Provider and model identifiers are supplied through `Settings`, not embedded in business logic.

These contracts allow later replacements of LLM providers, embedding models, rerankers, lexical search implementations, and vector databases without changing the application layer. They do not select or implement any provider or algorithm in Phase 1.

## Consequences

- Each implementation can be tested independently and substituted with a test double.
- Business services can depend on behavior rather than SDKs or storage details.
- Protocols add a small amount of typing surface; contracts should only expand when a real caller requires it.
- Retrieval orchestration and persistence remain deferred until their respective phases.