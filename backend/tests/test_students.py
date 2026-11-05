"""BE-04 student profile and preferences integration tests."""
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
    engine = create_engine(f"sqlite:///{(tmp_path / 'students.db').as_posix()}", connect_args={"check_same_thread": False})
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
    password = "secure-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password}).status_code == 201
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_profile_read_and_update(client):
    headers = auth(client, "one@example.com")
    assert client.get("/api/v1/students/me", headers=headers).json()["display_name"] == "Learner"
    updated = client.patch("/api/v1/students/me", headers=headers, json={"display_name": "  Telugu Student  "})
    assert updated.status_code == 200
    assert updated.json()["display_name"] == "Telugu Student"
    assert client.patch("/api/v1/students/me", headers=headers, json={"display_name": "   "}).status_code == 422


def test_preferences_default_and_update(client):
    headers = auth(client, "two@example.com")
    endpoint = "/api/v1/students/me/preferences"
    assert client.get(endpoint, headers=headers).json() == {
        "preferred_language": "mixed", "learning_level": "beginner", "learning_goal": None
    }
    result = client.put(endpoint, headers=headers, json={
        "preferred_language": "telugu", "learning_level": "intermediate", "learning_goal": "  Speak English confidently  "
    })
    assert result.status_code == 200, result.text
    assert result.json()["learning_goal"] == "Speak English confidently"
    assert client.get(endpoint, headers=headers).json() == result.json()


def test_students_cannot_read_or_change_others_preferences(client):
    first = auth(client, "first@example.com")
    second = auth(client, "second@example.com")
    endpoint = "/api/v1/students/me/preferences"
    assert client.put(endpoint, headers=first, json={"preferred_language": "telugu", "learning_level": "advanced"}).status_code == 200
    assert client.get(endpoint, headers=second).json()["preferred_language"] == "mixed"
    assert client.get(endpoint).status_code == 401
    assert client.patch("/api/v1/students/me", json={"display_name": "Intruder"}).status_code == 401


def test_preferences_validation(client):
    headers = auth(client, "valid@example.com")
    endpoint = "/api/v1/students/me/preferences"
    assert client.put(endpoint, headers=headers, json={"preferred_language": "spanish"}).status_code == 422
    assert client.put(endpoint, headers=headers, json={"learning_level": "expert"}).status_code == 422
