"""AI tutor chat endpoint using saved sessions and student preferences."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.api.sessions import owned_session
from backend.app.db.models import ChatMessage, Student, StudentPreferences
from backend.app.db.session import get_db
from backend.app.services.tutor import build_instruction, generate_tutor_reply

router = APIRouter(prefix="/tutor", tags=["AI tutor"])


class TutorRequest(BaseModel):
    message: str = Field(min_length=1, max_length=4000)

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class TutorResponse(BaseModel):
    session_id: str
    reply: str
    language: str
    learning_level: str


@router.post("/sessions/{session_id}/chat", response_model=TutorResponse)
def tutor_chat(
    session_id: str,
    payload: TutorRequest,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    session = owned_session(session_id, student, db)
    prefs = db.get(StudentPreferences, student.id)
    level = prefs.learning_level if prefs else "beginner"
    goal = prefs.learning_goal if prefs else None
    language = prefs.preferred_language if prefs else session.language
    instruction = build_instruction(session.topic, language, level, goal)
    # Retrieve at most 19 recent messages plus the current user message.
    prior = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
        .limit(19)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(prior)]
    history.append({"role": "user", "content": payload.message})
    # Provider failures must not persist a partial conversation.
    reply = generate_tutor_reply(instruction, history)
    db.add_all([
        ChatMessage(session_id=session_id, role="user", content=payload.message),
        ChatMessage(session_id=session_id, role="assistant", content=reply),
    ])
    db.commit()
    return TutorResponse(session_id=session_id, reply=reply, language=language, learning_level=level)
