from collections.abc import Mapping, Sequence
from time import perf_counter
from typing import Protocol

import numpy as np
import structlog

from support_assistant.retrieval.exceptions import InvalidRetrievalRequest, RerankingError
from support_assistant.retrieval.pipeline import HybridRetriever
from support_assistant.schemas.retrieval import (
    RetrievalCandidate,
    RetrievalDocument,
    RetrievalExecution,
)

logger = structlog.get_logger(__name__)


class CrossEncoderModel(Protocol):
    def predict(self, sentences: Sequence[tuple[str, str]]) -> Sequence[float]: ...


class Reranker(Protocol):
    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        documents: Mapping[str, RetrievalDocument],
        *,
        top_k: int,
    ) -> Sequence[RetrievalCandidate]: ...


class CrossEncoderReranker:
    """Explicitly loaded query/FAQ pair scorer; scores are ranking values, not probabilities."""

    def __init__(self, model_name: str, *, model: CrossEncoderModel | None = None) -> None:
        self.model_name = model_name
        if model is None:
            try:
                from sentence_transformers import CrossEncoder

                model = CrossEncoder(model_name)
            except Exception as error:
                raise RerankingError(
                    f"Could not load reranker model '{model_name}'. Check model access and cache."
                ) from error
        self._model = model
        logger.info("reranker_model_loaded", model_name=model_name)

    def rerank(
        self,
        query: str,
        candidates: Sequence[RetrievalCandidate],
        documents: Mapping[str, RetrievalDocument],
        *,
        top_k: int,
    ) -> list[RetrievalCandidate]:
        if top_k < 1:
            raise InvalidRetrievalRequest("Reranker top_k must be at least 1.")
        if not candidates:
            return []
        pairs = []
        for candidate in candidates:
            document = documents.get(candidate.faq_id)
            if document is None:
                raise RerankingError(
                    f"Candidate FAQ '{candidate.faq_id}' is missing from the document map."
                )
            pairs.append((query, document.content))
        try:
            scores = np.asarray(self._model.predict(pairs), dtype=np.float64).reshape(-1)
        except Exception as error:
            raise RerankingError("Cross-encoder inference failed.") from error
        if len(scores) != len(candidates) or not np.isfinite(scores).all():
            raise RerankingError("Cross-encoder returned invalid candidate scores.")
        ordered = sorted(
            zip(candidates, scores.tolist(), strict=True),
            key=lambda item: (-item[1], item[0].faq_id),
        )[:top_k]
        return [
            RetrievalCandidate(
                document_id=candidate.faq_id,
                score=score,
                rank=rank,
                retrieval_stage="reranked",
                metadata={
                    **candidate.metadata,
                    "rrf_score": candidate.score,
                    "reranker_score": score,
                },
            )
            for rank, (candidate, score) in enumerate(ordered, start=1)
        ]


class CrossEncoderRerankingRetriever:
    """Run a bounded hybrid candidate pool through one reused reranker instance."""

    name = "hybrid_rrf_reranker"

    def __init__(
        self,
        hybrid_retriever: HybridRetriever,
        reranker: Reranker,
        documents: Mapping[str, RetrievalDocument],
        *,
        rerank_top_k: int = 5,
    ) -> None:
        if rerank_top_k < 1:
            raise InvalidRetrievalRequest("Reranker top_k must be at least 1.")
        self.hybrid_retriever = hybrid_retriever
        self.reranker = reranker
        self.documents = documents
        self.rerank_top_k = rerank_top_k

    def search(self, query: str, *, top_k: int | None = None) -> list[RetrievalCandidate]:
        return self.search_detailed(query, top_k=top_k).candidates

    def search_detailed(self, query: str, *, top_k: int | None = None) -> RetrievalExecution:
        output_top_k = top_k if top_k is not None else self.rerank_top_k
        pool = self.hybrid_retriever.search(
            query,
            top_k=self.hybrid_retriever.fusion_top_k,
        )
        start = perf_counter()
        results = list(
            self.reranker.rerank(
                query,
                pool,
                self.documents,
                top_k=min(output_top_k, self.rerank_top_k),
            )
        )
        rerank_latency_ms = (perf_counter() - start) * 1000.0
        logger.info(
            "reranking_completed",
            candidate_pool_size=len(pool),
            returned_count=len(results),
        )
        return RetrievalExecution(
            candidates=results,
            stage_latency_ms={"reranker": rerank_latency_ms},
        )
