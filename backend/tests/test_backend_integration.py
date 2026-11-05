"""End-to-end backend journey with isolated database and mocked Gemini."""
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
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "integration-test-only-secret-with-32-characters")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'journey.db').as_posix()}", connect_args={"check_same_thread": False})
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

def login(client, email):
    password = "safe-test-password-123"
    registered = client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password})
    assert registered.status_code == 201, registered.text
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}

def test_full_student_journey(client, monkeypatch):
    headers = login(client, "journey@example.com")
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 200
    prefs = client.put("/api/v1/students/me/preferences", headers=headers, json={
        "preferred_language": "telugu", "learning_level": "beginner", "learning_goal": "Learn greetings"})
    assert prefs.status_code == 200, prefs.text
    session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Greetings", "language": "mixed"})
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    calls = []
    def mock_tutor(instruction, history):
        calls.append((instruction, history))
        return "నమస్తే! Hello!"
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", mock_tutor)
    chat = client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=headers, json={"message": "Teach me hello"})
    assert chat.status_code == 200, chat.text
    assert chat.json()["language"] == "telugu"
    assert "Learn greetings" in calls[0][0]
    assert len(client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers).json()) == 2
    memory = client.post("/api/v1/memories", headers=headers, json={"topic": "Greetings", "note": "Practice pronunciation"})
    assert memory.status_code == 201, memory.text
    assert len(client.get("/api/v1/memories", headers=headers).json()) == 1
    progress = client.put("/api/v1/progress", headers=headers, json={"topic": "Greetings", "mastery_score": 60, "attempts": 2})
    assert progress.status_code == 200, progress.text
    assert client.get("/api/v1/progress/Greetings", headers=headers).json()["mastery_score"] == 60

def test_cross_student_journey_isolation(client, monkeypatch):
    first = login(client, "firstjourney@example.com")
    second = login(client, "secondjourney@example.com")
    session_id = client.post("/api/v1/sessions", headers=first, json={"topic": "Private"}).json()["id"]
    memory_id = client.post("/api/v1/memories", headers=first, json={"topic": "Private", "note": "Keep private"}).json()["id"]
    client.put("/api/v1/progress", headers=first, json={"topic": "Private", "mastery_score": 55, "attempts": 1})
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda *args: "reply")
    assert client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=second, json={"message": "hello"}).status_code == 404
    assert client.get(f"/api/v1/sessions/{session_id}/messages", headers=second).status_code == 404
    assert client.get(f"/api/v1/memories/{memory_id}", headers=second).status_code == 404
    assert client.get("/api/v1/progress/Private", headers=second).status_code == 404
    assert client.get("/api/v1/sessions", headers=second).json() == []
    assert client.get("/api/v1/memories", headers=second).json() == []
    assert client.get("/api/v1/progress", headers=second).json() == []

def test_invalid_token_rejected_across_modules(client):
    headers = {"Authorization": "Bearer invalid-token"}
    for url in ["/api/v1/auth/me", "/api/v1/sessions", "/api/v1/memories", "/api/v1/progress"]:
        assert client.get(url, headers=headers).status_code == 401
