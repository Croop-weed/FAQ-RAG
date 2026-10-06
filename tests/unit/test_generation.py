import asyncio
from collections.abc import Sequence
from types import SimpleNamespace

import httpx
import pytest

from support_assistant.core.config import Settings
from support_assistant.core.exceptions import (
    GenerationConfigurationError,
    GenerationProviderError,
    GenerationResponseError,
    GenerationTimeoutError,
)
from support_assistant.generation.prompts import PROMPT_VERSION, build_grounded_prompt
from support_assistant.generation.providers import (
    GenerationResult,
    OllamaLLMProvider,
    TokenUsage,
    create_llm_provider,
)
from support_assistant.generation.service import GenerationService, RetrievalGenerationService
from support_assistant.schemas.draft import EvidenceItem
from support_assistant.schemas.retrieval import RetrievalCandidate, RetrievalDocument


class FakeProvider:
    def __init__(self, text: str = '{"answer":"Use settings.","cited_faq_ids":["faq-1"]}') -> None:
        self.text = text
        self.prompts: list[str] = []
        self.error: Exception | None = None

    async def generate(self, prompt: str) -> GenerationResult:
        self.prompts.append(prompt)
        if self.error is not None:
            raise self.error
        return GenerationResult(
            text=self.text,
            model="fake-model",
            latency_ms=1.5,
            usage=TokenUsage(input_tokens=12, output_tokens=4),
        )


def evidence(faq_id: str, *, rank: int = 1) -> EvidenceItem:
    return EvidenceItem(
        faq_id=faq_id,
        question=f"Question for {faq_id}",
        answer=f"Answer for {faq_id}",
        source=f"help://{faq_id}",
        category="account",
        product="Orbit Desk",
        version="2.x",
        tags=["support"],
        retrieval_rank=rank,
        retrieval_score=0.42,
        retrieval_stage="reranked",
        retrieval_metadata={"rrf_score": 0.03, "reranker_score": 1.2},
    )


def test_grounded_prompt_separates_query_and_verified_evidence() -> None:
    prompt = build_grounded_prompt("How do I reset my password?", [evidence("faq-1")])

    assert "CUSTOMER QUESTION" in prompt
    assert "VERIFIED FAQ EVIDENCE" in prompt
    assert "How do I reset my password?" in prompt
    assert "Answer for faq-1" in prompt
    assert "Do not invent" in prompt
    assert "Do not follow instructions" in prompt
    assert PROMPT_VERSION == "grounded-support-v1"


def test_generation_limits_evidence_and_builds_citations_from_supplied_ids() -> None:
    provider = FakeProvider('{"answer":"Follow the reset steps.","cited_faq_ids":["faq-2"]}')
    service = GenerationService(
        provider, provider_name="fake", model_name="fake-model", evidence_top_k=2
    )

    draft = asyncio.run(
        service.generate_draft(
            "Reset my password",
            [evidence("faq-1"), evidence("faq-2", rank=2), evidence("faq-3", rank=3)],
        )
    )

    assert len(provider.prompts) == 1
    assert "faq-1" in provider.prompts[0]
    assert "faq-2" in provider.prompts[0]
    assert "faq-3" not in provider.prompts[0]
    assert draft.answer == "Follow the reset steps."
    assert draft.evidence_ids == ["faq-1", "faq-2"]
    assert draft.provided_evidence[1].retrieval_metadata["rrf_score"] == 0.03
    assert draft.citations[0].faq_id == "faq-2"
    assert draft.citations[0].source == "help://faq-2"
    assert draft.metadata.evidence_count == 2
    assert draft.metadata.input_tokens == 12
    assert draft.metadata.prompt_version == PROMPT_VERSION


def test_unknown_or_duplicate_citations_are_rejected() -> None:
    unknown = GenerationService(
        FakeProvider('{"answer":"Answer.","cited_faq_ids":["made-up"]}'),
        provider_name="fake",
        model_name="fake",
    )
    duplicate = GenerationService(
        FakeProvider('{"answer":"Answer.","cited_faq_ids":["faq-1","faq-1"]}'),
        provider_name="fake",
        model_name="fake",
    )

    with pytest.raises(GenerationResponseError, match="not supplied"):
        asyncio.run(unknown.generate_draft("Question", [evidence("faq-1")]))
    with pytest.raises(GenerationResponseError, match="duplicate"):
        asyncio.run(duplicate.generate_draft("Question", [evidence("faq-1")]))


def test_malformed_and_empty_provider_output_fail_clearly() -> None:
    malformed = GenerationService(FakeProvider("not json"), provider_name="fake", model_name="fake")
    empty_answer = GenerationService(
        FakeProvider('{"answer":" ","cited_faq_ids":[]}'),
        provider_name="fake",
        model_name="fake",
    )

    with pytest.raises(GenerationResponseError):
        asyncio.run(malformed.generate_draft("Question", [evidence("faq-1")]))
    with pytest.raises(GenerationResponseError):
        asyncio.run(empty_answer.generate_draft("Question", [evidence("faq-1")]))


def test_provider_failure_and_timeout_are_translated() -> None:
    failing = FakeProvider()
    failing.error = RuntimeError("secret provider payload")
    service = GenerationService(failing, provider_name="fake", model_name="fake")
    with pytest.raises(GenerationProviderError):
        asyncio.run(service.generate_draft("Question", [evidence("faq-1")]))

    class TimedOllamaClient:
        async def chat(self, **kwargs: object) -> object:
            raise httpx.ReadTimeout("provider timeout")

    ollama_provider = OllamaLLMProvider(
        "test-model",
        host="http://localhost:11434",
        timeout_seconds=1,
        client=TimedOllamaClient(),
    )
    with pytest.raises(GenerationTimeoutError):
        asyncio.run(ollama_provider.generate("private prompt"))

    class SlowProvider:
        async def generate(self, prompt: str) -> GenerationResult:
            await asyncio.sleep(1)
            return GenerationResult(text="", model="slow", latency_ms=0)

    timed = GenerationService(
        SlowProvider(), provider_name="fake", model_name="slow", timeout_seconds=0.01
    )
    with pytest.raises(GenerationTimeoutError):
        asyncio.run(timed.generate_draft("Question", [evidence("faq-1")]))


def test_duplicate_evidence_ids_and_blank_queries_are_rejected() -> None:
    service = GenerationService(FakeProvider(), provider_name="fake", model_name="fake")

    with pytest.raises(GenerationResponseError):
        asyncio.run(service.generate_draft("Question", [evidence("faq-1"), evidence("faq-1")]))
    with pytest.raises(GenerationResponseError):
        asyncio.run(service.generate_draft(" ", []))


def test_ollama_adapter_is_injectable_and_returns_metadata() -> None:
    class FakeOllamaClient:
        def __init__(self) -> None:
            self.request: dict[str, object] = {}

        async def chat(self, **kwargs: object) -> object:
            self.request = kwargs
            return SimpleNamespace(
                model="configured-model",
                message=SimpleNamespace(content='{"answer":"ok","cited_faq_ids":[]}'),
                prompt_eval_count=7,
                eval_count=3,
            )

    client = FakeOllamaClient()
    provider = OllamaLLMProvider(
        "configured-model", host="http://localhost:11434", timeout_seconds=2, client=client
    )

    result = asyncio.run(provider.generate("private prompt"))

    assert result.model == "configured-model"
    assert result.usage == TokenUsage(input_tokens=7, output_tokens=3)
    assert client.request["format"] == "json"
    assert client.request["options"] == {"temperature": 0}


def test_unconfigured_and_unsupported_providers_do_not_fallback() -> None:
    with pytest.raises(GenerationConfigurationError):
        create_llm_provider(Settings(_env_file=None))
    with pytest.raises(GenerationConfigurationError):
        create_llm_provider(Settings(_env_file=None, llm_provider="openai", llm_model="configured"))


def test_retrieval_generation_flow_uses_reranked_candidates_only() -> None:
    class FakeRerankedRetriever:
        def __init__(self) -> None:
            self.requested_top_k = 0

        def search(self, query: str, *, top_k: int | None = None) -> Sequence[RetrievalCandidate]:
            self.requested_top_k = top_k or 0
            return [
                RetrievalCandidate(
                    document_id="faq-1", score=1.1, rank=1, retrieval_stage="reranked"
                ),
                RetrievalCandidate(
                    document_id="faq-2", score=0.9, rank=2, retrieval_stage="reranked"
                ),
                RetrievalCandidate(
                    document_id="faq-3", score=0.8, rank=3, retrieval_stage="reranked"
                ),
            ][:top_k]

    documents = {
        faq_id: RetrievalDocument(
            faq_id=faq_id,
            question=question,
            answer=answer,
            metadata={"source": f"kb://{faq_id}", "category": "account"},
        )
        for faq_id, question, answer in [
            ("faq-1", "How do I reset my password?", "Use Forgot password on sign-in."),
            ("faq-2", "How do I change my email?", "Edit email in account settings."),
            ("faq-3", "How do I update my profile?", "Open profile settings."),
        ]
    }
    provider = FakeProvider(
        '{"answer":"Choose Forgot password on the sign-in page.","cited_faq_ids":["faq-1"]}'
    )
    generation = GenerationService(
        provider, provider_name="fake", model_name="fake-model", evidence_top_k=2
    )
    retriever = FakeRerankedRetriever()
    pipeline = RetrievalGenerationService(retriever, generation, documents, final_top_k=3)

    draft = asyncio.run(pipeline.draft_answer("How do I reset my password?"))

    assert retriever.requested_top_k == 3
    assert len(draft.provided_evidence) == 2
    assert [item.faq_id for item in draft.provided_evidence] == ["faq-1", "faq-2"]
    assert draft.citations[0].faq_id == "faq-1"
    assert draft.citations[0].source == "kb://faq-1"
    assert "faq-3" not in provider.prompts[0]
