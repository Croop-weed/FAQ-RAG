from support_assistant.schemas.confidence import ConfidenceDecision
from support_assistant.schemas.draft import (
    DraftCitation,
    EvidenceItem,
    GenerationMetadata,
    GroundedDraft,
)
from support_assistant.services.confidence_service import ConfidenceService


def _make_evidence(faq_id: str, question: str, answer: str, score: float = 0.8) -> EvidenceItem:
    return EvidenceItem(
        faq_id=faq_id,
        question=question,
        answer=answer,
        retrieval_rank=1,
        retrieval_score=score,
        retrieval_stage="reranker",
    )


def _make_draft(answer: str, evidence: list[EvidenceItem], cited_ids: list[str]) -> GroundedDraft:
    citations = [
        DraftCitation(faq_id=cid, question=next(e.question for e in evidence if e.faq_id == cid))
        for cid in cited_ids
    ]
    return GroundedDraft(
        answer=answer,
        citations=citations,
        evidence_ids=[e.faq_id for e in evidence],
        provided_evidence=evidence,
        metadata=GenerationMetadata(
            provider="test-provider",
            model="test-model",
            latency_ms=15.0,
            evidence_count=len(evidence),
            prompt_version="v1",
        ),
    )


def test_confidence_knowledge_gap_abstain() -> None:
    svc = ConfidenceService(
        accept_threshold=0.75,
        review_threshold=0.45,
        min_evidence_reranker_score=0.30,
        knowledge_gap_threshold=0.25,
    )
    evidence = [_make_evidence("faq-1", "Reset password", "Click reset link", score=0.15)]
    draft = _make_draft("Click reset link", evidence, ["faq-1"])

    assessment = svc.assess_confidence("How do I reset password?", draft, evidence)

    assert assessment.decision == ConfidenceDecision.ABSTAIN
    assert assessment.confidence_score <= 0.20
    assert "Knowledge gap detected" in assessment.reason


def test_confidence_strong_evidence_accept() -> None:
    svc = ConfidenceService(
        accept_threshold=0.70,
        review_threshold=0.40,
        min_evidence_reranker_score=0.30,
    )
    evidence = [
        _make_evidence(
            "faq-1",
            "How do I reset password?",
            "Go to account settings and click reset password link.",
            score=0.85,
        )
    ]
    draft = _make_draft(
        "Go to account settings and click the reset password link.", evidence, ["faq-1"]
    )

    assessment = svc.assess_confidence("How do I reset password?", draft, evidence)

    assert assessment.decision == ConfidenceDecision.ACCEPT
    assert assessment.confidence_score >= 0.70
    assert "faq-1" in assessment.supporting_evidence_ids
    assert "Draft accepted" in assessment.reason


def test_confidence_borderline_evidence_review() -> None:
    svc = ConfidenceService(
        accept_threshold=0.80,
        review_threshold=0.40,
        min_evidence_reranker_score=0.30,
    )
    evidence = [
        _make_evidence(
            "faq-1",
            "How do I reset password?",
            "Go to account settings and click reset password link.",
            score=0.42,
        ),
        _make_evidence(
            "faq-2", "How do I change email?", "Go to settings and change email.", score=0.40
        ),
    ]
    draft = _make_draft("Go to settings and reset password.", evidence, ["faq-1"])

    assessment = svc.assess_confidence("How do I reset password?", draft, evidence)

    assert assessment.decision == ConfidenceDecision.REVIEW
    assert "Review required" in assessment.reason


def test_confidence_unsupported_claim_abstain() -> None:
    svc = ConfidenceService(
        accept_threshold=0.70,
        review_threshold=0.40,
        min_evidence_reranker_score=0.30,
    )
    evidence = [
        _make_evidence(
            "faq-1",
            "How do I reset password?",
            "Go to settings and click reset password link.",
            score=0.85,
        )
    ]
    draft = _make_draft(
        "Go to settings and click reset password link. "
        "Also we offer free 100 dollar bonus to all customers.",
        evidence,
        ["faq-1"],
    )

    assessment = svc.assess_confidence("How do I reset password?", draft, evidence)

    assert assessment.decision == ConfidenceDecision.ABSTAIN
    assert "Abstained" in assessment.reason
