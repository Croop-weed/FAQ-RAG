import pytest

from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.retrieval.fusion import ReciprocalRankFusion
from support_assistant.retrieval.pipeline import HybridRetriever
from support_assistant.schemas.retrieval import RetrievalCandidate


def candidate(faq_id: str, rank: int, score: float = 0.0) -> RetrievalCandidate:
    return RetrievalCandidate(document_id=faq_id, rank=rank, score=score)


def test_rrf_combines_rank_contributions_without_using_source_scores() -> None:
    fusion = ReciprocalRankFusion(rank_constant=10)
    lexical = [
        candidate("faq-a", 1, -400).model_copy(update={"retrieval_stage": "bm25"}),
        candidate("faq-b", 2, 1000).model_copy(update={"retrieval_stage": "bm25"}),
    ]
    semantic = [
        candidate("faq-b", 1, -1).model_copy(update={"retrieval_stage": "vector"}),
        candidate("faq-c", 2, 9999).model_copy(update={"retrieval_stage": "vector"}),
    ]

    fused = fusion.fuse([lexical, semantic], top_k=3)

    assert [item.faq_id for item in fused] == ["faq-b", "faq-a", "faq-c"]
    assert fused[0].score == pytest.approx(1 / 12 + 1 / 11)
    assert fused[1].score == pytest.approx(1 / 11)
    assert fused[0].metadata["source_ranks"] == {"bm25": 2, "vector": 1}
    assert len({item.faq_id for item in fused}) == 3


def test_rrf_single_or_empty_rankings_and_top_k() -> None:
    fusion = ReciprocalRankFusion(rank_constant=1)

    fused = fusion.fuse([[candidate("b", 2), candidate("a", 1)]], top_k=1)

    assert [item.faq_id for item in fused] == ["a"]
    assert fusion.fuse([[], []], top_k=4) == []


def test_rrf_ties_are_sorted_by_faq_id_and_constant_is_configurable() -> None:
    fusion = ReciprocalRankFusion(rank_constant=2)

    tied = fusion.fuse([[candidate("z", 1), candidate("a", 1)]], top_k=2)

    assert [item.faq_id for item in tied] == ["a", "z"]
    assert tied[0].score == pytest.approx(1 / 3)


def test_rrf_rejects_invalid_constant_top_k_and_duplicate_ids() -> None:
    with pytest.raises(InvalidRetrievalRequest):
        ReciprocalRankFusion(rank_constant=0)
    fusion = ReciprocalRankFusion()
    with pytest.raises(InvalidRetrievalRequest):
        fusion.fuse([], top_k=0)
    with pytest.raises(InvalidRetrievalRequest):
        fusion.fuse([[candidate("a", 1), candidate("a", 2)]], top_k=2)


class StubRetriever:
    name = "stub"

    def __init__(self, results: list[RetrievalCandidate], error: Exception | None = None) -> None:
        self.results = results
        self.error = error
        self.calls: list[tuple[str, int]] = []

    def search(self, query: str, *, top_k: int) -> list[RetrievalCandidate]:
        self.calls.append((query, top_k))
        if self.error:
            raise self.error
        return self.results[:top_k]


def test_hybrid_retriever_fuses_independent_backend_results() -> None:
    lexical = StubRetriever([candidate("faq-a", 1), candidate("faq-b", 2)])
    vector = StubRetriever([candidate("faq-b", 1), candidate("faq-c", 2)])
    retriever = HybridRetriever(
        lexical,
        vector,
        ReciprocalRankFusion(60),
        bm25_top_k=4,
        vector_top_k=6,
        fusion_top_k=2,
    )

    results = retriever.search("query")

    assert [candidate.faq_id for candidate in results] == ["faq-b", "faq-a"]
    assert lexical.calls == [("query", 4)]
    assert vector.calls == [("query", 6)]
    assert len(retriever.search("query", top_k=1)) == 1


def test_hybrid_propagates_backend_failures_explicitly() -> None:
    lexical = StubRetriever([candidate("faq-a", 1)])
    vector = StubRetriever([], error=RuntimeError("vector backend unavailable"))
    retriever = HybridRetriever(lexical, vector, ReciprocalRankFusion())

    with pytest.raises(RuntimeError, match="vector backend unavailable"):
        retriever.search("query")


def test_hybrid_rejects_invalid_query() -> None:
    retriever = HybridRetriever(StubRetriever([]), StubRetriever([]), ReciprocalRankFusion())

    with pytest.raises(InvalidRetrievalRequest):
        retriever.search(" ")
