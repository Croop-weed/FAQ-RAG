from support_assistant.generation.grounding import HeuristicEvidenceSupportEvaluator
from support_assistant.schemas.draft import EvidenceItem


def _make_evidence(faq_id: str, question: str, answer: str, score: float = 0.8) -> EvidenceItem:
    return EvidenceItem(
        faq_id=faq_id,
        question=question,
        answer=answer,
        retrieval_rank=1,
        retrieval_score=score,
        retrieval_stage="reranker",
    )


def test_empty_answer_returns_unsupported() -> None:
    evaluator = HeuristicEvidenceSupportEvaluator()
    evidence = [_make_evidence("faq-1", "How to reset password?", "Click forgot password link.")]
    result = evaluator.evaluate(query="reset password", answer="   ", evidence=evidence)

    assert not result.supported
    assert result.support_score == 0.0
    assert result.unsupported_claims == ["Empty answer text"]


def test_no_evidence_returns_unsupported() -> None:
    evaluator = HeuristicEvidenceSupportEvaluator()
    result = evaluator.evaluate(
        query="reset password", answer="Click forgot password link.", evidence=[]
    )

    assert not result.supported
    assert result.support_score == 0.0
    assert len(result.unsupported_claims) > 0


def test_fully_supported_answer() -> None:
    evaluator = HeuristicEvidenceSupportEvaluator()
    evidence = [
        _make_evidence(
            "faq-1", "How do I reset my password?", "Go to settings and click reset password link."
        )
    ]
    query = "How do I reset my password?"
    answer = "Go to settings and click the reset password link."
    result = evaluator.evaluate(
        query=query, answer=answer, evidence=evidence, cited_faq_ids=["faq-1"]
    )

    assert result.supported
    assert result.support_score >= 0.70
    assert result.citation_validity == 1.0
    assert len(result.unsupported_claims) == 0
    assert "faq-1" in result.supporting_evidence_ids


def test_unsupported_claim_detected() -> None:
    evaluator = HeuristicEvidenceSupportEvaluator()
    evidence = [
        _make_evidence(
            "faq-1", "How do I reset my password?", "Go to settings and click reset password link."
        )
    ]
    query = "How do I reset my password?"
    answer = (
        "Go to settings and click reset password link. "
        "Also we will mail a free crypto wallet to your home address."
    )
    result = evaluator.evaluate(
        query=query, answer=answer, evidence=evidence, cited_faq_ids=["faq-1"]
    )

    assert not result.supported
    assert len(result.unsupported_claims) > 0
    assert any("crypto wallet" in claim for claim in result.unsupported_claims)


def test_invalid_citation_lowers_validity() -> None:
    evaluator = HeuristicEvidenceSupportEvaluator()
    evidence = [
        _make_evidence(
            "faq-1", "How do I reset my password?", "Go to settings and click reset password link."
        )
    ]
    query = "How do I reset my password?"
    answer = "Go to settings and click reset password link."
    result = evaluator.evaluate(
        query=query, answer=answer, evidence=evidence, cited_faq_ids=["faq-999"]
    )

    assert not result.supported
    assert result.citation_validity == 0.0
