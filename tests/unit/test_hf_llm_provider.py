from unittest.mock import AsyncMock, MagicMock

import pytest

from support_assistant.core.exceptions import (
    GenerationConfigurationError,
    GenerationProviderError,
)
from support_assistant.generation.providers import HuggingFaceLLMProvider


def test_hf_llm_provider_init_validation() -> None:
    with pytest.raises(GenerationConfigurationError, match="SUPPORT_ASSISTANT_HF_API_KEY is not configured"):
        HuggingFaceLLMProvider(model_name="Qwen/Qwen3-8B", api_key="")

    with pytest.raises(GenerationConfigurationError, match="Configure SUPPORT_ASSISTANT_LLM_MODEL"):
        HuggingFaceLLMProvider(model_name="", api_key="hf_token")


@pytest.mark.anyio
async def test_hf_llm_provider_generate_success() -> None:
    mock_client = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = '```json\n{"answer": "Follow instructions.", "cited_faq_ids": ["faq-1"]}\n```'

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    mock_response.usage = MagicMock()
    mock_response.usage.prompt_tokens = 42
    mock_response.usage.completion_tokens = 18

    mock_client.chat_completion = AsyncMock(return_value=mock_response)

    provider = HuggingFaceLLMProvider(
        model_name="Qwen/Qwen3-8B",
        api_key="hf_dummy_token",
        client=mock_client,
    )

    result = await provider.generate("Test prompt")
    assert result.text == '{"answer": "Follow instructions.", "cited_faq_ids": ["faq-1"]}'
    assert result.model == "Qwen/Qwen3-8B"
    assert result.usage is not None
    assert result.usage.input_tokens == 42
    assert result.usage.output_tokens == 18


@pytest.mark.anyio
async def test_hf_llm_provider_generate_error_handling() -> None:
    mock_client = MagicMock()
    mock_client.chat_completion = AsyncMock(side_effect=RuntimeError("API error"))

    provider = HuggingFaceLLMProvider(
        model_name="Qwen/Qwen3-8B",
        api_key="hf_dummy_token",
        client=mock_client,
    )

    with pytest.raises(GenerationProviderError, match="configured language model provider is unavailable"):
        await provider.generate("Test prompt")

