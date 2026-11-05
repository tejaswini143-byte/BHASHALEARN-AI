"""Authenticated per-topic student learning progress API."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session
from backend.app.api.auth import current_student
from backend.app.db.models import LearningProgress, Student, utc_now
from backend.app.db.session import get_db

router = APIRouter(prefix="/progress", tags=["learning progress"])

class ProgressUpdate(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    mastery_score: float = Field(ge=0, le=100, allow_inf_nan=False)
    attempts: int = Field(ge=0)

    @field_validator("topic")
    @classmethod
    def clean_topic(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Topic cannot be blank")
        return value

class ProgressResponse(ProgressUpdate):
    model_config = ConfigDict(from_attributes=True)
    id: str
    updated_at: datetime

@router.put("", response_model=ProgressResponse)
def upsert_progress(payload: ProgressUpdate, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    progress = db.scalar(select(LearningProgress).where(
        LearningProgress.student_id == student.id, LearningProgress.topic == payload.topic
    ))
    if progress is None:
        progress = LearningProgress(student_id=student.id, **payload.model_dump())
        db.add(progress)
    else:
        progress.mastery_score = payload.mastery_score
        progress.attempts = payload.attempts
        progress.updated_at = utc_now()
    db.commit()
    db.refresh(progress)
    return progress

@router.get("", response_model=list[ProgressResponse])
def list_progress(
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
):
    stmt = (select(LearningProgress).where(LearningProgress.student_id == student.id)
            .order_by(LearningProgress.topic, LearningProgress.id).offset(offset).limit(limit))
    return db.scalars(stmt).all()

@router.get("/{topic}", response_model=ProgressResponse)
def get_progress(topic: str, student: Student = Depends(current_student), db: Session = Depends(get_db)):
    progress = db.scalar(select(LearningProgress).where(
        LearningProgress.student_id == student.id, LearningProgress.topic == topic
    ))
    if progress is None:
        raise HTTPException(status_code=404, detail="Progress not found")
    return progress
