from collections.abc import Sequence

import structlog

from support_assistant.db.repositories.faq_repository import FAQRepository
from support_assistant.ingestion.validation import normalize_faq_record
from support_assistant.schemas.faq import (
    FAQIngestionResult,
    FAQIngestionValidationError,
    faq_identity,
)

logger = structlog.get_logger(__name__)


class FAQIngestionPipeline:
    def __init__(self, repository: FAQRepository) -> None:
        self.repository = repository

    async def ingest(
        self,
        records: Sequence[tuple[int, object]],
        *,
        validation_errors: Sequence[FAQIngestionValidationError] = (),
        total_records: int | None = None,
    ) -> FAQIngestionResult:
        logger.info("FAQ ingestion started", total_records=total_records or len(records))
        issues = list(validation_errors)
        valid_records = []
        for record_number, record in records:
            faq, record_issues = normalize_faq_record(record, record_number)
            issues.extend(record_issues)
            if faq is not None:
                valid_records.append((record_number, faq))

        seen: set[tuple[str, str, str]] = set()
        unique_records = []
        duplicates = 0
        for record_number, faq in valid_records:
            identity = faq_identity(faq.question, faq.product, faq.version)
            if identity in seen:
                duplicates += 1
                continue
            seen.add(identity)
            unique_records.append((record_number, faq, identity))

        existing = await self.repository.get_by_identities(
            [identity for _, _, identity in unique_records]
        )
        existing_identities = {
            faq_identity(item.question, item.product, item.version) for item in existing
        }
        to_create = [
            faq for _, faq, identity in unique_records if identity not in existing_identities
        ]
        duplicates += len(unique_records) - len(to_create)
        created = await self.repository.create_many(to_create)
        result = FAQIngestionResult(
            total_records=total_records if total_records is not None else len(records),
            accepted_records=len(valid_records),
            rejected_records=len(issues),
            duplicates=duplicates,
            created_records=len(created),
            validation_errors=issues,
        )
        logger.info(
            "FAQ ingestion completed",
            total_records=result.total_records,
            accepted_records=result.accepted_records,
            rejected_records=result.rejected_records,
            duplicates=result.duplicates,
            created_records=result.created_records,
        )
        return result
