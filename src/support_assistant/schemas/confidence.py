from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from support_assistant.schemas.draft import DraftCitation, GroundedDraft


class ConfidenceDecision(StrEnum):
    ACCEPT = "accept"
    REVIEW = "review"
    ABSTAIN = "abstain"


class EvidenceSupportResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    supported: bool
    support_score: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    unsupported_claims: list[str] = Field(default_factory=list)
    citation_validity: float = Field(ge=0.0, le=1.0)
    evidence_relevance_scores: dict[str, float] = Field(default_factory=dict)
    explanation: str


class KnowledgeGapAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    is_gap: bool
    reason: str
    gap_type: str = "none"
    confidence_cap: float | None = Field(default=None, ge=0.0, le=1.0)


class ConfidenceAssessment(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: ConfidenceDecision
    confidence_score: float = Field(ge=0.0, le=1.0)
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    weak_evidence_indicators: list[str] = Field(default_factory=list)
    reason: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluatedGroundedDraft(BaseModel):
    model_config = ConfigDict(frozen=True)

    decision: ConfidenceDecision
    confidence: float = Field(ge=0.0, le=1.0)
    answer: str | None = None
    reason: str
    citations: list[DraftCitation] = Field(default_factory=list)
    confidence_assessment: ConfidenceAssessment
    grounded_draft: GroundedDraft | None = None

    @property
    def is_abstained(self) -> bool:
        return self.decision == ConfidenceDecision.ABSTAIN
