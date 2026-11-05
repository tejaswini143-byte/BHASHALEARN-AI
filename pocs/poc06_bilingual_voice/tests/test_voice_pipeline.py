from pathlib import Path

import pytest

from pocs.poc03_bilingual_llm.tutor import Tutor
from pocs.poc04_adaptive_teaching.evaluation import DeterministicEvaluator, ObjectiveQuestion, StructuredLLMEvaluator
from pocs.poc04_adaptive_teaching.models import Difficulty, Language, Outcome
from pocs.poc05_shared_session_context.manager import SessionManager
from pocs.poc05_shared_session_context.runtime import SharedSessionRuntime
from pocs.poc06_bilingual_voice.audio import AudioInputError
from pocs.poc06_bilingual_voice.stt_adapter import STTStageError, TranscriptionResult
from pocs.poc06_bilingual_voice.tests.helpers import sample_wav
from pocs.poc06_bilingual_voice.tts_adapter import SpeechArtifact, TTSStageError
from pocs.poc06_bilingual_voice.voice_pipeline import VoicePipeline


class FakeProvider:
    def __init__(self, responses=None, error=None):
        self.responses = list(responses or [])
        self.error = error
        self.calls = []

    def complete(self, messages):
        self.calls.append(messages)
        if self.error:
            raise self.error
        return self.responses.pop(0) if self.responses else "A helpful bilingual lesson response."


class FakeSTT:
    def __init__(self, results=None, error=None):
        self.results = list(results or [])
        self.error = error
        self.calls = []

    def transcribe(self, audio_path):
        self.calls.append(audio_path)
        if self.error:
            raise self.error
        return self.results.pop(0)


class FakeTTS:
    def __init__(self, tmp_path, error=None, errors=None):
        self.tmp_path = tmp_path
        self.error = error
        self.errors = list(errors or [])
        self.calls = []
        self.count = 0

    def synthesize_response(self, text, language, session_id, output_path=None):
        self.calls.append((text, language, session_id))
        current_error = self.errors.pop(0) if self.errors else self.error
        if current_error:
            raise current_error
        self.count += 1
        path = self.tmp_path / f"output-{self.count}.wav"
        path.write_bytes(sample_wav(frames=480, sample_rate=48000))
        return SpeechArtifact(path, "en-IN", "Kaveri", 48000, 1, 0.01, path.stat().st_size)


def make_pipeline(tmp_path, *, transcript="Explain fractions", language=Language.ENGLISH, provider=None, evaluator=None, stt_error=None, tts_error=None, tts_errors=None):
    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(sample_wav())
    manager = SessionManager()
    context = manager.create_session("learner", "fractions", language, lesson_objective="Understand fractions")
    provider = provider or FakeProvider()
    tutor = Tutor(provider, language=language.value, level=context.difficulty.value)
    runtime = SharedSessionRuntime(manager, context.session_id, tutor, evaluator or DeterministicEvaluator())
    raw = {"transcript": transcript, "detected_language_code": "en"}
    stt = FakeSTT([TranscriptionResult(transcript, "en", raw)], stt_error)
    tts = FakeTTS(tmp_path, tts_error, tts_errors)
    pipeline = VoicePipeline(stt, runtime, tts, manager)
    return pipeline, manager, context, provider, stt, tts, audio_path


def test_pipeline_success_returns_transcript_response_wav_context_and_latency(tmp_path):
    pipeline, manager, context, provider, stt, tts, audio = make_pipeline(tmp_path)
    result = pipeline.process_audio(context.session_id, audio)
    assert result.status == "success"
    assert result.transcript.text == "Explain fractions"
    assert result.tutor_response == "A helpful bilingual lesson response."
    assert result.audio.path.is_file()
    assert result.topic == "fractions"
    assert result.language is Language.ENGLISH
    assert result.difficulty is Difficulty.BEGINNER
    assert set(("audio_validation", "stt", "tutor", "tts", "total")).issubset(result.latency_seconds)
    assert stt.calls and tts.calls and provider.calls
    assert manager.get_session(context.session_id).conversation_history[-2].content == "Explain fractions"


def test_invalid_audio_does_not_call_any_provider(tmp_path):
    pipeline, _, context, provider, stt, tts, _ = make_pipeline(tmp_path)
    invalid = tmp_path / "not-a-wav.wav"
    invalid.write_bytes(b"invalid")
    result = pipeline.process_audio(context.session_id, invalid)
    assert result.status == "failed"
    assert result.errors[0].stage == "audio"
    assert stt.calls == provider.calls == tts.calls == []


def test_missing_audio_path_is_reported_without_provider_calls(tmp_path):
    pipeline, _, context, provider, stt, tts, _ = make_pipeline(tmp_path)
    result = pipeline.process_audio(context.session_id, tmp_path / "missing.wav")
    assert result.errors[0].stage == "audio"
    assert stt.calls == provider.calls == tts.calls == []


def test_empty_pcm_audio_is_rejected_without_provider_calls(tmp_path):
    pipeline, _, context, provider, stt, tts, _ = make_pipeline(tmp_path)
    empty_path = tmp_path / "empty.wav"
    empty_path.write_bytes(sample_wav(frames=0))
    result = pipeline.process_audio(context.session_id, empty_path)
    assert result.errors[0].code == "invalid_audio"
    assert stt.calls == provider.calls == tts.calls == []


def test_prisma_failure_stops_before_gemini_or_timbre(tmp_path):
    pipeline, _, context, provider, stt, tts, audio = make_pipeline(
        tmp_path, stt_error=STTStageError("provider_error", "GNANI returned HTTP 503.")
    )
    result = pipeline.process_audio(context.session_id, audio)
    assert result.errors[0].stage == "stt"
    assert result.tutor_response is None and result.audio is None
    assert stt.calls and provider.calls == tts.calls == []


def test_stt_timeout_is_retryable_and_does_not_mutate_session(tmp_path):
    pipeline, manager, context, provider, _, tts, audio = make_pipeline(
        tmp_path, stt_error=STTStageError("timeout", "GNANI request timed out.", True)
    )
    result = pipeline.process_audio(context.session_id, audio)
    assert result.errors[0].retryable
    assert result.errors[0].code == "timeout"
    assert manager.get_session(context.session_id).learning_state.attempts == 0
    assert provider.calls == tts.calls == []


def test_empty_transcript_stops_before_tutor_and_tts(tmp_path):
    pipeline, _, context, provider, stt, tts, audio = make_pipeline(tmp_path, transcript="")
    result = pipeline.process_audio(context.session_id, audio)
    assert result.transcript.text == ""
    assert result.errors[0].code == "no_speech"
    assert provider.calls == tts.calls == []
    assert stt.calls


@pytest.mark.parametrize("language,token", [
    (Language.ENGLISH, "English"),
    (Language.TELUGU, "Telugu"),
    (Language.MIXED, "code-mixing"),
])
def test_selected_language_reaches_tutor_and_context(tmp_path, language, token):
    pipeline, _, context, provider, _, _, audio = make_pipeline(tmp_path, language=language)
    result = pipeline.process_audio(context.session_id, audio)
    assert result.language is language
    assert token in provider.calls[0][0]["content"]


def test_language_override_persists_in_shared_session(tmp_path):
    pipeline, manager, context, provider, _, _, audio = make_pipeline(tmp_path, language=Language.ENGLISH)
    result = pipeline.process_audio(context.session_id, audio, language_override="telugu")
    assert result.language is Language.TELUGU
    assert manager.get_session(context.session_id).language is Language.TELUGU
    assert "Telugu" in provider.calls[0][0]["content"]


def test_follow_up_uses_same_topic_and_bounded_tutor_history(tmp_path):
    pipeline, manager, context, provider, stt, _, audio = make_pipeline(tmp_path)
    pipeline.process_audio(context.session_id, audio)
    stt.results.append(TranscriptionResult("Give another example", "en", {"transcript": "Give another example"}))
    second = pipeline.process_audio(context.session_id, audio)
    sent_messages = provider.calls[-1]
    assert second.topic == "fractions"
    assert any("Explain fractions" in message["content"] for message in sent_messages)
    assert any("A helpful bilingual lesson response." in message["content"] for message in sent_messages)
    assert manager.get_session(context.session_id).learning_state.mastery_score == 0.5


def test_adaptive_voice_answers_update_mastery_without_reset(tmp_path):
    pipeline, manager, context, _, stt, _, audio = make_pipeline(tmp_path)
    objective = ObjectiveQuestion(("2/4", "1/2"))
    wrong = pipeline.process_audio(context.session_id, audio, question="Which fraction equals one half?", objective=objective)
    assert wrong.adaptive_strategy == "hint"
    assert wrong.mastery_score == pytest.approx(0.4)
    stt.results.append(TranscriptionResult("2/4", "en", {"transcript": "2/4"}))
    correct = pipeline.process_audio(context.session_id, audio, question="Which fraction equals one half?", objective=objective)
    current = manager.get_session(context.session_id).learning_state
    assert correct.mastery_score == pytest.approx(0.5)
    assert current.attempts == 2
    assert current.hint_usage == 1
    assert current.session_id == context.session_id


def test_tts_failure_keeps_transcript_tutor_response_and_learning_context(tmp_path):
    pipeline, manager, context, _, _, tts, audio = make_pipeline(tmp_path, tts_error=TTSStageError("provider_error", "GNANI HTTP 503."))
    result = pipeline.process_audio(context.session_id, audio)
    current = manager.get_session(context.session_id)
    assert result.status == "partial_success"
    assert result.transcript.text
    assert result.tutor_response
    assert result.audio is None
    assert result.errors[0].stage == "tts"
    assert len(tts.calls) == 1
    assert current.conversation_history


def test_empty_tutor_response_does_not_call_tts(tmp_path):
    pipeline, _, context, _, _, tts, audio = make_pipeline(tmp_path, provider=FakeProvider(responses=[""]))
    result = pipeline.process_audio(context.session_id, audio)
    assert result.tutor_response is None
    assert result.audio is None
    assert result.errors[0].code == "empty_response"
    assert tts.calls == []


def test_tutor_provider_failure_is_reported_without_audio_or_learning_corruption(tmp_path):
    pipeline, manager, context, _, _, tts, audio = make_pipeline(tmp_path, provider=FakeProvider(error=RuntimeError("provider secret")))
    result = pipeline.process_audio(context.session_id, audio)
    assert result.errors[0].stage == "tutor"
    assert "provider secret" not in result.errors[0].message
    assert manager.get_session(context.session_id).learning_state.attempts == 0
    assert tts.calls == []


def test_invalid_structured_evaluation_does_not_update_mastery_or_generate_audio(tmp_path):
    provider = FakeProvider(responses=["not valid json", "I could not evaluate that safely."])
    evaluator = StructuredLLMEvaluator(provider)
    pipeline, manager, context, _, _, tts, audio = make_pipeline(tmp_path, provider=provider, evaluator=evaluator)
    result = pipeline.process_audio(context.session_id, audio, question="Explain a fraction")
    assert any(error.stage == "evaluation" for error in result.errors)
    assert result.audio is None
    assert manager.get_session(context.session_id).learning_state.attempts == 0
    assert tts.calls == []


def test_tts_saved_response_retry_does_not_repeat_stt_or_tutor(tmp_path):
    pipeline, _, context, provider, stt, tts, audio = make_pipeline(
        tmp_path,
        tts_errors=[TTSStageError("timeout", "GNANI TTS request timed out.", True), None],
    )
    first = pipeline.process_audio(context.session_id, audio)
    assert first.errors[0].retryable
    provider_calls, stt_calls = len(provider.calls), len(stt.calls)
    artifact = pipeline.synthesize_saved_response(context.session_id, first.tutor_response, Language.ENGLISH)
    assert artifact.path.exists()
    assert len(provider.calls) == provider_calls
    assert len(stt.calls) == stt_calls


def test_multiple_students_keep_separate_progress(tmp_path):
    pipeline, manager, first, _, stt, _, audio = make_pipeline(tmp_path)
    second = manager.create_session("student-2", "decimals", Language.TELUGU)
    objective = ObjectiveQuestion(("2/4",))
    pipeline.process_audio(first.session_id, audio, question="q", objective=objective)
    from pocs.poc03_bilingual_llm.tutor import Tutor
    from pocs.poc05_shared_session_context.runtime import SharedSessionRuntime
    other_tutor = Tutor(FakeProvider(), language="telugu")
    other_runtime = SharedSessionRuntime(manager, second.session_id, other_tutor, DeterministicEvaluator())
    assert manager.get_session(second.session_id).learning_state.attempts == 0
    assert manager.get_session(second.session_id).topic == "decimals"
    assert manager.get_session(first.session_id).learning_state.attempts == 1


def test_ended_session_rejects_audio_before_provider_calls(tmp_path):
    pipeline, manager, context, provider, stt, tts, audio = make_pipeline(tmp_path)
    manager.end_session(context.session_id)
    result = pipeline.process_audio(context.session_id, audio)
    assert result.errors[0].stage == "session"
    assert stt.calls == provider.calls == tts.calls == []


def test_invalid_session_is_structured_and_stops_pipeline(tmp_path):
    pipeline, _, _, provider, stt, tts, audio = make_pipeline(tmp_path)
    result = pipeline.process_audio("no-session", audio)
    assert result.errors[0].code == "not_found"
    assert result.topic is None
    assert provider.calls == stt.calls == tts.calls == []


def test_session_bound_runtime_rejects_another_students_session(tmp_path):
    pipeline, manager, _, provider, stt, tts, audio = make_pipeline(tmp_path)
    other = manager.create_session("student-2", "decimals", Language.TELUGU)
    result = pipeline.process_audio(other.session_id, audio)
    assert result.errors[0].code == "runtime_mismatch"
    assert result.topic == "decimals"
    assert provider.calls == stt.calls == tts.calls == []
    assert manager.get_session(other.session_id).learning_state.attempts == 0

