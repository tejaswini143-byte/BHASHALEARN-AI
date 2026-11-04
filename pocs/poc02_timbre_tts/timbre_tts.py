"""POC-02 GNANI Timbre TTS adapter scaffold.

The exact TTS request and response contract MUST be checked against the official
TTS REST documentation before enabling live calls. No speculative requests.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import requests


class TTSError(RuntimeError):
    """User-facing text-to-speech failure."""


@dataclass(frozen=True)
class TimbreConfig:
    api_key: str
    url: str
    model: str = "timbre-v2.5"
    voice: str = ""
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "TimbreConfig":
        key = os.getenv("GNANI_API_KEY", "").strip()
        if not key or key == "replace_me":
            raise TTSError("Set GNANI_API_KEY in your local .env file.")
        return cls(
            api_key=key,
            url=os.getenv("GNANI_TTS_URL", "").strip(),
            model=os.getenv("GNANI_TTS_MODEL", "timbre-v2.5"),
            voice=os.getenv("GNANI_TTS_VOICE", "").strip(),
            timeout_seconds=int(os.getenv("GNANI_TTS_TIMEOUT_SECONDS", "60")),
        )


def validate_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise TTSError("Text must be a non-empty string.")
    if len(text) > 3000:
        raise TTSError("Keep the POC input under 3000 characters.")
    return text.strip()


def write_audio(data: bytes, output: str | Path) -> Path:
    """Save audio bytes after a caller has verified the server's audio format."""
    if not isinstance(data, bytes) or not data:
        raise TTSError("TTS response did not contain audio bytes.")
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


class TimbreTTSAdapter:
    def __init__(self, config: TimbreConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    def synthesize(self, text: str) -> bytes:
        validate_text(text)
        raise TTSError(
            "Live Timbre REST request not enabled: verify the official TTS endpoint, "
            "request fields and response audio format first."
        )
