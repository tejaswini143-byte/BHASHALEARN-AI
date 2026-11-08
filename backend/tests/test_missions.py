"""Mission Mode API behavior using isolated per-test SQLite databases."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import MissionCompletion
from backend.app.db.session import get_db
from backend.app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "test-only-secret-key-please-never-use-in-production-123")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'missions.db').as_posix()}", connect_args={"check_same_thread": False})
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


def answer_correct_questions(client, headers, topic, count):
    session = client.post("/api/v1/sessions", headers=headers, json={"topic": topic}).json()
    for _ in range(count):
        issued = client.post(f"/api/v1/assessments/sessions/{session['id']}/issue", headers=headers)
        assert issued.status_code == 201, issued.text
        answer = issued.json()["options"][0]
        question_id = issued.json()["question_id"]
        if question_id == "dijkstra-01":
            answer = "C"
        elif question_id == "dijkstra-02":
            answer = "4"
        elif question_id == "dijkstra-03":
            answer = "3"
        result = client.post(f"/api/v1/assessments/{issued.json()['attempt_id']}/answer", headers=headers,
                             json={"answer": answer})
        assert result.status_code == 200 and result.json()["is_correct"] is True, result.text


def test_mission_completion_xp_level_and_duplicate_request(client):
    headers = auth(client, "mission-one@example.com")
    initial = client.get("/api/v1/missions", headers=headers)
    assert initial.status_code == 200
    assert [(item["subject"], item["target"]) for item in initial.json()["missions"][:2]] == [
        ("Mathematics", 3), ("Computer Science", 3),
    ]
    assert initial.json()["xp"] == 0 and initial.json()["level"] == 1
    assert client.post("/api/v1/missions/quest-fractions/claim", headers=headers).status_code == 409

    answer_correct_questions(client, headers, "Equivalent Fractions", 3)
    ready = client.get("/api/v1/missions", headers=headers).json()
    fraction_mission = next(item for item in ready["missions"] if item["id"] == "quest-fractions")
    assert fraction_mission["progress"] == 3 and fraction_mission["eligible"] is True

    claimed = client.post("/api/v1/missions/quest-fractions/claim", headers=headers)
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["xp_awarded"] == 60
    assert claimed.json()["total_xp"] == 60 and claimed.json()["level"] == 1
    assert claimed.json()["replayed"] is False
    assert "60 XP" in claimed.json()["feedback"]

    retry = client.post("/api/v1/missions/quest-fractions/claim", headers=headers)
    assert retry.status_code == 200
    assert retry.json()["xp_awarded"] == 0 and retry.json()["total_xp"] == 60
    assert retry.json()["replayed"] is True
    assert "already claimed" in retry.json()["feedback"]

    answer_correct_questions(client, headers, "Dijkstra Shortest Path", 3)
    path_claim = client.post("/api/v1/missions/quest-pathfinder/claim", headers=headers)
    assert path_claim.json()["total_xp"] == 135 and path_claim.json()["level"] == 2
    assert path_claim.json()["mission"]["xp_reward"] == 75
    assert path_claim.json()["mission"]["completed"] is True
    assert next(item for item in client.get("/api/v1/missions", headers=headers).json()["missions"] if item["id"] == "quest-pathfinder")["completed"]


def test_missions_require_auth_and_progress_is_student_owned(client):
    owner = auth(client, "mission-owner@example.com")
    other = auth(client, "mission-other@example.com")
    assert client.get("/api/v1/missions").status_code == 401
    answer_correct_questions(client, owner, "Equivalent Fractions", 3)
    claimed = client.post("/api/v1/missions/quest-fractions/claim", headers=owner)
    assert claimed.status_code == 200
    other_state = client.get("/api/v1/missions", headers=other).json()
    assert other_state["xp"] == 0 and other_state["level"] == 1 and other_state["badges"] == []
    other_mission = next(item for item in other_state["missions"] if item["id"] == "quest-fractions")
    assert other_mission["progress"] == 0 and not other_mission["completed"]
    assert client.post("/api/v1/missions/quest-fractions/claim", headers=other).status_code == 409
    assert client.post("/api/v1/missions/unknown/claim", headers=owner).status_code == 404


def test_daily_challenge_is_utc_day_scoped_and_badges_are_deterministic(client):
    headers = auth(client, "mission-daily@example.com")
    daily = next(item for item in client.get("/api/v1/missions", headers=headers).json()["missions"] if item["daily"])
    assert daily["active_date"] == datetime.now(timezone.utc).date().isoformat()
    topic = "Equivalent Fractions" if daily["subject"] == "Mathematics" else "Dijkstra Shortest Path"
    answer_correct_questions(client, headers, topic, 1)
    ready = next(item for item in client.get("/api/v1/missions", headers=headers).json()["missions"] if item["daily"])
    assert ready["progress"] == 1 and ready["eligible"] is True
    claim = client.post(f"/api/v1/missions/{daily['id']}/claim", headers=headers)
    assert claim.json()["xp_awarded"] == 25 and claim.json()["total_xp"] == 25
    assert "First Steps" in client.get("/api/v1/missions", headers=headers).json()["badges"]
