import asyncio

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from support_assistant.db.models import Base
from support_assistant.db.repositories.faq_repository import SqlAlchemyFAQRepository
from support_assistant.schemas.faq import FAQCreate, FAQStatus, FAQUpdate


def test_faq_repository_crud_and_bulk_operations() -> None:
    async def run_test() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as session, session.begin():
            repository = SqlAlchemyFAQRepository(session)
            created = await repository.create(
                FAQCreate(question="Reset password?", answer="Use account settings.")
            )
            bulk = await repository.create_many(
                [
                    FAQCreate(question="Change email?", answer="Update your profile."),
                    FAQCreate(question="Cancel plan?", answer="Contact an admin."),
                ]
            )
            assert len(bulk) == 2
            assert await repository.get(created.id) == created
            updated = await repository.update(created.id, FAQUpdate(status=FAQStatus.INACTIVE))
            assert updated is not None
            assert updated.status == FAQStatus.INACTIVE
            assert await repository.count() == 3
            assert await repository.count(status=FAQStatus.ACTIVE) == 2

        await engine.dispose()

    asyncio.run(run_test())
