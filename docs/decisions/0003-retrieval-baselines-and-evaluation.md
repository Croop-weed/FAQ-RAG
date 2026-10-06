# ADR 0003: Independent Retrieval Baselines and Evaluation

- Status: Accepted
- Date: 2026-10-07

## Context

The support FAQ corpus is small and synthetic today; final retrieval and model choices must be evidence-driven against labeled support queries. Fusion or reranking before independent baselines would obscure which component provides the retrieval quality.

## Decision

- Include BM25Plus as a transparent lexical baseline. BM25 is a strong, inexpensive baseline for exact product terms and identifiers; BM25Plus avoids negative inverse-document-frequency ranking inversions in small corpora.
- Include semantic retrieval behind an `EmbeddingProvider` contract. Use `sentence-transformers/all-MiniLM-L6-v2` only as the first reproducible local CPU baseline; it is compact and practical to evaluate, not selected as the final model.
- Use one complete FAQ question + answer as one retrieval document. This preserves the FAQ as an evidence unit and retains the source FAQ ID.
- Use FAISS CPU `IndexFlatIP` over normalized embeddings. Inner product then equals cosine similarity; the reported score is a ranking similarity, never a probability.
- Evaluate BM25 and vector retrieval independently with labeled relevant FAQ IDs, Recall@K, MRR, Hit Rate@K, and per-query latency. Keep model/index build time separate from query time and optionally cache document vectors by model and corpus identity.
- Defer RRF until independent baseline quality is measured; defer reranking until there is a useful candidate set; defer confidence because raw lexical and cosine scores are not calibrated probabilities; defer generation and abstention to later phases.
- Keep evaluation generic over a text-search retriever protocol. Store machine-readable, aggregate results and query-ID-only failures rather than raw query text.

## Consequences

- Retriever/model implementations can be compared without coupling the evaluator to BM25, FAISS, SQLAlchemy, or FastAPI.
- Corpus ordering, ID mapping, and score tie-breaking are deterministic.
- Vector model loading and index creation are explicit and absent from ordinary unit tests; tests inject deterministic embedding providers.
- The five-query synthetic demo dataset can validate plumbing only. A larger human-reviewed golden set (approximately 100-300 queries) is needed before model or architecture selection.
- BM25 scores and cosine similarities are not comparable scales and must not be treated as confidence.