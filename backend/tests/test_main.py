"""BE-01 smoke tests: no database or provider credentials required."""
from fastapi.testclient import TestClient
from sqlalchemy import create_engine

from backend.app.config import Settings
from backend.app.main import create_app
import backend.app.main as main_module


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


def test_database_readiness_uses_ephemeral_engine(monkeypatch) -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    monkeypatch.setattr(main_module, "get_engine", lambda: engine)
    with TestClient(create_app(Settings())) as client:
        root = client.get("/ready")
        versioned = client.get("/api/v1/ready")
    engine.dispose()
    assert root.status_code == versioned.status_code == 200
    assert root.json() == {"status": "ready", "database": "ok"}
    assert versioned.json() == root.json()


def test_database_readiness_hides_connection_failure(monkeypatch) -> None:
    def fail_connection():
        raise RuntimeError("sensitive driver detail")

    monkeypatch.setattr(main_module, "get_engine", fail_connection)
    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json() == {"detail": "Database is unavailable"}
    assert "sensitive" not in response.text


def test_openapi_and_custom_title() -> None:
    with TestClient(create_app(Settings(app_name="Test BHASHALEARN"))) as client:
        response = client.get("/openapi.json")
    assert response.status_code == 200
    assert response.json()["info"]["title"] == "Test BHASHALEARN"


def test_unknown_endpoint_is_404() -> None:
    with TestClient(create_app(Settings())) as client:
        response = client.get("/api/v1/unknown")
    assert response.status_code == 404
