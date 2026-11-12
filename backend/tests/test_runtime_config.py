"""Runtime configuration precedence and fail-closed behavior."""
import os

import pytest
from fastapi import HTTPException

from backend.app import config
from backend.app.config import Settings
from backend.app.core import security
from backend.app.db import session
from backend.app.services import embeddings
from backend.app.services import tutor
from backend.app.services.embeddings import EmbeddingError
from pocs.poc01_prisma_stt.prisma_stt import PrismaConfig, STTError
from pocs.poc02_timbre_tts.timbre_tts import TTSError, TimbreConfig
from pocs.poc06_bilingual_voice.config import load_provider_environment


BACKEND_ENV_NAMES = (
    "BHASHALEARN_DATABASE_URL",
    "BHASHALEARN_JWT_SECRET_KEY",
    "BHASHALEARN_GEMINI_API_KEY",
    "BHASHALEARN_GEMINI_EMBEDDING_API_KEY",
)
GNANI_ENV_NAMES = (
    "GNANI_API_KEY",
    "GNANI_STT_URL",
    "GNANI_AUTH_HEADER",
    "GNANI_MODEL",
    "GNANI_LANGUAGE",
    "GNANI_OUTPUT_FORMAT",
    "GNANI_TIMEOUT_SECONDS",
    "GNANI_TTS_URL",
    "GNANI_TTS_MODEL",
    "GNANI_TTS_VOICE",
    "GNANI_TTS_TIMEOUT_SECONDS",
)


@pytest.fixture(autouse=True)
def isolate_runtime_environment(monkeypatch):
    for name in BACKEND_ENV_NAMES + GNANI_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    clear_settings_caches()
    yield
    clear_settings_caches()


def clear_settings_caches() -> None:
    config.get_settings.cache_clear()
    session.get_engine.cache_clear()
    session.get_session_factory.cache_clear()


def test_settings_read_database_jwt_and_gemini_environment(monkeypatch):
    for name in BACKEND_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    defaults = Settings(_env_file=None)
    assert defaults.database_url == ""
    assert defaults.jwt_secret_key == ""
    assert defaults.gemini_api_key == ""
    assert defaults.gemini_embedding_api_key == ""

    monkeypatch.setenv("BHASHALEARN_DATABASE_URL", "sqlite:///isolated-config-test.db")
    monkeypatch.setenv("BHASHALEARN_JWT_SECRET_KEY", "synthetic-jwt-secret-for-config-test-only")
    monkeypatch.setenv("BHASHALEARN_GEMINI_API_KEY", "synthetic-gemini-key-for-config-test-only")
    monkeypatch.setenv("BHASHALEARN_GEMINI_EMBEDDING_API_KEY", "synthetic-embedding-key-for-config-test-only")
    configured = Settings(_env_file=None)
    assert configured.database_url == "sqlite:///isolated-config-test.db"
    assert configured.jwt_secret_key == "synthetic-jwt-secret-for-config-test-only"
    assert configured.gemini_api_key == "synthetic-gemini-key-for-config-test-only"
    assert configured.gemini_embedding_api_key == "synthetic-embedding-key-for-config-test-only"


def test_settings_read_canonical_root_env_file_with_process_override(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text(
        "BHASHALEARN_DATABASE_URL=sqlite:///root-env.db\n"
        "BHASHALEARN_JWT_SECRET_KEY=synthetic-root-jwt-secret-long-enough\n"
        "BHASHALEARN_GEMINI_API_KEY=synthetic-root-gemini-key\n",
        encoding="utf-8",
    )
    for name in BACKEND_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)

    from_file = Settings()
    assert from_file.database_url == "sqlite:///root-env.db"
    assert from_file.jwt_secret_key == "synthetic-root-jwt-secret-long-enough"
    assert from_file.gemini_api_key == "synthetic-root-gemini-key"

    monkeypatch.setenv("BHASHALEARN_DATABASE_URL", "sqlite:///process-env.db")
    assert Settings().database_url == "sqlite:///process-env.db"


def test_provider_loader_uses_parent_fallback_without_loading_database_or_jwt(tmp_path, monkeypatch):
    rc_root = tmp_path / "_integration_rc"
    (rc_root / "pocs" / "poc01_prisma_stt").mkdir(parents=True)
    (tmp_path / ".env").write_text(
        "BHASHALEARN_GEMINI_API_KEY=synthetic-parent-gemini\n"
        "GNANI_API_KEY=synthetic-parent-gnani\n"
        "BHASHALEARN_DATABASE_URL=sqlite:///do-not-load.db\n"
        "BHASHALEARN_JWT_SECRET_KEY=do-not-load-jwt\n",
        encoding="utf-8",
    )
    for name in BACKEND_ENV_NAMES + GNANI_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BHASHALEARN_GEMINI_MODEL", "process-model-override")

    load_provider_environment(rc_root)

    assert os.environ["BHASHALEARN_GEMINI_API_KEY"] == "synthetic-parent-gemini"
    assert os.environ["GNANI_API_KEY"] == "synthetic-parent-gnani"
    assert os.environ["BHASHALEARN_GEMINI_MODEL"] == "process-model-override"
    assert "BHASHALEARN_DATABASE_URL" not in os.environ
    assert "BHASHALEARN_JWT_SECRET_KEY" not in os.environ


def test_embedding_provider_uses_configured_embedding_key(monkeypatch):
    settings = Settings(
        _env_file=None,
        gemini_api_key="synthetic-tutor-key",
        gemini_embedding_api_key="synthetic-embedding-key",
    )
    monkeypatch.setattr(embeddings, "get_settings", lambda: settings)
    provider = embeddings.GeminiEmbeddingProvider()
    assert provider.api_key == "synthetic-embedding-key"


def test_gemini_placeholders_fail_before_outbound_requests(monkeypatch):
    settings = Settings(
        _env_file=None,
        gemini_api_key="replace-with-your-Gemini-API-key",
        gemini_embedding_api_key="replace-with-your-Gemini-API-key",
    )
    monkeypatch.setattr(tutor, "get_settings", lambda: settings)
    with pytest.raises(HTTPException) as error:
        tutor.generate_tutor_reply("test", [{"role": "user", "content": "hello"}])
    assert error.value.status_code == 503

    monkeypatch.setattr(embeddings, "get_settings", lambda: settings)
    provider = embeddings.GeminiEmbeddingProvider()
    with pytest.raises(EmbeddingError) as embedding_error:
        provider.embed_texts(["synthetic text"], task_type="RETRIEVAL_QUERY")
    assert embedding_error.value.status_code == 503


def test_missing_database_and_jwt_credentials_fail_closed(monkeypatch):
    empty_settings = Settings(_env_file=None)
    monkeypatch.setattr(security, "get_settings", lambda: empty_settings)
    monkeypatch.setattr(session, "get_settings", lambda: empty_settings)
    clear_settings_caches()
    with pytest.raises(HTTPException) as error:
        security.get_jwt_secret()
    assert error.value.status_code == 503
    with pytest.raises(RuntimeError, match="BHASHALEARN_DATABASE_URL"):
        session.get_engine()

    placeholder_settings = Settings(
        _env_file=None,
        database_url="postgresql+psycopg://YOUR_DB_USER:YOUR_DB_PASSWORD@127.0.0.1:5432/YOUR_DB_NAME",
        jwt_secret_key="replace-with-a-long-random-development-secret",
    )
    monkeypatch.setattr(security, "get_settings", lambda: placeholder_settings)
    monkeypatch.setattr(session, "get_settings", lambda: placeholder_settings)
    clear_settings_caches()
    try:
        with pytest.raises(HTTPException) as placeholder_error:
            security.get_jwt_secret()
        assert placeholder_error.value.status_code == 503
        with pytest.raises(RuntimeError, match="BHASHALEARN_DATABASE_URL"):
            session.get_engine()
    finally:
        clear_settings_caches()


def test_gnani_root_env_precedes_legacy_poc_env_and_process_env_wins(tmp_path, monkeypatch):
    root_env = tmp_path / ".env"
    root_env.write_text(
        "GNANI_API_KEY=synthetic-root-provider-key\n"
        "GNANI_STT_URL=https://root.example.invalid/stt\n"
        "GNANI_TTS_URL=https://root.example.invalid/tts\n",
        encoding="utf-8",
    )
    poc_env = tmp_path / "pocs" / "poc01_prisma_stt" / ".env"
    poc_env.parent.mkdir(parents=True)
    poc_env.write_text(
        "GNANI_API_KEY=synthetic-legacy-provider-key\n"
        "GNANI_STT_URL=https://legacy.example.invalid/stt\n",
        encoding="utf-8",
    )
    for name in GNANI_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    load_provider_environment(tmp_path)
    assert os.getenv("GNANI_API_KEY") == "synthetic-root-provider-key"
    assert os.getenv("GNANI_STT_URL") == "https://root.example.invalid/stt"
    assert PrismaConfig.from_env().url == "https://root.example.invalid/stt"
    assert TimbreConfig.from_env().url == "https://root.example.invalid/tts"

    monkeypatch.setenv("GNANI_API_KEY", "synthetic-process-provider-key")
    load_provider_environment(tmp_path)
    assert os.getenv("GNANI_API_KEY") == "synthetic-process-provider-key"


def test_gnani_legacy_poc_env_still_works_and_missing_key_fails_closed(tmp_path, monkeypatch):
    poc_env = tmp_path / "pocs" / "poc02_timbre_tts" / ".env"
    poc_env.parent.mkdir(parents=True)
    poc_env.write_text("GNANI_API_KEY=synthetic-legacy-provider-key\n", encoding="utf-8")
    for name in GNANI_ENV_NAMES:
        monkeypatch.delenv(name, raising=False)

    load_provider_environment(tmp_path)
    assert PrismaConfig.from_env().api_key == "synthetic-legacy-provider-key"
    assert TimbreConfig.from_env().api_key == "synthetic-legacy-provider-key"

    monkeypatch.delenv("GNANI_API_KEY", raising=False)
    with pytest.raises(STTError, match="GNANI_API_KEY"):
        PrismaConfig.from_env()
    with pytest.raises(TTSError, match="GNANI_API_KEY"):
        TimbreConfig.from_env()

    monkeypatch.setenv("GNANI_API_KEY", "replace-with-a-nonfunctional-provider-key")
    with pytest.raises(STTError, match="GNANI_API_KEY"):
        PrismaConfig.from_env()
    with pytest.raises(TTSError, match="GNANI_API_KEY"):
        TimbreConfig.from_env()


def test_root_placeholder_does_not_override_legacy_valid_key(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text("GNANI_API_KEY=replace_me\n", encoding="utf-8")
    poc_env = tmp_path / "pocs" / "poc01_prisma_stt" / ".env"
    poc_env.parent.mkdir(parents=True)
    poc_env.write_text("GNANI_API_KEY=synthetic-legacy-provider-key\n", encoding="utf-8")

    load_provider_environment(tmp_path)
    assert os.getenv("GNANI_API_KEY") == "synthetic-legacy-provider-key"
