"""Authenticated shared session context and visual lesson state endpoints."""
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, model_validator
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.api.sessions import owned_session
from backend.app.db.models import (
    ChatMessage,
    SessionVisualState,
    Student,
    StudentPreferences,
    utc_now,
)
from backend.app.db.session import get_db
from backend.app.services.visual_lessons import VISUAL_LESSONS, VisualLesson, describe_visual_lesson

router = APIRouter(prefix="/sessions", tags=["shared session context"])
VisualKey = Literal["fractions-equivalent", "dijkstra-shortest-path"]
GraphNode = Literal["A", "B", "C", "D", "E", "F"]


class ContextMessage(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    role: Literal["user", "assistant"]
    content: str
    created_at: datetime


class VisualLessonResponse(BaseModel):
    visual_key: str
    title: str
    concept: str
    description: str
    start_node: str | None = None
    end_node: str | None = None
    updated_at: datetime


class SharedSessionContextResponse(BaseModel):
    session_id: str
    topic: str
    preferred_language: Literal["telugu", "english", "mixed"]
    learning_level: Literal["beginner", "intermediate", "advanced"]
    learning_pace: Literal["slow", "steady", "fast"]
    learning_goal: str | None
    messages: list[ContextMessage]
    visual_lesson: VisualLessonResponse | None


class VisualLessonUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    visual_key: VisualKey
    start_node: GraphNode | None = None
    end_node: GraphNode | None = None

    @model_validator(mode="after")
    def validate_graph_selection(self):
        if self.visual_key == "dijkstra-shortest-path":
            if self.start_node is None:
                self.start_node = "A"
            if self.end_node is None:
                self.end_node = "F"
        elif self.start_node is not None or self.end_node is not None:
            raise ValueError("Graph nodes are only valid for the Dijkstra lesson.")
        return self


def _visual_response(state: SessionVisualState | None) -> VisualLessonResponse | None:
    if state is None:
        return None
    lesson: VisualLesson | None = describe_visual_lesson(state.visual_key, state.start_node, state.end_node)
    if lesson is None:
        return None
    return VisualLessonResponse(
        visual_key=lesson.key,
        title=lesson.title,
        concept=lesson.concept,
        description=lesson.description,
        start_node=state.start_node,
        end_node=state.end_node,
        updated_at=state.updated_at,
    )


@router.get("/{session_id}/context", response_model=SharedSessionContextResponse)
def get_shared_session_context(
    session_id: str,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    limit: int = Query(default=100, ge=1, le=500),
):
    session = owned_session(session_id, student, db)
    preferences = db.get(StudentPreferences, student.id)
    role_order = case(
        (ChatMessage.role == "user", 0),
        (ChatMessage.role == "assistant", 1),
        else_=2,
    )
    recent = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), role_order.desc(), ChatMessage.id.desc())
        .limit(limit)
    ).all()
    visual_state = db.get(SessionVisualState, session_id)
    return SharedSessionContextResponse(
        session_id=session.id,
        topic=session.topic,
        preferred_language=preferences.preferred_language if preferences else session.language,
        learning_level=preferences.learning_level if preferences else "beginner",
        learning_pace=preferences.learning_pace if preferences else "steady",
        learning_goal=preferences.learning_goal if preferences else None,
        messages=[ContextMessage.model_validate(message) for message in reversed(recent)],
        visual_lesson=_visual_response(visual_state),
    )


@router.put("/{session_id}/visual-context", response_model=VisualLessonResponse)
def save_visual_context(
    session_id: str,
    payload: VisualLessonUpdate,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    owned_session(session_id, student, db)
    if payload.visual_key not in VISUAL_LESSONS:
        raise HTTPException(status_code=422, detail="Unsupported built-in visual lesson.")
    state = db.get(SessionVisualState, session_id)
    if state is None:
        state = SessionVisualState(session_id=session_id, visual_key=payload.visual_key)
    state.visual_key = payload.visual_key
    state.start_node = payload.start_node
    state.end_node = payload.end_node
    state.updated_at = utc_now()
    db.add(state)
    db.commit()
    db.refresh(state)
    response = _visual_response(state)
    if response is None:
        raise HTTPException(status_code=422, detail="Visual lesson state is invalid.")
    return response
