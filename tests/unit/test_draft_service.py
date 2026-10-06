from collections.abc import Sequence
from typing import Any

import pytest

from support_assistant.generation.providers import GenerationResult, LLMProvider
from support_assistant.generation.service import GenerationService
from support_assistant.schemas.confidence import ConfidenceDecision
from support_assistant.schemas.retrieval import RetrievalCandidate, RetrievalDocument
from support_assistant.services.confidence_service import ConfidenceService
from support_assistant.services.draft_service import Phase7DraftService


class FakeRetriever:
    def __init__(self, candidates: list[RetrievalCandidate]) -> None:
        self.candidates = candidates

    def search(self, query: str, *, top_k: int | None = None) -> Sequence[RetrievalCandidate]:
        if top_k is not None:
            return self.candidates[:top_k]
        return self.candidates


class FakeLLMProvider(LLMProvider):
    def __init__(self, text: str) -> None:
        self.text = text

    async def generate(self, prompt: str, **kwargs: Any) -> GenerationResult:
        return GenerationResult(text=self.text, model="fake-llm", latency_ms=10.0)


@pytest.mark.anyio
async def test_phase7_pipeline_accept() -> None:
    doc1 = RetrievalDocument(
        faq_id="faq-1",
        question="How do I reset my password?",
        answer="Go to settings page and click reset password link.",
        metadata={"source": "security-guide"},
    )
    documents = {"faq-1": doc1}
    candidates = [
        RetrievalCandidate(document_id="faq-1", score=0.85, rank=1, retrieval_stage="reranker")
    ]
    retriever = FakeRetriever(candidates)

    llm_payload = (
        '{"answer": "Go to settings page and click reset password link.", '
        '"cited_faq_ids": ["faq-1"]}'
    )
    llm_provider = FakeLLMProvider(llm_payload)
    gen_svc = GenerationService(llm_provider, provider_name="fake", model_name="fake-llm")

    conf_svc = ConfidenceService(
        accept_threshold=0.70, review_threshold=0.40, min_evidence_reranker_score=0.30
    )
    pipeline = Phase7DraftService(
        retriever=retriever,
        generation_service=gen_svc,
        confidence_service=conf_svc,
        documents=documents,
    )

    result = await pipeline.process_query("How do I reset my password?")

    assert result.decision == ConfidenceDecision.ACCEPT
    assert result.answer == "Go to settings page and click reset password link."
    assert len(result.citations) == 1
    assert result.citations[0].faq_id == "faq-1"
    assert not result.is_abstained


@pytest.mark.anyio
async def test_phase7_pipeline_knowledge_gap_abstain() -> None:
    doc1 = RetrievalDocument(
        faq_id="faq-1",
        question="How do I reset my password?",
        answer="Go to settings page and click reset password link.",
        metadata={"source": "security-guide"},
    )
    documents = {"faq-1": doc1}
    # Reranker score is very low (0.10), triggering knowledge gap
    candidates = [
        RetrievalCandidate(document_id="faq-1", score=0.10, rank=1, retrieval_stage="reranker")
    ]
    retriever = FakeRetriever(candidates)

    llm_payload = '{"answer": "Go to settings page.", "cited_faq_ids": ["faq-1"]}'
    llm_provider = FakeLLMProvider(llm_payload)
    gen_svc = GenerationService(llm_provider, provider_name="fake", model_name="fake-llm")

    conf_svc = ConfidenceService(knowledge_gap_threshold=0.25)
    pipeline = Phase7DraftService(
        retriever=retriever,
        generation_service=gen_svc,
        confidence_service=conf_svc,
        documents=documents,
    )

    result = await pipeline.process_query("How do I reset my password?")

    assert result.decision == ConfidenceDecision.ABSTAIN
    assert result.answer is None
    assert result.is_abstained
    assert "Knowledge gap detected" in result.reason
