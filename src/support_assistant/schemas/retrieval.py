from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class RetrievalCandidate(BaseModel):
    model_config = ConfigDict(frozen=True)

    document_id: str
    content: str
    score: float
    metadata: dict[str, Any] = Field(default_factory=dict)
