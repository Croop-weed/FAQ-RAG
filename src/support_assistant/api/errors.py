from typing import cast

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.types import ExceptionHandler

from support_assistant.core.exceptions import AppException
from support_assistant.schemas.errors import ErrorDetail, ErrorResponse

logger = structlog.get_logger(__name__)


def _request_id() -> str:
    return structlog.contextvars.get_contextvars().get("request_id", "unknown")


def _error_response(*, status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorDetail(code=code, message=message, request_id=request_id))
    return JSONResponse(status_code=status_code, content=body.model_dump())


async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        request_id=_request_id(),
    )


async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return _error_response(
        status_code=exc.status_code,
        code=f"http_{exc.status_code}",
        message="The requested resource could not be found."
        if exc.status_code == 404
        else "The request could not be completed.",
        request_id=_request_id(),
    )


async def handle_validation_exception(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return _error_response(
        status_code=422,
        code="validation_error",
        message="The request is invalid.",
        request_id=_request_id(),
    )


async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "Unhandled API exception",
        exc_info=(type(exc), exc, exc.__traceback__),
        method=request.method,
        path=request.url.path,
    )
    return _error_response(
        status_code=500,
        code="internal_error",
        message="An unexpected error occurred.",
        request_id=_request_id(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppException, cast(ExceptionHandler, handle_app_exception))
    app.add_exception_handler(StarletteHTTPException, cast(ExceptionHandler, handle_http_exception))
    app.add_exception_handler(
        RequestValidationError, cast(ExceptionHandler, handle_validation_exception)
    )
    app.add_exception_handler(Exception, handle_unexpected_exception)
