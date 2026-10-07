import asyncio
import sys
from pathlib import Path

# Ensure src directory is in sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


from support_assistant.core.config import Settings
from support_assistant.generation.providers import HuggingFaceLLMProvider
from support_assistant.retrieval.hf_embeddings import HuggingFaceEmbeddingProvider


async def test_huggingface() -> None:
    settings = Settings()

    if not settings.hf_api_key:
        print("ERROR: SUPPORT_ASSISTANT_HF_API_KEY is not configured.")
        sys.exit(1)

    print("Checking Hugging Face Embeddings...")
    print(f"Model: {settings.embedding_model}")
    embedder = HuggingFaceEmbeddingProvider(
        model_name=settings.embedding_model,
        api_key=settings.hf_api_key,
    )

    query_vec = embedder.embed_query("How do I reset my password?")
    dimension = len(query_vec)
    print(f"Embedding generated successfully! Vector dimension: {dimension}")

    if dimension != 384:
        print(f"ERROR: Expected dimension 384, got {dimension}")
        sys.exit(1)

    print("\nChecking Hugging Face Qwen3-8B Generation...")
    print(f"Model: {settings.llm_model}")
    llm = HuggingFaceLLMProvider(
        model_name=settings.llm_model,
        api_key=settings.hf_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    prompt = (
        "You are a customer support assistant. Response MUST be JSON with fields 'answer' and 'cited_faq_ids'.\n"
        "Customer Question: How do I change my email?\n"
        "Available FAQ Evidence:\n"
        "FAQ ID: faq-123\n"
        "Question: How do I update my profile email address?\n"
        "Answer: Go to Account Settings > Security and enter your new email address."
    )

    result = await llm.generate(prompt)
    print("Generation successful!")
    print(f"Model used: {result.model}")
    print(f"Latency: {result.latency_ms:.2f} ms")
    print(f"Response text:\n{result.text}")


def main() -> None:
    asyncio.run(test_huggingface())


if __name__ == "__main__":
    main()
