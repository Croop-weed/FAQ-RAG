import json
from pathlib import Path

import pytest

from support_assistant.ingestion.evaluation import load_evaluation_jsonl
from support_assistant.schemas.evaluation import EvaluationDifficulty, EvaluationExample


def test_evaluation_schema_and_sample_jsonl() -> None:
    root = Path(__file__).parents[2]
    examples = load_evaluation_jsonl(root / "data/evaluation/sample_retrieval.jsonl")

    assert len(examples) == 5
    assert examples[0].difficulty == EvaluationDifficulty.EASY
    assert examples[0].relevant_faq_ids == ["sample-faq-001"]


def test_invalid_evaluation_jsonl_reports_line(tmp_path: Path) -> None:
    dataset = tmp_path / "invalid.jsonl"
    dataset.write_text(json.dumps({"query": "Where is billing?"}) + "\n", encoding="utf-8")

    with pytest.raises(ValueError, match="line 1"):
        load_evaluation_jsonl(dataset)


def test_evaluation_example_has_relevant_faq_ids() -> None:
    with pytest.raises(ValueError):
        EvaluationExample(query="Where can I export a report?", relevant_faq_ids=[])
