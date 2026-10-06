from collections.abc import Sequence

import pytest

from support_assistant.retrieval.exceptions import RerankingError
from support_assistant.retrieval.fusion import ReciprocalRankFusion
from support_assistant.retrieval.pipeline import HybridRetriever
from support_assistant.retrieval.reranker import (
    CrossEncoderReranker,
    CrossEncoderRerankingRetriever,
)
from support_assistant.schemas.retrieval import RetrievalCandidate, RetrievalDocument


class FakeCrossEncoder:
    def __init__(self, scores: Sequence[float]) -> None:
        self.scores = scores
        self.pairs: list[tuple[str, str]] = []

    def predict(self, sentences: Sequence[tuple[str, str]]) -> Sequence[float]:
        self.pairs = list(sentences)
        return self.scores


class FixedRetriever:
    name = "fixed"

    def __init__(self, results: list[RetrievalCandidate]) -> None:
        self.results = results
        self.requested_top_k: list[int] = []

    def search(self, query: str, *, top_k: int) -> list[RetrievalCandidate]:
        self.requested_top_k.append(top_k)
        return self.results[:top_k]


def docs() -> dict[str, RetrievalDocument]:
    return {
        "faq-a": RetrievalDocument(faq_id="faq-a", question="Question A", answer="Answer A"),
        "faq-b": RetrievalDocument(faq_id="faq-b", question="Question B", answer="Answer B"),
    }


def ranked() -> list[RetrievalCandidate]:
    return [
        RetrievalCandidate(document_id="faq-a", score=0.03, rank=1, retrieval_stage="rrf"),
        RetrievalCandidate(document_id="faq-b", score=0.02, rank=2, retrieval_stage="rrf"),
    ]


def test_cross_encoder_builds_query_document_pairs_and_reranks() -> None:
    model = FakeCrossEncoder([0.1, 0.9])
    reranker = CrossEncoderReranker("mock", model=model)

    result = reranker.rerank("customer question", ranked(), docs(), top_k=1)

    assert model.pairs == [
        ("customer question", "Question A\nAnswer A"),
        ("customer question", "Question B\nAnswer B"),
    ]
    assert len(result) == 1
    assert result[0].faq_id == "faq-b"
    assert result[0].rank == 1
    assert result[0].retrieval_stage == "reranked"
    assert result[0].score == pytest.approx(0.9)
    assert result[0].metadata["rrf_score"] == pytest.approx(0.02)
    assert "confidence" not in result[0].metadata


def test_reranker_empty_candidates_and_missing_document() -> None:
    model = FakeCrossEncoder([])
    reranker = CrossEncoderReranker("mock", model=model)

    assert reranker.rerank("query", [], docs(), top_k=5) == []
    with pytest.raises(RerankingError, match="missing"):
        reranker.rerank("query", ranked(), {"faq-a": docs()["faq-a"]}, top_k=5)


def test_reranker_propagates_inference_and_invalid_score_failures() -> None:
    class BrokenModel:
        def predict(self, sentences):
            raise RuntimeError("model failed")

    with pytest.raises(RerankingError, match="inference"):
        CrossEncoderReranker("mock", model=BrokenModel()).rerank("query", ranked(), docs(), top_k=2)
    with pytest.raises(RerankingError, match="invalid"):
        CrossEncoderReranker("mock", model=FakeCrossEncoder([float("nan"), 0.1])).rerank(
            "query", ranked(), docs(), top_k=2
        )


def test_hybrid_reranking_wrapper_uses_bounded_pool_and_final_top_k() -> None:
    pool = ranked() + [
        RetrievalCandidate(document_id="faq-c", score=0.01, rank=3, retrieval_stage="rrf")
    ]
    lexical = FixedRetriever(pool)
    vector = FixedRetriever(pool)
    hybrid = HybridRetriever(
        lexical,
        vector,
        ReciprocalRankFusion(),
        bm25_top_k=3,
        vector_top_k=3,
        fusion_top_k=2,
    )
    model = FakeCrossEncoder([0.2, 0.9])
    reranked = CrossEncoderRerankingRetriever(
        hybrid,
        CrossEncoderReranker("mock", model=model),
        docs(),
        rerank_top_k=1,
    )

    result = reranked.search("query")

    assert len(model.pairs) == 2
    assert result[0].faq_id == "faq-b"
    assert lexical.requested_top_k == [3]
    assert vector.requested_top_k == [3]
    execution = reranked.search_detailed("query")
    assert execution.stage_latency_ms["reranker"] >= 0
