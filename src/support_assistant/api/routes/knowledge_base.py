from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict, Field

from support_assistant.api.dependencies import get_knowledge_base_service
from support_assistant.schemas.faq import (
    FAQCreate,
    FAQIngestionResult,
    FAQListResponse,
    FAQRead,
    FAQStatus,
    FAQUpdate,
)
from support_assistant.services.knowledge_base_service import KnowledgeBaseService

router = APIRouter(prefix="/knowledge-base", tags=["knowledge-base"])


class FAQBulkRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    records: list[dict[str, Any]] = Field(min_length=1, max_length=1000)


@router.post("/faqs", response_model=FAQRead, status_code=status.HTTP_201_CREATED)
async def create_faq(
    faq: FAQCreate,
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> FAQRead:
    return await service.create_faq(faq)


@router.post("/faqs/bulk", response_model=FAQIngestionResult)
async def ingest_faqs(
    body: FAQBulkRequest,
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> FAQIngestionResult:
    return await service.ingest_records(
        list(enumerate(body.records, start=1)), total_records=len(body.records)
    )


@router.get("/faqs", response_model=FAQListResponse)
async def list_faqs(
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
    status_filter: Annotated[FAQStatus | None, Query(alias="status")] = None,
    category: str | None = None,
    product: str | None = None,
    version: str | None = None,
) -> FAQListResponse:
    return await service.list_faqs(
        offset=offset,
        limit=limit,
        status=status_filter,
        category=category,
        product=product,
        version=version,
    )


@router.get("/faqs/{faq_id}", response_model=FAQRead)
async def get_faq(
    faq_id: str,
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> FAQRead:
    return await service.get_faq(faq_id)


@router.patch("/faqs/{faq_id}", response_model=FAQRead)
async def update_faq(
    faq_id: str,
    changes: FAQUpdate,
    service: Annotated[KnowledgeBaseService, Depends(get_knowledge_base_service)],
) -> FAQRead:
    return await service.update_faq(faq_id, changes)
