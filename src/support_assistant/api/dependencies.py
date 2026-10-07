from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Annotated, cast


if TYPE_CHECKING:
    from support_assistant.services.draft_service import Phase7DraftService


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


def get_draft_service(request: Request) -> "Phase7DraftService":
    if hasattr(request.app.state, "draft_service") and request.app.state.draft_service is not None:
        return cast("Phase7DraftService", request.app.state.draft_service)

    settings = get_settings(request)
    from support_assistant.retrieval.azure_search import AzureAISearchRetriever
    from support_assistant.retrieval.hf_embeddings import HuggingFaceEmbeddingProvider
    from support_assistant.services.draft_service import create_phase7_draft_service

    hf_embedder = HuggingFaceEmbeddingProvider(
        model_name=settings.embedding_model,
        api_key=settings.hf_api_key,
    )
    retriever = AzureAISearchRetriever(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index,
        embedding_provider=hf_embedder,
    )

    return create_phase7_draft_service(
        settings=settings,
        retriever=retriever,
        documents={},
    )

