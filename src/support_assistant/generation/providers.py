from dataclasses import dataclass
from time import perf_counter
from typing import Protocol, cast

import httpx

from support_assistant.core.config import Settings
from support_assistant.core.exceptions import (
    GenerationConfigurationError,
    GenerationProviderError,
    GenerationTimeoutError,
)


class OllamaChatClient(Protocol):
    async def chat(self, **kwargs: object) -> object: ...


@dataclass(frozen=True, slots=True)
class TokenUsage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(frozen=True, slots=True)
class GenerationResult:
    text: str
    model: str
    latency_ms: float
    usage: TokenUsage | None = None


class LLMProvider(Protocol):
    async def generate(self, prompt: str) -> GenerationResult: ...


class OllamaLLMProvider:
    """Ollama adapter; the client/model are constructed once and reused."""

    name = "ollama"

    def __init__(
        self,
        model_name: str,
        *,
        host: str,
        timeout_seconds: float,
        client: OllamaChatClient | None = None,
    ) -> None:
        if model_name == "not-configured":
            raise GenerationConfigurationError("Configure SUPPORT_ASSISTANT_LLM_MODEL.")
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds
        try:
            if client is None:
                from ollama import AsyncClient

                client = cast(
                    OllamaChatClient,
                    AsyncClient(host=host, timeout=timeout_seconds),
                )
        except Exception as error:
            raise GenerationConfigurationError(
                "The configured Ollama client could not be initialized."
            ) from error
        self._client = client

    async def generate(self, prompt: str) -> GenerationResult:
        started = perf_counter()
        try:
            response = await self._client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": prompt}],
                format="json",
                options={"temperature": 0},
            )
        except (TimeoutError, httpx.TimeoutException) as error:
            raise GenerationTimeoutError() from error
        except Exception as error:
            raise GenerationProviderError() from error

        message = getattr(response, "message", None)
        text = getattr(message, "content", None)
        if not isinstance(text, str):
            raise GenerationProviderError()
        usage = TokenUsage(
            input_tokens=_optional_int(getattr(response, "prompt_eval_count", None)),
            output_tokens=_optional_int(getattr(response, "eval_count", None)),
        )
        return GenerationResult(
            text=text,
            model=str(getattr(response, "model", self.model_name)),
            latency_ms=(perf_counter() - started) * 1000.0,
            usage=usage
            if usage.input_tokens is not None or usage.output_tokens is not None
            else None,
        )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Create the configured provider explicitly; never silently switch vendors."""
    if settings.llm_provider == "ollama":
        return OllamaLLMProvider(
            settings.llm_model,
            host=settings.ollama_host,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    if settings.llm_provider == "not-configured":
        raise GenerationConfigurationError(
            "Configure SUPPORT_ASSISTANT_LLM_PROVIDER and SUPPORT_ASSISTANT_LLM_MODEL."
        )
    raise GenerationConfigurationError(
        f"Unsupported configured LLM provider '{settings.llm_provider}'."
    )
