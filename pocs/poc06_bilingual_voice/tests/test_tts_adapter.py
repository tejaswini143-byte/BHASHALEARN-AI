import wave

import pytest

from pocs.poc02_timbre_tts.timbre_tts import TimbreConfig, TimbreTTSAdapter, TTSError
from pocs.poc04_adaptive_teaching.models import Language
from pocs.poc06_bilingual_voice.tests.helpers import sample_wav
from pocs.poc06_bilingual_voice.tts_adapter import TimbreSpeechAdapter, TTSStageError, speech_text


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
    assert artifact.duration_seconds == pytest.approx(0.01)
    with wave.open(str(artifact.path), "rb") as wav:
        assert wav.getnframes() > 0


def test_mixed_language_uses_known_language_calls_and_joins_wavs(tmp_path):
    client = StubTimbre()
    adapter = TimbreSpeechAdapter(client, TimbreConfig(api_key="test-only"), tmp_path)
    artifact = adapter.synthesize_response("Hello fractions అంటే ఏమిటి?", Language.MIXED, "session")
    assert client.calls == [
        ("Hello fractions", "en-IN", "Kaveri"),
        ("అంటే ఏమిటి?", "te-IN", "Suhana"),
    ]
    assert artifact.provider_language == "en-IN+te-IN"
    assert artifact.voice == "Kaveri+Suhana"
    with wave.open(str(artifact.path), "rb") as wav:
        assert wav.getframerate() == 48000
        assert wav.getnframes() == 960


def test_mixed_text_without_supported_script_is_rejected_without_provider_call(tmp_path):
    client = StubTimbre()
    adapter = TimbreSpeechAdapter(client, TimbreConfig(api_key="test-only"), tmp_path)
    with pytest.raises(TTSStageError) as error:
        adapter.synthesize_response("123 + 456", Language.MIXED, "session")
    assert error.value.code == "unsupported_script"
    assert client.calls == []


def test_markdown_and_latex_are_cleaned_for_speech():
    result = speech_text("## **Answer**: \\(\\frac{1}{2}\\) and [one half](https://example.test)")
    assert result == "Answer: 1 over 2 and one half"


def test_fraction_text_is_rendered_as_readable_speech():
    assert speech_text("Compare 1/2 with 2 1/4.") == "Compare 1 over 2 with 2 and 1 over 4."


def test_speech_text_preserves_telugu_unicode():
    text = "మిశ్రమ భిన్నం (Mixed Fraction) అంటే 1/2 కంటే ఎక్కువ కావచ్చు."
    result = speech_text(text)
    assert "మిశ్రమ భిన్నం" in result
    assert "అంటే" in result
    assert "Mixed Fraction" in result
    assert "1 over 2" in result


def test_factory_reproduces_old_argument_mismatch_and_accepts_config(tmp_path):
    config = TimbreConfig(api_key="test-only")
    with pytest.raises(TypeError, match="expects a TimbreConfig"):
        TimbreSpeechAdapter.from_config(TimbreTTSAdapter(config), tmp_path)
    adapter = TimbreSpeechAdapter.from_config(config, tmp_path)
    assert isinstance(adapter.client, TimbreTTSAdapter)
    assert adapter.config is config


def test_empty_text_does_not_call_timbre(tmp_path):
    client = StubTimbre()
    adapter = TimbreSpeechAdapter(client, TimbreConfig(api_key="test-only"), tmp_path)
    with pytest.raises(TTSStageError, match="non-empty"):
        adapter.synthesize_response("  ", Language.ENGLISH, "session")
    assert client.calls == []


def test_timbre_failure_and_timeout_include_safe_diagnostics(tmp_path):
    failed = TimbreSpeechAdapter(StubTimbre(TTSError("GNANI HTTP 503: TTS request failed.")), TimbreConfig(api_key="test"), tmp_path)
    with pytest.raises(TTSStageError) as provider_error:
        failed.synthesize_response("Hello", Language.ENGLISH, "session")
    assert provider_error.value.code == "provider_error"
    assert provider_error.value.exception_type == "TTSError"
    assert provider_error.value.http_status == 503
    assert provider_error.value.provider_category == "provider_server_error"
    assert "test" not in str(provider_error.value)

    timed = TimbreSpeechAdapter(StubTimbre(TTSError("GNANI TTS request timed out.")), TimbreConfig(api_key="test"), tmp_path)
    with pytest.raises(TTSStageError) as timeout_error:
        timed.synthesize_response("Hello", Language.ENGLISH, "session")
    assert timeout_error.value.code == "timeout"
    assert timeout_error.value.retryable


def test_output_path_cannot_escape_configured_audio_directory(tmp_path):
    adapter = TimbreSpeechAdapter(StubTimbre(), TimbreConfig(api_key="test"), tmp_path / "audio")
    with pytest.raises(TTSStageError, match="inside"):
        adapter.synthesize_response("Hello", Language.ENGLISH, "session", tmp_path / "outside.wav")
