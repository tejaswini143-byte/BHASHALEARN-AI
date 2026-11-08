"""Read-only evidence-backed per-topic student learning progress API."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import LearningAssessmentAttempt, LearningProgress, Student
from backend.app.db.session import get_db
from backend.app.services.adaptive_learning import normalize_topic, recommend

router = APIRouter(prefix="/progress", tags=["learning progress"])


class ProgressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    topic: str
    mastery_score: float
    attempts: int
    evidence_attempts: int
    correct_attempts: int
    incorrect_attempts: int
    ambiguous_attempts: int
    evidence_status: str
    last_assessed_at: datetime | None
    updated_at: datetime
    difficulty: str
    strategy: str
    recommendation: str
    reason: str
    revision_recommended: bool


def _response(item: LearningProgress, student_id: str, db: Session) -> ProgressResponse:
    attempts = db.scalars(
        select(LearningAssessmentAttempt.is_correct)
        .where(LearningAssessmentAttempt.student_id == student_id,
               LearningAssessmentAttempt.normalized_topic_key == item.normalized_topic_key,
               LearningAssessmentAttempt.is_correct.is_not(None))
        .order_by(LearningAssessmentAttempt.answered_at.desc(), LearningAssessmentAttempt.id.desc())
        .limit(5)
    ).all()
    policy = recommend(item.evidence_attempts, item.correct_attempts, item.incorrect_attempts,
                       tuple(bool(value) for value in reversed(attempts)))
    return ProgressResponse(
        id=item.id, topic=item.topic,
        mastery_score=item.mastery_score if item.evidence_attempts else 0.0,
        attempts=item.evidence_attempts, evidence_attempts=item.evidence_attempts,
        correct_attempts=item.correct_attempts, incorrect_attempts=item.incorrect_attempts,
        ambiguous_attempts=item.ambiguous_attempts, evidence_status=item.evidence_status,
        last_assessed_at=item.last_assessed_at, updated_at=item.updated_at,
        difficulty=policy.difficulty, strategy=policy.strategy, recommendation=policy.recommendation,
        reason=policy.reason, revision_recommended=policy.revision_recommended,
    )


@router.get("", response_model=list[ProgressResponse])
def list_progress(
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = (select(LearningProgress).where(LearningProgress.student_id == student.id)
            .order_by(LearningProgress.topic, LearningProgress.id).offset(offset).limit(limit))
    return [_response(item, student.id, db) for item in db.scalars(stmt).all()]


@router.get("/{topic}", response_model=ProgressResponse)
def get_progress(topic: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    key = normalize_topic(topic)
    progress = db.scalar(select(LearningProgress).where(
        LearningProgress.student_id == student.id, LearningProgress.normalized_topic_key == key
    ).order_by(LearningProgress.updated_at.desc(), LearningProgress.id.asc()))
    if progress is None:
        raise HTTPException(status_code=404, detail="Progress not found")
    return _response(progress, student.id, db)
