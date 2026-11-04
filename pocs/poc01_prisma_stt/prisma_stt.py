"""POC-01: replaceable GNANI Prisma REST adapter.

The request schema is deliberately configurable because GNANI API versions
and account entitlements can differ. Confirm the endpoint and fields in the
developer portal before a live test.
"""
from __future__ import annotations

import os
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


class STTError(RuntimeError):
    """Safe, user-facing speech transcription failure."""


@dataclass(frozen=True)
class Transcript:
    text: str
    language: str | None
    raw: dict[str, Any]


@dataclass(frozen=True)
class PrismaConfig:
    url: str
    api_key: str
    auth_header: str = "X-API-Key-ID"
    model: str = "prisma-v3.0"
    language: str = "indic-auto"
    output_format: str = "codemix"
    timeout_seconds: int = 45

    @classmethod
    def from_env(cls) -> "PrismaConfig":
        key = os.getenv("GNANI_API_KEY", "").strip()
        url = os.getenv("GNANI_STT_URL", "").strip()
        if not key or key == "replace_me":
            raise STTError("Set GNANI_API_KEY in your local .env file.")
        if not url.startswith("https://"):
            raise STTError("Set GNANI_STT_URL to the verified HTTPS endpoint.")
        return cls(
            url=url,
            api_key=key,
            auth_header=os.getenv("GNANI_AUTH_HEADER", "X-API-Key-ID"),
            model=os.getenv("GNANI_MODEL", "prisma-v3.0"),
            language=os.getenv("GNANI_LANGUAGE", "indic-auto"),
            output_format=os.getenv("GNANI_OUTPUT_FORMAT", "codemix"),
            timeout_seconds=int(os.getenv("GNANI_TIMEOUT_SECONDS", "45")),
        )


def validate_audio(path: Path) -> None:
    if not path.is_file():
        raise STTError(f"Audio file does not exist: {path}")
    if path.suffix.lower() != ".wav":
        raise STTError("Use a PCM .wav recording for this initial experiment.")
    if path.stat().st_size > 10 * 1024 * 1024:
        raise STTError("Audio exceeds the 10 MB POC limit.")
    try:
        with wave.open(str(path), "rb") as audio:
            if audio.getcomptype() != "NONE":
                raise STTError("Only uncompressed PCM WAV is supported.")
            if audio.getnframes() == 0:
                raise STTError("Audio is empty.")
            if audio.getnframes() / audio.getframerate() > 30:
                raise STTError("Keep POC-01 audio at or under 30 seconds.")
    except (wave.Error, EOFError, ZeroDivisionError) as exc:
        raise STTError("Invalid or unsupported WAV file.") from exc


def normalize_response(payload: Any) -> Transcript:
    if not isinstance(payload, dict):
        raise STTError("Unexpected GNANI response: expected a JSON object.")
    data = payload.get("data")
    candidates = [payload]
    if isinstance(data, dict):
        candidates.insert(0, data)
    for item in candidates:
        text = item.get("transcript") or item.get("text")
        if isinstance(text, str) and text.strip():
            language = item.get("detected_language_code") or item.get("language")
            return Transcript(text.strip(), language, payload)
    raise STTError("GNANI response did not contain a recognized transcript.")


class PrismaSTTAdapter:
    def __init__(self, config: PrismaConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    def transcribe(self, audio_path: str | Path) -> Transcript:
        path = Path(audio_path)
        validate_audio(path)
        headers = {self.config.auth_header: self.config.api_key}
        form = {
            "model": self.config.model,
            "language": self.config.language,
            "format": self.config.output_format,
        }
        try:
            with path.open("rb") as handle:
                response = self.session.post(
                    self.config.url,
                    headers=headers,
                    data=form,
                    files={"file": (path.name, handle, "audio/wav")},
                    timeout=self.config.timeout_seconds,
                )
            response.raise_for_status()
            return normalize_response(response.json())
        except requests.Timeout as exc:
            raise STTError("GNANI request timed out.") from exc
        except requests.HTTPError as exc:
            code = exc.response.status_code if exc.response is not None else "unknown"
            raise STTError(f"GNANI returned HTTP {code}. Check endpoint, permissions and request schema.") from exc
        except (requests.RequestException, ValueError) as exc:
            raise STTError("GNANI request failed or returned invalid JSON.") from exc
