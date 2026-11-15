"""Auth, ownership, availability and consent gates for production LiveKit routes."""
from datetime import datetime, timedelta, timezone
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import AssistantDeadline, AssistantLiveKitSession, new_id
from backend.app.db.session import get_db
from backend.app.main import create_app


@pytest.fixture
def livekit_env(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "test-only-secret-key-never-use-in-production-123")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'livekit-integration.db').as_posix()}",
                           connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()
    def override_db():
        with factory() as db: yield db
    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client: yield client, factory
    app.dependency_overrides.clear(); engine.dispose(); get_settings.cache_clear()


def register(client, email):
    password = "integration-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Student", "password": password}).status_code == 201
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_livekit_status_requires_product_login_and_reports_missing_configuration(livekit_env, monkeypatch):
    from backend.app.api import assistant_livekit as assistant_livekit_api
    client, _ = livekit_env
    monkeypatch.setattr(assistant_livekit_api, "blockers", lambda: ["BHASHALEARN_LIVEKIT_URL"])
    assert client.get("/api/v1/assistant/livekit/status").status_code == 401
    headers = register(client, "livekit-status@example.com")
    response = client.get("/api/v1/assistant/livekit/status", headers=headers)
    assert response.status_code == 200
    assert response.json() == {"available": False, "provider_mode": "unconfigured", "missing": ["BHASHALEARN_LIVEKIT_URL"]}


def test_livekit_session_is_owned_by_authenticated_student(livekit_env):
    client, factory = livekit_env
    owner = register(client, "livekit-owner@example.com")
    other = register(client, "livekit-other@example.com")
    with factory.begin() as db:
        deadline = AssistantDeadline(id=new_id(), student_id=client.get("/api/v1/auth/me", headers=owner).json()["id"],
            title="Exam", due_at=datetime.now(timezone.utc) + timedelta(days=2), timezone_name="Asia/Kolkata",
            priority="normal", category="exam", status="upcoming", source="manual", dedupe_key=new_id())
        session = AssistantLiveKitSession(id=new_id(), student_id=deadline.student_id, deadline_id=deadline.id,
            room_name="test-private-room", language="te", status="dispatched")
        db.add_all([deadline, session])
    response = client.post(f"/api/v1/assistant/livekit-sessions/{session.id}/close", headers=other)
    assert response.status_code == 404
    assert client.get("/api/v1/assistant/livekit-sessions", headers=other).json() == []
    assert client.get("/api/v1/assistant/livekit-sessions", headers=owner).json()[0]["id"] == session.id


def test_sip_call_requires_explicit_confirmation(livekit_env):
    client, _ = livekit_env
    headers = register(client, "livekit-confirm@example.com")
    response = client.post("/api/v1/assistant/deadlines/not-used/sip-call", headers=headers,
                           json={"explicit_confirmation": False})
    assert response.status_code == 400
