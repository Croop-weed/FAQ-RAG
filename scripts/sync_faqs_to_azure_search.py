import asyncio
import sys
from pathlib import Path
from typing import Any

# Ensure src directory is in sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))


from azure.core.credentials import AzureKeyCredential
from azure.search.documents import SearchClient

from support_assistant.core.config import Settings
from support_assistant.db.repositories.faq_repository import SqlAlchemyFAQRepository
from support_assistant.db.session import Database
from support_assistant.retrieval.hf_embeddings import HuggingFaceEmbeddingProvider
from support_assistant.schemas.faq import FAQStatus


async def sync_faqs() -> None:
    settings = Settings()

    if not settings.azure_search_endpoint:
        print("Error: SUPPORT_ASSISTANT_AZURE_SEARCH_ENDPOINT is not configured.")
        sys.exit(1)

    if not settings.azure_search_api_key:
        print("Error: SUPPORT_ASSISTANT_AZURE_SEARCH_API_KEY is not configured.")
        sys.exit(1)

    if not settings.hf_api_key:
        print("Error: SUPPORT_ASSISTANT_HF_API_KEY is not configured.")
        sys.exit(1)

    print("Initializing Hugging Face embedding provider...")
    embedding_provider = HuggingFaceEmbeddingProvider(
        model_name=settings.embedding_model,
        api_key=settings.hf_api_key,
    )

    print("Connecting to database...")
    database = Database(settings.database_url)

    async for session in database.session():
        repository = SqlAlchemyFAQRepository(session)
        faqs, total = await repository.list_faqs(offset=0, limit=1000, status=FAQStatus.ACTIVE)
        print(f"Retrieved {len(faqs)} active FAQ(s) (total: {total}) from database.")


        if not faqs:
            print("No FAQs found in database to sync.")
            await database.dispose()
            return

        search_client = SearchClient(
            endpoint=settings.azure_search_endpoint,
            index_name=settings.azure_search_index,
            credential=AzureKeyCredential(settings.azure_search_api_key),
        )

        documents: list[dict[str, Any]] = []
        batch_size = 100
        synced_count = 0

        for faq in faqs:
            combined_content = f"{faq.question}\n{faq.answer}"
            embedding = embedding_provider.embed_query(combined_content)

            doc: dict[str, Any] = {
                "id": str(faq.id),
                "question": faq.question,
                "answer": faq.answer,
                "content": combined_content,
                "content_vector": embedding.tolist() if hasattr(embedding, "tolist") else list(embedding),
                "category": faq.category or "",
                "product": faq.product or "",
                "version": faq.version or "",
                "region": faq.region or "",
                "source": faq.source or "",
                "tags": faq.tags or [],
            }
            documents.append(doc)

            if len(documents) >= batch_size:
                search_client.merge_or_upload_documents(documents=documents)
                synced_count += len(documents)
                print(f"Uploaded batch of {len(documents)} FAQs (Total: {synced_count})")
                documents = []

        if documents:
            search_client.merge_or_upload_documents(documents=documents)
            synced_count += len(documents)
            print(f"Uploaded final batch of {len(documents)} FAQs (Total: {synced_count})")

        print(f"Successfully synchronized {synced_count} FAQs to Azure AI Search index '{settings.azure_search_index}'.")

    await database.dispose()


def main() -> None:
    asyncio.run(sync_faqs())


if __name__ == "__main__":
    main()
