import re
from collections.abc import Sequence

import structlog

from support_assistant.core.config import Settings
from support_assistant.schemas.confidence import KnowledgeGapAssessment
from support_assistant.schemas.draft import EvidenceItem, GroundedDraft

logger = structlog.get_logger(__name__)

STOP_WORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "but",
    "if",
    "what",
    "when",
    "where",
    "how",
    "which",
    "who",
    "is",
    "are",
    "to",
    "of",
    "in",
    "it",
    "you",
    "your",
    "can",
    "do",
    "does",
    "did",
}

REFUSAL_PHRASES = [
    "don't have enough",
    "do not have enough",
    "insufficient information",
    "not enough verified information",
    "cannot answer",
    "can't answer",
    "no information provided",
    "does not mention",
]


def _tokenize(text: str) -> set[str]:
    words = re.findall(r"\b\w+\b", text.lower())
    return {w for w in words if w not in STOP_WORDS and len(w) > 1}


class KnowledgeGapService:
    """Dedicated knowledge-gap service that evaluates whether available knowledge is sufficient.

    Inspected inputs: query, retrieved evidence, optional generated draft.
    Does NOT perform retrieval, call LLM directly, send messages, or modify knowledge base.
    """

    def __init__(
        self,
        *,
        knowledge_gap_threshold: float = 0.25,
        min_evidence_reranker_score: float = 0.30,
    ) -> None:
        self.knowledge_gap_threshold = knowledge_gap_threshold
        self.min_evidence_reranker_score = min_evidence_reranker_score

    def evaluate_knowledge_gap(
        self,
        query: str,
        evidence: Sequence[EvidenceItem],
        draft: GroundedDraft | None = None,
    ) -> KnowledgeGapAssessment:
        if not evidence:
            logger.info("knowledge_gap_detected", reason="no_evidence")
            return KnowledgeGapAssessment(
                is_gap=True,
                reason="No relevant FAQ evidence was retrieved for the query.",
                gap_type="no_evidence",
                confidence_cap=0.0,
            )

        top_score = evidence[0].retrieval_score
        if top_score < self.knowledge_gap_threshold:
            logger.info(
                "knowledge_gap_detected",
                reason="low_reranker_score",
                top_score=top_score,
                threshold=self.knowledge_gap_threshold,
            )
            return KnowledgeGapAssessment(
                is_gap=True,
                reason=(
                    f"Top reranked evidence score ({top_score:.3f}) is below "
                    f"knowledge-gap threshold ({self.knowledge_gap_threshold:.3f})."
                ),
                gap_type="low_reranker_score",
                confidence_cap=0.20,
            )

        # Token overlap check with top evidence
        query_tokens = _tokenize(query)
        if query_tokens:
            top_evidence_text = f"{evidence[0].question} {evidence[0].answer}"
            top_tokens = _tokenize(top_evidence_text)
            overlap = len(query_tokens & top_tokens)
            if overlap == 0 and len(query_tokens) >= 2:
                logger.info(
                    "knowledge_gap_detected",
                    reason="unmatched_query_terms",
                    query=query,
                )
                return KnowledgeGapAssessment(
                    is_gap=True,
                    reason="Retrieved evidence does not share key terms with customer query.",
                    gap_type="unmatched_query",
                    confidence_cap=0.25,
                )

        # Draft explicit refusal/insufficiency check
        if draft and draft.answer:
            answer_lower = draft.answer.lower()
            if any(phrase in answer_lower for phrase in REFUSAL_PHRASES):
                logger.info("knowledge_gap_detected", reason="draft_refusal_phrase")
                return KnowledgeGapAssessment(
                    is_gap=True,
                    reason="Generated draft indicated insufficient evidence in the knowledge base.",
                    gap_type="draft_refusal",
                    confidence_cap=0.15,
                )

        return KnowledgeGapAssessment(
            is_gap=False,
            reason="Available knowledge is sufficient to support answer generation.",
            gap_type="none",
            confidence_cap=None,
        )


def create_knowledge_gap_service(settings: Settings) -> KnowledgeGapService:
    return KnowledgeGapService(
        knowledge_gap_threshold=settings.knowledge_gap_threshold,
        min_evidence_reranker_score=settings.min_evidence_reranker_score,
    )
