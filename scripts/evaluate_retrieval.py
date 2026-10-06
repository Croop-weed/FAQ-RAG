import argparse
import asyncio
import re
from pathlib import Path
from time import perf_counter
from typing import Literal

import structlog

from support_assistant.core.config import Settings
from support_assistant.core.logging import configure_logging
from support_assistant.db.repositories.faq_repository import SqlAlchemyFAQRepository
from support_assistant.db.session import Database
from support_assistant.ingestion.evaluation import load_evaluation_dataset
from support_assistant.retrieval.benchmark import export_result, load_active_corpus, run_benchmark
from support_assistant.retrieval.bm25_search import BM25Retriever
from support_assistant.retrieval.embeddings import (
    DocumentEmbeddingCache,
    SentenceTransformerEmbeddingProvider,
)
from support_assistant.retrieval.exceptions import RetrievalError
from support_assistant.retrieval.fusion import ReciprocalRankFusion
from support_assistant.retrieval.pipeline import HybridRetriever
from support_assistant.retrieval.reranker import (
    CrossEncoderReranker,
    CrossEncoderRerankingRetriever,
)
from support_assistant.retrieval.vector_search import EmbeddingVectorRetriever
from support_assistant.schemas.evaluation import EvaluationResult


def _result_path(
    retriever: str, model_name: str | None, reranker_model_name: str | None = None
) -> Path:
    if retriever == "hybrid":
        return Path("data/evaluation/results/hybrid_rrf.json")
    if retriever == "hybrid-reranker":
        return Path("data/evaluation/results/hybrid_rrf_reranker.json")
    suffix = ""
    if model_name:
        suffix = "_" + re.sub(r"[^A-Za-z0-9._-]+", "_", model_name.split("/")[-1])
    return Path("data/evaluation/results") / f"{retriever}{suffix}.json"


def _print_result(result: EvaluationResult) -> None:
    metrics = result.metrics
    print("RETRIEVAL BENCHMARK")
    print("-------------------")
    print(f"Retriever: {result.retriever_name}")
    print(f"Dataset:   {result.dataset_name}")
    print(f"Corpus:    {result.corpus_size} active FAQs")
    print(f"Queries:   {result.num_queries} valid / {len(result.invalid_records)} invalid records")
    if result.model_name:
        print(f"Model:     {result.model_name}")
        print(f"Dimension: {result.embedding_dimension}")
        print(f"Index:     {result.index_type}")
        print(f"Model load: {result.model_load_time_ms:.2f} ms")
        print(f"Embeddings: {result.embedding_build_time_ms:.2f} ms")
        print(f"Index build: {result.index_build_time_ms:.2f} ms")
    if result.reranker_model_name:
        print(f"Reranker:  {result.reranker_model_name}")
        print(f"Reranker load: {result.reranker_model_load_time_ms:.2f} ms")
        latency = result.reranker_latency
        if latency:
            print(
                f"Reranker latency mean/p50/p95: {latency.mean_ms:.2f} / "
                f"{latency.p50_ms:.2f} / {latency.p95_ms:.2f} ms"
            )
    print(f"Recall@1:  {metrics.recall_at_1:.3f}")
    print(f"Recall@3:  {metrics.recall_at_3:.3f}")
    print(f"Recall@5:  {metrics.recall_at_5:.3f}")
    print(f"MRR:       {metrics.mrr:.3f}")
    print(f"HitRate@{metrics.hit_rate_at_k}: {metrics.hit_rate:.3f}")
    print(
        f"Latency mean/p50/p95: {metrics.mean_latency_ms:.2f} / "
        f"{metrics.p50_latency_ms:.2f} / {metrics.p95_latency_ms:.2f} ms"
    )
    print(f"Failed queries: {len(result.failures)}")


async def _run(
    *,
    dataset_path: Path,
    retriever_name: Literal["bm25", "vector", "hybrid", "hybrid-reranker"],
    output: Path,
    model_name: str,
    reranker_model_name: str,
    top_k: int,
) -> EvaluationResult:
    settings = Settings()
    configure_logging(settings)
    dataset = load_evaluation_dataset(dataset_path)
    database = Database(settings.database_url)
    try:
        async with database.session_factory() as session:
            documents = await load_active_corpus(SqlAlchemyFAQRepository(session))
    finally:
        await database.dispose()

    corpus_ids = {document.faq_id for document in documents}
    if retriever_name == "bm25":
        build_started = perf_counter()
        retriever = BM25Retriever(documents)
        build_time_ms = (perf_counter() - build_started) * 1000
        result = run_benchmark(
            retriever,
            dataset,
            corpus_ids=corpus_ids,
            top_k=top_k,
            configuration={"top_k": top_k, "algorithm": "BM25Plus"},
            index_type="rank_bm25.BM25Plus",
            index_build_time_ms=build_time_ms,
        )
    elif retriever_name == "vector":
        model_started = perf_counter()
        provider = SentenceTransformerEmbeddingProvider(model_name)
        model_load_time_ms = (perf_counter() - model_started) * 1000
        embedding_started = perf_counter()
        documents = sorted(documents, key=lambda document: document.faq_id)
        embeddings = DocumentEmbeddingCache(settings.embedding_cache_dir).get_or_create(
            provider,
            [(document.faq_id, document.content) for document in documents],
        )
        embedding_build_time_ms = (perf_counter() - embedding_started) * 1000
        index_started = perf_counter()
        retriever = EmbeddingVectorRetriever(
            documents,
            provider,
            document_embeddings=embeddings.tolist(),
        )
        index_build_time_ms = (perf_counter() - index_started) * 1000
        result = run_benchmark(
            retriever,
            dataset,
            corpus_ids=corpus_ids,
            top_k=top_k,
            configuration={
                "top_k": top_k,
                "similarity": "cosine",
                "cache_dir": str(settings.embedding_cache_dir),
            },
            model_name=provider.model_name,
            embedding_dimension=provider.dimension,
            index_type=retriever.index.index_type,
            model_load_time_ms=model_load_time_ms,
            embedding_build_time_ms=embedding_build_time_ms,
            index_build_time_ms=index_build_time_ms,
        )
    else:
        build_started = perf_counter()
        lexical_retriever = BM25Retriever(documents)
        build_time_ms = (perf_counter() - build_started) * 1000.0
        model_started = perf_counter()
        provider = SentenceTransformerEmbeddingProvider(model_name)
        model_load_time_ms = (perf_counter() - model_started) * 1000.0
        embeddings_started = perf_counter()
        documents = sorted(documents, key=lambda document: document.faq_id)
        embeddings = DocumentEmbeddingCache(settings.embedding_cache_dir).get_or_create(
            provider,
            [(document.faq_id, document.content) for document in documents],
        )
        embedding_build_time_ms = (perf_counter() - embeddings_started) * 1000.0
        index_started = perf_counter()
        vector_retriever = EmbeddingVectorRetriever(
            documents, provider, document_embeddings=embeddings.tolist()
        )
        index_build_time_ms = (perf_counter() - index_started) * 1000.0
        hybrid = HybridRetriever(
            lexical_retriever,
            vector_retriever,
            ReciprocalRankFusion(settings.rrf_k),
            bm25_top_k=settings.bm25_top_k,
            vector_top_k=settings.vector_top_k,
            fusion_top_k=settings.fusion_top_k,
        )
        hybrid_build_time_ms = build_time_ms + embedding_build_time_ms + index_build_time_ms
        reranker_model_load_time_ms = None
        if retriever_name == "hybrid-reranker":
            reranker_started = perf_counter()
            reranker = CrossEncoderReranker(reranker_model_name)
            reranker_model_load_time_ms = (perf_counter() - reranker_started) * 1000.0
            retriever = CrossEncoderRerankingRetriever(
                hybrid,
                reranker,
                {document.faq_id: document for document in documents},
                rerank_top_k=settings.rerank_top_k,
            )
        else:
            retriever = hybrid
        evaluation_top_k = settings.fusion_top_k if retriever_name == "hybrid" else top_k
        result = run_benchmark(
            retriever,
            dataset,
            corpus_ids=corpus_ids,
            top_k=evaluation_top_k,
            configuration={
                "bm25_top_k": settings.bm25_top_k,
                "vector_top_k": settings.vector_top_k,
                "fusion_top_k": settings.fusion_top_k,
                "rrf_k": settings.rrf_k,
                "output_top_k": top_k,
                "rerank_top_k": settings.rerank_top_k
                if retriever_name == "hybrid-reranker"
                else None,
            },
            model_name=provider.model_name,
            reranker_model_name=(
                reranker_model_name if retriever_name == "hybrid-reranker" else None
            ),
            embedding_dimension=provider.dimension,
            index_type=vector_retriever.index.index_type,
            model_load_time_ms=model_load_time_ms,
            reranker_model_load_time_ms=reranker_model_load_time_ms,
            embedding_build_time_ms=embedding_build_time_ms,
            index_build_time_ms=hybrid_build_time_ms,
        )
    export_result(result, output)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Run an independent FAQ retrieval baseline.")
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument(
        "--retriever",
        choices=("bm25", "vector", "hybrid", "hybrid-reranker"),
        required=True,
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", default=None, help="Embedding model (vector baseline only).")
    parser.add_argument("--reranker-model", default=None)
    parser.add_argument("--top-k", type=int, default=None)
    args = parser.parse_args()

    settings = Settings()
    top_k = args.top_k or settings.evaluation_top_k
    if top_k < 5:
        parser.error("--top-k must be at least 5 to report Recall@5")
    model_name = args.model or settings.embedding_model
    reranker_model_name = args.reranker_model or settings.reranker_model
    output = args.output or _result_path(
        args.retriever,
        model_name if args.retriever in {"vector", "hybrid", "hybrid-reranker"} else None,
        reranker_model_name if args.retriever == "hybrid-reranker" else None,
    )
    try:
        result = asyncio.run(
            _run(
                dataset_path=args.dataset,
                retriever_name=args.retriever,
                output=output,
                model_name=model_name,
                reranker_model_name=reranker_model_name,
                top_k=top_k,
            )
        )
    except Exception as error:
        if isinstance(error, RetrievalError):
            print(f"Benchmark could not run: {error}")
        else:
            structlog.get_logger(__name__).error(
                "retrieval_benchmark_failed", error_type=type(error).__name__
            )
            print("Benchmark failed; inspect structured logs and configuration.")
        return 1
    _print_result(result)
    print(f"JSON result: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
