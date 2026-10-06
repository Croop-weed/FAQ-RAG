import asyncio
from pathlib import Path

from fastapi.testclient import TestClient

from support_assistant.core.config import Settings
from support_assistant.db.models import Base
from support_assistant.main import create_app


def make_test_app(tmp_path: Path):
    database_url = f"sqlite+aiosqlite:///{tmp_path / 'knowledge-base.db'}"
    app = create_app(Settings(environment="test", database_url=database_url))

    async def create_schema() -> None:
        async with app.state.database.engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())
    return app


def test_create_list_and_get_faq_through_api(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        created = client.post(
            "/knowledge-base/faqs",
            json={
                "question": "How do I update my profile?",
                "answer": "Open account settings.",
                "category": "account",
                "tags": ["profile"],
            },
        )
        listed = client.get("/knowledge-base/faqs?status=active")
        fetched = client.get(f"/knowledge-base/faqs/{created.json()['id']}")

    assert created.status_code == 201
    assert created.json()["question"] == "How do I update my profile?"
    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert fetched.status_code == 200
    assert fetched.json()["answer"] == "Open account settings."
    assert created.headers["X-Request-ID"]


def test_bulk_ingestion_reports_partial_invalid_records(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        response = client.post(
            "/knowledge-base/faqs/bulk",
            json={
                "records": [
                    {"question": "Reset password?", "answer": "Use the reset link."},
                    {"question": "", "answer": "This record is invalid."},
                    {"question": " reset  password? ", "answer": "Duplicate."},
                ]
            },
        )
        listed = client.get("/knowledge-base/faqs")

    assert response.status_code == 200
    assert response.json()["accepted_records"] == 2
    assert response.json()["rejected_records"] == 1
    assert response.json()["duplicates"] == 1
    assert response.json()["created_records"] == 1
    assert response.json()["validation_errors"][0]["field"] == "question"
    assert listed.json()["total"] == 1


def test_invalid_create_and_missing_faq_use_typed_errors(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        invalid = client.post("/knowledge-base/faqs", json={"question": "", "answer": "Answer"})
        missing = client.get("/knowledge-base/faqs/not-present")

    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    assert invalid.json()["error"]["request_id"] == invalid.headers["X-Request-ID"]
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "faq_not_found"


def test_patch_can_deactivate_faq(tmp_path: Path) -> None:
    with TestClient(make_test_app(tmp_path)) as client:
        created = client.post(
            "/knowledge-base/faqs",
            json={"question": "How do I close a workspace?", "answer": "Contact support."},
        )
        updated = client.patch(
            f"/knowledge-base/faqs/{created.json()['id']}",
            json={"status": "inactive"},
        )

    assert updated.status_code == 200
    assert updated.json()["status"] == "inactive"
