"""WAV synthesis adapter over the existing POC-02 Timbre client and writer."""
from __future__ import annotations

import re
import wave
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from pocs.poc02_timbre_tts.timbre_tts import (
    VOICES,
    TTSError,
    TimbreConfig,
    TimbreTTSAdapter,
    validate_text,
    write_audio,
)
from pocs.poc04_adaptive_teaching.models import Language


class TTSStageError(RuntimeError):
    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code = code
        self.retryable = retryable


@dataclass(frozen=True)
class SpeechArtifact:
    path: Path
    provider_language: str
    voice: str
    sample_rate: int
    channels: int
    duration_seconds: float
    size_bytes: int


class TimbreSpeechAdapter:
    def __init__(self, client: TimbreTTSAdapter, config: TimbreConfig, output_dir: str | Path):
        self.client = client
        self.config = config
        self.output_dir = Path(output_dir).resolve()

    @classmethod
    def from_config(cls, config: TimbreConfig, output_dir: str | Path) -> "TimbreSpeechAdapter":
        return cls(TimbreTTSAdapter(config), config, output_dir)

    def synthesize_response(
        self,
        text: str,
        language: Language | str,
        session_id: str,
        output_path: str | Path | None = None,
    ) -> SpeechArtifact:
        try:
            speech_text = validate_text(text)
            selected_language = Language(language)
        except (TTSError, ValueError) as exc:
            raise TTSStageError("invalid_input", str(exc)) from exc

        provider_language = {
            Language.ENGLISH: "en-IN",
            Language.TELUGU: "te-IN",
            Language.MIXED: "auto",
        }[selected_language]
        if selected_language is Language.MIXED:
            # POC-02 documents this auto-detect/voice combination as its mixed-text experiment.
            selected_voice = self.config.voice or VOICES["te-IN"]
        else:
            selected_voice = self.config.voice or VOICES[provider_language]

        safe_session = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[-24:] or "session"
        if output_path is None:
            candidate = self.output_dir / f"voice_{safe_session}_{uuid4().hex[:10]}.wav"
        else:
            candidate = Path(output_path)
            if not candidate.is_absolute():
                candidate = self.output_dir / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.output_dir):
            raise TTSStageError("invalid_output_path", "Audio output must stay inside the configured POC-06 output directory.")

        try:
            audio_bytes = self.client.synthesize(speech_text, language=provider_language, voice=selected_voice)
            path = write_audio(audio_bytes, resolved)
            with wave.open(str(path), "rb") as wav:
                frames = wav.getnframes()
                rate = wav.getframerate()
                channels = wav.getnchannels()
            return SpeechArtifact(
                path=path,
                provider_language=provider_language,
                voice=selected_voice,
                sample_rate=rate,
                channels=channels,
                duration_seconds=frames / rate,
                size_bytes=path.stat().st_size,
            )
        except TTSError as exc:
            timed_out = "timed out" in str(exc).casefold()
            raise TTSStageError("timeout" if timed_out else "provider_error", str(exc), retryable=timed_out) from exc
        except (OSError, wave.Error, ZeroDivisionError) as exc:
            raise TTSStageError("invalid_audio", "Timbre output could not be saved as a valid WAV file.") from exc
        except Exception as exc:
            raise TTSStageError("provider_error", "GNANI Timbre speech generation failed.") from exc

