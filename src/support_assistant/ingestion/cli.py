import argparse
import asyncio
from collections.abc import Sequence
from pathlib import Path

import structlog

from support_assistant.core.config import Settings
from support_assistant.core.logging import configure_logging
from support_assistant.db.repositories.faq_repository import SqlAlchemyFAQRepository
from support_assistant.db.session import Database
from support_assistant.ingestion.loaders import FAQLoadError, load_faq_records
from support_assistant.ingestion.pipeline import FAQIngestionPipeline


async def ingest_file(path: Path) -> int:
    loaded = load_faq_records(path)
    settings = Settings()
    configure_logging(settings)
    database = Database(settings.database_url)
    try:
        async with database.session_factory() as session, session.begin():
            pipeline = FAQIngestionPipeline(SqlAlchemyFAQRepository(session))
            result = await pipeline.ingest(
                loaded.records,
                validation_errors=loaded.validation_errors,
                total_records=loaded.total_records,
            )
        print(
            f"total={result.total_records} accepted={result.accepted_records} "
            f"rejected={result.rejected_records} duplicates={result.duplicates} "
            f"created={result.created_records} updated={result.updated_records}"
        )
        if result.validation_errors:
            first_issue = result.validation_errors[0]
            print(
                f"First validation issue: record={first_issue.record} "
                f"field={first_issue.field} code={first_issue.code}"
            )
        return 0
    finally:
        await database.dispose()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest curated FAQ JSON or JSONL records.")
    parser.add_argument("path", type=Path, help="Input .json or .jsonl file")
    args = parser.parse_args(argv)
    try:
        return asyncio.run(ingest_file(args.path))
    except FAQLoadError as error:
        print(f"Input error: {error.message}")
        return 1
    except Exception as error:
        structlog.get_logger(__name__).error(
            "FAQ CLI ingestion failed", error_type=type(error).__name__
        )
        print("Ingestion failed; see structured logs for details.")
        return 1
