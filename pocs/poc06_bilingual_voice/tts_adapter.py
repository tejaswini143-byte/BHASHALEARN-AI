"""Speech synthesis over POC-02's existing, verified single-language Timbre API."""
from __future__ import annotations

import io
import re
import unicodedata
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
    """Safe synthesis error with diagnostics that omit request text and credentials."""

    def __init__(
        self,
        code: str,
        message: str,
        retryable: bool = False,
        *,
        exception_type: str | None = None,
        http_status: int | None = None,
        provider_category: str | None = None,
    ):
        self.code = code
        self.retryable = retryable
        self.exception_type = exception_type
        self.http_status = http_status
        self.provider_category = provider_category or code
        details = [message]
        if self.exception_type:
            details.append(f"exception_type={self.exception_type}")
        if self.http_status is not None:
            details.append(f"http_status={self.http_status}")
        if self.provider_category:
            details.append(f"category={self.provider_category}")
        super().__init__("; ".join(details))


@dataclass(frozen=True)
class SpeechArtifact:
    path: Path
    provider_language: str
    voice: str
    sample_rate: int
    channels: int
    duration_seconds: float
    size_bytes: int


def speech_text(text: str) -> str:
    """Remove common Markdown/LaTeX presentation syntax while retaining words."""
    if not isinstance(text, str):
        raise TTSError("Text must be a non-empty string.")
    result = text.strip()
    # Fences and headings are visual formatting, not content to be spoken.
    result = re.sub(r"```(?:[A-Za-z0-9_+-]+)?\s*([\s\S]*?)```", r"\1", result)
    result = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", result)
    result = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", result)
    result = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", result)
    result = re.sub(r"(?m)^\s*(?:[-*+] |\d+[.)] )", "", result)
    result = result.replace("**", "").replace("__", "").replace("~~", "")
    result = result.replace("`", "")

    # Convert common math markup to words without asking Timbre to voice TeX.
    result = re.sub(r"\\frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"\1 over \2", result)
    result = re.sub(r"\\sqrt\s*\{([^{}]*)\}", r"square root of \1", result)
    result = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", result)
    substitutions = {
        r"\\times\b": " times ", r"\\cdot\b": " times ",
        r"\\div\b": " divided by ", r"\\pm\b": " plus or minus ",
        r"\\leq\b": " less than or equal to ", r"\\geq\b": " greater than or equal to ",
        r"\\neq\b": " not equal to ", r"\\approx\b": " approximately ",
        r"\\pi\b": " pi ", r"\\infty\b": " infinity ",
    }
    for pattern, replacement in substitutions.items():
        result = re.sub(pattern, replacement, result)
    for delimiter in (r"\(", r"\)", r"\[", r"\]", "$$", "$", r"\,", r"\;", r"\!"):
        result = result.replace(delimiter, " ")
    result = result.replace("\\", " ")
    result = result.replace("{", " ").replace("}", " ")
    result = result.replace("|", ", ")
    result = re.sub(r"(?m)^\s*[-:| ]{3,}\s*$", "", result)
    result = re.sub(r"[ \t]+", " ", result)
    result = re.sub(r"\s+([,.;:!?])", r"\1", result)
    return result.strip()


def _script_segments(text: str) -> list[tuple[str, str]]:
    """Group mixed text by Latin/Telugu script, assigning punctuation to neighbors."""
    chunks: list[tuple[str, str]] = []
    active: str | None = None
    pending = ""
    current = ""
    for char in text:
        codepoint = ord(char)
        if 0x0C00 <= codepoint <= 0x0C7F:
            script = "te-IN"
        elif char.isalpha() and "LATIN" in unicodedata.name(char, ""):
            script = "en-IN"
        else:
            script = None

        if script is None:
            if active is None:
                pending += char
            else:
                current += char
            continue
        if active is None:
            active = script
            current = pending + char
            pending = ""
        elif script == active:
            current += char
        else:
            if current.strip():
                chunks.append((active, current.strip()))
            active = script
            current = char
    if active is not None and current.strip():
        chunks.append((active, current.strip()))
    return chunks


def _combine_pcm_wavs(audio_parts: list[bytes]) -> tuple[bytes, int, int, int, int]:
    """Join WAV frames only when each POC-02 response has matching PCM format."""
    if not audio_parts:
        raise ValueError("No audio segments were generated.")
    params = None
    frames: list[bytes] = []
    frame_count = 0
    for part in audio_parts:
        with wave.open(io.BytesIO(part), "rb") as wav:
            current = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getcomptype())
            if current[3] != "NONE":
                raise ValueError("Timbre returned non-PCM audio.")
            if params is None:
                params = current
            elif current != params:
                raise ValueError("Timbre returned inconsistent audio formats between language segments.")
            frame_count += wav.getnframes()
            frames.append(wav.readframes(wav.getnframes()))
    if params is None or frame_count <= 0:
        raise ValueError("Timbre returned empty audio.")
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(params[0])
        wav.setsampwidth(params[1])
        wav.setframerate(params[2])
        wav.writeframes(b"".join(frames))
    return output.getvalue(), params[0], params[2], frame_count, params[1]


class TimbreSpeechAdapter:
    def __init__(self, client: TimbreTTSAdapter, config: TimbreConfig, output_dir: str | Path):
        if not isinstance(config, TimbreConfig):
            raise TypeError("TimbreSpeechAdapter requires a TimbreConfig, not a prebuilt client, as config.")
        self.client = client
        self.config = config
        self.output_dir = Path(output_dir).resolve()

    @classmethod
    def from_config(cls, config: TimbreConfig, output_dir: str | Path) -> "TimbreSpeechAdapter":
        if not isinstance(config, TimbreConfig):
            raise TypeError("from_config expects a TimbreConfig.")
        return cls(TimbreTTSAdapter(config), config, output_dir)

    def synthesize_response(
        self,
        text: str,
        language: Language | str,
        session_id: str,
        output_path: str | Path | None = None,
    ) -> SpeechArtifact:
        try:
            cleaned_text = speech_text(text)
            speech = validate_text(cleaned_text)
            selected_language = Language(language)
        except (TTSError, ValueError) as exc:
            raise TTSStageError("invalid_input", str(exc), exception_type=type(exc).__name__, provider_category="request_validation") from exc

        if selected_language is Language.MIXED:
            if self.config.voice:
                raise TTSStageError(
                    "unsupported_mixed_voice_override",
                    "Mixed speech uses the verified per-language Timbre voices; clear GNANI_TTS_VOICE to use those defaults.",
                    provider_category="configuration_validation",
                )
            segments = _script_segments(speech)
            if not segments:
                raise TTSStageError(
                    "unsupported_script",
                    "Mixed speech requires detectable Latin or Telugu-script text; no provider request was sent.",
                    provider_category="unsupported_language_script",
                )
        else:
            provider_language = "en-IN" if selected_language is Language.ENGLISH else "te-IN"
            segments = [(provider_language, speech)]

        safe_session = re.sub(r"[^A-Za-z0-9_-]", "_", session_id)[-24:] or "session"
        if output_path is None:
            candidate = self.output_dir / f"voice_{safe_session}_{uuid4().hex[:10]}.wav"
        else:
            candidate = Path(output_path)
            if not candidate.is_absolute():
                candidate = self.output_dir / candidate
        resolved = candidate.resolve()
        if not resolved.is_relative_to(self.output_dir):
            raise TTSStageError("invalid_output_path", "Audio output must stay inside the configured POC-06 output directory.", provider_category="local_path_validation")

        audio_parts: list[bytes] = []
        voices: list[str] = []
        try:
            for api_language, segment in segments:
                voice = self.config.voice or VOICES[api_language]
                audio_parts.append(self.client.synthesize(segment, language=api_language, voice=voice))
                if voice not in voices:
                    voices.append(voice)
            combined, channels, rate, frames, _sample_width = _combine_pcm_wavs(audio_parts)
            path = write_audio(combined, resolved)
            return SpeechArtifact(
                path=path,
                provider_language="+".join(dict.fromkeys(lang for lang, _ in segments)),
                voice="+".join(voices),
                sample_rate=rate,
                channels=channels,
                duration_seconds=frames / rate,
                size_bytes=path.stat().st_size,
            )
        except TTSError as exc:
            status = _http_status(str(exc))
            category, message, code, retryable = _classify_provider_error(str(exc), status)
            raise TTSStageError(
                code, message, retryable,
                exception_type=type(exc).__name__,
                http_status=status,
                provider_category=category,
            ) from exc
        except (OSError, wave.Error, ZeroDivisionError, ValueError) as exc:
            raise TTSStageError(
                "invalid_audio", "Timbre output could not be combined or saved as a valid PCM WAV.",
                exception_type=type(exc).__name__, provider_category="audio_response_validation",
            ) from exc
        except Exception as exc:
            status = getattr(getattr(exc, "response", None), "status_code", None)
            category, message, code, retryable = _classify_provider_error("", status)
            raise TTSStageError(
                code, message, retryable,
                exception_type=type(exc).__name__,
                http_status=status,
                provider_category=category,
            ) from exc


def _http_status(message: str) -> int | None:
    match = re.search(r"GNANI HTTP (\d{3})", message)
    return int(match.group(1)) if match else None


def _classify_provider_error(
    safe_error: str,
    status: int | None,
) -> tuple[str, str, str, bool]:
    folded = safe_error.casefold()
    if "timed out" in folded or "timeout" in folded:
        return "timeout", "GNANI Timbre request timed out.", "timeout", True
    if status in {401, 403}:
        return "authentication_or_scope", "GNANI rejected authentication or TTS permission.", "auth_error", False
    if status == 429:
        return "rate_limited", "GNANI rate limit reached; wait before retrying.", "rate_limited", True
    if status == 400:
        return "request_rejected", "GNANI rejected the TTS request; verify text, voice, language, and model settings.", "request_rejected", False
    if status is not None and status >= 500:
        return "provider_server_error", "GNANI Timbre reported a server error.", "provider_error", True
    if "supports timbre-v2.5 only" in folded or "choose a voice" in folded or "use en-in, te-in, or auto" in folded:
        return "configuration_validation", "Timbre configuration is incompatible with the supported POC-02 model, language, or voice settings.", "configuration_error", False
    if "invalid wav" in folded or "audio" in folded and "returned" in folded:
        return "invalid_audio_response", "GNANI returned an invalid audio response.", "invalid_audio", False
    if "content type" in folded:
        return "unexpected_content_type", "GNANI returned an unexpected response content type.", "invalid_response", False
    if "network request failed" in folded:
        return "network_error", "GNANI Timbre network request failed.", "network_error", True
    return "provider_error", "GNANI Timbre synthesis failed; inspect the safe exception diagnostics.", "provider_error", False
