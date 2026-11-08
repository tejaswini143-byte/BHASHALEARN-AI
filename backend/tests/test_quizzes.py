"""Adaptive quiz API tests use one isolated SQLite database per test."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import LearningAssessmentAttempt, MissionCompletion
from backend.app.db.session import get_db
from backend.app.main import create_app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "quiz-only-test-secret-key-never-use-in-production-456")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'int13.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client, factory
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def auth(client, email):
    password = "safe-quiz-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def create_quiz(client, headers, **overrides):
    payload = {"topic": "Equivalent Fractions", "language": "english", "question_count": 2, **overrides}
    response = client.post("/api/v1/quizzes", headers=headers, json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def expected_answer(question):
    return {
        "fractions-01": "2/4", "fractions-02": "6/8", "fractions-03": "4/6",
        "fractions-tf-01": "True", "fractions-blank-01": "3/6", "fractions-short-01": "4/10",
        "dijkstra-01": "C", "dijkstra-02": "4", "dijkstra-03": "3",
        "dijkstra-tf-01": "True", "dijkstra-blank-01": "4", "dijkstra-short-01": "3",
    }[question["question_id"]]


def test_quizzes_require_auth_and_catalog_is_limited_to_supported_topics(client):
    api, _ = client
    assert api.get("/api/v1/quizzes/catalog").status_code == 401
    headers = auth(api, "quiz-catalog@example.com")
    catalog = api.get("/api/v1/quizzes/catalog", headers=headers)
    assert catalog.status_code == 200
    assert {entry["subject"] for entry in catalog.json()} == {"Mathematics", "Computer Science"}
    assert api.post("/api/v1/quizzes", headers=headers, json={"topic": "unsupported photosynthesis"}).status_code == 422


def test_question_payload_hides_answer_keys_until_submission(client):
    api, factory = client
    headers = auth(api, "quiz-privacy@example.com")
    quiz = create_quiz(api, headers, language="mixed")
    assert quiz["adaptive_difficulty"] is True
    assert quiz["source"] in {"curated", "deterministic_fallback", "mixed"}
    for question in quiz["questions"]:
        assert "answer" not in question and "correct_answer" not in question and "explanation" not in question
    retrieved = api.get(f"/api/v1/quizzes/{quiz['quiz_id']}", headers=headers)
    assert retrieved.status_code == 200 and len(retrieved.json()["questions"]) == len(quiz["questions"])
    assert all("correct_answer" not in question for question in retrieved.json()["questions"])
    with factory() as db:
        rows = db.scalars(select(LearningAssessmentAttempt).where(LearningAssessmentAttempt.student_id == api.get("/api/v1/auth/me", headers=headers).json()["id"])).all()
        assert all(row.expected_answer for row in rows)
        assert all("explanation" not in row.prompt.casefold() for row in rows)


def test_deterministic_grading_history_mastery_and_idempotent_retry(client):
    api, _ = client
    headers = auth(api, "quiz-grade@example.com")
    quiz = create_quiz(api, headers)
    answers = [{"attempt_id": question["attempt_id"], "answer": expected_answer(question)} for question in quiz["questions"]]
    submitted = api.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", headers=headers, json={"answers": answers})
    assert submitted.status_code == 200, submitted.text
    result = submitted.json()
    assert result["completed"] and result["score"] == 2 and result["mastery_score"] == 100
    assert all(row["is_correct"] is True and row["explanation"] for row in result["questions"])
    retry = api.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", headers=headers, json={"answers": answers})
    assert retry.status_code == 200 and retry.json()["replayed"] is True
    changed = [dict(answers[0], answer="wrong"), answers[1]]
    assert api.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", headers=headers, json={"answers": changed}).status_code == 409
    history = api.get("/api/v1/quizzes/history", headers=headers)
    assert history.status_code == 200 and len(history.json()) == 1
    assert history.json()[0]["score"] == 2
    assert api.get(f"/api/v1/quizzes/{quiz['quiz_id']}/results", headers=headers).json()["score"] == 2
    progress = api.get("/api/v1/progress", headers=headers).json()
    assert progress[0]["evidence_attempts"] == 2 and progress[0]["mastery_score"] == 100


def test_attempts_are_student_owned_and_answers_must_match_quiz_state(client):
    api, _ = client
    owner = auth(api, "quiz-owner@example.com")
    other = auth(api, "quiz-other@example.com")
    quiz = create_quiz(api, owner)
    assert api.get(f"/api/v1/quizzes/{quiz['quiz_id']}/results", headers=other).status_code == 404
    assert api.get("/api/v1/quizzes/history", headers=other).json() == []
    first = quiz["questions"][0]
    if first["type"] == "multiple_choice":
        invalid = "not an available choice"
    else:
        invalid = ""
    answers = [{"attempt_id": q["attempt_id"], "answer": expected_answer(q)} for q in quiz["questions"]]
    assert api.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", headers=owner,
                    json={"answers": answers[:1]}).status_code == 422
    assert api.get(f"/api/v1/quizzes/{quiz['quiz_id']}/results", headers=owner).status_code == 409
    assert api.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", headers=owner,
                    json={"answers": answers}).status_code == 200
    assert api.get(f"/api/v1/quizzes/{quiz['quiz_id']}/results", headers=other).status_code == 404


def test_question_types_language_and_strict_short_answer_grading(client):
    api, _ = client
    headers = auth(api, "quiz-types@example.com")
    for language in ("english", "telugu", "mixed"):
        quiz = create_quiz(api, headers, topic="Dijkstra Shortest Path", language=language,
                           difficulty="advanced", question_count=2)
        assert quiz["language"] == language
        assert any(question["type"] == "short_answer" for question in quiz["questions"])
        wrong = [{"attempt_id": question["attempt_id"],
                  "answer": (question["options"][0] if question["options"][0].casefold() != expected_answer(question).casefold()
                             else question["options"][1]) if question["options"] else "The route looks short"}
                 for question in quiz["questions"]]
        result = api.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", headers=headers, json={"answers": wrong})
        assert result.status_code == 200 and result.json()["score"] == 0
        assert all(row["is_correct"] is False for row in result.json()["questions"])
        if language == "telugu":
            assert any("\u0c00" <= char <= "\u0c7f" for char in result.json()["topic_recommendation"])


def test_adaptation_uses_scored_performance_and_xp_remains_separate(client):
    api, factory = client
    headers = auth(api, "quiz-adaptive@example.com")
    first = create_quiz(api, headers, question_count=2)
    correct = [{"attempt_id": question["attempt_id"], "answer": expected_answer(question)} for question in first["questions"]]
    assert api.post(f"/api/v1/quizzes/{first['quiz_id']}/submit", headers=headers, json={"answers": correct}).status_code == 200
    second = create_quiz(api, headers, question_count=1)
    second_answer = [{"attempt_id": q["attempt_id"], "answer": expected_answer(q)} for q in second["questions"]]
    api.post(f"/api/v1/quizzes/{second['quiz_id']}/submit", headers=headers, json={"answers": second_answer})
    third = create_quiz(api, headers, question_count=1)
    assert third["difficulty"] == "intermediate"
    with factory() as db:
        assert db.scalars(select(MissionCompletion)).all() == []
    mission = api.get("/api/v1/missions", headers=headers).json()
    assert mission["xp"] == 0


def test_invalid_choice_does_not_partially_score_quiz(client):
    api, _ = client
    headers = auth(api, "quiz-invalid@example.com")
    quiz = create_quiz(api, headers, difficulty="beginner", question_count=2)
    answers = [{"attempt_id": q["attempt_id"], "answer": "not a choice" if q["type"] in {"multiple_choice", "true_false"} else expected_answer(q)}
               for q in quiz["questions"]]
    response = api.post(f"/api/v1/quizzes/{quiz['quiz_id']}/submit", headers=headers, json={"answers": answers})
    assert response.status_code == 422
    assert api.get("/api/v1/quizzes/history", headers=headers).json()[0]["completed"] is False
