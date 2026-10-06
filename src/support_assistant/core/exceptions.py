class AppException(Exception):
    """An application error that is safe to return to an API client."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "application_error",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class FAQNotFound(AppException):
    def __init__(self, faq_id: str) -> None:
        super().__init__(f"FAQ '{faq_id}' was not found.", code="faq_not_found", status_code=404)


class FAQAlreadyExists(AppException):
    def __init__(self) -> None:
        super().__init__(
            "An FAQ with the same question, product, and version already exists.",
            code="faq_duplicate",
            status_code=409,
        )


class FAQValidationError(AppException):
    def __init__(self) -> None:
        super().__init__("FAQ record is invalid.", code="faq_validation_error", status_code=422)


class GenerationError(AppException):
    def __init__(
        self,
        message: str,
        *,
        code: str = "generation_error",
        status_code: int = 502,
    ) -> None:
        super().__init__(message, code=code, status_code=status_code)


class GenerationConfigurationError(GenerationError):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="generation_not_configured", status_code=503)


class GenerationProviderError(GenerationError):
    def __init__(self) -> None:
        super().__init__(
            "The configured language model provider is unavailable.",
            code="generation_provider_error",
            status_code=503,
        )


class GenerationTimeoutError(GenerationError):
    def __init__(self) -> None:
        super().__init__(
            "The language model request timed out.",
            code="generation_timeout",
            status_code=504,
        )


class GenerationResponseError(GenerationError):
    def __init__(self, message: str = "The language model returned an invalid draft.") -> None:
        super().__init__(message, code="generation_response_error", status_code=502)
