"""INT-05 live tutor adaptation and Gemini transport contract tests."""
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import create_app


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "BHASHALEARN_JWT_SECRET_KEY",
        "int05-test-secret-key-with-more-than-32-characters",
    )
    get_settings.cache_clear()
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'adaptive-tutor.db').as_posix()}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    return TestClient(app), engine


def _auth(client, email):
    password = "safe-test-password-123"
    assert client.post(
        "/api/v1/auth/register",
        json={"email": email, "display_name": "Learner", "password": password},
    ).status_code == 201
    token = client.post(
        "/api/v1/auth/login", json={"email": email, "password": password}
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_tutor_receives_assessment_evidence_and_saved_topic_memory(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    try:
        with client:
            headers = _auth(client, "adaptive-context@example.com")
            session = client.post(
                "/api/v1/sessions",
                headers=headers,
                json={"topic": "Equivalent Fractions", "language": "mixed"},
            ).json()
            session_id = session["id"]

            memory = client.post(
                "/api/v1/memories",
                headers=headers,
                json={"topic": "Equivalent Fractions", "note": "Needs visual fraction examples"},
            )
            assert memory.status_code == 201

            issued = client.post(
                f"/api/v1/assessments/sessions/{session_id}/issue",
                headers=headers,
            )
            assert issued.status_code == 201
            question = issued.json()
            wrong_option = next(
                option for option in question["options"]
                if option != "2/4"
            )
            submitted = client.post(
                f"/api/v1/assessments/{question['attempt_id']}/answer",
                headers=headers,
                json={"answer": wrong_option},
            )
            assert submitted.status_code == 200
            assert submitted.json()["is_correct"] is False

            captured = {}

            def mock_provider(instruction, history):
                captured["instruction"] = instruction
                captured["history"] = history
                return "Let's practise with a picture."

            monkeypatch.setattr(
                "backend.app.api.tutor.generate_tutor_reply",
                mock_provider,
            )
            response = client.post(
                f"/api/v1/tutor/sessions/{session_id}/chat",
                headers=headers,
                json={"message": "Can you explain this more simply?"},
            )
            assert response.status_code == 200, response.text
            instruction = captured["instruction"]
            assert "LEARNING EVIDENCE" in instruction
            assert "1 scored answers" in instruction
            assert "0 correct" in instruction
            assert "1 incorrect" in instruction
            assert "Needs visual fraction examples" in instruction
            assert "Suggested teaching strategy:" in instruction
            assert "Next step:" in instruction
    finally:
        client.close()
        engine.dispose()
        get_settings.cache_clear()


def test_tutor_instruction_includes_selected_learning_pace(tmp_path, monkeypatch):
    client, engine = _client(tmp_path, monkeypatch)
    try:
        with client:
            headers = _auth(client, "pace-context@example.com")
            session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Fractions", "language": "mixed"}).json()
            assert client.put("/api/v1/students/me/preferences", headers=headers, json={
                "preferred_language": "mixed", "learning_level": "beginner", "learning_pace": "slow", "learning_goal": None,
            }).status_code == 200
            captured = {"instructions": []}
            def record_instruction(instruction, history):
                captured["instructions"].append(instruction)
                return "Okay"
            monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", record_instruction)
            response = client.post(f"/api/v1/tutor/sessions/{session['id']}/chat", headers=headers, json={"message": "Help me"})
            assert response.status_code == 200, response.text
            assert "Learning pace: Use one idea at a time" in captured["instructions"][-1]
    finally:
        client.close(); engine.dispose(); get_settings.cache_clear()


def test_tutor_context_uses_recent_outcomes_and_missing_progress_fallback(tmp_path, monkeypatch):
    from datetime import datetime, timedelta, timezone
    from backend.app.db.models import LearningAssessmentAttempt, LearningProgress
    from backend.app.services.adaptive_learning import normalize_topic

    client, engine = _client(tmp_path, monkeypatch)
    try:
        with client:
            headers = _auth(client, "recent-context@example.com")
            session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Fractions", "language": "mixed"}).json()
            with engine.begin() as connection:
                student_id = connection.exec_driver_sql("SELECT id FROM students WHERE email = 'recent-context@example.com'").scalar_one()
            now = datetime.now(timezone.utc)
            with engine.begin() as connection:
                connection.execute(LearningProgress.__table__.insert().values(
                    student_id=student_id, topic="Fractions", normalized_topic_key=normalize_topic("Fractions"),
                    evidence_attempts=5, correct_attempts=5, incorrect_attempts=0, mastery_score=100,
                    updated_at=now,
                ))
                for i, correct in enumerate((True, False, False)):
                    connection.execute(LearningAssessmentAttempt.__table__.insert().values(
                        student_id=student_id, session_id=session["id"], topic="Fractions",
                        normalized_topic_key=normalize_topic("Fractions"), is_correct=correct,
                        question_id=f"q-{i}", prompt="Which fraction is equivalent?", options_json='["1/2","2/4"]',
                        expected_answer="2/4", idempotency_key=f"recent-{i}",
                        answered_at=now + timedelta(seconds=i), issued_at=now + timedelta(seconds=i),
                    ))
            captured = {"instructions": []}
            def record_instruction(instruction, history):
                captured["instructions"].append(instruction)
                return "Okay"
            monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", record_instruction)
            response = client.post(f"/api/v1/tutor/sessions/{session['id']}/chat", headers=headers, json={"message": "Help me"})
            assert response.status_code == 200, response.text
            prompt = captured["instructions"][-1]
            assert "Recent scored outcomes for this topic (oldest to newest): correct, incorrect, incorrect" in prompt
            assert "Suggested teaching strategy: hinted_practice" in prompt

            other_session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Geometry", "language": "mixed"}).json()
            response = client.post(f"/api/v1/tutor/sessions/{other_session['id']}/chat", headers=headers, json={"message": "Start"})
            assert response.status_code == 200
            assert "No scored progress is available for this topic" in captured["instructions"][-1]
    finally:
        client.close(); engine.dispose(); get_settings.cache_clear()


def test_tutor_context_is_isolated_between_students(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from backend.app.db.models import LearningAssessmentAttempt, LearningMemory, LearningProgress
    from backend.app.services.adaptive_learning import normalize_topic

    client, engine = _client(tmp_path, monkeypatch)
    try:
        with client:
            headers = _auth(client, "owner-context@example.com")
            other_headers = _auth(client, "other-context@example.com")
            session = client.post("/api/v1/sessions", headers=headers, json={"topic": "Algebra", "language": "mixed"}).json()
            other_session = client.post("/api/v1/sessions", headers=other_headers, json={"topic": "Algebra", "language": "mixed"}).json()
            with engine.begin() as connection:
                owner_id, other_id = connection.exec_driver_sql("SELECT id FROM students WHERE email = 'owner-context@example.com'").scalar_one(), connection.exec_driver_sql("SELECT id FROM students WHERE email = 'other-context@example.com'").scalar_one()
                now = datetime.now(timezone.utc)
                connection.execute(LearningProgress.__table__.insert().values(student_id=other_id, topic="Algebra", normalized_topic_key=normalize_topic("Algebra"), evidence_attempts=9, correct_attempts=9, incorrect_attempts=0, mastery_score=100, updated_at=now))
                connection.execute(LearningMemory.__table__.insert().values(student_id=other_id, topic="Algebra", note="FOREIGN STUDENT PRIVATE MARKER", created_at=now))
                connection.execute(LearningAssessmentAttempt.__table__.insert().values(
                    student_id=other_id, session_id=other_session["id"], topic="Algebra",
                    normalized_topic_key=normalize_topic("Algebra"), is_correct=False,
                    question_id="foreign-q", prompt="Private assessment", options_json='["x","y"]',
                    expected_answer="x", idempotency_key="foreign-history", answered_at=now, issued_at=now,
                ))
            captured = {}
            monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda instruction, history: captured.setdefault("instruction", instruction) or "Okay")
            response = client.post(f"/api/v1/tutor/sessions/{session['id']}/chat", headers=headers, json={"message": "Help"})
            assert response.status_code == 200
            prompt = captured["instruction"]
            assert "No scored progress is available for this topic" in prompt
            assert "FOREIGN STUDENT PRIVATE MARKER" not in prompt
            assert "9 scored answers" not in prompt
            assert "Recent scored outcomes for this topic" not in prompt
            assert owner_id != other_id
    finally:
        client.close(); engine.dispose(); get_settings.cache_clear()


def test_gemini_transport_sends_system_instruction_and_parses_text(monkeypatch):
    from backend.app.services import tutor

    captured = {}
    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "నమస్తే"}, {"text": "!"}]}}]}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, url, headers, json):
            captured.update({"url": url, "headers": headers, "body": json})
            return FakeResponse()

    monkeypatch.setattr(tutor, "get_settings", lambda: SimpleNamespace(
        gemini_api_key="test-api-key",
        gemini_model="gemini-test-model",
    ))
    monkeypatch.setattr(tutor.httpx, "Client", FakeClient)

    reply = tutor.generate_tutor_reply(
        "Teach in Telugu and adapt to beginner level.",
        [{"role": "user", "content": "Explain halves"}],
    )

    assert reply == "నమస్తే!"
    assert captured["timeout"] == 30.0
    assert captured["url"].endswith("/models/gemini-test-model:generateContent")
    assert captured["headers"] == {"x-goog-api-key": "test-api-key"}
    assert captured["body"]["systemInstruction"]["parts"][0]["text"].startswith("Teach in Telugu")
    assert captured["body"]["contents"] == [
        {"role": "user", "parts": [{"text": "Explain halves"}]}
    ]


def test_gemini_provider_http_failure_is_safely_reported(monkeypatch):
    import httpx
    import pytest
    from fastapi import HTTPException
    from backend.app.services import tutor

    class FakeClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def post(self, *_args, **_kwargs):
            request = httpx.Request("POST", "https://example.invalid")
            response = httpx.Response(503, request=request)
            raise httpx.HTTPStatusError("provider unavailable", request=request, response=response)

    monkeypatch.setattr(tutor, "get_settings", lambda: SimpleNamespace(
        gemini_api_key="test-api-key",
        gemini_model="gemini-test-model",
    ))
    monkeypatch.setattr(tutor.httpx, "Client", FakeClient)

    with pytest.raises(HTTPException) as error:
        tutor.generate_tutor_reply("instruction", [{"role": "user", "content": "hello"}])
    assert error.value.status_code == 502
    assert error.value.detail == "Gemini provider unavailable; retry later or check provider status."
