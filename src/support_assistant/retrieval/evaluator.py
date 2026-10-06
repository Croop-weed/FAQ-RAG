from collections import Counter
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from time import perf_counter
from typing import Protocol

import structlog

from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.retrieval.metrics import compute_retrieval_metrics
from support_assistant.schemas.evaluation import (
	EvaluationDataset,
	EvaluationFailure,
	EvaluationRecordError,
	EvaluationResult,
)
from support_assistant.schemas.retrieval import RetrievalCandidate

logger = structlog.get_logger(__name__)


class SearchRetriever(Protocol):
	name: str

	def search(self, query: str, *, top_k: int) -> Sequence[RetrievalCandidate]: ...


def evaluate_retriever(
	retriever: SearchRetriever,
	dataset: EvaluationDataset,
	*,
	corpus_ids: set[str],
	top_k: int = 5,
	hit_rate_at_k: int = 5,
	configuration: Mapping[str, object] | None = None,
	model_name: str | None = None,
	embedding_dimension: int | None = None,
	index_type: str | None = None,
	model_load_time_ms: float | None = None,
	embedding_build_time_ms: float | None = None,
	index_build_time_ms: float | None = None,
) -> EvaluationResult:
	if not corpus_ids:
		raise InvalidRetrievalRequest("Cannot evaluate retrieval against an empty FAQ corpus.")
	if top_k < 5 or hit_rate_at_k < 1 or hit_rate_at_k > top_k:
		raise InvalidRetrievalRequest(
			"top_k must be at least 5 and hit-rate K must be between 1 and top_k."
		)
	if not dataset.examples:
		raise InvalidRetrievalRequest("Evaluation dataset has no valid query examples.")

	logger.info(
		"benchmark_started",
		retriever=retriever.name,
		dataset=dataset.dataset_name,
		corpus_size=len(corpus_ids),
		query_count=len(dataset.examples),
	)
	valid_examples = []
	issues = list(dataset.invalid_records)
	for index, example in enumerate(dataset.examples, start=1):
		missing = sorted(set(example.relevant_faq_ids) - corpus_ids)
		if missing:
			issues.append(
				EvaluationRecordError(
					record=index,
					code="relevant_faq_missing_from_corpus",
					message="One or more relevant FAQ IDs are absent from the active corpus.",
					query_id=example.query_id,
				)
			)
		else:
			valid_examples.append(example)
	if not valid_examples:
		raise InvalidRetrievalRequest("No evaluation queries reference FAQs in the active corpus.")

	relevant_sets: list[set[str]] = []
	retrieved_sets: list[list[str]] = []
	latencies: list[float] = []
	failures: list[EvaluationFailure] = []
	confusions: Counter[str] = Counter()
	for example in valid_examples:
		start = perf_counter()
		candidates = retriever.search(example.query, top_k=top_k)
		latencies.append((perf_counter() - start) * 1000.0)
		relevant = set(example.relevant_faq_ids)
		retrieved = [candidate.faq_id for candidate in candidates]
		relevant_sets.append(relevant)
		retrieved_sets.append(retrieved)
		missed = sorted(relevant - set(retrieved[:5]))
		false_positives = [faq_id for faq_id in retrieved[:5] if faq_id not in relevant]
		confusions.update(false_positives)
		if missed:
			failures.append(
				EvaluationFailure(
					query_id=example.query_id,
					missed_relevant_faq_ids=missed,
					confused_faq_ids=false_positives,
				)
			)

	metrics = compute_retrieval_metrics(
		relevant_ids=relevant_sets,
		retrieved_ids=retrieved_sets,
		latency_ms=latencies,
		hit_rate_at_k=hit_rate_at_k,
	)
	result = EvaluationResult(
		created_at=datetime.now(UTC).isoformat(),
		retriever_name=retriever.name,
		dataset_name=dataset.dataset_name,
		corpus_size=len(corpus_ids),
		num_queries=len(valid_examples),
		invalid_records=issues,
		metrics=metrics,
		failures=failures,
		confused_faq_counts=dict(confusions.most_common()),
		configuration=dict(configuration or {}),
		model_name=model_name,
		embedding_dimension=embedding_dimension,
		index_type=index_type,
		model_load_time_ms=model_load_time_ms,
		embedding_build_time_ms=embedding_build_time_ms,
		index_build_time_ms=index_build_time_ms,
	)
	logger.info(
		"benchmark_completed",
		retriever=retriever.name,
		query_count=result.num_queries,
		invalid_records=len(result.invalid_records),
		recall_at_5=metrics.recall_at_5,
		mean_latency_ms=metrics.mean_latency_ms,
	)
	return result