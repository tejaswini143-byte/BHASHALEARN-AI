"""Career planner ownership, skill evidence, and deterministic dependency tests."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.career_roadmap import SKILLS, skill_gaps, topological_skills


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "career-test-secret-key-never-for-production-123456")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'career.db').as_posix()}", connect_args={"check_same_thread": False})
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
    password = "safe-career-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def create_goal(client, headers, **overrides):
    data = {"career_key": "software-developer", "education_level": "beginner", "interests": ["apps", "problem solving"], "weekly_minutes": 300, "preferred_language": "mixed"}
    data.update(overrides)
    return client.post("/api/v1/career/goals", json=data, headers=headers)


def test_goal_catalog_and_roadmap_are_bilingual_and_catalog_grounded(client):
    headers = auth(client, "planner@example.com")
    course = client.post("/api/v1/courses", json={"title": "Python basics"}, headers=headers).json()
    lesson = client.post(f"/api/v1/courses/{course['id']}/lessons", json={"title": "Python variables", "content": "Values", "position": 1}, headers=headers).json()
    goal = create_goal(client, headers, preferred_language="telugu").json()
    assert goal["career_title"] == "Software developer"
    profile = client.put("/api/v1/career/skills", headers=headers, json=[{"skill_key": "python", "proficiency": "advanced"}])
    assert profile.json()["evidence_type"] == "self_reported_only"
    roadmap = client.post(f"/api/v1/career/goals/{goal['id']}/roadmap", headers=headers).json()
    python = next(item for item in roadmap["phases"] if item["skill_key"] == "python")
    assert python["course_id"] == course["id"] and python["lesson_id"] == lesson["id"]
    assert roadmap["summary_te"] and roadmap["summary"]
    assert next(item for item in roadmap["skill_gaps"] if item["skill_key"] == "python")["status"] == "self_reported"
    assert all(item["course_id"] is None or item["course_id"] in {course["id"]} for item in roadmap["phases"])
    assert next(item for item in roadmap["phases"] if item["skill_key"] == "programming-basics")["assessment_topic"] == "dijkstra shortest path"
    assert next(item for item in roadmap["phases"] if item["skill_key"] == "python")["assessment_topic"] is None


def test_student_isolation_milestone_idempotency_and_replanning(client):
    first, second = auth(client, "first-career@example.com"), auth(client, "second-career@example.com")
    goal = create_goal(client, first).json()
    roadmap = client.post(f"/api/v1/career/goals/{goal['id']}/roadmap", headers=first).json()
    milestone = roadmap["phases"][0]["milestone_id"]
    assert client.get(f"/api/v1/career/goals/{goal['id']}/roadmap", headers=second).status_code == 404
    valid = {"career_key": "software-developer", "education_level": "beginner", "interests": [], "weekly_minutes": 300, "preferred_language": "mixed"}
    assert client.put(f"/api/v1/career/goals/{goal['id']}", headers=second, json=valid).status_code == 404
    one = client.post(f"/api/v1/career/goals/{goal['id']}/milestones/{milestone}/complete", headers=first)
    two = client.post(f"/api/v1/career/goals/{goal['id']}/milestones/{milestone}/complete", headers=first)
    assert one.status_code == two.status_code == 200
    assert one.json()["progress"]["completed_milestones"] == 1
    replanned = client.post(f"/api/v1/career/goals/{goal['id']}/replan", headers=first).json()
    assert next(item for item in replanned["phases"] if item["milestone_id"] == milestone)["completed"] is True
    assert client.get("/api/v1/career/goals", headers=second).json() == []
    assert client.get("/api/v1/career/recommendations").status_code == 401


def test_validation_and_ownership_responses(client):
    headers = auth(client, "validation-career@example.com")
    assert create_goal(client, headers, career_key="invented").status_code == 422
    assert create_goal(client, headers, weekly_minutes=0).status_code == 422
    assert create_goal(client, headers, career_key="custom").status_code == 422
    custom = create_goal(client, headers, career_key="custom", custom_goal="Learn robotics foundations")
    assert custom.status_code == 201 and custom.json()["career_title"] == "Learn robotics foundations"
    assert client.put("/api/v1/career/skills", headers=headers, json=[{"skill_key": "not-real", "proficiency": "advanced"}]).status_code == 422
    assert client.post("/api/v1/career/goals/missing/roadmap", headers=headers).status_code == 404


def test_skill_gap_states_separate_reported_from_assessed():
    rows = skill_gaps(["digital-literacy", "programming-basics", "python"],
                      [{"skill_key": "programming-basics", "proficiency": "advanced"}, {"skill_key": "python", "proficiency": "unknown"}],
                      {"digital-literacy"})
    assert rows[0]["status"] == "already_demonstrated" and rows[0]["verified"] is True
    assert rows[1]["status"] == "self_reported" and rows[1]["verified"] is False
    assert rows[2]["status"] == "needs_assessment" and rows[2]["verified"] is False


def test_prerequisite_order_is_unique_and_cycle_checked(monkeypatch):
    ordered = topological_skills(["javascript", "html-css"])
    assert len(ordered) == len(set(ordered))
    assert ordered.index("web-basics") < ordered.index("html-css")
    monkeypatch.setitem(SKILLS["digital-literacy"], "prerequisites", ["programming-basics"])
    with pytest.raises(ValueError, match="cycle"):
        topological_skills(["programming-basics"])
