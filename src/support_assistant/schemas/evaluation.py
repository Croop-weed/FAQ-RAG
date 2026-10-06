import hashlib
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class EvaluationDifficulty(StrEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class EvaluationExample(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    query_id: str = ""
    query: str = Field(min_length=1)
    relevant_faq_ids: list[str] = Field(min_length=1)
    metadata: dict[str, Any] = Field(default_factory=dict)
    category: str | None = None
    product: str | None = None
    version: str | None = None
    difficulty: EvaluationDifficulty | None = None
    notes: str | None = None

    @field_validator("query")
    @classmethod
    def require_nonempty_query(cls, query: str) -> str:
        query = query.strip()
        if not query:
            raise ValueError("query cannot be empty")
        return query

    @field_validator("relevant_faq_ids")
    @classmethod
    def require_unique_relevant_ids(cls, ids: list[str]) -> list[str]:
        if len(ids) != len(set(ids)):
            raise ValueError("relevant_faq_ids must not contain duplicates")
        return ids

    @model_validator(mode="before")
    @classmethod
    def derive_query_id(cls, value: object) -> object:
        if isinstance(value, dict) and not value.get("query_id"):
            query = str(value.get("query", "")).strip()
            digest = hashlib.sha256(query.encode("utf-8")).hexdigest()[:12]
            return {**value, "query_id": f"q-{digest}"}
        return value


class EvaluationRecordError(BaseModel):
    record: int
    code: str
    message: str
    query_id: str | None = None


class EvaluationDataset(BaseModel):
    dataset_name: str
    examples: list[EvaluationExample]
    invalid_records: list[EvaluationRecordError] = Field(default_factory=list)


class RetrievalMetrics(BaseModel):
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    hit_rate: float
    hit_rate_at_k: int
    mean_latency_ms: float
    p50_latency_ms: float
    p95_latency_ms: float


class LatencySummary(BaseModel):
    mean_ms: float
    p50_ms: float
    p95_ms: float


class EvaluationFailure(BaseModel):
    query_id: str
    missed_relevant_faq_ids: list[str]
    confused_faq_ids: list[str] = Field(default_factory=list)


class EvaluationResult(BaseModel):
    created_at: str
    retriever_name: str
    dataset_name: str
    corpus_size: int
    num_queries: int
    invalid_records: list[EvaluationRecordError] = Field(default_factory=list)
    metrics: RetrievalMetrics
    reranker_latency: LatencySummary | None = None
    failures: list[EvaluationFailure] = Field(default_factory=list)
    confused_faq_counts: dict[str, int] = Field(default_factory=dict)
    configuration: dict[str, Any] = Field(default_factory=dict)
    model_name: str | None = None
    reranker_model_name: str | None = None
    embedding_dimension: int | None = None
    index_type: str | None = None
    model_load_time_ms: float | None = None
    reranker_model_load_time_ms: float | None = None
    embedding_build_time_ms: float | None = None
    index_build_time_ms: float | None = None
    memory_bytes: int | None = None
