"""BE-01 smoke tests: no database or provider credentials required."""
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.main import create_app


def test_root_health() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "bhashalearn-api"}


def test_versioned_health() -> None:
    with TestClient(create_app(Settings(api_prefix="/api/v1"))) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_openapi_and_custom_title() -> None:
    with TestClient(create_app(Settings(app_name="Test BHASHALEARN"))) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Test BHASHALEARN"


def test_unknown_endpoint_is_404() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/v1/unknown")
    assert response.status_code == 404
