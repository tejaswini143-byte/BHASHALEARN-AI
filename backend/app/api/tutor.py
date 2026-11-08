"""AI tutor chat endpoint using saved sessions and student preferences."""
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.api.documents import get_embedding_provider
from backend.app.api.sessions import owned_session
from backend.app.db.models import ChatMessage, LearningAssessmentAttempt, LearningMemory, LearningProgress, SessionVisualState, Student, StudentPreferences, utc_now
from backend.app.db.session import get_db
from backend.app.services.tutor import build_instruction, generate_tutor_reply
from backend.app.services.adaptive_learning import normalize_topic, recommend
from backend.app.services.visual_lessons import describe_visual_lesson, tutor_visual_reference
from backend.app.services.embeddings import EmbeddingError, GeminiEmbeddingProvider
from backend.app.services.rag_tutor import (
    GeneratedAnswer,
    GenerationRequest,
    TeachingResponse,
    VectorPassageRetriever,
    orchestrate_tutoring,
)

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
    language: Literal["telugu", "english", "mixed"] | None = None

    @field_validator("message")
    @classmethod
    def clean_message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Message cannot be blank")
        return value


class TutorCitation(BaseModel):
    citation_id: str
    document_id: str
    document_title: str
    page_number: int


class TutorResponse(BaseModel):
    session_id: str
    reply: str
    language: str
    learning_level: str
    citations: list[TutorCitation] = Field(default_factory=list)
    grounded: bool = False
    retrieval_used: bool = False


@router.post("/sessions/{session_id}/chat", response_model=TutorResponse)
def tutor_chat(
    session_id: str,
    payload: TutorRequest,
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    embedding_provider: GeminiEmbeddingProvider = Depends(get_embedding_provider),
):
    session = owned_session(session_id, student, db)
    prefs = db.get(StudentPreferences, student.id)
    level = prefs.learning_level if prefs else "beginner"
    goal = prefs.learning_goal if prefs else None
    language = payload.language or (prefs.preferred_language if prefs else session.language)
    learning_pace = prefs.learning_pace if prefs else "steady"
    visual_state = db.get(SessionVisualState, session_id)
    visual_lesson = (
        describe_visual_lesson(visual_state.visual_key, visual_state.start_node, visual_state.end_node)
        if visual_state is not None
        else None
    )
    topic_key = normalize_topic(session.topic)
    progress = db.scalar(
        select(LearningProgress)
        .where(
            LearningProgress.student_id == student.id,
            LearningProgress.normalized_topic_key == topic_key,
        )
        .order_by(LearningProgress.updated_at.desc(), LearningProgress.id.asc())
    )
    recent_outcomes_desc = db.scalars(
        select(LearningAssessmentAttempt.is_correct)
        .where(
            LearningAssessmentAttempt.student_id == student.id,
            LearningAssessmentAttempt.normalized_topic_key == topic_key,
            LearningAssessmentAttempt.is_correct.is_not(None),
            LearningAssessmentAttempt.answered_at.is_not(None),
        )
        .order_by(LearningAssessmentAttempt.answered_at.desc(), LearningAssessmentAttempt.id.desc())
        .limit(5)
    ).all()
    recent_outcomes = tuple(bool(value) for value in reversed(recent_outcomes_desc))
    evidence_parts: list[str] = []
    if progress is not None and progress.evidence_attempts > 0:
        policy = recommend(
            progress.evidence_attempts,
            progress.correct_attempts,
            progress.incorrect_attempts,
            recent_outcomes=recent_outcomes,
        )
        mastery_score = max(0.0, min(100.0, float(progress.mastery_score)))
        evidence_parts.append(
            f"Topic mastery from submitted objective practice: {mastery_score:.1f}% "
            f"across {progress.evidence_attempts} scored answers ({progress.correct_attempts} correct, "
            f"{progress.incorrect_attempts} incorrect). Suggested teaching strategy: {policy.strategy}. "
            f"Next step: {policy.recommendation}"
        )
    else:
        evidence_parts.append(
            "No scored progress is available for this topic. Start with a short diagnostic question; "
            "do not infer the student's mastery."
        )
    if recent_outcomes:
        outcome_labels = ", ".join("correct" if outcome else "incorrect" for outcome in recent_outcomes)
        evidence_parts.append(
            "Recent scored outcomes for this topic (oldest to newest): " + outcome_labels + "."
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
        learning_pace=learning_pace,
    )
    # Use role order as a stable tie-break for legacy messages with equal timestamps.
    # The reverse below turns newest-first order into user-before-assistant chronology.
    role_order = case(
        (ChatMessage.role == "user", 0),
        (ChatMessage.role == "assistant", 1),
        else_=2,
    )
    # Retrieve at most 19 recent messages; the current message and retrieved
    # passages are added together in the generation adapter below.
    prior = db.scalars(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc(), role_order.desc(), ChatMessage.id.desc())
        .limit(19)
    ).all()
    prior_history = [{"role": m.role, "content": m.content} for m in reversed(prior)]

    def generate_rag_answer(request: GenerationRequest) -> GeneratedAnswer:
        combined_instruction = instruction + "\n\n" + request.system_instruction
        history = [
            *prior_history,
            {"role": "user", "content": request.user_prompt},
        ]
        return GeneratedAnswer(generate_tutor_reply(combined_instruction, history))

    # Retrieval and generation both complete before either half of the turn is
    # added to the session, so provider failures cannot persist a partial turn.
    try:
        teaching: TeachingResponse = orchestrate_tutoring(
            authenticated_student_id=student.id,
            session_owner_id=session.student_id,
            question=payload.message[:1000],
            topic=session.topic,
            language=language,
            level=level,
            retriever=VectorPassageRetriever(db, embedding_provider),
            generate=generate_rag_answer,
        )
    except EmbeddingError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail="Document retrieval is unavailable; no chat turn was saved.",
        ) from None
    reply = teaching.answer
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
    return TutorResponse(
        session_id=session_id,
        reply=reply,
        language=language,
        learning_level=level,
        citations=[TutorCitation(**citation.__dict__) for citation in teaching.citations],
        grounded=teaching.grounded,
        retrieval_used=teaching.retrieval_used,
    )
