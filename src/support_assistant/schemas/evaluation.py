from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class EvaluationDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class EvaluationExample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query: str = Field(min_length=1)
    relevant_faq_ids: list[str] = Field(min_length=1)
    category: str | None = None
    product: str | None = None
    version: str | None = None
    difficulty: EvaluationDifficulty | None = None
    notes: str | None = None
