import sys
from pathlib import Path

# Ensure src directory is in sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient

from support_assistant.core.config import Settings
from support_assistant.retrieval.azure_search import AzureAISearchRetriever
from support_assistant.retrieval.hf_embeddings import HuggingFaceEmbeddingProvider


def test_azure_search() -> None:
    settings = Settings()

    if not settings.azure_search_endpoint:
        print("ERROR: SUPPORT_ASSISTANT_AZURE_SEARCH_ENDPOINT is not set.")
        sys.exit(1)

    if not settings.azure_search_api_key:
        print("ERROR: SUPPORT_ASSISTANT_AZURE_SEARCH_API_KEY is not set.")
        sys.exit(1)

    if not settings.hf_api_key:
        print("ERROR: SUPPORT_ASSISTANT_HF_API_KEY is not set.")
        sys.exit(1)

    print("Verifying Azure AI Search credentials and index...")
    print(f"Endpoint: {settings.azure_search_endpoint}")
    print(f"Index: {settings.azure_search_index}")

    try:
        index_client = SearchIndexClient(
            endpoint=settings.azure_search_endpoint,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )
        index_info = index_client.get_index(settings.azure_search_index)
        print(f"Index '{index_info.name}' exists and is reachable.")
    except Exception as err:
        print(f"ERROR connecting to Azure Search index: {err}")
        sys.exit(1)

    print("\nExecuting hybrid search test query...")
    embedder = HuggingFaceEmbeddingProvider(
        model_name=settings.embedding_model,
        api_key=settings.hf_api_key,
    )
    retriever = AzureAISearchRetriever(
        endpoint=settings.azure_search_endpoint,
        api_key=settings.azure_search_api_key,
        index_name=settings.azure_search_index,
        embedding_provider=embedder,
    )

    results = retriever.search("How do I request a refund?", top_k=5)
    print(f"Retrieved {len(results)} candidate(s):")
    for cand in results:
        print(f"  - Rank {cand.rank} | Doc ID: {cand.document_id} | Score: {cand.score:.4f}")
        print(f"    Question: {cand.metadata.get('question')}")
        print(f"    Answer: {cand.metadata.get('answer')[:100]}...")


if __name__ == "__main__":
    test_azure_search()
