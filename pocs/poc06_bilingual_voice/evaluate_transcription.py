"""Repeatable local Prisma accuracy check for English, Telugu, and mixed WAV clips."""
from __future__ import annotations

import argparse
import re
import time
import unicodedata
import wave
from dataclasses import replace
from pathlib import Path

from pocs.poc01_prisma_stt.prisma_stt import PrismaConfig, STTError
from pocs.poc06_bilingual_voice.audio import AudioInputError, WavAudioInput
from pocs.poc06_bilingual_voice.config import load_provider_environment
from pocs.poc06_bilingual_voice.stt_adapter import PrismaTranscriptionAdapter, STTStageError


REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES = (
    ("English", "What is a mixed fraction?", "en-IN", "english"),
    ("Telugu", "మిశ్రమ భిన్నం అంటే ఏమిటి?", "te-IN", "telugu"),
    ("Mixed", "Mixed fraction అంటే ఏమిటి? ఒక example చెప్పండి.", "indic-auto", "mixed"),
)


def _normalize_words(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFC", text).casefold()
    tokens: list[str] = []
    current: list[str] = []
    for char in normalized:
        category = unicodedata.category(char)
        if category[0] in {"L", "M", "N"} or char == "_":
            current.append(char)
        elif current:
            tokens.append("".join(current))
            current = []
    if current:
        tokens.append("".join(current))
    return tokens


def _distance(reference: list[str], hypothesis: list[str]) -> int:
    previous = list(range(len(hypothesis) + 1))
    for row, ref_item in enumerate(reference, start=1):
        current = [row]
        for column, hyp_item in enumerate(hypothesis, start=1):
            current.append(min(
                current[-1] + 1,
                previous[column] + 1,
                previous[column - 1] + (ref_item != hyp_item),
            ))
        previous = current
    return previous[-1]


def word_error_rate(expected: str, actual: str) -> float:
    """WER over Unicode word tokens; it is a diagnostic for short fixed phrases."""
    reference = _normalize_words(expected)
    hypothesis = _normalize_words(actual)
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return _distance(reference, hypothesis) / len(reference)


def character_error_rate(expected: str, actual: str) -> float:
    """Code-point CER after NFC normalization and whitespace removal."""
    reference = list(re.sub(r"\s+", "", unicodedata.normalize("NFC", expected)))
    hypothesis = list(re.sub(r"\s+", "", unicodedata.normalize("NFC", actual)))
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return _distance(reference, hypothesis) / len(reference)


def _audio_format(path: Path) -> str:
    with wave.open(str(path), "rb") as audio:
        return (
            f"PCM WAV; {audio.getframerate()} Hz; {audio.getnchannels()} channel(s); "
            f"{audio.getsampwidth() * 8}-bit; {audio.getnframes() / audio.getframerate():.2f}s"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--english", required=True, help="PCM WAV recording of the English sample sentence")
    parser.add_argument("--telugu", required=True, help="PCM WAV recording of the Telugu sample sentence")
    parser.add_argument("--mixed", required=True, help="PCM WAV recording of the mixed sample sentence")
    args = parser.parse_args()
    recordings = {"english": args.english, "telugu": args.telugu, "mixed": args.mixed}

    load_provider_environment(REPO_ROOT)
    try:
        base_config = PrismaConfig.from_env()
    except STTError as exc:
        print(f"Configuration error: {exc}")
        return 2

    print(f"Model: {base_config.model}; output format: {base_config.output_format}")
    print("Expected sample phrases are fixed references; transcripts are displayed unchanged.")
    failures = 0
    for label, expected, language_code, key in SAMPLES:
        path = Path(recordings[key]).expanduser()
        print(f"\n[{label}] Expected: {expected}")
        print(f"Language configuration: language_code={language_code}; format={base_config.output_format}")
        try:
            capture = WavAudioInput.from_file(path)
            print(f"Audio: {_audio_format(capture.path)}")
            client = PrismaTranscriptionAdapter.from_config(replace(base_config, language=language_code))
            started = time.perf_counter()
            result = client.transcribe(capture.path)
            latency = time.perf_counter() - started
            print(f"Actual transcript (raw): {result.raw_text}")
            print(f"Detected language: {result.detected_language or 'not returned'}")
            print(f"Recognition latency: {latency:.3f}s")
            print(f"WER: {word_error_rate(expected, result.raw_text):.1%}")
            print(f"CER: {character_error_rate(expected, result.raw_text):.1%}")
        except (AudioInputError, STTStageError, STTError, OSError, wave.Error) as exc:
            failures += 1
            print(f"Evaluation failed: {exc}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
