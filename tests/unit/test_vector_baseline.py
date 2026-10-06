import sys
from collections.abc import Sequence
from datetime import UTC, datetime
from types import ModuleType

import numpy as np
import pytest

from support_assistant.retrieval.documents import build_retrieval_documents
from support_assistant.retrieval.embeddings import (
    DocumentEmbeddingCache,
    SentenceTransformerEmbeddingProvider,
)
from support_assistant.retrieval.exceptions import EmbeddingError, InvalidRetrievalRequest
from support_assistant.retrieval.vector_search import (
    EmbeddingVectorRetriever,
    FAISSVectorIndex,
)
from support_assistant.schemas.faq import FAQRead, FAQStatus
from support_assistant.schemas.retrieval import RetrievalDocument


class FakeEmbeddingProvider:
    model_name = "deterministic-test-model"
    dimension = 3

    def __init__(self) -> None:
        self.document_calls = 0

    def embed_documents(self, texts: Sequence[str]) -> Sequence[Sequence[float]]:
        self.document_calls += 1
        return [[1.0, 0.0, 0.0] if "password" in text else [0.0, 1.0, 0.0] for text in texts]

    def embed_query(self, text: str) -> Sequence[float]:
        return [1.0, 0.0, 0.0] if "password" in text else [0.0, 1.0, 0.0]


def sample_documents() -> list[RetrievalDocument]:
    return [
        RetrievalDocument(faq_id="faq-z", question="Download invoice", answer="Billing."),
        RetrievalDocument(faq_id="faq-a", question="Reset password", answer="Use reset link."),
    ]


def test_vector_index_returns_cosine_matches_with_stable_ids() -> None:
    documents = sample_documents()
    index = FAISSVectorIndex(documents, [[0.0, 1.0, 0.0], [1.0, 0.0, 0.0]])

    results = index.search([0.9, 0.1, 0.0], top_k=1)

    assert results[0].faq_id == "faq-a"
    assert results[0].score == pytest.approx(0.9938837, abs=1e-5)
    assert index.index_type == "faiss.IndexFlatIP"


def test_vector_retriever_embeds_documents_once_and_reuses_index() -> None:
    provider = FakeEmbeddingProvider()
    retriever = EmbeddingVectorRetriever(sample_documents(), provider)

    first = retriever.search("forgot password", top_k=1)
    second = retriever.search("change password", top_k=2)

    assert first[0].faq_id == "faq-a"
    assert len(second) == 2
    assert provider.document_calls == 1


def test_embedding_cache_reuses_corpus_vectors(tmp_path) -> None:
    provider = FakeEmbeddingProvider()
    cache = DocumentEmbeddingCache(tmp_path)
    pairs = [("faq-a", "Reset password"), ("faq-z", "Download invoice")]

    first = cache.get_or_create(provider, pairs)
    second = cache.get_or_create(provider, pairs)

    assert np.array_equal(first, second)
    assert provider.document_calls == 1


def test_vector_index_handles_empty_corpus() -> None:
    index = FAISSVectorIndex([], np.empty((0, 3), dtype=np.float32))

    assert index.search([1.0, 0.0, 0.0]) == []


def test_vector_index_rejects_invalid_dimensions() -> None:
    with pytest.raises(EmbeddingError):
        FAISSVectorIndex(sample_documents(), [[1.0, 0.0], [0.0, 1.0, 0.0]])


def test_semantic_retriever_rejects_empty_query() -> None:
    retriever = EmbeddingVectorRetriever(sample_documents(), FakeEmbeddingProvider())

    with pytest.raises(InvalidRetrievalRequest):
        retriever.search(" ")


def test_sentence_transformer_adapter_is_mockable_without_model_download(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeModel:
        def __init__(self, model_name: str) -> None:
            self.model_name = model_name

        def get_embedding_dimension(self) -> int:
            return 3

        def encode(self, texts, **kwargs):
            return np.ones((len(texts), 3), dtype=np.float32)

    module = ModuleType("sentence_transformers")
    module.SentenceTransformer = FakeModel
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    provider = SentenceTransformerEmbeddingProvider("example/test-model")

    assert provider.model_name == "example/test-model"
    assert provider.dimension == 3
    assert provider.embed_documents(["one", "two"]).shape == (2, 3)
    assert provider.embed_query("one").shape == (3,)


def test_document_builder_uses_complete_active_faqs_only() -> None:
    created_at = datetime.now(UTC)
    faqs = [
        FAQRead(
            id="faq-z",
            question="Question Z",
            answer="Answer Z",
            category="support",
            product="Orbit Desk",
            version="2.x",
            region=None,
            tags=["z"],
            source=None,
            status=FAQStatus.ACTIVE,
            created_at=created_at,
            updated_at=created_at,
        ),
        FAQRead(
            id="faq-old",
            question="Inactive question",
            answer="Inactive answer",
            category=None,
            product=None,
            version=None,
            region=None,
            tags=[],
            source=None,
            status=FAQStatus.INACTIVE,
            created_at=created_at,
            updated_at=created_at,
        ),
    ]

    documents = build_retrieval_documents(faqs)

    assert [document.faq_id for document in documents] == ["faq-z"]
    assert documents[0].content == "Question Z\nAnswer Z"
    assert documents[0].metadata["product"] == "Orbit Desk"
