"""Career planner ownership, skill evidence, and deterministic dependency tests."""
from datetime import date, timedelta
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
    completed = client.post(f"/api/v1/career/goals/{goal['id']}/lessons/{lesson['id']}/complete", headers=headers)
    assert completed.status_code == 200
    assert next(item for item in completed.json()["phases"] if item["lesson_id"] == lesson["id"])["lesson_completed"] is True
    assert next(item for item in completed.json()["skill_gaps"] if item["skill_key"] == "python")["status"] == "self_reported"


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


def test_weekly_target_tracking_replans_after_a_missed_week(client):
    first, second = auth(client, "weekly-one@example.com"), auth(client, "weekly-two@example.com")
    goal = create_goal(client, first).json()
    monday = date.today() - timedelta(days=date.today().weekday() + 7)
    path = f"/api/v1/career/goals/{goal['id']}/weekly-progress"
    payload = {"week_start": monday.isoformat(), "studied_minutes": 60}
    assert client.put(path, headers=second, json=payload).status_code == 404
    update = client.put(path, headers=first, json=payload)
    assert update.status_code == 200 and update.json()["status"] == "below_target"
    plan = client.post(f"/api/v1/career/goals/{goal['id']}/replan", headers=first).json()
    assert plan["study_adjustment"]["state"] == "missed_last_week"
    assert plan["study_adjustment"]["previous_studied_minutes"] == 60
    assert sum(day["minutes"] for day in plan["weekly_plan"]) == 60


def test_validation_and_ownership_responses(client):
    headers = auth(client, "validation-career@example.com")
    assert create_goal(client, headers, career_key="invented").status_code == 422
    assert create_goal(client, headers, weekly_minutes=0).status_code == 422
    assert create_goal(client, headers, career_key="custom").status_code == 422
    custom = create_goal(client, headers, career_key="custom", custom_goal="Learn robotics foundations")
    assert custom.status_code == 201 and custom.json()["career_title"] == "Learn robotics foundations"
    assert client.put("/api/v1/career/skills", headers=headers, json=[{"skill_key": "not-real", "proficiency": "advanced"}]).status_code == 422
    assert client.post("/api/v1/career/goals/missing/roadmap", headers=headers).status_code == 404


def test_future_seeker_profile_planning_capacity_and_version_history(client):
    headers = auth(client, "future-seeker@example.com")
    goal = create_goal(client, headers, field_of_study="Computer science", daily_minutes=60,
                       study_days_per_week=5, weekly_minutes=300, learning_format="practice",
                       timeframe_weeks=20, constraints=["shared computer"]).json()
    assert goal["field_of_study"] == "Computer science"
    assert goal["learning_format"] == "practice" and goal["timeframe_weeks"] == 20
    first = client.post(f"/api/v1/career/goals/{goal['id']}/roadmap", headers=headers).json()
    assert first["version_number"] == 1
    assert len(first["weekly_plan"]) == 5
    assert sum(day["minutes"] for day in first["weekly_plan"]) == 300
    assert max(day["minutes"] for day in first["weekly_plan"]) <= 60
    assert next(item for item in first["phases"] if item["skill_key"] == "python")["resources"][0]["url"].startswith("https://")

    changed = {"career_key": "ai-engineer", "education_level": "beginner", "field_of_study": "Computer science",
               "interests": ["AI"], "constraints": ["shared computer"], "weekly_minutes": 300,
               "daily_minutes": 60, "study_days_per_week": 5, "learning_format": "practice",
               "timeframe_weeks": 20, "preferred_language": "mixed", "target_date": None}
    assert client.put(f"/api/v1/career/goals/{goal['id']}", headers=headers, json=changed).status_code == 409
    changed["confirm_major_change"] = True
    assert client.put(f"/api/v1/career/goals/{goal['id']}", headers=headers, json=changed).status_code == 200
    second = client.post(f"/api/v1/career/goals/{goal['id']}/roadmap", headers=headers).json()
    assert second["version_number"] == 2 and second["career_title"] == "AI engineer"
    history = client.get(f"/api/v1/career/goals/{goal['id']}/versions", headers=headers).json()
    assert [item["version_number"] for item in history] == [2, 1]
    assert client.get(f"/api/v1/career/goals/{goal['id']}/versions/1", headers=headers).json()["career_title"] == "Software developer"
    other = auth(client, "future-seeker-other@example.com")
    assert client.get(f"/api/v1/career/goals/{goal['id']}/versions", headers=other).status_code == 404
    assert client.get(f"/api/v1/career/goals/{goal['id']}/versions/1", headers=other).status_code == 404


def test_weekly_plan_respects_selected_days_and_daily_capacity(client):
    headers = auth(client, "capacity@example.com")
    goal = create_goal(client, headers, weekly_minutes=180, daily_minutes=60,
                       study_days_per_week=3, timeframe_weeks=8).json()
    plan = client.post(f"/api/v1/career/goals/{goal['id']}/roadmap", headers=headers).json()
    assert [day["day"] for day in plan["weekly_plan"]] == ["Monday", "Tuesday", "Wednesday"]
    assert sum(day["minutes"] for day in plan["weekly_plan"]) == 180
    assert all(day["minutes"] <= 60 for day in plan["weekly_plan"])


def test_assessment_history_is_authenticated_and_student_scoped(client):
    headers = auth(client, "career-history@example.com")
    goal = create_goal(client, headers).json()
    assert client.get(f"/api/v1/career/goals/{goal['id']}/assessments", headers=headers).json() == []
    assert client.get(f"/api/v1/career/goals/{goal['id']}/assessments").status_code == 401


def test_saved_resources_are_curated_idempotent_and_student_scoped(client):
    owner, other = auth(client, "saved-resource-owner@example.com"), auth(client, "saved-resource-other@example.com")
    goal = create_goal(client, owner).json()
    plan = client.post(f"/api/v1/career/goals/{goal['id']}/roadmap", headers=owner).json()
    resource_url = next(phase["resources"][0]["url"] for phase in plan["phases"] if phase["resources"])
    path = f"/api/v1/career/goals/{goal['id']}/saved-resources"
    assert client.post(path, headers=owner, json={"resource_url": "https://untrusted.example/course"}).status_code == 404
    saved = client.post(path, headers=owner, json={"resource_url": resource_url})
    assert saved.status_code == 201
    assert client.post(path, headers=owner, json={"resource_url": resource_url}).json()["id"] == saved.json()["id"]
    assert client.get(path, headers=owner).json() == [saved.json()]
    assert client.get(path, headers=other).status_code == 404
    assert client.delete(f"{path}/{saved.json()['id']}", headers=other).status_code == 404
    assert client.delete(f"{path}/{saved.json()['id']}", headers=owner).status_code == 204
    assert client.get(path, headers=owner).json() == []


def test_gemini_skill_analysis_is_schema_validated_and_student_scoped(client, monkeypatch):
    from backend.app.services import career_ai
    headers = auth(client, "career-analysis@example.com")
    goal = create_goal(client, headers).json()
    valid = {"summary_en": "Start with foundations, then practise each new concept.",
             "summary_te": "తెలుగులో దశలవారీగా నేర్చుకొని సాధన చేయండి.",
             "advice": [{"skill_key": key, "priority": 2, "estimated_hours": 8,
                         "explanation_en": f"Build a solid foundation in {key} before moving on.",
                         "explanation_te": f"{key} నైపుణ్యాన్ని సాధనతో అభివృద్ధి చేయండి.",
                         "next_step_en": f"Practise one small {key} exercise.",
                         "next_step_te": f"{key} పై చిన్న సాధన చేయండి."}
                        for key in ["digital-literacy", "programming-basics", "python", "problem-solving", "version-control", "communication", "portfolio", "interview-prep"]]}
    monkeypatch.setattr(career_ai, "generate_tutor_reply", lambda *_: __import__("json").dumps(valid, ensure_ascii=False))
    result = client.post(f"/api/v1/career/goals/{goal['id']}/analysis", headers=headers)
    assert result.status_code == 200 and result.json()["provider"] == "gemini"
    assert len(result.json()["advice"]) == 8
    assert client.get(f"/api/v1/career/goals/{goal['id']}/analysis", headers=headers).json() == result.json()
    other = auth(client, "career-analysis-other@example.com")
    assert client.get(f"/api/v1/career/goals/{goal['id']}/analysis", headers=other).status_code == 404
    valid["advice"][-1]["skill_key"] = "python"
    assert client.post(f"/api/v1/career/goals/{goal['id']}/analysis", headers=headers).status_code == 502
    assert client.post(f"/api/v1/career/goals/{goal['id']}/analysis").status_code == 401


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
