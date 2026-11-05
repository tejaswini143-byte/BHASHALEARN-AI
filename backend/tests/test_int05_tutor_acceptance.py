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
    assert error.value.detail == "AI provider unavailable or returned an invalid response"
