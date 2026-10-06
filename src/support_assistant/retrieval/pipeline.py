from collections.abc import Sequence
from typing import Protocol

import structlog

from support_assistant.retrieval.bm25_search import LexicalRetriever
from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.retrieval.fusion import RankFusionStrategy
from support_assistant.schemas.retrieval import RetrievalCandidate

logger = structlog.get_logger(__name__)


class TextRetriever(Protocol):
    name: str

    def search(self, query: str, *, top_k: int) -> Sequence[RetrievalCandidate]: ...


class HybridRetriever:
    """Run independent lexical and semantic retrievers, then fuse their rankings."""

    name = "hybrid_rrf"

    def __init__(
        self,
        lexical_retriever: LexicalRetriever,
        vector_retriever: TextRetriever,
        fusion: RankFusionStrategy,
        *,
        bm25_top_k: int = 20,
        vector_top_k: int = 20,
        fusion_top_k: int = 20,
    ) -> None:
        if min(bm25_top_k, vector_top_k, fusion_top_k) < 1:
            raise InvalidRetrievalRequest("Hybrid retrieval top-K values must be positive.")
        self.lexical_retriever = lexical_retriever
        self.vector_retriever = vector_retriever
        self.fusion = fusion
        self.bm25_top_k = bm25_top_k
        self.vector_top_k = vector_top_k
        self.fusion_top_k = fusion_top_k

    def search(self, query: str, *, top_k: int | None = None) -> list[RetrievalCandidate]:
        if not query.strip():
            raise InvalidRetrievalRequest("Retrieval query cannot be empty.")
        fused_top_k = top_k if top_k is not None else self.fusion_top_k
        if fused_top_k < 1:
            raise InvalidRetrievalRequest("Hybrid top_k must be at least 1.")
        lexical = self.lexical_retriever.search(query, top_k=self.bm25_top_k)
        semantic = self.vector_retriever.search(query, top_k=self.vector_top_k)
        candidates = self.fusion.fuse([lexical, semantic], top_k=fused_top_k)
        logger.info(
            "hybrid_retrieval_completed",
            lexical_count=len(lexical),
            vector_count=len(semantic),
            fused_count=len(candidates),
        )
        return candidates
