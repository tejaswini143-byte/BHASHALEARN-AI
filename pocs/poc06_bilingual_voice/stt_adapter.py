"""Normalization around POC-01's existing Prisma REST adapter."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from pocs.poc01_prisma_stt.prisma_stt import PrismaConfig, PrismaSTTAdapter, STTError, Transcript


class PrismaClient(Protocol):
    def transcribe(self, audio_path: str | Path) -> Transcript: ...


class STTStageError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class TranscriptionResult:
    text: str
    detected_language: str | None
    raw_response: dict[str, Any]


class PrismaTranscriptionAdapter:
    """Preserves POC-01's raw provider response and configured indic-auto/codemix request."""

    def __init__(self, client: PrismaClient):
        self.client = client

    @classmethod
    def from_config(cls, config: PrismaConfig) -> "PrismaTranscriptionAdapter":
        return cls(PrismaSTTAdapter(config))

    def transcribe(self, audio_path: str | Path) -> TranscriptionResult:
        try:
            transcript = self.client.transcribe(audio_path)
        except STTError as exc:
            timed_out = "timed out" in str(exc).casefold()
            raise STTStageError("timeout" if timed_out else "provider_error", str(exc), retryable=timed_out) from exc
        except Exception as exc:
            raise STTStageError("provider_error", "GNANI Prisma transcription failed.") from exc
        if not isinstance(transcript, Transcript):
            raise STTStageError("invalid_response", "GNANI Prisma returned an unsupported response.")
        if not isinstance(transcript.text, str):
            raise STTStageError("invalid_response", "GNANI Prisma returned an invalid transcript field.")
        if transcript.language is not None and not isinstance(transcript.language, str):
            raise STTStageError("invalid_response", "GNANI Prisma returned invalid detected-language metadata.")
        return TranscriptionResult(
            text=transcript.text,
            detected_language=transcript.language,
            raw_response=transcript.raw,
        )

