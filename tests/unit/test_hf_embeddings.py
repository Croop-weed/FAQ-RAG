from unittest.mock import MagicMock

import numpy as np
import pytest

from support_assistant.retrieval.exceptions import EmbeddingError
from support_assistant.retrieval.hf_embeddings import HuggingFaceEmbeddingProvider


def test_hf_embeddings_initialization_requires_api_key() -> None:
    with pytest.raises(EmbeddingError, match="SUPPORT_ASSISTANT_HF_API_KEY is not configured"):
        HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", api_key="")


def test_hf_embeddings_dimension() -> None:
    provider = HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", api_key="dummy_key")
    assert provider.dimension == 384
    assert provider.model_name == "BAAI/bge-small-en-v1.5"


def test_hf_embeddings_embed_query_empty() -> None:
    provider = HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", api_key="dummy_key")
    with pytest.raises(EmbeddingError, match="cannot be empty"):
        provider.embed_query("   ")


def test_hf_embeddings_embed_documents_empty() -> None:
    provider = HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", api_key="dummy_key")
    vectors = provider.embed_documents([])
    assert vectors.shape == (0, 384)


def test_hf_embeddings_embed_query_success() -> None:
    provider = HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", api_key="dummy_key")
    mock_client = MagicMock()
    mock_vector = np.ones(384, dtype=np.float32)
    mock_client.feature_extraction.return_value = mock_vector
    provider._client = mock_client

    vec = provider.embed_query("password reset")
    assert vec.shape == (384,)
    assert np.allclose(vec, 1.0)


def test_hf_embeddings_embed_documents_success() -> None:
    provider = HuggingFaceEmbeddingProvider(model_name="BAAI/bge-small-en-v1.5", api_key="dummy_key")
    mock_client = MagicMock()
    mock_matrix = np.ones((2, 384), dtype=np.float32)
    mock_client.feature_extraction.return_value = mock_matrix
    provider._client = mock_client

    vectors = provider.embed_documents(["doc1", "doc2"])
    assert vectors.shape == (2, 384)
