from typing import cast

from fastapi import Request

from support_assistant.core.config import Settings
from support_assistant.generation.providers import LLMProvider


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_llm_provider(request: Request) -> LLMProvider | None:
    return cast(LLMProvider | None, request.app.state.llm_provider)
