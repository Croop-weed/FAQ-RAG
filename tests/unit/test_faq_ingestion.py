import asyncio

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from support_assistant.db.models import Base
from support_assistant.db.repositories.faq_repository import SqlAlchemyFAQRepository
from support_assistant.ingestion.pipeline import FAQIngestionPipeline
from support_assistant.ingestion.validation import normalize_faq_record
from support_assistant.schemas.faq import FAQCreate, FAQStatus


def test_faq_schema_requires_nonempty_question_and_answer() -> None:
    with pytest.raises(ValidationError):
        FAQCreate(question="  ", answer="An answer")
    with pytest.raises(ValidationError):
        FAQCreate(question="A question", answer="\n ")


def test_validation_normalizes_content_and_metadata() -> None:
    faq, issues = normalize_faq_record(
        {
            "question": "  How   do I reset\n my password? ",
            "answer": " First step.  \n\n Second   step. ",
            "product": " Orbit Desk ",
            "tags": [" Password ", "password", "Account"],
        },
        4,
    )

    assert issues == []
    assert faq is not None
    assert faq.question == "How do I reset\nmy password?"
    assert faq.answer == "First step.\n\nSecond step."
    assert faq.product == "Orbit Desk"
    assert faq.tags == ["Password", "Account"]
    assert faq.status == FAQStatus.ACTIVE


def test_invalid_records_return_structured_errors() -> None:
    faq, issues = normalize_faq_record(
        {"question": "", "answer": "A valid answer", "status": "unknown"}, 12
    )

    assert faq is None
    assert {(issue.record, issue.field, issue.code) for issue in issues} == {
        (12, "question", "empty_question"),
        (12, "status", "invalid_status"),
    }


def test_invalid_tags_are_reported_not_silently_removed() -> None:
    faq, issues = normalize_faq_record(
        {"question": "A question", "answer": "An answer", "tags": ["valid", " ", 7]},
        6,
    )

    assert faq is None
    assert issues[0].record == 6
    assert issues[0].field == "tags"


def test_ingestion_keeps_valid_records_and_skips_duplicates() -> None:
    async def run_test() -> None:
        engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        factory = async_sessionmaker(engine, expire_on_commit=False)

        async with factory() as session, session.begin():
            pipeline = FAQIngestionPipeline(SqlAlchemyFAQRepository(session))
            result = await pipeline.ingest(
                [
                    (1, {"question": "Reset password?", "answer": "Use settings."}),
                    (2, {"question": " reset   password? ", "answer": "A duplicate."}),
                    (3, {"question": "", "answer": "Invalid FAQ."}),
                    (4, {"question": "Invite a teammate?", "answer": "Use members."}),
                ],
                total_records=4,
            )
            assert result.total_records == 4
            assert result.accepted_records == 3
            assert result.rejected_records == 1
            assert result.duplicates == 1
            assert result.created_records == 2
            assert result.validation_errors[0].record == 3

            repeated = await pipeline.ingest(
                [(1, {"question": "Reset password?", "answer": "Another answer."})]
            )
            assert repeated.duplicates == 1
            assert repeated.created_records == 0

        await engine.dispose()

    asyncio.run(run_test())
