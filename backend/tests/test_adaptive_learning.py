"""INT-05 assessment, evidence, ownership, and idempotency tests."""
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
    engine = create_engine(f"sqlite:///{(tmp_path / 'int05.db').as_posix()}", connect_args={"check_same_thread": False})
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
    assert client.post("/api/v1/auth/register", json={
        "email": email, "display_name": "Learner", "password": password
    }).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def create_session(client, headers, topic="Equivalent Fractions"):
    response = client.post("/api/v1/sessions", headers=headers, json={"topic": topic, "language": "mixed"})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def issue(client, headers, session_id):
    response = client.post(f"/api/v1/assessments/sessions/{session_id}/issue", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def answer(client, headers, attempt_id, value):
    return client.post(f"/api/v1/assessments/{attempt_id}/answer", headers=headers, json={"answer": value})


def test_only_objective_submissions_change_mastery(client):
    headers = auth(client, "evidence@example.com")
    session_id = create_session(client, headers)
    question = issue(client, headers, session_id)
    result = answer(client, headers, question["attempt_id"], question["options"][0])
    assert result.status_code == 200
    progress = client.get("/api/v1/progress", headers=headers).json()
    assert len(progress) == 1
    assert progress[0]["evidence_attempts"] == 1
    assert progress[0]["mastery_score"] in (0, 100)


def test_ambiguous_answer_does_not_change_mastery(client):
    headers = auth(client, "ambiguous@example.com")
    session_id = create_session(client, headers)
    question = issue(client, headers, session_id)
    result = answer(client, headers, question["attempt_id"], "I am not sure")
    assert result.status_code == 200
    assert result.json()["ambiguous"] is True
    assert result.json()["mastery_score"] is None
    progress = client.get("/api/v1/progress", headers=headers).json()[0]
    assert progress["evidence_attempts"] == 0
    assert progress["ambiguous_attempts"] == 1
    assert progress["evidence_status"] == "unassessed"


def test_answer_retry_is_idempotent_and_conflicting_retry_is_rejected(client):
    headers = auth(client, "retry@example.com")
    session_id = create_session(client, headers)
    question = issue(client, headers, session_id)
    first = answer(client, headers, question["attempt_id"], question["options"][0])
    retry = answer(client, headers, question["attempt_id"], question["options"][0])
    conflict = answer(client, headers, question["attempt_id"], question["options"][1])
    assert first.status_code == 200
    assert retry.status_code == 200 and retry.json()["replayed"] is True
    assert conflict.status_code == 409
    progress = client.get("/api/v1/progress", headers=headers).json()[0]
    assert progress["evidence_attempts"] == 1


def test_assessment_and_progress_are_student_owned(client):
    first = auth(client, "first-int05@example.com")
    second = auth(client, "second-int05@example.com")
    session_id = create_session(client, first)
    question = issue(client, first, session_id)
    assert answer(client, second, question["attempt_id"], "2/4").status_code == 404
    assert client.get("/api/v1/progress", headers=second).json() == []
    assert client.get("/api/v1/progress", headers=first).status_code == 200


def test_unsupported_topic_stays_unassessed(client):
    headers = auth(client, "unsupported@example.com")
    session_id = create_session(client, headers, "Photosynthesis")
    response = client.post(f"/api/v1/assessments/sessions/{session_id}/issue", headers=headers)
    assert response.status_code == 422
    assert client.get("/api/v1/progress", headers=headers).json() == []
