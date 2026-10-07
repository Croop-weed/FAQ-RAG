import asyncio
import sys
from pathlib import Path

# Ensure src directory is in sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


from support_assistant.core.config import Settings
from support_assistant.generation.providers import HuggingFaceLLMProvider
from support_assistant.generation.service import GenerationService
from support_assistant.retrieval.azure_search import AzureAISearchRetriever
from support_assistant.retrieval.hf_embeddings import HuggingFaceEmbeddingProvider
from support_assistant.services.confidence_service import create_confidence_service
from support_assistant.services.draft_service import Phase7DraftService


async def test_end_to_end() -> None:
    settings = Settings()

    if not settings.azure_search_endpoint or not settings.azure_search_api_key:
        print("ERROR: Azure Search endpoint and key must be configured in environment.")
        sys.exit(1)

    if not settings.hf_api_key:
        print("ERROR: Hugging Face API key must be configured in environment.")
        sys.exit(1)

    question = "How do I request a refund for my subscription?"
    print(f"QUESTION:\n{question}\n")

    # 1. Hugging Face Embeddings
    embedder = HuggingFaceEmbeddingProvider(
        model_name=settings.embedding_model,
        api_key=settings.hf_api_key,
    )

    # 2. Azure AI Search Retriever
    retriever = AzureAISearchRetriever(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index,
        embedding_provider=embedder,
    )

    # 3. Hugging Face LLM Provider
    llm_provider = HuggingFaceLLMProvider(
        model_name=settings.llm_model,
        api_key=settings.hf_api_key,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    generation_service = GenerationService(
        provider=llm_provider,
        provider_name="huggingface",
        model_name=settings.llm_model,
        evidence_top_k=settings.generation_evidence_top_k,
        timeout_seconds=settings.llm_timeout_seconds,
    )

    confidence_service = create_confidence_service(settings)

    draft_service = Phase7DraftService(
        retriever=retriever,
        generation_service=generation_service,
        confidence_service=confidence_service,
        documents={},
        final_top_k=settings.rerank_top_k,
    )

    result = await draft_service.process_query(question)

    print("RETRIEVED FAQS:")
    if result.grounded_draft and result.grounded_draft.provided_evidence:
        for idx, item in enumerate(result.grounded_draft.provided_evidence, start=1):
            print(f"{idx}. [{item.faq_id}] {item.question}")
            print(f"   Score: {item.retrieval_score:.4f} | Answer: {item.answer[:120]}...")
    else:
        print("None")

    print("\nDRAFT:")
    print(result.answer or "(No draft produced - abstained)")

    print("\nCONFIDENCE:")
    print(f"{result.confidence:.4f}")

    print("\nDECISION:")
    print(result.decision.value if hasattr(result.decision, "value") else str(result.decision))


def main() -> None:
    asyncio.run(test_end_to_end())


if __name__ == "__main__":
    main()
