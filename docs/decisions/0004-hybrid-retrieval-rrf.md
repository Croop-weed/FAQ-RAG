# ADR 0004: Hybrid Retrieval with Reciprocal Rank Fusion

- Status: Accepted
- Date: 2026-10-07

## Context

BM25 emphasizes exact terms, product names, identifiers, and uncommon wording. Dense vector retrieval can recover paraphrases and conceptual matches. Their scores have different scales and neither is a calibrated probability.

## Decision

Run BM25 and vector retrieval independently and fuse their ranked FAQ IDs with Reciprocal Rank Fusion:

`RRF(d) = sum(1 / (k + rank_i(d)))`

The initial configurable rank constant is `k=60`. Candidate lists are bounded by independent BM25/vector top-K settings; the fused pool is bounded by `fusion_top_k` (initially 20). FAQ IDs are merged, source ranks are retained for traceability, and ties sort by FAQ ID. A backend error fails the hybrid request explicitly rather than silently degrading.

RRF is independent of both search implementations and does not inspect their raw scores. Cross-encoder reranking is a later stage over only the bounded fused pool.

## Consequences

- Lexical and semantic rankings can complement each other without numeric score normalization.
- Rank constant and candidate sizes can be benchmarked through configuration.
- Fusion itself is deterministic and independently testable.
- The candidate pool bounds downstream reranker work but these initial values are not globally optimal.