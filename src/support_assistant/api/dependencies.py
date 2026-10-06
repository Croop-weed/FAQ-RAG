from collections.abc import AsyncIterator
from typing import Annotated, cast

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from support_assistant.core.config import Settings
from support_assistant.db.repositories.faq_repository import (
    FAQRepository,
    SqlAlchemyFAQRepository,
)
from support_assistant.db.session import Database
from support_assistant.generation.providers import LLMProvider
from support_assistant.services.knowledge_base_service import KnowledgeBaseService


def get_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_llm_provider(request: Request) -> LLMProvider | None:
    return cast(LLMProvider | None, request.app.state.llm_provider)


async def get_database_session(request: Request) -> AsyncIterator[AsyncSession]:
    database = cast(Database, request.app.state.database)
    async for session in database.session():
        yield session


def get_faq_repository(
    session: Annotated[AsyncSession, Depends(get_database_session)],
) -> FAQRepository:
    return SqlAlchemyFAQRepository(session)


def get_knowledge_base_service(
    repository: Annotated[FAQRepository, Depends(get_faq_repository)],
) -> KnowledgeBaseService:
    return KnowledgeBaseService(repository)
