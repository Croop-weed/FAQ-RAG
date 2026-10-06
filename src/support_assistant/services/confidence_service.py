import math
from collections.abc import Sequence

import structlog

from support_assistant.core.config import Settings
from support_assistant.generation.grounding import (
    EvidenceSupportEvaluator,
    HeuristicEvidenceSupportEvaluator,
)
from support_assistant.schemas.confidence import (
    ConfidenceAssessment,
    ConfidenceDecision,
)
from support_assistant.schemas.draft import EvidenceItem, GroundedDraft
from support_assistant.services.knowledge_gap_service import KnowledgeGapService

logger = structlog.get_logger(__name__)


def _normalize_reranker_score(score: float) -> float:
    """Normalize cross-encoder score to [0.0, 1.0] range using a stable sigmoid curve."""
    if score >= 1.0:
        return 1.0
    if score <= -5.0:
        return 0.0
    if 0.0 <= score <= 1.0:
        return score
    # Use standard logistic sigmoid for arbitrary logit range
    return 1.0 / (1.0 + math.exp(-score))


class ConfidenceService:
    """Production confidence service evaluating draft support and knowledge-gap decisions.

    CRITICAL DESIGN PRINCIPLE:
    - Confidence is derived strictly from measurable application signals (reranker scores,
      candidate margins, evidence support score, citation validity, knowledge gap checks).
    - It NEVER uses LLM self-reported confidence.
    - Heuristic score formula is provisional and documented as requiring empirical calibration.
    """

    def __init__(
        self,
        *,
        accept_threshold: float = 0.75,
        review_threshold: float = 0.45,
        min_evidence_reranker_score: float = 0.30,
        min_supporting_evidence_count: int = 1,
        knowledge_gap_threshold: float = 0.25,
        support_evaluator: EvidenceSupportEvaluator | None = None,
        knowledge_gap_service: KnowledgeGapService | None = None,
    ) -> None:
        if review_threshold >= accept_threshold:
            raise ValueError("review_threshold must be strictly less than accept_threshold.")
        self.accept_threshold = accept_threshold
        self.review_threshold = review_threshold
        self.min_evidence_reranker_score = min_evidence_reranker_score
        self.min_supporting_evidence_count = min_supporting_evidence_count
        self.knowledge_gap_threshold = knowledge_gap_threshold
        self.support_evaluator = support_evaluator or HeuristicEvidenceSupportEvaluator()
        self.knowledge_gap_service = knowledge_gap_service or KnowledgeGapService(
            knowledge_gap_threshold=knowledge_gap_threshold,
            min_evidence_reranker_score=min_evidence_reranker_score,
        )

    def assess_confidence(
        self,
        query: str,
        draft: GroundedDraft,
        evidence: Sequence[EvidenceItem],
    ) -> ConfidenceAssessment:
        # Step 1: Knowledge gap check
        kg_assessment = self.knowledge_gap_service.evaluate_knowledge_gap(query, evidence, draft)
        if kg_assessment.is_gap:
            capped_score = min(0.20, kg_assessment.confidence_cap or 0.20)
            logger.info(
                "confidence_decision",
                decision=ConfidenceDecision.ABSTAIN,
                reason=kg_assessment.reason,
                confidence_score=capped_score,
            )
            return ConfidenceAssessment(
                decision=ConfidenceDecision.ABSTAIN,
                confidence_score=capped_score,
                supporting_evidence_ids=[],
                weak_evidence_indicators=[kg_assessment.reason],
                reason=f"Abstained: Knowledge gap detected - {kg_assessment.reason}",
                metadata={
                    "gap_type": kg_assessment.gap_type,
                    "provisional_heuristic": True,
                },
            )

        # Step 2: Evidence support evaluation
        support_result = self.support_evaluator.evaluate(
            query=query,
            answer=draft.answer,
            evidence=evidence,
            cited_faq_ids=[c.faq_id for c in draft.citations],
        )

        # Step 3: Extract measurable signals
        top_score = evidence[0].retrieval_score if evidence else 0.0
        second_score = evidence[1].retrieval_score if len(evidence) > 1 else 0.0
        score_margin = max(0.0, top_score - second_score)
        strong_evidence_count = sum(
            1 for item in evidence if item.retrieval_score >= self.min_evidence_reranker_score
        )

        reranker_signal = _normalize_reranker_score(top_score)
        margin_signal = min(1.0, score_margin / 0.5)
        citation_signal = support_result.citation_validity
        support_signal = support_result.support_score

        # Step 4: Calculate composite heuristic confidence score
        raw_score = (
            0.45 * support_signal
            + 0.35 * reranker_signal
            + 0.10 * citation_signal
            + 0.10 * margin_signal
        )
        confidence_score = round(max(0.0, min(1.0, raw_score)), 4)

        # Collect weak evidence / risk indicators
        weak_indicators: list[str] = []
        if top_score < self.min_evidence_reranker_score:
            weak_indicators.append(f"Top reranker score ({top_score:.2f}) below threshold.")
        if support_result.unsupported_claims:
            weak_indicators.append(
                f"Draft contains {len(support_result.unsupported_claims)} unsupported claim(s)."
            )
        if citation_signal < 1.0:
            weak_indicators.append("Draft contains invalid or unmapped citations.")
        if score_margin < 0.05 and len(evidence) > 1:
            weak_indicators.append("Narrow score margin between top retrieval candidates.")

        # Step 5: Decision Boundaries
        if (
            len(support_result.unsupported_claims) > 0
            or support_signal < 0.40
            or top_score < self.min_evidence_reranker_score
            or confidence_score < self.review_threshold
            or citation_signal < 1.0
        ):
            decision = ConfidenceDecision.ABSTAIN
            reason = (
                f"Abstained: Evidence support is insufficient (confidence {confidence_score:.2f}). "
                + (
                    f"Unsupported claims: {', '.join(support_result.unsupported_claims[:2])}"
                    if support_result.unsupported_claims
                    else support_result.explanation
                )
            )
        elif (
            confidence_score >= self.accept_threshold
            and support_signal >= 0.75
            and len(support_result.unsupported_claims) == 0
            and citation_signal == 1.0
            and strong_evidence_count >= self.min_supporting_evidence_count
        ):
            decision = ConfidenceDecision.ACCEPT
            reason = (
                f"Draft accepted: Strong reranked evidence (score {top_score:.2f}), "
                f"valid citations, and verified support (confidence {confidence_score:.2f})."
            )
        else:
            decision = ConfidenceDecision.REVIEW
            reason = (
                f"Review required: Relevant evidence exists but support is uncertain "
                f"(confidence {confidence_score:.2f}, support score {support_signal:.2f})."
            )

        metadata = {
            "top_reranker_score": top_score,
            "second_reranker_score": second_score,
            "score_margin": score_margin,
            "reranker_signal": reranker_signal,
            "support_signal": support_signal,
            "citation_signal": citation_signal,
            "strong_evidence_count": strong_evidence_count,
            "provisional_heuristic": True,
            "requires_calibration": True,
        }

        logger.info(
            "confidence_decision",
            decision=decision,
            confidence_score=confidence_score,
            support_score=support_signal,
            top_reranker_score=top_score,
            reason=reason,
        )

        return ConfidenceAssessment(
            decision=decision,
            confidence_score=confidence_score,
            supporting_evidence_ids=support_result.supporting_evidence_ids,
            weak_evidence_indicators=weak_indicators,
            reason=reason,
            metadata=metadata,
        )


def create_confidence_service(
    settings: Settings,
    *,
    support_evaluator: EvidenceSupportEvaluator | None = None,
    knowledge_gap_service: KnowledgeGapService | None = None,
) -> ConfidenceService:
    return ConfidenceService(
        accept_threshold=settings.confidence_accept_threshold,
        review_threshold=settings.confidence_review_threshold,
        min_evidence_reranker_score=settings.min_evidence_reranker_score,
        min_supporting_evidence_count=settings.min_supporting_evidence_count,
        knowledge_gap_threshold=settings.knowledge_gap_threshold,
        support_evaluator=support_evaluator,
        knowledge_gap_service=knowledge_gap_service,
    )
