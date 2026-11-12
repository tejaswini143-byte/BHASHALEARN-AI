"""POC-06 runtime settings and safe loading of existing POC provider env files."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


class VoiceConfigError(ValueError):
    """Safe local configuration error; never includes credential contents."""


PROVIDER_ENV_NAMES = frozenset({
    "BHASHALEARN_GEMINI_API_KEY", "BHASHALEARN_GEMINI_MODEL",
    "BHASHALEARN_GEMINI_EMBEDDING_API_KEY", "BHASHALEARN_GEMINI_EMBEDDING_MODEL",
    "BHASHALEARN_GEMINI_EMBEDDING_DIMENSIONS", "BHASHALEARN_EMBEDDING_CHUNK_SIZE",
    "BHASHALEARN_EMBEDDING_CHUNK_OVERLAP", "BHASHALEARN_EMBEDDING_TIMEOUT_SECONDS",
    "BHASHALEARN_EMBEDDING_MAX_RETRIES", "BHASHALEARN_BRAVE_SEARCH_API_KEY",
    "GNANI_API_KEY", "GNANI_STT_URL", "GNANI_AUTH_HEADER", "GNANI_MODEL",
    "GNANI_LANGUAGE", "GNANI_OUTPUT_FORMAT", "GNANI_TIMEOUT_SECONDS",
    "GNANI_TTS_URL", "GNANI_TTS_MODEL", "GNANI_TTS_VOICE", "GNANI_TTS_TIMEOUT_SECONDS",
    "POC06_SAMPLE_RATE", "POC06_CHANNELS", "POC06_RECORDING_SECONDS",
    "POC06_MAX_RECORDING_SECONDS", "POC06_AUDIO_OUTPUT_DIR",
})


def load_provider_environment(repo_root: Path) -> None:
    """Load provider settings from process env, root .env, then legacy POC .env files.

    Process environment has highest precedence. The repository-root .env is the
    canonical local configuration file and overrides legacy POC-local files.
    Existing POC files remain supported as a migration path for standalone POCs.
    Values are never printed.
    """
    folders = (
        "poc01_prisma_stt",
        "poc02_timbre_tts",
        "poc03_bilingual_llm",
        "poc06_bilingual_voice",
    )
    values: dict[str, str] = {}
    placeholders = {"replace_me", "your_actual_key", ""}

    def is_placeholder(value: str) -> bool:
        normalized = value.strip().casefold()
        return (
            normalized in placeholders
            or normalized.startswith(("replace-", "replace_", "your-", "your_"))
            or normalized.startswith("<")
        )

    # Parent project .env is a fallback for this linked RC worktree. Only
    # provider settings are read; database URLs, JWTs, OAuth, and other secrets
    # never enter this loader. RC process variables still win over every file.
    parent_env = repo_root.parent / ".env"
    if parent_env.is_file():
        for name, value in dotenv_values(parent_env).items():
            if name in PROVIDER_ENV_NAMES and value is not None and not is_placeholder(value):
                values[name] = value.strip()

    for folder in folders:
        env_path = repo_root / "pocs" / folder / ".env"
        if not env_path.is_file():
            continue
        for name, value in dotenv_values(env_path).items():
            if name in PROVIDER_ENV_NAMES and value is not None and not is_placeholder(value):
                values[name] = value.strip()

    # Pydantic Settings reads BHASHALEARN_* values from this same root file.
    # The Gnani adapters use os.environ directly, so load their unprefixed
    # settings here to make the documented root .env work for both providers.
    central_env = repo_root / ".env"
    if central_env.is_file():
        for name, value in dotenv_values(central_env).items():
            if name in PROVIDER_ENV_NAMES and value is not None and not is_placeholder(value):
                values[name] = value.strip()

    for name, value in values.items():
        current = os.getenv(name, "").strip()
        if is_placeholder(current):
            os.environ[name] = value


@dataclass(frozen=True)
class VoicePipelineConfig:
    sample_rate: int = 16000
    channels: int = 1
    recording_seconds: float = 5.0
    max_recording_seconds: int = 30
    output_dir: Path = Path("pocs/poc06_bilingual_voice/artifacts")

    def __post_init__(self) -> None:
        if self.sample_rate <= 0 or self.channels <= 0:
            raise VoiceConfigError("Sample rate and channel count must be positive.")
        if self.max_recording_seconds < 1 or self.max_recording_seconds > 30:
            raise VoiceConfigError("POC-06 recording limit must be between 1 and 30 seconds.")
        if not 0 < self.recording_seconds <= self.max_recording_seconds:
            raise VoiceConfigError("Recording duration must be positive and within the configured maximum.")

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "VoicePipelineConfig":
        base = repo_root or Path.cwd()
        try:
            sample_rate = int(os.getenv("POC06_SAMPLE_RATE", "16000"))
            channels = int(os.getenv("POC06_CHANNELS", "1"))
            duration = float(os.getenv("POC06_RECORDING_SECONDS", "5"))
            maximum = int(os.getenv("POC06_MAX_RECORDING_SECONDS", "30"))
        except ValueError as exc:
            raise VoiceConfigError("POC-06 audio settings must be numeric.") from exc
        output_dir = Path(os.getenv("POC06_AUDIO_OUTPUT_DIR", str(base / "pocs" / "poc06_bilingual_voice" / "artifacts")))
        return cls(sample_rate, channels, duration, maximum, output_dir)

