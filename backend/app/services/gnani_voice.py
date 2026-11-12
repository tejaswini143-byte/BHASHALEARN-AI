"""Factories for the existing POC-01 Prisma and POC-02 Timbre clients."""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from pocs.poc01_prisma_stt.prisma_stt import PrismaConfig, PrismaSTTAdapter, STTError
from pocs.poc02_timbre_tts.timbre_tts import TTSError, TimbreConfig, TimbreTTSAdapter
from pocs.poc06_bilingual_voice.config import load_provider_environment
from pocs.poc06_bilingual_voice.tts_adapter import TimbreSpeechAdapter


class VoiceProviderNotConfigured(RuntimeError):
    """Raised when local Gnani configuration is absent or invalid."""


def _load_existing_provider_env() -> None:
    # Reuse POC-06's precedence and safe .env loading; never print values.
    repository_root = Path(__file__).resolve().parents[3]
    load_provider_environment(repository_root)


_VOICE_PRISMA_SETTINGS = {
    "english": ("en-IN", "transcribe"),
    "telugu": ("te-IN", "transcribe"),
    "mixed": ("indic-auto", "codemix"),
}


def create_prisma_client_for_language(language_mode: str) -> PrismaSTTAdapter:
    """Build the existing Prisma client with the language selected in Voice Tutor."""
    _load_existing_provider_env()
    try:
        language, output_format = _VOICE_PRISMA_SETTINGS[language_mode]
        config = PrismaConfig.from_env()
        config = replace(config, language=language, output_format=output_format)
        return PrismaSTTAdapter(config)
    except (KeyError, STTError, ValueError) as exc:
        raise VoiceProviderNotConfigured("Gnani Prisma is not configured for the selected voice language; check GNANI_API_KEY and STT settings in the local POC .env files.") from exc


def create_prisma_client() -> PrismaSTTAdapter:
    _load_existing_provider_env()
    try:
        return PrismaSTTAdapter(PrismaConfig.from_env())
    except (STTError, ValueError) as exc:
        raise VoiceProviderNotConfigured("Gnani Prisma is not configured; check GNANI_API_KEY and STT settings in the local POC .env files.") from exc


def create_timbre_adapter(output_dir: str | Path) -> TimbreSpeechAdapter:
    _load_existing_provider_env()
    try:
        config = TimbreConfig.from_env()
        return TimbreSpeechAdapter(TimbreTTSAdapter(config), config, output_dir)
    except (TTSError, ValueError) as exc:
        raise VoiceProviderNotConfigured("Gnani Timbre is not configured; check GNANI_API_KEY and TTS settings in the local POC .env files.") from exc
