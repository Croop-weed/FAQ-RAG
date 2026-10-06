from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetrievalDocument(BaseModel):
    model_config = ConfigDict(frozen=True)

    faq_id: str
    question: str
    answer: str
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def content(self) -> str:
        return f"{self.question}\n{self.answer}"


class RetrievalCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    score: float
    rank: int = Field(ge=1)

    @property
    def faq_id(self) -> str:
        return self.document_id


class RetrievalResult(BaseModel):
    query_id: str
    retriever_name: str
    candidates: list[RetrievalCandidate]
    latency_ms: float = Field(ge=0)
