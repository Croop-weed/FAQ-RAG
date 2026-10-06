import json
from pathlib import Path

import pytest

from support_assistant.ingestion.evaluation import (
    load_evaluation_dataset,
    load_evaluation_jsonl,
)
from support_assistant.retrieval.benchmark import export_result, run_benchmark
from support_assistant.retrieval.bm25_search import BM25Retriever
from support_assistant.retrieval.evaluator import evaluate_retriever
from support_assistant.retrieval.exceptions import InvalidRetrievalRequest
from support_assistant.schemas.evaluation import EvaluationDataset, EvaluationExample
from support_assistant.schemas.retrieval import (
    RetrievalCandidate,
    RetrievalDocument,
    RetrievalExecution,
)


class FixedRetriever:
    name = "fixed-test"

    def search(self, query: str, *, top_k: int) -> list[RetrievalCandidate]:
        results = ["faq-1", "faq-2"] if "first" in query else ["faq-2", "faq-1"]
        return [
            RetrievalCandidate(document_id=faq_id, score=1 - rank / 10, rank=rank)
            for rank, faq_id in enumerate(results[:top_k], start=1)
        ]


def test_evaluation_loader_generates_compatible_query_ids(tmp_path: Path) -> None:
    path = tmp_path / "dataset.jsonl"
    path.write_text(
        json.dumps({"query": "first query", "relevant_faq_ids": ["faq-1"]}) + "\n",
        encoding="utf-8",
    )

    dataset = load_evaluation_dataset(path)

    assert dataset.examples[0].query_id.startswith("q-")
    assert dataset.examples[0].metadata == {}
    assert dataset.invalid_records == []
    assert load_evaluation_jsonl(path) == dataset.examples


def test_evaluation_loader_retains_structured_invalid_rows(tmp_path: Path) -> None:
    path = tmp_path / "bad.jsonl"
    path.write_text(
        "{malformed}\n"
        + json.dumps({"query": "bad", "relevant_faq_ids": ["faq-1", "faq-1"]})
        + "\n",
        encoding="utf-8",
    )

    dataset = load_evaluation_dataset(path)

    assert len(dataset.invalid_records) == 2
    assert all(issue.code == "invalid_evaluation_record" for issue in dataset.invalid_records)
    with pytest.raises(ValueError):
        load_evaluation_jsonl(path)


def test_runner_reports_metrics_failures_and_missing_relevance() -> None:
    dataset = EvaluationDataset(
        dataset_name="tiny.jsonl",
        examples=[
            EvaluationExample(
                query_id="q1", query="first query", relevant_faq_ids=["faq-1", "faq-2"]
            ),
            EvaluationExample(query_id="q2", query="second query", relevant_faq_ids=["faq-x"]),
        ],
    )

    result = evaluate_retriever(FixedRetriever(), dataset, corpus_ids={"faq-1", "faq-2"}, top_k=5)

    assert result.num_queries == 1
    assert result.metrics.recall_at_1 == pytest.approx(0.5)
    assert result.metrics.mrr == 1.0
    assert len(result.invalid_records) == 1
    assert result.invalid_records[0].code == "relevant_faq_missing_from_corpus"
    assert result.failures == []
    assert result.model_dump_json()


def test_runner_rejects_empty_corpus_and_all_invalid_examples() -> None:
    dataset = EvaluationDataset(
        dataset_name="tiny.jsonl",
        examples=[EvaluationExample(query="q", relevant_faq_ids=["missing"])],
    )

    with pytest.raises(InvalidRetrievalRequest):
        evaluate_retriever(FixedRetriever(), dataset, corpus_ids=set())
    with pytest.raises(InvalidRetrievalRequest):
        evaluate_retriever(FixedRetriever(), dataset, corpus_ids={"faq-1"})


def test_bm25_benchmark_result_exports_as_json(tmp_path: Path) -> None:
    query = EvaluationExample(
        query_id="q-bm25",
        query="reset password",
        relevant_faq_ids=["faq-password"],
    )
    dataset = EvaluationDataset(dataset_name="one.jsonl", examples=[query])
    retriever = BM25Retriever(
        [
            RetrievalDocument(
                faq_id="faq-password",
                question="Reset password",
                answer="Use password reset.",
            ),
            RetrievalDocument(
                faq_id="faq-invoice",
                question="Download invoice",
                answer="Open billing settings.",
            ),
        ]
    )
    result = run_benchmark(
        retriever,
        dataset,
        corpus_ids={"faq-password", "faq-invoice"},
        top_k=5,
        configuration={"top_k": 5},
    )
    output_path = tmp_path / "results" / "baseline.json"

    export_result(result, output_path)

    serialized = json.loads(output_path.read_text(encoding="utf-8"))
    assert serialized["retriever_name"] == "bm25"
    assert serialized["metrics"]["recall_at_1"] == 1.0
    assert serialized["configuration"]["top_k"] == 5


def test_runner_counts_false_positive_faqs_even_when_query_has_a_hit() -> None:
    dataset = EvaluationDataset(
        dataset_name="one.jsonl",
        examples=[
            EvaluationExample(query_id="q1", query="first query", relevant_faq_ids=["faq-1"])
        ],
    )

    result = evaluate_retriever(FixedRetriever(), dataset, corpus_ids={"faq-1", "faq-2"}, top_k=5)

    assert result.failures == []
    assert result.confused_faq_counts == {"faq-2": 1}


def test_runner_reports_reranker_latency_separately() -> None:
    class TimedRetriever(FixedRetriever):
        def __init__(self) -> None:
            super().__init__()
            self.stage_latency = 4.0

        def search_detailed(self, query: str, *, top_k: int):
            candidates = self.search(query, top_k=top_k)
            latency = self.stage_latency
            self.stage_latency += 2.0
            return RetrievalExecution(
                candidates=candidates,
                stage_latency_ms={"reranker": latency},
            )

    retriever = TimedRetriever()
    dataset = EvaluationDataset(
        dataset_name="two.jsonl",
        examples=[
            EvaluationExample(query_id="q1", query="first query", relevant_faq_ids=["faq-1"]),
            EvaluationExample(query_id="q2", query="second query", relevant_faq_ids=["faq-2"]),
        ],
    )

    result = evaluate_retriever(
        retriever,
        dataset,
        corpus_ids={"faq-1", "faq-2"},
        top_k=5,
    )

    assert result.reranker_latency is not None
    assert result.reranker_latency.mean_ms == pytest.approx(5.0)
    assert result.reranker_latency.p50_ms == pytest.approx(5.0)
