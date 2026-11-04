import pytest
from timbre_tts import TimbreConfig, TimbreTTSAdapter, TTSError, validate_text, write_audio


def test_valid_text():
    assert validate_text("  Hello Telugu!  ") == "Hello Telugu!"


def test_empty_text():
    with pytest.raises(TTSError, match="non-empty"):
        validate_text("  ")


def test_long_text():
    with pytest.raises(TTSError, match="3000"):
        validate_text("a" * 3001)


def test_write_audio(tmp_path):
    result = write_audio(b"fake-audio", tmp_path / "out.bin")
    assert result.read_bytes() == b"fake-audio"


def test_empty_audio(tmp_path):
    with pytest.raises(TTSError, match="audio bytes"):
        write_audio(b"", tmp_path / "out.bin")


def test_live_call_blocked_without_verified_schema():
    config = TimbreConfig(api_key="test", url="https://example.test/tts")
    with pytest.raises(TTSError, match="not enabled"):
        TimbreTTSAdapter(config).synthesize("Hello")
