"""Progress analytics API and aggregation tests on isolated SQLite databases."""
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import (
    LearningAssessmentAttempt,
    LearningProgress,
    LearningSession,
    MissionCompletion,
    Student,
)
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.progress_analytics import build_analytics
from backend.app.services.quiz_analytics import QuizAttemptEvidence, scored_outcome

UTC = timezone.utc


@pytest.fixture
def analytics_app(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "analytics-test-only-secret-key-never-use-in-production-123")
    get_settings.cache_clear()
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'analytics-disposable.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client, factory
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def _auth(client, email):
    password = "safe-test-password-123"
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Analytics learner", "password": password},
    )
    assert response.status_code == 201, response.text
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return response.json()["id"], {"Authorization": "Bearer " + token}


def _seed_fraction_evidence(factory, student_id, now):
    with factory() as db:
        session = LearningSession(student_id=student_id, topic="Equivalent Fractions", language="english",
                                  created_at=now - timedelta(days=1))
        db.add(session)
        db.flush()
        outcomes = (True, True, True, False)
        for index, outcome in enumerate(outcomes):
            db.add(LearningAssessmentAttempt(
                student_id=student_id, session_id=session.id, topic="Equivalent Fractions",
                normalized_topic_key="equivalent fractions", question_id="fraction-01",
                prompt="Private prompt", options_json='["A", "B"]', expected_answer="A",
                idempotency_key=f"attempt-{index}", submitted_answer="A" if outcome else "B",
                is_correct=outcome, feedback="Private feedback",
                issued_at=now - timedelta(days=1, minutes=2),
                answered_at=now - timedelta(days=1, minutes=1-index),
            ))
        # A legacy issued attempt is incomplete and is not a completed activity.
        db.add(LearningAssessmentAttempt(
            student_id=student_id, session_id=session.id, topic="Equivalent Fractions",
            normalized_topic_key="equivalent fractions", question_id="fraction-pending",
            prompt="Private prompt", options_json="[]", expected_answer="A",
            idempotency_key="attempt-pending", issued_at=now,
        ))
        db.add(LearningProgress(
            student_id=student_id, topic="Equivalent Fractions",
            normalized_topic_key="equivalent fractions", mastery_score=75, attempts=4,
            evidence_attempts=4, correct_attempts=3, incorrect_attempts=1,
            ambiguous_attempts=0, evidence_status="assessed",
            last_assessed_at=now - timedelta(days=1),
        ))
        db.add_all([
            MissionCompletion(student_id=student_id, mission_id="quest-fractions", xp_awarded=60,
                              completed_at=now - timedelta(days=1)),
            MissionCompletion(student_id=student_id, mission_id="quest-pathfinder", xp_awarded=75,
                              completed_at=now),
        ])
        db.commit()


def test_analytics_requires_auth_and_ignores_client_student_id(analytics_app):
    client, factory = analytics_app
    owner_id, owner_headers = _auth(client, "analytics-owner@example.com")
    other_id, other_headers = _auth(client, "analytics-other@example.com")
    now = datetime.now(UTC)
    _seed_fraction_evidence(factory, owner_id, now)

    assert client.get("/api/v1/analytics").status_code == 401
    owner = client.get("/api/v1/analytics?range_days=7", headers=owner_headers)
    assert owner.status_code == 200, owner.text
    result = owner.json()
    assert result["overview"]["learning_sessions"] == 1
    assert result["overview"]["completed_assessments"] == 4
    assert result["overview"]["completed_activities"] == 6
    assert result["overview"]["learning_time_minutes"] is None
    assert result["mission"]["xp"] == 135
    assert result["mission"]["level"] == 2
    assert result["mission"]["completed_missions"] == 2
    assert result["mission"]["badges"] == ["First Steps"]
    assert result["topics"][0]["mastery_score"] == 75.0
    assert result["subjects"] == [{"subject": "Mathematics", "mastery_score": 75.0, "scored_attempts": 4}]
    assert result["streak"]["days"] == 2
    assert "Private prompt" not in owner.text and "Private feedback" not in owner.text

    isolated = client.get(
        "/api/v1/analytics?range_days=7&student_id=" + owner_id,
        headers=other_headers,
    )
    assert isolated.status_code == 200, isolated.text
    assert isolated.json()["overview"]["learning_sessions"] == 0
    assert isolated.json()["mission"]["xp"] == 0
    assert isolated.json()["topics"] == []
    assert len(isolated.json()["trend"]) == 7
    assert isolated.json()["recommendations"][0]["topic"] is None
    assert client.get("/api/v1/analytics?range_days=14", headers=owner_headers).status_code == 422


def test_analytics_uses_inclusive_utc_day_boundaries_and_unique_streak_days(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'utc-window.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    start = datetime(2025, 1, 10, tzinfo=UTC)
    with factory() as db:
        student = Student(email="utc@example.com", display_name="UTC learner")
        db.add(student)
        db.flush()
        db.add_all([
            LearningSession(student_id=student.id, topic="Before range", language="english",
                            created_at=datetime(2025, 1, 2, 23, 59, tzinfo=UTC)),
            LearningSession(student_id=student.id, topic="First day", language="english",
                            created_at=datetime(2025, 1, 4, 0, 0, tzinfo=UTC)),
            LearningSession(student_id=student.id, topic="Last instant", language="english",
                            created_at=datetime(2025, 1, 10, 23, 59, tzinfo=UTC)),
            LearningSession(student_id=student.id, topic="Outside end", language="english",
                            created_at=datetime(2025, 1, 11, 0, 0, tzinfo=UTC)),
        ])
        db.commit()
        result = build_analytics(db, student.id, 7, now=start)
        assert result["range_totals"]["sessions"] == 2
        assert result["trend"][0]["date"] == "2025-01-04"
        assert result["trend"][0]["activity_count"] == 1
        assert result["trend"][-1]["date"] == "2025-01-10"
        assert result["trend"][-1]["activity_count"] == 1
        assert result["streak"]["days"] == 1
    engine.dispose()


def test_new_student_has_explicit_empty_metrics_and_unknown_topics_are_other(analytics_app):
    client, _factory = analytics_app
    _student_id, headers = _auth(client, "analytics-new@example.com")
    response = client.get("/api/v1/analytics?range_days=30", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["overview"]["learning_sessions"] == 0
    assert data["overview"]["completed_activities"] == 0
    assert data["overview"]["learning_time_status"] == "not_recorded"
    assert data["topics"] == []
    assert data["subjects"] == []
    assert data["trend"][0]["date"] < data["trend"][-1]["date"]
    assert len(data["trend"]) == 30


def test_analytics_includes_only_completed_student_owned_int13_quizzes(analytics_app):
    client, factory = analytics_app
    owner_id, owner_headers = _auth(client, "quiz-analytics-owner@example.com")
    other_id, other_headers = _auth(client, "quiz-analytics-other@example.com")
    now = datetime.now(UTC)

    with factory() as db:
        for student_id, quiz_id, correct_values in (
            (owner_id, "quiz-owner", (True, False)),
            (other_id, "quiz-other", (True, True)),
        ):
            session = LearningSession(student_id=student_id, topic="Plants", language="english")
            db.add(session)
            db.flush()
            for position, correct in enumerate(correct_values, 1):
                db.add(LearningAssessmentAttempt(
                    student_id=student_id, session_id=session.id, topic="Plants",
                    normalized_topic_key="plants", question_id=f"int13:{quiz_id}:{position}",
                    prompt="Private quiz prompt", options_json=f'{{"quiz_id":"{quiz_id}","position":{position}}}',
                    expected_answer="A", idempotency_key=f"{quiz_id}-{position}",
                    submitted_answer="A" if correct else "B", is_correct=correct,
                    issued_at=now, answered_at=now,
                ))
            if student_id == owner_id:
                # An answered fragment without position 2 is not a completed quiz.
                db.add(LearningAssessmentAttempt(
                    student_id=student_id, session_id=session.id, topic="Plants",
                    normalized_topic_key="plants", question_id="int13:quiz-incomplete:1",
                    prompt="Private fragment", options_json='{"quiz_id":"quiz-incomplete","position":1}',
                    expected_answer="A", idempotency_key="quiz-incomplete-1",
                    submitted_answer="A", is_correct=True, issued_at=now, answered_at=now,
                ))
        db.commit()

    owner = client.get("/api/v1/analytics?range_days=7", headers=owner_headers)
    assert owner.status_code == 200, owner.text
    assert owner.json()["quiz_analytics"] == {
        "available": True,
        "completed_quizzes": 1,
        "completed_questions": 2,
        "average_score": 50.0,
        "integration": "INT-13 student-owned completed quiz attempts",
    }
    assert owner.json()["range_totals"]["completed_quizzes"] == 1
    assert "Private quiz prompt" not in owner.text

    other = client.get("/api/v1/analytics?range_days=7", headers=other_headers)
    assert other.status_code == 200, other.text
    assert other.json()["quiz_analytics"]["completed_quizzes"] == 1
    assert other.json()["quiz_analytics"]["average_score"] == 100.0
    assert "quiz-owner" not in other.text


def test_timeline_is_bounded_and_quiz_seam_accepts_only_valid_scored_results(tmp_path):
    engine = create_engine(f"sqlite:///{(tmp_path / 'bounded-analytics.db').as_posix()}")
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    now = datetime.now(UTC)
    with factory() as db:
        student = Student(email="bounded@example.com", display_name="Bounded learner")
        db.add(student)
        db.flush()
        db.add_all([
            LearningSession(student_id=student.id, topic="Recorded session " + str(index), language="english",
                            created_at=now - timedelta(minutes=index))
            for index in range(18)
        ])
        db.commit()
        result = build_analytics(db, student.id, 7, now=now)
        assert len(result["recent_activity"]) == 12
    engine.dispose()

    valid = QuizAttemptEvidence("quiz-1", "student-1", "Science", "Plants", now, 8, 10)
    invalid = QuizAttemptEvidence("quiz-2", "student-1", "Science", "Plants", now, 11, 10)
    assert scored_outcome(valid) == (8, 10)
    assert scored_outcome(invalid) is None
