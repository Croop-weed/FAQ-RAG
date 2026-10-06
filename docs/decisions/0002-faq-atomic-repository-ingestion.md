# ADR 0002: FAQ Atomicity and Ingestion Boundaries

- Status: Accepted
- Date: 2026-10-07

## Context

Future retrieval must return complete, attributable evidence, and curated FAQ data needs reliable validation, persistence, and offline evaluation. API routes should not contain ingestion policy or persistence queries.

## Decision

Represent each FAQ question and answer together as one knowledge unit. Keep Pydantic domain/API schemas separate from SQLAlchemy rows. Define a repository protocol for persistence and coordinate it from a knowledge-base service. The ingestion pipeline validates and normalizes records independently, reports structured failures, applies deterministic first-occurrence deduplication by normalized question + product + version, and persists valid unique records in one transaction. Store an internal unique digest for the same identity to guard concurrent duplicates.

Represent retrieval evaluation cases as JSONL records with a query, one or more relevant FAQ IDs, optional metadata, difficulty, and notes. Keep metric computation for a later evaluation phase.

## Consequences

- Retrieval can consume a complete FAQ without joining detached question/answer records.
- Persistence can be replaced behind the repository contract without changing the service or API.
- Partial batch failures are visible and do not discard valid neighboring records.
- Duplicate imports are idempotent for content identity but do not overwrite existing curated answers.
- Evaluation labels remain small, versionable text data separate from production knowledge records.