import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from support_assistant.retrieval.exceptions import EvaluationDatasetError
from support_assistant.schemas.evaluation import (
    EvaluationDataset,
    EvaluationExample,
    EvaluationRecordError,
)


def load_evaluation_jsonl(path: Path) -> list[EvaluationExample]:
    dataset = load_evaluation_dataset(path)
    if dataset.invalid_records:
        first_error = dataset.invalid_records[0]
        raise ValueError(
            f"Invalid evaluation record on line {first_error.record}: {first_error.code}."
        )
    return dataset.examples


def load_evaluation_dataset(path: Path) -> EvaluationDataset:
    """Load JSONL and retain safe, structured diagnostics for invalid records."""
    examples: list[EvaluationExample] = []
    issues: list[EvaluationRecordError] = []
    seen_query_ids: set[str] = set()
    try:
        with path.open(encoding="utf-8") as dataset_file:
            for line_number, line in enumerate(dataset_file, start=1):
                if not line.strip():
                    continue
                try:
                    value: Any = json.loads(line)
                    if not isinstance(value, dict):
                        raise TypeError("Evaluation records must be JSON objects.")
                    example = EvaluationExample.model_validate(value)
                except (json.JSONDecodeError, TypeError, ValidationError):
                    issues.append(
                        EvaluationRecordError(
                            record=line_number,
                            code="invalid_evaluation_record",
                            message="Evaluation record is malformed or invalid.",
                        )
                    )
                    continue
                if example.query_id in seen_query_ids:
                    issues.append(
                        EvaluationRecordError(
                            record=line_number,
                            code="duplicate_query_id",
                            message="Query ID is duplicated in the dataset.",
                        )
                    )
                    continue
                seen_query_ids.add(example.query_id)
                examples.append(example)
    except (OSError, UnicodeError) as error:
        raise EvaluationDatasetError("Evaluation dataset could not be read as UTF-8.") from error
    return EvaluationDataset(
        dataset_name=path.name,
        examples=examples,
        invalid_records=issues,
    )
