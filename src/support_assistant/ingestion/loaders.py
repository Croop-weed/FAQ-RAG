import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from support_assistant.core.exceptions import AppException
from support_assistant.schemas.faq import FAQIngestionValidationError


class FAQLoadError(AppException):
    def __init__(self, message: str) -> None:
        super().__init__(message, code="faq_load_error", status_code=400)


@dataclass(frozen=True)
class LoadedFAQRecords:
    records: list[tuple[int, Any]]
    validation_errors: list[FAQIngestionValidationError]
    total_records: int


def load_faq_records(path: Path) -> LoadedFAQRecords:
    file_format = path.suffix.lower()
    if file_format not in {".json", ".jsonl"}:
        raise FAQLoadError("Input file must use .json or .jsonl format.")
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        raise FAQLoadError("Input file could not be read as UTF-8.") from error

    records: list[tuple[int, Any]] = []
    issues: list[FAQIngestionValidationError] = []
    if file_format == ".json":
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as error:
            raise FAQLoadError("Input file contains malformed JSON.") from error
        if not isinstance(payload, list):
            raise FAQLoadError("JSON input must contain an array of FAQ objects.")
        for record_number, record in enumerate(payload, start=1):
            records.append((record_number, record))
        return LoadedFAQRecords(records, issues, len(payload))

    line_count = 0
    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        line_count += 1
        try:
            records.append((line_number, json.loads(line)))
        except json.JSONDecodeError:
            issues.append(
                FAQIngestionValidationError(
                    record=line_number,
                    field="record",
                    code="malformed_json",
                    message="Line is not valid JSON.",
                )
            )
    return LoadedFAQRecords(records, issues, line_count)
