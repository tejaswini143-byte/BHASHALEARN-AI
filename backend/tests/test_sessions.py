"""BE-06 private learning sessions API tests with isolated SQLite."""
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
    engine = create_engine(f"sqlite:///{(tmp_path / 'sessions.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def auth(client, email):
    password = "safe-test-password-123"
    assert client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "Learner", "password": password
    }).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": "Bearer " + login.json()["access_token"]}


def test_create_list_and_get_sessions(client):
    headers = auth(client, "one@example.com")
    created = client.post("/api/v1/sessions", headers=headers, json={
        "topic": "  English greetings  ", "language": "mixed"
    })
    assert created.status_code == 201, created.text
    session = created.json()
    assert session["topic"] == "English greetings"
    assert client.get(f"/api/v1/sessions/{session['id']}", headers=headers).status_code == 200
    assert [s["id"] for s in client.get("/api/v1/sessions", headers=headers).json()] == [session["id"]]
    assert client.get("/api/v1/sessions?limit=0", headers=headers).status_code == 422


def test_message_history_and_validation(client):
    headers = auth(client, "two@example.com")
    session_id = client.post("/api/v1/sessions", headers=headers, json={"topic": "Telugu"}).json()["id"]
    url = f"/api/v1/sessions/{session_id}/messages"
    for role, content in [("user", "Namaste"), ("assistant", "Hello!")]:
        response = client.post(url, headers=headers, json={"role": role, "content": content})
        assert response.status_code == 201, response.text
    history = client.get(url, headers=headers)
    assert history.status_code == 200
    assert {m["role"] for m in history.json()} == {"user", "assistant"}
    assert len(history.json()) == 2
    assert client.post(url, headers=headers, json={"role": "system", "content": "bad"}).status_code == 422
    assert client.post(url, headers=headers, json={"role": "user", "content": "   "}).status_code == 422


def test_session_owner_isolation(client):
    first = auth(client, "first@example.com")
    second = auth(client, "second@example.com")
    session_id = client.post("/api/v1/sessions", headers=first, json={"topic": "Private"}).json()["id"]
    assert client.get("/api/v1/sessions", headers=second).json() == []
    assert client.get(f"/api/v1/sessions/{session_id}", headers=second).status_code == 404
    assert client.get(f"/api/v1/sessions/{session_id}/messages", headers=second).status_code == 404
    assert client.post(f"/api/v1/sessions/{session_id}/messages", headers=second, json={"role": "user", "content": "Intrude"}).status_code == 404
    assert client.get("/api/v1/sessions").status_code == 401


def test_course_association_and_missing_resources(client):
    headers = auth(client, "course@example.com")
    assert client.post("/api/v1/sessions", headers=headers, json={"topic": "X", "course_id": "missing"}).status_code == 404
    course = client.post("/api/v1/courses", headers=headers, json={"title": "Bilingual Basics"})
    assert course.status_code == 201
    course_id = course.json()["id"]
    created = client.post("/api/v1/sessions", headers=headers, json={"topic": "Greetings", "course_id": course_id})
    assert created.status_code == 201
    assert created.json()["course_id"] == course_id
    assert client.get("/api/v1/sessions/missing", headers=headers).status_code == 404
    assert client.get("/api/v1/sessions/missing/messages", headers=headers).status_code == 404
