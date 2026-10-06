from uuid import UUID

from fastapi.testclient import TestClient

from support_assistant.core.config import Settings
from support_assistant.core.exceptions import AppException
from support_assistant.main import create_app
from support_assistant.schemas.health import HealthResponse


def test_application_factory_and_health_response() -> None:
    app = create_app(Settings(app_name="test-service", environment="test"))

    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert HealthResponse.model_validate(response.json()) == HealthResponse(
        status="ok", service="test-service"
    )
    UUID(response.headers["X-Request-ID"])


def test_valid_request_id_is_reused() -> None:
    request_id = "a14279e5-4c28-4c24-b62c-c96f50c31cc4"

    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/health", headers={"X-Request-ID": request_id})

    assert response.headers["X-Request-ID"] == request_id


def test_invalid_request_id_is_replaced() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/health", headers={"X-Request-ID": "not-a-uuid"})

    assert response.headers["X-Request-ID"] != "not-a-uuid"
    UUID(response.headers["X-Request-ID"])


def test_error_response_has_consistent_structure() -> None:
    app = create_app(Settings(environment="test"))

    @app.get("/test-error")
    async def raise_application_error() -> None:
        raise AppException("Missing resource", code="resource_missing", status_code=404)

    with TestClient(app) as client:
        response = client.get("/test-error")

    assert response.status_code == 404
    assert response.json() == {
        "error": {
            "code": "resource_missing",
            "message": "Missing resource",
            "request_id": response.headers["X-Request-ID"],
        }
    }


def test_unexpected_errors_do_not_leak_details() -> None:
    app = create_app(Settings(environment="production"))

    @app.get("/unexpected-error")
    async def raise_unexpected_error() -> None:
        raise RuntimeError("private internal detail")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/unexpected-error")

    assert response.status_code == 500
    assert response.json()["error"]["message"] == "An unexpected error occurred."
    assert "private internal detail" not in response.text
