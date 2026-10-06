from typing import Annotated

from fastapi import APIRouter, Depends

from support_assistant.api.dependencies import get_settings
from support_assistant.core.config import Settings
from support_assistant.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)
