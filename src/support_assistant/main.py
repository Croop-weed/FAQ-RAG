from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import structlog
from fastapi import FastAPI
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from support_assistant.api.errors import register_exception_handlers
from support_assistant.api.routes.drafts import router as drafts_router
from support_assistant.api.routes.health import router as health_router
from support_assistant.api.routes.knowledge_base import router as knowledge_base_router
from support_assistant.core.config import Settings
from support_assistant.core.logging import configure_logging
from support_assistant.db.session import Database
from support_assistant.generation.providers import LLMProvider


class RequestContextMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        supplied_id = next(
            (
                value.decode("latin-1")
                for name, value in scope.get("headers", [])
                if name.lower() == b"x-request-id"
            ),
            "",
        )
        try:
            request_id = str(UUID(supplied_id))
        except (ValueError, AttributeError):
            request_id = str(uuid4())

        context_tokens = structlog.contextvars.bind_contextvars(request_id=request_id)

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower() != b"x-request-id"
                ]
                headers.append((b"x-request-id", request_id.encode("ascii")))
                message["headers"] = headers
            await send(message)

        try:
            await self.app(scope, receive, send_with_request_id)
        finally:
            structlog.contextvars.reset_contextvars(**context_tokens)


def create_app(
    settings: Settings | None = None,
    *,
    llm_provider: LLMProvider | None = None,
) -> FastAPI:
    application_settings = settings or Settings()
    configure_logging(application_settings)
    database = Database(application_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            await database.dispose()

    app = FastAPI(
        title=application_settings.app_name,
        version="0.1.0",
        description="Customer support assistant API",
        lifespan=lifespan,
    )
    app.state.settings = application_settings
    app.state.llm_provider = llm_provider
    app.state.database = database
    app.add_middleware(RequestContextMiddleware)
    app.include_router(health_router)
    app.include_router(knowledge_base_router)
    app.include_router(drafts_router)
    register_exception_handlers(app)
    return app

