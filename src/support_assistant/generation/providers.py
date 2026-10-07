from dataclasses import dataclass
from time import perf_counter
from typing import Any, Protocol, cast


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


class HuggingFaceLLMProvider:
    """Hugging Face Inference API provider for Qwen/Qwen3-8B."""

    name = "huggingface"

    def __init__(
        self,
        model_name: str,
        *,
        api_key: str,
        timeout_seconds: float = 60.0,
        client: Any | None = None,
    ) -> None:
        if not api_key and client is None:
            raise GenerationConfigurationError("SUPPORT_ASSISTANT_HF_API_KEY is not configured.")
        if not model_name or model_name == "not-configured":
            raise GenerationConfigurationError("Configure SUPPORT_ASSISTANT_LLM_MODEL.")

        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

        if client is None:
            try:
                from huggingface_hub import AsyncInferenceClient

                self._client = AsyncInferenceClient(
                    api_key=api_key,
                    timeout=timeout_seconds,
                )
            except Exception as error:
                raise GenerationConfigurationError(
                    "Could not initialize Hugging Face AsyncInferenceClient."
                ) from error
        else:
            self._client = client

    async def generate(self, prompt: str) -> GenerationResult:
        started = perf_counter()
        try:
            # Try chat_completion with json response format if supported
            try:
                response = await self._client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model_name,
                    max_tokens=1024,
                    temperature=0.01,
                    response_format={"type": "json_object"},
                )
            except Exception:
                # Fallback to chat completion without json constraint
                response = await self._client.chat_completion(
                    messages=[{"role": "user", "content": prompt}],
                    model=self.model_name,
                    max_tokens=1024,
                    temperature=0.01,
                )
        except (TimeoutError, httpx.TimeoutException) as error:
            raise GenerationTimeoutError() from error
        except Exception as error:
            raise GenerationProviderError() from error


        text = None
        usage = None
        model_used = self.model_name

        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            if hasattr(choice, "message") and hasattr(choice.message, "content"):
                text = choice.message.content

        if text is None and isinstance(response, str):
            text = response

        if not isinstance(text, str):
            raise GenerationProviderError("Hugging Face provider returned unexpected payload.")

        # Clean markdown code fences if present (```json ... ```)
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        if hasattr(response, "usage") and response.usage:
            usage = TokenUsage(
                input_tokens=_optional_int(getattr(response.usage, "prompt_tokens", None)),
                output_tokens=_optional_int(getattr(response.usage, "completion_tokens", None)),
            )

        return GenerationResult(
            text=text,
            model=model_used,
            latency_ms=(perf_counter() - started) * 1000.0,
            usage=usage,
        )


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def create_llm_provider(settings: Settings) -> LLMProvider:
    """Create the configured provider explicitly; never silently switch vendors."""
    if settings.llm_provider == "huggingface":
        return HuggingFaceLLMProvider(
            settings.llm_model,
            api_key=settings.hf_api_key,
            timeout_seconds=settings.llm_timeout_seconds,
        )
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

