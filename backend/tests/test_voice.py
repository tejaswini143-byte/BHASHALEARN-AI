"""Authenticated voice endpoint tests with deterministic provider doubles."""
from __future__ import annotations

import io
import wave
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.config import get_settings
from backend.app.db.base import Base
from backend.app.db.session import get_db
from backend.app.main import create_app
from pocs.poc01_prisma_stt.prisma_stt import STTError, Transcript
from pocs.poc04_adaptive_teaching.models import Language
from pocs.poc06_bilingual_voice.stt_adapter import STTStageError
from pocs.poc06_bilingual_voice.tts_adapter import SpeechArtifact, TTSStageError


def pcm_wav() -> bytes:
    target = io.BytesIO()
    with wave.open(target, "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(b"\x01\x00" * 16000)
    return target.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "voice-integration-test-secret-32-characters")
    get_settings.cache_clear()
    engine = create_engine(f"sqlite:///{(tmp_path / 'voice.db').as_posix()}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)
    app = create_app()

    def override_db():
        with factory() as db:
            yield db

    app.dependency_overrides[get_db] = override_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


def auth(client: TestClient, email: str) -> dict[str, str]:
    password = "voice-test-password-123"
    assert client.post("/api/v1/auth/register", json={"email": email, "display_name": "Voice Learner", "password": password}).status_code == 201
    token = client.post("/api/v1/auth/login", json={"email": email, "password": password}).json()["access_token"]
    return {"Authorization": "Bearer " + token}


def make_session(client: TestClient, headers: dict[str, str], language: str = "mixed") -> str:
    response = client.post("/api/v1/sessions", headers=headers, json={"topic": "Fractions", "language": language})
    assert response.status_code == 201, response.text
    return response.json()["id"]


class StubPrisma:
    def __init__(self, result=None, error=None):
        self.result = result or Transcript("What is one half?", "en", {"transcript": "What is one half?"})
        self.error = error
        self.calls = 0

    def transcribe(self, _path):
        self.calls += 1
        if self.error:
            raise self.error
        return self.result


class StubTimbre:
    def __init__(self, folder, error=None):
        self.folder = folder
        self.error = error
        self.calls = []

    def synthesize_response(self, text, language, session_id):
        self.calls.append((text, language, session_id))
        if self.error:
            raise self.error
        path = self.folder / "reply.wav"
        path.write_bytes(pcm_wav())
        return SpeechArtifact(path, "en-IN", "Kaveri", 16000, 1, 1.0, path.stat().st_size)


def test_stt_success_language_modes_keep_raw_transcript(client, monkeypatch):
    headers = auth(client, "voice-stt@example.com")
    session_id = make_session(client, headers)
    stub = StubPrisma(Transcript("మిశ్రమ భిన్నం అంటే ఏమిటి?", "te", {"transcript": "raw"}))
    monkeypatch.setattr("backend.app.api.voice.create_prisma_client", lambda: stub)
    expected = "మిశ్రమ భిన్నం అంటే ఏమిటి?"
    for mode in ("telugu", "english", "mixed"):
        response = client.post(
            f"/api/v1/voice/sessions/{session_id}/transcribe",
            headers=headers,
            files={"audio": ("speech.wav", pcm_wav(), "audio/wav")},
            data={"language": mode},
        )
        assert response.status_code == 200, response.text
        assert response.json()["transcript"] == expected
        assert response.json()["language_mode"] == mode
        assert response.json()["detected_language"] == "te"
    assert stub.calls == 3
    assert client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers).json() == []


def test_stt_empty_unsupported_missing_oversized_and_malformed_audio(client, monkeypatch):
    headers = auth(client, "voice-invalid-audio@example.com")
    session_id = make_session(client, headers)
    path = f"/api/v1/voice/sessions/{session_id}/transcribe"
    calls = []
    monkeypatch.setattr("backend.app.api.voice.create_prisma_client", lambda: calls.append(True) or StubPrisma())
    assert client.post(path, headers=headers, data={"language": "mixed"}).status_code == 422
    assert client.post(path, headers=headers, files={"audio": ("empty.wav", b"", "audio/wav")}, data={"language": "mixed"}).status_code == 422
    assert client.post(path, headers=headers, files={"audio": ("speech.webm", b"not wav", "audio/webm")}, data={"language": "mixed"}).status_code == 415
    assert client.post(path, headers=headers, files={"audio": ("broken.wav", b"bad", "audio/wav")}, data={"language": "mixed"}).status_code == 422
    assert client.post(path, headers=headers, files={"audio": ("large.wav", b"x" * (10 * 1024 * 1024 + 1), "audio/wav")}, data={"language": "mixed"}).status_code == 413
    assert client.post(path, headers=headers, files={"audio": ("speech.wav", pcm_wav(), "audio/wav")}, data={"language": "invalid"}).status_code == 422
    assert calls == []


def test_stt_auth_ownership_configuration_provider_and_timeout(client, monkeypatch):
    owner = auth(client, "voice-owner@example.com")
    other = auth(client, "voice-other@example.com")
    session_id = make_session(client, owner)
    path = f"/api/v1/voice/sessions/{session_id}/transcribe"
    calls = []
    monkeypatch.setattr("backend.app.api.voice.create_prisma_client", lambda: calls.append(True) or StubPrisma())
    request = {"files": {"audio": ("speech.wav", pcm_wav(), "audio/wav")}, "data": {"language": "mixed"}}
    assert client.post(path, **request).status_code == 401
    assert client.post(path, headers=other, **request).status_code == 404
    assert calls == []

    from backend.app.services.gnani_voice import VoiceProviderNotConfigured
    monkeypatch.setattr("backend.app.api.voice.create_prisma_client", lambda: (_ for _ in ()).throw(VoiceProviderNotConfigured("not configured")))
    assert client.post(path, headers=owner, **request).status_code == 503
    monkeypatch.setattr("backend.app.api.voice.create_prisma_client", lambda: StubPrisma(error=STTError("GNANI request timed out.")))
    assert client.post(path, headers=owner, **request).status_code == 504
    monkeypatch.setattr("backend.app.api.voice.create_prisma_client", lambda: StubPrisma(error=STTStageError("invalid_response", "bad response")))
    assert client.post(path, headers=owner, **request).status_code == 502
    monkeypatch.setattr("backend.app.api.voice.create_prisma_client", lambda: StubPrisma(Transcript("hello", 17, {})))
    assert client.post(path, headers=owner, **request).status_code == 502


def test_tts_wav_success_and_failure_does_not_create_chat_turn(client, monkeypatch, tmp_path):
    headers = auth(client, "voice-tts@example.com")
    session_id = make_session(client, headers, "telugu")
    created = []
    def make_timbre(folder):
        stub = StubTimbre(Path(folder))
        created.append(stub)
        return stub
    monkeypatch.setattr("backend.app.api.voice.create_timbre_adapter", make_timbre)
    response = client.post(f"/api/v1/voice/sessions/{session_id}/speech", headers=headers, json={"text": "నమస్కారం", "language": "telugu"})
    assert response.status_code == 200, response.text
    assert response.headers["content-type"].startswith("audio/wav")
    with wave.open(io.BytesIO(response.content), "rb") as audio:
        assert audio.getnframes() > 0
        assert audio.getnchannels() == 1
    assert created[0].calls == [("నమస్కారం", Language.TELUGU, session_id)]
    for mode in ("english", "mixed"):
        response = client.post(f"/api/v1/voice/sessions/{session_id}/speech", headers=headers, json={"text": "Hello", "language": mode})
        assert response.status_code == 200
    assert created[1].calls == [("Hello", Language.ENGLISH, session_id)]
    assert created[2].calls == [("Hello", Language.MIXED, session_id)]
    assert client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers).json() == []

    from backend.app.services.gnani_voice import VoiceProviderNotConfigured
    monkeypatch.setattr("backend.app.api.voice.create_timbre_adapter", lambda folder: (_ for _ in ()).throw(VoiceProviderNotConfigured("not configured")))
    failed = client.post(f"/api/v1/voice/sessions/{session_id}/speech", headers=headers, json={"text": "Hello"})
    assert failed.status_code == 503
    assert client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers).json() == []


def test_tts_validation_timeout_provider_failure_and_ownership(client, monkeypatch, tmp_path):
    owner = auth(client, "voice-tts-owner@example.com")
    other = auth(client, "voice-tts-other@example.com")
    session_id = make_session(client, owner)
    url = f"/api/v1/voice/sessions/{session_id}/speech"
    monkeypatch.setattr("backend.app.api.voice.create_timbre_adapter", lambda folder: StubTimbre(Path(folder)))
    assert client.post(url, json={"text": "Hello"}).status_code == 401
    assert client.post(url, headers=other, json={"text": "Hello"}).status_code == 404
    assert client.post(url, headers=owner, json={"text": " "}).status_code == 422
    assert client.post(url, headers=owner, json={"text": "x" * 3001}).status_code == 422
    assert client.post(url, headers=owner, json={"text": "Hello", "language": "french"}).status_code == 422
    assert client.post(url, headers=owner, json={"text": "Hello", "voice": "invented"}).status_code == 422
    monkeypatch.setattr("backend.app.api.voice.create_timbre_adapter", lambda folder: StubTimbre(Path(folder), TTSStageError("timeout", "timed out", True, provider_category="timeout")))
    assert client.post(url, headers=owner, json={"text": "Hello"}).status_code == 504
    monkeypatch.setattr("backend.app.api.voice.create_timbre_adapter", lambda folder: StubTimbre(Path(folder), TTSStageError("provider_error", "failure", provider_category="provider_server_error")))
    assert client.post(url, headers=owner, json={"text": "Hello"}).status_code == 502
    monkeypatch.setattr("backend.app.api.voice.create_timbre_adapter", lambda folder: StubTimbre(Path(folder), TTSStageError("invalid_audio", "invalid response", provider_category="audio_response_validation")))
    assert client.post(url, headers=owner, json={"text": "Hello"}).status_code == 502


def test_transcript_then_existing_chat_persists_exactly_one_turn(client, monkeypatch):
    headers = auth(client, "voice-chat@example.com")
    session_id = make_session(client, headers)
    provider = StubPrisma(Transcript("What is one half?", "en", {}))
    monkeypatch.setattr("backend.app.api.voice.create_prisma_client", lambda: provider)
    transcript = client.post(
        f"/api/v1/voice/sessions/{session_id}/transcribe", headers=headers,
        files={"audio": ("speech.wav", pcm_wav(), "audio/wav")}, data={"language": "english"},
    )
    assert transcript.status_code == 200
    seen = []
    monkeypatch.setattr("backend.app.api.tutor.generate_tutor_reply", lambda _instruction, history: seen.extend(history) or "One of two equal parts.")
    chat = client.post(f"/api/v1/tutor/sessions/{session_id}/chat", headers=headers, json={"message": transcript.json()["transcript"]})
    assert chat.status_code == 200
    history = client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers).json()
    assert [(turn["role"], turn["content"]) for turn in history] == [
        ("user", "What is one half?"), ("assistant", "One of two equal parts."),
    ]
    assert len(seen) == 1
    speech_calls = []
    def make_timbre(folder):
        stub = StubTimbre(Path(folder))
        speech_calls.append(stub)
        return stub
    monkeypatch.setattr("backend.app.api.voice.create_timbre_adapter", make_timbre)
    speech_url = f"/api/v1/voice/sessions/{session_id}/speech"
    for _ in range(2):
        spoken = client.post(speech_url, headers=headers, json={"text": chat.json()["reply"], "language": "english"})
        assert spoken.status_code == 200
    assert len(speech_calls) == 2
    assert all(call.calls == [("One of two equal parts.", Language.ENGLISH, session_id)] for call in speech_calls)
    assert [(turn["role"], turn["content"]) for turn in client.get(f"/api/v1/sessions/{session_id}/messages", headers=headers).json()] == [
        ("user", "What is one half?"), ("assistant", "One of two equal parts."),
    ]
