"""Authenticated student progress summaries backed by validated assessments."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import (
    LearningAssessmentAttempt,
    LearningProgress,
    LearningSession,
    Student,
    StudentPreferences,
)
from backend.app.db.session import get_db
from backend.app.services.adaptive_learning import choose_adaptation, mastery_category, normalize_topic

router = APIRouter(prefix="/progress", tags=["learning progress"])


class TopicProgressResponse(BaseModel):
    id: str
    topic: str
    topic_key: str
    mastery_score: float | None
    mastery_category: str
    attempts: int
    evidence_count: int
    correct_attempts: int
    incorrect_attempts: int
    recommended_difficulty: str
    teaching_strategy: str
    reason: str
    strengths: list[str]
    review_areas: list[str]
    updated_at: datetime | None


class RecentEvidenceResponse(BaseModel):
    assessment_id: str
    topic: str
    question: str
    outcome: str
    misconception_code: str | None
    feedback: str | None
    created_at: datetime


class ProgressSummaryResponse(BaseModel):
    topics: list[TopicProgressResponse]
    recent_evidence: list[RecentEvidenceResponse]


_MISCONCEPTION_NAMES = {
    "denominator_only": "Review why numerator and denominator must scale together.",
    "numerator_only": "Review why numerator and denominator must scale together.",
    "unequal_scaling": "Practice equivalent fractions with equal scaling.",
    "larger_edge": "Review how to compare candidate edge weights.",
    "not_connected": "Review which nodes are directly connected.",
    "not_minimum": "Practice selecting the smallest current edge weight.",
    "answer_error": "Review this concept with a worked example.",
}


def _recent_attempts(db: Session, student_id: str, topic_key: str, limit: int = 8) -> list[LearningAssessmentAttempt]:
    return list(db.scalars(
        select(LearningAssessmentAttempt)
        .where(
            LearningAssessmentAttempt.student_id == student_id,
            LearningAssessmentAttempt.topic_key == topic_key,
            LearningAssessmentAttempt.outcome.in_(("correct", "incorrect", "ambiguous")),
        )
        .order_by(LearningAssessmentAttempt.created_at.desc(), LearningAssessmentAttempt.id.desc())
        .limit(limit)
    ).all())


def _topic_response(
    topic: str,
    topic_key: str,
    progress: LearningProgress | None,
    recent: list[LearningAssessmentAttempt],
    preferred_level: str,
) -> TopicProgressResponse:
    adaptation = choose_adaptation(progress, recent, preferred_level)
    strengths: list[str] = []
    if progress and progress.correct_attempts >= 2:
        strengths.append("Repeated correct answers on objective checks.")
    active_misconceptions = []
    for item in recent:
        if item.outcome == "correct":
            break
        if item.outcome == "incorrect" and item.misconception_code in _MISCONCEPTION_NAMES:
            active_misconceptions.append(_MISCONCEPTION_NAMES[item.misconception_code])
    review_areas = list(dict.fromkeys(active_misconceptions))[:3]
    evidence = progress.evidence_count if progress else 0
    return TopicProgressResponse(
        id=progress.id if progress else topic_key,
        topic=topic,
        topic_key=topic_key,
        mastery_score=float(progress.mastery_score) if progress and evidence else None,
        mastery_category=mastery_category(progress),
        attempts=evidence,
        evidence_count=evidence,
        correct_attempts=progress.correct_attempts if progress else 0,
        incorrect_attempts=progress.incorrect_attempts if progress else 0,
        recommended_difficulty=adaptation.recommended_difficulty,
        teaching_strategy=adaptation.teaching_strategy,
        reason=adaptation.reason,
        strengths=strengths,
        review_areas=review_areas,
        updated_at=progress.updated_at if progress and evidence else None,
    )


def _owned_progress(db: Session, student_id: str, topic: str) -> tuple[str, str, LearningProgress]:
    display, key = normalize_topic(topic)
    progress = db.scalar(select(LearningProgress).where(
        LearningProgress.student_id == student_id,
        LearningProgress.topic_key == key,
    ))
    if progress is None:
        raise HTTPException(status_code=404, detail="Progress not found")
    return display, key, progress


@router.get("/summary", response_model=ProgressSummaryResponse)
def progress_summary(student: Student = Depends(current_student), db: Session = Depends(get_db)):
    preferences = db.get(StudentPreferences, student.id)
    preferred_level = preferences.learning_level if preferences else "beginner"
    profiles = db.scalars(select(LearningProgress).where(
        LearningProgress.student_id == student.id
    ).order_by(LearningProgress.updated_at.desc(), LearningProgress.topic_key).limit(100)).all()
    by_key = {item.topic_key: item for item in profiles}
    topics: dict[str, str] = {item.topic_key: item.topic for item in profiles}
    for session_topic in db.scalars(select(LearningSession.topic).where(
        LearningSession.student_id == student.id
    ).order_by(LearningSession.created_at.desc(), LearningSession.id.desc()).limit(100)).all():
        display, key = normalize_topic(session_topic)
        topics.setdefault(key, display)

    topic_rows = [
        _topic_response(topic, key, by_key.get(key), _recent_attempts(db, student.id, key), preferred_level)
        for key, topic in sorted(topics.items(), key=lambda item: item[1].casefold())[:100]
    ]
    attempts = db.scalars(
        select(LearningAssessmentAttempt)
        .where(
            LearningAssessmentAttempt.student_id == student.id,
            LearningAssessmentAttempt.outcome.in_(("correct", "incorrect", "ambiguous")),
        )
        .order_by(LearningAssessmentAttempt.created_at.desc(), LearningAssessmentAttempt.id.desc())
        .limit(20)
    ).all()
    topic_names = {key: topic for key, topic in topics.items()}
    return ProgressSummaryResponse(
        topics=topic_rows,
        recent_evidence=[RecentEvidenceResponse(
            assessment_id=item.id,
            topic=topic_names.get(item.topic_key, item.topic),
            question=item.question,
            outcome=item.outcome,
            misconception_code=item.misconception_code,
            feedback=item.feedback,
            created_at=item.submitted_at or item.created_at,
        ) for item in attempts],
    )


@router.put("", status_code=405)
def reject_client_mastery_updates(student: Student = Depends(current_student)):
    """Retain the legacy path but prohibit clients from setting mastery."""
    raise HTTPException(status_code=405, detail="Progress is updated only by authenticated assessment submissions.")


@router.get("", response_model=list[TopicProgressResponse])
def list_progress(
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    preferences = db.get(StudentPreferences, student.id)
    preferred_level = preferences.learning_level if preferences else "beginner"
    rows = db.scalars(
        select(LearningProgress)
        .where(LearningProgress.student_id == student.id)
        .order_by(LearningProgress.topic_key)
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        _topic_response(item.topic, item.topic_key, item, _recent_attempts(db, student.id, item.topic_key), preferred_level)
        for item in rows
    ]


@router.get("/{topic}", response_model=TopicProgressResponse)
def get_progress(topic: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    display, key, progress = _owned_progress(db, student.id, topic)
    preferences = db.get(StudentPreferences, student.id)
    return _topic_response(
        progress.topic or display,
        key,
        progress,
        _recent_attempts(db, student.id, key),
        preferences.learning_level if preferences else "beginner",
    )
