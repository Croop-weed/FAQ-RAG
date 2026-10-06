import json
from pathlib import Path

from pydantic import ValidationError

from support_assistant.schemas.evaluation import EvaluationExample


def load_evaluation_jsonl(path: Path) -> list[EvaluationExample]:
    """Load typed retrieval-evaluation examples from UTF-8 JSONL."""
    examples = []
    with path.open(encoding="utf-8") as dataset_file:
        for line_number, line in enumerate(dataset_file, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                examples.append(EvaluationExample.model_validate(value))
            except (json.JSONDecodeError, ValidationError) as error:
                raise ValueError(f"Invalid evaluation example on line {line_number}.") from error
    return examples
