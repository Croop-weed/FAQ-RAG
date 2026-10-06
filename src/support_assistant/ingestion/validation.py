from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from support_assistant.schemas.faq import FAQCreate, FAQIngestionValidationError


def _normalize_content(value: str) -> str:
    normalized = value.replace("\r\n", "\n").replace("\r", "\n")
    lines = [" ".join(line.split()) for line in normalized.split("\n")]
    return "\n".join(lines).strip()


def normalize_faq_record(
    record: object, record_number: int
) -> tuple[FAQCreate | None, list[FAQIngestionValidationError]]:
    if not isinstance(record, Mapping):
        return None, [
            FAQIngestionValidationError(
                record=record_number,
                field="record",
                code="invalid_record",
                message="FAQ record must be a JSON object.",
            )
        ]

    values: dict[str, Any] = dict(record)
    for field in ("question", "answer"):
        if isinstance(values.get(field), str):
            values[field] = _normalize_content(values[field])
    for field in ("category", "product", "version", "region", "source"):
        value = values.get(field)
        if isinstance(value, str):
            values[field] = " ".join(value.split()) or None
    if isinstance(values.get("tags"), list):
        normalized_tags: list[Any] = []
        seen_tags: set[str] = set()
        for tag in values["tags"]:
            if not isinstance(tag, str):
                normalized_tags.append(tag)
                continue
            normalized_tag = " ".join(tag.split())
            if not normalized_tag:
                normalized_tags.append(normalized_tag)
                continue
            key = normalized_tag.casefold()
            if key not in seen_tags:
                normalized_tags.append(normalized_tag)
                seen_tags.add(key)
        values["tags"] = normalized_tags

    try:
        faq = FAQCreate.model_validate(values)
    except ValidationError as error:
        issues = []
        for issue in error.errors():
            field = str(issue["loc"][0]) if issue["loc"] else "record"
            issue_type = str(issue["type"])
            code = {
                "question": "empty_question" if issue_type == "value_error" else "invalid_question",
                "answer": "empty_answer" if issue_type == "value_error" else "invalid_answer",
                "status": "invalid_status",
            }.get(field, "invalid_field")
            message = {
                "question": "Question cannot be empty",
                "answer": "Answer cannot be empty",
                "status": "Status must be active, inactive, or draft",
            }.get(field, "FAQ record contains an invalid field")
            issues.append(
                FAQIngestionValidationError(
                    record=record_number,
                    field=field,
                    code=code,
                    message=message,
                )
            )
        return None, issues
    return faq, []
