from collections.abc import Mapping

import structlog

from support_assistant.core.config import Settings
from support_assistant.core.exceptions import GenerationError
from support_assistant.generation.service import (
    GenerationService,
    RerankedRetriever,
    create_generation_service,
)
from support_assistant.schemas.confidence import (
    ConfidenceAssessment,
    ConfidenceDecision,
    EvaluatedGroundedDraft,
)
from support_assistant.schemas.draft import EvidenceItem
from support_assistant.schemas.retrieval import RetrievalDocument
from support_assistant.services.confidence_service import (
    ConfidenceService,
    create_confidence_service,
)

logger = structlog.get_logger(__name__)


class Phase7DraftService:
    """End-to-end pipeline service integrating retrieval/generation with Phase 7 confidence.

    Flow:
    query -> retrieval -> reranking -> evidence -> generation -> draft + citations
          -> EvidenceSupportEvaluator -> ConfidenceService -> KnowledgeGapService -> Result
    """

    def __init__(
        self,
        retriever: RerankedRetriever,
        generation_service: GenerationService,
        confidence_service: ConfidenceService,
        documents: Mapping[str, RetrievalDocument],
        *,
        final_top_k: int = 5,
    ) -> None:
        if final_top_k < 1:
            raise ValueError("final_top_k must be positive.")
        self.retriever = retriever
        self.generation_service = generation_service
        self.confidence_service = confidence_service
        self.documents = documents
        self.final_top_k = final_top_k

    async def process_query(self, query: str) -> EvaluatedGroundedDraft:
        clean_query = query.strip()
        if not clean_query:
            logger.info("draft_process_abstained", reason="empty_query")
            assessment = ConfidenceAssessment(
                decision=ConfidenceDecision.ABSTAIN,
                confidence_score=0.0,
                supporting_evidence_ids=[],
                weak_evidence_indicators=["Customer query is empty."],
                reason="Abstained: Customer query cannot be empty.",
                metadata={"gap_type": "empty_query"},
            )
            return EvaluatedGroundedDraft(
                decision=ConfidenceDecision.ABSTAIN,
                confidence=0.0,
                answer=None,
                reason="Abstained: Customer query cannot be empty.",
                citations=[],
                confidence_assessment=assessment,
                grounded_draft=None,
            )

        # 1. Retrieve candidates
        candidates = self.retriever.search(clean_query, top_k=self.final_top_k)

        # 2. Build evidence list
        evidence: list[EvidenceItem] = []
        for candidate in candidates[: self.final_top_k]:
            doc = self.documents.get(candidate.faq_id)
            if doc is not None:
                metadata = doc.metadata
                evidence.append(
                    EvidenceItem(
                        faq_id=doc.faq_id,
                        question=doc.question,
                        answer=doc.answer,
                        source=metadata.get("source"),
                        category=metadata.get("category"),
                        product=metadata.get("product"),
                        version=metadata.get("version"),
                        tags=metadata.get("tags", []),
                        retrieval_rank=candidate.rank,
                        retrieval_score=candidate.score,
                        retrieval_stage=candidate.retrieval_stage,
                        retrieval_metadata=candidate.metadata,
                    )
                )
            elif candidate.metadata and candidate.metadata.get("question") and candidate.metadata.get("answer"):
                evidence.append(
                    EvidenceItem(
                        faq_id=candidate.faq_id,
                        question=candidate.metadata["question"],
                        answer=candidate.metadata["answer"],
                        source=candidate.metadata.get("source"),
                        category=candidate.metadata.get("category"),
                        product=candidate.metadata.get("product"),
                        version=candidate.metadata.get("version"),
                        tags=candidate.metadata.get("tags", []),
                        retrieval_rank=candidate.rank,
                        retrieval_score=candidate.score,
                        retrieval_stage=candidate.retrieval_stage,
                        retrieval_metadata=candidate.metadata,
                    )
                )


        # 3. Pre-generation Knowledge Gap Check
        kg_assessment = self.confidence_service.knowledge_gap_service.evaluate_knowledge_gap(
            clean_query, evidence
        )
        if kg_assessment.is_gap:
            conf_cap = min(0.20, kg_assessment.confidence_cap or 0.20)
            assessment = ConfidenceAssessment(
                decision=ConfidenceDecision.ABSTAIN,
                confidence_score=conf_cap,
                supporting_evidence_ids=[],
                weak_evidence_indicators=[kg_assessment.reason],
                reason=f"Abstained: Knowledge gap detected - {kg_assessment.reason}",
                metadata={"gap_type": kg_assessment.gap_type},
            )
            logger.info(
                "draft_process_abstained",
                reason=kg_assessment.reason,
                gap_type=kg_assessment.gap_type,
            )
            return EvaluatedGroundedDraft(
                decision=ConfidenceDecision.ABSTAIN,
                confidence=conf_cap,
                answer=None,
                reason=f"Abstained: Knowledge gap detected - {kg_assessment.reason}",
                citations=[],
                confidence_assessment=assessment,
                grounded_draft=None,
            )

        # 4. Grounded LLM Generation
        try:
            draft = await self.generation_service.generate_draft(clean_query, evidence)
        except GenerationError as err:
            logger.warning(
                "draft_generation_failed",
                error_type=type(err).__name__,
                reason=str(err),
            )
            assessment = ConfidenceAssessment(
                decision=ConfidenceDecision.ABSTAIN,
                confidence_score=0.0,
                supporting_evidence_ids=[],
                weak_evidence_indicators=[f"Generation service error: {err}"],
                reason=f"Abstained: Generation service failed - {err}",
                metadata={"error": str(err)},
            )
            return EvaluatedGroundedDraft(
                decision=ConfidenceDecision.ABSTAIN,
                confidence=0.0,
                answer=None,
                reason=f"Abstained: Generation service failed - {err}",
                citations=[],
                confidence_assessment=assessment,
                grounded_draft=None,
            )

        # 5. Post-generation Confidence Assessment
        assessment = self.confidence_service.assess_confidence(clean_query, draft, evidence)

        if assessment.decision == ConfidenceDecision.ABSTAIN:
            logger.info(
                "draft_process_completed",
                decision=assessment.decision,
                confidence_score=assessment.confidence_score,
                reason=assessment.reason,
            )
            return EvaluatedGroundedDraft(
                decision=ConfidenceDecision.ABSTAIN,
                confidence=assessment.confidence_score,
                answer=None,
                reason=assessment.reason,
                citations=draft.citations,
                confidence_assessment=assessment,
                grounded_draft=draft,
            )

        logger.info(
            "draft_process_completed",
            decision=assessment.decision,
            confidence_score=assessment.confidence_score,
            reason=assessment.reason,
        )
        return EvaluatedGroundedDraft(
            decision=assessment.decision,
            confidence=assessment.confidence_score,
            answer=draft.answer,
            reason=assessment.reason,
            citations=draft.citations,
            confidence_assessment=assessment,
            grounded_draft=draft,
        )


def create_phase7_draft_service(
    settings: Settings,
    retriever: RerankedRetriever,
    documents: Mapping[str, RetrievalDocument],
    *,
    generation_service: GenerationService | None = None,
    confidence_service: ConfidenceService | None = None,
) -> Phase7DraftService:
    gen_svc = generation_service or create_generation_service(settings)
    conf_svc = confidence_service or create_confidence_service(settings)
    return Phase7DraftService(
        retriever=retriever,
        generation_service=gen_svc,
        confidence_service=conf_svc,
        documents=documents,
        final_top_k=settings.rerank_top_k,
    )
