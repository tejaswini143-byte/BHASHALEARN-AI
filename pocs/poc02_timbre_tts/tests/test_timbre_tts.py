import io
import wave

import pytest
import requests

try:
    # Repository-root pytest invocation (namespace package under ``pocs``).
    from pocs.poc02_timbre_tts.timbre_tts import (
        ENDPOINT, TimbreConfig, TimbreTTSAdapter, TTSError, validate_text, write_audio,
    )
except ModuleNotFoundError:
    # POC-directory invocation: this directory is pytest's import root.
    from timbre_tts import (
        ENDPOINT, TimbreConfig, TimbreTTSAdapter, TTSError, validate_text, write_audio,
    )


def sample_wav():
    stream = io.BytesIO()
    with wave.open(stream, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(bytes([1, 0]) * 160)
    return stream.getvalue()


def test_valid_text():
    assert validate_text("  Hello Telugu!  ") == "Hello Telugu!"


def test_empty_text():
    with pytest.raises(TTSError, match="non-empty"):
        validate_text("  ")


def test_long_text():
    with pytest.raises(TTSError, match="3000"):
        validate_text("a" * 3001)


def test_write_audio(tmp_path):
    audio = sample_wav()
    path = write_audio(audio, tmp_path / "out.wav")
    assert path.read_bytes() == audio


def test_normalize_gnani_sentinel_wav_sizes(tmp_path):
    audio = bytearray(sample_wav())
    audio[4:8] = b"\xff\xff\xff\xff"
    audio[40:44] = b"\xff\xff\xff\xff"
    path = write_audio(bytes(audio), tmp_path / "normalized.wav")

    normalized = path.read_bytes()
    assert int.from_bytes(normalized[4:8], "little") == len(normalized) - 8
    assert int.from_bytes(normalized[40:44], "little") == len(normalized) - 44
    with wave.open(str(path), "rb") as wav:
        assert wav.getnframes() == 160


def test_empty_audio(tmp_path):
    with pytest.raises(TTSError, match="audio bytes"):
        write_audio(b"", tmp_path / "out.wav")


def test_invalid_wav(tmp_path):
    with pytest.raises(TTSError, match="invalid WAV"):
        write_audio(b"not-a-wav", tmp_path / "out.wav")


class FakeResponse:
    def __init__(self, status=200, body=None, content_type="audio/wav"):
        self.status_code = status
        self.content = sample_wav() if body is None else body
        self.headers = {"Content-Type": content_type}

    def raise_for_status(self):
        if self.status_code >= 400:
            r = requests.Response()
            r.status_code = self.status_code
            r._content = self.content
            raise requests.HTTPError(str(self.status_code), response=r)

    def json(self):
        import json
        return json.loads(self.content)


class FakeSession:
    def __init__(self, response=None):
        self.response = response or FakeResponse()
        self.last = None

    def post(self, url, **kwargs):
        self.last = (url, kwargs)
        return self.response


@pytest.mark.parametrize("language,voice", [("en-IN", "Kaveri"), ("te-IN", "Suhana")])
def test_synthesize_request(language, voice):
    session = FakeSession()
    config = TimbreConfig(api_key="secret-test-key")
    result = TimbreTTSAdapter(config, session).synthesize("Test", language=language)
    assert result.startswith(b"RIFF")
    url, kwargs = session.last
    assert url == ENDPOINT
    assert kwargs["headers"]["X-API-Key-ID"] == "secret-test-key"
    assert kwargs["json"]["voice"] == voice
    assert kwargs["json"]["language"] == language
    assert kwargs["json"]["model"] == "timbre-v2.5"
    assert kwargs["json"]["audio_config"]["container"] == "wav"


def test_invalid_language():
    with pytest.raises(TTSError, match="en-IN"):
        TimbreTTSAdapter(TimbreConfig(api_key="test")).synthesize("Hello", "fr-FR")


def test_invalid_content_type():
    session = FakeSession(FakeResponse(content_type="application/json"))
    with pytest.raises(TTSError, match="content type"):
        TimbreTTSAdapter(TimbreConfig(api_key="test"), session).synthesize("Hello")


def test_invalid_api_key_error_safe():
    body = b'{"detail":{"error_code":"INVALID_API_KEY","message":"Unauthorized"}}'
    session = FakeSession(FakeResponse(status=401, body=body))
    with pytest.raises(TTSError, match="INVALID_API_KEY") as err:
        TimbreTTSAdapter(TimbreConfig(api_key="secret-test-key"), session).synthesize("Hello")
    assert "secret-test-key" not in str(err.value)


def test_scope_error():
    body = b'{"detail":{"error_code":"SCOPE_NOT_ALLOWED"}}'
    session = FakeSession(FakeResponse(status=403, body=body))
    with pytest.raises(TTSError, match="TTS permission"):
        TimbreTTSAdapter(TimbreConfig(api_key="test"), session).synthesize("Hello")


def test_missing_key(monkeypatch):
    monkeypatch.delenv("GNANI_API_KEY", raising=False)
    with pytest.raises(TTSError, match="GNANI_API_KEY"):
        TimbreConfig.from_env()
