from collections.abc import Sequence
from typing import Protocol

from support_assistant.schemas.retrieval import RetrievalCandidate


class LexicalRetriever(Protocol):
    def search(self, query: str, *, top_k: int) -> Sequence[RetrievalCandidate]: ...
