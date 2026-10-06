from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class EvidenceItem(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    faq_id: str
    question: str
    answer: str
    source: str | None = None
    category: str | None = None
    product: str | None = None
    version: str | None = None
    tags: list[str] = Field(default_factory=list)
    retrieval_rank: int = Field(ge=1)
    retrieval_score: float
    retrieval_stage: str
    retrieval_metadata: dict[str, Any] = Field(default_factory=dict)


class DraftCitation(BaseModel):
    model_config = ConfigDict(frozen=True)

    faq_id: str
    source: str | None = None
    question: str


class GeneratedDraftContent(BaseModel):
    """The constrained JSON shape requested from the model."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(min_length=1)
    cited_faq_ids: list[str]


class GenerationMetadata(BaseModel):
    provider: str
    model: str
    latency_ms: float = Field(ge=0)
    input_tokens: int | None = None
    output_tokens: int | None = None
    evidence_count: int = Field(ge=0)
    prompt_version: str


class GroundedDraft(BaseModel):
    answer: str
    citations: list[DraftCitation]
    evidence_ids: list[str]
    provided_evidence: list[EvidenceItem]
    metadata: GenerationMetadata
