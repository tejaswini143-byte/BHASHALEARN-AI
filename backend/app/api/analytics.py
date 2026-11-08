"""Authenticated student-owned progress analytics API."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.app.api.auth import current_student
from backend.app.db.models import Student
from backend.app.db.session import get_db
from backend.app.services.progress_analytics import build_analytics

router = APIRouter(prefix="/analytics", tags=["student analytics"])


class AnalyticsResponse(BaseModel):
    range_days: int
    timezone: str
    date_rule: str
    overview: dict
    range_totals: dict
    trend: list[dict]
    topics: list[dict]
    subjects: list[dict]
    strengths: list[dict]
    improvement_areas: list[dict]
    mission: dict
    streak: dict
    recent_activity: list[dict]
    recommendations: list[dict]
    quiz_analytics: dict


@router.get("", response_model=AnalyticsResponse)
def get_analytics(
    range_days: Literal["7", "30", "90"] = Query(default="7"),
    student: Student = Depends(current_student),
    db: Session = Depends(get_db),
):
    """Return bounded analytics for the token owner; client student IDs are not accepted."""
    return build_analytics(db, student.id, int(range_days))
