from typing import Annotated

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from support_assistant.api.dependencies import get_draft_service
from support_assistant.schemas.confidence import EvaluatedGroundedDraft
from support_assistant.services.draft_service import Phase7DraftService


class DraftRequest(BaseModel):
    query: str = Field(min_length=1, max_length=2000, description="Customer inquiry or question.")


router = APIRouter(prefix="", tags=["Drafts"])


@router.post("/draft", response_model=EvaluatedGroundedDraft, status_code=status.HTTP_200_OK)
@router.post("/drafts", response_model=EvaluatedGroundedDraft, status_code=status.HTTP_200_OK)
async def create_draft(
    request: DraftRequest,
    draft_service: Annotated[Phase7DraftService, Depends(get_draft_service)],
) -> EvaluatedGroundedDraft:
    return await draft_service.process_query(request.query)
