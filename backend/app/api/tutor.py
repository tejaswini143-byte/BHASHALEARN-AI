"""AI tutor chat endpoint using saved sessions and student preferences."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.api.sessions import owned_session
from backend.app.db.models import ChatMessage, LearningMemory, LearningProgress, SessionVisualState, Student, StudentPreferences, utc_now
from backend.app.db.session import get_db
from backend.app.services.tutor import build_instruction, generate_tutor_reply
from backend.app.services.adaptive_learning import normalize_topic, recommend
from backend.app.services.visual_lessons import describe_visual_lesson, tutor_visual_reference

router = APIRouter(prefix="/tutor", tags=["AI tutor"])


def _next_turn_timestamps(latest_message_at: datetime | None) -> tuple[datetime, datetime]:
    """Assign the user and assistant messages distinct, chronological timestamps."""
    user_created_at = utc_now()
    if latest_message_at is not None:
        if latest_message_at.tzinfo is None:
            latest_message_at = latest_message_at.replace(tzinfo=timezone.utc)
        else:
            latest_message_at = latest_message_at.astimezone(timezone.utc)
        user_created_at = max(user_created_at, latest_message_at + timedelta(microseconds=1))
    assistant_created_at = user_created_at + timedelta(microseconds=1)
    return user_created_at, assistant_created_at


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
    visual_state = db.get(SessionVisualState, session_id)
    visual_lesson = (
        describe_visual_lesson(visual_state.visual_key, visual_state.start_node, visual_state.end_node)
        if visual_state is not None
        else None
    )
    progress = db.scalar(
        select(LearningProgress)
        .where(
            LearningProgress.student_id == student.id,
            LearningProgress.normalized_topic_key == normalize_topic(session.topic),
        )
        .order_by(LearningProgress.updated_at.desc(), LearningProgress.id.asc())
    )
    evidence_parts: list[str] = []
    if progress is not None and progress.evidence_attempts > 0:
        policy = recommend(progress.evidence_attempts, progress.correct_attempts, progress.incorrect_attempts)
        evidence_parts.append(
            f"Topic mastery from submitted objective practice: {progress.mastery_score:.1f}% "
            f"across {progress.evidence_attempts} scored answers ({progress.correct_attempts} correct, "
            f"{progress.incorrect_attempts} incorrect). Suggested teaching strategy: {policy.strategy}. "
            f"Next step: {policy.recommendation}"
        )
    recent_memories = db.scalars(
        select(LearningMemory)
        .where(LearningMemory.student_id == student.id)
        .order_by(LearningMemory.created_at.desc(), LearningMemory.id.desc())
        .limit(40)
    ).all()
    topic_memories = [
        memory.note[:300] for memory in recent_memories
        if normalize_topic(memory.topic) == normalize_topic(session.topic)
    ][:3]
    if topic_memories:
        evidence_parts.append("Student's saved notes for this topic (treat as learner context, not verified facts): " + " | ".join(topic_memories))
    learning_context = "\n".join(evidence_parts) if evidence_parts else None
    instruction = build_instruction(
        session.topic,
        language,
        level,
        goal,
        visual_context=tutor_visual_reference(visual_lesson),
        learning_context=learning_context,
    )
    # Use role order as a stable tie-break for legacy messages with equal timestamps.
    # The reverse below turns newest-first order into user-before-assistant chronology.
    role_order = case(
        (ChatMessage.role == "user", 0),
        (ChatMessage.role == "assistant", 1),
        else_=2,
    )
    # Retrieve at most 19 recent messages plus the current user message.
    prior = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), role_order.desc(), ChatMessage.id.desc())
        .limit(19)
    ).all()
    history = [{"role": m.role, "content": m.content} for m in reversed(prior)]
    history.append({"role": "user", "content": payload.message})
    # Provider failures must not persist a partial conversation.
    reply = generate_tutor_reply(instruction, history)
    user_created_at, assistant_created_at = _next_turn_timestamps(
        prior[0].created_at if prior else None
    )
    db.add_all([
        ChatMessage(
            session_id=session_id,
            role="user",
            content=payload.message,
            created_at=user_created_at,
        ),
        ChatMessage(
            session_id=session_id,
            role="assistant",
            content=reply,
            created_at=assistant_created_at,
        ),
    ])
    db.commit()
    return TutorResponse(session_id=session_id, reply=reply, language=language, learning_level=level)
