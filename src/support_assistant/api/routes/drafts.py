import json
import re
from collections.abc import Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, ConfigDict, Field

from support_assistant.api.dependencies import get_knowledge_base_service, get_settings
from support_assistant.core.config import Settings
from support_assistant.generation.providers import GenerationResult, LLMProvider
from support_assistant.generation.service import GenerationService
from support_assistant.retrieval.bm25_search import BM25Retriever
from support_assistant.retrieval.documents import build_retrieval_documents
from support_assistant.schemas.confidence import EvaluatedGroundedDraft
from support_assistant.schemas.faq import FAQStatus
from support_assistant.schemas.retrieval import RetrievalCandidate
from support_assistant.services.confidence_service import create_confidence_service
from support_assistant.services.draft_service import Phase7DraftService
from support_assistant.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(prefix="/drafts", tags=["drafts"])


class DraftQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)


class BM25RetrieverAdapter:
    def __init__(self, bm25: BM25Retriever) -> None:
        self.bm25 = bm25

    def search(self, query: str, *, top_k: int | None = None) -> Sequence[RetrievalCandidate]:
        return self.bm25.search(query, top_k=top_k if top_k is not None else 5)


class DemonstrationLLMProvider(LLMProvider):
    """Fallback LLM provider for demonstration when no external LLM vendor is configured."""

    name = "demo-grounded-provider"

    async def generate(self, prompt: str, **kwargs: Any) -> GenerationResult:
        evidence_match = re.search(
            r"AVAILABLE FAQ EVIDENCE:\n(\[.*?\])\n\nCUSTOMER QUESTION:", prompt, re.DOTALL
        )
        if evidence_match:
            try:
                items = json.loads(evidence_match.group(1))
                if items:
                    top_faq = items[0]
                    faq_id = top_faq.get("faq_id")
                    answer = top_faq.get("answer", "")

                    formatted_text = json.dumps(
                        {
                            "answer": f"Based on support documentation: {answer}",
                            "cited_faq_ids": [faq_id] if faq_id else [],
                        }
                    )
                    return GenerationResult(
                        text=formatted_text, model="demo-grounded-v1", latency_ms=12.5
                    )
            except Exception:
                pass

        refusal_json = json.dumps(
            {
                "answer": "I don't have enough verified information to answer this question.",
                "cited_faq_ids": [],
            }
        )
        return GenerationResult(text=refusal_json, model="demo-grounded-v1", latency_ms=5.0)


@router.post("/process", response_model=EvaluatedGroundedDraft, status_code=status.HTTP_200_OK)
async def process_customer_draft(
    request: DraftQueryRequest,
    kb_service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> EvaluatedGroundedDraft:
    faq_response = await kb_service.list_faqs(status=FAQStatus.ACTIVE, limit=500)
    documents = build_retrieval_documents(faq_response.items)
    doc_map = {doc.faq_id: doc for doc in documents}

    bm25 = BM25Retriever(documents)
    retriever = BM25RetrieverAdapter(bm25)

    if settings.llm_provider != "not-configured":
        try:
            from support_assistant.generation.providers import create_llm_provider

            llm_provider = create_llm_provider(settings)
        except Exception:
            llm_provider = DemonstrationLLMProvider()
    else:
        llm_provider = DemonstrationLLMProvider()

    gen_service = GenerationService(
        llm_provider,
        provider_name=getattr(llm_provider, "name", settings.llm_provider),
        model_name=(
            settings.llm_model if settings.llm_provider != "not-configured" else "demo-grounded-v1"
        ),
        evidence_top_k=settings.generation_evidence_top_k,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    conf_service = create_confidence_service(settings)

    pipeline = Phase7DraftService(
        retriever=retriever,
        generation_service=gen_service,
        confidence_service=conf_service,
        documents=doc_map,
        final_top_k=settings.rerank_top_k,
    )

    return await pipeline.process_query(request.query)
