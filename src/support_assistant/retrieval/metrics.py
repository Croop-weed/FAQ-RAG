from collections.abc import Sequence

import numpy as np

from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.schemas.evaluation import RetrievalMetrics


def compute_retrieval_metrics(
    *,
    relevant_ids: Sequence[set[str]],
    retrieved_ids: Sequence[Sequence[str]],
    latency_ms: Sequence[float],
    hit_rate_at_k: int = 5,
) -> RetrievalMetrics:
    if not relevant_ids or len(relevant_ids) != len(retrieved_ids):
        raise InvalidRetrievalRequest("Metrics require equally sized, non-empty query results.")
    if len(latency_ms) != len(relevant_ids):
        raise InvalidRetrievalRequest("Metrics require one latency measurement per query.")
    if hit_rate_at_k < 1 or any(not relevant for relevant in relevant_ids):
        raise InvalidRetrievalRequest("Metrics require relevant IDs and a positive hit-rate K.")
    if any(latency < 0 or not np.isfinite(latency) for latency in latency_ms):
        raise InvalidRetrievalRequest("Latency values must be finite and non-negative.")

    recall: dict[int, float] = {}
    for k in (1, 3, 5):
        recall[k] = float(
            np.mean(
                [
                    len(set(results[:k]) & relevant) / len(relevant)
                    for relevant, results in zip(relevant_ids, retrieved_ids, strict=True)
                ]
            )
        )
    reciprocal_ranks = []
    hits = []
    for relevant, results in zip(relevant_ids, retrieved_ids, strict=True):
        first_rank = next(
            (rank for rank, faq_id in enumerate(results, start=1) if faq_id in relevant),
            None,
        )
        reciprocal_ranks.append(1.0 / first_rank if first_rank is not None else 0.0)
        hits.append(bool(set(results[:hit_rate_at_k]) & relevant))
    latencies = np.asarray(latency_ms, dtype=np.float64)
    return RetrievalMetrics(
        recall_at_1=recall[1],
        recall_at_3=recall[3],
        recall_at_5=recall[5],
        mrr=float(np.mean(reciprocal_ranks)),
        hit_rate=float(np.mean(hits)),
        hit_rate_at_k=hit_rate_at_k,
        mean_latency_ms=float(np.mean(latencies)),
        p50_latency_ms=float(np.percentile(latencies, 50)),
        p95_latency_ms=float(np.percentile(latencies, 95)),
    )
