"""End-to-end backend journey with isolated database and mocked Gemini."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import ChatMessage
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.tutor import LANGUAGE_GUIDANCE

@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "integration-test-only-secret-with-32-characters")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'journey.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()
    app.state.test_engine = engine
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
    session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Equivalent Fractions", "language": "mixed"})
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
    issued = client.post(f"/api/v1/assessments/sessions/{session_id}/issue", headers=headers)
    assert issued.status_code == 201, issued.text
    submitted = client.post(
        f"/api/v1/assessments/{issued.json()['attempt_id']}/answer",
        headers=headers,
        json={"answer": issued.json()["options"][0]},
    )
    assert submitted.status_code == 200, submitted.text
    assert submitted.json()["mastery_score"] == 100
    assert client.get("/api/v1/progress/equivalent%20fractions", headers=headers).json()["evidence_attempts"] == 1

def test_cross_student_journey_isolation(client, monkeypatch):
    first = login(client, "firstjourney@example.com")
    second = login(client, "secondjourney@example.com")
    session_id = client.post("/api/v1/sessions", headers=first, json={"topic": "Equivalent Fractions"}).json()["id"]
    memory_id = client.post("/api/v1/memories", headers=first, json={"topic": "Private", "note": "Keep private"}).json()["id"]
    issued = client.post(f"/api/v1/assessments/sessions/{session_id}/issue", headers=first)
    assert issued.status_code == 201
    submitted = client.post(f"/api/v1/assessments/{issued.json()['attempt_id']}/answer", headers=first, json={"answer": issued.json()["options"][0]})
    assert submitted.status_code == 200
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda *args: "reply")
    assert client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=second, json={"message": "hello"}).status_code == 404
    assert client.get(f"/api/v1/sessions/{session_id}/messages", headers=second).status_code == 404
    assert client.get(f"/api/v1/memories/{memory_id}", headers=second).status_code == 404
    assert client.get("/api/v1/progress/Equivalent%20Fractions", headers=second).status_code == 404
    assert client.get("/api/v1/sessions", headers=second).json() == []
    assert client.get("/api/v1/memories", headers=second).json() == []
    assert client.get("/api/v1/progress", headers=second).json() == []

def test_invalid_token_rejected_across_modules(client):
    headers = {"Authorization": "Bearer invalid-token"}
    for url in ["/api/v1/auth/me", "/api/v1/sessions", "/api/v1/memories", "/api/v1/progress"]:
        assert client.get(url, headers=headers).status_code == 401


def test_tutor_history_language_switch_and_message_persistence(client, monkeypatch):
    headers = login(client, "tutor-context@example.com")
    session = client.post("/api/v1/sessions", headers=headers, json={
        "topic": "Fractions", "language": "mixed",
    })
    assert session.status_code == 201, session.text
    session_id = session.json()["id"]
    messages_url = f"/api/v1/sessions/{session_id}/messages"
    for role, content in [
        ("user", "What is one half?"),
        ("assistant", "One half is one of two equal parts."),
    ]:
        saved = client.post(messages_url, headers=headers, json={"role": role, "content": content})
        assert saved.status_code == 201, saved.text

    calls = []

    def mock_tutor(instruction, history):
        calls.append((instruction, history))
        return f"mock reply {len(calls)}"

    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", mock_tutor)
    prefs = client.put("/api/v1/students/me/preferences", headers=headers, json={
        "preferred_language": "english",
        "learning_level": "intermediate",
        "learning_goal": "Prepare for algebra",
    })
    assert prefs.status_code == 200

    first = client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=headers, json={
        "message": "Give me another example",
    })
    assert first.status_code == 200, first.text
    assert first.json()["language"] == "english"
    assert first.json()["learning_level"] == "intermediate"
    assert "Current topic: Fractions" in calls[0][0]
    assert "Prepare for algebra" in calls[0][0]
    assert LANGUAGE_GUIDANCE["english"] in calls[0][0]
    assert calls[0][1] == [
        {"role": "user", "content": "What is one half?"},
        {"role": "assistant", "content": "One half is one of two equal parts."},
        {"role": "user", "content": "Give me another example"},
    ]

    prefs = client.put("/api/v1/students/me/preferences", headers=headers, json={
        "preferred_language": "telugu",
        "learning_level": "beginner",
        "learning_goal": "Review equivalent fractions",
    })
    assert prefs.status_code == 200
    second = client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=headers, json={
        "message": "Explain that more simply",
    })
    assert second.status_code == 200, second.text
    assert second.json()["language"] == "telugu"
    assert second.json()["learning_level"] == "beginner"
    assert LANGUAGE_GUIDANCE["telugu"] in calls[1][0]
    assert "Review equivalent fractions" in calls[1][0]
    assert calls[1][1] == [
        {"role": "user", "content": "What is one half?"},
        {"role": "assistant", "content": "One half is one of two equal parts."},
        {"role": "user", "content": "Give me another example"},
        {"role": "assistant", "content": "mock reply 1"},
        {"role": "user", "content": "Explain that more simply"},
    ]

    persisted = client.get(messages_url, headers=headers)
    assert persisted.status_code == 200
    assert [(item["role"], item["content"]) for item in persisted.json()] == [
        ("user", "What is one half?"),
        ("assistant", "One half is one of two equal parts."),
        ("user", "Give me another example"),
        ("assistant", "mock reply 1"),
        ("user", "Explain that more simply"),
        ("assistant", "mock reply 2"),
    ]


def test_tutor_missing_key_returns_503_without_persisting_messages(client, monkeypatch):
    from types import SimpleNamespace

    headers = login(client, "tutor-missing-key@example.com")
    session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Fractions"}).json()
    messages_url = f"/api/v1/sessions/{session['id']}/messages"
    monkeypatch.setattr(
        "backend.app.services.tutor.get_settings",
        lambda: SimpleNamespace(gemini_api_key="  ", gemini_model="gemini-test-model"),
    )

    response = client.post(
        f"/api/v1/tutor/sessions/{session['id']}/chat",
        headers=headers,
        json={"message": "Explain halves"},
    )

    assert response.status_code == 503
    assert "BHASHALEARN_GEMINI_API_KEY" in response.json()["detail"]
    assert client.get(messages_url, headers=headers).json() == []


def test_tutor_provider_failure_does_not_persist_partial_turn(client, monkeypatch):
    from fastapi import HTTPException

    headers = login(client, "tutor-provider-failure@example.com")
    session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Fractions"}).json()
    messages_url = f"/api/v1/sessions/{session['id']}/messages"
    saved = client.post(messages_url, headers=headers, json={"role": "user", "content": "Earlier question"})
    assert saved.status_code == 201

    def fail_provider(*_args):
        raise HTTPException(status_code=502, detail="AI provider unavailable or returned an invalid response")

    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", fail_provider)
    response = client.post(
        f"/api/v1/tutor/sessions/{session['id']}/chat",
        headers=headers,
        json={"message": "This turn must not be saved"},
    )

    assert response.status_code == 502
    history = client.get(messages_url, headers=headers).json()
    assert [(item["role"], item["content"]) for item in history] == [("user", "Earlier question")]


def test_tutor_authorization_and_input_validation_do_not_call_provider(client, monkeypatch):
    owner = login(client, "tutor-owner@example.com")
    other = login(client, "tutor-other@example.com")
    session = client.post("/api/v1/sessions", headers=owner, json={"topic": "Fractions"}).json()
    calls = []
    monkeypatch.setattr(
        "backend.app.api.tutor.generate_tutor_reply",
        lambda *args: calls.append(args) or "unused reply",
    )
    path = f"/api/v1/tutor/sessions/{session['id']}/chat"

    assert client.post(path, json={"message": "Hello"}).status_code == 401
    assert client.post(path, headers=other, json={"message": "Hello"}).status_code == 404
    assert client.post(path, headers=owner, json={"message": "   "}).status_code == 422
    assert client.post(path, headers=owner, json={"message": "x" * 4001}).status_code == 422
    assert calls == []


def test_equal_timestamp_chat_pair_keeps_user_before_assistant(client, monkeypatch):
    from datetime import datetime, timezone

    headers = login(client, "tutor-equal-timestamp@example.com")
    session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Fractions"}).json()
    session_id = session["id"]
    same_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    # Choose IDs that would reverse the intended turn if UUID ordering were used.
    with Session(client.app.state.test_engine) as db:
        db.add_all([
            ChatMessage(
                id="00000000-0000-0000-0000-000000000001",
                session_id=session_id,
                role="assistant",
                content="Earlier assistant reply",
                created_at=same_timestamp,
            ),
            ChatMessage(
                id="ffffffff-ffff-ffff-ffff-ffffffffffff",
                session_id=session_id,
                role="user",
                content="Earlier user question",
                created_at=same_timestamp,
            ),
        ])
        db.commit()

    calls = []

    def mock_tutor(instruction, history):
        calls.append(history)
        return "Follow-up response"

    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", mock_tutor)
    response = client.post(
        f"/api/v1/tutor/sessions/{session_id}/chat",
        headers=headers,
        json={"message": "Follow-up question"},
    )

    assert response.status_code == 200, response.text
    assert calls == [[
        {"role": "user", "content": "Earlier user question"},
        {"role": "assistant", "content": "Earlier assistant reply"},
        {"role": "user", "content": "Follow-up question"},
    ]]
    saved = client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers)
    assert saved.status_code == 200
    assert [(item["role"], item["content"]) for item in saved.json()] == [
        ("user", "Earlier user question"),
        ("assistant", "Earlier assistant reply"),
        ("user", "Follow-up question"),
        ("assistant", "Follow-up response"),
    ]
    assert saved.json()[2]["created_at"] < saved.json()[3]["created_at"]
