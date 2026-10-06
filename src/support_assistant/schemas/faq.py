import hashlib
import json
from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class FAQStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    DRAFT = "draft"


class FAQCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, min_length=1, max_length=36)
    question: str = Field(max_length=2000)
    answer: str = Field(max_length=20000)
    category: str | None = None
    product: str | None = None
    version: str | None = None
    region: str | None = None
    tags: list[str] = Field(default_factory=list, max_length=50)
    source: str | None = None
    status: FAQStatus = FAQStatus.ACTIVE

    @field_validator("question", "answer")
    @classmethod
    def require_nonempty_content(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be empty")
        return value

    @field_validator("tags")
    @classmethod
    def require_nonempty_tags(cls, value: list[str]) -> list[str]:
        if any(not tag.strip() for tag in value):
            raise ValueError("tags must not be empty")
        return value


class FAQUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str | None = None
    answer: str | None = None
    category: str | None = None
    product: str | None = None
    version: str | None = None
    region: str | None = None
    tags: list[str] | None = None
    source: str | None = None
    status: FAQStatus | None = None

    @model_validator(mode="before")
    @classmethod
    def reject_null_required_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            for field in ("question", "answer", "status"):
                if field in value and value[field] is None:
                    raise ValueError(f"{field} cannot be null")
        return value

    @field_validator("question", "answer")
    @classmethod
    def require_nonempty_content(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("must not be empty")
        return value


class FAQRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    question: str
    answer: str
    category: str | None
    product: str | None
    version: str | None
    region: str | None
    tags: list[str]
    source: str | None
    status: FAQStatus
    created_at: datetime
    updated_at: datetime


class FAQListResponse(BaseModel):
    items: list[FAQRead]
    total: int


class FAQIngestionValidationError(BaseModel):
    record: int
    field: str
    code: str
    message: str
    context: dict[str, Any] = Field(default_factory=dict)


class FAQIngestionResult(BaseModel):
    total_records: int
    accepted_records: int
    rejected_records: int
    duplicates: int
    created_records: int
    updated_records: int = 0
    validation_errors: list[FAQIngestionValidationError] = Field(default_factory=list)


def faq_identity(question: str, product: str | None, version: str | None) -> tuple[str, str, str]:
    def normalize(value: str) -> str:
        return " ".join(value.split()).casefold()

    return normalize(question), normalize(product or ""), normalize(version or "")


def faq_identity_key(question: str, product: str | None, version: str | None) -> str:
    identity = json.dumps(faq_identity(question, product, version), ensure_ascii=False)
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()
