from collections.abc import Sequence
from time import perf_counter
from typing import Any

from azure.core.credentials import AzureKeyCredential
from azure.core.exceptions import AzureError
from azure.search.documents import SearchClient
from azure.search.documents.models import VectorizedQuery

from support_assistant.retrieval.embeddings import EmbeddingProvider
from support_assistant.retrieval.exceptions import (
    InvalidRetrievalRequest,
    RetrievalError,
)
from support_assistant.schemas.retrieval import RetrievalCandidate


class AzureAISearchRetriever:
    """
    Hybrid Azure AI Search retriever.

    Performs:
        keyword search + vector search
        -> Azure AI Search RRF
    """

    name = "azure-ai-search"

    def __init__(
        self,
        endpoint: str,
        api_key: str,
        index_name: str,
        embedding_provider: EmbeddingProvider,
        *,
        client: SearchClient | None = None,
    ) -> None:
        if not endpoint and client is None:
            raise ValueError("Azure AI Search endpoint is not configured.")

        if not api_key and client is None:
            raise ValueError("Azure AI Search API key is not configured.")

        self.embedding_provider = embedding_provider

        if client is not None:
            self.client = client
        else:
            self.client = SearchClient(
                endpoint=endpoint,
                index_name=index_name,
                credential=AzureKeyCredential(api_key),
            )

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
    ) -> Sequence[RetrievalCandidate]:
        if not query.strip():
            raise InvalidRetrievalRequest("Retrieval query cannot be empty.")

        if top_k < 1:
            raise InvalidRetrievalRequest("top_k must be at least 1.")

        started = perf_counter()

        try:
            query_vector = self.embedding_provider.embed_query(query)
            if hasattr(query_vector, "tolist"):
                vector_list = query_vector.tolist()
            else:
                vector_list = list(query_vector)

            vector_query = VectorizedQuery(
                vector=vector_list,
                k_nearest_neighbors=top_k,
                fields="content_vector",
                kind="vector",
            )

            results = self.client.search(
                search_text=query,
                vector_queries=[vector_query],
                select=[
                    "id",
                    "question",
                    "answer",
                    "category",
                    "product",
                    "version",
                    "region",
                    "source",
                    "tags",
                ],
                top=top_k,
            )

            candidates: list[RetrievalCandidate] = []

            for rank, result in enumerate(results, start=1):
                raw_score = float(result.get("@search.score", 0.0))
                metadata: dict[str, Any] = {
                    "question": result.get("question"),
                    "answer": result.get("answer"),
                    "category": result.get("category"),
                    "product": result.get("product"),
                    "version": result.get("version"),
                    "region": result.get("region"),
                    "source": result.get("source"),
                    "tags": result.get("tags") or [],
                    "search_score": raw_score,
                    "reranker_score": result.get("@search.rerankerScore"),
                    "latency_ms": (perf_counter() - started) * 1000.0,
                }

                candidates.append(
                    RetrievalCandidate(
                        document_id=str(result["id"]),
                        score=raw_score,
                        rank=rank,
                        retrieval_stage="azure-ai-search-hybrid",
                        metadata=metadata,
                    )
                )

            return candidates
        except (InvalidRetrievalRequest, RetrievalError):
            raise
        except AzureError as error:
            raise RetrievalError(f"Azure AI Search query failed: {error}") from error
        except Exception as error:
            raise RetrievalError(f"Retrieval error during Azure Search: {error}") from error