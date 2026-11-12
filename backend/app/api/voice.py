"""Authenticated Gnani speech endpoints for existing learning sessions."""
from __future__ import annotations

import tempfile
from collections import defaultdict, deque
from enum import Enum
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import current_student
from backend.app.api.sessions import owned_session
from backend.app.db.models import ChatMessage, LearningSession, SessionVoiceState, Student, StudentPreferences, utc_now
from backend.app.db.session import get_db
from backend.app.services.gnani_voice import (
    VoiceProviderNotConfigured,
    create_prisma_client,
    create_prisma_client_for_language,
    create_timbre_adapter,
)
from pocs.poc01_prisma_stt.prisma_stt import STTError, validate_audio
from pocs.poc04_adaptive_teaching.models import Language
from pocs.poc06_bilingual_voice.stt_adapter import PrismaTranscriptionAdapter, STTStageError
from pocs.poc06_bilingual_voice.tts_adapter import TTSStageError
from pocs.poc02_timbre_tts.timbre_tts import TTSError

router = APIRouter(prefix="/voice/sessions", tags=["voice"])
MAX_AUDIO_BYTES = 10 * 1024 * 1024
MAX_SPEECH_TEXT = 3000
WAV_CONTENT_TYPES = {"audio/wav", "audio/x-wav", "audio/wave", "application/octet-stream"}
_VOICE_RATE_LIMITS = {"transcribe": (10, 60.0), "speech": (20, 60.0)}
_voice_request_times: dict[tuple[str, str], deque[float]] = defaultdict(deque)
_voice_limit_lock = Lock()


def _enforce_voice_rate_limit(student_id: str, operation: str) -> None:
    limit, window_seconds = _VOICE_RATE_LIMITS[operation]
    now = monotonic()
    key = (student_id, operation)
    with _voice_limit_lock:
        times = _voice_request_times[key]
        while times and now - times[0] >= window_seconds:
            times.popleft()
        if len(times) >= limit:
            raise HTTPException(
                status_code=429,
                detail="Voice service request limit reached. Please try again shortly.",
                headers={"Retry-After": str(max(1, int(window_seconds - (now - times[0]))))},
            )
        times.append(now)


@router.get("/provider-mode")
def voice_provider_mode(student: Student = Depends(current_student)):
    """Report configured readiness only; this route never calls Gnani."""
    try:
        create_prisma_client()
        create_timbre_adapter(tempfile.gettempdir())
    except VoiceProviderNotConfigured:
        return {"mode": "unavailable", "configured": False}
    return {"mode": "live", "configured": True}


class LanguageMode(str, Enum):
    english = "english"
    telugu = "telugu"
    mixed = "mixed"


class TranscriptionResponse(BaseModel):
    session_id: str
    transcript: str
    detected_language: str | None = None
    language_mode: LanguageMode


class SpeechRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_SPEECH_TEXT)
    language: LanguageMode | None = None

    @field_validator("text")
    @classmethod
    def nonblank_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Text cannot be blank")
        return value


PlaybackState = Literal["idle", "listening", "thinking", "speaking", "paused", "interrupted", "error"]
ResumeStatus = Literal["none", "awaiting_confirmation", "resumed", "dismissed"]


class VoiceLessonStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson_step: str = Field(default="introduction", min_length=1, max_length=120)
    student_question: str | None = Field(default=None, max_length=1000)
    active_response_language: LanguageMode
    playback_state: PlaybackState
    voice_transcript: str | None = Field(default=None, max_length=4000)
    checkpoint_message_id: str | None = Field(default=None, max_length=36)
    checkpoint_playback_ms: int | None = Field(default=None, ge=0, le=86_400_000)
    resume_status: ResumeStatus = "none"

    @field_validator("lesson_step")
    @classmethod
    def nonblank_lesson_step(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Lesson step cannot be blank")
        return value


class VoiceLessonStateResponse(VoiceLessonStateUpdate):
    session_id: str
    topic: str
    updated_at: str | None = None


def _owned(session_id: str, student: Student, db: Session) -> LearningSession:
    return owned_session(session_id, student, db)


@router.get("/{session_id}/state", response_model=VoiceLessonStateResponse)
def get_voice_state(
    session_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    session = _owned(session_id, student, db)
    state = db.get(SessionVoiceState, session_id)
    preferences = db.get(StudentPreferences, student.id)
    if state is None:
        return VoiceLessonStateResponse(
            session_id=session_id,
            topic=session.topic,
            active_response_language=preferences.preferred_language if preferences else session.language,
            playback_state="idle",
        )
    return VoiceLessonStateResponse(
        session_id=session_id,
        topic=session.topic,
        lesson_step=state.lesson_step,
        student_question=state.student_question,
        active_response_language=state.active_response_language,
        playback_state=state.playback_state,
        voice_transcript=state.voice_transcript,
        checkpoint_message_id=state.checkpoint_message_id,
        checkpoint_playback_ms=state.checkpoint_playback_ms,
        resume_status=state.resume_status,
        updated_at=state.updated_at.isoformat(),
    )


@router.put("/{session_id}/state", response_model=VoiceLessonStateResponse)
def put_voice_state(
    session_id: str,
    payload: VoiceLessonStateUpdate,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    session = _owned(session_id, student, db)
    state = db.get(SessionVoiceState, session_id)
    if state is None:
        state = SessionVoiceState(session_id=session_id)
    if payload.checkpoint_message_id:
        message = db.get(ChatMessage, payload.checkpoint_message_id)
        if message is None or message.session_id != session_id or message.role != "assistant":
            raise HTTPException(status_code=422, detail="Checkpoint must reference an assistant message in this session.")
    state.lesson_step = payload.lesson_step.strip()
    state.student_question = payload.student_question.strip() if payload.student_question else None
    state.active_response_language = payload.active_response_language.value
    state.playback_state = payload.playback_state
    state.voice_transcript = payload.voice_transcript
    state.checkpoint_message_id = payload.checkpoint_message_id
    state.checkpoint_playback_ms = payload.checkpoint_playback_ms
    state.resume_status = payload.resume_status
    state.updated_at = utc_now()
    db.add(state)
    db.commit()
    db.refresh(state)
    return VoiceLessonStateResponse(
        session_id=session_id,
        topic=session.topic,
        lesson_step=state.lesson_step,
        student_question=state.student_question,
        active_response_language=state.active_response_language,
        playback_state=state.playback_state,
        voice_transcript=state.voice_transcript,
        checkpoint_message_id=state.checkpoint_message_id,
        checkpoint_playback_ms=state.checkpoint_playback_ms,
        resume_status=state.resume_status,
        updated_at=state.updated_at.isoformat(),
    )


@router.post("/{session_id}/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    session_id: str,
    audio: Annotated[UploadFile, File()],
    language: Annotated[LanguageMode, Form()] = LanguageMode.mixed,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    _owned(session_id, student, db)
    _enforce_voice_rate_limit(student.id, "transcribe")
    filename = Path(audio.filename or "").name
    if Path(filename).suffix.casefold() != ".wav":
        raise HTTPException(status_code=415, detail="Upload an uncompressed PCM WAV audio file.")
    if audio.content_type and audio.content_type.casefold() not in WAV_CONTENT_TYPES:
        raise HTTPException(status_code=415, detail="Upload an uncompressed PCM WAV audio file.")

    try:
        data = await audio.read(MAX_AUDIO_BYTES + 1)
    finally:
        await audio.close()
    if not data:
        raise HTTPException(status_code=422, detail="Audio upload is empty.")
    if len(data) > MAX_AUDIO_BYTES:
        raise HTTPException(status_code=413, detail="Audio exceeds the 10 MB limit.")

    try:
        with tempfile.TemporaryDirectory(prefix="bhashalearn-stt-") as folder:
            path = Path(folder) / f"{uuid4().hex}.wav"
            path.write_bytes(data)
            validate_audio(path)
            try:
                provider = create_prisma_client_for_language(language.value)
            except VoiceProviderNotConfigured as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from exc
            try:
                result = await run_in_threadpool(PrismaTranscriptionAdapter(provider).transcribe, path)
            except STTStageError as exc:
                # The reused POC adapter emits safe, credential-free provider errors.
                if exc.code == "timeout":
                    raise HTTPException(status_code=504, detail="Gnani Prisma transcription timed out.") from exc
                raise HTTPException(status_code=502, detail="Gnani Prisma transcription failed or returned an invalid response.") from exc
    except STTError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return TranscriptionResponse(
        session_id=session_id,
        transcript=result.text,
        detected_language=result.detected_language,
        language_mode=language,
    )


@router.post("/{session_id}/speech")
def synthesize_speech(
    session_id: str,
    payload: SpeechRequest,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    session = _owned(session_id, student, db)
    _enforce_voice_rate_limit(student.id, "speech")
    try:
        selected_language = payload.language or LanguageMode(session.language)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Session has an unsupported language mode.") from exc
    try:
        language = Language(selected_language.value)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Use english, telugu, or mixed language mode.") from exc
    try:
        with tempfile.TemporaryDirectory(prefix="bhashalearn-tts-") as folder:
            adapter = create_timbre_adapter(folder)
            artifact = adapter.synthesize_response(payload.text, language, session_id)
            audio_bytes = artifact.path.read_bytes()
    except VoiceProviderNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except TTSStageError as exc:
        code = 504 if exc.code == "timeout" else 502
        raise HTTPException(status_code=code, detail=f"Gnani Timbre speech generation failed ({exc.provider_category}).") from exc
    except TTSError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return Response(
        content=audio_bytes,
        media_type="audio/wav",
        headers={"Cache-Control": "no-store", "X-Audio-Sample-Rate": str(artifact.sample_rate)},
    )
