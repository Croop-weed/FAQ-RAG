from support_assistant.schemas.draft import (
    DraftCitation,
    EvidenceItem,
    GenerationMetadata,
    GroundedDraft,
)
from support_assistant.services.knowledge_gap_service import KnowledgeGapService


def _make_evidence(faq_id: str, question: str, answer: str, score: float = 0.8) -> EvidenceItem:
    return EvidenceItem(
        faq_id=faq_id,
        question=question,
        answer=answer,
        retrieval_rank=1,
        retrieval_score=score,
        retrieval_stage="reranker",
    )


def test_empty_evidence_triggers_knowledge_gap() -> None:
    svc = KnowledgeGapService(knowledge_gap_threshold=0.25)
    assessment = svc.evaluate_knowledge_gap("What is the refund policy?", [])

    assert assessment.is_gap
    assert assessment.gap_type == "no_evidence"
    assert assessment.confidence_cap == 0.0


def test_low_reranker_score_triggers_knowledge_gap() -> None:
    svc = KnowledgeGapService(knowledge_gap_threshold=0.30)
    evidence = [
        _make_evidence("faq-1", "Billing question", "Contact support for billing.", score=0.15)
    ]
    assessment = svc.evaluate_knowledge_gap("How do I update billing?", evidence)

    assert assessment.is_gap
    assert assessment.gap_type == "low_reranker_score"
    assert assessment.confidence_cap == 0.20


def test_unmatched_query_terms_triggers_knowledge_gap() -> None:
    svc = KnowledgeGapService(knowledge_gap_threshold=0.10)
    evidence = [
        _make_evidence("faq-1", "Reset Password", "Click forgot password link.", score=0.50)
    ]
    assessment = svc.evaluate_knowledge_gap("quantum teleportation physics protocol", evidence)

    assert assessment.is_gap
    assert assessment.gap_type == "unmatched_query"


def test_draft_refusal_phrase_triggers_knowledge_gap() -> None:
    svc = KnowledgeGapService(knowledge_gap_threshold=0.10)
    evidence = [
        _make_evidence("faq-1", "Reset Password", "Click forgot password link.", score=0.50)
    ]
    draft = GroundedDraft(
        answer="I don't have enough verified information to answer this question.",
        citations=[DraftCitation(faq_id="faq-1", question="Reset Password")],
        evidence_ids=["faq-1"],
        provided_evidence=evidence,
        metadata=GenerationMetadata(
            provider="test", model="test-m", latency_ms=10.0, evidence_count=1, prompt_version="v1"
        ),
    )
    assessment = svc.evaluate_knowledge_gap(
        "What is the password reset step?", evidence, draft=draft
    )

    assert assessment.is_gap
    assert assessment.gap_type == "draft_refusal"


def test_sufficient_knowledge_returns_no_gap() -> None:
    svc = KnowledgeGapService(knowledge_gap_threshold=0.25)
    evidence = [
        _make_evidence(
            "faq-1", "How do I reset my password?", "Click forgot password link.", score=0.75
        )
    ]
    assessment = svc.evaluate_knowledge_gap("How do I reset my password?", evidence)

    assert not assessment.is_gap
    assert assessment.gap_type == "none"
