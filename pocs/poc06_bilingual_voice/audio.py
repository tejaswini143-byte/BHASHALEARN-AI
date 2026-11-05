"""WAV validation, optional microphone capture, and safe temporary-file cleanup."""
from __future__ import annotations

import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

from pocs.poc01_prisma_stt.prisma_stt import STTError, validate_audio


class AudioInputError(ValueError):
    """Invalid, empty, or unavailable audio input."""


@dataclass
class AudioCapture:
    path: Path
    temporary: bool = False

    def cleanup(self) -> None:
        if self.temporary:
            self.path.unlink(missing_ok=True)

    def __enter__(self) -> "AudioCapture":
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.cleanup()


class WavAudioInput:
    """Uses POC-01's verified PCM WAV constraints (10 MB and 30 second limits)."""

    @staticmethod
    def from_file(path: str | Path) -> AudioCapture:
        audio_path = Path(path).expanduser()
        try:
            validate_audio(audio_path)
        except STTError as exc:
            raise AudioInputError(str(exc)) from exc
        return AudioCapture(audio_path.resolve(), temporary=False)


class MicrophoneRecorder:
    """Optional sounddevice recorder; no microphone package is imported for WAV-only use."""

    def __init__(self, sample_rate: int = 16000, channels: int = 1, max_seconds: int = 30):
        if sample_rate < 1 or channels < 1 or not 1 <= max_seconds <= 30:
            raise AudioInputError("Invalid recording format or duration limit.")
        self.sample_rate = sample_rate
        self.channels = channels
        self.max_seconds = max_seconds

    def record(self, duration_seconds: float = 5.0) -> AudioCapture:
        if not 0 < duration_seconds <= self.max_seconds:
            raise AudioInputError(f"Recording duration must be between 0 and {self.max_seconds} seconds.")
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise AudioInputError("Microphone capture is optional; install sounddevice or provide a WAV file.") from exc

        frames = int(self.sample_rate * duration_seconds)
        if frames < 1:
            raise AudioInputError("Recording duration is too short.")
        capture_path: Path | None = None
        try:
            handle = tempfile.NamedTemporaryFile(prefix="bhashalearn_poc06_", suffix=".wav", delete=False)
            capture_path = Path(handle.name)
            handle.close()
            samples = sd.rec(frames, samplerate=self.sample_rate, channels=self.channels, dtype="int16")
            sd.wait()
            pcm = samples.tobytes()
            with wave.open(str(capture_path), "wb") as output:
                output.setnchannels(self.channels)
                output.setsampwidth(2)
                output.setframerate(self.sample_rate)
                output.writeframes(pcm)
            validate_audio(capture_path)
            return AudioCapture(capture_path, temporary=True)
        except AudioInputError:
            if capture_path is not None:
                capture_path.unlink(missing_ok=True)
            raise
        except Exception as exc:
            if capture_path is not None:
                capture_path.unlink(missing_ok=True)
            raise AudioInputError("Microphone recording failed; use a valid PCM WAV file instead.") from exc


def play_wav(path: str | Path) -> None:
    """Play a verified WAV using Windows' built-in player; saving remains available without playback."""
    audio_path = Path(path)
    if not audio_path.is_file() or audio_path.suffix.lower() != ".wav":
        raise AudioInputError("Audio playback requires an existing WAV file.")
    try:
        import winsound
        winsound.PlaySound(str(audio_path), winsound.SND_FILENAME)
    except (ImportError, RuntimeError, OSError) as exc:
        raise AudioInputError("WAV was saved, but this system could not play it automatically.") from exc

