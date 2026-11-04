"""GNANI Timbre v2.5 REST text-to-speech adapter.

API: https://docs.gnani.ai/api/TTS/tts-inference.md
"""
from __future__ import annotations

import os
import struct
import wave
from dataclasses import dataclass
from pathlib import Path

import requests

ENDPOINT = "https://api.vachana.ai/api/v1/tts/inference"
VOICES = {"en-IN": "Kaveri", "te-IN": "Suhana"}
LANGUAGES = {"en-IN", "te-IN", "auto"}


class TTSError(RuntimeError):
    """Safe, user-facing TTS failure."""


@dataclass(frozen=True)
class TimbreConfig:
    api_key: str
    url: str = ENDPOINT
    model: str = "timbre-v2.5"
    voice: str = ""
    timeout_seconds: int = 60

    @classmethod
    def from_env(cls) -> "TimbreConfig":
        key = os.getenv("GNANI_API_KEY", "").strip()
        if not key or key in {"replace_me", "YOUR_ACTUAL_KEY"}:
            raise TTSError("Set GNANI_API_KEY in your local .env file.")
        url = os.getenv("GNANI_TTS_URL", ENDPOINT).strip() or ENDPOINT
        if not url.startswith("https://"):
            raise TTSError("GNANI_TTS_URL must be an HTTPS endpoint.")
        return cls(
            api_key=key,
            url=url,
            model=os.getenv("GNANI_TTS_MODEL", "timbre-v2.5"),
            voice=os.getenv("GNANI_TTS_VOICE", "").strip(),
            timeout_seconds=int(os.getenv("GNANI_TTS_TIMEOUT_SECONDS", "60")),
        )


def validate_text(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        raise TTSError("Text must be a non-empty string.")
    if len(text) > 3000:
        raise TTSError("Keep POC text under 3000 characters.")
    return text.strip()


def normalize_wav_lengths(data: bytes) -> bytes:
    """Repair Gnani's sentinel RIFF/data lengths for ordinary WAV readers."""
    if len(data) < 44 or data[:4] != b"RIFF" or data[8:12] != b"WAVE":
        return data
    if data[12:16] != b"fmt " or data[36:40] != b"data":
        return data
    riff_size = int.from_bytes(data[4:8], "little")
    data_size = int.from_bytes(data[40:44], "little")
    if riff_size != 0xFFFFFFFF and data_size != 0xFFFFFFFF:
        return data
    normalized = bytearray(data)
    if riff_size == 0xFFFFFFFF:
        struct.pack_into("<I", normalized, 4, len(data) - 8)
    if data_size == 0xFFFFFFFF:
        struct.pack_into("<I", normalized, 40, len(data) - 44)
    return bytes(normalized)


def write_audio(data: bytes, output: str | Path) -> Path:
    if not isinstance(data, bytes) or not data:
        raise TTSError("TTS response did not contain audio bytes.")
    path = Path(output)
    if path.suffix.lower() != ".wav":
        raise TTSError("Output filename must end in .wav.")
    data = normalize_wav_lengths(data)
    try:
        import io
        with wave.open(io.BytesIO(data), "rb") as wav:
            if wav.getnframes() < 1:
                raise TTSError("GNANI returned an empty WAV.")
            if wav.getcomptype() != "NONE":
                raise TTSError("GNANI returned unsupported compressed WAV.")
    except (wave.Error, EOFError) as exc:
        raise TTSError("GNANI returned invalid WAV audio.") from exc
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def parse_http_error(response: requests.Response) -> str:
    status = response.status_code
    code = ""
    message = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            detail = payload.get("detail")
            if isinstance(detail, dict):
                code = str(detail.get("error_code", ""))
            if status == 400:
                message = str(payload.get("message", ""))
    except ValueError:
        pass
    if status in (401, 403):
        hints = {
            "MISSING_API_KEY": "Check GNANI_API_KEY in your local .env.",
            "INVALID_API_KEY": "GNANI rejected your API key.",
            "SCOPE_NOT_ALLOWED": "Your key does not have TTS permission.",
        }
        safe_code = code if code in hints else "AUTH_ERROR"
        return f"GNANI HTTP {status} ({safe_code}). {hints.get(safe_code, 'Check API key and TTS access.')}"
    if status == 429:
        return "GNANI HTTP 429: Rate limit reached; wait and retry."
    if status == 400:
        return f"GNANI HTTP 400: {message[:250]}" if message else "GNANI HTTP 400: Invalid TTS request."
    return f"GNANI HTTP {status}: TTS request failed."


class TimbreTTSAdapter:
    def __init__(self, config: TimbreConfig, session: requests.Session | None = None):
        self.config = config
        self.session = session or requests.Session()

    def synthesize(self, text: str, language: str = "en-IN", voice: str | None = None) -> bytes:
        text = validate_text(text)
        if language not in LANGUAGES:
            raise TTSError("Use en-IN, te-IN, or auto for POC-02.")
        if self.config.model != "timbre-v2.5":
            raise TTSError("POC-02 supports timbre-v2.5 only.")
        selected_voice = voice or self.config.voice or VOICES.get(language)
        if not selected_voice:
            raise TTSError("Choose a voice for auto language detection.")
        payload = {
            "text": text,
            "voice": selected_voice,
            "model": self.config.model,
            "language": language,
            "speed": 1.0,
            "audio_config": {
                "sample_rate": 48000,
                "num_channels": 1,
                "sample_width": 2,
                "encoding": "linear_pcm",
                "container": "wav",
            },
        }
        try:
            response = self.session.post(
                self.config.url,
                headers={"X-API-Key-ID": self.config.api_key, "Content-Type": "application/json"},
                json=payload,
                timeout=self.config.timeout_seconds,
            )
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if content_type not in {"audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"}:
                raise TTSError("GNANI did not return WAV audio (unexpected content type).")
            if not response.content:
                raise TTSError("GNANI returned an empty audio response.")
            return normalize_wav_lengths(response.content)
        except requests.Timeout as exc:
            raise TTSError("GNANI TTS request timed out.") from exc
        except requests.HTTPError as exc:
            error_response = exc.response if exc.response is not None else response
            raise TTSError(parse_http_error(error_response)) from exc
        except requests.RequestException as exc:
            raise TTSError("GNANI TTS network request failed.") from exc
