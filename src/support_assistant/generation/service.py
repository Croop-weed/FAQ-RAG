import asyncio
import json
from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Protocol

import structlog
from pydantic import ValidationError

from support_assistant.core.config import Settings
from support_assistant.core.exceptions import (
    GenerationError,
    GenerationProviderError,
    GenerationResponseError,
    GenerationTimeoutError,
)
from support_assistant.generation.prompts import PROMPT_VERSION, build_grounded_prompt
from support_assistant.generation.providers import LLMProvider, create_llm_provider
from support_assistant.schemas.draft import (
    DraftCitation,
    EvidenceItem,
    GeneratedDraftContent,
    GenerationMetadata,
    GroundedDraft,
)
from support_assistant.schemas.retrieval import RetrievalCandidate, RetrievalDocument

logger = structlog.get_logger(__name__)


def create_generation_service(settings: Settings) -> "GenerationService":
    provider = create_llm_provider(settings)
    return GenerationService(
        provider,
        provider_name=settings.llm_provider,
        model_name=settings.llm_model,
        evidence_top_k=settings.generation_evidence_top_k,
        timeout_seconds=settings.llm_timeout_seconds,
    )


class GenerationService:
    def __init__(
        self,
        provider: LLMProvider,
        *,
        provider_name: str,
        model_name: str,
        evidence_top_k: int = 5,
        timeout_seconds: float = 45.0,
    ) -> None:
        if evidence_top_k < 1 or timeout_seconds <= 0:
            raise ValueError("Evidence top-K and generation timeout must be positive.")
        self.provider = provider
        self.provider_name = provider_name
        self.model_name = model_name
        self.evidence_top_k = evidence_top_k
        self.timeout_seconds = timeout_seconds

    async def generate_draft(self, query: str, evidence: Sequence[EvidenceItem]) -> GroundedDraft:
        if not query.strip():
            raise GenerationResponseError("Customer question cannot be empty.")
        selected = list(evidence[: self.evidence_top_k])
        ids = [item.faq_id for item in selected]
        if len(ids) != len(set(ids)):
            raise GenerationResponseError("Evidence contains duplicate FAQ IDs.")
        prompt = build_grounded_prompt(query.strip(), selected)
        started = perf_counter()
        try:
            async with asyncio.timeout(self.timeout_seconds):
                provider_result = await self.provider.generate(prompt)
        except TimeoutError as error:
            logger.warning(
                "generation_failed",
                provider=self.provider_name,
                model=self.model_name,
                evidence_count=len(selected),
                reason="timeout",
            )
            raise GenerationTimeoutError() from error
        except GenerationError:
            logger.warning(
                "generation_failed",
                provider=self.provider_name,
                model=self.model_name,
                evidence_count=len(selected),
                reason="provider_error",
            )
            raise
        except Exception as error:
            logger.error(
                "generation_failed",
                provider=self.provider_name,
                model=self.model_name,
                evidence_count=len(selected),
                reason="provider_error",
                error_type=type(error).__name__,
            )
            raise GenerationProviderError() from error

        try:
            generated = GeneratedDraftContent.model_validate_json(provider_result.text)
        except (ValidationError, ValueError, json.JSONDecodeError) as error:
            logger.warning(
                "generation_failed",
                provider=self.provider_name,
                model=provider_result.model,
                evidence_count=len(selected),
                reason="invalid_structured_response",
            )
            raise GenerationResponseError() from error

        if not generated.answer.strip():
            raise GenerationResponseError("The language model returned an empty draft.")
        if len(generated.cited_faq_ids) != len(set(generated.cited_faq_ids)):
            raise GenerationResponseError("The language model returned duplicate FAQ citations.")
        by_id = {item.faq_id: item for item in selected}
        unknown = sorted(set(generated.cited_faq_ids) - by_id.keys())
        if unknown:
            logger.warning(
                "generation_failed",
                provider=self.provider_name,
                model=provider_result.model,
                evidence_count=len(selected),
                reason="unknown_citation_id",
            )
            raise GenerationResponseError(
                "The language model cited evidence that was not supplied."
            )

        citations = [
            DraftCitation(
                faq_id=faq_id,
                source=by_id[faq_id].source,
                question=by_id[faq_id].question,
            )
            for faq_id in generated.cited_faq_ids
        ]
        metadata = GenerationMetadata(
            provider=self.provider_name,
            model=provider_result.model or self.model_name,
            latency_ms=(perf_counter() - started) * 1000.0,
            input_tokens=(provider_result.usage.input_tokens if provider_result.usage else None),
            output_tokens=(provider_result.usage.output_tokens if provider_result.usage else None),
            evidence_count=len(selected),
            prompt_version=PROMPT_VERSION,
        )
        logger.info(
            "generation_completed",
            provider=self.provider_name,
            model=metadata.model,
            latency_ms=metadata.latency_ms,
            evidence_count=metadata.evidence_count,
            citation_count=len(citations),
        )
        return GroundedDraft(
            answer=generated.answer.strip(),
            citations=citations,
            evidence_ids=ids,
            provided_evidence=selected,
            metadata=metadata,
        )


class RetrievalGenerationService:
    """Small application orchestrator: reranked retrieval first, then grounded drafting."""

    def __init__(
        self,
        retriever: "RerankedRetriever",
        generation_service: GenerationService,
        documents: Mapping[str, RetrievalDocument],
        *,
        final_top_k: int = 5,
    ) -> None:
        if final_top_k < 1:
            raise ValueError("Final retrieval top-K must be positive.")
        self.retriever = retriever
        self.generation_service = generation_service
        self.documents = documents
        self.final_top_k = final_top_k

    async def draft_answer(self, query: str) -> GroundedDraft:
        candidates = self.retriever.search(query, top_k=self.final_top_k)
        evidence = []
        for candidate in candidates[: self.final_top_k]:
            document = self.documents.get(candidate.faq_id)
            if document is None:
                raise GenerationResponseError(
                    "A retrieved FAQ was not available for evidence construction."
                )
            metadata = document.metadata
            evidence.append(
                EvidenceItem(
                    faq_id=document.faq_id,
                    question=document.question,
                    answer=document.answer,
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
        return await self.generation_service.generate_draft(query, evidence)


def create_retrieval_generation_service(
    settings: Settings,
    retriever: "RerankedRetriever",
    documents: Mapping[str, RetrievalDocument],
) -> RetrievalGenerationService:
    return RetrievalGenerationService(
        retriever,
        create_generation_service(settings),
        documents,
        final_top_k=settings.rerank_top_k,
    )


class RerankedRetriever(Protocol):
    def search(self, query: str, *, top_k: int | None = None) -> Sequence[RetrievalCandidate]: ...
