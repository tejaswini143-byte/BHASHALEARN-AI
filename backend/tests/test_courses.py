"""BE-05 course and lesson API tests using isolated SQLite."""
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
    engine = create_engine(f"sqlite:///{(tmp_path / 'courses.db').as_posix()}", connect_args={"check_same_thread": False})
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


def auth(client):
    email, password = "author@example.com", "safe-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Author", "password": password}).status_code == 201
    login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200
    return {"Authorization": "Bearer " + login.json()["access_token"]}


def test_course_catalog_and_filter(client):
    headers = auth(client)
    assert client.post("/api/v1/courses", json={"title": "  Telugu Basics  ", "language": "telugu"}, headers=headers).status_code == 201
    assert client.post("/api/v1/courses", json={"title": "English Basics", "language": "english"}, headers=headers).status_code == 201
    assert len(client.get("/api/v1/courses").json()) == 2
    result = client.get("/api/v1/courses?language=telugu").json()
    assert len(result) == 1 and result[0]["title"] == "Telugu Basics"
    assert len(client.get("/api/v1/courses?limit=1&offset=1").json()) == 1
    assert client.get("/api/v1/courses?limit=0").status_code == 422


def test_course_and_ordered_lessons(client):
    headers = auth(client)
    course = client.post("/api/v1/courses", json={"title": "Fractions"}, headers=headers).json()
    course_id = course["id"]
    assert client.get(f"/api/v1/courses/{course_id}").status_code == 200
    base = f"/api/v1/courses/{course_id}/lessons"
    for position in (2, 1):
        response = client.post(base, json={"title": f"Lesson {position}", "content": "Example", "position": position}, headers=headers)
        assert response.status_code == 201, response.text
    lessons = client.get(base).json()
    assert [x["position"] for x in lessons] == [1, 2]
    assert client.get(f"{base}/{lessons[0]['id']}").json()["title"] == "Lesson 1"
    assert client.post(base, json={"title": "Duplicate", "content": "Example", "position": 1}, headers=headers).status_code == 409


def test_auth_validation_and_missing_resources(client):
    assert client.post("/api/v1/courses", json={"title": "Unauthorized"}).status_code == 401
    headers = auth(client)
    assert client.post("/api/v1/courses", json={"title": "   "}, headers=headers).status_code == 422
    assert client.post("/api/v1/courses", json={"title": "Bad", "language": "french"}, headers=headers).status_code == 422
    assert client.get("/api/v1/courses/unknown").status_code == 404
    assert client.get("/api/v1/courses/unknown/lessons").status_code == 404
    assert client.post("/api/v1/courses/unknown/lessons", json={"title": "One", "content": "X", "position": 1}, headers=headers).status_code == 404
    assert client.get("/api/v1/courses/unknown/lessons/unknown").status_code == 404


def test_in_app_catalog_enrollment_progress_and_student_isolation(client):
    first = auth(client)
    listed = client.get("/api/v1/courses/catalog", headers=first)
    assert listed.status_code == 200
    item = next(course for course in listed.json() if course["id"] == "fraction-foundations")
    assert item["lessons_count"] == 3 and item["enrolled"] is False

    detail_url = "/api/v1/courses/catalog/fraction-foundations"
    assert client.post(detail_url + "/lessons/equivalent-fractions/complete", headers=first).status_code == 409
    enrolled = client.post(detail_url + "/enroll", headers=first)
    assert enrolled.status_code == 200 and enrolled.json()["enrolled"] is True
    complete = client.post(detail_url + "/lessons/equivalent-fractions/complete", headers=first)
    assert complete.status_code == 200
    assert complete.json()["completed_lesson_ids"] == ["equivalent-fractions"]
    assert complete.json()["progress_percent"] == 33
    assert client.get(detail_url, headers=first).json()["progress_percent"] == 33
    assert client.post(detail_url + "/lessons/not-a-lesson/complete", headers=first).status_code == 404
    assert client.get(detail_url).status_code == 401

    email, password = "second@example.com", "safe-test-password-456"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Second", "password": password}).status_code == 201
    second_login = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    second = {"Authorization": "Bearer " + second_login.json()["access_token"]}
    private_view = client.get(detail_url, headers=second).json()
    assert private_view["enrolled"] is False and private_view["completed_lesson_ids"] == []
