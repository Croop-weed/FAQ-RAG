from collections.abc import Sequence
from typing import Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from support_assistant.db.models import FAQModel
from support_assistant.schemas.faq import (
    FAQCreate,
    FAQRead,
    FAQStatus,
    FAQUpdate,
    faq_identity_key,
)

FAQIdentity = tuple[str, str, str]


class FAQRepository(Protocol):
    async def create(self, faq: FAQCreate) -> FAQRead: ...

    async def create_many(self, faqs: Sequence[FAQCreate]) -> list[FAQRead]: ...

    async def get(self, faq_id: str) -> FAQRead | None: ...

    async def list_faqs(
        self,
        *,
        offset: int,
        limit: int,
        status: FAQStatus | None = None,
        category: str | None = None,
        product: str | None = None,
        version: str | None = None,
    ) -> tuple[list[FAQRead], int]: ...

    async def update(self, faq_id: str, changes: FAQUpdate) -> FAQRead | None: ...

    async def deactivate(self, faq_id: str) -> FAQRead | None: ...

    async def get_by_identities(self, identities: Sequence[FAQIdentity]) -> list[FAQRead]: ...

    async def count(self, *, status: FAQStatus | None = None) -> int: ...


class SqlAlchemyFAQRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, faq: FAQCreate) -> FAQRead:
        return (await self.create_many([faq]))[0]

    async def create_many(self, faqs: Sequence[FAQCreate]) -> list[FAQRead]:
        models = [
            FAQModel(
                **faq.model_dump(exclude={"id"}),
                **({"id": faq.id} if faq.id is not None else {}),
                deduplication_key=faq_identity_key(faq.question, faq.product, faq.version),
            )
            for faq in faqs
        ]
        self.session.add_all(models)
        await self.session.flush()
        for model in models:
            await self.session.refresh(model)
        return [FAQRead.model_validate(model) for model in models]

    async def get(self, faq_id: str) -> FAQRead | None:
        model = await self.session.get(FAQModel, faq_id)
        return FAQRead.model_validate(model) if model is not None else None

    async def list_faqs(
        self,
        *,
        offset: int,
        limit: int,
        status: FAQStatus | None = None,
        category: str | None = None,
        product: str | None = None,
        version: str | None = None,
    ) -> tuple[list[FAQRead], int]:
        filters = []
        if status is not None:
            filters.append(FAQModel.status == status)
        if category is not None:
            filters.append(FAQModel.category == category)
        if product is not None:
            filters.append(FAQModel.product == product)
        if version is not None:
            filters.append(FAQModel.version == version)

        count_statement = select(func.count()).select_from(FAQModel).where(*filters)
        total = await self.session.scalar(count_statement) or 0
        statement = (
            select(FAQModel)
            .where(*filters)
            .order_by(FAQModel.created_at.desc(), FAQModel.id)
            .offset(offset)
            .limit(limit)
        )
        models = (await self.session.scalars(statement)).all()
        return [FAQRead.model_validate(model) for model in models], total

    async def update(self, faq_id: str, changes: FAQUpdate) -> FAQRead | None:
        model = await self.session.get(FAQModel, faq_id)
        if model is None:
            return None
        for key, value in changes.model_dump(exclude_unset=True).items():
            setattr(model, key, value)
        model.deduplication_key = faq_identity_key(model.question, model.product, model.version)
        await self.session.flush()
        await self.session.refresh(model)
        return FAQRead.model_validate(model)

    async def get_by_identities(self, identities: Sequence[FAQIdentity]) -> list[FAQRead]:
        matches: list[FAQRead] = []
        for start in range(0, len(identities), 400):
            batch = identities[start : start + 400]
            keys = [faq_identity_key(*identity) for identity in batch]
            statement = select(FAQModel).where(FAQModel.deduplication_key.in_(keys))
            models = (await self.session.scalars(statement)).all()
            matches.extend(FAQRead.model_validate(model) for model in models)
        return matches

    async def count(self, *, status: FAQStatus | None = None) -> int:
        statement = select(func.count()).select_from(FAQModel)
        if status is not None:
            statement = statement.where(FAQModel.status == status)
        return await self.session.scalar(statement) or 0

    async def deactivate(self, faq_id: str) -> FAQRead | None:
        result = await self.update(faq_id, FAQUpdate(status=FAQStatus.INACTIVE))
        return result
