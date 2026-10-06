from collections.abc import Sequence

from support_assistant.core.exceptions import (
    FAQAlreadyExists,
    FAQNotFound,
    FAQValidationError,
)
from support_assistant.db.repositories.faq_repository import FAQRepository
from support_assistant.ingestion.pipeline import FAQIngestionPipeline
from support_assistant.ingestion.validation import normalize_faq_record
from support_assistant.schemas.faq import (
    FAQCreate,
    FAQIngestionResult,
    FAQIngestionValidationError,
    FAQListResponse,
    FAQRead,
    FAQStatus,
    FAQUpdate,
    faq_identity,
)


class KnowledgeBaseService:
    def __init__(self, repository: FAQRepository) -> None:
        self.repository = repository
        self.ingestion = FAQIngestionPipeline(repository)

    async def create_faq(self, faq: FAQCreate) -> FAQRead:
        normalized, _issues = normalize_faq_record(faq.model_dump(), 1)
        if normalized is None:
            raise FAQValidationError()
        identity = faq_identity(normalized.question, normalized.product, normalized.version)
        if await self.repository.get_by_identities([identity]):
            raise FAQAlreadyExists()
        return await self.repository.create(normalized)

    async def ingest_records(
        self,
        records: Sequence[tuple[int, object]],
        *,
        validation_errors: Sequence[FAQIngestionValidationError] = (),
        total_records: int | None = None,
    ) -> FAQIngestionResult:
        return await self.ingestion.ingest(
            records,
            validation_errors=validation_errors,
            total_records=total_records,
        )

    async def get_faq(self, faq_id: str) -> FAQRead:
        faq = await self.repository.get(faq_id)
        if faq is None:
            raise FAQNotFound(faq_id)
        return faq

    async def list_faqs(
        self,
        *,
        offset: int = 0,
        limit: int = 100,
        status: FAQStatus | None = None,
        category: str | None = None,
        product: str | None = None,
        version: str | None = None,
    ) -> FAQListResponse:
        items, total = await self.repository.list_faqs(
            offset=offset,
            limit=limit,
            status=status,
            category=category,
            product=product,
            version=version,
        )
        return FAQListResponse(items=items, total=total)

    async def update_faq(self, faq_id: str, changes: FAQUpdate) -> FAQRead:
        current = await self.repository.get(faq_id)
        if current is None:
            raise FAQNotFound(faq_id)
        values = current.model_dump(exclude={"created_at", "updated_at"})
        values.update(changes.model_dump(exclude_unset=True))
        normalized, _issues = normalize_faq_record(values, 1)
        if normalized is None:
            raise FAQValidationError()
        identity = faq_identity(normalized.question, normalized.product, normalized.version)
        duplicates = await self.repository.get_by_identities([identity])
        if any(item.id != faq_id for item in duplicates):
            raise FAQAlreadyExists()
        updated = await self.repository.update(
            faq_id, FAQUpdate.model_validate(normalized.model_dump(exclude={"id"}))
        )
        if updated is None:
            raise FAQNotFound(faq_id)
        return updated

    async def deactivate_faq(self, faq_id: str) -> FAQRead:
        faq = await self.repository.deactivate(faq_id)
        if faq is None:
            raise FAQNotFound(faq_id)
        return faq
