from unittest.mock import MagicMock

import numpy as np
import pytest

from support_assistant.retrieval.azure_search import AzureAISearchRetriever
from support_assistant.retrieval.exceptions import InvalidRetrievalRequest


def test_azure_search_init_requires_endpoint_and_key() -> None:
    embedder = MagicMock()
    with pytest.raises(ValueError, match="endpoint is not configured"):
        AzureAISearchRetriever(endpoint="", api_key="key", index_name="idx", embedding_provider=embedder)

    with pytest.raises(ValueError, match="API key is not configured"):
        AzureAISearchRetriever(endpoint="http://endpoint", api_key="", index_name="idx", embedding_provider=embedder)


def test_azure_search_empty_query() -> None:
    embedder = MagicMock()
    retriever = AzureAISearchRetriever(
        endpoint="http://test.search",
        api_key="key",
        index_name="idx",
        embedding_provider=embedder,
        client=MagicMock(),
    )
    with pytest.raises(InvalidRetrievalRequest, match="cannot be empty"):
        retriever.search("   ")


def test_azure_search_invalid_top_k() -> None:
    embedder = MagicMock()
    retriever = AzureAISearchRetriever(
        endpoint="http://test.search",
        api_key="key",
        index_name="idx",
        embedding_provider=embedder,
        client=MagicMock(),
    )
    with pytest.raises(InvalidRetrievalRequest, match="top_k must be at least 1"):
        retriever.search("valid query", top_k=0)


def test_azure_search_successful_retrieval() -> None:
    embedder = MagicMock()
    embedder.embed_query.return_value = np.zeros(384, dtype=np.float32)

    mock_client = MagicMock()
    mock_client.search.return_value = [
        {
            "id": "faq-101",
            "question": "How do I reset my password?",
            "answer": "Click forgot password on login screen.",
            "category": "Account",
            "product": "Web",
            "version": "1.0",
            "region": "US",
            "source": "manual",
            "tags": ["password", "login"],
            "@search.score": 0.01639,
        }
    ]

    retriever = AzureAISearchRetriever(
        endpoint="http://test.search",
        api_key="key",
        index_name="idx",
        embedding_provider=embedder,
        client=mock_client,
    )

    candidates = retriever.search("reset password", top_k=5)
    assert len(candidates) == 1
    cand = candidates[0]
    assert cand.document_id == "faq-101"
    assert cand.score == 0.01639
    assert cand.rank == 1
    assert cand.retrieval_stage == "azure-ai-search-hybrid"
    assert cand.metadata["question"] == "How do I reset my password?"
    assert cand.metadata["answer"] == "Click forgot password on login screen."
