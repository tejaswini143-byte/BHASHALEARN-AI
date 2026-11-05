"""INT-05 progress API is read-only and exposes assessment-backed evidence."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "test-only-secret-key-please-never-use-in-production-123")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'progress.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def auth(client, email):
    password = "safe-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def test_client_cannot_write_mastery_directly(client):
    headers = auth(client, "one@example.com")
    response = client.put("/api/v1/progress", headers=headers, json={
        "topic": "Greetings", "mastery_score": 99, "attempts": 100
    })
    assert response.status_code == 405
    assert client.get("/api/v1/progress", headers=headers).json() == []


def test_progress_student_isolation(client):
    first = auth(client, "first@example.com")
    second = auth(client, "second@example.com")
    assert client.get("/api/v1/progress", headers=first).json() == []
    assert client.get("/api/v1/progress", headers=second).json() == []
    assert client.get("/api/v1/progress", headers=second).status_code == 200
    assert client.get("/api/v1/progress").status_code == 401


def test_progress_validation(client):
    headers = auth(client, "valid@example.com")
    assert client.get("/api/v1/progress?limit=0", headers=headers).status_code == 422
    assert client.get("/api/v1/progress/missing", headers=headers).status_code == 404
