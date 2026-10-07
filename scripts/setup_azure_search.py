import sys
from pathlib import Path

# Ensure src directory is in sys.path for direct script execution
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from support_assistant.core.config import Settings


from azure.core.credentials import AzureKeyCredential
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    HnswAlgorithmConfiguration,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SearchableField,
    SimpleField,
    VectorSearch,
    VectorSearchProfile,
)


def main() -> None:
    settings = Settings()

    if not settings.azure_search_endpoint:
        print("Error: SUPPORT_ASSISTANT_AZURE_SEARCH_ENDPOINT is not set in environment.")
        return

    if not settings.azure_search_api_key:
        print("Error: SUPPORT_ASSISTANT_AZURE_SEARCH_API_KEY is not set in environment.")
        return

    credential = AzureKeyCredential(settings.azure_search_api_key)

    index_client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=credential,
    )


    fields = [
        SimpleField(
            name="id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),

        SearchableField(
            name="question",
            type=SearchFieldDataType.String,
        ),

        SearchableField(
            name="answer",
            type=SearchFieldDataType.String,
        ),

        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
        ),

        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(
                SearchFieldDataType.Single
            ),
            searchable=True,
            vector_search_dimensions=384,
            vector_search_profile_name="faq-vector-profile",
        ),

        SearchableField(
            name="category",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        SearchableField(
            name="product",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        SearchableField(
            name="version",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        SearchableField(
            name="region",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        SearchableField(
            name="source",
            type=SearchFieldDataType.String,
        ),

        SearchField(
            name="tags",
            type=SearchFieldDataType.Collection(
                SearchFieldDataType.String
            ),
            searchable=True,
            filterable=True,
        ),
    ]

    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="faq-hnsw"
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="faq-vector-profile",
                algorithm_configuration_name="faq-hnsw",
            )
        ],
    )

    index = SearchIndex(
        name=settings.azure_search_index,
        fields=fields,
        vector_search=vector_search,
    )

    result = index_client.create_or_update_index(index)

    print(
        f"Azure AI Search index ready: {result.name}"
    )


if __name__ == "__main__":
    main()