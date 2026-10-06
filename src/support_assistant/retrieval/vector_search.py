from collections.abc import Sequence
from typing import Protocol

from support_assistant.schemas.retrieval import RetrievalCandidate


class VectorRetriever(Protocol):
    def search(
        self, query_embedding: Sequence[float], *, top_k: int
    ) -> Sequence[RetrievalCandidate]: ...
