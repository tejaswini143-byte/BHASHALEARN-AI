import pytest

from pocs.poc01_prisma_stt.prisma_stt import Transcript, STTError
from pocs.poc06_bilingual_voice.stt_adapter import PrismaTranscriptionAdapter, STTStageError


class StubPrisma:
    def __init__(self, response=None, error=None):
        self.response = response or Transcript("fractions అంటే ఏమిటి?", "te", {"request_id": "r1"})
        self.error = error
        self.calls = []

    def transcribe(self, path):
        self.calls.append(path)
        if self.error:
            raise self.error
        return self.response


@pytest.mark.parametrize("text,language", [
    ("Explain fractions", "en"),
    ("భిన్నాలు అంటే ఏమిటి?", "te"),
    ("Fractions అంటే ఏమిటి?", "te-en"),
])
def test_transcript_text_and_language_are_preserved(text, language, tmp_path):
    raw = {"transcript": text, "detected_language_code": language}
    client = StubPrisma(Transcript(text, language, raw))
    result = PrismaTranscriptionAdapter(client).transcribe(tmp_path / "sample.wav")
    assert result.text == text
    assert result.detected_language == language
    assert result.raw_response is raw


def test_empty_successful_transcript_is_preserved_for_pipeline():
    result = PrismaTranscriptionAdapter(StubPrisma(Transcript("", None, {"success": True}))).transcribe("x.wav")
    assert result.text == ""
    assert result.raw_response["success"] is True


def test_prisma_failure_is_normalized_without_credentials():
    with pytest.raises(STTStageError, match="INVALID_API_KEY") as error:
        PrismaTranscriptionAdapter(StubPrisma(error=STTError("GNANI HTTP 401 (INVALID_API_KEY). Verify credentials."))).transcribe("x.wav")
    assert error.value.code == "provider_error"
    assert not error.value.retryable


def test_prisma_timeout_is_retryable():
    with pytest.raises(STTStageError) as error:
        PrismaTranscriptionAdapter(StubPrisma(error=STTError("GNANI request timed out."))).transcribe("x.wav")
    assert error.value.code == "timeout"
    assert error.value.retryable

