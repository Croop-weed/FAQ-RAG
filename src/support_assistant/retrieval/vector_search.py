from collections.abc import Sequence
from typing import Protocol

import numpy as np
import structlog

from support_assistant.retrieval.embeddings import DocumentEmbeddingCache, EmbeddingProvider
from support_assistant.retrieval.exceptions import EmbeddingError, InvalidRetrievalRequest
from support_assistant.schemas.retrieval import RetrievalCandidate, RetrievalDocument

logger = structlog.get_logger(__name__)


class VectorRetriever(Protocol):
    def search(
        self, query_embedding: Sequence[float], *, top_k: int
    ) -> Sequence[RetrievalCandidate]: ...


class FAISSVectorIndex:
    """FAISS inner-product index over L2-normalized vectors (cosine similarity)."""

    index_type = "faiss.IndexFlatIP"

    def __init__(
        self,
        documents: Sequence[RetrievalDocument],
        embeddings: Sequence[Sequence[float]],
    ) -> None:
        try:
            vectors = np.asarray(embeddings, dtype=np.float32)
        except ValueError as error:
            raise EmbeddingError("Document embeddings have inconsistent dimensions.") from error
        if not documents and vectors.size == 0:
            vectors = np.empty((0, 0), dtype=np.float32)
        if vectors.ndim != 2 or vectors.shape[0] != len(documents):
            raise EmbeddingError("Document embeddings must have one row per FAQ document.")
        if not np.isfinite(vectors).all():
            raise EmbeddingError("Document embeddings contain non-finite values.")
        pairs = sorted(zip(documents, vectors, strict=True), key=lambda pair: pair[0].faq_id)
        self.documents = [document for document, _ in pairs]
        ids = [document.faq_id for document in self.documents]
        if len(ids) != len(set(ids)):
            raise InvalidRetrievalRequest("FAQ document IDs must be unique.")
        vectors = np.asarray([vector for _, vector in pairs], dtype=np.float32)
        self.dimension = int(vectors.shape[1]) if vectors.ndim == 2 else 0
        if self.documents and self.dimension < 1:
            raise EmbeddingError("Document embeddings must have a positive dimension.")
        self._index = None
        if self.documents:
            try:
                import faiss
            except ImportError as error:
                raise EmbeddingError("FAISS CPU is required for vector retrieval.") from error
            norms = np.linalg.norm(vectors, axis=1)
            if np.any(norms == 0):
                raise EmbeddingError("Zero-length embeddings cannot be cosine-normalized.")
            normalized = np.ascontiguousarray(vectors / norms[:, np.newaxis], dtype=np.float32)
            self._index = faiss.IndexFlatIP(self.dimension)
            self._index.add(normalized)
        logger.info(
            "vector_index_built",
            corpus_size=len(self.documents),
            embedding_dimension=self.dimension,
            index_type=self.index_type,
        )

    @property
    def corpus_size(self) -> int:
        return len(self.documents)

    def search(
        self, query_embedding: Sequence[float], *, top_k: int = 5
    ) -> list[RetrievalCandidate]:
        if top_k < 1:
            raise InvalidRetrievalRequest("top_k must be at least 1.")
        if not self.documents:
            return []
        query = np.asarray(query_embedding, dtype=np.float32)
        if query.shape != (self.dimension,) or not np.isfinite(query).all():
            raise EmbeddingError("Query embedding has an invalid shape or values.")
        norm = float(np.linalg.norm(query))
        if norm == 0:
            raise EmbeddingError("Zero-length query embedding cannot be cosine-normalized.")
        if self._index is None:
            raise EmbeddingError("FAISS index was not initialized.")
        scores, indices = self._index.search(
            np.ascontiguousarray((query / norm).reshape(1, -1)), self.corpus_size
        )
        ordered = sorted(
            (
                (float(score), self.documents[int(index)].faq_id)
                for score, index in zip(scores[0], indices[0], strict=True)
                if index >= 0
            ),
            key=lambda row: (-row[0], row[1]),
        )[:top_k]
        return [
            RetrievalCandidate(
                document_id=faq_id,
                score=score,
                rank=rank,
                retrieval_stage="vector",
            )
            for rank, (score, faq_id) in enumerate(ordered, start=1)
        ]


class EmbeddingVectorRetriever:
    """Text query adapter over an embedding provider and reusable FAISS index."""

    name = "vector"

    def __init__(
        self,
        documents: Sequence[RetrievalDocument],
        provider: EmbeddingProvider,
        *,
        cache: DocumentEmbeddingCache | None = None,
        document_embeddings: Sequence[Sequence[float]] | None = None,
    ) -> None:
        ordered = sorted(documents, key=lambda document: document.faq_id)
        if len({document.faq_id for document in ordered}) != len(ordered):
            raise InvalidRetrievalRequest("FAQ document IDs must be unique.")
        self.provider = provider
        self.documents = ordered
        embeddings: Sequence[Sequence[float]]
        if document_embeddings is not None:
            embeddings = document_embeddings
        elif not ordered:
            embeddings = []
        elif cache is None:
            embeddings = provider.embed_documents([document.content for document in ordered])
        else:
            embeddings = cache.get_or_create(
                provider, [(document.faq_id, document.content) for document in ordered]
            ).tolist()
        self.index = FAISSVectorIndex(ordered, embeddings)

    @property
    def corpus_size(self) -> int:
        return self.index.corpus_size

    def search(self, query: str, *, top_k: int = 5) -> list[RetrievalCandidate]:
        if not query.strip():
            raise InvalidRetrievalRequest("Retrieval query cannot be empty.")
        if not self.documents:
            return []
        return self.index.search(self.provider.embed_query(query), top_k=top_k)
