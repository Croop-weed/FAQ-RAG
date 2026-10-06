from dataclasses import dataclass
from typing import Protocol


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
