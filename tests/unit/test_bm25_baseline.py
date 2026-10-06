import pytest

from support_assistant.retrieval.bm25_search import BM25Retriever
from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.schemas.retrieval import RetrievalDocument


@pytest.fixture
def documents() -> list[RetrievalDocument]:
    return [
        RetrievalDocument(
            faq_id="faq-b", question="Reset account password", answer="Use password reset."
        ),
        RetrievalDocument(
            faq_id="faq-a", question="Download an invoice", answer="Open billing invoices."
        ),
    ]


def test_bm25_returns_relevant_id_and_respects_top_k(
    documents: list[RetrievalDocument],
) -> None:
    retriever = BM25Retriever(documents)

    results = retriever.search("forgot account password", top_k=1)

    assert len(results) == 1
    assert results[0].faq_id == "faq-b"
    assert results[0].rank == 1


def test_bm25_ties_are_deterministic(documents: list[RetrievalDocument]) -> None:
    retriever = BM25Retriever(documents)

    first = retriever.search("unmatched", top_k=2)
    second = retriever.search("unmatched", top_k=2)

    assert [candidate.faq_id for candidate in first] == ["faq-a", "faq-b"]
    assert [candidate.faq_id for candidate in first] == [candidate.faq_id for candidate in second]


def test_bm25_rejects_empty_query_and_nonpositive_top_k(
    documents: list[RetrievalDocument],
) -> None:
    retriever = BM25Retriever(documents)

    with pytest.raises(InvalidRetrievalRequest):
        retriever.search("  ")
    with pytest.raises(InvalidRetrievalRequest):
        retriever.search("password", top_k=0)


def test_empty_bm25_corpus_returns_no_results() -> None:
    assert BM25Retriever([]).search("password") == []


def test_duplicate_faq_ids_are_rejected(documents: list[RetrievalDocument]) -> None:
    with pytest.raises(InvalidRetrievalRequest):
        BM25Retriever([documents[0], documents[0]])
