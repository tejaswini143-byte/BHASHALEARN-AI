"""Authenticated Gnani speech endpoints for existing learning sessions."""
from __future__ import annotations

import tempfile
from enum import Enum
from pathlib import Path
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from backend.app.api.auth import current_student
from backend.app.api.sessions import owned_session
from backend.app.db.models import LearningSession, Student
from backend.app.db.session import get_db
from backend.app.services.gnani_voice import (
    VoiceProviderNotConfigured,
    create_prisma_client,
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


def _owned(session_id: str, student: Student, db: Session) -> LearningSession:
    return owned_session(session_id, student, db)


@router.post("/{session_id}/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(
    session_id: str,
    audio: Annotated[UploadFile, File()],
    language: Annotated[LanguageMode, Form()] = LanguageMode.mixed,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    _owned(session_id, student, db)
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
                provider = create_prisma_client()
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
