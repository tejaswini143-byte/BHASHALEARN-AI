import wave

import pytest

from pocs.poc02_timbre_tts.timbre_tts import TimbreConfig
from pocs.poc04_adaptive_teaching.models import Language
from pocs.poc06_bilingual_voice.tests.helpers import sample_wav
from pocs.poc06_bilingual_voice.tts_adapter import TimbreSpeechAdapter, TTSStageError


class StubTimbre:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def synthesize(self, text, language="en-IN", voice=None):
        self.calls.append((text, language, voice))
        if self.error:
            raise self.error
        return sample_wav(frames=480, sample_rate=48000)


@pytest.mark.parametrize("language,api_language,voice", [
    (Language.ENGLISH, "en-IN", "Kaveri"),
    (Language.TELUGU, "te-IN", "Suhana"),
    (Language.MIXED, "auto", "Suhana"),
])
def test_language_maps_to_existing_timbre_contract(tmp_path, language, api_language, voice):
    client = StubTimbre()
    adapter = TimbreSpeechAdapter(client, TimbreConfig(api_key="test-only"), tmp_path)
    artifact = adapter.synthesize_response("నమస్కారం", language, "session-123")
    assert client.calls == [("నమస్కారం", api_language, voice)]
    assert artifact.path.exists()
    assert artifact.provider_language == api_language
    assert artifact.voice == voice
    assert artifact.sample_rate == 48000
    assert artifact.channels == 1
    with wave.open(str(artifact.path), "rb") as wav:
        assert wav.getnframes() > 0


def test_empty_text_does_not_call_timbre(tmp_path):
    client = StubTimbre()
    adapter = TimbreSpeechAdapter(client, TimbreConfig(api_key="test-only"), tmp_path)
    with pytest.raises(TTSStageError, match="non-empty"):
        adapter.synthesize_response("  ", Language.ENGLISH, "session")
    assert client.calls == []


def test_timbre_failure_and_timeout_are_structured(tmp_path):
    from pocs.poc02_timbre_tts.timbre_tts import TTSError

    failed = TimbreSpeechAdapter(StubTimbre(TTSError("GNANI HTTP 503: TTS request failed.")), TimbreConfig(api_key="test"), tmp_path)
    with pytest.raises(TTSStageError) as provider_error:
        failed.synthesize_response("Hello", Language.ENGLISH, "session")
    assert provider_error.value.code == "provider_error"

    timed = TimbreSpeechAdapter(StubTimbre(TTSError("GNANI TTS request timed out.")), TimbreConfig(api_key="test"), tmp_path)
    with pytest.raises(TTSStageError) as timeout_error:
        timed.synthesize_response("Hello", Language.ENGLISH, "session")
    assert timeout_error.value.code == "timeout"
    assert timeout_error.value.retryable


def test_output_path_cannot_escape_configured_audio_directory(tmp_path):
    adapter = TimbreSpeechAdapter(StubTimbre(), TimbreConfig(api_key="test"), tmp_path / "audio")
    with pytest.raises(TTSStageError, match="inside"):
        adapter.synthesize_response("Hello", Language.ENGLISH, "session", tmp_path / "outside.wav")

