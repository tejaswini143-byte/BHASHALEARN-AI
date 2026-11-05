"""STT -> shared POC-03/04/05 tutor context -> TTS orchestration."""
from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from pocs.poc01_prisma_stt.prisma_stt import STTError, validate_audio
from pocs.poc04_adaptive_teaching.evaluation import ObjectiveQuestion
from pocs.poc04_adaptive_teaching.models import Difficulty, Language
from pocs.poc03_bilingual_llm.llm_client import LLMProviderError
from pocs.poc05_shared_session_context.context import TeachingContext
from pocs.poc05_shared_session_context.manager import SessionEndedError, SessionManager, SessionNotFoundError
from pocs.poc05_shared_session_context.runtime import SharedSessionRuntime

from .stt_adapter import PrismaTranscriptionAdapter, STTStageError, TranscriptionResult
from .tutor_guard import EmptyTutorResponseError, NonEmptyTutor
from .tts_adapter import SpeechArtifact, TimbreSpeechAdapter, TTSStageError


@dataclass(frozen=True)
class PipelineError:
    stage: str
    code: str
    message: str
    retryable: bool = False


@dataclass(frozen=True)
class VoicePipelineResult:
    session_id: str
    transcript: TranscriptionResult | None
    tutor_response: str | None
    topic: str | None
    language: Language | None
    difficulty: Difficulty | None
    mastery_score: float | None
    adaptive_strategy: str | None
    audio: SpeechArtifact | None
    latency_seconds: dict[str, float]
    errors: tuple[PipelineError, ...]

    @property
    def status(self) -> str:
        if self.audio is not None and not self.errors:
            return "success"
        if (self.transcript is not None and bool(self.transcript.text.strip())) or self.tutor_response is not None:
            return "partial_success"
        return "failed"


class VoicePipeline:
    def __init__(
        self,
        stt: PrismaTranscriptionAdapter,
        runtime: SharedSessionRuntime,
        tts: TimbreSpeechAdapter,
        manager: SessionManager,
    ):
        self.stt = stt
        self.runtime = runtime
        self.tts = tts
        self.manager = manager
        if not isinstance(runtime.tutor, NonEmptyTutor):
            runtime.tutor = NonEmptyTutor(runtime.tutor)

    def process_audio(
        self,
        session_id: str,
        audio_path: str | Path,
        language_override: Language | str | None = None,
        *,
        question: str | None = None,
        reference_answer: str = "",
        objective: ObjectiveQuestion | None = None,
    ) -> VoicePipelineResult:
        total_start = time.perf_counter()
        latencies: dict[str, float] = {}
        errors: list[PipelineError] = []
        transcript_result: TranscriptionResult | None = None
        tutor_response: str | None = None
        speech: SpeechArtifact | None = None
        decision = None

        try:
            context = self.manager.get_session(session_id)
        except SessionNotFoundError as exc:
            return self._result(session_id, None, None, None, None, latencies, [PipelineError("session", "not_found", str(exc))], total_start)
        if context.ended_at is not None:
            return self._result(session_id, None, None, context, None, latencies, [PipelineError("session", "ended", "Session has ended.")], total_start)
        # POC-05 runtimes are intentionally session-bound. Refuse a mismatched
        # session instead of accidentally writing one learner's transcript to
        # another learner's conversation history.
        if session_id != self.runtime.session_id:
            return self._result(
                session_id, None, None, context, None, latencies,
                [PipelineError("session", "runtime_mismatch", "Voice pipeline runtime is bound to a different session.")],
                total_start,
            )

        validation_start = time.perf_counter()
        try:
            validate_audio(Path(audio_path).expanduser())
        except STTError as exc:
            errors.append(PipelineError("audio", "invalid_audio", str(exc)))
            latencies["audio_validation"] = time.perf_counter() - validation_start
            return self._result(session_id, None, None, context, None, latencies, errors, total_start)
        except (OSError, TypeError, ValueError) as exc:
            errors.append(PipelineError("audio", "invalid_path", "Audio path is invalid or inaccessible."))
            latencies["audio_validation"] = time.perf_counter() - validation_start
            return self._result(session_id, None, None, context, None, latencies, errors, total_start)
        latencies["audio_validation"] = time.perf_counter() - validation_start

        if language_override is not None:
            try:
                self.runtime.switch_language(Language(language_override))
            except ValueError:
                errors.append(PipelineError("language", "unsupported_language", "Use english, telugu, or mixed."))
                return self._result(session_id, None, None, context, None, latencies, errors, total_start)

        stt_start = time.perf_counter()
        try:
            transcript_result = self.stt.transcribe(Path(audio_path).expanduser())
        except STTStageError as exc:
            latencies["stt"] = time.perf_counter() - stt_start
            errors.append(PipelineError("stt", exc.code, str(exc), exc.retryable))
            return self._result(session_id, None, None, None, None, latencies, errors, total_start)
        latencies["stt"] = time.perf_counter() - stt_start
        if not transcript_result.text.strip():
            errors.append(PipelineError("stt", "no_speech", "Prisma returned an empty transcript; no tutor request was sent."))
            return self._result(session_id, transcript_result, None, None, None, latencies, errors, total_start)

        tutor_start = time.perf_counter()
        try:
            if question:
                interaction = self.runtime.adaptive_answer(
                    question,
                    transcript_result.text,
                    reference_answer,
                    objective,
                    source="voice_transcript",
                )
                decision = interaction.decision
                tutor_response = interaction.response
                if decision is not None and not decision.evaluated:
                    errors.append(PipelineError("evaluation", "not_evaluated", decision.evaluation.feedback, retryable=False))
                    tutor_response = None
                elif self.runtime.tutor.last_failure == "empty_response":
                    errors.append(PipelineError("tutor", "empty_response", "Tutor returned no text; speech was not generated."))
                    tutor_response = None
                elif tutor_response.startswith("The teaching response is unavailable right now."):
                    errors.append(PipelineError("tutor", "provider_unavailable", "Tutor response generation failed after answer evaluation.", retryable=False))
                    tutor_response = None
            else:
                interaction = self.runtime.voice_transcript(transcript_result.text)
                tutor_response = interaction.response
        except EmptyTutorResponseError as exc:
            errors.append(PipelineError("tutor", "empty_response", str(exc)))
        except Exception as exc:
            timed_out = "timed out" in str(exc).casefold()
            safe_message = str(exc) if isinstance(exc, LLMProviderError) else "Bilingual tutor request failed."
            errors.append(PipelineError("tutor", "timeout" if timed_out else "provider_error", safe_message, retryable=timed_out and question is None))
        latencies["tutor"] = time.perf_counter() - tutor_start

        if tutor_response is not None and not tutor_response.strip():
            tutor_response = None
            errors.append(PipelineError("tutor", "empty_response", "Tutor returned no text; speech was not generated."))
        if tutor_response is None:
            return self._result(session_id, transcript_result, None, None, decision, latencies, errors, total_start)

        tts_start = time.perf_counter()
        try:
            current = self.manager.get_session(session_id)
            speech = self.tts.synthesize_response(tutor_response, current.language, session_id)
        except TTSStageError as exc:
            errors.append(PipelineError("tts", exc.code, str(exc), exc.retryable))
        except (SessionEndedError, SessionNotFoundError) as exc:
            errors.append(PipelineError("session", "unavailable", str(exc)))
        except Exception:
            errors.append(PipelineError("tts", "provider_error", "GNANI Timbre speech generation failed."))
        latencies["tts"] = time.perf_counter() - tts_start
        return self._result(session_id, transcript_result, tutor_response, None, decision, latencies, errors, total_start, speech)

    def synthesize_saved_response(
        self,
        session_id: str,
        text: str,
        language: Language | str | None = None,
    ) -> SpeechArtifact:
        """Retry only TTS from retained text; do not repeat STT, Gemini, or mastery updates."""
        context = self.manager.get_session(session_id)
        if context.ended_at is not None:
            raise SessionEndedError("session has ended")
        return self.tts.synthesize_response(text, language or context.language, session_id)

    def _result(
        self,
        session_id: str,
        transcript: TranscriptionResult | None,
        tutor_response: str | None,
        context,
        decision,
        latencies: dict[str, float],
        errors: list[PipelineError],
        total_start: float,
        speech: SpeechArtifact | None = None,
    ) -> VoicePipelineResult:
        if context is None:
            try:
                context = self.manager.get_session(session_id)
            except (SessionNotFoundError, SessionEndedError):
                context = None
        snapshot: TeachingContext | None = None
        if context is not None:
            snapshot = self.manager.get_teaching_context(session_id)
        latencies["total"] = time.perf_counter() - total_start
        return VoicePipelineResult(
            session_id=session_id,
            transcript=transcript,
            tutor_response=tutor_response,
            topic=snapshot.topic if snapshot else None,
            language=snapshot.language if snapshot else None,
            difficulty=snapshot.difficulty if snapshot else None,
            mastery_score=snapshot.mastery_score if snapshot else None,
            adaptive_strategy=(decision.strategy.value if decision is not None else snapshot.adaptive_strategy if snapshot else None),
            audio=speech,
            latency_seconds=dict(latencies),
            errors=tuple(errors),
        )

