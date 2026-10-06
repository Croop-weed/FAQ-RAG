from collections.abc import Sequence
from typing import Protocol

from support_assistant.schemas.retrieval import RetrievalCandidate


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        *,
        top_k: int,
    ) -> Sequence[RetrievalCandidate]: ...
