"""Deterministic evidence, adaptation, ownership, and cross-session memory tests."""
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.models import LearningProgress
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.adaptive_learning import (
    choose_adaptation,
    mastery_category,
    normalize_topic,
    record_scored_outcome,
)


@pytest.fixture
def adaptive_client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "adaptive-test-secret-long-enough-for-tests-2026")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'adaptive.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def register(client: TestClient, email: str) -> dict[str, str]:
    password = "safe-adaptive-test-password-123"
    created = client.post("/api/v1/auth/register", json={"email": email, "display_name": "Learner", "password": password})
    assert created.status_code == 201, created.text
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_session(client: TestClient, headers: dict[str, str], topic: str = "Fractions") -> str:
    response = client.post("/api/v1/sessions", headers=headers, json={"topic": topic})
    assert response.status_code == 201, response.text
    return response.json()["id"]


def issue(client: TestClient, headers: dict[str, str], session_id: str) -> dict:
    response = client.post(f"/api/v1/tutor/sessions/{session_id}/assessments", headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def answer(client: TestClient, headers: dict[str, str], session_id: str, assessment_id: str, choice: str):
    return client.post(
        f"/api/v1/tutor/sessions/{session_id}/assessments/{assessment_id}/answer",
        headers=headers,
        json={"answer": choice},
    )


def test_normalization_unknown_evidence_and_bounded_mastery():
    display, key = normalize_topic("  \uFF26ractions   Basics ")
    assert display == "\uFF26ractions Basics"
    assert key == "fractions basics"
    progress = LearningProgress(student_id="student", topic="Fractions", mastery_score=0, attempts=0, evidence_count=0, correct_attempts=0, incorrect_attempts=0, correct_streak=0)
    assert mastery_category(progress) == "not_assessed"
    adaptation = choose_adaptation(progress, [], "intermediate")
    assert adaptation.mastery_score is None
    assert adaptation.teaching_strategy == "diagnostic_question"
    for _ in range(12):
        record_scored_outcome(progress, "correct")
    assert progress.mastery_score == 100
    assert progress.correct_streak == 12
    assert mastery_category(progress) == "demonstrated_proficiency"
    for _ in range(12):
        record_scored_outcome(progress, "incorrect")
    assert progress.mastery_score == 0
    assert progress.correct_streak == 0


def test_one_correct_is_not_mastery_and_repeated_mistakes_change_strategy():
    progress = LearningProgress(student_id="student", topic="Fractions", mastery_score=0, attempts=0, evidence_count=0, correct_attempts=0, incorrect_attempts=0, correct_streak=0)
    record_scored_outcome(progress, "correct")
    assert mastery_category(progress) == "developing"
    assert choose_adaptation(progress, [], "beginner").teaching_strategy != "challenge_practice"

    wrong = SimpleNamespace(outcome="incorrect", misconception_code="denominator_only")
    record_scored_outcome(progress, "incorrect")
    progress.mastery_score = 20
    repeated = choose_adaptation(progress, [wrong, wrong], "intermediate")
    assert repeated.teaching_strategy == "prerequisite_review"
    assert repeated.recommended_difficulty == "beginner"
    progress.evidence_count = 4
    progress.mastery_score = 90
    progress.correct_streak = 3
    challenge = choose_adaptation(progress, [SimpleNamespace(outcome="correct", misconception_code=None)], "beginner")
    assert challenge.mastery_category == "demonstrated_proficiency"
    assert challenge.teaching_strategy == "challenge_practice"

    resolved_history = [
        SimpleNamespace(outcome="correct", misconception_code=None),
        SimpleNamespace(outcome="correct", misconception_code=None),
        SimpleNamespace(outcome="correct", misconception_code=None),
        wrong,
    ]
    resolved = choose_adaptation(progress, resolved_history, "beginner")
    assert resolved.misconception_codes == ()
    assert resolved.teaching_strategy == "challenge_practice"


def test_assessment_answer_is_hidden_and_duplicate_retry_is_idempotent(adaptive_client):
    headers = register(adaptive_client, "idempotent@example.com")
    session_id = create_session(adaptive_client, headers)
    first = issue(adaptive_client, headers, session_id)
    assert "expected_answer" not in first
    assert first["question"]
    assert set(first["choices"]) == {"A", "B", "C", "D"}
    assert answer(adaptive_client, headers, session_id, first["assessment_id"], "Z").status_code == 422

    scored = answer(adaptive_client, headers, session_id, first["assessment_id"], "A")
    assert scored.status_code == 200, scored.text
    assert scored.json()["outcome"] == "correct"  # first question's A option is 2/6
    assert scored.json()["mastery_score"] == 60
    retry = answer(adaptive_client, headers, session_id, first["assessment_id"], "A")
    assert retry.status_code == 200 and retry.json() == scored.json()
    progress = adaptive_client.get("/api/v1/progress/fractions", headers=headers).json()
    assert progress["evidence_count"] == progress["attempts"] == 1
    assert progress["correct_attempts"] == 1
    assert answer(adaptive_client, headers, session_id, first["assessment_id"], "B").status_code == 409
    assert adaptive_client.get("/api/v1/progress/fractions", headers=headers).json()["evidence_count"] == 1


def test_uncertain_answer_and_normal_chat_do_not_change_mastery(adaptive_client, monkeypatch):
    headers = register(adaptive_client, "uncertain@example.com")
    session_id = create_session(adaptive_client, headers)
    first = issue(adaptive_client, headers, session_id)
    result = answer(adaptive_client, headers, session_id, first["assessment_id"], "unsure")
    assert result.status_code == 200 and result.json()["outcome"] == "ambiguous"
    before = adaptive_client.get("/api/v1/progress/fractions", headers=headers).json()
    assert before["evidence_count"] == 0 and before["mastery_score"] is None

    calls = []
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda instruction, history: calls.append(instruction) or "A helpful explanation")
    chat = adaptive_client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=headers, json={"message": "What is a fraction?"})
    assert chat.status_code == 200
    after = adaptive_client.get("/api/v1/progress/fractions", headers=headers).json()
    assert after["evidence_count"] == 0 and after["mastery_score"] is None
    assert "validated objective evidence" in calls[0]
    assert "not_assessed" in calls[0]


def test_cross_session_memory_and_adaptive_context_are_student_scoped(adaptive_client, monkeypatch):
    owner = register(adaptive_client, "owner-memory@example.com")
    other = register(adaptive_client, "other-memory@example.com")
    first_session = create_session(adaptive_client, owner, "Fractions")
    first = issue(adaptive_client, owner, first_session)
    # Sequence 0, B is a denominator-only misconception for 1/3.
    failed = answer(adaptive_client, owner, first_session, first["assessment_id"], "B")
    assert failed.status_code == 200 and failed.json()["outcome"] == "incorrect"
    assert failed.json()["mastery_score"] == 35

    next_session = create_session(adaptive_client, owner, " fractions ")
    second = issue(adaptive_client, owner, next_session)
    assert second["topic"] == "fractions"
    calls = []
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda instruction, history: calls.append((instruction, history)) or "Simpler explanation")
    reply = adaptive_client.post(f"/api/v1/tutor/sessions/{next_session}/chat", headers=owner, json={"message": "Explain it another way"})
    assert reply.status_code == 200
    assert "misconception_review" in calls[0][0]
    assert "denominator_only" in calls[0][0]
    assert "fractions" in calls[0][0]

    summary = adaptive_client.get("/api/v1/progress/summary", headers=owner)
    assert summary.status_code == 200
    assert len(summary.json()["topics"]) == 1
    assert summary.json()["topics"][0]["evidence_count"] == 1
    assert "expected_answer" not in summary.json()["recent_evidence"][0]
    assert adaptive_client.get("/api/v1/progress/summary", headers=other).json() == {"topics": [], "recent_evidence": []}
    assert adaptive_client.get(f"/api/v1/progress/{'fractions'}", headers=other).status_code == 404
    assert adaptive_client.post(f"/api/v1/tutor/sessions/{next_session}/assessments", headers=other).status_code == 404


def test_language_specific_assessment_and_authentication(adaptive_client):
    headers = register(adaptive_client, "telugu-practice@example.com")
    adaptive_client.put("/api/v1/students/me/preferences", headers=headers, json={"preferred_language": "telugu", "learning_level": "beginner"})
    session_id = create_session(adaptive_client, headers)
    question = issue(adaptive_client, headers, session_id)
    assert question["language"] == "telugu"
    assert question["question"]
    assert adaptive_client.get("/api/v1/progress/summary").status_code == 401
    assert adaptive_client.post(f"/api/v1/tutor/sessions/{session_id}/assessments").status_code == 401


def test_visual_visit_does_not_score_and_context_reaches_existing_tutor(adaptive_client, monkeypatch):
    headers = register(adaptive_client, "visual-progress@example.com")
    session_id = create_session(adaptive_client, headers)
    saved = adaptive_client.put(f"/api/v1/sessions/{session_id}/visual-context", headers=headers, json={"visual_key": "fractions-equivalent"})
    assert saved.status_code == 200
    before = adaptive_client.get("/api/v1/progress/summary", headers=headers).json()["topics"][0]
    assert before["mastery_score"] is None and before["evidence_count"] == 0
    captured = []
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda instruction, history: captured.append(instruction) or "Here is the diagram explained.")
    reply = adaptive_client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=headers, json={"message": "Explain this diagram"})
    assert reply.status_code == 200
    assert "Equivalent Fractions" in captured[0]
    assert "not an image supplied" in captured[0]
    after = adaptive_client.get("/api/v1/progress/summary", headers=headers).json()["topics"][0]
    assert after["mastery_score"] is None and after["evidence_count"] == 0


def test_provider_failure_does_not_change_learning_memory(adaptive_client, monkeypatch):
    from fastapi import HTTPException

    headers = register(adaptive_client, "failed-tutor@example.com")
    session_id = create_session(adaptive_client, headers)
    issued = issue(adaptive_client, headers, session_id)
    scored = answer(adaptive_client, headers, session_id, issued["assessment_id"], "B")
    assert scored.status_code == 200
    before = adaptive_client.get("/api/v1/progress/fractions", headers=headers).json()
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda *_: (_ for _ in ()).throw(HTTPException(status_code=502, detail="provider failed")))
    failed = adaptive_client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=headers, json={"message": "Explain"})
    assert failed.status_code == 502
    after = adaptive_client.get("/api/v1/progress/fractions", headers=headers).json()
    assert after["evidence_count"] == before["evidence_count"]
    assert after["mastery_score"] == before["mastery_score"]
    assert adaptive_client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers).json() == []


def test_unsupported_topic_does_not_create_progress(adaptive_client):
    headers = register(adaptive_client, "unsupported@example.com")
    session_id = create_session(adaptive_client, headers, "Open ended conversation")
    response = adaptive_client.post(f"/api/v1/tutor/sessions/{session_id}/assessments", headers=headers)
    assert response.status_code == 422
    assert adaptive_client.get("/api/v1/progress", headers=headers).json() == []
