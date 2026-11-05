"""Private student learning sessions and conversation history."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import ChatMessage, Course, LearningSession, Student
from backend.app.db.session import get_db

router = APIRouter(prefix="/sessions", tags=["learning sessions"])


class SessionCreate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    language: Literal["telugu", "english", "mixed"] = "mixed"
    course_id: str | None = None

    @field_validator("topic")
    @classmethod
    def nonblank_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic cannot be blank")
        return value


class SessionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    student_id: str
    course_id: str | None
    topic: str
    language: str
    created_at: datetime


class MessageCreate(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=20000)

    @field_validator("content")
    @classmethod
    def nonblank_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class MessageResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    session_id: str
    role: str
    content: str
    created_at: datetime


def owned_session(session_id: str, student: Student, db: Session) -> LearningSession:
    lesson_session = db.get(LearningSession, session_id)
    if lesson_session is None or lesson_session.student_id != student.id:
        # Avoid disclosing whether a different student's session exists.
        raise HTTPException(status_code=404, detail="Learning session not found")
    return lesson_session


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
def create_session(
    payload: SessionCreate,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    if payload.course_id is not None and db.get(Course, payload.course_id) is None:
        raise HTTPException(status_code=404, detail="Course not found")
    lesson_session = LearningSession(student_id=student.id, **payload.model_dump())
    db.add(lesson_session)
    db.commit()
    db.refresh(lesson_session)
    return lesson_session


@router.get("", response_model=list[SessionResponse])
def list_sessions(
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    stmt = (
        select(LearningSession)
        .where(LearningSession.student_id == student.id)
        .order_by(LearningSession.created_at.desc(), LearningSession.id.desc())
        .offset(offset).limit(limit)
    )
    return db.scalars(stmt).all()


@router.get("/{session_id}", response_model=SessionResponse)
def get_session(
    session_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    return owned_session(session_id, student, db)


@router.post("/{session_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def add_message(
    session_id: str,
    payload: MessageCreate,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    owned_session(session_id, student, db)
    message = ChatMessage(session_id=session_id, **payload.model_dump())
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
def list_messages(
    session_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    owned_session(session_id, student, db)
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        .offset(offset).limit(limit)
    )
    return db.scalars(stmt).all()
