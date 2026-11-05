"""POC-06 runtime settings and safe loading of existing POC provider env files."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import dotenv_values


class VoiceConfigError(ValueError):
    """Safe local configuration error; never includes credential contents."""


def load_provider_environment(repo_root: Path) -> None:
    """Load existing provider .env files, with valid POC-06 overrides, without printing values."""
    folders = (
        "poc01_prisma_stt",
        "poc02_timbre_tts",
        "poc03_bilingual_llm",
        "poc06_bilingual_voice",
    )
    values: dict[str, str] = {}
    placeholders = {"replace_me", "your_actual_key", ""}
    for folder in folders:
        env_path = repo_root / "pocs" / folder / ".env"
        if not env_path.is_file():
            continue
        for name, value in dotenv_values(env_path).items():
            if value is not None and value.strip().casefold() not in placeholders:
                values[name] = value.strip()
    for name, value in values.items():
        current = os.getenv(name, "").strip()
        if not current or current.casefold() in placeholders:
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

