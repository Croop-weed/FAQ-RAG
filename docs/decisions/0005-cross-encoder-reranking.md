# ADR 0005: Bounded Cross-Encoder Reranking

- Status: Accepted
- Date: 2026-10-07

## Context

Independent retrievers and RRF are optimized to find a broad set of potentially relevant FAQ evidence. A cross-encoder can score query/document pairs jointly for more precise ordering, but it is more expensive than first-stage retrieval.

## Decision

Define a provider-neutral `Reranker` contract that receives a query, candidate sequence, FAQ-ID-to-retrieval-document mapping, and final top-K. The initial adapter loads `cross-encoder/ms-marco-MiniLM-L6-v2` only when explicitly constructed, keeps the model for reuse, and scores only the bounded RRF candidate pool. The cross-encoder score alone determines the final order. Original RRF score and source ranks remain trace metadata; they are not added to cross-encoder scores.

The model is an initial local baseline, not a final model selection. Report model load time, reranker-only latency, and end-to-end pipeline latency separately. A missing document or model inference failure raises a retrieval error; no fallback silently returns differently scored results.

## Consequences

- Reranking can be substituted without changing BM25, vector retrieval, fusion, evaluator, or API.
- Candidate bounding limits cross-encoder inference cost.
- Reranker scores are ranking values, not probabilities or confidence.
- A human-reviewed larger evaluation set is required to determine whether quality gains justify added latency.