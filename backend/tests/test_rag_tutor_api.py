"""Authenticated chat boundary tests with mocked DB, retrieval, and generation."""
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from backend.app.api import tutor as tutor_api
from backend.app.config import Settings
from backend.app.db.models import LearningSession, Student
from backend.app.db.session import get_db
from backend.app.main import create_app
from backend.app.services.embeddings import EmbeddingError


class FakeRows:
    def all(self):
        return []


class FakeDb:
    def __init__(self, *, owner_id="student-1", scalars=(None, "ready-doc")):
        self.owner_id = owner_id
        self.scalar_values = list(scalars)
        self.added = []
        self.commits = 0
        self.rollbacks = 0

    def get(self, model, _key):
        if model is LearningSession:
            return SimpleNamespace(
                id="session-1", student_id=self.owner_id, topic="Fractions", language="mixed"
            )
        return None

    def scalar(self, _statement):
        return self.scalar_values.pop(0) if self.scalar_values else None

    def scalars(self, _statement):
        return FakeRows()

    def add_all(self, values):
        self.added.extend(values)

    def commit(self):
        self.commits += 1

    def rollback(self):
        self.rollbacks += 1


class FakeEmbeddingProvider:
    model = "gemini-embedding-001"

    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def embed_texts(self, texts, *, task_type):
        self.calls.append((texts, task_type))
        if self.error:
            raise self.error
        return [[0.5, 0.5]]


def call_chat(
    db,
    provider,
    monkeypatch,
    *,
    generated_text="A half is one of two equal parts. [S1]",
    hits=None,
    generator=None,
    language=None,
):
    if generator is None:
        monkeypatch.setattr(
            tutor_api,
            "generate_tutor_reply",
            lambda _instruction, _history: generated_text,
        )
    else:
        monkeypatch.setattr(tutor_api, "generate_tutor_reply", generator)
    monkeypatch.setattr(
        "backend.app.services.rag_tutor.search_documents",
        lambda *_args, **_kwargs: list(hits or []),
    )
    student = Student(id="student-1", email="student@example.test", display_name="Learner")
    return tutor_api.tutor_chat(
        "session-1",
        tutor_api.TutorRequest(message="What is one half?", language=language),
        student,
        db,
        provider,
    )


def source_hit():
    return {
        "chunk_id": "chunk-1",
        "document_id": "doc-1",
        "document_name": "Fractions lesson.pdf",
        "page_number": 2,
        "ordinal": 0,
        "content": "A half is one of two equal parts.",
        "score": 0.91,
    }


def test_chat_endpoint_requires_bearer_authentication():
    app = create_app(Settings(jwt_secret_key="test-only-secret-key-long-enough-for-auth"))

    def fake_db():
        yield FakeDb()

    app.dependency_overrides[get_db] = fake_db
    try:
        with TestClient(app) as client:
            response = client.post(
                "/api/v1/tutor/sessions/session-1/chat",
                json={"message": "Explain a half"},
            )
        assert response.status_code == 401
    finally:
        app.dependency_overrides.clear()


def test_chat_returns_structured_citation_and_persists_complete_turn(monkeypatch):
    db = FakeDb()
    provider = FakeEmbeddingProvider()

    response = call_chat(db, provider, monkeypatch, hits=[source_hit()])

    assert response.grounded is True
    assert response.retrieval_used is True
    assert response.citations[0].citation_id == "S1"
    assert response.citations[0].document_id == "doc-1"
    assert response.citations[0].document_title == "Fractions lesson.pdf"
    assert response.citations[0].page_number == 2
    assert "[S1]" in response.reply
    assert [item.role for item in db.added] == ["user", "assistant"]
    assert db.commits == 1
    assert provider.calls == [(["What is one half?"], "RETRIEVAL_QUERY")]


def test_explicit_response_language_overrides_session_language(monkeypatch):
    captured = {}

    def generate(instruction, _history):
        captured["instruction"] = instruction
        return "సమాధానం"

    response = call_chat(
        FakeDb(), FakeEmbeddingProvider(), monkeypatch, language="telugu",
        generator=generate,
    )
    assert response.language == "telugu"
    assert "Telugu Unicode script" in captured["instruction"]


def test_foreign_session_stops_before_retrieval_or_persistence(monkeypatch):
    db = FakeDb(owner_id="student-2")
    provider = FakeEmbeddingProvider()
    monkeypatch.setattr(
        "backend.app.services.rag_tutor.search_documents",
        lambda *_args, **_kwargs: pytest.fail("retrieval must not run for a foreign session"),
    )

    with pytest.raises(HTTPException) as error:
        call_chat(db, provider, monkeypatch)

    assert error.value.status_code == 404
    assert provider.calls == []
    assert db.added == [] and db.commits == 0


def test_embedding_failure_saves_no_chat_turn(monkeypatch):
    db = FakeDb()
    provider = FakeEmbeddingProvider(EmbeddingError("safe embedding failure", 503))

    with pytest.raises(HTTPException) as error:
        call_chat(db, provider, monkeypatch)

    assert error.value.status_code == 503
    assert db.added == [] and db.commits == 0


def test_generation_failure_saves_no_chat_turn(monkeypatch):
    db = FakeDb()
    provider = FakeEmbeddingProvider()
    monkeypatch.setattr(
        "backend.app.api.tutor.generate_tutor_reply",
        lambda *_args: (_ for _ in ()).throw(HTTPException(502, "provider unavailable")),
    )
    monkeypatch.setattr(
        "backend.app.services.rag_tutor.search_documents",
        lambda *_args, **_kwargs: [source_hit()],
    )

    with pytest.raises(HTTPException) as error:
        tutor_api.tutor_chat(
            "session-1", tutor_api.TutorRequest(message="What is one half?"),
            Student(id="student-1", email="student@example.test", display_name="Learner"),
            db, provider,
        )

    assert error.value.status_code == 502
    assert db.added == [] and db.commits == 0


def test_no_ready_documents_uses_general_answer_without_citations(monkeypatch):
    db = FakeDb(scalars=(None, None))
    provider = FakeEmbeddingProvider()
    captured = {}

    def general_answer(_instruction, history):
        captured["history"] = history
        return "A half is one of two equal parts."

    monkeypatch.setattr(tutor_api, "generate_tutor_reply", general_answer)

    response = call_chat(
        db, provider, monkeypatch, hits=[], generator=general_answer
    )

    assert response.grounded is False
    assert response.retrieval_used is False
    assert response.citations == []
    assert "Sources /" not in response.reply
    assert provider.calls == []
    assert "No relevant private document passages" in captured["history"][-1]["content"]
    assert db.commits == 1
