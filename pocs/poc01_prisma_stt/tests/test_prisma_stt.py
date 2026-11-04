import io
import wave
from pathlib import Path

import pytest
import requests

from prisma_stt import (
    PrismaConfig, PrismaSTTAdapter, STTError,
    normalize_response, validate_audio,
)


def make_wav(path: Path, seconds: int = 1):
    with wave.open(str(path), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(b"\x00\x00" * 16000 * seconds)


def test_valid_audio(tmp_path):
    file = tmp_path / "test.wav"
    make_wav(file)
    validate_audio(file)


def test_missing_audio(tmp_path):
    with pytest.raises(STTError, match="does not exist"):
        validate_audio(tmp_path / "missing.wav")


def test_long_audio(tmp_path):
    file = tmp_path / "long.wav"
    make_wav(file, 31)
    with pytest.raises(STTError, match="30 seconds"):
        validate_audio(file)


def test_normalize_response():
    result = normalize_response({"data": {"transcript": "Nenu DSA nerchukuntunnanu", "language": "te"}})
    assert result.text == "Nenu DSA nerchukuntunnanu"
    assert result.language == "te"


def test_missing_transcript():
    with pytest.raises(STTError, match="transcript"):
        normalize_response({"data": {}})


class FakeResponse:
    def raise_for_status(self):
        pass

    def json(self):
        return {"transcript": "Explain algorithms", "detected_language_code": "en"}


class FakeSession:
    def post(self, url, **kwargs):
        assert url == "https://example.test/stt"
        assert kwargs["headers"]["X-API-Key-ID"] == "test-key"
        assert kwargs["files"]["file"][2] == "audio/wav"
        return FakeResponse()


def test_adapter_mocked_request(tmp_path):
    file = tmp_path / "test.wav"
    make_wav(file)
    config = PrismaConfig(url="https://example.test/stt", api_key="test-key")
    result = PrismaSTTAdapter(config, session=FakeSession()).transcribe(file)
    assert result.text == "Explain algorithms"
