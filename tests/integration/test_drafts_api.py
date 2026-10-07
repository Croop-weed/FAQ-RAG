import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from support_assistant.core.config import Settings
from support_assistant.db.models import Base
from support_assistant.main import create_app


def make_test_app(tmp_path: Path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'drafts-test.db'}"
    app = create_app(Settings(environment="test", database_url=database_url))

    async def create_schema() -> None:
        async with app.state.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    return app


def test_health_and_drafts_endpoint(tmp_path: Path) -> None:
    app = make_test_app(tmp_path)
    with TestClient(app) as client:
        health_resp = client.get("/health")
        assert health_resp.status_code == 200
        assert health_resp.json()["status"] == "ok"

        # Create active FAQ first
        client.post(
            "/knowledge-base/faqs",
            json={
                "question": "How do I reset my password?",
                "answer": "Go to settings page and click reset password link.",
                "category": "security",
            },
        )

        draft_resp = client.post("/drafts/process", json={"query": "How do I reset my password?"})
        assert draft_resp.status_code == 200
        data = draft_resp.json()
        assert "decision" in data
        assert "confidence" in data
        assert "reason" in data
