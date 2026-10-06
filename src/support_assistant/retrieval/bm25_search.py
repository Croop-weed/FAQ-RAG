import re
from collections.abc import Sequence
from typing import Protocol

import structlog
from rank_bm25 import BM25Plus

from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.schemas.retrieval import RetrievalCandidate, RetrievalDocument

logger = structlog.get_logger(__name__)


class LexicalRetriever(Protocol):
    def search(self, query: str, *, top_k: int) -> Sequence[RetrievalCandidate]: ...


class BM25Retriever:
    """In-memory BM25 index built once from a deterministic FAQ ordering."""

    name = "bm25"

    def __init__(self, documents: Sequence[RetrievalDocument]) -> None:
        ordered = sorted(documents, key=lambda document: document.faq_id)
        self._validate_documents(ordered)
        self._documents = ordered
        self._index = (
            BM25Plus([self._tokenize(doc.content) for doc in ordered]) if ordered else None
        )
        logger.info("bm25_index_built", corpus_size=len(ordered), index_type="BM25Plus")

    @property
    def corpus_size(self) -> int:
        return len(self._documents)

    @staticmethod
    def _tokenize(text: str) -> list[str]:
        return re.findall(r"[\w]+", text.casefold())

    @staticmethod
    def _validate_documents(documents: Sequence[RetrievalDocument]) -> None:
        ids = [document.faq_id for document in documents]
        if len(ids) != len(set(ids)):
            raise InvalidRetrievalRequest("FAQ document IDs must be unique.")

    def search(self, query: str, *, top_k: int = 5) -> list[RetrievalCandidate]:
        if not query.strip():
            raise InvalidRetrievalRequest("Retrieval query cannot be empty.")
        if top_k < 1:
            raise InvalidRetrievalRequest("top_k must be at least 1.")
        if self._index is None:
            return []
        scores = self._index.get_scores(self._tokenize(query))
        indices = sorted(
            range(len(self._documents)),
            key=lambda index: (-float(scores[index]), self._documents[index].faq_id),
        )[:top_k]
        return [
            RetrievalCandidate(
                document_id=self._documents[index].faq_id,
                score=float(scores[index]),
                rank=rank,
            )
            for rank, index in enumerate(indices, start=1)
        ]
