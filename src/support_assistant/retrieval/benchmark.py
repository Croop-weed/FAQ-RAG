from collections.abc import Mapping
from pathlib import Path

import structlog

from support_assistant.db.repositories.faq_repository import FAQRepository
from support_assistant.retrieval.documents import build_retrieval_documents
from support_assistant.retrieval.evaluator import SearchRetriever, evaluate_retriever
from support_assistant.schemas.evaluation import EvaluationDataset, EvaluationResult
from support_assistant.schemas.faq import FAQStatus
from support_assistant.schemas.retrieval import RetrievalDocument

logger = structlog.get_logger(__name__)


async def load_active_corpus(repository: FAQRepository) -> list[RetrievalDocument]:
    faqs = []
    offset = 0
    page_size = 500
    while True:
        page, total = await repository.list_faqs(
            offset=offset,
            limit=page_size,
            status=FAQStatus.ACTIVE,
        )
        faqs.extend(page)
        offset += len(page)
        if not page or offset >= total:
            break
    documents = build_retrieval_documents(faqs)
    logger.info("corpus_loaded", corpus_size=len(documents))
    return documents


def run_benchmark(
    retriever: SearchRetriever,
    dataset: EvaluationDataset,
    *,
    corpus_ids: set[str],
    top_k: int,
    configuration: Mapping[str, object],
    model_name: str | None = None,
    embedding_dimension: int | None = None,
    index_type: str | None = None,
    model_load_time_ms: float | None = None,
    embedding_build_time_ms: float | None = None,
    index_build_time_ms: float | None = None,
) -> EvaluationResult:
    return evaluate_retriever(
        retriever,
        dataset,
        corpus_ids=corpus_ids,
        top_k=top_k,
        hit_rate_at_k=min(5, top_k),
        configuration=configuration,
        model_name=model_name,
        embedding_dimension=embedding_dimension,
        index_type=index_type,
        model_load_time_ms=model_load_time_ms,
        embedding_build_time_ms=embedding_build_time_ms,
        index_build_time_ms=index_build_time_ms,
    )


def export_result(result: EvaluationResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(result.model_dump_json(indent=2) + "\n", encoding="utf-8")
