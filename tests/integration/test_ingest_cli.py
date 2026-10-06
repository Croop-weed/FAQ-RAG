import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from support_assistant.core.config import Settings
from support_assistant.db.models import Base
from support_assistant.ingestion import cli


def test_ingestion_cli_uses_pipeline_and_prints_summary(
    tmp_path: Path, monkeypatch, capsys
) -> None:
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'cli.db'}"

    async def create_schema() -> None:
        engine = create_async_engine(database_url)
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        await engine.dispose()

    asyncio.run(create_schema())
    monkeypatch.setattr(
        cli,
        "Settings",
        lambda: Settings(environment="test", database_url=database_url),
    )
    sample_path = Path(__file__).parents[2] / "data/raw/sample_faqs.jsonl"

    exit_code = asyncio.run(cli.ingest_file(sample_path))

    output = capsys.readouterr().out
    assert exit_code == 0
    assert "total=12 accepted=12 rejected=0 duplicates=1 created=11" in output
    assert "Open the sign-in page" not in output
