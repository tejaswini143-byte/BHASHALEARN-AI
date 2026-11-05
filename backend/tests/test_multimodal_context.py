"""Deterministic tests for cross-mode session and visual context synchronization."""
from datetime import datetime, timezone

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
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "multimodal-test-secret-with-32-characters")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'multimodal.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    app.state.test_engine = engine
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def login(client: TestClient, email: str) -> dict[str, str]:
    password = "multimodal-test-password-123"
    registered = client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password})
    assert registered.status_code == 201, registered.text
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def create_session(client: TestClient, headers: dict[str, str], topic: str = "Fractions") -> str:
    response = client.post("/api/v1/sessions", headers=headers, json={"topic": topic, "language": "mixed"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_shared_context_auth_owner_and_missing_session(client):
    first = login(client, "context-first@example.com")
    second = login(client, "context-second@example.com")
    session_id = create_session(client, first)
    path = f"/api/v1/sessions/{session_id}/context"

    assert client.get(path).status_code == 401
    assert client.get(path, headers=second).status_code == 404
    assert client.get("/api/v1/sessions/not-a-session/context", headers=first).status_code == 404
    result = client.get(path, headers=first)
    assert result.status_code == 200
    assert result.json() == {
        "session_id": session_id,
        "topic": "Fractions",
        "preferred_language": "mixed",
        "learning_level": "beginner",
        "learning_goal": None,
        "messages": [],
        "visual_lesson": None,
    }


def test_context_preferences_level_goal_and_chronological_history(client):
    headers = login(client, "context-history@example.com")
    session_id = create_session(client, headers)
    pref = client.put("/api/v1/students/me/preferences", headers=headers, json={
        "preferred_language": "telugu", "learning_level": "intermediate", "learning_goal": "Understand equivalent fractions",
    })
    assert pref.status_code == 200
    timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)
    with Session(client.app.state.test_engine) as db:
        db.add_all([
            ChatMessage(id="z-user", session_id=session_id, role="user", content="Question", created_at=timestamp),
            ChatMessage(id="a-assistant", session_id=session_id, role="assistant", content="Answer", created_at=timestamp),
        ])
        db.commit()

    result = client.get(f"/api/v1/sessions/{session_id}/context", headers=headers)
    assert result.status_code == 200
    context = result.json()
    assert context["preferred_language"] == "telugu"
    assert context["learning_level"] == "intermediate"
    assert context["learning_goal"] == "Understand equivalent fractions"
    assert [(item["role"], item["content"]) for item in context["messages"]] == [
        ("user", "Question"), ("assistant", "Answer"),
    ]


def test_context_bounds_history_and_validates_limit(client):
    headers = login(client, "context-bounded@example.com")
    session_id = create_session(client, headers)
    with Session(client.app.state.test_engine) as db:
        db.add_all([
            ChatMessage(session_id=session_id, role="user", content=f"message {index}", created_at=datetime(2026, 1, 1, tzinfo=timezone.utc).replace(microsecond=index))
            for index in range(4)
        ])
        db.commit()
    result = client.get(f"/api/v1/sessions/{session_id}/context?limit=2", headers=headers)
    assert result.status_code == 200
    assert [item["content"] for item in result.json()["messages"]] == ["message 2", "message 3"]
    assert client.get(f"/api/v1/sessions/{session_id}/context?limit=501", headers=headers).status_code == 422


def test_visual_context_persists_per_session_without_adding_chat_turns(client):
    headers = login(client, "visual-state@example.com")
    first = create_session(client, headers, "Fractions")
    second = create_session(client, headers, "Graphs")
    save = client.put(f"/api/v1/sessions/{first}/visual-context", headers=headers, json={"visual_key": "fractions-equivalent"})
    assert save.status_code == 200, save.text
    assert save.json()["title"] == "Equivalent Fractions"
    assert "1/2 = 2/4 = 4/8" in save.json()["description"]
    with Session(client.app.state.test_engine) as db:
        db.add_all([
            ChatMessage(session_id=first, role="user", content="First session question"),
            ChatMessage(session_id=second, role="user", content="Second session question"),
        ])
        db.commit()
    assert client.get(f"/api/v1/sessions/{first}/context", headers=headers).json()["visual_lesson"]["visual_key"] == "fractions-equivalent"
    assert client.get(f"/api/v1/sessions/{second}/context", headers=headers).json()["visual_lesson"] is None
    first_context = client.get(f"/api/v1/sessions/{first}/context", headers=headers).json()
    second_context = client.get(f"/api/v1/sessions/{second}/context", headers=headers).json()
    assert [item["content"] for item in first_context["messages"]] == ["First session question"]
    assert [item["content"] for item in second_context["messages"]] == ["Second session question"]


def test_visual_context_ownership_validation_and_graph_selection(client):
    owner = login(client, "visual-owner@example.com")
    other = login(client, "visual-other@example.com")
    session_id = create_session(client, owner, "Graph algorithms")
    path = f"/api/v1/sessions/{session_id}/visual-context"
    payload = {"visual_key": "dijkstra-shortest-path", "start_node": "A", "end_node": "F"}
    assert client.put(path, json=payload).status_code == 401
    assert client.put(path, headers=other, json=payload).status_code == 404
    assert client.put(path, headers=owner, json={"visual_key": "unknown"}).status_code == 422
    assert client.put(path, headers=owner, json={**payload, "start_node": "X"}).status_code == 422
    assert client.put(path, headers=owner, json={**payload, "unexpected": "prompt"}).status_code == 422
    saved = client.put(path, headers=owner, json=payload)
    assert saved.status_code == 200, saved.text
    assert saved.json()["concept"] == "Shortest path from A to F"


def test_visual_context_is_added_to_only_its_gemini_session(client, monkeypatch):
    headers = login(client, "visual-tutor@example.com")
    first = create_session(client, headers, "Fractions")
    second = create_session(client, headers, "Fractions")
    saved = client.put(f"/api/v1/sessions/{first}/visual-context", headers=headers, json={"visual_key": "fractions-equivalent"})
    assert saved.status_code == 200
    calls = []

    def fake_tutor(instruction, history):
        calls.append((instruction, history))
        return "One half is the same amount in each bar."

    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", fake_tutor)
    first_reply = client.post(f"/api/v1/tutor/sessions/{first}/chat", headers=headers, json={"message": "Explain this diagram"})
    second_reply = client.post(f"/api/v1/tutor/sessions/{second}/chat", headers=headers, json={"message": "Explain this diagram"})
    assert first_reply.status_code == second_reply.status_code == 200
    assert "Equivalent Fractions" in calls[0][0]
    assert "1/2 = 2/4 = 4/8" in calls[0][0]
    assert "not an image supplied to you" in calls[0][0]
    assert "Equivalent Fractions" not in calls[1][0]
    assert LANGUAGE_GUIDANCE["mixed"] in calls[0][0]
    assert calls[0][1][-1] == {"role": "user", "content": "Explain this diagram"}


def test_existing_chat_and_session_contracts_remain_compatible(client, monkeypatch):
    headers = login(client, "context-compat@example.com")
    session_id = create_session(client, headers)
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda *_args: "A whole split into two equal parts.")
    response = client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=headers, json={"message": "What is one half?"})
    assert response.status_code == 200
    assert set(response.json()) == {"session_id", "reply", "language", "learning_level"}
    messages = client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers)
    assert [(item["role"], item["content"]) for item in messages.json()] == [
        ("user", "What is one half?"), ("assistant", "A whole split into two equal parts."),
    ]
    context = client.get(f"/api/v1/sessions/{session_id}/context", headers=headers).json()
    assert [(item["role"], item["content"]) for item in context["messages"]] == [
        (item["role"], item["content"]) for item in messages.json()
    ]
