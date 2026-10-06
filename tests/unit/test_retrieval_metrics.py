import pytest

from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.retrieval.metrics import compute_retrieval_metrics


def test_metrics_cover_recall_mrr_hit_rate_and_latency_percentiles() -> None:
    metrics = compute_retrieval_metrics(
        relevant_ids=[{"a", "b"}, {"z"}, {"x"}],
        retrieved_ids=[["a", "c", "b"], ["q", "z"], ["q", "r"]],
        latency_ms=[1.0, 2.0, 10.0],
        hit_rate_at_k=2,
    )

    assert metrics.recall_at_1 == pytest.approx(1 / 6)
    assert metrics.recall_at_3 == pytest.approx(2 / 3)
    assert metrics.recall_at_5 == pytest.approx(2 / 3)
    assert metrics.mrr == pytest.approx((1 + 0.5 + 0) / 3)
    assert metrics.hit_rate == pytest.approx(2 / 3)
    assert metrics.hit_rate_at_k == 2
    assert metrics.mean_latency_ms == pytest.approx(13 / 3)
    assert metrics.p50_latency_ms == pytest.approx(2.0)
    assert metrics.p95_latency_ms == pytest.approx(9.2)


def test_metrics_reject_empty_or_misaligned_inputs() -> None:
    with pytest.raises(InvalidRetrievalRequest):
        compute_retrieval_metrics(relevant_ids=[], retrieved_ids=[], latency_ms=[], hit_rate_at_k=5)
    with pytest.raises(InvalidRetrievalRequest):
        compute_retrieval_metrics(relevant_ids=[{"a"}], retrieved_ids=[], latency_ms=[1.0])


def test_metrics_handle_no_retrieval_results() -> None:
    metrics = compute_retrieval_metrics(
        relevant_ids=[{"known"}], retrieved_ids=[[]], latency_ms=[0.0]
    )

    assert metrics.recall_at_1 == metrics.recall_at_3 == metrics.recall_at_5 == 0
    assert metrics.mrr == metrics.hit_rate == 0
