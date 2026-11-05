"""BE-09 progress tests with isolated SQLite."""
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
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()

def auth(client, email):
    password = "safe-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}

def test_progress_is_updated_only_by_objective_assessments(client):
    headers = auth(client, "one@example.com")
    url = "/api/v1/progress"
    created = client.put(url, headers=headers, json={"topic": "  Fractions  ", "mastery_score": 100, "attempts": 99})
    assert created.status_code == 405
    assert client.get(url, headers=headers).json() == []
    session = client.post("/api/v1/sessions", headers=headers, json={"topic": "  Fractions  "}).json()
    issued = client.post(f"/api/v1/tutor/sessions/{session['id']}/assessments", headers=headers)
    assert issued.status_code == 201, issued.text
    assert "expected_answer" not in issued.json()
    answer = issued.json()["choices"].keys().__iter__().__next__()
    scored = client.post(f"/api/v1/tutor/sessions/{session['id']}/assessments/{issued.json()['assessment_id']}/answer", headers=headers, json={"answer": answer})
    assert scored.status_code == 200, scored.text
    assert len(client.get(url, headers=headers).json()) == 1
    row = client.get(url + "/fractions", headers=headers).json()
    assert row["evidence_count"] == 1
    assert row["mastery_score"] in {35, 60}

def test_progress_student_isolation(client):
    first = auth(client, "first@example.com")
    second = auth(client, "second@example.com")
    url = "/api/v1/progress"
    session = client.post("/api/v1/sessions", headers=first, json={"topic": "Fractions"}).json()
    issued = client.post(f"/api/v1/tutor/sessions/{session['id']}/assessments", headers=first).json()
    client.post(f"/api/v1/tutor/sessions/{session['id']}/assessments/{issued['assessment_id']}/answer", headers=first, json={"answer": "unsure"})
    assert client.get(url, headers=second).json() == []
    assert client.get(url + "/Fractions", headers=second).status_code == 404
    assert client.get(url).status_code == 401
    assert client.put(url, json={"topic": "A", "mastery_score": 20, "attempts": 1}).status_code == 401

def test_progress_validation(client):
    headers = auth(client, "valid@example.com")
    url = "/api/v1/progress"
    for payload in [
        {"topic": " ", "mastery_score": 10, "attempts": 1},
        {"topic": "A", "mastery_score": 101, "attempts": 1},
        {"topic": "A", "mastery_score": -1, "attempts": 1},
        {"topic": "A", "mastery_score": 20, "attempts": -1},
    ]:
        assert client.put(url, headers=headers, json=payload).status_code == 405
    assert client.get(url + "?limit=0", headers=headers).status_code == 422
    assert client.get(url + "/missing", headers=headers).status_code == 404
